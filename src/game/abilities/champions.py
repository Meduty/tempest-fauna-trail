"""Champion abilities — hooked to roster via content.py naming convention.

Champion IDs use `{piece_id}.active` and `{piece_id}.passive` patterns where
piece_id is the full roster id (e.g. `champ_torrent_heron`).
This module registers real handlers for champions from the roster.
Unregistered ability IDs gracefully no-op in the combat engine.
"""

from __future__ import annotations

from typing import Any

from src.game.effects import (
    EffectBundle,
    Hook,
    HookScope,
    Lifetime,
    Modifier,
    SourceTag,
)
from src.game.models import WeatherState
from src.game.registries import (
    ABILITY_META,
    ABILITY_REGISTRY,
    AbilityMeta,
    Clause,
    MaxOfTerm,
    PctResource,
    ScalingTerm,
    SummonSpec,
    register_active,
    register_passive,
)
from src.game.targeting import (
    lowest_hp_ally,
    lowest_hp_enemy,
    primary_target,
    neighbors_of,
    allies_in_radius,
    enemies_in_radius,
    furthest_enemy,
    random_enemy,
)


# ===========================================================================
# CLEAR — The Sunwild
# ===========================================================================


# --- Dawnwisp (T1, SUP-Heal) ---
# Cast: knit a wound on the lowest-HP ally, INT-scaled heal.
DAWNWISP_HEAL = ScalingTerm("heal", 40.0, "intelligence*2.5")


@register_active("champ_dawnwisp.active")
def dawnwisp_active(ctx: Any, actor: Any, targets: list) -> None:
    ally = lowest_hp_ally(actor, ctx)
    if not ally:
        return
    ctx.heal(actor, ally, DAWNWISP_HEAL.eval(actor))


ABILITY_META["champ_dawnwisp.active"] = AbilityMeta(
    name="Knit Wound", kind="active",
    blurb="Mend the lowest-HP ally for {heal}.",
    terms=(DAWNWISP_HEAL,), tags=("heal",),
)


# Passive: heal-over-time ticks on heal target (periodic tick effect every 100 ticks)
DAWNWISP_HOT = ScalingTerm("bonus", 0.0, "intelligence*0.3")


@register_passive("champ_dawnwisp.passive")
def dawnwisp_passive(owner: Any) -> EffectBundle:
    state = {"healing": False}

    def hook(ctx: Any, event: Any) -> None:
        if event.source is not owner:
            return
        if state["healing"]:
            return  # Prevent recursion
        state["healing"] = True
        # Small bonus heal (simulates HoT without G9)
        ctx.heal(owner, event.target, DAWNWISP_HOT.eval(owner))
        state["healing"] = False

    return EffectBundle(hooks=[
        Hook("on_heal", hook, scope=HookScope.ONCE_PER_CAST),
    ])


ABILITY_META["champ_dawnwisp.passive"] = AbilityMeta(
    name="Lingering Light", kind="passive",
    blurb="Each of your heals also restores {bonus} to its target.",
    terms=(DAWNWISP_HOT,), tags=("heal",),
)


# --- Veldt Pronghorn (T2, ADC-STR Warrior) ---
# Passive: every 3rd auto strikes twice.
_PRONGHORN_EXTRA_MULT = 0.5


@register_passive("champ_veldt_pronghorn.passive")
def veldt_pronghorn_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 3 == 0:
            ctx.deal_damage(owner, event.target, event.amount * _PRONGHORN_EXTRA_MULT,
                          SourceTag.BASIC_ATTACK, damage_type="physical")

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_veldt_pronghorn.passive"] = AbilityMeta(
    name="Double Kick", kind="passive",
    blurb="Every 3rd auto-attack strikes a second time.",
    clauses=(Clause(f"The extra hit deals {int(_PRONGHORN_EXTRA_MULT * 100)}% of the attack's damage."),),
    tags=("physical",),
)


# Active: lunging charge — STR-scaled single target
VELDT_PRONGHORN_DMG = ScalingTerm("damage", 50.0, "strength*1.8")


@register_active("champ_veldt_pronghorn.active")
def veldt_pronghorn_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, VELDT_PRONGHORN_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")


ABILITY_META["champ_veldt_pronghorn.active"] = AbilityMeta(
    name="Lunging Charge", kind="active",
    blurb="Charge the primary target for {damage} physical damage.",
    terms=(VELDT_PRONGHORN_DMG,), tags=("physical",),
)


# --- Ember Salamander (T3, APC-INT Mage) ---
# Cast: line of kindling light, burns ground for several ticks.
EMBER_SALAMANDER_DMG = ScalingTerm("damage", 60.0, "intelligence*1.8")


@register_active("champ_ember_salamander.active")
def ember_salamander_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, EMBER_SALAMANDER_DMG.eval(actor), SourceTag.ABILITY)
    ctx.apply_status(target, "burn", duration_ticks=300, source_id=actor.id)


ABILITY_META["champ_ember_salamander.active"] = AbilityMeta(
    name="Kindling Light", kind="active",
    blurb="Sear the primary target for {damage} magic damage.",
    terms=(EMBER_SALAMANDER_DMG,),
    clauses=(Clause("Sets the target burning for 3s."),), tags=("magic", "burn"),
)


EMBER_SALAMANDER_BONUS = ScalingTerm("bonus", 0.0, "intelligence*0.3")


@register_passive("champ_ember_salamander.passive")
def ember_salamander_passive(owner: Any) -> EffectBundle:
    # Bonus damage vs burning targets
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        if event.target.has_status("burn"):
            ctx.deal_damage(owner, event.target, EMBER_SALAMANDER_BONUS.eval(owner),
                          SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_ember_salamander.passive"] = AbilityMeta(
    name="Smoldering Strikes", kind="passive",
    blurb="Auto-attacks against burning targets deal {bonus} bonus magic damage.",
    terms=(EMBER_SALAMANDER_BONUS,), tags=("magic", "burn"),
)


# --- Goldcrest Lark (T4, SUP-Buff) ---
# Cast: allies gain damage and Attack Speed for one round (600 ticks).
@register_active("champ_goldcrest_lark.active")
def goldcrest_lark_active(ctx: Any, actor: Any, targets: list) -> None:
    allies = list(ctx.allies_of(actor))
    for ally in allies:
        ctx.apply_modifier(ally, Modifier(
            "strength", "add", 20.0, Lifetime.TIMED,
            "ability:champ_goldcrest_lark.active",
            expires_at_tick=ctx.current_tick + 600,
        ))
        ctx.apply_modifier(ally, Modifier(
            "attack_speed", "mul", 1.2, Lifetime.TIMED,
            "ability:champ_goldcrest_lark.active",
            expires_at_tick=ctx.current_tick + 600,
        ))


ABILITY_META["champ_goldcrest_lark.active"] = AbilityMeta(
    name="Rallying Song", kind="active",
    blurb="Empower the whole team for 6s.",
    clauses=(Clause("Allies gain +20 Strength and +20% Attack Speed."),),
    tags=("buff", "team"),
)


@register_passive("champ_goldcrest_lark.passive")
def goldcrest_lark_passive(owner: Any) -> EffectBundle:
    # Lark's song: allies near lark gain a small INT boost at combat start
    return EffectBundle(modifiers=[
        Modifier("intelligence", "add", 10.0, Lifetime.COMBAT, "passive:champ_goldcrest_lark"),
    ])


ABILITY_META["champ_goldcrest_lark.passive"] = AbilityMeta(
    name="Dawn Chorus", kind="passive",
    blurb="Grants +10 Intelligence for the whole battle.",
    tags=("buff",),
)


# --- Aegis Tortoise (T5, Tank-ARM+RES) ---
# Passive: reduces damage taken from adjacent attackers.
@register_passive("champ_aegis_tortoise.passive")
def aegis_tortoise_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any, value: float) -> float:
        if event.target is not owner:
            return value
        from src.game.combat import hex_distance
        dist = hex_distance(
            event.attacker.position_q, event.attacker.position_r,
            owner.position_q, owner.position_r,
        )
        if dist <= 1:
            return value * 0.8  # 20% reduction from adjacent
        return value

    return EffectBundle(hooks=[
        Hook("on_damage_pre", hook, scope=HookScope.PER_HIT, priority=50),
    ])


ABILITY_META["champ_aegis_tortoise.passive"] = AbilityMeta(
    name="Bulwark Shell", kind="passive",
    blurb="Reduces damage from adjacent attackers by 20%.",
    tags=("defense",),
)


@register_active("champ_aegis_tortoise.active")
def aegis_tortoise_active(ctx: Any, actor: Any, targets: list) -> None:
    # Fortify: gain armor and resistance for 600 ticks
    ctx.apply_modifier(actor, Modifier(
        "armor", "add", 30.0, Lifetime.TIMED,
        "ability:champ_aegis_tortoise.active",
        expires_at_tick=ctx.current_tick + 600,
    ))
    ctx.apply_modifier(actor, Modifier(
        "resistance", "add", 30.0, Lifetime.TIMED,
        "ability:champ_aegis_tortoise.active",
        expires_at_tick=ctx.current_tick + 600,
    ))


ABILITY_META["champ_aegis_tortoise.active"] = AbilityMeta(
    name="Fortify", kind="active",
    blurb="Harden the shell for 6s.",
    clauses=(Clause("Gain +30 Armor and +30 Resistance."),), tags=("defense", "buff"),
)


# --- Sunmane Lion (T6, Tank-STR) ---
# Cast: STR-scaled cleave; self-heal for a share of damage dealt.
SUNMANE_LION_DMG = ScalingTerm("damage", 80.0, "strength*2.0")
_LION_HEAL_SHARE = 0.3


@register_active("champ_sunmane_lion.active")
def sunmane_lion_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    dealt = ctx.deal_damage(actor, target, SUNMANE_LION_DMG.eval(actor), SourceTag.ABILITY,
                            damage_type="physical")
    # Self-heal for 30% of damage dealt (represents shield)
    ctx.heal(actor, actor, dealt * _LION_HEAL_SHARE)


ABILITY_META["champ_sunmane_lion.active"] = AbilityMeta(
    name="Regal Cleave", kind="active",
    blurb="Cleave the primary target for {damage} physical damage.",
    terms=(SUNMANE_LION_DMG,),
    clauses=(Clause(f"Heals for {int(_LION_HEAL_SHARE * 100)}% of the damage dealt."),),
    tags=("physical", "heal"),
)


@register_passive("champ_sunmane_lion.passive")
def sunmane_lion_passive(owner: Any) -> EffectBundle:
    # Pride's Fury: bonus STR when below 50% HP
    def hook(ctx: Any, event: Any) -> None:
        if event.target is not owner:
            return
        if owner.hp_pct < 0.5:
            ctx.apply_modifier(owner, Modifier(
                "strength", "add", 25.0, Lifetime.TIMED,
                "passive:champ_sunmane_lion",
                expires_at_tick=ctx.current_tick + 600,
            ))

    return EffectBundle(hooks=[
        Hook("on_damage_taken", hook, scope=HookScope.ONCE_PER_CAST),
    ])


ABILITY_META["champ_sunmane_lion.passive"] = AbilityMeta(
    name="Pride's Fury", kind="passive",
    blurb="Below 50% HP, gain +25 Strength for 6s when struck.",
    tags=("buff",),
)


# --- Goldhide Rhino (T7, Tank-Heal) ---
# Passive: heals on auto-attack, scaling with max HP (PctResource, V.46).
_GOLDHIDE_PASSIVE_HEAL = PctResource("heal", 0.03)


@register_passive("champ_goldhide_rhino.passive")
def goldhide_rhino_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        ctx.heal(owner, owner, _GOLDHIDE_PASSIVE_HEAL.eval(owner))

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_goldhide_rhino.passive"] = AbilityMeta(
    name="Thick Hide", kind="passive",
    blurb="Each auto-attack heals you.",
    clauses=(Clause(template="Restores {heal} HP per hit.", terms=(_GOLDHIDE_PASSIVE_HEAL,)),),
    tags=("heal",),
)


GOLDHIDE_RHINO_DMG = ScalingTerm("damage", 60.0, "strength*1.5")
_GOLDHIDE_ACTIVE_HEAL = PctResource("heal", 0.05)


@register_active("champ_goldhide_rhino.active")
def goldhide_rhino_active(ctx: Any, actor: Any, targets: list) -> None:
    # Stampede: STR damage to target + small self-heal
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, GOLDHIDE_RHINO_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")
    ctx.heal(actor, actor, _GOLDHIDE_ACTIVE_HEAL.eval(actor))


ABILITY_META["champ_goldhide_rhino.active"] = AbilityMeta(
    name="Stampede", kind="active",
    blurb="Gore the primary target for {damage} physical damage.",
    terms=(GOLDHIDE_RHINO_DMG,),
    clauses=(Clause(template="Heals you for {heal} HP.", terms=(_GOLDHIDE_ACTIVE_HEAL,)),),
    tags=("physical", "heal"),
)


