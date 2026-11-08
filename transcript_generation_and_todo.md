# Baseline transcripts + rubric: what's next

Scope: my ownership areas (belief-diff/probe script, Scout integration, TextQuests
baseline on Zork I + Wishbringer, failure-channel rubric). Data and rubric come before
adding more scanners.

## 0. Status (updated 2026-07-08)

Audited both teammate repos (`long-horizon` = Utsab, `long-horizon-scaling` = dignissimus).
Key realization: most of the rubric/probe machinery this doc plans is **already implemented
by dignissimus** — but on TextWorldExpress/CookingWorld, not on our Zork/TextQuests
transcripts. So the job is **port, not rebuild**.

| Item | Status | Notes |
|---|---|---|
| Scout converter (json + md) | ✅ done | `textquests/scout/convert.py` |
| Scanners: interface + liveness | ✅ done | `parser_rejections`, `action_loops` |
| OpenRouter + Claude backends wired | ✅ infra ready, unrun | `model_configs.yaml` has sonnet/opus/haiku entries |
| One Zork I baseline | ✅ done | `results/baseline_no_clues/or-gpt-oss-120b/zork1.json`, 500 steps |
| 4-channel rubric **as metrics** | ⚠️ exists in dignissimus, wrong env | `parse_ablation_results.py` (ALE/interface/liveness/info-seek) + `judge_drift.py` (drift). On CookingWorld only. `integration` channel = probe with no scoring rule. |
| Belief-diff / post-action probe | ⚠️ exists in dignissimus, wrong env | `probes/cooking.py::CookingALEProbe` (query belief → diff vs ground-truth object tree) |
| Cumulative-error plots | ⚠️ partial | dignissimus plots use **x = step**, not log(token budget) |
| **Per-step ground truth in transcripts** | ⚠️ **plumbing done, GT source blocked** | `get_ground_truth()` + `render_system_tracking()` added to `textquests_env.py`; `ground_truth` field now logged each step. BUT on the jiminy-cricket instrumented `.z3` ROMs, Jericho's object DB is unbound (`is_fully_supported==False`), so `get_player_location()/get_inventory()` return `None` → **location/inventory come back empty**; only score/max_score/moves are reliable. Fix (not yet built): get **location** from the status line `_remove_status_line` currently discards, and **inventory** via save-state → `step("inventory")` → parse → restore. Both use game text, not Jericho's object tree. |
| Rubric as a labeling instrument | ❌ not built | schema `{channel, evidence span, justification, confidence}`, `other` bucket, hand-labeled validation slice — nowhere yet |
| Wishbringer runs / Claude runs / multi-seed | ❌ not built | only 1 game × 1 model × 1 seed exists |
| Coz's two token-budget plots | ❌ not built | `token_usage` data is logged, plots aren't |

**Canonical ground-truth format** (all workers code against this). Each step's log dict
gains a structured field, and it renders to one human-readable line:

```json
"ground_truth": {"location": "West of House", "inventory": ["leaflet"], "score": 0, "max_score": 350, "moves": 3}
```
renders as:
```
[System Tracking] location: West of House | inventory: leaflet | score: 0/350 | moves: 3
```
Empty inventory → `inventory: (empty)`. Source: `env.env.get_inventory()` (list of objs with
`.name`), `env.env.get_player_location().name`, existing `score`/`moves` from `info`.

## 1. What needs to be done

### Priority: more baseline transcripts
- Collect more **no-harness (raw ReAct)** transcripts across **Zork I** and **Wishbringer**.
- Add **model diversity**: don't rely on `gpt-oss-120b` alone (it degenerates past ~300
  steps, truncated JSON, fails retries). Use Claude models as agent backends for
  long-context coherence, plus at least one cheap model for contrast. See section 2.
- Keep every transcript in the format the Scout converter already ingests (same schema as
  the 396-step Zork run), with `[System Tracking]` ground-truth lines interleaved.
- Open decision for the team: how many is enough? First pass ~5-10 seeds per
  (game x model) across 3-4 models, then expand only where per-run variance is high.

### Priority: failure-channel rubric
- Four channels, per step: accepted-local-error, control-path drift, integration,
  budget/liveness. Interface (parser rejection) is a control channel only.
- Write one local decision rule per channel (label from the step, not from the outcome).
- Add an `other` bucket for failures that don't fit (e.g. Sam's "bad decision /
  domain-knowledge" case).
- Lock the output schema: per-step record = {channel or none, evidence span,
  one-line justification, confidence}. Roll up to per-run channel rates.
- Hand-label a stratified slice of the existing Zork I baseline. This stress-tests the
  definitions and becomes the validation set (FP/FN) for any scanner later.
- Keep one taxonomy across games; vary only the ground-truth binding (Zork vs Wishbringer).

### Coz's two plots (from last meeting)
- Plot A: x = log(token budget), y = game score.
- Plot B: x = log(token budget), y = cumulative errors (rubric counts).
- Overlay and check correlation: when score flattens, do errors rise? Progress rate and
  error rate should be anti-correlated. If not, the setup is probably wrong.
- Lines = harnesses. Repeat across environments, models, games.
- Token budget = input + cache + reasoning + output (or just reasoning + output).

### Coordinate, don't duplicate
- belief-diff / per-step probe script: confirm split with Utsab before building. His
  approach is adjacent. The independent post-action probe (query belief, then diff against
  ground truth) is the version worth owning, since it isolates memory failure from prompt
  artifacts.

### Open decisions to settle with the team
- Per-step labels vs windowed (50-step) buckets for the rubric.
- Drift: hard number or qualitative report if annotator agreement is low.
- WITH CLUES vs NO CLUES as a config axis for collection.

## 2. Generating more transcripts with Claude subagents

