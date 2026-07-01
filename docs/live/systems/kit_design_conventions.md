> **Status: LIVING** — the definitive "how to author a champion / enemy / boss kit"
> reference *plus* the balance/identity faults to watch. Must match the primitives in
> `src/game/registries.py`, `src/game/effects.py`, `src/game/events.py`,
> `src/game/status.py`, `src/game/piece.py`, and the mutator surface in
> `src/game/combat/context.py`; and the formulas in `src/game/scaling.py` /
> `src/game/content.py`. Audited by `/check` (every cited symbol/number must resolve;
> the prose rules are review-enforced).
> **Reconciled:** 2026-07-01 @ authoring-reference expansion (verified against T.36 roster).

# Kit design conventions

This doc has two halves. **Part A — How a kit is authored** is the mechanical reference:
the decorators, the `EffectBundle` shape, the closure-per-combat pattern, the `ctx`
mutator API, the event→payload map, dedup semantics, determinism, and the description
layer. **Part B — Faults to watch** is the hard-won balance/identity checklist, each rule
paid for by a real misfit caught mid-design (mostly the T.36 Primordial rework + the
12-piece distribution re-axis).

Read Part A before writing *any* handler; read Part B before authoring or re-axising a kit.

---

# Part A — How a kit is authored

## The content ↔ combat boundary

`game/` is pure logic with zero Flet imports (V.1); combat is a pure function
`resolve_combat(team, enemies, weather) -> BattleResult` (V.2). A kit is **declarative
content** — factories decorated into registries at import time — that the engine looks up
by string id and invokes through the single `CombatContext` mutator surface. Content never
mutates combat state directly; it only calls `ctx` methods, which fire the event bus.

The compile path (`src/game/loadout.py`):

- `compile_loadout(team, enemies, weather, seed=42, run_mods=None)`
  (`loadout.py:315`) builds a `Piece` per model (`piece_from_champion` `loadout.py:156`,
  `piece_from_enemy` `loadout.py:193`), applies weather → items → traits → passives →
  augments as `EffectBundle`s, and returns `(pieces, bus, trait_activations)`.
- `apply_bundle(target, bundle, bus, ctx=None)` (`loadout.py:122`) is the *one* function
  that installs a bundle — used both pre-combat by `compile_loadout` and mid-combat by
  `ctx.register_bundle`. It appends `modifiers`, applies `statuses`, appends
  `granted_abilities` (as `ActiveSlot`s) and `granted_traits`, and `bus.subscribe(hook)`s
  every hook.
- Boss fights additionally call `attach_map_effect(effect_id, ctx, seed)`
  (`loadout.py:228`) **after** building the `CombatContext` and **before** `engine.run(ctx)`
  — see `tools/playtest/_common.py:105` `resolve_boss_combat` for the canonical wiring, and
  `resolve.py:46`.

## Registering an ability

All decorators live in `src/game/registries.py` and populate module-level dicts that the
engine reads by string id. **Unregistered ability ids gracefully no-op** — `cast_ability`
returns early if `ABILITY_REGISTRY.get(id)` is `None` (`context.py:442-444`).

| Decorator | Registry | Factory signature | Returns |
|---|---|---|---|
| `@register_active(id, *, mana_cost=None, max_mana=0, start_mana=0, priority=1)` | `ABILITY_REGISTRY` | `handler(ctx, actor, targets) -> None` | — |
| `@register_passive(id)` | `PASSIVE_REGISTRY` | `factory(owner) -> EffectBundle` | `EffectBundle` |
| `@register_item(id)` | `ITEM_REGISTRY` | `factory(owner) -> EffectBundle` | `EffectBundle` |
| `@register_trait(id)` | `TRAIT_REGISTRY` | `factory() -> list[TraitBreakpoint]` | breakpoints |
| `@register_run_action(id)` | `RUN_ACTION_REGISTRY` | `fn(run, *args) -> None` (V.24, never enters combat) | — |
| `register_active_simple(id, SimpleActive(...))` | `ABILITY_REGISTRY` | synthesised handler | — |

An active handler receives `(ctx, actor, targets)` where `targets` is the list of living
enemies at cast time (`context.py:462`) — most handlers ignore it and re-query via targeting
helpers (`primary_target`, `lowest_hp_ally`, `enemies_in_radius`, `furthest_enemy`, …).

