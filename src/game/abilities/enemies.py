"""Enemy abilities — all 60 enemies from the roster.

Registered under full roster IDs: `{enemy_id}.active` / `{enemy_id}.passive`.
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
from src.game.registries import (
    register_active,
    register_passive,
    _eval_scaling,
)
from src.game.targeting import (
    allies_in_radius,
    enemies_in_radius,
    lowest_hp_ally,
    lowest_hp_enemy,
    neighbors_of,
    primary_target,
    furthest_enemy,
)


# ===========================================================================
# CLEAR — Humans (30)
# ===========================================================================


# --- Conscript (T1) --- every 4th auto heavier
@register_passive("enemy_conscript.passive")
def conscript_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 4 == 0:
            bonus = owner.stat("strength") * 0.5
            ctx.deal_damage(owner, event.target, bonus, SourceTag.BASIC_ATTACK,
                          damage_type="physical")

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_conscript.active")
def conscript_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(30.0, "strength*1.5", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


# --- Levyman (T1) --- +HP every 600 ticks
@register_passive("enemy_levyman.passive")
def levyman_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 600:
            state["last_tick"] = ctx.current_tick
            owner.max_hp += 25.0
            owner.hp = min(owner.hp + 25.0, owner.max_hp)

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_levyman.active")
def levyman_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(25.0, "strength*1.3", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


# --- Picket (T1) --- plain auto-attacker (no special ability)
@register_passive("enemy_picket.passive")
def picket_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


@register_active("enemy_picket.active")
def picket_active(ctx: Any, actor: Any, targets: list) -> None:
    # No special ability — just a basic attack trigger
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(20.0, "strength*1.2", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


# --- Stretcher-Hand (T1) --- small fixed heal lowest ally
@register_active("enemy_stretcher_hand.active")
def stretcher_hand_active(ctx: Any, actor: Any, targets: list) -> None:
    ally = lowest_hp_ally(actor, ctx)
    if not ally:
        return
    amount = _eval_scaling(25.0, "intelligence*1.5", actor)
    ctx.heal(actor, ally, amount)


@register_passive("enemy_stretcher_hand.passive")
def stretcher_hand_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


# --- Signal Drummer (T1) --- aura: nearby allies +AS (periodic re-application)
@register_passive("enemy_signal_drummer.passive")
def signal_drummer_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 300:
            state["last_tick"] = ctx.current_tick
            allies = allies_in_radius(owner.position_q, owner.position_r, 2, owner, ctx)
            for ally in allies:
                if ally is not owner:
                    ctx.apply_modifier(ally, Modifier(
                        "attack_speed", "add", 12.0, Lifetime.TIMED,
                        "passive:enemy_signal_drummer.aura",
                        expires_at_tick=ctx.current_tick + 350,
                    ))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_signal_drummer.active")
def signal_drummer_active(ctx: Any, actor: Any, targets: list) -> None:
    # Drum roll: buff all allies AS
    allies = list(ctx.allies_of(actor))
    for ally in allies:
        ctx.apply_modifier(ally, Modifier(
            "attack_speed", "add", 15.0, Lifetime.TIMED,
            "ability:enemy_signal_drummer",
            expires_at_tick=ctx.current_tick + 600,
        ))


# --- Pikeman (T2) --- reduced damage from ≥2-hex attackers
@register_passive("enemy_pikeman.passive")
def pikeman_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any, value: float) -> float:
        if event.target is not owner:
            return value
        from src.game.combat import hex_distance
        dist = hex_distance(
            event.attacker.position_q, event.attacker.position_r,
            owner.position_q, owner.position_r,
        )
        if dist >= 2:
            return value * 0.75  # 25% reduction from ranged
        return value

    return EffectBundle(hooks=[
        Hook("on_damage_pre", hook, scope=HookScope.PER_HIT, priority=50),
    ])


@register_active("enemy_pikeman.active")
def pikeman_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(35.0, "strength*1.5", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


# --- Crossbow Levy (T2) --- armor-piercing bolt
@register_active("enemy_crossbow_levy.active")
def crossbow_levy_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(40.0, "strength*1.8", actor)
    # Armor-piercing: apply penetration modifier temporarily
    ctx.apply_modifier(actor, Modifier(
        "penetration", "add", 15.0, Lifetime.TIMED,
        "ability:enemy_crossbow_levy.pen",
        expires_at_tick=ctx.current_tick + 50,
    ))
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


@register_passive("enemy_crossbow_levy.passive")
def crossbow_levy_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("penetration", "add", 5.0, Lifetime.COMBAT, "passive:enemy_crossbow_levy"),
    ])


# --- Field Medic (T2) --- INT heal ally; self-regen
@register_active("enemy_field_medic.active")
def field_medic_active(ctx: Any, actor: Any, targets: list) -> None:
    ally = lowest_hp_ally(actor, ctx)
    if not ally:
        return
    amount = _eval_scaling(30.0, "intelligence*2.0", actor)
    ctx.heal(actor, ally, amount)


@register_passive("enemy_field_medic.passive")
def field_medic_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 300:
            state["last_tick"] = ctx.current_tick
            ctx.heal(owner, owner, owner.max_hp * 0.02)

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


# --- Powder Sapper (T2) --- STR splash charge
@register_active("enemy_powder_sapper.active")
def powder_sapper_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(50.0, "strength*1.8", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor):
            ctx.deal_damage(actor, n, amount * 0.4, SourceTag.ABILITY, damage_type="physical")


@register_passive("enemy_powder_sapper.passive")
def powder_sapper_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


# --- Sergeant-at-Arms (T3) --- +STR per nearby ally; cleave
@register_passive("enemy_sergeant_at_arms.passive")
def sergeant_at_arms_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 600:
            state["last_tick"] = ctx.current_tick
            allies = allies_in_radius(owner.position_q, owner.position_r, 2, owner, ctx)
            nearby_count = len([a for a in allies if a is not owner])
            if nearby_count > 0:
                ctx.apply_modifier(owner, Modifier(
                    "strength", "add", 8.0 * nearby_count, Lifetime.TIMED,
                    "passive:enemy_sergeant_at_arms",
                    expires_at_tick=ctx.current_tick + 600,
                ))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_sergeant_at_arms.active")
def sergeant_at_arms_active(ctx: Any, actor: Any, targets: list) -> None:
    # Cleave: STR damage to primary + adjacent enemies
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(50.0, "strength*1.6", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor):
            ctx.deal_damage(actor, n, amount * 0.5, SourceTag.ABILITY, damage_type="physical")


# --- Field Chaplain (T3) --- AOE heal around self
@register_active("enemy_field_chaplain.active")
def field_chaplain_active(ctx: Any, actor: Any, targets: list) -> None:
    allies = allies_in_radius(actor.position_q, actor.position_r, 2, actor, ctx)
    amount = _eval_scaling(30.0, "intelligence*1.5", actor)
    for ally in allies:
        ctx.heal(actor, ally, amount)


@register_passive("enemy_field_chaplain.passive")
def field_chaplain_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


# --- Standard ****** --- aura: allies +STR/+INT (periodic re-application)
@register_passive("enemy_standard_bearer.passive")
def standard_bearer_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 300:
            state["last_tick"] = ctx.current_tick
            allies = allies_in_radius(owner.position_q, owner.position_r, 2, owner, ctx)
            for ally in allies:
                if ally is not owner:
                    ctx.apply_modifier(ally, Modifier(
                        "strength", "add", 8.0, Lifetime.TIMED,
                        "passive:enemy_standard_bearer.aura",
                        expires_at_tick=ctx.current_tick + 350,
                    ))
                    ctx.apply_modifier(ally, Modifier(
                        "intelligence", "add", 8.0, Lifetime.TIMED,
                        "passive:enemy_standard_bearer.aura",
                        expires_at_tick=ctx.current_tick + 350,
                    ))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_standard_bearer.active")
def standard_bearer_active(ctx: Any, actor: Any, targets: list) -> None:
    # Rally: grant all allies STR/INT buff
    allies = list(ctx.allies_of(actor))
    for ally in allies:
        ctx.apply_modifier(ally, Modifier(
            "strength", "add", 12.0, Lifetime.TIMED,
            "ability:enemy_standard_bearer",
            expires_at_tick=ctx.current_tick + 600,
        ))


# --- Heavy Knight (T4) --- self-shield every 600 ticks
@register_passive("enemy_heavy_knight.passive")
def heavy_knight_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 600:
            state["last_tick"] = ctx.current_tick
            ctx.apply_modifier(owner, Modifier(
                "armor", "add", 40.0, Lifetime.TIMED,
                "passive:enemy_heavy_knight.shield",
                expires_at_tick=ctx.current_tick + 400,
            ))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_heavy_knight.active")
def heavy_knight_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(50.0, "strength*1.6", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


# --- Steam Engineer (T4) --- deploy turret (summon)
@register_active("enemy_steam_engineer.active")
def steam_engineer_active(ctx: Any, actor: Any, targets: list) -> None:
    from src.game.piece import Piece
    turret = Piece(
        id=f"{actor.id}_turret_{ctx.current_tick}",
        base_stats={
            "max_hp": actor.max_hp * 0.25,
            "strength": 0,
            "intelligence": actor.stat("intelligence") * 0.5,
            "armor": 20,
            "resistance": 20,
            "attack_speed": 80,
            "mana_regen": 0,
            "move_speed": 0,
            "threat": 10,
            "attack_range": 3,
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
    turret.hp = turret.base_stats["max_hp"]
    turret.max_hp = turret.base_stats["max_hp"]
    ctx.spawn(turret, actor.position_q + 1, actor.position_r)


@register_passive("enemy_steam_engineer.passive")
def steam_engineer_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


# --- Company Guard (T4) --- taunt (force attacker to target self via threat boost)
@register_passive("enemy_company_guard.passive")
def company_guard_passive(owner: Any) -> EffectBundle:
    # Simulates taunt via very high threat
    return EffectBundle(modifiers=[
        Modifier("threat", "add", 80.0, Lifetime.COMBAT, "passive:enemy_company_guard.taunt"),
    ])


@register_active("enemy_company_guard.active")
def company_guard_active(ctx: Any, actor: Any, targets: list) -> None:
    # Shield wall: gain armor + aggro enemies via threat
    ctx.apply_modifier(actor, Modifier(
        "armor", "add", 40.0, Lifetime.TIMED,
        "ability:enemy_company_guard",
        expires_at_tick=ctx.current_tick + 600,
    ))
    ctx.apply_modifier(actor, Modifier(
        "threat", "add", 50.0, Lifetime.TIMED,
        "ability:enemy_company_guard",
        expires_at_tick=ctx.current_tick + 600,
    ))


# --- Battlemage (T5) --- INT fireball splash
@register_active("enemy_battlemage.active")
def battlemage_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(70.0, "intelligence*2.0", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor):
            ctx.deal_damage(actor, n, amount * 0.5, SourceTag.ABILITY)


@register_passive("enemy_battlemage.passive")
def battlemage_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


# --- Gunslinger (T5) --- autos ricochet to 2nd target
@register_passive("enemy_gunslinger.passive")
def gunslinger_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        for n in neighbors_of(event.target, ctx):
            if ctx.is_enemy(n, owner) and n is not event.target:
                bonus = owner.stat("strength") * 0.3
                ctx.deal_damage(owner, n, bonus, SourceTag.BASIC_ATTACK, damage_type="physical")
                break

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_gunslinger.active")
def gunslinger_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(50.0, "strength*1.8", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


# --- Company Captain (T5) --- mark target → INT-scaled armor/resistance reduction
@register_active("enemy_company_captain.active")
def company_captain_active(ctx: Any, actor: Any, targets: list) -> None:
    target = lowest_hp_enemy(actor, ctx)
    if not target:
        return
    # Mark: reduce target's resistance/armor — scales from INT for stronger debuffs
    armor_reduction = -(8.0 + actor.stat("intelligence") * 0.15)
    resistance_reduction = -(8.0 + actor.stat("intelligence") * 0.15)
    ctx.apply_modifier(target, Modifier(
        "armor", "add", armor_reduction, Lifetime.TIMED,
        "ability:enemy_company_captain.mark",
        expires_at_tick=ctx.current_tick + 600,
    ))
    ctx.apply_modifier(target, Modifier(
        "resistance", "add", resistance_reduction, Lifetime.TIMED,
        "ability:enemy_company_captain.mark",
        expires_at_tick=ctx.current_tick + 600,
    ))


# --- Company Captain (T5) --- Focus Fire: mark hit targets; allies piling on
# a marked target trigger bonus INT magic damage from the captain.
@register_passive("enemy_company_captain.passive")
def company_captain_passive(owner: Any) -> EffectBundle:
    FOCUS_FIRE_DURATION = 600
    # Conservative INT scaling with a modest per-level bump:
    # original L1 0.12·INT, L2 0.15·INT, L3 0.18·INT per ally hit on a marked target.
    level = getattr(owner, "level", 1)
    bonus_coeff = 0.1 * level
    # Marked targets draw the captain's allies onto them (threat = targeting priority).
    threat_bonus = 15.0 * level
    _TRIGGER_TAGS = (SourceTag.BASIC_ATTACK.value, SourceTag.ABILITY.value)
    # Reentrancy guard: the bonus hit re-enters on_damage_dealt; this flag stops
    # it from re-marking the target or chaining bonus-on-bonus.
    state = {"in_bonus": False}

    def hook(ctx: Any, event: Any) -> None:
        if state["in_bonus"]:
            return
        if not owner.alive:
            return
        if event.tag not in _TRIGGER_TAGS:
            return
        attacker = event.attacker
        target = event.target

        # Captain's own attack/ability → mark the struck enemy and raise its
        # threat so the captain's allies focus it (expires with the mark).
        if attacker is owner:
            if target.alive and ctx.is_enemy(owner, target):
                ctx.apply_status(target, "focus_fire",
                                 duration_ticks=FOCUS_FIRE_DURATION,
                                 source_id=owner.id)
                ctx.apply_modifier(target, Modifier(
                    "threat", "add", threat_bonus, Lifetime.TIMED,
                    "passive:enemy_company_captain.focus_fire",
                    expires_at_tick=ctx.current_tick + FOCUS_FIRE_DURATION,
                ))
            return

        # An ally other than the captain hits a marked target → bonus magic dmg.
        if (attacker.is_enemy == owner.is_enemy
                and target.has_status("focus_fire")):
            bonus = owner.stat("intelligence") * bonus_coeff
            if bonus <= 0:
                return
            state["in_bonus"] = True
            try:
                ctx.deal_damage(owner, target, bonus, SourceTag.ABILITY,
                                damage_type="magical")
            finally:
                state["in_bonus"] = False

    return EffectBundle(hooks=[
        Hook("on_damage_dealt", hook, scope=HookScope.PER_HIT),
    ])


# --- Steam Knight (T6) --- every 3rd hit reflect STR damage
@register_passive("enemy_steam_knight.passive")
def steam_knight_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.target is not owner:
            return
        if event.tag == SourceTag.REFLECT.value:
            return  # never reflect a reflection — prevents mutual-reflect recursion
        state["count"] += 1
        if state["count"] % 3 == 0 and event.attacker.alive:
            reflect = owner.stat("strength") * 0.4
            ctx.deal_damage(owner, event.attacker, reflect, SourceTag.REFLECT,
                          damage_type="physical")

    return EffectBundle(hooks=[
        Hook("on_damage_taken", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_steam_knight.active")
def steam_knight_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(60.0, "strength*1.8", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


# --- Riflemaster (T6) --- +range; first auto huge
@register_passive("enemy_riflemaster.passive")
def riflemaster_passive(owner: Any) -> EffectBundle:
    state = {"first_hit": True}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        if state["first_hit"]:
            state["first_hit"] = False
            bonus = owner.stat("strength") * 1.2
            ctx.deal_damage(owner, event.target, bonus, SourceTag.BASIC_ATTACK,
                          damage_type="physical")

    return EffectBundle(
        modifiers=[Modifier("attack_range", "add", 1.0, Lifetime.COMBAT, "passive:enemy_riflemaster")],
        hooks=[Hook("on_attack_landed", hook, scope=HookScope.PER_HIT)],
    )


@register_active("enemy_riflemaster.active")
def riflemaster_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(70.0, "strength*2.0", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


# --- Inquisitor (T6) --- bonus damage vs casters (high INT targets)
@register_passive("enemy_inquisitor.passive")
def inquisitor_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        if event.target.stat("intelligence") > event.target.stat("strength"):
            bonus = max(owner.stat("strength"), owner.stat("intelligence")) * 0.3
            ctx.deal_damage(owner, event.target, bonus, SourceTag.BASIC_ATTACK)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_inquisitor.active")
def inquisitor_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(55.0, "strength*1.2+intelligence*1.2", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)


# --- Hexblade Officer (T6) --- autos bonus INT; empower next autos after cast
@register_passive("enemy_hexblade_officer.passive")
def hexblade_officer_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        bonus = owner.stat("intelligence") * 0.25
        ctx.deal_damage(owner, event.target, bonus, SourceTag.BASIC_ATTACK)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_hexblade_officer.active")
def hexblade_officer_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(60.0, "intelligence*1.8", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    # Empower autos
    ctx.apply_modifier(actor, Modifier(
        "intelligence", "add", 20.0, Lifetime.TIMED,
        "ability:enemy_hexblade_officer.empower",
        expires_at_tick=ctx.current_tick + 600,
    ))


# --- Lord Commander (T7) --- shockwave STR + stun
@register_active("enemy_lord_commander.active")
def lord_commander_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = _eval_scaling(80.0, "strength*2.0", actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 2, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount, SourceTag.ABILITY, damage_type="physical")
        ctx.apply_status(t, "stun", duration_ticks=150, source_id=actor.id)


@register_passive("enemy_lord_commander.passive")
def lord_commander_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("strength", "add", 15.0, Lifetime.COMBAT, "passive:enemy_lord_commander"),
    ])


# --- Iron Maiden (T7) --- +armor on hit; release AOE STR every 600 ticks
@register_passive("enemy_iron_maiden.passive")
def iron_maiden_passive(owner: Any) -> EffectBundle:
    state = {"stacks": 0, "last_release": 0}

    def on_hit(ctx: Any, event: Any) -> None:
        if event.target is not owner:
            return
        state["stacks"] += 1
        ctx.apply_modifier(owner, Modifier(
            "armor", "add", 3.0, Lifetime.TIMED,
            "passive:enemy_iron_maiden.stack",
            expires_at_tick=ctx.current_tick + 600,
        ))

    def on_tick(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_release"] >= 600 and state["stacks"] > 0:
            state["last_release"] = ctx.current_tick
            amount = owner.stat("strength") * 0.5 + state["stacks"] * 5
            enemies = enemies_in_radius(owner.position_q, owner.position_r, 2, owner, ctx)
            for e in enemies:
                ctx.deal_damage(owner, e, amount, SourceTag.ABILITY, damage_type="physical")
            state["stacks"] = 0

    return EffectBundle(hooks=[
        Hook("on_damage_taken", on_hit, scope=HookScope.PER_HIT),
        Hook("on_tick", on_tick, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_iron_maiden.active")
def iron_maiden_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(60.0, "strength*1.8", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


# --- Cannoneer (T8) --- autos splash
@register_passive("enemy_cannoneer.passive")
def cannoneer_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        for n in neighbors_of(event.target, ctx):
            if ctx.is_enemy(n, owner) and n is not event.target:
                bonus = owner.stat("strength") * 0.2
                ctx.deal_damage(owner, n, bonus, SourceTag.BASIC_ATTACK, damage_type="physical")

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_cannoneer.active")
def cannoneer_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(80.0, "strength*2.2", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor):
            ctx.deal_damage(actor, n, amount * 0.4, SourceTag.ABILITY, damage_type="physical")


# --- Spymaster (T8) --- stealth → INT execute (simulated via massive first hit)
@register_active("enemy_spymaster.active")
def spymaster_active(ctx: Any, actor: Any, targets: list) -> None:
    target = lowest_hp_enemy(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(100.0, "intelligence*2.5", actor)
    if target.hp_pct < 0.3:
        amount *= 1.6
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)


@register_passive("enemy_spymaster.passive")
def spymaster_passive(owner: Any) -> EffectBundle:
    state = {"first_hit": True}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        if state["first_hit"]:
            state["first_hit"] = False
            bonus = owner.stat("intelligence") * 1.0
            ctx.deal_damage(owner, event.target, bonus, SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


# --- Hierarch (T8) --- shield whole enemy line (allies get INT-scaled armor buff)
@register_active("enemy_hierarch.active")
def hierarch_active(ctx: Any, actor: Any, targets: list) -> None:
    allies = list(ctx.allies_of(actor))
    # Shield magnitude scales from INT — stronger shields for higher-tier/better-geared mages
    armor_bonus = 20.0 + actor.stat("intelligence") * 0.4
    resistance_bonus = 10.0 + actor.stat("intelligence") * 0.2
    for ally in allies:
        ctx.apply_modifier(ally, Modifier(
            "armor", "add", armor_bonus, Lifetime.TIMED,
            "ability:enemy_hierarch.shield",
            expires_at_tick=ctx.current_tick + 500,
        ))
        ctx.apply_modifier(ally, Modifier(
            "resistance", "add", resistance_bonus, Lifetime.TIMED,
            "ability:enemy_hierarch.shield",
            expires_at_tick=ctx.current_tick + 500,
        ))


@register_passive("enemy_hierarch.passive")
def hierarch_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


# --- Arcanist (T9) --- multi-bounce chain lightning with improved scaling
@register_active("enemy_arcanist.active")
def arcanist_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    # Buffed scaling for T9 mage damage dealer
    amount = _eval_scaling(100.0, "intelligence*2.8", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    chain_targets = []
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor) and n is not target and len(chain_targets) < 3:
            chain_targets.append(n)
    for i, ct in enumerate(chain_targets):
        chain_dmg = amount * (0.6 - i * 0.15)
        ctx.deal_damage(actor, ct, max(0, chain_dmg), SourceTag.ABILITY)


@register_passive("enemy_arcanist.passive")
def arcanist_passive(owner: Any) -> EffectBundle:
    # On-attack INT-scaling bonus magic damage — adds consistent DPS for damage-focused mage
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        bonus = owner.stat("intelligence") * 0.35
        ctx.deal_damage(owner, event.target, bonus, SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


# --- Archmagus Imperator (T9) --- STR/INT autos; both-scaling nuke
@register_passive("enemy_archmagus_imperator.passive")
def archmagus_imperator_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 2 == 0:
            bonus = owner.stat("intelligence") * 0.35
            ctx.deal_damage(owner, event.target, bonus, SourceTag.BASIC_ATTACK)
        else:
            bonus = owner.stat("strength") * 0.3
            ctx.deal_damage(owner, event.target, bonus, SourceTag.BASIC_ATTACK,
                          damage_type="physical")

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_archmagus_imperator.active")
def archmagus_imperator_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(80.0, "strength*1.5+intelligence*1.5", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)


# --- Grand Marshal (T10) --- auto-attacker with ramping STR
@register_passive("enemy_grand_marshal.passive")
def grand_marshal_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 600:
            state["last_tick"] = ctx.current_tick
            ctx.apply_modifier(owner, Modifier(
                "strength", "add", 20.0, Lifetime.COMBAT,
                "passive:enemy_grand_marshal.ramp",
            ))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_grand_marshal.active")
def grand_marshal_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(90.0, "strength*2.5", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


# ===========================================================================
# CORRUPTED WILDLIFE — Rain
# ===========================================================================


# --- Blight Lurker (T3, Rain) --- regen when un-attacked (periodic heal)
@register_passive("enemy_blight_lurker.passive")
def blight_lurker_passive(owner: Any) -> EffectBundle:
    state = {"last_hit_tick": 0, "last_heal_tick": 0}

    def on_hit(ctx: Any, event: Any) -> None:
        if event.target is not owner:
            return
        state["last_hit_tick"] = ctx.current_tick

    def on_tick(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_heal_tick"] >= 200:
            state["last_heal_tick"] = ctx.current_tick
            if ctx.current_tick - state["last_hit_tick"] >= 300:
                ctx.heal(owner, owner, owner.max_hp * 0.03)

    return EffectBundle(hooks=[
        Hook("on_damage_taken", on_hit, scope=HookScope.PER_HIT),
        Hook("on_tick", on_tick, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_blight_lurker.active")
def blight_lurker_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(40.0, "strength*1.5", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


# --- Drowned Siren (T4, Rain) --- AOE water → silence
@register_active("enemy_drowned_siren.active")
def drowned_siren_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = _eval_scaling(50.0, "intelligence*1.8", actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 2, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount, SourceTag.ABILITY)
        ctx.apply_status(t, "silence", duration_ticks=200, source_id=actor.id)


@register_passive("enemy_drowned_siren.passive")
def drowned_siren_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


# --- Brineblight Berserker (T5, Rain) --- +AS as HP falls
@register_passive("enemy_brineblight_berserker.passive")
def brineblight_berserker_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.target is not owner:
            return
        if owner.hp_pct < 0.5:
            ctx.apply_modifier(owner, Modifier(
                "attack_speed", "add", 15.0, Lifetime.TIMED,
                "passive:enemy_brineblight_berserker",
                expires_at_tick=ctx.current_tick + 300,
            ))

    return EffectBundle(hooks=[
        Hook("on_damage_taken", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_brineblight_berserker.active")
def brineblight_berserker_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(60.0, "strength*2.0", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


# --- Dredge-Hulk (T7, Rain) --- trail slowing puddles (aura slow)
@register_passive("enemy_dredge_hulk.passive")
def dredge_hulk_passive(owner: Any) -> EffectBundle:
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


@register_active("enemy_dredge_hulk.active")
def dredge_hulk_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(60.0, "strength*1.5+intelligence*1.0", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    ctx.apply_status(target, "slow", duration_ticks=400, stacks=2, source_id=actor.id)


# --- Maw of the Drowned (T9, Rain) --- empowered autos after cast; vortex pull
@register_passive("enemy_maw_of_the_drowned.passive")
def maw_of_the_drowned_passive(owner: Any) -> EffectBundle:
    state = {"empowered": 0}

    def on_cast(ctx: Any, event: Any) -> None:
        if event.caster is not owner:
            return
        state["empowered"] = 3

    def on_attack(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        if state["empowered"] > 0:
            state["empowered"] -= 1
            bonus = owner.stat("intelligence") * 0.5
            ctx.deal_damage(owner, event.target, bonus, SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_cast_complete", on_cast, scope=HookScope.PER_HIT),
        Hook("on_attack_landed", on_attack, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_maw_of_the_drowned.active")
def maw_of_the_drowned_active(ctx: Any, actor: Any, targets: list) -> None:
    # Vortex: damage + root
    amount = _eval_scaling(80.0, "intelligence*2.0", actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * 0.6, SourceTag.ABILITY)
        ctx.apply_status(t, "root", duration_ticks=200, source_id=actor.id)


# --- Flood Tyrant (T10, Rain) --- apex variant
@register_passive("enemy_flood_tyrant.passive")
def flood_tyrant_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 600:
            state["last_tick"] = ctx.current_tick
            ctx.apply_modifier(owner, Modifier(
                "intelligence", "add", 15.0, Lifetime.COMBAT,
                "passive:enemy_flood_tyrant.ramp",
            ))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_flood_tyrant.active")
def flood_tyrant_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = _eval_scaling(90.0, "intelligence*2.2", actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * 0.6, SourceTag.ABILITY)


# ===========================================================================
# CORRUPTED WILDLIFE — Snow
# ===========================================================================


# --- Iron-Collared Hound (T3, Snow) --- autos slow
@register_passive("enemy_iron_collared_hound.passive")
def iron_collared_hound_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        ctx.apply_status(event.target, "slow", duration_ticks=150, stacks=1, source_id=owner.id)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_iron_collared_hound.active")
def iron_collared_hound_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(40.0, "strength*1.6", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    ctx.apply_status(target, "slow", duration_ticks=250, stacks=2, source_id=actor.id)


# --- Cold-Iron Yeti (T4, Snow) --- reduce auto dmg; knockback charge (stun)
@register_passive("enemy_cold_iron_yeti.passive")
def cold_iron_yeti_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any, value: float) -> float:
        if event.target is not owner:
            return value
        return value * 0.85  # 15% damage reduction

    return EffectBundle(hooks=[
        Hook("on_damage_pre", hook, scope=HookScope.PER_HIT, priority=60),
    ])


@register_active("enemy_cold_iron_yeti.active")
def cold_iron_yeti_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(60.0, "strength*1.8", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    ctx.apply_status(target, "stun", duration_ticks=150, source_id=actor.id)


# --- Avalanche Engine (T5, Snow) --- ice-boulder line + slow
@register_active("enemy_avalanche_engine.active")
def avalanche_engine_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(65.0, "strength*1.8", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    ctx.apply_status(target, "slow", duration_ticks=300, stacks=2, source_id=actor.id)
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor):
            ctx.deal_damage(actor, n, amount * 0.5, SourceTag.ABILITY, damage_type="physical")
            ctx.apply_status(n, "slow", duration_ticks=200, stacks=1, source_id=actor.id)
            break


@register_passive("enemy_avalanche_engine.passive")
def avalanche_engine_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


# --- Glacier Goliath (T7, Snow) --- +ARM/+RES per 600 ticks; invuln via massive def
@register_passive("enemy_glacier_goliath.passive")
def glacier_goliath_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 600:
            state["last_tick"] = ctx.current_tick
            ctx.apply_modifier(owner, Modifier(
                "armor", "add", 15.0, Lifetime.COMBAT,
                "passive:enemy_glacier_goliath.arm",
            ))
            ctx.apply_modifier(owner, Modifier(
                "resistance", "add", 15.0, Lifetime.COMBAT,
                "passive:enemy_glacier_goliath.res",
            ))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_glacier_goliath.active")
def glacier_goliath_active(ctx: Any, actor: Any, targets: list) -> None:
    # Ice invuln: massive resistance buff + freeze enemies
    ctx.apply_modifier(actor, Modifier(
        "armor", "add", 100.0, Lifetime.TIMED,
        "ability:enemy_glacier_goliath.invuln",
        expires_at_tick=ctx.current_tick + 300,
    ))
    ctx.apply_modifier(actor, Modifier(
        "resistance", "add", 100.0, Lifetime.TIMED,
        "ability:enemy_glacier_goliath.invuln",
        expires_at_tick=ctx.current_tick + 300,
    ))


# --- Riven Frost-Wyrm (T9, Snow) --- freeze on auto; INT+STR cone
@register_passive("enemy_riven_frost_wyrm.passive")
def riven_frost_wyrm_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 4 == 0:
            ctx.apply_status(event.target, "frozen", duration_ticks=150, source_id=owner.id)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_riven_frost_wyrm.active")
def riven_frost_wyrm_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(80.0, "strength*1.3+intelligence*1.3", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor):
            ctx.deal_damage(actor, n, amount * 0.5, SourceTag.ABILITY)


# --- Frost Sovereign (T10, Snow)
@register_passive("enemy_frost_sovereign.passive")
def frost_sovereign_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 600:
            state["last_tick"] = ctx.current_tick
            ctx.apply_modifier(owner, Modifier(
                "intelligence", "add", 15.0, Lifetime.COMBAT,
                "passive:enemy_frost_sovereign.ramp",
            ))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_frost_sovereign.active")
def frost_sovereign_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = _eval_scaling(90.0, "strength*1.2+intelligence*1.5", actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * 0.6, SourceTag.ABILITY)
        ctx.apply_status(t, "frozen", duration_ticks=150, source_id=actor.id)


# ===========================================================================
# CORRUPTED WILDLIFE — Cloudy
# ===========================================================================


# --- Quarry Crawler (T3, Cloudy) --- gains armor after taking damage
@register_passive("enemy_quarry_crawler.passive")
def quarry_crawler_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.target is not owner:
            return
        ctx.apply_modifier(owner, Modifier(
            "armor", "add", 8.0, Lifetime.TIMED,
            "passive:enemy_quarry_crawler",
            expires_at_tick=ctx.current_tick + 400,
        ))

    return EffectBundle(hooks=[
        Hook("on_damage_taken", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_quarry_crawler.active")
def quarry_crawler_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(40.0, "strength*1.6", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


# --- Slag Sentinel (T4, Cloudy) --- CC-immune (high resistance); root target
@register_passive("enemy_slag_sentinel.passive")
def slag_sentinel_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("resistance", "add", 30.0, Lifetime.COMBAT, "passive:enemy_slag_sentinel"),
        Modifier("armor", "add", 20.0, Lifetime.COMBAT, "passive:enemy_slag_sentinel"),
    ])


@register_active("enemy_slag_sentinel.active")
def slag_sentinel_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(45.0, "strength*1.5", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    ctx.apply_status(target, "root", duration_ticks=250, source_id=actor.id)


# --- Shaftmaw (T5, Cloudy) --- blink INT burst
@register_active("enemy_shaftmaw.active")
def shaftmaw_active(ctx: Any, actor: Any, targets: list) -> None:
    target = lowest_hp_enemy(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(70.0, "intelligence*2.0", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)


@register_passive("enemy_shaftmaw.passive")
def shaftmaw_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


# --- Reaver of the Reach (T7, Cloudy) --- every 4th auto free cast; cleave
@register_passive("enemy_reaver_of_the_reach.passive")
def reaver_of_the_reach_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 4 == 0:
            # Free cleave
            amount = max(owner.stat("strength"), owner.stat("intelligence")) * 0.6
            for n in neighbors_of(event.target, ctx):
                if ctx.is_enemy(n, owner):
                    ctx.deal_damage(owner, n, amount, SourceTag.ABILITY, damage_type="physical")
                    break

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_reaver_of_the_reach.active")
def reaver_of_the_reach_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(70.0, "strength*1.5+intelligence*1.0", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


# --- Quarried Behemoth (T9, Cloudy) --- +STR per auto absorbed; ground-slam
@register_passive("enemy_quarried_behemoth.passive")
def quarried_behemoth_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.target is not owner:
            return
        ctx.apply_modifier(owner, Modifier(
            "strength", "add", 5.0, Lifetime.COMBAT,
            "passive:enemy_quarried_behemoth.stack",
        ))

    return EffectBundle(hooks=[
        Hook("on_damage_taken", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_quarried_behemoth.active")
def quarried_behemoth_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = _eval_scaling(80.0, "strength*2.2", actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 2, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount, SourceTag.ABILITY, damage_type="physical")
        ctx.apply_status(t, "stun", duration_ticks=100, source_id=actor.id)


# --- Stone Warden (T10, Cloudy)
@register_passive("enemy_stone_warden.passive")
def stone_warden_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 600:
            state["last_tick"] = ctx.current_tick
            ctx.apply_modifier(owner, Modifier(
                "armor", "add", 20.0, Lifetime.COMBAT,
                "passive:enemy_stone_warden.ramp",
            ))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_stone_warden.active")
def stone_warden_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = _eval_scaling(80.0, "strength*2.0", actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 2, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount, SourceTag.ABILITY, damage_type="physical")


# ===========================================================================
# CORRUPTED WILDLIFE — Mist
# ===========================================================================


# --- Hollowed Wisp (T3, Mist) --- start with bonus INT; phase hit
@register_passive("enemy_hollowed_wisp.passive")
def hollowed_wisp_passive(owner: Any) -> EffectBundle:
    state = {"first_hit": True}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        if state["first_hit"]:
            state["first_hit"] = False
            bonus = owner.stat("intelligence") * 0.8
            ctx.deal_damage(owner, event.target, bonus, SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_hollowed_wisp.active")
def hollowed_wisp_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(50.0, "intelligence*1.8", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)


# --- Drained Stalker (T4, Mist) --- line-pierce autos
@register_passive("enemy_drained_stalker.passive")
def drained_stalker_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        for n in neighbors_of(event.target, ctx):
            if ctx.is_enemy(n, owner) and n is not event.target:
                bonus = owner.stat("intelligence") * 0.25
                ctx.deal_damage(owner, n, bonus, SourceTag.BASIC_ATTACK)
                break

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_drained_stalker.active")
def drained_stalker_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(50.0, "intelligence*1.8", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)


# --- Caged Banshee (T5, Mist) --- AOE fear
@register_active("enemy_caged_banshee.active")
def caged_banshee_active(ctx: Any, actor: Any, targets: list) -> None:
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx)
    for t in hit_targets:
        ctx.apply_status(t, "fear", duration_ticks=200, source_id=actor.id)
        amount = _eval_scaling(30.0, "intelligence*1.0", actor)
        ctx.deal_damage(actor, t, amount, SourceTag.ABILITY)


@register_passive("enemy_caged_banshee.passive")
def caged_banshee_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


# --- Shroud-Killer (T7, Mist) --- backline dash execute; mana on kill
@register_active("enemy_shroud_killer.active")
def shroud_killer_active(ctx: Any, actor: Any, targets: list) -> None:
    target = lowest_hp_enemy(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(90.0, "strength*2.5", actor)
    if target.hp_pct < 0.3:
        amount *= 1.5
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


@register_passive("enemy_shroud_killer.passive")
def shroud_killer_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.killer is not owner:
            return
        ctx.gain_mana(owner, owner.actives[0].cost * 0.5 if owner.actives else 0)

    return EffectBundle(hooks=[
        Hook("on_kill", hook, scope=HookScope.PER_HIT),
    ])


# --- Sundered Lord (T9, Mist) --- STR/INT autos; AOE haunt
@register_passive("enemy_sundered_lord.passive")
def sundered_lord_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 2 == 0:
            bonus = owner.stat("intelligence") * 0.3
            ctx.deal_damage(owner, event.target, bonus, SourceTag.BASIC_ATTACK)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_sundered_lord.active")
def sundered_lord_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = _eval_scaling(70.0, "strength*1.2+intelligence*1.2", actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * 0.6, SourceTag.ABILITY)
        ctx.apply_status(t, "fear", duration_ticks=150, source_id=actor.id)


# --- Veil Lord (T10, Mist)
@register_passive("enemy_veil_lord.passive")
def veil_lord_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 600:
            state["last_tick"] = ctx.current_tick
            ctx.apply_modifier(owner, Modifier(
                "intelligence", "add", 15.0, Lifetime.COMBAT,
                "passive:enemy_veil_lord.ramp",
            ))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_veil_lord.active")
def veil_lord_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = _eval_scaling(80.0, "intelligence*2.0", actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * 0.6, SourceTag.ABILITY)


# ===========================================================================
# CORRUPTED WILDLIFE — Thunder
# ===========================================================================


# --- Capture-Rig Wolf (T3, Thunder) --- AS burst every 600 ticks
@register_passive("enemy_capture_rig_wolf.passive")
def capture_rig_wolf_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 600:
            state["last_tick"] = ctx.current_tick
            ctx.apply_modifier(owner, Modifier(
                "attack_speed", "add", 30.0, Lifetime.TIMED,
                "passive:enemy_capture_rig_wolf.burst",
                expires_at_tick=ctx.current_tick + 300,
            ))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_capture_rig_wolf.active")
def capture_rig_wolf_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(45.0, "strength*1.6", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


# --- Stormhawk (T4, Thunder) --- autos chain to 2nd
@register_passive("enemy_stormhawk.passive")
def stormhawk_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        for n in neighbors_of(event.target, ctx):
            if ctx.is_enemy(n, owner) and n is not event.target:
                bonus = owner.stat("intelligence") * 0.3
                ctx.deal_damage(owner, n, bonus, SourceTag.BASIC_ATTACK)
                break

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_stormhawk.active")
def stormhawk_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(50.0, "intelligence*1.8", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)


# --- Voltaic Diviner (T5, Thunder) --- chain lightning
@register_active("enemy_voltaic_diviner.active")
def voltaic_diviner_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(65.0, "intelligence*2.0", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    chain_targets = []
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor) and n is not target and len(chain_targets) < 2:
            chain_targets.append(n)
    for i, ct in enumerate(chain_targets):
        chain_dmg = amount * (0.5 - i * 0.15)
        ctx.deal_damage(actor, ct, max(0, chain_dmg), SourceTag.ABILITY)


@register_passive("enemy_voltaic_diviner.passive")
def voltaic_diviner_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


# --- Thunder Bull (T7, Thunder) --- build static; discharge stun
@register_passive("enemy_thunder_bull.passive")
def thunder_bull_passive(owner: Any) -> EffectBundle:
    state = {"stacks": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["stacks"] += 1

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_thunder_bull.active")
def thunder_bull_active(ctx: Any, actor: Any, targets: list) -> None:
    # Discharge: STR damage + stun
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = _eval_scaling(70.0, "strength*2.0", actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    ctx.apply_status(target, "stun", duration_ticks=180, source_id=actor.id)


# --- Caged Storm-Drake (T9, Thunder) --- mana-full autos chain; dive AOE
@register_passive("enemy_caged_storm_drake.passive")
def caged_storm_drake_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        if owner.actives:
            slot = owner.actives[0]
            if slot.current_mana >= slot.cost * 0.8:
                for n in neighbors_of(event.target, ctx):
                    if ctx.is_enemy(n, owner) and n is not event.target:
                        bonus = owner.stat("intelligence") * 0.4
                        ctx.deal_damage(owner, n, bonus, SourceTag.BASIC_ATTACK)
                        break

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_caged_storm_drake.active")
def caged_storm_drake_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = _eval_scaling(80.0, "strength*1.3+intelligence*1.3", actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 2, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount, SourceTag.ABILITY)
        ctx.apply_status(t, "stun", duration_ticks=100, source_id=actor.id)


# --- Storm Tyrant (T10, Thunder)
@register_passive("enemy_storm_tyrant.passive")
def storm_tyrant_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 600:
            state["last_tick"] = ctx.current_tick
            ctx.apply_modifier(owner, Modifier(
                "strength", "add", 12.0, Lifetime.COMBAT,
                "passive:enemy_storm_tyrant.ramp",
            ))
            ctx.apply_modifier(owner, Modifier(
                "intelligence", "add", 12.0, Lifetime.COMBAT,
                "passive:enemy_storm_tyrant.ramp",
            ))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


@register_active("enemy_storm_tyrant.active")
def storm_tyrant_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = _eval_scaling(90.0, "strength*1.3+intelligence*1.3", actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * 0.6, SourceTag.ABILITY)
