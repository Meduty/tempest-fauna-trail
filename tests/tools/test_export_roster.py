"""Smoke tests for the roster JSON export (tools/export_roster.py)."""

from __future__ import annotations

import json

from tools.export_roster import build_export


def test_export_counts() -> None:
    data = build_export(level=1, include_bosses=True)
    assert data["counts"] == {"champions": 60, "enemies": 60, "bosses": 6}


def test_every_unit_has_rendered_abilities() -> None:
    data = build_export(level=1, include_bosses=False)
    for unit in data["champions"] + data["enemies"]:
        # T.29d: "actives" is a list (one block per slot) + a single "passive".
        blocks = [(f"active[{i}]", b) for i, b in enumerate(unit["actives"])]
        blocks.append(("passive", unit["passive"]))
        for slot, block in blocks:
            assert not block.get("missing_meta"), f"{unit['id']} {slot} has no meta"
            assert block["name"] and block["text"]
            assert "{" not in block["text"], f"{unit['id']} {slot} left a token"


def test_export_is_json_serializable() -> None:
    data = build_export(level=3, include_bosses=True)
    # Round-trips cleanly (no non-serializable values).
    assert json.loads(json.dumps(data)) == data


def test_bosses_export_all_six_ability_slots() -> None:
    data = build_export(level=1, include_bosses=True)
    expected = {"active", "passive", "phase_hook", "phase2_active", "phase2_passive", "on_death"}
    for boss in data["bosses"]:
        assert set(boss["abilities"]) == expected
