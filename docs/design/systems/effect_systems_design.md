# Effect Systems Design — Tempest Fauna Trail

**Scope:** abilities, traits, items, augments — design as one substrate, four thin content registries.
**Audience:** engineers extending the engine; content designers adding champions, items, traits, augments.
**Status:** approved direction; supersedes the T20 effect/reducer sketch.

---

## 1. Goals & non-goals

**Goals**
- One shared effect substrate that all four content systems plug into.
- Combat engine (`combat/`) stays dumb: never imports content modules.
- Content authoring is mostly declarative; complex content drops into Python without ceremony.
- Deterministic, seeded, reproducible combat.
- Maintainable at scope (~80 champions, ~40 enemies, 6 cities, dozens of items / augments / traits).

**Non-goals**
- No data-driven mini-DSL for ability logic. Python is the DSL.
- No networking, no rollback, no concurrent simulation. Combat is sequential and that fact is exploited.
- No live-modding or hot-reloading content (could be added later — registry pattern supports it).

---

## 2. Architectural principle: sequential compute, direct mutation

Combat runs in a single Python process, one action at a time, advancing in 10 ms ticks. There is never a race, never simultaneity, never a need to merge concurrent writes.

This kills the main reason engines use Effect-as-data + reducer-dispatch (the T20 sketch). Instead:

- **Handlers mutate world state directly** through methods on `CombatContext`.
- **The event bus fires hooks synchronously** inside those mutators.
- **Reentrancy is the Python call stack** — nothing more.
- **`EffectBundle` is a static registration descriptor**, not a runtime value type.

Consequences:
- Stack traces tell the truth (`cast_ability → thunder_crash → ctx.deal_damage → ionic_shock_hook → ctx.deal_damage`).
- No `Effect` allocation per hit. With ~80 champions × ~40 enemies in long fights, the savings matter.
- No "applied effects in wrong order" bug class — order is literal call order.
- Designers write what they mean.

Trade-off: a hook that triggers a cast that triggers a hook *can* recurse. In practice these chains terminate; Python's recursion limit is the safety net. We log a warning on stack depth > 64 inside combat to catch runaway content.

---

## 3. Layering & isolation boundary

```
┌─────────────────────────────────────────────────────────────────┐
│  content/   abilities/  items/  traits/  augments/  champions/  │
│            (each module: data + @register-decorated factories)  │
└────────────────────────────┬────────────────────────────────────┘
                             │ imports
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  loadout.py  — compiles team + items + traits + augments        │
│                into an initialised CombatLoadout                │
│                THIS IS THE ISOLATION BOUNDARY                   │
└────────────────────────────┬────────────────────────────────────┘
                             │ imports
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  registries.py — ABILITY_REGISTRY, ITEM_REGISTRY, …             │
│  targeting.py  — lowest_hp_enemy, neighbors_of, in_radius, …    │
│  effects.py    — Modifier, Hook, EffectBundle, EventBus,        │
│                  SourceTag, HookScope, Lifetime                 │
└────────────────────────────┬────────────────────────────────────┘
                             │ imports
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  combat/  — CombatContext, tick loop, cast & damage pipelines   │
│             (subpackage; __init__ re-exports CombatContext, run)│
│             NEVER imports content modules                       │
└─────────────────────────────────────────────────────────────────┘
```

**Hard rules** (enforced by lint / CI grep, see §13):

- The `combat/` package may import: `effects.py`, `registries.py`, `events.py`, `status.py`, stdlib.
- The `combat/` package may **not** import: `abilities/*`, `items/*`, `traits/*`, `augments/*`, `champions/*`.
- Content modules may import: `effects.py`, `registries.py`, `targeting.py`, `events.py`, `scaling.py`, stdlib.
- Content modules may **not** import: `combat/*`, `loadout.py`, each other across categories.
- `loadout.py` is the only module that may import both content registries and combat types.

Top-level orchestration (`game/run.py` or app entrypoint) imports content packages once at startup to trigger `@register` side-effects, then runs combats through `loadout.compile_loadout(...) → combat.run(...)`.

---

## 4. Core substrate (`effects.py`)

All types are frozen dataclasses unless noted. No game-specific logic lives here — this is the vocabulary.

### 4.1 `Modifier` — declarative stat delta

```python
@dataclass(frozen=True)
class Modifier:
    stat: str                       # "attack_damage", "ability_power", "hp", "armor", "magic_resist", "attack_speed", "crit_chance", "mana_max", ...
    op: Literal["add", "mul", "set"]
    value: float
    lifetime: Lifetime              # see below
    source_id: str                  # "item:rapidfire_cannon", "trait:stormcaller@4", "augment:storm_blessing", "ability:storm_surge#passive"
    expires_at_tick: int | None = None      # for TIMED
    condition: Callable | None = None       # for WHILE_CONDITION; slow path
```

`Lifetime` values:

| Value | Meaning |
|---|---|
| `PERMANENT` | Survives across combats. Stored on the Piece. Used by trait grants that persist (rare), and by base-stat-style modifiers from items in TFT-style "items don't move" runs. In practice almost all of ours are `COMBAT`. |
| `COMBAT` | Cleared at `on_combat_end`. The default. |
| `TIMED` | `expires_at_tick` set; removed when `ctx.current_tick >= expires_at_tick`. |
| `WHILE_CONDITION` | `condition(ctx, owner) -> bool` re-evaluated each tick. Slow path; use only when other options can't express the rule. |

Stats are read via a single function:

```python
def compute_stat(piece: Piece, stat: str, ctx: CombatContext) -> float:
    base = piece.base_stats.get(stat, 0.0)
    additive = sum(m.value for m in piece.modifiers if m.stat == stat and m.op == "add")
    multiplicative = math.prod(
        m.value for m in piece.modifiers if m.stat == stat and m.op == "mul"
    ) or 1.0
    setters = [m.value for m in piece.modifiers if m.stat == stat and m.op == "set"]
    if setters:                              # last "set" wins
        return setters[-1]
    return (base + additive) * multiplicative
```

Order of operation: `(base + sum(adds)) * prod(muls)`. `set` overrides everything; if multiple, the last wins (deterministic by application order). Document this on every Modifier-emitting helper.

