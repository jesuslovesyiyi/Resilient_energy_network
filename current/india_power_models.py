#!/usr/bin/env python3
"""
india_power_models.py  --  ALL MODELS in one file (figures are in india_power_plots.py)
=====================================================================================
Chronic versus extreme weather and power outages at ESMI stations in India. Needs Python with numpy, pandas, scipy.
It runs from any folder and writes result CSVs to OUTPUT_DIR; india_power_plots.py reads those CSVs and draws the figures.

QUICK START
  1. Edit DATA_DIR / INPUT_CSVS / OUTPUT_DIR below (or pass --input-csv and --output-dir).
  2. python india_power_models.py            run every step (slow on the full data: run overnight)
  3. python india_power_plots.py             then draw the figures

COMMANDS AND OPTIONS
  (no command) or run   run the steps
  list                  show every step and whether its result exists
  --only STEP ...  --skip STEP ...  --force (rerun even if the result exists)  --keep-going (continue after a failed step)
  --input-csv FILE [FILE ...]   --output-dir DIR
  A step is skipped if its result CSV already exists, unless --force is given.

STEPS (in this order)
  main         lag windows and the flag-based model (robustness version)           -> main_*.csv
  percentile   MAIN MODEL: same-day percentile splines + chronic windows, plus exceedance and bins -> pct_*.csv
  irf          impulse responses (distributed lags, event studies, thresholds p1-p99, bins, by climate zone) -> irf_*.csv
  variance     within-R2 and Shapley shares                                          -> vd_*.csv
  interaction  chronic state x acute shock, twelve pairs                             -> interaction_results.csv
  robustness   placebo, seasonal, zone and permutation checks                        -> interaction_robustness.csv
  confirm      station halves, leave-one-year-out, multiplicity for dry spell -> heat -> dry_heat_confirmation.csv
  forest       forest cover x wind (rain and heat as placebos)                       -> forest_interaction_results.csv
  knots        spline-knot sensitivity                                               -> knot_sensitivity_*.csv
  fit          AIC, BIC, within-R2 and out-of-sample R2 of the main model and alternatives -> model_fit*.csv

The scripts are embedded unchanged as text in _SOURCES at the bottom (old script names); edit them there to change a model.
Numbers quoted in the Methods drafts came from Claude's sandbox runs, not from your machine: rerun everything here.
"""
import argparse
import os
import sys
import time
import traceback
import types

# ----------------------------------------------------------------------
# CONFIGURATION -- edit these (absolute paths; the file can run from any folder)
# ----------------------------------------------------------------------
DATA_DIR = "/Users/yiyi/Library/CloudStorage/OneDrive-GeorgiaInstituteofTechnology/Research/Energy_resilience/01_data/processed"
# The complete hourly file (one CSV with Lat and Lon columns).
INPUT_CSVS = ["/Users/yiyi/Library/CloudStorage/OneDrive-GeorgiaInstituteofTechnology/Research/Energy_resilience/01_data/processed/station_518_hourly_forest_perc_50kmBu_district_climate_dummy_latlon_df.csv"]
OUTPUT_DIR = os.path.join(DATA_DIR, "main_model_results")        # result CSVs and figures

# model steps: (name, module, result file that marks the step as done)
STEPS = [
    ("main", "compute_main_model", "main_quantities.csv"),
    ("percentile", "compute_percentile_model", "pct_spline_curve.csv"),
    ("irf", "compute_irf", "irf_dl_by_zone.csv"),
    ("variance", "compute_variance_decomposition", "vd_shapley.csv"),
    ("interaction", "compute_interaction_model", "interaction_results.csv"),
    ("robustness", "check_interaction_robustness", "interaction_robustness.csv"),
    ("confirm", "compute_dry_heat_confirmation", "dry_heat_confirmation.csv"),
    ("forest", "compute_forest_interaction", "forest_interaction_results.csv"),
    ("knots", "compute_knot_sensitivity", "knot_sensitivity_curves.csv"),
    ("fit", "compute_model_fit", "model_fit.csv"),
]

_BUNDLE = os.path.abspath(__file__)
_STATE = {"output_dir": OUTPUT_DIR, "input_csvs": INPUT_CSVS}


def _load(name):
    if name in sys.modules and getattr(sys.modules[name], "_from_bundle", False):
        return sys.modules[name]
    mod = types.ModuleType(name)
    mod.__file__ = _BUNDLE
    mod._from_bundle = True
    sys.modules[name] = mod
    exec(compile(_SOURCES[name], f"<{name}>", "exec"), mod.__dict__)
    return mod


def _load_models():
    """Load every model module in dependency order and point the data paths at the configuration above."""
    for name in ["compute_main_model", "compute_percentile_model", "compute_interaction_model", "check_interaction_robustness",
                 "compute_irf", "compute_variance_decomposition", "compute_dry_heat_confirmation", "compute_forest_interaction",
                 "compute_knot_sensitivity", "compute_model_fit"]:
        _load(name)
    cm = sys.modules["compute_main_model"]
    cm.INPUT_CSVS = list(_STATE["input_csvs"])
    cm.OUTPUT_DIR = _STATE["output_dir"]
    cm.COASTAL_CSV = os.path.join(cm.OUTPUT_DIR, "station_coastal_flags.csv")
    os.makedirs(cm.OUTPUT_DIR, exist_ok=True)
    return cm


def cmd_list(a):
    out = _STATE["output_dir"]
    print("INPUT_CSVS:", _STATE["input_csvs"])
    print("OUTPUT_DIR:", out)
    for name, module, marker in STEPS:
        print(f"  {name:12s} {module:34s} {'done' if os.path.exists(os.path.join(out, marker)) else 'missing'}")


def cmd_models(a):
    cm = _load_models()
    out = cm.OUTPUT_DIR
    todo = [s for s in STEPS if (not a.only or s[0] in a.only) and s[0] not in (a.skip or [])]
    failed = []
    t_all = time.time()
    for name, module, marker in todo:
        if os.path.exists(os.path.join(out, marker)) and not a.force:
            print(f"[{name}] output exists ({marker}); skipping (use --force to rerun)")
            continue
        print(f"\n[{name}] running {module} ...", flush=True)
        t0 = time.time()
        old_argv, sys.argv = sys.argv, [_BUNDLE]
        try:
            sys.modules[module].main()
            ok = True
        except Exception:
            traceback.print_exc()
            ok = False
        finally:
            sys.argv = old_argv
        print(f"[{name}] {'finished' if ok else 'FAILED'} in {(time.time() - t0) / 60:.1f} min", flush=True)
        if not ok:
            failed.append(name)
            if not a.keep_going:
                break
    print(f"\nModels done in {(time.time() - t_all) / 60:.1f} min. Failed steps: {failed or 'none'}. Results: {out}")
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", default="run", choices=["run", "models", "list"], help="run (default) or list")
    ap.add_argument("--input-csv", nargs="+")
    ap.add_argument("--output-dir")
    ap.add_argument("--only", nargs="+")
    ap.add_argument("--skip", nargs="+")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--keep-going", action="store_true")
    a = ap.parse_args()
    if a.input_csv:
        _STATE["input_csvs"] = [os.path.abspath(p) for p in a.input_csv]
    if a.output_dir:
        _STATE["output_dir"] = os.path.abspath(a.output_dir)
    names = [s[0] for s in STEPS]
    bad = [x for x in (a.only or []) + (a.skip or []) if x not in names]
    if bad:
        ap.error(f"unknown step {bad}; choose from {names}")
    if a.command == "list":
        cmd_list(a); return
    sys.exit(cmd_models(a))


# ======================================================================
# EMBEDDED SCRIPTS (unchanged copies of the original files)
# ======================================================================
_SOURCES = {}

