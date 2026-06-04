"""Weather-system impact sim (T.25 extension).

Measures *how much the two weather systems actually swing outcomes* at large
team sizes (default 8v8), by team composition rather than per-piece power.

Two systems, decoupled in `src/game/weather_effects.py`, are probed
independently and together:

  * **System A — Weather Favor** (`combat_modifier`): the node weather buffs/
    debuffs each piece by its affinity at combat init. "Who thrives under these
    conditions?" Probed by `--system A`.
  * **System B — Affinity Clash** (`damage_modifier`): a per-hit attacker-vs-
    defender multiplier on the predator/prey ring, weather-independent. "Do I
    beat this enemy?" Probed by `--system B`.

Isolation strategy — `CLEAR` affinity is inert in *both* systems (Weather Favor
returns IDENTITY for clear pieces and under clear weather; Affinity Clash returns
1.0 for any matchup touching clear). So:

  * To isolate **A**: make the enemy team all-`clear` and vary how many of the
    player's pieces are the *own-weather* affinity under node weather `W`. Clear
    fillers + clear enemies neutralise Clash, leaving only Favor. A matched
    control run at `CLEAR` weather (Favor off, same configs) is subtracted to
    strip out raw champ-design bias — the residual is pure Weather Favor.
  * To isolate **B**: fight at `CLEAR` weather (Favor off for everyone) and pit
    a mono-affinity-X team against a mono-affinity-Y team across every ring
    relation. Only the per-hit Clash multiplier differs.
  * To see them **overlap** (`--system AB`): under node weather `W`, a mono-`W`
    team (buffed *and* favourable clash vs its prey) against a mono-other team.
    The user's litmus: full-rain vs full-snow under rain should be decisive.

Equal power budget by construction: power depends only on (tier, level), so both
teams always draw the *same multiset of tiers* for a given sample — only the
affinity filling each tier-slot changes. Champ-design statline noise within a
tier is washed out by sampling many tier-windows per cell.

Determinism: the combat engine is byte-deterministic, so a single config has a
fixed win/loss. Meaningful win *rates* therefore come from sampling many distinct
team assemblies (tier-windows, which slots carry the own-weather affinity) per
cell with a seeded RNG (V.2/V.14 — no engine RNG touched).

Why an HP-*margin* metric, not just win rate — an 8-piece team that spans 8
distinct tiers has a top piece worth ~5× a bottom piece (power 2^((T-1)/3)), so
binary win/loss is dominated by the strongest piece's duel and carries huge
variance: it measures "did the weather tip the top duel?" not "how much does the
weather matter?". The normalised surviving-HP margin
`(hp_a - hp_b)/(hp_a + hp_b) ∈ [-1, 1]` is continuous — *every* piece's weather
buff feeds into it — so the systematic weather effect surfaces as a low-variance
mean shift even when no single battle is decisive. Mean margin is the primary
effect-size read; win rate is reported alongside as the gameplay-facing number.
High variance across individual pieces (many random tier-windows per cell) is the
ally here, not the enemy: it averages out individual-strength noise and leaves
the weather signal. Use `--tier-lo/--tier-hi` to shrink the pool to a near-equal
power band and confirm the signal is the weather system, not tier skew.

Examples:
    # System A: how much does fielding own-weather champs help, under rain?
    python -m tools.simulation.weather_impact --system A --weather rain --samples 200

    # System B: the full affinity-clash matrix at clear weather
    python -m tools.simulation.weather_impact --system B --samples 200

    # Overlap: mono-weather vs every opponent under that weather
    python -m tools.simulation.weather_impact --system AB --samples 200

    # Everything, 6v6, more samples
    python -m tools.simulation.weather_impact --system all --size 6 --samples 400
"""
from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass

from src.game.content import CHAMPION_ROSTER
from src.game.models import CombatOutcome, WeatherState
from src.game.weather_effects import (
    CYCLE_ORDER,
    RingRelation,
    ring_relation,
)

from tools.simulation.matchup import MatchupConfig, configure_sim_max_ticks
from tools.simulation.tournament import run_tournament