### 4.2 `Hook` & `HookScope` — event subscriptions

```python
class HookScope(Enum):
    PER_HIT          = "per_hit"           # fire on every event instance (default)
    ONCE_PER_CAST    = "once_per_cast"     # dedup by (hook_id, current_cast_id)
    ONCE_PER_TARGET  = "once_per_target"   # dedup by (hook_id, current_cast_id, target.id)
    ONCE_PER_COMBAT  = "once_per_combat"   # dedup by hook_id, reset on combat start

@dataclass
class Hook:
    event: str                                              # event name, e.g. "on_attack_landed"
    handler: Callable[[CombatContext, Event], None]         # mutates ctx; returns None
    priority: int = 0                                       # higher fires first
    scope: HookScope = HookScope.PER_HIT
    hook_id: str = ""                                       # auto-assigned at subscribe time, used as dedup key
```

The bus enforces scope. Handlers do not manage their own "already fired this cast" state — that bug surface is moved into one place.

### 4.3 `EffectBundle` — registration payload

Every piece of content (item, augment, trait breakpoint, ability passive) returns one of these from its factory. **It is not a runtime value type** — it's the description handed to `apply_bundle()` once, at loadout time or phase-change time.

```python
@dataclass
class EffectBundle:
    modifiers: list[Modifier] = field(default_factory=list)
    hooks: list[Hook] = field(default_factory=list)
    statuses: list[tuple[str, int]] = field(default_factory=list)  # (status_id, duration_ticks)
    granted_abilities: list[str] = field(default_factory=list)      # ability ids to append to actor.actives
    granted_traits: list[str] = field(default_factory=list)         # trait ids — used by emblems
```

### 4.4 `SourceTag` — damage attribution

Every damage instance carries one. Hooks filter on it.

```python
class SourceTag(Enum):
    BASIC_ATTACK = "basic_attack"
    ABILITY      = "ability"
    ITEM_PROC    = "item_proc"
    DOT          = "dot"           # damage-over-time tick (burn, poison)
    STATUS       = "status"        # damage from a status effect (reserved; usually use DOT)
    REFLECT      = "reflect"       # damage from a reflect proc — does NOT re-trigger on_damage_dealt cascades
    TRUE         = "true"          # bypasses mitigation; still tagged so hooks can distinguish
```

### 4.5 `EventBus`

```python
class EventBus:
    def subscribe(self, hook: Hook) -> str:
        """Returns assigned hook_id."""
    def unsubscribe(self, hook_id: str) -> None: ...
    def fire(self, event_name: str, event: Event) -> None: ...
    def fire_reducing(self, event_name: str, event: Event, value: float) -> float:
        """For 'on_damage_pre' style hooks that modify a numeric value through the chain."""
    def reset_combat(self) -> None:
        """Clear ONCE_PER_COMBAT dedup ledger."""
```

Dispatch order within one event: descending `priority`, then registration order (stable). Dedup ledger is a dict keyed by `(scope_kind, hook_id, *scope_args)` cleared per-cast / per-combat as appropriate.

### 4.6 Event taxonomy

Full list. Add to this only with team review — every addition is a contract content depends on.

| Event | Payload | Fires |
|---|---|---|
| `on_combat_start` | `CombatStartEvent(loadout)` | Once at combat init, after all bundles applied. |
| `on_combat_end` | `CombatEndEvent(winner)` | Once at combat resolution. |
| `on_tick` | `TickEvent(tick)` | Every 10 ms tick. Use sparingly — fires for everyone. |
| `on_cast` | `CastEvent(caster, ability_id, cast_id)` | When an active ability begins. |
| `on_cast_complete` | `CastEvent(...)` | After the active handler returns. |
| `on_attack_start` | `AttackEvent(attacker, target)` | Basic attack windup. |
| `on_attack_landed` | `AttackEvent(attacker, target, amount)` | Basic attack hit. (Ability-triggered basic attacks fire this too.) |
| `on_ability_damage` | `DamageEvent(attacker, target, amount, cast_id, hit_id)` | Each damage instance from an ability. |
| `on_damage_pre` | `DamageEvent(...)` — reducing | Before mitigation. Hooks may modify the amount. |
| `on_damage_dealt` | `DamageEvent(...)` | After damage applied, attacker's perspective. |
| `on_damage_taken` | `DamageEvent(...)` | After damage applied, target's perspective. |
| `on_heal` | `HealEvent(source, target, amount)` | After heal applied. |
| `on_status_applied` | `StatusEvent(target, status, duration)` | When a status begins. |
| `on_status_expired` | `StatusEvent(target, status)` | When a status ends. |
| `on_kill` | `KillEvent(killer, victim)` | From killer's perspective. |
| `on_death` | `DeathEvent(victim, killer)` | From victim's perspective. Fires before piece removal. |
| `on_mana_full` | `ManaEvent(actor, slot_idx)` | An active slot is ready to cast. |
| `on_phase_change` | `PhaseEvent(piece, new_phase)` | Boss phase transition (or other future phased actors). |
| `on_spawn` | `SpawnEvent(piece, hex)` | A piece appears mid-combat (summons). |

`hit_id` is a monotonic counter across all damage instances in a combat. `cast_id` is set on `DamageEvent` only when `tag == SourceTag.ABILITY`; threaded through every hit of one cast.

---

## 5. `CombatContext` — the mutator API

`combat/` owns `CombatContext` (defined in `combat/context.py`, re-exported by `combat/__init__.py`). Content interacts with the world only through these methods.

### 5.1 Mutators