Goal: more no-harness ReAct baselines on Zork I and Wishbringer, past the ~300-step wall,
with model diversity. "Subagent" here just means one independent worker that plays one
(game, seed, model) episode end to end and writes one transcript file. Fan out many in
parallel.

### Two ways to run it

**Option A (recommended, least new code): reuse the inspect harness.**
TextQuests is already wired to inspect via OpenRouter. Point the model config at Claude
models (Anthropic provider or OpenRouter), bump epochs/seeds, and let inspect's own
concurrency (`--max-connections`) parallelize the samples. The harness stays identical, so
the new transcripts are directly comparable to the existing baseline. inspect's parallel
sample workers are effectively your "subagents" here.

**Option B (self-healing orchestration): Claude Code subagents via the Task tool.**
Dispatch N subagents, each owning a batch of episodes with a focused brief: run the
episode, watch for the truncated-JSON crash, resume with the temperature + max_tokens bump
you already found, validate the output format, log the crash as a budget/liveness event
rather than dropping the run. Use this if you want a supervisor loop that recovers from
degeneration on its own.

Honest tradeoff: for pure throughput of API-driven episodes, plain parallel API workers
(asyncio, or inspect's built-in concurrency in Option A) are simpler and more reproducible.
Reserve Claude Code subagents for the parts that need judgment (crash recovery, format
validation), not as a wrapper around a loop that inspect already parallelizes.

### What each subagent/worker does (keep it identical to baseline)
Raw ReAct only. No memory store, no state externalization, no enforced info-seeking. Adding
any of those turns a baseline into a harness run and breaks comparability.

```
for step in range(max_steps):
    obs = game.observe()                 # Jericho/Frotz text
    log(obs)
    log(ground_truth(game))              # [System Tracking]: inventory, location, score
    resp = model(prompt + history)       # PLAN SYNTHESIS / REASONING / ACTION
    action = parse_action(resp)          # count parser rejections -> interface channel
    game.step(action)
    log(resp, action)
    checkpoint_every_n(step)             # so a crash resumes, not restarts
```

### Requirements that make the transcripts usable
- **Ground truth every step.** Interleave `[System Tracking]` lines (inventory, location,
  score) from Jericho. Without these the rubric can't check accepted-local-error or the
  belief-diff.
- **Format matches the Scout converter.** Same fields as the current Zork run so the 5
  scanners and the rubric ingest directly.
- **Baseline purity.** No hints. WITH CLUES vs NO CLUES only as a deliberate, labeled
  condition, not accidental leakage.
- **Diversity axes to vary:** game (Zork I, Wishbringer), model (2-3 Claude tiers + one
  cheap model), seed. Log all three in the transcript metadata.

### Handling degeneration
- Checkpoint every N steps; resume with the temperature + max_tokens bump on parse failure.
- Cap episodes at the game's natural step budget.
- Log crashes and repeated parse failures as budget/liveness events. They're data, not
  noise, and feed straight into Plot B.

### First-pass target
Enough to cover both games across 3-4 models with ~5-10 seeds each, then expand where
variance is high. Confirm the exact count with the team before a big run.

## 3. Execution plan: port from long-horizon-scaling + subagent split

Strategy: adopt dignissimus's abstractions (probe = independent post-action query, then diff
vs ground truth; per-channel cumulative metrics; score/error-vs-horizon plots) and re-target
them from CookingWorld onto our TextQuests transcripts. Reference files to port from:
- `long-horizon-scaling/harness/probes/cooking.py` (`CookingALEProbe`, `CookingDriftProbe`)
- `long-horizon-scaling/experiments/analysis/.../parse_ablation_results.py` (channel metrics)
- `long-horizon-scaling/experiments/analysis/.../judge_drift.py` (drift LLM judge)

Dependency: everything ALE/belief related needs the ground-truth field (§0 blocker). We
decouple by fixing the **format spec now** (§0), so metric/probe work codes against the spec
in parallel with the runner patch, validated on synthetic transcripts until real ones exist.

### Subagent split (4 parallel workers, disjoint files)

- **W1 — Ground-truth logging (BLOCKER).** Patch `textquests/play_textquests.py` (log dict
  ~L173) + `textquests/src/textquests_env.py` to emit the §0 `ground_truth` field every step
  from Jericho (`env.env.get_inventory()`, `get_player_location()`). Back-compatible: absent
  field must not break the converter. Verify by running ~3 steps and dumping the JSON.
- **W2 — Rubric metrics module** `textquests/scout/rubric.py` (NEW). Port the 4 channels
  (accepted-local-error, drift, integration, budget/liveness) + interface, adapted to the
  TextQuests JSON schema and the §0 ground_truth field. Emit per-step records
  `{channel, evidence_span, justification, confidence}` and per-run rollups. Unit-test on a
  synthetic transcript. No live API.
- **W3 — Belief-diff probe** `textquests/scout/belief_probe.py` (NEW). Port `CookingALEProbe`
  as an independent post-action probe for Zork: given history up to step t, ask the model to
  restate inventory/location, diff against §0 ground truth, count false-pos/false-neg = ALE.
  Offline (replay transcript); guard the LLM call behind a flag so it can dry-run.
- **W4 — Token-budget plots** `textquests/scout/plots.py` (NEW). Coz's two plots from
  `token_usage`: (A) log(token budget) vs score, (B) log(token budget) vs cumulative rubric
  errors. Works on the single existing run now; parameterized to fan across runs/harnesses
  later. Lines = harness config.

Sequenced after W1 lands: re-run collection (Wishbringer + 2-3 Claude tiers + one cheap
model, multi-seed) so W2/W3/W4 have real ground-truth transcripts. Then hand-label a
stratified slice as the rubric validation set.
