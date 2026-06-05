# Formation — enemy spawn placement

> **Status: LIVING** — must match `src/game/formation.py` (called by `combat/engine.py::assign_spawns`). Audited by `/check`.
> **Scope:** how a generated enemy squad is placed on the board. **Reconciled:** 2026-06-05 @ refactor/combat-engine-single-source.

Deterministic, role-aware placement of the enemy squad on the right of the board
(columns 7–9). Pure function — no RNG, no I/O (V.1, V.2). Player champions are
placed by the engine on the left (index-packed); this module handles **enemies
only**.

## Entry

`plan_enemy_formation(pieces, enemy_defs_by_id, *, boss_position=None,
board_height=BOARD_HEIGHT) -> dict[int, tuple[int, int]]` — maps each enemy's
`formation_index` → `(col, row)`. Called by `combat/engine.py::assign_spawns`,
which builds a lightweight `_FormationEnemy` shim per enemy (not a full `Piece`),
calls this, then writes `formation[enemy.formation_index]` back onto
`piece.position_q/position_r`.

## The input contract — `FormationPiece`

The planner reads exactly three attributes, declared as a structural `Protocol`
`FormationPiece` in `formation.py`:

- `piece_id: str` — identity (sorted by, for determinism).
- `tier: int` — boss/role weighting (tier 10 = boss).
- `formation_index: int` — the board-slot key the returned `placements` dict is
  keyed by. **Not** the combat tiebreak: T.33a split the old `speed_tiebreaker`
  into `formation_index` (this placement key) and `load_order` (the
  `_event_sort_key` tiebreak, see [combat.md](combat.md#tick-model)). Formation
  only touches `formation_index`.

`combat/engine.py::_FormationEnemy` and the tests satisfy this structurally —
formation imports **no** piece model, keeping it pure (V.1).

## Placement policy

`classify_role(enemy_def: EnemyDef) -> PlacementRole` buckets each enemy by
`enemy_def.durability` and `enemy_def.reach`:

| `PlacementRole` | Column | Rule (durability / reach) |
|---|---|---|
| `FRONTLINE` | `COL_FRONT` (7) | `durability in ("tanky_hp", "tanky_arm")` |
| `FLANK` | `COL_MID`/`COL_BACK` (8–9) edge rows | `reach == "melee" and durability == "squishy"` |
| `MIDLINE` | `COL_MID` (8) | `reach == "melee"` (else) |
| `BACKLINE` | `COL_BACK` (9) | ranged (fallthrough) |

Rows fill center-out (`_center_out_rows`); overflow spills to adjacent columns;
`_nearest_free` is the last-resort packer. Bosses (tier 10) take the per-boss
authored `boss_position` via `_place_boss`.

## File map

| Concern | Symbol |
|---|---|
| Plan a squad | `formation.plan_enemy_formation` |
| Role classification | `formation.classify_role` → `formation.PlacementRole` |
| Input contract | `formation.FormationPiece` (Protocol: `piece_id`/`tier`/`formation_index`) |
| Columns | `formation.COL_FRONT`/`COL_MID`/`COL_BACK` |
| Row packing | `formation._center_out_rows`, `formation._nearest_free` |
| Boss slot | `formation._place_boss` |
| Caller (builds `_FormationEnemy`, writes coords) | `combat/engine.py::assign_spawns` |