# ---------------------------------------------------------------------------
# Roster index — exactly one champion per (affinity, tier)
# ---------------------------------------------------------------------------

CHAMP_BY_AFF_TIER: dict[tuple[WeatherState, int], str] = {
    (c.affinity, c.tier): c.id for c in CHAMPION_ROSTER.values()
}

ALL_TIERS: tuple[int, ...] = tuple(sorted({c.tier for c in CHAMPION_ROSTER.values()}))

RING_WEATHERS: tuple[WeatherState, ...] = CYCLE_ORDER  # 5 active weathers, no clear

# Pool of tiers eligible for sampling — narrowed by --tier-lo/--tier-hi to shrink
# the intra-team power spread (so no single piece dominates the result).
TIER_POOL: list[int] = list(ALL_TIERS)


def champ_id(affinity: WeatherState, tier: int) -> str:
    """Roster id of the unique champion of `affinity` at `tier`."""
    return CHAMP_BY_AFF_TIER[(affinity, tier)]


def primary_prey(weather: WeatherState) -> WeatherState:
    """The weather that `weather` primarily preys on (Clash 1.30 attacker bonus).

    On the directed ring, member i's primary prey is member i-1.
    """
    idx = CYCLE_ORDER.index(weather)
    return CYCLE_ORDER[(idx - 1) % len(CYCLE_ORDER)]


def sample_tiers(rng: random.Random, size: int) -> list[int]:
    """Pick `size` distinct tiers — the shared budget skeleton for both teams."""
    return rng.sample(TIER_POOL, size)


# ---------------------------------------------------------------------------
# Win-rate over a sampled set of equal-budget assemblies
# ---------------------------------------------------------------------------


@dataclass
class Battle:
    """One sampled battle: outcome plus a continuous surviving-HP margin."""

    outcome: CombatOutcome
    margin: float  # (hp_a - hp_b) / (hp_a + hp_b) ∈ [-1, 1]; +1 = flawless A win


@dataclass
class CellResult:
    wins: int
    losses: int
    draws: int
    margins: list[float]

    @property
    def n(self) -> int:
        return self.wins + self.losses + self.draws

    @property
    def win_rate(self) -> float:
        """Wins / total. Draws count as non-wins (decisiveness matters here)."""
        return self.wins / self.n if self.n else float("nan")

    @property
    def decisive_rate(self) -> float:
        """Share of battles that were not draws."""
        return (self.wins + self.losses) / self.n if self.n else float("nan")

    @property
    def mean_margin(self) -> float:
        """Primary effect-size read — mean normalised HP margin (low variance)."""
        return sum(self.margins) / len(self.margins) if self.margins else float("nan")

    @property
    def margin_std(self) -> float:
        m = self.margins
        if len(m) < 2:
            return float("nan")
        mu = self.mean_margin
        return (sum((x - mu) ** 2 for x in m) / (len(m) - 1)) ** 0.5

    @property
    def margin_sem(self) -> float:
        """Std error of the mean margin — the ± on the effect-size estimate."""
        if len(self.margins) < 2:
            return float("nan")
        return self.margin_std / len(self.margins) ** 0.5


_FLIP = {CombatOutcome.WIN: CombatOutcome.LOSS,
         CombatOutcome.LOSS: CombatOutcome.WIN,
         CombatOutcome.DRAW: CombatOutcome.DRAW}


def _mk_configs(team: tuple[str, ...], enemy: tuple[str, ...],
                weather: WeatherState, both_sides: bool
                ) -> list[tuple[int, MatchupConfig]]:
    """Build the (sign, config) battles for one assembly.

    With `both_sides`, also play the swap (team/enemy roles flipped). The swap's
    result is folded with sign -1 — margin negated, outcome flipped — so the
    engine's input-order side advantage cancels in the cell aggregate.
    """
    cfgs = [(+1, MatchupConfig(piece_ids_a=team, piece_ids_b=enemy, weather=weather))]
    if both_sides:
        cfgs.append((-1, MatchupConfig(piece_ids_a=enemy, piece_ids_b=team, weather=weather)))
    return cfgs


