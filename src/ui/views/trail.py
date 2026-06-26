"""Trail view (T.11) — the run's route map + node focus + team summary.

Pure presentation (V.1/V.63): the view reads `Run` state and calls into `game/`
(`encounter.node_encounter`, `weather_effects`, `route.city_id_for_node`) — it
recomputes no economy/encounter/weather number itself. Combat resolution is **not**
done here; Play Next hands the node to the host (Prep → combat).

**Live weather (V.66/V.4):** the view owns a T.7 `WeatherCache` + `WeatherRefresher`,
started on open and **stopped on pop / Save & Exit** (the returned `ft.View` carries
the stop handler on `view.data`, which `main._pop` fires — same convention the combat
view uses for its autoplay thread). All HTTP runs on the refresher's worker thread;
the view never blocks on a fetch. Display is **tri-state (V.66):** `UNKNOWN`
entries render as `?` "pending" (never a fake default), `SUBSTITUTE` shows the
city default flagged `fallback`, `LIVE` shows the fetched weather.
"""

from __future__ import annotations

import threading
from typing import Callable

import flet as ft

from src.api.cache import CacheState, WeatherCache, fetch_and_cache
from src.api.refresher import WeatherRefresher
from src.api.weather import WeatherClient
from src.app_config import resolve_api_key
from src.game.encounter import node_encounter
from src.game.models import Node, NodeState, NodeType, NodeWeatherState, Run, WeatherState
from src.game.route import CITIES, ROUTE_CITY_IDS, city_id_for_node
from src.game.weather_effects import RingRelation, ring_relation
from src.ui.components.iconography import affinity_marker
from src.ui.components.weather_badge import weather_badge
from src.viz.route_map import build_route_map
from src.ui.theme import (
    ACCENT,
    AFFINITY_COLORS,
    BG,
    CARD_RADIUS,
    DANGER,
    FONT_SIZE_BODY,
    FONT_SIZE_CAPTION,
    FONT_SIZE_DISPLAY,
    FONT_SIZE_H2,
    FONT_SIZE_H3,
    SPACING_LG,
    SPACING_MD,
    SPACING_SM,
    SPACING_XL,
    SPACING_XS,
    SUCCESS,
    SURFACE,
    SURFACE_ELEVATED,
    TEXT_MUTED,
    TEXT_PRIMARY,
    WARNING,
)

# Node types that have no fight to preview.
_NO_FIGHT = frozenset({NodeType.AUGMENT, NodeType.SUPPLY})


