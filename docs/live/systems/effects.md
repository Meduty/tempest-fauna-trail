# Effects — hooks, modifiers, statuses, registries

> **Status: LIVING** — must match `src/game/effects.py`, `events.py`, `status.py`, `registries.py`, `piece.py`, and `combat/context.py`. Audited by `/check`.
> **Scope:** the T.20 effect substrate — how content (abilities/passives/traits) changes combat without touching the loop. **Reconciled:** 2026-06-05.
>
> Citations by symbol, not line. Design rationale (frozen): `docs/design/systems/effect_systems_design.md`, `passive_system_proposal.md`. Catalog: see [abilities.md](../content/abilities.md), [traits.md](../content/traits.md).

## The shape

Content never calls the tick loop. It registers **hooks** on an `EventBus`; the
loop fires events; hooks mutate the world **only** through the `CombatContext`
API. Three data primitives carry the change:

- **`Modifier`** (`effects.py`, frozen) — a stat delta `(stat, op, value)`,
  `op ∈ {add, mul, set}`, applied by `compute_stat` as `(base + Σadd) · Πmul`,
  `set` overriding. Carries a `Lifetime` (`PERMANENT`/`COMBAT`/`TIMED`); `TIMED`
  uses `expires_at_tick`. Lives in `Piece.modifiers`; read via `piece.stat()`.
- **`StatusInstance`** (`status.py`) — a stacking, expiring effect on
  `Piece.statuses`, defined by a `StatusDef` in `STATUS_DEFS` (DOT cadence,
  decay, `StackBehaviour`, gates). Tick upkeep is `engine.process_statuses`.
- **`EffectBundle`** (`effects.py`) — a named group of hooks + modifiers a
  passive/item installs at once; `ctx.register_bundle(owner, bundle)`.

## EventBus

`EventBus` (`effects.py`): `subscribe(Hook) -> hook_id`, `fire(name, event, *,
ctx)`, and `fire_reducing(...)` for value-mutating chains (e.g. damage pre-mods).
A `Hook` has an `event` name, `handler`, `priority` (higher first; the recorder
subscribes at `-1000` to record last), and a `HookScope` (`PER_HIT` /
`ONCE_PER_CAST` / `ONCE_PER_TARGET` / `ONCE_PER_COMBAT`).

Events fired by the engine/context (payloads in `events.py`):
`on_combat_start`, `on_tick`, `on_attack_start`, `on_attack_landed`,
`on_damage_pre`, `on_damage_dealt`, `on_damage_taken`, `on_ability_damage`,
`on_cast`, `on_cast_complete`, `on_heal`, `on_status_applied`,
`on_status_expired`, `on_kill`, `on_death`, `on_spawn`, `on_combat_end`.

## StatusGate — how statuses disable actions

`StatusGate` (`status.py`) values, checked by `piece.is_gated(gate)` in the loop:

| Gate | Blocks |
|---|---|
| `BLOCKS_ACTION` | all meter advancement (stun, frozen) |
| `BLOCKS_CAST` | ability casts (silence) |
| `BLOCKS_ATTACK` | auto-attacks (disarm) |
| `BLOCKS_MOVEMENT` | hex movement (root, frozen) |

## CombatContext — the mutator API

The **only** way content touches the world (`combat/context.py`).

- Damage / heal / shield: `deal_damage(source, target, amount, SourceTag, *,
  crit=None, damage_type=...)`, `heal`, `grant_barrier`.
- Statuses / mods: `apply_status`, `remove_status`, `apply_modifier`,
  `register_bundle`.
- Actions: `trigger_basic_attack(attacker, target, mult=1.0)`,
  `cast_ability(actor, slot_idx=0)`, `gain_mana`/`spend_mana`, `teleport`,
  `spawn`, `expire_summon`, `kill`, `end_combat`.
- Queries: `enemies_of`/`allies_of`, `all_pieces`/`living_pieces`,
  `both_sides_alive`, `current_tick`, `rng` (seeded — for non-combat-affecting
  choices only).

`SourceTag` (`basic_attack` / `ability` / `dot` / `status` / `reflect` / `true`
/ `item_proc`) tags every damage instance so hooks can filter what they react to.

## Registries — id → handler

`registries.py` holds `ABILITY_REGISTRY`, `PASSIVE_REGISTRY`, `ITEM_REGISTRY`,
`TRAIT_REGISTRY`, `AUGMENT_REGISTRY`. Content registers via `@register_active`,
`@register_passive`, `@register_item`, `@register_trait` (and
`register_active_simple` for declarative single-target spec abilities). Roster
ability ids are prefixed (`champ_x.active`); every id must resolve (CI-guarded).
`compile_loadout` imports the `abilities` package to trigger the decorators.

## Invariants this system owns

- **V.14 / determinism** — "chance" effects use a cadence counter
  (`crit_counter`, `StatusDef.dot_interval_ticks`), never RNG.
- **Boundary** — `combat/` never imports content at module scope; content
  reaches combat only through `CombatContext` + the registries.

## File map

| Concern | Symbol |
|---|---|
| Bus, Hook, HookScope, Modifier, EffectBundle, `compute_stat`, Lifetime, SourceTag | `effects.py` |
| Typed event payloads | `events.py` (`DamageEvent`, `AttackEvent`, `DeathEvent`, …) |
| Status defs/instances, gates, `STATUS_DEFS`, `StackBehaviour` | `status.py` |
| Mutator API | `combat/context.py` (`CombatContext`) |
| Per-piece modifier/status/barrier state, `crit_counter` | `piece.py` |
| id → handler registries + `@register_*` | `registries.py` |
| Status tick upkeep | `combat/engine.py::process_statuses` / `expire_modifiers` |
