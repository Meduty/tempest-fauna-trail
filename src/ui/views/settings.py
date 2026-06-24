"""Settings view — set the OpenWeather API key without touching `.env`/shell.

Pure presentation (V.1): persistence lives in `src/app_config.py` (Flet-free file
I/O); this view only renders the field + Save and emits intent. The key is masked
in the field and **never displayed in full** or logged (V.3). On Save the key is
written to the user config file; the next time the Trail opens it resolves the new
key (`app_config.resolve_api_key`) and starts the live-weather refresher.
"""

from __future__ import annotations

from typing import Callable

import flet as ft

from src.app_config import default_config_path, save_api_key, stored_api_key
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
    SUCCESS,
    SURFACE,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

_TITLE = "Settings"
_SUBTITLE = "Live weather needs a free OpenWeather API key."
_FIELD_W = 360


def build_settings_view(
    page: ft.Page,
    *,
    on_back: Callable[[], None],
) -> ft.View:
    """Build the Settings view (route `/settings`).

    Shows whether a key is already stored, a masked input, and Save. `on_back`
    returns to the menu.
    """
    existing = stored_api_key()
    status = ft.Text(
        "A key is currently saved." if existing else "No key saved — weather stays "
        '"pending".',
        size=FONT_SIZE_CAPTION,
        color=SUCCESS if existing else TEXT_MUTED,
    )

    key_field = ft.TextField(
        label="OpenWeather API key",
        hint_text="paste your key",
        password=True,
        can_reveal_password=True,
        width=_FIELD_W,
        value="",
    )

    def _save(_e: object) -> None:
        save_api_key(key_field.value or "")
        saved = stored_api_key()
        status.value = (
            "Saved — reopen the Trail to load live weather." if saved
            else 'Cleared — weather will stay "pending".'
        )
        status.color = SUCCESS if saved else TEXT_MUTED
        key_field.value = ""
        page.update()

    card = ft.Container(
        bgcolor=SURFACE,
        border_radius=12,
        padding=SPACING_XL,
        border=ft.Border.all(1, ACCENT),
        content=ft.Column(
            [
                ft.Text(_TITLE, size=FONT_SIZE_DISPLAY, weight=ft.FontWeight.BOLD,
                        color=TEXT_PRIMARY, text_align=ft.TextAlign.CENTER),
                ft.Text(_SUBTITLE, size=FONT_SIZE_BODY, color=TEXT_MUTED,
                        text_align=ft.TextAlign.CENTER, width=_FIELD_W),
                ft.Container(height=SPACING_LG),
                key_field,
                status,
                ft.Container(height=SPACING_SM),
                ft.Row(
                    [
                        ft.FilledButton("Save key", on_click=_save),
                        ft.OutlinedButton("← Back", on_click=lambda _e: on_back()),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=SPACING_MD,
                ),
                ft.Container(height=SPACING_SM),
                ft.Text(
                    "Stored locally, never logged. The OPENWEATHER_API_KEY env var, "
                    "if set, overrides this.",
                    size=FONT_SIZE_CAPTION, color=TEXT_MUTED,
                    text_align=ft.TextAlign.CENTER, width=_FIELD_W,
                ),
                ft.Text(f"{default_config_path()}", size=FONT_SIZE_CAPTION,
                        color=TEXT_MUTED, text_align=ft.TextAlign.CENTER,
                        width=_FIELD_W, selectable=True),
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
    return ft.View(route="/settings", controls=[root], padding=0)
