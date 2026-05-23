"""Champion abilities — hooked to roster via content.py naming convention.

Champion IDs use `{id}.active` and `{id}.passive` patterns.
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
    ABILITY_REGISTRY,
    register_active,
    register_passive,
    _eval_scaling,
)
from src.game.targeting import (
    lowest_hp_ally,
    lowest_hp_enemy,
    primary_target,
    neighbors_of,
    allies_in_radius,
)


# ===========================================================================
# CLEAR — The Sunwild
# ===========================================================================


# --- Dawnwisp (T1, SUP-Heal) ---
# Cast: knit a wound on the lowest-HP ally, INT-scaled heal.
@register_active("dawnwisp.active")
def dawnwisp_active(ctx: Any, actor: Any, targets: list) -> None:
    ally = lowest_hp_ally(actor, ctx)
    if not ally:
        return
    amount = _eval_scaling(40.0, "intelligence*2.5", actor)
    ctx.heal(actor, ally, amount)


# --- Veldt Pronghorn (T2, ADC-STR Warrior) ---
# Passive: every 3rd auto strikes twice.
@register_passive("veldt_pronghorn.passive")
def veldt_pronghorn_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 3 == 0:
            # Extra strike at 50% damage
            ctx.deal_damage(owner, event.target, event.amount * 0.5, SourceTag.BASIC_ATTACK,
                          damage_type="physical")

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


# --- Ember Salamander (T3, APC-INT Mage) ---
# Cast: line of kindling light, burns ground for several ticks.
@register_active("ember_salamander.active")
def ember_salamander_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(60.0, "intelligence*1.8", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    # Apply burn
    ctx.apply_status(target, "burn", duration_ticks=300)


# --- Goldcrest Lark (T4, SUP-Buff) ---
# Cast: allies gain damage and Attack Speed for one round (600 ticks).
@register_active("goldcrest_lark.active")
def goldcrest_lark_active(ctx: Any, actor: Any, targets: list) -> None:
    allies = list(ctx.allies_of(actor))
    for ally in allies:
        ctx.apply_modifier(ally, Modifier(
            "strength", "add", 20.0, Lifetime.TIMED,
            "ability:goldcrest_lark.active",
            expires_at_tick=ctx.current_tick + 600,
        ))
        ctx.apply_modifier(ally, Modifier(
            "attack_speed", "mul", 1.2, Lifetime.TIMED,
            "ability:goldcrest_lark.active",
            expires_at_tick=ctx.current_tick + 600,
        ))


# --- Aegis Tortoise (T5, Tank-ARM+RES) ---
# Passive: reduces damage taken from adjacent attackers.
@register_passive("aegis_tortoise.passive")
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


# --- Sunmane Lion (T6, Tank-STR) ---
# Cast: STR-scaled cleave; shields self for a share of damage dealt.
@register_active("sunmane_lion.active")
def sunmane_lion_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(80.0, "strength*2.0", actor)
    dealt = ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    # Shield = heal for 30% of damage dealt
    ctx.heal(actor, actor, dealt * 0.3)


# ===========================================================================
# RAIN — The Tidewild
# ===========================================================================


# --- Springfrog (T1, SUP-Heal) ---
# Cast: healing rain on lowest-HP ally, restoring health over several ticks.
@register_active("springfrog.active")
def springfrog_active(ctx: Any, actor: Any, targets: list) -> None:
    ally = lowest_hp_ally(actor, ctx)
    if not ally:
        return
    # Immediate heal + apply regen via heal (simplified from HoT)
    amount = _eval_scaling(30.0, "intelligence*2.0", actor)
    ctx.heal(actor, ally, amount)


# --- Torrent Heron (T3, APC-STR Mage) ---
# Cast: three water-spears in a cone, STR-scaled.
@register_active("torrent_heron.active")
def torrent_heron_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(50.0, "strength*1.6", actor)
    # Hit primary + up to 2 neighbors
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    hit_count = 0
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor) and hit_count < 2:
            ctx.deal_damage(actor, n, amount * 0.6, SourceTag.ABILITY, damage_type="physical")
            hit_count += 1


# ===========================================================================
# SNOW — The Frostwild
# ===========================================================================


# --- Permafrost Walrus (T3, APC-STR Mage) ---
# Cast: ice-boulder, STR-scaled impact + small splash.
@register_active("permafrost_walrus.active")
def permafrost_walrus_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(70.0, "strength*1.8", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    # Splash to neighbors at 40%
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor):
            ctx.deal_damage(actor, n, amount * 0.4, SourceTag.ABILITY, damage_type="physical")


# --- Iceclaw Lynx (T6, ADC-INT Warrior) ---
# Passive: autos deal bonus INT-magic damage and briefly slow target.
@register_passive("iceclaw_lynx.passive")
def iceclaw_lynx_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        # Bonus magic damage
        bonus = owner.stat("intelligence") * 0.4
        ctx.deal_damage(owner, event.target, bonus, SourceTag.BASIC_ATTACK)
        # Apply slow
        ctx.apply_status(event.target, "slow", duration_ticks=100, stacks=1)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


# ===========================================================================
# THUNDER — The Stormwild
# ===========================================================================


# --- Tempest Eel (T6, APC-INT Mage) ---
# Cast: chain lightning, jumps to nearby enemies.
@register_active("tempest_eel.active")
def tempest_eel_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(100.0, "intelligence*2.0", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    # Chain to 2 nearby enemies at diminishing damage
    chain_targets = []
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor) and n is not target and len(chain_targets) < 2:
            chain_targets.append(n)
    for i, ct in enumerate(chain_targets):
        chain_dmg = amount * (0.6 if i == 0 else 0.4)
        ctx.deal_damage(actor, ct, chain_dmg, SourceTag.ABILITY)


# ===========================================================================
# MIST — The Hazewild
# ===========================================================================


# --- Phantom Lynx (T3, APC-INT Assassin) ---
# Cast: phases through target for INT damage, ignoring a share of Resistance.
@register_active("phantom_lynx.active")
def phantom_lynx_active(ctx: Any, actor: Any, targets: list) -> None:
    target = lowest_hp_enemy(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(90.0, "intelligence*2.2", actor)
    # Bonus penetration for this hit (applied via increased damage)
    # Simplified: deal extra 20% to simulate resistance ignore
    ctx.deal_damage(actor, target, amount * 1.2, SourceTag.ABILITY)


# ===========================================================================
# CLOUDY — The Cragwild
# ===========================================================================


# --- Granite Gorilla (T6, Tank-INT) ---
# Passive: returns a share of damage taken as INT-magic damage.
@register_passive("granite_gorilla.passive")
def granite_gorilla_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.target is not owner:
            return
        if not hasattr(event, "attacker") or event.attacker is None:
            return
        if not event.attacker.alive:
            return
        # Reflect 15% of damage taken
        reflect_amount = event.amount * 0.15
        if reflect_amount > 0:
            ctx.deal_damage(owner, event.attacker, reflect_amount, SourceTag.REFLECT)

    return EffectBundle(hooks=[
        Hook("on_damage_taken", hook, scope=HookScope.PER_HIT, priority=-10),
    ])
