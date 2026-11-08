# RUBRIC.md — failure-channel annotation rubric (document of record)

Status: v1.1, 2026-11-07. These decision rules are **frozen** as of this version.
Any change requires a version bump here and a relabel of anything labelled under the
old rules. This document is the reference for hand-labelling and the gate for every
downstream scanner, plot, and judged number.

Changelog: v1.1 adds the ALE first/persisted split (CLAUDE.md §2, agreed 2026-11-07)
and the `subtype` field in the labelling schema. v1.2 adds the operational
contradiction-event rules the detector implements (below). Nothing was labelled under
v1.0 or v1.1, so no relabel is required.

Written against the code as it exists today:

| Implementation | File | Environment |
|---|---|---|
| Rubric as Scout scanner | `scout_report/cooking_rubric.py` | CookingWorld (`.eval` logs) |
| Rubric as per-step labeller | `base-project/textquests/scout/rubric.py` | TextQuests/Zork (`.json` transcripts) |
| Independent belief probe | `base-project/textquests/scout/belief_probe.py` | TextQuests (offline replay, LLM behind `--live`) |
| Drift LLM judge | ported from `judge_drift.py` into `cooking_rubric.py` | CookingWorld |

## 1. Reconciliation: 4-channel spec vs 6-channel code

The framework (CLAUDE.md §2) defines four failure channels plus one control channel.
The code measures six quantities. The mapping:

| Spec channel | Code quantity | Why they differ |
|---|---|---|
| Accepted-local-error (ALE), first + persisted | `ale_spatial` + `ale_recipe` | Code splits by probe `question_id` (`recipe_*` vs the rest). Spatial dominates (~99% in CookingWorld). Keep the split; report both. The first/persisted subtype (§2.1) has **no detector yet**; all code-emitted ALE counts are undifferentiated and must be reported as such. |
| Control-path drift | `drift` | Same channel, two implementations (LLM judge, heuristic proxy), both unreliable. See §2.5. |
| Integration / synthesis | `integration` | Same channel; both implementations are labelled heuristics. |
| Budget / liveness | `liveness` | Same channel. |
| Interface (control) | `interface` | Same channel. Control floor, not a finding. |
| (none) | `info_seek` | **Not a failure channel.** It counts entering a new room without looking around, which is a behavioural correlate of mechanism M1 (information-seeking). Keep it in reports as an auxiliary behaviour metric; never present it as a failure channel, and never hand-label it. |

Rule carried from CLAUDE.md: every label is a **local test on the step**, never derived
from run outcome, and any judge is blind to harness condition.

## 2. Channels

### 2.1 Accepted-local-error (ALE)

**Definition.** The agent holds a belief about world state (location, inventory,
container contents, recipe) that is false against ground truth at that step. Acting on
it is what makes the error "accepted". This is a belief test, never a parser test:
a rejected command is interface, a false belief is ALE.

**Decision rules (two, by source of the stated belief):**
- *Probe-based (CookingWorld, and the Zork belief probe).* An independent post-action
  probe asks the model to state inventory/rooms/containers/recipe. Each stated item
  list is diffed against the ground-truth item list after `clean_item_name`
  normalisation (lowercase, strip punctuation and articles). One ALE unit = one
  hallucinated item (false positive) or one forgotten item (false negative)
  (`calculate_ale`). 7 sub-questions per probe step, probes every 5 steps, so one
  probe step can add many units.
- *Reasoning-extraction (TextQuests `rubric.py::ale_channel`).* Regexes extract a
  stated location ("I am in ...") or stated inventory ("I am carrying ...") from the
  step's reasoning; location mismatch (no substring containment either way after
  normalisation) counts 1, inventory diffs count per item. Steps with no extractable
  statement are **not evaluable**, not zero.

**Subtypes (v1.1, per CLAUDE.md §2):**
- *ALE-first.* A false-belief event where no earlier observation in the run
  contradicted that belief. The agent guessed wrong with nothing telling it so.
