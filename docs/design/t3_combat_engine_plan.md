# T3 Plan - Combat Engine (`src/game/combat.py`)

## 1. Scope

T3 delivers a deterministic, pure combat simulator that resolves one battle from start to finish using the T1 runtime models and T2 weather modifiers.

Primary output:

- `src/game/combat.py`

Test output:

- `tests/game/test_combat.py`

Out of scope for this first T3 cut:

- UI animation/presentation behavior (`ui/views/combat.py`)
- Piece-specific active/passive scripting framework
- Mid-fight weather changes
- Economy/shop/roster transitions

## 2. Inputs and Outputs

### 2.1 Input contract

```python
resolve_combat(
    team: list[Champion],
    enemies: list[Enemy],
    weather: WeatherState,
    *,
    node_id: str = "",
) -> BattleResult
```

- Team and enemy inputs are static roster definitions (`Champion`, `Enemy`).
- Node weather System A is applied once at combat initialization via `weather_effects.apply_weather`.
- System B (the affinity damage triangle) is resolved per hit during damage application — it depends on the defender, so it cannot be pre-snapshotted.
- Function is pure and deterministic for identical inputs.

### 2.2 Output contract

Returns `BattleResult` with:

- `outcome`: `WIN` / `LOSS` / `DRAW`
- `duration_ticks`
- `rounds` where `rounds = ceil(duration_ticks / 600)`
- `turns` where turns are resolved **action events** (auto + cast)
- per-piece damage aggregates (`team_damage_dealt`, `team_damage_taken`)
- survivors (`surviving_team_ids`, `surviving_enemy_ids`)
- event log (`events`) usable by T12/T13

`rounds` and `turns` are retained as derived analytics fields for UI readability and summary charts. The simulator itself remains tick-native.

## 3. Engine Rules (MVP Lock)

These lock open proposal choices for implementation speed.

### 3.1 Time and thresholds

- `TICK_MS = 10`
- `ROUND_TICKS = 600`
- `ENERGY_THRESHOLD = 60_000`
- `MAX_TICKS = 7_200` (72s timeout)

### 3.1b Resource units

- `mana_regen` is interpreted as mana units per tick.
- `ability_cost` is in the same mana unit.
- All mana/energy math remains integer-only in simulation.

### 3.2 Per-tick meter updates

Each living piece updates on every tick:

- `action_energy += effective_as`
- `movement_energy += effective_ms`
- `mana = min(ability_cost, mana + effective_mr_tick)`

All values remain integer.

### 3.3 Action/movement trigger rules

Action resolution order for a triggered action meter:

1. Cast if `mana >= ability_cost` and a valid target exists.
2. Else auto-attack if at least one enemy is in `attack_range`.
3. Else idle-hold: clamp `action_energy = ENERGY_THRESHOLD`.

Movement resolution order for a triggered movement meter:

1. If in range of any enemy: hold `movement_energy = ENERGY_THRESHOLD`.
2. Else step one hex toward nearest reachable enemy.
3. If no path: hold `movement_energy = ENERGY_THRESHOLD`.

### 3.4 Target selection (deterministic)

When retargeting is needed:

1. Higher `threat`
2. Lower hex distance
3. Lower HP%
4. Lower absolute HP
5. Lower `piece_id` lexical order

A piece keeps current target while it remains valid.

### 3.5 Same-tick event ordering

Deterministic total ordering:

1. Same piece: movement event before action event.
2. Across pieces: higher `effective_as` first.
3. Then higher raw `attack_speed`.
4. Then lower `speed_tiebreaker`.

### 3.6 Damage formulas

- Auto raw damage: `1.0 * STR + 0.2 * INT`
- Ability raw damage (default): `0.2 * STR + 4.2 * INT`

Affinity multiplier (weather System B):

- Before mitigation, multiply raw damage by
  `weather_effects.damage_modifier(attacker.affinity, defender.affinity)` —
  `1.10 / 1.05 / 1.00 / 0.95 / 0.90` by the attacker-vs-defender ring relation.
- Applies to auto-attacks and abilities alike. A `Clear` attacker or defender
  resolves to `1.00`.

Mitigation (MVP):

- All outgoing damage is explicitly typed as one of: `physical`, `magical`, `true`.
- `physical` damage is mitigated by Armor.
- `magical` damage is mitigated by Resistance.
- `true` damage bypasses mitigation.
- Use bounded reduction: `reduction = stat / (stat + 100)`.
- Final integer damage is rounded and clamped to at least 1 on successful hit.

Type mapping for T3 MVP:

- Auto-attacks are `physical`.
- Default active ability is `magical`.
- No baseline `true` damage source in MVP, but engine supports it for future abilities.

### 3.7 Combat end conditions

- Team wipe: enemies all dead => `WIN`
- Enemy wipe: team all dead => `LOSS`
- Timeout at `MAX_TICKS` => `DRAW`, `timed_out=True`

## 4. Map and Pathing (MVP)

- Hex axial coordinates (`q`, `r`) from `CombatPieceState` fields.
- Large field target: approximately TFT-sized or slightly larger.
- MVP board uses a deterministic large hex field: `BOARD_WIDTH = 10`, `BOARD_HEIGHT = 7` (70 addressable cells before occupancy/path constraints).
- No terrain costs in MVP.
- Shortest-path via BFS (uniform edges).
- Occupied tiles block movement.
- Dead piece is removed immediately; tile becomes free.

Spawn policy (MVP deterministic):

- Team starts on left formation columns.
- Enemies start on right formation columns.
- Assignment is stable by input index.

## 4b. Deferred Systems (Must Not Be Forgotten)

These are approved as out of MVP scope but must be designed before piece-specific content tuning.

### 4b.1 Status effects system (stun/silence/disarm/root)

