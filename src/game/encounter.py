"""Encounter generation (T19 + T21).

Seed-deterministic procedural generation of enemy squads for FIGHT, REWARD,
CHALLENGE, and BOSS_FIGHT nodes. Pure functions — no Flet imports, no I/O (V.1, V.2).

All randomness derives from (run_seed, node_index, channel) — no external
state, no clock, no global RNG.

T21 additions:
  generate_challenge()       — champion-faction encounter with 50/30/20 affinity split
  generate_boss_encounter()  — authored boss + supporting cast with map effect
  ChallengeReward            — reward payload for challenge clears
"""
from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import Final

from .content import (
    ChampionDef,
    EnemyDef,
    _CHAMPION_DEFS,
    _ENEMY_DEFS,
    _apply_stat_overrides,
    build_role_code,
    classify_role,
    compose_stats,
    discover_abilities,
)
from .models import Enemy, WeatherState
from .route import StageDef
from .scaling import level_scale_stats, power

# ---------------------------------------------------------------------------
# Seed channels
# ---------------------------------------------------------------------------

CH_ENEMIES: Final[int] = 0
CH_AUGMENT: Final[int] = 1
CH_SUPPLY: Final[int] = 2
CH_REROLL: Final[int] = 3
CH_CHALLENGE: Final[int] = 4
CH_BOSS: Final[int] = 5
CH_SHOP: Final[int] = 6
CH_ECONOMY: Final[int] = 7
CH_REWARD: Final[int] = 8  # Seed channel for REWARD-node loot rolls (T.29a)

# Per-visit reroll stride: folds reroll_count into the shop sub-seed node arg so
# each reroll is deterministic and distinct without colliding across visits. Far
# above any realistic per-node reroll count (each reroll costs Amber).
SHOP_REROLL_STRIDE: Final[int] = 1000

# ---------------------------------------------------------------------------
# Content version (populated from roster hash, used by save/load T14)
# ---------------------------------------------------------------------------

CONTENT_VERSION: Final[str] = "1.0.0"

# ---------------------------------------------------------------------------
# Difficulty Coefficient
# ---------------------------------------------------------------------------

DEFAULT_DC: Final[float] = 1.0
DC_STEP: Final[float] = 1.1


def next_dc(current_dc: float) -> float:
    """Return the next unlockable difficulty coefficient (×1.1)."""
    return round(current_dc * DC_STEP, 4)


def dc_name(dc: float) -> str:
    """Human-readable DC label, e.g. 'DC +0', 'DC +1'."""
    import math
    if dc <= DEFAULT_DC:
        return "DC +0"
    steps = round(math.log(dc / DEFAULT_DC) / math.log(DC_STEP))
    return f"DC +{steps}"

# ---------------------------------------------------------------------------
# Stage base curve
# ---------------------------------------------------------------------------

STAGE_BASE: Final[dict[int, float]] = {
    1: 3.5,
    2: 9.0,
    3: 18.0,
    4: 28.0,
    5: 42.0,
    6: 65.0,
}

STAGE_MAX_SQUAD: Final[dict[int, int]] = {
    1: 4,
    2: 5,
    3: 6,
    4: 7,
    5: 8,
    6: 10,
}

# Type multipliers for node budgets
TYPE_MULT: Final[dict[str, float]] = {
    "fight": 1.0,
    "reward": 0.5,
    "challenge": 1.3,
}

# ---------------------------------------------------------------------------
# Level selection weights by stage
# ---------------------------------------------------------------------------

LEVEL_WEIGHTS: Final[dict[int, tuple[float, float, float]]] = {
    # (L1, L2, L3)
    1: (1.0, 0.0, 0.0),
    2: (0.8, 0.2, 0.0),
    3: (0.5, 0.5, 0.0),
    4: (0.3, 0.6, 0.1),
    5: (0.1, 0.7, 0.2),
    6: (0.0, 0.6, 0.4),
}

# ---------------------------------------------------------------------------
# Tier weighting (soft gates)
# ---------------------------------------------------------------------------

