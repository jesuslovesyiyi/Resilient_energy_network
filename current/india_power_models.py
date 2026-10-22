#!/usr/bin/env python3
"""
india_power_models.py  --  the whole analysis in ONE file
=========================================================
Chronic versus extreme weather and power outages at ESMI stations in India. This single file contains every model and every
figure of the paper (nothing else is needed except Python with numpy, pandas, scipy and matplotlib). It runs from any folder.

QUICK START
  1. Edit DATA_DIR / INPUT_CSVS / OUTPUT_DIR just below, or pass --input-csv and --output-dir on the command line.
  2. python india_power_models.py models          run the models on the full dataset (slow: run overnight)
  3. python india_power_models.py figures         draw the figures and gather them, numbered, in OUTPUT_DIR/paper_figures
     python india_power_models.py all             both

COMMANDS AND OPTIONS
  models   [--only STEP ...] [--skip STEP ...] [--force] [--keep-going]
  figures  [--no-replot] [--only main|si]
  list     show every step and whether its output already exists
  all      models, then figures
  Common:  --input-csv FILE [FILE ...]   hourly data (default: INPUT_CSVS below)
           --output-dir DIR              where result CSVs and figures go (default: OUTPUT_DIR below)
  A step is skipped if its result CSV already exists, unless --force is given.

MODEL STEPS (in this order)
  main         lag windows and the flag-based model (robustness version)           -> main_*.csv
  percentile   MAIN MODEL: same-day percentile splines + chronic windows, plus exceedance and bins -> pct_*.csv
  irf          impulse response functions (distributed lags, event studies, thresholds, zones)  -> irf_*.csv
  variance     within-R2 and Shapley shares                                          -> vd_*.csv
  interaction  chronic state x acute shock, twelve pairs                             -> interaction_results.csv
  robustness   placebo, seasonal, zone and permutation checks for three candidate pairs -> interaction_robustness.csv
  confirm      station halves, leave-one-year-out, multiplicity for dry spell -> heat -> dry_heat_confirmation.csv
  forest       forest cover x wind (rain and heat as placebos)                       -> forest_interaction_results.csv
  knots        spline-knot sensitivity                                               -> knot_sensitivity_*.csv

STRUCTURE OF THIS FILE
  1. configuration and the command-line runner (this part)
  2. the original scripts, embedded unchanged as text in _SOURCES at the bottom of the file and loaded as modules when run.
     To change a model, edit the matching text in _SOURCES (the names are the old script names).
The numbers quoted in the Methods drafts came from runs by Claude in a sandbox, not from your machine: rerun everything here.
"""
import argparse
import csv
import os
import re
import shutil
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
    ("irf", "compute_irf", "irf_dl.csv"),
    ("variance", "compute_variance_decomposition", "vd_shapley.csv"),
    ("interaction", "compute_interaction_model", "interaction_results.csv"),
    ("robustness", "check_interaction_robustness", "interaction_robustness.csv"),
    ("confirm", "compute_dry_heat_confirmation", "dry_heat_confirmation.csv"),
    ("forest", "compute_forest_interaction", "forest_interaction_results.csv"),
    ("knots", "compute_knot_sensitivity", "knot_sensitivity_curves.csv"),
]
PLOT_MODULES = ["plot_main_model", "plot_percentile_model", "plot_irf", "plot_variance_decomposition", "plot_interaction_model",
                "plot_forest_interaction", "plot_knot_sensitivity", "plot_dry_heat"]

# Figures: (number, subfolder of OUTPUT_DIR, figure name, what it shows). Edit to move figures between main text and SI.
MAIN_FIGS = [
    ("Fig1", "figures_percentile", "pfig1_spline", "Same-day dose-response: change in outage probability by within-zone percentile (temperature, rain, wind; outages >= 1, 6, 12 h)"),
    ("Fig2", "figures", "fig1_chronic_profile", "Chronic profile: effect of the mean weather in each lag window (1 to 179 days before)"),
    ("Fig3", "figures_irf", "ifig5_by_percentile", "Timing: same-day, next-day and cumulative response across percentile thresholds"),
]
SI_FIGS = [
    ("FigS1", "figures_knots", "kfig1_knot_sensitivity", "Same-day curves under different spline knots"),
    ("FigS2", "figures_dry_heat", "dfig1_dry_heat", "Heat extremes after a dry spell (outages >= 12 h): effect, checks and stability"),
    ("FigS3", "figures_vd", "vfig1_variance_decomposition", "Share of within-station variation explained, by weather variable (Shapley)"),
    ("FigS4", "figures_percentile", "pfig0_thresholds", "Within-zone percentile thresholds of temperature, rain and wind"),
    ("FigS5", "figures_percentile", "pfig2_exceedance", "Exceedance models: effect of a day at or above each percentile"),
    ("FigS6", "figures_percentile", "pfig3_bins", "Percentile-bin model"),
    ("FigS7", "figures_percentile", "pfig4_by_zone", "Same-day curves by climate zone"),
    ("FigS8", "figures_percentile", "pfig5_added", "Total versus added same-day curves"),
    ("FigS9", "figures_irf", "ifig1_dl_response", "Distributed-lag impulse response to a one-standard-deviation shock"),
    ("FigS10", "figures_irf", "ifig2_dl_cumulative", "Cumulative impulse response"),
    ("FigS11", "figures_irf", "ifig3_event_q95", "Event-study response to a day at or above the 95th percentile"),
    ("FigS12", "figures_irf", "ifig4_event_q99", "Event-study response to a day at or above the 99th percentile"),
    ("FigS13", "figures_irf", "ifig6_heatmap", "Response by percentile threshold and lag (heat map)"),
    ("FigS14", "figures_irf", "ifig7_by_zone", "Event-study response by climate zone"),
    ("FigS15", "figures_interaction", "xfig1_acute_by_state", "Chronic state x acute shock: effect after normal conditions and after chronic stress"),
    ("FigS16", "figures_interaction", "xfig2_interaction_forest", "Interaction across thresholds (30-day prior window)"),
    ("FigS17", "figures_interaction", "xfig3_interaction_heatmap", "Interaction by pair and prior-window length"),
    ("FigS18", "figures_forest", "ffig1_forest_interaction", "Forest cover x wind, rain and heat extremes (placebos)"),
    ("FigS19", "figures", "fig2_chronic_vs_extreme", "Flag-based model: chronic versus extreme-day associations"),
    ("FigS20", "figures", "fig5_net_decomposition", "Flag-based model: net association of an extreme day"),
    ("FigS21", "figures", "fig3_robustness", "Flag-based model: robustness"),
    ("FigS22", "figures", "fig4_event_counts", "Flag-based model: number of extreme days"),
]

_BUNDLE = os.path.abspath(__file__)
_STATE = {"output_dir": OUTPUT_DIR, "input_csvs": INPUT_CSVS}


# ----------------------------------------------------------------------
# loader: the embedded scripts become importable modules under their old names
# ----------------------------------------------------------------------
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
                 "compute_knot_sensitivity"]:
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


def _draw_all():
    results_dir = _STATE["output_dir"]
    for name in PLOT_MODULES:
        print(f"drawing with {name} ...", flush=True)
        src = re.sub(r'RESULTS_DIR = os\.path\.expanduser\(\s*"[^"]*"\)', "RESULTS_DIR = __RESULTS_DIR__", _SOURCES[name])
        ns = {"__name__": "__main__", "__file__": _BUNDLE, "__RESULTS_DIR__": results_dir}
        try:
            exec(compile(src, f"<{name}>", "exec"), ns)
        except Exception:
            traceback.print_exc()
            print(f"  WARNING: {name} failed; figures from it may be missing or old")


def cmd_figures(a):
    out = _STATE["output_dir"]
    if not a.no_replot:
        _draw_all()
    root = os.path.join(out, "paper_figures")
    rows, missing = [], []
    for label, entries in (("main", MAIN_FIGS), ("si", SI_FIGS)):
        if a.only and a.only != label:
            continue
        os.makedirs(os.path.join(root, label), exist_ok=True)
        for num, folder, name, what in entries:
            found = False
            for ext in ("png", "pdf"):
                src = os.path.join(out, folder, f"{name}.{ext}")
                if os.path.exists(src):
                    shutil.copyfile(src, os.path.join(root, label, f"{num}_{name}.{ext}"))
                    found = True
            if found:
                rows.append((num, f"{num}_{name}", folder + "/" + name, what))
            else:
                missing.append(f"{num} {folder}/{name}")
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "figure_index.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["number", "file", "source", "what it shows"]); w.writerows(rows)
    print(f"\n{len(rows)} figures gathered in {root}")
    if missing:
        print("Missing (run the models first):")
        for m in missing:
            print("  ", m)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", default="all", choices=["models", "figures", "all", "list"],
                    help="what to run (default: all = models, then figures)")
    ap.add_argument("--input-csv", nargs="+")
    ap.add_argument("--output-dir")
    ap.add_argument("--only", nargs="+")
    ap.add_argument("--skip", nargs="+")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--keep-going", action="store_true")
    ap.add_argument("--no-replot", action="store_true")
    a = ap.parse_args()
    if a.input_csv:
        _STATE["input_csvs"] = [os.path.abspath(p) for p in a.input_csv]
    if a.output_dir:
        _STATE["output_dir"] = os.path.abspath(a.output_dir)
    names = [s[0] for s in STEPS]
    if a.command in ("models", "all"):
        bad = [x for x in (a.only or []) + (a.skip or []) if x not in names]
        if bad:
            ap.error(f"unknown step {bad}; choose from {names}")
    rc = 0
    if a.command == "list":
        cmd_list(a)
    if a.command in ("models", "all"):
        rc = cmd_models(a)
    if a.command in ("figures", "all") and rc == 0:
        if a.command == "all":
            a.only = None
        elif a.only and a.only[0] not in ("main", "si"):
            ap.error("--only for figures is main or si")
        else:
            a.only = a.only[0] if a.only else None
        rc = cmd_figures(a)
    sys.exit(rc)