def _fold(sign: int, result) -> Battle:
    denom = result.hp_remaining_a + result.hp_remaining_b
    margin = (result.hp_remaining_a - result.hp_remaining_b) / denom if denom else 0.0
    outcome = result.outcome
    if sign < 0:  # swapped — re-orient to the player's perspective
        margin = -margin
        outcome = _FLIP[outcome]
    return Battle(outcome, margin)


def _tally(battles: list[Battle]) -> CellResult:
    w = sum(b.outcome == CombatOutcome.WIN for b in battles)
    l = sum(b.outcome == CombatOutcome.LOSS for b in battles)
    d = sum(b.outcome == CombatOutcome.DRAW for b in battles)
    return CellResult(w, l, d, [b.margin for b in battles])


def _run_cells(cell_configs: dict, workers: int, max_ticks: int) -> dict:
    """Flatten every cell's (sign, config) list, run them through the (parallel)
    tournament, and fold the ordered results back into per-cell CellResults.

    `run_tournament` preserves order, so we re-zip results against the flat
    (key, sign) index. Engine stays byte-deterministic (V.2).
    """
    keys: list = []
    signs: list[int] = []
    flat: list[MatchupConfig] = []
    for key, tagged in cell_configs.items():
        for sign, cfg in tagged:
            keys.append(key)
            signs.append(sign)
            flat.append(cfg)
    results = run_tournament(flat, workers=workers, max_ticks=max_ticks)

    from collections import defaultdict
    buckets: dict = defaultdict(list)
    for key, sign, res in zip(keys, signs, results):
        buckets[key].append(_fold(sign, res))
    return {key: _tally(battles) for key, battles in buckets.items()}


def _pool(cells: list[CellResult]) -> CellResult:
    """Merge several CellResults into one (sum tallies, concat margins)."""
    margins: list[float] = []
    w = l = d = 0
    for c in cells:
        w += c.wins
        l += c.losses
        d += c.draws
        margins += c.margins
    return CellResult(w, l, d, margins)


# ---------------------------------------------------------------------------
# Density sweeps — intensity of each system vs how many own-affinity pieces are
# fielded (j = 0..size), aggregated over all 5 ring weathers for one clean curve.
# ---------------------------------------------------------------------------


def _run_density(tag: str, *, enemy_affinity, weather_of, size: int,
                 samples: int, seed: int, both_sides: bool, workers: int,
                 max_ticks: int) -> list[tuple[int, CellResult]]:
    """Generic density sweep.

    For each j in 0..size and each ring weather X: player fields j pieces of X
    plus (size-j) clear fillers; the enemy is mono `enemy_affinity(X)`; the node
    weather is `weather_of(X)`. Results pool across X per j.

      * System B density: enemy_affinity = primary_prey(X), weather_of = CLEAR
        → pure Affinity-Clash, ramped by predator-piece count.
      * System AB density: enemy_affinity = primary_prey(X), weather_of = X
        → Favor (on the X pieces) AND Clash compound.
    """
    cell_configs: dict = {}
    for j in range(size + 1):
        for x in RING_WEATHERS:
            y = enemy_affinity(x)
            w = weather_of(x)
            rng = random.Random(f"{seed}|{tag}|{x.value}|{j}")
            tagged: list = []
            for _ in range(samples):
                tiers = sample_tiers(rng, size)
                own_slots = set(rng.sample(range(size), j))
                team = tuple(
                    champ_id(x if i in own_slots else WeatherState.CLEAR, t)
                    for i, t in enumerate(tiers)
                )
                enemy = tuple(champ_id(y, t) for t in tiers)
                tagged += _mk_configs(team, enemy, w, both_sides)
            cell_configs[(j, x)] = tagged
    cells = _run_cells(cell_configs, workers, max_ticks)
    return [(j, _pool([cells[(j, x)] for x in RING_WEATHERS])) for j in range(size + 1)]


