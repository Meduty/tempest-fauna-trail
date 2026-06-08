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

# Beast — pool 14, @2/3/4/6/8. Slow-burn bulk; @4/@6 strength ramp (T.28d fold-in,
# re-included at @8 alongside the enrage burst).
define_trait(
    "Beast",
    (2, _PER, {"hp": 0.08}),
    (3, _PER, {"hp": 0.08, "strength": 0.06}),
    (4, _PER, {"hp": 0.10, "strength": 0.10}, {}, [m.time_ramp(stat="strength", per=0.02, cap=8)]),
    (6, _PER, {"hp": 0.14, "strength": 0.14}, {}, [m.time_ramp(stat="strength", per=0.03, cap=8)]),
    (8, _TEAM, {"hp": 0.10, "strength": 0.10}, {}, [m.time_ramp(stat="strength", per=0.03, cap=8), m.enrage()]),
)

# Spirit — pool 11, @2/3/5/8. Casters; @5 hexproof opener (T.28b) + echo (every
# few casts the next ability fires twice). @8 echoes MORE often but at reduced
# potency (0.6×), adds mana-haste, and pierces hexproof — caster-gated → no-op for
# non-casters (T.28d).
define_trait(
    "Spirit",
    (2, _PER, {"mana_regen": 0.15}),
    (3, _PER, {"mana_regen": 0.20, "intelligence": 0.06}),
    (5, _PER, {"mana_regen": 0.25, "intelligence": 0.12}, {}, [m.hexproof_opener(), m.echo_cadence(4)]),
    # @8 TEAM: echo goes team-wide (caster-gated, the apex team buff); the hexproof
    # opener + pierce are Spirit SIGNATURES → carrier-guarded so non-casters don't
    # get a free untargetable opener. Opener re-included (cumulative — present @5).
    (8, _TEAM, {"intelligence": 0.12, "mana_regen": 0.20}, {},
        [m.hexproof_opener(trait="Spirit"), m.echo_cadence(3, potency=0.6), m.pierce_hexproof(trait="Spirit")]),
)

# Skyborn — pool 9, @1/2/3/5/8. Kiters. @2 arms kiting + melee +1 range (the
# range bump rides the kiting hook, conditional on base range ≤1); kiting is
# re-included on the @3/@5 PER rungs (cumulative — it was dropped past @2 before,
# a pre-existing bug; B.16). @3 adds kite-reward (bonus vs enemies that can't reach
# back), re-included @5/@8. @5 flat +1 range to all (stat). @8 is the TEAM apex:
# kite-reward goes team-wide (damage buff), but kiting MOVEMENT is NOT re-applied at
# a TEAM apex (the documented movement exception — would make every ally kite).
define_trait(
    "Skyborn",
    (1, _PER, {"move_speed": 0.10}),
    (2, _PER, {"attack_speed": 0.08, "move_speed": 0.06}, {}, [m.kiting()]),
    (3, _PER, {"attack_speed": 0.06}, {}, [m.kiting(), m.kite_reward(0.15)]),
    (5, _PER, {"attack_speed": 0.08}, {"attack_range": 1.0}, [m.kiting(), m.kite_reward(0.15)]),
    (8, _TEAM, {"move_speed": 0.12}, {}, [m.kite_reward(0.15)]),
)

# Scaled — pool 9, @2/3/5/8. Defensive; @5 hard-CC immunity (cc_immune marker →
# apply_status guard); @8 re-includes CC-immunity + full favorable weather override
# (weather_favored, set by the pre-weather marker pass in loadout) (T.28d).
define_trait(
    "Scaled",
    (2, _PER, {"armor": 0.10, "resistance": 0.10}),
    (3, _PER, {"armor": 0.08, "resistance": 0.08}),
    (5, _PER, {"armor": 0.14, "resistance": 0.14}, {}, [m.cc_immunity()]),
    # @8 TEAM: the armor/res pack buffs the whole team (apex), but hard-CC immunity
    # is a Scaled SIGNATURE → carrier-guarded so it doesn't blanket the squad.
    (8, _TEAM, {"armor": 0.10, "resistance": 0.10}, {}, [m.cc_immunity(trait="Scaled")]),
)

# Tidekin — pool 9, @2/3/5/8. Heal anchor; @3 ally-HoT (heals the lowest-HP ally —
# T.28d fold-in, re-included at @5/@8 alongside the carrier tidal_hot); @5/@8 carrier
# tidal HoT (T.28b).
define_trait(
    "Tidekin",
    (2, _PER, {"hp": 0.06, "mana_regen": 0.08}),
    (3, _PER, {"hp": 0.08, "mana_regen": 0.12}, {}, [m.ally_tidal()]),
    (5, _PER, {"hp": 0.12, "intelligence": 0.08}, {}, [m.tidal_hot(), m.ally_tidal()]),
    (8, _TEAM, {"hp": 0.10}, {}, [m.tidal_hot(), m.ally_tidal()]),
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