# ---------------------------------------------------------------- compute_main_model.py
_SOURCES['compute_main_model'] = r'''
"""
compute_main_model.py
=====================
Estimates the main (additive) model of the Methods section on the FULL hourly dataset, for four
ways of measuring a day's outages (the OUTCOMES below):

  share   share of the day in blackout, in percentage points (pct_blackout x 100)
  ge1h    probability that the day has at least 1 hour of blackout (in percentage points)
  ge6h    ... at least 6 hours
  ge12h   ... at least 12 hours
          (hours = share x 24; "probability" is a linear probability model, so coefficients are
          percentage-point changes in the chance of an outage of at least that length)

  Y_it = alpha_{i,m(t)} + gamma_{y(t)}
         + sum_{v in T,P,W} sum_{b in B} beta^v_b X^v_{it,b}
         + delta_T E^T_it + sum_{k=1..3} delta_{P,k} E^{P,k}_it + delta_W E^W_it + eps_it

  B     lag windows [0,1], [2,6], [7,13], [14,29] (days before and including day t)
  X^T   mean daily maximum temperature (deg C) over the window
  X^P   ln(1 + mean daily rainfall in mm) over the window
  X^W   mean daily maximum of the hourly 10 m wind speed (m/s) over the window
  E^T   heat wave: daily max >= 40 C (37 C at coastal stations) on >= 2 consecutive days
  E^P,k IMD rain classes on the daily total: 64.5-115.5, 115.6-204.4, >= 204.5 mm
  E^W   daily maximum hourly 10 m gust >= 20 m/s   (needs a gust file: see GUST_FILE)

Estimation: OLS after demeaning within station x calendar-month groups (year dummies
included before demeaning); standard errors clustered by station with the
G/(G-1) * (N-1)/(N-K) correction.

The extreme-day coefficient delta is only the part OVER AND ABOVE the linear chronic terms.
The script therefore also reports the NET effect of an extreme day: the predicted difference
between flagged days and other days of the same station-month, chronic terms plus delta.

OUTPUTS (written to OUTPUT_DIR; read by plot_main_model.py). Every file has an `outcome` column.
  main_coefficients.csv     every coefficient of the main model, natural units and per within-SD
  main_quantities.csv       cumulative chronic Delta^v over all lag windows (eq. 5), extreme-day delta,
                            net extreme-day effect, and the chronic-vs-extreme comparison
  robustness_long.csv       coefficients under each robustness specification
  robustness_quantities.csv the same quantities under each robustness specification
  outcome_summary.csv       mean of each outcome in the estimation sample (baseline for relative effects)
  event_counts.csv          how many station-days carry each extreme flag
  sample_summary.csv        N, stations, date range, dropped flags

Run order:  1) edit the CONFIG block   2) python compute_main_model.py   3) python plot_main_model.py

NOTES ON CHOICES (all documented in the Methods)
  * Days are UTC calendar days. IMD's rainfall day ends 08:30 IST (03:00 UTC), so daily
    rain totals are shifted by 3 hours relative to IMD's definition.
  * Hourly rain is recovered by differencing ERA5's running total `tp` (see add_hourly_rain).
  * Without a gust file the high-wind flag E^W is NOT estimated (ERA5 mean wind never
    reaches 20 m/s at these stations). The script says so and carries on without it.
"""

import os
import warnings
import numpy as np
import pandas as pd
from scipy.stats import chi2, norm

# ----------------------------------------------------------------------
# CONFIG -- edit these
# ----------------------------------------------------------------------
# Everything uses absolute paths, so the script can be run from any folder.
DATA_DIR = os.path.expanduser(
    "~/Library/CloudStorage/OneDrive-GeorgiaInstituteofTechnology/Research/Energy_resilience/01_data/processed")
# The complete hourly file (one CSV with Lat and Lon columns). To use split files instead, list them all.
INPUT_CSVS = [os.path.join(DATA_DIR, "station_518_hourly_forest_perc_50kmBu_district_climate_dummy_latlon_df.csv")]
OUTPUT_DIR = os.path.join(DATA_DIR, "main_model_results")        # results CSVs; plot_main_model.py reads them
# Built from the Lat/Lon columns (see build_coastal_flags below) if this file does not exist yet.
COASTAL_CSV = os.path.join(OUTPUT_DIR, "station_coastal_flags.csv")
GUST_FILE = None            # optional CSV with columns: station_id, datetime (UTC, hourly), gust (m/s)

DATETIME_COL, OUTCOME_COL, TEMP_COL = "datetime", "pct_blackout", "t2m"
RAW_PRECIP_COL, WIND_COL, STATION_COL, ZONE_COL = "tp", "wind_speed", "station_id", "climate_zone_code"

MIN_HOURS_PER_DAY = 20          # a station-day needs at least this many observed hours
MIN_DAYS_PER_STATION = 90       # a station needs at least this many such days
MIN_WINDOW_COVERAGE = 0.70      # a window mean needs this share of its days observed
# Lag windows, in days BEFORE day t (lag 0 = day t itself is not in any window: the same-day exposure is carried by the
# extreme flags / percentile terms). Ranges are [lo, hi) in days. The default reaches back 179 days in roughly 30-day
# blocks; shorten it by deleting entries from the end. Adding "[180,209]": (180, 210) and so on reaches further back,
# but keeps only stations with a longer history.
WINDOWS = {"[1,6]": (1, 7), "[7,13]": (7, 14), "[14,29]": (14, 30), "[30,59]": (30, 60), "[60,89]": (60, 90),
           "[90,119]": (90, 120), "[120,149]": (120, 150), "[150,179]": (150, 180)}
ACUTE = None            # set to one of the WINDOWS keys (e.g. "[0,1]" with a (0, 2) window) to single out an acute window
MAX_LAG = max(hi for lo, hi in WINDOWS.values()) - 1
VARS = ["T", "P", "W"]

OUTAGE_HOURS = {"ge1h": 1, "ge6h": 6, "ge12h": 12}      # outcome name -> minimum hours of blackout in the day
OUTCOMES = ["share"] + list(OUTAGE_HOURS)                   # share = daily share in blackout (pp)

HEAT_THRESHOLD_C, HEAT_COASTAL_THRESHOLD_C, HEAT_MIN_DAYS = 40.0, 37.0, 2
COASTAL_KM = 100.0
RAIN_CLASSES = {"P1": (64.5, 115.6), "P2": (115.6, 204.5), "P3": (204.5, np.inf)}   # IMD, mm per day
GUST_THRESHOLD = 20.0
MIN_EVENTS_PER_FLAG = 10        # a flag with fewer station-days is dropped (and reported)
SD_PER_UNIT = True              # also report coefficients per pooled within-SD of the regressor


def out_path(name):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    return os.path.join(OUTPUT_DIR, name)


# ----------------------------------------------------------------------
# LOAD AND DAILY PANEL
# ----------------------------------------------------------------------
def add_hourly_rain(df):
    """`tp` is a running total since 00:00 UTC that resets each day (the 00:00 row holds the
    previous day's total). Recover hourly rain by differencing consecutive hours; the
    difference is only valid when the previous row is exactly one hour earlier."""
    df = df.sort_values([STATION_COL, DATETIME_COL]).reset_index(drop=True)
    tp_mm = df[RAW_PRECIP_COL].to_numpy(dtype="float64") * 1000.0
    hour = df[DATETIME_COL].dt.hour.to_numpy()
    stn = df[STATION_COL].to_numpy()
    t = df[DATETIME_COL].to_numpy()
    prev_ok = np.zeros(len(df), dtype=bool)
    prev_ok[1:] = (stn[1:] == stn[:-1]) & ((t[1:] - t[:-1]) == np.timedelta64(1, "h"))
    rain = np.where(hour == 1, tp_mm, np.where(prev_ok, tp_mm - np.roll(tp_mm, 1), np.nan))
    rain = np.where(np.isnan(rain), np.nan, np.maximum(rain, 0.0))
    df["rain_mm"] = rain.astype("float32")
    return df.drop(columns=[RAW_PRECIP_COL])


def load_hourly():
    usecols = [DATETIME_COL, OUTCOME_COL, TEMP_COL, RAW_PRECIP_COL, WIND_COL, STATION_COL, ZONE_COL]
    frames = [pd.read_csv(p, parse_dates=[DATETIME_COL], usecols=usecols) for p in INPUT_CSVS]
    df = pd.concat(frames, ignore_index=True)
    df["t2m_c"] = (df[TEMP_COL] - 273.15).astype("float32")          # source is Kelvin
    df[OUTCOME_COL] = df[OUTCOME_COL].astype("float32")
    df[WIND_COL] = df[WIND_COL].astype("float32")
    df[STATION_COL] = df[STATION_COL].astype("int32")
    df[ZONE_COL] = df[ZONE_COL].astype("category")
    df = df.drop_duplicates([STATION_COL, DATETIME_COL])
    df = add_hourly_rain(df)
    if GUST_FILE:
        g = pd.read_csv(GUST_FILE, parse_dates=[DATETIME_COL], usecols=[STATION_COL, DATETIME_COL, "gust"])
        df = df.merge(g, on=[STATION_COL, DATETIME_COL], how="left")
    return df


def build_daily(df):
    d = df.copy()
    d["date"] = d[DATETIME_COL].dt.floor("D")
    agg = dict(n_hours=(OUTCOME_COL, "size"), blk=(OUTCOME_COL, "mean"), tmax=("t2m_c", "max"),
               rain=("rain_mm", "sum"), wind=(WIND_COL, "max"), zone=(ZONE_COL, "first"))
    if "gust" in d.columns:
        agg["gust"] = ("gust", "max")
    daily = d.groupby([STATION_COL, "date"], observed=True).agg(**agg).reset_index()
    daily["zone"] = daily["zone"].astype(str)
    daily = daily[daily["n_hours"] >= MIN_HOURS_PER_DAY]
    n_days = daily.groupby(STATION_COL)["date"].transform("size")
    daily = daily[n_days >= MIN_DAYS_PER_STATION].copy()
    daily["blk"] = daily["blk"].astype("float64") * 100.0                 # percentage points
    for c in ("tmax", "rain", "wind") + (("gust",) if "gust" in daily.columns else ()):
        daily[c] = daily[c].astype("float64")
    return daily.reset_index(drop=True)


def to_full_grid(daily):
    """One row per calendar day between a station's first and last observed day, so that a
    lag of k days is always k calendar days. Unobserved days are NaN."""
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
    return np.column_stack([shifted(grid, col, k) for k in range(max_lag + 1)])


def window_mean(M, lo, hi):
    """Mean over lags lo..hi-1; needs MIN_WINDOW_COVERAGE of the window's days observed."""
    W = M[:, lo:hi]
    n_obs = np.sum(~np.isnan(W), axis=1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        m = np.nanmean(W, axis=1)
    m[n_obs < max(MIN_WINDOW_COVERAGE * (hi - lo), 1)] = np.nan
    return m


# ----------------------------------------------------------------------
# COASTAL FLAGS (built once from the station Lat/Lon; needs `pip install basemap scikit-learn`)
# Distance to the nearest point of the intermediate-resolution GSHHG ocean coastline (bundled
# with basemap), lakes excluded, coastline densified to about 1 km. Blank beyond MAX_KM.
# ----------------------------------------------------------------------
MAX_KM = 150.0
EARTH_KM = 6371.0088
DENSIFY_KM = 1.0


def coastline_points():
    try:
        from mpl_toolkits.basemap import Basemap
        from sklearn.neighbors import BallTree  # noqa: F401  (checked here so the error appears early)
    except ImportError as ex:
        raise SystemExit(
            f"\nCannot build the coastal flags: {ex}\n"
            "Option 1: run   pip install basemap scikit-learn   and start the script again.\n"
            f"Option 2: copy station_coastal_flags.csv (sent separately) into\n  {os.path.dirname(COASTAL_CSV)}\n"
            "          and start the script again; it is used as is when the file exists.\n")
    m = Basemap(llcrnrlon=55, llcrnrlat=0, urcrnrlon=105, urcrnrlat=40, resolution="i", projection="cyl")
    # coastpolygontypes: 1 = land, 2 = lake, 3 = island in lake, 4 = pond. Keep ocean coast only
    # (type 1), otherwise reservoirs and lakes inland would count as coast.
    pts = []
    for poly, typ in zip(m.coastpolygons, m.coastpolygontypes):
        if typ != 1:
            continue
        a = np.column_stack([np.asarray(poly[0], dtype=float), np.asarray(poly[1], dtype=float)])  # lon, lat
        if len(a) < 2:
            continue
        for p, q in zip(a[:-1], a[1:]):
            # km length of this edge (equirectangular is fine at this scale)
            dx = np.radians(q[0] - p[0]) * np.cos(np.radians((p[1] + q[1]) / 2)) * EARTH_KM
            dy = np.radians(q[1] - p[1]) * EARTH_KM
            n = max(int(np.hypot(dx, dy) / DENSIFY_KM), 1)
            t = np.linspace(0, 1, n, endpoint=False)
            pts.append(np.column_stack([p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])]))
        pts.append(a[-1:])
    return np.vstack(pts)


def build_coastal_flags(input_csv, out_csv):
    from sklearn.neighbors import BallTree
    cols = ["station_id", "Lat", "Lon", "climate_zone_code"]
    paths = [input_csv] if isinstance(input_csv, (str, os.PathLike)) else list(input_csv)
    st = pd.concat([pd.read_csv(p, usecols=cols).drop_duplicates("station_id") for p in paths])
    st = st.drop_duplicates("station_id").reset_index(drop=True)
    coast = coastline_points()
    tree = BallTree(np.radians(coast[:, ::-1]), metric="haversine")      # (lat, lon) in radians
    d, _ = tree.query(np.radians(st[["Lat", "Lon"]].to_numpy()), k=1)
    km = d[:, 0] * EARTH_KM
    out = pd.DataFrame({"station_id": st["station_id"], "lat": st["Lat"], "lon": st["Lon"],
                        "climate_zone": st["climate_zone_code"],
                        "coast_km": np.where(km <= MAX_KM, km, np.nan)})
    # ERA5 0.25 degree cell: row counted from 90N, column from 0E (cell centres on the 0.25 grid)
    row = np.floor((90.0 - st["Lat"].to_numpy()) / 0.25 + 0.5).astype(int)
    col = np.floor((st["Lon"].to_numpy() % 360.0) / 0.25 + 0.5).astype(int)
    out["era5_cell_025deg"] = [f"{r}_{c}" for r, c in zip(row, col)]
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    out.to_csv(out_csv, index=False)
    n_coast = int((out["coast_km"] <= 100).sum())
    print(f"wrote {out_csv}: {len(out)} stations, {n_coast} within 100 km of the coast")
    return out


# ----------------------------------------------------------------------
# FEATURES: chronic windows (eq. 1) and extreme flags
# ----------------------------------------------------------------------
def add_chronic(grid):
    mats = {"T": lag_matrix(grid, "tmax", MAX_LAG), "P": lag_matrix(grid, "rain", MAX_LAG),
            "W": lag_matrix(grid, "wind", MAX_LAG)}
    for v, M in mats.items():
        for b, (lo, hi) in WINDOWS.items():
            m = window_mean(M, lo, hi)
            grid[f"X{v}_{b}"] = np.log1p(m) if v == "P" else m      # ln(1 + mean rain) for precipitation
    # leads (placebo): mean over the NEXT two days, same transformation
    for v, col in (("T", "tmax"), ("P", "rain"), ("W", "wind")):
        F = np.column_stack([shifted(grid, col, -1), shifted(grid, col, -2)])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            m = np.nanmean(F, axis=1)
        m[np.sum(~np.isnan(F), axis=1) < 2] = np.nan
        grid[f"LEAD_{v}"] = np.log1p(m) if v == "P" else m
    return grid


def add_coastal(grid, coastal_csv):
    c = pd.read_csv(coastal_csv)
    grid = grid.merge(c[[STATION_COL, "coast_km", "era5_cell_025deg"]], on=STATION_COL, how="left")
    return grid


def heat_flag(grid, thr, thr_coastal, min_days, coastal_km):
    """1 on every day of a spell of >= min_days consecutive observed hot days. Station-level
    absolute thresholds (IMD); the departure-from-normal test is omitted."""
    coastal = (grid["coast_km"] <= coastal_km).to_numpy()
    limit = np.where(coastal, thr_coastal, thr)
    hot = (grid["tmax"].to_numpy() >= limit)
    g = grid.assign(_hot=hot.astype(float))
    run = np.ones(len(g))
    ok = g["_hot"].to_numpy() == 1.0
    # a day belongs to a spell if it sits inside a run of >= min_days consecutive hot days
    inrun = np.zeros(len(g), dtype=bool)
    for k in range(min_days):
        # window of min_days days that contains this day at position k (start at lag k..)
        win = np.ones(len(g), dtype=bool)
        for j in range(min_days):
            win &= (shifted(g, "_hot", j - k) == 1.0)
        inrun |= win
    return (inrun & ok).astype("float64")


def add_extremes(grid, heat_kw=None, gust_thr=GUST_THRESHOLD):
    kw = dict(thr=HEAT_THRESHOLD_C, thr_coastal=HEAT_COASTAL_THRESHOLD_C, min_days=HEAT_MIN_DAYS, coastal_km=COASTAL_KM)
    kw.update(heat_kw or {})
    grid = grid.copy()
    grid["ET"] = heat_flag(grid, **kw)
    for k, (lo, hi) in RAIN_CLASSES.items():
        grid[f"E{k}"] = ((grid["rain"] >= lo) & (grid["rain"] < hi)).astype("float64")
    if "gust" in grid.columns:
        grid["EW"] = (grid["gust"] >= gust_thr).astype("float64")
    return grid


# ----------------------------------------------------------------------
# ESTIMATION: within estimator with one- and two-way clustered covariance
# ----------------------------------------------------------------------
class Fit:
    def __init__(self, params, cov, n, n_clusters, sd_within, extra=None, Xd=None, raw=None):
        self.params, self.cov, self.n, self.n_clusters, self.sd_within = params, cov, n, n_clusters, sd_within
        self.extra = extra or {}
        self.Xd, self.raw = Xd, raw          # within-demeaned regressors and the raw regressors (for net effects)


def _meat(Xd, e, ids, N, K):
    G = len(np.unique(ids))
    codes = np.unique(ids, return_inverse=True)[1]
    scores = np.zeros((G, Xd.shape[1]))
    np.add.at(scores, codes, Xd * e[:, None])
    return (G / (G - 1)) * ((N - 1) / (N - K)) * (scores.T @ scores), G


def fe_ols(d, ycol, xcols, fe="station_month", cluster="station"):
    """fe: 'station_month' (main) | 'station_week' | 'station' (+ month dummies).
    cluster: 'station' | 'two_way' (station and date) | 'cell' (ERA5 0.25 degree cell)."""
    d = d.reset_index(drop=True)
    month = d["date"].dt.month
    extra = pd.get_dummies(d["date"].dt.year, prefix="yr", drop_first=True).astype("float64")
    stn = d[STATION_COL].astype(str)
    if fe == "station":
        extra = pd.concat([extra, pd.get_dummies(month, prefix="mo", drop_first=True).astype("float64")], axis=1)
        grp = pd.factorize(stn)[0]
    elif fe == "station_week":
        week = d["date"].dt.isocalendar().week.astype(int)
        grp = pd.factorize(stn + "_" + week.astype(str))[0]
    else:
        grp = pd.factorize(stn + "_" + month.astype(str))[0]
    X = pd.concat([d[xcols], extra], axis=1)
    names = list(X.columns)
    Xd = (X - X.groupby(grp).transform("mean")).to_numpy()
    yd = (d[ycol] - d[ycol].groupby(grp).transform("mean")).to_numpy()
    keep = Xd.std(axis=0) > 1e-10
    for i, n in enumerate(names):
        if not keep[i] and n in xcols:
            raise ValueError(f"regressor {n} has no within-group variation")
    Xd, names = Xd[:, keep], [n for n, k_ in zip(names, keep) if k_]
    N, K = Xd.shape
    try:
        XtX_inv = np.linalg.inv(Xd.T @ Xd)
    except np.linalg.LinAlgError:
        # nuisance dummies (e.g. a year seen in a single station-month, in a small sub-sample) can be collinear;
        # a generalised inverse leaves the estimable coefficients unchanged
        XtX_inv = np.linalg.pinv(Xd.T @ Xd)
    beta = XtX_inv @ (Xd.T @ yd)
    e = yd - Xd @ beta
    stn_ids = d[STATION_COL].to_numpy()
    if cluster == "two_way":
        date_ids = d["date"].to_numpy().astype("int64")
        sd_ids = pd.factorize(pd.Series(stn_ids).astype(str) + "_" + pd.Series(date_ids).astype(str))[0]
        Ms, Gs = _meat(Xd, e, stn_ids, N, K)
        Md, Gd = _meat(Xd, e, date_ids, N, K)
        Msd, _ = _meat(Xd, e, sd_ids, N, K)
        meat, G = Ms + Md - Msd, min(Gs, Gd)
    elif cluster == "cell":
        cell = d["era5_cell_025deg"].astype(str).to_numpy()
        meat, G = _meat(Xd, e, cell, N, K)
    else:
        meat, G = _meat(Xd, e, stn_ids, N, K)
    cov = XtX_inv @ meat @ XtX_inv
    # two-way covariance can lose positive-definiteness; floor the eigenvalues
    w, v = np.linalg.eigh((cov + cov.T) / 2)
    cov = (v * np.maximum(w, 0)) @ v.T
    sd = pd.Series(Xd.std(axis=0), index=names)
    return Fit(pd.Series(beta, index=names), pd.DataFrame(cov, index=names, columns=names), int(N), int(G), sd,
               extra={"n_stations": int(d[STATION_COL].nunique())},
               Xd=pd.DataFrame(Xd, columns=names)[list(xcols)], raw=d[list(xcols)].reset_index(drop=True))


def wald(fit, names):
    b = fit.params[names].to_numpy()
    V = fit.cov.loc[names, names].to_numpy()
    st = float(b @ np.linalg.solve(V, b))
    return st, len(names), float(chi2.sf(st, len(names)))


def lincomb(fit, weights):
    names = list(weights)
    w = np.array([weights[n] for n in names])
    est = float(w @ fit.params[names].to_numpy())
    se = float(np.sqrt(max(w @ fit.cov.loc[names, names].to_numpy() @ w, 0.0)))
    return est, se


def tidy(fit, names, spec, outcome="share"):
    rows = []
    for n in names:
        se = float(np.sqrt(fit.cov.loc[n, n]))
        c = float(fit.params[n])
        sd = float(fit.sd_within[n])
        rows.append(dict(outcome=outcome, spec=spec, term=n, coef=c, se=se, lo=c - 1.96 * se, hi=c + 1.96 * se,
                         p=float(2 * norm.sf(abs(c / se))) if se > 0 else np.nan,
                         sd_within=sd, coef_per_sd=c * sd, lo_per_sd=(c - 1.96 * se) * sd,
                         hi_per_sd=(c + 1.96 * se) * sd, n=fit.n, n_clusters=fit.n_clusters))
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# MODEL RUNS
# ----------------------------------------------------------------------
def chronic_terms():
    return [f"X{v}_{b}" for v in VARS for b in WINDOWS]


def add_outcomes(grid):
    """share = daily share in blackout (pp); geXh = 100 if the day has at least X hours of blackout
    (share >= 100 * X / 24), else 0."""
    grid["y_share"] = grid["blk"]
    for k, h in OUTAGE_HOURS.items():
        grid[f"y_{k}"] = np.where(grid["blk"].notna(), (grid["blk"] >= 100.0 * h / 24.0).astype(float) * 100.0, np.nan)
    return grid


def usable_flags(grid, log):
    flags = []
    for f in ["ET", "EP1", "EP2", "EP3", "EW"]:
        if f not in grid.columns:
            log.append(dict(item=f, note="not estimated: no gust file" if f == "EW" else "missing"))
            continue
        n = int(grid.loc[grid["observed"], f].sum())
        if n < MIN_EVENTS_PER_FLAG:
            log.append(dict(item=f, note=f"dropped: only {n} station-days (< {MIN_EVENTS_PER_FLAG})"))
        else:
            flags.append(f)
    return flags


def fit_spec(grid, flags, ycol="y_share", fe="station_month", cluster="station", leads=False):
    lead_cols = ["LEAD_T", "LEAD_P", "LEAD_W"] if leads else []
    xcols = chronic_terms() + flags + lead_cols
    d = grid[grid["observed"]].dropna(subset=chronic_terms() + lead_cols)
    if cluster == "cell":
        d = d.dropna(subset=["era5_cell_025deg"])
    return fe_ols(d, ycol, xcols, fe=fe, cluster=cluster), xcols


def quantities(fit, flags, spec="main", outcome="share"):
    rows = []
    z = lambda e, s: float(2 * norm.sf(abs(e / s))) if s > 0 else np.nan
    for v in VARS:
        beyond = [f"X{v}_{b}" for b in WINDOWS if b != ACUTE]
        est, se = lincomb(fit, {n: 1.0 for n in beyond})
        est_sd, se_sd = lincomb(fit, {n: float(fit.sd_within[n]) for n in beyond})
        if ACUTE:
            acute = f"X{v}_{ACUTE}"
            a_est, a_se = lincomb(fit, {acute: 1.0})
            sd_a = float(fit.sd_within[acute])
            rows.append(dict(outcome=outcome, spec=spec, var=v, quantity="acute_beta", est=a_est, se=a_se,
                             est_per_sd=a_est * sd_a, se_per_sd=a_se * sd_a, p=z(a_est, a_se)))
        rows.append(dict(outcome=outcome, spec=spec, var=v, quantity="chronic_Delta", est=est, se=se,
                         est_per_sd=est_sd, se_per_sd=se_sd, p=z(est, se)))     # Wald test of eq. (5) = 0
    for f in flags:
        e, s = lincomb(fit, {f: 1.0})
        rows.append(dict(outcome=outcome, spec=spec, var=f, quantity="extreme_day_delta", est=e, se=s,
                         est_per_sd=np.nan, se_per_sd=np.nan, p=z(e, s)))
        # NET effect: flagged days minus other days of the same station-month, chronic terms plus delta
        if fit.Xd is not None:
            on = (fit.raw[f] == 1).to_numpy()
            m = fit.Xd[on].mean(axis=0) - fit.Xd[~on].mean(axis=0)
            w = {k_: float(v_) for k_, v_ in m.items() if k_ in chronic_terms() or k_ == f}
            tot, tse = lincomb(fit, w)
            ch, _ = lincomb(fit, {k_: v_ for k_, v_ in w.items() if k_ != f})
            rows.append(dict(outcome=outcome, spec=spec, var=f, quantity="net_extreme_effect", est=tot, se=tse,
                             est_per_sd=np.nan, se_per_sd=np.nan, p=z(tot, tse), net_chronic_part=ch,
                             net_flag_part=tot - ch, n_flagged=int(on.sum())))
    return pd.DataFrame(rows)


def main():
    log = []
    print("Loading hourly data ...")
    df = load_hourly()
    print(f"  {len(df):,} hourly rows, {df[STATION_COL].nunique()} stations")
    if "gust" not in df.columns:
        print("  NOTE: no gust file set (GUST_FILE). The high-wind flag E^W will not be estimated.")
    daily = build_daily(df)
    del df
    grid = to_full_grid(daily)
    if not os.path.exists(COASTAL_CSV):
        print("  coastal flag file not found: building it from the station coordinates ...")
        build_coastal_flags(INPUT_CSVS, COASTAL_CSV)
    grid = add_coastal(grid, COASTAL_CSV)
    grid = add_chronic(grid)
    grid = add_extremes(grid)
    grid = add_outcomes(grid)
    print(f"  daily grid: {int(grid['observed'].sum()):,} observed station-days, {grid[STATION_COL].nunique()} stations")

    flags = usable_flags(grid, log)
    obs = grid[grid["observed"]]
    pd.DataFrame([dict(flag=f, station_days=int(obs[f].sum()), share_pct=float(100 * obs[f].mean()),
                       stations_with_event=int(obs.loc[obs[f] == 1, STATION_COL].nunique()))
                  for f in ["ET", "EP1", "EP2", "EP3", "EW"] if f in obs.columns]).to_csv(out_path("event_counts.csv"), index=False)

    # baseline rate of each outcome in the estimation sample (used to express effects relative to it)
    est_sample = obs.dropna(subset=chronic_terms())
    pd.DataFrame([dict(outcome=o, baseline_mean=float(est_sample[f"y_{o}"].mean()), n=len(est_sample))
                  for o in OUTCOMES]).to_csv(out_path("outcome_summary.csv"), index=False)

    coefs_all, quant_all = [], []
    print("Main model, one fit per outcome ...")
    n_main = g_main = None
    for o in OUTCOMES:
        fit, xcols = fit_spec(grid, flags, ycol=f"y_{o}")
        coefs_all.append(tidy(fit, xcols, "main", o))
        quant_all.append(quantities(fit, flags, "main", o))
        n_main, g_main = fit.n, fit.n_clusters
        print(f"  {o}: N = {fit.n:,} station-days, G = {fit.n_clusters} stations")
        del fit
    pd.concat(coefs_all, ignore_index=True).to_csv(out_path("main_coefficients.csv"), index=False)
    pd.concat(quant_all, ignore_index=True).to_csv(out_path("main_quantities.csv"), index=False)

    pd.DataFrame([dict(item="n_station_days", note=str(n_main)), dict(item="n_stations", note=str(g_main)),
                  dict(item="date_min", note=str(obs["date"].min().date())),
                  dict(item="date_max", note=str(obs["date"].max().date())),
                  dict(item="coastal_stations_in_panel",
                       note=str(int(obs.loc[obs["coast_km"] <= COASTAL_KM, STATION_COL].nunique()))),
                  *log]).to_csv(out_path("sample_summary.csv"), index=False)

    # robustness: every specification, for every outcome
    print("Robustness ...")
    rob_c, rob_q = list(coefs_all), list(quant_all)
    specs = [("station_week_FE", dict(fe="station_week")),
             ("station_FE_plus_month", dict(fe="station")),
             ("two_way_cluster_station_date", dict(cluster="two_way")),
             ("cluster_era5_cell", dict(cluster="cell")),
             ("leads_added", dict(leads=True))]
    for name, kw in specs:
        for o in OUTCOMES:
            try:
                f2, x2 = fit_spec(grid, flags, ycol=f"y_{o}", **kw)
                rob_c.append(tidy(f2, x2, name, o))
                rob_q.append(quantities(f2, flags, name, o))
                if kw.get("leads"):
                    st, k, p = wald(f2, ["LEAD_T", "LEAD_P", "LEAD_W"])
                    rob_q.append(pd.DataFrame([dict(outcome=o, spec=name, var="leads", quantity="joint_wald_leads_zero",
                                                    est=st, se=np.nan, est_per_sd=np.nan, se_per_sd=np.nan, p=p)]))
                del f2
            except Exception as ex:
                print(f"  {name} / {o}: FAILED ({ex})")
                log.append(dict(item=f"{name}/{o}", note=f"failed: {ex}"))
        print(f"  {name}: done")

    alt = [("heat_3day", dict(heat_kw=dict(min_days=3))),
           ("coastal_25km", dict(heat_kw=dict(coastal_km=25.0))),
           ("coastal_50km", dict(heat_kw=dict(coastal_km=50.0)))]
    if "gust" in grid.columns:
        alt += [("gust_22", dict(gust_thr=22.0)), ("gust_25", dict(gust_thr=25.0))]
    for name, kw in alt:
        g2 = add_outcomes(add_extremes(grid, **kw))
        fl2 = [f for f in flags if f in g2.columns and g2.loc[g2["observed"], f].sum() >= MIN_EVENTS_PER_FLAG]
        for o in OUTCOMES:
            try:
                f2, x2 = fit_spec(g2, fl2, ycol=f"y_{o}")
                rob_c.append(tidy(f2, x2, name, o))
                rob_q.append(quantities(f2, fl2, name, o))
                del f2
            except Exception as ex:
                print(f"  {name} / {o}: FAILED ({ex})")
                log.append(dict(item=f"{name}/{o}", note=f"failed: {ex}"))
        print(f"  {name}: done")

    pd.concat(rob_c, ignore_index=True).to_csv(out_path("robustness_long.csv"), index=False)
    pd.concat(rob_q, ignore_index=True).to_csv(out_path("robustness_quantities.csv"), index=False)
    print("Done. Results in", OUTPUT_DIR)


if __name__ == "__main__":
    main()
'''

