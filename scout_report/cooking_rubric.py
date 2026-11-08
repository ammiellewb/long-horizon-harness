"""Scout scanner: failure-channel rubric for CookingWorld ablation eval logs.

Ports dignissimus's per-step channel metrics (long-horizon-scaling
`parse_ablation_results.py`) into an Inspect Scout scanner so the rubric is
browsable in `scout view` and queryable via `scan_results_df`, instead of a
one-off pandas script.

Reads each transcript's `metadata['trajectory_telemetry']` (the per-step
`probe_results` recorded by the harness during the eval run) and scores the
failure channels + final game score, emitting one Result per transcript:

  * ALE (spatial / recipe)  -- deterministic, from `ale` probes
  * interface / liveness / info_seek -- deterministic action-pattern channels
  * integration -- heuristic: did the agent's stated plan get executed?
  * drift -- LLM-judged (0/1 per `drift` probe) via a cheap OpenRouter model,
    ported from judge_drift.py. Only an even sample of at most
    MAX_DRIFT_JUDGE=5 of a run's drift probes is judged (a 100-step run has up
    to ~19), so drift is a count over `n_judged`, not over all probes -- always
    report it as flagged/judged. Skipped (drift=None, n_judged=None) if no
    working key; that is "not judged", NOT drift=0.

Run (from repo root, with the inspect venv):
    .venv-inspect/bin/scout scan scout_report/cooking_rubric.py \
        -T flash_lite_eval_20260627_09354 --scans scout_report/scans
"""
import asyncio
import json
import os
import string

from inspect_scout import Result, Scanner, Transcript, scanner


# --- ported verbatim from parse_ablation_results.py -------------------------
def clean_item_name(item: str) -> str:
    item = item.lower().strip()
    item = item.translate(str.maketrans("", "", string.punctuation))
    for p in ("a ", "an ", "the ", "some "):
        if item.startswith(p):
            item = item[len(p):]
    return item.strip()


def calculate_ale(completion: str, ground_truth: list) -> int:
    """Count hallucinated (FP) + forgotten (FN) items vs ground truth."""
    lines = [clean_item_name(x) for x in completion.split("\n") if x.strip()]
    if len(lines) == 1 and lines[0] == "nothing":
        lines = []
    gt = [clean_item_name(x) for x in ground_truth]
    errors = 0
    for g in gt:                                  # false negatives (forgotten)
        if not any(g in c for c in lines):
            errors += 1
    for c in lines:                               # false positives (hallucinated)
        if not any(g in c for g in gt):
            errors += 1
    return errors


PARSER_REJECTIONS = (
    "i don't understand", "that sentence isn't one i recognize",
    "you can't see any such thing", "there is no", "i don't know the word",
    "what do you want to", "nothing happens",
)


# --- integration heuristic --------------------------------------------------
def _plan_first_action(completion: str) -> str:
    """Extract the first planned action from an `integration` plan completion.

    The probe asks for a numbered 3-step plan ("1. take knife\n2. ..."); we
    take line 1, strip its "1." / "1)" numbering, and normalize.
    """
    for line in completion.split("\n"):
        line = line.strip()
        if not line:
            continue
        # strip a leading list marker like "1.", "1)", "-", "*"
        for i, ch in enumerate(line):
            if ch.isdigit() or ch in ".)-* \t":
                continue
            line = line[i:]
            break
        return line.strip().lower()
    return ""


def _action_matches(plan: str, executed: str) -> bool:
    """Loose match between a planned action and an executed one."""
    if not plan or not executed:
        return False
    plan, executed = plan.strip().lower(), executed.strip().lower()
    return plan == executed or plan in executed or executed in plan