def run_system_b_density(size, samples, seed, *, both_sides, workers, max_ticks):
    """Clash intensity vs predator-piece density (clear weather, enemy = prey)."""
    return _run_density(
        "Bd", enemy_affinity=primary_prey, weather_of=lambda x: WeatherState.CLEAR,
        size=size, samples=samples, seed=seed, both_sides=both_sides,
        workers=workers, max_ticks=max_ticks,
    )


def run_system_ab_density(size, samples, seed, *, both_sides, workers, max_ticks):
    """Favor+Clash intensity vs own-affinity density (weather = X, enemy = prey)."""
    return _run_density(
        "ABd", enemy_affinity=primary_prey, weather_of=lambda x: x,
        size=size, samples=samples, seed=seed, both_sides=both_sides,
        workers=workers, max_ticks=max_ticks,
    )


# ---------------------------------------------------------------------------
# System A — Weather Favor isolation
# ---------------------------------------------------------------------------
#
# Player fields k own-weather champs + (size-k) clear fillers; enemy is all
# clear (inert). Both draw the same tiers => equal budget. Run each sampled
# assembly under node weather W (Favor on) and under CLEAR (Favor off); the
# win-rate delta is the pure Weather-Favor swing, design bias subtracted.


def run_system_a(weather: WeatherState, size: int, samples: int, seed: int,
                 *, both_sides: bool, workers: int, max_ticks: int
                 ) -> list[tuple[int, CellResult, CellResult]]:
    """For k in 0..size: (k, cell_under_weather, cell_under_clear_control)."""
    cell_configs: dict = {}
    for k in range(size + 1):
        rng = random.Random(f"{seed}|A|{weather.value}|{k}")
        live: list = []
        ctrl: list = []
        for _ in range(samples):
            tiers = sample_tiers(rng, size)
            own_slots = set(rng.sample(range(size), k))
            team = tuple(
                champ_id(weather if i in own_slots else WeatherState.CLEAR, t)
                for i, t in enumerate(tiers)
            )
            enemy = tuple(champ_id(WeatherState.CLEAR, t) for t in tiers)
            live += _mk_configs(team, enemy, weather, both_sides)
            ctrl += _mk_configs(team, enemy, WeatherState.CLEAR, both_sides)
        cell_configs[(k, "live")] = live
        cell_configs[(k, "ctrl")] = ctrl
    cells = _run_cells(cell_configs, workers, max_ticks)
    return [(k, cells[(k, "live")], cells[(k, "ctrl")]) for k in range(size + 1)]


# ---------------------------------------------------------------------------
# System B — Affinity Clash isolation (clear weather, mono vs mono)
# ---------------------------------------------------------------------------


def run_system_b(size: int, samples: int, seed: int,
                 *, both_sides: bool, workers: int, max_ticks: int) -> dict:
    """Mono-X vs mono-Y at CLEAR weather for every ordered active-weather pair."""
    cell_configs: dict = {}
    for ax in RING_WEATHERS:
        for ay in RING_WEATHERS:
            rng = random.Random(f"{seed}|B|{ax.value}|{ay.value}")
            tagged: list = []
            for _ in range(samples):
                tiers = sample_tiers(rng, size)
                team = tuple(champ_id(ax, t) for t in tiers)
                enemy = tuple(champ_id(ay, t) for t in tiers)
                tagged += _mk_configs(team, enemy, WeatherState.CLEAR, both_sides)
            cell_configs[(ax, ay)] = tagged
    return _run_cells(cell_configs, workers, max_ticks)


# ---------------------------------------------------------------------------
# System AB — both systems live (node weather W, mono vs mono)
# ---------------------------------------------------------------------------


