"""Budget-vs-outcome plots for the CookingWorld flash-lite ablation.

Reconstructs per-step cumulative curves straight from each eval log's
`trajectory_telemetry` (the same source cooking_rubric.py scores), averages them
across the 10 seeds per config, and renders two figures:

  Plot A  budget (cumulative steps, log x)  vs  mean cumulative game score
  Plot B  budget (cumulative steps, log x)  vs  mean cumulative ALE  (+ drift
          overlay when the drift judge produced values)

Budget axis: per-step token counts are NOT recorded in these logs (only a
per-transcript total in `sample.model_usage`), so we use cumulative *steps* as
the budget proxy and annotate each config's mean total tokens in the legend.
Reference: long-horizon-scaling .../plot_ale_over_time.py (cum ALE vs step).

    .venv-inspect/bin/python scout_report/plots.py \
        [flash_lite_eval_20260627_09354] [scout_report/plots_out]
"""
import glob
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from inspect_ai.log import read_eval_log

from cooking_rubric import calculate_ale

CONFIGS = ["baseline-m5", "m3-m5", "m7-m5", "m5-m6", "m3-m5-m6", "m7-m5-m6"]
# human-readable harness names (all configs include M5 valid-move templating,
# so it's the shared base; labels name the harness(es) added on top).
LABELS = {
    "baseline-m5": "Baseline (M5 only)",
    "m3-m5": "+ State externalization (M3)",
    "m7-m5": "+ World model (M7)",
    "m5-m6": "+ Planning (M6)",
    "m3-m5-m6": "+ Planning + State (M6+M3)",
    "m7-m5-m6": "+ Planning + World model (M6+M7)",
}
LEGEND_TITLE = "Harness (all include M5 valid-move list)"
# The logs store only run-wide token totals, not per-step tokens, so the x-axis is
# turns, not compute. Labelled explicitly as a proxy (see REVIEW_RESPONSE.md #1).
XLABEL = "cumulative turns (log) — proxy for effort, NOT tokens"
# colorblind-safe categorical palette (Wong 2011), one hue per config
COLORS = {
    "baseline-m5": "#0072B2", "m3-m5": "#009E73", "m7-m5": "#56B4E9",
    "m5-m6": "#E69F00", "m3-m5-m6": "#D55E00", "m7-m5-m6": "#CC79A7",
}
MIN_RUNS = 3   # stop a config's curve once fewer than this many seeds remain


def _config(name: str) -> str:
    for c in sorted(CONFIGS, key=len, reverse=True):
        if c in name:
            return c
    return "?"


def _total_tokens(sample) -> int:
    usage = getattr(sample, "model_usage", None) or {}
    return sum(u.total_tokens for u in usage.values())


def load_curves(log_dir: str) -> dict:
    """config -> list of per-run dicts {cum_score[], cum_ale[], tokens}."""
    runs: dict[str, list] = {c: [] for c in CONFIGS}
    for f in sorted(glob.glob(f"{log_dir}/*.eval")):
        log = read_eval_log(f)
        cfg = _config(os.path.basename(f))
        for s in log.samples or []:
            tele = (s.metadata or {}).get("trajectory_telemetry") or []
            if not tele:
                continue
            cum_score, cum_ale, cum_items = [], [], []
            score = ale = items = 0.0
            for step in tele:
                score += step.get("reward", 0.0) or 0.0
                for pr in step.get("probe_results", []):
                    if pr.get("probe") == "ale":
                        gt = (pr.get("metadata") or {}).get("ground_truth", []) or []
                        ale += calculate_ale(pr.get("completion", ""), gt)
                        items += len(gt)   # ground-truth items queried = denominator
                cum_score.append(score)
                cum_ale.append(ale)
                cum_items.append(items)
            runs.setdefault(cfg, []).append(
                {"cum_score": np.array(cum_score),
                 "cum_ale": np.array(cum_ale),
                 "cum_items": np.array(cum_items),
                 "steps": len(tele),
                 "tokens": _total_tokens(s)})
    return runs


