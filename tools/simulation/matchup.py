"""Matchup primitives (T.25).

A *piece* is any roster entry — Champion or Enemy. A *matchup* is two teams
of pieces fighting under one weather. `run_matchup` is the only public unit
of work; it is pure, deterministic, and safe to invoke from worker processes.

Same piece may appear on both sides (mirror); piece ids are suffixed `_a` /
`_b` so the engine's per-id target lookup stays unique. Original ids live
in MatchupConfig for attribution.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.game.combat import resolve_combat
from src.game.content import (
    CHAMPION_ROSTER,
    ENEMY_ROSTER,
    build_champion_at_level,
    build_enemy_at_level,
)
from src.game.models import (
    BattleResult,
    Champion,
    CombatOutcome,
    Enemy,
    WeatherState,
)


SIDE_A_SUFFIX = "_a"
SIDE_B_SUFFIX = "_b"

# Piece ids carry an optional level tag `<base>@<level>`. Level 1 may be
# written bare (`<base>`) for backward compatibility. `@` never appears in a
# roster id, so it is a safe separator.
LEVELS = (1, 2, 3)
LEVEL_SEP = "@"


def make_piece_id(base_id: str, level: int) -> str:
    """Encode a leveled piece id. Level 1 stays bare for back-compat."""
    return base_id if level == 1 else f"{base_id}{LEVEL_SEP}{level}"


def parse_piece_id(piece_id: str) -> tuple[str, int]:
    """Split a (possibly leveled) piece id into (base_id, level)."""
    base, sep, lvl = piece_id.rpartition(LEVEL_SEP)
    if sep and lvl.isdigit():
        return base, int(lvl)
    return piece_id, 1


def base_of(piece_id: str) -> str:
    """Base roster id with any level tag stripped."""
    return parse_piece_id(piece_id)[0]


# ---------------------------------------------------------------------------
# Sim-mode engine cap
# ---------------------------------------------------------------------------


def configure_sim_max_ticks(max_ticks: int) -> None:
    """Raise the combat loop's hard cap so simulations resolve organically
    instead of via the sudden-death DOT.

    The engine ships with `MAX_TICKS = 12_000` (~120s sim time) so the
    auto-resolver finishes quickly in-game. For balance reads that bias
    outcomes against pieces that simply lose the sudden-death race rather
    than the actual fight. Calling this with a large value (e.g.
    1_000_000) effectively disables sudden death for the sim layer.

    Idempotent and process-local — call once per worker. ProcessPoolExecutor
    spawns get a clean import; pass this as `initializer=` to apply.
    """
    if max_ticks <= 0:
        return
    from src.game.combat import engine
    engine.MAX_TICKS = max_ticks
    engine.SUDDEN_DEATH_TICK_START = max_ticks
    engine.HARD_CAP_TICKS = max_ticks + 2_000


def _pool_initializer(max_ticks: int) -> None:
    """ProcessPoolExecutor initializer — sets the cap inside each worker."""
    configure_sim_max_ticks(max_ticks)


# ---------------------------------------------------------------------------
# Type bridges — same piece, both shapes
# ---------------------------------------------------------------------------


def _stat_kwargs(piece: Champion | Enemy) -> dict:
    """Combat-relevant stat fields shared by Champion and Enemy."""
    return {
        "affinity": piece.affinity,
        "role": piece.role,
        "role_code": piece.role_code,
        "intent": piece.intent,
        "tier": piece.tier,
        "level": piece.level,
        "max_hp": piece.max_hp,
        "strength": piece.strength,
        "intelligence": piece.intelligence,
        "attack_speed": piece.attack_speed,
        "move_speed": piece.move_speed,
        "mana_regen": piece.mana_regen,
        "threat": piece.threat,
        "armor": piece.armor,
        "resistance": piece.resistance,
        "attack_range": piece.attack_range,
        "active_ability": piece.active_ability,
        "passive_ability": piece.passive_ability,
        "crit_chance": piece.crit_chance,
        "penetration": piece.penetration,
        "penetration_pct": piece.penetration_pct,
    }


def as_team_piece(piece: Champion | Enemy, *, suffix: str = SIDE_A_SUFFIX) -> Champion:
    """Cast any roster piece into a Champion (team side) with id suffix.

    Traits are dropped — synergy bonuses are opaque to the engine and would
    bias 1v1 power readings. Empty traits list is legal under the Champion
    model.
    """
    return Champion(
        id=piece.id + suffix,
        name=piece.name,
        traits=[],
        **_stat_kwargs(piece),
    )


def as_enemy_piece(piece: Champion | Enemy, *, suffix: str = SIDE_B_SUFFIX) -> Enemy:
    """Cast any roster piece into an Enemy (enemy side) with id suffix."""
    return Enemy(
        id=piece.id + suffix,
        name=piece.name,
        **_stat_kwargs(piece),
    )


def get_piece(piece_id: str) -> Champion | Enemy:
    """Resolve a (possibly leveled) piece id into a level-scaled piece.

    The returned piece's `.id` is the full leveled id so downstream side
    suffixing (`_a`/`_b`) and survivor lookups stay unique per level.
    """
    base, level = parse_piece_id(piece_id)
    if base in CHAMPION_ROSTER:
        piece: Champion | Enemy = build_champion_at_level(base, level)
    elif base in ENEMY_ROSTER:
        piece = build_enemy_at_level(base, level)
    else:
        raise KeyError(f"Unknown piece id: {piece_id!r}")
    piece.id = piece_id
    return piece


def all_piece_ids() -> list[str]:
    """Stable union of champion + enemy roster ids, expanded across all levels."""
    bases = sorted(CHAMPION_ROSTER) + sorted(ENEMY_ROSTER)
    return [make_piece_id(b, lvl) for b in bases for lvl in LEVELS]


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MatchupConfig:
    """One battle's input.

    piece_ids_a and piece_ids_b are raw roster ids (no side suffix). Order
    is preserved into the engine — same input always produces the same
    output (engine is byte-deterministic).
    """
    piece_ids_a: tuple[str, ...]
    piece_ids_b: tuple[str, ...]
    weather: WeatherState

    def __post_init__(self) -> None:
        if not self.piece_ids_a:
            raise ValueError("piece_ids_a must be non-empty")
        if not self.piece_ids_b:
            raise ValueError("piece_ids_b must be non-empty")


@dataclass(frozen=True)
class MatchupResult:
    config: MatchupConfig
    outcome: CombatOutcome
    duration_ticks: int
    hp_remaining_a: int
    hp_remaining_b: int
    timed_out: bool


# ---------------------------------------------------------------------------
# Public unit of work
# ---------------------------------------------------------------------------


def _hp_sum_for_side(
    result: BattleResult,
    *,
    side_ids: tuple[str, ...],
    suffix: str,
) -> int:
    """Sum of remaining HP for survivors on one side.

    HP isn't returned per-piece by BattleResult; engine drops dead pieces.
    Compute via damage_taken vs max_hp from roster lookup; survivors retain
    >0 HP, dead pieces return 0.
    """
    survivors = (
        result.surviving_team_ids
        if suffix == SIDE_A_SUFFIX
        else result.surviving_enemy_ids
    )
    survivor_set = set(survivors)
    total = 0
    for raw_id in side_ids:
        suffixed_id = raw_id + suffix
        if suffixed_id not in survivor_set:
            continue
        piece = get_piece(raw_id)
        damage_taken = result.team_damage_taken.get(suffixed_id, 0)
        total += max(0, piece.max_hp - damage_taken)
    return total


def run_matchup(config: MatchupConfig) -> MatchupResult:
    """Resolve one matchup. Pure function — safe across processes.

    Engine is byte-deterministic; no rng seed required here.
    """
    team = [as_team_piece(get_piece(pid)) for pid in config.piece_ids_a]
    enemies = [as_enemy_piece(get_piece(pid)) for pid in config.piece_ids_b]
    result = resolve_combat(team, enemies, config.weather)

    hp_a = _hp_sum_for_side(result, side_ids=config.piece_ids_a, suffix=SIDE_A_SUFFIX)
    hp_b = _hp_sum_for_side(result, side_ids=config.piece_ids_b, suffix=SIDE_B_SUFFIX)

    return MatchupResult(
        config=config,
        outcome=result.outcome,
        duration_ticks=result.duration_ticks,
        hp_remaining_a=hp_a,
        hp_remaining_b=hp_b,
        timed_out=result.timed_out,
    )
