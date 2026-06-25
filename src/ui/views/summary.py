"""Run-summary view (T.13, route `/summary`) — the run-end screen.

Pure presentation (V.63/V.1): outcome banner + the canvas damage-per-battle chart
(`viz/run_summary.build_run_summary`, V.72) + final stats, all read off the live
`Run`. One **Return to Menu** button. The terminal → Summary routing is wired by
the producer in T.15b; this view is built + verified standalone here.
"""

from __future__ import annotations

from typing import Callable

import flet as ft

from src.game.models import NodeState, Run, RunStatus
from src.viz.run_summary import build_run_summary
from src.ui.theme import (
    ACCENT,
    BG,
    CARD_RADIUS,
    DANGER,
    FONT_SIZE_BODY,
    FONT_SIZE_CAPTION,
    FONT_SIZE_DISPLAY,
    FONT_SIZE_H2,
    SPACING_LG,
    SPACING_MD,
    SPACING_SM,
    SPACING_XL,
    SUCCESS,
    SURFACE,
    SURFACE_ELEVATED,
    TEXT_MUTED,
    TEXT_PRIMARY,
    WARNING,
)


def build_summary_view(
    page: ft.Page,
    run: Run,
    *,
    on_menu: Callable[[], None],
) -> ft.View:
    """Build the run-summary view for a finished ``run`` (T.13, route `/summary`).

    ``on_menu()`` returns to the main menu.
    """
    victory = run.status == RunStatus.VICTORY
    banner = "Victory" if victory else "Defeat"
    banner_color = SUCCESS if victory else DANGER

    cleared = sum(1 for n in run.route if n.state == NodeState.CLEARED)

    stats = ft.Row(
        [
            _chip("Nodes cleared", f"{cleared} / {len(run.route)}", TEXT_PRIMARY),
            _chip("Battles", str(len(run.battle_log)), ACCENT),
            _chip("Amber", str(run.amber), WARNING),
            _chip("Rank", str(run.tempest_rank), ACCENT),
        ],
        spacing=SPACING_SM, wrap=True, alignment=ft.MainAxisAlignment.CENTER,
    )

    chart = ft.Container(
        build_run_summary(run),
        bgcolor=SURFACE_ELEVATED, border_radius=CARD_RADIUS, padding=SPACING_MD,
    )

    card = ft.Container(
        ft.Column(
            [
                ft.Text(banner, size=FONT_SIZE_DISPLAY, weight=ft.FontWeight.BOLD,
                        color=banner_color),
                ft.Text("Damage dealt per battle", size=FONT_SIZE_CAPTION,
                        color=TEXT_MUTED),
                ft.Container(height=SPACING_SM),
                ft.Row([chart], alignment=ft.MainAxisAlignment.CENTER,
                       scroll=ft.ScrollMode.AUTO),
                ft.Container(height=SPACING_SM),
                stats,
                ft.Container(height=SPACING_LG),
                ft.FilledButton("Return to Menu", on_click=lambda _e: on_menu(),
                                style=ft.ButtonStyle(bgcolor=ACCENT)),
            ],
            spacing=SPACING_SM, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        ),
        bgcolor=SURFACE, border_radius=CARD_RADIUS, padding=SPACING_XL,
    )
    root = ft.Container(bgcolor=BG, expand=True, alignment=ft.Alignment.CENTER,
                        padding=SPACING_XL, content=ft.Column(
                            [card], alignment=ft.MainAxisAlignment.CENTER,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            scroll=ft.ScrollMode.AUTO, expand=True))
    return ft.View(route="/summary", controls=[root], padding=0)


def _chip(label: str, value: str, color: str) -> ft.Control:
    return ft.Container(
        ft.Row(
            [
                ft.Text(label, size=FONT_SIZE_CAPTION, color=TEXT_MUTED),
                ft.Text(value, size=FONT_SIZE_BODY, color=color,
                        weight=ft.FontWeight.BOLD),
            ],
            spacing=SPACING_SM, tight=True,
        ),
        bgcolor=SURFACE_ELEVATED, border_radius=CARD_RADIUS,
        padding=ft.Padding(left=10, right=10, top=4, bottom=4),
    )
