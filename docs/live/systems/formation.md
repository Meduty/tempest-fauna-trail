# Formation — enemy spawn placement

> **Status: LIVING** — must match `src/game/formation.py` (called by `combat/engine.py::assign_spawns`). Audited by `/check`.
> **Scope:** how a generated enemy squad is placed on the board. **Reconciled:** 2026-06-05 @ refactor/combat-engine-single-source.

Deterministic, role-aware placement of the enemy squad on the right of the board
(columns 7–9). Pure function — no RNG, no I/O (V.1, V.2). Player champions are
placed by the engine on the left (index-packed); this module handles **enemies
only**.

## Entry

`plan_enemy_formation(pieces, enemy_defs_by_id, *, boss_position=None,
board_height=7) -> dict[order_key, (q, r)]`. Called by
`combat/engine.py::assign_spawns`, which feeds it a lightweight shim per enemy
(not a full `Piece`) and then writes the returned coordinates back onto the
pieces.

## The input contract — `FormationPiece`

The planner needs only three attributes, declared as a structural `Protocol`
`FormationPiece` in `formation.py`: `piece_id`, `tier`, and the
side-independent ordering key it writes placements against. The engine's shim
and the tests both satisfy it structurally — formation imports **no** piece
model, keeping it pure. (The ordering-key field name is owned by combat; this
module only reads it.)

## Placement policy

`classify_role(enemy_def) -> PlacementRole` buckets each enemy by its
`EnemyDef.durability`/`reach`:

| Role | Column | Who |
|---|---|---|
| `FRONTLINE` | 7 (closest to player) | tanky_hp / tanky_arm |
| `MIDLINE` | 8 | melee, standard durability (warriors, bruisers) |
| `FLANK` | 8–9 edge rows | melee + squishy (assassins) |
| `BACKLINE` | 9 | ranged (mages, marksmen, supports) |

Rows fill **center-out** (`_center_out_rows`); overflow spills to adjacent
columns; `_nearest_free` is the last-resort packer. Bosses get a per-boss
authored `boss_position` (displacing whatever sat there).

## File map

| Concern | Symbol |
|---|---|
| Plan a squad | `formation.plan_enemy_formation` |
| Role classification | `formation.classify_role` → `PlacementRole` |
| Input contract | `formation.FormationPiece` (Protocol) |
| Row packing | `formation._center_out_rows`, `_nearest_free` |
| Caller (writes coords onto pieces) | `combat/engine.py::assign_spawns` |
