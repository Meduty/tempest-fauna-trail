# Abilities & passives — id resolution, registration, hooks

> **Status: LIVING** — must match `src/game/abilities/` + `registries.py` +
> `effects.py`/`events.py`. Audited by `/check`.
> **Scope:** how a roster ability/passive id becomes a runtime handler, how a
> handler is registered, and the event/hook model handlers plug into. **Reconciled:** 2026-07-01.
>
> Citations by symbol, not line. The *kits* (what each ability does, by lore) live
> in the frozen `docs/design/content/ABILITY_CATALOG_CHAMPIONS.md` /
> `ABILITY_CATALOG_ENEMIES.md`. The effect framework they plug into is
> [../systems/effects.md](../systems/effects.md); the authoring/balance rules are
> [../systems/kit_design_conventions.md](../systems/kit_design_conventions.md).

## Id convention

A `Champion`/`Enemy` carries `active_ability` / `passive_ability` **string ids**,
authored as prefixed ids in `content.py` (`active_ability = f"{id}.active"`,
`passive_ability = f"{id}.passive"`, e.g. `champ_torrent_heron.active`). Handlers
register under those exact ids — the T.30 fix was aligning the two (previously
short ids vs prefixed ids meant 0/240 resolved and every piece ran the generic
fallback).

**Multi-slot discovery (T.29d, V.49).** A piece's active slots are auto-discovered
by convention: `content.discover_abilities(piece_id)` regex-matches every
registered `{piece_id}.active`, `{piece_id}.active2`, … in sorted order (`.active`
< `.active2` < …). A champion with two registered actives (e.g.
`champ_ember_salamander.active` + `.active2`) fields **two `ActiveSlot`s** — this
is the Multicaster archetype (pieces with 2 active slots, each its own mana pool).
There are **9** `.active2` secondaries in the roster (6 champion + 3 enemy). A def
may override discovery with an explicit `abilities=` kwarg (named kits, bosses,
null stat-sticks).

