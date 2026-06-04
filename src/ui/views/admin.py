"""Admin / playtest Flet view (Layer 2 of the playtesting plan).

A single `/admin` route with four tabs (Roster, Encounter, Fight, Run) that
reuse the Layer-1 CLI internals from `tools/playtest/`. Each tab redirects
the CLI's stdout into a Flet `Text` control.

Gated behind the `TEMPEST_ADMIN=1` env var (see `src/main.py`). No
production styling — intentionally scuffed; aimed at dev/QA use only.
"""
from __future__ import annotations

import contextlib
import io
import threading
from typing import Callable

import flet as ft

from src.game.models import WeatherState
from tools.playtest.inspect import main as inspect_main
from tools.playtest.inspect_node import main as inspect_node_main
from tools.playtest.sim_fight import main as sim_fight_main
from tools.playtest.sim_node import main as sim_node_main
from tools.playtest.sim_run import main as sim_run_main


_MONO = "monospace"
_WEATHERS = [w.value for w in WeatherState]


def _capture(fn: Callable[[list[str]], int], argv: list[str]) -> str:
    """Run a Layer-1 CLI main() and return its stdout as one string."""
    buf = io.StringIO()
    err = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            fn(argv)
    except SystemExit:
        # argparse calls sys.exit on bad args; capture and continue
        pass
    except Exception as exc:  # surface the failure rather than killing the view
        return f"{buf.getvalue()}\n{err.getvalue()}\n[ERROR] {type(exc).__name__}: {exc}"
    return buf.getvalue() + err.getvalue()


def _output_box(initial: str = "") -> ft.Text:
    return ft.Text(initial, selectable=True, font_family=_MONO, size=11)


def _scroll(child: ft.Control) -> ft.Container:
    return ft.Container(
        content=ft.Column([child], scroll=ft.ScrollMode.AUTO, expand=True),
        expand=True,
        padding=8,
        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.WHITE),
        border_radius=4,
    )


# ---------------------------------------------------------------------------
# Tab 1 — Roster browser  (wraps inspect.py)
# ---------------------------------------------------------------------------


def _roster_tab(page: ft.Page) -> tuple[str, ft.Control]:
    kind = ft.Dropdown(
        label="Kind",
        value="champion",
        options=[ft.dropdown.Option("champion"), ft.dropdown.Option("enemy")],
        width=140,
    )
    affinity = ft.Dropdown(
        label="Affinity",
        value="",
        options=[ft.dropdown.Option("", "any")] + [ft.dropdown.Option(w) for w in _WEATHERS],
        width=140,
    )
    tier = ft.Dropdown(
        label="Tier",
        value="",
        options=[ft.dropdown.Option("", "any")] + [ft.dropdown.Option(str(t)) for t in range(1, 11)],
        width=120,
    )
    role = ft.TextField(label="Role filter", width=160, value="")
    intent = ft.Dropdown(
        label="Intent",
        value="",
        options=[ft.dropdown.Option("", "any")]
        + [ft.dropdown.Option(i) for i in ("damage", "hybrid", "utility")],
        width=140,
    )
    favor = ft.Dropdown(
        label="Show favor",
        value="",
        options=[ft.dropdown.Option("", "none")] + [ft.dropdown.Option(w) for w in _WEATHERS],
        width=160,
    )

    output = _output_box("Hit Run.")

    def run(_):
        args: list[str] = ["--kind", kind.value]
        if affinity.value:
            args += ["--affinity", affinity.value]
        if tier.value:
            args += ["--tier", tier.value]
        if role.value.strip():
            args += ["--role", role.value.strip()]
        if intent.value:
            args += ["--intent", intent.value]
        if favor.value:
            args += ["--show-favor", favor.value]
        output.value = _capture(inspect_main, args)
        page.update()

    return "Roster", ft.Column(
        [
            ft.Row([kind, affinity, tier, role, intent, favor, ft.FilledButton("Run", on_click=run)]),
            _scroll(output),
        ],
        expand=True,
    )


# ---------------------------------------------------------------------------
# Tab 2 — Encounter probe  (wraps inspect_node.py + sim_node.py)
# ---------------------------------------------------------------------------


