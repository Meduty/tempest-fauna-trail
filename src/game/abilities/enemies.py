"""Enemy abilities — all 60 enemies from the roster.

Registered under full roster IDs: `{enemy_id}.active` / `{enemy_id}.passive`.
"""

from __future__ import annotations

from src.game.status import secs

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
    ABILITY_META,
    AbilityMeta,
    Clause,
    MaxOfTerm,
    PctResource,
    ScalingTerm,
    SetByCaller,
    SummonSpec,
    register_active,
    register_passive,
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
CONSCRIPT_BONUS = ScalingTerm("bonus", 0.0, "intelligence*0.5")  # T.36c: int swashbuckler — on-hit magic (V.47)


@register_passive("enemy_conscript.passive")
def conscript_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 4 == 0:
            ctx.deal_damage(owner, event.target, CONSCRIPT_BONUS.eval(owner),
                          SourceTag.BASIC_ATTACK, damage_type="magic")

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_conscript.passive"] = AbilityMeta(
    name="Warded Edge", kind="passive",
    blurb="Every 4th auto-attack deals {bonus} bonus magic damage.",
    terms=(CONSCRIPT_BONUS,), tags=("magic",),
)


CONSCRIPT_DMG = ScalingTerm("damage", 30.0, "intelligence*1.2")  # T.36c: int swashbuckler (V.47)


@register_active("enemy_conscript.active")
def conscript_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, CONSCRIPT_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="magic")


ABILITY_META["enemy_conscript.active"] = AbilityMeta(
    name="Runed Thrust", kind="active",
    blurb="Strike the primary target for {damage} magic damage.",
    terms=(CONSCRIPT_DMG,), tags=("magic",),
)


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


ABILITY_META["enemy_levyman.passive"] = AbilityMeta(
    name="Hardened", kind="passive",
    blurb="Every 6s, permanently gain +25 max HP.",
    tags=("scaling",),
)


LEVYMAN_DMG = ScalingTerm("damage", 25.0, "intelligence*1.04")  # T.36c: int tank (V.47)


@register_active("enemy_levyman.active")
def levyman_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, LEVYMAN_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="magic")


ABILITY_META["enemy_levyman.active"] = AbilityMeta(
    name="Sigil Strike", kind="active",
    blurb="Strike the primary target for {damage} magic damage.",
    terms=(LEVYMAN_DMG,), tags=("magic",),
)


# --- Picket (T1) --- plain auto-attacker (no special ability)
@register_passive("enemy_picket.passive")
def picket_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


ABILITY_META["enemy_picket.passive"] = AbilityMeta(
    name="None", kind="passive",
    blurb="No passive effect — a plain auto-attacker.",
    tags=(),
)


PICKET_DMG = ScalingTerm("damage", 20.0, "strength*0.96")


@register_active("enemy_picket.active")
def picket_active(ctx: Any, actor: Any, targets: list) -> None:
    # No special ability — just a basic attack trigger
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, PICKET_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")


ABILITY_META["enemy_picket.active"] = AbilityMeta(
    name="Jab", kind="active",
    blurb="Strike the primary target for {damage} physical damage.",
    terms=(PICKET_DMG,), tags=("physical",),
)


# --- Stretcher-Hand (T1) --- small fixed heal lowest ally
STRETCHER_HAND_HEAL = ScalingTerm("heal", 25.0, "intelligence*2.38")


@register_active("enemy_stretcher_hand.active")
def stretcher_hand_active(ctx: Any, actor: Any, targets: list) -> None:
    ally = lowest_hp_ally(actor, ctx)
    if not ally:
        return
    ctx.heal(actor, ally, STRETCHER_HAND_HEAL.eval(actor))


ABILITY_META["enemy_stretcher_hand.active"] = AbilityMeta(
    name="Field Dressing", kind="active",
    blurb="Heal the lowest-HP ally for {heal}.",
    terms=(STRETCHER_HAND_HEAL,), tags=("heal",),
)


@register_passive("enemy_stretcher_hand.passive")
def stretcher_hand_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


ABILITY_META["enemy_stretcher_hand.passive"] = AbilityMeta(
    name="None", kind="passive", blurb="No passive effect.", tags=(),
)


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


ABILITY_META["enemy_signal_drummer.passive"] = AbilityMeta(
    name="Marching Beat", kind="passive",
    blurb="Every 3s, grants nearby allies +12 Attack Speed.",
    tags=("buff", "aura"),
)


# T.35b: drum-roll haste scales with the drummer's INT (V.47 dead-INT fix).
SIGNAL_DRUMMER_HASTE = ScalingTerm("haste", 15.0, "intelligence*0.19")


@register_active("enemy_signal_drummer.active")
def signal_drummer_active(ctx: Any, actor: Any, targets: list) -> None:
    # Drum roll: buff all allies AS
    allies = list(ctx.allies_of(actor))
    haste = SIGNAL_DRUMMER_HASTE.eval(actor)
    for ally in allies:
        ctx.apply_modifier(ally, Modifier(
            "attack_speed", "add", haste, Lifetime.TIMED,
            "ability:enemy_signal_drummer",
            expires_at_tick=ctx.current_tick + 600,
        ))


ABILITY_META["enemy_signal_drummer.active"] = AbilityMeta(
    name="Drum Roll", kind="active",
    blurb="Grant the whole team Attack Speed for 6s.",
    clauses=(Clause(template="Grants +{haste} Attack Speed.", terms=(SIGNAL_DRUMMER_HASTE,)),),
    tags=("buff", "team"),
)


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


ABILITY_META["enemy_pikeman.passive"] = AbilityMeta(
    name="Brace", kind="passive",
    blurb="Reduces damage from attackers 2+ hexes away by 25%.",
    tags=("defense",),
)


PIKEMAN_DMG = ScalingTerm("damage", 35.0, "strength*1.2")


@register_active("enemy_pikeman.active")
def pikeman_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, PIKEMAN_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")


ABILITY_META["enemy_pikeman.active"] = AbilityMeta(
    name="Pike Thrust", kind="active",
    blurb="Strike the primary target for {damage} physical damage.",
    terms=(PIKEMAN_DMG,), tags=("physical",),
)


# --- Crossbow Levy (T2) --- armor-piercing bolt
CROSSBOW_LEVY_DMG = ScalingTerm("damage", 40.0, "strength*1.44")


@register_active("enemy_crossbow_levy.active")
def crossbow_levy_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    # Armor-piercing: apply penetration modifier temporarily
    ctx.apply_modifier(actor, Modifier(
        "penetration", "add", 15.0, Lifetime.TIMED,
        "ability:enemy_crossbow_levy.pen",
        expires_at_tick=ctx.current_tick + 50,
    ))
    ctx.deal_damage(actor, target, CROSSBOW_LEVY_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")


ABILITY_META["enemy_crossbow_levy.active"] = AbilityMeta(
    name="Piercing Bolt", kind="active",
    blurb="Fire a bolt at the primary target for {damage} physical damage.",
    terms=(CROSSBOW_LEVY_DMG,),
    clauses=(Clause("Gains +15 Penetration for the hit."),), tags=("physical", "penetration"),
)


@register_passive("enemy_crossbow_levy.passive")
def crossbow_levy_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("penetration", "add", 5.0, Lifetime.COMBAT, "passive:enemy_crossbow_levy"),
    ])


ABILITY_META["enemy_crossbow_levy.passive"] = AbilityMeta(
    name="Bodkin Tips", kind="passive",
    blurb="Grants +5 Penetration for the whole battle.",
    tags=("penetration",),
)


# --- Field Medic (T2) --- INT heal ally; self-regen
FIELD_MEDIC_HEAL = ScalingTerm("heal", 30.0, "intelligence*3.17")


@register_active("enemy_field_medic.active")
def field_medic_active(ctx: Any, actor: Any, targets: list) -> None:
    ally = lowest_hp_ally(actor, ctx)
    if not ally:
        return
    ctx.heal(actor, ally, FIELD_MEDIC_HEAL.eval(actor))


ABILITY_META["enemy_field_medic.active"] = AbilityMeta(
    name="Triage", kind="active",
    blurb="Heal the lowest-HP ally for {heal}.",
    terms=(FIELD_MEDIC_HEAL,), tags=("heal",),
)


_FIELD_MEDIC_REGEN = PctResource("heal", 0.02)


@register_passive("enemy_field_medic.passive")
def field_medic_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 300:
            state["last_tick"] = ctx.current_tick
            ctx.heal(owner, owner, _FIELD_MEDIC_REGEN.eval(owner))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_field_medic.passive"] = AbilityMeta(
    name="Self-Care", kind="passive",
    blurb="Regenerates health over time.",
    clauses=(Clause(template="Heals {heal} HP every 3s.", terms=(_FIELD_MEDIC_REGEN,)),),
    tags=("heal",),
)


# --- Powder Sapper (T2) --- STR splash charge
POWDER_SAPPER_DMG = ScalingTerm("damage", 50.0, "strength*1.44")
_POWDER_SAPPER_SPLASH = 0.4


@register_active("enemy_powder_sapper.active")
def powder_sapper_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = POWDER_SAPPER_DMG.eval(actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor):
            ctx.deal_damage(actor, n, amount * _POWDER_SAPPER_SPLASH, SourceTag.ABILITY,
                            damage_type="physical")


ABILITY_META["enemy_powder_sapper.active"] = AbilityMeta(
    name="Powder Charge", kind="active",
    blurb="Detonate on the primary target for {damage} physical damage.",
    terms=(POWDER_SAPPER_DMG,),
    clauses=(Clause(f"Adjacent enemies take {int(_POWDER_SAPPER_SPLASH * 100)}% splash."),),
    tags=("physical", "aoe"),
)


@register_passive("enemy_powder_sapper.passive")
def powder_sapper_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


ABILITY_META["enemy_powder_sapper.passive"] = AbilityMeta(
    name="None", kind="passive", blurb="No passive effect.", tags=(),
)


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


