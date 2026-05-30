# T25 — Power Simulation & Balance Benchmarking

> **Status (2026-05-30): shipped.** Implemented per amendments below.
> The §3.2 1v1 framing was kept but expanded with full team-vs-team modes
> per the team-sim amendment. See §13 for the as-built notes.

## 1. Objective

Derive the **implicit power** of every champion/enemy piece empirically, using
the engine's deterministic auto-resolve as a zero-cost oracle. Win rates across
all pairings become a data-driven balance signal that complements the
theoretical `power(T, L)` function.

## 2. Key Insight: Determinism Eliminates Monte Carlo

`resolve_combat` is a pure, byte-deterministic function — no `random` module,
crits fire on a fixed counter interval (`crit_counter ≥ round(1 / crit_chance)`).
Identical inputs always produce identical output.

**Consequence:** each unique configuration `(piece_a, piece_b, tier, level, weather)`
only ever needs to be run **once**. The simulation is an exhaustive enumeration,
not a statistical sample. There is no variance to reduce.

## 3. Matchup Space

### 3.1 Piece configuration

A *piece config* is `(piece_id, tier, level)`. With 60 champions × 10 tiers × 3
levels = **1,800 configs**.

### 3.2 Matchup types

| Mode | Description | Battles |
|---|---|---|
| **Tier-normalized** | A and B at same (T, L) — measures relative merit at equal budget | C(60,2) × 30 = **53,100** |
| **All-weather sweep** | Tier-normalized × 6 weathers — isolates affinity/weather effects | 53,100 × 6 = **318,600** |
| **Power ladder** | One reference champion vs all opponents at every (T, L) — validates the power function | 59 × 30 = **1,770 per ref** |
| **Spot check** | Single (A, B) pair across all weathers | **6** |

At ~1 ms per battle (pessimistic), the all-weather sweep completes in ~320 s
single-threaded, ~40 s with 8 processes. Tractable without optimisation.

### 3.3 Weather dimension

Running under `CLEAR` gives a **weather-neutral baseline** (no favor, no
affinity clash with CLEAR). Running under each of the 5 active weathers reveals
how much a champion's rating depends on conditions. The simulation captures
both effects simultaneously because `apply_weather` and `damage_modifier` are
already applied inside `resolve_combat`.

## 4. Champion-vs-Champion Bridge

`resolve_combat(team, enemies, weather)` requires the "B" side to be `Enemy`
objects — `apply_weather` reads `isinstance(piece, Enemy)` to set `is_enemy`.

The simulation layer adds a thin conversion helper:

```python
# tools/simulation/matchup.py

def champion_as_enemy(champ: Champion) -> Enemy:
    """Mirror a Champion onto the enemy side for 1v1 simulation.

    Traits are not copied — the combat engine treats them as opaque labels
    and never reads them during resolution.
    """
    return Enemy(
        id=champ.id + "_sim_enemy",
        name=champ.name,
        affinity=champ.affinity,
        role=champ.role,
        tier=champ.tier,
        level=champ.level,
        max_hp=champ.max_hp,
        strength=champ.strength,
        intelligence=champ.intelligence,
        attack_speed=champ.attack_speed,
        move_speed=champ.move_speed,
        mana_regen=champ.mana_regen,
        threat=champ.threat,
        armor=champ.armor,
        resistance=champ.resistance,
        attack_range=champ.attack_range,
        active_ability=champ.active_ability,
        passive_ability=champ.passive_ability,
        ability_cost=champ.ability_cost,
        crit_chance=champ.crit_chance,
        penetration=champ.penetration,
        penetration_pct=champ.penetration_pct,
    )
```

No changes to `models.py`, `combat.py`, or `weather_effects.py` are required.

## 5. Data Contracts

```python
@dataclass(frozen=True)
class MatchupConfig:
    id_a:    str           # champion id
    id_b:    str           # champion id (enemy side)
    tier:    int
    level:   int
    weather: WeatherState

@dataclass(frozen=True)
class MatchupResult:
    config:         MatchupConfig
    outcome:        CombatOutcome   # A's perspective: WIN / LOSS / DRAW
    ticks:          int             # battle duration in ticks
    hp_remaining_a: int             # surviving HP sum, 0 if A lost
    hp_remaining_b: int             # surviving HP sum, 0 if B lost
```

