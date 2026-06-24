import os
import sys
from pathlib import Path

# `flet run` invokes this file with src/ on sys.path, not the project root.
# Add the project root so absolute `src.X` imports resolve the same as in
# tests + CLI tools.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import flet as ft  # noqa: E402 — must follow the sys.path bootstrap above

from src.ui.views.admin import build_admin_content  # noqa: E402


_ADMIN_ENABLED = os.environ.get("TEMPEST_ADMIN") == "1"
# Legacy shortcut — TEMPEST_DEV=1 jumps straight into the Playfight harness,
# skipping the menu. The same harness is now reachable from the menu's Playfight
# button, so this is a convenience for muscle-memory, not the only path.
_DEV_ENABLED = os.environ.get("TEMPEST_DEV") == "1"


def _admin_ui(page: ft.Page) -> None:
    page.title = "Tempest — Playtest Admin"
    page.appbar = ft.AppBar(title=ft.Text("Tempest — Playtest Admin"))
    page.add(build_admin_content(page))


def _pop(page: ft.Page) -> None:
    """Pop the top view, firing its on-pop handler (e.g. the combat view stops
    its autoplay thread via `view.data`). Never pops below the base view."""
    if len(page.views) > 1:
        top = page.views[-1]
        handler = getattr(top, "data", None)
        if callable(handler):
            handler(None)
        page.views.pop()
        page.update()


def _push_playfight(page: ft.Page) -> None:
    """Open the Playfight combat dev harness (harness → combat `page.views`
    stack). The harness builds a `CombatSession`; opening combat pushes the
    combat view, and back-nav pops to the menu (T.9, T.12a)."""
    from src.ui.views.combat import build_combat_view
    from src.ui.views.dev_harness import build_dev_harness_view

    def _open_combat(session) -> None:
        page.views.append(build_combat_view(page, session, on_exit=lambda: _pop(page)))
        page.update()

    page.views.append(build_dev_harness_view(page, _open_combat))
    page.update()


def _game_ui(page: ft.Page) -> None:
    """The real app shell (T.9) — a `page.views` stack rooted at the main menu.

    Playfight pushes the combat dev harness → combat view; New Run / Continue are
    surfaced but disabled until the Trail/Prep run shell (T.10/T.11) exists.
    """
    from src.game.save import default_save_dir
    from src.ui.views.menu import build_menu_view

    page.title = "Tempest Fauna Trail"

    def _quit() -> None:
        page.window.destroy()

    def _noop() -> None:
        """New Run / Continue placeholder — wired once Trail/Prep land (T.10/T.11)."""

    save_exists = default_save_dir().exists() and any(default_save_dir().glob("*.json"))

    menu = build_menu_view(
        page,
        on_new_run=_noop,
        on_continue=_noop,
        on_playfight=lambda: _push_playfight(page),
        on_quit=_quit,
        save_exists=save_exists,
    )

    page.on_view_pop = lambda _e: _pop(page)
    page.views.clear()
    page.views.append(menu)
    if _DEV_ENABLED:  # legacy shortcut — land directly in Playfight
        _push_playfight(page)
    page.update()


def main(page: ft.Page):
    if _ADMIN_ENABLED:
        _admin_ui(page)
    else:
        _game_ui(page)


ft.run(main)
