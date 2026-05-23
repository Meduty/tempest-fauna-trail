"""Encounter generation (T19).

Seed-deterministic procedural generation of enemy squads for FIGHT and REWARD
nodes. Pure functions — no Flet imports, no I/O (V.1, V.2).

All randomness derives from (run_seed, node_index, channel) — no external
state, no clock, no global RNG.
"""
from __future__ import annotations

from random import Random
from typing import Final

from .content import EnemyDef, _ENEMY_DEFS, compose_stats, _ROLE_FROM_AXES, _apply_stat_overrides
from .models import Enemy, WeatherState
from .route import StageDef
from .scaling import power

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
    return d.primary_stat in _SUPPORT_AXES and d.range_ == "ranged" and d.playstyle == "ability"


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
    from .scaling import stat_multiplier as sm

    base = compose_stats(
        d.primary_stat, d.range_, d.durability, d.playstyle, d.tier,
        speed=d.speed, ability_cost=d.ability_cost,
    )
    # Recompute stat scaling for the target level
    if level > 1:
        s = sm(d.tier, level) / sm(d.tier, 1)
        for k in ("max_hp", "strength", "intelligence", "armor", "resistance"):
            base[k] = round(base[k] * s)

    stats = _apply_stat_overrides(base, d.stat_overrides)
    return Enemy(
        id=d.id,
        name=d.name,
        affinity=d.affinity,
        role=_ROLE_FROM_AXES[d.primary_stat][d.range_],
        tier=d.tier,
        level=level,
        max_hp=max(1, stats["max_hp"]),
        strength=max(0, stats["strength"]),
        intelligence=max(0, stats["intelligence"]),
        armor=max(0, stats["armor"]),
        resistance=max(0, stats["resistance"]),
        attack_speed=round(stats["attack_speed"]),
        mana_regen=round(stats["mana_regen"]),
        move_speed=d.move_speed,
        threat=d.threat,
        attack_range=stats["attack_range"],
        ability_cost=d.ability_cost,
        active_ability=d.active_ability,
        passive_ability=d.passive_ability,
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


def shop_seed(run_seed: int, visit_index: int) -> int:
    """Return the sub-seed for champion shop offers at a given visit."""
    return derive_seed(run_seed, visit_index, CH_SHOP)
