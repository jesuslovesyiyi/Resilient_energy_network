"""
compute_chronic_rain.py
========================
SUSTAINED RAINFALL: does rain that persists over several days change the blackout rate
more than a single rainy day does, and does rain from EARLIER days matter once today's
rain is accounted for?

It reuses the machinery in compute_chronic_heat.py (daily table, fixed effects,
station-clustered inference), so keep compute_chronic_heat.py, compute_results.py and this
file in ONE folder. Set paths in compute_results.py.

Outcome  : daily mean of pct_blackout.
Exposure : daily rainfall (mm, summed from the de-accumulated hourly ERA5 rain).
           Rain is heavily skewed, so it enters as log(1 + mm) and is SCALED so that a
           coefficient is the change in blackout (percentage points of the day) when rain goes
           from none to 5 mm/day on average over the window (RAIN_CONTRAST_MM).
           5 mm/day is exceeded on about 17% of station-days.

DESIGN
  Fixed effects (main): station x calendar-month + year, as for heat. Each station is compared
  with ITSELF in the same month, so "wet places" and "wet seasons" drop out.
  Standard errors clustered by station.
  Controls: temperature (today's max, and the mean max of the previous 7 days).
  Diurnal temperature range is NOT used here: rain itself shrinks it, so it would absorb part
  of the effect we want to measure. Wind is added in variants b and c because storm wind is a
  main way rain causes outages; b/c ask what rain does BEYOND wind.

ANALYSES
  1. Window length  : exposure = mean daily rain over the last k days INCLUDING today
                      (k = 1,2,3,5,7,10,14,21,30). Variants:
                        a  temperature controls only
                        b  + wind today and yesterday
                        c  ANTECEDENT rain: mean over the previous k days EXCLUDING today,
                           holding today's rain and wind fixed (does earlier rain matter?)
                      Formal tests: 3/7/14-day window minus 1-day window (variants a, b).
  2. Distributed lag: rain today and each of the previous 14 days together, with FUTURE rain
                      (tomorrow, +2, +3 days) as a placebo.
  3. Heterogeneity  : 1-day and 14-day effects by season and climate zone (variant b).
  4. Wet-day runs   : length of the current run of consecutive wet days, for >= 1 mm and
                      >= 10 mm days, vs a non-wet day.

Run order: compute_chronic_rain.py, then plot_chronic_rain.py.
"""

import os
import warnings
import numpy as np
import pandas as pd
from scipy.stats import chi2, norm

import compute_results as cres
from compute_results import load_data, out_path, STATION_COL, WIND_COL
from compute_chronic_heat import (build_daily, to_full_grid, shifted, lag_matrix, fe_ols, wald,
                                  lincomb, diff_between_fits, tidy, run_lengths, run_category,
                                  WINDOWS, MIN_WINDOW_COVERAGE, COMMON_MAX_WINDOW, MAX_LAG,
                                  DIFF_TESTS, HET_WINDOWS, HET_MIN_STATIONS, SEASONS,
                                  RUN_LABELS, MIN_DAYS_IN_RUN_CATEGORY)

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
RAIN_CONTRAST_MM = 5.0          # coefficients = effect of going from 0 to this many mm/day
ZS = np.log1p(RAIN_CONTRAST_MM)
WET_DEFS = [("wet_1mm", 1.0), ("wet_10mm", 10.0)]    # a "wet day" has at least this much rain (mm)
TC = ["tmax", "tmax_p7"]        # temperature controls
WIND = ["wind", "wind1"]        # wind controls (variants b and c)


def pval(est, se):
    return float(2 * norm.sf(abs(est / se)))