# ======================================================================
# EMBEDDED SCRIPTS (unchanged copies of the original files; edit here to change a model or a figure)
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
  irf_event_grid.csv    event-study responses for every percentile in GRID_QUANTILES (zone-specific thresholds), lags -L..GRID_LAG_DAYS
  irf_event_grid_by_zone.csv  the same, estimated inside each climate zone, for ZONE_GRID_QUANTILES
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
GRID_QUANTILES = [0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 0.975, 0.99]   # event models over many thresholds
GRID_LAG_DAYS = 14                                   # the response is over within days, so the grid uses a shorter horizon
GRID_OUTCOMES = ["ge1h", "ge6h", "ge12h"]
MIN_EVENTS_ZONE = 10                                 # a lag regressor needs at least this many event days inside a zone
ZONE_GRID_QUANTILES = [0.90, 0.95]                   # the same models estimated inside each climate zone
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
    return grid, look


def main():
    grid, look = build_grid()

    dl_cols, ev_cols, store = {}, {}, {}
    for v in VARS:
        dl_cols[v] = lag_columns(grid, series_values(grid, v).to_numpy(), f"D{v}", store)
    for q in EVENT_QUANTILES:
        for v in VARS:
            t = grid["zone"].map({z: look[(z, v, round(q, 4))] for z in grid["zone"].dropna().unique()}).to_numpy()
            x = grid[SERIES[v]].to_numpy()
            flag = np.where(np.isnan(x), np.nan, (x >= t).astype(float))
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
    print("Done. Results in", cm.OUTPUT_DIR)


def grid_models(grid, look):
    """Event-study impulse responses for many zone-specific percentile thresholds, pooled and by climate zone."""
    ks = list(range(-LEADS_DAYS, GRID_LAG_DAYS + 1))
    keep = [cm.STATION_COL, "date", "zone", "observed"] + [f"y_{o}" for o in GRID_OUTCOMES]
    rows, rows_z, leads = [], [], []
    for q in GRID_QUANTILES:
        store, cols = {}, {}
        for v in VARS:
            t = grid["zone"].map({z: look[(z, v, round(q, 4))] for z in grid["zone"].dropna().unique()}).to_numpy()
            x = grid[SERIES[v]].to_numpy()
            flag = np.where(np.isnan(x), np.nan, (x >= t).astype(float))
            cols[v] = lag_columns(grid, flag, f"E{v}", store, ks)
        d = pd.concat([grid[keep], pd.DataFrame(store, index=grid.index)], axis=1)
        d = d[d["observed"]].dropna(subset=[c for v in VARS for c in cols[v]]).reset_index(drop=True)
        allc = [c for v in VARS for c in cols[v]]
        print(f"Grid, percentile {q}: {len(d):,} station-days")
        for o in GRID_OUTCOMES:
            fit = cm.fe_ols(d, f"y_{o}", allc, cluster=CLUSTER)
            for v in VARS:
                n_ev = int(d[f"E{v}_0"].sum())
                rows += rows_for(fit, cols[v], v, 1.0, dict(outcome=o, q=q, n_events=n_ev, n=fit.n), ks)
                st, df_, p = cm.wald(fit, [c for k, c in zip(ks, cols[v]) if k < 0])
                leads.append(dict(model=f"GRID_q{q}", outcome=o, var=v, wald=st, df=df_, p=p))
        if q in ZONE_GRID_QUANTILES:
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
                                           dict(zone=z, outcome=o, q=q, n_events=int(g[f"E{v}_0"].sum()),
                                                n=fit.n, n_stations=g[cm.STATION_COL].nunique()), [k for k, _ in zc[v]])
        pd.DataFrame(rows).to_csv(cm.out_path("irf_event_grid.csv"), index=False)       # saved after every threshold
        if rows_z:
            pd.DataFrame(rows_z).to_csv(cm.out_path("irf_event_grid_by_zone.csv"), index=False)
    pd.DataFrame(leads).to_csv(cm.out_path("irf_grid_leads_tests.csv"), index=False)


# Local-projection variant (not run here): for each horizon h regress Y_{i,t+h} on the day-t value / indicator with
# the same fixed effects. It gives the same impulse response when the controls are the other days' weather, and a
# total response (including the persistence of the weather itself) when they are not.

if __name__ == "__main__":
    if "--grid-only" in sys.argv:
        g_, l_ = build_grid()
        grid_models(g_, l_)
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

