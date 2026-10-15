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
  main_quantities.csv       acute beta, cumulative chronic Delta^v (eq. 5), extreme-day delta,
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
WINDOWS = {"[0,1]": (0, 2), "[2,6]": (2, 7), "[7,13]": (7, 14), "[14,29]": (14, 30)}  # lag ranges [lo, hi)
ACUTE = "[0,1]"
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
    mats = {"T": lag_matrix(grid, "tmax", 29), "P": lag_matrix(grid, "rain", 29),
            "W": lag_matrix(grid, "wind", 29)}
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
    XtX_inv = np.linalg.inv(Xd.T @ Xd)
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
        acute = f"X{v}_{ACUTE}"
        beyond = [f"X{v}_{b}" for b in WINDOWS if b != ACUTE]
        est, se = lincomb(fit, {n: 1.0 for n in beyond})
        est_sd, se_sd = lincomb(fit, {n: float(fit.sd_within[n]) for n in beyond})
        a_est, a_se = lincomb(fit, {acute: 1.0})
        sd_a = float(fit.sd_within[acute])
        rows.append(dict(outcome=outcome, spec=spec, var=v, quantity="acute_beta", est=a_est, se=a_se,
                         est_per_sd=a_est * sd_a, se_per_sd=a_se * sd_a, p=z(a_est, a_se)))
        rows.append(dict(outcome=outcome, spec=spec, var=v, quantity="chronic_beyond_acute_Delta", est=est, se=se,
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
