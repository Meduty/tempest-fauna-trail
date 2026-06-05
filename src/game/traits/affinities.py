"""Affinity trait breakpoints (T.28a) — `@2/4/6/8/10`, mono apex.

Derived from each piece's `affinity` (V.6) at resolution; never reads node
weather. The `@10` mono rider (snowball/burst-reduction/etc.) is a mechanic →
T.28c; here the @10 rung is the major stat pack. PER_TRAIT_PIECE.
"""

from __future__ import annotations

from ._packs import define_trait
from .types import TraitScope

_PER = TraitScope.PER_TRAIT_PIECE

# Sunlit hits many stats → smaller per-stat pct than the 2-stat affinities.
define_trait(
    "Sunlit",
    (2, _PER, {"strength": 0.04, "intelligence": 0.04, "attack_speed": 0.04, "move_speed": 0.04, "armor": 0.04, "resistance": 0.04, "hp": 0.04}),
    (4, _PER, {"strength": 0.07, "intelligence": 0.07, "attack_speed": 0.07, "move_speed": 0.07, "armor": 0.07, "resistance": 0.07, "hp": 0.07}),
    (6, _PER, {"strength": 0.10, "intelligence": 0.10, "attack_speed": 0.10, "move_speed": 0.10, "armor": 0.10, "resistance": 0.10, "hp": 0.10}),
    (8, _PER, {"strength": 0.13, "intelligence": 0.13, "attack_speed": 0.13, "move_speed": 0.13, "armor": 0.13, "resistance": 0.13, "hp": 0.13}),
    (10, _PER, {"strength": 0.16, "intelligence": 0.16, "attack_speed": 0.16, "move_speed": 0.16, "armor": 0.16, "resistance": 0.16, "hp": 0.16}),
)

_TWO = {
    "Overcast": ("hp", "resistance"),
    "Stormfed": ("attack_speed", "mana_regen"),
    "Frostbound": ("armor", "resistance"),
    "Galvanized": ("strength", "attack_speed"),
    "Shrouded": ("move_speed", "threat"),
}

for _name, (_a, _b) in _TWO.items():
    define_trait(
        _name,
        (2, _PER, {_a: 0.06, _b: 0.06}),
        (4, _PER, {_a: 0.11, _b: 0.11}),
        (6, _PER, {_a: 0.16, _b: 0.16}),
        (8, _PER, {_a: 0.21, _b: 0.21}),
        (10, _PER, {_a: 0.27, _b: 0.27}),
    )
