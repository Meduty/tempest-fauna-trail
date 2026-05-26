"""Generated-encounter preview CLI (no combat resolution).

    python -m tools.playtest.inspect_node --stage 3 --node-index 22 --run-seed 12345

Reports the city, node type, weather (live weather defaulting to the city's
default_weather, override with --weather), enemy squad stats, and — for
CHALLENGE / BOSS — the reward payload or boss kit summary.

Useful for sanity-checking encounter generation without paying the cost of
running a full battle.
"""
from __future__ import annotations

import argparse
import sys

from src.game.bosses.data import BOSS_DEFS
from src.game.content import ENEMY_ROSTER
from src.game.encounter import (
    CONTENT_VERSION,
    DEFAULT_DC,
    STAGE_BASE,
    STAGE_MAX_SQUAD,
    TYPE_MULT,
    generate_boss_encounter,
    generate_challenge,
    generate_fight,
    generate_reward,
)
from src.game.models import Enemy, NodeType, WeatherState
from src.game.route import CITIES, STAGES

from tools.playtest._common import (
    CHAMPION_COLUMNS,
    enemy_row,
    format_table,
    node_position_in_stage,
    parse_weather,
    stage_def,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="inspect_node",
        description="Preview a generated encounter without resolving combat.",
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


def _print_header(stage_idx: int, position: int, node_index: int, weather: WeatherState) -> None:
    stage = STAGES[stage_idx - 1]
    city_id = stage.node_cities[position]
    city = CITIES[city_id]
    node_type = stage.node_types[position]
    print(f"Node {node_index:>2} | stage {stage_idx} ({stage.name}, affinity={stage.affinity.value})")
    print(f"  City        : {city.name}, {city.country} ({city.continent})")
    print(f"  Type        : {node_type.value}")
    print(f"  Live weather: {weather.value} (city default: {city.default_weather.value})")
    print(f"  Stage budget: {STAGE_BASE[stage_idx]:.1f} · max squad: {STAGE_MAX_SQUAD[stage_idx]}")


def _print_squad(squad: list[Enemy]) -> None:
    if not squad:
        print("  (no enemy squad — non-combat node)")
        return
    rows = [enemy_row(e) for e in squad]
    print(f"  Enemy squad ({len(squad)}):")
    for line in format_table(CHAMPION_COLUMNS, rows):
        print("  " + line)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    stage = stage_def(args.stage)
    position = node_position_in_stage(args.stage, args.node_index)

    city_id = stage.node_cities[position]
    weather: WeatherState = args.weather if args.weather else CITIES[city_id].default_weather
    node_type = stage.node_types[position]

    _print_header(args.stage, position, args.node_index, weather)
    print(f"  Content ver : {CONTENT_VERSION}")

    if node_type == NodeType.FIGHT:
        squad = generate_fight(args.run_seed, args.node_index, stage, args.dc)
        budget = STAGE_BASE[args.stage] * args.dc * TYPE_MULT["fight"]
        print(f"  Budget (mid): ~{budget:.1f}")
        _print_squad(squad)

    elif node_type == NodeType.REWARD:
        squad = generate_reward(args.run_seed, args.node_index, stage, args.dc)
        budget = STAGE_BASE[args.stage] * args.dc * TYPE_MULT["reward"]
        print(f"  Budget (mid): ~{budget:.1f}")
        _print_squad(squad)

    elif node_type == NodeType.CHALLENGE:
        squad, reward = generate_challenge(
            args.run_seed, args.node_index, stage, weather, args.dc,
        )
        budget = STAGE_BASE[args.stage] * 1.3 * args.dc
        print(f"  Budget (mid): ~{budget:.1f}")
        _print_squad(squad)
        print("  Reward      :")
        print(f"    champion offer : {reward.champion_offer}")
        print(f"    component      : {reward.component_offer}")
        print(f"    themed comp.   : {reward.themed_component}")
        print(f"    amber          : {reward.amber}")
        print(f"    tempest bonus  : +{reward.tempest_bonus}")

    elif node_type == NodeType.BOSS_FIGHT:
        encounter = generate_boss_encounter(args.run_seed, args.node_index, stage)
        boss = encounter.boss_def
        print(f"  Boss        : {boss.name} ({boss.id})")
        print(f"    affinity    : {boss.affinity.value}")
        print(f"    HP/STR/INT  : {boss.max_hp} / {boss.strength} / {boss.intelligence}")
        print(f"    AR/RES/AS   : {boss.armor} / {boss.resistance} / {boss.attack_speed}")
        print(f"    phase 1 kit : {boss.phase1_active} | {boss.phase1_passive}")
        print(f"    phase 2 kit : {boss.phase2_active} | {boss.phase2_passive}")
        print(f"    on-death    : {boss.on_death_hook}")
        print(f"    map effect  : {encounter.map_effect_id}")
        print(f"    spawn pos   : {boss.spawn_position}")
        _print_squad(encounter.supporting_cast)

    else:
        print(f"  (no encounter generator for node type {node_type.value})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
