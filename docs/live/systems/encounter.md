# Encounter & board — squad generation, bosses, map effects

> **Status: LIVING** — must match `src/game/encounter.py`, `bosses/`, `map_effects.py`, `board.py`. Audited by `/check`.
> **Scope:** seed-deterministic enemy/boss squad generation and the board-cell modifier state combat reads. **Reconciled:** 2026-06-05.
>
> 🔶 **STUB** — anchors only; prose TBD. Design rationale (frozen): `docs/design/tasks/t19_*`, `t21_*`, `t24_enemy_formation_plan.md`.

## Where it lives
- `encounter.py` — seed-deterministic encounter gen; `generate_boss_encounter`.
- `bosses/data.py` — `BOSS_DEFS`, spawn positions, `BossEncounterResult`.
- `map_effects.py` — boss map effects; `board.py` — `BoardState` (slow cells, fog).
- Placement: see [formation.md](formation.md).
