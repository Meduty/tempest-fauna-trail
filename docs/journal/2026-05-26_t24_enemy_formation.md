# T24 — Enemy Formation Policy

**Date:** 2026-05-26
**Task:** T.24 (Enemy Formation Policy)
**Status:** ✅ Complete

---

## Summary

Implemented the deterministic, role-aware enemy formation planner (`src/game/formation.py`).
The formation system replaces the old index-based enemy packing in combat init with
tactically coherent placement based on piece archetypes.

## Key Decisions

### Amendment 1: §4.2 — Assassin/Flanker Positioning

The plan originally placed assassins at **frontline flanks** (column 7, edge rows).
Per the amendment, assassins now take **mid-to-backline flanks** (columns 8–9, edge rows 0/6).

Rationale: Warriors and bruisers are the tank/damage hybrids that hold midline — they
belong at column 8. Assassins want to slip *past* the frontline, not stand beside it.
Mid-to-back edge placement gives them a shorter path to the player's backline.

### Amendment 2: §5.6 — Per-Boss Authored Position

Instead of a fixed center-back position for all bosses, each boss now has a
`spawn_position` field on `BossDef`. Positions assigned:

| Boss | Position | Rationale |
|------|----------|-----------|
| Holloway (Stage 1) | (7, 3) — frontline center | Melee brawler, wants to fight immediately |
| Vance (Stage 2) | (9, 3) — backline center | Ranged caster, stays behind troops |
| Strand (Stage 3) | (9, 3) — backline center | Ranged caster |
| Vossberg (Stage 4) | (7, 3) — frontline center | Melee brawler |
| Crège (Stage 5) | (9, 3) — backline center | Ranged control |
| Iron Emperor (Stage 6) | (8, 3) — midline center | Hybrid commander, directs from mid |

### Open Items Resolved

- **#1 (Hybrid-Tank/DMG):** FRONTLINE — their tanky durability drives classification.
- **#2 (Boss position):** Per-boss authored via `spawn_position` field.
- **#3–5:** Deferred as planned (adaptive AI, map-aware, support sub-positioning).

## Files Changed

| File | Change |
|------|--------|
| `src/game/formation.py` | **New** — formation planner module |
| `src/game/bosses/data.py` | Added `spawn_position` field to `BossDef` + values for all 6 bosses |
| `src/game/content.py` | Added `ENEMY_DEF_BY_ID` lookup dict |
| `src/game/combat/legacy.py` | Replaced `_assign_spawns` with T24-integrated version |
| `tests/game/test_formation.py` | **New** — 41 tests covering all formation behavior |
| `tests/game/test_combat.py` | Updated retarget test for new formation positions |
| `SPEC.md` | T.24 status → ✅ Done |
| `docs/design/tasks/t24_enemy_formation_plan.md` | Status → implemented |

## Architecture Notes

The formation planner is a pure function with zero Flet imports and no RNG (V.1, V.2).
It integrates cleanly at the combat init boundary — `_assign_spawns` calls
`plan_enemy_formation()` for the enemy side while keeping index-based placement
for the player team (until T23 provides explicit player positions).

The `ENEMY_DEF_BY_ID` dict provides O(1) lookup from piece_id → EnemyDef,
enabling the formation planner to read archetype fields (range_, durability)
needed for role classification without coupling to the runtime CombatPieceState.
