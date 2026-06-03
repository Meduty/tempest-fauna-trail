# T20 Plan — Ability, Passive & Status Framework

> **Status:** comprehensive design — ready for admin review & decision on open items.
> **Depends:** T.3 (combat engine), T.1 (models). Resolves SPEC D.3, D.4, D.5.
> **Feeds into:** T.21 (boss phase hooks), T.5 (champion/enemy content), T.22 (augments).
> **Design authority:** `effect_systems_design.md` — this plan is the implementation
> bridge from that doc to code. Where this plan and the effect doc conflict, the
> effect doc wins.

---

## 1. Scope

T20 replaces the T3 MVP's placeholder cast path with the full
ability/passive/status/event framework described in `effect_systems_design.md`.
This is the **engine upgrade** that makes champion kits, boss phases, items,
traits, and augments possible.

**Primary outputs:**
- `src/game/effects.py` — Modifier, Hook, EffectBundle, EventBus, SourceTag, etc.
- `src/game/registries.py` — ABILITY_REGISTRY, ITEM_REGISTRY, TRAIT_REGISTRY, etc.
- `src/game/targeting.py` — targeting helpers
- `src/game/events.py` — event payload dataclasses
- `src/game/status.py` — status definitions
- `src/game/piece.py` — updated Piece/ActiveSlot dataclasses
- `src/game/loadout.py` — the isolation boundary compiler
- `src/game/combat/` — refactored engine subpackage (context, loop, casting, damage, ai)

**Test output:** `tests/game/test_abilities.py`, `tests/game/test_effects.py`

**Out of scope:** full champion/enemy kit *content* (individual ability
implementations). T20 ships the framework + a small set of reference abilities
to validate the pipeline.

---

## 2. Architectural Decision: Direct Mutation via CombatContext

The T20 plan previously specified a **reducer/Effect-ADT** pattern where handlers
return deltas and a centralized reducer applies them. The effect systems design
document (`effect_systems_design.md` §2) has since **rejected this in favor of
direct mutation** through `CombatContext`. The rationale:

- Combat is sequential, single-threaded, one action at a time. There is never
  a race condition or concurrent write.
- Direct mutation produces honest stack traces (`cast_ability → thunder_crash →
  ctx.deal_damage → ionic_shock_hook → ctx.deal_damage`).
- No `Effect` allocation per hit. At 80 champions × 40 enemies, this matters.
- No "effects applied in wrong order" bug class — order is literal call order.

**This plan adopts the direct-mutation architecture.** The old reducer pattern
is withdrawn.

---

## 3. Core Substrate — `effects.py`

Implements `effect_systems_design.md` §4 verbatim:

### 3.1 `Modifier` (frozen dataclass)

Declarative stat delta with:
- `stat: str` — e.g. `"hp"`, `"strength"`, `"attack_speed"`, `"armor"`, etc.
- `op: Literal["add", "mul", "set"]`
- `value: float`
- `lifetime: Lifetime` — `PERMANENT | COMBAT | TIMED | WHILE_CONDITION`
- `source_id: str` — e.g. `"item:rapidfire_cannon"`, `"trait:stormcaller@4"`
- `expires_at_tick: int | None` — for `TIMED`
- `condition: Callable | None` — for `WHILE_CONDITION` (slow path)

**Stat computation order:** `(base + Σ adds) × Π muls`. `set` overrides all;
last `set` wins.

### 3.2 `Hook` & `HookScope`

```python
class HookScope(Enum):
    PER_HIT          = "per_hit"
    ONCE_PER_CAST    = "once_per_cast"
    ONCE_PER_TARGET  = "once_per_target"
    ONCE_PER_COMBAT  = "once_per_combat"
```

The bus enforces scope dedup — handlers never manage their own "already fired"
state. This eliminates the largest source of content bugs.

### 3.3 `EffectBundle`

Registration descriptor (not a runtime value type) containing:
- `modifiers: list[Modifier]`
- `hooks: list[Hook]`
- `statuses: list[tuple[str, int]]`
- `granted_abilities: list[str]`
- `granted_traits: list[str]`

