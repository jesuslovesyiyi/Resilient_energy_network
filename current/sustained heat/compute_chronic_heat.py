"""
compute_chronic_heat.py
========================
SUSTAINED HEAT: does heat that persists over several days or weeks change the
blackout rate more than a single hot day does?

Works on STATION-DAYS (hourly rows collapsed to one row per station per day):
multi-day exposure needs consecutive days, and the daily table is small enough to
analyse in full with no subsampling.

Clock: `datetime` is UTC (temperature peaks at hour 9 as stored = mid-afternoon in
India). A UTC day runs 05:30 -> 05:30 local, which keeps the hot afternoon in the
middle of each day, so days are used as they are.

Outcome  : daily mean of pct_blackout (fraction of the day without power).
Exposure : daily MAXIMUM of the hourly ERA5 temperature (deg C).

DESIGN
  Fixed effects (main): station x calendar-month + year. Each station is compared only
  with ITSELF in the same month, so hot places, hot seasons and station quality drop
  out. What is left is "hotter than usual for that station and month".
  Fixed effects (robustness): station + month + year.
  Standard errors are clustered by station.

  Controls (none use future information): log rain today and 1,2,3 days ago, mean wind
  today and yesterday, diurnal temperature range (tmax-tmin) today and yesterday.
  The diurnal range is a cloud/storm proxy. Without these controls, outages on days
  that cool down after a hot day (storm and front days) contaminate the heat signal.

ANALYSES
  1. Window length   : effect of a +1C rise in the AVERAGE tmax over the last k days
                       (k = 1,2,3,5,7,10,14,21,30), one regression per k. If heat
                       accumulates, the effect grows with k.
                         variants: (a) main controls, (b) + rain over the same window,
                                   (c) + only windows with little rain.
                       Formal test that a k-day window differs from a 1-day window.
  2. Distributed lag : tmax today and each of the previous 14 days together, with a
                       placebo using FUTURE temperatures (should be ~0).
  3. Heterogeneity   : the 1-day and 14-day effects by season and climate zone.
  4. Hot-day runs    : length of the current run of consecutive hot days, for a relative
                       definition (hottest 10% of days for that station and time of year)
                       and absolute ones (>=38C, >=40C).

Run order: set paths in compute_results.py (keep both files in one folder), run this
file, then plot_chronic_heat.py.
"""

import os
import warnings
import numpy as np
import pandas as pd
from scipy.stats import chi2, norm

import compute_results as cres   # NOT "cr": keeps patsy-style names free
from compute_results import (load_data, out_path, OUTCOME_COL, STATION_COL,
                              CLIMATE_ZONE_COL, WIND_COL, DATETIME_COL)

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
MIN_HOURS_PER_DAY = 20          # a day needs at least this many observed hours
MIN_DAYS_PER_STATION = 90       # drop stations with fewer complete days
WINDOWS = [1, 2, 3, 5, 7, 10, 14, 21, 30]
COMMON_MAX_WINDOW = 14          # windows up to this length share one common sample
MIN_WINDOW_COVERAGE = 0.70      # a window mean needs this share of its days observed
DRY_WINDOW_MM = 0.5             # "dry window" = mean daily rain over the window below this (mm/day)
MAX_LAG = 14                    # distributed-lag length (days)
DIFF_TESTS = [(1, 3), (1, 7), (1, 14)]   # window pairs compared with a formal test
HET_WINDOWS = [1, 14]
HET_MIN_STATIONS = 8            # only report climate zones with at least this many stations
SEASONS = {"Mar-Jun (pre-monsoon heat)": [3, 4, 5, 6], "Jul-Sep (monsoon)": [7, 8, 9],
           "Oct-Feb (post-monsoon / winter)": [10, 11, 12, 1, 2]}
PCT_HOT = 90                    # relative hot-day definition: top (100-PCT_HOT)% for station x time of year
DOY_HALF_WINDOW = 7             # +/- days around the calendar day used for that percentile
MIN_OBS_FOR_THRESHOLD = 40      # need at least this many days in the window to set a threshold
HOT_DEFS = [("rel_p90", "relative", None), ("abs_38", "absolute", 38.0), ("abs_40", "absolute", 40.0)]
RUN_LABELS = ["1", "2", "3", "4-5", "6-9", "10+"]
MIN_DAYS_IN_RUN_CATEGORY = 300  # categories with fewer station-days are dropped from the output