ABILITY_META["enemy_sergeant_at_arms.passive"] = AbilityMeta(
    name="Rally the Line", kind="passive",
    blurb="Every 6s, gain +8 Strength per nearby ally for 6s.",
    tags=("buff",),
)


SERGEANT_AT_ARMS_DMG = ScalingTerm("damage", 50.0, "strength*1.28+intelligence*0.38")  # T.35b: +INT (V.47)
_SERGEANT_CLEAVE = 0.5


@register_active("enemy_sergeant_at_arms.active")
def sergeant_at_arms_active(ctx: Any, actor: Any, targets: list) -> None:
    # Cleave: STR damage to primary + adjacent enemies
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = SERGEANT_AT_ARMS_DMG.eval(actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor):
            ctx.deal_damage(actor, n, amount * _SERGEANT_CLEAVE, SourceTag.ABILITY,
                            damage_type="physical")


ABILITY_META["enemy_sergeant_at_arms.active"] = AbilityMeta(
    name="Cleave", kind="active",
    blurb="Cleave the primary target for {damage} physical damage.",
    terms=(SERGEANT_AT_ARMS_DMG,),
    clauses=(Clause(f"Adjacent enemies take {int(_SERGEANT_CLEAVE * 100)}% damage."),),
    tags=("physical", "aoe"),
)


# --- Field Chaplain (T3) --- AOE heal around self
FIELD_CHAPLAIN_HEAL = ScalingTerm("heal", 30.0, "intelligence*2.38")


@register_active("enemy_field_chaplain.active")
def field_chaplain_active(ctx: Any, actor: Any, targets: list) -> None:
    allies = allies_in_radius(actor.position_q, actor.position_r, 2, actor, ctx)
    amount = FIELD_CHAPLAIN_HEAL.eval(actor)
    for ally in allies:
        ctx.heal(actor, ally, amount)


ABILITY_META["enemy_field_chaplain.active"] = AbilityMeta(
    name="Benediction", kind="active",
    blurb="Heal all allies within 2 hexes for {heal} each.",
    terms=(FIELD_CHAPLAIN_HEAL,), tags=("heal", "aoe"),
)


@register_passive("enemy_field_chaplain.passive")
def field_chaplain_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


ABILITY_META["enemy_field_chaplain.passive"] = AbilityMeta(
    name="None", kind="passive", blurb="No passive effect.", tags=(),
)


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


ABILITY_META["enemy_standard_bearer.passive"] = AbilityMeta(
    name="Standard Aura", kind="passive",
    blurb="Every 3s, grants nearby allies +8 Strength and +8 Intelligence.",
    tags=("buff", "aura"),
)


# T.35b: rally buff scales with the bearer's INT (V.47 dead-INT fix).
STANDARD_BEARER_BUFF = ScalingTerm("buff", 12.0, "intelligence*0.19")


@register_active("enemy_standard_bearer.active")
def standard_bearer_active(ctx: Any, actor: Any, targets: list) -> None:
    # Rally: grant all allies STR/INT buff
    allies = list(ctx.allies_of(actor))
    buff = STANDARD_BEARER_BUFF.eval(actor)
    for ally in allies:
        ctx.apply_modifier(ally, Modifier(
            "strength", "add", buff, Lifetime.TIMED,
            "ability:enemy_standard_bearer",
            expires_at_tick=ctx.current_tick + 600,
        ))


ABILITY_META["enemy_standard_bearer.active"] = AbilityMeta(
    name="Rally", kind="active",
    blurb="Grant the whole team Strength for 6s.",
    clauses=(Clause(template="Grants +{buff} Strength.", terms=(STANDARD_BEARER_BUFF,)),),
    tags=("buff", "team"),
)


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


ABILITY_META["enemy_heavy_knight.passive"] = AbilityMeta(
    name="Iron Vigil", kind="passive",
    blurb="Every 6s, gain +40 Armor for 4s.",
    tags=("defense",),
)


HEAVY_KNIGHT_DMG = ScalingTerm("damage", 50.0, "strength*1.28")


@register_active("enemy_heavy_knight.active")
def heavy_knight_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, HEAVY_KNIGHT_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")


ABILITY_META["enemy_heavy_knight.active"] = AbilityMeta(
    name="Greatsword", kind="active",
    blurb="Strike the primary target for {damage} physical damage.",
    terms=(HEAVY_KNIGHT_DMG,), tags=("physical",),
)


# --- Steam Engineer (T4) --- deploy turret (summon)
# Turret statline: Magnitude fractions of the engineer + flat literals (SummonSpec, V.46).
_STEAM_TURRET = SummonSpec(stats={
    "max_hp": PctResource("max_hp", 0.25),
    "strength": 0,
    "intelligence": ScalingTerm("intelligence", 0.0, "intelligence*0.79"),
    "armor": 20,
    "resistance": 20,
    "attack_speed": 80,
    "mana_regen": 0,
    "move_speed": 0,
    "threat": 10,
    "attack_range": 3,
    "crit_chance": 0.0,
    "penetration": 0,
    "penetration_pct": 0.0,
})


@register_active("enemy_steam_engineer.active")
def steam_engineer_active(ctx: Any, actor: Any, targets: list) -> None:
    from src.game.piece import Piece
    turret = Piece(
        id=f"{actor.id}_turret_{ctx.current_tick}",
        base_stats=_STEAM_TURRET.eval(actor),
        affinity=actor.affinity,
        is_enemy=actor.is_enemy,
        summon=True,
        summon_owner_id=actor.id,
        summon_expires_tick=ctx.current_tick + 1200,
    )
    turret.hp = turret.base_stats["max_hp"]
    turret.max_hp = turret.base_stats["max_hp"]
    ctx.spawn(turret, actor.position_q + 1, actor.position_r)


ABILITY_META["enemy_steam_engineer.active"] = AbilityMeta(
    name="Deploy Turret", kind="active",
    blurb="Deploy a turret that fights for 12s.",
    clauses=(Clause("The turret has 25% of your max HP and attacks with 50% of your Intelligence."),),
    tags=("summon",),
)


@register_passive("enemy_steam_engineer.passive")
def steam_engineer_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


ABILITY_META["enemy_steam_engineer.passive"] = AbilityMeta(
    name="None", kind="passive", blurb="No passive effect.", tags=(),
)


# --- Company Guard (T4) --- taunt (force attacker to target self via threat boost)
@register_passive("enemy_company_guard.passive")
def company_guard_passive(owner: Any) -> EffectBundle:
    # Simulates taunt via very high threat
    return EffectBundle(modifiers=[
        Modifier("threat", "add", 80.0, Lifetime.COMBAT, "passive:enemy_company_guard.taunt"),
    ])


ABILITY_META["enemy_company_guard.passive"] = AbilityMeta(
    name="Bodyguard", kind="passive",
    blurb="High threat (+80) draws enemy attacks onto itself.",
    tags=("taunt",),
)


# T.35b: brace armor scales with the guard's INT (V.47 — hybrid tank, INT via kit).
COMPANY_GUARD_ARMOR = ScalingTerm("armor", 40.0, "intelligence*0.32")


@register_active("enemy_company_guard.active")
def company_guard_active(ctx: Any, actor: Any, targets: list) -> None:
    # Shield wall: gain armor + aggro enemies via threat
    ctx.apply_modifier(actor, Modifier(
        "armor", "add", COMPANY_GUARD_ARMOR.eval(actor), Lifetime.TIMED,
        "ability:enemy_company_guard",
        expires_at_tick=ctx.current_tick + 600,
    ))
    ctx.apply_modifier(actor, Modifier(
        "threat", "add", 50.0, Lifetime.TIMED,
        "ability:enemy_company_guard",
        expires_at_tick=ctx.current_tick + 600,
    ))


ABILITY_META["enemy_company_guard.active"] = AbilityMeta(
    name="Shield Wall", kind="active",
    blurb="Brace for 6s, gaining +50 threat to draw fire.",
    clauses=(Clause(template="Gains +{armor} Armor.", terms=(COMPANY_GUARD_ARMOR,)),),
    tags=("defense", "taunt"),
)


# --- Battlemage (T5) --- INT fireball splash
BATTLEMAGE_DMG = ScalingTerm("damage", 70.0, "intelligence*3.8")
_BATTLEMAGE_SPLASH = 0.5


@register_active("enemy_battlemage.active", priority=2)
def battlemage_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = BATTLEMAGE_DMG.eval(actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor):
            ctx.deal_damage(actor, n, amount * _BATTLEMAGE_SPLASH, SourceTag.ABILITY)


ABILITY_META["enemy_battlemage.active"] = AbilityMeta(
    name="Fireball", kind="active",
    blurb="Hurl a fireball at the primary target for {damage} magic damage.",
    terms=(BATTLEMAGE_DMG,),
    clauses=(Clause(f"Adjacent enemies take {int(_BATTLEMAGE_SPLASH * 100)}% splash."),),
    tags=("magic", "aoe"),
)


# --- Battlemage — Arcane Nova (AoE INT dmg) ---
BATTLEMAGE_NOVA = ScalingTerm("damage", 45.0, "intelligence*2.66")


@register_active("enemy_battlemage.active2")
def enemy_battlemage_active2(ctx: Any, actor: Any, targets: list) -> None:
    for e in enemies_in_radius(actor.position_q, actor.position_r, 2, actor, ctx):
        ctx.deal_damage(actor, e, BATTLEMAGE_NOVA.eval(actor), SourceTag.ABILITY, damage_type="magical")


ABILITY_META["enemy_battlemage.active2"] = AbilityMeta(
    name="Arcane Nova", kind="active",
    blurb="Detonate arcane force for {damage} magic damage to all enemies within 2 hexes.",
    terms=(BATTLEMAGE_NOVA,), tags=("magic", "aoe"),
)


@register_passive("enemy_battlemage.passive")
def battlemage_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


ABILITY_META["enemy_battlemage.passive"] = AbilityMeta(
    name="None", kind="passive", blurb="No passive effect.", tags=(),
)