def _encounter_tab(page: ft.Page) -> tuple[str, ft.Control]:
    stage = ft.Dropdown(
        label="Stage",
        value="1",
        options=[ft.dropdown.Option(str(s)) for s in range(1, 7)],
        width=100,
    )
    node = ft.TextField(label="Node index (1-50)", value="1", width=160)
    seed = ft.TextField(label="Run seed", value="42", width=140)
    weather = ft.Dropdown(
        label="Weather (override)",
        value="",
        options=[ft.dropdown.Option("", "city default")] + [ft.dropdown.Option(w) for w in _WEATHERS],
        width=180,
    )
    team = ft.TextField(label="Team ids (optional)", value="", width=420)

    output = _output_box("Pick a node, then Inspect or Resolve.")

    def _common_args() -> list[str]:
        args = ["--stage", stage.value, "--node-index", node.value, "--run-seed", seed.value]
        if weather.value:
            args += ["--weather", weather.value]
        return args

    def inspect(_):
        output.value = _capture(inspect_node_main, _common_args())
        page.update()

    def resolve(_):
        args = _common_args()
        if team.value.strip():
            args += ["--team", team.value.strip()]
        # sim_node prints a lot; run on a worker so UI stays responsive
        def worker():
            text = _capture(sim_node_main, args)
            output.value = text
            page.update()
        output.value = "Resolving…"
        page.update()
        threading.Thread(target=worker, daemon=True).start()

    return "Encounter", ft.Column(
        [
            ft.Row([stage, node, seed, weather]),
            ft.Row([team, ft.FilledButton("Inspect", on_click=inspect),
                    ft.FilledButton("Resolve", on_click=resolve)]),
            _scroll(output),
        ],
        expand=True,
    )


# ---------------------------------------------------------------------------
# Tab 3 — Fight runner  (wraps sim_fight.py)
# ---------------------------------------------------------------------------


def _fight_tab(page: ft.Page) -> tuple[str, ft.Control]:
    team = ft.TextField(
        label="Team ids (comma-separated)",
        value="champ_springfrog,champ_snowpelt_cub,champ_sparkfly",
        width=560,
    )
    enemies = ft.TextField(
        label="Enemy ids (comma-separated)",
        value="enemy_conscript,enemy_picket,enemy_levyman",
        width=560,
    )
    weather = ft.Dropdown(
        label="Weather",
        value="clear",
        options=[ft.dropdown.Option(w) for w in _WEATHERS],
        width=140,
    )
    seed = ft.TextField(label="Seed", value="42", width=100)

    output = _output_box("Hit Resolve.")

    def resolve(_):
        args = [
            "--team", team.value.strip(),
            "--enemies", enemies.value.strip(),
            "--weather", weather.value,
            "--seed", seed.value or "42",
        ]
        def worker():
            output.value = _capture(sim_fight_main, args)
            page.update()
        output.value = "Resolving…"
        page.update()
        threading.Thread(target=worker, daemon=True).start()

    return "Fight", ft.Column(
        [
            team,
            enemies,
            ft.Row([weather, seed, ft.FilledButton("Resolve", on_click=resolve)]),
            _scroll(output),
        ],
        expand=True,
    )


# ---------------------------------------------------------------------------
# Tab 4 — Full run  (wraps sim_run.py)
# ---------------------------------------------------------------------------


def _run_tab(page: ft.Page) -> tuple[str, ft.Control]:
    seed = ft.TextField(label="Run seed", value="42", width=140)
    team = ft.TextField(label="Team ids (optional)", value="", width=520)
    strategy = ft.Dropdown(
        label="Weather strategy",
        value="stage-affinity",
        options=[
            ft.dropdown.Option("stage-affinity"),
            ft.dropdown.Option("city-default"),
            *[ft.dropdown.Option(f"fixed:{w}") for w in _WEATHERS],
        ],
        width=200,
    )
    dc = ft.TextField(label="DC", value="1.0", width=100)

    output = _output_box("Hit Walk to simulate the full 50-node route.")

    def walk(_):
        args = ["--run-seed", seed.value or "0", "--weather-strategy", strategy.value, "--dc", dc.value or "1.0"]
        if team.value.strip():
            args += ["--team", team.value.strip()]
        def worker():
            output.value = _capture(sim_run_main, args)
            page.update()
        output.value = "Walking 50 nodes…"
        page.update()
        threading.Thread(target=worker, daemon=True).start()

    return "Run", ft.Column(
        [
            ft.Row([seed, strategy, dc, ft.FilledButton("Walk", on_click=walk)]),
            team,
            _scroll(output),
        ],
        expand=True,
    )


# ---------------------------------------------------------------------------
# View constructor — registered against the /admin route in main.py
# ---------------------------------------------------------------------------


def build_admin_content(page: ft.Page) -> ft.Control:
    """Return the admin tabs UI as a single control (no View wrapper)."""
    pairs = [
        _roster_tab(page),
        _encounter_tab(page),
        _fight_tab(page),
        _run_tab(page),
    ]
    tab_bar = ft.TabBar(tabs=[ft.Tab(label=label) for label, _ in pairs])
    tab_body = ft.TabBarView(controls=[content for _, content in pairs], expand=True)
    tabs = ft.Tabs(
        length=len(pairs),
        selected_index=0,
        expand=True,
        content=ft.Column([tab_bar, tab_body], expand=True),
    )
    return ft.Container(content=tabs, expand=True, padding=8)


def admin_view(page: ft.Page) -> ft.View:
    return ft.View(
        route="/admin",
        appbar=ft.AppBar(title=ft.Text("Tempest — Playtest Admin")),
        controls=[build_admin_content(page)],
    )
