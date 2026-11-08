# CLAUDE.md — long-horizon harness research

This file is the standing brief for agents working in this repo without a human in the loop.
Read it fully before doing anything. It tells you what the project is trying to establish,
what is already settled, what is open, and which rules you follow when nobody is watching.
Update the `## Status` and `## Open decisions` sections at the end of every session; leave
the rest alone unless a result changes it.

---

## 1. What this project is

**Research question.** Do specific harness mechanisms reduce specific failure channels in
long-horizon LLM agents, at matched compute, and do those effects survive stronger models?

**Why it matters.** Frontier labs are shipping harnesses (Google's Stellar Colosseum, Aletheia,
LeanMarathon, Danus) built on intuitions about how long runs fail: unsupported claims propagate,
definitions drift across sections, failed routes get retried. Those systems report aggregate
scores for the whole bundle, rarely report token counts, and their own authors say they cannot
isolate which component did the work or whether a gain came from structure or from volume
(Colosseum §2.3, §8.1, §8.2 say this in so many words). An aggregate score says an agent failed,
never why. This project decomposes "why" into channels, attaches one mechanism to each, and
measures whether the mechanism moves its channel.

**Why games.** Text games give ground-truth state, determinism, replay, cheap runs, and a known
solution. They are a proxy for long-horizon capability, never the object of study. Everything
we claim should be framed as a claim about mechanisms and channels, since a better harness for
Zork is worth little on its own.

**Who it is for.** Advisor and likely reviewer is Cozmin Ududec (Head of Science of Evaluation,
UK AISI). The audience for the result is evaluation science: if a harness can swing measured
capability this much, any capability estimate is conditional on elicitation effort, and the
useful output is a way to predict which failures are harness-fixable and which are model-limited.

**Collaborators.** Sam (`dignissimus/long-horizon-scaling`, main framework, CookingWorld
ablations), Utsab (branching simulator, runtime ALE detector, TextQuests mechanisms),
Robert (BlueDot stakeholder, wants a GPU-usage narrative), Ammielle (owner of this repo's
workstreams: TextQuests/Zork pipeline, Scout transcript analysis, annotation rubric, belief
probe, plots A to E, results and writing).

---

## 2. The framework

### Failure channels
| Channel | Definition (local test, never outcome-based) | Observable? |
|---|---|---|
| Accepted-local-error, first occurrence (ALE-first) | agent acts on a belief that is false against ground-truth state, and no earlier observation in the run contradicted that belief | yes, via ground truth |
| Accepted-local-error, persisted (ALE-persisted) | at step t an observation contradicts belief b; at step t+k (k ≥ 1) the agent still acts on b. Report the count and the correction latency k | yes, via ground truth plus belief probe |
| Control-path drift | agent loses the goal or current subgoal | weakly; needs a judge |
| Integration / synthesis | agent holds all prerequisites and never combines them | yes, via oracle |
| Budget / liveness | loops, stalls, burns budget without progress | yes, from behaviour |
| Interface (control) | cannot produce a parser-accepted command | yes; expected to vanish on capable models |

