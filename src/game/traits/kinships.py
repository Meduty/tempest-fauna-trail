"""Kinship trait breakpoints (T.28a) — stat-pack portions.

Mechanic riders (Beast ramp/lifesteal/enrage, Spirit echo, Skyborn kiting,
Scaled weather-immune, Tidekin HoT/revive, Swarm spawns) are T.28b/c on these
same trait ids. Apex = `min(pool, cap)` (V.37); apex rungs are TEAM_WIDE.
"""

from __future__ import annotations

from . import mechanics as m
from ._packs import define_trait
from .types import TraitScope

_PER = TraitScope.PER_TRAIT_PIECE
_TEAM = TraitScope.TEAM_WIDE

# Beast — pool 14, @2/3/4/6/8. Slow-burn bulk; ramp/lifesteal/enrage = T.28b.
define_trait(
    "Beast",
    (2, _PER, {"hp": 0.08}),
    (3, _PER, {"hp": 0.08, "strength": 0.06}),
    (4, _PER, {"hp": 0.10, "strength": 0.10}),
    (6, _PER, {"hp": 0.14, "strength": 0.14}),
    (8, _TEAM, {"hp": 0.10, "strength": 0.10}, {}, [m.enrage()]),
)

# Spirit — pool 11, @2/3/5/8. Casters; @5 untargetable opener (T.28b) + echo
# (every few casts the next ability fires twice). @8 echoes more often, team-wide
# (caster-gated → no-op for non-casters). Echo potency-cut/pierce/haste = T.28d.
define_trait(
    "Spirit",
    (2, _PER, {"mana_regen": 0.15}),
    (3, _PER, {"mana_regen": 0.20, "intelligence": 0.06}),
    (5, _PER, {"mana_regen": 0.25, "intelligence": 0.12}, {}, [m.untargetable_opener(), m.echo_cadence(4)]),
    (8, _TEAM, {"intelligence": 0.12, "mana_regen": 0.15}, {}, [m.echo_cadence(3)]),
)

# Skyborn — pool 9, @1/2/3/5/8. Kiters. @2 arms kiting + melee +1 range (the
# range bump rides the kiting hook, conditional on base range ≤1). @5 flat +1
# range to all (stat part). @3 stat proxies the kite-reward dmg.
define_trait(
    "Skyborn",
    (1, _PER, {"move_speed": 0.10}),
    (2, _PER, {"attack_speed": 0.08, "move_speed": 0.06}, {}, [m.kiting()]),
    (3, _PER, {"attack_speed": 0.06}),
    (5, _PER, {"attack_speed": 0.08}, {"attack_range": 1.0}),
    (8, _TEAM, {"move_speed": 0.12}),
)

# Scaled — pool 9, @2/3/5/8. Defensive; weather-immune/weather-as-buff = T.28c.
define_trait(
    "Scaled",
    (2, _PER, {"armor": 0.10, "resistance": 0.10}),
    (3, _PER, {"armor": 0.08, "resistance": 0.08}),
    (5, _PER, {"armor": 0.14, "resistance": 0.14}),
    (8, _TEAM, {"armor": 0.10, "resistance": 0.10}),
)

# Tidekin — pool 9, @2/3/5/8. Heal anchor; tidal HoT / team-rescue = T.28b.
define_trait(
    "Tidekin",
    (2, _PER, {"hp": 0.06, "mana_regen": 0.08}),
    (3, _PER, {"hp": 0.08, "mana_regen": 0.12}),
    (5, _PER, {"hp": 0.12, "intelligence": 0.08}, {}, [m.tidal_hot()]),
    (8, _TEAM, {"hp": 0.10}, {}, [m.tidal_hot()]),
)

# Swarm — pool 8, @3/4/5/6/8. Go-wide; a dying Swarm leaves a chitin-spawn that
# inherits a growing fraction of its stats (@6 the most). @8 is TEAM scope but the
# spawn hook is `trait="Swarm"`-guarded, so only actual Swarm pieces spawn.
define_trait(
    "Swarm",
    (3, _PER, {"strength": 0.05, "hp": 0.05}, {}, [m.on_death_spawn(0.35)]),
    (4, _PER, {"strength": 0.07, "hp": 0.07}, {}, [m.on_death_spawn(0.40)]),
    (5, _PER, {"strength": 0.09, "hp": 0.09}, {}, [m.on_death_spawn(0.50)]),
    (6, _PER, {"strength": 0.11, "hp": 0.11}, {}, [m.on_death_spawn(0.60)]),
    (8, _TEAM, {"strength": 0.08, "hp": 0.08}, {}, [m.on_death_spawn(0.60)]),
)