# Preferred tier ranges per stage (inclusive)
PREFERRED_TIERS: Final[dict[int, tuple[int, int]]] = {
    1: (1, 3),
    2: (2, 4),
    3: (3, 5),
    4: (4, 6),
    5: (5, 7),
    6: (6, 9),
}


def _tier_weight(tier: int, stage_index: int) -> float:
    """Soft tier gate: 1.0 for preferred, 0.3 for ±1, 0.1 for further."""
    if tier == 10:
        return 0.0  # T10 is boss-only
    lo, hi = PREFERRED_TIERS[stage_index]
    if lo <= tier <= hi:
        return 1.0
    if lo - 1 <= tier <= hi + 1:
        return 0.3
    return 0.1

# ---------------------------------------------------------------------------
# Seed derivation
# ---------------------------------------------------------------------------


def derive_seed(run_seed: int, node_index: int, channel: int) -> int:
    """Deterministic sub-seed. Integer-only, no hash()."""
    return (run_seed * 2654435761 + node_index * 40503 + channel * 97) & 0xFFFFFFFF

# ---------------------------------------------------------------------------
# Pool filtering
# ---------------------------------------------------------------------------


def filter_pool(
    *,
    faction: str | None = None,
    tier_range: tuple[int, int] | None = None,
) -> list[EnemyDef]:
    """Filter enemy defs by faction/tier. Never returns T10 enemies."""
    pool: list[EnemyDef] = []
    for d in _ENEMY_DEFS:
        if d.tier == 10:
            continue  # T10 reserved for bosses
        if faction is not None and faction not in d.tags:
            continue
        if tier_range is not None:
            if not (tier_range[0] <= d.tier <= tier_range[1]):
                continue
        pool.append(d)
    return pool

# ---------------------------------------------------------------------------
# Affinity slot assignment
# ---------------------------------------------------------------------------


def _affinity_slots(team_size: int, stage_affinity: WeatherState) -> list[WeatherState | None]:
    """Return a list of target affinities per slot (None = any non-clear)."""
    any_slots = max(1, round(0.2 * team_size))
    stage_slots = max(1, round(0.3 * team_size))
    clear_slots = max(0, team_size - any_slots - stage_slots)

    slots: list[WeatherState | None] = []
    slots.extend([WeatherState.CLEAR] * clear_slots)
    slots.extend([stage_affinity] * stage_slots)
    slots.extend([None] * any_slots)  # None = any non-clear
    return slots

# ---------------------------------------------------------------------------
# Composition templates (fuzzy role targets)
# ---------------------------------------------------------------------------

# durability values that count as "tanky"
_TANKY_DURS = frozenset({"tanky_hp", "tanky_arm"})
# ability-focused support indicator
_SUPPORT_AXES = frozenset({"int"})


def _is_tanky(d: EnemyDef) -> bool:
    return d.durability in _TANKY_DURS


def _is_support(d: EnemyDef) -> bool:
    # T.32: support intent is now first-class (`intent == "utility"` on a
    # non-tanky frame) instead of inferred from int/ranged/ability axes.
    return d.intent == "utility" and not _is_tanky(d)


def _is_dps(d: EnemyDef) -> bool:
    return not _is_tanky(d) and not _is_support(d)

# ---------------------------------------------------------------------------
# Squad packing (template-based with fuzzy acceptance)
# ---------------------------------------------------------------------------

BUDGET_TOLERANCE: Final[float] = 0.5
MAX_REROLLS: Final[int] = 5


def _pick_level(rng: Random, stage_index: int, tier: int, remaining_budget: float) -> int:
    """Select enemy level based on stage weights, capped by budget."""
    weights = list(LEVEL_WEIGHTS[stage_index])
    levels = [1, 2, 3]
    # Zero out levels that would exceed remaining budget
    for i, lvl in enumerate(levels):
        if power(tier, lvl) > remaining_budget + BUDGET_TOLERANCE:
            weights[i] = 0.0
    if sum(weights) == 0:
        return 1  # Fallback to L1
    chosen = rng.choices(levels, weights=weights, k=1)[0]
    return chosen


