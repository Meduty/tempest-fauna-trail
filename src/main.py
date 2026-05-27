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


def main(page: ft.Page):
    if _ADMIN_ENABLED:
        _admin_ui(page)
    else:
        _counter_ui(page)


ft.run(main)