`run_matchup(config, roster) -> MatchupResult` is the single unit of work
and the only public function in `matchup.py`. It is a pure function — safe
to call from multiple processes.

## 6. Power Rating Derivation

### 6.1 Simple win rate (fast, biased)

```
win_rate[A] = Σ wins_A / total_battles_A
```

Biased by opponent field composition. Useful for a quick first pass.

### 6.2 Bradley-Terry model (preferred)

Latent strength `β_i ≥ 0` per piece. Probability A beats B:

$$P(A \succ B) = \frac{\beta_A}{\beta_A + \beta_B}$$

Maximum likelihood iterative update (converges in ~30 iterations):

$$\beta_i^{\text{new}} = \frac{W_i}{\displaystyle\sum_{j \neq i} \frac{n_{ij}}{\beta_i + \beta_j}}$$

where $W_i$ = total wins for piece $i$, $n_{ij}$ = total games between $i$ and $j$.

Normalise so that a T1L1 baseline piece (the weakest defined champion) has
$\beta = 1.0$. Then the derived $\beta$ is directly comparable to
`power(T, L)`.

### 6.3 Derived metrics

| Metric | Formula | Interpretation |
|---|---|---|
| **Power deviation** | `β / power(T, L)` | > 1.2 → overtuned; < 0.8 → undertuned |
| **Matchup spread** | std dev of win rates across all opponents | high = rock-paper-scissors feel |
| **Weather sensitivity** | variance of `β` across 6 weather runs | high = weather-gated |
| **Affinity premium** | win rate vs prey − win rate vs predators | measures affinity ring payoff |

## 7. Module Structure

```
tools/
  simulation/
    __init__.py
    matchup.py          # champion_as_enemy, MatchupConfig, MatchupResult, run_matchup
    tournament.py       # all-pairs round-robin; returns list[MatchupResult]
    ratings.py          # bradley_terry(results) -> dict[str, float]; win_rates(...)
    report.py           # write_csv, print_summary (top 5 over/underperformers)
    runner.py           # CLI entry point (argparse)
```

No import from `src/ui/` or `src/api/`. `tools/simulation/` only imports
from `src/game/` — consistent with V.1.

## 8. CLI Interface

```
python -m tools.simulation.runner --mode tier-normalized --tier 3 --level 1 \
    --weather clear --out results/t3l1_clear.csv

python -m tools.simulation.runner --mode all-weather --tier 1 --level 1
python -m tools.simulation.runner --mode full-sweep          # all tiers, all levels, all weathers
python -m tools.simulation.runner --mode spot --id-a fox_thunder --id-b bear_snow
```

`--workers N` flag routes batches through `concurrent.futures.ProcessPoolExecutor`.

## 9. Output Files

| File | Content |
|---|---|
| `results/matrix_T{t}L{l}_{weather}.csv` | N×N win/loss matrix (cell = A beats B count) |
| `results/power_ratings.csv` | `piece_id, tier, level, weather, beta, expected_power, deviation` |
| `results/weather_sensitivity.csv` | `piece_id, tier, level, var_across_weathers, most_favorable_weather` |
| `results/affinity_premium.csv` | `piece_id, tier, level, prey_wr, predator_wr, premium` |

Console summary (always printed):
- Top 5 overperformers and underperformers per tier
- Any piece with deviation > ±20% flagged as `[BALANCE ALERT]`

## 10. Integration with Design Workflow

```
content change (stats/abilities)
        ↓
python -m tools.simulation.runner --mode tier-normalized --tier N
        ↓
power_ratings.csv → any deviation > ±20%?
        ↓
yes → adjust base stats → repeat
 no → commit
```

Optional: add a `pytest` marker `@pytest.mark.balance` that runs the
spot-check mode on a curated set of known-even matchups and asserts
`0.4 ≤ win_rate ≤ 0.6`. This turns balance regressions into CI failures
when stats are changed without intention.

## 11. Implementation Phases

| Phase | Deliverable | Effort |
|---|---|---|
| **P1** | `matchup.py`, `tournament.py`, sequential CSV output | S |
| **P2** | `ratings.py` (Bradley-Terry + win rate), `report.py` console summary | S |
| **P3** | `runner.py` CLI, `--workers` multiprocessing, all-weather sweep | M |
| **P4** | pytest `@balance` markers on curated matchups as regression gate | S |

