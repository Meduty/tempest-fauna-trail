"""Item factories — @register_item for 8 raw components + 16 core-cut items (T.29a).

All factories follow the same shape as passive factories: ``factory(owner) ->
EffectBundle``.  A freshly created EffectBundle (with its hook closures) is
returned each call, so per-combat closure state resets automatically.

Component magnitudes (§3.1, first-pass, tunable):
  Fang  +12% STR  · Talon +12% AS  · Heartseed +12% INT  · Old Hide +12% HP
  Stoneplate +14% Armor  · Wardpelt +14% RES  · Keen Claw +15% crit_chance (add)
  Springtear: +200 mana start, −10% cast cost (via on_combat_start hook)

Combined items ≈ both component stats + the showcase mechanic.
Stat magnitudes are first-pass; retune via sim sweep (plan §5).
"""

from __future__ import annotations

from typing import Any

from src.game.combat.context import hex_distance
from src.game.effects import (
    EffectBundle,
    Hook,
    HookScope,
    Lifetime,
    Modifier,
    SourceTag,
)
from src.game.registries import register_item


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _str_mod(value: float, source: str) -> Modifier:
    return Modifier("strength", "mul", value, Lifetime.COMBAT, source)


def _as_mod(value: float, source: str) -> list[Modifier]:
    """Attack-speed modifier (T.29-pre: attack_speed is float; sub-integer order derives from it)."""
    return [
        Modifier("attack_speed", "mul", value, Lifetime.COMBAT, source),
    ]


def _int_mod(value: float, source: str) -> Modifier:
    return Modifier("intelligence", "mul", value, Lifetime.COMBAT, source)


def _hp_mod(value: float, source: str) -> Modifier:
    return Modifier("hp", "mul", value, Lifetime.COMBAT, source)


def _armor_mod(value: float, source: str) -> Modifier:
    return Modifier("armor", "mul", value, Lifetime.COMBAT, source)


def _res_mod(value: float, source: str) -> Modifier:
    return Modifier("resistance", "mul", value, Lifetime.COMBAT, source)


def _crit_add(value: float, source: str) -> Modifier:
    """Crit chance modifier — additive (crit_chance is a 0–1 float)."""
    return Modifier("crit_chance", "add", value, Lifetime.COMBAT, source)


def _mr_mod(value: float, source: str) -> Modifier:
    """Mana-regen modifier — the cast-rate knob (V.48). Multiplicative."""
    return Modifier("mana_regen", "mul", value, Lifetime.COMBAT, source)


def _grant_start_mana(owner: Any, amount: float) -> None:
    """Grant a FLAT amount of starting mana to all active slots (V.48, T.29c).

    Cost is ≈300_000, so a meaningful head-start is sized in that scale (≈1/3 of
    default cost = 100_000), not a flat sip. The grant is a flat value (not a
    pct of cost). Bumps `start_mana` (the record) and seeds `current_mana`,
    clamped to `max_mana`. Mana items NEVER reduce `mana_cost` — they grant
    `mana_regen` (Modifier) or `start_mana` (here). Runs from an on_combat_start
    hook (after all bundles applied, before the first tick).
    """
    for slot in owner.actives:
        slot.start_mana += int(amount)
        slot.current_mana = min(float(slot.max_mana), slot.current_mana + amount)


# ---------------------------------------------------------------------------
# 8 Raw-component factories
# ---------------------------------------------------------------------------


@register_item("fang")
def fang(owner: Any) -> EffectBundle:
    """Fang — +12% Strength."""
    return EffectBundle(modifiers=[_str_mod(1.12, "item:fang")])


@register_item("talon")
def talon(owner: Any) -> EffectBundle:
    """Talon — +12% Attack Speed."""
    return EffectBundle(modifiers=_as_mod(1.12, "item:talon"))


@register_item("heartseed")
def heartseed(owner: Any) -> EffectBundle:
    """Heartseed — +12% Intelligence."""
    return EffectBundle(modifiers=[_int_mod(1.12, "item:heartseed")])


@register_item("old_hide")
def old_hide(owner: Any) -> EffectBundle:
    """Old Hide — +12% Health."""
    return EffectBundle(modifiers=[_hp_mod(1.12, "item:old_hide")])


