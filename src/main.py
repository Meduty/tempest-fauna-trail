import os
import sys
from pathlib import Path

# `flet run` invokes this file with src/ on sys.path, not the project root.
# Add the project root so absolute `src.X` imports resolve the same as in
# tests + CLI tools.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Load OPENWEATHER_API_KEY (and friends) from a repo-root .env so `flet run` sees
# the same key the tests do (conftest loads it separately). `python-dotenv` is a
# dev dependency — guard the import so packaged builds without it (or a shell that
# already exported the key) still start. An existing env var always wins.
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(_PROJECT_ROOT / ".env")
except ImportError:
    pass

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


def _push_prep(page: ft.Page, run, node) -> None:
    """Play-Next landing — the full Prep view (T.23a). Placement + shop + bench +
    preview + tooltips over the finished economy/combat backend (V.63). Start-Combat
    builds a `CombatSession` and opens the combat view; the reward/progression step
    lands in T.15 (15a), so for now combat exit pops back to Prep (result dropped)."""
    from src.ui.views.combat import build_combat_view
    from src.ui.views.prep import build_prep_view

    def _open_combat(session) -> None:
        # T.15 (15a) threads the BattleResult out via on_exit(result) for the reward
        # step; until then exit just unwinds to the Trail (V.64 producer is the loop).
        page.views.append(build_combat_view(page, session, on_exit=lambda: _pop(page)))
        page.update()

    page.views.append(
        build_prep_view(
            page, run, node,
            on_start_combat=_open_combat,
            on_back=lambda: _pop(page),
        )
    )
    page.update()


def _push_trail(page: ft.Page, run) -> None:
    """Push the Trail view (T.11) — route map + node focus + team summary + live
    weather. Play Next → Prep; Save & Exit autosaves the run and returns to menu."""
    from src.game.save import default_save_dir, save_run
    from src.ui.views.trail import build_trail_view

    def _save_exit() -> None:
        # Autosave via the atomic save layer (V.65/V.36), then back to the menu.
        save_run(run, default_save_dir() / f"{run.run_id}.json")
        _pop(page)  # fires the Trail's refresher-stop handler (V.66)

    page.views.append(
        build_trail_view(
            page, run,
            on_play_next=lambda node: _push_prep(page, run, node),
            on_save_exit=_save_exit,
        )
    )
    page.update()


def _start_new_run(page: ft.Page) -> None:
    """New Run → RunStart champion pick → build the Run → Trail (T.10, 10a)."""
    import secrets

    from src.game.run_init import new_run
    from src.ui.views.run_start import build_run_start_view

    seed = secrets.randbelow(0xFFFFFFFF)

    def _on_pick(champion_id: str) -> None:
        run = new_run(seed, champion_id)
        _push_trail(page, run)

    page.views.append(
        build_run_start_view(page, seed=seed, on_pick=_on_pick, on_back=lambda: _pop(page))
    )
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

    def _continue() -> None:
        """Continue placeholder — load-into-Trail wired in T.15 (15b)."""

    def _open_settings() -> None:
        from src.ui.views.settings import build_settings_view
        page.views.append(build_settings_view(page, on_back=lambda: _pop(page)))
        page.update()

    save_exists = default_save_dir().exists() and any(default_save_dir().glob("*.json"))

    menu = build_menu_view(
        page,
        on_new_run=lambda: _start_new_run(page),
        on_continue=_continue,
        on_playfight=lambda: _push_playfight(page),
        on_quit=_quit,
        on_settings=_open_settings,
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