# --- Gunslinger (T5) --- autos ricochet to 2nd target
GUNSLINGER_RICOCHET = ScalingTerm("bonus", 0.0, "strength*0.24")


@register_passive("enemy_gunslinger.passive")
def gunslinger_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        for n in neighbors_of(event.target, ctx):
            if ctx.is_enemy(n, owner) and n is not event.target:
                ctx.deal_damage(owner, n, GUNSLINGER_RICOCHET.eval(owner),
                                SourceTag.BASIC_ATTACK, damage_type="physical")
                break

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_gunslinger.passive"] = AbilityMeta(
    name="Ricochet", kind="passive",
    blurb="Auto-attacks ricochet to a nearby enemy for {bonus} physical damage.",
    terms=(GUNSLINGER_RICOCHET,), tags=("physical",),
)


GUNSLINGER_DMG = ScalingTerm("damage", 50.0, "strength*1.44")


@register_active("enemy_gunslinger.active")
def gunslinger_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, GUNSLINGER_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")


ABILITY_META["enemy_gunslinger.active"] = AbilityMeta(
    name="Deadeye Shot", kind="active",
    blurb="Shoot the primary target for {damage} physical damage.",
    terms=(GUNSLINGER_DMG,), tags=("physical",),
)


# --- Company Captain (T5) --- mark target → INT-scaled armor/resistance reduction
# Shred magnitude is a positive ScalingTerm; the handler applies it as a negative
# modifier (the scaling grammar has no negative-coeff form). A1/V.46.
COMPANY_CAPTAIN_SHRED = ScalingTerm("shred", 8.0, "intelligence*0.24")


@register_active("enemy_company_captain.active")
def company_captain_active(ctx: Any, actor: Any, targets: list) -> None:
    target = lowest_hp_enemy(actor, ctx)
    if not target:
        return
    # Mark: reduce target's resistance/armor — scales from INT for stronger debuffs
    armor_reduction = -COMPANY_CAPTAIN_SHRED.eval(actor)
    resistance_reduction = -COMPANY_CAPTAIN_SHRED.eval(actor)
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


ABILITY_META["enemy_company_captain.active"] = AbilityMeta(
    name="Mark Target", kind="active",
    blurb="Mark the lowest-HP enemy, shredding its Armor and Resistance for 6s.",
    clauses=(Clause(template="Reduces both by {shred}.", terms=(COMPANY_CAPTAIN_SHRED,)),),
    tags=("debuff",),
)


# --- Company Captain (T5) --- Focus Fire: mark hit targets; allies piling on
# a marked target trigger bonus INT magic damage from the captain.
# Per-LEVEL INT rate is a ScalingTerm; the handler multiplies by level (the
# coeff is level-dependent, which a static scaling string can't hold). A1/V.46.
COMPANY_CAPTAIN_FOCUS_BONUS = ScalingTerm("bonus", 0.0, "intelligence*0.15")


@register_passive("enemy_company_captain.passive")
def company_captain_passive(owner: Any) -> EffectBundle:
    FOCUS_FIRE_DURATION = secs(6)
    # Conservative INT scaling with a modest per-level bump:
    # original L1 0.12·INT, L2 0.15·INT, L3 0.18·INT per ally hit on a marked target.
    level = getattr(owner, "level", 1)
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
            bonus = COMPANY_CAPTAIN_FOCUS_BONUS.eval(owner) * level
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


ABILITY_META["enemy_company_captain.passive"] = AbilityMeta(
    name="Focus Fire", kind="passive",
    blurb="The Captain's strikes mark enemies and raise their threat; allies hitting a marked target trigger bonus magic damage.",
    clauses=(Clause(template="Bonus = {bonus} magic damage per Captain level.",
                    terms=(COMPANY_CAPTAIN_FOCUS_BONUS,)),),
    tags=("magic", "debuff"),
)


# --- Steam Knight (T6) --- every 3rd hit reflect STR damage
STEAM_KNIGHT_REFLECT = ScalingTerm("bonus", 0.0, "strength*0.32")


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
            ctx.deal_damage(owner, event.attacker, STEAM_KNIGHT_REFLECT.eval(owner),
                          SourceTag.REFLECT, damage_type="physical")

    return EffectBundle(hooks=[
        Hook("on_damage_taken", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_steam_knight.passive"] = AbilityMeta(
    name="Steam Vent", kind="passive",
    blurb="Every 3rd hit taken reflects {bonus} physical damage to the attacker.",
    terms=(STEAM_KNIGHT_REFLECT,), tags=("physical", "reflect"),
)


STEAM_KNIGHT_DMG = ScalingTerm("damage", 60.0, "strength*1.44")


@register_active("enemy_steam_knight.active")
def steam_knight_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, STEAM_KNIGHT_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")


ABILITY_META["enemy_steam_knight.active"] = AbilityMeta(
    name="Piston Strike", kind="active",
    blurb="Strike the primary target for {damage} physical damage.",
    terms=(STEAM_KNIGHT_DMG,), tags=("physical",),
)


# --- Riflemaster (T6) --- +range; first auto huge
RIFLEMASTER_FIRST = ScalingTerm("bonus", 0.0, "strength*0.96")


@register_passive("enemy_riflemaster.passive")
def riflemaster_passive(owner: Any) -> EffectBundle:
    state = {"first_hit": True}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        if state["first_hit"]:
            state["first_hit"] = False
            ctx.deal_damage(owner, event.target, RIFLEMASTER_FIRST.eval(owner),
                          SourceTag.BASIC_ATTACK, damage_type="physical")

    return EffectBundle(
        modifiers=[Modifier("attack_range", "add", 1.0, Lifetime.COMBAT, "passive:enemy_riflemaster")],
        hooks=[Hook("on_attack_landed", hook, scope=HookScope.PER_HIT)],
    )


ABILITY_META["enemy_riflemaster.passive"] = AbilityMeta(
    name="Long Shot", kind="passive",
    blurb="Grants +1 attack range; the first auto-attack deals {bonus} bonus physical damage.",
    terms=(RIFLEMASTER_FIRST,), tags=("physical",),
)


RIFLEMASTER_DMG = ScalingTerm("damage", 70.0, "strength*1.6")


@register_active("enemy_riflemaster.active")
def riflemaster_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, RIFLEMASTER_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")


ABILITY_META["enemy_riflemaster.active"] = AbilityMeta(
    name="Aimed Shot", kind="active",
    blurb="Take aim at the primary target for {damage} physical damage.",
    terms=(RIFLEMASTER_DMG,), tags=("physical",),
)


# --- Inquisitor (T6) --- bonus damage vs casters (high INT targets)
# Bonus uses max(STR, INT) → MaxOfTerm (V.46). The vs-caster gate is a target
# predicate (reads target STR/INT — same stat names the term covers).
INQUISITOR_BONUS = MaxOfTerm("bonus", 0.3, ("strength", "intelligence"))


@register_passive("enemy_inquisitor.passive")
def inquisitor_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        if event.target.stat("intelligence") > event.target.stat("strength"):
            ctx.deal_damage(owner, event.target, INQUISITOR_BONUS.eval(owner), SourceTag.BASIC_ATTACK)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_inquisitor.passive"] = AbilityMeta(
    name="Witch Hunter", kind="passive",
    blurb="Auto-attacks against caster-type targets deal {bonus} bonus magic damage.",
    terms=(INQUISITOR_BONUS,),
    tags=("magic",),
)


INQUISITOR_DMG = ScalingTerm("damage", 55.0, "strength*0.96+intelligence*2.28")


@register_active("enemy_inquisitor.active")
def inquisitor_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, INQUISITOR_DMG.eval(actor), SourceTag.ABILITY)


ABILITY_META["enemy_inquisitor.active"] = AbilityMeta(
    name="Smite", kind="active",
    blurb="Smite the primary target for {damage} hybrid magic damage.",
    terms=(INQUISITOR_DMG,), tags=("magic",),
)


# --- Hexblade Officer (T6) --- autos bonus INT; empower next autos after cast
HEXBLADE_OFFICER_BONUS = ScalingTerm("bonus", 0.0, "intelligence*0.4")


@register_passive("enemy_hexblade_officer.passive")
def hexblade_officer_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        ctx.deal_damage(owner, event.target, HEXBLADE_OFFICER_BONUS.eval(owner),
                        SourceTag.BASIC_ATTACK)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_hexblade_officer.passive"] = AbilityMeta(
    name="Hexed Blade", kind="passive",
    blurb="Auto-attacks deal {bonus} bonus magic damage.",
    terms=(HEXBLADE_OFFICER_BONUS,), tags=("magic",),
)


HEXBLADE_OFFICER_DMG = ScalingTerm("damage", 60.0, "intelligence*3.42")


@register_active("enemy_hexblade_officer.active")
def hexblade_officer_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, HEXBLADE_OFFICER_DMG.eval(actor), SourceTag.ABILITY)
    # Empower autos
    ctx.apply_modifier(actor, Modifier(
        "intelligence", "add", 20.0, Lifetime.TIMED,
        "ability:enemy_hexblade_officer.empower",
        expires_at_tick=ctx.current_tick + 600,
    ))


ABILITY_META["enemy_hexblade_officer.active"] = AbilityMeta(
    name="Hex Bolt", kind="active",
    blurb="Blast the primary target for {damage} magic damage.",
    terms=(HEXBLADE_OFFICER_DMG,),
    clauses=(Clause("Gain +20 Intelligence for 6s, empowering autos."),), tags=("magic", "buff"),
)


# --- Lord Commander (T7) --- shockwave STR + stun
LORD_COMMANDER_DMG = ScalingTerm("damage", 80.0, "strength*1.6")


@register_active("enemy_lord_commander.active")
def lord_commander_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = LORD_COMMANDER_DMG.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 2, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount, SourceTag.ABILITY, damage_type="physical")
        ctx.apply_status(t, "stun", duration_ticks=secs(3), source_id=actor.id)