@register_item("stoneplate")
def stoneplate(owner: Any) -> EffectBundle:
    """Stoneplate — +14% Armor."""
    return EffectBundle(modifiers=[_armor_mod(1.14, "item:stoneplate")])


@register_item("wardpelt")
def wardpelt(owner: Any) -> EffectBundle:
    """Wardpelt — +14% Resistance."""
    return EffectBundle(modifiers=[_res_mod(1.14, "item:wardpelt")])


@register_item("keen_claw")
def keen_claw(owner: Any) -> EffectBundle:
    """Keen Claw — +15% Crit Chance (additive)."""
    return EffectBundle(modifiers=[_crit_add(0.15, "item:keen_claw")])


@register_item("springtear")
def springtear(owner: Any) -> EffectBundle:
    """Springtear — +15% mana regen and +200 starting mana (V.48, T.29c).

    The mana component: faster casting via the `mana_regen` cast-rate knob
    (Modifier) plus a head-start (`start_mana`). Never touches `mana_cost`.
    """
    def on_start(ctx: Any, ev: Any) -> None:
        _grant_start_mana(owner, 100_000)  # flat ≈1/3 of default cost

    return EffectBundle(
        modifiers=[_mr_mod(1.15, "item:springtear")],
        hooks=[Hook("on_combat_start", on_start, scope=HookScope.PER_HIT)],
    )


# ---------------------------------------------------------------------------
# 16 Core-cut combined items
# ---------------------------------------------------------------------------


# --- Apex Fang (Fang + Fang) ---
@register_item("apex_fang")
def apex_fang(owner: Any) -> EffectBundle:
    """Apex Fang — +24% STR; gains a STR burst on every kill."""
    def on_kill(ctx: Any, ev: Any) -> None:
        if ev.killer is not owner:
            return
        # Grant a flat STR add equal to 5% of current max STR (compounding).
        bonus = owner.stat("strength") * 0.05
        ctx.apply_modifier(owner, Modifier("strength", "add", bonus, Lifetime.COMBAT, "item:apex_fang"))

    return EffectBundle(
        modifiers=[_str_mod(1.24, "item:apex_fang")],
        hooks=[Hook("on_kill", on_kill, scope=HookScope.PER_HIT)],
    )


# --- Tempest Talons (Talon + Talon) ---
@register_item("tempest_talons")
def tempest_talons(owner: Any) -> EffectBundle:
    """Tempest Talons — +24% AS; each auto landed adds +0.5% AS (compounding ramp)."""
    def on_attack(ctx: Any, ev: Any) -> None:
        if ev.attacker is not owner:
            return
        ramp = owner.stat("attack_speed") * 0.005
        ctx.apply_modifier(owner, Modifier("attack_speed", "add", ramp, Lifetime.COMBAT, "item:tempest_talons"))

    return EffectBundle(
        modifiers=_as_mod(1.24, "item:tempest_talons"),
        hooks=[Hook("on_attack_landed", on_attack, scope=HookScope.PER_HIT)],
    )


# --- Worldroot Bloom (Heartseed + Heartseed) ---
@register_item("worldroot_bloom")
def worldroot_bloom(owner: Any) -> EffectBundle:
    """Worldroot Bloom — +30% INT (boosted same-component payoff)."""
    return EffectBundle(modifiers=[_int_mod(1.30, "item:worldroot_bloom")])


# --- Deepwell (Springtear + Springtear) ---
@register_item("deepwell")
def deepwell(owner: Any) -> EffectBundle:
    """Deepwell — +30% mana regen and +400 starting mana; after the first cast,
    refunds 50% of `mana_cost` on every subsequent cast (V.48, T.29c).

    Never reduces `mana_cost`; the refund grants mana (clamped to `max_mana`)."""
    state: dict[str, bool] = {"first_cast_done": False}

    def on_start(ctx: Any, ev: Any) -> None:
        _grant_start_mana(owner, 200_000)  # flat ≈2/3 of default cost (two springtears)

    def on_cast(ctx: Any, ev: Any) -> None:
        if ev.caster is not owner:
            return
        if not state["first_cast_done"]:
            state["first_cast_done"] = True
            return
        # Refund 50% of the slot's mana_cost into current_mana (clamp max_mana).
        for slot in owner.actives:
            if slot.ability_id == ev.ability_id:
                refund = slot.mana_cost * 0.50
                slot.current_mana = min(float(slot.max_mana), slot.current_mana + refund)

    return EffectBundle(
        modifiers=[_mr_mod(1.30, "item:deepwell")],
        hooks=[
            Hook("on_combat_start", on_start, scope=HookScope.PER_HIT),
            Hook("on_cast", on_cast, scope=HookScope.ONCE_PER_CAST),
        ],
    )