def _weighted_pick(
    rng: Random,
    candidates: list[EnemyDef],
    stage_index: int,
    remaining_budget: float,
) -> EnemyDef | None:
    """Pick one enemy from candidates weighted by tier appropriateness and budget fit."""
    if not candidates:
        return None

    weights: list[float] = []
    for c in candidates:
        tw = _tier_weight(c.tier, stage_index)
        # Budget fit bonus
        cost = power(c.tier, 1)
        if cost > remaining_budget + BUDGET_TOLERANCE:
            weights.append(0.0)
        else:
            fill_ratio = cost / max(remaining_budget, 0.01)
            if fill_ratio < 0.2:
                budget_w = 0.4
            elif fill_ratio <= 0.8:
                budget_w = 1.0
            else:
                budget_w = 0.7
            weights.append(tw * budget_w)

    total = sum(weights)
    if total == 0:
        return None
    return rng.choices(candidates, weights=weights, k=1)[0]


def _instantiate_enemy(d: EnemyDef, level: int) -> Enemy:
    """Build an Enemy instance at the given level."""
    base = compose_stats(
        d.stat, d.reach, d.durability, d.playstyle, d.speed, d.intent, d.tier
    )
    base = _apply_stat_overrides(base, d.stat_overrides)
    level_scale_stats(base, d.tier, level)

    return Enemy(
        id=d.id,
        name=d.name,
        affinity=d.affinity,
        role=classify_role(d.stat, d.reach, d.durability, d.playstyle, d.speed, d.intent),
        role_code=build_role_code(d.stat, d.reach, d.durability, d.playstyle, d.speed, d.intent),
        intent=d.intent,
        tier=d.tier,
        level=level,
        max_hp=max(1, base["max_hp"]),
        strength=max(0, base["strength"]),
        intelligence=max(0, base["intelligence"]),
        armor=max(0, base["armor"]),
        resistance=max(0, base["resistance"]),
        attack_speed=base["attack_speed"],
        mana_regen=round(base["mana_regen"]),
        move_speed=round(base["move_speed"]),
        threat=round(base["threat"]),
        attack_range=base["attack_range"],
        active_abilities=(d.abilities if d.abilities is not None else discover_abilities(d.id)),
        passive_ability=d.passive_ability,
        crit_chance=base["crit_chance"],
        penetration=base["penetration"],
        penetration_pct=base["penetration_pct"],
    )


def _check_composition(squad_defs: list[EnemyDef], squad_size: int) -> bool:
    """Fuzzy composition check — soft guidelines, not hard constraints."""
    if squad_size < 3:
        return True  # Too small to have role requirements

    tank_count = sum(1 for d in squad_defs if _is_tanky(d))
    sup_count = sum(1 for d in squad_defs if _is_support(d))

    # At least 1 tanky for squads >= 3
    if tank_count < 1:
        return False

    # At least 1 support for squads >= 5
    if squad_size >= 5 and sup_count < 1:
        return False

    return True


