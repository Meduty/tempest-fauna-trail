"""Tournament generation + execution (T.25).

Three battle generators:
    enumerate_1v1   — every unordered pair of distinct pieces (C(N,2))
    enumerate_team2 — every unordered pair of disjoint 2-piece teams
    sample_teams    — random N-piece teams paired up; seeded for determinism

Plus `run_tournament` which executes a list[MatchupConfig] sequentially or
through a ProcessPoolExecutor when workers > 1.
"""
from __future__ import annotations

import itertools
import random
from concurrent.futures import ProcessPoolExecutor
from typing import Iterable

from src.game.models import WeatherState

from tools.simulation.matchup import (
    MatchupConfig,
    MatchupResult,
    _pool_initializer,
    all_piece_ids,
    base_of,
    configure_sim_max_ticks,
    get_piece,
    run_matchup,
)


# ---------------------------------------------------------------------------
# Enumerators
# ---------------------------------------------------------------------------


def enumerate_1v1(
    weather: WeatherState,
    *,
    piece_ids: list[str] | None = None,
) -> list[MatchupConfig]:
    """All unordered pairs of distinct pieces (no self-mirrors).

    Pairs sharing a base champ — e.g. the same champion at two levels — are
    excluded (no dupe of the same champ in one fight).
    """
    pieces = piece_ids if piece_ids is not None else all_piece_ids()
    configs: list[MatchupConfig] = []
    for a, b in itertools.combinations(pieces, 2):
        if base_of(a) == base_of(b):
            continue
        configs.append(MatchupConfig(piece_ids_a=(a,), piece_ids_b=(b,), weather=weather))
    return configs


def enumerate_team2(
    weather: WeatherState,
    *,
    piece_ids: list[str] | None = None,
) -> list[MatchupConfig]:
    """All unordered pairs of disjoint 2-piece teams.

    Output size grows as C(C(N,2), 2) minus configs where teams share a
    piece. With N=120 that is roughly 25 million configs — caller MUST
    confirm runtime budget before invoking.
    """
    pieces = piece_ids if piece_ids is not None else all_piece_ids()
    # No dupe of the same base champ within a team.
    teams = [
        t for t in itertools.combinations(pieces, 2)
        if base_of(t[0]) != base_of(t[1])
    ]
    configs: list[MatchupConfig] = []
    for team_a, team_b in itertools.combinations(teams, 2):
        bases_a = {base_of(p) for p in team_a}
        bases_b = {base_of(p) for p in team_b}
        if bases_a & bases_b:
            continue
        configs.append(
            MatchupConfig(piece_ids_a=team_a, piece_ids_b=team_b, weather=weather)
        )
    return configs


def sample_teams(
    weather: WeatherState,
    team_size: int,
    n_battles: int,
    *,
    seed: int = 42,
    piece_ids: list[str] | None = None,
    tier_stratified: bool = False,
) -> list[MatchupConfig]:
    """Sample `n_battles` random matchups of two disjoint team_size teams.

    With `tier_stratified=True`, both teams' pieces are drawn from a
    randomly chosen tier band — keeps the matchup at a comparable power
    budget so resulting win rates aren't dominated by tier differential.

    Seeded `random.Random` — same (weather, team_size, n_battles, seed,
    piece_ids) always returns the same list[MatchupConfig].
    """
    if team_size < 1:
        raise ValueError(f"team_size must be >= 1, got {team_size}")
    if n_battles < 0:
        raise ValueError(f"n_battles must be >= 0, got {n_battles}")

    pieces = piece_ids if piece_ids is not None else all_piece_ids()
    # Dedupe by base champ means distinct base count, not raw id count, is
    # what bounds team formation.
    n_bases = len({base_of(p) for p in pieces})
    if n_bases < 2 * team_size:
        raise ValueError(
            f"Need >= {2 * team_size} distinct base champs to sample "
            f"{team_size}v{team_size} teams (have {n_bases})"
        )

    rng = random.Random(seed)

    pool_by_tier: dict[int, list[str]] = {}
    if tier_stratified:
        for pid in pieces:
            tier = get_piece(pid).tier
            pool_by_tier.setdefault(tier, []).append(pid)
        usable_tiers = [
            t for t, ids in pool_by_tier.items()
            if len({base_of(p) for p in ids}) >= 2 * team_size
        ]
        if not usable_tiers:
            raise ValueError(
                f"No tier has >= {2 * team_size} pieces for stratified sampling"
            )

    configs: list[MatchupConfig] = []
    seen: set[tuple[tuple[str, ...], tuple[str, ...], WeatherState]] = set()
    # Bounded attempts so a saturated sample space doesn't loop forever.
    max_attempts = n_battles * 10 + 100
    attempts = 0
    while len(configs) < n_battles and attempts < max_attempts:
        attempts += 1
        if tier_stratified:
            tier = rng.choice(usable_tiers)
            pool = pool_by_tier[tier]
        else:
            pool = pieces
        drawn = rng.sample(pool, 2 * team_size)
        # No dupe of the same base champ anywhere in the fight (both teams).
        if len({base_of(p) for p in drawn}) < len(drawn):
            continue
        team_a = tuple(sorted(drawn[:team_size]))
        team_b = tuple(sorted(drawn[team_size:]))
        # Canonicalise so (A,B) and (B,A) dedupe identically.
        if team_a > team_b:
            team_a, team_b = team_b, team_a
        key = (team_a, team_b, weather)
        if key in seen:
            continue
        seen.add(key)
        configs.append(
            MatchupConfig(piece_ids_a=team_a, piece_ids_b=team_b, weather=weather)
        )
    return configs


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def run_tournament(
    configs: Iterable[MatchupConfig],
    *,
    workers: int = 1,
    max_ticks: int = 0,
) -> list[MatchupResult]:
    """Resolve every config in order. Multi-process when workers > 1.

    Engine determinism means there's no variance to reduce — every
    config is run exactly once. Pass `max_ticks > 0` to raise the combat
    engine's hard cap (default 12000) for sim-mode runs that should
    resolve organically without the sudden-death DOT — see
    `matchup.configure_sim_max_ticks`.
    """
    configs_list = list(configs)
    if workers <= 1:
        configure_sim_max_ticks(max_ticks)
        return [run_matchup(cfg) for cfg in configs_list]

    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=_pool_initializer,
        initargs=(max_ticks,),
    ) as pool:
        return list(pool.map(run_matchup, configs_list, chunksize=64))