**Bosses use named ids, not the `.active` convention.** Each boss def lists its
abilities explicitly (`abilities=[...]`) as `{boss}.{ability_name}` ids —
`holloway.pressure_vent`, `holloway.magma_heave`, `vance.sunflare_pounce`, plus a
`{boss}.phase_hook` passive that drives the 2-phase transition (see "Boss phase
hooks" below).

## Registration

Handlers live in `abilities/champions.py`, `abilities/enemies.py`,
`abilities/bosses.py` (+ `abilities/reference.py` for the shared/example kits that
validate the pipeline) and register **at import time** via decorators from
`registries.py`:

- `@register_active(ability_id, *, mana_cost=None, max_mana=0, start_mana=0, priority=1)`
  → `ABILITY_REGISTRY[id] = handler`. The handler signature is
  `handler(ctx, actor, targets) -> None`. The optional mana kwargs author the
  ability's `AbilityMana` statline in the same call (see "Mana on the ability def").
- `@register_passive(passive_id)` → `PASSIVE_REGISTRY[id] = factory`. The passive
  is a **factory** `factory(owner) -> EffectBundle` — it returns a bundle of
  `Modifier`s + `Hook`s bound to `owner`, applied at loadout.
- `register_active_simple(id, SimpleActive(...))` — declarative single-target /
  simple abilities with **no hand-written handler**. `SimpleActive(target, damage,
  scaling, tag, heal_amount, heal_scaling, heal_target)` synthesises a handler that
  resolves targets, deals `_eval_scaling(damage, scaling, actor)`, and optionally
  heals. `scaling` is an `_eval_scaling` expression like `"strength*1.5"` or
  `"intelligence*2.0+100"` (stat aliases: `str`→`strength`, `int`→`intelligence`,
  `atk`→`attack_speed`, `spd`→`move_speed`, `mr`→`mana_regen`, `arm`/`res`/`pen`).

`compile_loadout` imports the `abilities` package (`abilities/__init__.py` imports
`reference`, `champions`, `enemies`, `bosses`), which triggers every decorator,
populating the registries before any combat. `content.py` imports the package the
same way so the roster build can discover slots.

## Mana on the ability def (T.29c, V.48)

Mana is **per `ActiveSlot`**, not a `Piece` stat. Each ability's mana statline
lives in `ABILITY_MANA: dict[str, AbilityMana]`, keyed by the same ids as
`ABILITY_REGISTRY`:

- `AbilityMana(mana_cost=300_000, max_mana=0, start_mana=0, priority=1)` —
  `mana_cost` is the cast threshold **and** the amount deducted per cast;
  `max_mana=0` normalizes to `2 * mana_cost` (overload headroom); `start_mana`
  seeds the pool at combat start; `priority` is the unified rank (charge cycle +
  cast pick, `>=1`).
- `DEFAULT_MANA_COST = 300_000` is the baseline (former per-piece `ability_cost`,
  V.35). An ability with no entry uses the dataclass defaults.
- Author it inline on the decorator (`@register_active("...", mana_cost=150_000)`)
  or explicitly via `register_ability_mana(id, mana_cost=…, priority=…)`.
- `ability_mana(id)` resolves the statline (defaults if unregistered); `loadout`
  seeds each `ActiveSlot` from it.

## The hook model (event bus)

A passive/trait/item bundle carries `Hook`s that subscribe to combat events. The
engine fires events on the `EventBus`; a `Hook(event, handler, priority=0,
scope=HookScope.PER_HIT)` runs `handler(ctx, event)`. `HookScope` dedups repeated
fires: `PER_HIT` (every fire), `ONCE_PER_CAST`, `ONCE_PER_TARGET`,
`ONCE_PER_COMBAT`.

The events the engine emits and their typed payloads (`game/events.py`):

| Hook event | Payload | Key fields |
|---|---|---|
| `on_combat_start` / `on_combat_end` | `CombatStartEvent` / `CombatEndEvent` | — |
| `on_tick` | `TickEvent` | `tick` |
| `on_cast` / `on_cast_complete` | `CastEvent` | `caster`, `ability_id`, `cast_id`, `slot_idx`, `mana_cost`, `mana_after` |
| `on_attack_start` / `on_attack_landed` | `AttackEvent` | `attacker`, `target`, `amount` |
| `on_damage_pre` / `on_damage_dealt` / `on_damage_taken` / `on_ability_damage` | `DamageEvent` | `attacker`, `target`, `amount`, `tag`, `is_crit`, `damage_type`, `is_dot` |
| `on_heal` | `HealEvent` | `source`, `target`, `amount` |
| `on_status_applied` / `on_status_expired` | `StatusEvent` | `target`, `status_id`, `duration_ticks`, `stacks` |
| `on_kill` | `KillEvent` | `killer`, `victim` |
| `on_death` | `DeathEvent` | `victim`, `killer` |
| `on_phase_change` | `PhaseEvent` | `piece`, `new_phase` |
| `on_spawn` / `on_despawn` / `on_footprint` | `SpawnEvent` / `DespawnEvent` / `FootprintEvent` | — |

`on_damage_pre` is a **reducing** hook (`bus.fire_reducing`) — its handlers return
a modified damage number (dodge, burst-reduction). The other damage events are
observational. A passive typically guards on identity — `if event.attacker is not
owner: return` — then acts via a `ctx` mutator (`ctx.deal_damage`, `ctx.heal`,
`ctx.apply_status`, `ctx.apply_modifier`, `ctx.grant_barrier`, …).

`SourceTag` (the `event.tag` / damage classification, `effects.py`):
`BASIC_ATTACK`, `ABILITY`, `ITEM_PROC`, `DOT`, `STATUS`, `REFLECT`, `TRUE`.
`ITEM_PROC` is the "follow-up hit" tag that does **not** re-fire
`on_attack_landed`/`on_ability_damage`, so proc/secondary damage can't recurse;
`TRUE` bypasses all mitigation.

### Grounded example — Ember Salamander (`champ_ember_salamander`)

- `.active` "Kindling Light" — `register_active_simple`-style single-target nuke +
  applies `burn`.
- `.active2` "Magma Burst" (`mana_cost=150_000`) — a hand-written handler: picks
  `primary_target`, evals `EMBER_MAGMA_BURST` (a `ScalingTerm`), deals it to every
  enemy in radius 2 via `enemies_in_radius`.
- `.passive` "Smoldering Strikes" — `@register_passive` returning an
  `EffectBundle(hooks=[Hook("on_attack_landed", hook, scope=PER_HIT)])`; the hook
  guards `event.attacker is owner` + `event.target.has_status("burn")`, then deals
  a `ScalingTerm` bonus.

### Boss phase hooks

A boss's `{boss}.phase_hook` is a `@register_passive` returning a
`Hook("on_damage_taken", …, scope=ONCE_PER_COMBAT)`: when the owner drops below the
phase threshold it mutates the piece (grants abilities via `owner.actives.append`,
applies buffs) and fires `on_phase_change` with a `PhaseEvent(new_phase=2)`. The
reference kit `phase_hook_test` in `reference.py` is the minimal template.

## Counts (verified; `/check` re-checks)

- `len(ABILITY_REGISTRY)` = **144**, `len(PASSIVE_REGISTRY)` = **147** (shared
  handlers serve multiple roster ids; the guarantee below is per-roster-id, not
  per-handler).

## The resolution guarantee (CI-guarded)

Every ability/passive id referenced by the roster must resolve to a registered
handler — enforced by guard tests (`tests/game/test_ability_catalog.py`:
`test_all_champion_abilities_resolve` etc.; SPEC §V.15/§V.17). An unregistered id
is a build failure, not a silent generic-fallback. The engine's
unregistered-ability path (`engine._resolve_action`, which casts on full mana and
deals damage **without** spending mana or firing `on_cast`) is only a defensive
fallback, not the norm — and cast-triggered trait/passive riders only fire for
**registered** abilities.

## Ability descriptions (T.34)

A parallel registry `ABILITY_META: dict[str, AbilityMeta]` (in `registries.py`)
gives each roster ability id a tooltip. `AbilityMeta(name, kind, blurb, terms,
clauses, tags)` is presentation metadata; `ability_text.render(meta, source) ->
RenderedAbility(name, text, formula, tags)` is **pure** (no Flet/I-O, extends
V.1) and reads live numbers via `source.stat(name)`. The same call serves both
contexts — a base `Champion`/`Enemy` (roster sheet, via the `.stat()` field
adapters) and a live `Piece` (combat, with modifiers; **bosses always via the
compiled `Piece`**). `render_for(id, source)` is the dict-lookup convenience.

Each scaling term renders its coefficients as **percentages of the source
stat** so players read what a number scales from: `formula` lines read
`550 = 100 + 150% STR + 150% INT  (STR 1.5×150, INT 1.5×150)` — the trailing
note shows each term's contribution math (`coeff×stat`), not the bare stat
value, so the headline number is fully traceable — and `text` carries a
compact inline suffix beside the rendered total (`...550 magic damage. (100
+150% STR +150% INT)`). Pure-flat / no-scaling terms (buffs) add no suffix.

**Source-of-truth B (V.38 + V.46):** every stat-scaled outlet a handler computes
lives **once** in a `Magnitude` the handler reads via `term.eval(...)` — the
tooltip renders the same object, so tooltip and combat numbers cannot drift.
T.35a promoted `ScalingTerm` into a **closed `Magnitude` family** (modeled on
Unreal GAS's `EGameplayEffectModifierMagnitude`), so there is **no** free inline
handler math anymore — the old "Tier-B stays inline + prose" carve-out is gone.
The four kinds (all in `registries.py`, all pure/RNG-free, all self-describing via
`eval`/`render_formula`/`render_inline`/`render_token`):

| kind | shape | absorbs |
|---|---|---|
| `ScalingTerm` | `base + Σ source.stat·coeff` (delegates to `_eval_scaling`) | linear damage/heal/buff/shred |
| `PctResource` | `getattr(obj, resource)·pct`, `of="self"\|"target"` | %-of-max-HP heals (reads `.max_hp` **directly** — `Piece.stat("max_hp")` is 0, see `effects.compute_stat`) |
| `MaxOfTerm` | `base + max(source.stat(s)…)·coeff` | `max(STR,INT)` outlets (non-linear) |
| `SetByCaller` | `base + caller[key]·coeff` (handler injects the runtime value) | per-stack / runtime-count outlets |

`Clause` carries an optional `{token}` `template` + its own `terms`, so a Tier-B
scaler's prose number is filled from the same `Magnitude` the handler reads (A1) —
e.g. Hierarch's `Grants Armor ({armor})…`. `SummonSpec` holds a summon's statline
as `Magnitude` fractions + flat literals (`eval(owner) -> base_stats`), so summon
stats are introspectable, not inline. **A2 guard (`test_no_orphan_stat_reads`,
V.46):** an AST walk fails the build if any handler reads `.stat()`/`.max_hp`
outside a `Magnitude` on its meta — except ids on `_PROSE_ALLOWLIST` (flat
`max_hp +=` growth: `champ_snowpelt_cub.passive`, `champ_glacierback_mammoth.passive`,
`enemy_levyman.passive`). The conversion was **byte-identical** (sim digest unmoved,
V.2/V.14); only the rendered `formula`/`text` of the 15 converted Tier-B abilities
gained their scaling lines.

**Tick → seconds (V.39):** `TICKS_PER_SECOND = 100` in `ability_text.py` is the
single source for the `100 ticks = 1 second` display convention (matches `status.SECS
= 100`). Mechanics stay ticks-only; only `ability_text.render` (and `ui/`, which
imports the constant from here) converts. A coverage guard + golden formula snapshot
(`tests/game/ability_formulas.snapshot.json`) pin every rendered id; regenerate
with `UPDATE_ABILITY_SNAPSHOT=1 uv run pytest tests/game/test_ability_text.py`.

Meta coverage spans **all 285 roster ability ids** (120 champion `.active` T.34a +
120 enemy `.active` T.34b + 36 boss named-id T.34c = 276 base, **+ 9** multicaster
`.active2` secondaries T.29d = 285 — verified `len(ABILITY_META) == 285`).
`tools/export_roster.py` serializes the champion/enemy (and optional boss) rosters
with rendered descriptions to JSON.

## File map

| Concern | Symbol |
|---|---|
| Champion kits | `abilities/champions.py` |
| Enemy kits | `abilities/enemies.py` |
| Boss kits (2-phase, named ids + `.phase_hook`) | `abilities/bosses.py` |
| Shared/declarative templates | `abilities/reference.py`, `registries.register_active_simple` |
| Registries + decorators | `registries.py` (`ABILITY_REGISTRY`, `PASSIVE_REGISTRY`, `@register_active`/`@register_passive`, `register_active_simple`) |
| Mana on the ability def | `registries.py` (`ABILITY_MANA`, `AbilityMana`, `ability_mana`, `register_ability_mana`, `DEFAULT_MANA_COST`) |
| Hooks + events | `effects.py` (`Hook`, `HookScope`, `EventBus`, `SourceTag`, `EffectBundle`), `events.py` (typed payloads) |
| Slot discovery | `content.py` (`discover_abilities`), `piece.py` (`ActiveSlot`, `Piece.actives`) |
| Ability descriptions (T.34/T.35a) | `registries.py` (`ABILITY_META`, `Magnitude` family: `ScalingTerm`/`PctResource`/`MaxOfTerm`/`SetByCaller`, `Clause` w/ `template`+`terms`, `SummonSpec`, `AbilityMeta`), `ability_text.py` (`render` pure per-kind dispatch, `render_for`, `TICKS_PER_SECOND`) |
| id source on the model | `content.py` (`active_ability`/`passive_ability`) |