```python
class CombatContext:
    # --- damage & healing ---
    def deal_damage(
        self,
        attacker: Piece,
        target: Piece,
        amount: float,
        tag: SourceTag,
        crit: bool | None = None,            # None → roll from attacker.crit_chance
    ) -> float:
        """Returns final amount dealt (post-mitigation, post-pre-hooks)."""

    def heal(self, source: Piece, target: Piece, amount: float) -> float: ...

    # --- status & modifiers ---
    # potency overrides per-DOT-tick damage (0 → StatusDef.dot_per_tick). One instance
    # per status_id per piece; reapply merges, strongest potency wins. See §15 #11 / SPEC V.25-V.26.
    def apply_status(self, target: Piece, status_id: str, duration_ticks: int, stacks: int = 1,
                     source_id: str = "", potency: float = 0.0) -> None: ...
    def remove_status(self, target: Piece, status_id: str) -> None: ...
    def apply_modifier(self, target: Piece, modifier: Modifier) -> None: ...

    # --- attacks & casts ---
    def trigger_basic_attack(self, attacker: Piece, target: Piece, mult: float = 1.0) -> None:
        """Resolves as a normal attack: fires on_attack_landed, generates mana, etc."""
    def cast_ability(self, actor: Piece, slot_idx: int = 0) -> None: ...

    # --- mana ---
    def gain_mana(self, actor: Piece, amount: float) -> None: ...
    def spend_mana(self, actor: Piece, slot_idx: int) -> None: ...

    # --- positioning ---
    def teleport(self, actor: Piece, dest: Hex) -> None: ...
    def spawn(self, piece: Piece, hex: Hex) -> None: ...

    # --- lifecycle ---
    def kill(self, target: Piece, killer: Piece | None) -> None: ...
    def end_combat(self, winner: Team) -> None: ...

    # --- bundle registration (used by phase hooks; loadout uses it pre-combat) ---
    def register_bundle(self, owner: Piece, bundle: EffectBundle) -> None: ...
```

### 5.2 Read-only queries

```python
    @property
    def current_tick(self) -> int: ...
    @property
    def current_cast_id(self) -> int | None: ...
    @property
    def weather(self) -> WeatherState: ...
    @property
    def rng(self) -> SeededRng:
        """Use this for ALL randomness in handlers. NEVER import random.random()."""
    @property
    def board(self) -> Board: ...

    def enemies_of(self, piece: Piece) -> Iterable[Piece]: ...
    def allies_of(self, piece: Piece) -> Iterable[Piece]: ...
    def is_enemy(self, a: Piece, b: Piece) -> bool: ...
    def is_alive(self, piece: Piece) -> bool: ...
```

### 5.3 Determinism contract

Two rules content **must** honour or combat is no longer reproducible:

1. **Randomness only via `ctx.rng`.** Never `random.random()`, `random.choice()`, `time.time()`, etc.
2. **Iteration over sets/dicts uses a sorted key** when order is observable. Piece lookups are ordered by piece id.

CI grep enforces rule (1) in any file under `game/`.

---

## 6. Ability system

### 6.1 Piece ability shape

```python
@dataclass
class ActiveSlot:
    ability_id: str
    cost: int                       # mana required
    current_mana: float = 0.0
    priority: int = 0               # tiebreaker if multiple slots ready same tick

@dataclass
class Piece:
    id: str
    base_stats: dict[str, float]
    affinity: WeatherState
    traits: list[str]
    actives: list[ActiveSlot]       # 0..2 slots; was a single string in the old schema
    passives: list[str]             # 0..2 passive ability ids
    crit_chance: float
    items: list[str] = field(default_factory=list)
    modifiers: list[Modifier] = field(default_factory=list)
    statuses: list[StatusInstance] = field(default_factory=list)
    # … position, team, hp, etc.
```

**Cardinality:**

| Piece type | Actives | Passives |
|---|---|---|
| Normal champion / enemy | 0 or 1 | 0 or 1 |
| Boss, phase 1 | 1 | 1 |
| Boss, phase 2 (after HP threshold) | 2 | 2 |

### 6.2 Authoring model — hybrid

Three flavours, all land in the same registry, all are interchangeable at the engine's call site.

**(a) Pure Python handler** — for anything with branching, conditionals, weather scaling, target filtering.

```python
@register_active("storm_surge")
def storm_surge(ctx: CombatContext, actor: Piece, targets: list[Piece]) -> None:
    base = 50 + compute_stat(actor, "ability_power", ctx) * 2.0
    damage = base * 1.5 if ctx.weather is WeatherState.STORM else base
    for t in targets:
        ctx.deal_damage(actor, t, damage, SourceTag.ABILITY)
    if actor.has_status("charged"):
        ctx.apply_status(targets[0], "stun", duration_ticks=20)
```

**(b) Declarative simple ability** — for "deal X damage to primary target" style.

```python
register_active_simple("smash", SimpleActive(
    target=TargetSelector.PRIMARY,
    damage=100,
    scaling="ad*1.5",
    tag=SourceTag.ABILITY,
))
```

`register_active_simple` synthesises an equivalent handler at import time and inserts it into `ABILITY_REGISTRY`. The engine sees no difference.

**(c) Factory-built ability** — for the 80-champion reality where many abilities share shape. Define a factory once, stamp out variants.

```python
def cone_aoe(damage: int, scaling: str, half_to_neighbors: bool = False):
    """Returns a handler. Pair with @register_active or call .register(id)."""
    def handler(ctx, actor, targets):
        primary = targets[0]
        amt = damage + eval_scaling(scaling, actor, ctx)
        ctx.deal_damage(actor, primary, amt, SourceTag.ABILITY)
        if half_to_neighbors:
            for n in ctx.board.enemies_in_neighbors(primary, of=actor):
                ctx.deal_damage(actor, n, amt * 0.5, SourceTag.ABILITY)
    return handler

# In game/abilities/storm.py:
ABILITY_REGISTRY["thunder_crash"]  = cone_aoe(damage=180, scaling="ap*1.5", half_to_neighbors=True)
ABILITY_REGISTRY["squall_burst"]   = cone_aoe(damage=140, scaling="ap*1.8", half_to_neighbors=True)
ABILITY_REGISTRY["lightning_lash"] = cone_aoe(damage=220, scaling="ap*1.2", half_to_neighbors=False)
```

Authoring guideline: **use the simplest flavour that fits.** Don't write a 30-line handler if a factory call would do.

### 6.3 Targeting helpers (`targeting.py`)

Content must not reach into board state directly. All targeting goes through this module:

