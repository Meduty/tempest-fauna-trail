"""RunStart view (T.10) — pick 1 of 3 starting champions (views_spec §4 → Trail).

Pure presentation (V.1/V.63): the offer + run construction live in
:mod:`src.game.run_init`; this view only renders the offered champions and emits
the picked id via ``on_pick``. The host (`main.py`) calls ``run_init.new_run`` and
opens the Trail. No game logic computed here.
"""

from __future__ import annotations

from typing import Callable

import flet as ft

from src.game.content import CHAMPION_ROSTER
from src.game.run_init import champion_offer
from src.ui.components.champion_card import champion_card
from src.ui.theme import (
    BG,
    FONT_SIZE_BODY,
    FONT_SIZE_DISPLAY,
    SPACING_LG,
    SPACING_MD,
    SPACING_SM,
    SPACING_XL,
    SPACING_XXL,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

_TITLE = "Choose your first champion"
_SUBTITLE = "One of three. Live weather will favour different affinities along the trail."


def build_run_start_view(
    page: ft.Page,
    *,
    seed: int,
    on_pick: Callable[[str], None],
    on_back: Callable[[], None],
) -> ft.View:
    """Build the run-start champion-pick view for ``seed``.

    Renders ``run_init.champion_offer(seed)`` as selectable cards; a click calls
    ``on_pick(champion_id)``. ``on_back`` returns to the menu.
    """
    offer = champion_offer(seed)

    def _stats(champ) -> dict[str, int | float]:
        return {
            "STR": champ.strength,
            "INT": champ.intelligence,
            "AS": round(champ.attack_speed, 2),
            "Armor": champ.armor,
            "Res": champ.resistance,
        }

    cards = []
    for champ_id in offer:
        champ = CHAMPION_ROSTER[champ_id]
        cards.append(
            champion_card(
                name=champ.name,
                affinity=champ.affinity,
                traits=champ.traits,
                role=champ.role,
                tier=champ.tier,
                level=champ.level,
                max_hp=champ.max_hp,
                stats=_stats(champ),
                on_click=lambda _e, cid=champ_id: on_pick(cid),
            )
        )

    offer_row = ft.Row(
        cards,
        spacing=SPACING_LG,
        alignment=ft.MainAxisAlignment.CENTER,
        wrap=True,
    )

    body = ft.Column(
        [
            ft.Text(_TITLE, size=FONT_SIZE_DISPLAY, weight=ft.FontWeight.BOLD,
                    color=TEXT_PRIMARY, text_align=ft.TextAlign.CENTER),
            ft.Text(_SUBTITLE, size=FONT_SIZE_BODY, color=TEXT_MUTED,
                    text_align=ft.TextAlign.CENTER),
            ft.Container(height=SPACING_LG),
            offer_row,
            ft.Container(height=SPACING_SM),
            ft.TextButton("← Back to menu", on_click=lambda _e: on_back()),
        ],
        spacing=SPACING_MD,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        tight=True,
    )

    root = ft.Container(
        bgcolor=BG, expand=True, alignment=ft.Alignment.CENTER,
        padding=SPACING_XXL, content=body,
    )
    return ft.View(route="/run-start", controls=[root], padding=0)
