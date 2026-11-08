# Long-Horizon Harness Project: Where It Stands and Where It Can Go

The project's strongest move beyond mechanism ablations is to turn its per-step, ground-truth text-game data into a predictive eval-science instrument: a survival (hazard) model of long-horizon failure with channels as competing risks, used to forecast which failures a harness can fix and which are model-limited, plus a subgoal-level error-decorrelation analysis that explains ensembling gains like Colosseum's.

## TL;DR

- **Done so far:** a 6-config x 10-seed CookingWorld ablation (planning ~1.5x baseline at ~5x the tokens), a five-channel scoring pipeline with survivorship and per-opportunity fixes, a gpt-oss-120b Zork baseline, and (in the Drive but missing from CLAUDE.md) Utsab's M1-M6 TextQuests harness with judge-inclusive per-step token logging, run as single-seed 8-config sweeps on Zork I and Wishbringer with claude-sonnet-5. Drift measurement and TextQuests ground truth are still broken.
- **Best new contributions:** (1) predicting harness-fixable vs model-limited failure from a cheap baseline channel profile, (2) a within-run hazard model with channels as competing risks, which text games can identify and METR-style aggregate data cannot, and (3) subgoal-level error decorrelation. A quick check on Colosseum's own numbers shows its two runs fail almost independently (77.3% oracle vs 79.3% predicted under independence), so most of the 54% to 71% jump is a selection effect.
- **Most fundable for UK AISI:** #1 and #2 turn "capability estimates are elicitation-conditional" into a quantitative forecast. #3 answers the open question Colosseum's authors leave. All three reuse data the team is already collecting.

---

## 1. What's been done

**What the Drive folder actually holds.** The linked folder has one personal "Brain dump" doc (long-horizon safety reading notes plus unrelated side ideas) and three shortcuts: the shared "BASE 2026 - Ududec Stream" folder, the BlueDot grant update, and an unrelated AI Collusion handbook.\[1\] The project content sits in the BASE stream folder: Cozmin's research agenda v2 (5 Jun), a Dec 2025 to Jun 2026 literature review, the structured hazard note v15, meeting notes (22 Jun to 27 Jul), the "BASE Symposium Results" dump (30 Jul), symposium slides, and 24 reference PDFs (HarnessBench, LIFE, CATTS, MAP, AEC, TextQuests, Zork-Bench, TALES, Five-Nines, Battleship and others).\[1\] The Drive contains no code, notebooks or raw logs. Code lives in GitHub (Utsabab/long-horizon, dignissimus/long-horizon-scaling), so the summary below comes from the written results docs.\[1\]

**CookingWorld ablations (Sam; flash-lite, 6 configs x 10 seeds, about 53 usable runs).**
- Planning (M6) is the only mechanism whose effect CI clears zero. Best config m3-m5-m6 scores 0.508 vs baseline 0.335 (1.52x). Mean tokens per run: baseline 2.16M, M6+M3 11.5M, M6+M7 18.1M, so compute is far from matched.\[1\]
- State externalization works on its own channel. Items forgotten at step 100: world state ~21%, inventory ~34%, baseline ~42%. It barely moves score, and transcripts trace that to a domain-knowledge failure (the "grill means barbecue" rule), which was added as a fifth channel after the fact.\[1\]
- Same score, different death: planning roughly doubles median steps-to-termination among failed runs. Non-planning agents die early from irreversible mistakes, while planning agents livelock to the step cap.\[1\]
- Survivorship dominates the cumulative plots. By step 100 only 1 to 4 runs remain per config. Plot D (survivor-matched) and Plot E (per-opportunity ALE) were built to fix this. Per opportunity, the state and world-model harnesses sit in a lower ALE band than baseline.\[1\]
- Drift: the CookingWorld judge scored baseline 0/30 and planning roughly 9 to 13% of judged probes, while the Zork heuristic fires on 39% of steps. These two measurements fail in opposite directions, so drift is reported qualitatively.\[1\]
- One hypothesis was cleanly killed: models that are generally good at using any scaffold. Data from "Just a Wrapper?" showed no cross-task correlation.\[1\]

