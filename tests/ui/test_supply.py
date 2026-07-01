"""Supply view (T.42b) — construction + recruit wiring smoke test.

Constructing the view instantiates every Flet control, guarding bad control
kwargs the logic-only suite can't see (B.37).
"""

from __future__ import annotations

import flet as ft

from src.game.models import NodeState, NodeType
from src.game.run_init import champion_offer, new_run
from src.ui.views.supply import build_supply_view

_SEED = 7


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


def _run_on_supply_node():
    run = new_run(_SEED, champion_offer(_SEED)[0])
    node = next(n for n in run.route if n.node_type == NodeType.SUPPLY)
    for n in run.route:
        n.state = NodeState.UPCOMING
    node.state = NodeState.CURRENT
    run.current_node_index = node.index
    return run, node


def test_supply_view_constructs():
    run, node = _run_on_supply_node()
    view = build_supply_view(_FakePage(), run, node, on_done=lambda: None)
    assert isinstance(view, ft.View)
    assert view.route == "/supply"
    # 5 free-recruit cards each carry a FilledButton.
    assert len(_find(view, lambda c: isinstance(c, ft.FilledButton))) == 5


def test_supply_recruit_applies_and_advances():
    run, node = _run_on_supply_node()
    node_index = node.index
    copies_before = sum(run.champion_copies.values())
    calls = {"done": 0}
    view = build_supply_view(_FakePage(), run, node,
                             on_done=lambda: calls.__setitem__("done", 1))
    _find(view, lambda c: isinstance(c, ft.FilledButton))[0].on_click(None)
    assert sum(run.champion_copies.values()) == copies_before + 1     # recruited (free copy)
    assert node.state == NodeState.CLEARED                            # resolved (V.83)
    assert run.current_node_index > node_index                       # advanced
    assert calls["done"] == 1