def roll_squad(
    rng: Random,
    budget: float,
    pool: list[EnemyDef],
    *,
    min_count: int = 2,
    max_count: int = 10,
    max_dupes: int = 2,
    stage_index: int = 1,
    stage_affinity: WeatherState = WeatherState.CLEAR,
) -> list[Enemy]:
    """Template-based squad generation. Deterministic given rng state.

    Args:
        rng: Seeded Random instance (consumed, not stored).
        budget: Total power budget for the squad.
        pool: Available EnemyDef candidates (pre-filtered, no T10).
        min_count: Minimum squad size (padded with cheapest if needed).
        max_count: Maximum squad size.
        max_dupes: Max copies of same enemy type per squad.
        stage_index: Current stage (1-6) for tier/level weighting.
        stage_affinity: Stage's themed weather for affinity slot assignment.

    Returns:
        List of Enemy instances composing the squad.
    """
    if not pool:
        raise ValueError("roll_squad requires a non-empty enemy pool")
    if min_count > max_count:
        raise ValueError("roll_squad requires min_count <= max_count")
    unique_pool_size = len({enemy.id for enemy in pool})
    if unique_pool_size * max_dupes < min_count:
        raise ValueError(
            f"roll_squad cannot satisfy min_count={min_count} "
            f"with max_dupes={max_dupes} and {unique_pool_size} unique enemies in pool"
        )

    best_squad: list[tuple[EnemyDef, int]] | None = None
    best_cost: float = 0.0

    for attempt in range(MAX_REROLLS):
        squad_defs: list[EnemyDef] = []
        squad_levels: list[int] = []
        remaining = budget
        dupe_counts: dict[str, int] = {}

        # Determine target squad size from budget estimate
        avg_cost = power(PREFERRED_TIERS[stage_index][0], 1)
        target_size = min(max_count, max(min_count, round(budget / max(avg_cost, 0.5))))

        # Get affinity slot targets
        affinity_targets = _affinity_slots(target_size, stage_affinity)
        rng.shuffle(affinity_targets)

        for slot_idx in range(target_size):
            if remaining <= 0:
                break

            # Filter by affinity target for this slot
            target_aff = affinity_targets[slot_idx] if slot_idx < len(affinity_targets) else None
            if target_aff is not None:
                aff_pool = [d for d in pool if d.affinity == target_aff]
            else:
                # Any non-clear
                aff_pool = [d for d in pool if d.affinity != WeatherState.CLEAR]

            # Apply dupe limits
            aff_pool = [d for d in aff_pool if dupe_counts.get(d.id, 0) < max_dupes]
            if not aff_pool:
                aff_pool = [d for d in pool if dupe_counts.get(d.id, 0) < max_dupes]
            if not aff_pool:
                break

            pick = _weighted_pick(rng, aff_pool, stage_index, remaining)
            if pick is None:
                continue

            level = _pick_level(rng, stage_index, pick.tier, remaining)
            cost = power(pick.tier, level)

            # Allow slight overshoot
            if cost > remaining + BUDGET_TOLERANCE and len(squad_defs) >= min_count:
                continue

            squad_defs.append(pick)
            squad_levels.append(level)
            remaining -= cost
            dupe_counts[pick.id] = dupe_counts.get(pick.id, 0) + 1

        # Ensure minimum squad size
        while len(squad_defs) < min_count and len(squad_defs) < max_count:
            padding_pool = [d for d in pool if dupe_counts.get(d.id, 0) < max_dupes]
            if not padding_pool:
                break
            cheapest = min(padding_pool, key=lambda e: e.tier)
            squad_defs.append(cheapest)
            squad_levels.append(1)
            dupe_counts[cheapest.id] = dupe_counts.get(cheapest.id, 0) + 1

        # Check composition — accept if ok, or accept unconditionally on last attempt
        comp_ok = _check_composition(squad_defs, len(squad_defs))
        total_cost = sum(power(d.tier, l) for d, l in zip(squad_defs, squad_levels))

        if comp_ok:
            # Accept this squad
            best_squad = list(zip(squad_defs, squad_levels))
            best_cost = total_cost
            break
        if best_squad is None or abs(total_cost - budget) < abs(best_cost - budget):
            best_squad = list(zip(squad_defs, squad_levels))
            best_cost = total_cost
        if attempt == MAX_REROLLS - 1:
            break

    # Build final Enemy instances
    assert best_squad is not None
    return [_instantiate_enemy(d, lvl) for d, lvl in best_squad]

# ---------------------------------------------------------------------------
# Per-node generators
# ---------------------------------------------------------------------------


def generate_fight(
    run_seed: int,
    node_index: int,
    stage: StageDef,
    dc: float = DEFAULT_DC,
) -> list[Enemy]:
    """Generate an enemy squad for a FIGHT node."""
    rng = Random(derive_seed(run_seed, node_index, CH_ENEMIES))
    budget = STAGE_BASE[stage.index] * dc * TYPE_MULT["fight"] * rng.uniform(0.85, 1.15)
    pool = filter_pool()
    max_squad = STAGE_MAX_SQUAD[stage.index]
    return roll_squad(
        rng, budget, pool,
        max_count=max_squad,
        stage_index=stage.index,
        stage_affinity=stage.affinity,
    )


