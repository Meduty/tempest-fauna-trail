"""Run-summary damage chart (T.13) — a hand-drawn `flet.canvas` bar chart.

Mirrors :mod:`src.viz.route_map`: a **pure data** function
(:func:`run_summary_specs`) the tests assert against (counts / values /
normalization — never pixels) + a **canvas builder** (:func:`build_run_summary`)
that turns specs into ``cv.Rect``/``cv.Line``/``cv.Text`` shapes. Flet 0.85 removed
the core chart widgets (``ft.BarChart``/``LineChart``/``PieChart`` → optional
``flet-charts``), so the run-loop's graded viz is drawn by hand (V.72).

One bar per fought battle (``run.battle_log``), height ∝ team damage dealt,
coloured by outcome (win → success, loss → danger).
"""

from __future__ import annotations

from dataclasses import dataclass

import flet as ft
import flet.canvas as cv

from src.game.models import CombatOutcome, Run
from src.ui.theme import DANGER, SUCCESS, SURFACE, TEXT_MUTED, TEXT_PRIMARY

# Layout geometry (px).
MARGIN_X = 44
MARGIN_TOP = 28          # headroom for value labels
PLOT_H = 180             # bar plot height (a full-height bar = max damage)
BAR_W = 34
BAR_GAP = 16
LABEL_H = 30             # node-label band under the baseline
BASELINE_Y = MARGIN_TOP + PLOT_H
CANVAS_HEIGHT = BASELINE_Y + LABEL_H


@dataclass(frozen=True, slots=True)
class BarSpec:
    """One battle's bar — pure data (no Flet)."""

    index: int          # battle ordinal (0-based, in fight order)
    label: str          # short node label (city tail of BattleResult.node_id)
    damage: int         # sum of team damage dealt that battle
    height_frac: float  # damage / max_damage across the log (0..1)
    won: bool           # outcome == CombatOutcome.WIN


def _node_label(node_id: str) -> str:
    """`n3-Lisbon` → `Lisbon`; falls back to the raw id. Truncated for the axis."""
    tail = node_id.split("-", 1)[1] if "-" in node_id else node_id
    return tail[:8]


def run_summary_specs(run: Run) -> list[BarSpec]:
    """One :class:`BarSpec` per battle in ``run.battle_log`` (fight order).

    ``damage`` = ``sum(result.team_damage_dealt.values())``; ``height_frac`` is
    max-normalized across the log (the biggest bar = ``1.0``; an empty or all-zero
    log ⇒ ``0.0``, no divide-by-zero). Deterministic + Flet-free (V.2/V.72).
    """
    damages = [sum(r.team_damage_dealt.values()) for r in run.battle_log]
    peak = max(damages, default=0)
    specs: list[BarSpec] = []
    for i, result in enumerate(run.battle_log):
        dmg = damages[i]
        specs.append(
            BarSpec(
                index=i,
                label=_node_label(result.node_id),
                damage=dmg,
                height_frac=(dmg / peak) if peak > 0 else 0.0,
                won=result.outcome == CombatOutcome.WIN,
            )
        )
    return specs


def build_run_summary(run: Run) -> ft.Control:
    """Render the damage-per-battle chart as a `flet.canvas` bar chart (V.72).

    Empty log ⇒ a "No battles fought" text (no canvas). Pure presentation over
    :func:`run_summary_specs` — recomputes nothing (V.63).
    """
    specs = run_summary_specs(run)
    if not specs:
        return ft.Text("No battles fought.", size=13, color=TEXT_MUTED)

    width = MARGIN_X * 2 + len(specs) * BAR_W + max(len(specs) - 1, 0) * BAR_GAP
    shapes: list[cv.Shape] = []

    # Baseline.
    shapes.append(
        cv.Line(MARGIN_X - 8, BASELINE_Y, width - MARGIN_X + 8, BASELINE_Y,
                ft.Paint(color=SURFACE, stroke_width=2))
    )

    for spec in specs:
        x = MARGIN_X + spec.index * (BAR_W + BAR_GAP)
        cx = x + BAR_W / 2
        bar_h = max(2.0, spec.height_frac * PLOT_H)  # min nub so zero-dmg still reads
        top = BASELINE_Y - bar_h
        color = SUCCESS if spec.won else DANGER
        shapes.append(
            cv.Rect(x, top, BAR_W, bar_h, border_radius=3,
                    paint=ft.Paint(color=color, style=ft.PaintingStyle.FILL))
        )
        # Damage value above the bar.
        shapes.append(
            cv.Text(cx, top - 16, str(spec.damage),
                    ft.TextStyle(size=11, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                    alignment=ft.Alignment.CENTER)
        )
        # Node label under the baseline.
        shapes.append(
            cv.Text(cx, BASELINE_Y + 6, spec.label,
                    ft.TextStyle(size=10, color=TEXT_MUTED),
                    alignment=ft.Alignment.TOP_CENTER)
        )

    return cv.Canvas(shapes, width=width, height=CANVAS_HEIGHT)