# ---------------------------------------------------------------- compute_percentile_model.py
_SOURCES['compute_percentile_model'] = r'''
"""
compute_percentile_model.py
===========================
Replaces the hand-set extreme flags (heat wave, IMD rain classes, 20 m/s gust) with PERCENTILE
THRESHOLDS computed separately for each climate zone, and traces how outages change as the percentile
rises. Needs compute_main_model.py in the same folder (data loading, daily panel, lag windows and the
fixed-effects estimator are reused) and writes CSVs to the same OUTPUT_DIR.

Same-day exposure is carried by the percentile terms; the lag windows (compute_main_model.WINDOWS) start at day 1.

Weather variables (daily, same definitions as the main model)
  T  daily maximum 2 m temperature (deg C)
  P  daily rainfall total (mm)     percentiles are taken over WET days (>= WET_DAY_MM), see below
  W  daily maximum of the hourly 10 m wind speed (m/s)

Thresholds and ranks
  thr[z, v, q]  = q-th percentile of the daily value over the station-days of zone z in the estimation sample.
  rank_it       = within-zone percentile rank (0-100) of station i's value on day t.
  Rain: over a third of days are dry, so rain percentiles and ranks use wet days (>= WET_DAY_MM), following
  ETCCDI. Dry days get rank 0 and are absorbed by a wet-day dummy in the spline models.

Four sets of models (each for every outcome in compute_main_model.OUTCOMES). Every model also controls for the other
  two variables' same-day percentile (spline terms), so each curve is adjusted for same-day rain, wind and temperature.
  1 SPLINE      Y = FE + chronic terms + f_v(rank) [+ wet-day dummy for rain] + e
                f_v is a restricted cubic spline in the percentile rank (knots SPLINE_KNOTS), reported relative to
                the median day (rank 50). This is the smooth dose-response curve, no cut-points needed.
  2 EXCEEDANCE  Y = FE + chronic terms + theta_{v,q} * 1[x >= thr_{z,v,q}] + e, one regression per (v, q) on a fine grid.
  3 BINS        Y = FE + chronic terms + sum_k theta_{v,k} * 1[thr_k <= x < thr_{k+1}] + e, exclusive bins, reference < p50.
  4 BY ZONE     the SPLINE model estimated inside each climate zone ("total" version).
  Two versions of each:
    "total"  lag-window terms of the SAME variable dropped (the other two variables' kept): the coefficient
             is the total difference associated with the percentile.
    "added"  all chronic terms kept: the effect over and above them (Hajat et al. 2006; Gasparrini & Armstrong 2011).
  FE = station x calendar-month effects, plus year dummies. Standard errors are clustered two-way by station and date
  (CLUSTER below), because extreme days hit many stations on the same date.

OUTPUTS (every file carries `outcome`)
  pct_thresholds.csv      threshold values by zone, variable and percentile
  pct_spline_curve.csv    fitted curve f(rank) - f(50) with 95% CI, pooled ("ALL") and by zone
  pct_exceedance.csv      exceedance coefficients on the fine percentile grid
  pct_bins.csv            exclusive-bin coefficients
  outcome_summary.csv     baseline mean of each outcome

Run: python compute_percentile_model.py     then   python plot_percentile_model.py
"""
import os
import sys
import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compute_main_model as cm

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
QUANTILES = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.925, 0.95, 0.975, 0.99, 0.995]
BIN_EDGES = [0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 0.975, 0.99, 0.995]       # exclusive bins start at these
SPLINE_KNOTS = [5, 25, 50, 90, 99]                                          # percentile ranks (0-100)
SPLINE_GRID = list(np.arange(1, 100, 1.0)) + [99.5]                         # ranks at which the curve is reported
REF_RANK = 50.0
WET_DAY_MM = 1.0
MIN_FLAGGED = 30
CLUSTER = "two_way"                                                         # "station" | "two_way"
VARS = ["T", "P", "W"]
COLMAP = {"T": "tmax", "P": "rain", "W": "wind"}
OUTCOMES = cm.OUTCOMES


# ----------------------------------------------------------------------
def reference_values(x, v):
    x = x.dropna()
    return x[x >= WET_DAY_MM] if v == "P" else x


def thresholds(est):
    rows = []
    qs = sorted(set(QUANTILES) | set(BIN_EDGES))
    for z, g in est.groupby("zone"):
        for v in VARS:
            x = g[COLMAP[v]]
            ref = reference_values(x, v)
            for q in qs:
                rows.append(dict(zone=z, var=v, q=q, threshold=float(np.quantile(ref, q)),
                                 threshold_all_days=float(np.quantile(x.dropna(), q)), n_days=int(x.notna().sum()),
                                 n_days_in_reference=len(ref), n_stations=g[cm.STATION_COL].nunique()))
    return pd.DataFrame(rows)


def add_ranks_and_flags(est, thr):
    est = est.copy()
    look = {(r.zone, r["var"], round(r.q, 4)): r.threshold for _, r in thr.iterrows()}
    zone = est["zone"].to_numpy()
    for v in VARS:
        x = est[COLMAP[v]].to_numpy()
        rank = np.zeros(len(est))
        for z in pd.unique(zone):
            m = zone == z
            ref = np.sort(reference_values(est.loc[m, COLMAP[v]], v).to_numpy())
            rank[m] = 100.0 * np.searchsorted(ref, x[m], side="right") / len(ref)
        if v == "P":
            rank[x < WET_DAY_MM] = 0.0
            est["WET_P"] = (x >= WET_DAY_MM).astype("float64")
        est[f"R_{v}"] = np.clip(rank, 0, 100)
        B = rcs_basis(est[f"R_{v}"].to_numpy(), SPLINE_KNOTS)
        for j in range(B.shape[1]):
            est[f"S{v}_{j}"] = B[:, j]          # same-day spline basis of this variable's percentile rank

        def t(q):
            return pd.Series(zone).map({z: look[(z, v, round(q, 4))] for z in pd.unique(zone)}).to_numpy()
        for q in QUANTILES:
            est[f"F_{v}_{q}"] = (x >= t(q)).astype("float64")
        for k, lo in enumerate(BIN_EDGES):
            m = x >= t(lo)
            if k + 1 < len(BIN_EDGES):
                m &= x < t(BIN_EDGES[k + 1])
            est[f"B_{v}_{lo}"] = m.astype("float64")
    return est


def rcs_basis(r, knots):
    """Restricted (natural) cubic spline basis (Harrell). r and knots on the 0-100 rank scale; returns
    k-1 columns: the linear term and k-2 nonlinear terms."""
    x = np.asarray(r, float) / 100.0
    t = np.asarray(knots, float) / 100.0
    k = len(t)
    cube = lambda u: np.maximum(u, 0.0) ** 3
    cols = [x]
    for j in range(k - 2):
        c = (cube(x - t[j]) - cube(x - t[k - 2]) * (t[k - 1] - t[j]) / (t[k - 1] - t[k - 2])
             + cube(x - t[k - 1]) * (t[k - 2] - t[j]) / (t[k - 1] - t[k - 2])) / (t[k - 1] - t[0]) ** 2
        cols.append(c)
    return np.column_stack(cols)


def own_terms(v):
    return [f"X{v}_{b}" for b in cm.WINDOWS]


def same_day_controls(v):
    """Same-day percentile (spline) terms of the OTHER two variables, so that e.g. cool days caused by rain
    do not load on temperature. Rain also brings its wet-day dummy."""
    cols = []
    for u in VARS:
        if u != v:
            cols += [f"S{u}_{j}" for j in range(len(SPLINE_KNOTS) - 1)]
            if u == "P":
                cols.append("WET_P")
    return cols


def controls(v, version):
    ch = cm.chronic_terms()
    lag = [c for c in ch if c not in own_terms(v)] if version == "total" else list(ch)
    return lag + same_day_controls(v)


def coef_rows(fit, names, meta):
    rows = []
    for n in names:
        c, se = float(fit.params[n]), float(np.sqrt(fit.cov.loc[n, n]))
        rows.append(dict(meta, term=n, coef=c, se=se, lo=c - 1.96 * se, hi=c + 1.96 * se,
                         p=float(2 * norm.sf(abs(c / se))) if se > 0 else np.nan, n=fit.n, n_clusters=fit.n_clusters))
    return rows


def spline_curve(d, v, version, o, meta):
    """Fit the spline model on d and return the curve f(r) - f(REF_RANK) with CI on SPLINE_GRID."""
    names = [f"S{v}_{j}" for j in range(len(SPLINE_KNOTS) - 1)]
    extra = ["WET_P"] if v == "P" else []
    fit = cm.fe_ols(d, f"y_{o}", controls(v, version) + names + extra, cluster=CLUSTER)
    base = rcs_basis([REF_RANK], SPLINE_KNOTS)[0]
    G = rcs_basis(SPLINE_GRID, SPLINE_KNOTS)
    rows = []
    for r, g in zip(SPLINE_GRID, G):
        est, se = cm.lincomb(fit, {n: float(g[j] - base[j]) for j, n in enumerate(names)})
        rows.append(dict(meta, rank=r, coef=est, se=se, lo=est - 1.96 * se, hi=est + 1.96 * se))
    return rows


def main():
    print("Loading hourly data and building the daily panel ...")
    df = cm.load_hourly()
    daily = cm.build_daily(df)
    del df
    grid = cm.to_full_grid(daily)
    if not os.path.exists(cm.COASTAL_CSV):
        cm.build_coastal_flags(cm.INPUT_CSVS, cm.COASTAL_CSV)
    grid = cm.add_coastal(grid, cm.COASTAL_CSV)
    grid = cm.add_chronic(grid)
    grid = cm.add_outcomes(cm.add_extremes(grid))
    est = grid[grid["observed"]].dropna(subset=cm.chronic_terms()).reset_index(drop=True)
    print(f"  estimation sample: {len(est):,} station-days, {est[cm.STATION_COL].nunique()} stations; "
          f"zones: {est.groupby('zone')[cm.STATION_COL].nunique().to_dict()}")

    thr = thresholds(est)
    thr.to_csv(cm.out_path("pct_thresholds.csv"), index=False)
    est = add_ranks_and_flags(est, thr)
    pd.DataFrame([dict(outcome=o, baseline_mean=float(est[f"y_{o}"].mean()), n=len(est)) for o in OUTCOMES]
                 ).to_csv(cm.out_path("outcome_summary.csv"), index=False)

    # ---- 1 + 4: spline curves, pooled and by zone ----
    print("\nSpline models ...")
    rows = []
    for version in ("total", "added"):
        for v in VARS:
            for o in OUTCOMES:
                rows += spline_curve(est, v, version, o, dict(zone="ALL", version=version, var=v, outcome=o))
        print(f"  pooled {version}: done")
    for z, g in est.groupby("zone"):
        g = g.reset_index(drop=True)
        for v in VARS:
            for o in OUTCOMES:
                try:
                    rows += spline_curve(g, v, "total", o, dict(zone=z, version="total", var=v, outcome=o,
                                                                n_stations=g[cm.STATION_COL].nunique()))
                except Exception as ex:
                    print(f"  skipped {z}/{v}/{o}: {ex}")
        print(f"  zone {z}: done")
    pd.DataFrame(rows).to_csv(cm.out_path("pct_spline_curve.csv"), index=False)

    # ---- 2: exceedance on the fine grid ----
    print("Exceedance models ...")
    rows = []
    for version in ("total", "added"):
        for v in VARS:
            for q in QUANTILES:
                f = f"F_{v}_{q}"
                nfl = int(est[f].sum())
                if nfl < MIN_FLAGGED:
                    continue
                for o in OUTCOMES:
                    fit = cm.fe_ols(est, f"y_{o}", controls(v, version) + [f], cluster=CLUSTER)
                    rows += coef_rows(fit, [f], dict(version=version, var=v, q=q, outcome=o, n_flagged=nfl))
        print(f"  {version}: done")
    pd.DataFrame(rows).to_csv(cm.out_path("pct_exceedance.csv"), index=False)

    # ---- 3: bins ----
    print("Bin models ...")
    rows = []
    for version in ("total", "added"):
        for v in VARS:
            bins = [b for b in (f"B_{v}_{lo}" for lo in BIN_EDGES) if est[b].sum() >= MIN_FLAGGED]
            for o in OUTCOMES:
                fit = cm.fe_ols(est, f"y_{o}", controls(v, version) + bins, cluster=CLUSTER)
                for b in bins:
                    lo = float(b.split("_")[-1])
                    hi = BIN_EDGES[BIN_EDGES.index(lo) + 1] if BIN_EDGES.index(lo) + 1 < len(BIN_EDGES) else 1.0
                    rows += coef_rows(fit, [b], dict(version=version, var=v, q=lo, q_hi=hi, outcome=o,
                                                     n_flagged=int(est[b].sum())))
    pd.DataFrame(rows).to_csv(cm.out_path("pct_bins.csv"), index=False)
    print("Done. Results in", cm.OUTPUT_DIR)


if __name__ == "__main__":
    main()
'''

