"""Main-menu view (T.9) — construction + intent wiring smoke tests.

No display: build the `ft.View` and walk its control tree (mirrors
test_components). Asserts the route, the four entries + their enabled state, and
that the live buttons fire their intent callbacks.
"""

from __future__ import annotations

import flet as ft

from src.ui.views.menu import build_menu_view


def _buttons(control, found=None):
    """Recursively collect every button-like control (has `.text`)."""
    found = [] if found is None else found
    if isinstance(control, (ft.FilledButton, ft.OutlinedButton, ft.TextButton)):
        found.append(control)
    for attr in ("controls", "content"):
        child = getattr(control, attr, None)
        if isinstance(child, list):
            for c in child:
                _buttons(c, found)
        elif child is not None and not isinstance(child, str):
            _buttons(child, found)
    return found


class _FakePage:
    """build_menu_view only stores callbacks; it never touches the page."""


def _build(**over):
    calls = {"new_run": 0, "continue": 0, "playfight": 0, "quit": 0}
    view = build_menu_view(
        _FakePage(),  # construction never touches the page
        on_new_run=lambda: calls.__setitem__("new_run", calls["new_run"] + 1),
        on_continue=lambda: calls.__setitem__("continue", calls["continue"] + 1),
        on_playfight=lambda: calls.__setitem__("playfight", calls["playfight"] + 1),
        on_quit=lambda: calls.__setitem__("quit", calls["quit"] + 1),
        **over,
    )
    return view, calls


def test_menu_is_root_route_view():
    view, _ = _build()
    assert isinstance(view, ft.View)
    assert view.route == "/"


def test_menu_has_four_entries_with_expected_enabled_state():
    view, _ = _build()
    by_text = {b.content: b for b in _buttons(view)}
    assert set(by_text) == {"New Run", "Continue", "Playfight ▶", "Quit"}
    # New Run live (T.10 → RunStart); Continue disabled until load-into-Trail (T.15).
    assert not by_text["New Run"].disabled
    assert by_text["Continue"].disabled is True
    assert not by_text["Playfight ▶"].disabled
    assert not by_text["Quit"].disabled


def test_continue_enables_when_save_present():
    no_save = {b.content: b for b in _buttons(_build(save_exists=False)[0])}
    has_save = {b.content: b for b in _buttons(_build(save_exists=True)[0])}
    # No save → disabled with a hint; save present → live Continue (T.15b).
    assert no_save["Continue"].disabled is True
    assert no_save["Continue"].tooltip == "No saved run found."
    assert not has_save["Continue"].disabled


def test_continue_fires_when_enabled():
    view, calls = _build(save_exists=True)
    by_text = {b.content: b for b in _buttons(view)}
    by_text["Continue"].on_click(None)
    assert calls["continue"] == 1


def test_live_buttons_fire_their_intent():
    view, calls = _build()
    by_text = {b.content: b for b in _buttons(view)}
    by_text["New Run"].on_click(None)
    by_text["Playfight ▶"].on_click(None)
    by_text["Quit"].on_click(None)
    assert calls["new_run"] == 1 and calls["playfight"] == 1 and calls["quit"] == 1