**TextQuests / Zork pipeline (Ammielle).**
- Zork I gpt-oss-120b baseline, 500 steps. The model degenerates past ~300 steps, which pushed collection toward Claude-tier models.\[1\]
- rubric.py emits {step, channel, evidence_span, justification, confidence}. Interface counts (65 parser rejections) and liveness are precise. ALE logic is ready but blocked.\[1\]
- belief_probe.py does an independent fresh-context restatement of inventory and location, diffed against ground truth. Self-tests pass; it has not run live.\[1\]
- Ground-truth blocker: the jiminy-cricket ROMs fail Jericho's MD5 lookup, so location and inventory return None. The dual-wrapper route through TALES stock ROMs is the agreed fix.\[1\]

**TextQuests M1-M6 harness (Utsab), not reflected in CLAUDE.md.**
- One detector per channel, six toggleable mechanisms, 18 deterministic tests, and an ALE-triggered branching simulator (rewind to the step before the first confirmed ALE, replay with M1 on).\[1\]
- Per-step `steps[].tokens` logging is judge-inclusive.\[1\] CLAUDE.md priority 1 ("no per-step token logging") is therefore already partly solved on this harness.
- 8-config sweeps, seed 0 only, claude-sonnet-5:\[1\]
  - **Zork 100 steps:** only M1 clears the 25% plateau (40%).\[1\]
  - **Zork 500 steps:** vanilla reaches 40% progress and score 99 on 20.6M tokens; M5 alone reaches the same 40% on 6.9M; all_on dies at step 19.\[1\]
  - **Wishbringer:** every config is stuck at 5% (the poodle) at 100 steps. At 500 steps, all eight configs issue RESTART between steps 127 and 210 believing they had been fired. That is a hallucinated terminal state, and no detector catches it. Only M2 gets past the poodle.\[1\]

**Admin.** BlueDot spend is $720.99, with $1,279.01 remaining.\[1\] Run cost is about $20 per 10-seed eval on a cheap model and $100+ on a frontier model.\[1\]

**Net status.** One channel (state/ALE) is measured against ground truth and responds to its mechanism. Compute control, drift, self-report validity, multi-seed Zork/Wishbringer and cross-model runs are all still open.\[1\]

---

## 2. Where this can go beyond mechanism ablations

Ranked by eval-science payoff per unit effort.

### 1. Predict harness-fixable vs model-limited failures from a cheap baseline run

**Contribution:** a validated predictor that maps an unharnessed run's channel profile to (a) which mechanism will help and (b) how much measured capability is still on the table.\[1\] This yields an "elicitation headroom" estimate attached to any capability number.

**Why it's open:**
- The elicitation gap is well documented at the level of "scaffolds matter a lot." In Epoch AI's "Why benchmarking is hard," Brand and Denain found that switching scaffold moves SWE-bench Verified by up to 11 percentage points for GPT-5 and 15 for Kimi K2 Thinking, calling scaffold choice "the single biggest impact on the overall performance." Apollo's forecasts put low vs high elicitation on SWE-Bench at 54% vs 87%.\[2\] AISI's own elicitation protocol exists to avoid underestimation.\[3\]
- Harness-Bench (5,194 trajectories) explicitly says it measures "complete harness configurations" and does not isolate individual mechanisms.\[4\]\[5\]
- None of these predict which failures a given harness can fix.
- The "Frontier Lag" audit says Apollo, METR and AISI identify the gap but do not audit or model it.\[6\]

**Builds on:** RQ4, the channel taxonomy, the CookingWorld grid, Utsab's sweeps, and the planned 3 to 4 model x 2 game collection.\[1\] The "domain knowledge" and "hallucinated RESTART" cases are natural examples of model-limited failure that no current mechanism touches.\[1\]

**Effort:** mostly analysis on RQ2/RQ3 data. The main cost is enough models (4 or more) and seeds (5 to 10) to test the prediction out of sample. Hold out one model and predict its best mechanism and its gain. Roughly 3 to 4 weeks after collection.

### 2. A within-run hazard model of long-horizon failure, with channels as competing risks

**Contribution:** fit per-step hazard curves (exponential vs Weibull vs frailty mixture) within individual runs. Decompose total hazard into channel-specific hazards, and express each mechanism as a hazard ratio on its target channel (Cox-style).

