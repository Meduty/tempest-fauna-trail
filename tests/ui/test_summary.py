"""Run-summary view (T.13) — construction + Return-to-Menu wiring smoke test."""

from __future__ import annotations

from types import SimpleNamespace

import flet as ft

from src.game.models import CombatOutcome, RunStatus
from src.game.run_init import champion_offer, new_run
from src.ui.views.summary import build_summary_view


class _FakePage:
    def update(self):
        pass


def _find(control, pred, out=None):
    out = [] if out is None else out
    if pred(control):
        out.append(control)
    for attr in ("controls", "content"):
        child = getattr(control, attr, None)
        if isinstance(child, list):
            for c in child:
                _find(c, pred, out)
        elif child is not None and not isinstance(child, str):
            _find(child, pred, out)
    return out


def test_summary_view_constructs_and_returns_to_menu():
    run = new_run(5, champion_offer(5)[0])
    run.status = RunStatus.VICTORY
    run.battle_log = [
        SimpleNamespace(node_id="n1-Lisbon", team_damage_dealt={"a": 80},
                        outcome=CombatOutcome.WIN),
    ]
    calls = {"menu": 0}
    view = build_summary_view(_FakePage(), run,
                              on_menu=lambda: calls.__setitem__("menu", 1))
    assert isinstance(view, ft.View)
    assert view.route == "/summary"
    btns = _find(view, lambda c: isinstance(c, ft.FilledButton))
    assert btns, "Return to Menu button missing"
    btns[0].on_click(None)
    assert calls["menu"] == 1