# ---------------------------------------------------------------- plot_main_model.py
_SOURCES['plot_main_model'] = r'''
"""
plot_main_model.py
==================
Reads the CSV files written by compute_main_model.py and draws the figures. It does NOT
re-estimate anything, so it runs in seconds and can be re-run while you adjust the style.

The headline outcomes are the PROBABILITY that a station-day has at least 1 h, 6 h or 12 h of
blackout (linear probability model; coefficients are percentage-point changes in that probability).
The daily share of time in blackout is shown alongside in fig2 for continuity.

FIGURES (each saved as PNG at 600 dpi and as PDF in RESULTS_DIR/figures)
  fig1_chronic_profile     How each weather variable's association with P(outage >= 1 h / 6 h / 12 h)
                           changes with how far back the exposure lies. Per within-SD of the exposure.
  fig2_chronic_vs_extreme  One panel per outcome. Chronic (+1 SD in every lag window,
                           dots) next to the NET effect of an extreme day (diamonds): the predicted
                           difference between flagged days and other days of the same station-month,
                           chronic terms plus the extreme-day coefficient.
  fig3_robustness          The chronic association Delta (sum over all lag windows) under each robustness spec,
                           for the three probability outcomes.
  fig4_event_counts        How many station-days carry each extreme flag.
  fig5_net_decomposition   Net extreme-day effect split into the part carried by the chronic terms and
                           the part over and above them (the extreme-day coefficient), as a multiple of
                           the outcome's baseline rate.

Reading the figures
  * A dot is a point estimate; the bar is the 95% confidence interval (station-clustered).
  * "per SD" = per one pooled within-station-month standard deviation of that regressor.
  * The extreme-day coefficient alone is the effect OVER AND ABOVE the linear chronic terms; the net
    effect adds the chronic terms back.
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Must match OUTPUT_DIR in compute_main_model.py. Absolute path, so the script runs from any folder.
RESULTS_DIR = os.path.expanduser(
    "~/Library/CloudStorage/OneDrive-GeorgiaInstituteofTechnology/Research/Energy_resilience/01_data/processed/main_model_results")
FIG_DIR = os.path.join(RESULTS_DIR, "figures")
DPI = 600

# one colour per entity (temperature / precipitation / wind): validated categorical slots
COL = {"T": "#eb6834", "P": "#2a78d6", "W": "#1baf7a"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
VAR_NAME = {"T": "Temperature", "P": "Precipitation", "W": "Wind"}
VAR_UNIT = {"T": "°C", "P": "ln(1 + mm)", "W": "m s$^{-1}$"}
WINDOWS = []        # filled from the coefficient file by load(): every lag window the model used, shortest first
WIN_LABEL = []
EXTREME_LABEL = {"ET": "Heat wave", "EP1": "Heavy rain\n(64.5–115.5 mm)", "EP2": "Very heavy rain\n(115.6–204.4 mm)",
                 "EP3": "Extremely heavy rain\n(≥204.5 mm)", "EW": "High wind\n(gust ≥20 m s$^{-1}$)"}
EXTREME_VAR = {"ET": "T", "EP1": "P", "EP2": "P", "EP3": "P", "EW": "W"}
OUT_LABEL = {"share": "Daily blackout share (pp)", "ge1h": "P(outage ≥ 1 h) (pp)",
             "ge6h": "P(outage ≥ 6 h) (pp)", "ge12h": "P(outage ≥ 12 h) (pp)"}
OUT_SHORT = {"share": "share", "ge1h": "≥ 1 h", "ge6h": "≥ 6 h", "ge12h": "≥ 12 h"}
PROB = ["ge1h", "ge6h", "ge12h"]
SHADE = {"ge1h": 0.45, "ge6h": 0.72, "ge12h": 1.0}                      # darker = longer outage
MARK = {"ge1h": "o", "ge6h": "s", "ge12h": "^"}
SPEC_LABEL = {
    "main": "Main model", "station_week_FE": "Station × week-of-year FE", "station_FE_plus_month": "Station FE + month dummies",
    "two_way_cluster_station_date": "Two-way cluster (station, date)", "cluster_era5_cell": "Cluster by ERA5 cell",
    "leads_added": "Leads added", "heat_3day": "3-day heat wave", "coastal_25km": "Coastal ≤25 km", "coastal_50km": "Coastal ≤50 km",
    "gust_22": "Gust ≥22 m s$^{-1}$", "gust_25": "Gust ≥25 m s$^{-1}$"}

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"], "font.size": 7,
    "axes.edgecolor": INK2, "axes.linewidth": 0.6, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": INK2, "ytick.color": INK2, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
})


def save(fig, name):
    os.makedirs(FIG_DIR, exist_ok=True)
    fig.savefig(os.path.join(FIG_DIR, name + ".png"), dpi=DPI, bbox_inches="tight")
    fig.savefig(os.path.join(FIG_DIR, name + ".pdf"), bbox_inches="tight")
    plt.close(fig)
    print("saved", name)


def tag(ax, letter):
    ax.text(-0.02, 1.06, letter, transform=ax.transAxes, fontsize=9, fontweight="bold", va="bottom", ha="right")


def light_grid(ax, axis):
    ax.grid(axis=axis, color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)


def load():
    coefs = pd.read_csv(os.path.join(RESULTS_DIR, "main_coefficients.csv"))
    quant = pd.read_csv(os.path.join(RESULTS_DIR, "main_quantities.csv"))
    rob = pd.read_csv(os.path.join(RESULTS_DIR, "robustness_quantities.csv"))
    counts = pd.read_csv(os.path.join(RESULTS_DIR, "event_counts.csv"))
    base = pd.read_csv(os.path.join(RESULTS_DIR, "outcome_summary.csv")).set_index("outcome")["baseline_mean"].to_dict()
    wins = sorted({t.split("_", 1)[1] for t in coefs.term if t.startswith("XT_")}, key=lambda w: int(w.strip("[]").split(",")[0]))
    WINDOWS[:] = wins
    WIN_LABEL[:] = [w.strip("[]").replace(",", "–") + " d" for w in wins]
    return coefs, quant, rob, counts, base


# ----------------------------------------------------------------------
def fig1(coefs):
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.7), sharey=True)
    lo_all, hi_all = [], []
    for ax, v in zip(axes, ["T", "P", "W"]):
        x = np.arange(len(WINDOWS))
        ax.axhline(0, color=INK2, linewidth=0.6)
        for k, o in enumerate(PROB):
            sub = coefs[(coefs.outcome == o) & (coefs.spec == "main")]
            rows = [sub[sub.term == f"X{v}_{b}"].iloc[0] for b in WINDOWS]
            y = np.array([r.coef_per_sd for r in rows]); lo = np.array([r.lo_per_sd for r in rows])
            hi = np.array([r.hi_per_sd for r in rows])
            lo_all += list(lo); hi_all += list(hi)
            xo = x + (k - 1) * 0.12
            col = mpl_shade(COL[v], SHADE[o])
            ax.plot(xo, y, color=col, linewidth=1.0, zorder=2)
            ax.vlines(xo, lo, hi, color=col, linewidth=1.1, zorder=3)
            ax.scatter(xo, y, s=20, marker=MARK[o], color=col, edgecolor="white", linewidth=0.7, zorder=4,
                       label=OUT_SHORT[o])
        sd = float(np.mean([r.sd_within for r in rows]))
        ax.set_xticks(x); ax.set_xticklabels(WIN_LABEL, fontsize=5.5, rotation=45, ha="right"); ax.set_xlim(-0.45, len(WINDOWS) - 0.55)
        ax.set_title(VAR_NAME[v], loc="left", fontsize=8, fontweight="bold", pad=10)
        ax.text(0, 1.015, f"1 SD ≈ {sd:.2f} {VAR_UNIT[v]} (mean over windows)", transform=ax.transAxes,
                fontsize=6, color=INK2, va="bottom")
        light_grid(ax, "y"); tag(ax, "abc"[["T", "P", "W"].index(v)])
        ax.legend(title="Outage length", fontsize=6, title_fontsize=6, loc="upper right" if v != "P" else "upper right")
    pad = 0.06 * (max(hi_all) - min(lo_all))
    axes[0].set_ylim(min(lo_all) - pad, max(hi_all) + pad)
    axes[0].set_ylabel("Change in probability of an outage\nper 1 SD of exposure (pp)")
    axes[1].set_xlabel("Lag window (days before day t; day t itself is not included)")
    fig.tight_layout()
    save(fig, "fig1_chronic_profile")


def mpl_shade(hexcol, f):
    """Blend a colour towards white; f=1 keeps the full colour."""
    import matplotlib.colors as mc
    r = np.array(mc.to_rgb(hexcol))
    return tuple(1 - f * (1 - r))


def lag_span():
    lo = WINDOWS[0].strip("[]").split(",")[0]
    hi = WINDOWS[-1].strip("[]").split(",")[1]
    return f"{lo}–{hi} d"


def fig2(quant, counts):
    n_by = counts.set_index("flag")["station_days"].to_dict()
    outs = ["share"] + PROB
    flags = [f for f in ["ET", "EP1", "EP2", "EP3", "EW"] if f in set(quant["var"])]
    labels = ([f"{VAR_NAME[v]}\n(lags {lag_span()})" for v in ["T", "P", "W"]] +
              [f"{EXTREME_LABEL[f]}\n{int(n_by.get(f, 0)):,} station-days" for f in flags])
    gap = 1.3
    ypos, y = [], 0.0
    for i in range(len(labels)):
        if i == 3:
            y += gap
        ypos.append(y); y += 1.0
    fig, axes = plt.subplots(1, 4, figsize=(7.2, 0.40 * len(labels) + 1.9), sharey=True)
    for ax, o in zip(axes, outs):
        q = quant[quant.outcome == o]
        ch = q[q.quantity == "chronic_Delta"].set_index("var")
        ne = q[q.quantity == "net_extreme_effect"].set_index("var")
        ax.axvline(0, color=INK2, linewidth=0.6)
        for i, v in enumerate(["T", "P", "W"]):
            r = ch.loc[v]
            ax.hlines(ypos[i], r.est_per_sd - 1.96 * r.se_per_sd, r.est_per_sd + 1.96 * r.se_per_sd, color=COL[v], linewidth=1.4, zorder=3)
            ax.scatter([r.est_per_sd], [ypos[i]], s=26, marker="o", color=COL[v], edgecolor="white", linewidth=0.8, zorder=4)
        for j, f in enumerate(flags):
            r = ne.loc[f]; v = EXTREME_VAR[f]
            ax.hlines(ypos[3 + j], r.est - 1.96 * r.se, r.est + 1.96 * r.se, color=COL[v], linewidth=1.4, zorder=3)
            ax.scatter([r.est], [ypos[3 + j]], s=28, marker="D", color=COL[v], edgecolor="white", linewidth=0.8, zorder=4)
        ax.set_title(OUT_SHORT[o] if o != "share" else "Daily share", fontsize=8, fontweight="bold", loc="left")
        ax.set_xlabel("pp", fontsize=7)
        light_grid(ax, "x"); tag(ax, "abcd"[outs.index(o)])
    axes[0].set_yticks(ypos); axes[0].set_yticklabels(labels, fontsize=6.5)
    axes[0].set_ylim(max(ypos) + 0.7, -1.2)
    axes[0].text(-1.2, -0.55, "Chronic: +1 SD in every\nlag window (dots)", transform=axes[0].get_yaxis_transform(),
                 fontsize=6.5, fontweight="bold", va="center", ha="left", clip_on=False)
    axes[0].text(-1.2, ypos[3] - 0.85, "Extreme day, net effect (diamonds)", transform=axes[0].get_yaxis_transform(),
                 fontsize=6.5, fontweight="bold", va="center", ha="left", clip_on=False)
    fig.suptitle("Change in daily blackout share (panel a) or in the probability of an outage of at least 1, 6 or 12 h (b–d)",
                 fontsize=7, x=0.01, ha="left", y=1.0)
    fig.tight_layout()
    save(fig, "fig2_chronic_vs_extreme")


def fig3(rob):
    d = rob[rob.quantity == "chronic_Delta"].copy()
    specs = [s for s in SPEC_LABEL if s in set(d.spec)]
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 0.30 * len(specs) + 1.3), sharey=True)
    for ax, v in zip(axes, ["T", "P", "W"]):
        ax.axvline(0, color=INK2, linewidth=0.6)
        for k, o in enumerate(PROB):
            sub = d[(d["var"] == v) & (d.outcome == o)].set_index("spec")
            col = mpl_shade(COL[v], SHADE[o])
            for i, s_ in enumerate(specs):
                if s_ not in sub.index:
                    continue
                r = sub.loc[s_]; yy = i + (k - 1) * 0.22
                ax.hlines(yy, r.est_per_sd - 1.96 * r.se_per_sd, r.est_per_sd + 1.96 * r.se_per_sd, color=col, linewidth=1.0, zorder=3)
                ax.scatter([r.est_per_sd], [yy], s=14, marker=MARK[o], color=col, edgecolor="white", linewidth=0.5, zorder=4,
                           label=OUT_SHORT[o] if i == 0 else None)
        ax.set_yticks(np.arange(len(specs))); ax.set_yticklabels([SPEC_LABEL[s_] for s_ in specs], fontsize=6.5)
        ax.invert_yaxis()
        ax.set_title(VAR_NAME[v], loc="left", fontsize=8, fontweight="bold")
        light_grid(ax, "x"); tag(ax, "abc"[["T", "P", "W"].index(v)])
    axes[0].legend(title="Outage length", fontsize=6, title_fontsize=6, loc="lower right")
    fig.supxlabel("Chronic association, Δ = sum over all lag windows, per 1 SD in every window (pp of probability)", fontsize=7, y=-0.03)
    fig.tight_layout()
    save(fig, "fig3_robustness")


def fig5(quant, base):
    """Net extreme-day effect = chronic part + part over and above, as a multiple of the baseline rate."""
    flags = [f for f in ["ET", "EP1", "EP2", "EP3", "EW"] if f in set(quant["var"])]
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 0.36 * len(flags) + 1.5), sharey=True)
    for ax, o in zip(axes, PROB):
        q = quant[(quant.outcome == o) & (quant.quantity == "net_extreme_effect")].set_index("var")
        b = base[o]
        ax.axvline(0, color=INK2, linewidth=0.6)
        for i, f in enumerate(flags):
            r = q.loc[f]; v = EXTREME_VAR[f]
            c_, g_ = r.net_chronic_part / b, r.net_flag_part / b
            ax.barh(i, c_, color=mpl_shade(COL[v], 0.45), height=0.5, zorder=3, label="via chronic terms" if i == 0 else None)
            ax.barh(i, g_, left=c_, color=COL[v], height=0.5, zorder=3, label="over and above" if i == 0 else None)
            ax.scatter([r.est / b], [i], s=16, color=INK, zorder=5, marker="|")
        ax.set_title(f"{OUT_SHORT[o]}  (baseline {b:.1f}%)", loc="left", fontsize=8, fontweight="bold")
        light_grid(ax, "x"); tag(ax, "abc"[PROB.index(o)])
        ax.set_xlabel("Net effect ÷ baseline rate", fontsize=7)
    axes[0].set_yticks(range(len(flags))); axes[0].set_yticklabels([EXTREME_LABEL[f] for f in flags], fontsize=6.5)
    axes[0].invert_yaxis()
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, fontsize=6.5, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.04))
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save(fig, "fig5_net_decomposition")


def fig4(counts):
    c = counts.copy()
    c["lab"] = c.flag.map(lambda f: EXTREME_LABEL[f].replace("\n", " "))
    c["v"] = c.flag.map(EXTREME_VAR)
    fig, ax = plt.subplots(figsize=(7.2, 0.4 * len(c) + 0.9))
    ys = np.arange(len(c))
    for y, (_, r) in zip(ys, c.iterrows()):
        ax.hlines(y, 1, r.station_days, color=COL[r.v], linewidth=0.8, alpha=0.5)
        ax.scatter([r.station_days], [y], s=34, color=COL[r.v], edgecolor="white", linewidth=0.8, zorder=4)
        ax.text(r.station_days * 1.35, y, f"{int(r.station_days):,} days · {int(r.stations_with_event)} stations",
                va="center", fontsize=6.5, color=INK)
    ax.set_xscale("log")
    ax.set_xlim(left=1, right=c.station_days.max() * 40)
    ax.set_yticks(ys)
    ax.set_yticklabels(c.lab, fontsize=6.5)
    ax.invert_yaxis()
    ax.set_xlabel("Station-days flagged (log scale)")
    light_grid(ax, "x")
    fig.tight_layout()
    save(fig, "fig4_event_counts")


if __name__ == "__main__":
    coefs, quant, rob, counts, base = load()
    fig1(coefs)
    fig2(quant, counts)
    fig3(rob)
    fig4(counts)
    fig5(quant, base)
'''