def build_trail_view(
    page: ft.Page,
    run: Run,
    *,
    on_play_next: Callable[[Node], None],
    on_save_exit: Callable[[], None],
) -> ft.View:
    """Build the Trail view for ``run`` (T.11, route `/trail`).

    ``on_play_next(node)`` advances into the current node's Prep; ``on_save_exit()``
    autosaves + returns to the menu. The view starts a live-weather refresher and
    stops it when popped (V.66).
    """
    state = {"selected": run.current_node_index}

    # --- Live weather (V.66/V.4) ------------------------------------------------
    cache = WeatherCache(list(ROUTE_CITY_IDS))
    refresher: WeatherRefresher | None = None
    # Key resolves env → Settings-menu config file → None (app_config). No key ⇒
    # the refresher never starts and every node stays UNKNOWN → "?" (V.66).
    api_key = resolve_api_key()
    client = WeatherClient(api_key=api_key) if api_key else None

    def _sync_cache_to_run() -> None:
        """Write-through fetched cache weather into the persisted ``Run`` (T.39, V.73).

        The ``Run`` `Node` is the source of truth for display + game logic; the cache
        is the fetch-scheduling/freshness layer. For every node, copy a non-UNKNOWN
        cache entry onto the node via the pure game-side mutator (a no-op on a locked
        node — the refresher keeps refreshing the city but the value stays frozen,
        V.10/V.73). Cheap (≤50 reads), run before each render."""
        for node in run.route:
            entry = cache.get(city_id_for_node(node.index))
            if entry.state is CacheState.UNKNOWN or entry.result is None:
                continue
            run.set_node_live_weather(
                node.index, entry.result.state,
                is_substitute=entry.state is CacheState.SUBSTITUTE,
            )

    def _weather_status(node: Node) -> tuple[NodeWeatherState, WeatherState | None]:
        """Persisted weather state + displayed weather for ``node`` (T.39, V.73).

        Reads the **persisted ``Run`` ``Node``** (not the ephemeral cache) so weather
        survives Trail re-open + Save&Exit. UNKNOWN ⇒ ``(UNKNOWN, None)`` — the live
        value is **not yet known**, so the view shows ``"?"`` rather than the city
        default (the default backs game logic only, never shown as live data).
        LIVE/SUBSTITUTE ⇒ the node's weather + state (SUBSTITUTE flags a fallback;
        a locked node reads its frozen LIVE/SUBSTITUTE value)."""
        if node.weather_state is NodeWeatherState.UNKNOWN:
            return NodeWeatherState.UNKNOWN, None
        return node.weather_state, node.weather

    def _map_weather(node: Node) -> WeatherState | None:
        """Map-label weather: the known value, else ``None`` (renders ``"?"``)."""
        return _weather_status(node)[1]

    def _node_by_index(idx: int) -> Node:
        return next(n for n in run.route if n.index == idx)

    # --- Holders (re-rendered on selection + weather tick) ----------------------
    map_holder = ft.Container()
    focus_holder = ft.Container(
        bgcolor=SURFACE, border_radius=CARD_RADIUS, padding=SPACING_LG, expand=True,
    )
    team_holder = ft.Container(
        bgcolor=SURFACE, border_radius=CARD_RADIUS, padding=SPACING_LG, width=320,
    )

    def _on_select(idx: int) -> None:
        state["selected"] = idx
        _render()

    def _render() -> None:
        _sync_cache_to_run()  # persist latest fetched weather onto Run before paint (V.73)
        map_holder.content = build_route_map(
            run, _map_weather, _on_select, selected_index=state["selected"]
        )
        focus_holder.content = _build_focus(_node_by_index(state["selected"]))
        team_holder.content = _build_team_summary()
        page.update()

    async def _render_async() -> None:
        _render()

    def _schedule_render() -> None:
        """Repaint safely from any thread. The weather refresher fires from a
        `threading.Timer` worker thread; a bare `page.update()` there is unreliable
        on desktop, so marshal onto the Flet event loop via `page.run_task`
        (`asyncio.run_coroutine_threadsafe` under the hood) — the same pattern the
        combat view uses for autoplay. Falls back to a direct render for a headless
        test page that has no `run_task`."""
        run_task = getattr(page, "run_task", None)
        if callable(run_task):
            run_task(_render_async)
        else:
            _render()

    # --- Focus panel ------------------------------------------------------------
    def _favor_line(node: Node) -> ft.Control:
        """Team-wide Weather Favor for this node's *known* weather (read from game/).

        Pending (``—``) while the cache is UNKNOWN — favor of an unfetched node is
        unknowable, so we don't compute it off the default."""
        _state, wx = _weather_status(node)
        if wx is None:
            return ft.Row(
                [ft.Text("Weather favor:", size=FONT_SIZE_CAPTION, color=TEXT_MUTED),
                 ft.Text("— pending", size=FONT_SIZE_CAPTION, color=TEXT_MUTED)],
                spacing=SPACING_SM,
            )
        favored = neutral = unfavored = 0
        for champ in run.roster:
            rel = ring_relation(champ.affinity, wx)
            if rel in (RingRelation.SELF, RingRelation.PRIMARY_PREDATOR,
                       RingRelation.SECONDARY_PREDATOR):
                favored += 1
            elif rel in (RingRelation.PRIMARY_PREY, RingRelation.SECONDARY_PREY):
                unfavored += 1
            else:
                neutral += 1
        return ft.Row(
            [
                ft.Text("Weather favor:", size=FONT_SIZE_CAPTION, color=TEXT_MUTED),
                ft.Text(f"{favored}↑", size=FONT_SIZE_CAPTION, color=SUCCESS),
                ft.Text(f"{neutral}·", size=FONT_SIZE_CAPTION, color=TEXT_MUTED),
                ft.Text(f"{unfavored}↓", size=FONT_SIZE_CAPTION, color=DANGER),
            ],
            spacing=SPACING_SM,
        )

    def _enemy_preview(node: Node) -> ft.Control:
        if node.node_type in _NO_FIGHT:
            return ft.Text("No fight here.", size=FONT_SIZE_CAPTION, color=TEXT_MUTED)
        # Deterministic preview off the node's default weather (V.2) — stable as
        # live weather streams in; the actual fight re-derives identically.
        enc = node_encounter(run.seed, node)
        rows: list[ft.Control] = []
        for e in enc.enemies[:8]:
            rows.append(
                ft.Row(
                    [
                        affinity_marker(e.affinity, size=13),
                        ft.Text(f"{e.name}", size=FONT_SIZE_CAPTION, color=TEXT_PRIMARY,
                                expand=True, no_wrap=True),
                        ft.Text(f"T{e.tier} L{e.level}", size=FONT_SIZE_CAPTION,
                                color=TEXT_MUTED),
                        ft.Text(f"{e.max_hp}hp", size=FONT_SIZE_CAPTION, color=TEXT_MUTED),
                    ],
                    spacing=SPACING_SM,
                )
            )
        if len(enc.enemies) > 8:
            rows.append(ft.Text(f"+{len(enc.enemies) - 8} more", size=FONT_SIZE_CAPTION,
                                color=TEXT_MUTED))
        header = f"Enemies ({len(enc.enemies)})"
        if enc.map_effect_id:
            header += f" · map: {enc.map_effect_id}"
        return ft.Column(
            [ft.Text(header, size=FONT_SIZE_H3, color=TEXT_PRIMARY,
                     weight=ft.FontWeight.BOLD)] + rows,
            spacing=SPACING_XS,
        )

    def _weather_chip(node: Node) -> ft.Control:
        """Tri-state weather display: UNKNOWN → "?" pending, SUBSTITUTE → default
        weather flagged as fallback, LIVE → the live weather badge."""
        cstate, wx = _weather_status(node)
        if wx is None:  # UNKNOWN — not fetched yet
            return ft.Container(
                ft.Row([ft.Icon(ft.Icons.HELP_OUTLINE, size=14, color=TEXT_MUTED),
                        ft.Text("weather pending", size=FONT_SIZE_CAPTION,
                                color=TEXT_MUTED)], spacing=SPACING_XS, tight=True),
                bgcolor=SURFACE_ELEVATED, border_radius=CARD_RADIUS,
                padding=ft.Padding(left=8, right=8, top=4, bottom=4),
            )
        row = [weather_badge(weather=wx, size="sm")]
        if cstate is NodeWeatherState.SUBSTITUTE:  # fetch failed → city default, flagged
            row.append(ft.Text("fallback", size=FONT_SIZE_CAPTION, color=WARNING))
        return ft.Row(row, spacing=SPACING_XS, tight=True)

    def _build_focus(node: Node) -> ft.Control:
        is_current = node.index == run.current_node_index
        type_color = DANGER if node.node_type == NodeType.BOSS_FIGHT else ACCENT
        title = ft.Row(
            [
                ft.Text(f"Node {node.index} · {node.city}", size=FONT_SIZE_H2,
                        color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                ft.Container(
                    ft.Text(node.node_type.value.replace("_", " "),
                            size=FONT_SIZE_CAPTION, color=TEXT_PRIMARY),
                    bgcolor=type_color, border_radius=CARD_RADIUS,
                    padding=ft.Padding(left=8, right=8, top=2, bottom=2),
                ),
            ],
            spacing=SPACING_MD,
        )
        controls: list[ft.Control] = [
            title,
            ft.Row([_weather_chip(node), ft.Container(width=SPACING_SM),
                    ft.Text(_state_label(node.state), size=FONT_SIZE_CAPTION,
                            color=TEXT_MUTED)], spacing=SPACING_MD),
            _favor_line(node),
            ft.Divider(height=1, color=SURFACE_ELEVATED),
            _enemy_preview(node),
        ]
        if is_current and node.state == NodeState.CURRENT:
            controls.append(ft.Container(height=SPACING_SM))
            controls.append(
                ft.FilledButton(
                    "Play Next Encounter ▶",
                    on_click=lambda _e: _play_next(node),
                    style=ft.ButtonStyle(bgcolor=ACCENT),
                )
            )
        return ft.Column(controls, spacing=SPACING_MD, scroll=ft.ScrollMode.AUTO)

    # --- Team summary -----------------------------------------------------------
    def _build_team_summary() -> ft.Control:
        rows: list[ft.Control] = [
            ft.Text("Your Tempest", size=FONT_SIZE_H2, color=TEXT_PRIMARY,
                    weight=ft.FontWeight.BOLD),
            ft.Row(
                [
                    _stat_chip("Amber", str(run.amber), WARNING),
                    _stat_chip("Rank", str(run.tempest_rank), ACCENT),
                    _stat_chip("Bench", str(len(run.bench)), TEXT_MUTED),
                ],
                spacing=SPACING_SM, wrap=True,
            ),
            ft.Divider(height=1, color=SURFACE_ELEVATED),
        ]
        for champ in run.roster:
            rows.append(
                ft.Row(
                    [
                        ft.Container(width=10, height=10, border_radius=5,
                                     bgcolor=AFFINITY_COLORS[champ.affinity]),
                        ft.Text(champ.name, size=FONT_SIZE_BODY, color=TEXT_PRIMARY,
                                expand=True, no_wrap=True),
                        ft.Text(f"L{champ.level} {champ.role}", size=FONT_SIZE_CAPTION,
                                color=TEXT_MUTED),
                        ft.Text(f"{champ.max_hp}hp", size=FONT_SIZE_CAPTION,
                                color=TEXT_MUTED),
                    ],
                    spacing=SPACING_SM,
                )
            )
        if not run.roster:
            rows.append(ft.Text("(empty)", size=FONT_SIZE_CAPTION, color=TEXT_MUTED))
        return ft.Column(rows, spacing=SPACING_SM, scroll=ft.ScrollMode.AUTO)

    # --- Top bar + assembly -----------------------------------------------------
    top_bar = ft.Row(
        [
            ft.Text("The Trail", size=FONT_SIZE_DISPLAY, weight=ft.FontWeight.BOLD,
                    color=TEXT_PRIMARY),
            ft.Container(expand=True),
            ft.OutlinedButton("Save & Exit", on_click=lambda _e: _save_exit()),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    body_controls: list[ft.Control] = [top_bar]
    if client is None:
        # No key resolved → the refresher never starts, so weather stays "?".
        # Tell the player how to fix it instead of leaving a silent placeholder.
        body_controls.append(
            ft.Container(
                ft.Row(
                    [ft.Icon(ft.Icons.CLOUD_OFF, size=16, color=WARNING),
                     ft.Text("No OpenWeather API key — weather stays “?”. Add one in "
                             "Settings (main menu) for live weather.",
                             size=FONT_SIZE_CAPTION, color=TEXT_PRIMARY)],
                    spacing=SPACING_SM,
                ),
                bgcolor=SURFACE_ELEVATED, border_radius=CARD_RADIUS,
                padding=ft.Padding(left=SPACING_MD, right=SPACING_MD,
                                   top=SPACING_SM, bottom=SPACING_SM),
            )
        )
    body_controls.append(
        ft.Container(map_holder, bgcolor=SURFACE, border_radius=CARD_RADIUS,
                     padding=SPACING_MD)
    )
    body_controls.append(
        ft.Row(
            [focus_holder, team_holder],
            spacing=SPACING_LG, vertical_alignment=ft.CrossAxisAlignment.START,
            expand=True,
        )
    )
    body = ft.Column(body_controls, spacing=SPACING_LG, expand=True)

    root = ft.Container(bgcolor=BG, expand=True, padding=SPACING_XL, content=body)
    view = ft.View(route="/trail", controls=[root], padding=0)

    # --- Refresher lifecycle (V.66) ---------------------------------------------
    def _stop_refresher(_e: object = None) -> None:
        if refresher is not None:
            refresher.stop()

    def _save_exit() -> None:
        _stop_refresher()
        on_save_exit()

    def _play_next(node: Node) -> None:
        """Trail→Prep transition. Lock the current node's weather (V.73) so it stops
        refreshing and is frozen for the fight + reward (load-bearing for V.70
        byte-identity), then hand off to the host (which saves — V.65)."""
        run.lock_node_weather(run.current_node_index)
        on_play_next(node)

    # `main._pop` fires `view.data(None)` before popping → stops the worker thread.
    view.data = _stop_refresher

    def _kickstart() -> None:
        """Immediate first fetch so the Trail shows live weather on open instead of
        waiting a full ~60s refresher tick. Worker-thread only (V.4): fetch the
        current node first (the one the player is looking at), then run one seed
        tick for nearby nodes; both repaint via `_render`. The periodic refresher
        fills the rest at ≤3/min (V.11)."""
        assert client is not None
        node = run.current_node()
        if node is not None:
            cid = city_id_for_node(node.index)
            try:
                fetch_and_cache(cache, client, cid, CITIES[cid])
                _schedule_render()
            except Exception:  # noqa: BLE001 — never crash the view on a fetch error
                pass
        if refresher is not None:
            try:
                refresher.tick()  # seeds A/B/C neighbours + repaints via on_tick
            except Exception:  # noqa: BLE001
                pass

    if client is not None:
        refresher = WeatherRefresher(
            cache, client,
            get_current_node_index=lambda: run.current_node_index,
            # Repaint each pulse (~3 nodes/min) — marshaled to the event loop so the
            # update lands while the player sits on the Trail (V.66).
            on_tick=lambda _selected: _schedule_render(),
        )
        refresher.start()
        # Kick the first fetch off the main thread (V.4) — don't block view build.
        threading.Thread(target=_kickstart, name="trail-weather-kickstart",
                         daemon=True).start()

    _render()
    return view


# ---------------------------------------------------------------------------
# Small presentation helpers
# ---------------------------------------------------------------------------

_STATE_LABELS: dict[NodeState, str] = {
    NodeState.CLEARED: "cleared",
    NodeState.CURRENT: "you are here",
    NodeState.UPCOMING: "upcoming",
}


def _state_label(state: NodeState) -> str:
    return _STATE_LABELS.get(state, state.value)


def _stat_chip(label: str, value: str, color: str) -> ft.Control:
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
