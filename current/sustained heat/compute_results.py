"""
compute_results.py
===================
Loads the ESMI data, fits all models (Stage A binned bootstrap, Stage B
spline GLM, Stage C climate-zone-stratified models), and writes every
result out as CSV (+ a pickled Stage B model for later re-prediction at
a different temperature range without refitting).

This is the slow part -- run it once, then use make_plots.py as many
times as you like to adjust figure cosmetics without rerunning anything
here.

Install once:
    pip install pandas statsmodels patsy scipy pyarrow --break-system-packages
"""

import os
import pickle
import numpy as np
import pandas as pd
import statsmodels.api as sm
import patsy
from scipy import stats
from scipy.special import expit

# ----------------------------------------------------------------------
# CONFIG -- edit these for your own data / output location
# ----------------------------------------------------------------------
INPUT_CSVS = [
    os.path.join(os.path.expanduser("~"), "Library/CloudStorage/OneDrive-GeorgiaInstituteofTechnology/Research/Energy_resilience/01_data/processed", "station_518_forest_perc_50kmBu_district_climate_dummy_df.csv"),
]
OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "Library/CloudStorage/OneDrive-GeorgiaInstituteofTechnology/Research/Energy_resilience/01_data/processed", "temp_threshold")

TEMP_COL = "t2m"              # Kelvin in the source data
TEMP_UNITS = "kelvin"         # "kelvin" or "celsius"
OUTCOME_COL = "pct_blackout"  # continuous [0,1] fraction
STATION_COL = "station_id"
CLIMATE_ZONE_COL = "climate_zone_code"
RAW_PRECIP_COL = "tp"         # ERA5-Land ACCUMULATED precip (metres, running total since 00:00 each day)
PRECIP_COL = "log_rain"       # derived below: log(1 + hourly rain in mm). Used as the rain control in all models.
WIND_COL = "wind_speed"
DATETIME_COL = "datetime"

N_BOOT = 200              # bootstrap reps for Stage A
SPLINE_DF = 5              # degrees of freedom for the pooled temperature spline
SUBSAMPLE_EVERY_N = 1       # 1 = use every row (full data) for Stage B. Raise (e.g. 10) if you hit a memory error.
PRED_N_SAMPLE = 100_000_000  # rows used for the Stage B clustered-SE fit. Set far above your row count so min(n_sample, len(df)) always resolves to the full dataset.
T_GRID_QUANTILES = (0.01, 0.99)  # trims the sparsest 1% of temperature at each tail from the predicted curve


def out_path(name):
    return os.path.join(OUTPUT_DIR, name)


# ----------------------------------------------------------------------
# LOAD
# ----------------------------------------------------------------------
def add_hourly_rain(df):
    """The raw `tp` column is NOT hourly rainfall: it is a running total since
    00:00 that resets each day (mean `tp` climbs from ~0.11 mm at 01:00 to
    ~3.1 mm at 23:00, and the 00:00 row holds the previous day's 24h total).
    Recover hourly rain by differencing consecutive hours within a station:
        hour 01      -> rain = tp                    (accumulation just restarted)
        hours 02-23  -> rain = tp - tp(previous hour)
        hour 00      -> rain = tp - tp(previous 23:00)  (00:00 holds the day's total)
    Differencing is only valid when the previous row is exactly 1 hour earlier;
    otherwise (missing hours) rain is set to NaN and those rows are excluded
    from any model that uses rain. Returns df sorted by station and time."""
    df = df.sort_values([STATION_COL, DATETIME_COL]).reset_index(drop=True)
    tp_mm = df[RAW_PRECIP_COL].to_numpy(dtype="float64") * 1000.0
    hour = df[DATETIME_COL].dt.hour.to_numpy()
    stn = df[STATION_COL].to_numpy()
    t = df[DATETIME_COL].to_numpy()

    prev_ok = np.zeros(len(df), dtype=bool)
    prev_ok[1:] = (stn[1:] == stn[:-1]) & ((t[1:] - t[:-1]) == np.timedelta64(1, "h"))
    prev_tp = np.roll(tp_mm, 1)

    rain = np.where(hour == 1, tp_mm, np.where(prev_ok, tp_mm - prev_tp, np.nan))
    rain = np.where(np.isnan(rain), np.nan, np.maximum(rain, 0.0))  # clip tiny negative float noise

    df["rain_mm"] = rain.astype("float32")
    df[PRECIP_COL] = np.log1p(df["rain_mm"]).astype("float32")
    return df.drop(columns=[RAW_PRECIP_COL])


