"""Reward view (T.15a, route `/reward`) — the post-fight node-result panel.

Pure presentation (V.63/V.1): it reads the `NodeResultSummary` the producer
already computed via `economy.apply_node_result` (V.69) plus the live `Run`; it
recomputes no economy/progression number. One **Continue** button hands control
back to the producer, which routes to the Trail (loop continues) or — on a
terminal run — the Summary/menu (T.15b).
"""

from __future__ import annotations

from typing import Callable

import flet as ft

from src.game.economy import NodeResultSummary
from src.game.models import NodeState, Run, RunStatus
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


def build_reward_view(
    page: ft.Page,
    run: Run,
    summary: NodeResultSummary,
    *,
    on_continue: Callable[[], None],
) -> ft.View:
    """Build the Reward view for a fought node's ``summary`` (T.15a).

    ``on_continue()`` is the producer's router — Trail on a continuing run, or
    Summary/menu when ``summary.terminal``.
    """
    cleared = sum(1 for n in run.route if n.state == NodeState.CLEARED)

    if summary.status == RunStatus.VICTORY:
        banner, color = "Run Complete — Victory", SUCCESS
    elif summary.status == RunStatus.DEFEAT:
        banner, color = "Defeated", DANGER
    elif summary.won:
        banner, color = "Node Cleared", SUCCESS
    else:
        banner, color = "Held the Line", WARNING  # non-terminal non-win (unreachable in MVP)

    rows: list[ft.Control] = [
        ft.Text(banner, size=FONT_SIZE_DISPLAY, weight=ft.FontWeight.BOLD, color=color),
        ft.Container(height=SPACING_SM),
        _stat_row("Amber gained", f"+{summary.amber_gained}", WARNING),
        _stat_row("Amber", f"{run.amber}", TEXT_PRIMARY),
        _stat_row("Tempest gained", f"+{summary.tempest_gained}", ACCENT),
        _stat_row("Rank", f"{run.tempest_rank}", ACCENT),
        _stat_row("Nodes cleared", f"{cleared} / {len(run.route)}", TEXT_PRIMARY),
    ]

    continue_label = "Continue ▶"
    if summary.terminal:
        continue_label = "View Summary ▶" if summary.status == RunStatus.VICTORY else "Continue ▶"

    rows.append(ft.Container(height=SPACING_LG))
    rows.append(
        ft.FilledButton(continue_label, on_click=lambda _e: on_continue(),
                        style=ft.ButtonStyle(bgcolor=ACCENT))
    )

    card = ft.Container(
        ft.Column(rows, spacing=SPACING_SM,
                  horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
        bgcolor=SURFACE, border_radius=CARD_RADIUS, padding=SPACING_XL, width=420,
    )
    root = ft.Container(bgcolor=BG, expand=True, alignment=ft.Alignment.CENTER,
                        padding=SPACING_XL, content=card)
    return ft.View(route="/reward", controls=[root], padding=0)


def _stat_row(label: str, value: str, color: str) -> ft.Control:
    return ft.Row(
        [
            ft.Text(label, size=FONT_SIZE_BODY, color=TEXT_MUTED, expand=True),
            ft.Text(value, size=FONT_SIZE_H2, color=color, weight=ft.FontWeight.BOLD),
        ],
        spacing=SPACING_MD,
    )
