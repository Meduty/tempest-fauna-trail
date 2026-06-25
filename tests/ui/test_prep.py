"""Prep view (T.23a) — construction + Start-Combat seam smoke tests.

No display: build the `ft.View` against a fake page and assert the route, that
the board auto-places the team, and that Start-Combat hands back a `CombatSession`
shape-identical to the dev-harness producer (team + deterministic enemies +
in-zone validated positions). Logic only (CLAUDE.md) — no pixel assertions.
"""

from __future__ import annotations

import flet as ft

from src.game.run_init import champion_offer, new_run
from src.game.loadout import ALLIED_ZONE_MAX_Q, validate_team_positions
from src.ui.combat_playback import CombatSession
from src.ui.views.prep import build_prep_view

_SEED = 12345


class _FakePage:
    """Prep calls `page.update()` on render; handlers also use `get_control`."""

    def update(self):  # noqa: D401 — no-op for headless construction
        pass

    def get_control(self, _cid):
        return None


def _run():
    offer = champion_offer(_SEED)
    return new_run(_SEED, offer[0])


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


def _build(run):
    captured = {"session": None, "back": 0}
    view = build_prep_view(
        _FakePage(), run, run.current_node(),
        on_start_combat=lambda s: captured.__setitem__("session", s),
        on_back=lambda: captured.__setitem__("back", captured["back"] + 1),
    )
    return view, captured


def test_prep_is_prep_route_view():
    view, _ = _build(_run())
    assert isinstance(view, ft.View)
    assert view.route == "/prep"


def test_start_combat_builds_valid_session():
    run = _run()
    view, captured = _build(run)
    # Fire Start Combat ▶.
    btns = _find(view, lambda c: isinstance(c, ft.FilledButton)
                 and getattr(c, "content", None) == "Start Combat ▶")
    assert btns, "Start Combat button missing"
    btns[0].on_click(None)

    session = captured["session"]
    assert isinstance(session, CombatSession)
    assert session.team, "team should be non-empty"
    # Positions cover the whole team, all inside the allied zone, validated.
    assert set(session.positions) == {c.id for c in session.team}
    assert all(0 <= q < ALLIED_ZONE_MAX_Q for (q, _r) in session.positions.values())
    validate_team_positions(session.team, session.positions)
    # Deterministic enemies present + combat weather == the node default (V.2/V.66).
    assert session.enemies
    assert session.weather == run.current_node().weather


def test_back_to_trail_fires():
    view, captured = _build(_run())
    btns = _find(view, lambda c: isinstance(c, ft.OutlinedButton)
                 and getattr(c, "content", None) == "← Trail")
    assert btns
    btns[0].on_click(None)
    assert captured["back"] == 1