Used identically by items, augments, traits, passives, and boss phase hooks.

### 3.4 `SourceTag`

Damage attribution enum: `BASIC_ATTACK | ABILITY | ITEM_PROC | DOT | STATUS |
REFLECT | TRUE`. Hooks filter on this to distinguish "on basic attack" from
"on ability hit."

### 3.5 `EventBus`

- `subscribe(hook) -> hook_id`
- `unsubscribe(hook_id)`
- `fire(event_name, event)` — synchronous dispatch
- `fire_reducing(event_name, event, value) -> float` — for `on_damage_pre`
- `reset_combat()` — clears `ONCE_PER_COMBAT` ledger

Dispatch order: descending `priority`, then registration order (stable).

---

## 4. Event Taxonomy

Full list per `effect_systems_design.md` §4.6:

| Event | When |
|---|---|
| `on_combat_start` | Once after all bundles applied |
| `on_combat_end` | Once at resolution |
| `on_tick` | Every 10ms tick (use sparingly) |
| `on_cast` | Active ability begins |
| `on_cast_complete` | After active handler returns |
| `on_attack_start` | Basic attack windup |
| `on_attack_landed` | Basic attack hit |
| `on_ability_damage` | Each damage instance from an ability |
| `on_damage_pre` | Before mitigation (reducing — hooks modify amount) |
| `on_damage_dealt` | After damage applied (attacker view) |
| `on_damage_taken` | After damage applied (target view) |
| `on_heal` | After heal applied |
| `on_status_applied` | Status begins |
| `on_status_expired` | Status ends |
| `on_kill` | From killer's perspective |
| `on_death` | From victim's perspective (before removal) |
| `on_mana_full` | Active slot ready to cast |
| `on_phase_change` | Boss phase transition |
| `on_spawn` | Piece appears mid-combat |

Adding new events requires team review — each is a contract content depends on.

---

## 5. `CombatContext` — The Mutator API

Content interacts with the world **only** through CombatContext methods
(`effect_systems_design.md` §5):

### 5.1 Mutators

```python
ctx.deal_damage(attacker, target, amount, tag, crit=None) -> float
ctx.heal(source, target, amount) -> float
ctx.apply_status(target, status_id, duration_ticks, stacks=1)
ctx.remove_status(target, status_id)
ctx.apply_modifier(target, modifier)
ctx.trigger_basic_attack(attacker, target, mult=1.0)
ctx.cast_ability(actor, slot_idx=0)
ctx.gain_mana(actor, amount)
ctx.spend_mana(actor, slot_idx)
ctx.teleport(actor, dest_hex)
ctx.spawn(piece, hex)
ctx.kill(target, killer=None)
ctx.end_combat(winner)
ctx.register_bundle(owner, bundle)
```

### 5.2 Read-only queries

```python
ctx.current_tick -> int
ctx.current_cast_id -> int | None
ctx.weather -> WeatherState
ctx.rng -> SeededRng          # ALL randomness goes through this
ctx.board -> Board
ctx.enemies_of(piece) -> Iterable[Piece]
ctx.allies_of(piece) -> Iterable[Piece]
ctx.is_enemy(a, b) -> bool
ctx.is_alive(piece) -> bool
```

### 5.3 Determinism contract

Two rules content **must** honor:
1. **Randomness only via `ctx.rng`.** CI grep enforces no `random.random()` in `game/`.
2. **Iteration over sets/dicts uses sorted keys** when order is observable.

---

## 6. Ability System

### 6.1 Piece shape

Each piece carries:
- `actives: list[ActiveSlot]` — 0–2 slots (normal: 0–1; boss phase-2: 2)
- `passives: list[str]` — 0–2 passive ability ids

`ActiveSlot` holds: `ability_id`, `cost` (mana), `current_mana`, `priority`.

### 6.2 Three authoring flavours

Per `effect_systems_design.md` §6.2:

**(a) Pure Python handler** — for abilities with branching, weather conditionals,
target filtering:

