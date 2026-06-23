"""Dev-harness launcher (T.12a; hex-map board builder added later) — build a
`CombatSession` and open the combat view, without the (unbuilt) Menu/Trail/Prep
shell. Gated behind `TEMPEST_DEV=1` (see `src/main.py`); scuffed dev/QA styling.

Two modes (top switch):

- **Manual** — a **hex-map board builder** (a preliminary TFT-style prep phase). A
  **bench** (toggle Champions ↔ enemy mobs, searchable) of `Draggable` tiles; a
  **10×7 hex map** split down the middle — **left half = ally cells, right half =
  enemy cells**. Drag a bench tile onto a **cell** to place a piece at that
  **starting position**; drag a placed token to another cell to move it; click a
  token to set its **level (1-3)** or remove it. Side is the cell's half. A
  champion placed on the enemy half is converted to an `Enemy` (loses traits,
  V.22); an enemy mob placed on the ally half is converted to a `Champion`. Ids
  are de-duped so the same unit can be placed twice. The hand-placed cells flow
  into combat as a starting-position override (`CombatSession.positions` →
  `build_combat`, on top of `assign_spawns`). → `CombatSession`.
- **Procedural** — the original `sim_node`-style generated encounter (node type +
  stage + node index + seed + dc + team + weather + augments + items), incl. BOSS
  map effects + default formation.

The future Prep/Trail `Start Combat` flow builds the **identical** `CombatSession`
→ same combat view, no change (V.56).
"""

from __future__ import annotations

import dataclasses
from typing import Any, Callable

import flet as ft
import flet.canvas as cv

# Side-effect imports: populate the item/augment registries for validation.
import src.game.augments  # noqa: F401
import src.game.items  # noqa: F401
from src.game.content import (
    CHAMPION_ROSTER,
    ENEMY_ROSTER,
    build_champion_at_level,
    build_enemy_at_level,
)
from src.game.encounter import (
    DEFAULT_DC,
    generate_boss_encounter,
    generate_challenge,
    generate_fight,
    generate_reward,
)
from src.game.models import Champion, Enemy, WeatherState
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
    SPACING_XS,
    SUCCESS,
    SURFACE,
    SURFACE_ELEVATED,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

_NODE_TYPES = ["FIGHT", "CHALLENGE", "REWARD", "BOSS"]
_MAX_ITEMS = 3  # V.23 — up to 3 equipped items per champion
_LEVELS = ["1", "2", "3"]  # champion/enemy star level (1-3), level-scaled stats

# Manual board geometry — mirrors the combat view's 10×7 offset-hex layout.
_BW, _BH = 10, 7
_MID = 5  # ally cells q < _MID (left half); enemy cells q >= _MID (right half)
_MX, _MY, _CW, _RH, _TR = 30, 26, 46, 44, 15
_BOARD_PX_W = _MX * 2 + (_BW - 1) * _CW
_BOARD_PX_H = _MY * 2 + (_BH - 1) * _RH + _RH // 2


