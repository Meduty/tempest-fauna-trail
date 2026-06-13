"""Export the champion + enemy rosters to JSON, with ability descriptions.

Each unit carries its full stat sheet (``to_dict``) plus its rendered active and
passive ability — name, player-facing text (live numbers filled in), the
formula breakdown, and UI tags — via the T.34 ``ability_text`` renderer
(source-of-truth B; numbers match combat).

Usage:
    uv run python -m tools.export_roster                 # JSON to stdout
    uv run python -m tools.export_roster --out roster.json
    uv run python -m tools.export_roster --include-bosses
    uv run python -m tools.export_roster --level 3       # render at champion level 3

Pure read-only; no combat is run.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from src.game import abilities  # noqa: F401  (registers handlers + ABILITY_META)
from src.game.ability_text import render_for
from src.game.content import (
    CHAMPION_DEF_BY_ID,
    ENEMY_DEF_BY_ID,
    build_champion_at_level,
    build_enemy_at_level,
)


def _ability_block(ability_id: str, source: Any) -> dict[str, Any] | None:
    """Render one ability id against a unit sheet into a serializable dict."""
    rendered = render_for(ability_id, source)
    if rendered is None:
        return {"id": ability_id, "missing_meta": True}
    return {
        "id": ability_id,
        "name": rendered.name,
        "text": rendered.text,
        "formula": rendered.formula,
        "tags": list(rendered.tags),
    }


def _unit_block(unit: Any) -> dict[str, Any]:
    block = unit.to_dict()
    block["active"] = _ability_block(unit.active_ability, unit)
    block["passive"] = _ability_block(unit.passive_ability, unit)
    return block


def build_export(*, level: int, include_bosses: bool) -> dict[str, Any]:
    champions = [
        _unit_block(build_champion_at_level(cid, level))
        for cid in sorted(CHAMPION_DEF_BY_ID)
    ]
    enemies = [
        _unit_block(build_enemy_at_level(eid, level))
        for eid in sorted(ENEMY_DEF_BY_ID)
    ]
    out: dict[str, Any] = {
        "champions": champions,
        "enemies": enemies,
        "counts": {"champions": len(champions), "enemies": len(enemies)},
    }
    if include_bosses:
        out["bosses"] = _build_bosses()
        out["counts"]["bosses"] = len(out["bosses"])
    return out


def _build_bosses() -> list[dict[str, Any]]:
    """Bosses render every ability id (incl. phase 2 / hooks) against the boss sheet."""
    from src.game.bosses.data import get_boss_def

    fields = (
        ("phase1_active", "active"),
        ("phase1_passive", "passive"),
        ("phase1_phase_hook", "phase_hook"),
        ("phase2_active", "phase2_active"),
        ("phase2_passive", "phase2_passive"),
        ("on_death_hook", "on_death"),
    )
    bosses: list[dict[str, Any]] = []
    for stage in range(1, 7):
        d = get_boss_def(stage)
        sheet = d.build_enemy()
        block = sheet.to_dict()
        block["stage"] = stage
        block["abilities"] = {
            label: _ability_block(getattr(d, field), sheet)
            for field, label in fields
        }
        bosses.append(block)
    return bosses


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="Write JSON here instead of stdout.")
    parser.add_argument("--level", type=int, default=1,
                        help="Champion/enemy level to build at (1-3). Default 1.")
    parser.add_argument("--include-bosses", action="store_true",
                        help="Also export the 6 stage bosses (full 2-phase kits).")
    parser.add_argument("--indent", type=int, default=2, help="JSON indent. Default 2.")
    args = parser.parse_args(argv)

    data = build_export(level=args.level, include_bosses=args.include_bosses)
    text = json.dumps(data, indent=args.indent, ensure_ascii=False, sort_keys=False)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        counts = data["counts"]
        print(f"Wrote {args.out}: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