# ---------------------------------------------------------------- plot_percentile_model.py
_SOURCES['plot_percentile_model'] = r'''
"""
plot_percentile_model.py
========================
Draws the percentile-threshold results written by compute_percentile_model.py. Reads CSVs only.

FIGURES (PNG at 600 dpi and PDF, in RESULTS_DIR/figures_percentile)
  pfig0_thresholds   The thresholds in physical units, by climate zone.
  pfig1_spline       MAIN FIGURE. Smooth dose-response: change in the outcome as the within-zone percentile rank of
                     the day's temperature / rain / wind rises, relative to the median day (rank 50). Restricted cubic
                     spline; one line per outage length ("total" version).
  pfig2_exceedance   Change in the outcome on days at or above each percentile threshold (fine grid), vs days below.
  pfig3_bins         Exclusive percentile bins, reference = below the 50th.
  pfig4_by_zone      The spline curve inside each climate zone, for one outcome (OUTCOME_FOR_ZONES).
  pfig5_added        Total vs added (own chronic terms kept) spline curve, for one outcome.
Lines and dots are point estimates; bands and bars are 95% CIs, clustered by station and date. Units are percentage
points of the probability that the day has an outage of at least 1, 6 or 12 h.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mc

# Must match OUTPUT_DIR in compute_main_model.py.
RESULTS_DIR = os.path.expanduser(
    "~/Library/CloudStorage/OneDrive-GeorgiaInstituteofTechnology/Research/Energy_resilience/01_data/processed/main_model_results")
FIG_DIR = os.path.join(RESULTS_DIR, "figures_percentile")
DPI = 600
OUTCOME_FOR_ZONES = "ge6h"

COL = {"T": "#eb6834", "P": "#2a78d6", "W": "#1baf7a"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
VAR_NAME = {"T": "Temperature (daily max)", "P": "Precipitation (daily total)", "W": "Wind (daily max)"}
VAR_UNIT = {"T": "°C", "P": "mm", "W": "m s$^{-1}$"}
PROB = ["ge1h", "ge6h", "ge12h"]
SHADE = {"ge1h": 0.45, "ge6h": 0.72, "ge12h": 1.0}
MARK = {"ge1h": "o", "ge6h": "s", "ge12h": "^"}
OUT_SHORT = {"share": "daily share", "ge1h": "≥ 1 h", "ge6h": "≥ 6 h", "ge12h": "≥ 12 h"}
ZONE_NAME = {"Am": "Am (tropical monsoon)", "Aw": "Aw (tropical savanna)", "BSh": "BSh (hot semi-arid)", "Cw": "Cw (humid subtropical)"}
ZONE_LS = {"Am": "-", "Aw": "--", "BSh": ":", "Cw": "-."}

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"], "font.size": 7,
    "axes.edgecolor": INK2, "axes.linewidth": 0.6, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": INK2, "ytick.color": INK2, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
})


def shade(hexcol, f):
    r = np.array(mc.to_rgb(hexcol))
    return tuple(1 - f * (1 - r))


def save(fig, name):
    os.makedirs(FIG_DIR, exist_ok=True)
    fig.savefig(os.path.join(FIG_DIR, name + ".png"), dpi=DPI, bbox_inches="tight")
    fig.savefig(os.path.join(FIG_DIR, name + ".pdf"), bbox_inches="tight")
    plt.close(fig)
    print("saved", name)


def tag(ax, letter):
    ax.text(-0.02, 1.06, letter, transform=ax.transAxes, fontsize=9, fontweight="bold", va="bottom", ha="right")


def light_grid(ax, axis="y"):
    ax.grid(axis=axis, color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)


def rd(name):
    return pd.read_csv(os.path.join(RESULTS_DIR, name))


def pct_ticks(ax, qs):
    ax.set_xticks(range(len(qs)))
    ax.set_xticklabels([f"{100 * q:g}" for q in qs])
    ax.set_xlabel("Percentile of the zone's own distribution")


def fig0(thr):
    qs = [0.5, 0.75, 0.9, 0.95, 0.99]
    t = thr[thr.q.isin(qs)]
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.4))
    for ax, v in zip(axes, ["T", "P", "W"]):
        for z, ls in ZONE_LS.items():
            s = t[(t["var"] == v) & (t.zone == z)].sort_values("q")
            if s.empty:
                continue
            ax.plot(range(len(qs)), s.threshold, ls, color=COL[v], linewidth=1.2, marker="o", markersize=3, label=z)
        pct_ticks(ax, qs)
        ax.set_ylabel(VAR_UNIT[v])
        ax.set_title(VAR_NAME[v], loc="left", fontsize=8, fontweight="bold")
        light_grid(ax); tag(ax, "abc"["TPW".index(v)])
        ax.legend(fontsize=6, title="Zone", title_fontsize=6)
    axes[1].set_title(VAR_NAME["P"] + "\n(percentiles of wet days ≥ 1 mm)", loc="left", fontsize=8, fontweight="bold")
    fig.tight_layout()
    save(fig, "pfig0_thresholds")


def fig1(sp):
    d = sp[(sp.zone == "ALL") & (sp.version == "total")]
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.7))
    for ax, v in zip(axes, ["T", "P", "W"]):
        ax.axhline(0, color=INK2, linewidth=0.6)
        ax.axvline(50, color=GRID, linewidth=0.8, zorder=0)
        for o in PROB:
            s = d[(d["var"] == v) & (d.outcome == o)].sort_values("rank")
            col = shade(COL[v], SHADE[o])
            ax.fill_between(s["rank"], s.lo, s.hi, color=col, alpha=0.16, linewidth=0)
            ax.plot(s["rank"], s.coef, color=col, linewidth=1.3, label=OUT_SHORT[o])
        ax.set_xlim(0, 100)
        ax.set_xticks([0, 25, 50, 75, 90, 99])
        ax.set_xlabel("Percentile of the zone's own distribution")
        ax.set_title(VAR_NAME[v] + ("\n(percentile among wet days)" if v == "P" else ""), loc="left", fontsize=8, fontweight="bold")
        light_grid(ax); tag(ax, "abc"["TPW".index(v)])
        ax.legend(title="Outage length", fontsize=6, title_fontsize=6, loc="upper left")
    axes[0].set_ylabel("Change in probability of an outage (pp)\nrelative to the median day")
    fig.tight_layout()
    save(fig, "pfig1_spline")


def fig2(exc):
    d = exc[exc.version == "total"]
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.7))
    for ax, v in zip(axes, ["T", "P", "W"]):
        qs = sorted(d[d["var"] == v].q.unique())
        ax.axhline(0, color=INK2, linewidth=0.6)
        for o in PROB:
            s = d[(d["var"] == v) & (d.outcome == o)].set_index("q").reindex(qs)
            x = np.arange(len(qs)); col = shade(COL[v], SHADE[o])
            ax.fill_between(x, s.lo, s.hi, color=col, alpha=0.16, linewidth=0)
            ax.plot(x, s.coef, color=col, linewidth=1.1, marker=MARK[o], markersize=2.5, label=OUT_SHORT[o])
        pct_ticks(ax, qs)
        ax.tick_params(axis="x", labelsize=5, rotation=90)
        ax.set_title(VAR_NAME[v], loc="left", fontsize=8, fontweight="bold")
        light_grid(ax); tag(ax, "abc"["TPW".index(v)])
        ax.legend(title="Outage length", fontsize=6, title_fontsize=6, loc="upper left")
    axes[0].set_ylabel("Change in probability of an outage (pp)\nat or above the percentile vs below")
    fig.tight_layout()
    save(fig, "pfig2_exceedance")


def fig3(bins):
    d = bins[bins.version == "total"]
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.9))
    for ax, v in zip(axes, ["T", "P", "W"]):
        ax.axhline(0, color=INK2, linewidth=0.6)
        sub = d[d["var"] == v]
        qs = sorted(sub.q.unique())
        hi = sub.drop_duplicates("q").set_index("q").q_hi
        for k, o in enumerate(PROB):
            s = sub[sub.outcome == o].set_index("q").reindex(qs)
            x = np.arange(len(qs)) + (k - 1) * 0.15; col = shade(COL[v], SHADE[o])
            ax.vlines(x, s.lo, s.hi, color=col, linewidth=1.0)
            ax.plot(x, s.coef, color=col, linewidth=0.8)
            ax.scatter(x, s.coef, s=12, marker=MARK[o], color=col, edgecolor="white", linewidth=0.5, zorder=4, label=OUT_SHORT[o])
        ax.set_xticks(range(len(qs)))
        ax.set_xticklabels([f"{100 * q:g}–{100 * hi[q]:g}" if hi[q] < 1 else f"≥{100 * q:g}" for q in qs], rotation=60, ha="right", fontsize=5.5)
        ax.set_xlabel("Percentile bin (reference: below the 50th)")
        ax.set_title(VAR_NAME[v], loc="left", fontsize=8, fontweight="bold")
        light_grid(ax); tag(ax, "abc"["TPW".index(v)])
        ax.legend(title="Outage length", fontsize=6, title_fontsize=6, loc="upper left")
    axes[0].set_ylabel("Change in probability of an outage (pp)\nvs days below the 50th percentile")
    fig.tight_layout()
    save(fig, "pfig3_bins")


def fig4(sp):
    o = OUTCOME_FOR_ZONES
    d = sp[(sp.outcome == o) & (sp.version == "total") & (sp.zone != "ALL")]
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.7))
    for ax, v in zip(axes, ["T", "P", "W"]):
        ax.axhline(0, color=INK2, linewidth=0.6); ax.axvline(50, color=GRID, linewidth=0.8, zorder=0)
        for zn, ls in ZONE_LS.items():
            s = d[(d["var"] == v) & (d.zone == zn)].sort_values("rank")
            if s.empty:
                continue
            n = int(s.n_stations.iloc[0])
            ax.fill_between(s["rank"], s.lo, s.hi, color=COL[v], alpha=0.05, linewidth=0)
            ax.plot(s["rank"], s.coef, ls, color=COL[v], linewidth=1.2, label=f"{zn} ({n})")
        ax.set_xlim(0, 100); ax.set_xticks([0, 25, 50, 75, 90, 99])
        ax.set_xlabel("Percentile of the zone's own distribution")
        ax.set_title(VAR_NAME[v], loc="left", fontsize=8, fontweight="bold")
        light_grid(ax); tag(ax, "abc"["TPW".index(v)])
        ax.legend(title="Zone (stations)", fontsize=6, title_fontsize=6, loc="upper left")
    axes[0].set_ylabel(f"Change in P(outage {OUT_SHORT[o]}) (pp)\nrelative to the median day")
    fig.tight_layout()
    save(fig, "pfig4_by_zone")


def fig5(sp):
    o = OUTCOME_FOR_ZONES
    d = sp[(sp.outcome == o) & (sp.zone == "ALL")]
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.7))
    for ax, v in zip(axes, ["T", "P", "W"]):
        ax.axhline(0, color=INK2, linewidth=0.6); ax.axvline(50, color=GRID, linewidth=0.8, zorder=0)
        for ver, ls, f in (("total", "-", 1.0), ("added", "--", 0.5)):
            s = d[(d["var"] == v) & (d.version == ver)].sort_values("rank"); col = shade(COL[v], f)
            ax.fill_between(s["rank"], s.lo, s.hi, color=col, alpha=0.15, linewidth=0)
            ax.plot(s["rank"], s.coef, ls, color=col, linewidth=1.3,
                    label="total" if ver == "total" else "added (own chronic terms kept)")
        ax.set_xlim(0, 100); ax.set_xticks([0, 25, 50, 75, 90, 99])
        ax.set_xlabel("Percentile of the zone's own distribution")
        ax.set_title(VAR_NAME[v], loc="left", fontsize=8, fontweight="bold")
        light_grid(ax); tag(ax, "abc"["TPW".index(v)])
        ax.legend(fontsize=6, loc="upper left")
    axes[0].set_ylabel(f"Change in P(outage {OUT_SHORT[o]}) (pp)\nrelative to the median day")
    fig.tight_layout()
    save(fig, "pfig5_added")


if __name__ == "__main__":
    thr, exc, bins, sp = rd("pct_thresholds.csv"), rd("pct_exceedance.csv"), rd("pct_bins.csv"), rd("pct_spline_curve.csv")
    fig0(thr); fig1(sp); fig2(exc); fig3(bins); fig4(sp); fig5(sp)
'''