# --- Mirage Caracal (T8, APC-INT Assassin) ---
# Cast: blink execute (bonus damage to low-HP targets).
MIRAGE_CARACAL_DMG = ScalingTerm("damage", 80.0, "intelligence*2.2")
_CARACAL_EXECUTE_MULT = 1.5


@register_active("champ_mirage_caracal.active")
def mirage_caracal_active(ctx: Any, actor: Any, targets: list) -> None:
    target = lowest_hp_enemy(actor, ctx)
    if not target:
        return
    amount = MIRAGE_CARACAL_DMG.eval(actor)
    # Execute bonus: +50% damage if target below 30% HP
    if target.hp_pct < 0.3:
        amount *= _CARACAL_EXECUTE_MULT
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)


ABILITY_META["champ_mirage_caracal.active"] = AbilityMeta(
    name="Blink Execute", kind="active",
    blurb="Blink to the lowest-HP enemy for {damage} magic damage.",
    terms=(MIRAGE_CARACAL_DMG,),
    clauses=(Clause(f"Deals +{int((_CARACAL_EXECUTE_MULT - 1) * 100)}% to targets below 30% HP."),),
    tags=("magic", "execute"),
)


MIRAGE_CARACAL_BONUS = ScalingTerm("bonus", 0.0, "intelligence*0.5")


@register_passive("champ_mirage_caracal.passive")
def mirage_caracal_passive(owner: Any) -> EffectBundle:
    # After casting, next auto deals bonus INT damage
    state = {"empowered": False}

    def on_cast(ctx: Any, event: Any) -> None:
        if event.caster is not owner:
            return
        state["empowered"] = True

    def on_attack(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        if state["empowered"]:
            state["empowered"] = False
            ctx.deal_damage(owner, event.target, MIRAGE_CARACAL_BONUS.eval(owner), SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_cast_complete", on_cast, scope=HookScope.PER_HIT),
        Hook("on_attack_landed", on_attack, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_mirage_caracal.passive"] = AbilityMeta(
    name="Afterimage", kind="passive",
    blurb="After casting, your next auto-attack deals {bonus} bonus magic damage.",
    terms=(MIRAGE_CARACAL_BONUS,), tags=("magic",),
)


# --- Sunspear Falcon (T9, ADC-STR Marksman) ---
# Passive: sun-mark on target after first auto; bonus damage on subsequent autos.
SUNSPEAR_FALCON_BONUS = ScalingTerm("bonus", 0.0, "strength*0.35")


@register_passive("champ_sunspear_falcon.passive")
def sunspear_falcon_passive(owner: Any) -> EffectBundle:
    state: dict[str, bool] = {}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        target_id = event.target.id
        if target_id in state:
            # Marked — bonus damage
            ctx.deal_damage(owner, event.target, SUNSPEAR_FALCON_BONUS.eval(owner),
                          SourceTag.BASIC_ATTACK, damage_type="physical")
        else:
            state[target_id] = True

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_sunspear_falcon.passive"] = AbilityMeta(
    name="Sun Mark", kind="passive",
    blurb="The first auto-attack marks a target; every later auto on it deals {bonus} bonus physical damage.",
    terms=(SUNSPEAR_FALCON_BONUS,), tags=("physical",),
)


SUNSPEAR_FALCON_DMG = ScalingTerm("damage", 70.0, "strength*2.0")


@register_active("champ_sunspear_falcon.active")
def sunspear_falcon_active(ctx: Any, actor: Any, targets: list) -> None:
    # Diving strike: STR damage to primary, marks target
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, SUNSPEAR_FALCON_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")


ABILITY_META["champ_sunspear_falcon.active"] = AbilityMeta(
    name="Diving Strike", kind="active",
    blurb="Dive the primary target for {damage} physical damage.",
    terms=(SUNSPEAR_FALCON_DMG,), tags=("physical",),
)


# --- Aurion (T10, Primordial — hybrid) ---
# Passive: gains +STR and +INT every 600 ticks (periodic tick effect)
@register_passive("champ_aurion.passive")
def aurion_passive(owner: Any) -> EffectBundle:
    state = {"last_proc_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        tick = ctx.current_tick
        if tick - state["last_proc_tick"] >= 600:
            state["last_proc_tick"] = tick
            ctx.apply_modifier(owner, Modifier(
                "strength", "add", 15.0, Lifetime.COMBAT,
                "passive:champ_aurion.ramping",
            ))
            ctx.apply_modifier(owner, Modifier(
                "intelligence", "add", 15.0, Lifetime.COMBAT,
                "passive:champ_aurion.ramping",
            ))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_aurion.passive"] = AbilityMeta(
    name="Ascendance", kind="passive",
    blurb="Every 6s, permanently gain +15 Strength and +15 Intelligence.",
    tags=("buff", "scaling"),
)


# Active: nova that disarms all enemies in radius 2
AURION_DMG = ScalingTerm("damage", 100.0, "strength*1.5+intelligence*1.5")


@register_active("champ_aurion.active")
def aurion_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = AURION_DMG.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 2, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount, SourceTag.ABILITY)
        ctx.apply_status(t, "disarm", duration_ticks=200, source_id=actor.id)


ABILITY_META["champ_aurion.active"] = AbilityMeta(
    name="Solar Nova", kind="active",
    blurb="Erupt for {damage} magic damage to all enemies within 2 hexes.",
    terms=(AURION_DMG,),
    clauses=(Clause("Disarms struck enemies for 2s."),), tags=("magic", "aoe", "disarm"),
)


# ===========================================================================
# RAIN — The Tidewild
# ===========================================================================


# --- Springfrog (T1, SUP-Heal) ---
# Cast: healing rain on lowest-HP ally, restoring health.
SPRINGFROG_HEAL = ScalingTerm("heal", 30.0, "intelligence*2.0")


@register_active("champ_springfrog.active")
def springfrog_active(ctx: Any, actor: Any, targets: list) -> None:
    ally = lowest_hp_ally(actor, ctx)
    if not ally:
        return
    ctx.heal(actor, ally, SPRINGFROG_HEAL.eval(actor))


ABILITY_META["champ_springfrog.active"] = AbilityMeta(
    name="Healing Rain", kind="active",
    blurb="Shower the lowest-HP ally for {heal}.",
    terms=(SPRINGFROG_HEAL,), tags=("heal",),
)


SPRINGFROG_HOT = ScalingTerm("heal", 0.0, "intelligence*0.4")


@register_passive("champ_springfrog.passive")
def springfrog_passive(owner: Any) -> EffectBundle:
    # HoT effect: periodic heal tick every 200 ticks to lowest ally
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 200:
            state["last_tick"] = ctx.current_tick
            ally = lowest_hp_ally(owner, ctx)
            if ally:
                ctx.heal(owner, ally, SPRINGFROG_HOT.eval(owner))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_springfrog.passive"] = AbilityMeta(
    name="Dewfall", kind="passive",
    blurb="Every 2s, heal the lowest-HP ally for {heal}.",
    terms=(SPRINGFROG_HOT,), tags=("heal",),
)


# --- Reedbank Otter (T2, ADC-STR Skirmisher) ---
# Passive: gains move speed after attacking.
@register_passive("champ_reedbank_otter.passive")
def reedbank_otter_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        ctx.apply_modifier(owner, Modifier(
            "move_speed", "add", 20.0, Lifetime.TIMED,
            "passive:champ_reedbank_otter",
            expires_at_tick=ctx.current_tick + 300,
        ))

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_reedbank_otter.passive"] = AbilityMeta(
    name="Slipstream", kind="passive",
    blurb="Auto-attacks grant +20 Move Speed for 3s.",
    tags=("buff",),
)


REEDBANK_OTTER_DMG = ScalingTerm("damage", 40.0, "strength*1.6")


@register_active("champ_reedbank_otter.active")
def reedbank_otter_active(ctx: Any, actor: Any, targets: list) -> None:
    # Slippery strike: STR damage + MS boost
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, REEDBANK_OTTER_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")
    ctx.apply_modifier(actor, Modifier(
        "attack_speed", "add", 20.0, Lifetime.TIMED,
        "ability:champ_reedbank_otter",
        expires_at_tick=ctx.current_tick + 400,
    ))


ABILITY_META["champ_reedbank_otter.active"] = AbilityMeta(
    name="Slippery Strike", kind="active",
    blurb="Strike the primary target for {damage} physical damage.",
    terms=(REEDBANK_OTTER_DMG,),
    clauses=(Clause("Gain +20 Attack Speed for 4s."),), tags=("physical", "buff"),
)


# --- Torrent Heron (T3, APC-STR Mage) ---
# Cast: three water-spears in a cone, STR-scaled.
TORRENT_HERON_DMG = ScalingTerm("damage", 50.0, "strength*1.6")
_TORRENT_SPLASH_MULT = 0.6


@register_active("champ_torrent_heron.active")
def torrent_heron_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = TORRENT_HERON_DMG.eval(actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    hit_count = 0
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor) and hit_count < 2:
            ctx.deal_damage(actor, n, amount * _TORRENT_SPLASH_MULT, SourceTag.ABILITY,
                            damage_type="physical")
            hit_count += 1


ABILITY_META["champ_torrent_heron.active"] = AbilityMeta(
    name="Water Spears", kind="active",
    blurb="Spear the primary target for {damage} physical damage.",
    terms=(TORRENT_HERON_DMG,),
    clauses=(Clause(f"Up to 2 adjacent enemies take {int(_TORRENT_SPLASH_MULT * 100)}% splash."),),
    tags=("physical", "aoe"),
)


@register_passive("champ_torrent_heron.passive")
def torrent_heron_passive(owner: Any) -> EffectBundle:
    # Water affinity: bonus damage in rain weather
    return EffectBundle(modifiers=[
        Modifier("strength", "add", 8.0, Lifetime.COMBAT, "passive:champ_torrent_heron"),
    ])


ABILITY_META["champ_torrent_heron.passive"] = AbilityMeta(
    name="Tidal Might", kind="passive",
    blurb="Grants +8 Strength for the whole battle.",
    tags=("buff",),
)


# --- Grovekeeper Tapir (T4, Hybrid Bruiser-Mender) ---
# Cast: vine snare + DoT
GROVEKEEPER_TAPIR_DMG = ScalingTerm("damage", 40.0, "strength*1.0+intelligence*1.0")


@register_active("champ_grovekeeper_tapir.active")
def grovekeeper_tapir_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, GROVEKEEPER_TAPIR_DMG.eval(actor), SourceTag.ABILITY)
    ctx.apply_status(target, "root", duration_ticks=200, source_id=actor.id)
    ctx.apply_status(target, "poison", duration_ticks=400, stacks=2, source_id=actor.id)


ABILITY_META["champ_grovekeeper_tapir.active"] = AbilityMeta(
    name="Vine Snare", kind="active",
    blurb="Snare the primary target for {damage} hybrid damage.",
    terms=(GROVEKEEPER_TAPIR_DMG,),
    clauses=(Clause("Roots for 2s and applies 2 stacks of poison for 4s."),),
    tags=("hybrid", "root", "poison"),
)


# Regen: %-of-max-HP (PctResource, V.46).
_GROVEKEEPER_REGEN = PctResource("heal", 0.02)


@register_passive("champ_grovekeeper_tapir.passive")
def grovekeeper_tapir_passive(owner: Any) -> EffectBundle:
    # Regen: periodic heal every 300 ticks
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 300:
            state["last_tick"] = ctx.current_tick
            ctx.heal(owner, owner, _GROVEKEEPER_REGEN.eval(owner))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_grovekeeper_tapir.passive"] = AbilityMeta(
    name="Verdant Renewal", kind="passive",
    blurb="Regenerates health over time.",
    clauses=(Clause(template="Heals {heal} HP every 3s.", terms=(_GROVEKEEPER_REGEN,)),),
    tags=("heal",),
)


# --- Coral Colossus (T5, Tank-Guardian) ---
# Passive: regen when below 40% HP (PctResource, V.46)
_CORAL_REGEN = PctResource("heal", 0.04)


@register_passive("champ_coral_colossus.passive")
def coral_colossus_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 200:
            state["last_tick"] = ctx.current_tick
            if owner.hp_pct < 0.4:
                ctx.heal(owner, owner, _CORAL_REGEN.eval(owner))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_coral_colossus.passive"] = AbilityMeta(
    name="Coral Mend", kind="passive",
    blurb="Regenerates rapidly while wounded.",
    clauses=(Clause(template="Below 40% HP, heals {heal} HP every 2s.", terms=(_CORAL_REGEN,)),),
    tags=("heal",),
)