def generate_reward(
    run_seed: int,
    node_index: int,
    stage: StageDef,
    dc: float = DEFAULT_DC,
) -> list[Enemy]:
    """Generate an enemy squad for a REWARD node (half budget)."""
    rng = Random(derive_seed(run_seed, node_index, CH_ENEMIES))
    budget = STAGE_BASE[stage.index] * dc * TYPE_MULT["reward"] * rng.uniform(0.85, 1.15)
    pool = filter_pool()
    max_squad = STAGE_MAX_SQUAD[stage.index]
    return roll_squad(
        rng, budget, pool,
        max_count=max_squad,
        stage_index=stage.index,
        stage_affinity=stage.affinity,
    )


# ---------------------------------------------------------------------------
# REWARD-node loot generation (T.29a)
# ---------------------------------------------------------------------------

# First-pass drop table weights (tunable; final weights in T.22 / §D.12).
#   60% single component · 25% core-cut combined item · 15% two components
_COMPONENT_IDS: list[str] = [
    "fang", "talon", "heartseed", "springtear",
    "old_hide", "stoneplate", "wardpelt", "keen_claw",
]
_CORE_ITEM_IDS: list[str] = [
    "apex_fang", "tempest_talons", "worldroot_bloom", "deepwell",
    "mammoth_hide", "bramble_carapace", "mistward_shroud", "perfect_predator",
    "bloodthorn_briar", "wildfury_lash", "everbloom_staff", "witherbloom_censer",
    "stormglass_totem", "spellfang_crown", "living_bulwark", "splitwind_talons",
]


@dataclass
class RewardLoot:
    """Item loot granted to the player after clearing a REWARD node.

    ``item_ids`` is an ordered list of component and/or combined-item IDs.
    Added to ``Run.inventory`` by the run-manager (T.22).
    """

    item_ids: list[str] = field(default_factory=list)


def generate_reward_loot(
    run_seed: int,
    node_index: int,
) -> RewardLoot:
    """Return seed-deterministic item loot for a REWARD node (T.29a, V.23).

    Drop table (first-pass weights; T.22 / §D.12 refines):
      60% → 1 random base component
      25% → 1 random core-cut combined item
      15% → 2 random base components

    Uses CH_REWARD channel so the roll is independent of the squad roll.
    """
    rng = Random(derive_seed(run_seed, node_index, CH_REWARD))
    roll = rng.random()
    if roll < 0.60:
        return RewardLoot([rng.choice(_COMPONENT_IDS)])
    elif roll < 0.85:
        return RewardLoot([rng.choice(_CORE_ITEM_IDS)])
    else:
        a = rng.choice(_COMPONENT_IDS)
        b = rng.choice(_COMPONENT_IDS)
        return RewardLoot([a, b])

# ---------------------------------------------------------------------------
# Seed-only helpers for T22
# ---------------------------------------------------------------------------


def augment_seed(run_seed: int, node_index: int, rerolled: bool = False) -> int:
    """Return the sub-seed for augment offer generation."""
    channel = CH_REROLL if rerolled else CH_AUGMENT
    return derive_seed(run_seed, node_index, channel)


def supply_seed(run_seed: int, node_index: int, rerolled: bool = False) -> int:
    """Return the sub-seed for supply offer generation."""
    channel = CH_REROLL if rerolled else CH_SUPPLY
    return derive_seed(run_seed, node_index, channel)


def shop_seed(run_seed: int, visit_index: int, reroll_count: int = 0) -> int:
    """Return the sub-seed for champion shop offers at a given visit.

    Each manual reroll within a visit folds ``reroll_count`` into the node arg so
    successive rerolls are deterministic *and* distinct. ``reroll_count=0`` (the
    default) is the free auto-refresh draw on node entry — back-compatible with
    the original single-arg signature.
    """
    return derive_seed(run_seed, visit_index * SHOP_REROLL_STRIDE + reroll_count, CH_SHOP)