def run_system_ab(size: int, samples: int, seed: int,
                  *, both_sides: bool, workers: int, max_ticks: int) -> dict:
    """Under node weather W: mono-W player vs mono-Y enemy, for every Y.

    Player gets Weather Favor (it is the node weather's affinity) AND its Clash
    relation vs Y. The prey columns are the decisiveness litmus.
    """
    cell_configs: dict = {}
    for w in RING_WEATHERS:
        for ay in RING_WEATHERS:
            rng = random.Random(f"{seed}|AB|{w.value}|{ay.value}")
            tagged: list = []
            for _ in range(samples):
                tiers = sample_tiers(rng, size)
                team = tuple(champ_id(w, t) for t in tiers)
                enemy = tuple(champ_id(ay, t) for t in tiers)
                tagged += _mk_configs(team, enemy, w, both_sides)
            cell_configs[(w, ay)] = tagged
    return _run_cells(cell_configs, workers, max_ticks)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _pct(x: float) -> str:
    return "  NA " if x != x else f"{x * 100:5.1f}"


def _mgn(x: float) -> str:
    """Format a margin in [-1,1] as a signed value with sign, e.g. +0.34."""
    return "  NA  " if x != x else f"{x:+.3f}"


def report_a(weather: WeatherState, size: int,
             rows: list[tuple[int, CellResult, CellResult]]) -> list[str]:
    out = [
        "",
        f"=== System A — Weather Favor isolation @ {weather.value} (size {size}) ===",
        "Player: k own-weather champs + clear fillers.  Enemy: all clear (inert).",
        "margin = mean HP margin [-1..1] (primary, low-variance effect size);",
        "favor/ctrl = win% under node weather vs same teams under CLEAR (Favor off).",
        "d-mgn = favor margin - control margin = pure Weather-Favor swing per piece-set.",
        "",
        "  k   own%   m_favor  m_ctrl   d-mgn   favor%  ctrl%  dWin",
        "  --  -----  -------  -------  ------  ------  -----  -----",
    ]
    for k, live, ctrl in rows:
        own_frac = k / size * 100
        d_mgn = live.mean_margin - ctrl.mean_margin
        d_win = (live.win_rate - ctrl.win_rate) * 100
        out.append(
            f"  {k:>2}  {own_frac:4.0f}%  {_mgn(live.mean_margin)}  {_mgn(ctrl.mean_margin)}"
            f"  {d_mgn:+.3f}  {_pct(live.win_rate)}  {_pct(ctrl.win_rate)}  {d_win:+5.1f}"
        )
    full_live, full_ctrl = rows[-1][1], rows[-1][2]
    full_dmgn = full_live.mean_margin - full_ctrl.mean_margin
    full_dwin = (full_live.win_rate - full_ctrl.win_rate) * 100
    out += [
        "",
        f"  full-team Favor swing (k={size}): margin {full_dmgn:+.3f} "
        f"(±{full_live.margin_sem:.3f} sem), win {full_dwin:+.1f}pp",
    ]
    return out


def report_density(title: str, legend: str, size: int,
                   rows: list[tuple[int, CellResult]]) -> list[str]:
    """j-curve: effect intensity as own-affinity density rises 0..size."""
    out = ["", f"=== {title} ===", legend, "",
           "   j   own%   margin   win%   d-mgn(vs j=0)  dWin",
           "  --  -----  -------  -----  -------------  -----"]
    base_m = rows[0][1].mean_margin
    base_w = rows[0][1].win_rate
    for j, c in rows:
        dm = c.mean_margin - base_m
        dw = (c.win_rate - base_w) * 100
        out.append(
            f"  {j:>2}  {j / size * 100:4.0f}%  {_mgn(c.mean_margin)}  {_pct(c.win_rate)}"
            f"     {dm:+.3f}       {dw:+5.1f}"
        )
    top = rows[-1][1]
    out.append("")
    out.append(
        f"  saturation (j={size}): margin {_mgn(top.mean_margin)} "
        f"(±{top.margin_sem:.3f} sem), win {_pct(top.win_rate)}%  "
        f"[pooled n={top.n} over {len(RING_WEATHERS)} weathers]"
    )
    return out