# ---------------------------------------------------------------- plot_irf.py
_SOURCES['plot_irf'] = r'''
"""
plot_irf.py
===========
Draws the impulse-response functions written by compute_irf.py. Reads CSVs only.

FIGURES (PNG at 600 dpi and PDF, in RESULTS_DIR/figures_irf)
  ifig1_dl_response    Response of the probability of an outage to a +1 SD change in temperature / rain / wind, by
                       days after the change (k = 0 is the same day). The grey zone (k < 0) is the placebo: future
                       weather should have no effect.
  ifig2_dl_cumulative  The same, accumulated from day 0: the total change after k days.
  ifig3_event_q95      Response to a day at or above the zone's 95th percentile (pp), by days after the event.
  ifig4_event_q99      Same for the 99th percentile.
  ifig5_by_percentile  How the response changes with the percentile threshold (zone-specific, 50th to 99th): same-day
                       response, next-day response and the cumulative response over days 0-3. One row per outage length.
  ifig6_heatmap        The full impulse-response surface: response by days after the weather (x) and percentile threshold
                       (y). Faded cells are not distinguishable from zero.
  ifig7_by_zone        Impulse response to a day at or above the 95th (or ZONE_Q) percentile, inside each climate zone.
Bands are 95% CIs (clustered by station and date). Units are percentage points of the probability that the day has an
outage of at least 1, 6 or 12 h.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mc

# Must match OUTPUT_DIR in compute_main_model.py.
RESULTS_DIR = os.path.expanduser(
    "~/Library/CloudStorage/OneDrive-GeorgiaInstituteofTechnology/Research/Energy_resilience/01_data/processed/main_model_results")
FIG_DIR = os.path.join(RESULTS_DIR, "figures_irf")
DPI = 600

COL = {"T": "#eb6834", "P": "#2a78d6", "W": "#1baf7a"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
VAR_NAME = {"T": "Temperature (daily max)", "P": "Precipitation (daily total)", "W": "Wind (daily max)"}
PROB = ["ge1h", "ge6h", "ge12h"]
SHADE = {"ge1h": 0.45, "ge6h": 0.72, "ge12h": 1.0}
ZONE_LS = {"Am": "-", "Aw": "--", "BSh": ":", "Cw": "-."}
OUTCOME_FOR_ZONES = "ge6h"
ZONE_Q = 0.95
OUT_SHORT = {"ge1h": "≥ 1 h", "ge6h": "≥ 6 h", "ge12h": "≥ 12 h"}

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"], "font.size": 7,
    "axes.edgecolor": INK2, "axes.linewidth": 0.6, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": INK2, "ytick.color": INK2, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
})


def shade(hexcol, f):
    r = np.array(mc.to_rgb(hexcol))
    return tuple(1 - f * (1 - r))


def save(fig, name):
    os.makedirs(FIG_DIR, exist_ok=True)
    fig.savefig(os.path.join(FIG_DIR, name + ".png"), dpi=DPI, bbox_inches="tight")
    fig.savefig(os.path.join(FIG_DIR, name + ".pdf"), bbox_inches="tight")
    plt.close(fig)
    print("saved", name)


def rd(name):
    return pd.read_csv(os.path.join(RESULTS_DIR, name))


def panel_plot(df, ycol, lo, hi, ylabel, fname, cumulative=False, note=None):
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.7))
    for ax, v in zip(axes, ["T", "P", "W"]):
        kmin = df.k.min()
        if not cumulative:
            ax.axvspan(kmin - 0.5, -0.5, color="#f1f0ec", zorder=0)
        ax.axhline(0, color=INK2, linewidth=0.6)
        for o in PROB:
            s = df[(df["var"] == v) & (df.outcome == o)].sort_values("k")
            if cumulative:
                s = s[s.k >= 0]
            col = shade(COL[v], SHADE[o])
            ax.fill_between(s.k, s[lo], s[hi], color=col, alpha=0.16, linewidth=0)
            ax.plot(s.k, s[ycol], color=col, linewidth=1.2, label=OUT_SHORT[o])
        ax.set_xlabel("Days after the weather (0 = same day)")
        ax.set_title(VAR_NAME[v], loc="left", fontsize=8, fontweight="bold")
        ax.grid(axis="y", color=GRID, linewidth=0.5); ax.set_axisbelow(True)
        ax.text(-0.02, 1.06, "abc"["TPW".index(v)], transform=ax.transAxes, fontsize=9, fontweight="bold", ha="right")
        if not cumulative:
            ax.text(kmin, ax.get_ylim()[1], " placebo", fontsize=5.5, color=INK2, va="top", ha="left")
        ax.legend(title="Outage length", fontsize=6, title_fontsize=6, loc="upper right")
    axes[0].set_ylabel(ylabel)
    if note:
        fig.text(0.01, -0.02, note, fontsize=6, color=INK2, ha="left")
    fig.tight_layout()
    save(fig, fname)


def fig5(g):
    fig, axes = plt.subplots(3, 3, figsize=(7.2, 6.0), sharex="col")
    for i, o in enumerate(PROB):
        for j, v in enumerate(["T", "P", "W"]):
            ax = axes[i, j]
            ax.axhline(0, color=INK2, linewidth=0.6)
            sub = g[(g.outcome == o) & (g["var"] == v)]
            for k, ls, lab, ycol, lo, hi in ((0, "-", "same day", "coef", "lo", "hi"), (1, "--", "next day", "coef", "lo", "hi"),
                                             (3, ":", "cumulative, days 0–3", "cum", "cum_lo", "cum_hi")):
                s = sub[sub.k == k].sort_values("q")
                x = np.arange(len(s))
                ax.fill_between(x, s[lo], s[hi], color=COL[v], alpha=0.08, linewidth=0)
                ax.plot(x, s[ycol], ls, color=COL[v], linewidth=1.2, label=lab)
            qs = sorted(sub.q.unique())
            ax.set_xticks(range(len(qs))); ax.set_xticklabels([f"{100 * q:g}" for q in qs], fontsize=5.5, rotation=90)
            ax.grid(axis="y", color=GRID, linewidth=0.5); ax.set_axisbelow(True)
            if i == 0:
                ax.set_title(VAR_NAME[v], loc="left", fontsize=8, fontweight="bold")
            if j == 0:
                ax.set_ylabel(f"P(outage {OUT_SHORT[o]}), pp")
            if i == 2:
                ax.set_xlabel("Percentile threshold (zone-specific)")
            if i == 0 and j == 0:
                ax.legend(fontsize=5.5, loc="upper left")
    fig.tight_layout()
    save(fig, "ifig5_by_percentile")


def fig6(g):
    fig, axes = plt.subplots(3, 3, figsize=(7.2, 6.0), sharex=True, sharey=True)
    for i, o in enumerate(PROB):
        sub_o = g[g.outcome == o]
        lim = np.nanpercentile(np.abs(sub_o.coef), 97)
        for j, v in enumerate(["T", "P", "W"]):
            ax = axes[i, j]
            sub = sub_o[sub_o["var"] == v]
            ks = sorted(sub.k.unique()); qs = sorted(sub.q.unique())
            Z = sub.pivot(index="q", columns="k", values="coef").loc[qs, ks].to_numpy()
            sig = ~((sub.pivot(index="q", columns="k", values="lo").loc[qs, ks] <= 0) &
                    (sub.pivot(index="q", columns="k", values="hi").loc[qs, ks] >= 0)).to_numpy()
            rgba = plt.cm.RdBu_r(plt.Normalize(-lim, lim)(Z))
            rgba[..., 3] = np.where(sig, 1.0, 0.25)
            ax.imshow(rgba, aspect="auto", origin="lower", extent=(ks[0] - 0.5, ks[-1] + 0.5, -0.5, len(qs) - 0.5))
            ax.axvline(-0.5, color=INK2, linewidth=0.6)
            ax.set_yticks(range(len(qs))); ax.set_yticklabels([f"{100 * q:g}" for q in qs], fontsize=5.5)
            if i == 0:
                ax.set_title(VAR_NAME[v], loc="left", fontsize=8, fontweight="bold")
            if j == 0:
                ax.set_ylabel(f"P(outage {OUT_SHORT[o]})\npercentile threshold")
            if i == 2:
                ax.set_xlabel("Days after the weather")
        sm = plt.cm.ScalarMappable(norm=plt.Normalize(-lim, lim), cmap="RdBu_r")
        cb = fig.colorbar(sm, ax=axes[i, :], fraction=0.02, pad=0.01); cb.ax.tick_params(labelsize=5.5); cb.set_label("pp", fontsize=6)
    save(fig, "ifig6_heatmap")


def fig7(z):
    d = z[(z.outcome == OUTCOME_FOR_ZONES) & (np.isclose(z.q, ZONE_Q))]
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.7))
    for ax, v in zip(axes, ["T", "P", "W"]):
        ax.axhline(0, color=INK2, linewidth=0.6)
        for zn, ls in ZONE_LS.items():
            s = d[(d["var"] == v) & (d.zone == zn)].sort_values("k")
            if s.empty:
                continue
            n = int(s.n_stations.iloc[0])
            ax.fill_between(s.k, s.lo, s.hi, color=COL[v], alpha=0.05, linewidth=0)
            ax.plot(s.k, s.coef, ls, color=COL[v], linewidth=1.2, label=f"{zn} ({n})")
        ax.set_xlabel("Days after the weather (0 = same day)")
        ax.set_title(VAR_NAME[v], loc="left", fontsize=8, fontweight="bold")
        ax.grid(axis="y", color=GRID, linewidth=0.5); ax.set_axisbelow(True)
        ax.legend(title="Zone (stations)", fontsize=6, title_fontsize=6, loc="upper right")
    axes[0].set_ylabel(f"Change in P(outage {OUT_SHORT[OUTCOME_FOR_ZONES]}) (pp)\nafter a day at or above the {int(round(ZONE_Q * 100))}th percentile")
    fig.tight_layout()
    save(fig, "ifig7_by_zone")


if __name__ == "__main__":
    dl = rd("irf_dl.csv")
    panel_plot(dl, "coef", "lo", "hi", "Change in probability of an outage (pp)\nper +1 SD in the weather variable", "ifig1_dl_response")
    panel_plot(dl, "cum", "cum_lo", "cum_hi", "Cumulative change in probability (pp)\nper +1 SD, summed from day 0", "ifig2_dl_cumulative", cumulative=True)
    for q in (95, 99):
        path = os.path.join(RESULTS_DIR, f"irf_event_q{q}.csv")
        if os.path.exists(path):
            ev = rd(f"irf_event_q{q}.csv")
            n = ev[(ev.k == 0)].groupby("var").n_events.first().to_dict()
            note = "Event days at k = 0: " + ", ".join(f"{VAR_NAME[v].split(' ')[0]} {int(n[v]):,}" for v in ["T", "P", "W"])
            panel_plot(ev, "coef", "lo", "hi", f"Change in probability of an outage (pp)\nafter a day at or above the {q}th percentile",
                       f"ifig{3 if q == 95 else 4}_event_q{q}", note=note)
    gp = os.path.join(RESULTS_DIR, "irf_event_grid.csv")
    if os.path.exists(gp):
        grid_df = rd("irf_event_grid.csv")
        fig5(grid_df)
        fig6(grid_df)
    zp = os.path.join(RESULTS_DIR, "irf_event_grid_by_zone.csv")
    if os.path.exists(zp):
        fig7(rd("irf_event_grid_by_zone.csv"))
'''

