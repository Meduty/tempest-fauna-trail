"""Single-node playtest CLI — generate encounter + resolve combat.

    python -m tools.playtest.sim_node \\
        --stage 3 --node-index 22 --run-seed 12345 \\
        --team champ_storm_eagle,champ_drift_yak,champ_tide_otter

Walks one node end-to-end: looks up city + node type, runs the matching
encounter generator (FIGHT / REWARD / CHALLENGE / BOSS), resolves the
battle, and prints the human-readable log.

For BOSS_FIGHT nodes the map effect is attached via
`_common.resolve_boss_combat` (composes the same primitives `resolve_combat`
uses, plus `attach_map_effect`).
"""
from __future__ import annotations

import argparse
import sys

from src.game.combat import resolve_combat
from src.game.combat_log import format_combat_log
from src.game.encounter import (
    DEFAULT_DC,
    generate_boss_encounter,
    generate_challenge,
    generate_fight,
    generate_reward,
)
from src.game.models import NodeType, WeatherState
from src.game.route import CITIES, STAGES

from tools.playtest._common import (
    default_team,
    node_position_in_stage,
    parse_champion_ids,
    parse_weather,
    resolve_boss_combat,
    stage_def,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sim_node",
        description="Generate one node's encounter and resolve the battle.",
    )
    parser.add_argument("--stage", type=int, required=True, help="Stage index (1..6).")
    parser.add_argument(
        "--node-index",
        type=int,
        required=True,
        help="1-based absolute node index along the 50-node route.",
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
        help="Comma-separated champion ids. Defaults to default_team(stage).",
    )
    parser.add_argument(
        "--weather",
        type=parse_weather,
        default=None,
        help="Override live weather. Defaults to the city's default_weather.",
    )
    parser.add_argument(
        "--dc",
        type=float,
        default=DEFAULT_DC,
        help=f"Difficulty coefficient. Default: {DEFAULT_DC}.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    stage = stage_def(args.stage)
    position = node_position_in_stage(args.stage, args.node_index)

    city_id = stage.node_cities[position]
    weather: WeatherState = args.weather if args.weather else CITIES[city_id].default_weather
    node_type = stage.node_types[position]
    team = args.team if args.team is not None else default_team(args.stage)

    if not team:
        print("error: empty team", file=sys.stderr)
        return 2

    node_id = f"s{args.stage}-n{args.node_index}-{city_id}"

    print(f"# Stage {args.stage} · Node {args.node_index} ({STAGES[args.stage - 1].name})")
    print(f"# City {CITIES[city_id].name} · Type {node_type.value} · Weather {weather.value}")
    print(f"# Run seed {args.run_seed} · DC {args.dc} · Team {[c.id for c in team]}")
    print()

    if node_type == NodeType.FIGHT:
        enemies = generate_fight(args.run_seed, args.node_index, stage, args.dc)
        result = resolve_combat(team, enemies, weather, node_id=node_id)
        for line in format_combat_log(result, team=team, enemies=enemies):
            print(line)

    elif node_type == NodeType.REWARD:
        enemies = generate_reward(args.run_seed, args.node_index, stage, args.dc)
        result = resolve_combat(team, enemies, weather, node_id=node_id)
        for line in format_combat_log(result, team=team, enemies=enemies):
            print(line)

    elif node_type == NodeType.CHALLENGE:
        enemies, reward = generate_challenge(
            args.run_seed, args.node_index, stage, weather, args.dc,
        )
        result = resolve_combat(team, enemies, weather, node_id=node_id)
        for line in format_combat_log(result, team=team, enemies=enemies):
            print(line)
        print()
        print("Challenge reward on clear:")
        print(f"  champion offer  : {reward.champion_offer}")
        print(f"  component       : {reward.component_offer}")
        print(f"  themed comp.    : {reward.themed_component}")
        print(f"  amber           : {reward.amber}")
        print(f"  tempest bonus   : +{reward.tempest_bonus}")

    elif node_type == NodeType.BOSS_FIGHT:
        encounter = generate_boss_encounter(args.run_seed, args.node_index, stage)
        result = resolve_boss_combat(
            team, encounter, weather, run_seed=args.run_seed, node_id=node_id,
        )
        for line in format_combat_log(result, team=team, enemies=encounter.all_enemies):
            print(line)

    else:
        print(f"error: node type {node_type.value} has no combat to resolve", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
