"""Reward view (T.15a + T.38, route `/reward`) — the post-fight node-result panel.

Pure presentation (V.63/V.1): it reads the `NodeResultSummary` the producer
already computed via `economy.apply_node_result` (V.69/V.70/V.71) plus the live
`Run`; it recomputes no economy/progression number. It surfaces **Hearts**
remaining + the node's **type rewards** (REWARD loot / CHALLENGE payload) and,
for a pending CHALLENGE `champion_offer`, an interactive **Recruit / Skip** that
mutates the run only through `economy.recruit_challenge_offer` (the choice lives
here, the mutation in `game/`). One **Continue** button hands control back to the
producer, which routes to the Trail (loop continues) or — on a terminal run —
the Summary/menu (T.15b).
"""

from __future__ import annotations

from typing import Callable

import flet as ft

from src.game.content import CHAMPION_DEF_BY_ID
from src.game.economy import NodeResultSummary, recruit_challenge_offer
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
    """Build the Reward view for a fought node's ``summary`` (T.15a + T.38).

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
        banner, color = "Held the Line", WARNING  # survivable loss (Hearts model, V.71)

    hearts = summary.hearts_remaining
    hearts_str = ("♥" * hearts) if hearts > 0 else "—"
    hearts_color = DANGER if hearts <= 1 else TEXT_PRIMARY

    rows: list[ft.Control] = [
        ft.Text(banner, size=FONT_SIZE_DISPLAY, weight=ft.FontWeight.BOLD, color=color),
        ft.Container(height=SPACING_SM),
        _stat_row("Amber gained", f"+{summary.amber_gained}", WARNING),
        _stat_row("Amber", f"{run.amber}", TEXT_PRIMARY),
        _stat_row("Tempest gained", f"+{summary.tempest_gained}", ACCENT),
        _stat_row("Rank", f"{run.tempest_rank}", ACCENT),
        _stat_row("Hearts", hearts_str, hearts_color),
        _stat_row("Nodes cleared", f"{cleared} / {len(run.route)}", TEXT_PRIMARY),
    ]

    # Type-reward block (REWARD loot / CHALLENGE amber+components) — win only (V.70).
    reward_bits = [_pretty(item_id) for item_id in summary.item_ids]
    if summary.bonus_amber:
        reward_bits.append(f"+{summary.bonus_amber} Amber")
    if reward_bits:
        rows.append(ft.Container(height=SPACING_SM))
        rows.append(ft.Text("Rewards", size=FONT_SIZE_CAPTION, color=TEXT_MUTED))
        rows.append(
            ft.Container(
                ft.Text(" · ".join(reward_bits), size=FONT_SIZE_BODY, color=SUCCESS),
                bgcolor=SURFACE_ELEVATED, border_radius=CARD_RADIUS,
                padding=SPACING_SM,
            )
        )

    # Interactive CHALLENGE recruit — pending offer applied only via the game
    # function on Recruit (V.63 — view chooses, game mutates).
    if summary.champion_offer:
        champ_def = CHAMPION_DEF_BY_ID.get(summary.champion_offer)
        offer_name = champ_def.name if champ_def is not None else summary.champion_offer
        offer_slot = ft.Container()

        def _recruit(_e: ft.ControlEvent) -> None:
            recruited = recruit_challenge_offer(run, summary.champion_offer)  # type: ignore[arg-type]
            if recruited:                       # only claim success when the game state changed
                offer_slot.content = ft.Text(
                    f"✓ Recruited {offer_name}", size=FONT_SIZE_BODY, color=SUCCESS,
                )
            else:                               # already owned / unknown id — no-op, no false claim
                offer_slot.content = ft.Text(
                    f"Already recruited {offer_name}", size=FONT_SIZE_BODY, color=TEXT_MUTED,
                )
            page.update()

        def _skip(_e: ft.ControlEvent) -> None:
            offer_slot.content = ft.Text(
                f"Skipped {offer_name}", size=FONT_SIZE_BODY, color=TEXT_MUTED,
            )
            page.update()

        offer_slot.content = ft.Column(
            [
                ft.Text(f"Recruit {offer_name}?", size=FONT_SIZE_BODY, color=TEXT_PRIMARY),
                ft.Row(
                    [
                        ft.FilledButton("Recruit", on_click=_recruit,
                                        style=ft.ButtonStyle(bgcolor=ACCENT)),
                        ft.OutlinedButton("Skip", on_click=_skip),
                    ],
                    spacing=SPACING_SM,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ],
            spacing=SPACING_SM,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        )
        rows.append(ft.Container(height=SPACING_SM))
        rows.append(offer_slot)

    # Terminal runs (VICTORY *and* DEFEAT) route to the Summary view (main.py),
    # so the label must read "View Summary" for both — not just victory.
    continue_label = "View Summary ▶" if summary.terminal else "Continue ▶"

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


def _pretty(item_id: str) -> str:
    """Render a content id (`apex_fang`) as a display label (`Apex Fang`)."""
    return item_id.replace("_", " ").title()


def _stat_row(label: str, value: str, color: str) -> ft.Control:
    return ft.Row(
        [
            ft.Text(label, size=FONT_SIZE_BODY, color=TEXT_MUTED, expand=True),
            ft.Text(value, size=FONT_SIZE_H2, color=color, weight=ft.FontWeight.BOLD),
        ],
        spacing=SPACING_MD,
    )