# Active: shell immunity (invulnerability via massive damage reduction for 300 ticks)
@register_active("champ_coral_colossus.active")
def coral_colossus_active(ctx: Any, actor: Any, targets: list) -> None:
    # Simulate invulnerability: massive armor+resistance buff
    ctx.apply_modifier(actor, Modifier(
        "armor", "add", 200.0, Lifetime.TIMED,
        "ability:champ_coral_colossus.invuln",
        expires_at_tick=ctx.current_tick + 300,
    ))
    ctx.apply_modifier(actor, Modifier(
        "resistance", "add", 200.0, Lifetime.TIMED,
        "ability:champ_coral_colossus.invuln",
        expires_at_tick=ctx.current_tick + 300,
    ))


ABILITY_META["champ_coral_colossus.active"] = AbilityMeta(
    name="Shell Bastion", kind="active",
    blurb="Withdraw into the shell for 3s, becoming nearly invulnerable.",
    clauses=(Clause("Gain +200 Armor and +200 Resistance."),), tags=("defense", "buff"),
)


# --- Marsh Thrush (T6, SUP-Buff) ---
# Cast: team MS+AS buff — buff magnitude scales from INT
MARSH_THRUSH_BUFF = ScalingTerm("haste", 8.0, "intelligence*0.14")


@register_active("champ_marsh_thrush.active")
def marsh_thrush_active(ctx: Any, actor: Any, targets: list) -> None:
    allies = list(ctx.allies_of(actor))
    # Buff magnitude scales from INT — stronger buffs for higher-tier/better-geared support mages
    bonus = MARSH_THRUSH_BUFF.eval(actor)
    for ally in allies:
        ctx.apply_modifier(ally, Modifier(
            "move_speed", "add", bonus, Lifetime.TIMED,
            "ability:champ_marsh_thrush",
            expires_at_tick=ctx.current_tick + 600,
        ))
        ctx.apply_modifier(ally, Modifier(
            "attack_speed", "add", bonus, Lifetime.TIMED,
            "ability:champ_marsh_thrush",
            expires_at_tick=ctx.current_tick + 600,
        ))


ABILITY_META["champ_marsh_thrush.active"] = AbilityMeta(
    name="Quickening Trill", kind="active",
    blurb="Grant the whole team +{haste} Move Speed and +{haste} Attack Speed for 6s.",
    terms=(MARSH_THRUSH_BUFF,), tags=("buff", "team"),
)


MARSH_THRUSH_PASSIVE_MS = ScalingTerm("speed", 5.0, "intelligence*0.1")


@register_passive("champ_marsh_thrush.passive")
def marsh_thrush_passive(owner: Any) -> EffectBundle:
    # Passive MS buff also scales from INT
    return EffectBundle(modifiers=[
        Modifier("move_speed", "add", MARSH_THRUSH_PASSIVE_MS.eval(owner),
                 Lifetime.COMBAT, "passive:champ_marsh_thrush"),
    ])


ABILITY_META["champ_marsh_thrush.passive"] = AbilityMeta(
    name="Restless Wings", kind="passive",
    blurb="Grants +{speed} Move Speed for the whole battle.",
    terms=(MARSH_THRUSH_PASSIVE_MS,), tags=("buff",),
)


# --- Mirewarden Toad (T7, Tank-Guardian) ---
# Active: tongue pull (slow + damage)
MIREWARDEN_TOAD_DMG = ScalingTerm("damage", 50.0, "intelligence*1.5")


@register_active("champ_mirewarden_toad.active")
def mirewarden_toad_active(ctx: Any, actor: Any, targets: list) -> None:
    target = furthest_enemy(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, MIREWARDEN_TOAD_DMG.eval(actor), SourceTag.ABILITY)
    ctx.apply_status(target, "slow", duration_ticks=300, stacks=2, source_id=actor.id)
    ctx.apply_status(target, "root", duration_ticks=150, source_id=actor.id)


ABILITY_META["champ_mirewarden_toad.active"] = AbilityMeta(
    name="Tongue Pull", kind="active",
    blurb="Yank the furthest enemy for {damage} magic damage.",
    terms=(MIREWARDEN_TOAD_DMG,),
    clauses=(Clause("Applies 2 stacks of slow for 3s and roots for 1.5s."),),
    tags=("magic", "slow", "root"),
)


# Passive: slow aura — periodic re-application every 300 ticks
@register_passive("champ_mirewarden_toad.passive")
def mirewarden_toad_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 300:
            state["last_tick"] = ctx.current_tick
            enemies = enemies_in_radius(owner.position_q, owner.position_r, 2, owner, ctx)
            for e in enemies:
                ctx.apply_status(e, "slow", duration_ticks=350, stacks=1, source_id=owner.id)

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_mirewarden_toad.passive"] = AbilityMeta(
    name="Mire Aura", kind="passive",
    blurb="Every 3s, slows all enemies within 2 hexes.",
    clauses=(Clause("Applies 1 stack of slow for 3.5s."),), tags=("slow", "aoe"),
)


# --- Glade Heron (T8, ADC-INT Hunter) ---
# Identity: poison-stack DPS carry whose INT routes into damage via *speed*, not
# auto-punch. Autos apply poison + (once ramped) a poison burst; the active is a
# self-haste that, with enough INT, lets autos out-pace poison decay.
_HERON_HASTE_SOURCE = "ability:champ_glade_heron.haste"


# Passive: Venom Tip — each auto applies one poison stack, and once the target is
# deeply poisoned (3+ stacks) every auto detonates a small INT-scaled poison burst.
# The burst is the Heron's INT damage outlet (autos themselves barely scale on INT);
# it does NOT consume stacks, so it reinforces the sustain loop rather than
# fighting it. (Tuned to ~T8 peer DPS at L3 — see active.)
GLADE_HERON_BURST = ScalingTerm("burst", 0.0, "intelligence*0.2")


@register_passive("champ_glade_heron.passive")
def glade_heron_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        ctx.apply_status(event.target, "poison", duration_ticks=400, stacks=1,
                        source_id=owner.id)
        # Poison burst: bonus magic damage once poison has ramped to 3+ stacks.
        if event.target.status_stacks("poison") >= 3:
            ctx.deal_damage(owner, event.target, GLADE_HERON_BURST.eval(owner), SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_glade_heron.passive"] = AbilityMeta(
    name="Venom Tip", kind="passive",
    blurb="Each auto-attack applies a stack of poison for 4s.",
    terms=(GLADE_HERON_BURST,),
    clauses=(Clause("Against targets with 3+ poison stacks, autos also deal {burst} bonus magic damage."),),
    tags=("poison", "magic"),
)


# Active: Quickening — self attack-speed buff = INT×0.8 (additive). Auto interval =
# 60000 / AS ticks; poison net-stacks once apply out-paces decay, which uses
# percentage decay (V.25 decay_fraction) → poison settles at an investment-scaling
# plateau (stacks_eq ≈ apply_rate / frac) instead of running away — the build
# scales with INT/AS/items, no hard cap. Coeff 0.8 lands L3 DPS at ~T8 peer level.
# Refresh-replace (strip prior modifier first) so repeated casts never stack.
GLADE_HERON_HASTE = ScalingTerm("haste", 0.0, "intelligence*0.8")


@register_active("champ_glade_heron.active")
def glade_heron_active(ctx: Any, actor: Any, targets: list) -> None:
    as_bonus = GLADE_HERON_HASTE.eval(actor)
    actor.modifiers = [m for m in actor.modifiers if m.source_id != _HERON_HASTE_SOURCE]
    ctx.apply_modifier(actor, Modifier(
        "attack_speed", "add", as_bonus, Lifetime.TIMED,
        _HERON_HASTE_SOURCE, expires_at_tick=ctx.current_tick + 2500,
    ))


ABILITY_META["champ_glade_heron.active"] = AbilityMeta(
    name="Quickening", kind="active",
    blurb="Gain +{haste} Attack Speed for 25s, out-pacing poison decay.",
    terms=(GLADE_HERON_HASTE,), tags=("buff",),
)


# --- Riptide Caiman (T9, ADC-STR Stalker) ---
# Active: death-roll dash, bonus mana on kill
RIPTIDE_CAIMAN_DMG = ScalingTerm("damage", 100.0, "strength*2.5")


@register_active("champ_riptide_caiman.active")
def riptide_caiman_active(ctx: Any, actor: Any, targets: list) -> None:
    target = lowest_hp_enemy(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, RIPTIDE_CAIMAN_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")


ABILITY_META["champ_riptide_caiman.active"] = AbilityMeta(
    name="Death Roll", kind="active",
    blurb="Lunge at the lowest-HP enemy for {damage} physical damage.",
    terms=(RIPTIDE_CAIMAN_DMG,), tags=("physical",),
)


@register_passive("champ_riptide_caiman.passive")
def riptide_caiman_passive(owner: Any) -> EffectBundle:
    # Mana on kill
    def hook(ctx: Any, event: Any) -> None:
        if event.killer is not owner:
            return
        ctx.gain_mana(owner, owner.actives[0].cost * 0.4 if owner.actives else 0)

    return EffectBundle(hooks=[
        Hook("on_kill", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_riptide_caiman.passive"] = AbilityMeta(
    name="Bloodscent", kind="passive",
    blurb="Killing an enemy refunds 40% of your ability's mana cost.",
    tags=("mana",),
)


# --- Nerei (T10, Primordial — hybrid) ---
# Passive: after casting, next 3 autos deal bonus INT damage
NEREI_BONUS = ScalingTerm("bonus", 0.0, "intelligence*0.6")


@register_passive("champ_nerei.passive")
def nerei_passive(owner: Any) -> EffectBundle:
    state = {"empowered_autos": 0}

    def on_cast(ctx: Any, event: Any) -> None:
        if event.caster is not owner:
            return
        state["empowered_autos"] = 3

    def on_attack(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        if state["empowered_autos"] > 0:
            state["empowered_autos"] -= 1
            ctx.deal_damage(owner, event.target, NEREI_BONUS.eval(owner), SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_cast_complete", on_cast, scope=HookScope.PER_HIT),
        Hook("on_attack_landed", on_attack, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_nerei.passive"] = AbilityMeta(
    name="Tideturn", kind="passive",
    blurb="After casting, your next 3 auto-attacks each deal {bonus} bonus magic damage.",
    terms=(NEREI_BONUS,), tags=("magic",),
)


# Active: tidal wave — AOE INT damage
NEREI_DMG = ScalingTerm("damage", 90.0, "intelligence*2.0")
_NEREI_AOE_MULT = 0.7


@register_active("champ_nerei.active")
def nerei_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = NEREI_DMG.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * _NEREI_AOE_MULT, SourceTag.ABILITY)
    ctx.apply_status(actor, "charged", duration_ticks=300, source_id=actor.id)


ABILITY_META["champ_nerei.active"] = AbilityMeta(
    name="Tidal Wave", kind="active",
    blurb=f"Crash a wave over all enemies within 3 hexes, each taking {int(_NEREI_AOE_MULT * 100)}% of {{damage}} magic damage.",
    terms=(NEREI_DMG,),
    clauses=(Clause("Become charged for 3s."),),
    tags=("magic", "aoe"),
)


# ===========================================================================
# SNOW — The Frostwild
# ===========================================================================


# --- Snowpelt Cub (T1, Tank-Guardian) ---
# Passive: gains max HP every 600 ticks (periodic tick effect)
@register_passive("champ_snowpelt_cub.passive")
def snowpelt_cub_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 600:
            state["last_tick"] = ctx.current_tick
            owner.max_hp += 30.0
            owner.hp = min(owner.hp + 30.0, owner.max_hp)

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_snowpelt_cub.passive"] = AbilityMeta(
    name="Winter Growth", kind="passive",
    blurb="Steadily grows hardier through the battle.",
    clauses=(Clause("Every 6s, permanently gain +30 max HP (also healing 30)."),),
    tags=("scaling",),
)


SNOWPELT_CUB_DMG = ScalingTerm("damage", 25.0, "strength*1.2")


@register_active("champ_snowpelt_cub.active")
def snowpelt_cub_active(ctx: Any, actor: Any, targets: list) -> None:
    # Frostbite nip: small STR damage + slow
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, SNOWPELT_CUB_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")
    ctx.apply_status(target, "slow", duration_ticks=200, stacks=1, source_id=actor.id)


ABILITY_META["champ_snowpelt_cub.active"] = AbilityMeta(
    name="Frostbite Nip", kind="active",
    blurb="Nip the primary target for {damage} physical damage.",
    terms=(SNOWPELT_CUB_DMG,),
    clauses=(Clause("Applies 1 stack of slow for 2s."),), tags=("physical", "slow"),
)


# --- Wintermoth (T2, SUP-Buff) ---
# Active: grant ally AS buff
WINTERMOTH_HEAL = ScalingTerm("heal", 20.0, "intelligence*1.0")


@register_active("champ_wintermoth.active")
def wintermoth_active(ctx: Any, actor: Any, targets: list) -> None:
    ally = lowest_hp_ally(actor, ctx)
    if not ally:
        return
    ctx.apply_modifier(ally, Modifier(
        "attack_speed", "add", 25.0, Lifetime.TIMED,
        "ability:champ_wintermoth",
        expires_at_tick=ctx.current_tick + 600,
    ))
    ctx.heal(actor, ally, WINTERMOTH_HEAL.eval(actor))


ABILITY_META["champ_wintermoth.active"] = AbilityMeta(
    name="Frost Blessing", kind="active",
    blurb="Grant the lowest-HP ally +25 Attack Speed for 6s and heal {heal}.",
    terms=(WINTERMOTH_HEAL,), tags=("buff", "heal"),
)


@register_passive("champ_wintermoth.passive")
def wintermoth_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("resistance", "add", 8.0, Lifetime.COMBAT, "passive:champ_wintermoth"),
    ])


ABILITY_META["champ_wintermoth.passive"] = AbilityMeta(
    name="Frostward", kind="passive",
    blurb="Grants +8 Resistance for the whole battle.",
    tags=("buff",),
)


# --- Permafrost Walrus (T3, APC-STR Mage) ---
# Cast: ice-boulder, STR-scaled impact + small splash.
PERMAFROST_WALRUS_DMG = ScalingTerm("damage", 70.0, "strength*1.8")
_WALRUS_SPLASH_MULT = 0.4


@register_active("champ_permafrost_walrus.active")
def permafrost_walrus_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = PERMAFROST_WALRUS_DMG.eval(actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor):
            ctx.deal_damage(actor, n, amount * _WALRUS_SPLASH_MULT, SourceTag.ABILITY,
                            damage_type="physical")


ABILITY_META["champ_permafrost_walrus.active"] = AbilityMeta(
    name="Ice Boulder", kind="active",
    blurb="Hurl a boulder at the primary target for {damage} physical damage.",
    terms=(PERMAFROST_WALRUS_DMG,),
    clauses=(Clause(f"Adjacent enemies take {int(_WALRUS_SPLASH_MULT * 100)}% splash."),),
    tags=("physical", "aoe"),
)


@register_passive("champ_permafrost_walrus.passive")
def permafrost_walrus_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("strength", "add", 8.0, Lifetime.COMBAT, "passive:champ_permafrost_walrus"),
    ])


