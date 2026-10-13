"""
make_plots.py
=============
Reads the CSVs written by compute_results.py and draws every figure.
No data loading, no model fitting -- runs in seconds. Edit freely for
cosmetics (colors, titles, axis limits, annotations) and rerun as many
times as you like without touching compute_results.py.

To predict Stage B at a DIFFERENT temperature range (not just restyle
the existing curve), you need the cached model, not just this script --
see repredict_stage_b() at the bottom.
"""

import os
import pickle
import numpy as np
import pandas as pd
import patsy
from scipy.special import expit
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUTPUT_DIR = "/Users/yiyi/Library/CloudStorage/OneDrive-GeorgiaInstituteofTechnology/Research/Energy_resilience/01_data/processed/temp_threshold"


def p(name):
    return os.path.join(OUTPUT_DIR, name)


# ----------------------------------------------------------------------
def plot_stage_a(out_path=None):
    r = pd.read_csv(p("stage_a_binned_result.csv"))
    out_path = out_path or p("stage_a_curve.png")

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(r["t2m_bin_c"], r["mean_pct_blackout"], color="#c0392b", lw=2, marker="o", ms=4)
    ax.fill_between(r["t2m_bin_c"], r["ci_lo"], r["ci_hi"], color="#c0392b", alpha=0.15,
                     label="95% CI (station-clustered bootstrap)")
    ax.set_xlabel("Temperature (°C)")
    ax.set_ylabel("Mean pct_blackout")
    ax.set_title("Stage A: Raw exposure-response curve (unadjusted)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return r


def _steepest_t(r):
    deriv = np.gradient(r["pred"], r["t2m_c"])
    mask = (r["t2m_c"] > 15) & (r["t2m_c"] < 40)
    return float(r["t2m_c"][mask].iloc[deriv[mask].argmax()]) if mask.any() else None


def plot_stage_b(out_path=None):
    r = pd.read_csv(p("stage_b_predicted_curve.csv"))
    out_path = out_path or p("stage_b_curve.png")
    steepest_t = _steepest_t(r)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(r["t2m_c"], r["pred"], color="#2c3e50", lw=2)
    ax.fill_between(r["t2m_c"], r["lo"], r["hi"], color="#2c3e50", alpha=0.15, label="95% CI (cluster-robust)")
    if steepest_t is not None:
        ax.axvline(steepest_t, color="#c0392b", ls="--", lw=1, label=f"Steepest slope ≈ {steepest_t:.1f}°C")
    ax.set_xlabel("Temperature (°C)")
    ax.set_ylabel("Adjusted predicted pct_blackout")
    ax.set_title("Stage B: Model-adjusted exposure-response curve\n(controlling for precip, wind, month, climate zone)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return r, steepest_t


def plot_stage_b_with_counts(stage_b, stage_a, steepest_t, out_path=None):
    out_path = out_path or p("stage_b_with_counts.png")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 7.5), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    ax1.plot(stage_b["t2m_c"], stage_b["pred"], color="#2c3e50", lw=2)
    ax1.fill_between(stage_b["t2m_c"], stage_b["lo"], stage_b["hi"], color="#2c3e50", alpha=0.15,
                      label="95% CI (cluster-robust)")
    if steepest_t is not None:
        ax1.axvline(steepest_t, color="#c0392b", ls="--", lw=1, label=f"Steepest slope ≈ {steepest_t:.1f}°C")
    ax1.set_ylabel("Adjusted predicted pct_blackout")
    ax1.set_title("Model-adjusted exposure-response curve, with sample size")
    ax1.legend()
    ax1.grid(alpha=0.3)

    ax2.bar(stage_a["t2m_bin_c"], stage_a["n_station_hours"], width=1.8, color="#7f8c8d")
    ax2.set_yscale("log")
    ax2.set_xlabel("Temperature (°C)")
    ax2.set_ylabel("Station-hours\n(log scale)")
    ax2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_stage_c(out_path=None):
    out_path = out_path or p("stage_c_by_zone.png")
    fig, ax = plt.subplots(figsize=(9.5, 6))
    for fname in sorted(os.listdir(OUTPUT_DIR)):
        if fname.startswith("stage_c_") and fname.endswith(".csv"):
            zone = fname.replace("stage_c_", "").replace(".csv", "")
            r = pd.read_csv(p(fname))
            line, = ax.plot(r["t2m_c"], r["pred"], lw=2, label=zone)
            ax.fill_between(r["t2m_c"], r["lo"], r["hi"], color=line.get_color(), alpha=0.1)
    ax.set_xlabel("Temperature (°C)")
    ax.set_ylabel("Adjusted predicted pct_blackout")
    ax.set_title("Exposure-response curve by climate zone\n(controlling for precip, wind, month)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_coef_table(out_path=None, exclude_prefixes=("Month",)):
    """Forest plot (coefficient + 95% CI) of the Stage B regression table --
    a standard supplementary figure. Month dummies are excluded by default
    since there are 11 of them and they're a seasonal control, not part of
    the main story; pass exclude_prefixes=() to include everything."""
    path_csv = p("stage_b_coefficient_table.csv")
    if not os.path.exists(path_csv):
        print(f"  Skipping coefficient plot: {path_csv} not found "
              "(run compute_results.py with stage_b_coef_table() first).")
        return
    out_path = out_path or p("stage_b_coef_forest_plot.png")

    tbl = pd.read_csv(path_csv)
    tbl = tbl[tbl["label"] != "Intercept"]
    for prefix in exclude_prefixes:
        tbl = tbl[~tbl["label"].str.startswith(prefix)]
    tbl = tbl.iloc[::-1].reset_index(drop=True)  # flip so first row plots at top

    fig, ax = plt.subplots(figsize=(8, max(3, 0.4 * len(tbl))))
    y_pos = np.arange(len(tbl))
    for i, row in tbl.iterrows():
        color = "#c0392b" if row["p_value"] < 0.05 else "#95a5a6"
        xerr = [[row["coef"] - row["ci_lower"]], [row["ci_upper"] - row["coef"]]]
        ax.errorbar(row["coef"], y_pos[i], xerr=xerr, fmt="o", ecolor=color, color="#2c3e50", ms=5, capsize=3)
    ax.axvline(0, color="black", lw=0.8, ls="--")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(tbl["label"])
    ax.set_xlabel("Coefficient (log-odds scale) with 95% CI")
    ax.set_title("Stage B regression coefficients\n(red = p<0.05, grey = not significant)")
    ax.grid(alpha=0.3, axis="x")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def print_supplementary_stats():
    """Print the zone-interaction test and model meta info to console --
    not a plot, but useful to have alongside the figures when writing
    up results."""
    interact_path = p("stage_b_zone_interaction_test.csv")
    if os.path.exists(interact_path):
        r = pd.read_csv(interact_path).iloc[0]
        print(f"  Zone interaction LR test: stat={r['lr_stat']:.2f}, df={r['df']:.0f}, p={r['p_value']:.3g}")
    else:
        print(f"  (no {interact_path} found yet)")

    meta_path = p("stage_b_model_meta.csv")
    if os.path.exists(meta_path):
        m = pd.read_csv(meta_path).iloc[0]
        print(f"  Stage B model: N={int(m['n_obs']):,}, stations={int(m['n_stations_clustered'])}, "
              f"pseudo R-sq={m['pseudo_r_sq_deviance']:.4f}")
    else:
        print(f"  (no {meta_path} found yet)")


# ----------------------------------------------------------------------
# OPTIONAL: re-predict Stage B at a DIFFERENT temperature range using the
# cached model (stage_b_model.pkl) -- no refit, but needs that file to
# exist (written by compute_results.py). Overwrites stage_b_predicted_curve.csv
# and stage_b_curve.png with the new range. Call this BEFORE plot_stage_b()
# in __main__ if you want a custom range; otherwise it's skipped.
# ----------------------------------------------------------------------
def repredict_stage_b(t_min, t_max, step=0.5):
    model_path = p("stage_b_model.pkl")
    if not os.path.exists(model_path):
        print(f"  Skipping custom range: {model_path} not found "
              "(run compute_results.py with the model-caching version first).")
        return
    with open(model_path, "rb") as f:
        cached = pickle.load(f)
    params, cov_params = cached["params"], cached["cov_params"]

    # Rebuild design_info by rerunning patsy on the SAME training sample used
    # to fit the model -- this is cheap matrix construction, not a refit, and
    # reproduces the exact same spline knots since it's the identical data.
    df_fit = pd.read_parquet(cached["fit_sample_path"])
    _, X = patsy.dmatrices(f"pct_blackout ~ {cached['formula_rhs']}", df_fit, return_type="dataframe")

    t_grid = np.arange(t_min, t_max, step)
    pred_df = pd.DataFrame({
        "t2m_c": t_grid,
        "tp": cached["precip_median"],
        "wind_speed": cached["wind_median"],
        "month": 6,
        "climate_zone_code": pd.Categorical([cached["modal_zone"]] * len(t_grid),
                                             categories=cached["zone_categories"]),
    })
    Xp = np.asarray(patsy.build_design_matrices([X.design_info], pred_df)[0])
    eta = Xp @ params.values
    se_eta = np.sqrt(np.einsum("ij,jk,ik->i", Xp, cov_params.values, Xp))
    pred, lo, hi = expit(eta), expit(eta - 1.96 * se_eta), expit(eta + 1.96 * se_eta)

    out = pd.DataFrame({"t2m_c": t_grid, "pred": pred, "lo": lo, "hi": hi})
    out.to_csv(p("stage_b_predicted_curve.csv"), index=False)
    print(f"  Re-predicted Stage B over {t_min}C to {t_max}C "
          "(values far outside the original fit range are extrapolation -- treat with caution).")


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # --- Uncomment and edit this line to use a custom temperature range for Stage B ---
    # repredict_stage_b(t_min=-5, t_max=45)

    stage_a = plot_stage_a()
    stage_b, steepest_t = plot_stage_b()
    plot_stage_b_with_counts(stage_b, stage_a, steepest_t)
    plot_stage_c()
    plot_coef_table()

    print("\n--- Supplementary stats (not plots, for your results text) ---")
    print_supplementary_stats()

    print("\nDone. Plots written to:", OUTPUT_DIR)