```python
@register_active("storm_surge")
def storm_surge(ctx, actor, targets):
    base = 50 + compute_stat(actor, "ability_power", ctx) * 2.0
    damage = base * 1.5 if ctx.weather == WeatherState.THUNDER else base
    for t in targets:
        ctx.deal_damage(actor, t, damage, SourceTag.ABILITY)
```

**(b) Declarative simple ability** — for "deal X damage to primary target":

```python
register_active_simple("smash", SimpleActive(
    target=TargetSelector.PRIMARY,
    damage=100, scaling="ad*1.5", tag=SourceTag.ABILITY,
))
```

**(c) Factory-built ability** — stamp out variants from shared shape:

```python
ABILITY_REGISTRY["thunder_crash"] = cone_aoe(damage=180, scaling="ap*1.5", half_to_neighbors=True)
```

**Guideline:** use the simplest flavour that fits.

### 6.3 Targeting helpers (`targeting.py`)

Content must not reach into board state directly. All targeting goes through:

```python
primary_target(actor, ctx) -> Piece | None
lowest_hp_enemy(actor, ctx) -> Piece | None
highest_ap_enemy(actor, ctx) -> Piece | None
random_enemy(actor, ctx) -> Piece | None
neighbors_of(piece, ctx) -> list[Piece]
enemies_in_radius(center, radius, of, ctx) -> list[Piece]
allies_in_radius(center, radius, of, ctx) -> list[Piece]
furthest_enemy(actor, ctx) -> Piece | None
line_targets(actor, direction, length, ctx) -> list[Piece]
```

New patterns are added here and reused — never inlined into abilities.

### 6.4 Passive abilities

Same registry, different return type — a factory that takes the owner and
returns an `EffectBundle` whose hooks close over the owner:

```python
@register_passive("static_buildup")
def static_buildup(owner):
    def hook(ctx, ev):
        if ev.attacker is owner and ctx.weather == WeatherState.THUNDER:
            ctx.apply_status(ev.target, "charged", duration_ticks=200, stacks=1)
    return EffectBundle(hooks=[Hook("on_attack_landed", hook)])
```

### 6.5 Mana & cast resolution — separate pools

Per `effect_systems_design.md` §6.5:
- Boss phase-2 has two actives with **separate mana pools**.
- Mana gain goes to **all** slots in parallel; each caps at its own cost.
- Cast trigger: iterate slots in descending `priority`; first ready slot casts.
  Multiple slots can fire the same tick ("flurry").

---

## 7. Status Effects

### 7.1 Core status definitions

Per `combat_system_proposal.md` §9.4 and the combat engine:

| Status | Effect |
|---|---|
| `stun` | Skip action, pause energy gain, pause mana regen |
| `silence` | Block cast; mana regen continues |
| `disarm` | Block auto-attack; if mana low → idle |
| `root` | Block movement only |
| `burn` | DOT: damage per DOT tick (`dot_interval_ticks`, default 100t=1s; magnitude via `dot_per_tick` or per-instance `potency`) — see SPEC V.25 |
| `slow` | Reduce move_speed for duration |
| `charged` | Conditional flag — other effects check for it |
| `soaked` | Conditional flag — water-themed interactions |
| `frozen` | Like stun + conditional flag for crit interactions |
| `fear` | Forced movement away from source; blocks action |

### 7.2 Status stacking

MVP uses simple stack counts. Per-status custom rules (refresh vs. extend
duration) are deferred until content demands it.

> **⚠ DECISION NEEDED:** Whether `stun` should be **refresh** (reapply resets
> duration to the new value) or **extend** (adds duration). Refresh is simpler
> and prevents CC-lock; extend rewards multi-CC comps.
> **Recommendation:** refresh — prevents unfun permanent CC-lock and is the TFT
> convention.

### 7.3 Status processing in the tick loop

Each tick, before meter updates:
1. **Expire statuses** whose `expires_at_tick <= current_tick`. Fire
   `on_status_expired` for each.
2. **Evaluate `WHILE_CONDITION` modifiers** — remove any whose condition returns
   `False`.
3. **Gate checks:** if piece has `stun` → skip all meter updates; if `silence` →
   skip cast resolution; if `disarm` → skip auto resolution; if `root` → skip
   movement.

---

## 8. Combat Engine Refactoring