ABILITY_META["champ_permafrost_walrus.passive"] = AbilityMeta(
    name="Glacial Brawn", kind="passive",
    blurb="Grants +8 Strength for the whole battle.",
    tags=("buff",),
)


# --- Hoarfrost Owl (T4, SUP-Shield) ---
# Active: ally ice-shield (large armor buff) + chill burst on expiry
HOARFROST_OWL_HEAL = ScalingTerm("heal", 30.0, "intelligence*1.5")


@register_active("champ_hoarfrost_owl.active")
def hoarfrost_owl_active(ctx: Any, actor: Any, targets: list) -> None:
    ally = lowest_hp_ally(actor, ctx)
    if not ally:
        return
    # Shield as armor buff
    ctx.apply_modifier(ally, Modifier(
        "armor", "add", 60.0, Lifetime.TIMED,
        "ability:champ_hoarfrost_owl.shield",
        expires_at_tick=ctx.current_tick + 400,
    ))
    ctx.heal(actor, ally, HOARFROST_OWL_HEAL.eval(actor))


ABILITY_META["champ_hoarfrost_owl.active"] = AbilityMeta(
    name="Ice Shield", kind="active",
    blurb="Shield the lowest-HP ally with +60 Armor for 4s and heal {heal}.",
    terms=(HOARFROST_OWL_HEAL,), tags=("defense", "heal"),
)


@register_passive("champ_hoarfrost_owl.passive")
def hoarfrost_owl_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("intelligence", "add", 8.0, Lifetime.COMBAT, "passive:champ_hoarfrost_owl"),
    ])


ABILITY_META["champ_hoarfrost_owl.passive"] = AbilityMeta(
    name="Cold Insight", kind="passive",
    blurb="Grants +8 Intelligence for the whole battle.",
    tags=("buff",),
)


# --- Frostplate Tortoise (T5, Tank) ---
# Passive: stacking damage reduction on each hit taken
@register_passive("champ_frostplate_tortoise.passive")
def frostplate_tortoise_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any, value: float) -> float:
        if event.target is not owner:
            return value
        # Each hit grants stacking armor
        ctx.apply_modifier(owner, Modifier(
            "armor", "add", 5.0, Lifetime.TIMED,
            "passive:champ_frostplate_tortoise.stack",
            expires_at_tick=ctx.current_tick + 600,
        ))
        return value

    return EffectBundle(hooks=[
        Hook("on_damage_pre", hook, scope=HookScope.PER_HIT, priority=90),
    ])


ABILITY_META["champ_frostplate_tortoise.passive"] = AbilityMeta(
    name="Rimeplate", kind="passive",
    blurb="Each hit taken grants +5 Armor for 6s, stacking.",
    tags=("defense",),
)


FROSTPLATE_TORTOISE_DMG = ScalingTerm("damage", 60.0, "strength*1.6")


@register_active("champ_frostplate_tortoise.active")
def frostplate_tortoise_active(ctx: Any, actor: Any, targets: list) -> None:
    # Ice slam: STR damage + root
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, FROSTPLATE_TORTOISE_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")
    ctx.apply_status(target, "root", duration_ticks=200, source_id=actor.id)


ABILITY_META["champ_frostplate_tortoise.active"] = AbilityMeta(
    name="Ice Slam", kind="active",
    blurb="Slam the primary target for {damage} physical damage.",
    terms=(FROSTPLATE_TORTOISE_DMG,),
    clauses=(Clause("Roots for 2s."),), tags=("physical", "root"),
)


# --- Iceclaw Lynx (T6, ADC-INT Warrior) ---
# Passive: autos deal bonus INT-magic damage and briefly slow target.
ICECLAW_LYNX_BONUS = ScalingTerm("bonus", 0.0, "intelligence*0.4")


@register_passive("champ_iceclaw_lynx.passive")
def iceclaw_lynx_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        ctx.deal_damage(owner, event.target, ICECLAW_LYNX_BONUS.eval(owner), SourceTag.BASIC_ATTACK)
        ctx.apply_status(event.target, "slow", duration_ticks=100, stacks=1, source_id=owner.id)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_iceclaw_lynx.passive"] = AbilityMeta(
    name="Frostclaw", kind="passive",
    blurb="Auto-attacks deal {bonus} bonus magic damage and slow for 1s.",
    terms=(ICECLAW_LYNX_BONUS,), tags=("magic", "slow"),
)


ICECLAW_LYNX_DMG = ScalingTerm("damage", 80.0, "intelligence*2.0")


@register_active("champ_iceclaw_lynx.active")
def iceclaw_lynx_active(ctx: Any, actor: Any, targets: list) -> None:
    # Frost pounce: INT burst + freeze
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, ICECLAW_LYNX_DMG.eval(actor), SourceTag.ABILITY)
    ctx.apply_status(target, "frozen", duration_ticks=150, source_id=actor.id)


ABILITY_META["champ_iceclaw_lynx.active"] = AbilityMeta(
    name="Frost Pounce", kind="active",
    blurb="Pounce the primary target for {damage} magic damage.",
    terms=(ICECLAW_LYNX_DMG,),
    clauses=(Clause("Freezes for 1.5s."),), tags=("magic", "freeze"),
)


# --- Glacierback Mammoth (T7, Tank-Bruiser) ---
# Passive: +HP and +STR every 600 ticks
@register_passive("champ_glacierback_mammoth.passive")
def glacierback_mammoth_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 600:
            state["last_tick"] = ctx.current_tick
            owner.max_hp += 40.0
            owner.hp = min(owner.hp + 40.0, owner.max_hp)
            ctx.apply_modifier(owner, Modifier(
                "strength", "add", 10.0, Lifetime.COMBAT,
                "passive:champ_glacierback_mammoth.str",
            ))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_glacierback_mammoth.passive"] = AbilityMeta(
    name="Ancient Bulk", kind="passive",
    blurb="Grows mightier as the battle drags on.",
    clauses=(Clause("Every 6s, gain +40 max HP (healing 40) and +10 Strength."),),
    tags=("scaling", "buff"),
)


# Active: knockback stomp (STR damage + stun to neighbors)
GLACIERBACK_MAMMOTH_DMG = ScalingTerm("damage", 80.0, "strength*2.0")


@register_active("champ_glacierback_mammoth.active")
def glacierback_mammoth_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = GLACIERBACK_MAMMOTH_DMG.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 1, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount, SourceTag.ABILITY, damage_type="physical")
        ctx.apply_status(t, "stun", duration_ticks=100, source_id=actor.id)


ABILITY_META["champ_glacierback_mammoth.active"] = AbilityMeta(
    name="Knockback Stomp", kind="active",
    blurb="Stomp for {damage} physical damage to all adjacent enemies.",
    terms=(GLACIERBACK_MAMMOTH_DMG,),
    clauses=(Clause("Stuns struck enemies for 1s."),), tags=("physical", "aoe", "stun"),
)


# --- Frostfang Wolverine (T8, ADC-STR Stalker) ---
# Active: leap burst; crit vs frozen/slowed
FROSTFANG_WOLVERINE_DMG = ScalingTerm("damage", 90.0, "strength*2.2")
_FROSTFANG_BONUS_MULT = 1.5


@register_active("champ_frostfang_wolverine.active")
def frostfang_wolverine_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = FROSTFANG_WOLVERINE_DMG.eval(actor)
    # Bonus vs frozen/slowed
    if target.has_status("frozen") or target.has_status("slow"):
        amount *= _FROSTFANG_BONUS_MULT
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical", crit=True)


ABILITY_META["champ_frostfang_wolverine.active"] = AbilityMeta(
    name="Frozen Leap", kind="active",
    blurb="Leap onto the primary target for {damage} physical damage (always crits).",
    terms=(FROSTFANG_WOLVERINE_DMG,),
    clauses=(Clause(f"Deals +{int((_FROSTFANG_BONUS_MULT - 1) * 100)}% to frozen or slowed targets."),),
    tags=("physical", "crit"),
)


@register_passive("champ_frostfang_wolverine.passive")
def frostfang_wolverine_passive(owner: Any) -> EffectBundle:
    # Frenzy: gains AS after each kill
    def hook(ctx: Any, event: Any) -> None:
        if event.killer is not owner:
            return
        ctx.apply_modifier(owner, Modifier(
            "attack_speed", "add", 20.0, Lifetime.COMBAT,
            "passive:champ_frostfang_wolverine.frenzy",
        ))

    return EffectBundle(hooks=[
        Hook("on_kill", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_frostfang_wolverine.passive"] = AbilityMeta(
    name="Frenzy", kind="passive",
    blurb="Each kill grants +20 Attack Speed for the rest of the battle.",
    tags=("buff", "scaling"),
)


# --- Frostquill Porcupine (T9, ADC-STR Hunter) ---
# Passive: autos slow; bonus damage vs slowed
FROSTQUILL_PORCUPINE_BONUS = ScalingTerm("bonus", 0.0, "strength*0.25")


@register_passive("champ_frostquill_porcupine.passive")
def frostquill_porcupine_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        ctx.apply_status(event.target, "slow", duration_ticks=150, stacks=1, source_id=owner.id)
        if event.target.has_status("slow"):
            ctx.deal_damage(owner, event.target, FROSTQUILL_PORCUPINE_BONUS.eval(owner),
                          SourceTag.BASIC_ATTACK, damage_type="physical")

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_frostquill_porcupine.passive"] = AbilityMeta(
    name="Chill Quills", kind="passive",
    blurb="Auto-attacks slow for 1.5s and deal {bonus} bonus physical damage to slowed targets.",
    terms=(FROSTQUILL_PORCUPINE_BONUS,), tags=("physical", "slow"),
)


FROSTQUILL_PORCUPINE_DMG = ScalingTerm("damage", 70.0, "strength*1.8")
_PORCUPINE_SPLASH_MULT = 0.5


@register_active("champ_frostquill_porcupine.active")
def frostquill_porcupine_active(ctx: Any, actor: Any, targets: list) -> None:
    # Quill volley: STR damage to primary + 2 nearby, all slowed
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = FROSTQUILL_PORCUPINE_DMG.eval(actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    ctx.apply_status(target, "slow", duration_ticks=300, stacks=2, source_id=actor.id)
    hit_count = 0
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor) and hit_count < 2:
            ctx.deal_damage(actor, n, amount * _PORCUPINE_SPLASH_MULT, SourceTag.ABILITY,
                            damage_type="physical")
            ctx.apply_status(n, "slow", duration_ticks=300, stacks=1, source_id=actor.id)
            hit_count += 1


ABILITY_META["champ_frostquill_porcupine.active"] = AbilityMeta(
    name="Quill Volley", kind="active",
    blurb="Loose quills at the primary target for {damage} physical damage.",
    terms=(FROSTQUILL_PORCUPINE_DMG,),
    clauses=(Clause(f"Up to 2 nearby enemies take {int(_PORCUPINE_SPLASH_MULT * 100)}% splash; all hit are slowed."),),
    tags=("physical", "aoe", "slow"),
)


# --- Borealis (T10, Primordial) ---
# Passive: freeze nearest enemy every 600 ticks
@register_passive("champ_borealis.passive")
def borealis_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 600:
            state["last_tick"] = ctx.current_tick
            from src.game.targeting import _closest_enemy
            enemies = list(ctx.enemies_of(owner))
            if enemies:
                nearest = _closest_enemy(owner, enemies)
                if nearest:
                    ctx.apply_status(nearest, "frozen", duration_ticks=200, source_id=owner.id)

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_borealis.passive"] = AbilityMeta(
    name="Deep Freeze", kind="passive",
    blurb="Every 6s, freezes the nearest enemy for 2s.",
    tags=("freeze", "control"),
)


