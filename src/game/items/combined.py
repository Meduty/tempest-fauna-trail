"""Item factories — @register_item for 8 raw components + 16 core-cut items (T.29a).

All factories follow the same shape as passive factories: ``factory(owner) ->
EffectBundle``.  A freshly created EffectBundle (with its hook closures) is
returned each call, so per-combat closure state resets automatically.

Component magnitudes (§3.1, first-pass, tunable):
  Fang  +12% STR  · Talon +12% AS  · Heartseed +12% INT  · Old Hide +12% HP
  Stoneplate +14% Armor  · Wardpelt +14% RES  · Keen Claw +15% crit_chance (add)
  Springtear: +15% mana_regen + flat 100_000 start mana (V.48; never cuts cost)

Durations use `secs(x)` (seconds → ticks, fractions OK); `SECS` for tick
intervals. Readable + real-tick honest (no hidden runtime scaling).

Combined items ≈ both component stats + the showcase mechanic.
Stat magnitudes are first-pass; retune via sim sweep (plan §5).
"""

from __future__ import annotations

from src.game.status import SECS, secs

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
    """Springtear — +15% mana regen and +100_000 flat starting mana (V.48, T.29c).

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
    """Deepwell — +30% mana regen, +200_000 flat starting mana, and a combat-start
    barrier (15% of holder max HP) on the lowest-HP ally (support-caster anchor);
    after the first cast, refunds 50% of `mana_cost` on every subsequent cast (V.48).

    Never reduces `mana_cost`; the refund grants mana (clamped to `max_mana`)."""
    state: dict[str, bool] = {"first_cast_done": False}

    def on_start(ctx: Any, ev: Any) -> None:
        _grant_start_mana(owner, 200_000)  # flat ≈2/3 of default cost (two springtears)
        # Support: shield the lowest-HP ally (the mana battery peels for the team).
        if ctx is None:
            return
        from src.game.targeting import lowest_hp_ally
        ally = lowest_hp_ally(owner, ctx)
        if ally is not None:
            ctx.grant_barrier(ally, owner.max_hp * 0.15)

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
    """Mammoth Hide — +24% HP; every 2 s heals the holder AND adjacent allies for
    2% of their max HP (a frontline regen aura ≈ 1%/s, ungated). The team-wide
    sibling of Mistward Shroud's self-only 1%/s sustain."""
    def on_tick(ctx: Any, ev: Any) -> None:
        if not owner.alive:
            return
        if ev.tick == 0 or ev.tick % (2*SECS) != 0:   # every 200 ticks = 2 s
            return
        from src.game.targeting import allies_in_radius
        # radius 1 = adjacent; allies_of includes self, so owner is covered.
        for ally in allies_in_radius(owner.position_q, owner.position_r, 1, owner, ctx):
            ctx.heal(owner, ally, ally.max_hp * 0.02)

    return EffectBundle(
        modifiers=[_hp_mod(1.24, "item:mammoth_hide")],
        hooks=[Hook("on_tick", on_tick, scope=HookScope.PER_HIT)],
    )


# --- Bramble Carapace (Stoneplate + Stoneplate) ---
@register_item("bramble_carapace")
def bramble_carapace(owner: Any) -> EffectBundle:
    """Bramble Carapace — +28% Armor; retaliates a FLAT magic hit to any melee
    attacker (thorns, TFT-style) AND inflicts grievous wounds (halved healing) on
    that attacker. Flat thorns by design: tank item, INT is the dump stat (the old
    INT×0.35 dealt ~2 dmg). Restores the catalog's 'cuts attacker healing'."""
    THORNS = 80.0

    def on_damaged(ctx: Any, ev: Any) -> None:
        if ev.target is not owner:
            return
        attacker = ev.attacker
        if attacker is None or not attacker.alive:
            return
        if attacker.stat("attack_range") > 1:   # melee only (range 1)
            return
        ctx.deal_damage(owner, attacker, THORNS, SourceTag.ITEM_PROC)
        ctx.apply_status(attacker, "grievous", secs(2))   # antiheal 2 s

    return EffectBundle(
        modifiers=[_armor_mod(1.28, "item:bramble_carapace")],
        hooks=[Hook("on_damage_taken", on_damaged, scope=HookScope.PER_HIT)],
    )


