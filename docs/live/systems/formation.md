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

The planner runs a fixed, deterministic pass order (enemies pre-sorted by
`piece_id` first): **frontline → flankers → midline → backline → boss**. Each
band is placed by `_place_band`, which fills its primary column center-out
(`_center_out_rows`), spills to `overflow_cols` when the column is full, and
falls back to `_nearest_free` as a last resort. Flankers are placed by
`_place_flankers` at the four board corners — edge rows `(0, board_height-1)` of
columns 8–9 — so assassins slip around the frontline toward the backline.

Bosses (tier 10) are detected up front and placed **last** by `_place_boss` at
the per-boss authored `boss_position` (default `(COL_BACK, board_height // 2)` =
center-back when none is given); a boss **displaces** any occupant of that cell,
relocating it via `_nearest_free`. An enemy whose `piece_id` has no matching
`EnemyDef` falls back to the `MIDLINE` bucket.

## File map

| Concern | Symbol |
|---|---|
| Plan a squad | `formation.plan_enemy_formation` |
| Role classification | `formation.classify_role` → `formation.PlacementRole` |
| Input contract | `formation.FormationPiece` (Protocol: `piece_id`/`tier`/`formation_index`) |
| Columns | `formation.COL_FRONT`/`COL_MID`/`COL_BACK` |
| Band placement (column + overflow) | `formation._place_band` |
| Flanker placement (corner edge rows) | `formation._place_flankers` |
| Row packing | `formation._center_out_rows`, `formation._nearest_free` |
| Boss slot (displaces occupant) | `formation._place_boss` |
| Caller (builds `_FormationEnemy`, writes coords) | `combat/engine.py::assign_spawns` |