# ---------------------------------------------------------------- plot_variance_decomposition.py
_SOURCES['plot_variance_decomposition'] = r'''
"""
plot_variance_decomposition.py
==============================
Draws the within-R2 and Shapley decomposition written by compute_variance_decomposition.py. Reads CSVs only.

FIGURE (PNG at 600 dpi and PDF, in RESULTS_DIR/figures_vd)
  vfig1_variance_decomposition
    a  Within-R2 (% of the variation left after station x month and year effects) explained by weather, split into six
       Shapley contributions: same-day and lagged terms of temperature, rain and wind. Bars show the full model; the
       tick marks the R2 from leaving whole stations out.
    b  The same split as a share of each outcome's explained variation.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mc

# Must match OUTPUT_DIR in compute_main_model.py.
RESULTS_DIR = os.path.expanduser(
    "~/Library/CloudStorage/OneDrive-GeorgiaInstituteofTechnology/Research/Energy_resilience/01_data/processed/main_model_results")
FIG_DIR = os.path.join(RESULTS_DIR, "figures_vd")
DPI = 600

COL = {"T": "#eb6834", "P": "#2a78d6", "W": "#1baf7a"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
NAME = {"T": "Temperature", "P": "Rain", "W": "Wind"}
OUT_LABEL = {"share": "Daily share", "ge1h": "P(outage ≥ 1 h)", "ge6h": "P(outage ≥ 6 h)", "ge12h": "P(outage ≥ 12 h)"}
ORDER_OUT = ["share", "ge1h", "ge6h", "ge12h"]
PLAYERS = ["P_same", "P_lag", "T_same", "T_lag", "W_same", "W_lag"]

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"], "font.size": 7,
    "axes.edgecolor": INK2, "axes.linewidth": 0.6, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": INK2, "ytick.color": INK2, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
})


def shade(hexcol, f):
    r = np.array(mc.to_rgb(hexcol))
    return tuple(1 - f * (1 - r))


def colour(p):
    v, kind = p.split("_")
    return shade(COL[v], 1.0 if kind == "same" else 0.45)


def label(p):
    v, kind = p.split("_")
    return f"{NAME[v]}, {'same day' if kind == 'same' else 'lagged days'}"


def save(fig, name):
    os.makedirs(FIG_DIR, exist_ok=True)
    fig.savefig(os.path.join(FIG_DIR, name + ".png"), dpi=DPI, bbox_inches="tight")
    fig.savefig(os.path.join(FIG_DIR, name + ".pdf"), bbox_inches="tight")
    plt.close(fig)
    print("saved", name)


if __name__ == "__main__":
    sh = pd.read_csv(os.path.join(RESULTS_DIR, "vd_shapley.csv"))
    tot = pd.read_csv(os.path.join(RESULTS_DIR, "vd_r2_total.csv")).set_index("outcome")
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8), gridspec_kw={"width_ratios": [1.1, 1]})
    ys = np.arange(len(ORDER_OUT))[::-1]
    for ax, mode in zip(axes, ["abs", "share"]):
        for yi, o in zip(ys, ORDER_OUT):
            left = 0.0
            s = sh[sh.outcome == o].set_index("player")
            for p in PLAYERS:
                w = 100 * s.loc[p, "shapley_r2"] if mode == "abs" else 100 * s.loc[p, "share_of_total"]
                ax.barh(yi, w, left=left, color=colour(p), height=0.6, edgecolor="white", linewidth=0.5,
                        label=label(p) if yi == ys[0] else None)
                left += w
            if mode == "abs":
                ax.plot([100 * tot.loc[o, "within_r2_leave_stations_out"]] * 2, [yi - 0.38, yi + 0.38], color=INK, linewidth=1.0)
                ax.text(left + 0.02, yi, f"{left:.2f}%", va="center", fontsize=6.5)
        ax.set_yticks(ys)
        ax.set_yticklabels([OUT_LABEL[o] for o in ORDER_OUT] if mode == "abs" else [])
        ax.grid(axis="x", color=GRID, linewidth=0.5); ax.set_axisbelow(True)
    axes[0].set_xlabel("Within-R² explained by weather (%)")
    axes[1].set_xlabel("Share of the explained variation (%)")
    axes[0].set_xlim(0, axes[0].get_xlim()[1] * 1.12)
    axes[0].text(-0.02, 1.06, "a", transform=axes[0].transAxes, fontsize=9, fontweight="bold", ha="right")
    axes[1].text(-0.02, 1.06, "b", transform=axes[1].transAxes, fontsize=9, fontweight="bold", ha="right")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, fontsize=6.5, bbox_to_anchor=(0.5, -0.12))
    fig.text(0.01, -0.17, "Black tick (a): within-R² when whole stations are left out of the fit.", fontsize=6, color=INK2)
    fig.tight_layout()
    save(fig, "vfig1_variance_decomposition")
'''

