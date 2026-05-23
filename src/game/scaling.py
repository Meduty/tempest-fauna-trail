"""Power scaling model (T18).

P(T, L) = TIER_UP_MOD^(T-1) * LEVEL_UP_MOD^triplings(L)

where LEVEL_UP_MOD = 2, TIER_UP_MOD = cbrt(2), and
triplings = {L1: 0, L2: 1, L3: 3}.

Equivalently: P(T, L) = 2 ^ ((T-1)/3 + triplings(L)).

Level-ups use a "tripling" mechanic — you need 3 copies to go from L1→L2
(1 tripling), then 3 more L2 copies to reach L3 (3 total triplings fed in).
This gives an *accelerating* curve: L2 is a modest bump, L3 is a big spike.

Stat multiplier is sqrt(P) so that HP*DPS (≈combat value) grows linearly
with P, keeping encounter budgets linear.

Per-tier stat gain:  2^(1/6) ≈ 1.122 (≈12% per tier)
L1→L2 stat gain:    2^0.5   ≈ 1.414
L2→L3 stat gain:    2^1.0   = 2.000
L1→L3 stat gain:    2^1.5   ≈ 2.828
Total T1L1→T10L3:   2^3.0   = 8.0× in stats
"""
import math

# Base multiplier per "tripling" of copies (mirrors TFT's 3-to-1 combine).
LEVEL_UP_MOD: float = 2.0

# Per-tier power multiplier = cbrt(LEVEL_UP_MOD). Three tier-ups = one tripling step in power.
TIER_UP_MOD: float = LEVEL_UP_MOD ** (1 / 3)  # ≈ 1.2599

# Cumulative triplings fed to reach each level.
# L1 = base (0), L2 = 1 tripling, L3 = 3 triplings (1 tripling of L2 copies).
TRIPLINGS: dict[int, int] = {1: 0, 2: 1, 3: 3}

# Legacy aliases for backward compatibility.
LEVEL_STEP: float = LEVEL_UP_MOD
TIER_STEP: float = TIER_UP_MOD

# Stats scaled by stat_multiplier.  Flat stats (attack_speed, mana_regen,
# move_speed, attack_range, threat, ability_cost) are NOT in this tuple.
SCALABLE_STATS: tuple[str, ...] = (
    "max_hp",
    "strength",
    "intelligence",
    "armor",
    "resistance",
)


def power(tier: int, level: int) -> float:
    """Abstract power scalar for a piece at *tier* T and *level* L.

    P(T, L) = TIER_UP_MOD^(T-1) * LEVEL_UP_MOD^triplings(L)
            = 2 ^ ((T-1)/3 + triplings[L])

    Args:
        tier:  Piece tier, integer in [1, 10].
        level: Piece level, integer in [1, 3].

    Returns:
        Raw power scalar ≥ 1.0.

    Raises:
        ValueError: If tier not in [1, 10] or level not in [1, 3].
    """
    if not (1 <= tier <= 10):
        raise ValueError(f"tier must be in [1, 10], got {tier}")
    if not (1 <= level <= 3):
        raise ValueError(f"level must be in [1, 3], got {level}")
    exponent = (tier - 1) / 3 + TRIPLINGS[level]
    return LEVEL_UP_MOD**exponent


def stat_multiplier(tier: int, level: int) -> float:
    """Stat multiplier = sqrt(power(T, L)).

    Each scaled stat grows with sqrt(P) so that HP*DPS ∝ P, keeping
    encounter budgets linear.

    Args:
        tier:  Piece tier, integer in [1, 10].
        level: Piece level, integer in [1, 3].

    Returns:
        Multiplier ≥ 1.0 to apply to base stats.
    """
    return math.sqrt(power(tier, level))


def scale_stat(base: int, tier: int, level: int) -> int:
    """Apply T18 stat scaling to a single base value.

    Args:
        base:  Base stat value at T1 L1.
        tier:  Target tier, integer in [1, 10].
        level: Target level, integer in [1, 3].

    Returns:
        Scaled integer stat value.
    """
    return round(base * stat_multiplier(tier, level))
