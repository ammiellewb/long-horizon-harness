# Team update — measuring how our game-playing agents fail

*Plain-language summary. Goal: give us enough to decide next steps.*

## In one sentence
We can now automatically measure **what kinds of mistakes** an AI agent makes
while playing these games, and we ran it on our first real batch of experiments.

---

## The headline finding

**Making the agent plan ahead is the biggest single help** — it lifts the game
score about **1.5×** over the baseline (0.33 → ~0.51, an added ~0.17) and keeps
the agent going much longer before it gives up. *(Earlier drafts said "doubles";
that only holds against the weakest setup, not the real baseline — corrected.)*

**But there's a catch:** those same planning agents also make **a lot more
mistakes** along the way. The score goes up, but the mistakes pile up even
faster. So "plays longer and scores higher" is *not* the same as "plays more
carefully." That tension is probably the most interesting thing to discuss.

---

## The results (60 runs, 6 different agent setups)

Each setup adds a different helper to the agent. Higher score = better.

| Setup (what we gave the agent) | Score | Memory<br>mistakes | Rejected<br>commands | Ignored<br>its own plan | Lost<br>the goal | How long<br>it lasted |
|---|---|---|---|---|---|---|
| **Baseline** — just a list of valid moves | 0.33 | 98 | 18 | 1.6 | 0.0 | 28 turns |
| + reminder of the true game state | 0.26 | 87 | 23 | 1.8 | 0.0 | 31 turns |
| + a map of the world | 0.29 | 83 | 19 | 1.5 | 0.1 | 27 turns |
| **+ planning** | **0.48** | 287 | 31 | 1.0 | 0.3 | 56 turns |
| **+ planning + state reminder** | **0.51** | 250 | 26 | 0.6 | 0.4 | 48 turns |
| **+ planning + world map** | **0.47** | 253 | 31 | 1.9 | 0.4 | 63 turns |

*Score = the game's own score at the end of a run, averaged over 10 tries (0–1). All 6
setups shown; "Baseline" is the reference the others are compared against.*

**How to read it:**
- The bottom three rows (with **planning**) clearly win on score.
- "Memory mistakes" are counted over the whole run, so agents that last longer
  naturally rack up more. But even adjusting for length, the planning agents
  still make more memory mistakes *per turn* — so it's a real effect, not just
  "they played longer."
- "Ignored its own plan" actually *improves* with planning (lower is better) —
  planning agents are better at following through on what they decided to do.

**Two honesty caveats for the meeting:**
- **The charts' x-axis is turns, not tokens.** We wanted to show mistakes vs.
  compute spent, but the logs don't record tokens per turn — only a run total. So
  the charts use turns as a stand-in. A proper token axis needs the next batch of
  experiments to log it.
- **Few runs reach the end.** Only **1–4 of the 10 runs per setup** survive to the
  100-turn cap. So the far-right of the "mistakes over time" charts is just a
  handful of long runs, not the whole group — don't over-read the tails.

**What the mistake types mean (plain):**
- **Memory mistakes** — the agent forgets what it's holding or where it is.
- **Rejected commands** — it types something the game doesn't understand.
- **Ignored its own plan** — it makes a plan, then does something else.
- **Lost the goal** — drifts off onto an unrelated task. *Now measured — and it
  turns out to be rare (see the second finding below).*

## Second finding: it's a *memory* problem, not a *focus* problem

Now that we can measure "lost the goal," the numbers are strikingly low — **near
zero** for every setup (at most ~0.4 times per run). In other words, the agent
almost never forgets *what it's trying to do*. It knows the goal the whole time —
it just **misremembers the world around it** (memory mistakes) and **fumbles
commands**. So the problem to attack is the agent's picture of the world, not its
sense of purpose. That's a sharper, more useful conclusion than "it drifts."

(Worth noting: an earlier rough version of this measure made it look like drift
was happening constantly. The proper measurement showed the opposite — a good
reminder to trust the careful number over the quick proxy.)

---

## What we built (so we can keep doing this)

A one-command tool that takes the raw experiment logs and prints the scorecard
above, plus three charts: score-over-time, and two that show **how each kind of
mistake piles up over the course of a game**. It works on both game types we use,
so we can point it at future experiments without redoing the analysis each time.
All five mistake types (including "lost the goal") are now fully measured.

---

## Decisions for the team

1. **Which game to focus on.** Two options, and we don't have to pick only one:
   - *Cooking game* — clean, fast, easy to measure. Best for big comparisons.
   - *Real classic games (Zork etc.)* — more realistic and harder, but messier
     to measure. Best for a smaller "does this hold up in the real world" check.

2. **Is "planning makes more memory mistakes" worth chasing?** It's the most
   surprising result. Do we dig into *why* (e.g. planning agents wander into
   more rooms, so more to keep track of), or park it and move on?

3. **Given the failures are about memory, do the memory-focused helpers need
   rethinking?** The "state reminder" and "world map" helpers are supposed to fix
   exactly this, but so far they barely move the score. Either they need to be
   stronger, or the memory problem is harder than a simple reminder can fix.

---

*Details, code, and charts live in `scout_report/`. Full technical log in
`scout_report/PROGRESS.md`.*
