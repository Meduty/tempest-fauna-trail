"""Reward view (T.15a) — construction + Continue wiring smoke test."""

from __future__ import annotations

import flet as ft

from src.game.economy import NodeResultSummary
from src.game.models import RunStatus
from src.game.run_init import champion_offer, new_run
from src.ui.views.reward import build_reward_view


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


def test_reward_view_constructs_and_continues():
    run = new_run(7, champion_offer(7)[0])
    summary = NodeResultSummary(won=True, amber_gained=5, tempest_gained=2,
                                terminal=False, status=RunStatus.IN_PROGRESS)
    calls = {"continue": 0}
    view = build_reward_view(_FakePage(), run, summary,
                             on_continue=lambda: calls.__setitem__("continue", 1))
    assert isinstance(view, ft.View)
    assert view.route == "/reward"
    btns = _find(view, lambda c: isinstance(c, ft.FilledButton))
    assert btns, "Continue button missing"
    btns[0].on_click(None)
    assert calls["continue"] == 1