ABILITY_META["enemy_lord_commander.active"] = AbilityMeta(
    name="Commanding Shockwave", kind="active",
    blurb="Unleash a shockwave for {damage} physical damage to all enemies within 2 hexes.",
    terms=(LORD_COMMANDER_DMG,),
    clauses=(Clause("Stuns struck enemies for 1.5s."),), tags=("physical", "aoe", "stun"),
)


@register_passive("enemy_lord_commander.passive")
def lord_commander_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("strength", "add", 15.0, Lifetime.COMBAT, "passive:enemy_lord_commander"),
    ])


ABILITY_META["enemy_lord_commander.passive"] = AbilityMeta(
    name="Command Presence", kind="passive",
    blurb="Grants +15 Strength for the whole battle.",
    tags=("buff",),
)


# --- Iron Maiden (T7) --- +armor on hit; release AOE STR every 600 ticks
# Spike release = STR*0.5 (ScalingTerm) + 5 per stored stack (SetByCaller, V.46).
IRON_MAIDEN_SPIKE = ScalingTerm("spike", 0.0, "strength*0.4+intelligence*0.32")  # T.35b: +INT (V.47)
IRON_MAIDEN_PER_STACK = SetByCaller("per_stack", 0.0, 5.0, "stacks")


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
            amount = (
                IRON_MAIDEN_SPIKE.eval(owner)
                + IRON_MAIDEN_PER_STACK.eval(owner, caller={"stacks": state["stacks"]})
            )
            enemies = enemies_in_radius(owner.position_q, owner.position_r, 2, owner, ctx)
            for e in enemies:
                ctx.deal_damage(owner, e, amount, SourceTag.ABILITY, damage_type="physical")
            state["stacks"] = 0

    return EffectBundle(hooks=[
        Hook("on_damage_taken", on_hit, scope=HookScope.PER_HIT),
        Hook("on_tick", on_tick, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_iron_maiden.passive"] = AbilityMeta(
    name="Spike Mantle", kind="passive",
    blurb="Each hit taken grants +3 Armor for 6s and stores a spike.",
    clauses=(Clause(template="Every 6s, releases stored spikes as AoE physical damage ({spike} + {per_stack} per stored stack).",
                    terms=(IRON_MAIDEN_SPIKE, IRON_MAIDEN_PER_STACK)),),
    tags=("defense", "physical", "aoe"),
)


IRON_MAIDEN_DMG = ScalingTerm("damage", 60.0, "strength*1.44")


@register_active("enemy_iron_maiden.active")
def iron_maiden_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, IRON_MAIDEN_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")


ABILITY_META["enemy_iron_maiden.active"] = AbilityMeta(
    name="Impale", kind="active",
    blurb="Impale the primary target for {damage} physical damage.",
    terms=(IRON_MAIDEN_DMG,), tags=("physical",),
)


# --- Cannoneer (T8) --- autos splash
CANNONEER_SPLASH_BONUS = ScalingTerm("bonus", 0.0, "strength*0.16")


@register_passive("enemy_cannoneer.passive")
def cannoneer_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        for n in neighbors_of(event.target, ctx):
            if ctx.is_enemy(n, owner) and n is not event.target:
                ctx.deal_damage(owner, n, CANNONEER_SPLASH_BONUS.eval(owner),
                                SourceTag.BASIC_ATTACK, damage_type="physical")

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_cannoneer.passive"] = AbilityMeta(
    name="Scattershot", kind="passive",
    blurb="Auto-attacks splash {bonus} physical damage to nearby enemies.",
    terms=(CANNONEER_SPLASH_BONUS,), tags=("physical", "aoe"),
)


CANNONEER_DMG = ScalingTerm("damage", 80.0, "strength*1.76")
_CANNONEER_SPLASH = 0.4


@register_active("enemy_cannoneer.active")
def cannoneer_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = CANNONEER_DMG.eval(actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor):
            ctx.deal_damage(actor, n, amount * _CANNONEER_SPLASH, SourceTag.ABILITY,
                            damage_type="physical")


ABILITY_META["enemy_cannoneer.active"] = AbilityMeta(
    name="Cannon Blast", kind="active",
    blurb="Fire a cannonball at the primary target for {damage} physical damage.",
    terms=(CANNONEER_DMG,),
    clauses=(Clause(f"Adjacent enemies take {int(_CANNONEER_SPLASH * 100)}% splash."),),
    tags=("physical", "aoe"),
)


# --- Spymaster (T8) --- stealth → INT execute (simulated via massive first hit)
SPYMASTER_DMG = ScalingTerm("damage", 100.0, "intelligence*4.75")
_SPYMASTER_EXECUTE_MULT = 1.6


@register_active("enemy_spymaster.active")
def spymaster_active(ctx: Any, actor: Any, targets: list) -> None:
    target = lowest_hp_enemy(actor, ctx)
    if not target:
        return
    amount = SPYMASTER_DMG.eval(actor)
    if target.hp_pct < 0.3:
        amount *= _SPYMASTER_EXECUTE_MULT
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)


ABILITY_META["enemy_spymaster.active"] = AbilityMeta(
    name="Assassinate", kind="active",
    blurb="Strike the lowest-HP enemy for {damage} magic damage.",
    terms=(SPYMASTER_DMG,),
    clauses=(Clause(f"Deals +{int((_SPYMASTER_EXECUTE_MULT - 1) * 100)}% to targets below 30% HP."),),
    tags=("magic", "execute"),
)


SPYMASTER_FIRST = ScalingTerm("bonus", 0.0, "intelligence*1.58")


@register_passive("enemy_spymaster.passive")
def spymaster_passive(owner: Any) -> EffectBundle:
    state = {"first_hit": True}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        if state["first_hit"]:
            state["first_hit"] = False
            ctx.deal_damage(owner, event.target, SPYMASTER_FIRST.eval(owner), SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_spymaster.passive"] = AbilityMeta(
    name="Opening Strike", kind="passive",
    blurb="The first auto-attack deals {bonus} bonus magic damage.",
    terms=(SPYMASTER_FIRST,), tags=("magic",),
)


# --- Hierarch (T8) --- shield whole enemy line (allies get INT-scaled armor buff)
# INT-scaled armor/res buff → ScalingTerms the handler + clause both read (A1, V.46).
HIERARCH_ARMOR = ScalingTerm("armor", 20.0, "intelligence*0.64")
HIERARCH_RES = ScalingTerm("res", 10.0, "intelligence*0.32")


@register_active("enemy_hierarch.active")
def hierarch_active(ctx: Any, actor: Any, targets: list) -> None:
    allies = list(ctx.allies_of(actor))
    # Shield magnitude scales from INT — stronger shields for higher-tier/better-geared mages
    armor_bonus = HIERARCH_ARMOR.eval(actor)
    resistance_bonus = HIERARCH_RES.eval(actor)
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


ABILITY_META["enemy_hierarch.active"] = AbilityMeta(
    name="Sanctuary", kind="active",
    blurb="Shield the whole team for 5s.",
    clauses=(Clause(template="Grants Armor ({armor}) and Resistance ({res}).",
                    terms=(HIERARCH_ARMOR, HIERARCH_RES)),),
    tags=("defense", "team"),
)


# On-death: Last Rites — grant all surviving allies an INT-scaled barrier
# (temp absorb pool, not armor) lasting 600·level ticks. Rewards killing the
# Hierarch last; killing it early denies the team-wide barrier.
HIERARCH_BARRIER = ScalingTerm("barrier", 50.0, "intelligence*3.17")


@register_passive("enemy_hierarch.passive")
def hierarch_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.victim is not owner:
            return
        barrier = HIERARCH_BARRIER.eval(owner)
        duration = secs(6) * owner.level
        for ally in ctx.allies_of(owner):
            if ally is owner or not ally.alive:
                continue
            ctx.grant_barrier(ally, barrier, duration_ticks=duration)

    return EffectBundle(hooks=[
        Hook("on_death", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_hierarch.passive"] = AbilityMeta(
    name="Last Rites", kind="passive",
    blurb="On death, grants all surviving allies a barrier.",
    clauses=(Clause(template="Barrier = {barrier}, lasting 6s per level.", terms=(HIERARCH_BARRIER,)),),
    tags=("defense", "team"),
)


# --- Arcanist (T9) --- multi-bounce chain lightning with improved scaling
ARCANIST_DMG = ScalingTerm("damage", 100.0, "intelligence*5.32")


@register_active("enemy_arcanist.active", priority=2)
def arcanist_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    # Buffed scaling for T9 mage damage dealer
    amount = ARCANIST_DMG.eval(actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    chain_targets = []
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor) and n is not target and len(chain_targets) < 3:
            chain_targets.append(n)
    for i, ct in enumerate(chain_targets):
        chain_dmg = amount * (0.6 - i * 0.15)
        ctx.deal_damage(actor, ct, max(0, chain_dmg), SourceTag.ABILITY)


ABILITY_META["enemy_arcanist.active"] = AbilityMeta(
    name="Chain Lightning", kind="active",
    blurb="Strike the primary target for {damage} magic damage.",
    terms=(ARCANIST_DMG,),
    clauses=(Clause("Bounces to up to 3 nearby enemies at 60%, 45%, then 30% damage."),),
    tags=("magic", "aoe"),
)


# --- Arcanist — Mana Burn (dmg + mana denial) ---
ARCANIST_BURN = ScalingTerm("damage", 50.0, "intelligence*2.86")


@register_active("enemy_arcanist.active2")
def enemy_arcanist_active2(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, ARCANIST_BURN.eval(actor), SourceTag.ABILITY, damage_type="magical")
    # Mana denial: drain the target's slot pools (direct slot write, V.48).
    for slot in target.actives:
        slot.current_mana = max(0.0, slot.current_mana - slot.mana_cost * 0.5)


ABILITY_META["enemy_arcanist.active2"] = AbilityMeta(
    name="Mana Burn", kind="active",
    blurb="Sear the target for {damage} magic damage and drain half a cast's worth of mana.",
    terms=(ARCANIST_BURN,), tags=("magic",),
)


ARCANIST_BONUS = ScalingTerm("bonus", 0.0, "intelligence*0.55")


@register_passive("enemy_arcanist.passive")
def arcanist_passive(owner: Any) -> EffectBundle:
    # On-attack INT-scaling bonus magic damage — adds consistent DPS for damage-focused mage
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        ctx.deal_damage(owner, event.target, ARCANIST_BONUS.eval(owner), SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_arcanist.passive"] = AbilityMeta(
    name="Arcane Surge", kind="passive",
    blurb="Auto-attacks deal {bonus} bonus magic damage.",
    terms=(ARCANIST_BONUS,), tags=("magic",),
)


# --- Archmagus Imperator (T9) --- STR/INT autos; both-scaling nuke
ARCHMAGUS_INT_BONUS = ScalingTerm("magic", 0.0, "intelligence*0.55")
ARCHMAGUS_STR_BONUS = ScalingTerm("physical", 0.0, "strength*0.24")


@register_passive("enemy_archmagus_imperator.passive")
def archmagus_imperator_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 2 == 0:
            ctx.deal_damage(owner, event.target, ARCHMAGUS_INT_BONUS.eval(owner),
                            SourceTag.BASIC_ATTACK)
        else:
            ctx.deal_damage(owner, event.target, ARCHMAGUS_STR_BONUS.eval(owner),
                          SourceTag.BASIC_ATTACK, damage_type="physical")

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_archmagus_imperator.passive"] = AbilityMeta(
    name="Spellblade", kind="passive",
    blurb="Auto-attacks alternate {physical} physical (odd) and {magic} magic (even) bonus damage.",
    terms=(ARCHMAGUS_STR_BONUS, ARCHMAGUS_INT_BONUS), tags=("physical", "magic"),
)


ARCHMAGUS_DMG = ScalingTerm("damage", 80.0, "strength*1.2+intelligence*2.86")


@register_active("enemy_archmagus_imperator.active")
def archmagus_imperator_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, ARCHMAGUS_DMG.eval(actor), SourceTag.ABILITY)