def _matrix(title: str, legend: str,
            cells: dict[tuple[WeatherState, WeatherState], CellResult],
            row_label: str, col_label: str,
            cell_fn, cell_w: int = 7) -> list[str]:
    out = ["", f"=== {title} ===", legend, ""]
    head = f"  {row_label:>12} \\ {col_label}"
    out.append(head + "".join(f"  {w.value[:cell_w]:>{cell_w}}" for w in RING_WEATHERS))
    out.append("  " + "-" * (12 + 3 + (cell_w + 2) * len(RING_WEATHERS)))
    for ax in RING_WEATHERS:
        cells_str = "".join(f"  {cell_fn(cells[(ax, ay)]):>{cell_w}}" for ay in RING_WEATHERS)
        out.append(f"  {ax.value:>12}    {cells_str}")
    return out


def _relation_summary(cells, value_fn, fmt) -> list[str]:
    by_rel: dict[RingRelation, list[float]] = {}
    for (ax, ay), c in cells.items():
        if ax == ay:
            continue
        by_rel.setdefault(ring_relation(ax, ay), []).append(value_fn(c))
    order = [
        RingRelation.PRIMARY_PREDATOR,
        RingRelation.SECONDARY_PREDATOR,
        RingRelation.SECONDARY_PREY,
        RingRelation.PRIMARY_PREY,
    ]
    lines = []
    for rel in order:
        vals = [v for v in by_rel.get(rel, []) if v == v]
        avg = sum(vals) / len(vals) if vals else float("nan")
        lines.append(f"    {rel.value:<20} {fmt(avg)}  (n={len(by_rel.get(rel, []))})")
    return lines


def report_b(cells: dict[tuple[WeatherState, WeatherState], CellResult]) -> list[str]:
    legend = (
        "Row = player mono-affinity, Col = enemy mono-affinity.\n"
        "  Weather Favor OFF (clear weather); only the per-hit Affinity-Clash ring differs."
    )
    lines = _matrix("System B — Affinity Clash isolation @ clear weather — mean HP margin",
                    legend, cells, "player", "enemy",
                    lambda c: _mgn(c.mean_margin))
    lines += _matrix("System B — Affinity Clash — player win%",
                     "Same cells, win% view.", cells, "player", "enemy",
                     lambda c: _pct(c.win_rate))
    lines += ["", "  By ring relation (player vs enemy) — margin / win%:"]
    lines += _relation_summary(cells, lambda c: c.mean_margin, _mgn)
    lines += ["    (win%)"]
    lines += _relation_summary(cells, lambda c: c.win_rate, _pct)
    return lines