# Active: blizzard — AOE INT+STR damage
BOREALIS_DMG = ScalingTerm("damage", 80.0, "strength*1.2+intelligence*1.2")


@register_active("champ_borealis.active")
def borealis_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = BOREALIS_DMG.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount, SourceTag.ABILITY)
        ctx.apply_status(t, "slow", duration_ticks=300, stacks=2, source_id=actor.id)


ABILITY_META["champ_borealis.active"] = AbilityMeta(
    name="Blizzard", kind="active",
    blurb="Conjure a blizzard for {damage} magic damage to all enemies within 3 hexes.",
    terms=(BOREALIS_DMG,),
    clauses=(Clause("Applies 2 stacks of slow for 3s."),), tags=("magic", "aoe", "slow"),
)


# ===========================================================================
# CLOUDY — The Cragwild
# ===========================================================================


# --- Pebbleback Pangolin (T1, Tank) ---
# Passive: reduced damage while not moved (armor buff at start)
@register_passive("champ_pebbleback_pangolin.passive")
def pebbleback_pangolin_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("armor", "add", 15.0, Lifetime.COMBAT, "passive:champ_pebbleback_pangolin"),
    ])


ABILITY_META["champ_pebbleback_pangolin.passive"] = AbilityMeta(
    name="Stone Scales", kind="passive",
    blurb="Grants +15 Armor for the whole battle.",
    tags=("defense",),
)


@register_active("champ_pebbleback_pangolin.active")
def pebbleback_pangolin_active(ctx: Any, actor: Any, targets: list) -> None:
    # Curl up: gain armor briefly
    ctx.apply_modifier(actor, Modifier(
        "armor", "add", 25.0, Lifetime.TIMED,
        "ability:champ_pebbleback_pangolin",
        expires_at_tick=ctx.current_tick + 400,
    ))


ABILITY_META["champ_pebbleback_pangolin.active"] = AbilityMeta(
    name="Curl Up", kind="active",
    blurb="Curl into a ball, gaining +25 Armor for 4s.",
    tags=("defense", "buff"),
)


# --- Dusk Bat (T2, Trickster) ---
# Active: blind one enemy (reduce AS)
@register_active("champ_dusk_bat.active")
def dusk_bat_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.apply_modifier(target, Modifier(
        "attack_speed", "add", -30.0, Lifetime.TIMED,
        "ability:champ_dusk_bat.blind",
        expires_at_tick=ctx.current_tick + 400,
    ))


ABILITY_META["champ_dusk_bat.active"] = AbilityMeta(
    name="Blinding Screech", kind="active",
    blurb="Blind the primary target, cutting 30 Attack Speed for 4s.",
    tags=("debuff", "control"),
)


@register_passive("champ_dusk_bat.passive")
def dusk_bat_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("move_speed", "add", 10.0, Lifetime.COMBAT, "passive:champ_dusk_bat"),
    ])


ABILITY_META["champ_dusk_bat.passive"] = AbilityMeta(
    name="Nightwing", kind="passive",
    blurb="Grants +10 Move Speed for the whole battle.",
    tags=("buff",),
)


# --- Boulderhide Skink (T3, APC-STR Mage) ---
# Active: boulder rolls a line — STR damage
BOULDERHIDE_SKINK_DMG = ScalingTerm("damage", 60.0, "strength*1.8")
_SKINK_LINE_MULT = 0.5


@register_active("champ_boulderhide_skink.active")
def boulderhide_skink_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = BOULDERHIDE_SKINK_DMG.eval(actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    # Hit neighbors in line
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor):
            ctx.deal_damage(actor, n, amount * _SKINK_LINE_MULT, SourceTag.ABILITY,
                            damage_type="physical")
            break  # Only one extra target for line


ABILITY_META["champ_boulderhide_skink.active"] = AbilityMeta(
    name="Rolling Boulder", kind="active",
    blurb="Roll a boulder into the primary target for {damage} physical damage.",
    terms=(BOULDERHIDE_SKINK_DMG,),
    clauses=(Clause(f"One enemy in the line takes {int(_SKINK_LINE_MULT * 100)}% damage."),),
    tags=("physical", "aoe"),
)


@register_passive("champ_boulderhide_skink.passive")
def boulderhide_skink_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("armor", "add", 5.0, Lifetime.COMBAT, "passive:champ_boulderhide_skink"),
    ])


ABILITY_META["champ_boulderhide_skink.passive"] = AbilityMeta(
    name="Pebbled Hide", kind="passive",
    blurb="Grants +5 Armor for the whole battle.",
    tags=("defense",),
)


# --- Geode Beetle (T4, SUP-Shield) ---
# Active: ally shield (large armor buff that blocks next big hit)
@register_active("champ_geode_beetle.active")
def geode_beetle_active(ctx: Any, actor: Any, targets: list) -> None:
    ally = lowest_hp_ally(actor, ctx)
    if not ally:
        return
    ctx.apply_modifier(ally, Modifier(
        "armor", "add", 80.0, Lifetime.TIMED,
        "ability:champ_geode_beetle.shield",
        expires_at_tick=ctx.current_tick + 400,
    ))
    ctx.apply_modifier(ally, Modifier(
        "resistance", "add", 40.0, Lifetime.TIMED,
        "ability:champ_geode_beetle.shield",
        expires_at_tick=ctx.current_tick + 400,
    ))


ABILITY_META["champ_geode_beetle.active"] = AbilityMeta(
    name="Geode Ward", kind="active",
    blurb="Shield the lowest-HP ally with +80 Armor and +40 Resistance for 4s.",
    tags=("defense", "buff"),
)


@register_passive("champ_geode_beetle.passive")
def geode_beetle_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("armor", "add", 10.0, Lifetime.COMBAT, "passive:champ_geode_beetle"),
    ])


ABILITY_META["champ_geode_beetle.passive"] = AbilityMeta(
    name="Crystal Carapace", kind="passive",
    blurb="Grants +10 Armor for the whole battle.",
    tags=("defense",),
)


# --- Duskstep Marten (T5, INT Assassin) ---
# Passive: shadow-step — every 4th auto, teleport behind target for bonus damage
DUSKSTEP_MARTEN_BONUS = ScalingTerm("bonus", 0.0, "intelligence*0.6")


@register_passive("champ_duskstep_marten.passive")
def duskstep_marten_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 4 == 0:
            ctx.deal_damage(owner, event.target, DUSKSTEP_MARTEN_BONUS.eval(owner), SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_duskstep_marten.passive"] = AbilityMeta(
    name="Shadow Step", kind="passive",
    blurb="Every 4th auto-attack blinks behind the target for {bonus} bonus magic damage.",
    terms=(DUSKSTEP_MARTEN_BONUS,), tags=("magic",),
)


DUSKSTEP_MARTEN_DMG = ScalingTerm("damage", 70.0, "intelligence*2.0")


@register_active("champ_duskstep_marten.active")
def duskstep_marten_active(ctx: Any, actor: Any, targets: list) -> None:
    # Shadow strike: INT burst
    target = lowest_hp_enemy(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, DUSKSTEP_MARTEN_DMG.eval(actor), SourceTag.ABILITY)


ABILITY_META["champ_duskstep_marten.active"] = AbilityMeta(
    name="Shadow Strike", kind="active",
    blurb="Strike the lowest-HP enemy for {damage} magic damage.",
    terms=(DUSKSTEP_MARTEN_DMG,), tags=("magic",),
)


# --- Granite Gorilla (T6, Tank-INT) ---
# Passive: returns a share of damage taken as INT-magic damage.
_GORILLA_REFLECT_PCT = 0.15


@register_passive("champ_granite_gorilla.passive")
def granite_gorilla_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.target is not owner:
            return
        if event.tag == SourceTag.REFLECT.value:
            return  # never reflect a reflection — prevents mutual-reflect recursion
        if not hasattr(event, "attacker") or event.attacker is None:
            return
        if not event.attacker.alive:
            return
        reflect_amount = event.amount * _GORILLA_REFLECT_PCT
        if reflect_amount > 0:
            ctx.deal_damage(owner, event.attacker, reflect_amount, SourceTag.REFLECT)

    return EffectBundle(hooks=[
        Hook("on_damage_taken", hook, scope=HookScope.PER_HIT, priority=-10),
    ])


ABILITY_META["champ_granite_gorilla.passive"] = AbilityMeta(
    name="Stone Recoil", kind="passive",
    blurb="Returns a share of damage taken back to the attacker as magic damage.",
    clauses=(Clause(f"Reflects {int(_GORILLA_REFLECT_PCT * 100)}% of damage taken."),),
    tags=("magic", "reflect"),
)


GRANITE_GORILLA_DMG = ScalingTerm("damage", 70.0, "intelligence*1.8")


@register_active("champ_granite_gorilla.active")
def granite_gorilla_active(ctx: Any, actor: Any, targets: list) -> None:
    # Ground slam: INT damage AOE + stun
    amount = GRANITE_GORILLA_DMG.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 1, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount, SourceTag.ABILITY)
        ctx.apply_status(t, "stun", duration_ticks=100, source_id=actor.id)


ABILITY_META["champ_granite_gorilla.active"] = AbilityMeta(
    name="Ground Slam", kind="active",
    blurb="Slam the ground for {damage} magic damage to all adjacent enemies.",
    terms=(GRANITE_GORILLA_DMG,),
    clauses=(Clause("Stuns struck enemies for 1s."),), tags=("magic", "aoe", "stun"),
)


# --- Eclipse Jaguar (T7, Hybrid Stalker) ---
# Passive: autos alternate STR and INT damage
ECLIPSE_JAGUAR_INT_BONUS = ScalingTerm("magic", 0.0, "intelligence*0.4")
ECLIPSE_JAGUAR_STR_BONUS = ScalingTerm("physical", 0.0, "strength*0.3")


@register_passive("champ_eclipse_jaguar.passive")
def eclipse_jaguar_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 2 == 0:
            # INT bonus on even hits
            ctx.deal_damage(owner, event.target, ECLIPSE_JAGUAR_INT_BONUS.eval(owner),
                            SourceTag.BASIC_ATTACK)
        else:
            # STR bonus on odd hits
            ctx.deal_damage(owner, event.target, ECLIPSE_JAGUAR_STR_BONUS.eval(owner),
                            SourceTag.BASIC_ATTACK, damage_type="physical")

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_eclipse_jaguar.passive"] = AbilityMeta(
    name="Eclipse Rhythm", kind="passive",
    blurb="Auto-attacks alternate bonus damage: {physical} physical on odd hits, {magic} magic on even hits.",
    terms=(ECLIPSE_JAGUAR_STR_BONUS, ECLIPSE_JAGUAR_INT_BONUS), tags=("physical", "magic"),
)


# Active: twin strike — both STR and INT damage
ECLIPSE_JAGUAR_STR_DMG = ScalingTerm("physical", 50.0, "strength*1.5")
ECLIPSE_JAGUAR_INT_DMG = ScalingTerm("magic", 50.0, "intelligence*1.5")


@register_active("champ_eclipse_jaguar.active")
def eclipse_jaguar_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, ECLIPSE_JAGUAR_STR_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")
    ctx.deal_damage(actor, target, ECLIPSE_JAGUAR_INT_DMG.eval(actor), SourceTag.ABILITY)


ABILITY_META["champ_eclipse_jaguar.active"] = AbilityMeta(
    name="Twin Strike", kind="active",
    blurb="Strike the primary target twice: {physical} physical and {magic} magic damage.",
    terms=(ECLIPSE_JAGUAR_STR_DMG, ECLIPSE_JAGUAR_INT_DMG), tags=("physical", "magic"),
)


