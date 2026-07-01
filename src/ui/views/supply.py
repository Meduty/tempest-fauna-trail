"""Supply node view (T.42b, route `/supply`) — the 1-of-5 free-recruit screen.

Pure presentation (V.63/V.1): the offer, recruit, and node advance all live in
``game/`` — this view only renders champion cards and routes the player's choice
through ``shop.generate_supply_offer`` / ``shop.take_supply_champion`` /
``economy.resolve_nonfight_node`` (V.83). It computes no game logic. Reuses the
same non-fight-node seam as the augment view (T.42a).

Flow: recruit one of five offered champions for free (or skip). On recruit/skip
the node resolves (mark-cleared + advance) and the producer autosaves (V.65)
before routing back to the Trail.
"""

from __future__ import annotations

from typing import Callable

import flet as ft

from src.game.content import CHAMPION_DEF_BY_ID
from src.game.economy import MAX_COPIES, resolve_nonfight_node
from src.game.models import Node, Run
from src.game.shop import generate_supply_offer, take_supply_champion
from src.ui.components.iconography import affinity_marker
from src.ui.theme import (
    ACCENT,
    BG,
    CARD_RADIUS,
    FONT_SIZE_BODY,
    FONT_SIZE_CAPTION,
    FONT_SIZE_DISPLAY,
    SPACING_LG,
    SPACING_MD,
    SPACING_SM,
    SPACING_XS,
    SPACING_XL,
    SURFACE,
    SURFACE_ELEVATED,
    TEXT_MUTED,
    TEXT_PRIMARY,
)


def build_supply_view(
    page: ft.Page,
    run: Run,
    node: Node,
    *,
    on_done: Callable[[], None],
) -> ft.View:
    """Build the Supply-node view for ``node`` (T.42b, V.83).

    ``on_done()`` is the producer's router — called after the node resolves
    (recruit or skip), routing back to the Trail.
    """
    offer_ids = generate_supply_offer(run.seed, node.index, run.tempest_rank)
    acted = {"done": False}   # re-entrancy guard: resolve the node exactly once

    def _resolve_and_leave() -> None:
        if acted["done"]:     # a second Recruit/Skip click must not advance twice
            return
        acted["done"] = True
        from src.game.save import default_save_dir, save_run

        resolve_nonfight_node(run)
        save_run(run, default_save_dir() / f"{run.run_id}.json")
        on_done()

    def _recruit(cid: str) -> None:
        if acted["done"]:     # guard before recruit, so a double-click can't recruit twice
            return
        take_supply_champion(run, cid)   # game-side guards unknown/tier-10/maxed
        _resolve_and_leave()

    def _skip(_e: ft.ControlEvent) -> None:
        _resolve_and_leave()

    def _card(cid: str) -> ft.Control:
        cdef = CHAMPION_DEF_BY_ID.get(cid)
        if cdef is None:
            return ft.Container(width=180)
        owned = run.champion_copies.get(cid, 0)
        maxed = owned >= MAX_COPIES
        return ft.Container(
            ft.Column(
                [
                    ft.Row(
                        [
                            affinity_marker(cdef.affinity, size=16),
                            ft.Text(cdef.name, size=FONT_SIZE_BODY, color=TEXT_PRIMARY,
                                    expand=True, no_wrap=True),
                        ],
                        spacing=SPACING_XS,
                    ),
                    ft.Row(
                        [
                            ft.Text(f"T{cdef.tier}", size=FONT_SIZE_CAPTION, color=TEXT_MUTED),
                            *([ft.Text(f"●{owned}", size=FONT_SIZE_CAPTION, color=ACCENT,
                                       tooltip="copies owned (3 combine → next level)")]
                              if owned else []),
                            ft.Container(expand=True),
                        ],
                        spacing=SPACING_XS,
                    ),
                    ft.Container(height=SPACING_XS),
                    ft.FilledButton(
                        "Maxed" if maxed else "Recruit (free)",
                        width=164,
                        on_click=lambda _e, c=cid: _recruit(c),
                        disabled=maxed,
                        style=ft.ButtonStyle(bgcolor=ACCENT),
                    ),
                ],
                spacing=SPACING_XS,
                tight=True,
            ),
            bgcolor=SURFACE_ELEVATED, border_radius=CARD_RADIUS,
            padding=SPACING_MD, width=190,
        )

    body = ft.Column(
        [
            ft.Text("Supply", size=FONT_SIZE_DISPLAY, weight=ft.FontWeight.BOLD,
                    color=ACCENT),
            ft.Text("Recruit one champion — free.", size=FONT_SIZE_BODY, color=TEXT_MUTED),
            ft.Container(height=SPACING_MD),
            ft.Row([_card(c) for c in offer_ids], spacing=SPACING_MD,
                   alignment=ft.MainAxisAlignment.CENTER, wrap=True),
            ft.Container(height=SPACING_LG),
            ft.TextButton("Skip", on_click=_skip),
        ],
        spacing=SPACING_SM,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        tight=True,
    )
    card = ft.Container(body, bgcolor=SURFACE, border_radius=CARD_RADIUS,
                        padding=SPACING_XL)
    root = ft.Container(bgcolor=BG, expand=True, alignment=ft.Alignment.CENTER,
                        padding=SPACING_XL, content=card)
    return ft.View(route="/supply", controls=[root], padding=0)
