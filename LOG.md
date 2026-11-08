# LOG.md — session log (newest entry last)

## 2026-11-07 — priorities 1-3 implemented (agent session)

**Done**

1. **Per-step token logging (priority 1).**
   - `base-project/textquests/src/llm_agents.py`: `TokenUsage` gains `reasoning_tokens`
     (OpenAI-compatible `completion_tokens_details.reasoning_tokens`; Anthropic reports
     thinking inside `output_tokens`, stays 0). Provider semantics documented on the class.
   - `base-project/textquests/play_textquests.py`: each step's log dict now carries
     `token_usage` (all classes, summed across retries) and `cumulative_token_usage`.
   - `base-project/textquests/scout/convert.py`: surfaces `step_token_usage` list in
     transcript metadata when present.
   - Verified: unit test on sum/max utils, plus live 3-step run (below).
   - NOT done: Sam's CookingWorld harness (`step_log` in `harness_orchestrator`).
     That is a framework change owned by Sam; flagged, not touched.

2. **RUBRIC.md (priority 2).** `scout_report/RUBRIC.md` v1.0, frozen. Per channel:
   definition, exact decision rule, type, ground-truth requirement, caveats.
   Reconciles 4-channel spec with 6-channel code: `info_seek` is declared an auxiliary
   M1 behaviour metric, not a failure channel; ALE split spatial/recipe kept.
   Labelling schema `{step, channel, evidence_span, justification, confidence}` with
   `other` bucket and tie-break rules. §4 proposes the compute-axis token definition
   (billed total = input + disjoint cache reads + output) — flagged, needs team sign-off.

3. **TALES-side baseline runner (priority 3).** `base-project/textquests/play_tales.py`:
   raw ReAct (no clues, no restore affordance), stock jericho-suite ROMs in
   `data/tales-roms/` (zork1.z5 MD5 b732a93a…, wishbringer.z3 MD5 87ed53d8…, both
   `is_fully_supported=True` [verified]), `ground_truth` (location/inventory/score/moves)
   logged every step from the Jericho object tree, per-step token logging, multi-seed CLI,
   checkpoint-every-10-steps atomic saves, deterministic replay resume. Output schema
   ingests through `scout/convert.py` unchanged (seed-qualified transcript ids added).
   This implements the dual-wrapper route and dissolves the instrumented-ROM
   ground-truth blocker for baseline collection.

**Verification (reproducible commands)**

```
cd base-project/textquests
/opt/anaconda3/bin/python play_tales.py --model or-gpt-oss-120b --game_name zork1 \
    --seeds 0 --max_steps 3 --run_id tales_smoke
../../.venv-inspect/bin/python scout/convert.py --results results/tales_smoke --db <tmp>
```
Smoke run (3 steps, [verified]): ground truth tracks state ('take leaflet' → inventory
['leaflet']); per-step tokens e.g. step 0 = {input 284, output 140, cached 0, reasoning 76};
cumulative 1467 total. Converter inserts `tales_smoke__or-gpt-oss-120b__zork1_seed0`.
Smoke cost < $0.01. OpenRouter key in `.env` replaced this week; valid to 2027-01-11,
$50 limit, $0 spent at check time [verified].

**Proposed collection run grid (NOT executed — needs budget + scope sign-off)**

Anchor [verified]: existing 500-step Zork run (gpt-oss-120b) = 13.24M total tokens
(13.09M input / 0.33M cached / 0.15M output). Estimates below scale from that anchor
and public price sheets [unverified]:

| Model | $/run (500 steps) | 2 games × 5 seeds |
|---|---|---|
| or-gpt-oss-120b | ~$1.5 | ~$15 |
| claude-haiku-3-5 | ~$3-8 | ~$30-80 |
| claude-sonnet-4-0 | ~$10-30 | ~$100-300 |
| **Total (3 models, 30 runs)** | | **~$150-400** |

Options to cut cost: max_steps 300 (gpt-oss degenerates past ~300 anyway) roughly
halves it; drop sonnet to 3 seeds first and expand where variance is high.
Decision needed from team: model set, seeds, max_steps, budget. Do not launch before
that sign-off.

**Blocked / flagged**
- CookingWorld per-step tokens: Sam's framework, his call on the `step_log` change.
- Collection scope: team decision (grid above).
- Token-definition default: proposed in RUBRIC.md §4, needs sign-off before Plot A/B
  captions use it.