# --- Mammoth Hide (Old Hide + Old Hide) ---
@register_item("mammoth_hide")
def mammoth_hide(owner: Any) -> EffectBundle:
    """Mammoth Hide — +24% HP; regenerates 2% max HP every 1.5 s while not
    recently damaged (no damage taken in the last 2 s)."""
    last_damaged: list[int] = [-9999]   # mutable closure: last tick owner took damage

    def on_damaged(ctx: Any, ev: Any) -> None:
        if ev.target is owner:
            last_damaged[0] = ctx.current_tick

    def on_tick(ctx: Any, ev: Any) -> None:
        if not owner.alive:
            return
        tick = ev.tick
        # Regen pulse every 150 ticks (1.5 s); no damage in last 200 ticks (2 s).
        if tick % 150 != 0:
            return
        if tick - last_damaged[0] >= 200:
            ctx.heal(owner, owner, owner.max_hp * 0.02)

    return EffectBundle(
        modifiers=[_hp_mod(1.24, "item:mammoth_hide")],
        hooks=[
            Hook("on_damage_taken", on_damaged, scope=HookScope.PER_HIT),
            Hook("on_tick", on_tick, scope=HookScope.PER_HIT),
        ],
    )


# --- Bramble Carapace (Stoneplate + Stoneplate) ---
@register_item("bramble_carapace")
def bramble_carapace(owner: Any) -> EffectBundle:
    """Bramble Carapace — +28% Armor; when struck by a melee attacker, retaliates
    with magic damage proportional to the holder's Intelligence."""
    def on_damaged(ctx: Any, ev: Any) -> None:
        if ev.target is not owner:
            return
        attacker = ev.attacker
        if attacker is None or not attacker.alive:
            return
        # Melee: attack_range == 1
        if attacker.stat("attack_range") > 1:
            return
        dmg = owner.stat("intelligence") * 0.35
        ctx.deal_damage(owner, attacker, dmg, SourceTag.ITEM_PROC)

    return EffectBundle(
        modifiers=[_armor_mod(1.28, "item:bramble_carapace")],
        hooks=[Hook("on_damage_taken", on_damaged, scope=HookScope.PER_HIT)],
    )


# --- Mistward Shroud (Wardpelt + Wardpelt) ---
@register_item("mistward_shroud")
def mistward_shroud(owner: Any) -> EffectBundle:
    """Mistward Shroud — +28% Resistance; regenerates 1.5% max HP every second."""
    def on_tick(ctx: Any, ev: Any) -> None:
        if not owner.alive:
            return
        if ev.tick % 100 == 0:
            ctx.heal(owner, owner, owner.max_hp * 0.015)

    return EffectBundle(
        modifiers=[_res_mod(1.28, "item:mistward_shroud")],
        hooks=[Hook("on_tick", on_tick, scope=HookScope.PER_HIT)],
    )


# --- Perfect Predator (Keen Claw + Keen Claw) ---
@register_item("perfect_predator")
def perfect_predator(owner: Any) -> EffectBundle:
    """Perfect Predator — +30% Crit Chance; critical hits deal 25% bonus damage."""
    def on_damage(ctx: Any, ev: Any) -> None:
        if ev.attacker is not owner:
            return
        if not ev.is_crit:
            return
        if ev.tag == SourceTag.ITEM_PROC:  # guard: do not re-trigger on own bonus
            return
        if not ev.target.alive:
            return
        ctx.deal_damage(owner, ev.target, ev.amount * 0.25, SourceTag.ITEM_PROC, crit=False)

    return EffectBundle(
        modifiers=[_crit_add(0.30, "item:perfect_predator")],
        hooks=[Hook("on_damage_dealt", on_damage, scope=HookScope.PER_HIT)],
    )