# ---------------------------------------------------------------- compute_interaction_model.py
_SOURCES['compute_interaction_model'] = r'''
"""
compute_interaction_model.py
============================
Does a same-day weather extreme (the ACUTE shock) do more damage after a stretch of stressful weather (the CHRONIC
state)? Needs compute_main_model.py and compute_percentile_model.py in the same folder.

PAIRS (pre-specified on physical grounds; edit PAIRS to change them)
  rain -> rain   saturated ground and a loaded grid:  prior-30-day rain high,  then a rain extreme today
  heat -> heat   equipment stress:                    prior-30-day heat high,  then a heat extreme today
  heat -> rain   equipment already stressed by heat:  prior-30-day heat high,  then a rain extreme today

DEFINITIONS (all thresholds are percentiles within the station's climate zone)
  chronic state C_it   1 if the mean of the variable over the previous CHRONIC_DAYS days (days t-1 ... t-30) is at or above
                       the zone's CHRONIC_Q-th percentile of that 30-day mean. Heat = daily max temperature, rain = daily total.
  acute shock   D_it   1 if the day's value is at or above the zone's SAME_Q-th percentile (rain: percentile of wet days, as in
                       compute_percentile_model.py).

MODEL (one regression per pair, outcome, SAME_Q, CHRONIC_Q)
  Y_it = alpha_{i,m(t)} + gamma_{y(t)} + sum_v sum_b beta^v_b X^v_{it,b}          lag windows of all three variables
         + same-day spline terms of the variables other than the acute one         (as in compute_percentile_model.py)
         + d1 D_it + d2 C_it + d3 (D_it x C_it) + e_it
  d1  acute effect when the chronic state is normal;   d1 + d3  acute effect after chronic stress;   d3  the INTERACTION:
  how much the acute effect changes after chronic stress. FE = station x calendar month, plus year dummies; standard errors
  clustered by station and date.

OUTPUTS (every file carries `outcome`)
  interaction_results.csv   per pair x outcome x threshold pair: d1, d2, d3, d1 + d3 with SE and p, and the number of
                            station-days in each of the four cells (acute x chronic)

The interaction describes how the association differs by chronic state; it is not a causal mechanism.

Run: python compute_interaction_model.py     then   python plot_interaction_model.py
"""
import os
import sys
import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compute_main_model as cm
import compute_percentile_model as cpm

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
# (name, chronic variable, acute variable)
# (name, chronic variable, acute variable, direction): direction "high" = prior mean at or above the zone percentile,
# "low" = prior mean at or below the zone's (1 - q) percentile (a dry or cool spell).
PAIRS = [("rain_rain", "P", "P", "high"), ("heat_heat", "T", "T", "high"), ("heat_rain", "T", "P", "high"),
         ("heat_wind", "T", "W", "high"), ("rain_wind", "P", "W", "high"), ("rain_heat", "P", "T", "high"),
         ("wind_rain", "W", "P", "high"), ("wind_wind", "W", "W", "high"), ("wind_heat", "W", "T", "high"),
         ("dry_heat", "P", "T", "low"), ("dry_rain", "P", "P", "low"), ("dry_wind", "P", "W", "low")]
CHRONIC_DAYS_LIST = [7, 14, 30]                  # length of the prior window (days t-1 ... t-N)
MAIN_DAYS = 30
CHRONIC_QS = [0.75, 0.90]                        # the state is "prior mean at or above this zone percentile"
SAME_QS = [0.90, 0.95]                           # the acute shock is "today at or above this zone percentile"
MAIN = (0.75, 0.95)                              # (chronic q, same-day q) shown in the main figure
MIN_CELL = 30                                    # skip a model if the acute x chronic cell has fewer station-days
SERIES = {"T": "tmax", "P": "rain", "W": "wind"}
CLUSTER = "two_way"
OUTCOMES = cm.OUTCOMES


def add_prior_state(grid):
    """Mean of the variable over days t-1 ... t-CHRONIC_DAYS, and its zone-specific percentiles."""
    for v, col in SERIES.items():
        M = cm.lag_matrix(grid, col, max(CHRONIC_DAYS_LIST))
        for n in CHRONIC_DAYS_LIST:
            grid[f"PRIOR_{v}_{n}"] = cm.window_mean(M, 1, n + 1)
    return grid


def main():
    print("Loading hourly data and building the daily panel ...")
    df = cm.load_hourly()
    daily = cm.build_daily(df)
    del df
    grid = cm.to_full_grid(daily)
    if not os.path.exists(cm.COASTAL_CSV):
        cm.build_coastal_flags(cm.INPUT_CSVS, cm.COASTAL_CSV)
    grid = cm.add_coastal(grid, cm.COASTAL_CSV)
    grid = cm.add_chronic(grid)
    grid = add_prior_state(grid)
    grid = cm.add_outcomes(cm.add_extremes(grid))
    est = grid[grid["observed"]].dropna(subset=cm.chronic_terms() + [f"PRIOR_{v}_{MAIN_DAYS}" for v in SERIES]).reset_index(drop=True)
    est = cpm.add_ranks_and_flags(est, cpm.thresholds(est))
    print(f"  estimation sample: {len(est):,} station-days, {est[cm.STATION_COL].nunique()} stations")

    # chronic-state flags: prior mean at or above (high) / at or below (low) the zone's percentile
    for v in SERIES:
        for n in CHRONIC_DAYS_LIST:
            for q in CHRONIC_QS:
                g = est.groupby("zone")[f"PRIOR_{v}_{n}"]
                est[f"C_{v}_{n}_{q}_high"] = (est[f"PRIOR_{v}_{n}"] >= g.transform(lambda s: s.quantile(q))).astype(float)
                est[f"C_{v}_{n}_{q}_low"] = (est[f"PRIOR_{v}_{n}"] <= g.transform(lambda s: s.quantile(1 - q))).astype(float)

    rows = []
    for name, cv, av, dirn in PAIRS:
        controls = cm.chronic_terms() + cpm.same_day_controls(av)
        for nd in CHRONIC_DAYS_LIST:
          for cq in CHRONIC_QS:
            for sq in SAME_QS:
                D, C = f"F_{av}_{sq}", f"C_{cv}_{nd}_{cq}_{dirn}"
                est["_DC"] = est[D] * est[C]
                cells = {"neither": int(((est[D] == 0) & (est[C] == 0)).sum()), "chronic_only": int(((est[D] == 0) & (est[C] == 1)).sum()),
                         "acute_only": int(((est[D] == 1) & (est[C] == 0)).sum()), "both": int(((est[D] == 1) & (est[C] == 1)).sum())}
                if min(cells["acute_only"], cells["both"]) < MIN_CELL:
                    print(f"  skip {name} n={nd} cq={cq} sq={sq}: thin cells {cells}")
                    continue
                for o in OUTCOMES:
                    fit = cm.fe_ols(est, f"y_{o}", controls + [D, C, "_DC"], cluster=CLUSTER)
                    for label, w in (("acute_when_normal", {D: 1.0}), ("chronic_only", {C: 1.0}), ("interaction", {"_DC": 1.0}),
                                     ("acute_after_chronic_stress", {D: 1.0, "_DC": 1.0})):
                        e, sd = cm.lincomb(fit, w)
                        rows.append(dict(pair=name, direction=dirn, chronic_days=nd, outcome=o, chronic_q=cq, same_q=sq, quantity=label,
                                         est=e, se=sd, lo=e - 1.96 * sd, hi=e + 1.96 * sd,
                                         p=float(2 * norm.sf(abs(e / sd))) if sd > 0 else np.nan,
                                         n=fit.n, **{f"cell_{k}": v for k, v in cells.items()}))
        print(f"  {name} done", flush=True)
    pd.DataFrame(rows).to_csv(cm.out_path("interaction_results.csv"), index=False)
    print("Done. Results in", cm.OUTPUT_DIR)


if __name__ == "__main__":
    main()
'''

