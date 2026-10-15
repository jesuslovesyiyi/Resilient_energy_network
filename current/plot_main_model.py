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
                           changes with the length of the lag window. Per within-SD of the exposure.
  fig2_chronic_vs_extreme  One panel per outcome. Chronic (+1 SD in every window beyond the acute one,
                           dots) next to the NET effect of an extreme day (diamonds): the predicted
                           difference between flagged days and other days of the same station-month,
                           chronic terms plus the extreme-day coefficient.
  fig3_robustness          The chronic-beyond-acute association Delta under each robustness spec,
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
WINDOWS = ["[0,1]", "[2,6]", "[7,13]", "[14,29]"]
WIN_LABEL = ["0–1 d\n(acute)", "2–6 d", "7–13 d", "14–29 d"]
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
        ax.set_xticks(x); ax.set_xticklabels(WIN_LABEL); ax.set_xlim(-0.45, len(WINDOWS) - 0.55)
        ax.set_title(VAR_NAME[v], loc="left", fontsize=8, fontweight="bold", pad=10)
        ax.text(0, 1.015, f"1 SD ≈ {sd:.2f} {VAR_UNIT[v]} (mean over windows)", transform=ax.transAxes,
                fontsize=6, color=INK2, va="bottom")
        light_grid(ax, "y"); tag(ax, "abc"[["T", "P", "W"].index(v)])
        ax.legend(title="Outage length", fontsize=6, title_fontsize=6, loc="upper right" if v != "P" else "upper right")
    pad = 0.06 * (max(hi_all) - min(lo_all))
    axes[0].set_ylim(min(lo_all) - pad, max(hi_all) + pad)
    axes[0].set_ylabel("Change in probability of an outage\nper 1 SD of exposure (pp)")
    axes[1].set_xlabel("Lag window (days before and including day t)")
    fig.tight_layout()
    save(fig, "fig1_chronic_profile")


def mpl_shade(hexcol, f):
    """Blend a colour towards white; f=1 keeps the full colour."""
    import matplotlib.colors as mc
    r = np.array(mc.to_rgb(hexcol))
    return tuple(1 - f * (1 - r))


def fig2(quant, counts):
    n_by = counts.set_index("flag")["station_days"].to_dict()
    outs = ["share"] + PROB
    flags = [f for f in ["ET", "EP1", "EP2", "EP3", "EW"] if f in set(quant["var"])]
    labels = ([f"{VAR_NAME[v]}\n(windows 2–29 d)" for v in ["T", "P", "W"]] +
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
        ch = q[q.quantity == "chronic_beyond_acute_Delta"].set_index("var")
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
    axes[0].text(-1.2, -0.55, "Chronic: +1 SD beyond\nthe acute window (dots)", transform=axes[0].get_yaxis_transform(),
                 fontsize=6.5, fontweight="bold", va="center", ha="left", clip_on=False)
    axes[0].text(-1.2, ypos[3] - 0.85, "Extreme day, net effect (diamonds)", transform=axes[0].get_yaxis_transform(),
                 fontsize=6.5, fontweight="bold", va="center", ha="left", clip_on=False)
    fig.suptitle("Change in daily blackout share (panel a) or in the probability of an outage of at least 1, 6 or 12 h (b–d)",
                 fontsize=7, x=0.01, ha="left", y=1.0)
    fig.tight_layout()
    save(fig, "fig2_chronic_vs_extreme")


def fig3(rob):
    d = rob[rob.quantity == "chronic_beyond_acute_Delta"].copy()
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
    fig.supxlabel("Chronic association beyond the acute window, Δ per 1 SD in every window (pp of probability)", fontsize=7, y=-0.03)
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
