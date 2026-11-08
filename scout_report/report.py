"""Aggregate the cooking_rubric Scout scan into a per-config report.

Reads the latest scan under scout_report/scans, groups the 60 per-transcript
Results by ablation config, and prints score + failure-channel rates (raw and
per-step normalized, since cumulative channel counts scale with episode length).

    .venv-inspect/bin/python scout_report/report.py
"""
import glob
import json
import os
import sys

import pandas as pd

from cooking_rubric import MAX_DRIFT_JUDGE

CONFIGS = ["baseline-m5", "m3-m5", "m7-m5", "m5-m6", "m3-m5-m6", "m7-m5-m6"]
CHANNELS = ["total_ale", "ale_spatial", "ale_recipe", "interface", "liveness",
            "info_seek", "integration", "drift", "n_drift_probes", "steps"]

# Printed under every drift figure/table: the drift count is a numerator over
# an at-most-5-probe sample, not over the run's probes (review #5).
DRIFT_NOTE = (
    f"drift note: the LLM judge scores an even sample of at most "
    f"MAX_DRIFT_JUDGE={MAX_DRIFT_JUDGE} of a run's drift probes (a 100-step run "
    f"has up to ~19), so drift is reported as flagged/judged, never as a raw "
    f"count. 'not judged' = the judge did not run on those runs (NOT drift=0)."
)
NOT_JUDGED = "not judged"


def _config(uri: str) -> str:
    # match longest labels first so "m3-m5" doesn't shadow "m3-m5-m6"
    for c in sorted(CONFIGS, key=len, reverse=True):
        if c in str(uri):
            return c
    return "?"


def _md(cell, key, default=0):
    if isinstance(cell, str):
        try:
            cell = json.loads(cell)
        except Exception:
            cell = {}
    return (cell or {}).get(key, default) if isinstance(cell, dict) else default


def load(scan_dir: str | None = None) -> pd.DataFrame:
    if scan_dir is None:
        # scan_ids are random, so pick the most recently written scan by mtime
        scans = glob.glob("scout_report/scans/scan_id=*")
        scan_dir = max(scans, key=os.path.getmtime)
    df = pd.read_parquet(f"{scan_dir}/cooking_rubric.parquet")
    df["config"] = df["transcript_source_uri"].map(_config)
    df["final_score"] = df["metadata"].map(lambda m: _md(m, "final_score"))
    for k in CHANNELS:
        default = None if k == "drift" else 0
        df[k] = df["metadata"].map(lambda m, k=k, d=default: _md(m, k, d))
    df["drift_note"] = df["metadata"].map(lambda m: _md(m, "drift_note", ""))
    # n drift probes actually judged (<=5 sampled per run); the drift count is a
    # numerator over THIS, not over the run's ~19 available probes (review #5).
    def _n_judged(m):
        n = _md(m, "n_judged", None)
        if n is not None:
            return float(n)
        ev = _md(m, "drift_events", "[]")        # scans predating n_judged
        try:
            return float(len(json.loads(ev) if isinstance(ev, str) else (ev or [])))
        except Exception:
            return 0.0
    df["drift_judged"] = df["metadata"].map(_n_judged)
    # judge never ran -> NaN judged, so nothing can average it in as a 0.
    df.loc[df["drift"].isna(), "drift_judged"] = float("nan")
    return df


def drift_status(df: pd.DataFrame) -> str:
    """One-line summary of whether (and how widely) the drift judge ran."""
    runs = int(df["drift"].notna().sum())
    n_judged = int(df["drift_judged"].sum())          # NaN (skipped) excluded
    n_probes = int(df["n_drift_probes"].sum())
    cov = (f"{n_judged} of {n_probes} drift probes judged "
           f"(cap {MAX_DRIFT_JUDGE}/run)")
    # a skip reason is only recorded on runs the judge did not score
    notes = [n for n in df.loc[df["drift"].isna(), "drift_note"].unique() if n]
    if runs == len(df):
        return f"drift judge ran on all {runs} runs; {cov}."
    if notes:
        return (f"drift judge SKIPPED on {len(df) - runs} runs -> {notes[0]} "
                f"| judged runs: {runs}/{len(df)}, {cov}")
    return f"drift judged on {runs}/{len(df)} runs ({cov}); others had no drift probes."


def report(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("config").agg(
        n=("value", "size"),
        score=("final_score", "mean"),
        ALE=("total_ale", "mean"),
        ALE_per_step=("total_ale", "sum"),
        interface=("interface", "mean"),
        liveness=("liveness", "mean"),
        info_seek=("info_seek", "mean"),
        integration=("integration", "mean"),
        steps=("steps", "mean"),
    )
    # per-step ALE rate = total ALE / total steps (length-normalized)
    tot = df.groupby("config").agg(ale=("total_ale", "sum"), st=("steps", "sum"),
                                   dpos=("drift", "sum"), djud=("drift_judged", "sum"),
                                   dprobes=("n_drift_probes", "sum"),
                                   druns=("drift_judged", lambda s: (s.fillna(0) > 0).sum()),
                                   n100=("steps", lambda s: (s >= 95).sum()))
    g["ALE_per_step"] = (tot["ale"] / tot["st"]).round(2)
    # Drift as "X of Y judged" + a rate -- never a raw sum, which would imply we
    # judged every probe (we judge <=MAX_DRIFT_JUDGE of up to ~19). A config
    # whose judge never ran reads "not judged", not 0 (review #5).
    g["drift_flagged/judged"] = [NOT_JUDGED if j == 0 else f"{int(p)}/{int(j)}"
                                 for p, j in zip(tot["dpos"], tot["djud"])]
    g["drift_rate"] = [NOT_JUDGED if j == 0 else f"{p / j:.3f}"
                       for p, j in zip(tot["dpos"], tot["djud"])]
    # sampling coverage: judged probes / probes available, and how many of the
    # config's runs contributed >=1 judged probe
    g["drift_judged/probes"] = [f"{int(j)}/{int(n)}"
                                for j, n in zip(tot["djud"], tot["dprobes"])]
    g["drift_runs"] = [f"{int(r)}/{int(n)}" for r, n in zip(tot["druns"], g["n"])]
    g["runs_reaching_cap"] = tot["n100"].astype(int)   # survivorship (review #2)
    return g.reindex(CONFIGS).round(2)


if __name__ == "__main__":
    scan_dir = sys.argv[1] if len(sys.argv) > 1 else None
    df = load(scan_dir)
    pd.set_option("display.width", 240)
    print(f"Scored {len(df)} runs across {df['config'].nunique()} configs "
          f"(labels: {df['label'].value_counts().to_dict()})")
    print(drift_status(df) + "\n")
    print(report(df).to_string())
    print(f"\n{DRIFT_NOTE}")