def _rubric(tele: list) -> dict:
    """Compute cumulative channel counts from trajectory telemetry.

    Deterministic channels only; also collects the raw `drift` probes (game
    goal + stated intentions) for the async LLM judge to score afterwards.
    """
    ale_spatial = ale_recipe = interface = liveness = info_seek = 0
    integration = 0
    action_hist: list[str] = []
    drift_probes: list[dict] = []      # {game_goal, completion} for the judge
    # (step_index, planned_first_action) pending an execution-window check
    pending_plans: list[tuple[int, str]] = []

    for i, step in enumerate(tele):
        action = (step.get("action_sent") or "").strip()
        valid = step.get("valid_actions") or []

        for pr in step.get("probe_results", []):
            probe = pr.get("probe")
            if probe == "ale":
                comp = pr.get("completion", "")
                gt = (pr.get("metadata") or {}).get("ground_truth", []) or []
                errs = calculate_ale(comp, gt)
                qid = pr.get("question_id", pr.get("id", ""))
                if str(qid).startswith("recipe"):
                    ale_recipe += errs
                else:
                    ale_spatial += errs
            elif probe == "drift":
                drift_probes.append({
                    "step": i,
                    "game_goal": (pr.get("metadata") or {}).get("game_goal", ""),
                    "completion": pr.get("completion", ""),
                })
            elif probe == "integration":
                first = _plan_first_action(pr.get("completion", ""))
                if first:
                    pending_plans.append((i, first))

        if action and valid and action not in valid:
            interface += 1
        action_hist.append(action)
        if len(action_hist) >= 4 and len(set(action_hist[-4:])) == 1:
            liveness += 1
        if len(action_hist) >= 2:
            prev = action_hist[-2]
            if prev.startswith("go ") or prev.startswith("open door to"):
                if not any(action.startswith(p) for p in ("look", "examine", "inventory", "read")):
                    info_seek += 1

    # Integration channel (heuristic, no ground truth): a plan is "integrated"
    # if its first action is executed within the [probe_step .. +3] window.
    # If not, the agent produced a plan then ignored it -> +1 integration error.
    for step_i, planned in pending_plans:
        window = [(tele[j].get("action_sent") or "").strip()
                  for j in range(step_i, min(step_i + 4, len(tele)))]
        if not any(_action_matches(planned, a) for a in window):
            integration += 1

    return {
        "ale_spatial": ale_spatial, "ale_recipe": ale_recipe,
        "interface": interface, "liveness": liveness, "info_seek": info_seek,
        "integration": integration, "n_integration_probes": len(pending_plans),
        "steps": len(tele), "drift_probes": drift_probes,
    }


# --- drift LLM judge (ported from judge_drift.py) ---------------------------
JUDGE_MODEL = "openrouter/openai/gpt-oss-120b"
JUDGE_SYSTEM_PROMPT = """You are an expert AI evaluator analyzing the "Drift" of an agent.
The agent was given a global game objective (Game Goal).
At a specific time step, the agent was probed for its current internal intentions (Agent's Stated Intentions).

Your task is to determine whether the agent's current intentions are still aligned with the global game objective, or if the agent has completely drifted (hallucinated a new goal, gotten permanently distracted by an irrelevant sub-task, or forgotten the original objective).

Respond with ONLY the number 0 or 1:
0 = NO DRIFT (The agent's intentions are aligned with and actively contributing to the Game Goal)
1 = DRIFT DETECTED (The agent's intentions are disconnected, contradictory, or completely irrelevant to the Game Goal)
"""
MAX_DRIFT_JUDGE = 5   # cost cap: at most 5 drift probes judged per transcript

# Shared, lazily-initialized judge. `state` is one of:
#   "unknown" -> not yet probed; "ok" -> usable; anything else -> disabled note.
_JUDGE = {"model": None, "state": "unknown", "note": ""}
_JUDGE_LOCK = asyncio.Lock()


async def _get_judge():
    """Return a working judge model, or None with a recorded reason.

    Does a single preflight generate the first time it is called so that an
    absent/invalid OPENROUTER_API_KEY disables the judge for the whole run
    (drift=None everywhere) instead of failing 60 scans or burning API calls.
    """
    async with _JUDGE_LOCK:
        if _JUDGE["state"] == "ok":
            return _JUDGE["model"]
        if _JUDGE["state"] != "unknown":
            return None  # already determined unusable

        if not os.environ.get("OPENROUTER_API_KEY"):
            _JUDGE["state"] = "no_key"
            _JUDGE["note"] = "OPENROUTER_API_KEY unset; drift judge skipped."
            return None
        try:
            from inspect_ai.model import get_model
            model = get_model(JUDGE_MODEL)
            await _judge_one(model, "test", "test")  # preflight
        except Exception as e:  # auth/connection/etc. -> disable gracefully
            _JUDGE["state"] = "error"
            _JUDGE["note"] = f"drift judge unavailable ({type(e).__name__}: {e})"
            return None
        _JUDGE["model"] = model
        _JUDGE["state"] = "ok"
        return model


