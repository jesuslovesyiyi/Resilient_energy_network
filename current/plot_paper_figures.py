"""
plot_paper_figures.py
=====================
Draws every figure of the paper from the result CSVs and gathers them, numbered, in one folder:
    <OUTPUT_DIR>/paper_figures/main/   main-text figures  (Fig1, Fig2, ...)
    <OUTPUT_DIR>/paper_figures/si/     supplementary figures (FigS1, FigS2, ...)
    <OUTPUT_DIR>/paper_figures/figure_index.csv   number, file, what it shows
Run run_all_models.py first (the figures only read CSVs). Each figure is saved as PNG (600 dpi) and PDF.

HOW IT WORKS  It runs the plot_*.py scripts of this folder (each draws its own set into a subfolder of OUTPUT_DIR), then
copies the chosen figures under their paper numbers. Edit MAIN and SUPPLEMENT below to change what is main text and what is
SI: each entry is (paper number, subfolder, figure name, what it shows). Fig. S1 and S2 match the references in the Methods.

USAGE   python plot_paper_figures.py              redraw everything, then gather
        python plot_paper_figures.py --no-replot  only gather figures already drawn
        python plot_paper_figures.py --only main  gather the main-text set only (or: si)
"""
import argparse
import csv
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compute_main_model as cm  # only for OUTPUT_DIR

PLOT_SCRIPTS = ["plot_main_model.py", "plot_percentile_model.py", "plot_irf.py", "plot_variance_decomposition.py",
                "plot_interaction_model.py", "plot_forest_interaction.py", "plot_knot_sensitivity.py", "plot_dry_heat.py"]

# (number, subfolder of OUTPUT_DIR, figure file name without extension, what it shows)
MAIN = [
    ("Fig1", "figures_percentile", "pfig1_spline", "Same-day dose-response: change in outage probability by within-zone percentile (temperature, rain, wind; outages >= 1, 6, 12 h)"),
    ("Fig2", "figures", "fig1_chronic_profile", "Chronic profile: effect of the mean weather in each lag window (1 to 179 days before)"),
    ("Fig3", "figures_irf", "ifig5_by_percentile", "Timing: same-day, next-day and cumulative response across percentile thresholds"),
]
SUPPLEMENT = [
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


def replot():
    for s in PLOT_SCRIPTS:
        print(f"drawing with {s} ...", flush=True)
        rc = subprocess.call([sys.executable, os.path.join(HERE, s)], cwd=HERE)
        if rc != 0:
            print(f"  WARNING: {s} exited with code {rc}; figures from it may be missing or old")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-replot", action="store_true")
    ap.add_argument("--only", choices=["main", "si"])
    a = ap.parse_args()
    if not a.no_replot:
        replot()
    root = os.path.join(cm.OUTPUT_DIR, "paper_figures")
    rows, missing = [], []
    for label, entries, sub in (("main", MAIN, "main"), ("si", SUPPLEMENT, "si")):
        if a.only and a.only != label:
            continue
        os.makedirs(os.path.join(root, sub), exist_ok=True)
        for num, folder, name, what in entries:
            found = False
            for ext in ("png", "pdf"):
                src = os.path.join(cm.OUTPUT_DIR, folder, f"{name}.{ext}")
                if os.path.exists(src):
                    shutil.copyfile(src, os.path.join(root, sub, f"{num}_{name}.{ext}"))
                    found = True
            (rows if found else missing).append((num, f"{num}_{name}", folder + "/" + name, what) if found else (num, folder + "/" + name))
    with open(os.path.join(root, "figure_index.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["number", "file", "source", "what it shows"]); w.writerows(rows)
    print(f"\n{len(rows)} figures gathered in {root}")
    if missing:
        print("Missing (run run_all_models.py and the plot step first):")
        for m in missing:
            print("  ", m[0], m[1])


if __name__ == "__main__":
    main()
