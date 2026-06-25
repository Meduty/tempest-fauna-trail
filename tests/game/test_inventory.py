"""T.23b — item equip seam (`game/inventory.py`): inventory↔champion.items, ≤3
cap, auto-combine on double-equip (V.2 — deterministic combine partner)."""

from __future__ import annotations

import dataclasses

from src.game.content import CHAMPION_ROSTER
from src.game.inventory import equip_item, unequip_item
from src.game.run_init import champion_offer, new_run


def _champ(items=None):
    base = next(iter(CHAMPION_ROSTER.values()))
    return dataclasses.replace(base, items=list(items or []))


def _run(inventory=None):
    run = new_run(5, champion_offer(5)[0])
    run.inventory = dict(inventory or {})
    return run


def test_equip_into_free_slot_consumes_inventory():
    run = _run({"old_hide": 1})
    champ = _champ()
    assert equip_item(run, champ, "old_hide") is True
    assert champ.items == ["old_hide"]
    assert run.inventory.get("old_hide", 0) == 0


def test_equip_not_in_inventory_is_noop():
    run = _run({})
    champ = _champ()
    assert equip_item(run, champ, "old_hide") is False
    assert champ.items == []


def test_cap_blocks_fourth_non_combining_item():
    # Three combined items (not base components ⇒ never combine) fill the slots.
    run = _run({"gorehide_wrap": 1})
    champ = _champ(["spiritbark_hide", "greatward_carapace", "hexward_claw"])
    assert equip_item(run, champ, "gorehide_wrap") is False
    assert len(champ.items) == 3
    assert run.inventory.get("gorehide_wrap", 0) == 1  # not consumed


def test_auto_combine_on_double_equip():
    run = _run({"keen_claw": 1})
    champ = _champ(["old_hide"])
    assert equip_item(run, champ, "keen_claw") is True
    # old_hide + keen_claw → gorehide_wrap, one slot.
    assert champ.items == ["gorehide_wrap"]
    assert run.inventory.get("keen_claw", 0) == 0


def test_auto_combine_works_at_full_slots():
    run = _run({"keen_claw": 1})
    champ = _champ(["old_hide", "spiritbark_hide", "hexward_claw"])  # full
    assert equip_item(run, champ, "keen_claw") is True
    assert champ.items == ["gorehide_wrap", "spiritbark_hide", "hexward_claw"]
    assert len(champ.items) == 3


def test_combine_partner_is_first_match_deterministic():
    run = _run({"keen_claw": 1})
    champ = _champ(["old_hide", "stoneplate"])  # both pair with keen_claw
    equip_item(run, champ, "keen_claw")
    # First held (old_hide) wins → gorehide_wrap; stoneplate untouched.
    assert champ.items == ["gorehide_wrap", "stoneplate"]


def test_unequip_returns_item_to_inventory():
    run = _run({})
    champ = _champ(["old_hide"])
    assert unequip_item(run, champ, "old_hide") is True
    assert champ.items == []
    assert run.inventory.get("old_hide", 0) == 1


def test_unequip_not_held_is_noop():
    run = _run({})
    champ = _champ(["old_hide"])
    assert unequip_item(run, champ, "keen_claw") is False
    assert champ.items == ["old_hide"]
