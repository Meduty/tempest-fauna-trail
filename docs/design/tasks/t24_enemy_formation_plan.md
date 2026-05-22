# T24 Plan - Enemy Formation Policy (`game/formation.py`, `game/combat.py`)

## 1. Scope

T24 replaces index-only enemy spawn packing with a deterministic, role-aware
formation planner. Enemy placement should be "reasonable" by default:
frontline ahead, fragile backline protected, and compact layouts for varying
team sizes.

Primary outputs:

- `game/formation.py`
- `game/combat.py`

Test output:

- `tests/game/test_formation.py`
- `tests/game/test_combat.py`

Out of scope:

- Adaptive counter-positioning against player comp
- Terrain-aware tactical placement
- Mid-fight reformation behavior

## 2. Public Surface

```python
def plan_enemy_formation(
    enemies: list[CombatPieceState],
    *,
    board_width: int,
    board_height: int,
) -> dict[str, tuple[int, int]]
```

`plan_enemy_formation` returns deterministic coordinates for enemy piece ids.

## 3. Role Buckets

Use role labels from content/model layer and bucket into placement bands:

- Frontline: `tank`, `bruiser`, `frontline`, `guardian`
- Midline: `fighter`, `ranged`, `support`
- Backline: `caster`, `artillery`, `healer`
- Unknown role: defaults to midline

## 4. Placement Heuristics (MVP)

1. Reserve right-side columns for enemy deployment.
2. Place frontline in the most forward enemy column.
3. Place backline in the most rear enemy column.
4. Place midline between front and back when space exists.
5. For each band, fill rows center-out for compact, stable shapes.
6. If band overflows, spill into nearest safe adjacent column.

All tie-breaks must be deterministic (piece id lexical, then source index).

## 5. Fallback and Safety

- If planner cannot place all pieces (extreme board constraints), fall back to
  existing deterministic index-based enemy packing.
- Never place off-board or duplicate coordinates.

## 6. Combat Integration

At combat init:

- Player team uses T23 snapshot when present, otherwise fallback spawn.
- Enemy team uses `plan_enemy_formation` by default.
- Existing deterministic `speed_tiebreaker` assignment remains unchanged.

## 7. Test Plan

- Determinism: identical input yields identical formation.
- Role behavior: frontline average q is more forward than backline average q.
- Size behavior: 1, 2, 3, 5, 8 enemy squads produce valid compact layouts.
- Safety: no duplicates, no off-board coordinates.
- Fallback path is exercised and deterministic.

## 8. Acceptance Criteria

1. Enemy placement is role-aware and deterministic.
2. Formations are valid for all tested squad sizes.
3. Fallback path remains safe and deterministic.
4. Combat tests pass with new formation planner integrated.