def economy_seed(run_seed: int, node_index: int) -> int:
    """Return the sub-seed for per-node Amber income rolls (win bonus)."""
    return derive_seed(run_seed, node_index, CH_ECONOMY)


# ===========================================================================
# T21 — Challenge & Boss Encounters
# ===========================================================================

# ---------------------------------------------------------------------------
# Challenge team sizes per stage (t21_challenge_boss_plan.md §2.2)
# ---------------------------------------------------------------------------

CHALLENGE_TEAM_SIZE: Final[dict[int, int]] = {
    1: 4,
    2: 5,
    3: 7,
    4: 8,
    5: 9,
    6: 11,
}

# Base components thematically linked to each affinity (challenge reward)
AFFINITY_THEMED_COMPONENT: Final[dict[WeatherState, str]] = {
    WeatherState.CLEAR:   "sword",   # direct power, the sunlit warrior
    WeatherState.MIST:    "cloak",   # evasion/resistance, the veiled
    WeatherState.THUNDER: "rod",     # ability power, the channelled storm
    WeatherState.CLOUDY:  "belt",    # HP/endurance, the mountain's weight
    WeatherState.RAIN:    "tear",    # mana/sustain, the flowing river
    WeatherState.SNOW:    "bow",     # attack speed, the patient hunter
}


# ---------------------------------------------------------------------------
# ChallengeReward — payload returned alongside the challenge encounter
# ---------------------------------------------------------------------------


@dataclass
class ChallengeReward:
    """Reward payload for clearing a challenge encounter.

    champion_offer  — id of one champion drawn from the defeated team;
                      the player may recruit this champion.
    component_offer — a random base component id.
    themed_component — a base component themed to the stage affinity.
    amber           — Amber currency granted (= 2 × stage_index).
    tempest_bonus   — extra Tempest beyond the normal +2 per fight.
    """
    champion_offer: str
    component_offer: str
    themed_component: str
    amber: int
    tempest_bonus: int = 1


# ---------------------------------------------------------------------------
# Champion-pool helpers
# ---------------------------------------------------------------------------

# Base component ids (for random component rewards)
_BASE_COMPONENTS: Final[list[str]] = ["bow", "tear", "rod", "belt", "sword", "cloak"]


def _champion_defs_by_affinity() -> dict[WeatherState, list[ChampionDef]]:
    """Return all champion defs (excl. T10 Primordials) grouped by affinity."""
    pool: dict[WeatherState, list[ChampionDef]] = {ws: [] for ws in WeatherState}
    for d in _CHAMPION_DEFS:
        if d.tier == 10:
            continue  # T10 Primordials reserved
        pool[d.affinity].append(d)
    return pool


def _champion_def_to_enemy(d: ChampionDef, level: int = 1) -> "Enemy":
    """Build an Enemy from a ChampionDef at the given level.

    Champions used as challenge enemies retain their stat profile but are
    presented as Enemy objects (opponent-side pieces). Traits are dropped
    (trait synergies are a player-board mechanic only).
    """
    base = compose_stats(
        d.stat, d.reach, d.durability, d.playstyle, d.speed, d.intent, d.tier
    )
    base = _apply_stat_overrides(base, d.stat_overrides)
    level_scale_stats(base, d.tier, level)

    return Enemy(
        id=d.id,
        name=d.name,
        affinity=d.affinity,
        role=classify_role(d.stat, d.reach, d.durability, d.playstyle, d.speed, d.intent),
        role_code=build_role_code(d.stat, d.reach, d.durability, d.playstyle, d.speed, d.intent),
        intent=d.intent,
        tier=d.tier,
        level=level,
        max_hp=max(1, base["max_hp"]),
        strength=max(0, base["strength"]),
        intelligence=max(0, base["intelligence"]),
        armor=max(0, base["armor"]),
        resistance=max(0, base["resistance"]),
        attack_speed=base["attack_speed"],
        mana_regen=round(base["mana_regen"]),
        move_speed=round(base["move_speed"]),
        threat=round(base["threat"]),
        attack_range=base["attack_range"],
        active_abilities=(d.abilities if d.abilities is not None else discover_abilities(d.id)),
        passive_ability=d.passive_ability,
        crit_chance=base["crit_chance"],
        penetration=base["penetration"],
        penetration_pct=base["penetration_pct"],
    )