# --- Bloodthorn Briar (Fang + Heartseed) ---
@register_item("bloodthorn_briar")
def bloodthorn_briar(owner: Any) -> EffectBundle:
    """Bloodthorn Briar — +12% STR, +12% INT; heals the holder for 18% of all
    damage it deals (basic attacks and abilities)."""
    def on_damage(ctx: Any, ev: Any) -> None:
        if ev.attacker is not owner:
            return
        if ev.tag == SourceTag.ITEM_PROC:  # guard: no recursive lifesteal
            return
        heal_amount = ev.amount * 0.18
        if heal_amount > 0.0:
            ctx.heal(owner, owner, heal_amount)

    return EffectBundle(
        modifiers=[
            _str_mod(1.12, "item:bloodthorn_briar"),
            _int_mod(1.12, "item:bloodthorn_briar"),
        ],
        hooks=[Hook("on_damage_dealt", on_damage, scope=HookScope.PER_HIT)],
    )


# --- Wildfury Lash (Talon + Heartseed) ---
@register_item("wildfury_lash")
def wildfury_lash(owner: Any) -> EffectBundle:
    """Wildfury Lash — +12% AS, +12% INT; each auto adds +1% AS; every 5th auto
    also immediately triggers a cast (if the holder has an active ability ready or
    partially filled — fires even at 0 mana by granting a free full-mana fill
    then casting).  Deterministic cadence, no RNG (V.2/V.14)."""
    counter: list[int] = [0]
    THRESHOLD = 5

    def on_attack(ctx: Any, ev: Any) -> None:
        if ev.attacker is not owner:
            return
        # Stack AS ramp
        ramp = owner.stat("attack_speed") * 0.01
        ctx.apply_modifier(owner, Modifier("attack_speed", "add", ramp, Lifetime.COMBAT, "item:wildfury_lash"))
        # Threshold cast
        counter[0] += 1
        if counter[0] >= THRESHOLD:
            counter[0] = 0
            if owner.actives:
                # Free cast: top each slot to its mana_cost, then cast slot 0.
                for slot in owner.actives:
                    slot.current_mana = float(slot.mana_cost)
                ctx.cast_ability(owner, 0)

    return EffectBundle(
        modifiers=[
            *_as_mod(1.12, "item:wildfury_lash"),
            _int_mod(1.12, "item:wildfury_lash"),
        ],
        hooks=[Hook("on_attack_landed", on_attack, scope=HookScope.PER_HIT)],
    )


# --- Everbloom Staff (Heartseed + Springtear) ---
@register_item("everbloom_staff")
def everbloom_staff(owner: Any) -> EffectBundle:
    """Everbloom Staff — +12% INT, +15% mana regen, +200 starting mana; INT grows
    steadily (+1% per 2 s) while the holder stays alive (V.48, T.29c)."""
    def on_start(ctx: Any, ev: Any) -> None:
        _grant_start_mana(owner, 100_000)  # flat ≈1/3 of default cost

    def on_tick(ctx: Any, ev: Any) -> None:
        if not owner.alive:
            return
        # +1% of current INT every 200 ticks (2 s).
        if ev.tick % 200 != 0 or ev.tick == 0:
            return
        bonus = owner.stat("intelligence") * 0.01
        ctx.apply_modifier(owner, Modifier("intelligence", "add", bonus, Lifetime.COMBAT, "item:everbloom_staff"))

    return EffectBundle(
        modifiers=[
            _int_mod(1.12, "item:everbloom_staff"),
            _mr_mod(1.15, "item:everbloom_staff"),
        ],
        hooks=[
            Hook("on_combat_start", on_start, scope=HookScope.PER_HIT),
            Hook("on_tick", on_tick, scope=HookScope.PER_HIT),
        ],
    )


