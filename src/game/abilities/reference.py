"""Reference abilities shipped with T20.

These validate the full pipeline and serve as templates for content authors.
Covers: simple active, factory AOE, passive, phase hook, heal.
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
    compute_stat,
)
from src.game.events import AttackEvent, DamageEvent
from src.game.models import WeatherState
from src.game.registries import (
    ABILITY_REGISTRY,
    SimpleActive,
    register_active,
    register_active_simple,
    register_passive,
)
from src.game.targeting import lowest_hp_ally, lowest_hp_enemy, primary_target


# ---------------------------------------------------------------------------
# 1. smash — Simple active: single-target STR damage
# ---------------------------------------------------------------------------

register_active_simple("smash", SimpleActive(
    target="primary",
    damage=100.0,
    scaling="strength*1.5",
    tag=SourceTag.ABILITY,
))


# ---------------------------------------------------------------------------
# 2. thunder_crash — Factory cone AOE (weather conditional)
# ---------------------------------------------------------------------------

def cone_aoe(damage: float, scaling: str, half_to_neighbors: bool = False):
    """Factory: produces a handler for cone AOE abilities."""
    def handler(ctx: Any, actor: Any, targets: list) -> None:
        target = primary_target(actor, ctx)
        if not target:
            return
        from src.game.registries import _eval_scaling
        amt = _eval_scaling(damage, scaling, actor)

        # Weather conditional: Thunder boosts damage
        if ctx.weather == WeatherState.THUNDER:
            amt *= 1.5

        ctx.deal_damage(actor, target, amt, SourceTag.ABILITY)

        if half_to_neighbors:
            from src.game.targeting import neighbors_of
            for n in neighbors_of(target, ctx):
                if ctx.is_enemy(n, actor):
                    ctx.deal_damage(actor, n, amt * 0.5, SourceTag.ABILITY)

    return handler


ABILITY_REGISTRY["thunder_crash"] = cone_aoe(
    damage=180.0, scaling="intelligence*1.5", half_to_neighbors=True
)


# ---------------------------------------------------------------------------
# 3. static_buildup — Passive: on_attack_landed, apply 'charged' status
# ---------------------------------------------------------------------------

@register_passive("static_buildup")
def static_buildup(owner: Any) -> EffectBundle:
    """When this piece lands a basic attack in THUNDER weather, apply 'charged'."""
    def hook(ctx: Any, event: Any) -> None:
        if not hasattr(event, "attacker"):
            return
        if event.attacker is not owner:
            return
        if ctx.weather == WeatherState.THUNDER:
            ctx.apply_status(event.target, "charged", duration_ticks=200, stacks=1)

    return EffectBundle(hooks=[
        Hook("on_attack_landed", hook, scope=HookScope.PER_HIT),
    ])


# ---------------------------------------------------------------------------
# 4. phase_hook_test — Phase hook: grant ability at 50% HP
# ---------------------------------------------------------------------------

@register_passive("phase_hook_test")
def phase_hook_test(owner: Any) -> EffectBundle:
    """Boss phase hook: at 50% HP, grant a second ability."""
    def hook(ctx: Any, event: Any) -> None:
        if not hasattr(event, "target"):
            return
        if event.target is not owner:
            return
        if owner.hp_pct >= 0.50:
            return
        # Grant a second ability
        from src.game.piece import ActiveSlot
        owner.actives.append(ActiveSlot(
            ability_id="smash",
            cost=36_000,
            priority=10,
        ))

    return EffectBundle(hooks=[
        Hook("on_damage_taken", hook, scope=HookScope.ONCE_PER_COMBAT, priority=100),
    ])


# ---------------------------------------------------------------------------
# 5. heal_pulse — Simple active: heal lowest ally
# ---------------------------------------------------------------------------

@register_active("heal_pulse")
def heal_pulse(ctx: Any, actor: Any, targets: list) -> None:
    """Heal the lowest-HP ally for INT-scaled amount."""
    ally = lowest_hp_ally(actor, ctx)
    if not ally:
        return
    from src.game.registries import _eval_scaling
    amount = _eval_scaling(80.0, "intelligence*2.0", actor)
    ctx.heal(actor, ally, amount)


# ---------------------------------------------------------------------------
# 6. sunlit_vigor — CLEAR-affinity passive (first passive content)
# ---------------------------------------------------------------------------

@register_passive("sunlit_vigor")
def sunlit_vigor(owner: Any) -> EffectBundle:
    """CLEAR-affinity pieces gain a stat buff when node weather is CLEAR."""
    def hook(ctx: Any, event: Any) -> None:
        if ctx.weather == WeatherState.CLEAR and owner.affinity == WeatherState.CLEAR:
            ctx.apply_modifier(owner, Modifier(
                "strength", "add", 15.0, Lifetime.COMBAT, "passive:sunlit_vigor"
            ))
            ctx.apply_modifier(owner, Modifier(
                "intelligence", "add", 15.0, Lifetime.COMBAT, "passive:sunlit_vigor"
            ))

    return EffectBundle(hooks=[
        Hook("on_combat_start", hook, scope=HookScope.ONCE_PER_COMBAT),
    ])