# ---------------------------------------------------------------- check_interaction_robustness.py
_SOURCES['check_interaction_robustness'] = r'''
"""
check_interaction_robustness.py
===============================
Stress-tests the interaction estimates that look positive in compute_interaction_model.py. Needs compute_main_model.py,
compute_percentile_model.py and compute_interaction_model.py in the same folder.

CASES (chronic state -> acute shock, outcome in which the interaction looked positive)
  dry_heat   prior-30-day rain at or below the zone's 25th percentile  -> heat extreme today   (>= 1 h, >= 12 h)
  heat_wind  prior-30-day heat at or above the zone's 75th percentile  -> wind extreme today   (>= 12 h)
  wind_rain  prior-30-day wind at or above the zone's 75th percentile  -> rain extreme today   (>= 1 h)

CHECKS (each reports the interaction d3 = how much the acute effect changes after chronic stress)
  baseline            the model of compute_interaction_model.py
  seasonal_acute      + acute shock x calendar month   (the acute effect may differ by season, and chronic states are seasonal)
  zone_acute          + acute shock x climate zone
  skip_3d             chronic state measured over days t-33 ... t-4, leaving out the last three days before t
  future_placebo      chronic state measured over the NEXT 30 days (t+1 ... t+30): it cannot cause today's outage, so a
                      similar d3 points to persistence or seasonality rather than a build-up
  continuous          the state enters as the zone z-score of the prior mean instead of a flag (d3 per +1 SD)
  by_zone             separate model per climate zone
  by_period           separate model for the first and second half of the years
  drop_zone           leave one climate zone out
  permuted            the chronic flag is permuted across years within station x calendar month (keeps season and station,
                      breaks the link to the actual preceding weather); mean and 2.5/97.5 percentiles of d3 over N_PERM draws

OUTPUT  interaction_robustness.csv    Run: python check_interaction_robustness.py
"""
import os, sys
import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compute_main_model as cm
import compute_percentile_model as cpm
import compute_interaction_model as cim

CASES = [("dry_heat", "P", "T", "low", ["ge1h", "ge12h"]),
         ("heat_wind", "T", "W", "high", ["ge12h"]),
         ("wind_rain", "W", "P", "high", ["ge1h"])]
N_DAYS, CQ, SQS = 30, 0.75, [0.90, 0.95]
N_PERM = 200
SEED = 1


def future_mean(grid, col, n):
    def f(s):
        return s[::-1].rolling(n, min_periods=int(0.7 * n)).mean()[::-1].shift(-1)
    return grid.groupby(cm.STATION_COL)[col].transform(f)


def flag(est, col, q, dirn):
    g = est.groupby("zone")[col]
    return (est[col] >= g.transform(lambda s: s.quantile(q))).astype(float) if dirn == "high" else \
           (est[col] <= g.transform(lambda s: s.quantile(1 - q))).astype(float)


def d3(est, o, controls, D, C, sub=None):
    d = est if sub is None else est[sub]
    if min(((d[D] == 1) & (d[C] == 0)).sum(), ((d[D] == 1) & (d[C] == 1)).sum()) < 30:
        return None
    d = d.copy(); d["_DC"] = d[D] * d[C]
    fit = cm.fe_ols(d, f"y_{o}", controls + [D, C, "_DC"], cluster=cim.CLUSTER)
    e, s = cm.lincomb(fit, {"_DC": 1.0})
    a, sa = cm.lincomb(fit, {D: 1.0})
    return dict(est=e, se=s, lo=e - 1.96 * s, hi=e + 1.96 * s, p=float(2 * norm.sf(abs(e / s))) if s > 0 else np.nan,
                acute_when_normal=a, n=fit.n, cell_acute_only=int(((d[D] == 1) & (d[C] == 0)).sum()), cell_both=int(((d[D] == 1) & (d[C] == 1)).sum()))


def main():
    rng = np.random.default_rng(SEED)
    df = cm.load_hourly(); daily = cm.build_daily(df); del df
    grid = cm.to_full_grid(daily)
    if not os.path.exists(cm.COASTAL_CSV):
        cm.build_coastal_flags(cm.INPUT_CSVS, cm.COASTAL_CSV)
    grid = cm.add_coastal(grid, cm.COASTAL_CSV)
    grid = cm.add_chronic(grid)
    cim.CHRONIC_DAYS_LIST = [N_DAYS]
    grid = cim.add_prior_state(grid)
    for v, col in cim.SERIES.items():
        M = cm.lag_matrix(grid, col, N_DAYS + 3)
        grid[f"SKIP_{v}"] = cm.window_mean(M, 4, N_DAYS + 4)
        grid[f"FUT_{v}"] = future_mean(grid, col, N_DAYS)
    grid = cm.add_outcomes(cm.add_extremes(grid))
    need = cm.chronic_terms() + [f"PRIOR_{v}_{N_DAYS}" for v in cim.SERIES]
    est = grid[grid["observed"]].dropna(subset=need).reset_index(drop=True)
    est = cpm.add_ranks_and_flags(est, cpm.thresholds(est))
    est["_month"] = est["date"].dt.month
    est["_year"] = est["date"].dt.year
    zones = sorted(est["zone"].unique())
    print(f"sample {len(est):,} station-days, zones {zones}", flush=True)
    rows = []

    def add(case, o, sq, check, r, extra=""):
        if r is not None:
            rows.append(dict(case=case, outcome=o, chronic_q=CQ, same_q=sq, check=check, detail=extra, **r))

    for name, cv, av, dirn, outs in CASES:
        base = f"PRIOR_{cv}_{N_DAYS}"
        est["_C"] = flag(est, base, CQ, dirn)
        est["_Cskip"] = flag(est.dropna(subset=[f"SKIP_{cv}"]).reindex(est.index), f"SKIP_{cv}", CQ, dirn)
        est["_Cfut"] = flag(est, f"FUT_{cv}", CQ, dirn).where(est[f"FUT_{cv}"].notna())
        est["_Z"] = (est[base] - est.groupby("zone")[base].transform("mean")) / est.groupby("zone")[base].transform("std")
        if dirn == "low":
            est["_Z"] = -est["_Z"]
        for sq in SQS:
            D = f"F_{av}_{sq}"
            controls = cm.chronic_terms() + cpm.same_day_controls(av)
            mdum = pd.get_dummies(est["_month"], prefix="Dm").astype(float).mul(est[D], axis=0).iloc[:, 1:]
            zdum = pd.get_dummies(est["zone"], prefix="Dz").astype(float).mul(est[D], axis=0).iloc[:, 1:]
            mdum = mdum.loc[:, (mdum.sum() >= 30)]
            zdum = zdum.loc[:, (zdum.sum() >= 30)]
            for c in list(mdum) + list(zdum):
                est[c] = pd.concat([mdum, zdum], axis=1)[c]
            for o in outs:
                print(name, sq, o, flush=True)
                add(name, o, sq, "baseline", d3(est, o, controls, D, "_C"))
                add(name, o, sq, "seasonal_acute", d3(est, o, controls + list(mdum), D, "_C"))
                add(name, o, sq, "zone_acute", d3(est, o, controls + list(zdum), D, "_C"))
                add(name, o, sq, "skip_3d", d3(est, o, controls, D, "_Cskip", est["_Cskip"].notna()))
                add(name, o, sq, "future_placebo", d3(est, o, controls, D, "_Cfut", est["_Cfut"].notna()))
                add(name, o, sq, "continuous", d3(est, o, controls, D, "_Z"))
                for z in zones:
                    add(name, o, sq, "by_zone", d3(est, o, controls, D, "_C", est["zone"] == z), z)
                    add(name, o, sq, "drop_zone", d3(est, o, controls, D, "_C", est["zone"] != z), z)
                yrs = sorted(est["_year"].unique()); half = yrs[len(yrs) // 2]
                add(name, o, sq, "by_period", d3(est, o, controls, D, "_C", est["_year"] < half), f"<{half}")
                add(name, o, sq, "by_period", d3(est, o, controls, D, "_C", est["_year"] >= half), f">={half}")
                # permutation: shuffle the chronic flag across years within station x calendar month
                key = est[cm.STATION_COL].astype(str) + "_" + est["_month"].astype(str)
                draws = []
                for _ in range(N_PERM):
                    perm = est.groupby(key)["_C"].transform(lambda s: rng.permutation(s.to_numpy()))
                    est["_Cp"] = perm.to_numpy()
                    r = d3_fast(est, o, controls, D, "_Cp")
                    if r is not None:
                        draws.append(r)
                if draws:
                    obs = d3(est, o, controls, D, "_C")["est"]
                    draws = np.array(draws)
                    rows.append(dict(case=name, outcome=o, chronic_q=CQ, same_q=sq, check="permuted", detail=f"{len(draws)} draws",
                                     est=float(draws.mean()), lo=float(np.percentile(draws, 2.5)), hi=float(np.percentile(draws, 97.5)),
                                     p=float((np.abs(draws) >= abs(obs)).mean())))
    pd.DataFrame(rows).to_csv(cm.out_path("interaction_robustness.csv"), index=False)
    print("Done")


def d3_fast(est, o, controls, D, C):
    """Point estimate only (no standard errors): used for the permutation draws."""
    d = est.copy(); d["_DC"] = d[D] * d[C]
    if min(((d[D] == 1) & (d[C] == 0)).sum(), ((d[D] == 1) & (d[C] == 1)).sum()) < 30:
        return None
    fit = cm.fe_ols(d, f"y_{o}", controls + [D, C, "_DC"], cluster="station")
    return cm.lincomb(fit, {"_DC": 1.0})[0]


if __name__ == "__main__":
    main()
'''