# ---------------------------------------------------------------------------
# Champion affinity slot assignment for challenges
# ---------------------------------------------------------------------------


def _challenge_affinity_slots(
    team_size: int,
    stage_affinity: WeatherState,
    live_weather: WeatherState,
) -> list[WeatherState]:
    """Return a list of target affinities per slot following the 50/30/20 rule.

    50% stage affinity (challenge identity), 30% live weather affinity
    (weather-driven variety), 20% random (any affinity).
    """
    random_slots = max(1, round(0.20 * team_size))
    live_wx_slots = max(1, round(0.30 * team_size))
    stage_slots = team_size - random_slots - live_wx_slots

    slots: list[WeatherState] = []
    slots.extend([stage_affinity] * stage_slots)
    slots.extend([live_weather] * live_wx_slots)

    # Random slots: one of the 6 affinities (decided during generation)
    all_affinities = list(WeatherState)
    slots.extend([_rng_affinity_placeholder] * random_slots)  # filled during roll
    return slots


# Sentinel to mark "random affinity" slots (replaced during squad build)
_rng_affinity_placeholder = WeatherState.CLEAR  # overridden by rng.choice


def _roll_challenge_squad(
    rng: Random,
    team_size: int,
    stage_affinity: WeatherState,
    live_weather: WeatherState,
    budget: float,
    stage_index: int,
) -> list[Enemy]:
    """Build a challenge squad from the champion roster.

    Follows the 50/30/20 affinity distribution:
      50% stage affinity, 30% live weather, 20% random.
    Excludes T10 Primordials.
    """
    all_affinities = list(WeatherState)
    pool_by_affinity = _champion_defs_by_affinity()

    # Compute slot targets
    random_slots = max(1, round(0.20 * team_size))
    live_wx_slots = max(1, round(0.30 * team_size))
    stage_slots = team_size - random_slots - live_wx_slots

    slot_affinities: list[WeatherState] = (
        [stage_affinity] * stage_slots
        + [live_weather] * live_wx_slots
        + [rng.choice(all_affinities) for _ in range(random_slots)]
    )
    rng.shuffle(slot_affinities)

    squad: list[Enemy] = []
    remaining_budget = budget
    dupe_counts: dict[str, int] = {}
    max_dupes = 2

    for target_affinity in slot_affinities:
        if remaining_budget <= 0:
            break

        candidates = [
            d for d in pool_by_affinity.get(target_affinity, [])
            if dupe_counts.get(d.id, 0) < max_dupes
            and _tier_weight(d.tier, stage_index) > 0
            and power(d.tier, 1) <= remaining_budget + BUDGET_TOLERANCE
        ]
        if not candidates:
            # Fallback: any affinity, affordable
            candidates = [
                d for d in _CHAMPION_DEFS
                if d.tier != 10
                and dupe_counts.get(d.id, 0) < max_dupes
                and power(d.tier, 1) <= remaining_budget + BUDGET_TOLERANCE
            ]
        if not candidates:
            continue

        # Weight by tier appropriateness
        weights = [_tier_weight(d.tier, stage_index) for d in candidates]
        pick: ChampionDef = rng.choices(candidates, weights=weights, k=1)[0]
        level = _pick_level(rng, stage_index, pick.tier, remaining_budget)
        cost = power(pick.tier, level)

        squad.append(_champion_def_to_enemy(pick, level))
        remaining_budget -= cost
        dupe_counts[pick.id] = dupe_counts.get(pick.id, 0) + 1

    # Pad to team_size — budget is a soft quality target; count is a hard design target.
    # Use cheapest available champions (lowest tier, ignoring remaining budget).
    while len(squad) < team_size:
        candidates = [
            d for d in _CHAMPION_DEFS
            if d.tier != 10 and dupe_counts.get(d.id, 0) < max_dupes
        ]
        if not candidates:
            break
        cheapest = min(candidates, key=lambda d: d.tier)
        squad.append(_champion_def_to_enemy(cheapest, 1))
        dupe_counts[cheapest.id] = dupe_counts.get(cheapest.id, 0) + 1

    return squad


