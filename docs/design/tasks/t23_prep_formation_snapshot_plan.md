# T23 Plan - Prep Formation Snapshot Integration (`ui/views/prep.py`, `game/combat.py`)

## 1. Scope

T23 makes Prep placement authoritative for the player team. When the player
locks setup in Prep, explicit board coordinates are validated and passed into
combat initialization instead of being overwritten by default spawn packing.

Primary outputs:

- `ui/views/prep.py`
- `game/combat.py`
- `game/models.py` (if a placement snapshot type is added)

Test outputs:

- `tests/game/test_combat.py`
- `tests/ui/` (if UI-level contract tests exist)

Out of scope:

- Enemy placement heuristics (T24)
- New ability/status behavior
- New economy/shop rules

## 2. Input and Output Contract

Combat entry should accept an optional player placement snapshot:

```python
resolve_combat(
    team: list[Champion],
    enemies: list[Enemy],
    weather: WeatherState,
    *,
    node_id: str = "",
    team_positions: dict[str, tuple[int, int]] | None = None,
) -> BattleResult
```

Rules:

- `team_positions is None`: existing deterministic spawn fallback remains.
- Provided snapshot must map champion ids to legal board cells.
- Invalid snapshots are rejected before simulation starts (clear error).

## 3. Validation Rules

Before combat starts, placement snapshot must satisfy all:

1. Every deployed team piece has exactly one coordinate.
2. Coordinates are on-board.
3. No duplicate occupied cells.
4. Coordinates are inside the allied deployment zone.
5. Snapshot ids match the current `team` roster ids.

Validation must be deterministic and side-effect free.

## 4. Prep Integration

- `Start Combat` in Prep produces the placement snapshot from board state.
- Snapshot is passed through routing/app wiring into combat start.
- On validation failure, Prep remains active and shows a user-facing error.

## 5. Backward Compatibility

- Existing call sites without placement data continue to work unchanged.
- Replays remain deterministic for both snapshot and fallback paths.

## 6. Test Plan

- Valid snapshot preserves exact player positions at tick 1.
- Duplicate/off-board/out-of-zone snapshots fail with clear errors.
- Missing/extra ids fail validation.
- Legacy path (`team_positions=None`) still produces prior deterministic spawn.

## 7. Acceptance Criteria

1. Prep-locked placement is used verbatim by combat init.
2. Invalid placement cannot start combat.
3. Existing no-snapshot call sites still function.
4. Determinism tests pass for both paths.
