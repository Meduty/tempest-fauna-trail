"""Full 50-node run walker.

    python -m tools.playtest.sim_run \\
        --run-seed 12345 \\
        --team champ_dawnwisp,champ_veldt_pronghorn,champ_aegis_tortoise \\
        --weather-strategy stage-affinity \\
        --csv run_12345.csv

Walks every node in route order. For each node, picks weather per the
strategy, generates the encounter, resolves combat, and records the result.
Aborts the moment the team wipes (LOSS or DRAW with zero survivors).

Per-node CSV columns:
    node_index, stage, node_type, city_id, weather, outcome, ticks,
    survivors, damage_dealt
"""
from __future__ import annotations

import argparse
import csv
import sys

from src.game.combat import resolve_combat
from src.game.encounter import (
    DEFAULT_DC,
    generate_boss_encounter,
    generate_challenge,
    generate_fight,
    generate_reward,
)
from src.game.models import BattleResult, Champion, CombatOutcome, NodeType, WeatherState
from src.game.route import CITIES, STAGES

from tools.playtest._common import (
    default_team,
    parse_champion_ids,
    parse_weather,
    resolve_boss_combat,
)


WEATHER_STRATEGIES = ("stage-affinity", "city-default")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sim_run",
        description="Walk a full 50-node run with a fixed team.",
    )
    parser.add_argument(
        "--run-seed",
        type=int,
        default=0,
        help="Run seed driving encounter generation. Default: 0.",
    )
    parser.add_argument(
        "--team",
        type=parse_champion_ids,
        default=None,
        help="Comma-separated champion ids. Defaults to default_team(stage_1).",
    )
    parser.add_argument(
        "--weather-strategy",
        default="stage-affinity",
        help=(
            f"Weather selection: one of {', '.join(WEATHER_STRATEGIES)}, or "
            "fixed:<state> (e.g. fixed:rain). Default: stage-affinity."
        ),
    )
    parser.add_argument(
        "--dc",
        type=float,
        default=DEFAULT_DC,
        help=f"Difficulty coefficient. Default: {DEFAULT_DC}.",
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Optional path to write a per-node CSV summary.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-node stdout lines; print only the final summary.",
    )
    return parser


def _pick_weather(strategy: str, stage_idx: int, city_id: str) -> WeatherState:
    if strategy == "stage-affinity":
        return STAGES[stage_idx - 1].affinity
    if strategy == "city-default":
        return CITIES[city_id].default_weather
    if strategy.startswith("fixed:"):
        return parse_weather(strategy.split(":", 1)[1])
    raise argparse.ArgumentTypeError(
        f"Unknown weather strategy {strategy!r}. "
        f"Try one of: {', '.join(WEATHER_STRATEGIES)}, or fixed:<state>."
    )


def _resolve_node(
    team: list[Champion],
    stage_idx: int,
    node_index: int,
    position: int,
    weather: WeatherState,
    run_seed: int,
    dc: float,
) -> tuple[BattleResult | None, NodeType, str]:
    """Resolve one node. Returns (result_or_None, node_type, city_id)."""
    stage = STAGES[stage_idx - 1]
    city_id = stage.node_cities[position]
    node_type = stage.node_types[position]
    node_id = f"s{stage_idx}-n{node_index}-{city_id}"

    if node_type == NodeType.FIGHT:
        enemies = generate_fight(run_seed, node_index, stage, dc)
        return resolve_combat(team, enemies, weather, node_id=node_id), node_type, city_id
    if node_type == NodeType.REWARD:
        enemies = generate_reward(run_seed, node_index, stage, dc)
        return resolve_combat(team, enemies, weather, node_id=node_id), node_type, city_id
    if node_type == NodeType.CHALLENGE:
        enemies, _reward = generate_challenge(run_seed, node_index, stage, weather, dc)
        return resolve_combat(team, enemies, weather, node_id=node_id), node_type, city_id
    if node_type == NodeType.BOSS_FIGHT:
        encounter = generate_boss_encounter(run_seed, node_index, stage)
        return (
            resolve_boss_combat(team, encounter, weather, run_seed=run_seed, node_id=node_id),
            node_type,
            city_id,
        )
    # Non-combat node (AUGMENT / SUPPLY) — skip without resolving anything.
    return None, node_type, city_id


def _team_alive(result: BattleResult) -> bool:
    return bool(result.surviving_team_ids)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    team = args.team if args.team is not None else default_team(1)
    if not team:
        print("error: empty team", file=sys.stderr)
        return 2

    rows: list[dict[str, object]] = []
    cleared = 0
    died_at_node: int | None = None
    total_damage = 0

    node_index = 0
    for stage_idx, stage in enumerate(STAGES, start=1):
        for position, _ in enumerate(stage.node_cities):
            node_index += 1
            city_id = stage.node_cities[position]
            weather = _pick_weather(args.weather_strategy, stage_idx, city_id)

            result, node_type, city_id = _resolve_node(
                team, stage_idx, node_index, position, weather, args.run_seed, args.dc,
            )

            if result is None:
                row = {
                    "node_index": node_index,
                    "stage": stage_idx,
                    "node_type": node_type.value,
                    "city_id": city_id,
                    "weather": weather.value,
                    "outcome": "skipped",
                    "ticks": 0,
                    "survivors": "",
                    "damage_dealt": 0,
                }
                rows.append(row)
                if not args.quiet:
                    print(f"[{node_index:02d}/{stage_idx}] {city_id:25} {node_type.value:9} weather={weather.value:7} → skipped")
                cleared += 1
                continue

            outcome = result.outcome.value
            dmg = sum(
                amt for pid, amt in result.team_damage_dealt.items()
                if pid in {c.id for c in team}
            )
            total_damage += dmg
            survivors = ",".join(result.surviving_team_ids)
            row = {
                "node_index": node_index,
                "stage": stage_idx,
                "node_type": node_type.value,
                "city_id": city_id,
                "weather": weather.value,
                "outcome": outcome,
                "ticks": result.duration_ticks,
                "survivors": survivors,
                "damage_dealt": dmg,
            }
            rows.append(row)

            if not args.quiet:
                print(
                    f"[{node_index:02d}/{stage_idx}] {city_id:25} {node_type.value:9} "
                    f"weather={weather.value:7} → {outcome:4} "
                    f"({result.duration_ticks:>5}t, dmg={dmg:>5}, survivors={len(result.surviving_team_ids)})"
                )

            if result.outcome == CombatOutcome.WIN:
                cleared += 1
            else:
                # LOSS or DRAW — abort the run
                died_at_node = node_index
                break
        if died_at_node is not None:
            break

    print()
    print("=== Run summary ===")
    print(f"Team        : {[c.id for c in team]}")
    print(f"Seed        : {args.run_seed}")
    print(f"Strategy    : {args.weather_strategy}")
    print(f"Nodes cleared: {cleared}/50")
    print(f"Total damage : {total_damage}")
    if died_at_node is not None:
        last = rows[-1]
        print(
            f"Run ended at node {died_at_node} (stage {last['stage']}, "
            f"{last['city_id']}, {last['node_type']}, {last['outcome']})"
        )
    else:
        print("Run reached node 50 — victory!")

    if args.csv:
        with open(args.csv, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"CSV written: {args.csv}")

    return 0 if died_at_node is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
