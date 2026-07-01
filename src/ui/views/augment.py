"""Augment node view (T.42a, route `/augment`) — the 1-of-3 augment-pick screen.

Pure presentation (V.63/V.1): the offer, reroll bookkeeping, pick-apply, and
node advance all live in ``game/`` — this view only renders cards and routes the
player's choice through ``augments.generate_augment_offer`` /
``augments.reroll_augment_offer`` / ``augments.apply_augment`` /
``economy.resolve_nonfight_node`` (V.83). It computes no game logic.

Flow: pick one of three offered augments (or reroll — 1 free + banked/awarded,
V.84 — or skip). On pick/skip the node resolves (mark-cleared + advance) and the
producer autosaves (V.65) before routing back to the Trail.
"""

from __future__ import annotations

from typing import Callable

import flet as ft

from src.game.augments import (
    Augment,
    AugmentQuality,
    apply_augment,
    generate_augment_offer,
    reroll_augment_offer,
    rerolls_available,
)
from src.game.economy import resolve_nonfight_node
from src.game.models import Node, Run
from src.game.route import stage_of
from src.ui.theme import (
    ACCENT,
    BG,
    CARD_RADIUS,
    DOT_DAMAGE,
    FONT_SIZE_BODY,
    FONT_SIZE_CAPTION,
    FONT_SIZE_DISPLAY,
    FONT_SIZE_H2,
    SPACING_LG,
    SPACING_MD,
    SPACING_SM,
    SPACING_XL,
    SURFACE,
    SURFACE_ELEVATED,
    TEXT_MUTED,
    TEXT_PRIMARY,
    WARNING,
)

# Quality → accent color (T.42a). No shared quality palette exists yet; kept local
# until a second surface needs it (then lift to theme/iconography).
_QUALITY_COLOR: dict[AugmentQuality, str] = {
    AugmentQuality.COMMON: TEXT_MUTED,
    AugmentQuality.RARE: ACCENT,
    AugmentQuality.EPIC: DOT_DAMAGE,     # violet
    AugmentQuality.PRISMATIC: WARNING,   # gold
}


def build_augment_view(
    page: ft.Page,
    run: Run,
    node: Node,
    *,
    on_done: Callable[[], None],
) -> ft.View:
    """Build the Augment-node view for ``node`` (T.42a, V.83/V.84).

    ``on_done()`` is the producer's router — called after the node resolves
    (pick or skip), routing back to the Trail.
    """
    node_index = node.index
    stage_index = stage_of(node_index).index

    # Mutable playback state held in a list so the nested handlers can rebind it.
    state = {
        "offer": generate_augment_offer(
            run.seed, node_index, stage_index, exclude=tuple(run.active_augments)
        ),
        "reroll_count": 0,
    }

    offer_slot = ft.Container()
    controls_slot = ft.Container()
    acted = {"done": False}   # re-entrancy guard: resolve the node exactly once

    def _resolve_and_leave() -> None:
        """Advance past the node (V.83) + autosave (V.65), then route on."""
        if acted["done"]:     # a second Choose/Skip click must not advance twice
            return
        acted["done"] = True
        from src.game.save import default_save_dir, save_run

        resolve_nonfight_node(run)
        save_run(run, default_save_dir() / f"{run.run_id}.json")
        on_done()

    def _pick(aug: Augment) -> None:
        if acted["done"]:     # guard before apply, so a double-click can't apply twice
            return
        apply_augment(run, aug)
        _resolve_and_leave()

    def _skip(_e: ft.ControlEvent) -> None:
        _resolve_and_leave()

    def _reroll(_e: ft.ControlEvent) -> None:
        result = reroll_augment_offer(run, node_index, stage_index, state["reroll_count"])
        if result is None:                 # exhausted — button should already be disabled
            return
        offer, new_count, _left = result
        state["offer"] = offer
        state["reroll_count"] = new_count
        _render()
        page.update()

    def _card(aug: Augment) -> ft.Control:
        color = _QUALITY_COLOR.get(aug.quality, TEXT_PRIMARY)
        return ft.Container(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(
                                ft.Text(aug.quality.value.upper(), size=FONT_SIZE_CAPTION,
                                        color=BG, weight=ft.FontWeight.BOLD),
                                bgcolor=color, border_radius=CARD_RADIUS,
                                padding=ft.Padding(SPACING_SM, 2, SPACING_SM, 2),
                            ),
                            ft.Text(aug.scope.value.upper(), size=FONT_SIZE_CAPTION,
                                    color=TEXT_MUTED),
                        ],
                        spacing=SPACING_SM,
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(aug.name, size=FONT_SIZE_H2, color=color,
                            weight=ft.FontWeight.BOLD),
                    ft.Text(aug.blurb, size=FONT_SIZE_BODY, color=TEXT_PRIMARY),
                    ft.Container(height=SPACING_SM),
                    ft.FilledButton("Choose", on_click=lambda _e, a=aug: _pick(a),
                                    style=ft.ButtonStyle(bgcolor=ACCENT)),
                ],
                spacing=SPACING_SM,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
            ),
            bgcolor=SURFACE_ELEVATED, border_radius=CARD_RADIUS,
            padding=SPACING_LG, width=240,
            border=ft.Border.all(1, color),
        )

    def _render() -> None:
        offer_slot.content = ft.Row(
            [_card(a) for a in state["offer"]],
            spacing=SPACING_MD,
            alignment=ft.MainAxisAlignment.CENTER,
            wrap=True,
        )
        left = rerolls_available(run, state["reroll_count"])
        controls_slot.content = ft.Row(
            [
                ft.OutlinedButton(
                    f"Reroll ({left} left)" if left else "Reroll (none left)",
                    icon=ft.Icons.CASINO,
                    on_click=_reroll,
                    disabled=left <= 0,
                ),
                ft.TextButton("Skip", on_click=_skip),
            ],
            spacing=SPACING_MD,
            alignment=ft.MainAxisAlignment.CENTER,
        )

    _render()

    body = ft.Column(
        [
            ft.Text("Augment", size=FONT_SIZE_DISPLAY, weight=ft.FontWeight.BOLD,
                    color=ACCENT),
            ft.Text("Choose one run-long boon.", size=FONT_SIZE_BODY, color=TEXT_MUTED),
            ft.Container(height=SPACING_MD),
            offer_slot,
            ft.Container(height=SPACING_LG),
            controls_slot,
        ],
        spacing=SPACING_SM,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        tight=True,
    )
    card = ft.Container(
        body, bgcolor=SURFACE, border_radius=CARD_RADIUS, padding=SPACING_XL,
    )
    root = ft.Container(bgcolor=BG, expand=True, alignment=ft.Alignment.CENTER,
                        padding=SPACING_XL, content=card)
    return ft.View(route="/augment", controls=[root], padding=0)