**Next session should**: get sign-off on grid + token definition, launch collection,
then port the belief probe run over the new transcripts (priority 4) and draw Coz's
two plots on real tokens from `step_token_usage`.

## 2026-11-07 (later) — live pricing correction + $50 plan

Live OpenRouter prices pulled via API [verified 2026-11-07]: gpt-oss-120b $0.023/M in,
$0.085/M out; flash-lite $0.10/$0.40; haiku-4.5 $1/$5 (cache read $0.10); sonnet-4.5
$3/$15 (cache read $0.30). This corrects the earlier [unverified] grid estimate:
gpt-oss-120b is ~$0.31/run at 500 steps, not ~$1.5. Scaling: input ~quadratic in steps
(context grows linearly), output ~linear; anchor is the verified 13.09M-in/0.152M-out
Zork run.

Caveats: Wishbringer per-run tokens assumed similar to Zork [unverified]. Claude via
OpenRouter gets NO prompt caching from our OpenAI-compatible client (no cache_control
sent); Claude costs below are uncached. Caching via direct Anthropic API (AnthropicAgent
already does it) cuts sonnet to ~$10/run, haiku to ~$2-3/run, but spends the Anthropic
key, not the OpenRouter key.

Plan that fits the $50 OpenRouter cap (committed ~$35, ~$15 headroom for retries,
degeneration, drift judge, belief-probe pilot): see session summary / message to
research manager. Not launched; awaiting scope sign-off.

## 2026-11-07 (later still) — alignment check vs new plan doc + updated CLAUDE.md

**Checked** the eval-science directions doc and the 2026-11-07 CLAUDE.md revision
(ALE first/persisted split, revised priorities) against this session's work.

**Verified from repos (upgrading two [reported] claims):**
- Utsab's harness per-step tokens: `experiments/logger.py` schema has `steps[].tokens`
  (judge-inclusive total) + `judge_tokens`. No class split; `prompt_tokens` is used
  transiently for truncation, not persisted [verified]. So priority 1 "port and
  reconcile" resolves to: our class-split logging stands; comparisons with his runs
  need a mapping (his tokens ≈ our total + judge spend).
- Anthropic key in repo-root `.env` is valid (HTTP 200) [verified]. `llm_agents.py`
  now also loads the root .env (never overriding local/shell).

**Alignment fixes made:**
- RUBRIC.md bumped to v1.1: ALE-first/ALE-persisted subtypes with decision rules,
  latency + contradiction-event denominator, probe-every-step instrument note,
  amplification excluded from channels, `subtype` added to the labelling schema.
  Nothing was labelled under v1.0, so no relabel.
- `model_configs.yaml`: added claude-haiku-4-5 / claude-sonnet-4-5 (direct Anthropic,
  thinking off for baseline parity).
- Stale-status notes: plan doc says ground truth and RUBRIC are still missing; both
  were closed earlier today (doc was written from Drive docs, predates this session).

**Still misaligned / not built (next):** ALE-persisted detector + probe outputs
(priority 4; coordinate ownership with Utsab before building), hand-labelled slice,
Coz plots on real tokens.

**Collection grid v2 (aligned with new plan; NOT launched, needs sign-off):**
300-step cap (gpt-oss degenerates past ~300 [reported]; cap is a team call):

| Model (route) | Games x seeds | Est. cost |
|---|---|---|
| gpt-oss-120b (OpenRouter) | 2 x 10 | ~$2.50 |
| gemini-2.5-flash-lite (OpenRouter) | 2 x 5 | ~$6 |
| claude-haiku-4-5 (Anthropic, cached) | 2 x 10 | ~$30 |
| claude-sonnet-4-5 (Anthropic, cached) | 2 x 5 | ~$44 |

OpenRouter ~$9 of $50; Anthropic ~$75 against BlueDot remaining $1,279 [reported].
All Claude estimates [unverified], scaled from the verified 13.09M/0.152M anchor with
~0.36 quadratic input scaling to 300 steps and cache-read discounting.
Grid serves: 4 models (predictor RQ4 needs 4+), 10 seeds on two models
(decorrelation RQ5 needs 10+ on a pair), ground truth every step (hazard model,
ALE-persisted), per-step class-split tokens (compute axis).
