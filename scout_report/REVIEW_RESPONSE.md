# Response to the plots/rubric review

Answers verified against the actual code (`scout_report/plots.py`, `cooking_rubric.py`,
`report.py`, `plots_rubric.py`) and re-run on the raw eval logs
(`flash_lite_eval_20260627_09354/`, 6 configs × 10 seeds), 2026-07-30.

**Naming note:** the files are under `scout_report/`, not `scout/`. The rubric lives in
`cooking_rubric.py` (there is no `rubric.py` in this tree; that name referred to an earlier
TextQuests-side module).

**Headline:** the review is largely correct. Three findings **change conclusions** — (1)
per-step tokens don't exist so the x-axis can't be fixed with this data, (2) the plot tails
are survivorship over 1–4 runs, and (3) the "doubles score" claim is ~1.5× against the real
baseline, which was dropped from the current table. The rest tighten the figures.

---

## Git updates just pulled

- **long-horizon (Utsab): 7 new commits.** Built out the full parallel harness: new
  `channels/` (`drift.py` +247, `budget.py`, `integration.py`, revamped `ale.py`) and
  `mechanisms/` (`memory.py`, `planning.py`, `state_ext.py`, `action_templating.py`,
  `adaptive.py`, `info_seeking.py`) — i.e. M1–M6 now implemented on the TextQuests side,
  plus `run_mechanism_comparison.py`, a `tests/` file (+294), and new 100-step experiment
  logs/plots. This mirrors dignissimus's mechanism set onto Jericho games.
- **long-horizon-scaling (dignissimus): no change** since last pull (HEAD `93d3adf`).

---

## The A/B/C fixes

### 1. Real tokens on the x axis — **can't, and here's the proof**
Per-step token counts **are not in the schema.** A telemetry step has exactly:
`['step','action_sent','observation_received','ground_truth_state','reward','probe_results','valid_actions']`
— no token field. The only token data is **run-wide**, in `sample.model_usage`
(e.g. `total_tokens: 94,655` for one baseline run). So there is nowhere to pull per-step
tokens from; the earlier "distribute run-wide totals by text-length weight" was an
approximation, and the current plots use **cumulative steps** as the proxy.

**Verdict:** genuinely not logged — not a silent fallback we can swap out. To get a real
token x-axis we'd have to **re-run the experiments** with per-step token logging added to
the harness's `step_log` (one line in `harness_orchestrator`). Recommend we do that for the
next batch; for *this* batch, steps is the only honest axis and I'll label it as an explicit
proxy, not "budget."

### 2. Survivorship — **confirmed, and worse than it looks**
`_mean_curve` averages only over runs still alive at each step and truncates a line once
fewer than `MIN_RUNS=3` remain. Runs that reached step 100, per config:

| config | runs reaching ~100 steps (of 10) |
|---|---|
| baseline-m5 | **1** |
| m3-m5 | 2 |
| m7-m5 | 1 |
| m5-m6 | 4 |
| m3-m5-m6 | 3 |
| m7-m5-m6 | 4 |

So the entire right-hand side of Plots A/B — where the "score plateaus, errors climb" story
lives — is **1–4 runs per line, not 10.** And yes, a survivor-averaged cumulative-score line
**can decrease** when a high-scoring run drops out of the survivor set (exactly the
0.39→0.22 you saw).

**Fix (agreed, additive):** add an `n(alive)` trace under Plots A/B, and a
**survivor-conditioned** variant restricted to the runs that reached max step, so comparisons
are at matched exposure. I'll leave the originals untouched.

### 3. Normalise the error counts — **denominator exists; can do both (a) and (b)**
Every step carries `ground_truth_state`, and each `ale` probe carries a `ground_truth` list.
Summing those lists per probe step gives the **number of ground-truth items queried** — a
valid denominator. So:
- (a) errors per step — trivial.
- (b) errors per known-item-opportunity — **the denominator is available**, so this is doable
  (= cumulative ALE ÷ cumulative ground-truth items queried).

Will add both as variants and keep the raw version.

