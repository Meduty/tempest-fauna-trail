"""Roster browser CLI.

    python -m tools.playtest.inspect --kind champion --affinity rain
    python -m tools.playtest.inspect --kind enemy --tier 5
    python -m tools.playtest.inspect --kind champion --show-favor cloudy

Prints an aligned stat table over the champion or enemy roster, optionally
filtered by affinity / tier / role. `--show-favor WX` adds a second table
with Weather Favor applied (HP / STR / INT / AS / MS / ARM / RES) so devs
can eyeball weather impact without running a fight.
"""
from __future__ import annotations

import argparse
import sys
from typing import Iterable

from src.game.content import CHAMPION_ROSTER, ENEMY_ROSTER
from src.game.models import Champion, Enemy, WeatherState
from src.game.weather_effects import combat_modifier

from tools.playtest._common import (
    CHAMPION_COLUMNS,
    Column,
    champion_row,
    enemy_row,
    format_table,
    parse_weather,
)


FAVOR_COLUMNS: list[Column] = [
    Column("id", 32),
    Column("affinity", 8),
    Column("HP", 5, "right"),
    Column("STR", 4, "right"),
    Column("INT", 4, "right"),
    Column("AS", 4, "right"),
    Column("MS", 4, "right"),
    Column("MR", 4, "right"),
    Column("ARM", 4, "right"),
    Column("RES", 4, "right"),
    Column("RNG", 4, "right"),
]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="inspect",
        description="Browse the champion or enemy roster with optional filters.",
    )
    parser.add_argument(
        "--kind",
        choices=["champion", "enemy"],
        default="champion",
        help="Which roster to browse. Default: champion.",
    )
    parser.add_argument(
        "--affinity",
        type=parse_weather,
        default=None,
        help="Filter by affinity (clear, cloudy, mist, rain, snow, thunder).",
    )
    parser.add_argument(
        "--tier",
        type=int,
        default=None,
        help="Filter by tier (1..10).",
    )
    parser.add_argument(
        "--role",
        type=str,
        default=None,
        help="Filter by role string (case-insensitive substring match).",
    )
    parser.add_argument(
        "--show-favor",
        type=parse_weather,
        default=None,
        help="Also print a Weather-Favor-modified stat table under the given weather.",
    )
    return parser


def _filter_champions(args: argparse.Namespace) -> list[Champion]:
    pieces = list(CHAMPION_ROSTER.values())
    if args.affinity is not None:
        pieces = [c for c in pieces if c.affinity == args.affinity]
    if args.tier is not None:
        pieces = [c for c in pieces if c.tier == args.tier]
    if args.role is not None:
        needle = args.role.lower()
        pieces = [c for c in pieces if needle in c.role.lower()]
    pieces.sort(key=lambda c: (c.affinity.value, c.tier, c.id))
    return pieces


def _filter_enemies(args: argparse.Namespace) -> list[Enemy]:
    pieces = list(ENEMY_ROSTER.values())
    if args.affinity is not None:
        pieces = [e for e in pieces if e.affinity == args.affinity]
    if args.tier is not None:
        pieces = [e for e in pieces if e.tier == args.tier]
    if args.role is not None:
        needle = args.role.lower()
        pieces = [e for e in pieces if needle in e.role.lower()]
    pieces.sort(key=lambda e: (e.affinity.value, e.tier, e.id))
    return pieces


def _apply_favor(piece: Champion | Enemy, weather: WeatherState) -> list[str]:
    """Return a favor-modified row for FAVOR_COLUMNS."""
    mod = combat_modifier(piece.affinity, weather)
    return [
        piece.id,
        piece.affinity.value,
        str(max(0, round(piece.max_hp * mod.hp_mult))),
        str(max(0, round(piece.strength * mod.str_mult))),
        str(max(0, round(piece.intelligence * mod.int_mult))),
        str(max(0, round(piece.attack_speed * mod.as_mult))),
        str(max(0, round(piece.move_speed * mod.ms_mult))),
        str(max(0, round(piece.mana_regen * mod.mr_mult))),
        str(max(0, round(piece.armor * mod.armor_mult))),
        str(max(0, round(piece.resistance * mod.res_mult))),
        str(max(1, piece.attack_range + mod.attack_range_delta)),
    ]


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.kind == "champion":
        rows_objs: Iterable[Champion | Enemy] = _filter_champions(args)
        row_fn = champion_row
    else:
        rows_objs = _filter_enemies(args)
        row_fn = enemy_row

    rows = [row_fn(p) for p in rows_objs]  # type: ignore[arg-type]
    if not rows:
        print("No pieces match the given filters.", file=sys.stderr)
        return 1

    plural = "Champions" if args.kind == "champion" else "Enemies"
    print(f"{plural} — {len(rows)} matching:")
    for line in format_table(CHAMPION_COLUMNS, rows):
        print(line)

    if args.show_favor is not None:
        weather: WeatherState = args.show_favor
        print()
        print(f"Weather Favor applied — weather={weather.value}:")
        favor_rows = [_apply_favor(p, weather) for p in rows_objs]  # type: ignore[arg-type]
        for line in format_table(FAVOR_COLUMNS, favor_rows):
            print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
