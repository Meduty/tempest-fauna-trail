"""Emblem item factories (T.29b §3.5).

An emblem makes its wearer count toward a **Kinship** it does not natively have:
the bundle carries `granted_traits=["<Kinship>"]` (+ a small flavour stat).
`apply_bundle` appends `granted_traits` to `piece.traits` at §10.1 step 2 —
*before* `_resolve_traits` (step 3, T.28a) — so the wearer is counted toward that
Kinship's breakpoints. One emblem per Kinship; crafted via `combine(Spirit Gem,
component)` (see `recipes.py` + `base.KINSHIP_OF`).
"""

from __future__ import annotations

from typing import Any

from src.game.effects import EffectBundle, Lifetime, Modifier
from src.game.registries import register_item


def _emblem(kinship: str, stat: str, mul: float, item_id: str) -> EffectBundle:
    """Emblem bundle: grant the Kinship trait + a small flavour stat."""
    return EffectBundle(
        granted_traits=[kinship],
        modifiers=[Modifier(stat, "mul", mul, Lifetime.COMBAT, f"item:{item_id}")],
    )


@register_item("beast_emblem")
def beast_emblem(owner: Any) -> EffectBundle:
    """Beast Emblem — grants Beast + 8% STR."""
    return _emblem("Beast", "strength", 1.08, "beast_emblem")


@register_item("skyborn_emblem")
def skyborn_emblem(owner: Any) -> EffectBundle:
    """Skyborn Emblem — grants Skyborn + 8% AS."""
    return _emblem("Skyborn", "attack_speed", 1.08, "skyborn_emblem")


@register_item("scaled_emblem")
def scaled_emblem(owner: Any) -> EffectBundle:
    """Scaled Emblem — grants Scaled + 8% Armor."""
    return _emblem("Scaled", "armor", 1.08, "scaled_emblem")


@register_item("tidekin_emblem")
def tidekin_emblem(owner: Any) -> EffectBundle:
    """Tidekin Emblem — grants Tidekin + 8% mana regen."""
    return _emblem("Tidekin", "mana_regen", 1.08, "tidekin_emblem")


@register_item("swarm_emblem")
def swarm_emblem(owner: Any) -> EffectBundle:
    """Swarm Emblem — grants Swarm + 8% HP."""
    return _emblem("Swarm", "hp", 1.08, "swarm_emblem")


@register_item("spirit_emblem")
def spirit_emblem(owner: Any) -> EffectBundle:
    """Spirit Emblem — grants Spirit + 8% INT."""
    return _emblem("Spirit", "intelligence", 1.08, "spirit_emblem")