ABILITY_META["enemy_archmagus_imperator.active"] = AbilityMeta(
    name="Imperial Nuke", kind="active",
    blurb="Blast the primary target for {damage} hybrid magic damage.",
    terms=(ARCHMAGUS_DMG,), tags=("magic",),
)


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


ABILITY_META["enemy_grand_marshal.passive"] = AbilityMeta(
    name="War Momentum", kind="passive",
    blurb="Every 6s, permanently gain +20 Strength.",
    tags=("scaling", "buff"),
)


GRAND_MARSHAL_DMG = ScalingTerm("damage", 90.0, "strength*2")


@register_active("enemy_grand_marshal.active")
def grand_marshal_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, GRAND_MARSHAL_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")


ABILITY_META["enemy_grand_marshal.active"] = AbilityMeta(
    name="Decapitate", kind="active",
    blurb="Strike the primary target for {damage} physical damage.",
    terms=(GRAND_MARSHAL_DMG,), tags=("physical",),
)


# ===========================================================================
# CORRUPTED WILDLIFE — Rain
# ===========================================================================


# --- Blight Lurker (T3, Rain) --- regen when un-attacked (periodic heal)
_BLIGHT_LURKER_REGEN = PctResource("heal", 0.03)


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
                ctx.heal(owner, owner, _BLIGHT_LURKER_REGEN.eval(owner))

    return EffectBundle(hooks=[
        Hook("on_damage_taken", on_hit, scope=HookScope.PER_HIT),
        Hook("on_tick", on_tick, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_blight_lurker.passive"] = AbilityMeta(
    name="Lurking Regen", kind="passive",
    blurb="Regenerates while it avoids being hit.",
    clauses=(Clause(template="After 3s without taking damage, heals {heal} HP every 2s.",
                    terms=(_BLIGHT_LURKER_REGEN,)),),
    tags=("heal",),
)


BLIGHT_LURKER_DMG = ScalingTerm("damage", 40.0, "strength*1.2")


@register_active("enemy_blight_lurker.active")
def blight_lurker_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, BLIGHT_LURKER_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")


ABILITY_META["enemy_blight_lurker.active"] = AbilityMeta(
    name="Blighted Claw", kind="active",
    blurb="Claw the primary target for {damage} physical damage.",
    terms=(BLIGHT_LURKER_DMG,), tags=("physical",),
)


# --- Drowned Siren (T4, Rain) --- AOE water → silence
DROWNED_SIREN_DMG = ScalingTerm("damage", 50.0, "intelligence*3.42")


@register_active("enemy_drowned_siren.active", priority=2)
def drowned_siren_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = DROWNED_SIREN_DMG.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 2, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount, SourceTag.ABILITY)
        ctx.apply_status(t, "silence", duration_ticks=secs(4), source_id=actor.id)


ABILITY_META["enemy_drowned_siren.active"] = AbilityMeta(
    name="Drowning Song", kind="active",
    blurb="Flood all enemies within 2 hexes for {damage} magic damage each.",
    terms=(DROWNED_SIREN_DMG,),
    clauses=(Clause("Silences struck enemies for 2s."),), tags=("magic", "aoe", "silence"),
)


# --- Drowned Siren — Siren Wail (AoE slow + DoT) ---
SIREN_WAIL = ScalingTerm("damage", 30.0, "intelligence*1.9")


@register_active("enemy_drowned_siren.active2")
def enemy_drowned_siren_active2(ctx: Any, actor: Any, targets: list) -> None:
    for e in enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx):
        ctx.deal_damage(actor, e, SIREN_WAIL.eval(actor), SourceTag.ABILITY, damage_type="magical")
        ctx.apply_status(e, "slow", duration_ticks=secs(4), stacks=1, source_id=actor.id)
        ctx.apply_status(e, "poison", duration_ticks=secs(4), stacks=1, source_id=actor.id)


ABILITY_META["enemy_drowned_siren.active2"] = AbilityMeta(
    name="Siren Wail", kind="active",
    blurb="A keening wail deals {damage} magic damage, slowing and poisoning all enemies within 3 hexes.",
    terms=(SIREN_WAIL,), clauses=(Clause("Slows and poisons for 4s."),), tags=("magic", "aoe", "slow"),
)


@register_passive("enemy_drowned_siren.passive")
def drowned_siren_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


ABILITY_META["enemy_drowned_siren.passive"] = AbilityMeta(
    name="None", kind="passive", blurb="No passive effect.", tags=(),
)


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


ABILITY_META["enemy_brineblight_berserker.passive"] = AbilityMeta(
    name="Bloodfrenzy", kind="passive",
    blurb="Below 50% HP, each hit taken grants +15 Attack Speed for 3s.",
    tags=("buff",),
)


BRINEBLIGHT_BERSERKER_DMG = ScalingTerm("damage", 60.0, "strength*1.6")


@register_active("enemy_brineblight_berserker.active")
def brineblight_berserker_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, BRINEBLIGHT_BERSERKER_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")


ABILITY_META["enemy_brineblight_berserker.active"] = AbilityMeta(
    name="Frenzied Blow", kind="active",
    blurb="Strike the primary target for {damage} physical damage.",
    terms=(BRINEBLIGHT_BERSERKER_DMG,), tags=("physical",),
)


# --- Dredge-Hulk (T7, Rain) --- trail slowing puddles (aura slow)
@register_passive("enemy_dredge_hulk.passive")
def dredge_hulk_passive(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 300:
            state["last_tick"] = ctx.current_tick
            enemies = enemies_in_radius(owner.position_q, owner.position_r, 2, owner, ctx)
            for e in enemies:
                ctx.apply_status(e, "slow", duration_ticks=secs(3.5), stacks=1, source_id=owner.id)

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_dredge_hulk.passive"] = AbilityMeta(
    name="Slurry Trail", kind="passive",
    blurb="Every 3s, slows all enemies within 2 hexes for 3.5s.",
    tags=("slow", "aura"),
)


DREDGE_HULK_DMG = ScalingTerm("damage", 60.0, "strength*1.2+intelligence*1.9")


@register_active("enemy_dredge_hulk.active")
def dredge_hulk_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, DREDGE_HULK_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")
    ctx.apply_status(target, "slow", duration_ticks=secs(4), stacks=2, source_id=actor.id)


ABILITY_META["enemy_dredge_hulk.active"] = AbilityMeta(
    name="Crushing Sweep", kind="active",
    blurb="Sweep the primary target for {damage} physical damage.",
    terms=(DREDGE_HULK_DMG,),
    clauses=(Clause("Applies 2 stacks of slow for 4s."),), tags=("physical", "slow"),
)


# --- Maw of the Drowned (T9, Rain) --- empowered autos after cast; vortex pull
MAW_BONUS = ScalingTerm("bonus", 0.0, "intelligence*0.79")


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
            ctx.deal_damage(owner, event.target, MAW_BONUS.eval(owner), SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_cast_complete", on_cast, scope=HookScope.PER_HIT),
        Hook("on_attack_landed", on_attack, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_maw_of_the_drowned.passive"] = AbilityMeta(
    name="Devouring Tide", kind="passive",
    blurb="After casting, the next 3 auto-attacks each deal {bonus} bonus magic damage.",
    terms=(MAW_BONUS,), tags=("magic",),
)


MAW_DMG = ScalingTerm("damage", 80.0, "strength*1.9+intelligence*1.9")  # T.36c: hybrid tank reads both (V.47/B.24)
_MAW_AOE = 0.6


@register_active("enemy_maw_of_the_drowned.active")
def maw_of_the_drowned_active(ctx: Any, actor: Any, targets: list) -> None:
    # Vortex: damage + root
    amount = MAW_DMG.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * _MAW_AOE, SourceTag.ABILITY)
        ctx.apply_status(t, "root", duration_ticks=secs(4), source_id=actor.id)