CTRL = ["lr0", "lr1", "lr2", "lr3", "wind", "wind1", "dtr", "dtr1"]


# ----------------------------------------------------------------------
# DAILY TABLE
# ----------------------------------------------------------------------
def build_daily(df):
    d = df.copy()
    d["date"] = d[DATETIME_COL].dt.floor("D")
    g = d.groupby([STATION_COL, "date"], observed=True)
    daily = g.agg(n_hours=(OUTCOME_COL, "size"), blk=(OUTCOME_COL, "mean"),
                  tmax=("t2m_c", "max"), tmin=("t2m_c", "min"), rain=("rain_mm", "sum"),
                  wind=(WIND_COL, "mean"), zone=(CLIMATE_ZONE_COL, "first")).reset_index()
    daily["zone"] = daily["zone"].astype(str)
    daily = daily[daily["n_hours"] >= MIN_HOURS_PER_DAY]
    n_days = daily.groupby(STATION_COL)["date"].transform("size")
    daily = daily[n_days >= MIN_DAYS_PER_STATION].copy()
    for c in ("blk", "tmax", "tmin", "rain", "wind"):
        daily[c] = daily[c].astype("float64")
    return daily.reset_index(drop=True)


def to_full_grid(daily):
    """One row per calendar day between each station's first and last observed day.
    Days with no monitor data are NaN, so that 'k days ago' really means k calendar days."""
    parts = []
    for s, g in daily.groupby(STATION_COL):
        idx = pd.date_range(g["date"].min(), g["date"].max(), freq="D")
        h = g.set_index("date").reindex(idx).rename_axis("date").reset_index()
        h[STATION_COL] = s
        parts.append(h)
    grid = pd.concat(parts, ignore_index=True)
    grid["zone"] = grid.groupby(STATION_COL)["zone"].transform(lambda x: x.dropna().iloc[0])
    grid["observed"] = grid["blk"].notna()
    return grid


def shifted(grid, col, k):
    return grid.groupby(STATION_COL, sort=False)[col].shift(k).to_numpy()


def lag_matrix(grid, col, max_lag):
    """N x (max_lag+1) array: column k holds `col` k calendar days earlier (same station)."""
    return np.column_stack([shifted(grid, col, k) for k in range(max_lag + 1)])