# --- Mistward Shroud (Wardpelt + Wardpelt) ---
@register_item("mistward_shroud")
def mistward_shroud(owner: Any) -> EffectBundle:
    """Mistward Shroud — +28% Resistance; regenerates 1% max HP every second
    (self only). Mammoth Hide is the team-wide regen sibling."""
    def on_tick(ctx: Any, ev: Any) -> None:
        if not owner.alive:
            return
        if ev.tick % SECS == 0:   # every 1 s
            ctx.heal(owner, owner, owner.max_hp * 0.01)   # 1%/s self (was 1.5%/s ≈ unkillable)

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
        if ev.tick % (2*SECS) != 0 or ev.tick == 0:
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
    """Witherbloom Censer — +12% INT, +12% HP; basic attacks apply burn (3 s),
    sunder the target's Resistance by 20%, AND inflict grievous wounds (halved
    healing) — the 'withering rot'. Res-shred is the scaling lever (amplifies the
    holder's INT autos/casts) since flat burn doesn't scale; grievous restores the
    catalog's 'cuts target healing'. All refresh each hit, single instances."""
    SHRED_TICKS = secs(3)   # 3 s — matches the burn duration
    RES_SHRED = "item:witherbloom_censer"

    def on_attack(ctx: Any, ev: Any) -> None:
        if ev.attacker is not owner or not ev.target.alive:
            return
        target = ev.target
        ctx.apply_status(target, "burn", secs(3))   # 3 s (was 1.5 s — too short vs cadence)
        ctx.apply_status(target, "grievous", secs(3))   # antiheal while burning
        # Resistance sunder: single refreshing instance (drop the prior one so
        # repeated hits refresh duration, not stack ×0.8 repeatedly).
        target.modifiers = [
            m for m in target.modifiers
            if not (m.source_id == RES_SHRED and m.stat == "resistance")
        ]
        target.modifiers.append(Modifier(
            "resistance", "mul", 0.80, Lifetime.TIMED, RES_SHRED,
            expires_at_tick=ctx.current_tick + SHRED_TICKS,
        ))

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
    """Living Bulwark — +12% HP, +14% Armor; at combat start grants adjacent allies
    a +18% Armor aura (support anchor). Was a pure stat stick — the aura gives the
    frontline brick a team identity."""
    def on_start(ctx: Any, ev: Any) -> None:
        if ctx is None:
            return
        from src.game.targeting import allies_in_radius
        for ally in allies_in_radius(owner.position_q, owner.position_r, 1, owner, ctx):
            if ally is owner:
                continue
            ctx.apply_modifier(ally, Modifier(
                "armor", "mul", 1.18, Lifetime.COMBAT, "item:living_bulwark",
            ))

    return EffectBundle(
        modifiers=[
            _hp_mod(1.12, "item:living_bulwark"),
            _armor_mod(1.14, "item:living_bulwark"),
        ],
        hooks=[Hook("on_combat_start", on_start, scope=HookScope.PER_HIT)],
    )


# --- Splitwind Talons (Talon + Wardpelt) ---
@register_item("splitwind_talons")
def splitwind_talons(owner: Any) -> EffectBundle:
    """Splitwind Talons — +12% AS, +14% RES; autos also strike the nearest second
    enemy within range 2 for 50% of the hit's damage AND apply Slow (soft CC) to
    both. The auto-attacker's control/kite item."""
    SPLASH_RANGE = 2

    def on_attack(ctx: Any, ev: Any) -> None:
        if ev.attacker is not owner:
            return
        primary = ev.target
        if primary.alive:
            ctx.apply_status(primary, "slow", secs(2))   # soft CC, 2 s
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
            ctx.apply_status(second, "slow", secs(2))

    return EffectBundle(
        modifiers=[
            *_as_mod(1.12, "item:splitwind_talons"),
            _res_mod(1.14, "item:splitwind_talons"),
        ],
        hooks=[Hook("on_attack_landed", on_attack, scope=HookScope.PER_HIT)],
    )


# ===========================================================================
# T.29b — remaining 20 combined items
# ===========================================================================