def _cell_xy(q: int, r: int) -> tuple[float, float]:
    """Offset-hex (q,r) → pixel centre. Odd columns stagger down half a row."""
    x = _MX + q * _CW
    y = _MY + r * _RH + (_RH // 2 if q % 2 else 0)
    return float(x), float(y)


def _initials(name: str) -> str:
    parts = [s for s in name.replace("_", " ").split() if s]
    if not parts:
        return "?"
    return (parts[0][:2] if len(parts) == 1 else parts[0][0] + parts[1][0]).upper()


def _parse_ids(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]


# --- model conversions (champion ↔ enemy) for cross-side placement -----------
# A unit dropped on the opposite half is rebuilt as the other model. All stat
# fields are shared; only Champion-exclusive traits/items differ (enemies carry
# neither — V.22), so enemy→champion gets empty traits/items.

_SHARED = (
    "id", "name", "affinity", "role", "role_code", "intent", "tier", "level",
    "max_hp", "strength", "intelligence", "attack_speed", "move_speed",
    "mana_regen", "threat", "armor", "resistance", "attack_range",
    "passive_ability", "crit_chance", "penetration", "penetration_pct",
)


def _shared_kwargs(unit: Any) -> dict[str, Any]:
    kw = {k: getattr(unit, k) for k in _SHARED}
    kw["active_abilities"] = list(unit.active_abilities)
    return kw


def _as_enemy(unit: Any) -> Enemy:
    return unit if isinstance(unit, Enemy) else Enemy(**_shared_kwargs(unit))


def _as_champion(unit: Any) -> Champion:
    if isinstance(unit, Champion):
        return unit
    return Champion(**_shared_kwargs(unit), traits=[], items=[])


def _build_unit(kind: str, unit_id: str, level: int) -> Any:
    """Roster lookup at a given level (level-scaled stats). `kind` = champ|enemy."""
    if kind == "champ":
        return build_champion_at_level(unit_id, level)
    return build_enemy_at_level(unit_id, level)


# --- quick-test presets ------------------------------------------------------
# Each preset is a list of (kind, id, level, q, r) placements loaded onto the
# map; once loaded they are fully editable via normal drag-and-drop. Built from
# the live rosters (ids validated on load → unknowns skipped) so a roster rename
# can't crash the harness.


def _build_presets() -> dict[str, list[tuple[str, str, int, int, int]]]:
    champs = sorted(CHAMPION_ROSTER.values(), key=lambda u: (u.tier, u.id))
    mobs = sorted(ENEMY_ROSTER.values(), key=lambda u: (u.tier, u.id))

    def cid(pref: str) -> str:
        return pref if pref in CHAMPION_ROSTER else champs[0].id

    ally_cells = [(2, 3), (2, 1), (2, 5), (1, 2), (1, 4)]
    enemy_cells = [(7, 3), (7, 1), (7, 5), (8, 2), (8, 4)]
    cluster = [(7, 3), (7, 2), (7, 4), (8, 3)]  # tight enemy cluster (AoE bait)

    presets: dict[str, list[tuple[str, str, int, int, int]]] = {}

    # 1. AoE showcase — Aurion (radius solar AoE) L3 vs a tight mob cluster.
    aoe = [("champ", cid("champ_aurion"), 3, 2, 3)]
    aoe += [("enemy", m.id, 1, q, r) for (q, r), m in zip(cluster, mobs)]
    presets["Aurion AoE vs cluster"] = aoe

    # 2. Ember DoT — burn champ L2 vs a trio.
    ember = [("champ", cid("champ_ember_salamander"), 2, 2, 3)]
    ember += [("enemy", m.id, 1, q, r) for (q, r), m in zip(cluster[1:], mobs)]
    presets["Ember DoT vs trio"] = ember

    # 3. Mirror duel — same champion both sides, L1 (ally) vs L3 (enemy).
    duel = cid("champ_aurion")
    presets["Mirror duel (L1 vs L3)"] = [("champ", duel, 1, 2, 3), ("champ", duel, 3, 7, 3)]

    # 4. 5 champs vs 5 mobs — a fuller board.
    five = [("champ", champs[i].id, 1, *ally_cells[i]) for i in range(min(5, len(champs)))]
    five += [("enemy", mobs[i].id, 1, *enemy_cells[i]) for i in range(min(5, len(mobs)))]
    presets["5 champs vs 5 mobs"] = five

    return presets


_PRESETS = _build_presets()


def build_dev_harness_view(
    page: ft.Page,
    open_combat: Callable[[CombatSession], None],
) -> ft.View:
    """The `/dev` launcher view. `open_combat(session)` pushes the combat view."""
    error_text = ft.Text("", size=12, color=DANGER, selectable=True)

    def _fail(msg: str) -> None:
        error_text.value = msg
        page.update()

    def _seg_style(active: bool) -> ft.ButtonStyle:
        return ft.ButtonStyle(
            bgcolor=ACCENT if active else SURFACE_ELEVATED,
            color="#111111" if active else TEXT_MUTED,
        )

    # =====================================================================
    # MANUAL board builder — hex map (preliminary TFT-style prep placement)
    # =====================================================================
    # placements: cell (q,r) -> {kind,id,name,tier,level}. side = ally if q<_MID.
    mstate: dict[str, Any] = {"placements": {}, "roster": "champ", "selected": None}
    m_search = ft.TextField(label="Filter bench (id / name)", width=300, height=44,
                            text_size=12, on_change=lambda _e: _refresh_bench())
    m_seed = ft.TextField(label="Seed", value="0", width=90)
    m_weather = ft.Dropdown(
        label="Weather", value="clear", width=140,
        options=[ft.dropdown.Option(w.value) for w in WeatherState],
    )
    m_augs = ft.TextField(label="Augments (comma ids — ally)", width=280)
    m_items = ft.TextField(label=f"Items (comma — each ally champ, max {_MAX_ITEMS})", width=280)

    bench_wrap = ft.Row(wrap=True, spacing=SPACING_XS, run_spacing=SPACING_XS, scroll=ft.ScrollMode.AUTO)
    board_stack = ft.Stack(width=_BOARD_PX_W, height=_BOARD_PX_H)
    sel_panel = ft.Column(spacing=SPACING_XS, width=240)
    count_text = ft.Text("", size=11, color=TEXT_MUTED)

    def _roster_items() -> list[Any]:
        src = CHAMPION_ROSTER if mstate["roster"] == "champ" else ENEMY_ROSTER
        q = (m_search.value or "").strip().lower()
        units = [u for u in src.values() if not q or q in u.id.lower() or q in u.name.lower()]
        return sorted(units, key=lambda u: (u.tier, u.id))

    def _bench_tile(unit: Any) -> ft.Control:
        kind = mstate["roster"]
        tile = ft.Container(
            padding=ft.Padding(6, 3, 6, 3), border_radius=6, bgcolor=SURFACE_ELEVATED,
            border=ft.Border.all(1, ACCENT if kind == "champ" else DANGER),
            content=ft.Column([
                ft.Text(unit.name, size=10, color=TEXT_PRIMARY, no_wrap=True),
                ft.Text(f"T{unit.tier} · {unit.affinity.value}", size=8, color=TEXT_MUTED),
            ], spacing=0, tight=True),
        )
        return ft.Draggable(
            group="unit", content=tile, data=f"new:{kind}:{unit.id}:{unit.name}:{unit.tier}",
            content_feedback=ft.Container(
                width=_TR * 2, height=_TR * 2, border_radius=_TR, bgcolor=ACCENT,
                alignment=ft.Alignment.CENTER,
                content=ft.Text(_initials(unit.name), size=9, color="#111111"),
            ),
        )

    def _token(q: int, r: int, p: dict[str, Any]) -> ft.Control:
        cx, cy = _cell_xy(q, r)
        ally = q < _MID
        selected = mstate["selected"] == (q, r)
        tok = ft.Container(
            width=_TR * 2, height=_TR * 2, border_radius=_TR,
            bgcolor=SUCCESS if ally else DANGER,
            border=ft.Border.all(2, ACCENT if selected else "#111111"),
            alignment=ft.Alignment.CENTER,
            content=ft.Text(_initials(p["name"]), size=9, weight=ft.FontWeight.BOLD, color="#111111"),
            tooltip=f'{p["name"]} · L{p["level"]} · ({q},{r})',
            on_click=lambda _e, c=(q, r): _select(c),
        )
        return ft.Container(left=cx - _TR, top=cy - _TR,
                            content=ft.Draggable(group="unit", data=f"move:{q}:{r}", content=tok))

    def _build_board() -> None:
        shapes: list[Any] = []
        for q in range(_BW):
            for r in range(_BH):
                cx, cy = _cell_xy(q, r)
                tint = SUCCESS if q < _MID else DANGER
                shapes.append(cv.Circle(cx, cy, _TR + 1,
                              ft.Paint(color=ft.Colors.with_opacity(0.07, tint), style=ft.PaintingStyle.FILL)))
                shapes.append(cv.Circle(cx, cy, 2.5,
                              ft.Paint(color=SURFACE_ELEVATED, style=ft.PaintingStyle.FILL)))
        dx = _MX + (_MID - 0.5) * _CW  # the "missing middle" divider
        shapes.append(cv.Line(dx, 4.0, dx, _BOARD_PX_H - 4.0,
                      ft.Paint(color=TEXT_MUTED, stroke_width=1.5, style=ft.PaintingStyle.STROKE)))

        controls: list[ft.Control] = [cv.Canvas(shapes=shapes, width=_BOARD_PX_W, height=_BOARD_PX_H)]
        # per-cell drop targets (base layer)
        for q in range(_BW):
            for r in range(_BH):
                cx, cy = _cell_xy(q, r)
                controls.append(ft.Container(
                    left=cx - _TR, top=cy - _TR,
                    content=ft.DragTarget(
                        group="unit",
                        content=ft.Container(width=_TR * 2, height=_TR * 2, border_radius=_TR),
                        on_accept=lambda e, c=(q, r): _on_cell_drop(e, c),
                    ),
                ))
        # placed tokens (on top)
        for (q, r), p in mstate["placements"].items():
            controls.append(_token(q, r, p))
        board_stack.controls = controls

    def _build_sel_panel() -> None:
        c = mstate["selected"]
        p = mstate["placements"].get(c) if c else None
        if not p:
            sel_panel.controls = [
                ft.Text("Selected piece", size=12, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                ft.Text("Click a placed token to set level / remove.", size=11, color=TEXT_MUTED),
            ]
            return
        q, r = c
        ally = q < _MID
        sel_panel.controls = [
            ft.Text(p["name"], size=13, weight=ft.FontWeight.BOLD, color=SUCCESS if ally else DANGER),
            ft.Text(f"{'ally' if ally else 'enemy'} · cell ({q},{r}) · T{p['tier']}",
                    size=11, color=TEXT_MUTED),
            ft.Row([
                ft.Text("Level", size=11, color=TEXT_MUTED, width=44),
                ft.Dropdown(value=str(p["level"]), width=72, text_size=11,
                            options=[ft.dropdown.Option(l) for l in _LEVELS],
                            on_select=lambda e: _set_level(e.control.value)),
            ], spacing=SPACING_XS, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.FilledButton("Remove ✕", on_click=lambda _e: _remove()),
        ]

    def _on_cell_drop(e: ft.DragTargetEvent, cell: tuple[int, int]) -> None:
        key = e.src.data or ""
        if cell in mstate["placements"]:
            return  # occupied — remove the token first to replace
        if key.startswith("move:"):
            _, fq, fr = key.split(":")
            p = mstate["placements"].pop((int(fq), int(fr)), None)
            if p is not None:
                mstate["placements"][cell] = p
                mstate["selected"] = cell
        elif key.startswith("new:"):
            _, kind, uid, name, tier = key.split(":", 4)
            mstate["placements"][cell] = {"kind": kind, "id": uid, "name": name,
                                          "tier": int(tier), "level": 1}
            mstate["selected"] = cell
        _refresh_board()

    def _select(cell: tuple[int, int]) -> None:
        mstate["selected"] = cell
        _refresh_board()

    def _set_level(value: str) -> None:
        c = mstate["selected"]
        if c in mstate["placements"]:
            mstate["placements"][c]["level"] = int(value)

    def _remove() -> None:
        mstate["placements"].pop(mstate["selected"], None)
        mstate["selected"] = None
        _refresh_board()

    def _load_preset(name: str) -> None:
        spec = _PRESETS.get(name)
        if not spec:
            return
        pl: dict[tuple[int, int], dict[str, Any]] = {}
        for kind, uid, level, q, r in spec:
            unit = (CHAMPION_ROSTER if kind == "champ" else ENEMY_ROSTER).get(uid)
            if unit is None:
                continue  # roster rename → skip rather than crash
            pl[(q, r)] = {"kind": kind, "id": uid, "name": unit.name,
                          "tier": unit.tier, "level": level}
        mstate["placements"] = pl
        mstate["selected"] = None
        _refresh_board()

    def _clear_board() -> None:
        mstate["placements"] = {}
        mstate["selected"] = None
        _refresh_board()

    def _set_roster(mode: str) -> None:
        mstate["roster"] = mode
        roster_champ_btn.style = _seg_style(mode == "champ")
        roster_enemy_btn.style = _seg_style(mode == "enemy")
        _refresh_bench()

    def _refresh_bench() -> None:
        bench_wrap.controls = [_bench_tile(u) for u in _roster_items()]
        page.update()

    def _refresh_board() -> None:
        _build_board()
        _build_sel_panel()
        n_ally = sum(1 for (q, _r) in mstate["placements"] if q < _MID)
        count_text.value = f"{n_ally} ally · {len(mstate['placements']) - n_ally} enemy"
        page.update()

    def _on_run_manual(_e: Any) -> None:
        error_text.value = ""
        pl = mstate["placements"]
        if not any(q < _MID for q, _r in pl) or not any(q >= _MID for q, _r in pl):
            return _fail("Place at least one ally (left half) and one enemy (right half).")
        try:
            int(m_seed.value or "0")
        except ValueError:
            return _fail("Seed must be a number.")
        item_ids = _parse_ids(m_items.value or "")
        bad_items = [i for i in item_ids if i not in ITEM_REGISTRY]
        if bad_items:
            return _fail(f"Unknown item id(s): {', '.join(bad_items)}")
        aug_ids = _parse_ids(m_augs.value or "")
        bad_augs = [a for a in aug_ids if a not in AUGMENT_REGISTRY]
        if bad_augs:
            return _fail(f"Unknown augment id(s): {', '.join(bad_augs)}")

        seen: dict[str, int] = {}
        team: list[Champion] = []
        enemies: list[Enemy] = []
        positions: dict[str, tuple[int, int]] = {}
        for (q, r), p in sorted(pl.items()):
            unit = _build_unit(p["kind"], p["id"], p["level"])
            ally = q < _MID
            unit = _as_champion(unit) if ally else _as_enemy(unit)
            if unit.id in seen:
                seen[unit.id] += 1
                unit = dataclasses.replace(unit, id=f"{unit.id}~{seen[unit.id]}")
            else:
                seen[unit.id] = 1
            positions[unit.id] = (q, r)
            (team if ally else enemies).append(unit)

        if item_ids:  # dataclasses.replace keeps the id → positions stay valid
            team = [dataclasses.replace(c, items=list(item_ids[:_MAX_ITEMS])) for c in team]

        run_mods = None
        if aug_ids:
            from src.game.augments import RunModifiers
            run_mods = RunModifiers(augments=list(aug_ids))

        open_combat(CombatSession(
            team=team, enemies=enemies, weather=WeatherState(m_weather.value),
            run_mods=run_mods, node_id="dev-manual", map_effect_id="", positions=positions,
        ))

    roster_champ_btn = ft.OutlinedButton("Champions", on_click=lambda _e: _set_roster("champ"),
                                          style=_seg_style(True))
    roster_enemy_btn = ft.OutlinedButton("Enemy mobs", on_click=lambda _e: _set_roster("enemy"),
                                          style=_seg_style(False))

    preset_dd = ft.Dropdown(
        label="Preset (then edit)", width=240,
        options=[ft.dropdown.Option(n) for n in _PRESETS],
        on_select=lambda e: _load_preset(e.control.value),
    )

    manual_panel = ft.Column([
        ft.Text("Drag a bench tile onto a hex cell = that unit's starting position. "
                "Left half = ally, right half = enemy. Drag a placed token to another cell "
                "to move it; click a token to set level / remove. Or load a preset and edit it.",
                size=12, color=TEXT_MUTED),
        ft.Row([preset_dd, ft.OutlinedButton("Clear board", on_click=lambda _e: _clear_board())],
               spacing=SPACING_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ft.Row([roster_champ_btn, roster_enemy_btn, m_search], spacing=SPACING_SM,
               vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ft.Container(content=bench_wrap, height=110, bgcolor=BG, border_radius=8,
                     padding=SPACING_SM, border=ft.Border.all(1, TEXT_MUTED)),
        ft.Row([
            ft.Container(content=board_stack, bgcolor=SURFACE, border_radius=8,
                         padding=SPACING_SM, border=ft.Border.all(1, TEXT_MUTED)),
            ft.Container(content=sel_panel, bgcolor=SURFACE, border_radius=8,
                         padding=SPACING_MD, width=260),
        ], spacing=SPACING_MD, vertical_alignment=ft.CrossAxisAlignment.START),
        ft.Row([m_seed, m_weather, m_augs, m_items], spacing=SPACING_MD, wrap=True),
        ft.Row([ft.FilledButton("Run ▶", on_click=_on_run_manual),
                ft.Container(width=SPACING_MD), count_text]),
    ], spacing=SPACING_MD)

    # =====================================================================
    # PROCEDURAL encounter (original form)
    # =====================================================================
    run_seed = ft.TextField(label="Run seed", value="0", width=120)
    stage = ft.Dropdown(label="Stage", value="1", width=100,
                        options=[ft.dropdown.Option(str(i)) for i in range(1, 7)])
    node_index = ft.TextField(label="Node index", value="1", width=120)
    dc = ft.TextField(label="DC", value=str(DEFAULT_DC), width=100)
    node_type = ft.Dropdown(label="Node type", value="FIGHT", width=160,
                            options=[ft.dropdown.Option(t) for t in _NODE_TYPES])
    weather = ft.Dropdown(
        label="Weather", value="(default)", width=160,
        options=[ft.dropdown.Option("(default)")] + [ft.dropdown.Option(w.value) for w in WeatherState],
    )
    team_field = ft.TextField(label="Team (comma champion ids — blank = default_team(stage))", width=560)
    items_field = ft.TextField(label=f"Items (comma ids — each champion, max {_MAX_ITEMS})", width=560)
    augments_field = ft.TextField(label="Augments (comma ids)", width=560)

    def _on_run_procedural(_e: Any) -> None:
        from tools.playtest._common import default_team, node_position_in_stage, stage_def
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
        except Exception as exc:
            return _fail(str(exc))
        city_id = sdef.node_cities[position]
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
        item_ids = _parse_ids(items_field.value or "")
        bad_items = [i for i in item_ids if i not in ITEM_REGISTRY]
        if bad_items:
            return _fail(f"Unknown item id(s): {', '.join(bad_items)}")
        if item_ids:
            team = [dataclasses.replace(c, items=list(item_ids[:_MAX_ITEMS])) for c in team]
        aug_ids = _parse_ids(augments_field.value or "")
        bad_augs = [a for a in aug_ids if a not in AUGMENT_REGISTRY]
        if bad_augs:
            return _fail(f"Unknown augment id(s): {', '.join(bad_augs)}")
        run_mods = None
        if aug_ids:
            from src.game.augments import RunModifiers
            run_mods = RunModifiers(augments=list(aug_ids))
        wx = CITIES[city_id].default_weather if weather.value == "(default)" else WeatherState(weather.value)
        map_effect_id = ""
        try:
            ntype = node_type.value
            if ntype == "FIGHT":
                enemies = generate_fight(seed, n_index, sdef, dc_val)
            elif ntype == "REWARD":
                enemies = generate_reward(seed, n_index, sdef, dc_val)
            elif ntype == "BOSS":
                encounter = generate_boss_encounter(seed, n_index, sdef)
                enemies = encounter.all_enemies
                map_effect_id = encounter.map_effect_id
            else:
                enemies, _reward = generate_challenge(seed, n_index, sdef, wx, dc_val)
        except Exception as exc:
            return _fail(f"Encounter generation failed: {type(exc).__name__}: {exc}")
        node_id = f"s{stage_idx}-n{n_index}-{city_id}"
        open_combat(CombatSession(team=team, enemies=enemies, weather=wx, run_mods=run_mods,
                                  node_id=node_id, map_effect_id=map_effect_id))

    procedural_panel = ft.Column([
        ft.Text("Generate a procedural encounter (incl. BOSS map effects + default formation).",
                size=12, color=TEXT_MUTED),
        ft.Row([run_seed, stage, node_index, dc], spacing=SPACING_MD, wrap=True),
        ft.Row([node_type, weather], spacing=SPACING_MD, wrap=True),
        team_field, items_field, augments_field,
        ft.Row([ft.FilledButton("Run ▶", on_click=_on_run_procedural)]),
    ], spacing=SPACING_MD, visible=False)

    # =====================================================================
    # mode switch + shell
    # =====================================================================
    def _set_mode(mode: str) -> None:
        manual_panel.visible = mode == "manual"
        procedural_panel.visible = mode == "procedural"
        mode_manual_btn.style = _seg_style(mode == "manual")
        mode_proc_btn.style = _seg_style(mode == "procedural")
        error_text.value = ""
        page.update()

    mode_manual_btn = ft.OutlinedButton("Manual board", on_click=lambda _e: _set_mode("manual"),
                                        style=_seg_style(True))
    mode_proc_btn = ft.OutlinedButton("Procedural", on_click=lambda _e: _set_mode("procedural"),
                                      style=_seg_style(False))

    form = ft.Column([
        ft.Text("Combat dev harness", size=20, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
        ft.Row([mode_manual_btn, mode_proc_btn], spacing=SPACING_SM),
        error_text,
        manual_panel,
        procedural_panel,
        ft.Container(height=SPACING_SM),
        ft.Text(
            f"Champions: {len(CHAMPION_ROSTER)} · Enemies: {len(ENEMY_ROSTER)} · "
            f"Items: {len(ITEM_REGISTRY)} · Augments: {len(AUGMENT_REGISTRY)}",
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
    # initial paint
    _refresh_bench()
    _refresh_board()
    return ft.View(route="/dev", controls=[root], padding=0)
