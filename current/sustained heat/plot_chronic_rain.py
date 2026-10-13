"""
plot_chronic_rain.py
====================
Reads the CSVs written by compute_chronic_rain.py and draws:

  MAIN TEXT
  rain_window_curve.png     Fig R1: effect of rain going from none to 5 mm/day on average over the
                            window, by window length (specs a / b / c = earlier days only).
  rain_heterogeneity.png    Fig R2: 1-day vs 14-day effect by season and climate zone.
  rain_lag_placebo.png      Fig R3: (left) effect of rain k days ago, estimated jointly;
                            (right) placebo: FUTURE rain should show no effect.

  SUPPLEMENT
  rain_run_length.png       Fig RS1: blackout vs length of the current wet-day streak.

All effects are percentage points of the day (1 pp = 14.4 minutes) for rain going from none to
5 mm/day. No fitting happens here. Edit styling and rerun.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "Library/CloudStorage/OneDrive-GeorgiaInstituteofTechnology/Research/Energy_resilience/01_data/processed", "temp_threshold")
FE = "station_month"
PP = 100.0
DPI = 600                     # PNG resolution; a vector PDF is also saved for each figure
CONTRAST = "none to 5 mm/day"

INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#898781", "#e6e5e1"
BLUE, ORANGE, GRAY = "#2a78d6", "#eb6834", "#898781"

plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK2, "xtick.color": INK2,
    "ytick.color": INK2, "text.color": INK, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "figure.facecolor": "white", "axes.facecolor": "white", "legend.frameon": False,
})


def p(n): return os.path.join(OUTPUT_DIR, n)


def fmt_p(x): return "p < 0.001" if x < 1e-3 else f"p = {x:.3f}"


def save(fig, name):
    fig.savefig(p(name), dpi=DPI, bbox_inches="tight", facecolor="white")
    fig.savefig(p(name.replace(".png", ".pdf")), bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------- Fig R1
def plot_window():
    d = pd.read_csv(p("rain_window_effects.csv")); d = d[d.fe == FE]
    t = pd.read_csv(p("rain_window_diff_tests.csv"))
    specs = [("a_temp_controls", GRAY, "Window incl. today, temperature controls", 1.6),
             ("b_plus_wind", BLUE, "Window incl. today, + wind", 1.6),
             ("c_antecedent_beyond_today", ORANGE, "Earlier days only (excl. today), holding today's rain fixed", 2.4)]
    fig, ax = plt.subplots(figsize=(8.5, 5.4))
    for v, c, lab, lw in specs:
        s = d[d.variant == v].sort_values("window_days")
        if s.empty: continue
        ax.fill_between(s.window_days, s.lo * PP, s.hi * PP, color=c, alpha=0.13, lw=0)
        ax.plot(s.window_days, s.coef * PP, "-o", color=c, lw=lw, ms=5, mec="white", mew=1.2, label=lab)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xscale("log")
    ks = sorted(d.window_days.unique()); ax.set_xticks(ks); ax.set_xticklabels(ks); ax.minorticks_off()
    ax.set_xlabel("Rain window: number of days averaged (mean daily rainfall)")
    ax.set_ylabel(f"Effect of rain from {CONTRAST} (pp of the day)")
    ax.set_title("Rain effects are front-loaded: they peak over 2-3 days and do not build up",
                 loc="left", fontsize=11, fontweight="bold")
    a = t[(t.variant == "a_temp_controls") & t.comparison.str.startswith("3-day")]
    b = t[(t.variant == "a_temp_controls") & t.comparison.str.startswith("14-day")]
    lines = []
    if len(a): lines.append(f"3-day minus 1-day: {a.iloc[0]['diff']*PP:+.2f} pp, {fmt_p(a.iloc[0]['p'])}")
    if len(b): lines.append(f"14-day minus 1-day: {b.iloc[0]['diff']*PP:+.2f} pp, {fmt_p(b.iloc[0]['p'])}")
    if lines:
        ax.text(0.985, 0.97, "\n".join(lines), transform=ax.transAxes, va="top", ha="right", fontsize=9, color=INK2)
    ax.set_ylim(bottom=min(0, ax.get_ylim()[0]), top=ax.get_ylim()[1] + 0.25)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=1, fontsize=9, handlelength=1.6)
    ax.text(0.0, -0.40, "Bands: 95% CI, clustered by station. Station x calendar-month and year fixed effects; "
            "temperature controls throughout.", transform=ax.transAxes, fontsize=8, color=MUTED)
    fig.tight_layout(); save(fig, "rain_window_curve.png")


# ---------------------------------------------------------------- Fig R2
def plot_het():
    h = pd.read_csv(p("rain_heterogeneity.csv")); h = h[h.group_type != "all"]
    rows, y = [], 0.0
    for gt, title in (("season", "SEASON"), ("climate zone", "CLIMATE ZONE (Köppen)")):
        g = h[h.group_type == gt]
        rows.append(("header", title, y)); y += 0.8
        for grp in list(dict.fromkeys(g.group)):
            n = g[(g.group == grp) & (g.window_days == 14)].n_stations
            lab = f"{grp}  (n = {int(n.iloc[0])} stations)" if len(n) else grp
            rows.append(("row", (gt, grp, lab), y)); y += 1.0
        y += 0.3
    fig, ax = plt.subplots(figsize=(8.8, 0.46 * y + 1.8))
    for kind, val, yy in rows:
        if kind == "header":
            ax.text(-0.02, yy, val, transform=ax.get_yaxis_transform(), ha="right", va="center",
                    fontsize=8.5, color=INK2, fontweight="bold")
    for off, k, col, lab in ((-0.17, 1, GRAY, "1-day window"), (0.17, 14, BLUE, "14-day window")):
        first = True
        for kind, val, yy in rows:
            if kind != "row": continue
            gt, grp, _ = val
            s = h[(h.group_type == gt) & (h.group == grp) & (h.window_days == k)]
            if s.empty: continue
            r = s.iloc[0]
            ax.errorbar(r.coef * PP, yy + off, xerr=[[(r.coef - r.lo) * PP], [(r.hi - r.coef) * PP]],
                        fmt="o", color=col, ms=6, mec="white", mew=1, capsize=0, elinewidth=1.8,
                        label=lab if first else None)
            first = False
    ax.set_yticks([yy for kd, _, yy in rows if kd == "row"])
    ax.set_yticklabels([v[2] for kd, v, _ in rows if kd == "row"])
    ax.set_ylim(y - 0.5, -0.8); ax.axvline(0, color=MUTED, lw=0.8); ax.grid(axis="y", visible=False)
    ax.set_xlabel(f"Effect on daily blackout of rain going from {CONTRAST} (pp)")
    ax.set_title("Rain effects by season and climate zone", loc="left", fontsize=11, fontweight="bold", pad=12)
    ax.legend(loc="lower right", fontsize=9)
    fig.tight_layout(); save(fig, "rain_heterogeneity.png")


# ---------------------------------------------------------------- Fig R3
def plot_lag_placebo():
    l = pd.read_csv(p("rain_DL_lags.csv")); l = l[l.fe == FE]
    past = l[l.term.str.startswith("zl")].copy(); past["k"] = past.term.str[2:].astype(int); past = past.sort_values("k")
    fut = l[l.term.str.startswith("zf")].copy(); fut["k"] = fut.term.str[2:].astype(int); fut = fut.sort_values("k")
    tt = pd.read_csv(p("rain_DL_tests.csv")); tt = tt[tt.fe == FE]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 4.6), gridspec_kw={"width_ratios": [1.6, 1]})
    a1.errorbar(past.k, past.coef * PP, yerr=[(past.coef - past.lo) * PP, (past.hi - past.coef) * PP],
                fmt="o", color=BLUE, ms=6, mec="white", mew=1, elinewidth=1.8, capsize=0)
    a1.axhline(0, color=MUTED, lw=0.8)
    a1.set_xlabel("Days before the outcome day (0 = same day)")
    a1.set_ylabel(f"Effect of rain from {CONTRAST} on that day (pp)")
    a1.set_title("Effect of rain by lag: concentrated on the same and previous day", loc="left", fontsize=10.5, fontweight="bold")
    a1.set_xticks(range(0, int(past.k.max()) + 1, 2))
    tl = tt[tt.test.str.startswith("lags 1-")]
    if len(tl): a1.text(0.97, 0.96, f"lags 1-14 jointly zero: {fmt_p(tl.iloc[0].p)}", transform=a1.transAxes, ha="right", va="top", fontsize=9, color=INK2)
    a2.errorbar(range(len(fut)), fut.coef * PP, yerr=[(fut.coef - fut.lo) * PP, (fut.hi - fut.coef) * PP], fmt="o",
                color=GRAY, ms=6, mec="white", mew=1, elinewidth=1.8, capsize=0)
    a2.axhline(0, color=MUTED, lw=0.8)
    a2.set_xticks(range(len(fut))); a2.set_xticklabels([f"+{k} d" for k in fut.k]); a2.set_xlim(-0.6, len(fut) - 0.4)
    a2.set_ylim(a1.get_ylim())
    a2.set_xlabel("FUTURE rain (days after the outcome day)"); a2.set_ylabel("Effect (pp)")
    a2.set_title("Placebo: future rain", loc="left", fontsize=10.5, fontweight="bold")
    pl = tt[tt.test.str.startswith("PLACEBO")]
    if len(pl): a2.text(0.97, 0.96, f"joint test, {fmt_p(pl.iloc[0].p)}", transform=a2.transAxes, ha="right", va="top", fontsize=9, color=INK2)
    fig.tight_layout(); save(fig, "rain_lag_placebo.png")


# ---------------------------------------------------------------- Fig RS1 (supplement)
def plot_runs():
    r = pd.read_csv(p("rain_run_length.csv"))
    tests = pd.read_csv(p("rain_run_tests.csv"))
    names = {"wet_1mm": "Wet day: rain >= 1 mm", "wet_10mm": "Heavy-rain day: rain >= 10 mm"}
    defs = [d for d in names if d in r["def"].unique()]
    fig, axs = plt.subplots(1, len(defs), figsize=(5.6 * len(defs), 4.6), sharey=True)
    axs = np.atleast_1d(axs)
    for ax, d in zip(axs, defs):
        for off, ver, col, lab in ((-0.12, "total", GRAY, "total (includes today's rain intensity)"),
                                   (0.12, "net_of_today_intensity", BLUE, "net of today's rain intensity")):
            s = r[(r["def"] == d) & (r.version == ver)]
            x = np.arange(len(s))
            ax.errorbar(x + off, s.coef * PP, yerr=[(s.coef - s.lo) * PP, (s.hi - s.coef) * PP], fmt="o", color=col,
                        ms=6, mec="white", mew=1, elinewidth=1.8, capsize=0, label=lab)
        ax.axhline(0, color=MUTED, lw=0.8); ax.set_xticks(x); ax.set_xticklabels(s.label)
        ax.set_xlabel("Consecutive wet days so far"); ax.set_title(names[d], fontsize=10, loc="left")
        pt = tests[(tests["def"] == d) & (tests.version == "total")]
        if len(pt): ax.text(0.03, 0.03, f"persistence test (total), {fmt_p(pt.iloc[0].p)}", transform=ax.transAxes, fontsize=8.5, color=INK2)
    axs[0].set_ylabel("Blackout vs a non-wet day (pp)")
    axs[0].legend(loc="upper left", fontsize=8.5)
    fig.suptitle("Fig RS1. Blackout by length of the current wet-day streak (descriptive; streaks differ in rain intensity)",
                 fontsize=10, x=0.01, ha="left")
    fig.tight_layout(); save(fig, "rain_run_length.png")


def print_tests():
    for f, t in (("rain_window_diff_tests.csv", "window-difference tests"),
                 ("rain_DL_tests.csv", "distributed-lag tests"),
                 ("rain_run_tests.csv", "run-length tests"), ("rain_sample_log.csv", "sample")):
        print(f"\n== {t} =="); print(pd.read_csv(p(f)).to_string(index=False))


if __name__ == "__main__":
    plot_window(); plot_het(); plot_lag_placebo(); plot_runs(); print_tests()
    print(f"\nFigures saved to {OUTPUT_DIR}")