ABILITY_META["enemy_maw_of_the_drowned.active"] = AbilityMeta(
    name="Vortex", kind="active",
    blurb=f"Pull all enemies within 3 hexes, each taking {int(_MAW_AOE * 100)}% of {{damage}} magic damage.",
    terms=(MAW_DMG,),
    clauses=(Clause("Roots struck enemies for 2s."),), tags=("magic", "aoe", "root"),
)


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


ABILITY_META["enemy_flood_tyrant.passive"] = AbilityMeta(
    name="Rising Tide", kind="passive",
    blurb="Every 6s, permanently gain +15 Intelligence.",
    tags=("scaling", "buff"),
)


FLOOD_TYRANT_DMG = ScalingTerm("damage", 90.0, "strength*2.1+intelligence*2.09")  # T.36c: hybrid mage reads both (V.47/B.24)
_FLOOD_TYRANT_AOE = 0.6


@register_active("enemy_flood_tyrant.active")
def flood_tyrant_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = FLOOD_TYRANT_DMG.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * _FLOOD_TYRANT_AOE, SourceTag.ABILITY)


ABILITY_META["enemy_flood_tyrant.active"] = AbilityMeta(
    name="Deluge", kind="active",
    blurb=f"Flood all enemies within 3 hexes for {int(_FLOOD_TYRANT_AOE * 100)}% of {{damage}} magic damage.",
    terms=(FLOOD_TYRANT_DMG,), tags=("magic", "aoe"),
)


# ===========================================================================
# CORRUPTED WILDLIFE — Snow
# ===========================================================================


# --- Iron-Collared Hound (T3, Snow) --- autos slow
@register_passive("enemy_iron_collared_hound.passive")
def iron_collared_hound_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        ctx.apply_status(event.target, "slow", duration_ticks=secs(3), stacks=1, source_id=owner.id)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_iron_collared_hound.passive"] = AbilityMeta(
    name="Hamstring", kind="passive",
    blurb="Auto-attacks apply 1 stack of slow for 1.5s.",
    tags=("slow",),
)


IRON_COLLARED_HOUND_DMG = ScalingTerm("damage", 40.0, "strength*1.28")


@register_active("enemy_iron_collared_hound.active")
def iron_collared_hound_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, IRON_COLLARED_HOUND_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")
    ctx.apply_status(target, "slow", duration_ticks=secs(5), stacks=2, source_id=actor.id)


ABILITY_META["enemy_iron_collared_hound.active"] = AbilityMeta(
    name="Savage Bite", kind="active",
    blurb="Bite the primary target for {damage} physical damage.",
    terms=(IRON_COLLARED_HOUND_DMG,),
    clauses=(Clause("Applies 2 stacks of slow for 2.5s."),), tags=("physical", "slow"),
)


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


ABILITY_META["enemy_cold_iron_yeti.passive"] = AbilityMeta(
    name="Frosthide", kind="passive",
    blurb="Reduces all incoming damage by 15%.",
    tags=("defense",),
)


COLD_IRON_YETI_DMG = ScalingTerm("damage", 60.0, "strength*1.44")


@register_active("enemy_cold_iron_yeti.active")
def cold_iron_yeti_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, COLD_IRON_YETI_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")
    ctx.apply_status(target, "stun", duration_ticks=secs(3), source_id=actor.id)


ABILITY_META["enemy_cold_iron_yeti.active"] = AbilityMeta(
    name="Knockback Charge", kind="active",
    blurb="Charge the primary target for {damage} physical damage.",
    terms=(COLD_IRON_YETI_DMG,),
    clauses=(Clause("Stuns for 1.5s."),), tags=("physical", "stun"),
)


# --- Avalanche Engine (T5, Snow) --- ice-boulder line + slow
AVALANCHE_ENGINE_DMG = ScalingTerm("damage", 65.0, "strength*1.44")
_AVALANCHE_LINE = 0.5


@register_active("enemy_avalanche_engine.active")
def avalanche_engine_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = AVALANCHE_ENGINE_DMG.eval(actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    ctx.apply_status(target, "slow", duration_ticks=secs(6), stacks=2, source_id=actor.id)
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor):
            ctx.deal_damage(actor, n, amount * _AVALANCHE_LINE, SourceTag.ABILITY,
                            damage_type="physical")
            ctx.apply_status(n, "slow", duration_ticks=secs(4), stacks=1, source_id=actor.id)
            break


ABILITY_META["enemy_avalanche_engine.active"] = AbilityMeta(
    name="Ice Boulder", kind="active",
    blurb="Roll a boulder into the primary target for {damage} physical damage.",
    terms=(AVALANCHE_ENGINE_DMG,),
    clauses=(Clause(f"Slows the target (2 stacks); one enemy in the line takes {int(_AVALANCHE_LINE * 100)}% and is slowed."),),
    tags=("physical", "aoe", "slow"),
)


@register_passive("enemy_avalanche_engine.passive")
def avalanche_engine_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


ABILITY_META["enemy_avalanche_engine.passive"] = AbilityMeta(
    name="None", kind="passive", blurb="No passive effect.", tags=(),
)


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


ABILITY_META["enemy_glacier_goliath.passive"] = AbilityMeta(
    name="Glacial Growth", kind="passive",
    blurb="Every 6s, permanently gain +15 Armor and +15 Resistance.",
    tags=("defense", "scaling"),
)


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


ABILITY_META["enemy_glacier_goliath.active"] = AbilityMeta(
    name="Ice Carapace", kind="active",
    blurb="Encase in ice for 3s, gaining +100 Armor and +100 Resistance.",
    tags=("defense", "buff"),
)


# --- Riven Frost-Wyrm (T9, Snow) --- freeze on auto; INT+STR cone
@register_passive("enemy_riven_frost_wyrm.passive")
def riven_frost_wyrm_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 4 == 0:
            ctx.apply_status(event.target, "frozen", duration_ticks=secs(3), source_id=owner.id)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_riven_frost_wyrm.passive"] = AbilityMeta(
    name="Rimebite", kind="passive",
    blurb="Every 4th auto-attack freezes the target for 1.5s.",
    tags=("freeze",),
)


RIVEN_FROST_WYRM_DMG = ScalingTerm("damage", 80.0, "strength*1.04+intelligence*2.47")
_RIVEN_CONE = 0.5


@register_active("enemy_riven_frost_wyrm.active")
def riven_frost_wyrm_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = RIVEN_FROST_WYRM_DMG.eval(actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor):
            ctx.deal_damage(actor, n, amount * _RIVEN_CONE, SourceTag.ABILITY)


ABILITY_META["enemy_riven_frost_wyrm.active"] = AbilityMeta(
    name="Frost Cone", kind="active",
    blurb="Breathe frost on the primary target for {damage} hybrid magic damage.",
    terms=(RIVEN_FROST_WYRM_DMG,),
    clauses=(Clause(f"Adjacent enemies take {int(_RIVEN_CONE * 100)}% damage."),),
    tags=("magic", "aoe"),
)


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


ABILITY_META["enemy_frost_sovereign.passive"] = AbilityMeta(
    name="Endless Winter", kind="passive",
    blurb="Every 6s, permanently gain +15 Intelligence.",
    tags=("scaling", "buff"),
)


FROST_SOVEREIGN_DMG = ScalingTerm("damage", 90.0, "strength*0.96+intelligence*2.86")
_FROST_SOVEREIGN_AOE = 0.6


@register_active("enemy_frost_sovereign.active")
def frost_sovereign_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = FROST_SOVEREIGN_DMG.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * _FROST_SOVEREIGN_AOE, SourceTag.ABILITY)
        ctx.apply_status(t, "frozen", duration_ticks=secs(3), source_id=actor.id)


ABILITY_META["enemy_frost_sovereign.active"] = AbilityMeta(
    name="Absolute Zero", kind="active",
    blurb=f"Freeze all enemies within 3 hexes for {int(_FROST_SOVEREIGN_AOE * 100)}% of {{damage}} magic damage.",
    terms=(FROST_SOVEREIGN_DMG,),
    clauses=(Clause("Freezes struck enemies for 1.5s."),), tags=("magic", "aoe", "freeze"),
)


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


ABILITY_META["enemy_quarry_crawler.passive"] = AbilityMeta(
    name="Hardening Shell", kind="passive",
    blurb="Each hit taken grants +8 Armor for 4s.",
    tags=("defense",),
)


QUARRY_CRAWLER_DMG = ScalingTerm("damage", 40.0, "strength*1.28")


@register_active("enemy_quarry_crawler.active")
def quarry_crawler_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, QUARRY_CRAWLER_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")


ABILITY_META["enemy_quarry_crawler.active"] = AbilityMeta(
    name="Pincer", kind="active",
    blurb="Strike the primary target for {damage} physical damage.",
    terms=(QUARRY_CRAWLER_DMG,), tags=("physical",),
)


# --- Slag Sentinel (T4, Cloudy) --- CC-immune (high resistance); root target
@register_passive("enemy_slag_sentinel.passive")
def slag_sentinel_passive(owner: Any) -> EffectBundle:
    return EffectBundle(modifiers=[
        Modifier("resistance", "add", 30.0, Lifetime.COMBAT, "passive:enemy_slag_sentinel"),
        Modifier("armor", "add", 20.0, Lifetime.COMBAT, "passive:enemy_slag_sentinel"),
    ])


ABILITY_META["enemy_slag_sentinel.passive"] = AbilityMeta(
    name="Slag Plating", kind="passive",
    blurb="Grants +30 Resistance and +20 Armor for the whole battle.",
    tags=("defense",),
)


SLAG_SENTINEL_DMG = ScalingTerm("damage", 45.0, "strength*1.2")


@register_active("enemy_slag_sentinel.active")
def slag_sentinel_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, SLAG_SENTINEL_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")
    ctx.apply_status(target, "root", duration_ticks=secs(5), source_id=actor.id)


