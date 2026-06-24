"""Route-map Canvas viz (T.11) — the run's 50-node trail as a horizontal node-line.

Two layers, mirroring `ui/combat_playback.py`'s split:

- **Pure data** — :func:`route_node_specs` turns a ``Run`` (+ a weather lookup)
  into a list of :class:`RouteNodeSpec` (index/city/weather/state/boss/coords/
  colour). Flet-free + testable; the test asserts this structure, not pixels.
- **Canvas builder** — :func:`build_route_map` draws those specs with
  ``flet.canvas`` (`cv.Line` connections behind, `cv.Circle` nodes on top) and
  lays transparent overlay buttons over each node for hit-testing (per the
  CLAUDE.md canvas convention — no gesture math).

This is a graded visualization (kept, no shortcut). It computes **no game state**
(V.63): node state/weather come from the ``Run`` + the caller's weather lookup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import flet as ft
import flet.canvas as cv

from src.game.models import Node, NodeState, NodeType, Run, WeatherState
from src.ui.theme import (
    ACCENT,
    AFFINITY_COLORS,
    DANGER,
    SUCCESS,
    SURFACE,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

# Layout geometry (px). One node per column along a single horizontal lane,
# wrapping isn't needed — the lane scrolls horizontally.
NODE_SPACING = 76
NODE_RADIUS = 14
LANE_Y = 60
MARGIN_X = 40
CANVAS_HEIGHT = 150

# State tints — cleared (done), current (here), upcoming (ahead).
_STATE_COLORS: dict[NodeState, str] = {
    NodeState.CLEARED: SUCCESS,
    NodeState.CURRENT: ACCENT,
    NodeState.UPCOMING: TEXT_MUTED,
}

_BOSS_TYPES = frozenset({NodeType.BOSS_FIGHT})


@dataclass(frozen=True, slots=True)
class RouteNodeSpec:
    """One node's render data — pure, asserted by tests (no Flet here).

    ``weather`` is ``None`` when the live value is **not yet known** (cache
    UNKNOWN) — the node renders a ``"?"`` placeholder, never a concrete weather it
    hasn't fetched. A non-``None`` value is a *known* state (live or substitute).
    """

    index: int
    city: str
    weather: WeatherState | None
    node_type: NodeType
    state: NodeState
    is_boss: bool
    is_selected: bool
    x: float
    y: float
    color: str  # state tint

    @property
    def weather_known(self) -> bool:
        return self.weather is not None


def route_node_specs(
    run: Run,
    weather_for: Callable[[Node], WeatherState | None],
    selected_index: int | None = None,
) -> list[RouteNodeSpec]:
    """Build the ordered render specs for every node in ``run.route`` (T.11).

    ``weather_for(node)`` resolves the *displayed* weather — a live/substitute
    `WeatherState`, or ``None`` when the cache is still UNKNOWN (rendered ``"?"``,
    not the city default). The viz never fetches. ``selected_index`` marks the
    focused node (defaults to the current node). Pure + deterministic.
    """
    sel = selected_index if selected_index is not None else run.current_node_index
    specs: list[RouteNodeSpec] = []
    for col, node in enumerate(sorted(run.route, key=lambda n: n.index)):
        specs.append(
            RouteNodeSpec(
                index=node.index,
                city=node.city,
                weather=weather_for(node),
                node_type=node.node_type,
                state=node.state,
                is_boss=node.node_type in _BOSS_TYPES,
                is_selected=node.index == sel,
                x=MARGIN_X + col * NODE_SPACING,
                y=LANE_Y,
                color=_STATE_COLORS.get(node.state, TEXT_MUTED),
            )
        )
    return specs


def _circle(x: float, y: float, r: float, color: str, *, fill: bool) -> cv.Circle:
    paint = ft.Paint(
        color=color,
        style=ft.PaintingStyle.FILL if fill else ft.PaintingStyle.STROKE,
        stroke_width=3,
    )
    return cv.Circle(x, y, r, paint)


def build_route_map(
    run: Run,
    weather_for: Callable[[Node], WeatherState],
    on_select: Callable[[int], None],
    selected_index: int | None = None,
) -> ft.Control:
    """Render the route as a scrollable Canvas node-line with hit-test overlays.

    A click on a node calls ``on_select(node_index)``. Connections draw behind
    the nodes; the focused node gets a highlight ring; boss nodes a danger ring.
    """
    specs = route_node_specs(run, weather_for, selected_index)
    width = MARGIN_X * 2 + max(len(specs) - 1, 0) * NODE_SPACING + NODE_RADIUS

    shapes: list[cv.Shape] = []

    # Connection lane behind the nodes.
    if len(specs) >= 2:
        lane_paint = ft.Paint(color=SURFACE, stroke_width=4)
        shapes.append(cv.Line(specs[0].x, LANE_Y, specs[-1].x, LANE_Y, lane_paint))

    # Nodes on top.
    for spec in specs:
        shapes.append(_circle(spec.x, spec.y, NODE_RADIUS, spec.color, fill=True))
        if spec.is_boss:
            shapes.append(_circle(spec.x, spec.y, NODE_RADIUS + 4, DANGER, fill=False))
        if spec.is_selected:
            shapes.append(
                _circle(spec.x, spec.y, NODE_RADIUS + 7, TEXT_PRIMARY, fill=False)
            )
        # Node index + weather label.
        shapes.append(
            cv.Text(
                spec.x,
                spec.y - 6,
                str(spec.index),
                ft.TextStyle(size=11, weight=ft.FontWeight.BOLD, color="#1C1C1E"),
                alignment=ft.Alignment.CENTER,
            )
        )
        if spec.weather_known:
            wx_label = spec.weather.value[:4].capitalize()
            wx_color = AFFINITY_COLORS[spec.weather]
        else:
            wx_label = "?"  # UNKNOWN — not yet fetched, never the city default
            wx_color = TEXT_MUTED
        shapes.append(
            cv.Text(
                spec.x,
                spec.y + NODE_RADIUS + 6,
                wx_label,
                ft.TextStyle(size=10, color=wx_color),
                alignment=ft.Alignment.TOP_CENTER,
            )
        )

    canvas = cv.Canvas(shapes, width=width, height=CANVAS_HEIGHT)

    # Transparent hit-test overlays (one button per node — no gesture math).
    overlays: list[ft.Control] = [canvas]
    for spec in specs:
        size = (NODE_RADIUS + 8) * 2
        overlays.append(
            ft.Container(
                left=spec.x - (NODE_RADIUS + 8),
                top=spec.y - (NODE_RADIUS + 8),
                width=size,
                height=size,
                tooltip=f"Node {spec.index}: {spec.city} · "
                f"{spec.node_type.value} · "
                f"{spec.weather.value if spec.weather_known else 'weather pending'}",
                on_click=lambda _e, i=spec.index: on_select(i),
            )
        )

    return ft.Row(
        [ft.Stack(overlays, width=width, height=CANVAS_HEIGHT)],
        scroll=ft.ScrollMode.AUTO,
    )
