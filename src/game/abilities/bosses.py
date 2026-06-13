"""Boss abilities — full 2-phase kits for all 6 stage bosses (T.30).

Each boss has:
  - Phase 1 active + passive + phase hook (triggers at 50% HP)
  - Phase 2 active + passive
  - On-death hook

Per amendments: full 2-phase kits authored here, including phase-transition map effects.
Summons are full Piece objects with summon flag (G6 amendment).
Round semantics: periodic tick effects every 600 ticks, no round abstraction (G8 amendment).
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
from src.game.events import PhaseEvent
from src.game.registries import (
    ABILITY_META,
    AbilityMeta,
    Clause,
    ScalingTerm,
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
# STAGE 1 — Foundry-Lord Holloway (Clear)
# ===========================================================================


# Phase 1 Active: Pressure Vent — STR cone damage + burn
HOLLOWAY_PRESSURE_VENT = ScalingTerm("damage", 100.0, "strength*2.5")


@register_active("holloway.pressure_vent")
def holloway_pressure_vent(ctx: Any, actor: Any, targets: list) -> None:
    amount = HOLLOWAY_PRESSURE_VENT.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 2, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount, SourceTag.ABILITY, damage_type="physical")
        ctx.apply_status(t, "burn", duration_ticks=400, source_id=actor.id)


ABILITY_META["holloway.pressure_vent"] = AbilityMeta(
    name="Pressure Vent", kind="active",
    blurb="Vent scalding steam for {damage} physical damage to all enemies within 2 hexes.",
    terms=(HOLLOWAY_PRESSURE_VENT,),
    clauses=(Clause("Burns struck enemies for 4s."),), tags=("physical", "aoe", "burn"),
)


# Phase 1 Passive: Stoke the Fires — gains STR per living ally every 600 ticks
@register_passive("holloway.stoke_the_fires")
def holloway_stoke_the_fires(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 600:
            state["last_tick"] = ctx.current_tick
            ally_count = len([a for a in ctx.allies_of(owner) if a is not owner])
            if ally_count > 0:
                ctx.apply_modifier(owner, Modifier(
                    "strength", "add", 8.0 * ally_count, Lifetime.TIMED,
                    "passive:holloway.stoke",
                    expires_at_tick=ctx.current_tick + 600,
                ))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["holloway.stoke_the_fires"] = AbilityMeta(
    name="Stoke the Fires", kind="passive",
    blurb="Every 6s, gain +8 Strength per living ally for 6s.",
    tags=("buff",),
)


# Phase Hook: triggers at 50% HP, grants phase 2 abilities
@register_passive("holloway.phase_hook")
def holloway_phase_hook(owner: Any) -> EffectBundle:
    state = {"triggered": False}

    def hook(ctx: Any, event: Any) -> None:
        if event.target is not owner:
            return
        if not state["triggered"] and owner.hp_pct <= 0.5:
            state["triggered"] = True
            # Phase transition: grant phase 2 abilities
            from src.game.piece import ActiveSlot
            owner.actives = [ActiveSlot(
                ability_id="holloway.magma_heave",
                cost=owner.actives[0].cost if owner.actives else 420_000,
            )]
            # Apply phase 2 passive
            bundle = holloway_cinder_husk(owner)
            ctx.register_bundle(owner, bundle)
            # Fire phase event
            ctx.fire("on_phase_change", PhaseEvent(piece=owner, new_phase=2))
            # Map effect intensification: burn all enemies
            enemies = list(ctx.enemies_of(owner))
            for e in enemies:
                ctx.apply_status(e, "burn", duration_ticks=200, source_id=owner.id)

    return EffectBundle(hooks=[
        Hook("on_damage_taken", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["holloway.phase_hook"] = AbilityMeta(
    name="Overpressure", kind="passive",
    blurb="At 50% HP, enter Phase 2: swap to Magma Heave, gain the Cinder Husk passive, and burn all enemies.",
    tags=("phase",),
)


# Phase 2 Active: Magma Heave — massive STR AOE + ground burn
HOLLOWAY_MAGMA_HEAVE = ScalingTerm("damage", 140.0, "strength*3.0")
_HOLLOWAY_MAGMA_AOE = 0.7


@register_active("holloway.magma_heave")
def holloway_magma_heave(ctx: Any, actor: Any, targets: list) -> None:
    amount = HOLLOWAY_MAGMA_HEAVE.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * _HOLLOWAY_MAGMA_AOE, SourceTag.ABILITY,
                        damage_type="physical")
        ctx.apply_status(t, "burn", duration_ticks=500, source_id=actor.id)


ABILITY_META["holloway.magma_heave"] = AbilityMeta(
    name="Magma Heave", kind="active",
    blurb=f"Erupt for {int(_HOLLOWAY_MAGMA_AOE * 100)}% of {{damage}} physical damage to all enemies within 3 hexes.",
    terms=(HOLLOWAY_MAGMA_HEAVE,),
    clauses=(Clause("Burns struck enemies for 5s."),), tags=("physical", "aoe", "burn"),
)


# Phase 2 Passive: Cinder Husk — reflects damage + armor
_HOLLOWAY_REFLECT_PCT = 0.1


@register_passive("holloway.cinder_husk")
def holloway_cinder_husk(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.target is not owner:
            return
        if event.tag == SourceTag.REFLECT.value:
            return  # never reflect a reflection — prevents mutual-reflect recursion
        if not hasattr(event, "attacker") or event.attacker is None:
            return
        if event.attacker.alive:
            reflect = event.amount * _HOLLOWAY_REFLECT_PCT
            ctx.deal_damage(owner, event.attacker, reflect, SourceTag.REFLECT,
                          damage_type="physical")

    return EffectBundle(
        modifiers=[Modifier("armor", "add", 30.0, Lifetime.COMBAT, "passive:holloway.cinder_husk")],
        hooks=[Hook("on_damage_taken", hook, scope=HookScope.PER_HIT, priority=-10)],
    )


ABILITY_META["holloway.cinder_husk"] = AbilityMeta(
    name="Cinder Husk", kind="passive",
    blurb="Grants +30 Armor and reflects 10% of damage taken as physical damage.",
    tags=("defense", "reflect"),
)


# On-death: Boiler Burst — AOE damage to all enemies
HOLLOWAY_BOILER_BURST = ScalingTerm("damage", 80.0, "")


@register_passive("holloway.boiler_burst")
def holloway_boiler_burst(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.victim is not owner:
            return
        # Explosion on death
        enemies = list(ctx.enemies_of(owner))
        for e in enemies:
            if e.alive:
                ctx.deal_damage(owner, e, HOLLOWAY_BOILER_BURST.eval(owner), SourceTag.TRUE)

    return EffectBundle(hooks=[
        Hook("on_death", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["holloway.boiler_burst"] = AbilityMeta(
    name="Boiler Burst", kind="passive",
    blurb="On death, explode for {damage} true damage to all enemies.",
    terms=(HOLLOWAY_BOILER_BURST,), tags=("true", "aoe", "on-death"),
)


# ===========================================================================
# STAGE 2 — Solar Overseer Vance (Mist)
# ===========================================================================


# Phase 1 Active: Focusing Lens — high INT single target nuke
VANCE_FOCUSING_LENS = ScalingTerm("damage", 120.0, "intelligence*2.8")


@register_active("vance.focusing_lens")
def vance_focusing_lens(ctx: Any, actor: Any, targets: list) -> None:
    target = furthest_enemy(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, VANCE_FOCUSING_LENS.eval(actor), SourceTag.ABILITY)


ABILITY_META["vance.focusing_lens"] = AbilityMeta(
    name="Focusing Lens", kind="active",
    blurb="Focus a beam on the furthest enemy for {damage} magic damage.",
    terms=(VANCE_FOCUSING_LENS,), tags=("magic",),
)


# Phase 1 Passive: Glare — enemies near Vance lose AS
@register_passive("vance.glare")
def vance_glare(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 300:
            state["last_tick"] = ctx.current_tick
            enemies = enemies_in_radius(owner.position_q, owner.position_r, 3, owner, ctx)
            for e in enemies:
                ctx.apply_modifier(e, Modifier(
                    "attack_speed", "add", -15.0, Lifetime.TIMED,
                    "passive:vance.glare",
                    expires_at_tick=ctx.current_tick + 350,
                ))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["vance.glare"] = AbilityMeta(
    name="Glare", kind="passive",
    blurb="Every 3s, enemies within 3 hexes lose 15 Attack Speed for 3.5s.",
    tags=("debuff", "aura"),
)


# Phase Hook
@register_passive("vance.phase_hook")
def vance_phase_hook(owner: Any) -> EffectBundle:
    state = {"triggered": False}

    def hook(ctx: Any, event: Any) -> None:
        if event.target is not owner:
            return
        if not state["triggered"] and owner.hp_pct <= 0.5:
            state["triggered"] = True
            from src.game.piece import ActiveSlot
            owner.actives = [ActiveSlot(
                ability_id="vance.sunflare_pounce",
                cost=owner.actives[0].cost if owner.actives else 440_000,
            )]
            bundle = vance_drought_aura(owner)
            ctx.register_bundle(owner, bundle)
            ctx.fire("on_phase_change", PhaseEvent(piece=owner, new_phase=2))
            # Phase transition effect: silence all enemies briefly
            enemies = list(ctx.enemies_of(owner))
            for e in enemies:
                ctx.apply_status(e, "silence", duration_ticks=200, source_id=owner.id)

    return EffectBundle(hooks=[
        Hook("on_damage_taken", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["vance.phase_hook"] = AbilityMeta(
    name="Solar Eclipse", kind="passive",
    blurb="At 50% HP, enter Phase 2: swap to Sunflare Pounce, gain the Drought Aura passive, and silence all enemies.",
    tags=("phase",),
)


# Phase 2 Active: Sunflare Pounce — INT burst + fear
VANCE_SUNFLARE_POUNCE = ScalingTerm("damage", 150.0, "intelligence*3.0")


@register_active("vance.sunflare_pounce")
def vance_sunflare_pounce(ctx: Any, actor: Any, targets: list) -> None:
    target = lowest_hp_enemy(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, VANCE_SUNFLARE_POUNCE.eval(actor), SourceTag.ABILITY)
    ctx.apply_status(target, "fear", duration_ticks=250, source_id=actor.id)


ABILITY_META["vance.sunflare_pounce"] = AbilityMeta(
    name="Sunflare Pounce", kind="active",
    blurb="Pounce the lowest-HP enemy for {damage} magic damage.",
    terms=(VANCE_SUNFLARE_POUNCE,),
    clauses=(Clause("Fears for 2.5s."),), tags=("magic", "fear"),
)


# Phase 2 Passive: Drought Aura — periodic mana drain (reduce enemy mana regen)
@register_passive("vance.drought_aura")
def vance_drought_aura(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 300:
            state["last_tick"] = ctx.current_tick
            enemies = enemies_in_radius(owner.position_q, owner.position_r, 4, owner, ctx)
            for e in enemies:
                ctx.apply_modifier(e, Modifier(
                    "mana_regen", "add", -5.0, Lifetime.TIMED,
                    "passive:vance.drought",
                    expires_at_tick=ctx.current_tick + 350,
                ))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["vance.drought_aura"] = AbilityMeta(
    name="Drought Aura", kind="passive",
    blurb="Every 3s, enemies within 4 hexes lose 5 Mana Regen for 3.5s.",
    tags=("debuff", "aura"),
)


# On-death: Sun Husk Collapse
VANCE_SUN_HUSK_COLLAPSE = ScalingTerm("damage", 60.0, "")


@register_passive("vance.sun_husk_collapse")
def vance_sun_husk_collapse(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.victim is not owner:
            return
        enemies = list(ctx.enemies_of(owner))
        for e in enemies:
            if e.alive:
                ctx.deal_damage(owner, e, VANCE_SUN_HUSK_COLLAPSE.eval(owner), SourceTag.TRUE)
                ctx.apply_status(e, "burn", duration_ticks=300, source_id=owner.id)

    return EffectBundle(hooks=[
        Hook("on_death", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["vance.sun_husk_collapse"] = AbilityMeta(
    name="Sun Husk Collapse", kind="passive",
    blurb="On death, burst for {damage} true damage to all enemies and burn them for 3s.",
    terms=(VANCE_SUN_HUSK_COLLAPSE,), tags=("true", "aoe", "burn", "on-death"),
)


# ===========================================================================
# STAGE 3 — Grid-Director Strand (Thunder)
# ===========================================================================


# Phase 1 Active: Arc Cascade — chain lightning
STRAND_ARC_CASCADE = ScalingTerm("damage", 110.0, "intelligence*2.5")


@register_active("strand.arc_cascade")
def strand_arc_cascade(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = STRAND_ARC_CASCADE.eval(actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY)
    chain_targets = []
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor) and n is not target and len(chain_targets) < 3:
            chain_targets.append(n)
    for i, ct in enumerate(chain_targets):
        chain_dmg = amount * (0.6 - i * 0.1)
        ctx.deal_damage(actor, ct, max(0, chain_dmg), SourceTag.ABILITY)


ABILITY_META["strand.arc_cascade"] = AbilityMeta(
    name="Arc Cascade", kind="active",
    blurb="Strike the primary target for {damage} magic damage.",
    terms=(STRAND_ARC_CASCADE,),
    clauses=(Clause("Chains to up to 3 nearby enemies at 60%, 50%, then 40% damage."),),
    tags=("magic", "aoe"),
)


# Phase 1 Passive: Overcharged — stacking INT after each cast
@register_passive("strand.overcharged")
def strand_overcharged(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.caster is not owner:
            return
        ctx.apply_modifier(owner, Modifier(
            "intelligence", "add", 12.0, Lifetime.COMBAT,
            "passive:strand.overcharged.stack",
        ))

    return EffectBundle(hooks=[
        Hook("on_cast_complete", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["strand.overcharged"] = AbilityMeta(
    name="Overcharged", kind="passive",
    blurb="Each cast permanently grants +12 Intelligence.",
    tags=("scaling", "buff"),
)


# Phase Hook
@register_passive("strand.phase_hook")
def strand_phase_hook(owner: Any) -> EffectBundle:
    state = {"triggered": False}

    def hook(ctx: Any, event: Any) -> None:
        if event.target is not owner:
            return
        if not state["triggered"] and owner.hp_pct <= 0.5:
            state["triggered"] = True
            from src.game.piece import ActiveSlot
            owner.actives = [ActiveSlot(
                ability_id="strand.thunderhead",
                cost=owner.actives[0].cost if owner.actives else 380_000,
            )]
            bundle = strand_stormform(owner)
            ctx.register_bundle(owner, bundle)
            ctx.fire("on_phase_change", PhaseEvent(piece=owner, new_phase=2))
            # Transition: stun all enemies briefly
            enemies = list(ctx.enemies_of(owner))
            for e in enemies:
                ctx.apply_status(e, "stun", duration_ticks=150, source_id=owner.id)

    return EffectBundle(hooks=[
        Hook("on_damage_taken", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["strand.phase_hook"] = AbilityMeta(
    name="Grid Overload", kind="passive",
    blurb="At 50% HP, enter Phase 2: swap to Thunderhead, gain the Stormform passive, and stun all enemies.",
    tags=("phase",),
)


# Phase 2 Active: Thunderhead — massive AOE + charged status
STRAND_THUNDERHEAD = ScalingTerm("damage", 130.0, "intelligence*3.0")
_STRAND_THUNDERHEAD_AOE = 0.6


@register_active("strand.thunderhead")
def strand_thunderhead(ctx: Any, actor: Any, targets: list) -> None:
    amount = STRAND_THUNDERHEAD.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 4, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * _STRAND_THUNDERHEAD_AOE, SourceTag.ABILITY)
        ctx.apply_status(t, "charged", duration_ticks=300, source_id=actor.id)


ABILITY_META["strand.thunderhead"] = AbilityMeta(
    name="Thunderhead", kind="active",
    blurb=f"Call down a storm for {int(_STRAND_THUNDERHEAD_AOE * 100)}% of {{damage}} magic damage to all enemies within 4 hexes.",
    terms=(STRAND_THUNDERHEAD,),
    clauses=(Clause("Charges struck enemies for 3s."),), tags=("magic", "aoe"),
)


# Phase 2 Passive: Stormform — bonus damage to charged enemies
STRAND_STORMFORM = ScalingTerm("bonus", 0.0, "intelligence*0.4")


@register_passive("strand.stormform")
def strand_stormform(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        if event.target.has_status("charged"):
            ctx.deal_damage(owner, event.target, STRAND_STORMFORM.eval(owner), SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["strand.stormform"] = AbilityMeta(
    name="Stormform", kind="passive",
    blurb="Auto-attacks against charged enemies deal {bonus} bonus magic damage.",
    terms=(STRAND_STORMFORM,), tags=("magic",),
)


# On-death: Lightning Strike
STRAND_LIGHTNING_STRIKE = ScalingTerm("damage", 100.0, "")


@register_passive("strand.lightning_strike")
def strand_lightning_strike(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.victim is not owner:
            return
        enemies = list(ctx.enemies_of(owner))
        for e in enemies:
            if e.alive:
                ctx.deal_damage(owner, e, STRAND_LIGHTNING_STRIKE.eval(owner), SourceTag.TRUE)
                ctx.apply_status(e, "stun", duration_ticks=100, source_id=owner.id)

    return EffectBundle(hooks=[
        Hook("on_death", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["strand.lightning_strike"] = AbilityMeta(
    name="Lightning Strike", kind="passive",
    blurb="On death, blast all enemies for {damage} true damage and stun them for 1s.",
    terms=(STRAND_LIGHTNING_STRIKE,), tags=("true", "aoe", "stun", "on-death"),
)


# ===========================================================================
# STAGE 4 — Clearance-Marshal Vossberg (Cloudy)
# ===========================================================================


# Phase 1 Active: Scorched Advance — STR charge + burn
VOSSBERG_SCORCHED_ADVANCE = ScalingTerm("damage", 130.0, "strength*2.8")
_VOSSBERG_SCORCHED_SPLASH = 0.4


@register_active("vossberg.scorched_advance")
def vossberg_scorched_advance(ctx: Any, actor: Any, targets: list) -> None:
    target = primary_target(actor, ctx)
    if not target:
        return
    amount = VOSSBERG_SCORCHED_ADVANCE.eval(actor)
    ctx.deal_damage(actor, target, amount, SourceTag.ABILITY, damage_type="physical")
    ctx.apply_status(target, "burn", duration_ticks=300, source_id=actor.id)
    # Hit neighbors
    for n in neighbors_of(target, ctx):
        if ctx.is_enemy(n, actor):
            ctx.deal_damage(actor, n, amount * _VOSSBERG_SCORCHED_SPLASH, SourceTag.ABILITY,
                            damage_type="physical")


ABILITY_META["vossberg.scorched_advance"] = AbilityMeta(
    name="Scorched Advance", kind="active",
    blurb="Charge the primary target for {damage} physical damage and burn for 3s.",
    terms=(VOSSBERG_SCORCHED_ADVANCE,),
    clauses=(Clause(f"Adjacent enemies take {int(_VOSSBERG_SCORCHED_SPLASH * 100)}% splash."),),
    tags=("physical", "aoe", "burn"),
)


# Phase 1 Passive: No Quarter — gains STR when damaging enemies
@register_passive("vossberg.no_quarter")
def vossberg_no_quarter(owner: Any) -> EffectBundle:
    state = {"count": 0}

    def hook(ctx: Any, event: Any) -> None:
        if event.attacker is not owner:
            return
        state["count"] += 1
        if state["count"] % 3 == 0:
            ctx.apply_modifier(owner, Modifier(
                "strength", "add", 10.0, Lifetime.COMBAT,
                "passive:vossberg.no_quarter",
            ))

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["vossberg.no_quarter"] = AbilityMeta(
    name="No Quarter", kind="passive",
    blurb="Every 3rd attack permanently grants +10 Strength.",
    tags=("scaling", "buff"),
)


# Phase Hook
@register_passive("vossberg.phase_hook")
def vossberg_phase_hook(owner: Any) -> EffectBundle:
    state = {"triggered": False}

    def hook(ctx: Any, event: Any) -> None:
        if event.target is not owner:
            return
        if not state["triggered"] and owner.hp_pct <= 0.5:
            state["triggered"] = True
            from src.game.piece import ActiveSlot
            owner.actives = [ActiveSlot(
                ability_id="vossberg.wildfire_leap",
                cost=owner.actives[0].cost if owner.actives else 400_000,
            )]
            bundle = vossberg_feeding_frenzy(owner)
            ctx.register_bundle(owner, bundle)
            ctx.fire("on_phase_change", PhaseEvent(piece=owner, new_phase=2))
            # Transition: gain massive STR burst
            ctx.apply_modifier(owner, Modifier(
                "strength", "add", 40.0, Lifetime.COMBAT,
                "vossberg.phase2_str",
            ))

    return EffectBundle(hooks=[
        Hook("on_damage_taken", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["vossberg.phase_hook"] = AbilityMeta(
    name="Total War", kind="passive",
    blurb="At 50% HP, enter Phase 2: swap to Wildfire Leap, gain the Feeding Frenzy passive, and surge +40 Strength.",
    tags=("phase",),
)


# Phase 2 Active: Wildfire Leap — massive STR AOE
VOSSBERG_WILDFIRE_LEAP = ScalingTerm("damage", 160.0, "strength*3.2")
_VOSSBERG_WILDFIRE_AOE = 0.8


@register_active("vossberg.wildfire_leap")
def vossberg_wildfire_leap(ctx: Any, actor: Any, targets: list) -> None:
    amount = VOSSBERG_WILDFIRE_LEAP.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 2, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * _VOSSBERG_WILDFIRE_AOE, SourceTag.ABILITY,
                        damage_type="physical")
        ctx.apply_status(t, "burn", duration_ticks=400, source_id=actor.id)


ABILITY_META["vossberg.wildfire_leap"] = AbilityMeta(
    name="Wildfire Leap", kind="active",
    blurb=f"Leap and erupt for {int(_VOSSBERG_WILDFIRE_AOE * 100)}% of {{damage}} physical damage to all enemies within 2 hexes.",
    terms=(VOSSBERG_WILDFIRE_LEAP,),
    clauses=(Clause("Burns struck enemies for 4s."),), tags=("physical", "aoe", "burn"),
)


# Phase 2 Passive: Feeding Frenzy — heal on kill (%-of-max-HP stays inline)
_VOSSBERG_FRENZY_HEAL_PCT = 0.1


@register_passive("vossberg.feeding_frenzy")
def vossberg_feeding_frenzy(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.killer is not owner:
            return
        ctx.heal(owner, owner, owner.max_hp * _VOSSBERG_FRENZY_HEAL_PCT)

    return EffectBundle(hooks=[
        Hook("on_kill", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["vossberg.feeding_frenzy"] = AbilityMeta(
    name="Feeding Frenzy", kind="passive",
    blurb="Killing an enemy heals for 10% of max HP.",
    tags=("heal",),
)


# On-death: Fire Gutters Out
@register_passive("vossberg.fire_gutters_out")
def vossberg_fire_gutters_out(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.victim is not owner:
            return
        # Allies lose STR on marshal death
        allies = [a for a in ctx.allies_of(owner) if a.alive and a is not owner]
        for a in allies:
            ctx.apply_modifier(a, Modifier(
                "strength", "add", -20.0, Lifetime.COMBAT,
                "vossberg.death_debuff",
            ))

    return EffectBundle(hooks=[
        Hook("on_death", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["vossberg.fire_gutters_out"] = AbilityMeta(
    name="Fire Gutters Out", kind="passive",
    blurb="On death, the marshal's surviving allies lose 20 Strength.",
    tags=("debuff", "on-death"),
)


# ===========================================================================
# STAGE 5 — Dredge-Admiral Crège (Rain)
# ===========================================================================


# Phase 1 Active: Harpoon Winch — pull + damage + root
CREGE_HARPOON_WINCH = ScalingTerm("damage", 100.0, "strength*2.0+intelligence*1.0")


@register_active("crege.harpoon_winch")
def crege_harpoon_winch(ctx: Any, actor: Any, targets: list) -> None:
    target = furthest_enemy(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, CREGE_HARPOON_WINCH.eval(actor), SourceTag.ABILITY,
                    damage_type="physical")
    ctx.apply_status(target, "root", duration_ticks=250, source_id=actor.id)
    # Simulate pull via teleport toward boss
    if abs(target.position_q - actor.position_q) > 1:
        step_q = 1 if target.position_q < actor.position_q else -1
        ctx.teleport(target, target.position_q + step_q, target.position_r)


ABILITY_META["crege.harpoon_winch"] = AbilityMeta(
    name="Harpoon Winch", kind="active",
    blurb="Harpoon the furthest enemy for {damage} physical damage.",
    terms=(CREGE_HARPOON_WINCH,),
    clauses=(Clause("Pulls the target toward Crège and roots it for 2.5s."),),
    tags=("physical", "root"),
)


# Phase 1 Passive: Dredged Depths — slow aura periodic
@register_passive("crege.dredged_depths")
def crege_dredged_depths(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 300:
            state["last_tick"] = ctx.current_tick
            enemies = enemies_in_radius(owner.position_q, owner.position_r, 3, owner, ctx)
            for e in enemies:
                ctx.apply_status(e, "slow", duration_ticks=350, stacks=1, source_id=owner.id)

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["crege.dredged_depths"] = AbilityMeta(
    name="Dredged Depths", kind="passive",
    blurb="Every 3s, slows all enemies within 3 hexes for 3.5s.",
    tags=("slow", "aura"),
)


# Phase Hook
@register_passive("crege.phase_hook")
def crege_phase_hook(owner: Any) -> EffectBundle:
    state = {"triggered": False}

    def hook(ctx: Any, event: Any) -> None:
        if event.target is not owner:
            return
        if not state["triggered"] and owner.hp_pct <= 0.5:
            state["triggered"] = True
            from src.game.piece import ActiveSlot
            owner.actives = [ActiveSlot(
                ability_id="crege.maelstrom_jaws",
                cost=owner.actives[0].cost if owner.actives else 460_000,
            )]
            bundle = crege_drowning_tide(owner)
            ctx.register_bundle(owner, bundle)
            ctx.fire("on_phase_change", PhaseEvent(piece=owner, new_phase=2))
            # Transition: root all enemies
            enemies = list(ctx.enemies_of(owner))
            for e in enemies:
                ctx.apply_status(e, "root", duration_ticks=200, source_id=owner.id)

    return EffectBundle(hooks=[
        Hook("on_damage_taken", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["crege.phase_hook"] = AbilityMeta(
    name="Maelstrom Rising", kind="passive",
    blurb="At 50% HP, enter Phase 2: swap to Maelstrom Jaws, gain the Drowning Tide passive, and root all enemies.",
    tags=("phase",),
)


# Phase 2 Active: Maelstrom Jaws — massive AOE + slow
CREGE_MAELSTROM_JAWS = ScalingTerm("damage", 120.0, "strength*2.5+intelligence*1.5")
_CREGE_MAELSTROM_AOE = 0.7


@register_active("crege.maelstrom_jaws")
def crege_maelstrom_jaws(ctx: Any, actor: Any, targets: list) -> None:
    amount = CREGE_MAELSTROM_JAWS.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 3, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * _CREGE_MAELSTROM_AOE, SourceTag.ABILITY,
                        damage_type="physical")
        ctx.apply_status(t, "slow", duration_ticks=400, stacks=2, source_id=actor.id)


ABILITY_META["crege.maelstrom_jaws"] = AbilityMeta(
    name="Maelstrom Jaws", kind="active",
    blurb=f"Engulf all enemies within 3 hexes for {int(_CREGE_MAELSTROM_AOE * 100)}% of {{damage}} physical damage.",
    terms=(CREGE_MAELSTROM_JAWS,),
    clauses=(Clause("Applies 2 stacks of slow for 4s."),), tags=("physical", "aoe", "slow"),
)


# Phase 2 Passive: Drowning Tide — periodic damage to all enemies
CREGE_DROWNING_TIDE = ScalingTerm("damage", 5.0, "")


@register_passive("crege.drowning_tide")
def crege_drowning_tide(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 200:
            state["last_tick"] = ctx.current_tick
            enemies = list(ctx.enemies_of(owner))
            for e in enemies:
                if e.alive:
                    ctx.deal_damage(owner, e, CREGE_DROWNING_TIDE.eval(owner), SourceTag.DOT)

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["crege.drowning_tide"] = AbilityMeta(
    name="Drowning Tide", kind="passive",
    blurb="Every 2s, deals {damage} damage to all enemies.",
    terms=(CREGE_DROWNING_TIDE,), tags=("aoe", "dot"),
)


# On-death: Silt Drains
@register_passive("crege.silt_drains")
def crege_silt_drains(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.victim is not owner:
            return
        # Remove slow from all enemies when boss dies
        enemies = list(ctx.enemies_of(owner))
        for e in enemies:
            if e.alive:
                ctx.remove_status(e, "slow")
                ctx.heal(owner, e, 50.0)

    return EffectBundle(hooks=[
        Hook("on_death", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["crege.silt_drains"] = AbilityMeta(
    name="Silt Drains", kind="passive",
    blurb="On death, the waters recede: removes slow from all enemies and heals each for 50.",
    tags=("heal", "on-death"),
)


# ===========================================================================
# STAGE 6 — The Iron Emperor (Snow)
# ===========================================================================


# Phase 1 Active: Decree of Iron — mark target for +damage taken
IRON_EMPEROR_DECREE = ScalingTerm("damage", 100.0, "strength*1.5+intelligence*1.5")


@register_active("iron_emperor.decree_of_iron")
def iron_emperor_decree_of_iron(ctx: Any, actor: Any, targets: list) -> None:
    target = lowest_hp_enemy(actor, ctx)
    if not target:
        return
    ctx.deal_damage(actor, target, IRON_EMPEROR_DECREE.eval(actor), SourceTag.ABILITY)
    # Mark: reduce defenses
    ctx.apply_modifier(target, Modifier(
        "armor", "add", -25.0, Lifetime.TIMED,
        "ability:iron_emperor.decree",
        expires_at_tick=ctx.current_tick + 600,
    ))
    ctx.apply_modifier(target, Modifier(
        "resistance", "add", -25.0, Lifetime.TIMED,
        "ability:iron_emperor.decree",
        expires_at_tick=ctx.current_tick + 600,
    ))


ABILITY_META["iron_emperor.decree_of_iron"] = AbilityMeta(
    name="Decree of Iron", kind="active",
    blurb="Mark the lowest-HP enemy for {damage} magic damage.",
    terms=(IRON_EMPEROR_DECREE,),
    clauses=(Clause("Shreds 25 Armor and 25 Resistance for 6s."),), tags=("magic", "debuff"),
)


# Phase 1 Passive: Tribute — gains STR/INT per living ally
@register_passive("iron_emperor.tribute")
def iron_emperor_tribute(owner: Any) -> EffectBundle:
    state = {"last_tick": 0}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 600:
            state["last_tick"] = ctx.current_tick
            ally_count = len([a for a in ctx.allies_of(owner) if a is not owner and a.alive])
            if ally_count > 0:
                ctx.apply_modifier(owner, Modifier(
                    "strength", "add", 6.0 * ally_count, Lifetime.TIMED,
                    "passive:iron_emperor.tribute",
                    expires_at_tick=ctx.current_tick + 600,
                ))
                ctx.apply_modifier(owner, Modifier(
                    "intelligence", "add", 6.0 * ally_count, Lifetime.TIMED,
                    "passive:iron_emperor.tribute",
                    expires_at_tick=ctx.current_tick + 600,
                ))

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["iron_emperor.tribute"] = AbilityMeta(
    name="Tribute", kind="passive",
    blurb="Every 6s, gain +6 Strength and +6 Intelligence per living ally for 6s.",
    tags=("buff",),
)


# Phase Hook
@register_passive("iron_emperor.phase_hook")
def iron_emperor_phase_hook(owner: Any) -> EffectBundle:
    state = {"triggered": False}

    def hook(ctx: Any, event: Any) -> None:
        if event.target is not owner:
            return
        if not state["triggered"] and owner.hp_pct <= 0.5:
            state["triggered"] = True
            from src.game.piece import ActiveSlot
            owner.actives = [ActiveSlot(
                ability_id="iron_emperor.reclamation",
                cost=owner.actives[0].cost if owner.actives else 520_000,
            )]
            bundle = iron_emperor_the_wound_spreads(owner)
            ctx.register_bundle(owner, bundle)
            ctx.fire("on_phase_change", PhaseEvent(piece=owner, new_phase=2))
            # Transition: massive STR/INT boost + freeze all enemies
            ctx.apply_modifier(owner, Modifier(
                "strength", "add", 50.0, Lifetime.COMBAT,
                "iron_emperor.phase2",
            ))
            ctx.apply_modifier(owner, Modifier(
                "intelligence", "add", 50.0, Lifetime.COMBAT,
                "iron_emperor.phase2",
            ))
            enemies = list(ctx.enemies_of(owner))
            for e in enemies:
                ctx.apply_status(e, "frozen", duration_ticks=200, source_id=owner.id)

    return EffectBundle(hooks=[
        Hook("on_damage_taken", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["iron_emperor.phase_hook"] = AbilityMeta(
    name="Iron Reclamation", kind="passive",
    blurb="At 50% HP, enter Phase 2: swap to Reclamation, gain The Wound Spreads passive, surge +50 Strength and +50 Intelligence, and freeze all enemies.",
    tags=("phase",),
)


# Phase 2 Active: Reclamation — channel finisher (massive damage)
IRON_EMPEROR_RECLAMATION = ScalingTerm("damage", 150.0, "strength*2.0+intelligence*2.0")
_IRON_EMPEROR_RECLAMATION_AOE = 0.5


@register_active("iron_emperor.reclamation")
def iron_emperor_reclamation(ctx: Any, actor: Any, targets: list) -> None:
    amount = IRON_EMPEROR_RECLAMATION.eval(actor)
    hit_targets = enemies_in_radius(actor.position_q, actor.position_r, 4, actor, ctx)
    for t in hit_targets:
        ctx.deal_damage(actor, t, amount * _IRON_EMPEROR_RECLAMATION_AOE, SourceTag.ABILITY)
        ctx.apply_status(t, "slow", duration_ticks=400, stacks=3, source_id=actor.id)


ABILITY_META["iron_emperor.reclamation"] = AbilityMeta(
    name="Reclamation", kind="active",
    blurb=f"Channel a finisher for {int(_IRON_EMPEROR_RECLAMATION_AOE * 100)}% of {{damage}} magic damage to all enemies within 4 hexes.",
    terms=(IRON_EMPEROR_RECLAMATION,),
    clauses=(Clause("Applies 3 stacks of slow for 4s."),), tags=("magic", "aoe", "slow"),
)


# Phase 2 Passive: The Wound Spreads — periodic AOE damage + slow tile spread
@register_passive("iron_emperor.the_wound_spreads")
def iron_emperor_the_wound_spreads(owner: Any) -> EffectBundle:
    state = {"last_tick": 0, "intensity": 1}

    def hook(ctx: Any, event: Any) -> None:
        if ctx.current_tick - state["last_tick"] >= 300:
            state["last_tick"] = ctx.current_tick
            state["intensity"] += 1
            enemies = list(ctx.enemies_of(owner))
            for e in enemies:
                if e.alive:
                    ctx.deal_damage(owner, e, 3.0 * state["intensity"], SourceTag.DOT)
                    ctx.apply_status(e, "slow", duration_ticks=350, stacks=1,
                                    source_id=owner.id)

    return EffectBundle(hooks=[
        Hook("on_tick", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["iron_emperor.the_wound_spreads"] = AbilityMeta(
    name="The Wound Spreads", kind="passive",
    blurb="Every 3s, deals escalating damage (3 × growing intensity) to all enemies and slows them for 3.5s.",
    tags=("aoe", "dot", "slow", "scaling"),
)


# On-death: World Engine Dark — removes all buffs from enemies (allies)
@register_passive("iron_emperor.world_engine_dark")
def iron_emperor_world_engine_dark(owner: Any) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        if event.victim is not owner:
            return
        # All allies (emperor's side) lose all timed modifiers
        allies = [a for a in ctx.allies_of(owner) if a.alive and a is not owner]
        for a in allies:
            a.modifiers = [m for m in a.modifiers if m.lifetime != Lifetime.TIMED]
        # Heal all enemies slightly (the world breathes again)
        enemies = list(ctx.enemies_of(owner))
        for e in enemies:
            if e.alive:
                ctx.heal(owner, e, 100.0)

    return EffectBundle(hooks=[
        Hook("on_death", hook, scope=HookScope.PER_HIT),
    ])


ABILITY_META["iron_emperor.world_engine_dark"] = AbilityMeta(
    name="World Engine Dark", kind="passive",
    blurb="On death, strips all timed buffs from the Emperor's allies and heals each surviving enemy for 100.",
    tags=("debuff", "heal", "on-death"),
)
