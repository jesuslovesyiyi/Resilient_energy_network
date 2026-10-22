"""
run_all_models.py
=================
Runs the whole analysis on the full dataset, in the right order, from any folder. Every step is one of the compute
scripts in this folder; each writes its CSVs to OUTPUT_DIR (set once in compute_main_model.py). Then run
plot_paper_figures.py to draw the figures.

STEPS (in order)
  main         compute_main_model.py              chronic lag windows and the flag-based model (robustness version)
  percentile   compute_percentile_model.py        MAIN MODEL: same-day percentile splines + chronic windows, exceedance and bins
  irf          compute_irf.py                     impulse response functions (distributed lags, event studies, by threshold and zone)
  variance     compute_variance_decomposition.py  within-R2 and Shapley shares
  interaction  compute_interaction_model.py       chronic state x acute shock, twelve pairs
  robustness   check_interaction_robustness.py    placebo, seasonal, zone and permutation checks for three candidate pairs
  confirm      compute_dry_heat_confirmation.py   station halves, leave-one-year-out and multiplicity for dry spell -> heat
  forest       compute_forest_interaction.py      forest cover x wind (rain and heat as placebos)
  knots        compute_knot_sensitivity.py        spline-knot sensitivity
`confirm` needs the CSV of `interaction`, so it runs after it.

USAGE
  python run_all_models.py                     run every step whose output is missing
  python run_all_models.py --force             rerun every step
  python run_all_models.py --only percentile irf
  python run_all_models.py --skip knots forest
  python run_all_models.py --list              show the steps and whether their output exists
  python run_all_models.py --keep-going        continue with the next step if one fails

Each step reads the hourly data (about 7 million rows), so a full run takes a long time (the interaction, robustness and
confirmation steps are the slowest; run them overnight). The numbers quoted in the Methods drafts came from runs by Claude
in a sandbox, not from your machine: rerun everything here before filling the red placeholders.
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compute_main_model as cm  # only for OUTPUT_DIR

STEPS = [
    ("main", "compute_main_model.py", "main_quantities.csv"),
    ("percentile", "compute_percentile_model.py", "pct_spline_curve.csv"),
    ("irf", "compute_irf.py", "irf_dl.csv"),
    ("variance", "compute_variance_decomposition.py", "vd_shapley.csv"),
    ("interaction", "compute_interaction_model.py", "interaction_results.csv"),
    ("robustness", "check_interaction_robustness.py", "interaction_robustness.csv"),
    ("confirm", "compute_dry_heat_confirmation.py", "dry_heat_confirmation.csv"),
    ("forest", "compute_forest_interaction.py", "forest_interaction_results.csv"),
    ("knots", "compute_knot_sensitivity.py", "knot_sensitivity_curves.csv"),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="+", choices=[s[0] for s in STEPS])
    ap.add_argument("--skip", nargs="+", choices=[s[0] for s in STEPS], default=[])
    ap.add_argument("--force", action="store_true", help="rerun steps whose output already exists")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--keep-going", action="store_true")
    a = ap.parse_args()

    out = cm.OUTPUT_DIR
    if a.list:
        print("OUTPUT_DIR:", out)
        for name, script, marker in STEPS:
            print(f"  {name:12s} {script:36s} {'done' if os.path.exists(os.path.join(out, marker)) else 'missing'}")
        return
    todo = [s for s in STEPS if (not a.only or s[0] in a.only) and s[0] not in a.skip]
    failed = []
    t_all = time.time()
    for name, script, marker in todo:
        if os.path.exists(os.path.join(out, marker)) and not a.force:
            print(f"[{name}] output exists ({marker}); skipping (use --force to rerun)")
            continue
        print(f"\n[{name}] running {script} ...", flush=True)
        t0 = time.time()
        rc = subprocess.call([sys.executable, os.path.join(HERE, script)], cwd=HERE)
        print(f"[{name}] {'finished' if rc == 0 else 'FAILED (exit %d)' % rc} in {(time.time() - t0) / 60:.1f} min", flush=True)
        if rc != 0:
            failed.append(name)
            if not a.keep_going:
                break
    print(f"\nAll done in {(time.time() - t_all) / 60:.1f} min. Failed steps: {failed or 'none'}. Results: {out}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
