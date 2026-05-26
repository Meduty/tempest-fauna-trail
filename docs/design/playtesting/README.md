# Playtesting

Dev tools for exercising the game engine before the Flet UI exists.

The engine (~6.5k LoC across `src/game/` and `src/api/`) is feature-complete
through T.21 / T.24 / T.26 (unified combat, abilities, statuses, role-aware
enemy formation). The UI is still a placeholder counter. Without dedicated
dev tools, the only way to observe combat, encounters, and run flow is
through unit tests — which prove correctness, not feel.

This directory designs the dev-facing playtest surface that unblocks balance
work, content authoring, and qualitative validation before the Flet UI
catches up.

## Documents

| File | Purpose |
|---|---|
| [plan.md](plan.md) | Full plan: scope, layers, file structure, phase order. |
| [engine_split.md](engine_split.md) | Historical note on the (now resolved) two-engine split that T.26 closed. |

## Relationship to other tasks

- **T.25 — power simulation** (`tools/simulation/`, planned) covers batch
  matchup sweeps and Bradley-Terry ratings. The playtest tools here are
  interactive / one-shot / qualitative; they sit beside T.25, not on top.
- **T.12 — combat view** is the eventual UI consumer of the same
  `BattleResult.events` the playtest CLIs render to text. Layer 3 of this
  plan (a tick-replay visualizer) is the bridge from CLI to UI.
- **T.16 — unit tests** stay the regression net. Playtest tools are read-only
  observability, not replacements for assertions.

## Status

| Task | State |
|---|---|
| Plan + docs | ✅ Done |
| Layer 1 CLI (`tools/playtest/`) | ✅ Done |
| Layer 2 admin view | 📋 Plan, deferred |
| Layer 3 tick-replay (T.12 prototype) | 📋 Plan, deferred |
