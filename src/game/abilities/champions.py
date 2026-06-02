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
    enemies_in_radius,
    furthest_enemy,
    random_enemy,
)


# ===========================================================================
# CLEAR — The Sunwild
# ===========================================================================


# --- Dawnwisp (T1, SUP-Heal) ---
# Cast: knit a wound on the lowest-HP ally, INT-scaled heal.
@register_active("champ_dawnwisp.active")
def dawnwisp_active(ctx: Any, actor: Any, targets: list) -> None:
    ally = lowest_hp_ally(actor, ctx)
    if not ally:
        return
    amount = _eval_scaling(40.0, "intelligence*2.5", actor)
    ctx.heal(actor, ally, amount)


# Passive: heal-over-time ticks on heal target (periodic tick effect every 100 ticks)
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
        ctx.heal(owner, event.target, owner.stat("intelligence") * 0.3)
        state["healing"] = False

    return EffectBundle(hooks=[
        Hook("on_heal", hook, scope=HookScope.ONCE_PER_CAST),
    ])


# --- Veldt Pronghorn (T2, ADC-STR Warrior) ---
# Passive: every 3rd auto strikes twice.
@register_passive("champ_veldt_pronghorn.passive")
def veldt_pronghorn_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 3 == 0:
            ctx.deal_damage(owner, event.target, event.amount * 0.5, SourceTag.BASIC_ATTACK,
                          damage_type="physical")

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