### 4. ALE unit + reconcile the two tables — **confirmed: survivorship, exactly your hypothesis**
**One ALE unit** (`calculate_ale`): a single **item-level belief mismatch** — a hallucinated
item (false positive) or a forgotten item (false negative). It is computed **per sub-question**
and there are **7 ale sub-questions per probe step** (inventory, rooms, containers, recipe
ingredients/directions), with probes firing **every 5 steps**. So a probe step can add many
units at once — that's why cumulative ALE reaches the hundreds. It is *not* per-step binary.

**Reconciliation (both numbers are right; different aggregations):**

| config | Table `ALE` = mean over **all 10** runs | Plot B endpoint = mean over **survivors to step 100** |
|---|---|---|
| baseline-m5 | 97.6 | 477 |
| m5-m6 | 287.4 | 582 |
| m3-m5-m6 | 249.7 | 626 |
| m7-m5-m6 | 253.4 | 434 |

The table (`report.py`: `mean(total_ale)` over all rows) **matches TEAM_UPDATE** (98/287/250/253).
The plot's ~600 endpoint is the survivor mean at step 100. Your hypothesis is **correct**: the
table includes early deaths (low ALE), the plot tail is the few long survivors (high ALE).

**(Correction to an earlier draft):** I initially flagged the spatial-vs-recipe split as
broken, but that was an error in my verification script (it read `id`, which is `None`, not
`question_id`). The probe field is **`question_id`** and it is populated
(`recipe_ingredients`, `recipe_directions`, `inventory`, `room_*`, `container_*`), and
`cooking_rubric.py` correctly reads `pr.get("question_id", ...)` first — so the split
**works**. `ale_recipe` is genuinely small (~0.3–1.6) because only 2 of the 7 sub-questions
are recipe-related and the agent gets those right more often; `ale_spatial` dominates for
real, not by mislabeling. No bug.

### 5. Split the drift axis + drift denominator — **confirmed**
- **Dual axis:** agreed, 0–600 vs 0–1.4 on one figure is unreadable. Will split drift into its
  own figure (and I already added a `plot_c` drift panel on its own scale).
- **Denominator:** `_judge_drift` does `_even_sample(drift_probes, MAX_DRIFT_JUDGE=5)` then
  `sum(scores)`. A 100-step run has **19 drift probes but only 5 are judged**; short runs judge
  all they have (1 of 1). So the absolute count is out of a **tiny, run-length-dependent
  denominator** — not comparable across runs. You're right: it must be reported as
  **"X of Y judged"** (or a rate), and the note should state we sample ≤5 of up to ~19 probes.
  I'll surface `n_drift_probes`, `n_judged`, and the fraction per run (all already stored except
  I'll add `n_judged`).

---

## The questions that change the paper

### The baseline row — **you're right, and it's currently missing**
- The table in `TEAM_UPDATE.md` shows **5 rows but the study is 6 configs / 60 runs.** The
  missing row is **`baseline-m5`** (M5 valid-move list only) — it was dropped from the current
  table. It must go back.