def load_data():
    usecols = [DATETIME_COL, OUTCOME_COL, TEMP_COL, RAW_PRECIP_COL, WIND_COL,
               STATION_COL, CLIMATE_ZONE_COL]
    frames = [pd.read_csv(p, parse_dates=[DATETIME_COL], usecols=usecols)
              for p in INPUT_CSVS]
    df = pd.concat(frames, ignore_index=True)

    df["t2m_c"] = (df[TEMP_COL] - 273.15 if TEMP_UNITS == "kelvin" else df[TEMP_COL]).astype("float32")
    df[OUTCOME_COL] = df[OUTCOME_COL].astype("float32")
    df[WIND_COL] = df[WIND_COL].astype("float32")
    df[STATION_COL] = df[STATION_COL].astype("int32")
    df[CLIMATE_ZONE_COL] = df[CLIMATE_ZONE_COL].astype("category")
    df["month"] = df[DATETIME_COL].dt.month.astype("int8")
    df = add_hourly_rain(df)
    return df


# ----------------------------------------------------------------------
# STAGE A: binned exposure-response with station-clustered bootstrap CI
# ----------------------------------------------------------------------
def stage_a_binned(df, bin_width=2, min_n=2000):
    df = df.copy()
    df["t2m_bin"] = ((df["t2m_c"] // bin_width) * bin_width).astype("int16")

    bin_counts = df["t2m_bin"].value_counts()
    valid_bins = bin_counts[bin_counts > min_n].index
    df_b = df[df["t2m_bin"].isin(valid_bins)][[STATION_COL, "t2m_bin", OUTCOME_COL]]

    bins_sorted = sorted(df_b["t2m_bin"].unique())
    grp = df_b.groupby([STATION_COL, "t2m_bin"], observed=True)[OUTCOME_COL].agg(["sum", "count"]).reset_index()
    pivot_sum = grp.pivot(index=STATION_COL, columns="t2m_bin", values="sum").fillna(0).reindex(columns=bins_sorted, fill_value=0)
    pivot_cnt = grp.pivot(index=STATION_COL, columns="t2m_bin", values="count").fillna(0).reindex(columns=bins_sorted, fill_value=0)

    sum_vals, cnt_vals = pivot_sum.values, pivot_cnt.values
    n_stations = sum_vals.shape[0]

    rng = np.random.default_rng(42)
    boot = np.zeros((N_BOOT, len(bins_sorted)))
    for i in range(N_BOOT):
        idx = rng.integers(0, n_stations, size=n_stations)
        boot[i] = sum_vals[idx].sum(axis=0) / cnt_vals[idx].sum(axis=0)

    point = sum_vals.sum(axis=0) / cnt_vals.sum(axis=0)
    return pd.DataFrame({
        "t2m_bin_c": bins_sorted,
        "mean_pct_blackout": point,
        "ci_lo": np.percentile(boot, 2.5, axis=0),
        "ci_hi": np.percentile(boot, 97.5, axis=0),
        "n_station_hours": cnt_vals.sum(axis=0).astype(int),
    })


# ----------------------------------------------------------------------
# STAGE B: confirmatory spline GLM + likelihood-ratio test + predicted curve
# ----------------------------------------------------------------------
def subsample_per_station(df, every_n):
    df = df.sort_values(STATION_COL).reset_index(drop=True)
    row_in_group = df.groupby(STATION_COL, observed=True).cumcount()
    return df[row_in_group % every_n == 0].reset_index(drop=True)


def stage_b_lr_test(df_sample):
    """Likelihood-ratio test: does the nonlinear spline fit better than a linear temperature term?"""
    f_spline = (f"{OUTCOME_COL} ~ cr(t2m_c, df={SPLINE_DF}, constraints='center') "
                f"+ {PRECIP_COL} + {WIND_COL} + C(month) + C({CLIMATE_ZONE_COL})")
    f_linear = (f"{OUTCOME_COL} ~ t2m_c + {PRECIP_COL} + {WIND_COL} + C(month) + C({CLIMATE_ZONE_COL})")

    m_spline = sm.formula.glm(f_spline, df_sample, family=sm.families.Binomial()).fit()
    m_linear = sm.formula.glm(f_linear, df_sample, family=sm.families.Binomial()).fit()

    lr_stat = 2 * (m_spline.llf - m_linear.llf)
    df_diff = m_spline.df_model - m_linear.df_model
    p_value = stats.chi2.sf(lr_stat, df_diff)
    return lr_stat, df_diff, p_value, f_spline


def stage_b_predict_curve(df_sample, formula_rhs, n_sample=PRED_N_SAMPLE, random_state=1,
                           t_grid_quantiles=T_GRID_QUANTILES, save_model_path=None):
    """Fit with cluster-robust SEs on a tractable subsample, then predict an
    adjusted exposure-response curve (holding other covariates at representative values).

    save_model_path: if given, saves what's needed to RE-PREDICT at a new
    temperature range later without refitting -- but NOT by pickling the
    patsy design_info directly (patsy's DesignInfo objects can't be pickled,
    see https://github.com/pydata/patsy/issues/26). Instead we save the
    plain-array coefficients/covariance (pickle-safe) as save_model_path,
    plus the exact training sample used (as a parquet next to it, same
    name with _fit_sample.parquet suffix) so a future script can cheaply
    REBUILD the design_info by rerunning patsy.dmatrices on that same
    sample (fast matrix construction, not a model fit) before predicting
    on the new grid."""
    df_fit = df_sample.sample(n=min(n_sample, len(df_sample)), random_state=random_state)

    rhs = formula_rhs.split("~", 1)[1] if "~" in formula_rhs else formula_rhs
    y, X = patsy.dmatrices(f"{OUTCOME_COL} ~ {rhs}", df_fit, return_type="dataframe")
    model = sm.GLM(y, X, family=sm.families.Binomial())
    res = model.fit(cov_type="cluster", cov_kwds={"groups": df_fit[STATION_COL]})

    if save_model_path:
        fit_sample_path = save_model_path.replace(".pkl", "_fit_sample.parquet")
        df_fit.to_parquet(fit_sample_path)
        with open(save_model_path, "wb") as f:
            pickle.dump({"params": res.params, "cov_params": res.cov_params(),
                         "formula_rhs": rhs, "fit_sample_path": fit_sample_path,
                         "precip_median": df_sample[PRECIP_COL].median(),
                         "wind_median": df_sample[WIND_COL].median(),
                         "modal_zone": df_sample[CLIMATE_ZONE_COL].mode().iloc[0],
                         "zone_categories": df_sample[CLIMATE_ZONE_COL].cat.categories}, f)

    lo_q, hi_q = t_grid_quantiles
    t_grid = np.arange(df_sample["t2m_c"].quantile(lo_q), df_sample["t2m_c"].quantile(hi_q), 0.5)
    modal_zone = df_sample[CLIMATE_ZONE_COL].mode().iloc[0]
    pred_df = pd.DataFrame({
        "t2m_c": t_grid,
        PRECIP_COL: df_sample[PRECIP_COL].median(),
        WIND_COL: df_sample[WIND_COL].median(),
        "month": 6,
        CLIMATE_ZONE_COL: pd.Categorical([modal_zone] * len(t_grid), categories=df_sample[CLIMATE_ZONE_COL].cat.categories),
    })
    Xp = np.asarray(patsy.build_design_matrices([X.design_info], pred_df)[0])

    eta = Xp @ res.params.values
    se_eta = np.sqrt(np.einsum("ij,jk,ik->i", Xp, res.cov_params().values, Xp))
    pred, lo, hi = expit(eta), expit(eta - 1.96 * se_eta), expit(eta + 1.96 * se_eta)

    out = pd.DataFrame({"t2m_c": t_grid, "pred": pred, "lo": lo, "hi": hi})

    deriv = np.gradient(pred, t_grid)
    mask = (t_grid > 15) & (t_grid < 40)
    steepest_t = float(t_grid[mask][np.argmax(deriv[mask])]) if mask.any() else None
    return out, res, steepest_t


# ----------------------------------------------------------------------
# STAGE B+: formal interaction test (does the curve SHAPE really differ by zone?)
# and a supplementary regression coefficient table
# ----------------------------------------------------------------------
def stage_b_zone_interaction_test(df_sample):
    """LR test: does letting the temperature spline's SHAPE vary by climate
    zone (interaction) fit significantly better than assuming the same shape
    for all zones and only letting the level shift (additive, used in the
    main Stage B model)? This is the formal backing for Figure 2 -- confirms
    the zone-specific curves differ by more than sampling noise."""
    f_additive = (f"{OUTCOME_COL} ~ cr(t2m_c, df={SPLINE_DF}, constraints='center') "
                  f"+ {PRECIP_COL} + {WIND_COL} + C(month) + C({CLIMATE_ZONE_COL})")
    f_interact = (f"{OUTCOME_COL} ~ cr(t2m_c, df={SPLINE_DF}, constraints='center') * C({CLIMATE_ZONE_COL}) "
                  f"+ {PRECIP_COL} + {WIND_COL} + C(month)")

    m_additive = sm.formula.glm(f_additive, df_sample, family=sm.families.Binomial()).fit()
    m_interact = sm.formula.glm(f_interact, df_sample, family=sm.families.Binomial()).fit()

    lr_stat = 2 * (m_interact.llf - m_additive.llf)
    df_diff = m_interact.df_model - m_additive.df_model
    p_value = stats.chi2.sf(lr_stat, df_diff)
    return lr_stat, df_diff, p_value


def stage_b_coef_table(df_sample, formula_rhs, n_sample=PRED_N_SAMPLE, random_state=1):
    """Supplementary table: full coefficient estimates, cluster-robust SEs,
    z, p-values and 95% CI for the main (additive) Stage B model. Individual
    spline-term coefficients aren't meaningfully interpretable alone -- the
    LR test and the plotted curve are what carry the nonlinearity finding."""
    df_fit = df_sample.sample(n=min(n_sample, len(df_sample)), random_state=random_state)
    rhs = formula_rhs.split("~", 1)[1] if "~" in formula_rhs else formula_rhs
    y, X = patsy.dmatrices(f"{OUTCOME_COL} ~ {rhs}", df_fit, return_type="dataframe")
    res = sm.GLM(y, X, family=sm.families.Binomial()).fit(
        cov_type="cluster", cov_kwds={"groups": df_fit[STATION_COL]})

    def clean_label(t):
        if t.startswith("cr(t2m_c"):
            return f"Temperature spline term {t.split('[')[-1].rstrip(']')}"
        if t.startswith("C(month)"):
            return f"Month = {t.split('T.')[-1].rstrip(']')}"
        if t.startswith(f"C({CLIMATE_ZONE_COL})"):
            return f"Climate zone = {t.split('T.')[-1].rstrip(']')}"
        return t

    tbl = pd.DataFrame({
        "term": res.params.index,
        "coef": res.params.values,
        "std_err": res.bse.values,
        "z": res.tvalues.values,
        "p_value": res.pvalues.values,
        "ci_lower": res.conf_int()[0].values,
        "ci_upper": res.conf_int()[1].values,
    })
    tbl["label"] = tbl["term"].apply(clean_label)
    tbl = tbl[["label", "term", "coef", "std_err", "z", "p_value", "ci_lower", "ci_upper"]]

    meta = pd.DataFrame([{
        "n_obs": int(res.nobs),
        "n_stations_clustered": df_fit[STATION_COL].nunique(),
        "pseudo_r_sq_deviance": 1 - res.deviance / res.null_deviance,
    }])
    return tbl, meta


# ----------------------------------------------------------------------
# STAGE C: climate-zone-stratified curves (does the threshold shift by zone?)
# ----------------------------------------------------------------------
def stage_c_by_zone(df, spline_df=4, every_n=1, fit_n_sample=PRED_N_SAMPLE, min_rows=5000, min_stations=2):
    """Fit a separate spline GLM per climate zone and return each zone's
    predicted curve + its steepest-slope ('threshold') temperature.
    Zones with few stations will have noisier/overfit curves -- check
    station counts before trusting any wiggle in the curve shape."""
    df = df.dropna(subset=[PRECIP_COL])   # rows where hourly rain couldn't be recovered
    results = {}
    for zone in df[CLIMATE_ZONE_COL].cat.categories:
        sub = df[df[CLIMATE_ZONE_COL] == zone].copy()
        n_stations = sub[STATION_COL].nunique()
        if len(sub) < min_rows or n_stations < min_stations:
            print(f"  {zone}: skipped (n={len(sub)}, stations={n_stations})")
            continue

        sub = sub.sort_values(STATION_COL)
        row_in_group = sub.groupby(STATION_COL, observed=True).cumcount()
        sub_s = sub[row_in_group % every_n == 0].reset_index(drop=True)
        fit_sample = sub_s.sample(n=min(len(sub_s), fit_n_sample), random_state=1)

        formula_rhs = f"cr(t2m_c, df={spline_df}, constraints='center') + {PRECIP_COL} + {WIND_COL} + C(month)"
        y, X = patsy.dmatrices(f"{OUTCOME_COL} ~ {formula_rhs}", fit_sample, return_type="dataframe")
        res = sm.GLM(y, X, family=sm.families.Binomial()).fit(
            cov_type="cluster", cov_kwds={"groups": fit_sample[STATION_COL]})

        t_grid = np.arange(sub_s["t2m_c"].quantile(0.02), sub_s["t2m_c"].quantile(0.98), 0.5)
        pred_df = pd.DataFrame({
            "t2m_c": t_grid,
            PRECIP_COL: sub_s[PRECIP_COL].median(),
            WIND_COL: sub_s[WIND_COL].median(),
            "month": 6,
        })
        Xp = np.asarray(patsy.build_design_matrices([X.design_info], pred_df)[0])
        eta = Xp @ res.params.values
        se = np.sqrt(np.einsum("ij,jk,ik->i", Xp, res.cov_params().values, Xp))
        pred = expit(eta)
        steepest_t = float(t_grid[np.argmax(np.gradient(pred, t_grid))])

        results[zone] = pd.DataFrame({
            "t2m_c": t_grid, "pred": pred,
            "lo": expit(eta - 1.96 * se), "hi": expit(eta + 1.96 * se),
        })
        print(f"  {zone}: n={len(sub):,} ({n_stations} stations), steepest slope ~{steepest_t:.1f}C")
    return results


# ----------------------------------------------------------------------
# MAIN -- computes everything, writes CSVs (+ model pickle) only. No plots.
# ----------------------------------------------------------------------
if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading data...")
    df = load_data()
    print(f"  {len(df):,} rows, {df[STATION_COL].nunique()} stations")

    print("\n--- Stage A: binned exposure-response ---")
    stage_a_result = stage_a_binned(df)
    stage_a_result.to_csv(out_path("stage_a_binned_result.csv"), index=False)
    print(stage_a_result.to_string(index=False))

    print("\n--- Stage B: confirmatory spline GLM ---")
    df_sample = subsample_per_station(df.dropna(subset=[PRECIP_COL]), SUBSAMPLE_EVERY_N)
    print(f"  Using {len(df_sample):,} rows (every {SUBSAMPLE_EVERY_N}th per station) for fitting")

    lr_stat, df_diff, p_value, formula = stage_b_lr_test(df_sample)
    print(f"  LR test (nonlinear vs. linear): stat={lr_stat:.2f}, df={df_diff:.0f}, p={p_value:.3g}")

    pred_curve, res, steepest_t = stage_b_predict_curve(
        df_sample, formula, save_model_path=out_path("stage_b_model.pkl"))
    pred_curve.to_csv(out_path("stage_b_predicted_curve.csv"), index=False)
    print(f"  Steepest-slope (approx. threshold) temperature: {steepest_t:.1f}°C" if steepest_t else "  (no clear steepest point found)")

    print("\n--- Stage B+: formal temp x climate-zone interaction test ---")
    lr_stat_z, df_diff_z, p_value_z = stage_b_zone_interaction_test(df_sample)
    print(f"  LR test (does curve SHAPE differ by zone?): stat={lr_stat_z:.2f}, df={df_diff_z:.0f}, p={p_value_z:.3g}")
    pd.DataFrame([{"lr_stat": lr_stat_z, "df": df_diff_z, "p_value": p_value_z}]).to_csv(
        out_path("stage_b_zone_interaction_test.csv"), index=False)

    print("\n--- Stage B+: supplementary coefficient table ---")
    coef_tbl, coef_meta = stage_b_coef_table(df_sample, formula)
    coef_tbl.to_csv(out_path("stage_b_coefficient_table.csv"), index=False)
    coef_meta.to_csv(out_path("stage_b_model_meta.csv"), index=False)
    print(coef_tbl.round(4).to_string(index=False))
    print(coef_meta.to_string(index=False))

    print("\n--- Stage C: climate-zone-stratified thresholds ---")
    zone_results = stage_c_by_zone(df)
    for zone, r in zone_results.items():
        r.to_csv(out_path(f"stage_c_{zone}.csv"), index=False)

    print("\nDone. CSVs (+ stage_b_model.pkl) written to:", OUTPUT_DIR)
    print("Now run make_plots.py to generate figures -- it only reads these "
          "CSVs, so you can rerun it freely to tweak plot cosmetics without "
          "ever refitting.")