# --- Nightglass Mantis (T8, INT Assassin) ---
# Active: vanish → INT execute (bonus vs low HP)
NIGHTGLASS_MANTIS_DMG = ScalingTerm("damage", 100.0, "intelligence*2.5")
_MANTIS_EXECUTE_MULT = 1.6


@register_active("champ_nightglass_mantis.active")
def nightglass_mantis_active(ctx: Any, actor: Any, targets: list) -> None:
    target = lowest_hp_enemy(actor, ctx)
    if not target:
        return
    amount = NIGHTGLASS_MANTIS_DMG.eval(actor)
    if target.hp_pct < 0.3:
        amount *= _MANTIS_EXECUTE_MULT
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)


ABILITY_META["champ_nightglass_mantis.active"] = AbilityMeta(
    name="Vanishing Execute", kind="active",
    blurb="Vanish and strike the lowest-HP enemy for {damage} magic damage.",
    terms=(NIGHTGLASS_MANTIS_DMG,),
    clauses=(Clause(f"Deals +{int((_MANTIS_EXECUTE_MULT - 1) * 100)}% to targets below 30% HP."),),
    tags=("magic", "execute"),
)


NIGHTGLASS_MANTIS_BONUS = ScalingTerm("bonus", 0.0, "intelligence*0.8")


@register_passive("champ_nightglass_mantis.passive")
def nightglass_mantis_passive(owner: Any) -> EffectBundle:
    # Bonus damage from stealth (first hit after being idle is amplified)
    state = {"first_hit": True}

    def on_attack(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        if state["first_hit"]:
            state["first_hit"] = False
            ctx.deal_damage(owner, event.target, NIGHTGLASS_MANTIS_BONUS.eval(owner), SourceTag.ABILITY)

    def on_cast(ctx: Any, event: Any) -> None:
        if event.caster is not owner:
            return
        state["first_hit"] = True  # Reset after each cast

    return EffectBundle(hooks=[
        Hook("on_attack_landed", on_attack, scope=HookScope.PER_HIT),
        Hook("on_cast_complete", on_cast, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_nightglass_mantis.passive"] = AbilityMeta(
    name="Ambush", kind="passive",
    blurb="The first auto-attack after each cast deals {bonus} bonus magic damage.",
    terms=(NIGHTGLASS_MANTIS_BONUS,), tags=("magic",),
)


# --- Cliffeyrie Eagle (T9, ADC-STR Hunter) ---
# Passive: first auto vastly amplified
CLIFFEYRIE_EAGLE_BONUS = ScalingTerm("bonus", 0.0, "strength*1.5")


@register_passive("champ_cliffeyrie_eagle.passive")
def cliffeyrie_eagle_passive(owner: Any) -> EffectBundle:
    state = {"first_hit": True}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        if state["first_hit"]:
            state["first_hit"] = False
            ctx.deal_damage(owner, event.target, CLIFFEYRIE_EAGLE_BONUS.eval(owner),
                          SourceTag.BASIC_ATTACK, damage_type="physical")

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_cliffeyrie_eagle.passive"] = AbilityMeta(
    name="Talon Dive", kind="passive",
    blurb="The first auto-attack deals {bonus} bonus physical damage.",
    terms=(CLIFFEYRIE_EAGLE_BONUS,), tags=("physical",),
)


CLIFFEYRIE_EAGLE_DMG = ScalingTerm("damage", 80.0, "strength*2.2")


@register_active("champ_cliffeyrie_eagle.active")
def cliffeyrie_eagle_active(ctx: Any, actor: Any, targets: list) -> None:
    # Diving talon: STR damage + reset first-hit passive
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, CLIFFEYRIE_EAGLE_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")


ABILITY_META["champ_cliffeyrie_eagle.active"] = AbilityMeta(
    name="Diving Talon", kind="active",
    blurb="Dive the primary target for {damage} physical damage.",
    terms=(CLIFFEYRIE_EAGLE_DMG,), tags=("physical",),
)


# --- Umbra (T10, Primordial — Cloudy) ---
# Passive: every 5th auto triggers a free cast
UMBRA_CLONE_STRIKE = ScalingTerm("bonus", 0.0, "intelligence*1.5")


@register_passive("champ_umbra.passive")
def umbra_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 5 == 0:
            # Free cast: deal INT damage as shadow clone strike
            ctx.deal_damage(owner, event.target, UMBRA_CLONE_STRIKE.eval(owner), SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_umbra.passive"] = AbilityMeta(
    name="Shadow Echo", kind="passive",
    blurb="Every 5th auto-attack unleashes a clone strike for {bonus} magic damage.",
    terms=(UMBRA_CLONE_STRIKE,), tags=("magic",),
)


ABILITY_META["champ_umbra.active"] = AbilityMeta(
    name="Shadow Clones", kind="active",
    blurb="Summon 2 shadow clones that fight at your side for 12s.",
    clauses=(Clause("Each clone inherits 40% of your Strength/Intelligence and 30% of max HP, Armor and Resistance."),),
    tags=("summon",),
)


# Clone statline: Magnitude fractions of the summoner + flat literals (SummonSpec, V.46).
_UMBRA_CLONE = SummonSpec(stats={
    "max_hp": PctResource("max_hp", 0.3),
    "strength": ScalingTerm("strength", 0.0, "strength*0.4"),
    "intelligence": ScalingTerm("intelligence", 0.0, "intelligence*0.4"),
    "armor": ScalingTerm("armor", 0.0, "armor*0.3"),
    "resistance": ScalingTerm("resistance", 0.0, "resistance*0.3"),
    "attack_speed": ScalingTerm("attack_speed", 0.0, "attack_speed*1.0"),
    "mana_regen": 0,
    "move_speed": ScalingTerm("move_speed", 0.0, "move_speed*1.0"),
    "threat": 20,
    "attack_range": ScalingTerm("attack_range", 0.0, "attack_range*1.0"),
    "ability_cost": 999_999,
    "crit_chance": 0.0,
    "penetration": 0,
    "penetration_pct": 0.0,
})


# Active: summon shadow clones (spawn real flagged pieces)
@register_active("champ_umbra.active")
def umbra_active(ctx: Any, actor: Any, targets: list) -> None:
    from src.game.piece import Piece, ActiveSlot
    # Spawn 2 shadow clones as real Piece objects with summon flag
    for i in range(2):
        clone = Piece(
            id=f"{actor.id}_clone_{ctx.current_tick}_{i}",
            base_stats=_UMBRA_CLONE.eval(actor),
            affinity=actor.affinity,
            is_enemy=actor.is_enemy,
            summon=True,
            summon_owner_id=actor.id,
            summon_expires_tick=ctx.current_tick + 1200,
        )
        clone.hp = clone.base_stats["max_hp"]
        clone.max_hp = clone.base_stats["max_hp"]
        offset_q = actor.position_q + (1 if i == 0 else -1)
        ctx.spawn(clone, offset_q, actor.position_r)


# ===========================================================================
# MIST — The Hazewild
# ===========================================================================


# --- Lostlight Wisp (T1, SUP-Heal) ---
# Active: HoT wisp heal on ally
LOSTLIGHT_WISP_HEAL = ScalingTerm("heal", 35.0, "intelligence*2.0")


@register_active("champ_lostlight_wisp.active")
def lostlight_wisp_active(ctx: Any, actor: Any, targets: list) -> None:
    ally = lowest_hp_ally(actor, ctx)
    if not ally:
        return
    ctx.heal(actor, ally, LOSTLIGHT_WISP_HEAL.eval(actor))


ABILITY_META["champ_lostlight_wisp.active"] = AbilityMeta(
    name="Wisplight", kind="active",
    blurb="Mend the lowest-HP ally for {heal}.",
    terms=(LOSTLIGHT_WISP_HEAL,), tags=("heal",),
)


LOSTLIGHT_WISP_HOT = ScalingTerm("heal", 0.0, "intelligence*0.3")


@register_passive("champ_lostlight_wisp.passive")
def lostlight_wisp_passive(owner: Any) -> EffectBundle:
    # Periodic heal to lowest ally every 200 ticks
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 200:
            state["last_tick"] = ctx.current_tick
            ally = lowest_hp_ally(owner, ctx)
            if ally:
                ctx.heal(owner, ally, LOSTLIGHT_WISP_HOT.eval(owner))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_lostlight_wisp.passive"] = AbilityMeta(
    name="Guiding Glow", kind="passive",
    blurb="Every 2s, heal the lowest-HP ally for {heal}.",
    terms=(LOSTLIGHT_WISP_HOT,), tags=("heal",),
)


# --- Will-o-Fawn (T2, INT Mystic) ---
# Active: conjure ally-auto double (grant ally bonus attack)
@register_active("champ_will_o_fawn.active")
def will_o_fawn_active(ctx: Any, actor: Any, targets: list) -> None:
    # Grant an ally a temporary attack speed buff (simulates double attack)
    allies = [a for a in ctx.allies_of(actor) if a is not actor]
    if not allies:
        return
    ally = min(allies, key=lambda a: (a.hp, a.id))
    ctx.apply_modifier(ally, Modifier(
        "attack_speed", "add", 40.0, Lifetime.TIMED,
        "ability:champ_will_o_fawn",
        expires_at_tick=ctx.current_tick + 300,
    ))


ABILITY_META["champ_will_o_fawn.active"] = AbilityMeta(
    name="Conjure Double", kind="active",
    blurb="Grant a wounded ally +40 Attack Speed for 3s.",
    tags=("buff",),
)


@register_passive("champ_will_o_fawn.passive")
def will_o_fawn_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("intelligence", "add", 8.0, Lifetime.COMBAT, "passive:champ_will_o_fawn"),
    ])


ABILITY_META["champ_will_o_fawn.passive"] = AbilityMeta(
    name="Wandering Light", kind="passive",
    blurb="Grants +8 Intelligence for the whole battle.",
    tags=("buff",),
)


# --- Phantom Lynx (T3, APC-INT Assassin) ---
# Cast: phases through target for INT damage, with penetration.
PHANTOM_LYNX_DMG = ScalingTerm("damage", 90.0, "intelligence*2.2")


@register_active("champ_phantom_lynx.active")
def phantom_lynx_active(ctx: Any, actor: Any, targets: list) -> None:
    target = lowest_hp_enemy(actor, ctx)
    if not target:
        return
    # Use pen_pct parameter for resistance ignore
    ctx.deal_damage(actor, target, PHANTOM_LYNX_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="magical")
    # Apply temporary pen boost
    ctx.apply_modifier(actor, Modifier(
        "penetration_pct", "add", 0.3, Lifetime.TIMED,
        "ability:champ_phantom_lynx.pen",
        expires_at_tick=ctx.current_tick + 200,
    ))


ABILITY_META["champ_phantom_lynx.active"] = AbilityMeta(
    name="Phase Strike", kind="active",
    blurb="Phase through the lowest-HP enemy for {damage} magic damage.",
    terms=(PHANTOM_LYNX_DMG,),
    clauses=(Clause("Gain +30% magic penetration for 2s."),), tags=("magic", "penetration"),
)


@register_passive("champ_phantom_lynx.passive")
def phantom_lynx_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("penetration_pct", "add", 0.15, Lifetime.COMBAT, "passive:champ_phantom_lynx"),
    ])


ABILITY_META["champ_phantom_lynx.passive"] = AbilityMeta(
    name="Ghostpierce", kind="passive",
    blurb="Grants +15% magic penetration for the whole battle.",
    tags=("penetration",),
)


# --- Hollow Elk (T4, Tank-Channeler) ---
# Passive: convert incoming damage to mana
_HOLLOW_ELK_MANA_PCT = 0.10


