# Overnight progress — Scout eval reporting

Ran unattended 2026-07-17. All work under `scout_report/`. `long-horizon/` and
`long-horizon-scaling/` untouched (read-only). New deps installed only into
`.venv-inspect`: `openai` (OpenRouter provider dep) and `matplotlib`.

## Summary

| Goal | Status | Note |
|------|--------|------|
| A — drift + integration channels | **DONE** (drift judge skipped: invalid key) | integration works; drift wired & degrades cleanly |
| B — budget-vs-outcome plots | **DONE** | 2 PNGs; score plateaus while ALE climbs |
| C — unified TextQuests+Cooking entrypoint | **DONE** | both sources reproduce their tables |

---

## Goal A — drift & integration channels in `cooking_rubric.py`

**What changed**
- **Integration channel (heuristic, no API).** Each `integration` probe emits a
  numbered 3-step plan. I take the plan's first action, normalize it, and check
  whether it is actually executed within the `[probe_step .. probe_step+3]`
  action window. If not, the agent produced a plan then ignored it → +1
  integration error. Cumulative count stored as `integration` (and
  `n_integration_probes`). This is a documented heuristic — the integration
  probe has no ground truth. Verified sensible on a hand-traced transcript
  (plan "take knife" never executed → failure; plan "move north" = current
  action → no failure).
- **Drift channel (LLM-judged).** Ported `judge_drift.py`'s system prompt and
  0/1 semantics. For each `drift` probe I judge whether the agent's stated
  intentions still align with the game goal, using `openrouter/openai/gpt-oss-120b`
  read from `OPENROUTER_API_KEY`. Per-run cumulative drift count → `drift` in
  Result metadata (plus `n_drift_probes`, `drift_note`).
  - **Cost cap:** at most `MAX_DRIFT_JUDGE = 5` drift probes judged per
    transcript, evenly spaced (`_even_sample`). Bounds spend to ≲300 calls.
  - **Graceful skip:** a single locked preflight generate decides judge
    availability for the whole run. Missing key **or** a failing key disables
    the judge (drift=None) with a recorded note, instead of failing 60 scans or
    burning calls.

**Blocker (drift only):** `OPENROUTER_API_KEY` is *set* but **invalid** — both
`curl .../auth/key` and a test generate return `401 "User not found."` So the
judge was skipped exactly as the "no key" fallback specifies: 53 runs →
`drift=None` with note `AuthenticationError 401`; 7 short runs → `drift=0`
legitimately (they fired **zero** drift probes). The report prints an explicit
`drift judge SKIPPED on 53 runs -> ...` line. If a valid key is dropped in, the
same code path judges live with no changes.

**Fix — drift denominator (review #5, 2026-10-13).** The drift column printed a
raw *sum* of judge verdicts, which implied every drift probe was judged. It was
not: `_judge_drift` evenly samples at most `MAX_DRIFT_JUDGE = 5` probes, so a
100-step run with 19 drift probes contributes a count out of 5 while a short run
contributes out of 1 — not comparable across runs. Changes:
- `cooking_rubric.py` now surfaces **`n_judged`** (the denominator) and
  **`drift_judged_frac`** alongside the existing `drift` / `n_drift_probes`, and
  the Result answer reads `drift=4 flagged of 5 judged (19 probes)` instead of
  `drift=4`. `_judge_drift` returns `(flagged, n_judged, note, events)`;
  `n_judged is None` ⇔ the judge never ran.
- `report.py` drops the raw `drift` mean and prints
  `drift_flagged/judged`, `drift_rate`, `drift_judged/probes` and `drift_runs`
  (+ `DRIFT_NOTE`, the sampling caveat, under every table). Old scans without
  `n_judged` fall back to `len(drift_events)`.
- `plots_rubric.py` builds the drift panel from **judged runs only**
  (`load_drift_panel`) — a skipped run previously averaged in as a flat zero
  line — and labels the panel `mean cumulative flags (of <=5 judged)` with the
  per-figure coverage note.
- **Skipped judge now reads "not judged", never 0:** `drift_judged` is NaN (not
  0) when the judge did not run, so the rate/ratio columns print `not judged`
  and the drift panel prints
  `drift judge did not run: NOT JUDGED (0/459 probes), not drift=0`.

Rendering on the two existing scans (`.venv-inspect/bin/python scout_report/report.py [scan_dir]`):
```
# judged scan (scan_id=9KeZ...)   before:  drift 0.0 / 0.1 / 0.4 ... (raw mean)
                        after:  drift_flagged/judged 0/30  drift_rate 0.000  drift_judged/probes 30/48  drift_runs 8/10
                                drift judge ran on all 60 runs; 197 of 459 drift probes judged (cap 5/run).
# skipped scan (scan_id=8ant...)  before:  drift 0.0 for 3 configs, NaN for 3; drift_flagged/judged "0/0"
                        after:  drift_flagged/judged "not judged", drift_rate "not judged", drift_judged/probes 0/48
```
Note: `plots_out/plot_c_failure_modes_accumulate.png` is stale until
`plots_rubric.py` is re-run (verified by rendering to a temp dir, repo PNG left
untouched).

**Verify**
```
.venv-inspect/bin/scout scan scout_report/cooking_rubric.py \
    -T flash_lite_eval_20260627_09354 --scans scout_report/scans --display none
.venv-inspect/bin/python scout_report/report.py
```
Output (all 60 scored, 0 errors in `_errors.jsonl`):
```
Scored 60 runs across 6 configs (labels: {'scored': 60})
drift judge SKIPPED on 53 runs -> drift judge unavailable (AuthenticationError: 401 ... 'User not found.')

              n  score    ALE  ALE_per_step  interface  liveness  info_seek  integration  drift  steps
baseline-m5  10   0.33   97.6          3.51       18.1       0.0        1.9          1.6    0.0   27.8
m3-m5        10   0.26   87.0          2.82       22.5       0.0        1.2          1.8    0.0   30.9
m7-m5        10   0.29   83.2          3.13       18.7       0.0        1.6          1.5    0.0   26.6
m5-m6        10   0.48  287.4          5.18       31.0       0.2        3.2          1.0    NaN   55.5
m3-m5-m6     10   0.51  249.7          5.25       25.7       0.3        3.0          0.6    NaN   47.6
m7-m5-m6     10   0.47  253.4          4.00       31.4       0.4        3.4          1.9    NaN   63.4
```
`integration` is non-trivial (0.6–1.9/run). (Table above is the pre-fix
rendering — the `drift` raw-mean column is gone; see "Fix — drift denominator".)

**Also fixed:** `report.py` picked the "latest" scan by *lexical* sort of the
random scan_id — it was silently reading a stale scan. Now picks by mtime.

---

## Goal B — plots (`plots.py` → `plots_out/`)

**What changed.** New `scout_report/plots.py` reconstructs per-step cumulative
curves straight from each eval log's `trajectory_telemetry` (reusing
`calculate_ale`), averages across the 10 seeds per config (truncating a config's
curve once <3 seeds remain), and renders:
- `plot_a_score_vs_budget.png` — mean cumulative game score vs budget.
- `plot_b_errors_vs_budget.png` — mean cumulative ALE vs budget (drift overlay
  omitted with an on-plot note, since the drift judge was skipped).

