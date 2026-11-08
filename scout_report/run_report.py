"""One entrypoint for both CookingWorld eval logs and TextQuests results.

Dispatches on what `--source` points at and reuses the existing per-pipeline
modules (no scanner logic is duplicated here):

  * a dir of Inspect `.eval` logs  -> cooking_rubric scanner + report.py table
  * a dir of TextQuests `.json`     -> convert.py DB + textquests scanners.py,
    running only the deterministic (no-API) scanners so it stays dry.

    .venv-inspect/bin/python scout_report/run_report.py \
        --source flash_lite_eval_20260627_09354
    .venv-inspect/bin/python scout_report/run_report.py \
        --source base-project/textquests/results/baseline_no_clues
"""
import argparse
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TQ_SCOUT = os.path.join(ROOT, "base-project", "textquests", "scout")
SCOUT_BIN = os.path.join(os.path.dirname(sys.executable), "scout")

# TextQuests scanners that need no model/API (keeps the run dry)
TQ_DRY_SCANNERS = ["action_loops", "parser_rejections"]


def _classify(source: str) -> str:
    """Return 'cooking' | 'textquests' from the source dir's contents."""
    if os.path.isdir(source):
        if glob.glob(os.path.join(source, "**", "*.eval"), recursive=True):
            return "cooking"
        if glob.glob(os.path.join(source, "**", "*.json"), recursive=True):
            return "textquests"
    elif source.endswith(".eval"):
        return "cooking"
    elif source.endswith(".json"):
        return "textquests"
    raise SystemExit(f"Unrecognized source (no .eval or .json under {source})")


def _scan(*args: str) -> None:
    subprocess.run([SCOUT_BIN, "scan", *args, "--display", "none"],
                   cwd=ROOT, check=True)


# --- cooking path -----------------------------------------------------------
def run_cooking(source: str) -> None:
    sys.path.insert(0, HERE)
    import report
    scans = os.path.join(HERE, "scans")
    _scan(os.path.join(HERE, "cooking_rubric.py"), "-T", source, "--scans", scans)
    df = report.load()
    print(f"CookingWorld report from {source}")
    print(f"Scored {len(df)} runs across {df['config'].nunique()} configs "
          f"(labels: {df['label'].value_counts().to_dict()})")
    print(report.drift_status(df) + "\n")
    print(report.report(df).to_string())
    print(f"\n{report.DRIFT_NOTE}")


# --- textquests path --------------------------------------------------------
def run_textquests(source: str) -> None:
    sys.path.insert(0, TQ_SCOUT)
    import asyncio
    import convert
    from inspect_scout import scan_results_df

    db = os.path.join(HERE, "tq_db")
    n = asyncio.run(convert.build_db(source, db))
    if not n:
        raise SystemExit(f"No convertible TextQuests transcripts under {source}")

    scanners_py = os.path.join(TQ_SCOUT, "scanners.py")
    rows = []
    for sc in TQ_DRY_SCANNERS:
        out = os.path.join(HERE, "scans_tq", sc)
        _scan(f"{scanners_py}@{sc}", "-T", db, "--scans", out)
        scan_dir = max(glob.glob(os.path.join(out, "scan_id=*")),
                       key=os.path.getmtime)
        r = scan_results_df(scan_dir)
        for name in r.scanners.keys():
            for _, row in r.scanners[name].iterrows():
                rows.append({"scanner": name,
                             "transcript": row["transcript_id"],
                             "value": row["value"],
                             "answer": str(row["answer"])[:40],
                             "label": row["label"]})

    import pandas as pd
    pd.set_option("display.max_colwidth", 44)
    pd.set_option("display.width", 200)
    print(f"TextQuests report from {source} "
          f"({n} transcript(s), dry scanners only)\n")
    print(pd.DataFrame(rows).to_string(index=False))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True,
                    help="dir of .eval logs (cooking) or TextQuests .json results")
    args = ap.parse_args()
    kind = _classify(args.source)
    (run_cooking if kind == "cooking" else run_textquests)(args.source)


if __name__ == "__main__":
    main()