- **Score column definition:** `final_score` = the environment's cumulative game score at end
  of run (from `harness_scorer`), and `report.py` reports the **mean over the 10 seeds** — *not*
  a survivor-conditioned or cumulative-curve number. (Plot A's line is a *different* quantity:
  survivor-averaged cumulative reward, which is why its endpoint doesn't equal the table.)
- **The doubling claim (recomputed from raw logs):**
  - baseline-m5 = **0.335**, best planning (m3-m5-m6) = **0.508**.
  - best / baseline = **1.52×** (+0.17, i.e. ~+52%).
  - best / *worst* non-planning (m3-m5 = 0.263) = **1.93×**.
  - So "planning roughly **doubles** score" is only true against the *worst* non-planning
    config. Against the actual baseline it's **~1.5×**. Headline should be
    **"planning adds ~0.17 (≈1.5×) over baseline,"** not "doubles." I recommend fixing this in
    TEAM_UPDATE and restoring the baseline row.

### The ground-truth / cross-suite gap — **confirmed CookingWorld-only**
All of Plots A/B/C and the whole `cooking_rubric` scorecard are **CookingWorld
(TextWorldExpress) only.** The TextQuests/Zork ALE channel is **still empty** — Jericho's
object DB is unbound on the jiminy-cricket ROMs (Utsab's new `channels/env_checker.py` works
around it with text probes, but that's a *separate* pipeline and hasn't been run through these
plots). **No cross-suite numbers are mixed here**, and none should be presented as one dataset.

### Interpreter / real rubric vs fallback proxy — **real rubric, confirmed**
The current `plot_a/b/c.png` were generated by **`.venv-inspect/bin/python` (Python 3.12)**,
and `plots.py`/`plots_rubric.py` import **`calculate_ale` directly from `cooking_rubric.py`** and
recompute channels from telemetry. There is **no fallback-proxy path** in the current plot
scripts. The 3.8/matplotlib-only situation that forced a proxy during the overnight run no
longer applies — `.venv-inspect` has both inspect and matplotlib on 3.12, and these plots use
the actual rubric logic.

### The two "65"s — **I overstated that; treat as NOT independent corroboration**
Honest correction: the overnight W4 "proxy" and the W2 rubric were **different code paths**
(W2 interface = `action ∉ valid_actions`; W4 proxy = parser-rejection *phrase* matching +
liveness), so they don't literally share a function — but they **measure overlapping
phenomena** (invalid commands), and an exact 65 = 65 on a noisy quantity computed two
different ways is more likely coincidence-or-same-underlying-events than a meaningful
independent check. I should not have called it a consistency check. The number that matters
(`interface` in the current report) comes solely from the real rubric's `action ∉
valid_actions` rule.

---

## Bottom line

| Point | Status | Changes a conclusion? |
|---|---|---|
| 1. Real tokens on x-axis | **Not possible** with this data (not logged); needs re-run | Yes — "budget" axis is really steps |
| 2. Survivorship | **Confirmed**; tails are 1–4 runs | Yes — weakens the plateau story |
| 3. Normalise errors | Denominator exists; will add (a)+(b) | Tightens |
| 4. ALE unit / table vs plot | **Confirmed** survivorship (recipe-split is fine; my earlier bug claim retracted) | Tightens |
| 5. Drift denominator | **Confirmed**; report as "X of Y judged" | Yes — rare-vs-blind now distinguishable |
| Baseline row + doubling | **Confirmed** missing; it's ~1.5×, not 2× | **Yes — the headline** |
| CookingWorld-only | **Confirmed**; no TextQuests ALE yet | Prevents a cross-suite error |
| Interpreter / real rubric | **Confirmed** real rubric, 3.12 | No (reassurance) |
| The two 65s | **Overstated**; not independent | No (retract the claim) |

The two that flip headlines are **#1 (call the axis "steps," not "budget")** and the
**baseline row (planning is ~1.5×, not 2×)**.

---

## What was implemented (2026-07-30)

All acted on except #1, which the data can't support:

- **Baseline row restored** in `TEAM_UPDATE.md`, headline corrected to **~1.5× (+0.17)**,
  Score column defined ("game's own score at end, averaged over 10 tries").
- **Axis relabelled** everywhere to `cumulative turns (log) — proxy for effort, NOT tokens`
  (`XLABEL` in `plots.py`). #1 can't be done without re-running with per-step token logging.
- **Survivorship figure** added — `plot_d_survivorship.png`: left = runs alive at each turn
  (drops to 1–4 of 10); right = ALE for survivors reaching turn 95+ (matched exposure), which
  shows the raw ALE gaps are mostly survivorship. `runs_reaching_cap` column added to the report.
- **Normalized figure** added — `plot_e_normalized.png`: (a) ALE per turn, (b) ALE per
  ground-truth item queried (denominator confirmed to exist in the schema).
- **Drift split out of Plot B** (Plot B is ALE-only again; drift keeps its own-scale panel in
  `plot_c`), and **drift reported as a rate**: report now prints `drift_flagged/judged` and
  `drift_rate` (e.g. planning ≈ 4–5 flags / ~38 judged ≈ 9–13%, baseline 0/30 = 0%).
- **TEAM_UPDATE caveats added**: axis-is-turns-not-tokens, and "only 1–4 of 10 runs reach the
  cap — don't over-read the chart tails."
- Recipe/spatial split **confirmed working** (my earlier bug claim retracted above).

Not changed: the experiments themselves (needed for #1 real tokens) — flagged for the next batch.