def window_mean(M, k):
    """Mean over the last k days (columns 0..k-1), requiring MIN_WINDOW_COVERAGE of them."""
    W = M[:, :k]
    n_obs = np.sum(~np.isnan(W), axis=1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        m = np.nanmean(W, axis=1)
    m[n_obs < max(MIN_WINDOW_COVERAGE * k, 1)] = np.nan
    return m


def add_features(grid):
    T = lag_matrix(grid, "tmax", 30)
    Rm = lag_matrix(grid, "rain", 30)
    grid["dtr"] = grid["tmax"] - grid["tmin"]
    grid["lr0"] = np.log1p(grid["rain"])
    for k in (1, 2, 3):
        grid[f"lr{k}"] = np.log1p(Rm[:, k])
    grid["wind1"] = shifted(grid, "wind", 1)
    grid["dtr1"] = shifted(grid, "dtr", 1)
    for k in range(MAX_LAG + 1):
        grid[f"t_l{k}"] = T[:, k]
    for k in (1, 2, 3):
        grid[f"t_f{k}"] = shifted(grid, "tmax", -k)      # FUTURE temperatures: placebo only
    for k in WINDOWS:
        grid[f"S{k}"] = window_mean(T, k)                         # mean tmax over the last k days
        grid[f"RW{k}"] = np.log1p(window_mean(Rm, k))             # log(1 + mean daily rain mm) over the window
        grid[f"RWmm{k}"] = np.expm1(grid[f"RW{k}"])
    return grid


# ----------------------------------------------------------------------
# ESTIMATION: within-estimator, cluster-robust by station (with influence functions)
# ----------------------------------------------------------------------
class Fit:
    def __init__(self, params, cov, n, n_clusters, psi, clusters):
        self.params, self.cov, self.n, self.n_clusters = params, cov, n, n_clusters
        self.psi, self.clusters = psi, clusters       # psi: G x K cluster influence of each coefficient


def fe_ols(d, ycol, xcols, fe="station_month"):
    """Within-estimator, cluster-robust SEs by station (same small-sample correction as
    statsmodels). fe='station_month': demean by station x calendar-month, year dummies added.
    fe='station': demean by station, month and year dummies added."""
    d = d.reset_index(drop=True)
    month = d["date"].dt.month
    extra = pd.get_dummies(d["date"].dt.year, prefix="yr", drop_first=True).astype("float64")
    if fe == "station":
        extra = pd.concat([extra, pd.get_dummies(month, prefix="mo", drop_first=True).astype("float64")], axis=1)
        grp = pd.factorize(d[STATION_COL])[0]
    else:
        grp = pd.factorize(d[STATION_COL].astype(str) + "_" + month.astype(str))[0]
    X = pd.concat([d[xcols], extra], axis=1)
    names = list(X.columns)
    Xd = (X - X.groupby(grp).transform("mean")).to_numpy()
    yd = (d[ycol] - d[ycol].groupby(grp).transform("mean")).to_numpy()
    keep = Xd.std(axis=0) > 1e-10          # e.g. a year dummy with no variation inside any group
    for i, n in enumerate(names):
        if not keep[i] and n in xcols:
            raise ValueError(f"regressor {n} has no within-group variation")
    Xd, names = Xd[:, keep], [n for n, k_ in zip(names, keep) if k_]
    stn_ids = np.sort(d[STATION_COL].unique())
    clus = np.searchsorted(stn_ids, d[STATION_COL].to_numpy())
    N, K = Xd.shape
    G = len(stn_ids)
    XtX_inv = np.linalg.inv(Xd.T @ Xd)
    beta = XtX_inv @ (Xd.T @ yd)
    e = yd - Xd @ beta
    scores = np.zeros((G, K))
    np.add.at(scores, clus, Xd * e[:, None])
    psi = scores @ XtX_inv
    corr = (G / (G - 1)) * ((N - 1) / (N - K))
    cov = corr * (psi.T @ psi)
    return Fit(pd.Series(beta, index=names), pd.DataFrame(cov, index=names, columns=names),
               int(N), int(G), pd.DataFrame(psi, index=stn_ids, columns=names), stn_ids)


def wald(fit, names):
    b = fit.params[names].to_numpy()
    V = fit.cov.loc[names, names].to_numpy()
    st = float(b @ np.linalg.solve(V, b))
    return st, len(names), float(chi2.sf(st, len(names)))


def lincomb(fit, weights):
    names = list(weights)
    w = np.array([weights[n] for n in names])
    est = float(w @ fit.params[names].to_numpy())
    se = float(np.sqrt(w @ fit.cov.loc[names, names].to_numpy() @ w))
    return est, se


def diff_between_fits(fa, ca, fb, cb):
    """Difference of coefficient `cb` in fit B minus `ca` in fit A when both come from the SAME
    stations (clusters), using the clusters' joint influence. Returns (diff, se, p)."""
    assert np.array_equal(fa.clusters, fb.clusters), "fits must use the same stations"
    G, Na, Nb = fa.n_clusters, fa.n, fb.n
    Ka, Kb = len(fa.params), len(fb.params)
    corr = (G / (G - 1)) * ((Na - 1) / (Na - Ka))   # same sample size/regressors count scale as in fe_ols
    diff = float(fb.params[cb] - fa.params[ca])
    psi_d = fb.psi[cb].to_numpy() - fa.psi[ca].to_numpy()
    se = float(np.sqrt(corr * np.sum(psi_d ** 2)))
    return diff, se, float(2 * norm.sf(abs(diff / se)))


def tidy(fit, names, labels=None):
    rows = []
    for i, n in enumerate(names):
        se = float(np.sqrt(fit.cov.loc[n, n]))
        c = float(fit.params[n])
        rows.append({"term": n, "label": labels[i] if labels else n, "coef": c, "se": se,
                     "lo": c - 1.96 * se, "hi": c + 1.96 * se})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# HOT-DAY DEFINITIONS AND RUN LENGTHS
# ----------------------------------------------------------------------
def relative_threshold(grid):
    """Per-row threshold = PCT_HOT percentile of tmax for that station within +/-
    DOY_HALF_WINDOW days of the same calendar day (all years pooled)."""
    thr = np.full(len(grid), np.nan)
    doy_all = grid["date"].dt.dayofyear.to_numpy()
    tmax_all = grid["tmax"].to_numpy()
    for s, idx in grid.groupby(STATION_COL, sort=False).indices.items():
        doy, t = doy_all[idx], tmax_all[idx]
        ok = ~np.isnan(t)
        doy_o, t_o = doy[ok], t[ok]
        table = {}
        for dd in np.unique(doy):
            gap = np.abs(doy_o - dd)
            gap = np.minimum(gap, 366 - gap)
            vals = t_o[gap <= DOY_HALF_WINDOW]
            table[dd] = np.percentile(vals, PCT_HOT) if len(vals) >= MIN_OBS_FOR_THRESHOLD else np.nan
        thr[idx] = [table[x] for x in doy]
    return thr


def run_lengths(grid, hot):
    """Consecutive hot days ending today. hot: 1 hot, 0 not hot, NaN unknown.
    0 = not hot. NaN = unknown: today's threshold undefined, or the run reaches back to an
    unobserved day so its true length is censored (stays NaN until a not-hot day resets it)."""
    out = np.full(len(grid), np.nan)
    for s, idx in grid.groupby(STATION_COL, sort=False).indices.items():
        h = hot[idx]
        prev = np.nan
        res = np.full(len(idx), np.nan)
        for i, v in enumerate(h):
            if np.isnan(v):
                prev = np.nan
                continue
            if v == 0:
                res[i] = 0.0
                prev = 0.0
            else:
                res[i] = prev + 1.0 if not np.isnan(prev) else np.nan
                prev = res[i]
        out[idx] = res
    return out


def run_category(r):
    cat = np.full(len(r), np.nan)
    ok = ~np.isnan(r)
    rr = r[ok]
    cat[ok] = np.where(rr == 0, 0, np.where(rr == 1, 1, np.where(rr == 2, 2, np.where(rr == 3, 3,
              np.where(rr <= 5, 4, np.where(rr <= 9, 5, 6))))))
    return cat


# ----------------------------------------------------------------------
def win_ctrl(k):
    """Rain over the same k-day window as an extra control. For k=1 that is today's rain,
    already in CTRL (adding it again makes the regression singular)."""
    return [] if k == 1 else [f"RW{k}"]


def window_sample(obs, k, common):
    cols = [f"S{k}", f"RW{k}", "blk"] + CTRL
    d = obs.dropna(subset=cols)
    if k <= COMMON_MAX_WINDOW:
        d = d.dropna(subset=common)
    return d


def main():
    os.makedirs(cres.OUTPUT_DIR, exist_ok=True)
    log = []

    print("Loading hourly data...")
    df = load_data()
    n_hours_total = len(df)
    daily = build_daily(df)
    del df
    print(f"  {n_hours_total:,} hourly rows -> {len(daily):,} complete station-days, "
          f"{daily[STATION_COL].nunique()} stations")
    log += [("hourly rows", n_hours_total),
            (f"complete station-days (>= {MIN_HOURS_PER_DAY} h) at stations with >= {MIN_DAYS_PER_STATION} days", len(daily))]

    grid = add_features(to_full_grid(daily))
    log += [("calendar days in station spans (incl. unobserved)", len(grid)),
            ("share of those days observed", float(grid["observed"].mean()))]
    obs = grid[grid["observed"]].copy()
    common = [f"t_l{k}" for k in range(MAX_LAG + 1)]     # complete tmax lags 0-14 define the common sample

    # ==================================================================
    # 1. WINDOW LENGTH
    # ==================================================================
    print("\n--- 1. Effect of +1C sustained over the last k days (pp of the day per C) ---")
    rows, fits = [], {}
    for k in WINDOWS:
        d = window_sample(obs, k, common)
        sample = "common (complete lags 0-14)" if k <= COMMON_MAX_WINDOW else f">= {MIN_WINDOW_COVERAGE:.0%} of window observed"
        specs = [("a_main_controls", CTRL, d, ("station_month", "station")),
                 ("b_plus_window_rain", CTRL + win_ctrl(k), d, ("station_month", "station")),
                 ("c_dry_windows_only", CTRL + win_ctrl(k), d[d[f"RWmm{k}"] < DRY_WINDOW_MM], ("station_month",))]
        for variant, ctrl, data, fes in specs:
            for fe in fes:
                f = fe_ols(data, "blk", [f"S{k}"] + ctrl, fe=fe)
                est, se = lincomb(f, {f"S{k}": 1.0})
                rows.append({"variant": variant, "fe": fe, "window_days": k, "coef": est, "se": se,
                             "lo": est - 1.96 * se, "hi": est + 1.96 * se, "n_obs": f.n,
                             "n_stations": f.n_clusters, "sample": sample})
                if fe == "station_month":
                    fits[(variant, k)] = f
        r = {(x["variant"], x["fe"]): x for x in rows if x["window_days"] == k}
        print(f"  k={k:2d}  a: {r[('a_main_controls','station_month')]['coef']*100:+.3f}  "
              f"b: {r[('b_plus_window_rain','station_month')]['coef']*100:+.3f}  "
              f"c (dry): {r[('c_dry_windows_only','station_month')]['coef']*100:+.3f}   "
              f"[n={r[('a_main_controls','station_month')]['n_obs']:,}]")
    pd.DataFrame(rows).to_csv(out_path("chronic_window_effects.csv"), index=False)

    dt = []
    for variant in ("a_main_controls", "b_plus_window_rain"):
        for ka, kb in DIFF_TESTS:
            fa, fb = fits[(variant, ka)], fits[(variant, kb)]
            # same stations needed: both on the common sample
            diff, se, p = diff_between_fits(fa, f"S{ka}", fb, f"S{kb}")
            dt.append({"variant": variant, "comparison": f"{kb}-day window minus {ka}-day window",
                       "diff": diff, "se": se, "lo": diff - 1.96 * se, "hi": diff + 1.96 * se, "p": p})
            print(f"    [{variant}] {kb}-day minus {ka}-day: {diff*100:+.3f} pp/C (se {se*100:.3f}, p={p:.3g})")
    pd.DataFrame(dt).to_csv(out_path("chronic_window_diff_tests.csv"), index=False)

    # ==================================================================
    # 2. DISTRIBUTED LAG (+ placebo with FUTURE temperatures)
    # ==================================================================
    lag_cols = [f"t_l{k}" for k in range(MAX_LAG + 1)]
    lead_cols = ["t_f1", "t_f2", "t_f3"]
    dA = obs.dropna(subset=lag_cols + lead_cols + CTRL + ["blk"])
    log.append((f"2: station-days with all lags 0-{MAX_LAG}, 3 leads and controls", len(dA)))
    print(f"\n--- 2. Distributed lag 0-{MAX_LAG} days with placebo, {len(dA):,} station-days ---")
    rowsA, cumA, testsA = [], [], []
    for fe in ("station_month", "station"):
        f = fe_ols(dA, "blk", lead_cols + lag_cols + CTRL, fe=fe)
        t = tidy(f, lead_cols + lag_cols)
        t["lag_days"] = [-1, -2, -3] + list(range(MAX_LAG + 1)); t["fe"] = fe
        # lead_cols are t_f1, t_f2, t_f3 = tomorrow, +2, +3 days  ->  lag_days -1, -2, -3
        rowsA.append(t)
        for K in (0, 1, 2, 3, 5, 7, 10, MAX_LAG):
            est, se = lincomb(f, {f"t_l{k}": 1.0 for k in range(K + 1)})
            cumA.append({"fe": fe, "through_lag": K, "cumulative_coef": est, "se": se,
                         "lo": est - 1.96 * se, "hi": est + 1.96 * se})
        for label, names in ((f"PLACEBO: future temperatures (tomorrow, +2, +3 days) jointly zero", lead_cols),
                             (f"lags 1-{MAX_LAG} jointly zero (past heat adds nothing beyond today)", lag_cols[1:]),
                             (f"lags 0-{MAX_LAG} jointly zero (no temperature effect at all)", lag_cols)):
            st, df_, pv = wald(f, names)
            testsA.append({"fe": fe, "test": label, "chi2": st, "df": df_, "p": pv, "n_obs": f.n, "n_stations": f.n_clusters})
        cK = [r for r in cumA if r["fe"] == fe and r["through_lag"] == MAX_LAG][0]
        print(f"  [{fe}] lag0 {f.params['t_l0']*100:+.3f}  lag1 {f.params['t_l1']*100:+.3f} | "
              f"sum lags 0-{MAX_LAG}: {cK['cumulative_coef']*100:+.3f} [{cK['lo']*100:+.3f}, {cK['hi']*100:+.3f}] | "
              f"placebo p={testsA[-3]['p']:.3g}")
    pd.concat(rowsA).to_csv(out_path("chronic_DL_lags.csv"), index=False)
    pd.DataFrame(cumA).to_csv(out_path("chronic_DL_cumulative.csv"), index=False)
    pd.DataFrame(testsA).to_csv(out_path("chronic_DL_tests.csv"), index=False)

    # ==================================================================
    # 3. HETEROGENEITY (variant b, windows 1 and 14)
    # ==================================================================
    print("\n--- 3. Heterogeneity (1-day and 14-day windows; rain-over-window control) ---")
    het = []
    month = obs["date"].dt.month
    groups = [("all", "all stations", np.ones(len(obs), dtype=bool))]
    groups += [("season", name, month.isin(ms).to_numpy()) for name, ms in SEASONS.items()]
    zone_counts = obs.groupby("zone")[STATION_COL].nunique()
    groups += [("climate zone", z, (obs["zone"] == z).to_numpy()) for z in sorted(zone_counts.index)
               if zone_counts[z] >= HET_MIN_STATIONS]
    for gtype, gname, mask in groups:
        for k in HET_WINDOWS:
            d = window_sample(obs[mask], k, common)
            f = fe_ols(d, "blk", [f"S{k}"] + win_ctrl(k) + CTRL)
            est, se = lincomb(f, {f"S{k}": 1.0})
            het.append({"group_type": gtype, "group": gname, "window_days": k, "coef": est, "se": se,
                        "lo": est - 1.96 * se, "hi": est + 1.96 * se, "n_obs": f.n, "n_stations": f.n_clusters})
        a, b = het[-2], het[-1]
        print(f"  {gtype:12s} {gname:34s} 1-day {a['coef']*100:+.3f} | 14-day {b['coef']*100:+.3f}  (stations {b['n_stations']}, n={b['n_obs']:,})")
    pd.DataFrame(het).to_csv(out_path("chronic_heterogeneity.csv"), index=False)

    # ==================================================================
    # 4. CONSECUTIVE HOT DAYS
    # ==================================================================
    print("\n--- 4. Consecutive hot days ---")
    grid["thr_rel"] = relative_threshold(grid)
    z = (grid["tmax"].to_numpy() - 30.0) / 10.0
    grid["tz1"], grid["tz2"], grid["tz3"] = z, z ** 2, z ** 3
    rowsC, testsC, countsC = [], [], []
    for key, kind, absval in HOT_DEFS:
        tm = grid["tmax"].to_numpy()
        if kind == "relative":
            hot = np.where(np.isnan(grid["thr_rel"].to_numpy()) | np.isnan(tm), np.nan, (tm >= grid["thr_rel"].to_numpy()).astype(float))
            desc = f"relative: hottest {100 - PCT_HOT}% of days for that station and time of year"
        else:
            hot = np.where(np.isnan(tm), np.nan, (tm >= absval).astype(float))
            desc = f"absolute: daily max >= {absval:g}C"
        grid["runcat"] = run_category(run_lengths(grid, hot))
        dC = grid[grid["observed"]].dropna(subset=["runcat"] + CTRL + ["blk"]).copy()
        cnt = dC.groupby("runcat").agg(n_days=("blk", "size"), n_stations=(STATION_COL, "nunique"))
        keep = [c for c in range(1, 7) if c in cnt.index and cnt.loc[c, "n_days"] >= MIN_DAYS_IN_RUN_CATEGORY]
        dC = dC[dC["runcat"].isin([0] + keep)]
        dummies = []
        for c in keep:
            dC[f"run_{c}"] = (dC["runcat"] == c).astype(float)
            dummies.append(f"run_{c}")
        lab = {f"run_{c}": RUN_LABELS[c - 1] for c in keep}
        cnt = cnt.reset_index(); cnt["def"] = key
        cnt["label"] = cnt["runcat"].map(lambda c: "not hot" if c == 0 else RUN_LABELS[int(c) - 1])
        countsC.append(cnt)
        print(f"  {key} ({desc}): {len(dC):,} station-days; run categories kept: " + ", ".join(lab[d] for d in dummies))
        log.append((f"4 [{key}] station-days with defined run length + controls", len(dC)))
        for version, extra in (("total", []), ("net_of_today_temp", ["tz1", "tz2", "tz3"])):
            f = fe_ols(dC, "blk", dummies + extra + CTRL)
            t = tidy(f, dummies, [lab[d] for d in dummies])
            t["def"], t["version"], t["desc"], t["n_obs"], t["n_stations"] = key, version, desc, f.n, f.n_clusters
            if "run_1" in dummies:
                ests = [(0.0, 0.0) if d == "run_1" else lincomb(f, {d: 1.0, "run_1": -1.0}) for d in dummies]
                t["vs_first_day"] = [e[0] for e in ests]
                t["vs_first_day_lo"] = [e[0] - 1.96 * e[1] for e in ests]
                t["vs_first_day_hi"] = [e[0] + 1.96 * e[1] for e in ests]
                later = [d for d in dummies if d != "run_1"]
                if later:
                    b = np.array([lincomb(f, {d: 1.0, "run_1": -1.0})[0] for d in later])
                    L = np.zeros((len(later), len(f.params)))
                    names = list(f.params.index)
                    for i, d in enumerate(later):
                        L[i, names.index(d)], L[i, names.index("run_1")] = 1.0, -1.0
                    Vc = L @ f.cov.to_numpy() @ L.T
                    st = float(b @ np.linalg.solve(Vc, b))
                    testsC.append({"def": key, "version": version,
                                   "test": "later hot days equal the 1st hot day (persistence adds nothing)",
                                   "chi2": st, "df": len(later), "p": float(chi2.sf(st, len(later))),
                                   "n_obs": f.n, "n_stations": f.n_clusters})
            rowsC.append(t)
            print(f"    [{version}] pp of day vs not-hot (run 1,2,..): " +
                  " | ".join(f"{r['label']}: {r['coef']*100:+.2f}" for _, r in t.iterrows()))
    pd.concat(rowsC).to_csv(out_path("chronic_run_length.csv"), index=False)
    pd.concat(countsC).to_csv(out_path("chronic_run_counts.csv"), index=False)
    pd.DataFrame(testsC).to_csv(out_path("chronic_run_tests.csv"), index=False)
    for r in testsC:
        print(f"    test [{r['def']}, {r['version']}]: later hot days = 1st hot day: chi2={r['chi2']:.1f}, df={r['df']}, p={r['p']:.3g}")

    pd.DataFrame(log, columns=["step", "value"]).to_csv(out_path("chronic_sample_log.csv"), index=False)
    daily.to_parquet(out_path("daily_station_table.parquet"), index=False)
    print("\nDone. Daily table saved for reuse (daily_station_table.parquet). Now run plot_chronic_heat.py.")


if __name__ == "__main__":
    main()
