"""Augment view (T.42a) — construction + pick/reroll wiring smoke test.

Constructing the view instantiates every Flet control, so this guards against
bad control kwargs (e.g. the `Text(wrap=...)` crash) that the logic-only suite
can't see (B.37).
"""

from __future__ import annotations

import flet as ft

from src.game.models import NodeState, NodeType
from src.game.run_init import champion_offer, new_run
from src.ui.views.augment import build_augment_view

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


def _run_on_augment_node():
    run = new_run(_SEED, champion_offer(_SEED)[0])
    node = next(n for n in run.route if n.node_type == NodeType.AUGMENT)
    for n in run.route:
        n.state = NodeState.UPCOMING
    node.state = NodeState.CURRENT
    run.current_node_index = node.index
    return run, node


def test_augment_view_constructs():
    run, node = _run_on_augment_node()
    view = build_augment_view(_FakePage(), run, node, on_done=lambda: None)
    assert isinstance(view, ft.View)
    assert view.route == "/augment"
    # 3 offer cards each carry a "Choose" FilledButton.
    choose = _find(view, lambda c: isinstance(c, ft.FilledButton))
    assert len(choose) == 3


def test_augment_pick_applies_and_advances():
    run, node = _run_on_augment_node()
    node_index = node.index
    calls = {"done": 0}
    view = build_augment_view(_FakePage(), run, node,
                              on_done=lambda: calls.__setitem__("done", 1))
    assert not run.active_augments
    _find(view, lambda c: isinstance(c, ft.FilledButton))[0].on_click(None)
    assert len(run.active_augments) == 1          # augment applied
    assert node.state == NodeState.CLEARED         # node resolved (V.83)
    assert run.current_node_index > node_index     # advanced
    assert calls["done"] == 1


def test_augment_double_pick_resolves_once():
    """Re-entrancy guard: a second Choose click must not apply a 2nd augment or
    advance a 2nd node (F1 review finding)."""
    run, node = _run_on_augment_node()
    node_index = node.index
    calls = {"done": 0}
    view = build_augment_view(_FakePage(), run, node,
                              on_done=lambda: calls.__setitem__("done", calls["done"] + 1))
    btn = _find(view, lambda c: isinstance(c, ft.FilledButton))[0]
    btn.on_click(None)
    btn.on_click(None)   # simulate a stray second click before the view pops
    assert len(run.active_augments) == 1              # not 2
    assert run.current_node_index > node_index        # advanced
    assert node.state == NodeState.CLEARED
    assert calls["done"] == 1                          # resolved exactly once


def test_augment_reroll_button_present_and_fires():
    run, node = _run_on_augment_node()
    view = build_augment_view(_FakePage(), run, node, on_done=lambda: None)
    reroll = _find(view, lambda c: isinstance(c, ft.OutlinedButton))
    assert reroll and not reroll[0].disabled   # one free reroll available
    reroll[0].on_click(None)                   # must not raise (rebuilds offer)