# --- Huntress Talon (Fang + Talon) ---
@register_item("huntress_talon")
def huntress_talon(owner: Any) -> EffectBundle:
    """Huntress Talon — +12% STR, +12% AS; autos apply a stacking bleed (poison)."""
    def on_attack(ctx: Any, ev: Any) -> None:
        if ev.attacker is not owner or not ev.target.alive:
            return
        ctx.apply_status(ev.target, "poison", secs(3), stacks=1, source_id=owner.id)

    return EffectBundle(
        modifiers=[_str_mod(1.12, "item:huntress_talon"), *_as_mod(1.12, "item:huntress_talon")],
        hooks=[Hook("on_attack_landed", on_attack, scope=HookScope.PER_HIT)],
    )


# --- Relentless Spear (Fang + Springtear) ---
@register_item("relentless_spear")
def relentless_spear(owner: Any) -> EffectBundle:
    """Relentless Spear — +12% STR, +15% mana regen; each auto grants bonus mana
    (≈10% of default cost) so an auto-attacker casts often."""
    def on_attack(ctx: Any, ev: Any) -> None:
        if ev.attacker is not owner:
            return
        ctx.gain_mana(owner, 30_000)

    return EffectBundle(
        modifiers=[_str_mod(1.12, "item:relentless_spear"), _mr_mod(1.15, "item:relentless_spear")],
        hooks=[Hook("on_attack_landed", on_attack, scope=HookScope.PER_HIT)],
    )


# --- Titanbone Charm (Fang + Old Hide) ---
@register_item("titanbone_charm")
def titanbone_charm(owner: Any) -> EffectBundle:
    """Titanbone Charm — +12% STR, +12% HP; stacks STR (+0.4% current) each time
    the holder attacks or is attacked; at 12 stacks, once, gains a barrier (15%
    max HP) — the defensive payoff at full stacks."""
    state = {"stacks": 0, "paid": False}

    def stack(ctx: Any) -> None:
        state["stacks"] += 1
        ctx.apply_modifier(owner, Modifier(
            "strength", "add", owner.stat("strength") * 0.004, Lifetime.COMBAT, "item:titanbone_charm"))
        if state["stacks"] >= 12 and not state["paid"]:
            state["paid"] = True
            ctx.grant_barrier(owner, owner.max_hp * 0.15)

    def on_attack(ctx: Any, ev: Any) -> None:
        if ev.attacker is owner:
            stack(ctx)

    def on_damaged(ctx: Any, ev: Any) -> None:
        if ev.target is owner:
            stack(ctx)

    return EffectBundle(
        modifiers=[_str_mod(1.12, "item:titanbone_charm"), _hp_mod(1.12, "item:titanbone_charm")],
        hooks=[
            Hook("on_attack_landed", on_attack, scope=HookScope.PER_HIT),
            Hook("on_damage_taken", on_damaged, scope=HookScope.PER_HIT),
        ],
    )


# --- Beastheart Gauntlet (Fang + Stoneplate) ---
@register_item("beastheart_gauntlet")
def beastheart_gauntlet(owner: Any) -> EffectBundle:
    """Beastheart Gauntlet — +12% STR, +14% Armor; the first time the holder drops
    below 35% HP, gains a large barrier (25% max HP)."""
    state = {"paid": False}

    def on_damaged(ctx: Any, ev: Any) -> None:
        if ev.target is not owner or state["paid"]:
            return
        if owner.alive and owner.hp / owner.max_hp < 0.35:
            state["paid"] = True
            ctx.grant_barrier(owner, owner.max_hp * 0.25)

    return EffectBundle(
        modifiers=[_str_mod(1.12, "item:beastheart_gauntlet"), _armor_mod(1.14, "item:beastheart_gauntlet")],
        hooks=[Hook("on_damage_taken", on_damaged, scope=HookScope.PER_HIT)],
    )


# --- Twinclaw Pact (Fang + Wardpelt) ---
@register_item("twinclaw_pact")
def twinclaw_pact(owner: Any) -> EffectBundle:
    """Twinclaw Pact — +12% STR, +14% RES; the holder alternates — one strike deals
    +50% bonus damage, the next heals it for 30% of the hit."""
    state = {"n": 0}

    def on_attack(ctx: Any, ev: Any) -> None:
        if ev.attacker is not owner:
            return
        state["n"] += 1
        if state["n"] % 2 == 1:
            if ev.target.alive:
                ctx.deal_damage(owner, ev.target, ev.amount * 0.50, SourceTag.ITEM_PROC, crit=False)
        else:
            ctx.heal(owner, owner, ev.amount * 0.30)

    return EffectBundle(
        modifiers=[_str_mod(1.12, "item:twinclaw_pact"), _res_mod(1.14, "item:twinclaw_pact")],
        hooks=[Hook("on_attack_landed", on_attack, scope=HookScope.PER_HIT)],
    )


