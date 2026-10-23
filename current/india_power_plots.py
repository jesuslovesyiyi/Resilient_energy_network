#!/usr/bin/env python3
"""
india_power_plots.py  --  ALL FIGURES in one file (models are in india_power_models.py)
======================================================================================
Reads the result CSVs written by india_power_models.py and draws every figure (PNG at 600 dpi and PDF). Needs Python with
numpy, pandas and matplotlib only; it does not fit any model. It runs from any folder.

QUICK START
  1. Set OUTPUT_DIR below to the folder holding the result CSVs (or pass --output-dir).
  2. python india_power_plots.py              draw every figure, then gather the numbered ones in OUTPUT_DIR/paper_figures
  Options:  --output-dir DIR   --no-redraw (only gather figures already drawn)   --only main|si   --list

Figures go to OUTPUT_DIR/figures*, and the numbered main-text (Fig1-3) and SI (FigS1-...) figures are copied to
OUTPUT_DIR/paper_figures/main and /si with figure_index.csv. Move a figure between main and SI by editing MAIN_FIGS / SI_FIGS.
A figure whose result CSV is missing is reported and skipped.
The scripts are embedded unchanged as text in _SOURCES at the bottom (old script names).
"""
import argparse
import csv
import os
import re
import shutil
import sys
import traceback

# ----------------------------------------------------------------------
# CONFIGURATION -- absolute path; must be the OUTPUT_DIR of india_power_models.py
# ----------------------------------------------------------------------
DATA_DIR = "/Users/yiyi/Library/CloudStorage/OneDrive-GeorgiaInstituteofTechnology/Research/Energy_resilience/01_data/processed"
OUTPUT_DIR = os.path.join(DATA_DIR, "main_model_results")

PLOT_MODULES = ["plot_main_model", "plot_percentile_model", "plot_irf", "plot_variance_decomposition", "plot_interaction_model",
                "plot_forest_interaction", "plot_knot_sensitivity", "plot_dry_heat", "plot_model_fit"]

# Figures: (number, subfolder of OUTPUT_DIR, figure name, what it shows). Edit to move figures between main text and SI.
MAIN_FIGS = [
    ("Fig1", "figures_percentile", "pfig1_spline", "Same-day dose-response: change in outage probability by within-zone percentile (temperature, rain, wind; outages >= 1, 6, 12 h)"),
    ("Fig2", "figures", "fig1_chronic_profile", "Chronic profile: effect of the mean weather in each lag window (1 to 179 days before)"),
    ("Fig3", "figures_irf", "ifig5_by_percentile", "Timing across the whole 0-100 percentile range: same-day, next-day and cumulative response by zone-percentile bin, relative to the median band"),
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
    ("FigS9", "figures_fit", "mfig1_model_fit", "Goodness of fit: BIC and out-of-sample R2 of the main model and alternative specifications"),
    ("FigS10", "figures_irf", "ifig1_dl_response", "Distributed-lag impulse response to a one-standard-deviation shock"),
    ("FigS11", "figures_irf", "ifig2_dl_cumulative", "Cumulative impulse response"),
    ("FigS12", "figures_irf", "ifig3_event_q95", "Event-study response to a day at or above the 95th percentile"),
    ("FigS13", "figures_irf", "ifig4_event_q99", "Event-study response to a day at or above the 99th percentile"),
    ("FigS14", "figures_irf", "ifig6_heatmap", "Response by zone-percentile bin (relative to the median band) and lag (heat map)"),
    ("FigS14b", "figures_irf", "ifig6b_heatmap_exceedance", "Exceedance version of the heat map: a day at or above the zone p50 ... p99 versus days below (upper tail)"),
    ("FigS14c", "figures_irf", "ifig5b_by_threshold", "Exceedance version of the timing figure (upper tail)"),
    ("FigS15", "figures_irf", "ifig7_by_zone", "Event-study response to a p95 day, by climate zone"),
    ("FigS16", "figures_irf", "ifig7b_by_zone_q99", "Event-study response to a p99 day, by climate zone"),
    ("FigS17", "figures_irf", "ifig8_dl_by_zone", "Distributed-lag response to a one-standard-deviation shock, by climate zone"),
    ("FigS18", "figures_irf", "ifig6_heatmap_Am", "Heat map by percentile threshold and lag, climate zone Am"),
    ("FigS19", "figures_irf", "ifig6_heatmap_Aw", "Heat map by percentile threshold and lag, climate zone Aw"),
    ("FigS20", "figures_irf", "ifig6_heatmap_BSh", "Heat map by percentile threshold and lag, climate zone BSh"),
    ("FigS21", "figures_irf", "ifig6_heatmap_Cw", "Heat map by percentile threshold and lag, climate zone Cw"),
    ("FigS22", "figures_interaction", "xfig1_acute_by_state", "Chronic state x acute shock: effect after normal conditions and after chronic stress"),
    ("FigS23", "figures_interaction", "xfig2_interaction_forest", "Interaction across thresholds (30-day prior window)"),
    ("FigS24", "figures_interaction", "xfig3_interaction_heatmap", "Interaction by pair and prior-window length"),
    ("FigS25", "figures_forest", "ffig1_forest_interaction", "Forest cover x wind, rain and heat extremes (placebos)"),
    ("FigS26", "figures", "fig2_chronic_vs_extreme", "Flag-based model: chronic versus extreme-day associations"),
    ("FigS27", "figures", "fig5_net_decomposition", "Flag-based model: net association of an extreme day"),
    ("FigS28", "figures", "fig3_robustness", "Flag-based model: robustness"),
    ("FigS29", "figures", "fig4_event_counts", "Flag-based model: number of extreme days"),
]