ABILITY_META["enemy_slag_sentinel.active"] = AbilityMeta(
    name="Molten Grasp", kind="active",
    blurb="Strike the primary target for {damage} physical damage.",
    terms=(SLAG_SENTINEL_DMG,),
    clauses=(Clause("Roots for 2.5s."),), tags=("physical", "root"),
)


# --- Shaftmaw (T5, Cloudy) --- blink INT burst
SHAFTMAW_DMG = ScalingTerm("damage", 70.0, "intelligence*3.8")


@register_active("enemy_shaftmaw.active")
def shaftmaw_active(ctx: Any, actor: Any, targets: list) -> None:
    target = lowest_hp_enemy(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, SHAFTMAW_DMG.eval(actor), SourceTag.ABILITY)


ABILITY_META["enemy_shaftmaw.active"] = AbilityMeta(
    name="Blink Maul", kind="active",
    blurb="Blink to the lowest-HP enemy for {damage} magic damage.",
    terms=(SHAFTMAW_DMG,), tags=("magic",),
)


@register_passive("enemy_shaftmaw.passive")
def shaftmaw_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


ABILITY_META["enemy_shaftmaw.passive"] = AbilityMeta(
    name="None", kind="passive", blurb="No passive effect.", tags=(),
)


# --- Reaver of the Reach (T7, Cloudy) --- every 4th auto free cast; cleave
# Cleave scales on the higher of STR/INT → MaxOfTerm (V.46).
REAVER_CLEAVE = MaxOfTerm("bonus", 0.6, ("strength", "intelligence"))


@register_passive("enemy_reaver_of_the_reach.passive")
def reaver_of_the_reach_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 4 == 0:
            amount = REAVER_CLEAVE.eval(owner)
            for n in neighbors_of(event.target, ctx):
                if ctx.is_enemy(n, owner):
                    ctx.deal_damage(owner, n, amount, SourceTag.ABILITY, damage_type="physical")
                    break

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_reaver_of_the_reach.passive"] = AbilityMeta(
    name="Reaving Sweep", kind="passive",
    blurb="Every 4th auto-attack cleaves a nearby enemy for {bonus}.",
    terms=(REAVER_CLEAVE,),
    tags=("physical",),
)


REAVER_OF_THE_REACH_DMG = ScalingTerm("damage", 70.0, "strength*1.2+intelligence*1.9")


@register_active("enemy_reaver_of_the_reach.active")
def reaver_of_the_reach_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, REAVER_OF_THE_REACH_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")


ABILITY_META["enemy_reaver_of_the_reach.active"] = AbilityMeta(
    name="Reaver Strike", kind="active",
    blurb="Strike the primary target for {damage} hybrid physical damage.",
    terms=(REAVER_OF_THE_REACH_DMG,), tags=("physical",),
)


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


ABILITY_META["enemy_quarried_behemoth.passive"] = AbilityMeta(
    name="Absorb Stone", kind="passive",
    blurb="Each hit taken permanently grants +5 Strength.",
    tags=("scaling", "buff"),
)


QUARRIED_BEHEMOTH_DMG = ScalingTerm("damage", 80.0, "strength*1.76+intelligence*0.38")  # T.35b: +INT (V.47)


@register_active("enemy_quarried_behemoth.active")
def quarried_behemoth_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = QUARRIED_BEHEMOTH_DMG.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 2, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount, SourceTag.ABILITY, damage_type="physical")
        ctx.apply_status(t, "stun", duration_ticks=secs(2), source_id=actor.id)


ABILITY_META["enemy_quarried_behemoth.active"] = AbilityMeta(
    name="Ground Slam", kind="active",
    blurb="Slam for {damage} physical damage to all enemies within 2 hexes.",
    terms=(QUARRIED_BEHEMOTH_DMG,),
    clauses=(Clause("Stuns struck enemies for 1s."),), tags=("physical", "aoe", "stun"),
)


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


ABILITY_META["enemy_stone_warden.passive"] = AbilityMeta(
    name="Bulwark", kind="passive",
    blurb="Every 6s, permanently gain +20 Armor.",
    tags=("defense", "scaling"),
)


STONE_WARDEN_DMG = ScalingTerm("damage", 80.0, "strength*1.6+intelligence*0.38")  # T.35b: +INT (V.47)


@register_active("enemy_stone_warden.active")
def stone_warden_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = STONE_WARDEN_DMG.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 2, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount, SourceTag.ABILITY, damage_type="physical")


ABILITY_META["enemy_stone_warden.active"] = AbilityMeta(
    name="Seismic Slam", kind="active",
    blurb="Slam for {damage} physical damage to all enemies within 2 hexes.",
    terms=(STONE_WARDEN_DMG,), tags=("physical", "aoe"),
)


# ===========================================================================
# CORRUPTED WILDLIFE — Mist
# ===========================================================================


# --- Hollowed Wisp (T3, Mist) --- start with bonus INT; phase hit
HOLLOWED_WISP_FIRST = ScalingTerm("bonus", 0.0, "intelligence*1.26")


@register_passive("enemy_hollowed_wisp.passive")
def hollowed_wisp_passive(owner: Any) -> EffectBundle:
    state = {"first_hit": True}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        if state["first_hit"]:
            state["first_hit"] = False
            ctx.deal_damage(owner, event.target, HOLLOWED_WISP_FIRST.eval(owner), SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_hollowed_wisp.passive"] = AbilityMeta(
    name="Phantom Strike", kind="passive",
    blurb="The first auto-attack deals {bonus} bonus magic damage.",
    terms=(HOLLOWED_WISP_FIRST,), tags=("magic",),
)


HOLLOWED_WISP_DMG = ScalingTerm("damage", 50.0, "intelligence*3.42")


@register_active("enemy_hollowed_wisp.active")
def hollowed_wisp_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, HOLLOWED_WISP_DMG.eval(actor), SourceTag.ABILITY)


ABILITY_META["enemy_hollowed_wisp.active"] = AbilityMeta(
    name="Spirit Bolt", kind="active",
    blurb="Strike the primary target for {damage} magic damage.",
    terms=(HOLLOWED_WISP_DMG,), tags=("magic",),
)


# --- Drained Stalker (T4, Mist) --- line-pierce autos
DRAINED_STALKER_PIERCE = ScalingTerm("bonus", 0.0, "intelligence*0.4")


@register_passive("enemy_drained_stalker.passive")
def drained_stalker_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        for n in neighbors_of(event.target, ctx):
            if ctx.is_enemy(n, owner) and n is not event.target:
                ctx.deal_damage(owner, n, DRAINED_STALKER_PIERCE.eval(owner), SourceTag.BASIC_ATTACK)
                break

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_drained_stalker.passive"] = AbilityMeta(
    name="Soul Pierce", kind="passive",
    blurb="Auto-attacks pierce to one enemy behind the target for {bonus} magic damage.",
    terms=(DRAINED_STALKER_PIERCE,), tags=("magic",),
)


DRAINED_STALKER_DMG = ScalingTerm("damage", 50.0, "intelligence*3.42")


@register_active("enemy_drained_stalker.active")
def drained_stalker_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, DRAINED_STALKER_DMG.eval(actor), SourceTag.ABILITY)


ABILITY_META["enemy_drained_stalker.active"] = AbilityMeta(
    name="Drain Bolt", kind="active",
    blurb="Strike the primary target for {damage} magic damage.",
    terms=(DRAINED_STALKER_DMG,), tags=("magic",),
)


# --- Caged Banshee (T5, Mist) --- AOE fear
CAGED_BANSHEE_DMG = ScalingTerm("damage", 30.0, "intelligence*1.9")


@register_active("enemy_caged_banshee.active")
def caged_banshee_active(ctx: Any, actor: Any, targets: list) -> None:
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx)
    for t in hit_targets:
        ctx.apply_status(t, "fear", duration_ticks=secs(4), source_id=actor.id)
        ctx.deal_damage(actor, t, CAGED_BANSHEE_DMG.eval(actor), SourceTag.ABILITY)


ABILITY_META["enemy_caged_banshee.active"] = AbilityMeta(
    name="Wailing Scream", kind="active",
    blurb="Scream at all enemies within 3 hexes for {damage} magic damage each.",
    terms=(CAGED_BANSHEE_DMG,),
    clauses=(Clause("Fears struck enemies for 2s."),), tags=("magic", "aoe", "fear"),
)


@register_passive("enemy_caged_banshee.passive")
def caged_banshee_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


ABILITY_META["enemy_caged_banshee.passive"] = AbilityMeta(
    name="None", kind="passive", blurb="No passive effect.", tags=(),
)


# --- Shroud-Killer (T7, Mist) --- backline dash execute; mana on kill
SHROUD_KILLER_DMG = ScalingTerm("damage", 90.0, "strength*2")
_SHROUD_KILLER_EXECUTE_MULT = 1.5


@register_active("enemy_shroud_killer.active")
def shroud_killer_active(ctx: Any, actor: Any, targets: list) -> None:
    target = lowest_hp_enemy(actor, ctx)
    if not target:
        return
    amount = SHROUD_KILLER_DMG.eval(actor)
    if target.hp_pct < 0.3:
        amount *= _SHROUD_KILLER_EXECUTE_MULT
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")


ABILITY_META["enemy_shroud_killer.active"] = AbilityMeta(
    name="Shadow Execute", kind="active",
    blurb="Dash to the lowest-HP enemy for {damage} physical damage.",
    terms=(SHROUD_KILLER_DMG,),
    clauses=(Clause(f"Deals +{int((_SHROUD_KILLER_EXECUTE_MULT - 1) * 100)}% to targets below 30% HP."),),
    tags=("physical", "execute"),
)