### 8.1 From monolith to subpackage

The current `src/game/combat.py` monolith is refactored into:

```
src/game/combat/
  __init__.py     # re-exports: CombatContext, run
  context.py      # CombatContext class
  loop.py         # tick loop, run(loadout) entry point
  casting.py      # active/passive cast resolution, multi-slot mana
  damage.py       # damage pipeline (pre-hooks → mitigation → apply → kill)
  ai.py           # target selection per piece type
```

**Hard import rule:** `combat/` may import `effects.py`, `registries.py`,
`events.py`, `status.py`, stdlib. **Never** content modules.

### 8.2 Damage pipeline

The damage pipeline integrates all damage-modifying systems:

```
raw = base_formula
→ × weather_modifier (Affinity Clash)
→ × 1.5 if crit
→ fire on_damage_pre (reducing — hooks can modify amount)
→ apply penetration: effective_mit = max(0, round(mit × (1 - PEN%)) - PEN)
→ mitigate: reduction = effective_mit / (effective_mit + 100)
→ final = raw × (1 - reduction)
→ fire on_damage_dealt (attacker view)
→ fire on_damage_taken (target view)
→ if target.hp <= 0: fire on_kill, on_death, remove piece
```

### 8.3 Backward compatibility

- T3 MVP behavior is unchanged when no abilities, statuses, or phases are
  present — empty registry == current engine.
- Existing `resolve_combat()` signature stays; internally delegates to the
  new `combat.run()`.

---

## 9. Loadout Compiler — The Isolation Boundary

`loadout.py` is the only module that imports both content registries and combat
types. Application order per `effect_systems_design.md` §10.1:

```
1. Deep-copy input pieces (combat doesn't mutate Run state)
2. Apply items' granted_traits FIRST (emblems visible to trait counting)
3. Resolve trait breakpoints (count unique champion ids)
4. Apply trait bundles (per-trait-piece or team-wide)
5. Apply item bundles (modifiers + hooks)
6. Apply augment bundles (PIECE-filtered, then TEAM)
7. Apply champion passive bundles
8. Apply boss phase-1 passives
9. Wire quest trackers for active RUN-scope augments
10. Fire on_combat_start
```

---

## 10. Critical Strike Hooks

### 10.1 `crit_chance`

Default `0.0` for all pieces. Raised by items, augments, or passives.
Deterministic cadence: piece crits on every `round(1/c)`-th eligible hit.
Counter shared between autos and casts (when `ability_can_crit = True`).

### 10.2 `ability_can_crit`

Default `False`. Set by:
- Mystic @4 trait breakpoint (team-wide for Mystic pieces)
- Spellfang Crown item
- Apex Instinct prismatic augment (team-wide)
- Individual passives

### 10.3 Pipeline order

```
raw → × weather_modifier → × 1.5 if crit → mitigate
```

No RNG — `resolve_combat` remains fully deterministic.

---

## 11. Reference Abilities (shipped with T20)

T20 ships a small set of reference abilities to validate the full pipeline:

| Ability | Type | Tests |
|---|---|---|
| `smash` | Simple active — single-target STR damage | Basic cast pipeline |
| `thunder_crash` | Factory cone AOE | Multi-target, weather conditional |
| `static_buildup` | Passive — on_attack_landed status apply | Event bus, status system |
| `phase_hook_test` | Phase hook — grant ability at 50% HP | Phase transition |
| `heal_pulse` | Simple active — heal lowest ally | Healing pipeline |

These serve as templates for content authors. Each has a corresponding test.

---

## 12. First Passive Content — CLEAR-Weather Buff

`CLEAR` is inert in both weather systems. To give Clear-affinity pieces their
identity, T20 ships a reference passive:

```python
@register_passive("sunlit_vigor")
def sunlit_vigor(owner):
    """CLEAR-affinity pieces gain a stat buff when node weather is CLEAR."""
    def hook(ctx, ev):
        if ctx.weather == WeatherState.CLEAR and owner.affinity == WeatherState.CLEAR:
            ctx.apply_modifier(owner, Modifier("strength", "add", 15, Lifetime.COMBAT, "passive:sunlit_vigor"))
            ctx.apply_modifier(owner, Modifier("intelligence", "add", 15, Lifetime.COMBAT, "passive:sunlit_vigor"))
    return EffectBundle(hooks=[Hook("on_combat_start", hook, scope=HookScope.ONCE_PER_COMBAT)])
```

