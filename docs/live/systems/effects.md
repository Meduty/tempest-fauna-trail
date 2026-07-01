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

`EventBus` (`effects.py`) is a synchronous, priority-ordered dispatcher:

- `subscribe(hook) -> hook_id` — appends the `Hook`, then re-sorts that event's
  list by `-priority` (higher priority fires first; stable within a tie).
- `fire(name, event, *, cast_id=None, ctx=None)` — notification dispatch. Every
  handler is called as `handler(ctx, event)`; return values are ignored.
- `fire_reducing(name, event, value, *, cast_id=None, ctx=None) -> float` — the
  value-mutating chain (damage pre-mods). Each handler is `handler(ctx, event,
  value)` and **returns the new value**; a `None` return leaves `value`
  unchanged. Only `on_damage_pre` uses this path.
- `unsubscribe(hook_id)`, `reset_combat()` (clears the `ONCE_PER_COMBAT` ledger
  at combat start), `clear_cast(cast_id)` (drops a finished cast's per-cast /
  per-target ledger entries).

A `Hook` (`effects.py`, dataclass) has an `event` name, a `handler` callable, a
`priority` int (default 0; the recorder subscribes at `-1000` so it observes
after all game logic), a `HookScope` (default `PER_HIT`), and a `hook_id`
auto-assigned at `subscribe` time (`hook_0`, `hook_1`, …).

### HookScope — dedup within a cast/combat

`_should_dedup` skips a hook's invocation when its scope has already fired for
the relevant key (tracked in `_dedup_ledger`):

| Scope | Fires… | Ledger key |
|---|---|---|
| `PER_HIT` (default) | every time — never deduped | — |
| `ONCE_PER_CAST` | once per `cast_id` (no-op when `cast_id is None`) | `("cast", cast_id, hook_id)` |
| `ONCE_PER_TARGET` | once per `(cast_id, target)` — reads `event.target.id` | `("target", cast_id, hook_id, target_id)` |
| `ONCE_PER_COMBAT` | once per combat, cleared by `reset_combat()` | `("combat", hook_id)` |

`cast_id` is threaded from `ctx.current_cast_id` at fire time; `ONCE_PER_CAST` /
`ONCE_PER_TARGET` degrade to `PER_HIT` when there is no cast in flight.

### Events fired by the engine/context

Payloads live in `events.py` (plain `@dataclass(slots=True)`, no methods).
Verified against the `bus.fire`/`fire_reducing` call sites:

`on_combat_start`, `on_tick`, `on_attack_start`, `on_attack_landed`,
`on_damage_pre` (reducing), `on_damage_dealt`, `on_damage_taken`,
`on_ability_damage`, `on_cast`, `on_cast_complete`, `on_heal`,
`on_status_applied`, `on_status_expired`, `on_kill`, `on_death`, `on_spawn`,
`on_despawn`, `on_phase_change`, `on_footprint`, `on_combat_end`.

`ManaEvent` (`on_mana_full`) is defined in `events.py` but is **not** currently
fired by the engine — mana readiness is polled in the tick loop, not published.

### Event payloads — which event carries which fields

Filtering hooks read `event.<field>`, so the exact field set matters. Note the
asymmetry between the two damage-adjacent events:

| Event(s) | Payload | Key fields |
|---|---|---|
| `on_attack_start` / `on_attack_landed` | `AttackEvent` | `attacker`, `target`, `amount` — **no `tag`, no `damage_type`, no crit** |
| `on_damage_pre` / `_dealt` / `_taken` / `_ability_damage` | `DamageEvent` | `attacker`, `target`, `amount`, **`tag`** (`SourceTag` value), `cast_id`, `hit_id`, `is_crit`, `damage_type` (`physical`/`magical`/`true`), `is_dot` |
| `on_cast` / `on_cast_complete` | `CastEvent` | `caster`, `ability_id`, `cast_id`, `slot_idx`, `mana_cost`, `mana_after` |
| `on_heal` | `HealEvent` | `source`, `target`, `amount` |
| `on_status_applied` / `on_status_expired` | `StatusEvent` | `target`, `status_id`, `duration_ticks`, `stacks` |
| `on_kill` | `KillEvent` | `killer`, `victim` |
| `on_death` | `DeathEvent` | `victim`, `killer` (may be `None`) |
| `on_spawn` | `SpawnEvent` | `piece`, `position` |
| `on_despawn` | `DespawnEvent` | `piece` (summon expiry — **not** a death) |
| `on_phase_change` | `PhaseEvent` | `piece`, `new_phase` |
| `on_footprint` | `FootprintEvent` | `cast_id`, `kind` (`circle`/`line`), `center_q`, `center_r`, `radius`, `direction`, `length` |
| `on_tick` | `TickEvent` | `tick` |
| `on_combat_start` / `on_combat_end` | `CombatStartEvent` / `CombatEndEvent` | (start: empty) / `winner` |