```python
def primary_target(actor: Piece, ctx: CombatContext) -> Piece | None
def lowest_hp_enemy(actor: Piece, ctx: CombatContext) -> Piece | None
def highest_ap_enemy(actor: Piece, ctx: CombatContext) -> Piece | None
def random_enemy(actor: Piece, ctx: CombatContext) -> Piece | None
def neighbors_of(piece: Piece, ctx: CombatContext) -> list[Piece]
def enemies_in_radius(center: Hex, radius: int, of: Piece, ctx: CombatContext) -> list[Piece]
def allies_in_radius(center: Hex, radius: int, of: Piece, ctx: CombatContext) -> list[Piece]
def furthest_enemy(actor: Piece, ctx: CombatContext) -> Piece | None
def line_targets(actor: Piece, direction: Hex, length: int, ctx: CombatContext) -> list[Piece]
```

When a designer needs a new pattern, it's added here and reused — not inlined into one ability. At 80 champions this discipline is the difference between a workable codebase and a swamp.

### 6.4 Passive abilities

Same registry pattern, different return:

```python
@register_passive("static_buildup")
def static_buildup(owner: Piece) -> EffectBundle:
    """When this piece lands a basic attack in STORM weather, stack 'charged' on the target."""
    def hook(ctx: CombatContext, ev: AttackEvent) -> None:
        if ev.attacker is owner and ctx.weather is WeatherState.STORM:
            ctx.apply_status(ev.target, "charged", duration_ticks=200, stacks=1)
    return EffectBundle(
        hooks=[Hook("on_attack_landed", hook, scope=HookScope.PER_HIT)],
    )
```

Passives are factory functions: take the owner Piece, return an EffectBundle whose hooks close over `owner`. `loadout.compile_loadout` invokes them once per piece per combat.

### 6.5 Mana & cast resolution — separate pools (decision locked)

Boss phase-2 has two actives. They use **separate mana pools** — each slot has its own cost and its own meter. Outcome: when both slots fill independently, you get a flurry of casts rather than one alternating bar.

**Mana gain:** any source of mana gain (autoattack, taking damage, item proc) adds to **all** of the actor's slots in parallel. A slot caps at its own `cost`.

**Cast trigger:** every tick, after damage / status processing, the engine iterates an actor's slots in descending `priority` order. The first slot with `current_mana >= cost` that is not blocked (silenced, dead, mid-cast on another slot) casts and resets its own meter to 0. Other slots keep their accumulated mana. If multiple slots are ready and the actor isn't silenced after the first cast, the loop continues — both can fire the same tick. (This is the "flurry" you want.)

```python
def _process_casts(ctx: CombatContext, actor: Piece) -> None:
    if actor.has_status("silence") or not ctx.is_alive(actor):
        return
    for slot_idx in sorted(range(len(actor.actives)),
                           key=lambda i: -actor.actives[i].priority):
        slot = actor.actives[slot_idx]
        if slot.current_mana < slot.cost:
            continue
        slot.current_mana = 0.0
        ctx.cast_ability(actor, slot_idx=slot_idx)
        if actor.has_status("silence") or not ctx.is_alive(actor):
            return                      # cast (or its on_cast hooks) may have changed state
```

Per-piece tuning: a boss whose two phase-2 abilities should clearly alternate (one buff, one nuke) can set both `priority` and `cost` so the buff goes first. Content controls cadence.

### 6.6 Boss phase hook

Phase 2 is appended at runtime when the boss drops below 50% HP. The boss champion definition declares its phase-2 content; the phase hook itself is a passive registered at combat start.

```python
@register_passive("storm_titan_phase_hook")
def storm_titan_phase_hook(owner: Piece) -> EffectBundle:
    def hook(ctx: CombatContext, ev: DamageEvent) -> None:
        if ev.target is not owner: return
        if compute_hp_pct(owner, ctx) >= 0.50: return
        # idempotency handled by HookScope.ONCE_PER_COMBAT
        owner.actives.append(ActiveSlot(
            ability_id="meteor_finale",
            cost=ABILITY_META["meteor_finale"].cost,
            priority=10,
        ))
        owner.passives.append("eye_of_the_storm")
        ctx.register_bundle(owner, PASSIVE_REGISTRY["eye_of_the_storm"](owner))
        ctx.fire("on_phase_change", PhaseEvent(piece=owner, new_phase=2))
    return EffectBundle(
        hooks=[Hook("on_damage_taken", hook, scope=HookScope.ONCE_PER_COMBAT, priority=100)],
    )
```

`ctx.register_bundle` is the runtime entry point for adding hooks mid-combat; loadout uses the same function pre-combat. No special path.

---

## 7. Trait system

### 7.1 Shape

```python
class TraitScope(Enum):
    PER_TRAIT_PIECE = "per_trait_piece"     # bundle applies only to pieces with the trait
    TEAM_WIDE       = "team_wide"           # bundle applies to all team pieces

@dataclass
class TraitBreakpoint:
    count: int                                              # minimum unique champions with this trait
    scope: TraitScope
    bundle_factory: Callable[[Piece], EffectBundle]         # called per target piece

@register_trait("stormcaller")
def stormcaller() -> list[TraitBreakpoint]:
    return [
        TraitBreakpoint(2, TraitScope.PER_TRAIT_PIECE,
            lambda owner: EffectBundle(modifiers=[
                Modifier("ability_power", "add", 20, Lifetime.COMBAT,
                         source_id="trait:stormcaller@2"),
            ])),
        TraitBreakpoint(4, TraitScope.PER_TRAIT_PIECE,
            lambda owner: EffectBundle(
                modifiers=[Modifier("ability_power", "add", 50, Lifetime.COMBAT,
                                    source_id="trait:stormcaller@4")],
                hooks=[Hook("on_cast", _stormcaller_4_zap(owner))],
            )),
        TraitBreakpoint(6, TraitScope.TEAM_WIDE,
            lambda owner: EffectBundle(
                modifiers=[Modifier("ability_power", "add", 100, Lifetime.COMBAT,
                                    source_id="trait:stormcaller@6")],
            )),
    ]
```

Counting rule: **unique champion ids**, not duplicates. Two copies of the same champion count once toward a trait (TFT convention).

### 7.2 Resolution (in `loadout.compile_loadout`)