# Active: lunging charge — STR-scaled single target
@register_active("champ_veldt_pronghorn.active")
def veldt_pronghorn_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(50.0, "strength*1.8", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


# --- Ember Salamander (T3, APC-INT Mage) ---
# Cast: line of kindling light, burns ground for several ticks.
@register_active("champ_ember_salamander.active")
def ember_salamander_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(60.0, "intelligence*1.8", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    ctx.apply_status(target, "burn", duration_ticks=300, source_id=actor.id)


@register_passive("champ_ember_salamander.passive")
def ember_salamander_passive(owner: Any) -> EffectBundle:
    # Bonus damage vs burning targets
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        if event.target.has_status("burn"):
            ctx.deal_damage(owner, event.target, owner.stat("intelligence") * 0.3,
                          SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


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


@register_passive("champ_goldcrest_lark.passive")
def goldcrest_lark_passive(owner: Any) -> EffectBundle:
    # Lark's song: allies near lark gain a small INT boost at combat start
    return EffectBundle(modifiers=[
        Modifier("intelligence", "add", 10.0, Lifetime.COMBAT, "passive:champ_goldcrest_lark"),
    ])


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


# --- Sunmane Lion (T6, Tank-STR) ---
# Cast: STR-scaled cleave; self-heal for a share of damage dealt.
@register_active("champ_sunmane_lion.active")
def sunmane_lion_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(80.0, "strength*2.0", actor)
    dealt = ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    # Self-heal for 30% of damage dealt (represents shield)
    ctx.heal(actor, actor, dealt * 0.3)


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


# --- Goldhide Rhino (T7, Tank-Heal) ---
# Passive: heals on auto-attack, scaling with max HP.
@register_passive("champ_goldhide_rhino.passive")
def goldhide_rhino_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        heal_amt = owner.max_hp * 0.03  # 3% max HP on hit
        ctx.heal(owner, owner, heal_amt)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("champ_goldhide_rhino.active")
def goldhide_rhino_active(ctx: Any, actor: Any, targets: list) -> None:
    # Stampede: STR damage to target + small self-heal
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(60.0, "strength*1.5", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    ctx.heal(actor, actor, actor.max_hp * 0.05)


# --- Mirage Caracal (T8, APC-INT Assassin) ---
# Cast: blink execute (bonus damage to low-HP targets).
@register_active("champ_mirage_caracal.active")
def mirage_caracal_active(ctx: Any, actor: Any, targets: list) -> None:
    target = lowest_hp_enemy(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(80.0, "intelligence*2.2", actor)
    # Execute bonus: +50% damage if target below 30% HP
    if target.hp_pct < 0.3:
        amount *= 1.5
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)


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
            bonus = owner.stat("intelligence") * 0.5
            ctx.deal_damage(owner, event.target, bonus, SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_cast_complete", on_cast, scope=HookScope.PER_HIT),
        Hook("on_attack_landed", on_attack, scope=HookScope.PER_HIT),
    ])


# --- Sunspear Falcon (T9, ADC-STR Marksman) ---
# Passive: sun-mark on target after first auto; bonus damage on subsequent autos.
@register_passive("champ_sunspear_falcon.passive")
def sunspear_falcon_passive(owner: Any) -> EffectBundle:
    state: dict[str, bool] = {}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        target_id = event.target.id
        if target_id in state:
            # Marked — bonus damage
            bonus = owner.stat("strength") * 0.35
            ctx.deal_damage(owner, event.target, bonus, SourceTag.BASIC_ATTACK,
                          damage_type="physical")
        else:
            state[target_id] = True

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("champ_sunspear_falcon.active")
def sunspear_falcon_active(ctx: Any, actor: Any, targets: list) -> None:
    # Diving strike: STR damage to primary, marks target
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(70.0, "strength*2.0", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


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


# Active: nova that disarms all enemies in radius 2
@register_active("champ_aurion.active")
def aurion_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = _eval_scaling(100.0, "strength*1.5+intelligence*1.5", actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 2, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount, SourceTag.ABILITY)
        ctx.apply_status(t, "disarm", duration_ticks=200, source_id=actor.id)


# ===========================================================================
# RAIN — The Tidewild
# ===========================================================================


# --- Springfrog (T1, SUP-Heal) ---
# Cast: healing rain on lowest-HP ally, restoring health.
@register_active("champ_springfrog.active")
def springfrog_active(ctx: Any, actor: Any, targets: list) -> None:
    ally = lowest_hp_ally(actor, ctx)
    if not ally:
        return
    amount = _eval_scaling(30.0, "intelligence*2.0", actor)
    ctx.heal(actor, ally, amount)


@register_passive("champ_springfrog.passive")
def springfrog_passive(owner: Any) -> EffectBundle:
    # HoT effect: periodic heal tick every 200 ticks to lowest ally
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 200:
            state["last_tick"] = ctx.current_tick
            ally = lowest_hp_ally(owner, ctx)
            if ally:
                ctx.heal(owner, ally, owner.stat("intelligence") * 0.4)

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


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


@register_active("champ_reedbank_otter.active")
def reedbank_otter_active(ctx: Any, actor: Any, targets: list) -> None:
    # Slippery strike: STR damage + MS boost
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(40.0, "strength*1.6", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    ctx.apply_modifier(actor, Modifier(
        "attack_speed", "add", 20.0, Lifetime.TIMED,
        "ability:champ_reedbank_otter",
        expires_at_tick=ctx.current_tick + 400,
    ))


# --- Torrent Heron (T3, APC-STR Mage) ---
# Cast: three water-spears in a cone, STR-scaled.
@register_active("champ_torrent_heron.active")
def torrent_heron_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(50.0, "strength*1.6", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    hit_count = 0
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor) and hit_count < 2:
            ctx.deal_damage(actor, n, amount * 0.6, SourceTag.ABILITY, damage_type="physical")
            hit_count += 1


@register_passive("champ_torrent_heron.passive")
def torrent_heron_passive(owner: Any) -> EffectBundle:
    # Water affinity: bonus damage in rain weather
    return EffectBundle(modifiers=[
        Modifier("strength", "add", 8.0, Lifetime.COMBAT, "passive:champ_torrent_heron"),
    ])


# --- Grovekeeper Tapir (T4, Hybrid Bruiser-Mender) ---
# Cast: vine snare + DoT
@register_active("champ_grovekeeper_tapir.active")
def grovekeeper_tapir_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(40.0, "strength*1.0+intelligence*1.0", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    ctx.apply_status(target, "root", duration_ticks=200, source_id=actor.id)
    ctx.apply_status(target, "poison", duration_ticks=400, stacks=2, source_id=actor.id)


@register_passive("champ_grovekeeper_tapir.passive")
def grovekeeper_tapir_passive(owner: Any) -> EffectBundle:
    # Regen: periodic heal every 300 ticks
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 300:
            state["last_tick"] = ctx.current_tick
            ctx.heal(owner, owner, owner.max_hp * 0.02)

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


# --- Coral Colossus (T5, Tank-Guardian) ---
# Passive: regen when below 40% HP
@register_passive("champ_coral_colossus.passive")
def coral_colossus_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 200:
            state["last_tick"] = ctx.current_tick
            if owner.hp_pct < 0.4:
                ctx.heal(owner, owner, owner.max_hp * 0.04)

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


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


# --- Marsh Thrush (T6, SUP-Buff) ---
# Cast: team MS+AS buff + INT-scaled damage to primary target
@register_active("champ_marsh_thrush.active")
def marsh_thrush_active(ctx: Any, actor: Any, targets: list) -> None:
    allies = list(ctx.allies_of(actor))
    for ally in allies:
        ctx.apply_modifier(ally, Modifier(
            "move_speed", "add", 15.0, Lifetime.TIMED,
            "ability:champ_marsh_thrush",
            expires_at_tick=ctx.current_tick + 600,
        ))
        ctx.apply_modifier(ally, Modifier(
            "attack_speed", "add", 15.0, Lifetime.TIMED,
            "ability:champ_marsh_thrush",
            expires_at_tick=ctx.current_tick + 600,
        ))
    # Damage rider — INT-scaled burst on primary target
    target = primary_target(actor, ctx)
    if target:
        amount = _eval_scaling(65.0, "intelligence*1.8", actor)
        ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)


@register_passive("champ_marsh_thrush.passive")
def marsh_thrush_passive(owner: Any) -> EffectBundle:
    # Periodic INT-scaled damage aura every 300 ticks + move speed boost
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 300:
            state["last_tick"] = ctx.current_tick
            amount = owner.stat("intelligence") * 0.4
            enemies = enemies_in_radius(owner.position_q, owner.position_r, 2, owner, ctx)
            for e in enemies:
                ctx.deal_damage(owner, e, amount, SourceTag.ABILITY)

    return EffectBundle(
        modifiers=[
            Modifier("move_speed", "add", 10.0, Lifetime.COMBAT, "passive:champ_marsh_thrush"),
        ],
        hooks=[
            Hook("on_tick", hook, scope=HookScope.PER_HIT),
        ],
    )


# --- Mirewarden Toad (T7, Tank-Guardian) ---
# Active: tongue pull (slow + damage)
@register_active("champ_mirewarden_toad.active")
def mirewarden_toad_active(ctx: Any, actor: Any, targets: list) -> None:
    target = furthest_enemy(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(50.0, "intelligence*1.5", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    ctx.apply_status(target, "slow", duration_ticks=300, stacks=2, source_id=actor.id)
    ctx.apply_status(target, "root", duration_ticks=150, source_id=actor.id)


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


# --- Glade Heron (T8, ADC-INT Hunter) ---
# Passive: autos apply poison stacks + execute bonus vs poisoned targets
@register_passive("champ_glade_heron.passive")
def glade_heron_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        ctx.apply_status(event.target, "poison", duration_ticks=400, stacks=1,
                        source_id=owner.id)
        # Execute bonus: extra INT-scaled damage vs targets with 3+ poison stacks
        if hasattr(event.target, 'status_stacks'):
            poison_stacks = event.target.status_stacks("poison")
        else:
            poison_stacks = 0
        if poison_stacks >= 3:
            execute_bonus = owner.stat("intelligence") * 0.5
            ctx.deal_damage(owner, event.target, execute_bonus, SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("champ_glade_heron.active")
def glade_heron_active(ctx: Any, actor: Any, targets: list) -> None:
    # Toxic volley: higher INT damage + heavy poison stacks
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(80.0, "intelligence*2.4", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    ctx.apply_status(target, "poison", duration_ticks=600, stacks=4, source_id=actor.id)


# --- Riptide Caiman (T9, ADC-STR Stalker) ---
# Active: death-roll dash, bonus mana on kill
@register_active("champ_riptide_caiman.active")
def riptide_caiman_active(ctx: Any, actor: Any, targets: list) -> None:
    target = lowest_hp_enemy(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(100.0, "strength*2.5", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


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


# --- Nerei (T10, Primordial — hybrid) ---
# Passive: after casting, next 3 autos deal bonus INT damage
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
            bonus = owner.stat("intelligence") * 0.6
            ctx.deal_damage(owner, event.target, bonus, SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_cast_complete", on_cast, scope=HookScope.PER_HIT),
        Hook("on_attack_landed", on_attack, scope=HookScope.PER_HIT),
    ])


# Active: tidal wave — AOE INT damage
@register_active("champ_nerei.active")
def nerei_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = _eval_scaling(90.0, "intelligence*2.0", actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * 0.7, SourceTag.ABILITY)
    ctx.apply_status(actor, "charged", duration_ticks=300, source_id=actor.id)


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


@register_active("champ_snowpelt_cub.active")
def snowpelt_cub_active(ctx: Any, actor: Any, targets: list) -> None:
    # Frostbite nip: small STR damage + slow
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(25.0, "strength*1.2", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    ctx.apply_status(target, "slow", duration_ticks=200, stacks=1, source_id=actor.id)


# --- Wintermoth (T2, SUP-Buff) ---
# Active: grant ally AS buff
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
    ctx.heal(actor, ally, _eval_scaling(20.0, "intelligence*1.0", actor))


@register_passive("champ_wintermoth.passive")
def wintermoth_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("resistance", "add", 8.0, Lifetime.COMBAT, "passive:champ_wintermoth"),
    ])


# --- Permafrost Walrus (T3, APC-STR Mage) ---
# Cast: ice-boulder, STR-scaled impact + small splash.
@register_active("champ_permafrost_walrus.active")
def permafrost_walrus_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(70.0, "strength*1.8", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor):
            ctx.deal_damage(actor, n, amount * 0.4, SourceTag.ABILITY, damage_type="physical")


@register_passive("champ_permafrost_walrus.passive")
def permafrost_walrus_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("strength", "add", 8.0, Lifetime.COMBAT, "passive:champ_permafrost_walrus"),
    ])


# --- Hoarfrost Owl (T4, SUP-Shield) ---
# Active: ally ice-shield (large armor buff) + chill burst on expiry
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
    ctx.heal(actor, ally, _eval_scaling(30.0, "intelligence*1.5", actor))


@register_passive("champ_hoarfrost_owl.passive")
def hoarfrost_owl_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("intelligence", "add", 8.0, Lifetime.COMBAT, "passive:champ_hoarfrost_owl"),
    ])


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


@register_active("champ_frostplate_tortoise.active")
def frostplate_tortoise_active(ctx: Any, actor: Any, targets: list) -> None:
    # Ice slam: STR damage + root
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(60.0, "strength*1.6", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    ctx.apply_status(target, "root", duration_ticks=200, source_id=actor.id)


# --- Iceclaw Lynx (T6, ADC-INT Warrior) ---
# Passive: autos deal bonus INT-magic damage and briefly slow target.
@register_passive("champ_iceclaw_lynx.passive")
def iceclaw_lynx_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        bonus = owner.stat("intelligence") * 0.4
        ctx.deal_damage(owner, event.target, bonus, SourceTag.BASIC_ATTACK)
        ctx.apply_status(event.target, "slow", duration_ticks=100, stacks=1, source_id=owner.id)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("champ_iceclaw_lynx.active")
def iceclaw_lynx_active(ctx: Any, actor: Any, targets: list) -> None:
    # Frost pounce: INT burst + freeze
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(80.0, "intelligence*2.0", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    ctx.apply_status(target, "frozen", duration_ticks=150, source_id=actor.id)


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


# Active: knockback stomp (STR damage + stun to neighbors)
@register_active("champ_glacierback_mammoth.active")
def glacierback_mammoth_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = _eval_scaling(80.0, "strength*2.0", actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 1, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount, SourceTag.ABILITY, damage_type="physical")
        ctx.apply_status(t, "stun", duration_ticks=100, source_id=actor.id)


# --- Frostfang Wolverine (T8, ADC-STR Stalker) ---
# Active: leap burst; crit vs frozen/slowed
@register_active("champ_frostfang_wolverine.active")
def frostfang_wolverine_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(90.0, "strength*2.2", actor)
    # Bonus vs frozen/slowed
    if target.has_status("frozen") or target.has_status("slow"):
        amount *= 1.5
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical", crit=True)


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


# --- Frostquill Porcupine (T9, ADC-STR Hunter) ---
# Passive: autos slow; bonus damage vs slowed
@register_passive("champ_frostquill_porcupine.passive")
def frostquill_porcupine_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        ctx.apply_status(event.target, "slow", duration_ticks=150, stacks=1, source_id=owner.id)
        if event.target.has_status("slow"):
            bonus = owner.stat("strength") * 0.25
            ctx.deal_damage(owner, event.target, bonus, SourceTag.BASIC_ATTACK,
                          damage_type="physical")

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("champ_frostquill_porcupine.active")
def frostquill_porcupine_active(ctx: Any, actor: Any, targets: list) -> None:
    # Quill volley: STR damage to primary + 2 nearby, all slowed
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(70.0, "strength*1.8", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    ctx.apply_status(target, "slow", duration_ticks=300, stacks=2, source_id=actor.id)
    hit_count = 0
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor) and hit_count < 2:
            ctx.deal_damage(actor, n, amount * 0.5, SourceTag.ABILITY, damage_type="physical")
            ctx.apply_status(n, "slow", duration_ticks=300, stacks=1, source_id=actor.id)
            hit_count += 1


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


# Active: blizzard — AOE INT+STR damage
@register_active("champ_borealis.active")
def borealis_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = _eval_scaling(80.0, "strength*1.2+intelligence*1.2", actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount, SourceTag.ABILITY)
        ctx.apply_status(t, "slow", duration_ticks=300, stacks=2, source_id=actor.id)


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


@register_active("champ_pebbleback_pangolin.active")
def pebbleback_pangolin_active(ctx: Any, actor: Any, targets: list) -> None:
    # Curl up: gain armor briefly
    ctx.apply_modifier(actor, Modifier(
        "armor", "add", 25.0, Lifetime.TIMED,
        "ability:champ_pebbleback_pangolin",
        expires_at_tick=ctx.current_tick + 400,
    ))


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


@register_passive("champ_dusk_bat.passive")
def dusk_bat_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("move_speed", "add", 10.0, Lifetime.COMBAT, "passive:champ_dusk_bat"),
    ])


# --- Boulderhide Skink (T3, APC-STR Mage) ---
# Active: boulder rolls a line — STR damage
@register_active("champ_boulderhide_skink.active")
def boulderhide_skink_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(60.0, "strength*1.8", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    # Hit neighbors in line
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor):
            ctx.deal_damage(actor, n, amount * 0.5, SourceTag.ABILITY, damage_type="physical")
            break  # Only one extra target for line


@register_passive("champ_boulderhide_skink.passive")
def boulderhide_skink_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("armor", "add", 5.0, Lifetime.COMBAT, "passive:champ_boulderhide_skink"),
    ])


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


@register_passive("champ_geode_beetle.passive")
def geode_beetle_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("armor", "add", 10.0, Lifetime.COMBAT, "passive:champ_geode_beetle"),
    ])


# --- Duskstep Marten (T5, INT Assassin) ---
# Passive: shadow-step — every 4th auto, teleport behind target for bonus damage
@register_passive("champ_duskstep_marten.passive")
def duskstep_marten_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 4 == 0:
            bonus = owner.stat("intelligence") * 0.6
            ctx.deal_damage(owner, event.target, bonus, SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("champ_duskstep_marten.active")
def duskstep_marten_active(ctx: Any, actor: Any, targets: list) -> None:
    # Shadow strike: INT burst
    target = lowest_hp_enemy(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(70.0, "intelligence*2.0", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)


# --- Granite Gorilla (T6, Tank-INT) ---
# Passive: returns a share of damage taken as INT-magic damage.
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
        reflect_amount = event.amount * 0.15
        if reflect_amount > 0:
            ctx.deal_damage(owner, event.attacker, reflect_amount, SourceTag.REFLECT)

    return EffectBundle(hooks=[
        Hook("on_damage_taken", hook, scope=HookScope.PER_HIT, priority=-10),
    ])


@register_active("champ_granite_gorilla.active")
def granite_gorilla_active(ctx: Any, actor: Any, targets: list) -> None:
    # Ground slam: INT damage AOE + stun
    amount = _eval_scaling(70.0, "intelligence*1.8", actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 1, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount, SourceTag.ABILITY)
        ctx.apply_status(t, "stun", duration_ticks=100, source_id=actor.id)


# --- Eclipse Jaguar (T7, Hybrid Stalker) ---
# Passive: autos alternate STR and INT damage
@register_passive("champ_eclipse_jaguar.passive")
def eclipse_jaguar_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 2 == 0:
            # INT bonus on even hits
            bonus = owner.stat("intelligence") * 0.4
            ctx.deal_damage(owner, event.target, bonus, SourceTag.BASIC_ATTACK)
        else:
            # STR bonus on odd hits
            bonus = owner.stat("strength") * 0.3
            ctx.deal_damage(owner, event.target, bonus, SourceTag.BASIC_ATTACK,
                          damage_type="physical")

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


# Active: twin strike — both STR and INT damage
@register_active("champ_eclipse_jaguar.active")
def eclipse_jaguar_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    str_dmg = _eval_scaling(50.0, "strength*1.5", actor)
    int_dmg = _eval_scaling(50.0, "intelligence*1.5", actor)
    ctx.deal_damage(actor, target, str_dmg, SourceTag.ABILITY, damage_type="physical")
    ctx.deal_damage(actor, target, int_dmg, SourceTag.ABILITY)


# --- Nightglass Mantis (T8, INT Assassin) ---
# Active: vanish → INT execute (bonus vs low HP)
@register_active("champ_nightglass_mantis.active")
def nightglass_mantis_active(ctx: Any, actor: Any, targets: list) -> None:
    target = lowest_hp_enemy(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(100.0, "intelligence*2.5", actor)
    if target.hp_pct < 0.3:
        amount *= 1.6
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)


@register_passive("champ_nightglass_mantis.passive")
def nightglass_mantis_passive(owner: Any) -> EffectBundle:
    # Bonus damage from stealth (first hit after being idle is amplified)
    state = {"first_hit": True}

    def on_attack(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        if state["first_hit"]:
            state["first_hit"] = False
            bonus = owner.stat("intelligence") * 0.8
            ctx.deal_damage(owner, event.target, bonus, SourceTag.ABILITY)

    def on_cast(ctx: Any, event: Any) -> None:
        if event.caster is not owner:
            return
        state["first_hit"] = True  # Reset after each cast

    return EffectBundle(hooks=[
        Hook("on_attack_landed", on_attack, scope=HookScope.PER_HIT),
        Hook("on_cast_complete", on_cast, scope=HookScope.PER_HIT),
    ])


# --- Cliffeyrie Eagle (T9, ADC-STR Hunter) ---
# Passive: first auto vastly amplified
@register_passive("champ_cliffeyrie_eagle.passive")
def cliffeyrie_eagle_passive(owner: Any) -> EffectBundle:
    state = {"first_hit": True}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        if state["first_hit"]:
            state["first_hit"] = False
            bonus = owner.stat("strength") * 1.5
            ctx.deal_damage(owner, event.target, bonus, SourceTag.BASIC_ATTACK,
                          damage_type="physical")

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("champ_cliffeyrie_eagle.active")
def cliffeyrie_eagle_active(ctx: Any, actor: Any, targets: list) -> None:
    # Diving talon: STR damage + reset first-hit passive
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(80.0, "strength*2.2", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


# --- Umbra (T10, Primordial — Cloudy) ---
# Passive: every 5th auto triggers a free cast
@register_passive("champ_umbra.passive")
def umbra_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 5 == 0:
            # Free cast: deal INT damage as shadow clone strike
            amount = owner.stat("intelligence") * 1.5
            ctx.deal_damage(owner, event.target, amount, SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


# Active: summon shadow clones (spawn real flagged pieces)
@register_active("champ_umbra.active")
def umbra_active(ctx: Any, actor: Any, targets: list) -> None:
    from src.game.piece import Piece, ActiveSlot
    # Spawn 2 shadow clones as real Piece objects with summon flag
    for i in range(2):
        clone = Piece(
            id=f"{actor.id}_clone_{ctx.current_tick}_{i}",
            base_stats={
                "max_hp": actor.max_hp * 0.3,
                "strength": actor.stat("strength") * 0.4,
                "intelligence": actor.stat("intelligence") * 0.4,
                "armor": actor.stat("armor") * 0.3,
                "resistance": actor.stat("resistance") * 0.3,
                "attack_speed": actor.stat("attack_speed"),
                "mana_regen": 0,
                "move_speed": actor.stat("move_speed"),
                "threat": 20,
                "attack_range": actor.stat("attack_range"),
                "ability_cost": 999_999,
                "crit_chance": 0.0,
                "penetration": 0,
                "penetration_pct": 0.0,
            },
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
@register_active("champ_lostlight_wisp.active")
def lostlight_wisp_active(ctx: Any, actor: Any, targets: list) -> None:
    ally = lowest_hp_ally(actor, ctx)
    if not ally:
        return
    amount = _eval_scaling(35.0, "intelligence*2.0", actor)
    ctx.heal(actor, ally, amount)


@register_passive("champ_lostlight_wisp.passive")
def lostlight_wisp_passive(owner: Any) -> EffectBundle:
    # Periodic heal to lowest ally every 200 ticks
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 200:
            state["last_tick"] = ctx.current_tick
            ally = lowest_hp_ally(owner, ctx)
            if ally:
                ctx.heal(owner, ally, owner.stat("intelligence") * 0.3)

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


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


@register_passive("champ_will_o_fawn.passive")
def will_o_fawn_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("intelligence", "add", 8.0, Lifetime.COMBAT, "passive:champ_will_o_fawn"),
    ])


# --- Phantom Lynx (T3, APC-INT Assassin) ---
# Cast: phases through target for INT damage, with penetration.
@register_active("champ_phantom_lynx.active")
def phantom_lynx_active(ctx: Any, actor: Any, targets: list) -> None:
    target = lowest_hp_enemy(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(90.0, "intelligence*2.2", actor)
    # Use pen_pct parameter for resistance ignore
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="magical")
    # Apply temporary pen boost
    ctx.apply_modifier(actor, Modifier(
        "penetration_pct", "add", 0.3, Lifetime.TIMED,
        "ability:champ_phantom_lynx.pen",
        expires_at_tick=ctx.current_tick + 200,
    ))


@register_passive("champ_phantom_lynx.passive")
def phantom_lynx_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("penetration_pct", "add", 0.15, Lifetime.COMBAT, "passive:champ_phantom_lynx"),
    ])


# --- Hollow Elk (T4, Tank-Channeler) ---
# Passive: convert incoming damage to mana
@register_passive("champ_hollow_elk.passive")
def hollow_elk_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.target is not owner:
            return
        # Convert 10% of damage taken to mana
        mana_gain = event.amount * 0.10
        ctx.gain_mana(owner, mana_gain)

    return EffectBundle(hooks=[
        Hook("on_damage_taken", hook, scope=HookScope.PER_HIT),
    ])


@register_active("champ_hollow_elk.active")
def hollow_elk_active(ctx: Any, actor: Any, targets: list) -> None:
    # Spirit drain: INT damage + self heal
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(60.0, "intelligence*1.8", actor)
    dealt = ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    ctx.heal(actor, actor, dealt * 0.3)


# --- Fogveil Moth (T5, Trickster) ---
# Active: shroud enemy (reduce their AS — simulates miss chance)
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
    amount = _eval_scaling(30.0, "intelligence*1.2", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)


@register_passive("champ_fogveil_moth.passive")
def fogveil_moth_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("resistance", "add", 10.0, Lifetime.COMBAT, "passive:champ_fogveil_moth"),
    ])


# --- Wraithorn Stag (T6, STR Bruiser) ---
# Active: spectral gore — STR burst
@register_active("champ_wraithorn_stag.active")
def wraithorn_stag_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(80.0, "strength*2.2", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


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


@register_active("champ_marshghast_boar.active")
def marshghast_boar_active(ctx: Any, actor: Any, targets: list) -> None:
    # Ghost charge: hybrid damage
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(60.0, "strength*1.2+intelligence*1.2", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


# --- Veilfang Wolf (T8, INT Skirmisher) ---
# Passive: autos deal bonus INT + shred resistance
@register_passive("champ_veilfang_wolf.passive")
def veilfang_wolf_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        bonus = owner.stat("intelligence") * 0.35
        ctx.deal_damage(owner, event.target, bonus, SourceTag.BASIC_ATTACK)
        # Resistance shred
        ctx.apply_modifier(event.target, Modifier(
            "resistance", "add", -8.0, Lifetime.TIMED,
            "passive:champ_veilfang_wolf.shred",
            expires_at_tick=ctx.current_tick + 400,
        ))

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("champ_veilfang_wolf.active")
def veilfang_wolf_active(ctx: Any, actor: Any, targets: list) -> None:
    # Fang rush: INT damage
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(80.0, "intelligence*2.2", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)


# --- Spectral Heron (T9, INT Hunter) ---
# Passive: autos pierce (hit target + 1 behind)
@register_passive("champ_spectral_heron.passive")
def spectral_heron_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        # Pierce: hit one enemy behind target
        for n in neighbors_of(event.target, ctx):
            if ctx.is_enemy(n, owner) and n is not event.target:
                bonus = owner.stat("intelligence") * 0.3
                ctx.deal_damage(owner, n, bonus, SourceTag.BASIC_ATTACK)
                break

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("champ_spectral_heron.active")
def spectral_heron_active(ctx: Any, actor: Any, targets: list) -> None:
    # Spectral beam: line damage
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(80.0, "intelligence*2.0", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor):
            ctx.deal_damage(actor, n, amount * 0.6, SourceTag.ABILITY)


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


# Active: board fear — AOE fear enemies
@register_active("champ_mournhollow.active")
def mournhollow_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = _eval_scaling(80.0, "intelligence*1.8", actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * 0.6, SourceTag.ABILITY)
        ctx.apply_status(t, "fear", duration_ticks=200, source_id=actor.id)


# ===========================================================================
# THUNDER — The Stormwild
# ===========================================================================


# --- Sparkfly (T1, Trickster) ---
# Active: brief stun one enemy
@register_active("champ_sparkfly.active")
def sparkfly_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(20.0, "intelligence*1.0", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    ctx.apply_status(target, "stun", duration_ticks=150, source_id=actor.id)


@register_passive("champ_sparkfly.passive")
def sparkfly_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("move_speed", "add", 10.0, Lifetime.COMBAT, "passive:champ_sparkfly"),
    ])


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


@register_active("champ_thunderhoof_colt.active")
def thunderhoof_colt_active(ctx: Any, actor: Any, targets: list) -> None:
    # Thunder charge: STR damage
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(45.0, "strength*1.6", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


# --- Voltscale Mamba (T3, ADC-STR Stalker) ---
# Active: dash + electric trail damage
@register_active("champ_voltscale_mamba.active")
def voltscale_mamba_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(55.0, "strength*1.8", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    # Electric trail: apply burn to target (represents trail damage)
    ctx.apply_status(target, "burn", duration_ticks=200, source_id=actor.id)


@register_passive("champ_voltscale_mamba.passive")
def voltscale_mamba_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("move_speed", "add", 15.0, Lifetime.COMBAT, "passive:champ_voltscale_mamba"),
    ])


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


@register_passive("champ_coppercrest_stork.passive")
def coppercrest_stork_passive(owner: Any) -> EffectBundle:
    # Shield reflects: when shielded ally takes damage, reflect portion
    return EffectBundle(modifiers=[
        Modifier("resistance", "add", 10.0, Lifetime.COMBAT, "passive:champ_coppercrest_stork"),
    ])


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


@register_active("champ_thunderhide_bison.active")
def thunderhide_bison_active(ctx: Any, actor: Any, targets: list) -> None:
    # Thunder stomp: STR damage + stun
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(60.0, "strength*1.8", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    ctx.apply_status(target, "stun", duration_ticks=120, source_id=actor.id)


# --- Tempest Eel (T6, APC-INT Mage) ---
# Cast: chain lightning, jumps to nearby enemies.
@register_active("champ_tempest_eel.active")
def tempest_eel_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(100.0, "intelligence*2.0", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    chain_targets = []
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor) and n is not target and len(chain_targets) < 2:
            chain_targets.append(n)
    for i, ct in enumerate(chain_targets):
        chain_dmg = amount * (0.6 if i == 0 else 0.4)
        ctx.deal_damage(actor, ct, chain_dmg, SourceTag.ABILITY)


@register_passive("champ_tempest_eel.passive")
def tempest_eel_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("intelligence", "add", 10.0, Lifetime.COMBAT, "passive:champ_tempest_eel"),
    ])


# --- Voltmane Jackal (T7, Hybrid Skirmisher) ---
# Passive: autos alternate STR/INT; discharge on higher stat
@register_passive("champ_voltmane_jackal.passive")
def voltmane_jackal_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        str_val = owner.stat("strength")
        int_val = owner.stat("intelligence")
        if state["count"] % 3 == 0:
            # Discharge: bonus damage based on higher stat
            bonus = max(str_val, int_val) * 0.5
            ctx.deal_damage(owner, event.target, bonus, SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


# Active: static discharge — both-scaling burst
@register_active("champ_voltmane_jackal.active")
def voltmane_jackal_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(60.0, "strength*1.2+intelligence*1.2", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    ctx.apply_status(target, "charged", duration_ticks=300, source_id=actor.id)


# --- Thunderclap Gorilla (T8, STR Bruiser) ---
# Active: shockwave knockback + stun
@register_active("champ_thunderclap_gorilla.active")
def thunderclap_gorilla_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = _eval_scaling(90.0, "strength*2.2", actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 2, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount, SourceTag.ABILITY, damage_type="physical")
        ctx.apply_status(t, "stun", duration_ticks=150, source_id=actor.id)


@register_passive("champ_thunderclap_gorilla.passive")
def thunderclap_gorilla_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("strength", "add", 15.0, Lifetime.COMBAT, "passive:champ_thunderclap_gorilla"),
    ])


# --- Storm Eagle (T9, INT Hunter) ---
# Passive: every 3rd auto forks to 2 targets
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
                    bonus = owner.stat("intelligence") * 0.4
                    ctx.deal_damage(owner, n, bonus, SourceTag.BASIC_ATTACK)
                    hit_count += 1

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("champ_storm_eagle.active")
def storm_eagle_active(ctx: Any, actor: Any, targets: list) -> None:
    # Lightning dive: INT damage to primary + chain to neighbors
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(100.0, "intelligence*2.8", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    # Chain bounce to up to 2 neighbors at 50% damage
    hit_count = 0
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor) and n is not target and hit_count < 2:
            ctx.deal_damage(actor, n, amount * 0.5, SourceTag.ABILITY)
            hit_count += 1


# --- Aerion (T10, Primordial — Thunder) ---
# Passive: when mana is full, autos trigger free casts
@register_passive("champ_aerion.passive")
def aerion_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        # If mana is near-full, grant bonus damage (simulates free cast)
        if owner.actives:
            slot = owner.actives[0]
            if slot.current_mana >= slot.cost * 0.9:
                bonus = owner.stat("intelligence") * 0.8
                ctx.deal_damage(owner, event.target, bonus, SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


# Active: board storm — massive AOE
@register_active("champ_aerion.active")
def aerion_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = _eval_scaling(100.0, "strength*1.3+intelligence*1.3", actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 4, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * 0.6, SourceTag.ABILITY)
        ctx.apply_status(t, "charged", duration_ticks=200, source_id=actor.id)
