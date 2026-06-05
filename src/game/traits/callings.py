"""Calling trait breakpoints (T.28a) — stat-pack portions.

No emblems → apex sits at the native pool (V.37). Mechanic riders (Hunter
empowered shot, Mystic ability-crit/splash, Guardian/Warden shields, Stalker
backline-target/untargetable, Channeler free-cast, Mender revive, Trickster
debuff/aura, Packmate full-board scaling, Primordial second-wind) are T.28b/c on
these same trait ids. Apex rungs TEAM_WIDE.
"""

from __future__ import annotations

from . import mechanics as m
from .types import TraitScope
from ._packs import define_trait

_PER = TraitScope.PER_TRAIT_PIECE
_TEAM = TraitScope.TEAM_WIDE

# Hunter — pool 8, @2/4/6/8. Ranged carries; empowered/pierce/cleave = T.28c.
define_trait(
    "Hunter",
    (2, _PER, {"strength": 0.08}),
    (4, _PER, {"strength": 0.10, "attack_speed": 0.08}),
    (6, _PER, {"strength": 0.12}, {"attack_range": 1.0}),
    (8, _TEAM, {"strength": 0.10}),
)

# Mystic — pool 8, @2/3/5/8. Mages; ability-crit (@5) + splash = T.28b/c.
define_trait(
    "Mystic",
    (2, _PER, {"intelligence": 0.10}),
    (3, _PER, {"intelligence": 0.08}),
    (5, _PER, {"intelligence": 0.14}),
    (8, _TEAM, {"intelligence": 0.12}),
)

# Guardian — pool 9, @2/3/4/6/8. Shields = T.28b; stat = armor/hp.
define_trait(
    "Guardian",
    (2, _PER, {"armor": 0.10, "hp": 0.06}),
    (3, _PER, {"armor": 0.08, "hp": 0.06}),
    (4, _PER, {"armor": 0.10, "hp": 0.08}),
    (6, _PER, {"armor": 0.14, "hp": 0.10}),
    (8, _TEAM, {"armor": 0.08, "hp": 0.06}),
)

# Bruiser — pool 8, @2/4/6/8. Lifesteal = T.28c; stat = hp/str.
define_trait(
    "Bruiser",
    (2, _PER, {"hp": 0.10}),
    (4, _PER, {"hp": 0.10, "strength": 0.08}),
    (6, _PER, {"hp": 0.12, "strength": 0.12}),
    (8, _TEAM, {"hp": 0.08, "strength": 0.08}),
)

# Skirmisher — pool 8, @2/3/4/5/8. AS ramp/dodge = T.28b; stat = as/ms.
define_trait(
    "Skirmisher",
    (2, _PER, {"attack_speed": 0.08}, {}, [m.time_ramp()]),
    (3, _PER, {"attack_speed": 0.06}),
    (4, _PER, {"attack_speed": 0.06, "move_speed": 0.10}, {}, [m.dodge()]),
    (5, _PER, {"attack_speed": 0.08}),
    (8, _TEAM, {"attack_speed": 0.10}),
)

# Stalker — pool 7, @2/3/5/7. Backline-target/untargetable = T.28b/c; stat = ms/str.
define_trait(
    "Stalker",
    (2, _PER, {"move_speed": 0.10, "strength": 0.06}),
    (3, _PER, {"strength": 0.08}),
    (5, _PER, {"strength": 0.12}),
    (7, _PER, {"strength": 0.14}),
)

# Channeler — pool 7, @1/2/4/7. Free/double-cast = T.28c; stat = mana_regen.
define_trait(
    "Channeler",
    (1, _PER, {"mana_regen": 0.12}),
    (2, _PER, {"mana_regen": 0.10}),
    (4, _PER, {"mana_regen": 0.18}),
    (7, _TEAM, {"mana_regen": 0.15}),
)

# Warden — pool 6, @1/2/4/6. Ally shields = T.28b; stat = defensive splash.
define_trait(
    "Warden",
    (1, _PER, {"mana_regen": 0.08}),
    (2, _PER, {"armor": 0.06, "resistance": 0.06}),
    (4, _PER, {"armor": 0.08, "resistance": 0.08}),
    (6, _TEAM, {"armor": 0.06, "resistance": 0.06}),
)

# Trickster — pool 6, @2/3/4/6. Debuff/taunt/aura = T.28b/c; stat = threat/int.
define_trait(
    "Trickster",
    (2, _PER, {"threat": 0.10, "intelligence": 0.06}),
    (3, _PER, {"intelligence": 0.06}),
    (4, _PER, {"intelligence": 0.08}),
    (6, _TEAM, {"intelligence": 0.06}),
)

# Mender — pool 6, @1/2/4/6. Heal amp/overheal-shield/revive = T.28b; stat proxy.
define_trait(
    "Mender",
    (1, _PER, {"mana_regen": 0.08}),
    (2, _PER, {"intelligence": 0.06, "mana_regen": 0.08}),
    (4, _PER, {"intelligence": 0.08}),
    (6, _TEAM, {"hp": 0.06}),
)

# Packmate — pool 8, @2/3/4/6/full-board. TEAM_WIDE; @full = dynamic == fielded
# board size. Per-count scaling of the bonus is T.28c; stat proxy now.
define_trait(
    "Packmate",
    (2, _TEAM, {"strength": 0.04, "hp": 0.04}),
    (3, _TEAM, {"strength": 0.05, "hp": 0.05}),
    (4, _TEAM, {"strength": 0.06, "hp": 0.06}),
    (6, _TEAM, {"strength": 0.08, "hp": 0.08}),
    ((lambda team, cap: cap), _TEAM, {"strength": 0.10, "hp": 0.10, "attack_speed": 0.06}),
)

# Primordial — pool 6, @1/2/3. Augment-gated (V.37). Second wind = T.28b.
# @1 buffs the legendary itself (PER); @2/@3 team packs.
define_trait(
    "Primordial",
    (1, _PER, {"strength": 0.10, "intelligence": 0.10, "hp": 0.10}),
    (2, _TEAM, {"strength": 0.10, "intelligence": 0.10, "hp": 0.10}, {}, [m.second_wind()]),
    (3, _TEAM, {"strength": 0.14, "intelligence": 0.14, "hp": 0.14}),
)