# ---------------------------------------------------------------- plot_interaction_model.py
_SOURCES['plot_interaction_model'] = r'''
"""
plot_interaction_model.py
=========================
Draws the results of compute_interaction_model.py. Reads CSVs only.

FIGURES (PNG at 600 dpi and PDF, in RESULTS_DIR/figures_interaction)
  xfig1_acute_by_state   Main specification (chronic state: prior-30-day mean at or above the zone's 75th percentile;
                         acute shock: today at or above the zone's 95th percentile). For each pair, the effect of the acute
                         shock when conditions were normal versus after chronic stress, for P(outage >= 1, 6, 12 h).
                         A pair is not drawn where either cell has fewer than MIN_CELL station-days.
  xfig2_interaction_forest   The interaction coefficient (how much the acute effect changes after chronic stress) for every
                         pair and threshold combination with enough days, for the three outage lengths.
Bars are 95% CIs (clustered by station and date). Units are percentage points of the probability of an outage.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mc

# Must match OUTPUT_DIR in compute_main_model.py.
RESULTS_DIR = os.path.expanduser(
    "~/Library/CloudStorage/OneDrive-GeorgiaInstituteofTechnology/Research/Energy_resilience/01_data/processed/main_model_results")
FIG_DIR = os.path.join(RESULTS_DIR, "figures_interaction")
DPI = 600
MIN_CELL = 200
MAIN = (0.75, 0.95)          # (chronic q, same-day q)

INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
PAIRS_ALL = ["rain_rain", "heat_heat", "heat_rain", "heat_wind", "rain_wind", "rain_heat", "wind_rain", "wind_wind", "wind_heat",
             "dry_heat", "dry_rain", "dry_wind"]
_C = {"rain": "#2a78d6", "heat": "#eb6834", "wind": "#2a9d8f", "dry": "#8a5cc2"}
COL = {p: _C[p.split("_")[0]] for p in PAIRS_ALL}
_N = {"rain": "rain", "heat": "heat", "wind": "wind", "dry": "dry spell"}
PAIR_LABEL = {p: f"Prior {_N[p.split('_')[0]]} → {p.split('_')[1]} extreme" for p in PAIRS_ALL}
PROB4 = ["share", "ge1h", "ge6h", "ge12h"]
OUT4 = {"share": "Blackout share", "ge1h": "≥ 1 h", "ge6h": "≥ 6 h", "ge12h": "≥ 12 h"}
PROB = ["ge1h", "ge6h", "ge12h"]
OUT_SHORT = {"ge1h": "≥ 1 h", "ge6h": "≥ 6 h", "ge12h": "≥ 12 h"}

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"], "font.size": 7,
    "axes.edgecolor": INK2, "axes.linewidth": 0.6, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": INK2, "ytick.color": INK2, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
})


def save(fig, name):
    os.makedirs(FIG_DIR, exist_ok=True)
    fig.savefig(os.path.join(FIG_DIR, name + ".png"), dpi=DPI, bbox_inches="tight")
    fig.savefig(os.path.join(FIG_DIR, name + ".pdf"), bbox_inches="tight")
    plt.close(fig)
    print("saved", name)


def shade(hexcol, f):
    r = np.array(mc.to_rgb(hexcol))
    return tuple(1 - f * (1 - r))


def fig1(r):
    cq, sq = MAIN
    d = r[(np.isclose(r.chronic_q, cq)) & (np.isclose(r.same_q, sq)) & (r.chronic_days == 30)]
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.8), sharey=True)
    for ax, pair in zip(axes, ["rain_rain", "heat_heat", "heat_rain"]):
        ax.axhline(0, color=INK2, linewidth=0.6)
        s = d[d.pair == pair]
        ok = len(s) > 0 and min(s.cell_acute_only.iloc[0], s.cell_both.iloc[0]) >= MIN_CELL
        ax.set_title(PAIR_LABEL[pair], loc="left", fontsize=8, fontweight="bold")
        if not ok:
            cells = (int(s.cell_acute_only.iloc[0]), int(s.cell_both.iloc[0])) if len(s) else (0, 0)
            ax.text(0.5, 0.5, f"not estimable at this specification:\nonly {cells[0]:,} extreme days after normal\nconditions ({cells[1]:,} after chronic stress)",
                    transform=ax.transAxes, ha="center", va="center", fontsize=6.5, color=INK2)
            ax.set_xticks([])
            continue
        for k, o in enumerate(PROB):
            for j, (q, lab, f) in enumerate((("acute_when_normal", "after normal conditions", 0.45), ("acute_after_chronic_stress", "after chronic stress", 1.0))):
                e = s[(s.outcome == o) & (s.quantity == q)].iloc[0]
                x = k + (j - 0.5) * 0.28
                ax.vlines(x, e.lo, e.hi, color=shade(COL[pair], f), linewidth=1.3)
                ax.scatter([x], [e.est], s=22, marker="o" if j == 0 else "D", color=shade(COL[pair], f), edgecolor="white", linewidth=0.7,
                           zorder=4, label=lab if k == 0 else None)
        ax.set_xticks(range(len(PROB))); ax.set_xticklabels([OUT_SHORT[o] for o in PROB])
        ax.set_xlabel("Outage length")
        ax.grid(axis="y", color=GRID, linewidth=0.5); ax.set_axisbelow(True)
        ax.legend(fontsize=6, loc="upper left")
    axes[0].set_ylabel("Change in probability of an outage (pp)\nfrom a same-day extreme")
    fig.tight_layout()
    save(fig, "xfig1_acute_by_state")


def fig2(r):
    d = r[(r.quantity == "interaction") & (r.chronic_days == 30) & (r.cell_acute_only >= MIN_CELL) & (r.cell_both >= MIN_CELL)]
    specs = d.drop_duplicates(["pair", "chronic_q", "same_q"])[["pair", "chronic_q", "same_q"]].sort_values(["pair", "chronic_q", "same_q"]).reset_index(drop=True)
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 0.17 * len(specs) + 1.1), sharey=True)
    for ax, o in zip(axes, PROB):
        ax.axvline(0, color=INK2, linewidth=0.6)
        for i, sp in specs.iterrows():
            e = d[(d.pair == sp.pair) & np.isclose(d.chronic_q, sp.chronic_q) & np.isclose(d.same_q, sp.same_q) & (d.outcome == o)].iloc[0]
            ax.hlines(i, e.lo, e.hi, color=COL[sp.pair], linewidth=1.2)
            ax.scatter([e.est], [i], s=18, color=COL[sp.pair], edgecolor="white", linewidth=0.6, zorder=4)
        ax.set_yticks(range(len(specs)))
        ax.set_yticklabels([f"{PAIR_LABEL[p].replace(' extreme', '')}  (prior ≥ p{int(100 * c)}, today ≥ p{int(100 * s)})"
                            for p, c, s in zip(specs.pair, specs.chronic_q, specs.same_q)], fontsize=5)
        ax.invert_yaxis()
        ax.set_title(f"P(outage {OUT_SHORT[o]})", loc="left", fontsize=8, fontweight="bold")
        ax.grid(axis="x", color=GRID, linewidth=0.5); ax.set_axisbelow(True)
    fig.supxlabel("Interaction: change in the acute effect after chronic stress (pp)", fontsize=7, y=-0.02)
    fig.tight_layout()
    save(fig, "xfig2_interaction_forest")


def fig3(r):
    """Heat map of the interaction coefficient: pair x length of the prior window, chronic p75 and today p95 (p90 if thin)."""
    d = r[(r.quantity == "interaction") & (r.cell_acute_only >= MIN_CELL) & (r.cell_both >= MIN_CELL)]
    fig, axes = plt.subplots(1, 4, figsize=(7.2, 3.6), sharey=True)
    days = sorted(d.chronic_days.unique())
    for ax, o in zip(axes, PROB4):
        M = np.full((len(PAIRS_ALL), len(days)), np.nan); P = np.full_like(M, np.nan)
        for i, pr in enumerate(PAIRS_ALL):
            for j, nd in enumerate(days):
                e = d[(d.pair == pr) & (d.chronic_days == nd) & (d.outcome == o) & np.isclose(d.chronic_q, 0.75) & np.isclose(d.same_q, 0.90)]
                if len(e): M[i, j], P[i, j] = e.est.iloc[0], e.p.iloc[0]
        v = np.nanmax(np.abs(M))
        ax.imshow(np.ma.masked_invalid(M), cmap="RdBu_r", vmin=-v, vmax=v, aspect="auto")
        for i in range(M.shape[0]):
            for j in range(M.shape[1]):
                if np.isfinite(M[i, j]):
                    st = "**" if P[i, j] < .01 else "*" if P[i, j] < .05 else ""
                    ax.text(j, i, f"{M[i, j]:.1f}{st}", ha="center", va="center", fontsize=5.5, color=INK)
                else:
                    ax.text(j, i, "–", ha="center", va="center", fontsize=6, color=INK2)
        ax.set_xticks(range(len(days))); ax.set_xticklabels([f"{n} d" for n in days])
        ax.set_title(OUT4[o], loc="left", fontsize=8, fontweight="bold")
        ax.spines[:].set_visible(False); ax.tick_params(length=0)
    axes[0].set_yticks(range(len(PAIRS_ALL))); axes[0].set_yticklabels([PAIR_LABEL[p].replace(" extreme", "") for p in PAIRS_ALL], fontsize=6)
    fig.supxlabel("Length of the prior window. Interaction in pp: prior state ≥ p75 (dry: ≤ p25), today ≥ p90.  * p<0.05, ** p<0.01, – not estimable", fontsize=6.2, y=0.0)
    fig.tight_layout()
    save(fig, "xfig3_interaction_heatmap")


if __name__ == "__main__":
    r = pd.read_csv(os.path.join(RESULTS_DIR, "interaction_results.csv"))
    fig1(r)
    fig2(r)
    fig3(r)
'''

# ---------------------------------------------------------------- plot_forest_interaction.py
_SOURCES['plot_forest_interaction'] = r'''
"""
plot_forest_interaction.py
==========================
Draws forest_interaction_results.csv (from compute_forest_interaction.py). One panel per same-day extreme (wind, with rain
and heat as placebos). Dots: the interaction d3 = how much more (positive) or less (negative) the extreme matters at
stations with above-median forest cover for their climate zone, 50 km buffer, with 95% CIs, for each outcome and threshold.
Output: figures_forest/ffig1_forest_interaction (PNG at 600 dpi and PDF).
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS_DIR = os.path.expanduser(
    "~/Library/CloudStorage/OneDrive-GeorgiaInstituteofTechnology/Research/Energy_resilience/01_data/processed/main_model_results")
FIG_DIR = os.path.join(RESULTS_DIR, "figures_forest")
DPI = 600
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
COL = {0.90: "#2a78d6", 0.95: "#eb6834", 0.99: "#8a5cc2"}
OUTS = [("share", "Blackout share"), ("ge1h", "≥ 1 h"), ("ge6h", "≥ 6 h"), ("ge12h", "≥ 12 h")]
PANELS = [("wind", "Wind extreme (the tree hypothesis)"), ("rain", "Rain extreme (placebo)"), ("heat", "Heat extreme (placebo)")]
plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"], "font.size": 7,
                     "axes.edgecolor": INK2, "axes.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
                     "legend.frameon": False, "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white"})

if __name__ == "__main__":
    r = pd.read_csv(os.path.join(RESULTS_DIR, "forest_interaction_results.csv"))
    d = r[(r.quantity == "interaction") & (r.measure == "high") & (r.forest == "buffer50km")]
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.9), sharey=True)
    for ax, (a, title) in zip(axes, PANELS):
        ax.axhline(0, color=INK2, linewidth=0.6)
        for k, (o, ol) in enumerate(OUTS):
            for j, q in enumerate([0.90, 0.95, 0.99]):
                e = d[(d.acute == a) & (d.outcome == o) & np.isclose(d.same_q, q)]
                if not len(e): continue
                e = e.iloc[0]; x = k + (j - 1) * 0.22
                ax.vlines(x, e.lo, e.hi, color=COL[q], linewidth=1.1)
                ax.scatter([x], [e.est], s=14, color=COL[q], edgecolor="white", linewidth=0.5, zorder=4, label=f"today ≥ p{int(q*100)}" if k == 0 else None)
        ax.set_xticks(range(len(OUTS))); ax.set_xticklabels([o[1] for o in OUTS], fontsize=6)
        ax.set_title(title, loc="left", fontsize=7.5, fontweight="bold")
        ax.grid(axis="y", color=GRID, linewidth=0.5); ax.set_axisbelow(True)
    axes[0].set_ylabel("Interaction with forest cover (pp):\nhigh-forest minus low-forest stations")
    axes[0].legend(fontsize=6, loc="lower left")
    fig.tight_layout()
    os.makedirs(FIG_DIR, exist_ok=True)
    fig.savefig(os.path.join(FIG_DIR, "ffig1_forest_interaction.png"), dpi=DPI, bbox_inches="tight")
    fig.savefig(os.path.join(FIG_DIR, "ffig1_forest_interaction.pdf"), bbox_inches="tight")
'''

