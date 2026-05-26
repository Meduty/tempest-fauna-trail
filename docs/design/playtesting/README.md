# Playtesting

Dev tools for exercising the game engine before UI exists.

The engine (~6.5k LoC pure logic across `src/game/` and `src/api/`) is far ahead
of the UI (still a placeholder counter in `src/main.py`). Without dedicated dev
tools, the only way to observe combat, encounters, and run flow is through
unit tests — which prove correctness, not feel.

This directory designs the dev-facing playtest surface that unblocks balance
work, content authoring, and qualitative validation before the Flet UI catches
up.

## Documents

| File | Purpose |
|---|---|
| [plan.md](plan.md) | Full plan: scope, layers, file structure, phase order. |
| [engine_split.md](engine_split.md) | Reality-check note on the two combat entry points; every playtest tool must pick one. |

## Relationship to other tasks

- **T.25 — power simulation** (`tools/simulation/`) covers batch matchup sweeps
  and Bradley-Terry ratings. The playtest tools here are interactive / one-shot
  / qualitative; they sit next to T.25, not on top of it.
- **T.12 — combat view** is the eventual UI consumer of the same event streams
  the playtest tools render to text. The new-engine `DebugRecorder` from this
  plan is reusable by T.12.
- **T.16 — unit tests** stay the regression net. Playtest tools are read-only
  observability, not replacements for assertions.