- *ALE-persisted.* An observation at step t contradicts belief b, and at step t+k
  (k >= 1) the agent still acts on b. Record `contradiction_step` (t), `latency`
  (k, steps from contradiction to correction; right-censored at end of run), and the
  run's **contradiction-event count as the denominator**. A persisted count with no
  denominator is exposure, not a rate. ALE-persisted is distinct from drift: drift is
  a correct world model with a lost goal; persisted is a retained goal pursued from a
  stale premise. Canonical example: the Wishbringer RESTART (all 8 configs
  hallucinated being fired and restarted, steps 127 to 210) [reported].
- Measurement instrument: the independent belief probe run **every step** on offline
  replay (priority 4 outputs: ALE-first count, ALE-persisted count, latency
  distribution, contradiction events). Detector implemented in
  `base-project/textquests/scout/belief_probe.py::analyze_persistence` (v1.2).
  Operational contradiction-event rules: *inventory* = the agent issued an inventory
  command or the observation shows a full listing ("you are carrying" / "you are
  holding" / "you are empty-handed"); *location* = a look command, or ground-truth
  location changed from the previous step (the game prints the room on arrival).
  A hallucinated-item error qualifies as persisted only if the item was absent at
  the revealing event; a forgotten-item error only if it was present. Latency runs
  from the qualifying event to the first error-free later probe, right-censored at
  the last probe. Hand-labelling uses the same rules.
- Amplification (downstream progress lost to the stale premise) is a derived
  counterfactual measured by branching replay (Utsab). It is not a channel and is
  never hand-labelled.

**Type.** Deterministic given the probe completion or reasoning text; the
contradiction finder for persisted requires the per-step observation log.
**Ground truth required.** Yes (`ground_truth` field per step; Jericho object tree or
probe metadata). Without it the channel is unmeasurable, never approximated.
**Caveats.** Probe-based ALE measures elicited belief, which is why the independent
post-action probe is the priority variant (isolates memory failure from prompt
artifacts). Reasoning-extraction under-fires on unmatched phrasings and can over-fire
on incidental "I have". Denominators matter: per-turn ALE and per-opportunity ALE
(cumulative ALE over cumulative ground-truth items queried) tell different stories;
always state which one a number uses. The per-opportunity denominator was added
2026-07-30 after review, post hoc for the CookingWorld batch; from this version on it
is the frozen default for cross-condition comparisons.

### 2.2 Interface (control channel)

**Definition.** The agent cannot produce a command the parser accepts.
**Decision rules.** CookingWorld: `action not in valid_actions` for the step.
TextQuests: next observation contains one of the 6 `PARSER_REJECTION_PHRASES`
("i don't understand that", "that sentence isn't one i recognize", "you can't see any
such thing", "there is no", "i don't know the word", "what do you want to").
**Type.** Deterministic. **Ground truth.** No.
**Caveats.** The phrase list is a proxy; "there is no" can also appear in ordinary
prose. Expected to shrink on capable models; treat as the elicitation floor, not a
finding. The two rules (valid-action set vs phrase match) are different measurements
and must not be pooled across environments.

### 2.3 Budget / liveness

**Definition.** The agent burns budget without progress: loops or stalls.
**Decision rule.** Identical action 4 times in a row (`LIVENESS_WINDOW = 4`), or
(TextQuests only) 4 consecutive parser-rejected actions.
**Type.** Deterministic. **Ground truth.** No.
**Caveats.** Window of 4 is a convention, frozen here. Crashes and repeated
generation failures (truncated JSON, degeneration) are logged as liveness events, not
dropped: they are data. Liveness was ~0 in CookingWorld under M5; the channel exists
mainly for no-template and long-horizon settings.

### 2.4 Integration / synthesis

**Definition.** The agent holds all prerequisites and fails to combine them.
**Decision rules (both labelled heuristics):**
- CookingWorld: an `integration` probe elicits a numbered 3-step plan; if the plan's
  first action is not executed within the `[probe_step .. probe_step+3]` action window
  (loose containment match), +1 integration error. Measures plan-follow-through.
- TextQuests: parser accepted the action, observation shows a no-effect phrase
  ("nothing happens", ...), and the step's reasoning has >= 6 content words. Weakest
  signal in the module, documented as such in the code.
**Type.** Heuristic, deterministic to compute. **Ground truth.** None exists for this
channel in either schema.
**Caveats.** The two heuristics measure different things (ignoring one's own plan vs
ineffectual-but-parsed actions) and must not be pooled. The CookingWorld oracle-style
definition ("held all prerequisites") is only approximated. A real measurement likely
needs an LLM judge; that is an open team decision, not something to backfill silently.

### 2.5 Control-path drift

**Definition.** The agent loses the goal or current subgoal.
**Decision rules (two, both unreliable in opposite directions):**
- *LLM judge* (CookingWorld): for each `drift` probe, a judge model sees the game goal
  and the agent's stated intentions and returns 0/1. Cost cap `MAX_DRIFT_JUDGE = 5`
  probes per run, evenly sampled from up to ~19. A skipped judge is "not judged",
  never 0.
- *Heuristic proxy* (TextQuests): progress flat over a 10-step window AND Jaccard
  word-overlap between the window-start reasoning and current reasoning < 0.15.
  Fired on 39% of Zork steps, which is over-firing.
**Type.** LLM-judged (primary) or heuristic (flagging only).
**Ground truth.** No. **Caveats.** Report only as **X flagged of Y judged** with the
sampling cap stated. The judged CookingWorld numbers were baseline 0/30, planning
4-5 of ~38. Until judge-vs-human agreement is measured (priority 5), drift stays a
qualitative read. That unreliability is itself an RQ1 finding; do not bury it.

## 3. The labelling instrument (for hand-labelling)

Per-step record, exactly this schema (already emitted by
`rubric.py::score_transcript`):

```json
{"step": 12, "channel": "ale", "subtype": "persisted", "contradiction_step": 7,
 "latency": 5, "evidence_span": "...", "justification": "...", "confidence": "high"}
```

- `subtype`: only for `channel: ale`, one of `first` | `persisted`; `contradiction_step`
  and `latency` only for `persisted`. ALE-persisted stays a sub-label, not a seventh
  channel, so ALE totals remain comparable with the CookingWorld numbers (team may
  revisit). In a static game contradictions only arrive when the agent moves, so the
  persisted denominator is small and uncontrolled; the perturbation axis that would
  fix this is an open team decision, not something to improvise.
- `channel`: one of `ale`, `interface`, `liveness`, `integration`, `drift`, `other`,
  or null (no failure this step). At most one primary channel per step; when two
  co-occur, interface wins over liveness, ALE wins over drift, and the second goes in
  the justification.
- `other`: failures that fit no channel (e.g. the grill/barbecue domain-knowledge
  case). Review the `other` bucket before any schema change.
- `evidence_span`: verbatim quote from the step. A label with no quotable span is not
  a label.
- `confidence`: high / medium / low. Low-confidence labels are kept and reported, not
  silently dropped.
- Labels are per-step. Windowed (50-step) labels are an open team decision; do not
  mix the two in one dataset.

**Hand-labelling protocol (priority 5):** stratified sample across games, conditions,
and run phase (early/mid/late); two passes by the same annotator with a wash-out gap
until a second annotator exists; rules frozen before labelling starts (this version);
report judge-vs-human agreement per channel, and judge-vs-ground-truth wherever
ground truth exists. Expect drift agreement to be poor; if so, scope drift to a
qualitative read and say so in anything that reports it.

## 4. Compute axis (token definition) — proposed default, flagged

Per-step logging (added 2026-11-07 to the TextQuests runner) records all classes:
`input_tokens`, `cached_tokens`, `output_tokens`, `reasoning_tokens`, `total_tokens`,
summed across retries within a step, plus running totals. Provider semantics differ
(OpenAI-compatible: cached is a subset of input, reasoning a subset of output;
Anthropic: cache reads are disjoint from input, thinking is inside output), and the
raw fields are logged so any definition can be recomputed.

**Proposed default for plots, pending team sign-off:** billed-token total = input
+ cache reads (where disjoint) + output, i.e. everything the provider charges for.
Rationale: it is the only definition comparable across providers and it is what a
budget cap would bind on. Report reasoning+output as a sensitivity axis where
reasoning counts exist. This is an open team decision (CLAUDE.md); flag the choice in
every figure caption until it is settled.