_BUNDLE = os.path.abspath(__file__)
_STATE = {"output_dir": OUTPUT_DIR}


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
    if not a.no_redraw:
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
    ap.add_argument("--output-dir")
    ap.add_argument("--no-redraw", action="store_true")
    ap.add_argument("--only", choices=["main", "si"])
    ap.add_argument("--list", action="store_true", help="list the numbered figures and whether each exists")
    a = ap.parse_args()
    if a.output_dir:
        _STATE["output_dir"] = os.path.abspath(a.output_dir)
    if a.list:
        for num, folder, name, what in MAIN_FIGS + SI_FIGS:
            ok = os.path.exists(os.path.join(_STATE["output_dir"], folder, name + ".png"))
            print(f"{num:8s} {'ok     ' if ok else 'missing'} {folder}/{name}")
        return
    sys.exit(cmd_figures(a))


# ======================================================================
# EMBEDDED SCRIPTS (unchanged copies of the original files)
# ======================================================================
_SOURCES = {}

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
  ifig5_by_percentile  Timing across the WHOLE 0-100 percentile range: change in outage probability on the same day, the next
                       day and cumulatively over days 0-3, for each zone-percentile bin relative to the median band (40-60).
                       One row per outage length. (From irf_bins.csv; rain also has a "dry" day row.)
  ifig6_heatmap        The full impulse-response surface: response by days after the weather (x) and percentile bin (y), relative
                       to the median band. Faded cells are not distinguishable from zero.
  ifig6_heatmap_<zone> The same surface estimated inside each climate zone (Am, Aw, BSh, Cw).
  ifig5b_by_threshold  Exceedance version of ifig5: a day at or above the zone's p50 ... p99 versus all days below (upper tail only).
  ifig6b_heatmap_exceedance  Exceedance version of the heat map (upper tail only).
  ifig7_by_zone        Impulse response to a day at or above the 95th percentile, inside each climate zone (3 x 3 panels).
  ifig7b_by_zone_q99   Same for the 99th percentile.
  ifig8_dl_by_zone     Distributed-lag response to a +1 SD change (the zone's own SD), inside each climate zone.
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
ZONE_COL = {"Am": "#1b6ca8", "Aw": "#d98c1f", "BSh": "#b04a8f", "Cw": "#2f9e6b"}
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


def specs_of(g):
    """Threshold specifications present in g, ordered from the lowest percentile to the highest:
    lower tail (at or below) first, then upper tail (at or above)."""
    if "tail" not in g.columns:
        g = g.assign(tail="upper")
    u = g[["tail", "q"]].drop_duplicates()
    low = sorted(u[u["tail"] == "lower"].q.tolist())
    up = sorted(u[u["tail"] == "upper"].q.tolist())
    return [("lower", q) for q in low] + [("upper", q) for q in up]


def spec_label(tail, q):
    return ("≤" if tail == "lower" else "≥") + f"{100 * q:g}"


def sel(g, tail, q):
    if "tail" not in g.columns:
        g = g.assign(tail="upper")
    return g[(g["tail"] == tail) & np.isclose(g.q, q)]


def fig5(g, fname="ifig5_by_percentile"):
    specs = specs_of(g)
    n_low = sum(t == "lower" for t, _ in specs)
    xpos = [i + (1 if t == "upper" and n_low else 0) for i, (t, _) in enumerate(specs)]
    fig, axes = plt.subplots(3, 3, figsize=(7.2, 6.0), sharex="col")
    for i, o in enumerate(PROB):
        for j, v in enumerate(["T", "P", "W"]):
            ax = axes[i, j]
            ax.axhline(0, color=INK2, linewidth=0.6)
            if n_low:
                ax.axvline(n_low, color=INK2, linewidth=0.5, linestyle=(0, (1, 2)))
            for k, ls, lab, ycol, lo, hi in ((0, "-", "same day", "coef", "lo", "hi"), (1, "--", "next day", "coef", "lo", "hi"),
                                             (3, ":", "cumulative, days 0–3", "cum", "cum_lo", "cum_hi")):
                for tail in ("lower", "upper"):
                    pts = [(x, sel(g, t, q)) for x, (t, q) in zip(xpos, specs) if t == tail]
                    xs, ys, ls_, hs_ = [], [], [], []
                    for x, d in pts:
                        r = d[(d.outcome == o) & (d["var"] == v) & (d.k == k)]
                        if r.empty:
                            continue
                        xs.append(x); ys.append(float(r[ycol].iloc[0])); ls_.append(float(r[lo].iloc[0])); hs_.append(float(r[hi].iloc[0]))
                    if xs:
                        ax.fill_between(xs, ls_, hs_, color=COL[v], alpha=0.08, linewidth=0)
                        ax.plot(xs, ys, ls, color=COL[v], linewidth=1.2, label=lab if tail == ("lower" if n_low else "upper") else None)
            ax.set_xticks(xpos); ax.set_xticklabels([spec_label(t, q) for t, q in specs], fontsize=5.5, rotation=90)
            ax.grid(axis="y", color=GRID, linewidth=0.5); ax.set_axisbelow(True)
            if i == 0:
                ax.set_title(VAR_NAME[v], loc="left", fontsize=8, fontweight="bold")
            if j == 0:
                ax.set_ylabel(f"P(outage {OUT_SHORT[o]}), pp")
            if i == 2:
                ax.set_xlabel("Zone percentile (≤ lower, ≥ upper)", fontsize=6.5)
            if i == 0 and j == 0:
                ax.legend(fontsize=5.5, loc="upper left")
    fig.tight_layout()
    save(fig, fname)


def heatmap(g, fname, title=None):
    specs = specs_of(g)
    n_low = sum(t == "lower" for t, _ in specs)
    fig, axes = plt.subplots(3, 3, figsize=(7.2, 6.4), sharex=True, sharey=True)
    fig.text(0.0, 0.5, "Zone-specific percentile threshold (≤ lower tail, ≥ upper tail)", rotation=90, va="center", ha="center", fontsize=7)
    for i, o in enumerate(PROB):
        sub_o = g[g.outcome == o]
        lim = np.nanpercentile(np.abs(sub_o.coef), 97)
        for j, v in enumerate(["T", "P", "W"]):
            ax = axes[i, j]
            sub = sub_o[sub_o["var"] == v]
            ks = sorted(sub.k.unique())
            Z = np.full((len(specs), len(ks)), np.nan); sig = np.zeros_like(Z, dtype=bool)
            for r, (t, q) in enumerate(specs):
                d = sel(sub, t, q).set_index("k")
                for c, k in enumerate(ks):
                    if k in d.index:
                        row = d.loc[k]
                        Z[r, c] = row["coef"]
                        sig[r, c] = not (row["lo"] <= 0 <= row["hi"])
            rgba = plt.cm.RdBu_r(plt.Normalize(-lim, lim)(Z))
            rgba[..., 3] = np.where(np.isnan(Z), 0.0, np.where(sig, 1.0, 0.25))
            ax.imshow(rgba, aspect="auto", origin="lower", extent=(ks[0] - 0.5, ks[-1] + 0.5, -0.5, len(specs) - 0.5))
            ax.axvline(-0.5, color=INK2, linewidth=0.6)
            if n_low:
                ax.axhline(n_low - 0.5, color=INK2, linewidth=0.6, linestyle=(0, (2, 2)))
            ax.set_yticks(range(len(specs))); ax.set_yticklabels([spec_label(t, q) for t, q in specs], fontsize=5.5)
            if i == 0:
                ax.set_title(VAR_NAME[v], loc="left", fontsize=8, fontweight="bold")
            if j == 0:
                ax.set_ylabel(f"P(outage {OUT_SHORT[o]})", labelpad=8)
            if i == 2:
                ax.set_xlabel("Days after the weather")
        sm = plt.cm.ScalarMappable(norm=plt.Normalize(-lim, lim), cmap="RdBu_r")
        cb = fig.colorbar(sm, ax=axes[i, :], fraction=0.02, pad=0.01); cb.ax.tick_params(labelsize=5.5); cb.set_label("pp", fontsize=6)
    if title:
        fig.suptitle(title, x=0.01, ha="left", fontsize=8, fontweight="bold")
    save(fig, fname)


REF_BIN = (40, 60)             # must match compute_irf.REF_BIN: the median band every bin is compared with


def bin_rows(g, v):
    """Row labels of the bin surface for variable v, from the lowest percentile to the highest, with the reference band in place."""
    d = g[g["var"] == v][["bin", "bin_lo"]].drop_duplicates()
    items = [(r.bin, -1.0 if r.bin == "dry" else float(r.bin_lo)) for r in d.itertuples()]
    ref = f"{REF_BIN[0]:g}–{REF_BIN[1]:g}"
    items.append((ref, float(REF_BIN[0])))
    items.sort(key=lambda t: t[1])
    return [a for a, _ in items], ref


def bin_profile(g, fname="ifig5_by_percentile"):
    fig, axes = plt.subplots(3, 3, figsize=(7.2, 6.0))
    for i, o in enumerate(PROB):
        for j, v in enumerate(["T", "P", "W"]):
            ax = axes[i, j]
            ax.axhline(0, color=INK2, linewidth=0.6)
            rows, ref = bin_rows(g, v)
            x = np.arange(len(rows))
            sub = g[(g.outcome == o) & (g["var"] == v)]
            for k, ls, lab, ycol, lo, hi in ((0, "-", "same day", "coef", "lo", "hi"), (1, "--", "next day", "coef", "lo", "hi"),
                                             (3, ":", "cumulative, days 0–3", "cum", "cum_lo", "cum_hi")):
                y, l, h = [], [], []
                for r in rows:
                    t = sub[(sub.bin == r) & (sub.k == k)]
                    if r == ref:
                        y.append(0.0); l.append(0.0); h.append(0.0)
                    elif t.empty:
                        y.append(np.nan); l.append(np.nan); h.append(np.nan)
                    else:
                        y.append(float(t[ycol].iloc[0])); l.append(float(t[lo].iloc[0])); h.append(float(t[hi].iloc[0]))
                ax.fill_between(x, l, h, color=COL[v], alpha=0.08, linewidth=0)
                ax.plot(x, y, ls, color=COL[v], linewidth=1.2, label=lab)
            ax.plot([rows.index(ref)], [0], "D", color=INK, markersize=3, zorder=5)
            ax.set_xticks(x); ax.set_xticklabels(["median" if r == ref else r for r in rows], fontsize=5.3, rotation=90)
            ax.grid(axis="y", color=GRID, linewidth=0.5); ax.set_axisbelow(True)
            if i == 0:
                ax.set_title(VAR_NAME[v], loc="left", fontsize=8, fontweight="bold")
            if j == 0:
                ax.set_ylabel(f"P(outage {OUT_SHORT[o]}), pp\nvs. the median band")
            if i == 2:
                ax.set_xlabel("Zone percentile bin", fontsize=6.5)
            if i == 0 and j == 0:
                ax.legend(fontsize=5.5, loc="upper left")
    fig.tight_layout()
    save(fig, fname)


def bin_heatmap(g, fname, title=None):
    fig, axes = plt.subplots(3, 3, figsize=(7.2, 6.4), sharex=True)
    for i, o in enumerate(PROB):
        sub_o = g[g.outcome == o]
        lim = np.nanpercentile(np.abs(sub_o.coef), 97)
        for j, v in enumerate(["T", "P", "W"]):
            ax = axes[i, j]
            sub = sub_o[sub_o["var"] == v]
            rows, ref = bin_rows(g, v)
            ks = sorted(sub.k.unique())
            Z = np.full((len(rows), len(ks)), np.nan); sig = np.zeros_like(Z, dtype=bool)
            for r, lab in enumerate(rows):
                d = sub[sub.bin == lab].set_index("k")
                for c, k in enumerate(ks):
                    if k in d.index:
                        row = d.loc[k]
                        Z[r, c] = row["coef"]
                        sig[r, c] = not (row["lo"] <= 0 <= row["hi"])
            rgba = plt.cm.RdBu_r(plt.Normalize(-lim, lim)(Z))
            rgba[..., 3] = np.where(np.isnan(Z), 0.0, np.where(sig, 1.0, 0.25))
            ref_r = rows.index(ref)
            rgba[ref_r, :, :] = (0.93, 0.93, 0.91, 1.0)                       # the reference band itself (zero by construction)
            ax.imshow(rgba, aspect="auto", origin="lower", extent=(ks[0] - 0.5, ks[-1] + 0.5, -0.5, len(rows) - 0.5))
            ax.axvline(-0.5, color=INK2, linewidth=0.6)
            ax.set_yticks(range(len(rows)))
            ax.set_yticklabels(["median" if r == ref else r for r in rows], fontsize=5.5)
            if i == 0:
                ax.set_title(VAR_NAME[v], loc="left", fontsize=8, fontweight="bold")
            if j == 0:
                ax.set_ylabel(f"P(outage {OUT_SHORT[o]})\nzone percentile bin")
            if i == 2:
                ax.set_xlabel("Days after the weather")
        sm = plt.cm.ScalarMappable(norm=plt.Normalize(-lim, lim), cmap="RdBu_r")
        cb = fig.colorbar(sm, ax=axes[i, :], fraction=0.02, pad=0.01); cb.ax.tick_params(labelsize=5.5); cb.set_label("pp vs. median band", fontsize=6)
    if title:
        fig.suptitle(title, x=0.01, ha="left", fontsize=8, fontweight="bold")
    save(fig, fname)


def fig_by_zone(z, tail, q, fname):
    d = sel(z, tail, q)
    if d.empty:
        return
    fig, axes = plt.subplots(3, 3, figsize=(7.2, 6.0), sharex=True)
    for i, o in enumerate(PROB):
        for j, v in enumerate(["T", "P", "W"]):
            ax = axes[i, j]
            ax.axhline(0, color=INK2, linewidth=0.6)
            ax.axvspan(d.k.min() - 0.5, -0.5, color="#f1f0ec", zorder=0)
            for zn, ls in ZONE_LS.items():
                s = d[(d["var"] == v) & (d.zone == zn) & (d.outcome == o)].sort_values("k")
                if s.empty:
                    continue
                n = int(s.n_stations.iloc[0])
                ax.fill_between(s.k, s.lo, s.hi, color=ZONE_COL[zn], alpha=0.07, linewidth=0)
                ax.plot(s.k, s.coef, ls, color=ZONE_COL[zn], linewidth=1.1, label=f"{zn} ({n})")
            ax.grid(axis="y", color=GRID, linewidth=0.5); ax.set_axisbelow(True)
            if i == 0:
                ax.set_title(VAR_NAME[v], loc="left", fontsize=8, fontweight="bold")
            if j == 0:
                ax.set_ylabel(f"P(outage {OUT_SHORT[o]}), pp")
            if i == 2:
                ax.set_xlabel("Days after the weather (0 = same day)")
            if i == 0 and j == 0:
                ax.legend(title="Zone (stations)", fontsize=5.5, title_fontsize=5.5, loc="upper left")
    fig.suptitle(f"Change in outage probability after a day {'at or above' if tail == 'upper' else 'at or below'} the "
                 f"zone's {100 * q:g}th percentile", x=0.01, ha="left", fontsize=7.5)
    fig.tight_layout()
    save(fig, fname)


def fig_dl_by_zone(z, fname="ifig8_dl_by_zone"):
    fig, axes = plt.subplots(3, 3, figsize=(7.2, 6.0), sharex=True)
    for i, o in enumerate(PROB):
        for j, v in enumerate(["T", "P", "W"]):
            ax = axes[i, j]
            ax.axhline(0, color=INK2, linewidth=0.6)
            ax.axvspan(z.k.min() - 0.5, -0.5, color="#f1f0ec", zorder=0)
            for zn, ls in ZONE_LS.items():
                s = z[(z["var"] == v) & (z.zone == zn) & (z.outcome == o)].sort_values("k")
                if s.empty:
                    continue
                ax.fill_between(s.k, s.lo, s.hi, color=ZONE_COL[zn], alpha=0.07, linewidth=0)
                ax.plot(s.k, s.coef, ls, color=ZONE_COL[zn], linewidth=1.1, label=f"{zn} ({int(s.n_stations.iloc[0])})")
            ax.grid(axis="y", color=GRID, linewidth=0.5); ax.set_axisbelow(True)
            if i == 0:
                ax.set_title(VAR_NAME[v], loc="left", fontsize=8, fontweight="bold")
            if j == 0:
                ax.set_ylabel(f"P(outage {OUT_SHORT[o]}), pp per +1 SD")
            if i == 2:
                ax.set_xlabel("Days after the weather (0 = same day)")
            if i == 0 and j == 0:
                ax.legend(title="Zone (stations)", fontsize=5.5, title_fontsize=5.5, loc="upper left")
    fig.tight_layout()
    save(fig, fname)


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
    bp = os.path.join(RESULTS_DIR, "irf_bins.csv")
    gp = os.path.join(RESULTS_DIR, "irf_event_grid.csv")
    have_bins = os.path.exists(bp)
    if have_bins:
        bdf = rd("irf_bins.csv")
        pooled = bdf[bdf.zone == "ALL"]
        bin_profile(pooled, "ifig5_by_percentile")
        bin_heatmap(pooled, "ifig6_heatmap")
        for zn in ZONE_LS:
            sub = bdf[bdf.zone == zn]
            if not sub.empty:
                bin_heatmap(sub, f"ifig6_heatmap_{zn}", title=f"Climate zone {zn} ({int(sub.n_stations.iloc[0])} stations)")
    if os.path.exists(gp):
        grid_df = rd("irf_event_grid.csv")
        fig5(grid_df, "ifig5b_by_threshold" if have_bins else "ifig5_by_percentile")
        heatmap(grid_df, "ifig6b_heatmap_exceedance" if have_bins else "ifig6_heatmap")
    zp = os.path.join(RESULTS_DIR, "irf_event_grid_by_zone.csv")
    if os.path.exists(zp):
        zdf = rd("irf_event_grid_by_zone.csv")
        fig_by_zone(zdf, "upper", 0.95, "ifig7_by_zone")
        fig_by_zone(zdf, "upper", 0.99, "ifig7b_by_zone_q99")
    dp = os.path.join(RESULTS_DIR, "irf_dl_by_zone.csv")
    if os.path.exists(dp):
        fig_dl_by_zone(rd("irf_dl_by_zone.csv"))
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

# ---------------------------------------------------------------- plot_model_fit.py
_SOURCES['plot_model_fit'] = r'''
"""
plot_model_fit.py
=================
Draws the model comparison written by compute_model_fit.py. Reads CSVs only.

FIGURE (PNG at 600 dpi and PDF, in RESULTS_DIR/figures_fit)
  mfig1_model_fit   One panel per outcome. Each dot is a model; x is its BIC relative to the main model (positive = the
                    model fits worse after the penalty for extra terms; symmetric-log axis). The number at the right is
                    the out-of-sample within-R2 (OOS R2: stations left out of the fit).
It also prints a plain table (all criteria) to the screen.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Must match OUTPUT_DIR in compute_main_model.py.
RESULTS_DIR = os.path.expanduser(
    "~/Library/CloudStorage/OneDrive-GeorgiaInstituteofTechnology/Research/Energy_resilience/01_data/processed/main_model_results")
FIG_DIR = os.path.join(RESULTS_DIR, "figures_fit")
DPI = 600
MAIN_MODEL = "I"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
WORSE, BETTER, MAIN = "#d4553a", "#2a78d6", "#0b0b0b"
OUT_NAME = {"share": "Blackout share", "ge1h": "Outage ≥ 1 h", "ge6h": "Outage ≥ 6 h", "ge12h": "Outage ≥ 12 h"}

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"], "font.size": 7,
    "axes.edgecolor": INK2, "axes.linewidth": 0.6, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": INK2, "ytick.color": INK2, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
})


def main():
    df = pd.read_csv(os.path.join(RESULTS_DIR, "model_fit.csv"))
    outs = [o for o in OUT_NAME if o in set(df.outcome)]
    models = sorted(set(df.model))
    labels = df.drop_duplicates("model").set_index("model")["label"].to_dict()
    fig, axes = plt.subplots(1, len(outs), figsize=(7.4, 3.4), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, o in zip(axes, outs):
        d = df[df.outcome == o].set_index("model")
        ax.axvline(0, color=INK2, linewidth=0.6)
        for i, m in enumerate(models):
            x = float(d.loc[m, "d_bic"])
            col = MAIN if m == MAIN_MODEL else (WORSE if x > 0 else BETTER)
            ax.plot([0, x], [i, i], color=col, linewidth=0.7, alpha=0.6)
            ax.plot(x, i, "o", color=col, markersize=4.5, markeredgecolor="white", markeredgewidth=0.5)
        ax.set_xscale("symlog", linthresh=10)
        ax.set_xticks([-100, -10, 0, 10, 100, 1000]); ax.set_xticklabels(["−100", "−10", "0", "10", "100", "1000"], fontsize=5.5)
        ax.minorticks_off()
        ax.set_yticks(range(len(models)))
        ax.set_yticklabels([labels[m] for m in models], fontsize=6)
        ax.set_ylim(len(models) - 0.4, -0.6)
        ax.set_title(OUT_NAME[o], loc="left", fontsize=8, fontweight="bold")
        ax.grid(axis="x", color=GRID, linewidth=0.5); ax.set_axisbelow(True)
        ax.set_xlabel("ΔBIC vs. main", fontsize=6.5)
        for i, m in enumerate(models):
            ax.annotate(f"{100 * float(d.loc[m, 'cv_within_r2']):.2f}%", xy=(1.0, i), xycoords=("axes fraction", "data"),
                        xytext=(2, 0), textcoords="offset points", fontsize=5, color=INK2, va="center", ha="left")
    for ax in axes:
        ax.annotate("OOS R²", xy=(1.0, 1.0), xycoords="axes fraction", xytext=(3, 3), textcoords="offset points",
                    fontsize=5.5, color=INK2, ha="left", va="bottom")
    fig.tight_layout()
    os.makedirs(FIG_DIR, exist_ok=True)
    fig.savefig(os.path.join(FIG_DIR, "mfig1_model_fit.png"), dpi=DPI, bbox_inches="tight")
    fig.savefig(os.path.join(FIG_DIR, "mfig1_model_fit.pdf"), bbox_inches="tight")
    plt.close(fig)
    print("saved mfig1_model_fit")
    pd.set_option("display.width", 200)
    show = df[["outcome", "model", "label", "k_slopes", "within_r2", "cv_within_r2", "d_aic", "d_bic"]].copy()
    show["within_r2"] = (100 * show.within_r2).round(3); show["cv_within_r2"] = (100 * show.cv_within_r2).round(3)
    show[["d_aic", "d_bic"]] = show[["d_aic", "d_bic"]].round(1)
    print(show.to_string(index=False))


if __name__ == "__main__":
    main()
'''


if __name__ == "__main__":
    main()