**Why it's open:**
- Ord's constant-hazard "half-life" model is fitted to aggregate METR success-vs-length data.\[7\]\[8\]\[9\]\[10\]
- Hamilton's reanalysis, which Ord accepted in Feb 2026, finds declining hazard (Weibull k ~0.6 for agents vs ~0.37 for humans).\[7\]\[11\]\[12\]
- HorizonKit shows that aggregate curves often cannot separate a truly declining hazard from a mixture of constant hazards over tasks of varying difficulty.\[8\]\[13\]\[14\]
- METR's March 2026 note shows that modelling choices alone move recent 50% horizons by up to 35%.\[15\]
- All of that work only sees task-level success. Text games give step-level failure events, ground-truth state and replay, so they can identify which law holds within a run.\[1\]

**Builds on:**
- Fig 3 (steps-to-termination) and Plot D (alive-at-step).\[1\]
- Per-step channel labels.
- The survivorship problem, which becomes ordinary right-censoring.
- Planning's "late livelock vs early fatal error" finding, which reads directly as a shift between competing risks.\[1\]

**Effort:** low for a first pass on existing CookingWorld logs (days). A credible version needs 20 or more seeds per config, which is cheap on CookingWorld at ~$20 per 10 seeds.\[1\]

### 3. Subgoal-level error decorrelation (RQ5), with a channel-matched joint-failure test

**Contribution:**
- Compare joint failure probabilities at each checkpoint against the product of the marginals.
- Plot coverage curves against the independence prediction.
- Use a mixed-effects split of variance into item vs seed vs harness.
- For runs that fail jointly, test whether both runs fail through the same channel at the same place.

**Why it's open:**
- Colosseum reports single-run scores of 54.0% (3.1 Pro) and 55.0% (3.7 Flash), 71.0% for critique-based cross-model selection (213 of 300 problems), and a 77.3% oracle.\[16\] It has no per-subgoal or per-channel analysis.
- Under independence, two runs at 54% and 55% would jointly solve 1 − (0.46)(0.45) = 79.3%. The observed 77.3% oracle is close to that. Their failures are only mildly correlated, and the selector recovers about 92% of the oracle solves.
- Kim et al. (ICML 2025), testing over 350 LLMs, find that on the HELM leaderboard models agree 60% of the time when both err (vs 1/3 by chance), and that larger, more accurate models have highly correlated errors even across providers. That work covers static questions only.
- Large Language Monkeys (Brown et al.) shows coverage scaling over four orders of magnitude of samples, with DeepSeek-Coder-V2-Instruct going from 15.9% to 56% on SWE-bench Lite at 250 samples, again for single-shot tasks.
- Nobody has measured where in a long trajectory correlated failures happen, or through which channel.

**Builds on:** deterministic replay, TextQuests milestone checkpoints (game_progress.json), multi-seed runs, and channel labels. The Wishbringer RESTART, hit by all 8 configs, is a ready-made example of a perfectly correlated, channel-specific failure that no ensemble would fix.\[1\]

**Effort:** moderate. It needs 10 or more seeds per config on at least one game and a cross-model pair. The analysis itself is a few days.

### 4. Counterfactual credit assignment and decisive-step labels via branching replay

**Contribution:** generalize Utsab's `run_comparison()` to fork at any step, switch one mechanism on, and measure its causal effect on downstream progress.\[1\] Label each failed run's decisive error step as the earliest step at which an oracle correction rescues the outcome.

**Why it's open:**
- Colosseum §8.2 names credit assignment as "the main challenge" and suggests comparing candidates that share context but diverge downstream.\[16\] The paper runs no such analysis.
- Who&When (Zhang et al., ICML 2025), built from failure logs of 127 multi-agent systems, reports the best automated method at 53.5% on agent attribution and only 14.2% on decisive-step attribution.
- Text games with save/restore can produce decisive-step labels that are correct by construction.\[1\]

**Builds on:** the branching simulator, TextQuests checkpointing, and the ALE detector.\[1\]

**Effort:** moderate engineering (arbitrary-step forking plus a mechanism grid). Cost grows with the number of forks, so sample decision points instead of forking everywhere.

### 5. A validated channel-measurement instrument, with judge error corrected rather than just reported

**Contribution:**
- Per-channel judge-vs-human and judge-vs-ground-truth agreement (kappa, recall), using fault-injected trajectories as gold labels.\[1\]
- Prevalence correction (Rogan-Gladen) so judge false-negative rates adjust the reported channel rates.
- A documented result that drift is not reliably measurable with current methods, which is itself an RQ1 finding.\[1\]

