import os
import sys
from pathlib import Path

# `flet run` invokes this file with src/ on sys.path, not the project root.
# Add the project root so absolute `src.X` imports resolve the same as in
# tests + CLI tools.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import flet as ft

from src.ui.views.admin import build_admin_content


_ADMIN_ENABLED = os.environ.get("TEMPEST_ADMIN") == "1"
_DEV_ENABLED = os.environ.get("TEMPEST_DEV") == "1"


def _counter_ui(page: ft.Page) -> None:
    counter = ft.Text("0", size=50, data=0)

    def increment_click(_):
        counter.data += 1
        counter.value = str(counter.data)
        counter.update()

    page.floating_action_button = ft.FloatingActionButton(
        icon=ft.Icons.ADD, on_click=increment_click
    )
    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Container(content=counter, alignment=ft.Alignment.CENTER),
        )
    )


def _admin_ui(page: ft.Page) -> None:
    page.title = "Tempest — Playtest Admin"
    page.appbar = ft.AppBar(title=ft.Text("Tempest — Playtest Admin"))
    page.add(build_admin_content(page))


def _dev_ui(page: ft.Page) -> None:
    """Dev combat harness (TEMPEST_DEV=1) — a tiny harness↔combat `page.views`
    stack ahead of the real routing (T.15). Not a production shell."""
    from src.ui.views.combat import build_combat_view
    from src.ui.views.dev_harness import build_dev_harness_view

    page.title = "Tempest — Combat Dev Harness"

    def _pop() -> None:
        if len(page.views) > 1:
            top = page.views[-1]
            handler = getattr(top, "data", None)
            if callable(handler):
                handler(None)  # combat view's on-pop (stops autoplay thread)
            page.views.pop()
            page.update()

    def _open_combat(session) -> None:
        page.views.append(build_combat_view(page, session, on_exit=_pop))
        page.update()

    page.on_view_pop = lambda _e: _pop()
    page.views.clear()
    page.views.append(build_dev_harness_view(page, _open_combat))
    page.update()


def main(page: ft.Page):
    if _DEV_ENABLED:
        _dev_ui(page)
    elif _ADMIN_ENABLED:
        _admin_ui(page)
    else:
        _counter_ui(page)


ft.run(main)