# ---------------------------------------------------------------- plot_knot_sensitivity.py
_SOURCES['plot_knot_sensitivity'] = r'''
"""
plot_knot_sensitivity.py
========================
Draws knot_sensitivity_curves.csv (from compute_knot_sensitivity.py): the same-day percentile curve for each knot set.
Rows: outcome (outage >= 1 h, >= 12 h). Columns: temperature, rain, wind. Shaded band: 95% CI of the main knot set.
Output: figures_knots/kfig1_knot_sensitivity (PNG at 600 dpi and PDF).
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS_DIR = os.path.expanduser(
    "~/Library/CloudStorage/OneDrive-GeorgiaInstituteofTechnology/Research/Energy_resilience/01_data/processed/main_model_results")
FIG_DIR = os.path.join(RESULTS_DIR, "figures_knots")
DPI = 600
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
STYLE = {"current": ("#0b0b0b", "-", 1.6, "main: 5, 25, 50, 90, 99"), "harrell5": ("#2a78d6", "--", 1.0, "Harrell 5: 5, 27.5, 50, 72.5, 95"),
         "harrell4": ("#eb6834", "--", 1.0, "Harrell 4: 5, 35, 65, 95"), "harrell6": ("#2a9d8f", "--", 1.0, "Harrell 6: 5, 23, 41, 59, 77, 95"),
         "upper_tail": ("#8a5cc2", ":", 1.3, "tail: 10, 50, 90, 97.5, 99.5")}
VARS = [("T", "Temperature"), ("P", "Rain (wet days)"), ("W", "Wind")]
OUTS = [("ge1h", "P(outage ≥ 1 h)"), ("ge12h", "P(outage ≥ 12 h)")]
plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"], "font.size": 7,
                     "axes.edgecolor": INK2, "axes.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
                     "legend.frameon": False, "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white"})

if __name__ == "__main__":
    c = pd.read_csv(os.path.join(RESULTS_DIR, "knot_sensitivity_curves.csv"))
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 4.2), sharex=True)
    for i, (o, ol) in enumerate(OUTS):
        for j, (v, vl) in enumerate(VARS):
            ax = axes[i, j]
            ax.axhline(0, color=INK2, linewidth=0.5)
            m = c[(c["var"] == v) & (c.outcome == o) & (c.knots == "current")]
            ax.fill_between(m["rank"], m.lo, m.hi, color="#0b0b0b", alpha=0.08, linewidth=0)
            for k, (col, ls, lw, lab) in STYLE.items():
                d = c[(c["var"] == v) & (c.outcome == o) & (c.knots == k)]
                ax.plot(d["rank"], d.coef, color=col, linestyle=ls, linewidth=lw, label=lab)
            ax.grid(axis="y", color=GRID, linewidth=0.5)
            if i == 0: ax.set_title(vl, loc="left", fontsize=8, fontweight="bold")
            if j == 0: ax.set_ylabel(f"{ol}\nvs median day (pp)")
            if i == 1: ax.set_xlabel("Within-zone percentile")
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, fontsize=6, bbox_to_anchor=(0.5, -0.04))
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    os.makedirs(FIG_DIR, exist_ok=True)
    fig.savefig(os.path.join(FIG_DIR, "kfig1_knot_sensitivity.png"), dpi=DPI, bbox_inches="tight")
    fig.savefig(os.path.join(FIG_DIR, "kfig1_knot_sensitivity.pdf"), bbox_inches="tight")
'''

# ---------------------------------------------------------------- plot_dry_heat.py
_SOURCES['plot_dry_heat'] = r'''
"""
plot_dry_heat.py
================
Figure for the exploratory dry spell -> heat result (prior 30-day rain at or below the zone's 25th percentile; heat extreme =
daily maximum temperature at or above the zone's 90th percentile). Reads interaction_results.csv,
interaction_robustness.csv and dry_heat_confirmation.csv.
  a  Heat association after normal conditions vs after a dry spell, for outages of >= 1, 6 and 12 h.
  b  Robustness for >= 12 h: interaction under each check (the future-state placebo and the permutation should be near zero).
  c  Stability for >= 12 h: interaction in 60 random station halves (dots), the full sample (line) and leaving out each year.
Output: figures_dry_heat/dfig1_dry_heat (PNG at 600 dpi and PDF). Units: percentage points of the probability of an outage.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS_DIR = os.path.expanduser(
    "~/Library/CloudStorage/OneDrive-GeorgiaInstituteofTechnology/Research/Energy_resilience/01_data/processed/main_model_results")
FIG_DIR = os.path.join(RESULTS_DIR, "figures_dry_heat")
DPI = 600
INK, INK2, GRID, C1, C2 = "#0b0b0b", "#52514e", "#e4e3df", "#8a8984", "#eb6834"
plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"], "font.size": 7,
                     "axes.edgecolor": INK2, "axes.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
                     "legend.frameon": False, "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white"})

if __name__ == "__main__":
    r = pd.read_csv(os.path.join(RESULTS_DIR, "interaction_results.csv"))
    rb = pd.read_csv(os.path.join(RESULTS_DIR, "interaction_robustness.csv"))
    cf = pd.read_csv(os.path.join(RESULTS_DIR, "dry_heat_confirmation.csv"))
    fig, axes = plt.subplots(1, 3, figsize=(7.6, 2.9), gridspec_kw=dict(width_ratios=[1.0, 1.25, 1.0], wspace=1.0))

    # a
    ax = axes[0]
    d = r[(r.pair == "dry_heat") & (r.chronic_days == 30) & np.isclose(r.chronic_q, 0.75) & np.isclose(r.same_q, 0.90)]
    ax.axhline(0, color=INK2, linewidth=0.6)
    for k, (o, ol) in enumerate([("ge1h", "≥ 1 h"), ("ge6h", "≥ 6 h"), ("ge12h", "≥ 12 h")]):
        for j, (q, col, lab) in enumerate([("acute_when_normal", C1, "after normal conditions"), ("acute_after_chronic_stress", C2, "after a dry spell")]):
            e = d[(d.outcome == o) & (d.quantity == q)].iloc[0]; x = k + (j - 0.5) * 0.28
            ax.vlines(x, e.lo, e.hi, color=col, linewidth=1.3)
            ax.scatter([x], [e.est], s=20, color=col, edgecolor="white", linewidth=0.6, zorder=4, marker="o" if j == 0 else "D", label=lab if k == 0 else None)
    ax.set_xticks(range(3)); ax.set_xticklabels(["≥ 1 h", "≥ 6 h", "≥ 12 h"]); ax.set_xlabel("Outage length")
    ax.set_ylabel("Change in probability of an outage (pp)\nfrom a heat extreme"); ax.set_ylim(-3.3, 5.0); ax.legend(fontsize=6, loc="upper left")
    ax.set_title("a", loc="left", fontweight="bold", fontsize=8); ax.grid(axis="y", color=GRID, linewidth=0.5)

    # b
    ax = axes[1]
    b = rb[(rb.case == "dry_heat") & (rb.outcome == "ge12h") & np.isclose(rb.same_q, 0.90)]
    labs, ests = [], []
    order = [("baseline", None, "Main specification"), ("seasonal_acute", None, "+ acute × month"), ("zone_acute", None, "+ acute × zone"),
             ("skip_3d", None, "Skip last 3 days"), ("future_placebo", None, "Placebo: next 30 d"), ("permuted", None, "Permuted (years)")]
    ax.axvline(0, color=INK2, linewidth=0.6)
    for i, (ck, _, lab) in enumerate(order):
        e = b[b.check == ck].iloc[0]
        col = C2 if ck in ("baseline", "seasonal_acute", "zone_acute", "skip_3d") else C1
        ax.hlines(i, e.lo, e.hi, color=col, linewidth=1.3); ax.scatter([e.est], [i], s=18, color=col, edgecolor="white", linewidth=0.6, zorder=4)
    ax.set_yticks(range(len(order))); ax.set_yticklabels([o[2] for o in order], fontsize=6.3); ax.invert_yaxis()
    ax.set_xlabel("Interaction (pp), outages ≥ 12 h"); ax.set_title("b", loc="left", fontweight="bold", fontsize=8); ax.grid(axis="x", color=GRID, linewidth=0.5)

    # c
    ax = axes[2]
    h = cf[cf.check == "random_station_halves"]; f = cf[cf.check == "full_sample"].iloc[0]; y = cf[cf.check == "leave_one_year_out"]
    rng = np.random.default_rng(3)
    ax.axhline(0, color=INK2, linewidth=0.6)
    ax.scatter(rng.normal(0, 0.07, len(h)), h.est, s=7, color=C1, alpha=0.8, linewidth=0)
    ax.scatter(rng.normal(1, 0.07, len(y)), y.est, s=12, color=C1, alpha=0.9, linewidth=0)
    ax.scatter([2], [f.est], s=24, color=C2, zorder=4); ax.vlines(2, f.lo, f.hi, color=C2, linewidth=1.3)
    ax.set_xticks([0, 1, 2]); ax.set_xticklabels(["60\nhalves", "Leave\none year", "Full\nsample"], fontsize=6.3)
    ax.set_ylabel("Interaction (pp), outages ≥ 12 h"); ax.set_title("c", loc="left", fontweight="bold", fontsize=8); ax.grid(axis="y", color=GRID, linewidth=0.5)
    fig.subplots_adjust(left=0.08, right=0.99, bottom=0.2, top=0.9)
    os.makedirs(FIG_DIR, exist_ok=True)
    fig.savefig(os.path.join(FIG_DIR, "dfig1_dry_heat.png"), dpi=DPI, bbox_inches="tight")
    fig.savefig(os.path.join(FIG_DIR, "dfig1_dry_heat.pdf"), bbox_inches="tight")
'''


if __name__ == "__main__":
    main()