### Mana is per-`ActiveSlot`, not a `Piece` stat

Mana lives on each `ActiveSlot` (separate pool per slot — `piece.py:17`), authored on the
**ability def** via the mana kwargs on `@register_active` (T.29c, V.48):

- `mana_cost` — cast threshold + amount spent per cast. Default `DEFAULT_MANA_COST = 300_000`
  (`registries.py:48`).
- `max_mana` — universal pool cap (regen/start/grant clamp to it). `0` normalizes to
  `2 * mana_cost` (overload headroom, `piece.py:39`).
- `start_mana` — seeds `current_mana` at combat start.
- `priority` — unified rank (≥1): drives both the weighted-rank charge cycle and the
  ≤1-cast-per-window pick.

```python
@register_active("champ_ember_salamander.active", mana_cost=230_000, priority=2)
def ember_salamander_active(ctx, actor, targets):
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, EMBER_SALAMANDER_DMG.eval(actor), SourceTag.ABILITY)
    ctx.apply_status(target, "burn", duration_ticks=secs(6), source_id=actor.id)
```

Omitting the kwargs uses the defaults (byte-identical for single-ability champs). You may
also author a statline separately with `register_ability_mana(id, ...)` (`registries.py:72`).

### `SimpleActive` shorthand

For "deal X + optional heal" abilities, skip the handler and register declaratively
(`registries.py:171`): `SimpleActive(target, damage, scaling, tag, heal_amount,
heal_scaling, heal_target)`. `scaling` is an `_eval_scaling` expression like
`"strength*1.5"` (stat aliases `str/int/atk/spd/mr/arm/res/pen` are accepted). Example from
`reference.py`: `register_active_simple("smash", SimpleActive(target="primary", damage=100.0,
scaling="strength*1.5", tag=SourceTag.ABILITY))`.

## The `EffectBundle` — the registration payload

Passives/items/traits/augments/boss-phase-hooks all return an `EffectBundle`
(`effects.py:180`). It is a descriptor handed to `apply_bundle` once, not a runtime value:

```python
@dataclass
class EffectBundle:
    modifiers: list[Modifier]        = []   # static/timed stat deltas
    hooks: list[Hook]                = []   # event subscriptions
    statuses: list[tuple[str, int]]  = []   # (status_id, duration_ticks) applied at install
    granted_abilities: list[str]     = []   # extra ActiveSlots
    granted_traits: list[str]        = []   # extra trait ids
```

A pure static buff needs only `modifiers` (`goldcrest_lark.passive`):

```python
@register_passive("champ_goldcrest_lark.passive")
def goldcrest_lark_passive(owner):
    return EffectBundle(modifiers=[
        Modifier("intelligence", "add", 10.0, Lifetime.COMBAT, "passive:champ_goldcrest_lark"),
    ])
```

### `Modifier` — declarative stat delta

`Modifier(stat, op, value, lifetime=Lifetime.COMBAT, source_id="", expires_at_tick=None)`
(`effects.py:45`). `op ∈ {"add", "mul", "set"}`. `compute_stat` folds
`(base + Σadds) × Πmuls`, and a `set` overrides everything (last `set` wins)
(`effects.py:66-99`). A per-stat floor clamp applies at the tail (`attack_range ≥ 1`, V.43).

