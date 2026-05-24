# 2026-05-23 — T20: Ability / Passive / Status Framework

## Context

T20 implements the ability, passive, and status effect framework — the core
substrate that all content (champions, enemies, items, augments, traits) plugs
into. This is the "effect system" described in `effect_systems_design.md`.

## Key Decisions

### Architecture: Direct mutation, not Effect-as-data

Per the effect systems design doc, we chose **direct mutation through
CombatContext** rather than an Effect-as-data + reducer pattern. The game is
sequential (10ms ticks, one action at a time, no concurrency), so the main
motivation for Effect-as-data doesn't apply. Handlers mutate world state
directly; the event bus fires hooks synchronously inside those mutators.

Benefits:
- Stack traces tell the truth
- No allocation per damage instance
- No "effects applied in wrong order" bug class
- Content designers write what they mean

### Hook dispatch: `(ctx, event)` signature

All hooks receive `(ctx, event)` from the EventBus. The ctx is the
CombatContext — handlers can mutate state, access weather, use rng, etc.
Reducing hooks receive `(ctx, event, value)` and return the modified value.

### Mana: 0 starting, refresh on reapply

Per user direction:
- All pieces start combat with **0 mana** by default
- Starting mana can only be granted by items, passives, or augments
- No mana on damage taken (except via explicit item/augment/passive)
- Mana regen fills **all active slots** in parallel (separate pools)

### Status stacking: per-status-type behaviour

- CC (stun, silence, disarm, root, frozen): **REFRESH** — reapply resets duration
- Poison: **STACK** — stacks increase, damage = base × stacks
- Slow: **STACK** — stacks intensify the debuff
- Sudden Death (timeout): **STACK** — escalating DOT per tick

### Sudden Death (combat timeout)

Instead of a hard draw at MAX_TICKS, the design calls for an escalating DOT
that intensifies each tick. This is registered as the `sudden_death` status
with `dot_scales_with_stacks=True`.

### Backward compatibility

The old `resolve_combat()` function is preserved in `src/game/combat/legacy.py`
and re-exported from `src/game/combat/__init__.py`. All 252 existing tests pass
without modification.

## What Was Built

### New modules (`src/game/`)

| Module | Lines | Purpose |
|--------|-------|---------|
| `effects.py` | ~210 | Modifier, Hook, EffectBundle, EventBus, SourceTag, HookScope, Lifetime |
| `events.py` | ~110 | Event payload dataclasses (CombatStartEvent, DamageEvent, etc.) |
| `status.py` | ~140 | StatusDef, StatusInstance, 12 core status definitions |
| `piece.py` | ~90 | Piece and ActiveSlot — the runtime combat entity |
| `rng.py` | ~40 | SeededRng for deterministic combat |
| `registries.py` | ~140 | @register decorators, ABILITY/PASSIVE/ITEM/TRAIT registries |
| `targeting.py` | ~150 | Targeting helpers (primary_target, lowest_hp, neighbors, radius) |
| `loadout.py` | ~160 | compile_loadout, apply_bundle, piece_from_champion/enemy |

### Combat subpackage (`src/game/combat/`)

| Module | Purpose |
|--------|---------|
| `__init__.py` | Re-exports + backward compat from legacy |
| `context.py` | CombatContext — the mutator API (deal_damage, heal, apply_status, cast, etc.) |
| `loop.py` | Tick loop: status processing, mana regen, cast resolution |
| `legacy.py` | Original resolve_combat (moved from combat.py) |

### Abilities (`src/game/abilities/`)

| Module | Purpose |
|--------|---------|
| `reference.py` | 3 actives + 3 passives demonstrating all authoring patterns |
| `champions.py` | 9 actives + 4 passives hooked to roster champion IDs |

### Tests

| File | Tests |
|------|-------|
| `tests/game/test_effects.py` | Modifier compute, EventBus dispatch, scope dedup |
| `tests/game/test_abilities.py` | Active/passive abilities, statuses, damage pipeline, loop integration |

## Integration Points

- **Legacy combat** (`resolve_combat`): unchanged, still uses the old flat model
- **Content roster** (`content.py`): champions have `{id}.active`/`{id}.passive`
  ability IDs; when registered in the ability registry, the new system picks them
  up via `loadout.compile_loadout`
- **Weather effects**: affinity clash multiplier integrated into damage pipeline
- **Scaling** (`scaling.py`): power scaling still used by content.py for stat
  generation; ability scaling uses the new `_eval_scaling` utility

## What's Next

- **T21**: Hook encounter generation to the new ability system (enemies with
  registered abilities use the new pipeline)
- **T22**: Augment and item systems (EffectBundle producers)
- Trait system implementation (breakpoint resolution, team-wide bundles)
- Full combat migration from legacy → new context-based loop
- More champion ability content (remaining 48 champions)