# ---------------------------------------------------------------- compute_irf.py
_SOURCES['compute_irf'] = r'''
"""
compute_irf.py
==============
Impulse-response functions of outages to weather, estimated as daily distributed-lag models (a local-projection-style
alternative is noted at the bottom). Needs compute_main_model.py and compute_percentile_model.py in the same folder.

WHY DISTRIBUTED LAGS, NOT A VAR
  Weather is exogenous to outages (outages do not change tomorrow's temperature, rain or wind), so no feedback loop
  needs to be modelled. A VAR would add structure we do not need. With exogenous shocks, the coefficient on the lag-k
  value of the weather variable in a regression of Y_it on lags -L..K IS the impulse response at horizon k.

TWO MODELS (each for every outcome in compute_main_model.OUTCOMES)
  DL     Y_it = alpha_{i,m(t)} + gamma_{y(t)} + sum_v sum_{k=-L..K} b^v_k x^v_{i,t-k} + e_it
         x^T = daily max temperature, x^P = ln(1 + daily rain mm), x^W = daily max wind. b^v_k is the change in the
         outcome k days after a +1 SD change in x^v (per within-station-month SD), holding the other days' weather fixed.
         k < 0 are LEADS (future weather): a placebo that should be zero. The cumulative response is the running sum.
  EVENT  Y_it = alpha_{i,m(t)} + gamma_{y(t)} + sum_v sum_{k=-L..K} c^v_k 1[x^v_{i,t-k} >= thr_{zone,v,q}] + e_it
         the same idea with an extreme-day indicator (zone-specific percentile q, as in compute_percentile_model.py):
         c^v_k is the change in the outcome k days after a day at or above the q-th percentile. The leads (k < 0) are the
         usual event-study pre-trend check.
  FE = station x calendar-month, plus year dummies; standard errors clustered by station and date.

OUTPUTS (CSV, every file carries `outcome`)
  irf_dl.csv            b^v_k per SD with 95% CI, and the cumulative response from k = 0
  irf_event_q95.csv     c^v_k (pp) with 95% CI and cumulative response, for event percentile EVENT_QUANTILES[0], etc.
  irf_leads_tests.csv   joint Wald test that all leads are zero, per model, outcome and variable
  irf_event_grid.csv    event-study responses for every percentile threshold, lags -L..GRID_LAG_DAYS. Column `tail` is "upper"
                        (a day at or above the q-th zone percentile, q = 0.50 ... 0.99) or "lower" (a day at or below it,
                        q = 0.01 ... 0.40), so the grid covers the whole 0-100 range.
  irf_event_grid_by_zone.csv  the same grid, estimated inside each climate zone
  irf_bins.csv          event-study responses of percentile BINS relative to the median band (one regression per variable, all
                        bins and lags -L..GRID_LAG_DAYS together), pooled ("ALL") and inside each climate zone. This is the
                        full 0-100 percentile surface on one scale: every bin is compared with the same reference days.
  irf_dl_by_zone.csv    distributed-lag response per +1 SD (the zone's own within-station-month SD), estimated inside each zone
  irf_grid_leads_tests.csv    leads tests for the grid models
(python compute_irf.py --grid-only  re-runs only the threshold grid.)

Run: python compute_irf.py      then   python plot_irf.py
"""
import os
import sys
import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compute_main_model as cm
import compute_percentile_model as cpm

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
LEADS_DAYS = 7              # L: days of future weather used as a placebo
LAG_DAYS = 30               # K: horizon of the response, in days
EVENT_QUANTILES = [0.95, 0.99]                       # long-horizon event models (K = LAG_DAYS)
GRID_QUANTILES = [0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 0.975, 0.99]   # upper tail: a day AT OR ABOVE the zone percentile
GRID_LOWER_QUANTILES = []                            # optional lower-tail events (a day AT OR BELOW the zone percentile); the
                                                     # bin models below cover the lower tail on one consistent scale instead
BIN_EDGES_PCT = [0, 5, 15, 30, 40, 60, 70, 80, 90, 95, 99, 100]   # zone-percentile bins of the same-day weather
REF_BIN = (40, 60)                                   # reference: the median band; every other bin is compared with it
                                                     # (rain: bins are over wet days; dry days get their own indicator, "dry")
GRID_LAG_DAYS = 14                                   # the response is over within days, so the grid uses a shorter horizon
GRID_OUTCOMES = ["ge1h", "ge6h", "ge12h"]
MIN_EVENTS_ZONE = 10                                 # a lag regressor needs at least this many event days inside a zone
ZONE_GRID_QUANTILES = None                           # None = every threshold of the grid is also estimated inside each climate zone
CLUSTER = "two_way"
VARS = ["T", "P", "W"]
SERIES = {"T": "tmax", "P": "rain", "W": "wind"}
OUTCOMES = cm.OUTCOMES
KS = list(range(-LEADS_DAYS, LAG_DAYS + 1))


def series_values(grid, v):
    x = grid[SERIES[v]]
    return np.log1p(x) if v == "P" else x


def lag_columns(grid, base, name, store, ks=None):
    """Store columns <name>_<k> = the value k days earlier (k < 0: k days later); return their names."""
    tmp = pd.DataFrame({cm.STATION_COL: grid[cm.STATION_COL].to_numpy(), "_b": np.asarray(base, float)})
    cols = []
    for k in (KS if ks is None else ks):
        c = f"{name}_{k}"
        store[c] = tmp.groupby(cm.STATION_COL, sort=False)["_b"].shift(k).to_numpy()
        cols.append(c)
    return cols


def rows_for(fit, cols, var, scale, meta, ks=None):
    """Coefficients, cumulative response from k = 0, and the leads Wald test."""
    out, cum_w = [], {}
    for k, c in zip(KS if ks is None else ks, cols):
        est, se = cm.lincomb(fit, {c: scale})
        row = dict(meta, var=var, k=k, coef=est, se=se, lo=est - 1.96 * se, hi=est + 1.96 * se,
                   p=float(2 * norm.sf(abs(est / se))) if se > 0 else np.nan)
        if k >= 0:
            cum_w[c] = scale
            ce, cs = cm.lincomb(fit, dict(cum_w))
            row.update(cum=ce, cum_lo=ce - 1.96 * cs, cum_hi=ce + 1.96 * cs)
        out.append(row)
    return out


def extra_thresholds(obs, qs):
    """Zone-specific thresholds at quantiles qs, keyed like `look`: (zone, variable, q). Rain is ranked among wet days."""
    out = {}
    for z, g in obs.groupby("zone"):
        for v in VARS:
            ref = cpm.reference_values(g[SERIES[v]], v)
            for q in qs:
                out[(z, v, round(q, 4))] = float(np.quantile(ref, q))
    return out


def bin_flag(grid, v, lo, hi, look):
    """1 on days whose zone-percentile lies in [lo, hi) (percent, 0-100; hi = 100 includes the maximum); rain: wet days only."""
    zones = grid["zone"].dropna().unique()
    x = grid[SERIES[v]].to_numpy()

    def thr(e, low):
        if e <= 0:
            return -np.inf
        if e >= 100:
            return np.inf
        return grid["zone"].map({z: look[(z, v, round(e / 100, 4))] for z in zones}).to_numpy()
    with np.errstate(invalid="ignore"):
        hit = (x >= thr(lo, True)) & (x < thr(hi, False))
        if v == "P":
            hit = hit & (x >= cpm.WET_DAY_MM)
    return np.where(np.isnan(x), np.nan, hit.astype(float))


def event_flag(grid, v, q, tail, look):
    """1 on days at or above (upper) / at or below (lower) the zone's q-th percentile, NaN where the weather is missing."""
    t = grid["zone"].map({z: look[(z, v, round(q, 4))] for z in grid["zone"].dropna().unique()}).to_numpy()
    x = grid[SERIES[v]].to_numpy()
    with np.errstate(invalid="ignore"):
        hit = (x >= t) if tail == "upper" else (x <= t)
        if tail == "lower" and v == "P":
            hit = hit & (x >= cpm.WET_DAY_MM)             # a light-rain day is a wet day, not a dry one
    return np.where(np.isnan(x), np.nan, hit.astype(float))


def build_grid():
    print("Loading hourly data and building the daily panel ...")
    df = cm.load_hourly()
    daily = cm.build_daily(df)
    del df
    grid = cm.to_full_grid(daily)
    if not os.path.exists(cm.COASTAL_CSV):
        cm.build_coastal_flags(cm.INPUT_CSVS, cm.COASTAL_CSV)
    grid = cm.add_coastal(grid, cm.COASTAL_CSV)
    grid = cm.add_outcomes(grid)
    obs = grid[grid["observed"]]
    # thresholds from the observed station-days (same definition as compute_percentile_model.py)
    thr = cpm.thresholds(obs)
    look = {(r.zone, r["var"], round(r.q, 4)): r.threshold for _, r in thr.iterrows()}
    look.update(extra_thresholds(obs, GRID_LOWER_QUANTILES))
    edges = sorted({e / 100 for e in BIN_EDGES_PCT if 0 < e < 100})
    look.update(extra_thresholds(obs, [q for q in edges if (obs["zone"].iloc[0], "T", round(q, 4)) not in look]))
    return grid, look


def main():
    grid, look = build_grid()

    dl_cols, ev_cols, store = {}, {}, {}
    for v in VARS:
        dl_cols[v] = lag_columns(grid, series_values(grid, v).to_numpy(), f"D{v}", store)
    for q in EVENT_QUANTILES:
        for v in VARS:
            flag = event_flag(grid, v, q, "upper", look)
            ev_cols[(q, v)] = lag_columns(grid, flag, f"E{v}{int(round(q * 1000))}", store)
    grid = pd.concat([grid, pd.DataFrame(store, index=grid.index)], axis=1)
    del store
    print(f"  built lag columns for k = {KS[0]} ... {KS[-1]}")

    base_cols = [c for v in VARS for c in dl_cols[v]]
    d = grid[grid["observed"]].dropna(subset=base_cols).reset_index(drop=True)
    print(f"  complete-case sample for the DL model: {len(d):,} station-days, {d[cm.STATION_COL].nunique()} stations")

    leads_rows = []
    print("DL (continuous) models ...")
    rows = []
    for o in OUTCOMES:
        fit = cm.fe_ols(d, f"y_{o}", base_cols, cluster=CLUSTER)
        for v in VARS:
            sd0 = float(fit.sd_within[f"D{v}_0"])          # one SD of the within-station-month variation of day-t value
            rows += rows_for(fit, dl_cols[v], v, sd0, dict(outcome=o, sd=sd0, n=fit.n, n_clusters=fit.n_clusters))
            lead_names = [c for k, c in zip(KS, dl_cols[v]) if k < 0]
            st, df_, p = cm.wald(fit, lead_names)
            leads_rows.append(dict(model="DL", outcome=o, var=v, wald=st, df=df_, p=p))
        print(f"  {o} done")
    pd.DataFrame(rows).to_csv(cm.out_path("irf_dl.csv"), index=False)
    print("DL models by climate zone ...")
    dl_by_zone(d, base_cols)

    for q in EVENT_QUANTILES:
        print(f"Event models, percentile {q} ...")
        cols = [c for v in VARS for c in ev_cols[(q, v)]]
        de = grid[grid["observed"]].dropna(subset=cols).reset_index(drop=True)
        print(f"  complete-case sample: {len(de):,} station-days")
        rows = []
        for o in OUTCOMES:
            fit = cm.fe_ols(de, f"y_{o}", cols, cluster=CLUSTER)
            for v in VARS:
                n_ev = int(de[f"E{v}{int(round(q * 1000))}_0"].sum())
                rows += rows_for(fit, ev_cols[(q, v)], v, 1.0, dict(outcome=o, q=q, n_events=n_ev, n=fit.n))
                lead_names = [c for k, c in zip(KS, ev_cols[(q, v)]) if k < 0]
                st, df_, p = cm.wald(fit, lead_names)
                leads_rows.append(dict(model=f"EVENT_q{q}", outcome=o, var=v, wald=st, df=df_, p=p))
            print(f"  {o} done")
        pd.DataFrame(rows).to_csv(cm.out_path(f"irf_event_q{int(round(q * 100))}.csv"), index=False)

    pd.DataFrame(leads_rows).to_csv(cm.out_path("irf_leads_tests.csv"), index=False)
    grid_models(grid, look)
    bin_models(grid, look)
    print("Done. Results in", cm.OUTPUT_DIR)


def grid_models(grid, look):
    """Event-study impulse responses for many zone-specific percentile thresholds (both tails), pooled and by climate zone."""
    ks = list(range(-LEADS_DAYS, GRID_LAG_DAYS + 1))
    keep = [cm.STATION_COL, "date", "zone", "observed"] + [f"y_{o}" for o in GRID_OUTCOMES]
    specs = [("lower", q) for q in GRID_LOWER_QUANTILES] + [("upper", q) for q in GRID_QUANTILES]
    zone_specs = specs if ZONE_GRID_QUANTILES is None else [(t, q) for t, q in specs if q in ZONE_GRID_QUANTILES]
    rows, rows_z, leads = [], [], []
    for tail, q in specs:
        store, cols = {}, {}
        for v in VARS:
            cols[v] = lag_columns(grid, event_flag(grid, v, q, tail, look), f"E{v}", store, ks)
        d = pd.concat([grid[keep], pd.DataFrame(store, index=grid.index)], axis=1)
        d = d[d["observed"]].dropna(subset=[c for v in VARS for c in cols[v]]).reset_index(drop=True)
        allc = [c for v in VARS for c in cols[v]]
        print(f"Grid, {tail} tail, percentile {q}: {len(d):,} station-days")
        for o in GRID_OUTCOMES:
            fit = cm.fe_ols(d, f"y_{o}", allc, cluster=CLUSTER)
            for v in VARS:
                n_ev = int(d[f"E{v}_0"].sum())
                rows += rows_for(fit, cols[v], v, 1.0, dict(outcome=o, q=q, tail=tail, n_events=n_ev, n=fit.n), ks)
                st, df_, p = cm.wald(fit, [c for k, c in zip(ks, cols[v]) if k < 0])
                leads.append(dict(model=f"GRID_{tail}_q{q}", outcome=o, var=v, wald=st, df=df_, p=p))
        if (tail, q) in zone_specs:
            for z, g in d.groupby("zone"):
                g = g.reset_index(drop=True)
                # inside a zone some lags have (almost) no events: drop those regressors so the fit is not singular
                zc = {v: [(k, c) for k, c in zip(ks, cols[v]) if g[c].sum() >= MIN_EVENTS_ZONE] for v in VARS}
                allz = [c for v in VARS for _, c in zc[v]]
                for o in GRID_OUTCOMES:
                    try:
                        fit = cm.fe_ols(g, f"y_{o}", allz, cluster=CLUSTER)
                    except Exception as ex:
                        print(f"  skipped zone {z} / {o}: {ex}")
                        continue
                    for v in VARS:
                        if not zc[v]:
                            continue
                        rows_z += rows_for(fit, [c for _, c in zc[v]], v, 1.0,
                                           dict(zone=z, outcome=o, q=q, tail=tail, n_events=int(g[f"E{v}_0"].sum()),
                                                n=fit.n, n_stations=g[cm.STATION_COL].nunique()), [k for k, _ in zc[v]])
        pd.DataFrame(rows).to_csv(cm.out_path("irf_event_grid.csv"), index=False)       # saved after every threshold
        if rows_z:
            pd.DataFrame(rows_z).to_csv(cm.out_path("irf_event_grid_by_zone.csv"), index=False)
    pd.DataFrame(leads).to_csv(cm.out_path("irf_grid_leads_tests.csv"), index=False)


def bin_models(grid, look):
    """Percentile-bin impulse responses relative to the median band.

    For each variable v and outcome, one regression holds the indicators of every non-reference bin of v at lags
    -LEADS_DAYS ... +GRID_LAG_DAYS, plus the other two variables' bin indicators on the same day (their same-day
    percentile, as in the main model). The reference is the median band REF_BIN, so each coefficient is the change in the
    probability of an outage k days after a day in that percentile bin, relative to a day near the median.
    Rain: bins are over wet days, and dry days enter as their own indicator ("dry")."""
    ks = list(range(-LEADS_DAYS, GRID_LAG_DAYS + 1))
    obs = grid["observed"].to_numpy()
    base = grid.loc[obs, [cm.STATION_COL, "date", "zone"] + [f"y_{o}" for o in GRID_OUTCOMES]].reset_index(drop=True)
    stn = grid[cm.STATION_COL].to_numpy()
    bins = [(lo, hi) for lo, hi in zip(BIN_EDGES_PCT[:-1], BIN_EDGES_PCT[1:]) if (lo, hi) != REF_BIN]

    def shifted(flag, k):
        tmp = pd.DataFrame({cm.STATION_COL: stn, "_b": flag})
        return tmp.groupby(cm.STATION_COL, sort=False)["_b"].shift(k).to_numpy()[obs]

    flags = {}
    for v in VARS:
        f = {f"{lo:g}–{hi:g}": bin_flag(grid, v, lo, hi, look) for lo, hi in bins}
        if v == "P":
            x = grid[SERIES["P"]].to_numpy()
            with np.errstate(invalid="ignore"):
                f = {"dry": np.where(np.isnan(x), np.nan, (x < cpm.WET_DAY_MM).astype(float)), **f}
        flags[v] = f
    ctrl = {v: {f"C{v}{i}": shifted(f, 0) for i, f in enumerate(flags[v].values())} for v in VARS}
    meta_bin = {"dry": (np.nan, np.nan)}
    meta_bin.update({f"{lo:g}–{hi:g}": (lo, hi) for lo, hi in bins})

    rows = []
    for v in VARS:
        names = list(flags[v])
        own = {}
        for i, nm in enumerate(names):
            for k in ks:
                own[f"O{i}_{k}"] = shifted(flags[v][nm], k)
        oc = {i: [f"O{i}_{k}" for k in ks] for i in range(len(names))}
        cc = {c: a for u in VARS if u != v for c, a in ctrl[u].items()}
        d = pd.concat([base, pd.DataFrame(own), pd.DataFrame(cc)], axis=1)
        del own
        d = d.dropna(subset=[c for i in oc for c in oc[i]] + list(cc)).reset_index(drop=True)
        print(f"Bin models, {v}: {len(d):,} station-days, {len(names)} bins x {len(ks)} lags")
        for z in ["ALL"] + sorted(d["zone"].dropna().unique()):
            g = d if z == "ALL" else d[d["zone"] == z].reset_index(drop=True)
            use = {i: [(k, c) for k, c in zip(ks, oc[i]) if g[c].sum() >= MIN_EVENTS_ZONE] for i in oc}
            xc = [c for i in use for _, c in use[i]] + [c for c in cc if g[c].sum() >= MIN_EVENTS_ZONE]
            for o in GRID_OUTCOMES:
                try:
                    fit = cm.fe_ols(g, f"y_{o}", xc, cluster=CLUSTER)
                except Exception as ex:
                    print(f"  skipped {v} / {z} / {o}: {ex}")
                    continue
                for i, nm in enumerate(names):
                    if not use[i]:
                        continue
                    lo, hi = meta_bin[nm]
                    rows += rows_for(fit, [c for _, c in use[i]], v, 1.0,
                                     dict(zone=z, outcome=o, bin=nm, bin_lo=lo, bin_hi=hi, n_events=int(g[f"O{i}_0"].sum()),
                                          n=fit.n, n_stations=g[cm.STATION_COL].nunique()), [k for k, _ in use[i]])
            print(f"  {v} / {z} done")
        pd.DataFrame(rows).to_csv(cm.out_path("irf_bins.csv"), index=False)           # saved after every variable
    print("Bin models done.")


def dl_by_zone(d, base_cols):
    """Distributed-lag response estimated separately inside each climate zone (per +1 SD of the zone's own
    within-station-month variation, so a 'standard' shock is comparable across zones)."""
    rows = []
    for z, g in d.groupby("zone"):
        g = g.reset_index(drop=True)
        for o in OUTCOMES:
            try:
                fit = cm.fe_ols(g, f"y_{o}", base_cols, cluster=CLUSTER)
            except Exception as ex:
                print(f"  skipped zone {z} / {o}: {ex}")
                continue
            for v in VARS:
                sd0 = float(fit.sd_within[f"D{v}_0"])
                rows += rows_for(fit, [f"D{v}_{k}" for k in KS], v, sd0,
                                 dict(zone=z, outcome=o, sd=sd0, n=fit.n, n_clusters=fit.n_clusters,
                                      n_stations=g[cm.STATION_COL].nunique()))
        print(f"  zone {z} done")
    pd.DataFrame(rows).to_csv(cm.out_path("irf_dl_by_zone.csv"), index=False)


# Local-projection variant (not run here): for each horizon h regress Y_{i,t+h} on the day-t value / indicator with
# the same fixed effects. It gives the same impulse response when the controls are the other days' weather, and a
# total response (including the persistence of the weather itself) when they are not.

if __name__ == "__main__":
    if "--grid-only" in sys.argv:
        g_, l_ = build_grid()
        grid_models(g_, l_)
        bin_models(g_, l_)
        print("Done. Results in", cm.OUTPUT_DIR)
    else:
        main()
'''

