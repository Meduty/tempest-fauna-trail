"""Dev-harness launcher (T.12a) — build a `CombatSession` and open the combat
view, without the (unbuilt) Menu/Trail/Prep shell.

GUI wrapper over the `sim_node` inputs (`tools/playtest/sim_node.py` is the
headless reference): node type + stage + node index + run seed + dc + team +
weather + augments + items → `CombatSession`. The future Prep/Trail `Start
Combat` flow builds the **identical** `CombatSession` → same combat view, no
change (V.56). Gated behind `TEMPEST_DEV=1` (see `src/main.py`); scuffed
dev/QA styling, like the admin panel.

All three buildable node types are combats (REWARD = an easy fight); the loot
grant is a Trail concern, out of scope here.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Callable

import flet as ft

# Side-effect imports: populate the item/augment registries for validation.
import src.game.augments  # noqa: F401
import src.game.items  # noqa: F401
from src.game.content import CHAMPION_ROSTER
from src.game.encounter import (
    DEFAULT_DC,
    generate_challenge,
    generate_fight,
    generate_reward,
)
from src.game.models import WeatherState
from src.game.registries import AUGMENT_REGISTRY, ITEM_REGISTRY
from src.game.route import CITIES
from src.ui.combat_playback import CombatSession
from src.ui.theme import (
    ACCENT,
    BG,
    DANGER,
    SPACING_LG,
    SPACING_MD,
    SPACING_SM,
    SURFACE,
    TEXT_MUTED,
    TEXT_PRIMARY,
)
from tools.playtest._common import (
    default_team,
    node_position_in_stage,
    stage_def,
)

_NODE_TYPES = ["FIGHT", "CHALLENGE", "REWARD"]
_MAX_ITEMS = 3  # V.23 — up to 3 equipped items per champion


def _parse_ids(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]


def build_dev_harness_view(
    page: ft.Page,
    open_combat: Callable[[CombatSession], None],
) -> ft.View:
    """The `/dev` launcher view. `open_combat(session)` pushes the combat view."""
    run_seed = ft.TextField(label="Run seed", value="0", width=120)
    stage = ft.Dropdown(
        label="Stage", value="1", width=100,
        options=[ft.dropdown.Option(str(i)) for i in range(1, 7)],
    )
    node_index = ft.TextField(label="Node index", value="1", width=120)
    dc = ft.TextField(label="DC", value=str(DEFAULT_DC), width=100)
    node_type = ft.Dropdown(
        label="Node type", value="FIGHT", width=160,
        options=[ft.dropdown.Option(t) for t in _NODE_TYPES],
    )
    weather = ft.Dropdown(
        label="Weather", value="(default)", width=160,
        options=[ft.dropdown.Option("(default)")]
        + [ft.dropdown.Option(w.value) for w in WeatherState],
    )
    team_field = ft.TextField(
        label="Team (comma champion ids — blank = default_team(stage))",
        width=560,
    )
    items_field = ft.TextField(
        label=f"Items (comma ids — applied to each champion, max {_MAX_ITEMS})",
        width=560,
    )
    augments_field = ft.TextField(label="Augments (comma ids)", width=560)
    error_text = ft.Text("", size=12, color=DANGER, selectable=True)

    def _fail(msg: str) -> None:
        error_text.value = msg
        page.update()

    def _on_run(_e: Any) -> None:
        error_text.value = ""
        try:
            seed = int(run_seed.value or "0")
            stage_idx = int(stage.value or "1")
            n_index = int(node_index.value or "1")
            dc_val = float(dc.value or DEFAULT_DC)
        except ValueError:
            return _fail("Seed / node index / DC must be numbers.")

        try:
            sdef = stage_def(stage_idx)
            position = node_position_in_stage(stage_idx, n_index)
        except Exception as exc:  # argparse-style range error
            return _fail(str(exc))

        city_id = sdef.node_cities[position]
        # team
        team_ids = _parse_ids(team_field.value or "")
        if team_ids:
            bad = [t for t in team_ids if t not in CHAMPION_ROSTER]
            if bad:
                return _fail(f"Unknown champion id(s): {', '.join(bad)}")
            team = [CHAMPION_ROSTER[t] for t in team_ids]
        else:
            team = default_team(stage_idx)
        if not team:
            return _fail("Empty team.")

        # items → applied to each champion (fresh instances, never mutate roster)
        item_ids = _parse_ids(items_field.value or "")
        bad_items = [i for i in item_ids if i not in ITEM_REGISTRY]
        if bad_items:
            return _fail(f"Unknown item id(s): {', '.join(bad_items)}")
        if item_ids:
            team = [dataclasses.replace(c, items=list(item_ids[:_MAX_ITEMS])) for c in team]

        # augments → RunModifiers
        aug_ids = _parse_ids(augments_field.value or "")
        bad_augs = [a for a in aug_ids if a not in AUGMENT_REGISTRY]
        if bad_augs:
            return _fail(f"Unknown augment id(s): {', '.join(bad_augs)}")
        run_mods = None
        if aug_ids:
            from src.game.augments import RunModifiers
            run_mods = RunModifiers(augments=list(aug_ids))

        # weather
        if weather.value == "(default)":
            wx = CITIES[city_id].default_weather
        else:
            wx = WeatherState(weather.value)

        # enemies per node type (all combats; REWARD = easy fight)
        try:
            ntype = node_type.value
            if ntype == "FIGHT":
                enemies = generate_fight(seed, n_index, sdef, dc_val)
            elif ntype == "REWARD":
                enemies = generate_reward(seed, n_index, sdef, dc_val)
            else:  # CHALLENGE
                enemies, _reward = generate_challenge(seed, n_index, sdef, wx, dc_val)
        except Exception as exc:
            return _fail(f"Encounter generation failed: {type(exc).__name__}: {exc}")

        node_id = f"s{stage_idx}-n{n_index}-{city_id}"
        session = CombatSession(
            team=team, enemies=enemies, weather=wx, run_mods=run_mods, node_id=node_id,
        )
        open_combat(session)

    form = ft.Column([
        ft.Text("Combat dev harness", size=20, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
        ft.Text("Build a one-off fight and step through it. (TEMPEST_DEV=1)",
                size=12, color=TEXT_MUTED),
        ft.Row([run_seed, stage, node_index, dc], spacing=SPACING_MD, wrap=True),
        ft.Row([node_type, weather], spacing=SPACING_MD, wrap=True),
        team_field,
        items_field,
        augments_field,
        ft.Row([
            ft.FilledButton("Run ▶", on_click=_on_run),
            ft.Container(width=SPACING_MD),
            error_text,
        ]),
        ft.Container(height=SPACING_SM),
        ft.Text(
            f"Champions: {len(CHAMPION_ROSTER)} · Items: {len(ITEM_REGISTRY)} · "
            f"Augments: {len(AUGMENT_REGISTRY)}",
            size=11, color=TEXT_MUTED,
        ),
    ], spacing=SPACING_MD, scroll=ft.ScrollMode.AUTO)

    root = ft.Container(
        bgcolor=BG, padding=SPACING_LG, expand=True,
        content=ft.Container(
            content=form, bgcolor=SURFACE, border_radius=8, padding=SPACING_LG,
            border=ft.Border.all(1, ACCENT),
        ),
    )
    return ft.View(route="/dev", controls=[root], padding=0)
