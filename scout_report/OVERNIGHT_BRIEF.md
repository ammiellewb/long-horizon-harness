# Overnight autonomous task — Scout eval reporting

You are running unattended. Complete the three goals below, verify each, and write a
summary to `scout_report/PROGRESS.md`. Work only inside `BASE Project/scout_report/`
(plus reading the eval logs and teammate repos). Do NOT modify or `git push` anything in
`long-horizon/` or `long-horizon-scaling/` — they are read-only references. Do NOT install
packages other than into `.venv-inspect`. Always run python/scout via
`/Users/ammiellewambobecker/github/BASE Project/.venv-inspect/bin/python` (and `.../bin/scout`).

## Context (already built, working)
- `.venv-inspect` has inspect_ai 0.3.247 + inspect_scout 0.4.44. `.eval` files are zstd —
  only readable via inspect.
- Data: `flash_lite_eval_20260627_09354/` — 6 configs (baseline-m5, m3-m5, m7-m5, m5-m6,
  m3-m5-m6, m7-m5-m6) × 10 seeds. Real gemini-flash-lite CookingWorld ablation logs.
- `scout_report/cooking_rubric.py` — a `@scanner` that scores ALE/interface/liveness/info-seek
  from each transcript's `metadata["sample_metadata"]["trajectory_telemetry"]`. GOTCHA: sample
  metadata is nested under `sample_metadata`, NOT top-level `transcript.metadata`.
- `scout_report/report.py` — aggregates the scan parquet by config.
- Run pattern: `.venv-inspect/bin/scout scan scout_report/cooking_rubric.py -T flash_lite_eval_20260627_09354 --scans scout_report/scans --display none` then `.venv-inspect/bin/python scout_report/report.py`.
- Reference: `long-horizon-scaling/experiments/analysis/2026-06-26-error-category-game-score-experiment/judge_drift.py` (drift LLM judge) and `parse_ablation_results.py` (channel logic).

## Goal A — add the drift (and integration) channel to the rubric scanner
The telemetry has `drift` and `integration` probe_results that the current scanner ignores.
- Port `judge_drift.py`'s prompt/semantics into `cooking_rubric.py` as a drift channel: for each
  `drift` probe result, judge (0/1) whether the agent's stated intentions still align with the
  game goal. Add a per-run cumulative drift count to the Result metadata.
- Use a CHEAP model via `OPENROUTER_API_KEY`: `openrouter/openai/gpt-oss-120b`. Read the key
  from env. If `OPENROUTER_API_KEY` is unset, SKIP the judge, emit drift=None, and note it in
  PROGRESS.md (do not fail the whole run).
- COST CAP: judge at most 5 drift probes per transcript (they fire every 5 steps; take an evenly
  spaced sample). This bounds spend to ~300 judge calls total.
- Integration: the `integration` probe has no ground-truth rule. Add a documented heuristic
  (e.g. agent produced a plan but next action ignores it) OR leave a clearly-labeled stub —
  your call, but document which in PROGRESS.md. Do not spend API on integration.
- Done when: `report.py` shows a `drift` column with non-trivial values (or a clear "judge
  skipped, no key" note), and the scanner still scores all 60 runs without error.

## Goal B — plots on this eval data
Create `scout_report/plots.py` producing, from the scan results + eval logs:
- Plot A: x = log(cumulative tokens or steps as a budget proxy), y = mean game score, one line
  per config. (Token totals are in each eval log; if per-step tokens are unavailable use steps
  as the budget proxy and document it.)
- Plot B: x = same budget axis, y = cumulative ALE (and drift if available), one line per config.
- Save PNGs to `scout_report/plots_out/`. matplotlib is fine to add to `.venv-inspect` if missing.
- Done when: both PNGs exist and the script re-runs cleanly. Note in PROGRESS.md the one-line
  takeaway (does score plateau while errors climb?).

## Goal C — unify TextQuests + CookingWorld reporting under one entrypoint
Create `scout_report/run_report.py` that takes `--source <dir-of-eval-logs OR textquests-results>`
and dispatches: eval-log dirs → `cooking_rubric` scanner path; TextQuests JSON (see
`base-project/textquests/scout/convert.py` + `scanners.py`) → the TextQuests scanners. It should
run the scan and print the aggregated report for whichever source type is given. Keep it thin —
reuse existing modules, don't duplicate scanner logic.
- Done when: `run_report.py --source flash_lite_eval_20260627_09354` reproduces the cooking table,
  and `--source base-project/textquests/results/baseline_no_clues` produces a TextQuests report
  (dry, no API) without error.

## Finish
Write `scout_report/PROGRESS.md`: per goal — DONE/PARTIAL/BLOCKED, what you changed, the verify
command you ran and its output, and any decision/limitation. If a goal is blocked (e.g. no API
key), do the other two fully and record the blocker. Keep all outputs under `scout_report/`.
