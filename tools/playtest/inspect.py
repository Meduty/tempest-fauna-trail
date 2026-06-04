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
import csv
import json
from io import StringIO
import sys

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
        "--intent",
        choices=["damage", "hybrid", "utility"],
        default=None,
        help="Filter by combat intent (damage / hybrid / utility).",
    )
    parser.add_argument(
        "--show-favor",
        type=parse_weather,
        default=None,
        help="Also print a Weather-Favor-modified stat table under the given weather.",
    )
    parser.add_argument(
        "--format",
        choices=["table", "csv", "json"],
        default="table",
        help="Output format. Default: table.",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Write output to file path instead of stdout.",
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
    if args.intent is not None:
        pieces = [c for c in pieces if c.intent == args.intent]
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
    if args.intent is not None:
        pieces = [e for e in pieces if e.intent == args.intent]
    pieces.sort(key=lambda e: (e.affinity.value, e.tier, e.id))
    return pieces


def _apply_favor(piece: Champion | Enemy, weather: WeatherState) -> list[str]:
    """Return a favor-modified row for FAVOR_COLUMNS."""
    mod = combat_modifier(piece.affinity, weather)
    return [
        piece.id,
        piece.affinity.value,
        str(max(1, round(piece.max_hp * mod.hp_mult))),
        str(max(0, round(piece.strength * mod.str_mult))),
        str(max(0, round(piece.intelligence * mod.int_mult))),
        str(max(0, round(piece.attack_speed * mod.as_mult))),
        str(max(0, round(piece.move_speed * mod.ms_mult))),
        str(max(0, round(piece.mana_regen * mod.mr_mult))),
        str(max(0, round(piece.armor * mod.armor_mult))),
        str(max(0, round(piece.resistance * mod.res_mult))),
        str(max(1, piece.attack_range + mod.attack_range_delta)),
    ]


def _favor_fields(piece: Champion | Enemy, weather: WeatherState) -> dict[str, int | str]:
    mod = combat_modifier(piece.affinity, weather)
    return {
        "favor_weather": weather.value,
        "favor_max_hp": max(1, round(piece.max_hp * mod.hp_mult)),
        "favor_strength": max(0, round(piece.strength * mod.str_mult)),
        "favor_intelligence": max(0, round(piece.intelligence * mod.int_mult)),
        "favor_attack_speed": max(0, round(piece.attack_speed * mod.as_mult)),
        "favor_move_speed": max(0, round(piece.move_speed * mod.ms_mult)),
        "favor_mana_regen": max(0, round(piece.mana_regen * mod.mr_mult)),
        "favor_armor": max(0, round(piece.armor * mod.armor_mult)),
        "favor_resistance": max(0, round(piece.resistance * mod.res_mult)),
        "favor_attack_range": max(1, piece.attack_range + mod.attack_range_delta),
    }


def _stringify_for_csv(row: dict[str, object]) -> dict[str, object]:
    converted: dict[str, object] = {}
    for key, value in row.items():
        if isinstance(value, list):
            converted[key] = json.dumps(value)
        else:
            converted[key] = value
    return converted


def _render_table(kind: str, rows: list[list[str]], favor_rows: list[list[str]] | None, weather: WeatherState | None) -> str:
    plural = "Champions" if kind == "champion" else "Enemies"
    lines: list[str] = [f"{plural} — {len(rows)} matching:"]
    lines.extend(format_table(CHAMPION_COLUMNS, rows))

    if favor_rows is not None and weather is not None:
        lines.append("")
        lines.append(f"Weather Favor applied — weather={weather.value}:")
        lines.extend(format_table(FAVOR_COLUMNS, favor_rows))

    return "\n".join(lines)


def _render_csv(payload_rows: list[dict[str, object]]) -> str:
    if not payload_rows:
        return ""
    fieldnames = list(payload_rows[0].keys())
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for row in payload_rows:
        writer.writerow(_stringify_for_csv(row))
    return buf.getvalue()


def _render_json(payload_rows: list[dict[str, object]]) -> str:
    return json.dumps(payload_rows, indent=2)


def _emit_output(content: str, out_path: str | None) -> None:
    if out_path:
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write(content)
            if not content.endswith("\n"):
                handle.write("\n")
        return
    if content.endswith("\n"):
        print(content, end="")
    else:
        print(content)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.kind == "champion":
        rows_objs: list[Champion | Enemy] = _filter_champions(args)
        row_fn = champion_row
    else:
        rows_objs = _filter_enemies(args)
        row_fn = enemy_row

    rows = [row_fn(p) for p in rows_objs]  # type: ignore[arg-type]
    if not rows:
        print("No pieces match the given filters.", file=sys.stderr)
        return 1

    payload_rows: list[dict[str, object]] = [p.to_dict() for p in rows_objs]
    if args.show_favor is not None:
        weather: WeatherState = args.show_favor
        for piece, payload in zip(rows_objs, payload_rows):
            payload.update(_favor_fields(piece, weather))

    if args.format == "table":
        favor_rows: list[list[str]] | None = None
        weather_for_table: WeatherState | None = None
        if args.show_favor is not None:
            weather_for_table = args.show_favor
            favor_rows = [_apply_favor(p, weather_for_table) for p in rows_objs]
        content = _render_table(args.kind, rows, favor_rows, weather_for_table)
    elif args.format == "csv":
        content = _render_csv(payload_rows)
    else:
        content = _render_json(payload_rows)

    _emit_output(content, args.out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
