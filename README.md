# Long-horizon harness research

Workstreams owned here: TextQuests/Zork pipeline, Scout transcript analysis, annotation rubric, belief probe, plots A to E, results and writing. See `CLAUDE.md` for the full brief and `LOG.md` for session history.

## Layout

- `scout_report/` analysis code (`cooking_rubric.py`, `plots.py`, `report.py`), `RUBRIC.md`, plots and scan outputs
- `flash_lite_eval_20260627_09354/` CookingWorld 6-config x 10-seed `.eval` logs (zstd-compressed INSPECT logs)
- `textquests/` (submodule) fork of `centerforaisafety/textquests` with the TALES wrapper and Scout scanners
- `long-horizon/` (submodule) fork of `Utsabab/long-horizon` with the M7 world-model mechanism

## Collaborator repos

- Sam Ezeh, main framework and CookingWorld ablations: https://github.com/dignissimus/long-horizon-scaling
- Utsab Khakurel, branching simulator and runtime ALE detector: https://github.com/Utsabab/long-horizon
- TextQuests (CAIS): https://github.com/centerforaisafety/textquests