**Budget axis decision.** Per-step token counts are **not** in these logs — only
a per-transcript total in `sample.model_usage`. So x = **cumulative steps**
(log scale) as the budget proxy, documented in the module docstring, with each
config's mean total tokens/run shown in Plot A's legend (~2.2M for baseline-m5
up to ~18M for m7-m5-m6).

**Takeaway.** Yes — score plateaus while errors climb. The long-horizon m6
configs flatten around ~0.4 game score, but their cumulative ALE keeps rising
steeply to 430–630 errors; error accumulation outpaces reward gain.

**Verify**
```
.venv-inspect/bin/python scout_report/plots.py
# -> Loaded 60 runs; wrote plot_a_score_vs_budget.png, plot_b_errors_vs_budget.png
ls scout_report/plots_out/   # both PNGs present; script re-runs cleanly
```

---

## Goal C — unified entrypoint (`run_report.py`)

**What changed.** New `scout_report/run_report.py --source <path>` classifies the
source and dispatches, reusing existing modules (no scanner logic duplicated):
- **`.eval` logs** → runs the `cooking_rubric` scan, then prints via
  `report.load/drift_status/report`.
- **TextQuests `.json`** → `convert.build_db` → runs only the deterministic
  TextQuests scanners (`action_loops`, `parser_rejections`) so it stays **dry /
  no-API**, then aggregates with `scan_results_df` into one table. (The LLM
  scanners in `scanners.py` are deliberately not selected.)

Note: `scout scan` accepts scanner subsets only as `file@name` one-at-a-time
(comma / multiple `@` args did not work here), so the TextQuests path runs one
scan per dry scanner into its own `scans_tq/<scanner>/` dir and merges results.

**Verify**
```
.venv-inspect/bin/python scout_report/run_report.py --source flash_lite_eval_20260627_09354
#   -> reproduces the 6-config cooking table above

.venv-inspect/bin/python scout_report/run_report.py \
    --source base-project/textquests/results/baseline_no_clues
#   -> TextQuests report from ... (1 transcript(s), dry scanners only)
#         scanner                                transcript  value           answer label
#      action_loops baseline_no_clues__or-gpt-oss-120b__zork1      3 3x 'WIND CANARY'    ok
# parser_rejections baseline_no_clues__or-gpt-oss-120b__zork1     66             <NA>   NaN
```
Both dispatch and print without error; TextQuests path makes no API calls.

---

## Decisions & limitations
- **Drift judge could not run** — the provided `OPENROUTER_API_KEY` is invalid
  (401 "User not found"). Code is complete and cost-capped; drop in a valid key
  and re-run the Goal A verify command to get live drift values. No other goal
  depends on it.
- **Drift is a sampled measure** — at most `MAX_DRIFT_JUDGE = 5` of a run's up
  to ~19 drift probes are judged (deliberate cost cap, unchanged), so it is only
  ever reported as flagged/judged + a rate, never as a raw count.
- **Integration** is a labeled heuristic (plan-first-action executed within the
  next-3 window), not ground truth — by design; no API used.
- **Budget axis** is steps, not tokens, because per-step tokens aren't logged.
- New deps (`openai`, `matplotlib`) went only into `.venv-inspect`.
- `report.py` scan-selection bug (lexical vs mtime) fixed in passing.