**Why it's open:**
- Recent judge-audit work finds outcome-only judges catch turn-local defects but miss cross-turn state defects. One study reports a judge catching 2 of 9 human-confirmed systematic patterns.\[17\]
- Reflect builds correct-by-construction labels for research agents.\[18\]
- Long-horizon game agents have nothing comparable, and ground truth makes ALE labels cheap and exact.

**Builds on:** belief_probe.py (fresh-context probing, a cleaner instrument than self-report), rubric.py, Scout scanners, and the planned hand-labelled slice.\[1\]

**Effort:** about 150 to 300 hand-labelled steps plus scripted fault injection via save/restore. Roughly 2 to 3 weeks.

### 6. A compute-matched comparison protocol for harnesses (structure vs volume)

**Contribution:** report every mechanism as a point on a score-vs-tokens frontier against budget-matched baselines: best-of-N vanilla, loop-until-budget, and a longer step cap. Use the fixed-compute and budget-sweep axes already in Cozmin's agenda.\[1\]

**Why it's open:**
- Colosseum reports no token counts, cost or model-call totals. Its §8.1 states that "compute-matched evaluation would be needed to distinguish improved allocation from simply using more inference."\[16\]
- A coding-harness study finds up to 40x token differences between harnesses for at most 8 pp of pass-rate change.\[19\]
- EvoMAS shows that budget-matched looping baselines can be flat. On SWE-agent with Claude-3.5-Sonnet, looping at 29M tokens still scores 33.6%.\[20\]

**Builds on:** Utsab's per-step judge-inclusive tokens and the existing Zork data. Vanilla at 20.6M tokens and M5 at 6.9M reach the same 40% progress, so the frontier framing applies immediately.\[1\]

**Effort:** low to moderate. The main cost is extra best-of-N baseline runs.

### 7. Harness-induced failure as a measured channel

**Contribution:** formalize and count failures that the harness creates. Examples so far: all_on dying at step 19 on Zork while vanilla runs to 500; the CookingWorld domain-knowledge failure that the project attributed to the harness; the pre-redesign memory mechanism costing −0.15.\[1\] Report how often adding structure lowers measured capability.

**Why it's open:**
- AISI's elicitation work and the log-analysis position paper both treat underestimation from scaffold conflicts as a credibility threat.\[3\]\[21\]
- "Beyond pass@1" reports that memory scaffolds hurt long-horizon performance across all 10 models it tested.\[22\]\[23\]
- Nobody has tied harness-induced failures to specific mechanisms and channels.

**Builds on:** existing transcripts and the taxonomy. The Wishbringer hallucinated-terminal-state case also argues for a sixth channel.\[1\]

**Effort:** low. Mostly relabelling and a short section.

### 8. An open, ground-truth-annotated long-horizon transcript set

**Contribution:** release the per-step store (state, beliefs, probe diffs, tokens, channel labels, decisive steps) across models x harnesses x seeds as an Inspect-compatible eval plus Scout scanners.

**Why it's open:**
- Agent benchmarking is expensive. The Holistic Agent Leaderboard (Kapoor et al., ICLR 2026) ran 21,730 rollouts across 9 benchmarks and 9 models for about $40,000 in compute.
- TALES and TextQuests release scores and games, without channel-labelled trajectories.\[24\]\[25\]

**Builds on:** everything above.

**Effort:** packaging time once the collection runs, and it gives Robert a concrete compute-and-artifact narrative for BlueDot.\[1\]

---

## Best fit for Cozmin Ududec / UK AISI

**#1 (harness-fixable predictor), #2 (hazard model), and #3 (decorrelation)** are the three to lead with.

- **#1** answers the question AISI actually faces: how much a measured capability would move under better elicitation, and where. It turns the brief's "capability is elicitation-conditional" into a number with an error bar.
- **#2** connects the project to the METR/Ord/Hamilton time-horizon debate. Ground-truth games can identify the hazard law that aggregate data cannot. A mechanism then has a clean interpretation as a hazard ratio on one channel, which is exactly the C2 bet.\[1\]
- **#3** is new as of October and is the cheapest way to say something sharp about bundled harnesses. The Colosseum arithmetic above already suggests that its biggest gain is a near-independence selection effect. The project can test whether that holds at subgoal level and by channel.

Contributions #5 and #6 are prerequisites for all three, so they should be framed as the methodology section, not as separate papers.

## Caveats