# --- Giantsbane (Fang + Keen Claw) ---
@register_item("giantsbane")
def giantsbane(owner: Any) -> EffectBundle:
    """Giantsbane — +12% STR, +15% Crit; autos deal bonus magic damage = 4% of the
    target's max HP (the anti-tank carry)."""
    def on_attack(ctx: Any, ev: Any) -> None:
        if ev.attacker is not owner or ev.tag == SourceTag.ITEM_PROC or not ev.target.alive:
            return
        ctx.deal_damage(owner, ev.target, ev.target.max_hp * 0.04, SourceTag.ITEM_PROC, crit=False)

    return EffectBundle(
        modifiers=[_str_mod(1.12, "item:giantsbane"), _crit_add(0.15, "item:giantsbane")],
        hooks=[Hook("on_attack_landed", on_attack, scope=HookScope.PER_HIT)],
    )


# --- Stormscale Quiver (Talon + Springtear) ---
@register_item("stormscale_quiver")
def stormscale_quiver(owner: Any) -> EffectBundle:
    """Stormscale Quiver — +12% AS, +15% mana regen; every 4th auto discharges a
    chain of lightning to up to 3 enemies near the target (INT/STR-scaled)."""
    state = {"n": 0}

    def on_attack(ctx: Any, ev: Any) -> None:
        if ev.attacker is not owner:
            return
        state["n"] += 1
        if state["n"] % 4 != 0:
            return
        from src.game.targeting import enemies_in_radius
        bolt = 0.6 * max(owner.stat("strength"), owner.stat("intelligence"))
        hit = 0
        for e in enemies_in_radius(ev.target.position_q, ev.target.position_r, 3, owner, ctx):
            if hit >= 3:
                break
            ctx.deal_damage(owner, e, bolt, SourceTag.ITEM_PROC, crit=False, damage_type="magical")
            hit += 1

    return EffectBundle(
        modifiers=[*_as_mod(1.12, "item:stormscale_quiver"), _mr_mod(1.15, "item:stormscale_quiver")],
        hooks=[Hook("on_attack_landed", on_attack, scope=HookScope.PER_HIT)],
    )


# --- Quickpelt Harness (Talon + Old Hide) ---
@register_item("quickpelt_harness")
def quickpelt_harness(owner: Any) -> EffectBundle:
    """Quickpelt Harness — +12% AS, +12% HP; the first time the holder is hard-CC'd,
    it cleanses and is briefly (3 s) CC-immune."""
    _CC = ("stun", "root", "frozen", "fear", "silence", "disarm")
    state = {"used": False, "release": -1}

    def on_tick(ctx: Any, ev: Any) -> None:
        if not owner.alive:
            return
        if not state["used"] and any(owner.has_status(s) for s in _CC):
            state["used"] = True
            for s in _CC:
                if owner.has_status(s):
                    ctx.remove_status(owner, s)
            owner.cc_immune = True
            state["release"] = ev.tick + secs(3)
        elif state["release"] >= 0 and ev.tick >= state["release"]:
            owner.cc_immune = False
            state["release"] = -1

    return EffectBundle(
        modifiers=[*_as_mod(1.12, "item:quickpelt_harness"), _hp_mod(1.12, "item:quickpelt_harness")],
        hooks=[Hook("on_tick", on_tick, scope=HookScope.PER_HIT)],
    )


# --- Sundertalon (Talon + Stoneplate) ---
@register_item("sundertalon")
def sundertalon(owner: Any) -> EffectBundle:
    """Sundertalon — +12% AS, +14% Armor; the holder's autos shred the target's
    Armor by 18% (single refreshing TIMED mod, 3 s)."""
    SRC = "item:sundertalon"

    def on_attack(ctx: Any, ev: Any) -> None:
        if ev.attacker is not owner or not ev.target.alive:
            return
        t = ev.target
        t.modifiers = [m for m in t.modifiers if not (m.source_id == SRC and m.stat == "armor")]
        t.modifiers.append(Modifier(
            "armor", "mul", 0.82, Lifetime.TIMED, SRC, expires_at_tick=ctx.current_tick + secs(3)))

    return EffectBundle(
        modifiers=[*_as_mod(1.12, "item:sundertalon"), _armor_mod(1.14, "item:sundertalon")],
        hooks=[Hook("on_attack_landed", on_attack, scope=HookScope.PER_HIT)],
    )