# ---------------------------------------------------------------- compute_variance_decomposition.py
_SOURCES['compute_variance_decomposition'] = r'''
"""
compute_variance_decomposition.py
=================================
How much of the variation in outages does weather explain, and which part of the weather matters most?

METRIC
  Within-R2 of the fixed-effects model: the share of outage variation, after removing station x calendar-month and
  year effects, that the weather terms account for. It is split among "players" with a SHAPLEY (LMG) decomposition:
  each player's contribution is its increase in within-R2, averaged over every order in which the players could enter.
  This does not depend on an ordering (unlike a Cholesky-ordered forecast-error variance decomposition).

PLAYERS (six; the three-variable totals are also reported)
  T_same, P_same, W_same   same-day terms: the spline of the day's within-zone percentile rank of temperature / rain / wind
                           (and the wet-day dummy for rain), as in compute_percentile_model.py
  T_lag,  P_lag,  W_lag    lagged terms: all lag-window means of that variable (compute_main_model.WINDOWS, day 1 onwards)

ALSO REPORTED
  Out-of-sample within-R2 of the full model, by leaving out whole stations (5 folds), as a guard against overfitting.

OUTCOMES   every outcome in compute_main_model.OUTCOMES (daily share; P(outage >= 1, 6, 12 h))

OUTPUTS
  vd_shapley.csv    Shapley share of the within-R2 for each player and outcome (absolute R2 points and % of the total)
  vd_shapley_by_variable.csv   the same for the three-player split (temperature, rain, wind)
  vd_r2_total.csv   total within-R2 of the full model, with leave-stations-out R2

The decomposition describes statistical association in this sample, not a causal share.

Run: python compute_variance_decomposition.py     then   python plot_variance_decomposition.py
Needs compute_main_model.py and compute_percentile_model.py in the same folder.
"""
import os
import sys
import itertools
from math import factorial
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compute_main_model as cm
import compute_percentile_model as cpm

VARS = ["T", "P", "W"]
N_FOLDS = 5
SEED = 0


def players():
    same = {v: [f"S{v}_{j}" for j in range(len(cpm.SPLINE_KNOTS) - 1)] + (["WET_P"] if v == "P" else []) for v in VARS}
    lag = {v: [f"X{v}_{b}" for b in cm.WINDOWS] for v in VARS}
    out = {}
    for v in VARS:
        out[f"{v}_same"] = same[v]
        out[f"{v}_lag"] = lag[v]
    return out


def residualise(est, cols, ycols):
    """Demean by station x calendar month and project out year dummies. Returns residualised X (DataFrame) and Y."""
    month = est["date"].dt.month
    grp = pd.factorize(est[cm.STATION_COL].astype(str) + "_" + month.astype(str))[0]
    yr = pd.get_dummies(est["date"].dt.year, prefix="yr", drop_first=True).astype("float64")
    Z = pd.concat([est[cols], est[ycols], yr], axis=1)
    Zd = Z - Z.groupby(grp).transform("mean")
    Dy = Zd[list(yr.columns)].to_numpy()
    keep = Dy.std(axis=0) > 1e-10
    Dy = Dy[:, keep]
    W = Zd[cols + ycols].to_numpy()
    coef, *_ = np.linalg.lstsq(Dy, W, rcond=None)
    R = W - Dy @ coef
    return pd.DataFrame(R[:, :len(cols)], columns=cols), pd.DataFrame(R[:, len(cols):], columns=ycols)


def r2_subset(A, b, yy, idx):
    if not idx:
        return 0.0
    As, bs = A[np.ix_(idx, idx)], b[idx]
    beta = np.linalg.lstsq(As, bs, rcond=None)[0]
    return float(bs @ beta / yy)


def shapley(names, r2):
    """names: list of players; r2: dict frozenset(players) -> R2. Returns dict player -> Shapley value."""
    n = len(names)
    out = {}
    for p in names:
        rest = [q for q in names if q != p]
        phi = 0.0
        for k in range(len(rest) + 1):
            w = factorial(k) * factorial(n - k - 1) / factorial(n)
            for S in itertools.combinations(rest, k):
                phi += w * (r2[frozenset(S) | {p}] - r2[frozenset(S)])
        out[p] = phi
    return out


def main():
    print("Loading hourly data and building the daily panel ...")
    df = cm.load_hourly()
    daily = cm.build_daily(df)
    del df
    grid = cm.to_full_grid(daily)
    if not os.path.exists(cm.COASTAL_CSV):
        cm.build_coastal_flags(cm.INPUT_CSVS, cm.COASTAL_CSV)
    grid = cm.add_coastal(grid, cm.COASTAL_CSV)
    grid = cm.add_chronic(grid)
    grid = cm.add_outcomes(cm.add_extremes(grid))
    est = grid[grid["observed"]].dropna(subset=cm.chronic_terms()).reset_index(drop=True)
    est = cpm.add_ranks_and_flags(est, cpm.thresholds(est))
    print(f"  estimation sample: {len(est):,} station-days, {est[cm.STATION_COL].nunique()} stations")

    P = players()
    pnames = list(P)
    cols = [c for p in pnames for c in P[p]]
    ycols = [f"y_{o}" for o in cm.OUTCOMES]
    X, Y = residualise(est, cols, ycols)
    Xn = X.to_numpy()
    A = Xn.T @ Xn
    pos = {c: i for i, c in enumerate(cols)}
    stn = est[cm.STATION_COL].astype(str).to_numpy()

    rows, rows_v, rows_tot = [], [], []
    rng = np.random.default_rng(SEED)
    stations = np.array(sorted(set(stn)))
    fold_of = dict(zip(stations, rng.permutation(len(stations)) % N_FOLDS))
    fold = np.array([fold_of[s] for s in stn])
    for o in cm.OUTCOMES:
        y = Y[f"y_{o}"].to_numpy()
        b, yy = Xn.T @ y, float(y @ y)
        r2 = {}
        for k in range(len(pnames) + 1):
            for S in itertools.combinations(pnames, k):
                idx = [pos[c] for p in S for c in P[p]]
                r2[frozenset(S)] = r2_subset(A, b, yy, idx)
        full = r2[frozenset(pnames)]
        phi = shapley(pnames, r2)
        for p in pnames:
            rows.append(dict(outcome=o, player=p, shapley_r2=phi[p], share_of_total=phi[p] / full if full > 0 else np.nan, total_r2=full))
        # three-player version (temperature, rain, wind), each with its same-day and lagged terms
        groups = {v: P[f"{v}_same"] + P[f"{v}_lag"] for v in VARS}
        r2v = {}
        for k in range(len(VARS) + 1):
            for S in itertools.combinations(VARS, k):
                idx = [pos[c] for v in S for c in groups[v]]
                r2v[frozenset(S)] = r2_subset(A, b, yy, idx)
        phiv = shapley(VARS, r2v)
        for v in VARS:
            rows_v.append(dict(outcome=o, var=v, shapley_r2=phiv[v], share_of_total=phiv[v] / full if full > 0 else np.nan, total_r2=full))
        # out-of-sample (leave stations out)
        ssr = sst = 0.0
        for f in range(N_FOLDS):
            tr, te = fold != f, fold == f
            beta = np.linalg.lstsq(Xn[tr], y[tr], rcond=None)[0]
            ssr += float(((y[te] - Xn[te] @ beta) ** 2).sum()); sst += float((y[te] ** 2).sum())
        rows_tot.append(dict(outcome=o, within_r2=full, within_r2_leave_stations_out=1 - ssr / sst, n=len(y)))
        print(f"  {o}: within-R2 = {full:.4f}, leave-stations-out = {1 - ssr / sst:.4f}")
    pd.DataFrame(rows).to_csv(cm.out_path("vd_shapley.csv"), index=False)
    pd.DataFrame(rows_v).to_csv(cm.out_path("vd_shapley_by_variable.csv"), index=False)
    pd.DataFrame(rows_tot).to_csv(cm.out_path("vd_r2_total.csv"), index=False)
    print("Done. Results in", cm.OUTPUT_DIR)


if __name__ == "__main__":
    main()
'''

# ---------------------------------------------------------------- compute_dry_heat_confirmation.py
_SOURCES['compute_dry_heat_confirmation'] = r'''
"""
compute_dry_heat_confirmation.py
================================
Stability and multiplicity check for the one interaction that survived the robustness checks: a dry spell followed by a
heat extreme, for outages of at least 12 h. Needs compute_main_model.py, compute_percentile_model.py,
compute_interaction_model.py and check_interaction_robustness.py in the same folder.

SPECIFICATION (fixed before these checks; chosen after seeing the full sample, so these checks cannot be fully
out-of-sample)
  chronic state  mean rain over the prior 30 days at or below the zone's 25th percentile
  acute shock    daily maximum temperature at or above the zone's 90th percentile
  outcome        probability of an outage of at least 12 h in a day
  d3 = interaction (the change in the heat association after a dry spell)

CHECKS
  random_station_halves   N_SPLITS random splits of the stations into two halves; d3 in each half
  leave_one_year_out      d3 with each year left out
  multiplicity            Holm- and Bonferroni-adjusted p-values for d3 across all twelve pairs of
                          compute_interaction_model.py at this specification and outcome (reads interaction_results.csv)

OUTPUT  dry_heat_confirmation.csv   Run: python compute_dry_heat_confirmation.py
"""
import os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compute_main_model as cm
import compute_percentile_model as cpm
import compute_interaction_model as cim
import check_interaction_robustness as cir

N_SPLITS = 30
SEED = 7
CV, AV, DIRN, NDAYS, CQ, SQ, OUT = "P", "T", "low", 30, 0.75, 0.90, "ge12h"


def main():
    rng = np.random.default_rng(SEED)
    df = cm.load_hourly(); daily = cm.build_daily(df); del df
    grid = cm.to_full_grid(daily)
    if not os.path.exists(cm.COASTAL_CSV):
        cm.build_coastal_flags(cm.INPUT_CSVS, cm.COASTAL_CSV)
    grid = cm.add_coastal(grid, cm.COASTAL_CSV)
    grid = cm.add_chronic(grid)
    cim.CHRONIC_DAYS_LIST = [NDAYS]
    grid = cim.add_prior_state(grid)
    grid = cm.add_outcomes(cm.add_extremes(grid))
    est = grid[grid["observed"]].dropna(subset=cm.chronic_terms() + [f"PRIOR_{v}_{NDAYS}" for v in cim.SERIES]).reset_index(drop=True)
    est = cpm.add_ranks_and_flags(est, cpm.thresholds(est))
    est["_C"] = cir.flag(est, f"PRIOR_{CV}_{NDAYS}", CQ, DIRN)
    est["_year"] = est["date"].dt.year
    D = f"F_{AV}_{SQ}"
    controls = cm.chronic_terms() + cpm.same_day_controls(AV)
    rows = []

    def add(check, detail, r):
        if r is not None:
            rows.append(dict(check=check, detail=detail, **r))

    add("full_sample", "", cir.d3(est, OUT, controls, D, "_C"))
    stations = est[cm.STATION_COL].unique()
    for s in range(N_SPLITS):
        perm = rng.permutation(stations); half = set(perm[: len(perm) // 2])
        m = est[cm.STATION_COL].isin(half)
        add("random_station_halves", f"split{s}_A", cir.d3(est, OUT, controls, D, "_C", m))
        add("random_station_halves", f"split{s}_B", cir.d3(est, OUT, controls, D, "_C", ~m))
        print("split", s, flush=True)
    for y in sorted(est["_year"].unique()):
        add("leave_one_year_out", f"without {y}", cir.d3(est, OUT, controls, D, "_C", est["_year"] != y))
    # multiplicity across the twelve pairs at this specification (same outcome)
    r = pd.read_csv(cm.out_path("interaction_results.csv"))
    r = r[(r.quantity == "interaction") & (r.chronic_days == NDAYS) & np.isclose(r.chronic_q, CQ) & np.isclose(r.same_q, SQ) & (r.outcome == OUT)]
    p = r.set_index("pair")["p"].sort_values()
    m = len(p)
    holm = np.minimum(1, np.maximum.accumulate(p.to_numpy() * (m - np.arange(m))))
    for (pair, pv), h in zip(p.items(), holm):
        rows.append(dict(check="multiplicity", detail=pair, p=pv, p_bonferroni=min(1, pv * m), p_holm=h, n_tests=m))
    pd.DataFrame(rows).to_csv(cm.out_path("dry_heat_confirmation.csv"), index=False)
    print("Done")


if __name__ == "__main__":
    main()
'''

# ---------------------------------------------------------------- compute_forest_interaction.py
_SOURCES['compute_forest_interaction'] = r'''
"""
compute_forest_interaction.py
=============================
Does a wind extreme do more at stations with more forest around them (trees falling on lines)? Needs
compute_main_model.py and compute_percentile_model.py in the same folder.

DESIGN
  Forest cover is a fixed station characteristic, so its main effect is absorbed by the station-month effect and only
  its interaction with a same-day extreme is estimated:
     Y_it = alpha_{i,m(t)} + gamma_{y(t)} + sum_v sum_b beta^v_b X^v_{it,b} + sum_{u != a} f_u(R^u_it)
            + d1 D_it + d3 D_it x G_i + e_it
  D_it   same-day exceedance of variable a at the zone's SAME_Q-th percentile
  G_i    forest cover of station i, measured relative to the other stations of its climate zone, because forest cover
         differs strongly between zones (Am has the most). Two versions:
           high   1 if the station's forest cover is above its zone's median (the model then reports the acute effect at
                  low-forest and high-forest stations, d1 and d1 + d3)
           rank   the station's within-zone percentile rank of forest cover, scaled 0-1 (d3 is the change in the acute
                  effect from the least- to the most-forested station of a zone)
  FOREST measures: the share of forest within a 50 km buffer (primary) and within the district.
  PLACEBOS  Wind is the variable that trees should matter for. Rain and heat extremes are run in the same way: an
            interaction there would point to a general difference between forested and other stations, not to trees.
Standard errors are clustered by station and date. Forest cover varies only between stations (516 values), so the
effective sample for the interaction is the number of stations.

OUTPUT  forest_interaction_results.csv     Run: python compute_forest_interaction.py     then   python plot_forest_interaction.py
"""
import os, sys
import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compute_main_model as cm
import compute_percentile_model as cpm

ACUTE_VARS = [("W", "wind"), ("P", "rain"), ("T", "heat")]
SAME_QS = [0.90, 0.95, 0.99]
FOREST_COLS = {"buffer50km": "forest_perc_50kmbuffer", "district": "forest_perc_district"}
OUTCOMES = cm.OUTCOMES
CLUSTER = "two_way"


def station_forest():
    fs = [pd.read_csv(p, usecols=[cm.STATION_COL, cm.ZONE_COL] + list(FOREST_COLS.values())) for p in cm.INPUT_CSVS]
    return pd.concat(fs).drop_duplicates(cm.STATION_COL).set_index(cm.STATION_COL)


def main():
    df = cm.load_hourly(); daily = cm.build_daily(df); del df
    grid = cm.to_full_grid(daily)
    if not os.path.exists(cm.COASTAL_CSV):
        cm.build_coastal_flags(cm.INPUT_CSVS, cm.COASTAL_CSV)
    grid = cm.add_coastal(grid, cm.COASTAL_CSV)
    grid = cm.add_chronic(grid)
    grid = cm.add_outcomes(cm.add_extremes(grid))
    est = grid[grid["observed"]].dropna(subset=cm.chronic_terms()).reset_index(drop=True)
    est = cpm.add_ranks_and_flags(est, cpm.thresholds(est))
    sf = station_forest()
    stn = est.groupby(cm.STATION_COL)["zone"].first().to_frame()
    for name, col in FOREST_COLS.items():
        stn[name] = sf.loc[stn.index, col].to_numpy()
        stn[f"rank_{name}"] = stn.groupby("zone")[name].rank(pct=True)
        stn[f"high_{name}"] = (stn[name] > stn.groupby("zone")[name].transform("median")).astype(float)
        est[f"G_rank_{name}"] = est[cm.STATION_COL].map(stn[f"rank_{name}"])
        est[f"G_high_{name}"] = est[cm.STATION_COL].map(stn[f"high_{name}"])
    print(f"sample {len(est):,} station-days, {len(stn)} stations; high-forest stations by zone: "
          f"{stn.groupby('zone')['high_buffer50km'].sum().astype(int).to_dict()}", flush=True)
    rows = []
    for av, aname in ACUTE_VARS:
        controls = cm.chronic_terms() + cpm.same_day_controls(av)
        for sq in SAME_QS:
            D = f"F_{av}_{sq}"
            for fname in FOREST_COLS:
                for kind in ("high", "rank"):
                    G = f"G_{kind}_{fname}"
                    est["_DG"] = est[D] * est[G]
                    n_d = int(est[D].sum())
                    if n_d < 100:
                        continue
                    for o in OUTCOMES:
                        fit = cm.fe_ols(est, f"y_{o}", controls + [D, "_DG"], cluster=CLUSTER)
                        for label, w in (("acute_low_forest" if kind == "high" else "acute_least_forest", {D: 1.0}),
                                         ("interaction", {"_DG": 1.0}),
                                         ("acute_high_forest" if kind == "high" else "acute_most_forest", {D: 1.0, "_DG": 1.0})):
                            e, s = cm.lincomb(fit, w)
                            rows.append(dict(acute=aname, outcome=o, same_q=sq, forest=fname, measure=kind, quantity=label, est=e, se=s,
                                             lo=e - 1.96 * s, hi=e + 1.96 * s, p=float(2 * norm.sf(abs(e / s))) if s > 0 else np.nan,
                                             n=fit.n, n_extreme_days=n_d, n_stations=len(stn)))
            print(aname, sq, "done", flush=True)
    pd.DataFrame(rows).to_csv(cm.out_path("forest_interaction_results.csv"), index=False)
    print("Done")


if __name__ == "__main__":
    main()
'''