To react to auto-attacks *with* damage attribution, subscribe to
`on_damage_dealt` and filter on `event.tag == SourceTag.BASIC_ATTACK` — the
`AttackEvent` alone can't tell you damage type or whether it crit.

## StatusGate — how statuses disable actions

`StatusGate` (`status.py`) values, checked by `piece.is_gated(gate)` in the loop:

| Gate | Blocks |
|---|---|
| `BLOCKS_ACTION` | all meter advancement (stun, frozen, fear) |
| `BLOCKS_CAST` | ability casts (silence) |
| `BLOCKS_ATTACK` | auto-attacks (disarm) |
| `BLOCKS_MOVEMENT` | hex movement (root, frozen) |
| `HEXPROOF` | not a meter gate — excludes the bearer from single-target acquisition (autos + targeted abilities); AoE still lands, and the piece can still act (T.28d, V.40) |

`STATUS_DEFS` (`status.py`) currently registers: `stun`, `silence`, `disarm`,
`root`, `burn`, `poison`, `slow`, `charged`, `focus_fire`, `grievous`,
`hexproof`, `taunt`, `soaked`, `frozen`, `fear`, `sudden_death`, `grief`,
`stone_charge`, `soul_charged`, `nerei_grudge`. Pure markers (`focus_fire`,
`stone_charge`, `soul_charged`, `nerei_grudge`, `taunt`, …) carry no gate/DOT —
a kit's hooks read their presence/`stacks`/`source_id` directly.

A `StatusDef` is frozen data: `stack_behaviour` (`REFRESH` resets duration on
reapply / `STACK` accumulates), `gates`, and the DOT clock — `dot_per_tick`
(damage per **DOT tick**, not per engine tick), `dot_interval_ticks` (default
100 = 1 s, V.25), `dot_scales_with_stacks`, `decay_stacks_per_dot` /
`decay_fraction` (poison's percentage shed → self-limiting plateau, no hard
cap), and `dot_true_damage` (bypasses mitigation, e.g. `sudden_death`). A live
`StatusInstance` adds `remaining_ticks`, `stacks`, `source_id`, `potency` (a
per-DOT-tick damage override; 0 → fall back to the def's `dot_per_tick`), and
`ticks_to_next_dot` (the free-running DOT clock). `ctx.apply_status` honours
`piece.cc_immune` (drops gating statuses) and seeds the DOT clock.

## CombatContext — the mutator API

The **only** way content touches the world (`combat/context.py`).

- Damage / heal / shield: `deal_damage(attacker, target, amount, tag, *,
  crit=None, damage_type="magical", is_dot=False) -> float` (returns the final
  post-mitigation amount; `crit=None` defers to the deterministic `crit_counter`
  cadence; `is_dot` is presentation-only — routes the recorder to a `dot` beat),
  `heal` (honours the `grievous` antiheal marker), `grant_barrier`.
- Statuses / mods: `apply_status`, `remove_status`, `apply_modifier`,
  `register_bundle`.
- Actions: `trigger_basic_attack(attacker, target, mult=1.0)`,
  `cast_ability(actor, slot_idx=0)`, `gain_mana`, `teleport`, `spawn`,
  `expire_summon`, `kill`, `revive(target, hp_frac=0.3)`, `end_combat`.
- Queries: `enemies_of`/`allies_of`, `all_pieces`/`living_pieces`,
  `both_sides_alive`, `current_tick`, `current_cast_id`, `weather`, `bus`,
  `board_state`, `rng` (seeded — for non-combat-affecting choices only).
- Footprint telemetry: `note_footprint(kind, q, r, …)` — observer-only shape
  capture for the combat view, no-op outside a cast (see [combat.md](combat.md)).

`SourceTag` (`basic_attack` / `ability` / `item_proc` / `dot` / `status` /
`reflect` / `true`) tags every damage instance so hooks can filter what they
react to.

`compute_stat` (`effects.py`) folds `base + Σadd` then `×Πmul`, with `set`
overriding, then clamps via `_STAT_FLOORS` (currently `attack_range ≥ 1`, V.43).
`stat_breakdown(piece)` telescopes the same fold by `source:` prefix
(`item`/`augment`/`passive`/`trait`/`weather`, in `_SOURCE_ORDER`) for the prep
view's per-source stat attribution — pure, no Flet (V.1/V.45).

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