# ---------------------------------------------------------------------------
# generate_challenge — public API
# ---------------------------------------------------------------------------


def generate_challenge(
    run_seed: int,
    node_index: int,
    stage: "StageDef",
    live_weather: WeatherState = WeatherState.CLEAR,
    dc: float = DEFAULT_DC,
) -> tuple[list[Enemy], ChallengeReward]:
    """Generate a CHALLENGE encounter and its reward payload.

    The encounter uses the champion faction (not enemies). Affinity is:
      50% stage affinity | 30% live weather | 20% random

    Returns:
        (enemy_squad, ChallengeReward)
    """
    rng = Random(derive_seed(run_seed, node_index, CH_CHALLENGE))
    team_size = CHALLENGE_TEAM_SIZE[stage.index]
    budget = STAGE_BASE[stage.index] * 1.3 * dc * rng.uniform(0.90, 1.10)

    squad = _roll_challenge_squad(
        rng, team_size, stage.affinity, live_weather, budget, stage.index,
    )

    # Build reward
    champion_offer = rng.choice(squad).id if squad else ""
    random_component = rng.choice(_BASE_COMPONENTS)
    themed_component = AFFINITY_THEMED_COMPONENT[stage.affinity]
    amber = 2 * stage.index

    reward = ChallengeReward(
        champion_offer=champion_offer,
        component_offer=random_component,
        themed_component=themed_component,
        amber=amber,
        tempest_bonus=1,
    )
    return squad, reward


# ---------------------------------------------------------------------------
# generate_boss_encounter — public API
# ---------------------------------------------------------------------------


def generate_boss_encounter(
    run_seed: int,
    node_index: int,
    stage: "StageDef",
) -> "BossEncounterResult":
    """Generate a BOSS_FIGHT encounter for the given stage.

    Returns a BossEncounterResult with:
      - The boss Enemy instance (authored stats)
      - The full supporting cast (fixed core + variable adds)
      - The map effect id to apply to the combat context
    """
    from .bosses.data import BossEncounterResult, get_boss_def

    boss_def = get_boss_def(stage.index)
    rng = Random(derive_seed(run_seed, node_index, CH_BOSS))

    # Build boss Enemy object from authored stats
    boss_enemy = boss_def.build_enemy()

    # Build fixed core cast
    supporting_cast: list[Enemy] = []
    for entry in boss_def.fixed_cast:
        for _ in range(entry.count):
            enemy_def = _get_enemy_def(entry.enemy_id)
            if enemy_def is not None:
                supporting_cast.append(_instantiate_enemy(enemy_def, entry.level))

    # Draw variable adds from the pool
    if boss_def.variable_cast_pool and boss_def.variable_cast_count_max > 0:
        n_adds = rng.randint(
            boss_def.variable_cast_count_min,
            boss_def.variable_cast_count_max,
        )
        add_pool_defs = [
            _get_enemy_def(eid)
            for eid in boss_def.variable_cast_pool
            if _get_enemy_def(eid) is not None
        ]
        if add_pool_defs:
            for _ in range(n_adds):
                pick = rng.choice(add_pool_defs)
                supporting_cast.append(_instantiate_enemy(pick, 1))

    return BossEncounterResult(
        stage_index=stage.index,
        boss_def=boss_def,
        boss_enemy=boss_enemy,
        supporting_cast=supporting_cast,
        map_effect_id=boss_def.map_effect_id,
    )


def _get_enemy_def(enemy_id: str) -> EnemyDef | None:
    """Look up an EnemyDef by id. Returns None if not found."""
    for d in _ENEMY_DEFS:
        if d.id == enemy_id:
            return d
    return None