# --- Stalkerclaw (Talon + Keen Claw) ---
@register_item("stalkerclaw")
def stalkerclaw(owner: Any) -> EffectBundle:
    """Stalkerclaw — +14% AS, +15% Crit (the clean auto-attack crit stat stick)."""
    return EffectBundle(modifiers=[*_as_mod(1.14, "item:stalkerclaw"), _crit_add(0.15, "item:stalkerclaw")])


# --- Stoneward Idol (Heartseed + Stoneplate) ---
@register_item("stoneward_idol")
def stoneward_idol(owner: Any) -> EffectBundle:
    """Stoneward Idol — +14% INT, +16% Armor (the durable backline-caster anchor)."""
    return EffectBundle(modifiers=[_int_mod(1.14, "item:stoneward_idol"), _armor_mod(1.16, "item:stoneward_idol")])


# --- Sapwood Aegis (Springtear + Old Hide) ---
@register_item("sapwood_aegis")
def sapwood_aegis(owner: Any) -> EffectBundle:
    """Sapwood Aegis — +15% mana regen, +12% HP; shields the holder at combat start
    (20% max HP); when that shield breaks, releases an INT-scaled burst to nearby
    enemies."""
    state = {"shielded": False, "burst": False}

    def on_start(ctx: Any, ev: Any) -> None:
        ctx.grant_barrier(owner, owner.max_hp * 0.20)
        state["shielded"] = True

    def on_tick(ctx: Any, ev: Any) -> None:
        if not owner.alive or state["burst"] or not state["shielded"]:
            return
        if owner.barrier_total <= 0.0:
            state["burst"] = True
            from src.game.targeting import enemies_in_radius
            dmg = 2.0 * owner.stat("intelligence")
            for e in enemies_in_radius(owner.position_q, owner.position_r, 2, owner, ctx):
                ctx.deal_damage(owner, e, dmg, SourceTag.ITEM_PROC, crit=False, damage_type="magical")

    return EffectBundle(
        modifiers=[_mr_mod(1.15, "item:sapwood_aegis"), _hp_mod(1.12, "item:sapwood_aegis")],
        hooks=[
            Hook("on_combat_start", on_start, scope=HookScope.PER_HIT),
            Hook("on_tick", on_tick, scope=HookScope.PER_HIT),
        ],
    )


# --- Warden's Dewstone (Springtear + Stoneplate) ---
@register_item("wardens_dewstone")
def wardens_dewstone(owner: Any) -> EffectBundle:
    """Warden's Dewstone — +15% mana regen, +14% Armor; at combat start grants
    adjacent allies +15% mana regen (the defensive support-caster anchor)."""
    def on_start(ctx: Any, ev: Any) -> None:
        if ctx is None:
            return
        from src.game.targeting import allies_in_radius
        for ally in allies_in_radius(owner.position_q, owner.position_r, 1, owner, ctx):
            if ally is owner:
                continue
            ctx.apply_modifier(ally, Modifier("mana_regen", "mul", 1.15, Lifetime.COMBAT, "item:wardens_dewstone"))

    return EffectBundle(
        modifiers=[_mr_mod(1.15, "item:wardens_dewstone"), _armor_mod(1.14, "item:wardens_dewstone")],
        hooks=[Hook("on_combat_start", on_start, scope=HookScope.PER_HIT)],
    )