```python
def _resolve_traits(team: list[Piece]) -> dict[str, TraitBreakpoint]:
    counts: dict[str, set[str]] = defaultdict(set)
    for piece in team:
        for trait in piece.traits:
            counts[trait].add(piece.id)
    cleared = {}
    for trait, owners in counts.items():
        breakpoints = TRAIT_REGISTRY[trait]()
        active = max(
            (bp for bp in breakpoints if len(owners) >= bp.count),
            key=lambda bp: bp.count,
            default=None,
        )
        if active:
            cleared[trait] = active
    return cleared
```

Then for each `(trait, breakpoint)`: pick target pieces (per-trait-piece vs team-wide), call factory per target, `apply_bundle` each.

### 7.3 Emblems

An emblem is an item whose `EffectBundle` uses `granted_traits` to make its wearer count toward a trait they don't natively have. Emblems are produced by combining a gem (special item) with a base component (see §8.4).

```python
@register_item("stormcaller_emblem")
def stormcaller_emblem(owner: Piece) -> EffectBundle:
    return EffectBundle(
        granted_traits=["stormcaller"],
        modifiers=[Modifier("ability_power", "add", 15, Lifetime.PERMANENT,
                            source_id="item:stormcaller_emblem")],
    )
```

`granted_traits` is processed by `apply_bundle` **before** trait resolution; the order matters and is documented in §9.

---

## 8. Item system

### 8.1 Categories

| Category | Count (target) | EffectBundle? | Notes |
|---|---|---|---|
| Base components | 6 | Yes (pure modifiers) | The atoms. Held individually on a piece. |
| Combined items | 15 | Yes (modifiers + hooks) | Recipe of two base components, static map. |
| Special items | ~6 | **No** | Reforger, unequipper, champion-copy, gems. Operate on Run state, not combat. |
| Emblems | 6 | Yes (`granted_traits`) | Gem + base component → emblem for one trait. |

### 8.2 Base components — pure data

```python
# game/items/base.py
BASE_COMPONENTS: dict[str, EffectBundle] = {
    "bow":   EffectBundle(modifiers=[Modifier("attack_speed", "mul", 1.10, Lifetime.PERMANENT, "item:bow")]),
    "tear":  EffectBundle(modifiers=[Modifier("mana_max",     "add", -15,  Lifetime.PERMANENT, "item:tear")]),
    "rod":   EffectBundle(modifiers=[Modifier("ability_power","add", 10,   Lifetime.PERMANENT, "item:rod")]),
    "belt":  EffectBundle(modifiers=[Modifier("hp",           "add", 150,  Lifetime.PERMANENT, "item:belt")]),
    "sword": EffectBundle(modifiers=[Modifier("attack_damage","add", 10,   Lifetime.PERMANENT, "item:sword")]),
    "cloak": EffectBundle(modifiers=[Modifier("magic_resist", "add", 20,   Lifetime.PERMANENT, "item:cloak")]),
}
```

A base component held by a piece is registered into the item path the same way a combined item is — its bundle just happens to be a pure-modifier one.

### 8.3 Combined items — recipe map + factories

```python
# game/items/recipes.py
RECIPE_MAP: dict[frozenset[str], str] = {
    frozenset({"bow", "sword"}):  "rapidfire_cannon",
    frozenset({"bow", "rod"}):    "guinsoo",
    frozenset({"tear", "rod"}):   "archangels",
    frozenset({"belt", "cloak"}): "warmogs",
    frozenset({"sword", "belt"}): "titans",
    # … 15 total
}

# game/items/combined.py
@register_item("rapidfire_cannon")
def rapidfire_cannon(owner: Piece) -> EffectBundle:
    state = {"count": 0}
    def every_third(ctx, ev):
        if ev.attacker is not owner: return
        state["count"] += 1
        if state["count"] % 3 == 0:
            ctx.deal_damage(owner, ev.target, ev.amount, SourceTag.ITEM_PROC)
    return EffectBundle(
        modifiers=[
            Modifier("attack_speed", "mul", 1.55, Lifetime.PERMANENT, "item:rapidfire_cannon"),
            Modifier("attack_damage","add", 10,   Lifetime.PERMANENT, "item:rapidfire_cannon"),
        ],
        hooks=[Hook("on_attack_landed", every_third, scope=HookScope.PER_HIT)],
    )
```

Closure state (the `count` dict) lives for one combat — the closure is freshly created each combat by the loadout compiler.

### 8.4 Special items — meta actions, off the combat path

These never produce an `EffectBundle`. They live in a separate registry and are invoked from the Run / map layer, not from `combat/`.

```python
# game/items/special.py
@register_run_action("reforger")
def reforger(run: RunState, target_item_idx: int) -> None:
    """Randomly swap one base component of the chosen combined item, then recombine."""
    ...

@register_run_action("unequipper")
def unequipper(run: RunState, piece_id: str) -> None:
    """Return all items from the chosen piece to the bench, decomposed to base components."""
    ...

@register_run_action("champion_copy_gem")
def champion_copy_gem(run: RunState, target_piece_id: str) -> None:
    """Add a copy of the chosen piece to the bench."""
    ...

# Plain gems are handled inline by the recipe system:
GEM_IDS = {"stormcaller_gem", "embercaller_gem", ...}
def combine(a: str, b: str) -> str | None:
    if a in GEM_IDS and b in BASE_COMPONENTS:
        return f"{a.removesuffix('_gem')}_emblem"
    if b in GEM_IDS and a in BASE_COMPONENTS:
        return f"{b.removesuffix('_gem')}_emblem"
    return RECIPE_MAP.get(frozenset({a, b}))
```

Keeping these out of `combat/` is non-negotiable. Combat never sees a reforger; combat sees the *result* of running one.

---

## 9. Augment system

### 9.1 Four flavours, one signature

```python
class AugmentScope(Enum):
    PIECE = "piece"     # bundle applied to specific pieces (optionally filtered)
    TEAM  = "team"      # bundle applied team-wide
    RUN   = "run"       # operates on Run state, no combat bundle

@dataclass
class Augment:
    id: str
    scope: AugmentScope
    handler: Callable                # signature depends on scope, see below
    piece_filter: Callable[[Piece], bool] | None = None    # PIECE-scope only
    quest_tracker: Callable | None = None                  # quest augments

AUGMENT_REGISTRY: dict[str, Augment] = {}
```