Tracking status: deferred design required.

Suggested implementation approach:

1. Add a generic `StatusEffect` runtime record with `kind`, `source_id`, `expires_tick`, and effect payload.
2. Maintain `active_statuses` on each `CombatPieceState`.
3. Resolve statuses via hook gates in the tick loop:
  - meter gain gate
  - action gate
  - movement gate
  - damage gate
4. Canonical semantics proposal:
  - `stun`: blocks action + movement; mana regen pauses
  - `silence`: blocks cast only; auto and movement allowed
  - `disarm`: blocks auto only; cast/move allowed
  - `root`: blocks movement only; action/mana allowed
5. Process expiry at deterministic phase boundary (start of tick).

### 4b.2 Ability/passive framework

Tracking status: deferred design required.

Suggested implementation approach:

1. Introduce an `AbilityRegistry` mapping ability ids to pure handlers.
2. Split handlers by type:
  - active: `resolve_active(ctx, actor, target)`
  - passive: event-driven listeners
3. Add an internal event bus with typed events:
  - `on_tick`
  - `on_attack_landed`
  - `on_cast`
  - `on_damage_taken`
  - `on_kill`
4. Keep handlers pure (return deltas/events) and apply through centralized reducer for determinism.
5. Keep current MVP fallback ability path as default when no registered ability exists.

## 5. Implementation Steps

### Step 1 - Module and constants

Create `src/game/combat.py` with:

- Engine constants (`ROUND_TICKS`, `ENERGY_THRESHOLD`, `MAX_TICKS`)
- Internal dataclasses/helpers only if needed
- Public `resolve_combat(...)`

### Step 2 - Initialization

- Convert `Champion`/`Enemy` to `CombatPieceState` through `apply_weather` — applies System A and copies `affinity` onto the snapshot for System B lookups.
- Assign deterministic positions and `speed_tiebreaker`.
- Initialize aggregate trackers for damage and events.

### Step 3 - Effective stat helpers

Implement integer helper functions:

- `effective_as(piece) -> int`
- `effective_ms(piece) -> int`
- `effective_mr_tick(piece) -> int`

No floating-point accumulation in simulation loop.

### Step 4 - Tick loop

- Update meters for all living pieces.
- Collect triggered movement/action events.
- Sort by deterministic key.
- Resolve each event and subtract threshold with overflow preservation.
- Remove dead pieces immediately and invalidate stale targets.

### Step 5 - Action resolution

- Retarget if needed.
- Cast-or-attack-or-hold logic.
- Record `BattleEvent` for each resolved cast/attack/death.
- Update damage aggregates.

### Step 6 - Movement resolution

- Check in-range condition.
- Path one-step BFS move if needed.
- Preserve deterministic tie breaks when multiple shortest next steps exist.

### Step 7 - Result construction

Build `BattleResult` from final state:

- `duration_ticks`, `rounds`, `turns`, `timed_out`, `outcome`
- Survivors lists
- Damage dicts
- Ordered event list

## 6. Test Plan (`tests/game/test_combat.py`)

### 6.1 Determinism

- Same team/enemies/weather inputs produce byte-equal `BattleResult.to_dict()`.

### 6.2 Basic outcomes

- Simple favorable matchup produces `WIN`.
- Inverted matchup produces `LOSS`.
- Stalemate setup reaches `DRAW` timeout.

### 6.3 Meter semantics

- Idle action holds at threshold, not reset.
- Movement hold in range works.
- Overflow energy carries correctly after trigger.

### 6.4 Targeting

- Threat priority wins over distance.
- Tie chain falls through correctly to `piece_id`.
- Target invalidation triggers deterministic retarget.

### 6.5 Pathing

- Piece routes around blockers.
- No-path scenario holds movement meter.

### 6.6 Weather integration

- System-A modified stats from `apply_weather` are actually used by combat outcomes.
- System-B `damage_modifier` is applied per hit: for otherwise-identical pieces, a predator attacker deals more and a prey attacker deals less.

### 6.7 BattleResult integrity

- `rounds`, `turns`, survivor ids, and damage maps are consistent with event stream.

## 7. Acceptance Criteria

T3 is complete when all are true:

1. `resolve_combat(...)` exists in `src/game/combat.py` and is pure.
2. System-A weather modifiers are applied once at init and never mutated afterward; System B is applied per hit via `damage_modifier`.
3. Combat resolves by tick loop with deterministic ordering and no randomness.
4. `BattleResult` fields are fully populated and coherent.
5. `tests/game/test_combat.py` passes and verifies determinism + edge cases.
6. Existing tests (`tests/game/test_models.py`, `tests/game/test_weather_effects.py`) still pass.

## 8. Risks and Mitigations

- Risk: hidden nondeterminism from dict/set iteration.
  - Mitigation: sort all candidate collections before selection.

- Risk: performance regressions from per-tick pathfinding.
  - Mitigation: small board + one-step BFS + early exits; optimize after baseline correctness.

- Risk: spec drift between proposal and implementation.
  - Mitigation: this plan is authoritative for T3 MVP; advanced behavior tracked as T3 follow-ups.

## 9. Follow-up Tasks (Post-T3)

- Add ability registry and per-piece active behavior definitions.
- Add passive trigger framework (`on_hit`, `on_cast`, etc.).
- Add full status-effect framework (`stun`, `silence`, `disarm`, `root`) and lock semantics.
- Optional sudden-death mode after timeout threshold.
- Expose queue projection helper for T12 combat UI.

## 10. Open Model Hygiene Item (Documentation Drift)

- `docs/design/t1_model_contracts.md` currently contains stale enum and enemy-field definitions compared to `src/game/models.py`.
- Treat contract sync as a prerequisite cleanup before broad T3 implementation merges.