# --- Witherbloom Censer (Heartseed + Old Hide) ---
@register_item("witherbloom_censer")
def witherbloom_censer(owner: Any) -> EffectBundle:
    """Witherbloom Censer — +12% INT, +12% HP; basic attacks apply burn to the
    target (150-tick / 1.5 s duration)."""
    def on_attack(ctx: Any, ev: Any) -> None:
        if ev.attacker is not owner:
            return
        if ev.target.alive:
            ctx.apply_status(ev.target, "burn", 150)

    return EffectBundle(
        modifiers=[
            _int_mod(1.12, "item:witherbloom_censer"),
            _hp_mod(1.12, "item:witherbloom_censer"),
        ],
        hooks=[Hook("on_attack_landed", on_attack, scope=HookScope.PER_HIT)],
    )


# --- Stormglass Totem (Heartseed + Wardpelt) ---
@register_item("stormglass_totem")
def stormglass_totem(owner: Any) -> EffectBundle:
    """Stormglass Totem — +12% INT, +14% RES; when a nearby enemy casts, the
    holder zaps them for INT-scaled magic damage (radius 5)."""
    TOTEM_RANGE = 5

    def on_cast(ctx: Any, ev: Any) -> None:
        caster = ev.caster
        if caster is owner:
            return
        if not owner.alive or not caster.alive:
            return
        # Only trigger on enemy casts
        if caster.is_enemy == owner.is_enemy:
            return
        dist = hex_distance(owner.position_q, owner.position_r, caster.position_q, caster.position_r)
        if dist > TOTEM_RANGE:
            return
        dmg = owner.stat("intelligence") * 0.50
        ctx.deal_damage(owner, caster, dmg, SourceTag.ITEM_PROC)

    return EffectBundle(
        modifiers=[
            _int_mod(1.12, "item:stormglass_totem"),
            _res_mod(1.14, "item:stormglass_totem"),
        ],
        hooks=[Hook("on_cast", on_cast, scope=HookScope.ONCE_PER_CAST)],
    )


# --- Spellfang Crown (Heartseed + Keen Claw) ---
@register_item("spellfang_crown")
def spellfang_crown(owner: Any) -> EffectBundle:
    """Spellfang Crown — +12% INT, +15% Crit Chance; the holder's abilities can
    critically strike (sets ``ability_can_crit``, same idiom as Mystic @4)."""
    def on_start(ctx: Any, ev: Any) -> None:
        owner.ability_can_crit = True

    return EffectBundle(
        modifiers=[
            _int_mod(1.12, "item:spellfang_crown"),
            _crit_add(0.15, "item:spellfang_crown"),
        ],
        hooks=[Hook("on_combat_start", on_start, scope=HookScope.PER_HIT)],
    )


# --- Living Bulwark (Old Hide + Stoneplate) ---
@register_item("living_bulwark")
def living_bulwark(owner: Any) -> EffectBundle:
    """Living Bulwark — +12% HP, +14% Armor (pure defensive stat stick)."""
    return EffectBundle(modifiers=[
        _hp_mod(1.12, "item:living_bulwark"),
        _armor_mod(1.14, "item:living_bulwark"),
    ])


# --- Splitwind Talons (Talon + Wardpelt) ---
@register_item("splitwind_talons")
def splitwind_talons(owner: Any) -> EffectBundle:
    """Splitwind Talons — +12% AS, +14% RES; autos also strike the nearest second
    enemy within range 2 for 50% of the hit's damage (ITEM_PROC tag)."""
    SPLASH_RANGE = 2

    def on_attack(ctx: Any, ev: Any) -> None:
        if ev.attacker is not owner:
            return
        primary = ev.target
        # Find the nearest second enemy (excluding the primary target)
        second: Any = None
        best_dist = 999
        for e in ctx.enemies_of(owner):
            if e is primary:
                continue
            d = hex_distance(primary.position_q, primary.position_r, e.position_q, e.position_r)
            if d <= SPLASH_RANGE and d < best_dist:
                best_dist = d
                second = e
        if second is not None:
            ctx.deal_damage(owner, second, ev.amount * 0.50, SourceTag.ITEM_PROC, crit=False)

    return EffectBundle(
        modifiers=[
            *_as_mod(1.12, "item:splitwind_talons"),
            _res_mod(1.14, "item:splitwind_talons"),
        ],
        hooks=[Hook("on_attack_landed", on_attack, scope=HookScope.PER_HIT)],
    )