Handler signatures:

| Scope | Signature | Return |
|---|---|---|
| `PIECE` | `(piece: Piece) -> EffectBundle` | bundle applied to that piece |
| `TEAM` | `(team: list[Piece]) -> EffectBundle` | bundle applied to every team piece |
| `RUN` | `(run: RunState) -> None` | mutates run state directly |

### 9.2 Examples — one per flavour

```python
# (a) Stat boost — TEAM scope
@register_augment("storm_blessing", scope=AugmentScope.TEAM)
def storm_blessing(team):
    return EffectBundle(modifiers=[
        Modifier("ability_power", "add", 20, Lifetime.COMBAT, "augment:storm_blessing"),
    ])

# (b) Filtered piece boost — PIECE scope with filter
@register_augment("stormcaller_crown", scope=AugmentScope.PIECE,
                  piece_filter=lambda p: "stormcaller" in p.traits)
def stormcaller_crown(piece):
    return EffectBundle(modifiers=[
        Modifier("ability_power", "add", 40, Lifetime.COMBAT, "augment:stormcaller_crown"),
    ])

# (c) Item grant — RUN scope (meta-action, no combat bundle)
@register_augment("free_belt", scope=AugmentScope.RUN)
def free_belt(run):
    run.bench_items.append("belt")

# (d) Quest augment — RUN scope + persistent tracker
@register_augment("dragon_slayer", scope=AugmentScope.RUN,
                  quest_tracker="dragon_slayer_progress")
def dragon_slayer(run):
    run.augment_state.setdefault("dragon_slayer", {"kills": 0, "completed": False})

@register_quest_tracker("dragon_slayer_progress")
def dragon_slayer_progress(run: RunState, event_name: str, event: Event) -> None:
    """Subscribed once per Run to global events from every combat."""
    state = run.augment_state["dragon_slayer"]
    if state["completed"]: return
    if event_name == "on_kill" and "dragon" in event.victim.traits:
        state["kills"] += 1
        if state["kills"] >= 10:
            run.bench_items.append("dragon_claw")
            state["completed"] = True
```

### 9.3 Quest tracker plumbing

Quest trackers are not combat hooks. They're **Run-level subscribers** — they survive across combats, accumulating progress.

`loadout.compile_loadout` notices a Run has quest augments and wires their trackers into the bus as `ONCE_PER_COMBAT` hooks on every relevant event. The tracker callback receives `RunState`, not just `CombatContext`, so it can mutate persistent state.

Implementation detail: the Run-level wiring is a thin layer in `loadout.py`:

```python
def _wire_quest_trackers(bus: EventBus, run: RunState) -> None:
    for aug_id in run.active_augments:
        aug = AUGMENT_REGISTRY[aug_id]
        if not aug.quest_tracker: continue
        tracker = QUEST_TRACKER_REGISTRY[aug.quest_tracker]
        for event_name in QUEST_TRACKER_EVENTS[aug.quest_tracker]:
            bus.subscribe(Hook(
                event=event_name,
                handler=lambda ctx, ev, t=tracker, en=event_name: t(run, en, ev),
                scope=HookScope.PER_HIT,
                priority=-100,                # quest progress fires last
            ))
```

---

## 10. Loadout compiler — the isolation boundary

`loadout.py` is the only module allowed to import both content registries and combat types. It produces a `CombatLoadout` that `combat.run()` consumes.

### 10.1 Application order (deterministic)

```
1. Snapshot input pieces (deep-copy so combat doesn't mutate Run state).
2. Apply items' granted_traits FIRST (emblems must be visible to trait counting).
3. Resolve trait breakpoints (count unique champion ids).
4. Apply trait bundles (per-trait-piece or team-wide).
5. Apply item bundles (modifiers + hooks).
6. Apply augment bundles (PIECE-filtered, then TEAM).
7. Apply champion passive bundles.
8. Apply boss phase-1 passives.
9. Wire quest trackers for active RUN-scope augments.
10. Fire on_combat_start.
```

The order is the rule-of-precedence for content interactions. If two systems both grant the same modifier, the later application overrides. If a designer needs a specific interaction, they pick where to slot the bundle by choosing the system that emits it.

### 10.2 `apply_bundle`

```python
def apply_bundle(target: Piece, bundle: EffectBundle, bus: EventBus, ctx: CombatContext | None = None) -> None:
    for trait_id in bundle.granted_traits:
        if trait_id not in target.traits:
            target.traits.append(trait_id)
    for mod in bundle.modifiers:
        target.modifiers.append(mod)
    for status_id, duration in bundle.statuses:
        if ctx:
            ctx.apply_status(target, status_id, duration)
        else:
            target.statuses.append(StatusInstance(status_id=status_id, remaining_ticks=duration))
    for ability_id in bundle.granted_abilities:
        target.actives.append(ActiveSlot(
            ability_id=ability_id,
            cost=ABILITY_META[ability_id].cost,
        ))
    for hook in bundle.hooks:
        bus.subscribe(hook)
```

Same function used by `loadout.compile_loadout` (pre-combat) and `ctx.register_bundle` (mid-combat, e.g. boss phase hook).

### 10.3 `CombatLoadout`

```python
@dataclass
class CombatLoadout:
    pieces: list[Piece]
    bus: EventBus
    seed: int                       # for ctx.rng
    weather: WeatherState           # snapshot at combat start
    board: Board
```

Combat receives this opaque value, runs the tick loop, returns `BattleResult`. Nothing in `combat/` cares which content system contributed which hook.

---

## 11. Module layout

