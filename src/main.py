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


def _pop_to_root(page: ft.Page) -> None:
    """Unwind the whole `page.views` stack back to the menu, firing each view's
    on-pop handler (stops combat autoplay + the Trail refresher, V.66)."""
    while len(page.views) > 1:
        _pop(page)


def _finish_combat(page: ft.Page, run, node, result) -> None:
    """Reward step (T.15a, V.64/V.69) — the run-loop *producer*. Applies the fought
    node's outcome through the single game-side orchestrator, autosaves the run
    (V.65), then shows the reward panel. Continue routes back to a fresh Trail (loop
    continues) or, on a terminal run, the menu (T.15a interim → Summary in T.15b)."""
    from src.game.economy import apply_node_result
    from src.game.save import default_save_dir, save_run
    from src.ui.views.reward import build_reward_view
    from src.ui.views.summary import build_summary_view

    save_path = default_save_dir() / f"{run.run_id}.json"
    summary = apply_node_result(run, result)
    save_run(run, save_path)  # node-boundary autosave (pre-reward-panel state)

    def _continue() -> None:
        # Re-autosave: the reward panel's interactive choices (T.38 Recruit) mutate
        # the run *after* the first save, so persist again before leaving the node
        # boundary — else a recruit is lost if the player quits here (V.65).
        save_run(run, save_path)
        _pop_to_root(page)  # drop reward + combat + prep + stale trail → menu
        if summary.terminal:
            # Run over (victory/defeat) → the run-summary screen, then the menu (T.15b).
            page.views.append(build_summary_view(page, run, on_menu=lambda: _pop(page)))
            page.update()
        else:
            _push_trail(page, run)  # fresh Trail at the new current node

    page.views.append(build_reward_view(page, run, summary, on_continue=_continue))
    page.update()


def _push_prep(page: ft.Page, run, node) -> None:
    """Play-Next landing — the full Prep view (T.23a). Placement + shop + bench +
    preview + tooltips over the finished economy/combat backend (V.63). Start-Combat
    builds a `CombatSession` and opens the combat view; on any exit the reward step
    applies the resolved result (commit-on-start, V.69) and shows the reward panel."""
    from src.ui.views.combat import build_combat_view
    from src.ui.views.prep import build_prep_view

    def _open_combat(session) -> None:
        page.views.append(build_combat_view(
            page, session,
            on_exit=lambda result: _finish_combat(page, run, node, result),
        ))
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
        # Non-loop producer — ignores the BattleResult (V.64), just pops to the harness.
        page.views.append(build_combat_view(page, session, on_exit=lambda _result: _pop(page)))
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
        """Resume the most-recent saved run into the Trail (T.15b). Picks the latest
        `*.json` by mtime; a corrupt/unreadable save is ignored (stays on the menu)."""
        from src.game.save import load_run

        saves = sorted(default_save_dir().glob("*.json"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        for path in saves:
            try:
                run = load_run(path)
            except Exception:  # noqa: BLE001 — skip a corrupt/newer save, try the next
                continue
            _push_trail(page, run)
            return

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