# ---------------------------------------------------------------- compute_knot_sensitivity.py
_SOURCES['compute_knot_sensitivity'] = r'''
"""
compute_knot_sensitivity.py
===========================
Does the shape of the same-day percentile curve depend on where the spline knots sit? Refits the pooled "total" spline
model of compute_percentile_model.py with several knot sets and writes the curves. Needs compute_main_model.py and
compute_percentile_model.py in the same folder.

KNOT SETS (percentile ranks)
  current       5, 25, 50, 90, 99            main specification (extra flexibility in the upper tail)
  harrell5      5, 27.5, 50, 72.5, 95        Harrell's default for five knots
  harrell4      5, 35, 65, 95                Harrell's default for four knots
  harrell6      5, 23, 41, 59, 77, 95        Harrell's default for six knots
  upper_tail    10, 50, 90, 97.5, 99.5       more knots far out in the tail
The curve is always reported relative to the median (rank 50).

OUTPUT  knot_sensitivity_curves.csv   curve, SE and 95% CI by knot set, variable, outcome and rank
        knot_sensitivity_summary.csv  curve at ranks 75, 90, 95, 99 for each knot set, and its difference from `current`

Run: python compute_knot_sensitivity.py     then   python plot_knot_sensitivity.py
"""
import os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compute_main_model as cm
import compute_percentile_model as cpm

KNOT_SETS = {"current": [5, 25, 50, 90, 99], "harrell5": [5, 27.5, 50, 72.5, 95], "harrell4": [5, 35, 65, 95],
             "harrell6": [5, 23, 41, 59, 77, 95], "upper_tail": [10, 50, 90, 97.5, 99.5]}
OUTCOMES = ["ge1h", "ge6h", "ge12h"]
REPORT_RANKS = [75, 90, 95, 99]


def main():
    df = cm.load_hourly(); daily = cm.build_daily(df); del df
    grid = cm.to_full_grid(daily)
    if not os.path.exists(cm.COASTAL_CSV):
        cm.build_coastal_flags(cm.INPUT_CSVS, cm.COASTAL_CSV)
    grid = cm.add_coastal(grid, cm.COASTAL_CSV)
    grid = cm.add_chronic(grid)
    grid = cm.add_outcomes(cm.add_extremes(grid))
    est = grid[grid["observed"]].dropna(subset=cm.chronic_terms()).reset_index(drop=True)
    thr = cpm.thresholds(est)
    rows = []
    for name, knots in KNOT_SETS.items():
        cpm.SPLINE_KNOTS = knots
        e = cpm.add_ranks_and_flags(est.copy(), thr)
        for v in cpm.VARS:
            for o in OUTCOMES:
                rows += cpm.spline_curve(e, v, "total", o, dict(knots=name, var=v, outcome=o))
        print(name, "done", flush=True)
    c = pd.DataFrame(rows)
    c.to_csv(cm.out_path("knot_sensitivity_curves.csv"), index=False)
    s = c[np.isin(c["rank"], REPORT_RANKS)].copy()
    ref = s[s.knots == "current"].set_index(["var", "outcome", "rank"])["coef"]
    s["diff_vs_current"] = s.apply(lambda r: r.coef - ref.loc[(r["var"], r["outcome"], r["rank"])], axis=1)
    s.to_csv(cm.out_path("knot_sensitivity_summary.csv"), index=False)
    print("Done")


if __name__ == "__main__":
    main()
'''

# ---------------------------------------------------------------- compute_model_fit.py
_SOURCES['compute_model_fit'] = r'''
"""
compute_model_fit.py
====================
Goodness of fit of the main model and of alternative specifications, for every outcome.
Needs compute_main_model.py and compute_percentile_model.py in the same folder; writes CSVs to the same OUTPUT_DIR.

All models are fitted on the SAME estimation sample, with the same fixed effects (station x calendar month) and year
dummies, so their information criteria are comparable. Models (cumulative, simplest first):

  A  fixed effects only                       (no weather)
  B  chronic windows only                     (the lag windows of temperature, rain and wind; no same-day terms)
  C  + same-day percentile, linear
  D  + same-day hand-set extreme flags        (the earlier design: heat wave, IMD rain classes, wind gust)
  E  + same-day step exceedances              (day at or above the zone p90, p95, p99)
  F  + same-day percentile bins               (exclusive bins above p50, reference below p50)
  G  + same-day spline, 3 knots               (knots 10, 50, 90)
  H  + same-day spline, 4 knots               (Harrell: 5, 35, 65, 95)
  I  + same-day spline, 5 knots               MAIN MODEL (5, 25, 50, 90, 99)
  J  + same-day spline, 5 knots, Harrell      (5, 27.5, 50, 72.5, 95)
  K  + same-day spline, 6 knots               (5, 23, 41, 59, 77, 95)
  L  same-day spline only                     (main spline, no chronic windows)
  M  main model with zone-specific splines    (each climate zone gets its own curve; tests equal curves across zones)
Rain also carries the wet-day dummy in every model that has same-day rain terms. Every model contains all three
variables (temperature, rain, wind).

Criteria (Gaussian likelihood of the linear probability model, estimated on the within-transformed data):
  AIC = N ln(RSS/N) + 2k,   BIC = N ln(RSS/N) + k ln N,   k = slopes + year dummies + station-month effects + 1.
  The fixed effects are the same in every model, so differences between models depend only on the slope terms.
  d_aic / d_bic are relative to the main model (positive = worse than the main model).
  within_r2 is the share of the within-station-month variation explained; cv_within_r2 is the same on stations
  left out of the fit (5 folds of whole stations), the guard against over-fitting.
  Caveat: the outcomes are binary or bounded and the errors are correlated within station and date, so N ln(RSS/N)
  overstates the information in the data; treat the criteria as a ranking and use cv_within_r2 as a cross-check.

OUTPUTS
  model_fit.csv            one row per outcome and model
  model_fit_zone_test.csv  Wald test of equal curves across climate zones, by variable (two-way clustered)

Run: python compute_model_fit.py     then   python plot_model_fit.py
"""
import os
import sys
import numpy as np
import pandas as pd
from scipy.stats import chi2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compute_main_model as cm
import compute_percentile_model as cpm

VARS = ["T", "P", "W"]
MAIN_MODEL = "I"
N_FOLDS = 5
SEED = 0
CHUNK = 40                      # columns demeaned at a time (memory)
STEP_QS = [0.90, 0.95, 0.99]
KNOT_SETS = {                   # alternative spline knots (percentile ranks); "I" is cpm.SPLINE_KNOTS
    "G": [10, 50, 90],
    "H": [5, 35, 65, 95],
    "J": [5, 27.5, 50, 72.5, 95],
    "K": [5, 23, 41, 59, 77, 95],
}
LABELS = {
    "A": "Fixed effects only",
    "B": "Chronic windows only",
    "C": "+ same day, linear",
    "D": "+ same day, hand-set flags",
    "E": "+ same day, exceedance steps (p90, p95, p99)",
    "F": "+ same day, percentile bins",
    "G": "+ same day, spline 3 knots",
    "H": "+ same day, spline 4 knots",
    "I": "+ same day, spline 5 knots (main)",
    "J": "+ same day, spline 5 knots (Harrell)",
    "K": "+ same day, spline 6 knots",
    "L": "Same-day spline only (no chronic)",
    "M": "Main model, zone-specific splines",
}


def residualise(est, cols, ycols):
    """Demean by station x calendar month and project out year dummies (chunked to save memory)."""
    month = est["date"].dt.month
    grp = pd.factorize(est[cm.STATION_COL].astype(str) + "_" + month.astype(str))[0]
    yr = pd.get_dummies(est["date"].dt.year, prefix="yr", drop_first=True).astype("float64")
    Dy = (yr - yr.groupby(grp).transform("mean")).to_numpy()
    Dy = Dy[:, Dy.std(axis=0) > 1e-10]
    Q, _ = np.linalg.qr(Dy)

    def clean(frame):
        out = []
        names = list(frame.columns)
        for i in range(0, len(names), CHUNK):
            part = frame[names[i:i + CHUNK]]
            W = (part - part.groupby(grp).transform("mean")).to_numpy()
            out.append(W - Q @ (Q.T @ W))
        return np.column_stack(out) if out else np.zeros((len(frame), 0))
    X = pd.DataFrame(clean(est[cols]), columns=cols)
    Y = pd.DataFrame(clean(est[ycols]), columns=ycols)
    return X, Y, int(grp.max() + 1), int(Dy.shape[1])


def add_spline(new, est, knots, tag):
    """Spline basis columns of each variable's percentile rank; they are collected in `new` (a dict of arrays)."""
    cols = {v: [] for v in VARS}
    for v in VARS:
        B = cpm.rcs_basis(est[f"R_{v}"].to_numpy(), knots)
        for j in range(B.shape[1]):
            new[f"{tag}{v}_{j}"] = B[:, j]
            cols[v].append(f"{tag}{v}_{j}")
    return cols


def specs(est):
    """Return ({model: list of regressor columns}, zone interaction columns, DataFrame of the extra columns the models need)."""
    chronic = cm.chronic_terms()
    wet = ["WET_P"]
    main_sp = {v: [f"S{v}_{j}" for j in range(len(cpm.SPLINE_KNOTS) - 1)] for v in VARS}
    new = {}                                     # extra columns, attached to est in one go at the end
    sp = {"I": main_sp}
    for m, knots in KNOT_SETS.items():
        sp[m] = add_spline(new, est, knots, f"K{m}")
    flat = lambda d: [c for v in VARS for c in d[v]]

    flags = [c for c in ["ET", "EW"] + [f"E{k}" for k in cm.RAIN_CLASSES] if c in est.columns]
    for c in flags:
        est[c] = est[c].fillna(0.0)
    flags = [c for c in flags if est[c].sum() >= cm.MIN_EVENTS_PER_FLAG]        # a flag with too few days is dropped
    zones = sorted(est["zone"].dropna().unique())
    inter = {v: [] for v in VARS}
    for z in zones[1:]:
        dz = (est["zone"] == z).astype("float64")
        for v in VARS:
            for c in main_sp[v] + (wet if v == "P" else []):
                new[f"{c}__{z}"] = est[c].to_numpy() * dz.to_numpy()
                inter[v].append(f"{c}__{z}")

    out = {
        "A": [],
        "B": chronic,
        "C": chronic + [f"R_{v}" for v in VARS] + wet,
        "D": chronic + flags,
        "E": chronic + [f"F_{v}_{q}" for v in VARS for q in STEP_QS] + wet,
        "F": chronic + [f"B_{v}_{lo}" for v in VARS for lo in cpm.BIN_EDGES] + wet,
        "L": flat(main_sp) + wet,
        "M": chronic + flat(main_sp) + wet + flat(inter),
    }
    for m in ("G", "H", "I", "J", "K"):
        out[m] = chronic + flat(sp[m]) + wet
    return out, inter, pd.DataFrame(new, index=est.index)


def main():
    print("Loading hourly data and building the daily panel ...")
    df = cm.load_hourly()
    daily = cm.build_daily(df)
    del df
    grid = cm.to_full_grid(daily)
    if not os.path.exists(cm.COASTAL_CSV):
        cm.build_coastal_flags(cm.INPUT_CSVS, cm.COASTAL_CSV)
    grid = cm.add_coastal(grid, cm.COASTAL_CSV)
    grid = cm.add_chronic(grid)
    grid = cm.add_outcomes(cm.add_extremes(grid))
    est = grid[grid["observed"]].dropna(subset=cm.chronic_terms()).reset_index(drop=True)
    del grid
    est = cpm.add_ranks_and_flags(est, cpm.thresholds(est))
    print(f"  estimation sample: {len(est):,} station-days, {est[cm.STATION_COL].nunique()} stations")

    spec, inter, new = specs(est)
    est = pd.concat([est, new], axis=1)
    cols = list(dict.fromkeys(c for m in spec.values() for c in m))
    ycols = [f"y_{o}" for o in cm.OUTCOMES]
    X, Y, n_fe, n_year = residualise(est, cols, ycols)
    pos = {c: i for i, c in enumerate(cols)}
    Xn = X.to_numpy()
    del X
    N = len(est)
    k0 = n_fe + n_year + 1
    stn = est[cm.STATION_COL].astype(str).to_numpy()
    rng = np.random.default_rng(SEED)
    stations = np.array(sorted(set(stn)))
    fold_of = dict(zip(stations, rng.permutation(len(stations)) % N_FOLDS))
    fold = np.array([fold_of[s] for s in stn])

    rows = []
    for o in cm.OUTCOMES:
        y = Y[f"y_{o}"].to_numpy()
        tss = float(y @ y)
        for m, names in spec.items():
            idx = [pos[c] for c in names]
            if idx:
                A = Xn[:, idx]
                beta = np.linalg.lstsq(A, y, rcond=None)[0]
                rss = float(((y - A @ beta) ** 2).sum())
                ssr = 0.0
                for f in range(N_FOLDS):
                    tr, te = fold != f, fold == f
                    b = np.linalg.lstsq(A[tr], y[tr], rcond=None)[0]
                    ssr += float(((y[te] - A[te] @ b) ** 2).sum())
            else:
                rss, ssr = tss, tss
            k = len(idx) + k0
            ll = N * np.log(rss / N)
            rows.append(dict(outcome=o, model=m, label=LABELS[m], n=N, k_slopes=len(idx), rss=rss, within_r2=1 - rss / tss,
                             cv_within_r2=1 - ssr / tss, aic=ll + 2 * k, bic=ll + np.log(N) * k))
        print(f"  {o}: done")
    res = pd.DataFrame(rows)
    ref = res[res.model == MAIN_MODEL].set_index("outcome")
    res["d_aic"] = res["aic"] - res["outcome"].map(ref["aic"])
    res["d_bic"] = res["bic"] - res["outcome"].map(ref["bic"])
    res.to_csv(cm.out_path("model_fit.csv"), index=False)

    # equal curves across zones: Wald test on the zone interactions, two-way clustered
    print("Zone-equality test ...")
    trows = []
    for o in cm.OUTCOMES:
        fit = cm.fe_ols(est, f"y_{o}", spec["M"], cluster="two_way")
        for v in VARS:
            if not inter[v]:
                continue
            st, df_, p = cm.wald(fit, inter[v])
            trows.append(dict(outcome=o, var=v, wald=st, df=df_, p=p, n=fit.n, n_clusters=fit.n_clusters))
        print(f"  {o}: done")
    pd.DataFrame(trows).to_csv(cm.out_path("model_fit_zone_test.csv"), index=False)
    print("Done. Results in", cm.OUTPUT_DIR)


if __name__ == "__main__":
    main()
'''


if __name__ == "__main__":
    main()