def report_ab(cells: dict[tuple[WeatherState, WeatherState], CellResult]) -> list[str]:
    legend = (
        "Row = node weather = player mono-affinity, Col = enemy mono-affinity.\n"
        "  Player gets Weather Favor AND its Clash vs enemy. Vs its prey = decisive."
    )
    lines = _matrix("System AB — both systems live (node weather = player affinity) — mean HP margin",
                    legend, cells, "weather", "enemy",
                    lambda c: _mgn(c.mean_margin))
    lines += _matrix("System AB — player win%", "Same cells, win% view.",
                     cells, "weather", "enemy", lambda c: _pct(c.win_rate))
    lines += ["", "  Diagonal (mirror, enemy same affinity) — should sit near 0 margin / 50%",
              "  (Favor cancels: both buffed; Clash is self = 1.0):"]
    for w in RING_WEATHERS:
        c = cells[(w, w)]
        lines.append(f"    {w.value:>8}: margin {_mgn(c.mean_margin)}  win {_pct(c.win_rate)}%")
    return lines


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_weather(raw: str) -> WeatherState:
    try:
        w = WeatherState(raw.lower())
    except ValueError:
        valid = ", ".join(x.value for x in WeatherState)
        raise argparse.ArgumentTypeError(f"Unknown weather {raw!r}; expected: {valid}")
    if w == WeatherState.CLEAR:
        raise argparse.ArgumentTypeError("System A/AB need an active weather, not clear.")
    return w


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tools.simulation.weather_impact")
    p.add_argument("--system",
                   choices=["A", "B", "AB", "Bd", "ABd", "all"], default="all",
                   help="A=Favor density, B=Clash matrix, AB=overlap matrix, "
                        "Bd=Clash density curve, ABd=Favor+Clash density curve, "
                        "all=every probe.")
    p.add_argument("--weather", type=_parse_weather, default=WeatherState.RAIN,
                   help="Node weather for system A (active weather). Default rain.")
    p.add_argument("--size", type=int, default=8, help="Pieces per team. Default 8.")
    p.add_argument("--samples", type=int, default=150,
                   help="Team assemblies sampled per cell. Default 150.")
    p.add_argument("--seed", type=int, default=42, help="Sampling RNG seed.")
    p.add_argument("--workers", type=int, default=0,
                   help="Process pool size. 0 = os.cpu_count(). 1 = serial.")
    p.add_argument("--both-sides", dest="both_sides", action="store_true", default=True,
                   help="Play each matchup swapped + fold, cancelling the engine's "
                        "input-order side advantage. On by default.")
    p.add_argument("--no-both-sides", dest="both_sides", action="store_false",
                   help="Disable side-swap folding (halves battles; mirror cells "
                        "will show the engine side-A bias).")
    p.add_argument("--tier-lo", type=int, default=min(ALL_TIERS),
                   help="Lowest tier in the sampling pool. Narrow [lo,hi] to shrink "
                        "intra-team power spread so no single piece dominates.")
    p.add_argument("--tier-hi", type=int, default=max(ALL_TIERS),
                   help="Highest tier in the sampling pool.")
    p.add_argument("--max-ticks", type=int, default=1_000_000,
                   help="Engine MAX_TICKS override (disables sudden death). 0=engine default.")
    return p


def main(argv: list[str] | None = None) -> int:
    global TIER_POOL
    import os
    args = _build_parser().parse_args(argv)
    TIER_POOL = [t for t in ALL_TIERS if args.tier_lo <= t <= args.tier_hi]
    if args.size > len(TIER_POOL):
        raise SystemExit(
            f"--size {args.size} exceeds {len(TIER_POOL)} tiers in pool "
            f"[{args.tier_lo}..{args.tier_hi}] (one champ per tier)."
        )
    if args.size < 1:
        raise SystemExit("--size must be >= 1.")
    workers = args.workers if args.workers > 0 else (os.cpu_count() or 1)
    kw = dict(both_sides=args.both_sides, workers=workers, max_ticks=args.max_ticks)

    lines: list[str] = [
        f"weather-impact sim | size={args.size} samples={args.samples} "
        f"seed={args.seed} tiers=[{args.tier_lo}..{args.tier_hi}] "
        f"both_sides={args.both_sides} workers={workers} max_ticks={args.max_ticks}",
    ]

    if args.system in ("A", "all"):
        rows = run_system_a(args.weather, args.size, args.samples, args.seed, **kw)
        lines += report_a(args.weather, args.size, rows)
    if args.system in ("Bd", "all"):
        rows = run_system_b_density(args.size, args.samples, args.seed, **kw)
        lines += report_density(
            "System B density — Affinity-Clash intensity vs predator-piece count",
            "Player: j predator pieces + clear filler.  Enemy: mono prey.  Clear weather "
            "(Favor off).\n  Pooled over all 5 ring weathers. j=0 anchor ≈ 50% (all clear).",
            args.size, rows)
    if args.system in ("ABd", "all"):
        rows = run_system_ab_density(args.size, args.samples, args.seed, **kw)
        lines += report_density(
            "System AB density — Favor+Clash intensity vs own-affinity count",
            "Player: j own-weather pieces + clear filler.  Enemy: mono prey.  Node weather = X "
            "(Favor ON).\n  Pooled over all 5 ring weathers. Favor and Clash compound.",
            args.size, rows)
    if args.system in ("B", "all"):
        lines += report_b(run_system_b(args.size, args.samples, args.seed, **kw))
    if args.system in ("AB", "all"):
        lines += report_ab(run_system_ab(args.size, args.samples, args.seed, **kw))

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
