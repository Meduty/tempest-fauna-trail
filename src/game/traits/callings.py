"""Calling trait breakpoints — stat packs (T.28a) + mechanic/apex riders (T.28b/c).

No emblems → apex sits at the native pool (V.37). Apex rungs are TEAM_WIDE.

**Cumulative rungs:** trait resolution applies only the *highest cleared* rung's
bundle (see `traits/__init__._resolve_traits`), so every rung re-includes the
mechanic riders it should still grant. Carrier-movement mechanics (kiting,
backline) are *not* re-applied at a TEAM apex — apex trades the few-carrier
identity for a team-wide buff (caster/role-gated hooks like echo/splash/lifesteal
are team-safe and stay).

T.28d adds the subsystem-heavy/dormant riders (Primordial @1 kits, @3 tier-up).
"""

from __future__ import annotations

from . import mechanics as m
from .types import TraitScope
from ._packs import define_trait

_PER = TraitScope.PER_TRAIT_PIECE
_TEAM = TraitScope.TEAM_WIDE

# Hunter — pool 8, @2/4/6/8. Ranged carries: bonus auto → empowered → cleave →
# team auto-damage aura. @6 also adds +1 Attack Range (stat).
define_trait(
    "Hunter",
    (2, _PER, {"strength": 0.08}, {}, [m.bonus_auto_damage(0.12)]),
    (4, _PER, {"strength": 0.10, "attack_speed": 0.08}, {}, [m.bonus_auto_damage(0.12), m.empowered_shot(4, 0.8)]),
    (6, _PER, {"strength": 0.12}, {"attack_range": 1.0}, [m.bonus_auto_damage(0.15), m.empowered_shot(4, 0.9), m.cleave(0.30)]),
    (8, _TEAM, {"strength": 0.10}, {}, [m.bonus_auto_damage(0.12), m.empowered_shot(4, 0.8), m.cleave(0.35)]),
)

# Mystic — pool 8, @2/3/5/8. Mages; @5 ability-crit + splash, @8 double-splash +
# team AP (stat).
define_trait(
    "Mystic",
    (2, _PER, {"intelligence": 0.10}),
    (3, _PER, {"intelligence": 0.08}),
    (5, _PER, {"intelligence": 0.14}, {}, [m.ability_crit(), m.ability_splash(0.40, 1)]),
    (8, _TEAM, {"intelligence": 0.12}, {}, [m.ability_crit(), m.ability_splash(0.45, 2)]),
)

# Guardian — pool 9, @2/3/4/6/8. Start shield grows; @6+ round-refresh shields
# self + adjacent allies; @8 team bastion.
define_trait(
    "Guardian",
    (2, _PER, {"armor": 0.10, "hp": 0.06}, {}, [m.start_shield(0.18)]),
    (3, _PER, {"armor": 0.08, "hp": 0.06}, {}, [m.start_shield(0.24)]),
    (4, _PER, {"armor": 0.10, "hp": 0.08}, {}, [m.start_shield(0.30)]),
    (6, _PER, {"armor": 0.14, "hp": 0.10}, {}, [m.start_shield(0.30), m.periodic_shield(600, 0.15, 600, allies=True)]),
    (8, _TEAM, {"armor": 0.08, "hp": 0.06}, {}, [m.start_shield(0.25), m.periodic_shield(600, 0.15, 600, allies=True)]),
)

# Bruiser — pool 8, @2/4/6/8. @6 attack-lifesteal, @8 team-wide lifesteal.
define_trait(
    "Bruiser",
    (2, _PER, {"hp": 0.10}),
    (4, _PER, {"hp": 0.10, "strength": 0.08}),
    (6, _PER, {"hp": 0.12, "strength": 0.12}, {}, [m.attack_lifesteal(0.12)]),
    (8, _TEAM, {"hp": 0.08, "strength": 0.08}, {}, [m.attack_lifesteal(0.12)]),
)

# Skirmisher — pool 8, @2/3/4/5/8. AS ramp (@2, COMBAT-lifetime → never decays) +
# dodge (@4); @8 extends ramp+dodge to the team.
define_trait(
    "Skirmisher",
    (2, _PER, {"attack_speed": 0.08}, {}, [m.time_ramp()]),
    (3, _PER, {"attack_speed": 0.06}, {}, [m.time_ramp()]),
    (4, _PER, {"attack_speed": 0.06, "move_speed": 0.10}, {}, [m.time_ramp(), m.dodge()]),
    (5, _PER, {"attack_speed": 0.08}, {}, [m.time_ramp(), m.dodge()]),
    (8, _TEAM, {"attack_speed": 0.10}, {}, [m.time_ramp(), m.dodge()]),
)

# Stalker — pool 7, @2/3/5/7. Backline target-priority (@2); @5 hi-HP bonus dmg +
# mana on takedown; @7 brief hexproof after a takedown. PER apex (no team).
define_trait(
    "Stalker",
    (2, _PER, {"move_speed": 0.10, "strength": 0.06}, {}, [m.backline_seeker()]),
    (3, _PER, {"strength": 0.08}, {}, [m.backline_seeker()]),
    (5, _PER, {"strength": 0.12}, {}, [m.backline_seeker(), m.high_hp_bonus(0.20, 0.6), m.mana_on_kill()]),
    (7, _PER, {"strength": 0.14}, {}, [m.backline_seeker(), m.high_hp_bonus(0.25, 0.6), m.mana_on_kill(), m.hexproof_after_kill(120)]),
)