- **`Lifetime`** (`effects.py:19`): `COMBAT` (default — cleared at combat end), `TIMED`
  (removed when `current_tick >= expires_at_tick`, so `TIMED` **requires**
  `expires_at_tick=ctx.current_tick + N`), `PERMANENT` (survives across combats — reserve
  for augments; nothing else should persist, see Fault #11).
- **Stat keys** (the real `base_stats` vocabulary, `loadout.py:160-173`): `strength`,
  `intelligence`, `attack_speed`, `move_speed`, `mana_regen`, `threat`, `armor`,
  `resistance`, `attack_range`, `crit_chance`, `penetration`, `penetration_pct`, plus `hp`.
  The primary damage stats are **`strength`** and **`intelligence`** — there is no
  `attack_damage`/`ability_power`/`mana_max` stat. `max_hp` is a `Piece` *attribute*, not a
  `base_stats` key, so `piece.stat("max_hp")` is `0` — read `owner.max_hp` directly, or use
  a `PctResource` (below).

### `source_id` tagging (V.45)

Every `Modifier.source_id` should carry a `<prefix>:` group so the stat-breakdown UI can
attribute it. The canonical prefixes and order (`effects.py:109`) are: `item:`, `augment:`,
`passive:`, `trait:`, `weather:` — with `ability:<id>` used for a cast-applied buff. Unknown
prefixes sort last. The breakdown telescopes so rows sum exactly to the effective total.

## Hooks — subscribing to the event bus

`Hook(event, handler, priority=0, scope=HookScope.PER_HIT, hook_id="")` (`effects.py:164`).
Hooks fire synchronously inside the `ctx` mutator that produced the event; reentrancy is the
Python call stack. Higher `priority` fires first (`effects.py:217`). Nearly every hook
handler must **filter to its owner first** (`if event.attacker is not owner: return`) because
the bus is global across all pieces.

Two handler shapes:

- **Normal hook** — `handler(ctx, event) -> None`. Fired via `bus.fire(...)`.
- **Reducing hook** — only `on_damage_pre`, fired via `fire_reducing(...)`. Signature
  `handler(ctx, event, value) -> float`; return the (possibly modified) numeric value.
  Used to scale/reduce a hit before mitigation (`aegis_tortoise.passive` returns `value*0.8`
  for adjacent attackers; `nerei.passive` amplifies by grudge stacks).

### Which event fires which payload

Payloads are plain dataclasses in `src/game/events.py`. The engine fires these exact strings
(confirmed across `combat/*.py` + `context.py`):

| Event string | Payload | Key fields |
|---|---|---|
| `on_combat_start` | `CombatStartEvent` | — (fires once, after all bundles applied) |
| `on_combat_end` | `CombatEndEvent` | `winner` (`"team"/"enemy"/"draw"`) |
| `on_tick` | `TickEvent` | `tick` — *use sparingly* |
| `on_cast`, `on_cast_complete` | `CastEvent` | `caster`, `ability_id`, `cast_id`, `slot_idx`, `mana_cost`, `mana_after` |
| `on_attack_start`, `on_attack_landed` | `AttackEvent` | `attacker`, `target`, `amount` — **NO `.tag`** |
| `on_damage_pre` (reducing), `on_damage_dealt`, `on_damage_taken`, `on_ability_damage` | `DamageEvent` | `attacker`, `target`, `amount`, **`tag`** (str), `cast_id`, `hit_id`, `is_crit`, `damage_type`, `is_dot` |
| `on_heal` | `HealEvent` | `source`, `target`, `amount` |
| `on_status_applied`, `on_status_expired` | `StatusEvent` | `target`, `status_id`, `duration_ticks`, `stacks` |
| `on_kill` | `KillEvent` | `killer`, `victim` |
| `on_death` | `DeathEvent` | `victim`, `killer` (may be `None`) |
| `on_spawn` | `SpawnEvent` | `piece`, `position` |
| `on_despawn` | `DespawnEvent` | `piece` (summon expiry — **not** a death, G6) |
| `on_footprint` | `FootprintEvent` | observer-only cast geometry telemetry (V.61) |

**The `AttackEvent` / `DamageEvent` split is a common trap.** `on_attack_landed` carries an
`AttackEvent` with only `attacker`/`target`/`amount` — it has **no `.tag`**. If you need the
`SourceTag`, the `damage_type`, `is_crit`, or `is_dot`, hook `on_damage_dealt`/
`on_damage_taken`/`on_damage_pre` which carry a `DamageEvent` (whose `.tag` is the *string*
value, e.g. compare against `SourceTag.REFLECT.value`, as in `holloway.cinder_husk`).

Two payloads are **defined but not wired by the engine**: `ManaEvent`/`on_mana_full` (no
engine `fire`), and `PhaseEvent`/`on_phase_change` — the latter is fired *by content*, from a
boss phase hook via `ctx.fire("on_phase_change", PhaseEvent(...))` and by `map_effects.py`,
not by the engine loop. Do not subscribe expecting the engine to raise them.

### `HookScope` dedup (`effects.py:152`, `269-302`)

The bus dedups by scope so a single logical effect doesn't multi-fire:

- `PER_HIT` — never deduped; fires on every matching event (the default).
- `ONCE_PER_CAST` — one fire per `cast_id`; needs a cast in flight (no-op filter if `cast_id`
  is `None`). Cleared when the cast completes (`clear_cast`).
- `ONCE_PER_TARGET` — one fire per `(cast_id, target)`.
- `ONCE_PER_COMBAT` — one fire for the whole battle; ledger cleared at `reset_combat`.

Use `ONCE_PER_COMBAT` for on-combat-start buffs (`sunlit_vigor`) and once-ever phase gates.
Use `ONCE_PER_CAST` for "react to my own heal without recursing" (`dawnwisp.passive`) or
"once per damage-taken event" ramps (`sunmane_lion.passive`).

## The closure-per-combat pattern

A passive factory is called **once per combat** (pieces rebuild every `resolve_combat`, V.2),
so per-combat mutable state lives in a **closure dict** the hook closes over. This is how
counters/flags/timers persist within a fight and reset between fights *by construction*:

```python
@register_passive("champ_veldt_pronghorn.passive")
def veldt_pronghorn_passive(owner):
    state = {"count": 0}                      # per-combat state
    def hook(ctx, event):
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 3 == 0:           # deterministic cadence — every 3rd auto
            ctx.deal_damage(owner, event.target, event.amount * 0.5,
                            SourceTag.BASIC_ATTACK, damage_type="physical")
    return EffectBundle(hooks=[Hook("on_attack_landed", hook, scope=HookScope.PER_HIT)])
```

Common closure idioms: cadence counters (`% N`), "empower next auto" flags across the
active→passive boundary (`mirage_caracal.passive`, or via a `soul_charged` marker status), and
periodic-tick timers keyed on `ctx.current_tick - state["last_tick"] >= interval`
(`springfrog.passive`).

## The `ctx` mutator API (`src/game/combat/context.py`)

A handler/hook touches the world **only** through these methods. Damage/heal/status all fire
their own downstream events (so a `deal_damage` can trigger another piece's `on_damage_taken`).

- `deal_damage(attacker, target, amount, tag, *, crit=None, damage_type="magical",
  is_dot=False) -> float` — the core damage pipeline (`context.py:194`): raw × weather-affinity
  clash × crit → `on_damage_pre` (reducing) → mitigation → apply (barriers soak first) →
  `on_damage_dealt` → `on_damage_taken` → `on_ability_damage` (if `tag == ABILITY`) → kill
  check. `damage_type` is a **closed vocabulary** `{"physical", "magical", "true"}` (V.58) —
  an unknown string raises. `physical`→armor, `magical`→resistance, `true`/`SourceTag.TRUE`→
  unmitigated. `crit=None` lets the deterministic crit cadence decide (see below). Returns the
  final amount dealt (use it to scale lifesteal/reflect — `sunmane_lion`, `riptide_caiman`).
- `heal(source, target, amount) -> float` — clamps to missing HP, honours `grievous`
  antiheal (`GRIEVOUS_HEAL_MULT = 0.5`), fires `on_heal`.
- `grant_barrier(target, amount, duration_ticks=0)` — temp absorb pool, consumed before HP,
  not counted in hp/max_hp (distinct from armor/resistance "shield" buffs).
- `apply_status(target, status_id, duration_ticks, stacks=1, source_id="", potency=0.0)` —
  one instance per status per piece; raises on an unknown `status_id`. `cc_immune` pieces
  ignore hard-CC (gate-bearing) statuses. On merge the **stronger `potency` wins**.
- `remove_status(target, status_id)`, `apply_modifier(target, modifier)`.
- `trigger_basic_attack(attacker, target, mult=1.0)` — resolves an auto: fires
  `on_attack_start`, computes `(1.0·STR + 0.25·INT)·mult` as **physical** `BASIC_ATTACK`
  damage (`context.py:422`), fires `on_attack_landed`.
- `cast_ability(actor, slot_idx=0)`, `gain_mana(actor, amount)` (adds to **all** slots,
  clamped to `max_mana`), `teleport`, `spawn`, `expire_summon`, `kill`, `revive`,
  `end_combat`, `register_bundle(owner, bundle)` (mid-combat install), `fire(event, payload)`,
  `note_footprint(...)` (observer-only view telemetry, V.61).
- Read-only queries: `enemies_of`, `allies_of`, `living_pieces`, `is_enemy`, `is_alive`,
  `both_sides_alive`, and properties `current_tick`, `current_cast_id`, `weather`, `rng`,
  `bus`, `board_state`.

### The free-auto subsidy is baked into the engine

Every STR- or hybrid-stat piece has *live* autos worth `1.0·STR + 0.25·INT` per swing
(`context.py:422`) whether or not its kit references them. This is the mechanical basis of
Fault #4: it is why a STR/`ability` piece's ability coeff sits below its INT peer's.

## Determinism (V.2 / V.14) — non-negotiable

Sims must stay byte-identical, so **every "chance" / "every Nth" / ramp uses a deterministic
cadence counter, never RNG**. The engine's own crit is the template (`context.py:246-250`):
`crit_counter += 1`; `cadence = max(1, round(1/crit_chance))`; crit and reset when the counter
reaches cadence. Kits follow suit — `veldt_pronghorn` fires every 3rd auto via `% 3`;
`glade_heron`'s poison uses percentage decay (`decay_fraction`, `status.py:60`) to reach a
deterministic plateau rather than a random shed. A `SeededRng` exists on `ctx.rng` for cases
that genuinely need draws, but it must be seeded from the combat seed. Prefer cadence.

## Statuses (`src/game/status.py`)

Statuses are id-based `StatusDef`s in `STATUS_DEFS`; `secs(x)` converts seconds → ticks
(`SECS = 100`, tick = 10 ms). `StackBehaviour` is `REFRESH` (reapply resets duration — most
CC) or `STACK` (poison/slow/sudden_death/stone_charge/nerei_grudge). `StatusGate` flags what a
piece can't do: `BLOCKS_ACTION` (stun/frozen/fear), `BLOCKS_CAST` (silence), `BLOCKS_ATTACK`
(disarm), `BLOCKS_MOVEMENT` (root/frozen), `HEXPROOF` (excluded from single-target acquisition;
AoE still hits, V.40). Shipped statuses: `stun, silence, disarm, root, burn, poison, slow,
charged, focus_fire, grievous, hexproof, taunt, soaked, frozen, fear, sudden_death, grief,
stone_charge, soul_charged, nerei_grudge`. DOTs run on a free-running clock
(`dot_interval_ticks`, default 100 = 1 s) that is **not** reset by reapply spam; `potency`
overrides per-DOT-tick damage.

## The description layer (T.34, V.38/V.46) — `AbilityMeta` + `Magnitude`

The tooltip/combat-log presentation is a *parallel* registry `ABILITY_META` keyed by the same
ability ids. The rule (source-of-truth B): a handler and its tooltip read the **same**
`Magnitude` object, so their numbers can never drift. Author the headline number as a
module-level `Magnitude`, call `.eval(actor)` in the handler, and pass the same object into
the meta's `terms`.

The **closed** `Magnitude` family (`registries.py`, all pure + RNG-free, all self-rendering):

- `ScalingTerm(label, base, scaling="", note="")` — linear `base [+ stat*coeff …]`; `eval`
  reuses `_eval_scaling`. The workhorse (e.g. `ScalingTerm("damage", 100.0, "strength*1.5")`).
- `PctResource(label, pct, of="self"|"target", resource="max_hp", note="")` — %-of-a-resource;
  reads the attribute **directly** (used precisely because `stat("max_hp")` is `0`).
- `MaxOfTerm(label, coeff, stats=("strength","intelligence"), base=0.0)` — `base + max(stats)·coeff`
  (the non-linear `max()` `ScalingTerm` can't express).
- `SetByCaller(label, base=0.0, coeff=1.0, key="stacks")` — a runtime value the handler injects
  via `eval(caller={key: n})`; renders the *rate*.

`AbilityMeta(name, kind, blurb, terms=(), clauses=(), tags=())` — `blurb` prose has `{label}`
slots filled by the matching term; `clauses` are extra sentences (conditionals, cadences,
status durations) that may carry their own `terms` via a `Clause(text=…)` or
`Clause(template="…{token}…", terms=(…,))`. `tags` here are **UI-iconography** labels owned by
this layer — not the trait/role vocabulary.

```python
DAWNWISP_HEAL = ScalingTerm("heal", 40.0, "strength*3.6")

@register_active("champ_dawnwisp.active")
def dawnwisp_active(ctx, actor, targets):
    ally = lowest_hp_ally(actor, ctx)
    if not ally:
        return
    ctx.heal(actor, ally, DAWNWISP_HEAL.eval(actor))   # handler reads the term

ABILITY_META["champ_dawnwisp.active"] = AbilityMeta(
    name="Knit Wound", kind="active",
    blurb="Mend the lowest-HP ally for {heal}.",         # tooltip reads the SAME term
    terms=(DAWNWISP_HEAL,), tags=("heal",),
)
```

## Enemy kits

Enemies register with the same decorators; they are usually simpler (one active, one passive)
and carry no items (`piece_from_enemy`, `loadout.py:193`). A summon uses a `SummonSpec` for the
statline and `ctx.spawn` to place a full `Piece` (G6 — summons are real pieces flagged
`summon=True`, expiring via `expire_summon` → `on_despawn`, never `on_death`):

```python
_STEAM_TURRET = SummonSpec(stats={
    "max_hp": PctResource("max_hp", 0.25),
    "intelligence": ScalingTerm("intelligence", 0.0, "intelligence*0.79"),
    "armor": 20, "resistance": 20, "attack_speed": 80, "attack_range": 3,
    # …flat literals pass through verbatim…
})

@register_active("enemy_steam_engineer.active")
def steam_engineer_active(ctx, actor, targets):
    from src.game.piece import Piece
    turret = Piece(id=f"{actor.id}_turret_{ctx.current_tick}",
                   base_stats=_STEAM_TURRET.eval(actor), affinity=actor.affinity,
                   is_enemy=actor.is_enemy, summon=True, summon_owner_id=actor.id,
                   summon_expires_tick=ctx.current_tick + 1200)
    turret.hp = turret.max_hp = turret.base_stats["max_hp"]
    ctx.spawn(turret, actor.position_q + 1, actor.position_r)
```

## Boss kits — phase hooks + map effects

Bosses add two things on top of a normal kit. A **phase hook** is a passive whose hook watches
`on_damage_taken` (guarded by a `state["triggered"]` flag + `ONCE`-style scope), swaps the
boss's `actives`, installs a phase-2 passive with `ctx.register_bundle`, and announces the
transition with `ctx.fire("on_phase_change", PhaseEvent(...))`:

```python
@register_passive("holloway.phase_hook")
def holloway_phase_hook(owner):
    state = {"triggered": False}
    def hook(ctx, event):
        if event.target is not owner:
            return
        if not state["triggered"] and owner.hp_pct <= 0.5:
            state["triggered"] = True
            owner.actives = [ActiveSlot(ability_id="holloway.magma_heave", mana_cost=...)]
            ctx.register_bundle(owner, holloway_cinder_husk(owner))       # phase-2 passive
            ctx.fire("on_phase_change", PhaseEvent(piece=owner, new_phase=2))
    return EffectBundle(hooks=[Hook("on_damage_taken", hook, scope=HookScope.PER_HIT)])
```

The **map effect** is attached separately (not a bundle): `attach_map_effect(effect_id, ctx,
seed)` after building the context, before `engine.run(ctx)` (`loadout.py:228`; wiring in
`tools/playtest/_common.py` `resolve_boss_combat`). It subscribes its own hooks to `ctx.bus`
and writes `ctx.board_state`. On-death bursts are just a passive hooking `on_death`
(`holloway.boiler_burst`).

---

# Part B — Faults to watch

Each rule below was paid for by a real misfit caught mid-design. Read before authoring or
re-axising a kit.

## Identity & role

1. **The Calling fixes the *playstyle*; the stat stays flexible.**
   Cast-Callings (Channeler / Mystic / Multicaster / Warden / Mender) → `ability`.
   Auto-Callings (Hunter / Skirmisher / Stalker / Bruiser) → `auto`. Guardian = tank,
   *leans* cast but soft. **Never put a Channeler in an `auto` cell or a Hunter in an
   `ability` cell** — the kit reads wrong even when the numbers are fine. (T.36 caught this
   in 3 of 6 kings + 4 of 12 distribution pieces; the original plan draft had them
   backwards.) When a target cell needs a playstyle the Calling fights, the cheap fix is a
   **minimal, lore-natural Calling tweak** (add an auto-Calling), not a forced playstyle.

2. **Hold `intent` → preserve the role. Flex `stat` + `playstyle` freely.**
   `classify_role(stat, reach, durability, playstyle, speed, intent)` — `intent` (with
   durability) is the dominant role lever. Changing stat/playstyle reshapes *how* a piece
   fights; changing intent silently changes *what role it is*. A Hunter at `intent=utility`
   is still a **support** that happens to auto-attack — not all auto-Callings are dealers.
   Verify `build_role_code` before/after any re-axis; if the role moved and you didn't mean
   it to, you changed intent by accident.

3. **Don't erase a piece's soul when you re-axis it — relocate it.**
   dusk_bat (debuff-support) flipped to `str/auto` kept its blind by moving it *onto the
   autos*. phantom_lynx kept its pen/ghost identity by moving "ignore defense" onto a
   true-damage empowered auto. The mechanic moves to the new playstyle; the fantasy stays.

## Coefficients & scaling

4. **`str/ability`: the ability is the main value; the STR coeff sits *below* the INT
   baseline.** The free auto-attack tagalong already pays STR (autos are `1.0·STR + 0.25·INT`,
   `context.py:422`). Parity vs the INT coeff it replaces:
   `coeff_str ≈ coeff_int − 0.667·(autos_per_cast)` → a ranged caster lands ~1.1–1.7; AoE+CC
   sits at the low end (the CC is the payoff). **Not** the old "ability empowers autos"
   steroid. (Mournhollow's naive `STR·2.7` was ~2× over.)
   **The free-auto subsidy is universal — it applies to casters and supports too, not just
   carries.** Any STR- or hybrid-*stat* piece has live autos (`1.0·STR` base) that out-chip an
   INT peer's dead `0.25·STR` autos *for free*, even at a caster's low attack_speed (measured: a
   hybrid-stat support out-chips an INT support by ~5–18 DPS from the stat alone). So a
   STR/hybrid-stat **support's** ability coeff must also be discounted vs its INT peers, or it
   out-budgets them (T.36b: `dawnwisp` flipped int→str support with its heal discounted
   `INT·4.55→STR·3.6`, ~0.8× for the subsidy — see the `DAWNWISP_HEAL` snippet above). The
   naive `int/ability → str/ability` stat-swap that keeps the old INT coeff (mirewarden,
   hollow_elk had `INT·3.3–3.9`) is the same landmine — drop the coeff hard on the swap.

4b. **When a re-axis produces a role that *misrepresents* the piece, suspect a taxonomy hole —
   don't force a misfit.** A ranged playstyle-`hybrid` damage dealer (casts *and* autos)
   classified as `marksman` because `classify_role` lumps hybrid-playstyle with auto. That was
   a real hole — the ranged analog of `spellblade` (which is *stat*-hybrid). Fix = a new role
   (`Spellslinger`), not a contorted axis. Check `build_role_code`/`classify_role` on every
   re-axis; an off-reading role is a signal.

5. **`*/auto` (str/auto, int/auto, hybrid/auto): the autos must carry — fold the active's
   payoff *into* an auto.** Patterns: on-hit proc (`int/auto` = on-hit-INT, no STR — see
   `mirewarden_toad.passive` routing `intelligence*0.7` onto its autos), empower-next-auto
   (Yorick-style, `mirage_caracal`/`phantom_lynx` via `soul_charged`), discharge-on-auto
   (`granite_gorilla`). If the piece "doesn't care about its autos," it isn't really an auto
   piece. Autos default to `1.0·STR + 0.25·INT` — an int/auto piece with no INT-on-auto routing
   ships with **dead autos** (the real mirewarden bug).

6. **Beware the hidden multiplier: per-event scaling × event count.**
   `charge += STR·k` *per blow* over `N` blows = an effective coeff of `k·N`, not `k`. A tank
   eats many hits → `N` is large → a normal-looking `k` becomes a hypercarry coeff, and stat
   items then scale it. **Fix:** keep `k` low *and* hard-cap the accumulator (`charge ≤
   STR·1.5`) so the `N` multiplier can't run — leaving linear stat scaling. Same family as
   the Aurion bug (`+1 primary/tick` → ~600% over a fight, fixed by a cast-driven ramp capped
   at `_AURION_STACK_CAP = 8`, `champions.py`); both are unbounded per-tick/per-event ramps.
   Always bound a ramp by stacks or a cap.

7. **Size penetration against the actual resistance ceiling.**
   Penetration is a **global attacker stat** (`penetration` / `penetration_pct`,
   `context.py:269-270`), *not* per-hit — you cannot scope it to one damage instance. Flat
   pen subtracts from mitigation, so it **zeroes any target whose res < pen**. Max resistance
   in the roster ≈ **359** (T7 tanky_arm), typical big tank ~286, `MITIGATION_CONSTANT=100`
   (`context.py:49`). Size flat pen so it shreds tanks *partially* and never blankets the
   midfield (phantom's `INT·0.12` peaks ~49 ≈ 14% of max res; `INT·0.3` zeroed everything
   under 123).

8. **True damage is premium → lower its coeff than a magic hit.**
   `SourceTag.TRUE` / `damage_type="true"` bypasses **all** mitigation (`context.py:266`).
   Prefer it over penetration for an "ignore defense" finisher, but price it below a mitigated
   nuke.

## Retaliation, sustain, persistence

9. **Never tie retaliation to a flat/% of *incoming* damage when HP pools are asymmetric.**
   A tank reflecting %-of-hit returns trivial damage to itself but *lethal* chip to a squishy
   — worst case **a squishy dies faster attacking the tank than the tank dies**. Punishes the
   wrong axis. Use a banked-and-discharged model directed at the retaliator's *own* target,
   capped, scaled by the retaliator's own stat (not enemy damage). (granite_gorilla.) When you
   do reflect (`holloway.cinder_husk`), tag it `SourceTag.REFLECT` and early-return on an
   incoming `REFLECT` hit to prevent mutual-reflect recursion.

10. **Scope a diver's sustain to its own commitment, not a passive omni-stat.**
    A squishy auto-carry/swashbuckler gets lifesteal tied to its burst/true-strike (so it
    must commit and land to be rewarded), never free lifesteal on every hit. (phantom_lynx
    reaps only off the empowered true-damage auto; `riptide_caiman` heals a share of its Death
    Roll's dealt damage via the `deal_damage` return value.)

11. **Piece stat-stacking is in-combat only; cross-`Run` permastacking is augment-exclusive.**
    Combat is a pure function (V.2) — all piece runtime state rebuilds per `resolve_combat`,
    so nothing persists across battles by construction. Use `Lifetime.COMBAT`/`TIMED`, never
    `Lifetime.PERMANENT`, for a kit modifier. Write blurbs as "until end of battle," never
    "permanently" (which mislabels an in-combat ramp).

## Process & verification

12. **The analytic DPS / HP·DPS proxy is a smoke-detector, not a scale.**
    Single-target DPS *understates* AoE+CC casters (no AoE multiply, no CC value) and
    auto-carries with uncounted procs/steroids. Use it to catch a piece sitting wildly
    off-budget (it caught Mournhollow at ~147k). The real gate is the V.33 ±10% HP·DPS proxy
    + `tools/simulation/stat_edge.py` teamfight sims.

13. **"power" is reserved.** `scaling.power(T,L) = 2^((T-1)/3 + triplings(L))` is the abstract
    power scalar. The survivability×damage worth proxy is **HP·DPS** — never call it "power."

14. **Determinism is non-negotiable (V.2/V.14).** Every "every Nth" / "chance" / ramp uses a
    deterministic cadence counter (like `crit_counter`), never RNG — sims must stay
    byte-identical. See Part A → Determinism for the primitives.

15. **When reshuffling axis assignments, preserve the *destination cell multiset*.**
    The stat×playstyle grid marginals are the contract, not which piece sits where. Reassign
    freely to honor Callings as long as the multiset of target cells is unchanged — the grid
    still lands exactly. (Both T.36a kings and T.36b distribution were corrected this way with
    zero grid impact.)