@register_passive("champ_hollow_elk.passive")
def hollow_elk_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.target is not owner:
            return
        # Convert 10% of damage taken to mana
        ctx.gain_mana(owner, event.amount * _HOLLOW_ELK_MANA_PCT)

    return EffectBundle(hooks=[
        Hook("on_damage_taken", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_hollow_elk.passive"] = AbilityMeta(
    name="Spirit Vessel", kind="passive",
    blurb="Converts a share of damage taken into mana.",
    clauses=(Clause(f"Gains mana equal to {int(_HOLLOW_ELK_MANA_PCT * 100)}% of damage taken."),),
    tags=("mana",),
)


HOLLOW_ELK_DMG = ScalingTerm("damage", 60.0, "intelligence*1.8")
_HOLLOW_ELK_HEAL_SHARE = 0.3


@register_active("champ_hollow_elk.active")
def hollow_elk_active(ctx: Any, actor: Any, targets: list) -> None:
    # Spirit drain: INT damage + self heal
    target = primary_target(actor, ctx)
    if not target:
        return
    dealt = ctx.deal_damage(actor, target, HOLLOW_ELK_DMG.eval(actor), SourceTag.ABILITY)
    ctx.heal(actor, actor, dealt * _HOLLOW_ELK_HEAL_SHARE)


ABILITY_META["champ_hollow_elk.active"] = AbilityMeta(
    name="Spirit Drain", kind="active",
    blurb="Drain the primary target for {damage} magic damage.",
    terms=(HOLLOW_ELK_DMG,),
    clauses=(Clause(f"Heals you for {int(_HOLLOW_ELK_HEAL_SHARE * 100)}% of the damage dealt."),),
    tags=("magic", "heal"),
)


# --- Fogveil Moth (T5, Trickster) ---
# Active: shroud enemy (reduce their AS — simulates miss chance)
FOGVEIL_MOTH_DMG = ScalingTerm("damage", 30.0, "intelligence*1.2")


@register_active("champ_fogveil_moth.active")
def fogveil_moth_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.apply_modifier(target, Modifier(
        "attack_speed", "add", -35.0, Lifetime.TIMED,
        "ability:champ_fogveil_moth.shroud",
        expires_at_tick=ctx.current_tick + 500,
    ))
    # Small INT damage
    ctx.deal_damage(actor, target, FOGVEIL_MOTH_DMG.eval(actor), SourceTag.ABILITY)


ABILITY_META["champ_fogveil_moth.active"] = AbilityMeta(
    name="Shroud", kind="active",
    blurb="Shroud the primary target for {damage} magic damage and cut 35 Attack Speed for 5s.",
    terms=(FOGVEIL_MOTH_DMG,), tags=("magic", "debuff"),
)


@register_passive("champ_fogveil_moth.passive")
def fogveil_moth_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("resistance", "add", 10.0, Lifetime.COMBAT, "passive:champ_fogveil_moth"),
    ])


ABILITY_META["champ_fogveil_moth.passive"] = AbilityMeta(
    name="Veiled Form", kind="passive",
    blurb="Grants +10 Resistance for the whole battle.",
    tags=("defense",),
)


# --- Wraithorn Stag (T6, STR Bruiser) ---
# Active: spectral gore — STR burst
WRAITHORN_STAG_DMG = ScalingTerm("damage", 80.0, "strength*2.2")


@register_active("champ_wraithorn_stag.active")
def wraithorn_stag_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, WRAITHORN_STAG_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")


ABILITY_META["champ_wraithorn_stag.active"] = AbilityMeta(
    name="Spectral Gore", kind="active",
    blurb="Gore the primary target for {damage} physical damage.",
    terms=(WRAITHORN_STAG_DMG,), tags=("physical",),
)


@register_passive("champ_wraithorn_stag.passive")
def wraithorn_stag_passive(owner: Any) -> EffectBundle:
    # Phase-move: gains move speed after attacking
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        ctx.apply_modifier(owner, Modifier(
            "move_speed", "add", 25.0, Lifetime.TIMED,
            "passive:champ_wraithorn_stag",
            expires_at_tick=ctx.current_tick + 300,
        ))

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_wraithorn_stag.passive"] = AbilityMeta(
    name="Phase Drift", kind="passive",
    blurb="Auto-attacks grant +25 Move Speed for 3s.",
    tags=("buff",),
)


# --- Marshghast Boar (T7, Hybrid Bruiser) ---
# Passive: below 50% HP, gain massive resistance and mana regen
@register_passive("champ_marshghast_boar.passive")
def marshghast_boar_passive(owner: Any) -> EffectBundle:
    state = {"activated": False}

    def hook(ctx: Any, event: Any) -> None:
        if event.target is not owner:
            return
        if not state["activated"] and owner.hp_pct < 0.5:
            state["activated"] = True
            ctx.apply_modifier(owner, Modifier(
                "resistance", "add", 60.0, Lifetime.COMBAT,
                "passive:champ_marshghast_boar.ghost",
            ))
            ctx.apply_modifier(owner, Modifier(
                "armor", "add", 40.0, Lifetime.COMBAT,
                "passive:champ_marshghast_boar.ghost",
            ))
            ctx.gain_mana(owner, owner.actives[0].cost * 0.5 if owner.actives else 0)

    return EffectBundle(hooks=[
        Hook("on_damage_taken", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_marshghast_boar.passive"] = AbilityMeta(
    name="Ghostform", kind="passive",
    blurb="The first time you drop below 50% HP, turn spectral for the rest of the battle.",
    clauses=(Clause("Gain +60 Resistance, +40 Armor, and refund 50% of your ability's mana cost."),),
    tags=("defense", "buff"),
)


MARSHGHAST_BOAR_DMG = ScalingTerm("damage", 60.0, "strength*1.2+intelligence*1.2")


@register_active("champ_marshghast_boar.active")
def marshghast_boar_active(ctx: Any, actor: Any, targets: list) -> None:
    # Ghost charge: hybrid damage
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, MARSHGHAST_BOAR_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")


ABILITY_META["champ_marshghast_boar.active"] = AbilityMeta(
    name="Ghost Charge", kind="active",
    blurb="Charge the primary target for {damage} hybrid damage.",
    terms=(MARSHGHAST_BOAR_DMG,), tags=("hybrid",),
)


# --- Veilfang Wolf (T8, INT Skirmisher) ---
# Passive: autos deal bonus INT + shred resistance
VEILFANG_WOLF_BONUS = ScalingTerm("bonus", 0.0, "intelligence*0.35")


@register_passive("champ_veilfang_wolf.passive")
def veilfang_wolf_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        ctx.deal_damage(owner, event.target, VEILFANG_WOLF_BONUS.eval(owner), SourceTag.BASIC_ATTACK)
        # Resistance shred
        ctx.apply_modifier(event.target, Modifier(
            "resistance", "add", -8.0, Lifetime.TIMED,
            "passive:champ_veilfang_wolf.shred",
            expires_at_tick=ctx.current_tick + 400,
        ))

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_veilfang_wolf.passive"] = AbilityMeta(
    name="Rending Fangs", kind="passive",
    blurb="Auto-attacks deal {bonus} bonus magic damage and shred 8 Resistance for 4s.",
    terms=(VEILFANG_WOLF_BONUS,), tags=("magic", "debuff"),
)


VEILFANG_WOLF_DMG = ScalingTerm("damage", 80.0, "intelligence*2.2")


@register_active("champ_veilfang_wolf.active")
def veilfang_wolf_active(ctx: Any, actor: Any, targets: list) -> None:
    # Fang rush: INT damage
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, VEILFANG_WOLF_DMG.eval(actor), SourceTag.ABILITY)


ABILITY_META["champ_veilfang_wolf.active"] = AbilityMeta(
    name="Fang Rush", kind="active",
    blurb="Rush the primary target for {damage} magic damage.",
    terms=(VEILFANG_WOLF_DMG,), tags=("magic",),
)


# --- Spectral Heron (T9, INT Hunter) ---
# Passive: autos pierce (hit target + 1 behind)
SPECTRAL_HERON_PIERCE = ScalingTerm("bonus", 0.0, "intelligence*0.3")


@register_passive("champ_spectral_heron.passive")
def spectral_heron_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        # Pierce: hit one enemy behind target
        for n in neighbors_of(event.target, ctx):
            if ctx.is_enemy(n, owner) and n is not event.target:
                ctx.deal_damage(owner, n, SPECTRAL_HERON_PIERCE.eval(owner), SourceTag.BASIC_ATTACK)
                break

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_spectral_heron.passive"] = AbilityMeta(
    name="Piercing Shot", kind="passive",
    blurb="Auto-attacks pierce to one enemy behind the target for {bonus} magic damage.",
    terms=(SPECTRAL_HERON_PIERCE,), tags=("magic",),
)


SPECTRAL_HERON_DMG = ScalingTerm("damage", 80.0, "intelligence*2.0")
_SPECTRAL_HERON_LINE_MULT = 0.6


@register_active("champ_spectral_heron.active")
def spectral_heron_active(ctx: Any, actor: Any, targets: list) -> None:
    # Spectral beam: line damage
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = SPECTRAL_HERON_DMG.eval(actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor):
            ctx.deal_damage(actor, n, amount * _SPECTRAL_HERON_LINE_MULT, SourceTag.ABILITY)


ABILITY_META["champ_spectral_heron.active"] = AbilityMeta(
    name="Spectral Beam", kind="active",
    blurb="Fire a beam through the primary target for {damage} magic damage.",
    terms=(SPECTRAL_HERON_DMG,),
    clauses=(Clause(f"Enemies in the line take {int(_SPECTRAL_HERON_LINE_MULT * 100)}% damage."),),
    tags=("magic", "aoe"),
)


# --- Mournhollow (T10, Primordial — Mist) ---
# Passive: every other action is a free auto attack
@register_passive("champ_mournhollow.passive")
def mournhollow_passive(owner: Any) -> EffectBundle:
    state = {"cast_count": 0}

    def on_cast(ctx: Any, event: Any) -> None:
        if event.caster is not owner:
            return
        state["cast_count"] += 1
        if state["cast_count"] % 2 == 0:
            # Free auto on cast target (or primary)
            target = primary_target(owner, ctx)
            if target and target.alive:
                ctx.trigger_basic_attack(owner, target, mult=1.0)

    return EffectBundle(hooks=[
        Hook("on_cast_complete", on_cast, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_mournhollow.passive"] = AbilityMeta(
    name="Echoing Dead", kind="passive",
    blurb="Every 2nd cast triggers a free auto-attack on the primary target.",
    tags=("tempo",),
)


# Active: board fear — AOE fear enemies
MOURNHOLLOW_DMG = ScalingTerm("damage", 80.0, "intelligence*1.8")
_MOURNHOLLOW_AOE_MULT = 0.6


@register_active("champ_mournhollow.active")
def mournhollow_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = MOURNHOLLOW_DMG.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * _MOURNHOLLOW_AOE_MULT, SourceTag.ABILITY)
        ctx.apply_status(t, "fear", duration_ticks=200, source_id=actor.id)


ABILITY_META["champ_mournhollow.active"] = AbilityMeta(
    name="Board Fear", kind="active",
    blurb=f"Terrify all enemies within 3 hexes, each taking {int(_MOURNHOLLOW_AOE_MULT * 100)}% of {{damage}} magic damage.",
    terms=(MOURNHOLLOW_DMG,),
    clauses=(Clause("Feared for 2s."),), tags=("magic", "aoe", "fear"),
)


# ===========================================================================
# THUNDER — The Stormwild
# ===========================================================================


# --- Sparkfly (T1, Trickster) ---
# Active: brief stun one enemy
SPARKFLY_DMG = ScalingTerm("damage", 20.0, "intelligence*1.0")


@register_active("champ_sparkfly.active")
def sparkfly_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, SPARKFLY_DMG.eval(actor), SourceTag.ABILITY)
    ctx.apply_status(target, "stun", duration_ticks=150, source_id=actor.id)


ABILITY_META["champ_sparkfly.active"] = AbilityMeta(
    name="Static Jolt", kind="active",
    blurb="Jolt the primary target for {damage} magic damage.",
    terms=(SPARKFLY_DMG,),
    clauses=(Clause("Stuns for 1.5s."),), tags=("magic", "stun"),
)


@register_passive("champ_sparkfly.passive")
def sparkfly_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("move_speed", "add", 10.0, Lifetime.COMBAT, "passive:champ_sparkfly"),
    ])


ABILITY_META["champ_sparkfly.passive"] = AbilityMeta(
    name="Crackle", kind="passive",
    blurb="Grants +10 Move Speed for the whole battle.",
    tags=("buff",),
)