def latest_scan(scans_root: str = "scout_report/scans") -> str | None:
    """Most recently written rubric scan dir (holds drift_events), or None."""
    dirs = glob.glob(f"{scans_root}/scan_id=*")
    return max(dirs, key=os.path.getmtime) if dirs else None


def load_drift_curves(scan_dir: str) -> dict:
    """config -> list of per-run cumulative-drift arrays, from the scan parquet.

    Drift is judged at a few sampled probe steps (drift_events = [[step, 0/1]]);
    we spread each verdict forward to build a per-step cumulative curve, so drift
    can be drawn on the same horizon axis as the deterministic channels.
    """
    import pandas as pd
    df = pd.read_parquet(f"{scan_dir}/cooking_rubric.parquet")
    runs: dict[str, list] = {c: [] for c in CONFIGS}
    for _, row in df.iterrows():
        cfg = _config(str(row.get("transcript_source_uri", "")))
        if cfg not in runs:
            continue
        meta = row.get("metadata")
        meta = json.loads(meta) if isinstance(meta, str) else (meta or {})
        steps = int(meta.get("steps") or 0)
        events = meta.get("drift_events")
        events = json.loads(events) if isinstance(events, str) else (events or [])
        if steps <= 0:
            continue
        cum = np.zeros(steps)
        for s, v in events:
            if 0 <= s < steps:
                cum[s:] += v
        runs[cfg].append({"cum_drift": cum})
    return runs


def _mean_curve(run_arrays: list, key: str, min_runs: int = MIN_RUNS):
    """Mean over runs at each step index, truncated where <min_runs remain."""
    if not run_arrays:
        return np.array([]), np.array([])
    max_len = max(len(r[key]) for r in run_arrays)
    xs, ys = [], []
    for t in range(max_len):
        vals = [r[key][t] for r in run_arrays if len(r[key]) > t]
        if len(vals) < min_runs:
            break
        xs.append(t + 1)           # 1-based turn
        ys.append(float(np.mean(vals)))
    return np.array(xs), np.array(ys)


def _style(ax, xlabel, ylabel, title):
    ax.set_xscale("log")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=12, weight="bold")
    ax.grid(True, which="both", alpha=0.25, linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)


