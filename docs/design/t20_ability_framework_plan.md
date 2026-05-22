# T20 Plan - Ability, Passive & Status Framework (`src/game/abilities.py`)

## 1. Scope

T20 formalizes the systems T3 deferred (plan §4b) and SPEC marked undetermined
(D.3, D.4, D.5): piece active abilities, passive triggers, and status effects.
Bosses (T21) are the first hard consumer — boss phase 2 grants abilities, so
T20 must land before boss content.

Primary output: `src/game/abilities.py` (+ hooks into `src/game/combat.py`)

Test output: `tests/game/test_abilities.py`

## 2. Ability Registry

```python
AbilityRegistry: dict[str, AbilityHandler]
```

- **Active**: `resolve_active(ctx, actor, target) -> list[Effect]` — pure;
  returns effects/events, never mutates engine state directly.
- **Passive**: event listeners registered against the bus (§3).
- MVP fallback preserved: a piece with no registered ability uses the current
  T3 default cast path.

## 3. Event Bus

Typed, deterministically ordered events:

`on_tick`, `on_attack_landed`, `on_cast`, `on_damage_taken`, `on_kill`.

Handlers are pure — they return deltas/events; a **centralized reducer** applies
them in a sorted, deterministic order. No handler mutates engine state directly,
preserving the T3 determinism invariant (V.2).

## 4. Status Effects

```python
@dataclass
class StatusEffect:
    kind: str           # stun | silence | disarm | root
    source_id: str
    expires_tick: int
    payload: dict
```

- `CombatPieceState` gains `active_statuses: list[StatusEffect]` (model change).
- Tick-loop **hook gates**: meter-gain gate, action gate, movement gate,
  damage gate.
- Semantics (per T3 §4b.1): `stun` blocks action + movement and pauses mana;
  `silence` blocks cast only; `disarm` blocks auto only; `root` blocks movement
  only.
- Expiry processed at a fixed phase boundary (start of tick).

## 5. Phase Hook (for bosses)

New combat-engine hook: an HP-threshold trigger that mutates a piece mid-fight
(e.g. boss drops below 50% → grant a phase-2 active + passive). Deterministic,
evaluated at start of tick alongside status expiry.

## 6. Combat Engine Changes

- `CombatPieceState`: `+ active_statuses`. (`affinity` is added separately by
  the T.2 weather rework — SPEC B.5.)
- Tick loop: status-expiry phase, four gate checks, phase-hook check.
- Ability damage effects must route through the engine's shared damage function
  so the weather System-B affinity multiplier (`damage_modifier`) applies to
  spell damage, not only auto-attacks. Handlers return damage effects tagged
  with the actor; the reducer resolves the attacker-vs-defender multiplier.
- T3 MVP behavior is unchanged when no abilities, statuses, or phases are
  present — empty registry == current engine.

## 7. Test Plan

- Active ability resolves and produces the expected effects.
- Passive fires on its bound event; reducer order is deterministic.
- Each status gate blocks exactly its channel
  (`stun` / `silence` / `disarm` / `root`).
- Status expiry occurs at the correct tick.
- Phase hook fires once at threshold and grants abilities.
- Determinism: same inputs → byte-equal `BattleResult`.

## 8. Acceptance Criteria

1. `abilities.py` exists, pure, zero Flet imports.
2. Registry, event bus, status gates, and phase hook are all implemented.
3. T3 existing tests still pass (no regression with an empty registry).
4. `tests/game/test_abilities.py` passes.

## 9. Dependencies & Open Items

- Depends: T3. Resolves SPEC D.3, D.4, D.5.
- Open: full ability content (per-champion kits).

### 9.1 First passive content — `CLEAR`-weather buff

A concrete first passive for the framework: 1-2 `CLEAR`-affinity pieces gain a
passive buff while node weather is `CLEAR`. Rationale — `CLEAR` is inert in
**both** weather systems (no System-A node buff/debuff, no System-B triangle —
`CLEAR` neither counters nor is countered), so `CLEAR`-affinity pieces otherwise
never interact with weather; this passive gives the affinity its identity. The
passive owner **must** have `CLEAR` affinity. Pairs with the T21 `CLEAR`-boss
compensating stat bump — both address `CLEAR`'s inertness.