```
game/
  __init__.py
  effects.py              # Modifier, Hook, EffectBundle, EventBus, SourceTag, HookScope, Lifetime
  loadout.py              # compile_loadout, apply_bundle
  registries.py           # ABILITY_REGISTRY, ITEM_REGISTRY, TRAIT_REGISTRY, AUGMENT_REGISTRY,
                          #   PASSIVE_REGISTRY, QUEST_TRACKER_REGISTRY + @register decorators
  targeting.py            # primary_target, lowest_hp_enemy, neighbors_of, in_radius, …
  geometry.py             # Hex math
  scaling.py              # eval_scaling("ap*1.5+200", actor, ctx)
  rng.py                  # SeededRng
  events.py               # event payload dataclasses
  status.py               # status definitions (stun, silence, disarm, root, charged, burn, …)
  piece.py                # Piece, ActiveSlot dataclasses

  combat/                 # the engine — subpackaged because it has 4–5 distinct concerns
    __init__.py           # re-exports: CombatContext, run
    context.py            # CombatContext class — mutator API + read-only queries
    loop.py               # tick loop, run(loadout) entry point
    casting.py            # active/passive cast resolution, multi-slot mana handling
    damage.py             # damage pipeline (pre-hooks → mitigation → apply → post-hooks → kill)
    ai.py                 # default target selection per piece type

  abilities/
    __init__.py           # imports each submodule to trigger @register
    factories.py          # cone_aoe, single_target_nuke, line_aoe, summon, …
    simple.py             # data-driven simple actives (register_active_simple calls)
    storm.py              # storm-affinity champion abilities
    ember.py
    tide.py
    earth.py
    sun.py
    void.py
    boss_phases.py        # phase-2 ability definitions + phase hook passives

  items/
    __init__.py
    base.py               # BASE_COMPONENTS dict
    recipes.py            # RECIPE_MAP, combine(a, b)
    combined.py           # the 15 combined items
    special.py            # reforger, unequipper, champion-copy
    emblems.py            # one factory per emblem, gem definitions

  traits/
    __init__.py
    storm.py
    ember.py
    tide.py
    earth.py
    sun.py
    void.py

  augments/
    __init__.py
    stat.py               # TEAM / PIECE stat boosts
    grant.py              # item-grant RUN augments
    quest.py              # quest augments + their trackers

  champions/
    __init__.py
    data.py               # CHAMPION_DATA: dict[str, ChampionSpec] — stat blocks + ability id refs

  enemies/
    data.py

  bosses/
    data.py
```

**Why this shape (and not uniform flat or uniform subpackaged):**

- `effects.py` is a *stable substrate*. Adding a 50th champion adds zero lines to it. Projected ~300 lines forever. One file fits one concept; top-to-bottom reading beats subpackage navigation.
- `combat/` is the engine, and the engine has genuinely distinct concerns: the CombatContext API surface, the tick loop, cast/mana resolution, the damage pipeline, and target-selection AI. They share a file today only out of habit, not because they belong together. Subpackaging matches the conceptual shape and absorbs future growth (reaction windows, smarter AI, visual-effect emission) without forcing a refactor.
- `loadout.py`, `registries.py`, `targeting.py` are each one cohesive thing — flat is honest.
- Content categories are subpackaged because the file count demands it at 80-champion scope.

**Conventions:**
- Every content subpackage's `__init__.py` does `from . import storm, ember, …` so importing the package triggers all `@register` decorators.
- `combat/__init__.py` re-exports `CombatContext` and `run` so external callers write `from game.combat import CombatContext, run` — they don't see the internal split. Internal combat modules import each other by relative path (`from .context import CombatContext`).
- Top-level `game/__init__.py` imports `abilities`, `items`, `traits`, `augments`, `champions`, `enemies`, `bosses` in that order at import time.
- A piece's `ability_id` is a *string*. Champion data lives in plain dicts (`champions/data.py`); ability code lives in `abilities/*.py`. The link is the registry. This is the standard registry-pattern decoupling.
- The shape is reversible. Splitting `effects.py` into `effects/*.py` later, or merging `combat/` back into `combat.py`, is a 10-minute refactor; `__init__.py` re-exports keep all import sites stable either direction. Don't be precious about it.

---

## 12. Worked examples

### 12.1 Adding a new champion (full content surface)

```python
# game/abilities/tide.py
from game.registries import register_active, register_passive
from game.effects import EffectBundle, Hook, HookScope, SourceTag, Modifier, Lifetime
from game.targeting import lowest_hp_enemy, neighbors_of

@register_active("riptide_lash")
def riptide_lash(ctx, actor, targets):
    target = lowest_hp_enemy(actor, ctx)
    if not target: return
    base = 160 + actor.modifiers_total("ability_power") * 1.6
    ctx.deal_damage(actor, target, base, SourceTag.ABILITY)
    if ctx.weather.is_wet():
        for n in neighbors_of(target, ctx):
            if ctx.is_enemy(n, actor):
                ctx.deal_damage(actor, n, base * 0.4, SourceTag.ABILITY)

@register_passive("brine_curse")
def brine_curse(owner):
    def hook(ctx, ev):
        if ev.attacker is owner and ctx.rng.random() < 0.25:
            ctx.apply_status(ev.target, "soaked", duration_ticks=150)
    return EffectBundle(hooks=[Hook("on_attack_landed", hook)])
```

```python
# game/champions/data.py
CHAMPION_DATA["tide_otter"] = ChampionSpec(
    id="tide_otter",
    affinity=WeatherState.RAIN,
    traits=["tidecaller", "swift"],
    base_stats={"hp": 800, "attack_damage": 55, "ability_power": 0, "attack_speed": 0.85,
                "armor": 25, "magic_resist": 25, "mana_max": 70, "crit_chance": 0.20},
    actives=[ActiveSlot(ability_id="riptide_lash", cost=70)],
    passives=["brine_curse"],
)
```

That's the whole surface. The champion now appears in the pool, can be combined with traits and items, can carry augments.

### 12.2 Adding a combined item

```python
# game/items/recipes.py
RECIPE_MAP[frozenset({"rod", "cloak"})] = "ionic_spark"

# game/items/combined.py
@register_item("ionic_spark")
def ionic_spark(owner):
    def on_enemy_cast(ctx, ev):
        if ctx.is_enemy(ev.caster, owner):
            ctx.deal_damage(owner, ev.caster, 80, SourceTag.ITEM_PROC)
    return EffectBundle(
        modifiers=[
            Modifier("ability_power",  "add", 15, Lifetime.PERMANENT, "item:ionic_spark"),
            Modifier("magic_resist",   "add", 20, Lifetime.PERMANENT, "item:ionic_spark"),
        ],
        hooks=[Hook("on_cast", on_enemy_cast)],
    )
```