Pairs with the T21 CLEAR-boss compensating stat bump.

---

## 13. Module Layout

```
src/game/
  effects.py        # Modifier, Hook, EffectBundle, EventBus, SourceTag, HookScope, Lifetime
  registries.py      # @register decorators + registry dicts
  targeting.py       # Targeting helpers
  events.py          # Event payload dataclasses
  status.py          # Status definitions
  piece.py           # Piece, ActiveSlot dataclasses
  loadout.py         # compile_loadout, apply_bundle
  rng.py             # SeededRng

  combat/
    __init__.py      # re-exports CombatContext, run
    context.py       # CombatContext class
    loop.py          # Tick loop
    casting.py       # Cast resolution + multi-slot mana
    damage.py        # Damage pipeline
    ai.py            # Target selection

  abilities/         # Content — one file per affinity + factories
    __init__.py
    factories.py
    simple.py
    storm.py, ember.py, tide.py, earth.py, sun.py, void.py
    boss_phases.py
```

---

## 14. Test Plan

See T.16 for full test details. Summary:

1. **Modifier computation:** `(base + adds) × muls`; `set` override; lifetime
   expiry.
2. **Hook dispatch:** correct priority ordering; scope dedup works for all four
   scope types.
3. **Active ability resolution:** simple, factory, and handler flavours all
   produce expected damage/healing.
4. **Passive ability resolution:** hooks fire on correct events; closures
   capture owner correctly.
5. **Status gates:** `stun` blocks all; `silence` blocks cast only; `disarm`
   blocks auto only; `root` blocks movement only.
6. **Status lifecycle:** apply fires `on_status_applied`; expire fires
   `on_status_expired` at correct tick; stacks work.
7. **Phase hook:** fires once at HP threshold; grants abilities; `ONCE_PER_COMBAT`
   prevents re-fire.
8. **Damage pipeline:** pre-hooks modify damage; penetration applies; mitigation
   applies; kill chain fires correctly.
9. **Determinism:** same inputs → byte-equal `BattleResult` with abilities active.
10. **Backward compatibility:** empty registry produces identical results to T3 MVP.
11. **Import-direction lint:** `combat/` never imports content modules.
12. **`ctx.rng` lint:** no `random.random` / `random.choice` in `game/`.

---

## 15. Acceptance Criteria

1. All modules in §13 exist, pure, zero Flet imports.
2. `CombatContext` mutator API matches §5.
3. Event taxonomy matches §4.
4. All four status gates implemented.
5. Phase hook fires correctly.
6. T3 existing tests still pass with empty registry.
7. Reference abilities (§11) pass their tests.
8. Import-direction and `ctx.rng` lints pass.
9. `tests/game/test_abilities.py` and `tests/game/test_effects.py` pass.

---

## 16. Open Items Summary

| # | Question | Recommendation | Impact if deferred |
|---|---|---|---|
| 1 | Stun refresh vs. extend | Refresh | Low — content handles either; refresh is safer |
| 2 | Starting mana per champion | 0 for MVP; add per-champion starting mana later | Medium — affects early-fight pacing |
| 3 | Mana on damage taken | Not in MVP (TFT uses it) | Medium — revisit if fights feel too slow |
| 4 | Cast time (instant vs. delayed) | Instant for MVP | Low — can add wind-up later |
| 5 | Ability range separate from attack range | Yes, per-ability config | Low — targeting helpers handle it |
| 6 | Combat timeout fallback | Sudden Death: escalating DOT per tick | Low — implement when long fights appear |
| 7 | Multi-instance status stacking semantics | Simple count for MVP | Low — content will force this |
| 8 | Whether `WHILE_CONDITION` modifiers are needed at MVP | Defer — use `TIMED` + hook refresh | Zero — avoids per-tick eval cost |
