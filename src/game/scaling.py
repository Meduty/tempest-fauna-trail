"""Power scaling model (T18).

P(T, L) = 1.5 ** ((T - 1) / 2 + (L - 1))

Two tier steps equal one level step: P(T+2, L) == P(T, L+1).
Stat multiplier is sqrt(P) so that HP*DPS (≈combat value) grows linearly with P.
"""
import math

# Per-tier and per-level multipliers on the raw power scalar P.
TIER_STEP: float = 1.5**0.5   # ≈1.2247 — per-tier power multiplier (ratio)
LEVEL_STEP: float = 1.5        # per-level power multiplier (ratio)

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

    P(T, L) = 1.5 ** ((T - 1) / 2 + (L - 1))

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
    exponent = (tier - 1) / 2 + (level - 1)
    return 1.5**exponent


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