# ----------------------------------------------------------------------
# FEATURES
# ----------------------------------------------------------------------
def win_mean_cols(M, a, b):
    """Mean of columns a..b-1 of a lag matrix (column k = k days earlier), requiring
    MIN_WINDOW_COVERAGE of the days to be observed."""
    W = M[:, a:b]
    k = b - a
    n_obs = np.sum(~np.isnan(W), axis=1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        m = np.nanmean(W, axis=1)
    m[n_obs < max(MIN_WINDOW_COVERAGE * k, 1)] = np.nan
    return m


def zscale(mm):
    return np.log1p(mm) / ZS


def add_rain_features(grid):
    Rm = lag_matrix(grid, "rain", 30)
    Tm = lag_matrix(grid, "tmax", 30)
    grid["tmax_p7"] = win_mean_cols(Tm, 1, 8)                    # mean tmax over the previous 7 days
    grid["wind1"] = shifted(grid, "wind", 1)
    for k in range(MAX_LAG + 1):
        grid[f"zl{k}"] = zscale(Rm[:, k])                        # scaled log rain k days ago
    for k in (1, 2, 3):
        grid[f"zf{k}"] = zscale(shifted(grid, "rain", -k))       # FUTURE rain: placebo only
    for k in WINDOWS:
        grid[f"W{k}"] = zscale(win_mean_cols(Rm, 0, k))          # last k days incl. today
        grid[f"A{k}"] = zscale(win_mean_cols(Rm, 1, k + 1))      # previous k days, excluding today
    grid["z0"], grid["z0sq"] = grid["zl0"], grid["zl0"] ** 2
    return grid


def window_sample(obs, exposures, k, common):
    """One shared sample per k for all variants, so differences between variants are not
    sample artefacts. Windows up to COMMON_MAX_WINDOW also share the sample ACROSS k."""
    d = obs.dropna(subset=exposures + TC + WIND + ["zl0", "blk"])
    if k <= COMMON_MAX_WINDOW:
        d = d.dropna(subset=common)
    return d


# ----------------------------------------------------------------------
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
    log += [("hourly rows", n_hours_total), ("complete station-days", len(daily)),
            ("rain contrast (mm/day, 0 -> this)", RAIN_CONTRAST_MM)]

    grid = add_rain_features(to_full_grid(daily))
    obs = grid[grid["observed"]].copy()
    common = [f"zl{k}" for k in range(MAX_LAG + 1)]
    log.append(("share of station-days with rain >= 5 mm", float((obs["rain"] >= 5).mean())))

    # ==================================================================
    # 1. WINDOW LENGTH (+ antecedent rain)
    # ==================================================================
    print(f"\n--- 1. Effect of rain going 0 -> {RAIN_CONTRAST_MM:g} mm/day over the window (pp of the day) ---")
    rows, fits = [], {}
    for k in WINDOWS:
        d = window_sample(obs, [f"W{k}", f"A{k}"], k, common)
        sample = "common (complete lags 0-14)" if k <= COMMON_MAX_WINDOW else f">= {MIN_WINDOW_COVERAGE:.0%} of window observed"
        specs = [("a_temp_controls", f"W{k}", TC),
                 ("b_plus_wind", f"W{k}", TC + WIND),
                 ("c_antecedent_beyond_today", f"A{k}", TC + WIND + ["zl0"])]
        for variant, xcol, ctrl in specs:
            for fe in ("station_month", "station"):
                f = fe_ols(d, "blk", [xcol] + ctrl, fe=fe)
                est, se = lincomb(f, {xcol: 1.0})
                rows.append({"variant": variant, "fe": fe, "window_days": k, "coef": est, "se": se,
                             "lo": est - 1.96 * se, "hi": est + 1.96 * se, "p": pval(est, se),
                             "n_obs": f.n, "n_stations": f.n_clusters, "sample": sample})
                if fe == "station_month":
                    fits[(variant, k)] = f
        r = {x["variant"]: x for x in rows if x["window_days"] == k and x["fe"] == "station_month"}
        print(f"  k={k:2d}  a: {r['a_temp_controls']['coef']*100:+.3f}  b: {r['b_plus_wind']['coef']*100:+.3f}  "
              f"c (earlier days only): {r['c_antecedent_beyond_today']['coef']*100:+.3f} "
              f"(p={r['c_antecedent_beyond_today']['p']:.3g})   [n={r['a_temp_controls']['n_obs']:,}]")
    pd.DataFrame(rows).to_csv(out_path("rain_window_effects.csv"), index=False)

    dt = []
    for variant in ("a_temp_controls", "b_plus_wind"):
        for ka, kb in DIFF_TESTS:
            fa, fb = fits[(variant, ka)], fits[(variant, kb)]
            diff, se, p = diff_between_fits(fa, f"W{ka}", fb, f"W{kb}")
            dt.append({"variant": variant, "comparison": f"{kb}-day window minus {ka}-day window",
                       "diff": diff, "se": se, "lo": diff - 1.96 * se, "hi": diff + 1.96 * se, "p": p})
            print(f"    [{variant}] {kb}-day minus {ka}-day: {diff*100:+.3f} pp (se {se*100:.3f}, p={p:.3g})")
    pd.DataFrame(dt).to_csv(out_path("rain_window_diff_tests.csv"), index=False)

    # ==================================================================
    # 2. DISTRIBUTED LAG (+ placebo with FUTURE rain)
    # ==================================================================
    lag_cols = [f"zl{k}" for k in range(MAX_LAG + 1)]
    lead_cols = ["zf1", "zf2", "zf3"]
    dA = obs.dropna(subset=lag_cols + lead_cols + TC + WIND + ["blk"])
    log.append((f"2: station-days with all rain lags 0-{MAX_LAG}, 3 leads and controls", len(dA)))
    print(f"\n--- 2. Distributed lag 0-{MAX_LAG} days with placebo, {len(dA):,} station-days ---")
    rowsA, cumA, testsA = [], [], []
    for fe in ("station_month", "station"):
        f = fe_ols(dA, "blk", lead_cols + lag_cols + TC + WIND, fe=fe)
        t = tidy(f, lead_cols + lag_cols)
        t["lag_days"] = [-1, -2, -3] + list(range(MAX_LAG + 1)); t["fe"] = fe
        rowsA.append(t)
        for K in (0, 1, 2, 3, 5, 7, 10, MAX_LAG):
            est, se = lincomb(f, {f"zl{k}": 1.0 for k in range(K + 1)})
            cumA.append({"fe": fe, "through_lag": K, "cumulative_coef": est, "se": se,
                         "lo": est - 1.96 * se, "hi": est + 1.96 * se})
        for label, names in (("PLACEBO: future rain (tomorrow, +2, +3 days) jointly zero", lead_cols),
                             (f"lags 1-{MAX_LAG} jointly zero (past rain adds nothing beyond today)", lag_cols[1:]),
                             (f"lags 0-{MAX_LAG} jointly zero (no rain effect at all)", lag_cols)):
            st, df_, pv = wald(f, names)
            testsA.append({"fe": fe, "test": label, "chi2": st, "df": df_, "p": pv,
                           "n_obs": f.n, "n_stations": f.n_clusters})
        cK = [r for r in cumA if r["fe"] == fe and r["through_lag"] == MAX_LAG][0]
        print(f"  [{fe}] lag0 {f.params['zl0']*100:+.3f}  lag1 {f.params['zl1']*100:+.3f} | "
              f"sum lags 0-{MAX_LAG}: {cK['cumulative_coef']*100:+.3f} [{cK['lo']*100:+.3f}, {cK['hi']*100:+.3f}] | "
              f"placebo p={testsA[-3]['p']:.3g}")
    # lead rows were stored as t_f3,t_f2,t_f1 order in heat; here zf1,zf2,zf3 -> lags -1,-2,-3 (set above)
    pd.concat(rowsA).to_csv(out_path("rain_DL_lags.csv"), index=False)
    pd.DataFrame(cumA).to_csv(out_path("rain_DL_cumulative.csv"), index=False)
    pd.DataFrame(testsA).to_csv(out_path("rain_DL_tests.csv"), index=False)

    # ==================================================================
    # 3. HETEROGENEITY (variant b, windows 1 and 14)
    # ==================================================================
    print("\n--- 3. Heterogeneity (1-day and 14-day windows; temperature + wind controls) ---")
    het = []
    month = obs["date"].dt.month
    groups = [("all", "all stations", np.ones(len(obs), dtype=bool))]
    groups += [("season", name, month.isin(ms).to_numpy()) for name, ms in SEASONS.items()]
    zone_counts = obs.groupby("zone")[STATION_COL].nunique()
    groups += [("climate zone", z, (obs["zone"] == z).to_numpy()) for z in sorted(zone_counts.index)
               if zone_counts[z] >= HET_MIN_STATIONS]
    for gtype, gname, mask in groups:
        for k in HET_WINDOWS:
            d = window_sample(obs[mask], [f"W{k}"], k, common)
            f = fe_ols(d, "blk", [f"W{k}"] + TC + WIND)
            est, se = lincomb(f, {f"W{k}": 1.0})
            het.append({"group_type": gtype, "group": gname, "window_days": k, "coef": est, "se": se,
                        "lo": est - 1.96 * se, "hi": est + 1.96 * se, "p": pval(est, se),
                        "n_obs": f.n, "n_stations": f.n_clusters})
        a, b = het[-2], het[-1]
        print(f"  {gtype:12s} {gname:34s} 1-day {a['coef']*100:+.3f} | 14-day {b['coef']*100:+.3f}  (stations {b['n_stations']}, n={b['n_obs']:,})")
    pd.DataFrame(het).to_csv(out_path("rain_heterogeneity.csv"), index=False)

    # ==================================================================
    # 4. CONSECUTIVE WET DAYS
    # ==================================================================
    print("\n--- 4. Consecutive wet days ---")
    rowsC, testsC, countsC = [], [], []
    rain = grid["rain"].to_numpy()
    for key, thr in WET_DEFS:
        wet = np.where(np.isnan(rain), np.nan, (rain >= thr).astype(float))
        desc = f"wet day: rain >= {thr:g} mm"
        grid["runcat"] = run_category(run_lengths(grid, wet))
        dC = grid[grid["observed"]].dropna(subset=["runcat"] + TC + ["blk", "z0"]).copy()
        cnt = dC.groupby("runcat").agg(n_days=("blk", "size"), n_stations=(STATION_COL, "nunique"))
        keep = [c for c in range(1, 7) if c in cnt.index and cnt.loc[c, "n_days"] >= MIN_DAYS_IN_RUN_CATEGORY]
        dC = dC[dC["runcat"].isin([0] + keep)]
        dummies = []
        for c in keep:
            dC[f"run_{c}"] = (dC["runcat"] == c).astype(float)
            dummies.append(f"run_{c}")
        lab = {f"run_{c}": RUN_LABELS[c - 1] for c in keep}
        cnt = cnt.reset_index(); cnt["def"] = key
        cnt["label"] = cnt["runcat"].map(lambda c: "not wet" if c == 0 else RUN_LABELS[int(c) - 1])
        countsC.append(cnt)
        print(f"  {key} ({desc}): {len(dC):,} station-days; run categories kept: " + ", ".join(lab[x] for x in dummies))
        log.append((f"4 [{key}] station-days with defined run length + controls", len(dC)))
        for version, extra in (("total", []), ("net_of_today_intensity", ["z0", "z0sq"])):
            f = fe_ols(dC, "blk", dummies + extra + TC)
            t = tidy(f, dummies, [lab[x] for x in dummies])
            t["def"], t["version"], t["desc"], t["n_obs"], t["n_stations"] = key, version, desc, f.n, f.n_clusters
            if "run_1" in dummies:
                ests = [(0.0, 0.0) if x == "run_1" else lincomb(f, {x: 1.0, "run_1": -1.0}) for x in dummies]
                t["vs_first_day"] = [e[0] for e in ests]
                t["vs_first_day_lo"] = [e[0] - 1.96 * e[1] for e in ests]
                t["vs_first_day_hi"] = [e[0] + 1.96 * e[1] for e in ests]
                later = [x for x in dummies if x != "run_1"]
                if later:
                    b = np.array([lincomb(f, {x: 1.0, "run_1": -1.0})[0] for x in later])
                    L = np.zeros((len(later), len(f.params)))
                    names = list(f.params.index)
                    for i, x in enumerate(later):
                        L[i, names.index(x)], L[i, names.index("run_1")] = 1.0, -1.0
                    Vc = L @ f.cov.to_numpy() @ L.T
                    st = float(b @ np.linalg.solve(Vc, b))
                    testsC.append({"def": key, "version": version,
                                   "test": "later wet days equal the 1st wet day (persistence adds nothing)",
                                   "chi2": st, "df": len(later), "p": float(chi2.sf(st, len(later))),
                                   "n_obs": f.n, "n_stations": f.n_clusters})
            rowsC.append(t)
            print(f"    [{version}] pp of day vs not-wet (run 1,2,..): " +
                  " | ".join(f"{r['label']}: {r['coef']*100:+.2f}" for _, r in t.iterrows()))
    pd.concat(rowsC).to_csv(out_path("rain_run_length.csv"), index=False)
    pd.concat(countsC).to_csv(out_path("rain_run_counts.csv"), index=False)
    pd.DataFrame(testsC).to_csv(out_path("rain_run_tests.csv"), index=False)
    for r in testsC:
        print(f"    test [{r['def']}, {r['version']}]: later wet days = 1st wet day: chi2={r['chi2']:.1f}, df={r['df']}, p={r['p']:.3g}")

    pd.DataFrame(log, columns=["step", "value"]).to_csv(out_path("rain_sample_log.csv"), index=False)
    print("\nDone. Now run plot_chronic_rain.py.")


if __name__ == "__main__":
    main()