def plot_a(runs: dict, out: str):
    fig, ax = plt.subplots(figsize=(8, 5))
    for cfg in CONFIGS:
        if not runs.get(cfg):
            continue
        x, y = _mean_curve(runs[cfg], "cum_score")
        toks = np.mean([r["tokens"] for r in runs[cfg]])
        ax.plot(x, y, color=COLORS[cfg], linewidth=2,
                label=f"{LABELS[cfg]}  (~{toks/1e3:.0f}k tok)")
    _style(ax, XLABEL, "mean cumulative game score", "Plot A — game score vs effort")
    ax.legend(title=f"{LEGEND_TITLE}; ~mean tokens/run", fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_b(runs: dict, out: str):
    """Cumulative memory errors (ALE) vs effort. Drift lives in its own panel
    (plot_c) now — mixing 0-600 ALE and 0-1.4 drift on one twin axis was
    unreadable (review #5)."""
    fig, ax = plt.subplots(figsize=(8, 5))
    for cfg in CONFIGS:
        if not runs.get(cfg):
            continue
        x, y = _mean_curve(runs[cfg], "cum_ale")
        ax.plot(x, y, color=COLORS[cfg], linewidth=2, label=LABELS[cfg])
    _style(ax, XLABEL, "mean cumulative memory errors (ALE)",
           "Plot B — accumulated memory errors vs effort")
    ax.text(0.02, 0.97, "raw cumulative count; see survivorship + normalized "
            "figures for length-controlled views", transform=ax.transAxes,
            fontsize=7.5, va="top", color="#555")
    ax.legend(title=LEGEND_TITLE, fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


SURV_MIN_STEPS = 95   # a run "survived" if it reached ~the 100-turn cap


def plot_survivorship(runs: dict, out: str):
    """Left: how many runs are still alive at each turn (the survivorship the raw
    means hide). Right: memory errors for ONLY the runs that reached the cap, so
    conditions are compared at matched exposure (review #2)."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.5))
    for cfg in CONFIGS:
        rs = runs.get(cfg) or []
        if not rs:
            continue
        maxlen = max(r["steps"] for r in rs)
        xs = np.arange(1, maxlen + 1)
        n_alive = [sum(1 for r in rs if r["steps"] >= t) for t in xs]
        ax1.plot(xs, n_alive, color=COLORS[cfg], linewidth=1.8, label=LABELS[cfg])

        surv = [r for r in rs if r["steps"] >= SURV_MIN_STEPS]
        x, y = _mean_curve(surv, "cum_ale", min_runs=1)
        if len(x):
            ax2.plot(x, y, color=COLORS[cfg], linewidth=1.8,
                     label=f"{LABELS[cfg]} (n={len(surv)})")
    for ax in (ax1, ax2):
        ax.set_xscale("log")
        ax.set_xlabel(XLABEL)
        ax.grid(True, alpha=0.25)
    ax1.set_ylabel("runs still alive (of 10)")
    ax1.set_title("Survivorship — runs alive at each turn", weight="bold")
    ax1.legend(title=LEGEND_TITLE, fontsize=7.5, frameon=False)
    ax2.set_ylabel("mean cumulative memory errors (ALE)")
    ax2.set_title(f"Matched exposure — errors for runs reaching turn {SURV_MIN_STEPS}+",
                  weight="bold")
    ax2.legend(fontsize=7.5, frameon=False)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_normalized(runs: dict, out: str):
    """Length-controlled error views (review #3): (a) errors per turn, and
    (b) errors per ground-truth item the agent was asked about."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.5))
    for cfg in CONFIGS:
        rs = runs.get(cfg) or []
        if not rs:
            continue
        per_turn = [{"v": r["cum_ale"] / np.arange(1, len(r["cum_ale"]) + 1)} for r in rs]
        x, y = _mean_curve(per_turn, "v")
        if len(x):
            ax1.plot(x, y, color=COLORS[cfg], linewidth=1.8, label=LABELS[cfg])
        per_item = [{"v": r["cum_ale"] / np.maximum(r["cum_items"], 1)} for r in rs]
        x2, y2 = _mean_curve(per_item, "v")
        if len(x2):
            ax2.plot(x2, y2, color=COLORS[cfg], linewidth=1.8)
    for ax in (ax1, ax2):
        ax.set_xscale("log")
        ax.set_xlabel(XLABEL)
        ax.grid(True, alpha=0.25)
    ax1.set_ylabel("mean ALE per turn")
    ax1.set_title("(a) Errors per turn", weight="bold")
    ax1.legend(title=LEGEND_TITLE, fontsize=7.5, frameon=False)
    ax2.set_ylabel("mean ALE per ground-truth item queried")
    ax2.set_title("(b) Errors per known-item opportunity", weight="bold")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def main(log_dir: str, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    runs = load_curves(log_dir)
    n = sum(len(v) for v in runs.values())
    a = plot_a(runs, f"{out_dir}/plot_a_score_vs_budget.png")
    b = plot_b(runs, f"{out_dir}/plot_b_errors_vs_budget.png")
    s = plot_survivorship(runs, f"{out_dir}/plot_d_survivorship.png")
    nm = plot_normalized(runs, f"{out_dir}/plot_e_normalized.png")
    print(f"Loaded {n} runs from {log_dir}")
    for cfg in CONFIGS:
        if runs.get(cfg):
            xs, ys = _mean_curve(runs[cfg], "cum_score")
            _, ae = _mean_curve(runs[cfg], "cum_ale")
            print(f"  {cfg:12s} steps~{xs[-1]:3d}  final score~{ys[-1]:.2f}  "
                  f"cum ALE~{ae[-1]:.0f}")
    for p in (a, b, s, nm):
        print(f"wrote {p}")


if __name__ == "__main__":
    log_dir = sys.argv[1] if len(sys.argv) > 1 else "flash_lite_eval_20260627_09354"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "scout_report/plots_out"
    main(log_dir, out_dir)
