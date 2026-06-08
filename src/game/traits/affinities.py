"""Affinity trait breakpoints (T.28a) — `@2/4/6/8/10`, mono apex.

Derived from each piece's `affinity` (V.6) at resolution; never reads node
weather. **T.28d** adds the `@10` apex riders: 5 of the 6 affinities gain a
mechanic at @10 (Galvanized crit-arc, Frostbound chill-attackers, Stormfed
mana-haste [stat], Shrouded longer hexproof-opener, Overcast burst-reduction);
**Sunlit stays stat-only** but its `@10` pack broadens to premium stats. Scope
stays PER_TRAIT_PIECE — at @10 the board is 10 mono-affinity uniques, so per ==
team in practice, and the riders are all team-safe damage/defensive idioms.
"""

from __future__ import annotations

from . import mechanics as m
from ._packs import define_trait
from .types import TraitScope

_PER = TraitScope.PER_TRAIT_PIECE

# Sunlit hits many stats → smaller per-stat pct than the 2-stat affinities. The
# @10 rung additionally seeds PREMIUM stats (crit/pen flat adds + mana_regen mul)
# at small values — "bathe in clear skies, a little of everything" — kept low by
# design: full-Clear's no-weakness identity is already strong (T.28d).
define_trait(
    "Sunlit",
    (2, _PER, {"strength": 0.04, "intelligence": 0.04, "attack_speed": 0.04, "move_speed": 0.04, "armor": 0.04, "resistance": 0.04, "hp": 0.04}),
    (4, _PER, {"strength": 0.07, "intelligence": 0.07, "attack_speed": 0.07, "move_speed": 0.07, "armor": 0.07, "resistance": 0.07, "hp": 0.07}),
    (6, _PER, {"strength": 0.10, "intelligence": 0.10, "attack_speed": 0.10, "move_speed": 0.10, "armor": 0.10, "resistance": 0.10, "hp": 0.10}),
    (8, _PER, {"strength": 0.13, "intelligence": 0.13, "attack_speed": 0.13, "move_speed": 0.13, "armor": 0.13, "resistance": 0.13, "hp": 0.13}),
    (10, _PER,
        {"strength": 0.16, "intelligence": 0.16, "attack_speed": 0.16, "move_speed": 0.16, "armor": 0.16, "resistance": 0.16, "hp": 0.16, "mana_regen": 0.10},
        {"crit_chance": 0.04, "penetration_pct": 0.04}),
)

# The five 2-stat affinities. @2-@8 share the ladder; @10 carries a per-affinity
# apex rider (Stormfed's "mana-haste" is purely a fatter mana_regen pack — no hook).
_TWO: dict[str, tuple[tuple[str, str], dict[str, float], list]] = {
    "Overcast": (("hp", "resistance"), {"hp": 0.27, "resistance": 0.27}, [m.burst_reduction(0.25)]),
    "Stormfed": (("attack_speed", "mana_regen"), {"attack_speed": 0.27, "mana_regen": 0.40}, []),
    "Frostbound": (("armor", "resistance"), {"armor": 0.27, "resistance": 0.27}, [m.chill_attackers(200)]),
    "Galvanized": (("strength", "attack_speed"), {"strength": 0.27, "attack_speed": 0.27}, [m.crit_arc(0.5)]),
    "Shrouded": (("move_speed", "threat"), {"move_speed": 0.27, "threat": 0.27}, [m.hexproof_opener(300)]),
}

for _name, ((_a, _b), _apex_muls, _apex_riders) in _TWO.items():
    define_trait(
        _name,
        (2, _PER, {_a: 0.06, _b: 0.06}),
        (4, _PER, {_a: 0.11, _b: 0.11}),
        (6, _PER, {_a: 0.16, _b: 0.16}),
        (8, _PER, {_a: 0.21, _b: 0.21}),
        (10, _PER, _apex_muls, {}, _apex_riders),
    )