P1 is useful independently — you can inspect raw win matrices without ratings.
P2 turns raw matrices into actionable power numbers. P3 scales to full-roster
sweeps. P4 is optional but valuable for catching stat-change regressions.

## 12. Assumptions & Constraints

- Content (champion roster `src/game/content.py`) must exist before P1 can run
  meaningful sweeps — the plan depends on T.5 being complete.
- The sim runs pieces at identical tier/level to isolate kit design; cross-tier
  validation (power ladder) is secondary and added in P3.
- Draws (`CombatOutcome.DRAW`) are excluded from Bradley-Terry input. If draw
  rate exceeds ~5%, add a tie-correction (e.g. split as 0.5 win each).
- `traits` are intentionally excluded from `champion_as_enemy` — synergy bonuses
  from trait groupings are a team-comp mechanic, not a 1v1 property. If team
  synergy bonuses are later implemented, add a `--synergies` flag to optionally
  activate them.

## 13. As-built notes (2026-05-30)

The shipped layer follows the plan's module structure (`matchup.py`,
`tournament.py`, `ratings.py`, `report.py`, `runner.py`) but extends it
per the T.25 team-sim amendment.

### 13.1 Modes

| CLI mode | Generator | Battle count (N=120 pieces) |
|---|---|---|
| `1v1` | `enumerate_1v1` — every unordered pair of distinct pieces | C(120,2) = 7140 |
| `team2-full` | `enumerate_team2` — every unordered pair of disjoint 2-piece teams (gated behind `--i-know-what-im-doing`) | ~25M |
| `team-sample` | `sample_teams` — random N-piece teams, paired sample-by-sample, optional `--tier-stratified` | `--n-battles` |

The §3.2 tier-normalised mode collapses into `1v1` plus `team-sample
--tier-stratified` because the shipped roster only carries `level = 1`.

### 13.2 Champion / enemy bridges

The plan's `champion_as_enemy` is generalised into a symmetric pair:

- `as_team_piece(piece)` — coerce any roster entry into a `Champion`-typed
  piece with id suffix `_a`. Traits dropped (engine treats them as opaque
  labels; sim does not invoke trait synergies).
- `as_enemy_piece(piece)` — coerce any roster entry into an `Enemy`-typed
  piece with id suffix `_b`.

Suffixing both sides keeps piece ids unique across mirror matches without
the engine ever seeing the same id twice. The original id lives in
`MatchupConfig.piece_ids_*`, so attribution back to the roster does not
read piece ids from `BattleResult.surviving_team_ids` directly.

### 13.3 Per-piece attribution

Binary rule (decision locked at session start, per T.25 prompt):

> Every piece on the winning team scores 1 win against every piece on the
> losing team. Draws split 0.5 each direction.

`_pairwise_records` aggregates this across all results into `(wins, games)`
dicts keyed by piece-id pairs. Surviving HP and damage shares were
considered and rejected — see [docs/journal/2026-05-30_power_simulation.md](../../journal/2026-05-30_power_simulation.md).

### 13.4 Bradley-Terry implementation

MM update per the plan §6.2, with these implementation notes:

- Per-iteration normalisation uses the **geometric mean** of nonzero β
  values to prevent drift. The plan didn't specify this; arithmetic mean
  causes scale blow-up when many pieces have zero wins.
- Pieces that never win are floored at `β = 1e-3` so the update step stays
  finite without polluting the geometric mean.
- Final pass normalises so the weakest piece anchors at `β = 1.0`
  (plan §6.2 — "T1L1 baseline piece").

**Caveat**: stratified sampling produces tier-disjoint games — there is
no β anchor between tiers, so BT betas drift per tier under that mode.
Recommend non-stratified data for cross-tier BT comparisons; use
stratified mode only for within-tier relative reads.

### 13.5 Files

- [tools/simulation/matchup.py](../../../tools/simulation/matchup.py)
- [tools/simulation/tournament.py](../../../tools/simulation/tournament.py)
- [tools/simulation/ratings.py](../../../tools/simulation/ratings.py)
- [tools/simulation/report.py](../../../tools/simulation/report.py)
- [tools/simulation/runner.py](../../../tools/simulation/runner.py)
- Tests: [tests/tools/simulation/](../../../tests/tools/simulation/)
