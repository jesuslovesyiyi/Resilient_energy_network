"""
plot_chronic_heat.py
====================
Reads the CSVs written by compute_chronic_heat.py and draws:

  MAIN TEXT
  chronic_window_curve.png         Fig 1: effect of +1C on the k-day mean of daily max temperature
                                   (specs a/b/c). The headline result.
  chronic_heterogeneity.png        Fig 2: 1-day vs 14-day effect by season and climate zone.
  chronic_cumulative_placebo.png   Fig 3: (left) cumulative effect over the past k days,
                                   (right) placebo: FUTURE temperatures should show no effect.

  SUPPLEMENT
  chronic_run_length.png           Fig S1: blackout vs length of the current hot-day streak (descriptive).

No fitting happens here. Edit styling and rerun.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "Library/CloudStorage/OneDrive-GeorgiaInstituteofTechnology/Research/Energy_resilience/01_data/processed", "temp_threshold")
FE = "station_month"          # main fixed-effects spec (use "station" for the robustness version)
PP = 100.0                    # coefficients are fractions -> percentage points
DPI = 600                     # PNG resolution (journals ask for 300-600). A vector PDF is also saved for each figure.

# palette (validated reference instance) and ink colors
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
    fig.savefig(p(name.replace(".png", ".pdf")), bbox_inches="tight", facecolor="white")  # vector, infinitely sharp
    plt.close(fig)


# ---------------------------------------------------------------- Fig 1
def plot_window():
    d = pd.read_csv(p("chronic_window_effects.csv")); d = d[d.fe == FE]
    t = pd.read_csv(p("chronic_window_diff_tests.csv"))
    specs = [("a_main_controls", GRAY, "Main controls", 1.6),
             ("b_plus_window_rain", BLUE, "+ rain over the window", 1.6),
             ("c_dry_windows_only", ORANGE, "Dry windows only (< 0.5 mm in total)", 2.4)]
    fig, ax = plt.subplots(figsize=(8.5, 5.4))
    for v, c, lab, lw in specs:
        s = d[d.variant == v].sort_values("window_days")
        if s.empty: continue
        ax.fill_between(s.window_days, s.lo * PP, s.hi * PP, color=c, alpha=0.13, lw=0)
        ax.plot(s.window_days, s.coef * PP, "-o", color=c, lw=lw, ms=5, mec="white", mew=1.2, label=lab)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xscale("log")
    ks = sorted(d.window_days.unique()); ax.set_xticks(ks); ax.set_xticklabels(ks); ax.minorticks_off()
    ax.set_xlabel("Heat window: number of days averaged (mean of daily maximum temperature)")
    ax.set_ylabel("Effect of +1 °C on daily blackout (percentage points)")
    ax.set_title("Heat sustained over days is associated with more blackout than one hot day,\n"
                 "but the build-up disappears in dry windows", loc="left", fontsize=11, fontweight="bold")
    a = t[(t.variant == "a_main_controls") & t.comparison.str.startswith("14")]
    if len(a):
        r = a.iloc[0]
        ax.text(0.015, 0.985, f"14-day minus 1-day (main controls): {r['diff']*PP:+.2f} pp per °C, {fmt_p(r['p'])}",
                transform=ax.transAxes, va="top", fontsize=9, color=INK2)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=3, fontsize=9, handlelength=1.6)
    ax.text(0.0, -0.30, "Bands: 95% CI, clustered by station. Station × calendar-month and year fixed effects.",
            transform=ax.transAxes, fontsize=8, color=MUTED)
    fig.tight_layout(); save(fig, "chronic_window_curve.png")


# ---------------------------------------------------------------- Fig 2
def plot_het():
    h = pd.read_csv(p("chronic_heterogeneity.csv")); h = h[h.group_type != "all"]
    rows, y, ypos = [], 0.0, {}
    for gt, title in (("season", "SEASON"), ("climate zone", "CLIMATE ZONE (Köppen)")):
        g = h[h.group_type == gt]
        rows.append(("header", title, y)); y += 0.8
        for grp in list(dict.fromkeys(g.group)):
            n = g[(g.group == grp) & (g.window_days == 14)].n_stations
            lab = f"{grp}  (n = {int(n.iloc[0])} stations)" if len(n) else grp
            rows.append(("row", (gt, grp, lab), y)); ypos[(gt, grp)] = y; y += 1.0
        y += 0.3
    fig, ax = plt.subplots(figsize=(8.8, 0.46 * y + 1.8))
    for kind, val, yy in rows:
        if kind == "header":
            ax.text(-0.02, yy, val, transform=ax.get_yaxis_transform(), ha="right", va="center",
                    fontsize=8.5, color=INK2, fontweight="bold")
    for off, k, col, lab in ((-0.17, 1, GRAY, "1-day window"), (0.17, 14, ORANGE, "14-day window")):
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
    ax.set_xlabel("Effect of +1 °C on daily blackout (percentage points)")
    ax.set_title("The extra effect of sustained heat is concentrated in the pre-monsoon season",
                 loc="left", fontsize=11, fontweight="bold", pad=12)
    ax.legend(loc="lower right", fontsize=9)
    fig.tight_layout(); save(fig, "chronic_heterogeneity.png")


# ---------------------------------------------------------------- Fig 3
def plot_cum_placebo():
    c = pd.read_csv(p("chronic_DL_cumulative.csv")); c = c[(c.fe == FE) & (c.through_lag >= 1)].sort_values("through_lag")
    l = pd.read_csv(p("chronic_DL_lags.csv")); l = l[(l.fe == FE) & l.term.str.startswith("t_f")].copy()
    l["lag_days"] = -l.term.str[-1].astype(int)   # t_f1 = tomorrow = -1 (older CSVs mislabelled this)
    l = l.sort_values("lag_days", ascending=False)
    tt = pd.read_csv(p("chronic_DL_tests.csv")); tt = tt[tt.fe == FE]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 4.6), gridspec_kw={"width_ratios": [1.5, 1]})
    a1.fill_between(c.through_lag, c.lo * PP, c.hi * PP, color=ORANGE, alpha=0.15, lw=0)
    a1.plot(c.through_lag, c.cumulative_coef * PP, "-o", color=ORANGE, lw=2.2, ms=5, mec="white", mew=1.2)
    a1.axhline(0, color=MUTED, lw=0.8)
    a1.set_xlabel("Window length: today plus the previous k days of temperature")
    a1.set_ylabel("Effect of a sustained +1 °C (pp)")
    a1.set_title("Cumulative effect grows with the days of heat included", loc="left", fontsize=10.5, fontweight="bold")
    a2.errorbar(range(len(l)), l.coef * PP, yerr=[(l.coef - l.lo) * PP, (l.hi - l.coef) * PP], fmt="o",
                color=GRAY, ms=6, mec="white", mew=1, elinewidth=1.8, capsize=0)
    a2.axhline(0, color=MUTED, lw=0.8)
    a2.set_xticks(range(len(l))); a2.set_xticklabels([f"+{abs(int(k))} d" for k in l.lag_days]); a2.set_xlim(-0.6, len(l) - 0.4)
    a2.set_xlabel("FUTURE temperature (days after the outcome day)")
    a2.set_ylabel("Effect of +1 °C (pp)")
    a2.set_title("Placebo: future heat should not matter", loc="left", fontsize=10.5, fontweight="bold")
    pl = tt[tt.test.str.startswith("PLACEBO")]
    if len(pl):
        a2.text(0.03, 0.96, f"joint test, {fmt_p(pl.iloc[0].p)}", transform=a2.transAxes, ha="left", va="top", fontsize=9, color=INK2)
    fig.tight_layout(); save(fig, "chronic_cumulative_placebo.png")


# ---------------------------------------------------------------- Fig S1 (supplement)
def plot_runs():
    r = pd.read_csv(p("chronic_run_length.csv")); r = r[r.version == "total"]
    tests = pd.read_csv(p("chronic_run_tests.csv")); tests = tests[tests.version == "total"]
    names = {"rel_p90": "Hottest 10% of days\nfor that station and season",
             "abs_38": "Daily max ≥ 38 °C", "abs_40": "Daily max ≥ 40 °C"}
    defs = [d for d in names if d in r["def"].unique()]
    fig, axs = plt.subplots(1, len(defs), figsize=(4.6 * len(defs), 4.6), sharey=True)
    axs = np.atleast_1d(axs)
    for ax, d in zip(axs, defs):
        s = r[r["def"] == d]; x = np.arange(len(s))
        ax.errorbar(x, s.coef * PP, yerr=[(s.coef - s.lo) * PP, (s.hi - s.coef) * PP], fmt="o", color=ORANGE,
                    ms=6, mec="white", mew=1, elinewidth=1.8, capsize=0)
        ax.axhline(0, color=MUTED, lw=0.8); ax.set_xticks(x); ax.set_xticklabels(s.label)
        ax.set_xlabel("Consecutive hot days so far"); ax.set_title(names[d], fontsize=10, loc="left")
        pt = tests[tests["def"] == d]
        if len(pt): ax.text(0.03, 0.03, f"persistence test, {fmt_p(pt.iloc[0].p)}", transform=ax.transAxes, fontsize=8.5, color=INK2)
    axs[0].set_ylabel("Blackout vs a non-hot day (pp)")
    fig.suptitle("Fig S1. Blackout by length of the current hot-day streak (descriptive; streak membership differs across stations)",
                 fontsize=10, x=0.01, ha="left")
    fig.tight_layout(); save(fig, "chronic_run_length.png")


def print_tests():
    for f, t in (("chronic_window_diff_tests.csv", "window-difference tests"),
                 ("chronic_DL_tests.csv", "distributed-lag tests"),
                 ("chronic_run_tests.csv", "run-length tests"), ("chronic_sample_log.csv", "sample")):
        print(f"\n== {t} =="); print(pd.read_csv(p(f)).to_string(index=False))


if __name__ == "__main__":
    plot_window(); plot_het(); plot_cum_placebo(); plot_runs(); print_tests()
    print(f"\nFigures saved to {OUTPUT_DIR}")