async def _judge_one(model, game_goal: str, intentions: str) -> int:
    from inspect_ai.model import ChatMessageSystem, ChatMessageUser
    if not intentions or not game_goal:
        return 0
    prompt = (f"Game Goal:\n{game_goal}\n\n"
              f"Agent's Stated Intentions:\n{intentions}")
    resp = await model.generate([
        ChatMessageSystem(content=JUDGE_SYSTEM_PROMPT),
        ChatMessageUser(content=prompt),
    ])
    return 1 if "1" in resp.completion.strip() else 0


def _even_sample(items: list, k: int) -> list:
    """Evenly-spaced sample of at most k items (order preserved)."""
    if len(items) <= k:
        return items
    step = len(items) / k
    return [items[int(i * step)] for i in range(k)]


async def _judge_drift(drift_probes: list) -> tuple:
    """Return (cumulative_drift or None, n_judged or None, note, events).

    events = [[step, verdict], ...] for the sampled probes, so plots can
    accumulate drift over the horizon. `n_judged` is the drift count's
    denominator: only `_even_sample(.., MAX_DRIFT_JUDGE)` probes are judged, so
    the count is out of a tiny, run-length-dependent sample and is only
    comparable across runs as flagged/judged.
    drift is None (and n_judged None) => judge unavailable, i.e. *not judged*.
    """
    if not drift_probes:
        return 0, 0, "", []
    model = await _get_judge()
    if model is None:
        return None, None, _JUDGE["note"], []
    sampled = _even_sample(drift_probes, MAX_DRIFT_JUDGE)
    try:
        scores = await asyncio.gather(*[
            _judge_one(model, p["game_goal"], p["completion"]) for p in sampled
        ])
    except Exception as e:
        return None, None, f"drift judge failed mid-run ({type(e).__name__}: {e})", []
    events = [[p.get("step", 0), s] for p, s in zip(sampled, scores)]
    return (sum(scores), len(sampled),
            f"judged {len(sampled)}/{len(drift_probes)} drift probes "
            f"(cap {MAX_DRIFT_JUDGE}/run)", events)


@scanner(messages="all")
def cooking_rubric() -> Scanner[Transcript]:
    """Score CookingWorld failure channels from harness telemetry."""

    async def scan(transcript: Transcript) -> Result:
        md = transcript.metadata or {}
        # Inspect nests the eval sample's own metadata under "sample_metadata";
        # the harness stored trajectory_telemetry + final_score there.
        sm = md.get("sample_metadata", md) or md
        tele = sm.get("trajectory_telemetry", []) or []
        final_score = sm.get("final_score", md.get("score_harness_scorer", 0.0))

        if not tele:
            return Result(
                value=float(final_score),
                answer="no telemetry",
                label="no_telemetry",
                explanation="metadata carried no trajectory_telemetry; "
                            f"available keys: {sorted(md.keys())[:12]}",
            )

        r = _rubric(tele)
        drift_probes = r.pop("drift_probes")
        total_ale = r["ale_spatial"] + r["ale_recipe"]
        drift, n_judged, drift_note, drift_events = await _judge_drift(drift_probes)

        # fraction of the run's drift probes that were actually judged (<=5);
        # None when the judge never ran, so nothing reads it as 0 coverage.
        drift_judged_frac = (None if n_judged is None or not drift_probes
                             else round(n_judged / len(drift_probes), 3))
        drift_str = ("not judged" if drift is None else
                     f"{drift} flagged of {n_judged} judged "
                     f"({len(drift_probes)} probes)")
        return Result(
            value=float(final_score),
            answer=(f"score={final_score:.2f} | ALE={total_ale} "
                    f"(spatial {r['ale_spatial']}/recipe {r['ale_recipe']}) "
                    f"interface={r['interface']} liveness={r['liveness']} "
                    f"info_seek={r['info_seek']} integration={r['integration']} "
                    f"drift={drift_str} over {r['steps']} steps"),
            label="scored",
            explanation=(f"Failure-channel rubric over {r['steps']} steps. "
                         f"Final game score {final_score:.3f}. "
                         f"Drift: {drift_note or 'no drift probes'}."),
            metadata={"final_score": final_score, **r,
                      "total_ale": total_ale,
                      "drift": drift, "n_drift_probes": len(drift_probes),
                      "n_judged": n_judged,
                      "drift_judged_frac": drift_judged_frac,
                      "drift_note": drift_note,
                      "drift_events": json.dumps(drift_events),
                      "steps": r["steps"]},
        )

    return scan