- The Colosseum independence comparison is my own arithmetic on the reported marginals. It ignores problem-level difficulty structure, and the TCS-Bench grader is model-based (reported >90% accuracy on 100 expert-labelled proofs).\[16\]
- All TextQuests sweep results are single-seed. CookingWorld cells have N≈9 with zero successes.\[1\]
- Several cited 2026 papers (HorizonKit, judge-audit studies, EvoMAS) are recent preprints and not peer-reviewed.
- I could not read the code repos or raw logs from the Drive. Claims about tooling come from the written results docs.

## Sources

1. Google Drive
2. [2025-03-04 Forecasting Frontier Language Model Agent Capabilities](https://arxiv.org/pdf/2502.15850)
3. [A structured protocol for elicitation experiments](https://www.aisi.gov.uk/blog/our-approach-to-ai-capability-elicitation)
4. [Harness-Bench: Measuring Harness Effects across Models in Realistic Agent Workflows](https://arxiv.org/html/2605.27922v1)
5. [\[2605.27922\] Harness-Bench: Evaluating Agent Harnesses across Models and Realistic Workflows](https://arxiv.org/abs/2605.27922)
6. [Frontier Lag:A Bibliometric Audit of Capability Misrepresentationin Academic AI Evaluation](https://arxiv.org/html/2605.04135v4)
7. [Hazard Rates for AI Agents Decline as a Task Goes On — Toby Ord](https://www.tobyord.com/writing/hazard-rates-for-ai-agents-decline)
8. [Is there a Half-Life for the Success Rates of AI Agents? — EA Forum](https://forum.effectivealtruism.org/posts/qz3xyqCeriFHeTAJs/is-there-a-half-life-for-the-success-rates-of-ai-agents-3)
9. [Is there a Half-Life for the Success Rates of AI Agents? — Toby Ord](https://www.tobyord.com/writing/half-life)
10. [Is there a half-life for the success rates of AI agents?](https://arxiv.org/pdf/2505.05115)
11. [Open problems — Agents — Fedor Pakhurov](https://fpakhurov.com/notes/agents/open-problems/)
12. [On Economics of A(S)I Agents — EA Forum](https://forum.effectivealtruism.org/posts/dXsBcjCJAKX77Pgsd/on-economics-of-a-s-i-agents)
13. [GitHub - ranadhir19/horizonkit: Which hazard law governs your AI agent's reliability — and can your data even tell? Fits exponential / Weibull / Lomax (frailty) laws to agent run logs, refuses identification when the data cannot distinguish them, and reports honest pass^k intervals and T50/T90/T99 side by side. · GitHub](https://github.com/ranadhir19/horizonkit)
14. [Is There a Half-Life for the Success Rates of AI Agents?](https://www.forethought.org/research/is-there-a-half-life-for-the-success-rates-of-ai-agents)
15. [Impact of modelling assumptions on time horizon results - METR](https://metr.org/notes/2026-03-20-impact-of-modelling-assumptions-on-time-horizon-results/)
16. <https://arxiv.org/pdf/2609.15983>
17. [(PDF) trajectory-judge: What Outcome-Only LLM Judges Miss on Agent Trajectories](https://www.researchgate.net/publication/413883513_trajectory-judge_What_Outcome-Only_LLM_Judges_Miss_on_Agent_Trajectories)
18. [Time to Reflect : Can We Trust LLM Judges for Evidence-based Research Agents?](https://arxiv.org/html/2605.19196v1)
19. [\[2607.22585\] The Scaffold Effect in Coding Agents: Harness Choice as a Hidden Variable in Coding-Agent Evaluation](https://arxiv.org/abs/2607.22585)
20. [EvoMAS: Evolutionary Generation of Multi-Agent Systems](https://arxiv.org/pdf/2602.06511)
21. [Log analysis is necessary for credible evaluationof AI agents](https://arxiv.org/html/2605.08545)
22. [Beyond pass@1: A Reliability Science Framework for Long-Horizon LLM Agents](https://www.deepdyve.com/lp/arxiv/beyond-pass-1-a-reliability-science-framework-for-long-horizon-llm-9uAbPLTPTX)
23. [Beyond pass@1: A Reliability Science Framework for Long-Horizon LLM Agents](https://arxiv.org/pdf/2603.29231)
24. [arxiv.org](https://arxiv.org/abs/2504.14128v4)
25. [TextQuests: How Good are LLMs at Text-Based Video Games? · Pith Review](https://pith.science/paper/2507.23701)