**Why ALE is split (added 2026-11-07).** The guess-then-harden failure (agent resolves
uncertainty by guessing, folds the guess into a plan, and later actions compound the error
instead of correcting it) is only half covered by a per-step ALE count. The first guess is
ALE-first, and if a check was available and skipped it is also an info_seek miss (M1's target).
The hardening is what ALE-persisted measures: a false belief that survives a contradicting
observation. This is a different thing from drift. Drift is a correct world model with a lost
goal; ALE-persisted is a retained goal pursued from a stale premise. Lumping them hides which
mechanism applies (M2 for drift, M1 or a belief-revision check for ALE-persisted).
Amplification (how much downstream progress the stale premise cost) is a derived, counterfactual
quantity, measured by forking at the first ALE step, correcting the belief, and replaying
(Utsab's branching simulator). It is not a channel.
Canonical example: the Wishbringer RESTART, where every config hallucinated being fired and
restarted between steps 127 and 210 **[reported]**; no detector fired.
Limit: in a static game, contradicting observations only arrive when the agent moves, so the
denominator for ALE-persisted (contradiction events) is small and uncontrolled. See
`## Open decisions` on a perturbation axis.

### Mechanisms and targets
| Mechanism | Target channel | Status in code |
|---|---|---|
| M1 information-seeking (lead; off / prompted / enforced) | ALE-first, ALE-persisted, drift | designed, not run as a clean switch |
| M2 memory / context | drift | partial |
| M3 state externalization (map, inventory, fact store) | ALE-first | built on CookingWorld; blocked on TextQuests until ground truth exists |
| M4 adaptive compute | budget/liveness | not built |
| M5 action templating (control) | interface | built; used as baseline floor |
| M6 planning / synthesis | integration | built; strongest effect so far |
| M7 world model | ALE-first, ALE-persisted | built on CookingWorld (Sam) |

### Central bets (if either fails, the paper changes)
- **C1 frontier relevance.** Mechanisms must be a lever on capable models, not a weak-model crutch.
- **C2 channel-specific signatures.** Mechanisms must move specific channels. If everything rises together the decomposition adds nothing over "tools help".

### Research questions
- RQ1: can the channels be measured reliably? (judge agreement, gold set, ground truth)
- RQ2: does each mechanism move its channel at matched compute? (core)
- RQ3: do effects survive across model generations? Sub-question (Nov 2026): which channels
  expire as models improve and which persist. Prediction, borrowed from Queen & Zou's shelf-life
  result (capability failures with a checkable right answer fade, tendencies persist): interface,
  liveness and ALE-first expire fastest; drift and ALE-persisted persist.
- RQ4 (stretch): does a baseline channel profile predict which mechanism a model needs?
- RQ5 (new, Oct 2026): is the value of a mechanism in reducing per-run error, or in decorrelating errors across runs? Colosseum's biggest single gain (54% to 71%) came from choosing between two runs with complementary failures. Our channel × mechanism grid only measures the former.

---

## 3. What is established (with provenance)

Mark every number you carry forward as **[verified]** (you read the artifact), **[reported]**
(came from a summary), or **[unverified]** (inferred). Never promote a number silently.

**CookingWorld, flash-lite, 6 configs × 10 seeds (`flash_lite_eval_20260627_09354`) [verified]**
- Planning (M6) is the main driver: best condition m3-m5-m6 final score 0.508 vs baseline-m5 0.335, about 1.5x. The earlier "doubles" claim compared against the worst non-planning config and was retracted.
- M6 conditions spend roughly 5x the tokens of baseline. Compute is not equalised. Per-step tokens were not logged, so Plot A's x axis is steps, labelled as a proxy.
- Per-turn ALE looks worse under planning (about 5.2 vs 3.5), but per-opportunity ALE (Plot E-b) puts state and world-model harnesses in a lower band than baseline. The per-turn effect was mostly exposure. This is a reinterpretation, not an invalidation; keep that wording.
- All existing ALE numbers are undifferentiated (first plus persisted). Do not relabel them retroactively; the split applies to new collection and to any replay of old transcripts through the probe.
- Survivorship bias affects Plots A, B, C: past step ~30 only 1 to 4 runs per config remain alive. Plot D shows n(alive).
- Inventory state cut forgetting from 42% to 34% (one-pager Fig 2, strongest figure).
- Drift: two measurement attempts failed in opposite directions. The LLM judge subsamples at most 5 of up to 19 probes per run; the Zork heuristic proxy fires on 39% of steps. Report drift as X-of-Y judged, qualitatively. This is itself an RQ1 finding.
- ALE is ~99% spatial (room/inventory), almost no recipe ALE. Liveness ≈ 0 under M5. Interface errors persist (18 to 31 per run) despite M5.
- Domain-knowledge failure (grill/barbecue excerpt): a case where the harness, not the model, produced the failure. Strongest qualitative example for the eval-science framing.

**Methodology decisions already taken**
- Dual-wrapper: Zork I and Wishbringer exist in both TALES (stock ROMs, free ground-truth introspection) and TextQuests (instrumented ROMs, harm labels, checkpoint progress). Use TALES for ground truth and TextQuests for progress/harm. This dissolves the save/restore patch blocker.
- Rubric before transcripts: freeze annotation decision rules before generating transcripts that will be labelled.
- The independent post-action belief probe (query belief, diff vs ground truth) is the priority variant, since it isolates memory failure from prompt artifacts. Sam's `CookingALEProbe` and Utsab's runtime detector are the two existing implementations; port, don't rebuild. The probe is also the instrument for ALE-persisted: probe every step, mark false beliefs, find the first contradicting observation, count steps until the belief is corrected or the run ends (right-censored).
- ALE-persisted stays a sub-label of ALE in the rubric schema (`channel: ale`, `subtype: first | persisted`, plus `contradiction_step` and `latency` for persisted) rather than a seventh channel, until the team decides otherwise. Keeps ALE totals comparable with the CookingWorld numbers.
- M6 suppresses drift but does not prevent exhaustive no-map search, so M3 is the logical next mechanism.
- External corroboration (e.g. OpenAI ARC-AGI-3 compaction result) supports the broad "harness design matters" thesis, not any per-channel sub-claim. Keep that distinction when citing.

---

## 4. Environments and tooling

- Environments: Jericho/Frotz (Zork I, Wishbringer) via TextQuests and TALES; TextWorldExpress/CookingWorld (Sam's framework); TALES suite (122 games) as the broad statistical set.
- Analysis: INSPECT Scout scanners (`scout_report/`, `textquests/scout/`), `cooking_rubric.py`, `rubric.py`, `judge_drift.py`, `belief_probe.py`, `plots.py`, `report.py`. Unified per-step JSON transcript store; `convert.py` ingests JSON and md.
- Gotchas already learned: `.eval` files are zstd-compressed; sample metadata lives under `transcript.metadata["sample_metadata"]`; Jericho binds its object database on ROM MD5, so instrumented TextQuests ROMs return None for inventory/location.
- Two pipelines exist (CookingWorld Scout path, TextQuests scout path). A single entrypoint that reports either is wanted.
- Known-unbuilt: per-step token logging in `step_log` (see Status: Utsab's harness may already have it); the rubric as a labelling instrument (schema `{channel, subtype, evidence_span, justification, confidence}`, `other` bucket, hand-labelled validation slice); the ALE-persisted detector (contradiction finder plus latency counter over probe output); Coz's two token-budget plots on real token data; Wishbringer + Claude tiers + multi-seed collection; automated resume on degeneration.

---

## 5. Priorities (ordered; work top-down unless blocked)

1. **Per-step token logging.** Add input/cache/reasoning/output tokens to `step_log`. Everything about compute control depends on this. Without it RQ2 cannot be answered and C4 stays open. Settle the definition question (which token classes count) by proposing a default and flagging it, since the team has not decided. First check whether Utsab's `steps[].tokens` already covers this; if so, this item becomes "port and reconcile".
2. **Rubric as a document.** Write `scout_report/RUBRIC.md`: per channel, plain definition, exact decision rule, deterministic vs LLM-judged, ground truth required, known caveats. Include the ALE first/persisted split with its decision rule and the latency definition. Reconcile the 4-channel spec with the 6-channel code (info_seek added, ALE split spatial/recipe). This is the reference for hand-labelling and the gate for everything downstream.
3. **No-harness baseline transcripts** on Zork I and Wishbringer via TALES wrapper (ground truth) with `ground_truth` logged every step. Multi-seed. This precedes any new Scout scanners.
4. **Belief probe on Zork** ported from `CookingALEProbe`, offline replay, LLM call behind a flag. Output per run: ALE-first count, ALE-persisted count, correction-latency distribution, number of contradiction events (the denominator).
5. **Hand-labelled validation slice.** Stratified sample, two-pass, frozen decision rules, report judge-vs-human agreement per channel. Drift agreement is expected to be poor; if so, scope drift to a qualitative read and say so.
6. **Compute-matched comparison.** Fixed-compute axis (mechanism at baseline token budget) and budget-sweep axis (baseline vs best mechanism across budgets). Utsab's branching simulator may be the matched-comparison method; do not duplicate his work, coordinate.
7. **Error-decorrelation measurement (RQ5).** For runs of the same condition across seeds and across conditions, compute joint failure vs product of marginals at the checkpoint/subgoal level, a coverage curve against the independence prediction, and a mixed-effects decomposition of variance into item vs seed. Same-condition multi-seed correlation is the reference level. Conditional on joint failure, check whether both runs fail through the same channel at the same place; this is the measure Colosseum cannot produce. ALE-persisted failures shared across seeds (Wishbringer RESTART pattern) are the expected example of perfectly correlated, non-ensemblable failure.
8. **Cross-model (RQ3).** Only after 1 to 5 are in place. Models: gpt-oss-120b, flash-lite, 2 to 3 Claude tiers, plus at least one current open-weight model. Open question whether gpt-oss-120b has enough long-context coherence to be the baseline model. Report per-channel rate against model release date.

---

## 6. Standing rules for autonomous work

**Scope you may act on alone**
- Analysis code, plots, rubric documents, transcript generation within an approved budget, literature extraction, draft write-ups marked as drafts.

**Scope you must stop and flag (do the prep work, write the decision up, do not execute)**
- Any dataset-level or environment-level decision (which game, which model is baseline, with-clues vs no-clues as a labelled axis, any perturbation axis). Ammielle brings these to the group.
- API spend beyond what the current task was scoped for. Build out run parameters and cost estimates first.
- Ownership splits with Utsab (belief-diff, branching simulator) or Sam (framework changes).
- Anything that would change a number already in the one-pager, Overleaf, or the results Google Doc.

**Provenance and framing**
- Mark [verified] / [reported] / [unverified] on every number. Surface internal conflicts rather than smoothing them.
- "Invalidated" and "reinterpreted" are different words. A result reinterpreted by a better denominator is still a result.
- Never headline a ratio next to a plot of a different quantity (mean final_score vs survivor-averaged cumulative reward vs ablation effect contribution are three different numbers).
- Steps are not tokens. Label axes accordingly until per-step tokens exist.
- When a mechanism raises success, ask whether its channel moved and whether compute was matched before writing anything stronger than "consistent with".
- External papers corroborate the thesis or a sub-claim, rarely both. Say which.
- ALE-persisted needs its denominator (contradiction events) reported next to it. A persisted count with no denominator is exposure, not a rate.

**Judge hygiene**
- Judge is blind to harness condition.
- Labels are local tests, never derived from run outcome.
- Report inter-judge and judge-vs-human agreement with every judged number.
- Where ground truth exists, score the judge against it and report that too.

**Writing style for anything that reaches a human**
- No em dashes. No "not X, it's Y" constructions.
- Direct and terse. State the finding, the denominator, and the caveat. Skip hedging preambles.
- Slack updates: short plain prose. Google Doc updates: markdown for paste.

---

## 7. How a session should run

1. Read `## Status` below and the last entry in `LOG.md` (create it if absent).
2. Pick the highest-priority item from §5 that is unblocked. If a lower item is the only unblocked one, say so in the log.
3. Before any API spend, write the planned run grid and cost to the log. If it exceeds the scoped budget, stop and flag.
4. Produce the artifact (code, plot, table, doc). Run the verification step: recompute numbers from raw logs, open the plot, check denominators and n at each x.
5. Append to `LOG.md`: date, what was done, numbers with provenance tags, what changed in `## Status`, what is blocked and on whom, what the next session should do first.
6. Update `## Status` and `## Open decisions` in this file. Keep each under 15 lines.
7. Never leave a result in the log that is not reproducible from a command in the repo.

**When stuck:** write the blocker, the two or three options you see, your recommendation and its cost, then move to the next unblocked item. Do not spin on a blocked item or invent a workaround that changes the experimental design.

**When a result contradicts §3:** do not edit §3. Write the contradiction in the log with both numbers and their provenance, and flag it at the top of `## Status`.

---

## 8. External context worth knowing

- Stellar Colosseum (Lin, Woodruff et al., arXiv 2609.15983, Sep 2026): five-stage pipeline (strategy exploration, readiness gate, DAG decomposition, parallel subproblem solving, global verification) with falsifier-paired candidates and tree aggregation. Gemini 3.1 Pro 30.3% → 54.0% on TCS-Bench; cross-model selection with Flash reaches 71.0%; oracle best-of-two 77.3%. No ablations, no token counts. Its four design motivations map onto our channels (error propagation → ALE-persisted, definition drift → integration, failed-route retention → M3). Future-work section names compute-matched evaluation and credit assignment as the open problems, which is our project. Under independence, two runs at 54% and 55% would jointly solve 79.3%; the 77.3% oracle is close to that **[unverified, own arithmetic on reported marginals]**.
- Related harnesses in the same space: Aletheia, QED, ProofCouncil, RMA, Danus, Albilich, MechMath, LeanMarathon. All bundle mechanisms; none isolate them.
- Queen & Zou, "The shelf life of LLM findings" (Nov 2026): Kaplan–Meier over 50 published claims across 20 models by release date; capability failures with a checkable answer expire (median ~15 months), tendencies persist. Method and framing transfer to RQ3 per channel.
- Dynamic or perturbed environments, for the perturbation-axis decision only: Gaia2 (ICLR 2026 oral, async consumer env, ARE platform), WildGrid (Pezeshkpour & Hruschka, Feb 2026, grid game with controlled perturbations: hazards spread, dynamics shift, teleportation), MirrorCraft (Jul 2026, paired vanilla/mirror Minecraft worlds with hidden rule changes), Learn2Play Bench (Oct 2026, new text games with counterintuitive hidden rules; reports that harness choice changes learning and cost). None has ground-truth belief state at the step level.
- Reference PDFs are indexed in `README.md` (project files). HarnessBench, LIFE harness runtime adaptation, CATTS, map-then-act, active epistemic control, TextQuests, Zork-Bench, TALES are the core set.

---

## Status (update every session)

_Last updated: 2026-11-07, Ammielle (manual) merged with agent session (see LOG.md)._

- CookingWorld 6-config analysis is complete and written up (Symposium results doc, 30 Jul). Fix list items 2 to 6 done; item 1 (real tokens on Plot A) impossible on current data.
- ALE split into first/persisted agreed (2026-11-07); in RUBRIC.md v1.1. No detector yet; existing ALE numbers are undifferentiated.
- Per-step token logging, all classes incl. reasoning, now in the TextQuests runner and the new TALES runner [verified]. Utsab's harness logs per-step `tokens` + `judge_tokens` only (no class split; `prompt_tokens` transient) [verified from repo]. Reconciliation: his totals are judge-inclusive, ours class-split; map before comparing.
- Dual-wrapper implemented: `play_tales.py` on stock ROMs (zork1, wishbringer fully supported, ground truth live) [verified], smoke-tested, converter ingests. Collection NOT launched; grid v2 + costs in LOG.md, needs sign-off.
- `scout_report/RUBRIC.md` v1.1 written and frozen (incl. ALE split, subtype schema). Token-definition default proposed in its §4, needs sign-off.
- Drift measurement is unreliable in both existing implementations; reported qualitatively.
- Belief probe: CookingWorld (Sam), runtime detector (Utsab), offline scaffold on TextQuests (dry-run default); ALE-persisted outputs (priority 4) not built.
- Models run so far: flash-lite (CookingWorld), gpt-oss-120b (Zork, degenerates past ~300 steps), claude-sonnet-5 (Utsab sweeps, single seed).
- Keys: OpenRouter valid to 2027-01-11, $50 cap; Anthropic key in root .env valid [verified]. Claude runs go through the Anthropic API, open models through OpenRouter.

## Open decisions (team, not agent)

- ROM / ground-truth route: dual-wrapper vs status-line parse + save/restore vs proxies. Leaning dual-wrapper.
- ALE-persisted: sub-label of ALE (current default) vs its own channel. Also whether latency is reported in steps or in contradiction events.
- Perturbation axis: whether to inject a small number of controlled contradictions (object moved, recipe changed mid-run in CookingWorld) to give ALE-persisted a known denominator. This is a probe for one channel, not a realism claim, and is distinct from evaluating harnesses on dynamic benchmarks (separate project).
- Belief-diff ownership split with Utsab.
- Per-step vs windowed labels for the rubric.
- Whether drift and integration need LLM judges, and judge cost / subsampling policy.
- Token definition for the compute axis (input + cache + reasoning + output, or reasoning + output only).
- Baseline model: is gpt-oss-120b adequate for long-context coherence. Which current open-weight model replaces or joins it.
- Whether Utsab's branching simulator becomes the matched-comparison method.
- With-clues vs no-clues as a labelled axis.
- Focus game: CookingWorld for power, Zork/Wishbringer for realism, or both.