### 12.3 Adding a quest augment

```python
# game/augments/quest.py
@register_augment("storm_chaser", scope=AugmentScope.RUN,
                  quest_tracker="storm_chaser_progress")
def storm_chaser(run):
    run.augment_state.setdefault("storm_chaser", {"storm_wins": 0, "completed": False})

@register_quest_tracker("storm_chaser_progress", events=["on_combat_end"])
def storm_chaser_progress(run, event_name, ev):
    state = run.augment_state["storm_chaser"]
    if state["completed"]: return
    if ev.winner is run.player_team and ev.weather is WeatherState.STORM:
        state["storm_wins"] += 1
        if state["storm_wins"] >= 5:
            run.bench_items.append("stormcaller_emblem")
            state["completed"] = True
```

### 12.4 "Execute below 20% HP, once per ability cast" — testing all three axes

```python
@register_passive("executioner")
def executioner(owner):
    def hook(ctx, ev):
        if ev.attacker is not owner: return
        if ev.target.hp_pct() < 0.20:
            # If the ability hit 5 enemies, this hook fires up to 5 times.
            # ONCE_PER_CAST scope ensures we execute at most one of them per cast.
            ctx.deal_damage(owner, ev.target, ev.target.hp, SourceTag.ITEM_PROC)
    return EffectBundle(hooks=[Hook(
        event="on_ability_damage",
        handler=hook,
        scope=HookScope.ONCE_PER_CAST,
        priority=20,
    )])
```

All three differentiation axes from the design conversation in one example:
- **Event name:** `on_ability_damage` (not `on_attack_landed` — doesn't proc on autos).
- **Source tag:** carried implicitly by the event (`tag=SourceTag.ABILITY` on the damage instance).
- **Scope:** `ONCE_PER_CAST` — the bus deduplicates by `(hook_id, cast_id)`.

---

## 13. Testing strategy

- **Unit-test handlers in isolation.** Build a minimal `FakeCombatContext` exposing only mutator methods the handler uses; assert calls and final piece state. Most handlers are <20 lines and trivially testable.
- **Property-test the bus.** Determinism: same seed + same loadout + same enemy script → byte-identical battle log.
- **Recipe completeness.** CI test asserts every `frozenset` in `RECIPE_MAP` maps to a registered item.
- **Registry completeness.** CI test imports every content package and asserts that every champion's `ability_id` and `passive_id` exist in registries.
- **Import-direction lint.** Grep every file under `combat/` for forbidden content imports (no `from game.abilities`, `from game.items`, `from game.traits`, `from game.augments`, `from game.champions`); grep every content module for `from game.combat`. Fail CI on violation.
- **`ctx.rng` lint.** Grep for `random.random`, `random.choice`, `random.randint`, `time.time` in `game/` outside `rng.py`. Fail CI on violation.
- **Replay test.** Save a serialised battle log; replay from seed; assert byte-equal log on every PR.

---

## 14. Open questions / deferred

- **Targeting overrides from items** (e.g. "your next ability targets the highest-HP enemy instead"): not in v1. When needed, add a `TargetOverride` field on `Piece` that targeting helpers consult before computing.
- **Multi-instance status stacking semantics:** v1 uses simple stack counts. Per-status custom rules (refresh-vs-extend duration, etc.) deferred until content demands it.
- **Item slot limits per piece:** TFT uses 3. We adopt the same; enforce in `loadout.compile_loadout` validation.
- **Augment selection UI / picking algorithm:** out of scope here; this doc describes only the runtime contract.
- **Save/replay format:** the deterministic battle log inside `ctx.deal_damage` etc. is the foundation; the on-disk format is a separate doc.
- **Performance budget:** with 80 champions × 40 enemies, worst-case combat is ~12 pieces per side × 10 hooks per piece × 100 ticks = ~120k hook invocations. Direct-call bus is fine; revisit only if profiling shows otherwise.
- **Hot-reload of content:** the registry pattern makes this feasible (clear registry, re-import packages) but is deferred until the content workflow demands it.

---

## 15. Decisions of record

| # | Decision | Rationale |
|---|---|---|
| 1 | Direct mutation via `CombatContext`; no `Effect` ADT | Combat is sequential; reducer/queue patterns add cost without benefit |
| 2 | `EffectBundle` is a registration descriptor, not a runtime type | Same shape used by items, augments, traits, passives → one apply path |
| 3 | Hybrid ability authoring (handler / simple-spec / factory) | At 80 champions, factories carry most of the load; handlers cover bespoke |
| 4 | Separate mana pools for boss multi-active | Independent fill = flurry of casts, the desired feel |
| 5 | Hybrid module layout: `effects.py` flat; `combat/` subpackaged (`context`, `loop`, `casting`, `damage`, `ai`); `loadout.py`/`registries.py`/`targeting.py` flat; content subpackaged | Split where conceptual structure demands it (engine has 4–5 distinct concerns); flat where it doesn't (substrate is one concept). Reversible later via `__init__.py` re-exports |
| 6 | Hard import-direction rule: the `combat/` package never imports content | Single source of isolation; CI-enforced |
| 7 | All randomness through `ctx.rng` | Determinism for replay; CI-enforced grep |
| 8 | Special items (reforger, gems, champion-copy) are run-actions, not combat content | Keeps the combat path clean of meta operations |
| 9 | Quest augments wire trackers at Run level, persist across combats | Quest state is a Run concept; combat fires the events, trackers accumulate |
| 10 | Bus enforces `HookScope` dedup; handlers are stateless re: dedup | Single place for bug-prone logic; designers don't repeat it 80× |
| 11 | DOT fires on a per-status cadence (`StatusDef.dot_interval_ticks`, default 100t=1s; `sudden_death`=1), not every engine tick; per-instance `ticks_to_next_dot` free-runs across reapply; status identity = `status_id` only (one instance, strongest-`potency`-wins merge) | A tick is ~600× finer than an action, so per-tick DOT was ~100× mis-scaled and spammed `on_damage_*` hooks; free-running clock stops reapply-spam from starving ticks; single-instance keeps CC/DoT identity predictable (TFT-style). See SPEC V.25-V.26 |
