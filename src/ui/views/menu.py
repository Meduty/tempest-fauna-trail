"""Main menu view (T.9) — the app entry point at route `/` (views_spec §4).

Pure presentation (V.1 — `ui/` only). Offers the run-loop entries plus the
**Playfight** mode (the combat dev harness promoted to a first-class play mode):

- **New Run** / **Continue** — the Trail/Prep run shell (T.10/T.11) is not built
  yet, so these are surfaced but disabled with a hint; `save_exists` is plumbed
  so Continue lights up once a resumable run flow lands.
- **Playfight ▶** — opens the combat dev harness (`dev_harness.py`) → combat
  view. The one fully-playable path today.
- **Quit** — closes the app.

The caller (`main.py`) owns the `page.views` stack + navigation; this view only
emits intent via the `on_*` callbacks.
"""

from __future__ import annotations

from typing import Callable

import flet as ft

from src.ui.theme import (
    ACCENT,
    BG,
    FONT_SIZE_BODY,
    FONT_SIZE_CAPTION,
    FONT_SIZE_DISPLAY,
    SPACING_LG,
    SPACING_MD,
    SPACING_SM,
    SPACING_XL,
    SPACING_XXL,
    SURFACE,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

_TITLE = "Tempest Fauna Trail"
_SUBTITLE = "Animal champions cross real-world cities — live weather shapes the fight."
_NOT_YET_HINT = "Coming soon — needs the Trail run shell (T.10/T.11)."
_CONTINUE_SOON_HINT = "Coming soon — load-into-Trail lands in T.15."


def build_menu_view(
    page: ft.Page,
    *,
    on_new_run: Callable[[], None],
    on_continue: Callable[[], None],
    on_playfight: Callable[[], None],
    on_quit: Callable[[], None],
    save_exists: bool = False,
) -> ft.View:
    """Build the `/` main-menu view (views_spec §4).

    `on_*` are intent callbacks the host (`main.py`) wires into the view stack.
    `save_exists` gates **Continue** once a load-into-Trail flow exists; for now
    both New Run + Continue are disabled (no Trail to open) and carry a hint.
    """
    _btn_w = 280

    def _primary(label: str, on_click: Callable[[], None]) -> ft.Control:
        return ft.FilledButton(
            label, width=_btn_w, height=46,
            on_click=lambda _e: on_click(),
        )

    def _disabled(label: str, hint: str) -> ft.Control:
        return ft.OutlinedButton(label, width=_btn_w, height=46, disabled=True, tooltip=hint)

    # New Run is live (T.10 → RunStart → Trail). Continue stays disabled until the
    # load-into-Trail flow lands (T.15/15b); `save_exists` already threaded for it.
    new_run = _primary("New Run", on_new_run)
    if save_exists:
        continue_btn: ft.Control = _disabled("Continue", _CONTINUE_SOON_HINT)
    else:
        continue_btn = _disabled("Continue", "No saved run found.")

    actions = ft.Column(
        [
            new_run,
            continue_btn,
            _primary("Playfight ▶", on_playfight),
            ft.OutlinedButton("Quit", width=_btn_w, height=46, on_click=lambda _e: on_quit()),
        ],
        spacing=SPACING_MD,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    card = ft.Container(
        bgcolor=SURFACE, border_radius=12, padding=SPACING_XL,
        border=ft.Border.all(1, ACCENT),
        content=ft.Column(
            [
                ft.Text(_TITLE, size=FONT_SIZE_DISPLAY, weight=ft.FontWeight.BOLD,
                        color=TEXT_PRIMARY, text_align=ft.TextAlign.CENTER),
                ft.Text(_SUBTITLE, size=FONT_SIZE_BODY, color=TEXT_MUTED,
                        text_align=ft.TextAlign.CENTER, width=_btn_w),
                ft.Container(height=SPACING_LG),
                actions,
                ft.Container(height=SPACING_SM),
                ft.Text("Playfight = build a one-off fight and step through it.",
                        size=FONT_SIZE_CAPTION, color=TEXT_MUTED,
                        text_align=ft.TextAlign.CENTER, width=_btn_w),
            ],
            spacing=SPACING_SM,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        ),
    )

    root = ft.Container(
        bgcolor=BG, expand=True, alignment=ft.Alignment.CENTER,
        padding=SPACING_XXL, content=card,
    )
    return ft.View(route="/", controls=[root], padding=0)
