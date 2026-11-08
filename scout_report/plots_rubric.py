"""How each failure mode accumulates over the horizon (per rubric channel).

Small-multiples companion to plots.py: instead of only ALE, it reconstructs the
per-step cumulative curve for EVERY deterministic rubric channel and draws one
panel per channel, one line per config. Answers "plot how failure modes
accumulate across the rubric." The drift panel comes from the scan's judged
verdicts only -- at most MAX_DRIFT_JUDGE of a run's probes are judged, and runs
the judge skipped are excluded (not drawn as 0).

    .venv-inspect/bin/python scout_report/plots_rubric.py \
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

import report
from cooking_rubric import (MAX_DRIFT_JUDGE, calculate_ale, _plan_first_action,
                            _action_matches)
from plots import (CONFIGS, COLORS, LABELS, LEGEND_TITLE, MIN_RUNS, XLABEL, _config,
                   _mean_curve, latest_scan)

CHANNELS = [
    ("ale", "Memory errors (ALE)"),
    ("interface", "Rejected commands"),
    ("liveness", "Stuck / repeating"),
    ("integration", "Ignored own plan"),
    ("drift", "Lost the goal (drift)"),
]


# deterministic channels reconstructable from telemetry (drift comes from the scan)
DET_CHANNELS = ["ale", "interface", "liveness", "integration"]


def load_channel_curves(log_dir: str) -> dict:
    """config -> list of per-run dicts, each det. channel -> cumulative np.array."""
    runs: dict[str, list] = {c: [] for c in CONFIGS}
    for f in sorted(glob.glob(f"{log_dir}/*.eval")):
        log = read_eval_log(f)
        cfg = _config(os.path.basename(f))
        for s in log.samples or []:
            tele = (s.metadata or {}).get("trajectory_telemetry") or []
            if not tele:
                continue
            cum = {k: [] for k in DET_CHANNELS}
            ale = interface = liveness = integration = 0
            hist: list[str] = []
            for i, step in enumerate(tele):
                action = (step.get("action_sent") or "").strip()
                valid = step.get("valid_actions") or []
                for pr in step.get("probe_results", []):
                    if pr.get("probe") == "ale":
                        gt = (pr.get("metadata") or {}).get("ground_truth", []) or []
                        ale += calculate_ale(pr.get("completion", ""), gt)
                    elif pr.get("probe") == "integration":
                        planned = _plan_first_action(pr.get("completion", ""))
                        window = [(tele[j].get("action_sent") or "").strip()
                                  for j in range(i, min(i + 4, len(tele)))]
                        if planned and not any(_action_matches(planned, a) for a in window):
                            integration += 1
                if action and valid and action not in valid:
                    interface += 1
                hist.append(action)
                if len(hist) >= 4 and len(set(hist[-4:])) == 1:
                    liveness += 1
                cum["ale"].append(ale)
                cum["interface"].append(interface)
                cum["liveness"].append(liveness)
                cum["integration"].append(integration)
            runs.setdefault(cfg, []).append({k: np.array(v) for k, v in cum.items()})
    return runs


def load_drift_panel(scan_dir: str) -> tuple[dict, str]:
    """config -> cumulative-drift curves for JUDGED runs only, + coverage note.

    `plots.load_drift_curves` keeps every run, but a run whose judge was skipped
    carries no verdicts and would average in as a flat zero line -- reading as
    "no drift" when the truth is "not judged" (review #5). Those runs are
    dropped and reported in the returned note instead.
    """
    df = report.load(scan_dir)
    runs: dict[str, list] = {c: [] for c in CONFIGS}
    for _, row in df.iterrows():
        cfg, steps = row["config"], int(row["steps"] or 0)
        # drift_judged is NaN when the judge was skipped and 0 when the run
        # fired no drift probes -- neither carries a verdict to plot.
        if cfg not in runs or steps <= 0 or not row["drift_judged"] > 0:
            continue
        events = report._md(row["metadata"], "drift_events", "[]")
        events = json.loads(events) if isinstance(events, str) else (events or [])
        cum = np.zeros(steps)
        for s, v in events:                    # spread each verdict forward
            if 0 <= s < steps:
                cum[s:] += v
        runs[cfg].append({"cum_drift": cum})
    n_runs = sum(len(v) for v in runs.values())
    n_judged, n_probes = int(df["drift_judged"].sum()), int(df["n_drift_probes"].sum())
    note = (f"LLM-judged on {n_judged}/{n_probes} probes "
            f"(<={MAX_DRIFT_JUDGE} of up to ~19 per run), {n_runs}/{len(df)} runs"
            if n_judged else
            f"drift judge did not run: NOT JUDGED (0/{n_probes} probes), not drift=0")
    return runs, note


def plot_rubric(runs: dict, drift_runs: dict, out: str, drift_note: str = ""):
    fig, axes = plt.subplots(2, 3, figsize=(16, 9), sharex=True)
    for ax, (key, label) in zip(axes.flat, CHANNELS):
        src = drift_runs if key == "drift" else runs
        curve_key = "cum_drift" if key == "drift" else key
        for cfg in CONFIGS:
            if not src.get(cfg):
                continue
            x, y = _mean_curve(src[cfg], curve_key)
            if len(x):
                ax.plot(x, y, label=LABELS[cfg], color=COLORS[cfg], linewidth=1.8)
        ax.set_xscale("log")
        ax.set_title(label, fontsize=12, weight="bold")
        ax.set_ylabel("mean cumulative count")
        ax.grid(True, alpha=0.25)
        if key == "drift":
            # drift is a count over the <=5 judged probes, not over all probes
            ax.set_ylabel(f"mean cumulative flags (of <={MAX_DRIFT_JUDGE} judged)")
            ax.text(0.03, 0.9, drift_note or "LLM-judged (others deterministic)",
                    transform=ax.transAxes, fontsize=7.5, color="#555")
    # hide the unused 6th panel
    for ax in axes.flat[len(CHANNELS):]:
        ax.set_visible(False)
    for ax in axes[-1]:
        ax.set_xlabel(XLABEL)
    axes[0, 0].legend(title=LEGEND_TITLE, fontsize=8, frameon=False)
    fig.suptitle("How each failure mode accumulates over the horizon",
                 fontsize=14, weight="bold")
    fig.text(0.01, 0.01, report.DRIFT_NOTE, fontsize=7.5, color="#555")
    fig.tight_layout(rect=[0, 0.025, 1, 0.97])
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


if __name__ == "__main__":
    log_dir = sys.argv[1] if len(sys.argv) > 1 else "flash_lite_eval_20260627_09354"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "scout_report/plots_out"
    os.makedirs(out_dir, exist_ok=True)
    runs = load_channel_curves(log_dir)
    scan_dir = latest_scan()
    if scan_dir:
        drift_runs, drift_note = load_drift_panel(scan_dir)
    else:
        drift_runs, drift_note = {c: [] for c in CONFIGS}, "no scan found: NOT JUDGED"
    n = sum(len(v) for v in runs.values())
    print(f"Loaded {n} runs across {sum(1 for v in runs.values() if v)} configs"
          f"{'' if scan_dir else ' (no scan found -> drift panel empty)'}")
    print(f"drift panel: {drift_note}")
    plot_rubric(runs, drift_runs, f"{out_dir}/plot_c_failure_modes_accumulate.png",
                drift_note=drift_note)