# --- Thunderhoof Colt (T2, ADC-STR Skirmisher) ---
# Passive: stacking AS when auto attacked
@register_passive("champ_thunderhoof_colt.passive")
def thunderhoof_colt_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.target is not owner:
            return
        ctx.apply_modifier(owner, Modifier(
            "attack_speed", "add", 8.0, Lifetime.TIMED,
            "passive:champ_thunderhoof_colt.stack",
            expires_at_tick=ctx.current_tick + 600,
        ))

    return EffectBundle(hooks=[
        Hook("on_damage_taken", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_thunderhoof_colt.passive"] = AbilityMeta(
    name="Galvanize", kind="passive",
    blurb="Each hit taken grants +8 Attack Speed for 6s, stacking.",
    tags=("buff",),
)


THUNDERHOOF_COLT_DMG = ScalingTerm("damage", 45.0, "strength*1.6")


@register_active("champ_thunderhoof_colt.active")
def thunderhoof_colt_active(ctx: Any, actor: Any, targets: list) -> None:
    # Thunder charge: STR damage
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, THUNDERHOOF_COLT_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")


ABILITY_META["champ_thunderhoof_colt.active"] = AbilityMeta(
    name="Thunder Charge", kind="active",
    blurb="Charge the primary target for {damage} physical damage.",
    terms=(THUNDERHOOF_COLT_DMG,), tags=("physical",),
)


# --- Voltscale Mamba (T3, ADC-STR Stalker) ---
# Active: dash + electric trail damage
VOLTSCALE_MAMBA_DMG = ScalingTerm("damage", 55.0, "strength*1.8")


@register_active("champ_voltscale_mamba.active")
def voltscale_mamba_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, VOLTSCALE_MAMBA_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")
    # Electric trail: apply burn to target (represents trail damage)
    ctx.apply_status(target, "burn", duration_ticks=200, source_id=actor.id)


ABILITY_META["champ_voltscale_mamba.active"] = AbilityMeta(
    name="Electric Dash", kind="active",
    blurb="Dash through the primary target for {damage} physical damage.",
    terms=(VOLTSCALE_MAMBA_DMG,),
    clauses=(Clause("Leaves a trail that burns for 2s."),), tags=("physical", "burn"),
)


@register_passive("champ_voltscale_mamba.passive")
def voltscale_mamba_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("move_speed", "add", 15.0, Lifetime.COMBAT, "passive:champ_voltscale_mamba"),
    ])


ABILITY_META["champ_voltscale_mamba.passive"] = AbilityMeta(
    name="Live Wire", kind="passive",
    blurb="Grants +15 Move Speed for the whole battle.",
    tags=("buff",),
)


# --- Coppercrest Stork (T4, SUP-Shield) ---
# Active: ally shield that reflects damage
@register_active("champ_coppercrest_stork.active")
def coppercrest_stork_active(ctx: Any, actor: Any, targets: list) -> None:
    ally = lowest_hp_ally(actor, ctx)
    if not ally:
        return
    # Shield as armor buff
    ctx.apply_modifier(ally, Modifier(
        "armor", "add", 50.0, Lifetime.TIMED,
        "ability:champ_coppercrest_stork.shield",
        expires_at_tick=ctx.current_tick + 400,
    ))


ABILITY_META["champ_coppercrest_stork.active"] = AbilityMeta(
    name="Copper Ward", kind="active",
    blurb="Shield the lowest-HP ally with +50 Armor for 4s.",
    tags=("defense", "buff"),
)


@register_passive("champ_coppercrest_stork.passive")
def coppercrest_stork_passive(owner: Any) -> EffectBundle:
    # Shield reflects: when shielded ally takes damage, reflect portion
    return EffectBundle(modifiers=[
        Modifier("resistance", "add", 10.0, Lifetime.COMBAT, "passive:champ_coppercrest_stork"),
    ])


ABILITY_META["champ_coppercrest_stork.passive"] = AbilityMeta(
    name="Conductive Plumage", kind="passive",
    blurb="Grants +10 Resistance for the whole battle.",
    tags=("defense",),
)


# --- Thunderhide Bison (T5, Tank) ---
# Passive: absorb first magic hit per 600 ticks (massive resistance buff periodically)
@register_passive("champ_thunderhide_bison.passive")
def thunderhide_bison_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 600:
            state["last_tick"] = ctx.current_tick
            ctx.apply_modifier(owner, Modifier(
                "resistance", "add", 50.0, Lifetime.TIMED,
                "passive:champ_thunderhide_bison.absorb",
                expires_at_tick=ctx.current_tick + 200,
            ))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_thunderhide_bison.passive"] = AbilityMeta(
    name="Storm Hide", kind="passive",
    blurb="Every 6s, gain +50 Resistance for 2s to absorb a magic burst.",
    tags=("defense",),
)


THUNDERHIDE_BISON_DMG = ScalingTerm("damage", 60.0, "strength*1.8")


@register_active("champ_thunderhide_bison.active")
def thunderhide_bison_active(ctx: Any, actor: Any, targets: list) -> None:
    # Thunder stomp: STR damage + stun
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, THUNDERHIDE_BISON_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")
    ctx.apply_status(target, "stun", duration_ticks=120, source_id=actor.id)


ABILITY_META["champ_thunderhide_bison.active"] = AbilityMeta(
    name="Thunder Stomp", kind="active",
    blurb="Stomp the primary target for {damage} physical damage.",
    terms=(THUNDERHIDE_BISON_DMG,),
    clauses=(Clause("Stuns for 1.2s."),), tags=("physical", "stun"),
)


# --- Tempest Eel (T6, APC-INT Mage) ---
# Cast: chain lightning, jumps to nearby enemies.
TEMPEST_EEL_DMG = ScalingTerm("damage", 100.0, "intelligence*2.0")
_TEMPEST_EEL_CHAIN1_MULT = 0.6
_TEMPEST_EEL_CHAIN2_MULT = 0.4


@register_active("champ_tempest_eel.active")
def tempest_eel_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = TEMPEST_EEL_DMG.eval(actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    chain_targets = []
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor) and n is not target and len(chain_targets) < 2:
            chain_targets.append(n)
    for i, ct in enumerate(chain_targets):
        chain_dmg = amount * (_TEMPEST_EEL_CHAIN1_MULT if i == 0 else _TEMPEST_EEL_CHAIN2_MULT)
        ctx.deal_damage(actor, ct, chain_dmg, SourceTag.ABILITY)


ABILITY_META["champ_tempest_eel.active"] = AbilityMeta(
    name="Chain Lightning", kind="active",
    blurb="Strike the primary target for {damage} magic damage.",
    terms=(TEMPEST_EEL_DMG,),
    clauses=(Clause(f"Arcs to up to 2 nearby enemies for {int(_TEMPEST_EEL_CHAIN1_MULT * 100)}% then {int(_TEMPEST_EEL_CHAIN2_MULT * 100)}% damage."),),
    tags=("magic", "aoe"),
)


@register_passive("champ_tempest_eel.passive")
def tempest_eel_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("intelligence", "add", 10.0, Lifetime.COMBAT, "passive:champ_tempest_eel"),
    ])


ABILITY_META["champ_tempest_eel.passive"] = AbilityMeta(
    name="Storm Charge", kind="passive",
    blurb="Grants +10 Intelligence for the whole battle.",
    tags=("buff",),
)


# --- Voltmane Jackal (T7, Hybrid Skirmisher) ---
# Passive: autos alternate STR/INT; discharge on higher stat (MaxOfTerm, V.46).
JACKAL_DISCHARGE = MaxOfTerm("bonus", 0.5, ("strength", "intelligence"))


@register_passive("champ_voltmane_jackal.passive")
def voltmane_jackal_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 3 == 0:
            # Discharge: bonus damage based on higher stat
            ctx.deal_damage(owner, event.target, JACKAL_DISCHARGE.eval(owner), SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_voltmane_jackal.passive"] = AbilityMeta(
    name="Discharge", kind="passive",
    blurb="Every 3rd auto-attack discharges {bonus} bonus magic damage.",
    terms=(JACKAL_DISCHARGE,),
    tags=("magic",),
)


# Active: static discharge — both-scaling burst
VOLTMANE_JACKAL_DMG = ScalingTerm("damage", 60.0, "strength*1.2+intelligence*1.2")


@register_active("champ_voltmane_jackal.active")
def voltmane_jackal_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, VOLTMANE_JACKAL_DMG.eval(actor), SourceTag.ABILITY)
    ctx.apply_status(target, "charged", duration_ticks=300, source_id=actor.id)


ABILITY_META["champ_voltmane_jackal.active"] = AbilityMeta(
    name="Static Discharge", kind="active",
    blurb="Blast the primary target for {damage} hybrid magic damage.",
    terms=(VOLTMANE_JACKAL_DMG,),
    clauses=(Clause("Charges the target for 3s."),), tags=("magic",),
)


# --- Thunderclap Gorilla (T8, STR Bruiser) ---
# Active: shockwave knockback + stun
THUNDERCLAP_GORILLA_DMG = ScalingTerm("damage", 90.0, "strength*2.2")


@register_active("champ_thunderclap_gorilla.active")
def thunderclap_gorilla_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = THUNDERCLAP_GORILLA_DMG.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 2, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount, SourceTag.ABILITY, damage_type="physical")
        ctx.apply_status(t, "stun", duration_ticks=150, source_id=actor.id)


ABILITY_META["champ_thunderclap_gorilla.active"] = AbilityMeta(
    name="Shockwave", kind="active",
    blurb="Unleash a shockwave for {damage} physical damage to all enemies within 2 hexes.",
    terms=(THUNDERCLAP_GORILLA_DMG,),
    clauses=(Clause("Stuns struck enemies for 1.5s."),), tags=("physical", "aoe", "stun"),
)


@register_passive("champ_thunderclap_gorilla.passive")
def thunderclap_gorilla_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("strength", "add", 15.0, Lifetime.COMBAT, "passive:champ_thunderclap_gorilla"),
    ])


ABILITY_META["champ_thunderclap_gorilla.passive"] = AbilityMeta(
    name="Brawn", kind="passive",
    blurb="Grants +15 Strength for the whole battle.",
    tags=("buff",),
)


# --- Storm Eagle (T9, INT Hunter) ---
# Passive: every 3rd auto forks to 2 targets
STORM_EAGLE_FORK = ScalingTerm("bonus", 0.0, "intelligence*0.4")


@register_passive("champ_storm_eagle.passive")
def storm_eagle_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 3 == 0:
            hit_count = 0
            for n in neighbors_of(event.target, ctx):
                if ctx.is_enemy(n, owner) and n is not event.target and hit_count < 2:
                    ctx.deal_damage(owner, n, STORM_EAGLE_FORK.eval(owner), SourceTag.BASIC_ATTACK)
                    hit_count += 1

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_storm_eagle.passive"] = AbilityMeta(
    name="Forked Lightning", kind="passive",
    blurb="Every 3rd auto-attack forks to up to 2 nearby enemies for {bonus} magic damage each.",
    terms=(STORM_EAGLE_FORK,), tags=("magic", "aoe"),
)


STORM_EAGLE_DMG = ScalingTerm("damage", 100.0, "intelligence*2.8")
_STORM_EAGLE_CHAIN_MULT = 0.5


@register_active("champ_storm_eagle.active")
def storm_eagle_active(ctx: Any, actor: Any, targets: list) -> None:
    # Lightning dive: INT damage to primary + chain to 2 neighbors
    target = primary_target(actor, ctx)
    if not target:
        return
    # Buffed scaling for T9 mage damage dealer + chain bounce at 50%
    amount = STORM_EAGLE_DMG.eval(actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    # Chain to 2 neighbors at 50% damage
    hit_count = 0
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor) and n is not target and hit_count < 2:
            ctx.deal_damage(actor, n, amount * _STORM_EAGLE_CHAIN_MULT, SourceTag.ABILITY)
            hit_count += 1


ABILITY_META["champ_storm_eagle.active"] = AbilityMeta(
    name="Lightning Dive", kind="active",
    blurb="Dive the primary target for {damage} magic damage.",
    terms=(STORM_EAGLE_DMG,),
    clauses=(Clause(f"Chains to 2 nearby enemies for {int(_STORM_EAGLE_CHAIN_MULT * 100)}% damage."),),
    tags=("magic", "aoe"),
)


# --- Aerion (T10, Primordial — Thunder) ---
# Passive: when mana is full, autos trigger free casts
AERION_BONUS = ScalingTerm("bonus", 0.0, "intelligence*0.8")


@register_passive("champ_aerion.passive")
def aerion_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        # If mana is near-full, grant bonus damage (simulates free cast)
        if owner.actives:
            slot = owner.actives[0]
            if slot.current_mana >= slot.cost * 0.9:
                ctx.deal_damage(owner, event.target, AERION_BONUS.eval(owner), SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["champ_aerion.passive"] = AbilityMeta(
    name="Overcharge", kind="passive",
    blurb="While mana is near-full, auto-attacks unleash {bonus} bonus magic damage.",
    terms=(AERION_BONUS,), tags=("magic",),
)


# Active: board storm — massive AOE
AERION_DMG = ScalingTerm("damage", 100.0, "strength*1.3+intelligence*1.3")
_AERION_AOE_MULT = 0.6


@register_active("champ_aerion.active")
def aerion_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = AERION_DMG.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 4, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * _AERION_AOE_MULT, SourceTag.ABILITY)
        ctx.apply_status(t, "charged", duration_ticks=200, source_id=actor.id)


ABILITY_META["champ_aerion.active"] = AbilityMeta(
    name="Board Storm", kind="active",
    blurb=f"Summon a storm over all enemies within 4 hexes, each taking {int(_AERION_AOE_MULT * 100)}% of {{damage}} magic damage.",
    terms=(AERION_DMG,),
    clauses=(Clause("Charges struck enemies for 2s."),), tags=("magic", "aoe"),
)
