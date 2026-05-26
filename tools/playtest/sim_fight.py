"""Single-fight playtest CLI.

    python -m tools.playtest.sim_fight \\
        --team champ_blaze_fox,champ_drift_yak,champ_tide_otter \\
        --enemies enemy_frost_drone,enemy_smog_bot \\
        --weather rain --seed 42

Resolves one battle via `resolve_combat` and prints the human-readable log
via `combat_log.format_combat_log`. No I/O beyond stdout.
"""
from __future__ import annotations

import argparse
import sys

from src.game.combat import resolve_combat
from src.game.combat_log import format_combat_log
from src.game.models import WeatherState

from tools.playtest._common import (
    parse_champion_ids,
    parse_enemy_ids,
    parse_weather,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sim_fight",
        description="Resolve a single battle and print a tick-by-tick log.",
    )
    parser.add_argument(
        "--team",
        required=True,
        type=parse_champion_ids,
        help="Comma-separated champion ids (e.g. champ_blaze_fox,champ_drift_yak).",
    )
    parser.add_argument(
        "--enemies",
        required=True,
        type=parse_enemy_ids,
        help="Comma-separated enemy ids (e.g. enemy_frost_drone,enemy_smog_bot).",
    )
    parser.add_argument(
        "--weather",
        default="clear",
        type=parse_weather,
        help="WeatherState value (clear, cloudy, mist, rain, snow, thunder). Default: clear.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Reserved for future use; combat is deterministic regardless. Default: 42.",
    )
    parser.add_argument(
        "--node-id",
        default="",
        help="Optional node id stamped into the BattleResult header.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    team = args.team
    enemies = args.enemies
    weather: WeatherState = args.weather

    if not team:
        print("error: --team is empty", file=sys.stderr)
        return 2
    if not enemies:
        print("error: --enemies is empty", file=sys.stderr)
        return 2

    result = resolve_combat(team, enemies, weather, node_id=args.node_id)
    for line in format_combat_log(result, team=team, enemies=enemies):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