# --- Seasonward Charm (Springtear + Wardpelt) ---
@register_item("seasonward_charm")
def seasonward_charm(owner: Any) -> EffectBundle:
    """Seasonward Charm — +15% mana regen, +14% RES; adapts — every 2 s it bolsters
    the defense (Armor vs physical / Resistance vs magic) matching whichever damage
    type has hurt the holder most recently."""
    dmg = {"physical": 0.0, "magical": 0.0}
    SRC = "item:seasonward_charm"

    def on_damaged(ctx: Any, ev: Any) -> None:
        if ev.target is owner:
            dmg[getattr(ev, "damage_type", "physical")] = dmg.get(getattr(ev, "damage_type", "physical"), 0.0) + (ev.amount or 0.0)

    def on_tick(ctx: Any, ev: Any) -> None:
        if not owner.alive or ev.tick == 0 or ev.tick % (2 * SECS) != 0:
            return
        if dmg["physical"] <= 0.0 and dmg["magical"] <= 0.0:
            return
        stat = "armor" if dmg["physical"] >= dmg["magical"] else "resistance"
        owner.modifiers = [m for m in owner.modifiers if m.source_id != SRC]
        owner.modifiers.append(Modifier(stat, "mul", 1.20, Lifetime.TIMED, SRC, expires_at_tick=ev.tick + 3 * SECS))
        dmg["physical"] = dmg["magical"] = 0.0

    return EffectBundle(
        modifiers=[_mr_mod(1.15, "item:seasonward_charm"), _res_mod(1.14, "item:seasonward_charm")],
        hooks=[
            Hook("on_damage_taken", on_damaged, scope=HookScope.PER_HIT),
            Hook("on_tick", on_tick, scope=HookScope.PER_HIT),
        ],
    )


# --- Dewclaw Fetish (Springtear + Keen Claw) ---
@register_item("dewclaw_fetish")
def dewclaw_fetish(owner: Any) -> EffectBundle:
    """Dewclaw Fetish — +15% mana regen, +15% Crit (a crit item for a cast-cycling carry)."""
    return EffectBundle(modifiers=[_mr_mod(1.15, "item:dewclaw_fetish"), _crit_add(0.15, "item:dewclaw_fetish")])


# --- Spiritbark Hide (Old Hide + Wardpelt) ---
@register_item("spiritbark_hide")
def spiritbark_hide(owner: Any) -> EffectBundle:
    """Spiritbark Hide — +12% HP, +16% RES (the anti-magic frontline brick)."""
    return EffectBundle(modifiers=[_hp_mod(1.12, "item:spiritbark_hide"), _res_mod(1.16, "item:spiritbark_hide")])


# --- Gorehide Wrap (Old Hide + Keen Claw) ---
@register_item("gorehide_wrap")
def gorehide_wrap(owner: Any) -> EffectBundle:
    """Gorehide Wrap — +14% HP, +15% Crit (lets a fragile crit-carry survive the frontline)."""
    return EffectBundle(modifiers=[_hp_mod(1.14, "item:gorehide_wrap"), _crit_add(0.15, "item:gorehide_wrap")])


# --- Greatward Carapace (Stoneplate + Wardpelt) ---
@register_item("greatward_carapace")
def greatward_carapace(owner: Any) -> EffectBundle:
    """Greatward Carapace — +14% Armor, +14% RES; at combat start the holder's
    defenses scale with the enemy count (+4% Armor & RES per living enemy)."""
    def on_start(ctx: Any, ev: Any) -> None:
        if ctx is None:
            return
        n = sum(1 for e in ctx.enemies_of(owner) if e.alive)
        if n <= 0:
            return
        owner.modifiers.append(Modifier("armor", "mul", 1.0 + 0.04 * n, Lifetime.COMBAT, "item:greatward_carapace"))
        owner.modifiers.append(Modifier("resistance", "mul", 1.0 + 0.04 * n, Lifetime.COMBAT, "item:greatward_carapace"))

    return EffectBundle(
        modifiers=[_armor_mod(1.14, "item:greatward_carapace"), _res_mod(1.14, "item:greatward_carapace")],
        hooks=[Hook("on_combat_start", on_start, scope=HookScope.PER_HIT)],
    )


# --- Edge of Stone (Stoneplate + Keen Claw) ---
@register_item("edge_of_stone")
def edge_of_stone(owner: Any) -> EffectBundle:
    """Edge of Stone — +16% Armor, +15% Crit (a bruiser-carry hybrid stat stick)."""
    return EffectBundle(modifiers=[_armor_mod(1.16, "item:edge_of_stone"), _crit_add(0.15, "item:edge_of_stone")])


# --- Hexward Claw (Wardpelt + Keen Claw) ---
@register_item("hexward_claw")
def hexward_claw(owner: Any) -> EffectBundle:
    """Hexward Claw — +16% RES, +15% Crit (a crit item that survives magic burst)."""
    return EffectBundle(modifiers=[_res_mod(1.16, "item:hexward_claw"), _crit_add(0.15, "item:hexward_claw")])