# Channeler — pool 7, @1/2/4/7. @4 free-cast cadence; @7 first cast triggers twice
# + team ability-haste (mana_regen stat).
define_trait(
    "Channeler",
    (1, _PER, {"mana_regen": 0.12}),
    (2, _PER, {"mana_regen": 0.10}),
    (4, _PER, {"mana_regen": 0.18}, {}, [m.free_cast(3)]),
    (7, _TEAM, {"mana_regen": 0.15}, {}, [m.free_cast(3), m.recast_first()]),
)

# Warden — pool 6, @1/2/4/6. Cast shields the lowest-HP ally; @6 adds a team
# opening shield.
define_trait(
    "Warden",
    (1, _PER, {"mana_regen": 0.08}, {}, [m.cast_shield_lowest(0.15)]),
    (2, _PER, {"armor": 0.06, "resistance": 0.06}, {}, [m.cast_shield_lowest(0.18)]),
    (4, _PER, {"armor": 0.08, "resistance": 0.08}, {}, [m.cast_shield_lowest(0.22)]),
    (6, _TEAM, {"armor": 0.06, "resistance": 0.06}, {}, [m.cast_shield_lowest(0.20), m.start_shield(0.20)]),
)

# Trickster — pool 6, @2/3/4/6. Casts slow (@2) + taunt the nearest enemy (@3+);
# @6 mana-denial aura on adjacent enemies.
define_trait(
    "Trickster",
    (2, _PER, {"threat": 0.10, "intelligence": 0.06}, {}, [m.slow_on_cast()]),
    (3, _PER, {"intelligence": 0.06}, {}, [m.slow_on_cast(), m.taunt_on_cast()]),
    (4, _PER, {"intelligence": 0.08}, {}, [m.slow_on_cast(), m.taunt_on_cast()]),
    (6, _TEAM, {"intelligence": 0.06}, {}, [m.slow_on_cast(), m.taunt_on_cast(), m.mana_denial_aura()]),
)

# Mender — pool 6, @1/2/4/6. Heal-splash (@1); @4 overheal → shield; @6 the one
# true revive (V.37, T.28b).
define_trait(
    "Mender",
    (1, _PER, {"mana_regen": 0.08}, {}, [m.heal_splash(0.25)]),
    (2, _PER, {"intelligence": 0.06, "mana_regen": 0.08}, {}, [m.heal_splash(0.30)]),
    (4, _PER, {"intelligence": 0.08}, {}, [m.heal_splash(0.30), m.overheal_shield(0.30)]),
    (6, _TEAM, {"hp": 0.06}, {}, [m.heal_splash(0.30), m.overheal_shield(0.30), m.revive_first_ally()]),
)

# Packmate — pool 8, @2/3/4/6/full-board. TEAM_WIDE; @full = dynamic == fielded
# board size. The flat stat pack *is* the @full-board payoff (the anti-churn aura).
define_trait(
    "Packmate",
    (2, _TEAM, {"strength": 0.04, "hp": 0.04}),
    (3, _TEAM, {"strength": 0.05, "hp": 0.05}),
    (4, _TEAM, {"strength": 0.06, "hp": 0.06}),
    (6, _TEAM, {"strength": 0.08, "hp": 0.08}),
    ((lambda team, cap: cap), _TEAM, {"strength": 0.10, "hp": 0.10, "attack_speed": 0.06}),
)

# Primordial — pool 6, @1/2/3. Augment-gated (V.37), ships dormant. @2 second wind
# (T.28b, team-wide per catalog); @3 re-includes it (cumulative, V.41). @1 signature
# mechanics + @3 aspirational tier-up = T.31 (D.20).
define_trait(
    "Primordial",
    (1, _PER, {"strength": 0.10, "intelligence": 0.10, "hp": 0.10}),
    (2, _TEAM, {"strength": 0.10, "intelligence": 0.10, "hp": 0.10}, {}, [m.second_wind()]),
    (3, _TEAM, {"strength": 0.14, "intelligence": 0.14, "hp": 0.14}, {}, [m.second_wind()]),
)

# Multicaster — pool 6 (the T.29d showcase champs), @2/3/4. Quick-caster: stack
# attack_speed + mana_regen per cast (cast_momentum); no team apex (apex =
# min(pool, cap), V.37). Per-trait throughout — the few-carrier quick-cast identity.
define_trait(
    "Multicaster",
    (2, _PER, {"attack_speed": 0.06, "mana_regen": 0.10}, {}, [m.cast_momentum(per=0.04, cap=5)]),
    (3, _PER, {"attack_speed": 0.06, "mana_regen": 0.10}, {}, [m.cast_momentum(per=0.05, cap=6)]),
    (4, _PER, {"attack_speed": 0.08, "mana_regen": 0.14}, {}, [m.cast_momentum(per=0.06, cap=8)]),
)
