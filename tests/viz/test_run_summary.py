"""T.13 — `run_summary_specs` pure data + `build_run_summary` builder (V.72/V.2).

Asserts structure (counts / values / normalization / outcome), never pixels
(mirrors `test_route_map.py`). Battle-log entries are stubs — `run_summary_specs`
only reads `node_id` / `team_damage_dealt` / `outcome`.
"""

from __future__ import annotations

from types import SimpleNamespace

import flet as ft
import flet.canvas as cv

from src.game.models import CombatOutcome
from src.game.run_init import champion_offer, new_run
from src.viz.run_summary import BarSpec, build_run_summary, run_summary_specs


def _battle(node_id: str, dealt: dict[str, int], outcome=CombatOutcome.WIN):
    return SimpleNamespace(node_id=node_id, team_damage_dealt=dealt, outcome=outcome)


def _run_with_log(*battles):
    run = new_run(5, champion_offer(5)[0])
    run.battle_log = list(battles)
    return run


def test_empty_log_yields_no_specs():
    run = _run_with_log()
    assert run_summary_specs(run) == []
    # Builder must not crash on an empty log.
    assert isinstance(build_run_summary(run), ft.Text)


def test_one_spec_per_battle_in_order():
    run = _run_with_log(
        _battle("n1-Lisbon", {"a": 100}),
        _battle("n2-Madrid", {"a": 50, "b": 50}),
        _battle("n3-Paris", {"a": 200}),
    )
    specs = run_summary_specs(run)
    assert len(specs) == 3
    assert [s.index for s in specs] == [0, 1, 2]
    assert [s.label for s in specs] == ["Lisbon", "Madrid", "Paris"]


def test_damage_is_team_dealt_sum():
    run = _run_with_log(_battle("n1-Lisbon", {"a": 30, "b": 70}))
    assert run_summary_specs(run)[0].damage == 100


def test_height_frac_max_normalized():
    run = _run_with_log(
        _battle("n1-A", {"x": 50}),
        _battle("n2-B", {"x": 200}),   # peak
        _battle("n3-C", {"x": 100}),
    )
    specs = run_summary_specs(run)
    fracs = {s.label: s.height_frac for s in specs}
    assert fracs["B"] == 1.0
    assert fracs["A"] == 50 / 200
    assert fracs["C"] == 100 / 200
    assert all(0.0 <= s.height_frac <= 1.0 for s in specs)


def test_all_zero_damage_no_divide_by_zero():
    run = _run_with_log(_battle("n1-A", {"x": 0}), _battle("n2-B", {}))
    specs = run_summary_specs(run)
    assert all(s.height_frac == 0.0 for s in specs)


def test_won_flag_tracks_outcome():
    run = _run_with_log(
        _battle("n1-A", {"x": 10}, CombatOutcome.WIN),
        _battle("n2-B", {"x": 10}, CombatOutcome.LOSS),
        _battle("n3-C", {"x": 10}, CombatOutcome.DRAW),
    )
    assert [s.won for s in run_summary_specs(run)] == [True, False, False]


def test_builder_returns_canvas_for_nonempty():
    run = _run_with_log(_battle("n1-A", {"x": 10}))
    assert isinstance(build_run_summary(run), cv.Canvas)


def test_specs_deterministic():
    run = _run_with_log(_battle("n1-A", {"x": 10}), _battle("n2-B", {"x": 20}))
    assert run_summary_specs(run) == run_summary_specs(run)
    assert isinstance(run_summary_specs(run)[0], BarSpec)