@register_passive("enemy_shroud_killer.passive")
def shroud_killer_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.killer is not owner:
            return
        ctx.gain_mana(owner, owner.actives[0].mana_cost * 0.5 if owner.actives else 0)

    return EffectBundle(hooks=[
        Hook("on_kill", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_shroud_killer.passive"] = AbilityMeta(
    name="Bloodthirst", kind="passive",
    blurb="Killing an enemy refunds 50% of the ability's mana cost.",
    tags=("mana",),
)


# --- Sundered Lord (T9, Mist) --- STR/INT autos; AOE haunt
SUNDERED_LORD_BONUS = ScalingTerm("bonus", 0.0, "intelligence*0.47")


@register_passive("enemy_sundered_lord.passive")
def sundered_lord_passive(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 2 == 0:
            ctx.deal_damage(owner, event.target, SUNDERED_LORD_BONUS.eval(owner),
                            SourceTag.BASIC_ATTACK)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_sundered_lord.passive"] = AbilityMeta(
    name="Haunting Blade", kind="passive",
    blurb="Every 2nd auto-attack deals {bonus} bonus magic damage.",
    terms=(SUNDERED_LORD_BONUS,), tags=("magic",),
)


SUNDERED_LORD_DMG = ScalingTerm("damage", 70.0, "strength*0.96+intelligence*2.28")
_SUNDERED_LORD_AOE = 0.6


@register_active("enemy_sundered_lord.active")
def sundered_lord_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = SUNDERED_LORD_DMG.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * _SUNDERED_LORD_AOE, SourceTag.ABILITY)
        ctx.apply_status(t, "fear", duration_ticks=secs(3), source_id=actor.id)


ABILITY_META["enemy_sundered_lord.active"] = AbilityMeta(
    name="Haunt", kind="active",
    blurb=f"Haunt all enemies within 3 hexes for {int(_SUNDERED_LORD_AOE * 100)}% of {{damage}} magic damage.",
    terms=(SUNDERED_LORD_DMG,),
    clauses=(Clause("Fears struck enemies for 1.5s."),), tags=("magic", "aoe", "fear"),
)


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


ABILITY_META["enemy_veil_lord.passive"] = AbilityMeta(
    name="Veiled Ascendance", kind="passive",
    blurb="Every 6s, permanently gain +15 Intelligence.",
    tags=("scaling", "buff"),
)


VEIL_LORD_DMG = ScalingTerm("damage", 80.0, "intelligence*3.8")
_VEIL_LORD_AOE = 0.6


@register_active("enemy_veil_lord.active")
def veil_lord_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = VEIL_LORD_DMG.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * _VEIL_LORD_AOE, SourceTag.ABILITY)


ABILITY_META["enemy_veil_lord.active"] = AbilityMeta(
    name="Shroud Burst", kind="active",
    blurb=f"Blast all enemies within 3 hexes for {int(_VEIL_LORD_AOE * 100)}% of {{damage}} magic damage.",
    terms=(VEIL_LORD_DMG,), tags=("magic", "aoe"),
)


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


ABILITY_META["enemy_capture_rig_wolf.passive"] = AbilityMeta(
    name="Static Burst", kind="passive",
    blurb="Every 6s, gain +30 Attack Speed for 3s.",
    tags=("buff",),
)


CAPTURE_RIG_WOLF_DMG = ScalingTerm("damage", 45.0, "strength*1.28")


@register_active("enemy_capture_rig_wolf.active")
def capture_rig_wolf_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, CAPTURE_RIG_WOLF_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")


ABILITY_META["enemy_capture_rig_wolf.active"] = AbilityMeta(
    name="Shock Bite", kind="active",
    blurb="Bite the primary target for {damage} physical damage.",
    terms=(CAPTURE_RIG_WOLF_DMG,), tags=("physical",),
)


# --- Stormhawk (T4, Thunder) --- autos chain to 2nd
STORMHAWK_CHAIN = ScalingTerm("bonus", 0.0, "intelligence*0.47")


@register_passive("enemy_stormhawk.passive")
def stormhawk_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        for n in neighbors_of(event.target, ctx):
            if ctx.is_enemy(n, owner) and n is not event.target:
                ctx.deal_damage(owner, n, STORMHAWK_CHAIN.eval(owner), SourceTag.BASIC_ATTACK)
                break

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_stormhawk.passive"] = AbilityMeta(
    name="Arc Strike", kind="passive",
    blurb="Auto-attacks arc to a nearby enemy for {bonus} magic damage.",
    terms=(STORMHAWK_CHAIN,), tags=("magic",),
)


STORMHAWK_DMG = ScalingTerm("damage", 50.0, "intelligence*3.42")


@register_active("enemy_stormhawk.active")
def stormhawk_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, STORMHAWK_DMG.eval(actor), SourceTag.ABILITY)


ABILITY_META["enemy_stormhawk.active"] = AbilityMeta(
    name="Lightning Dive", kind="active",
    blurb="Dive the primary target for {damage} magic damage.",
    terms=(STORMHAWK_DMG,), tags=("magic",),
)


# --- Voltaic Diviner (T5, Thunder) --- chain lightning
VOLTAIC_DIVINER_DMG = ScalingTerm("damage", 65.0, "intelligence*3.8")


@register_active("enemy_voltaic_diviner.active")
def voltaic_diviner_active(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = VOLTAIC_DIVINER_DMG.eval(actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    chain_targets = []
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor) and n is not target and len(chain_targets) < 2:
            chain_targets.append(n)
    for i, ct in enumerate(chain_targets):
        chain_dmg = amount * (0.5 - i * 0.15)
        ctx.deal_damage(actor, ct, max(0, chain_dmg), SourceTag.ABILITY)


ABILITY_META["enemy_voltaic_diviner.active"] = AbilityMeta(
    name="Chain Lightning", kind="active",
    blurb="Strike the primary target for {damage} magic damage.",
    terms=(VOLTAIC_DIVINER_DMG,),
    clauses=(Clause("Bounces to up to 2 nearby enemies at 50% then 35% damage."),),
    tags=("magic", "aoe"),
)


@register_passive("enemy_voltaic_diviner.passive")
def voltaic_diviner_passive(owner: Any) -> EffectBundle:
    return EffectBundle()


ABILITY_META["enemy_voltaic_diviner.passive"] = AbilityMeta(
    name="None", kind="passive", blurb="No passive effect.", tags=(),
)


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


ABILITY_META["enemy_thunder_bull.passive"] = AbilityMeta(
    name="Static Build", kind="passive",
    blurb="Builds static charge with each auto-attack landed.",
    tags=("tempo",),
)


THUNDER_BULL_DMG = ScalingTerm("damage", 70.0, "strength*1.6")


@register_active("enemy_thunder_bull.active")
def thunder_bull_active(ctx: Any, actor: Any, targets: list) -> None:
    # Discharge: STR damage + stun
    target = primary_target(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, THUNDER_BULL_DMG.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")
    ctx.apply_status(target, "stun", duration_ticks=secs(3.6), source_id=actor.id)


ABILITY_META["enemy_thunder_bull.active"] = AbilityMeta(
    name="Discharge", kind="active",
    blurb="Gore the primary target for {damage} physical damage.",
    terms=(THUNDER_BULL_DMG,),
    clauses=(Clause("Stuns for 1.8s."),), tags=("physical", "stun"),
)


# --- Caged Storm-Drake (T9, Thunder) --- mana-full autos chain; dive AOE
CAGED_STORM_DRAKE_CHAIN = ScalingTerm("bonus", 0.0, "intelligence*0.64")


@register_passive("enemy_caged_storm_drake.passive")
def caged_storm_drake_passive(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        if owner.actives:
            slot = owner.actives[0]
            if slot.current_mana >= slot.mana_cost * 0.8:
                for n in neighbors_of(event.target, ctx):
                    if ctx.is_enemy(n, owner) and n is not event.target:
                        ctx.deal_damage(owner, n, CAGED_STORM_DRAKE_CHAIN.eval(owner),
                                        SourceTag.BASIC_ATTACK)
                        break

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["enemy_caged_storm_drake.passive"] = AbilityMeta(
    name="Storm Conduit", kind="passive",
    blurb="While mana is near-full, auto-attacks chain to a nearby enemy for {bonus} magic damage.",
    terms=(CAGED_STORM_DRAKE_CHAIN,), tags=("magic",),
)


CAGED_STORM_DRAKE_DMG = ScalingTerm("damage", 80.0, "strength*1.04+intelligence*2.47")


@register_active("enemy_caged_storm_drake.active")
def caged_storm_drake_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = CAGED_STORM_DRAKE_DMG.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 2, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount, SourceTag.ABILITY)
        ctx.apply_status(t, "stun", duration_ticks=secs(2), source_id=actor.id)


ABILITY_META["enemy_caged_storm_drake.active"] = AbilityMeta(
    name="Storm Dive", kind="active",
    blurb="Dive for {damage} hybrid magic damage to all enemies within 2 hexes.",
    terms=(CAGED_STORM_DRAKE_DMG,),
    clauses=(Clause("Stuns struck enemies for 1s."),), tags=("magic", "aoe", "stun"),
)


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


ABILITY_META["enemy_storm_tyrant.passive"] = AbilityMeta(
    name="Gathering Storm", kind="passive",
    blurb="Every 6s, permanently gain +12 Strength and +12 Intelligence.",
    tags=("scaling", "buff"),
)


STORM_TYRANT_DMG = ScalingTerm("damage", 90.0, "strength*1.04+intelligence*2.47")
_STORM_TYRANT_AOE = 0.6


@register_active("enemy_storm_tyrant.active")
def storm_tyrant_active(ctx: Any, actor: Any, targets: list) -> None:
    amount = STORM_TYRANT_DMG.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * _STORM_TYRANT_AOE, SourceTag.ABILITY)


ABILITY_META["enemy_storm_tyrant.active"] = AbilityMeta(
    name="Tempest", kind="active",
    blurb=f"Unleash a tempest on all enemies within 3 hexes for {int(_STORM_TYRANT_AOE * 100)}% of {{damage}} magic damage.",
    terms=(STORM_TYRANT_DMG,), tags=("magic", "aoe"),
)
