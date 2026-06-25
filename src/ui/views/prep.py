"""Prep view (T.23a, route `/prep`) — the pre-combat decision layer.

Pure presentation over the finished economy/combat backend (V.63/V.1): the view
mutates ``Run`` **only** through ``game/economy.py`` / ``game/shop.py`` (shop
buy/reroll/sell/supply, rank-up) and resolves combat **only** by building a
``CombatSession`` and handing it to the host — it recomputes no Amber/cost/level/
encounter number itself.

**Placement → combat:** the player arranges the team on the hex board (drag bench↔
board, TFT-style) within the **allied deployment zone** (columns 0..2, V.68). Each
placed champion gets a ``team_positions[champion_id] = (q, r)`` cell; Start-Combat
validates it with ``loadout.validate_team_positions`` (zone + roster-id, on top of
the V.62 engine guard) and builds ``CombatSession(positions=team_positions)`` —
shape-identical to the dev-harness producer. ``Auto-Place`` mirrors the default
``assign_spawns`` packing (champion *i* → ``(i // 7, i % 7)``) so it stays
byte-identical to the engine's default formation (V.2).

Enemies/weather come from the shared ``encounter.node_encounter`` dispatcher (the
same one Trail previews) so *preview == fought squad* (V.2). The displayed live
weather (V.66) is decoupled from the combat weather — combat always uses the
node's deterministic ``weather``.
"""

from __future__ import annotations

from typing import Callable

import flet as ft

from src.game.combat import BOARD_HEIGHT
from src.game.content import CHAMPION_DEF_BY_ID
from src.game.economy import (
    champion_cost,
    sell_champion,
    try_rank_up_with_amber,
)
from src.game.encounter import node_encounter
from src.game.loadout import ALLIED_ZONE_MAX_Q, validate_team_positions
from src.game.models import Champion, Node, NodeType, Run
from src.game.shop import buy_from_shop, reroll_cost, reroll_shop
from src.game.weather_effects import RingRelation, ring_relation
from src.ui.combat_playback import CombatSession
from src.ui.components.board_geometry import BOARD_H, BOARD_W, COL_W, ROW_H, cell_xy
from src.ui.components.weather_badge import weather_badge
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

_TOKEN_R = 16
_NO_FIGHT = frozenset({NodeType.AUGMENT, NodeType.SUPPLY})
_DRAG_GROUP = "champ"


def _initials(name: str) -> str:
    parts = [p for p in name.replace("_", " ").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def build_prep_view(
    page: ft.Page,
    run: Run,
    node: Node,
    *,
    on_start_combat: Callable[[CombatSession], None],
    on_back: Callable[[], None],
) -> ft.View:
    """Build the Prep view for ``run`` at ``node`` (T.23a).

    ``on_start_combat(session)`` opens combat with the assembled ``CombatSession``;
    ``on_back()`` returns to the Trail. The reward/progression step (applying the
    ``BattleResult``) is the host's job (T.15, V.64) — Prep only produces the input.
    """
    # team_positions: champion_id -> (q, r) board cell. The board shows run.roster
    # (the deployable field, capped at tempest_rank); run.bench holds reserves.
    team_positions: dict[str, tuple[int, int]] = {}
    state: dict[str, object] = {"selected": None}

    enc = node_encounter(run.seed, node, weather=node.weather)

    # --- team / board state helpers --------------------------------------------
    def _cap() -> int:
        return run.tempest_rank

    def _normalize_roster() -> None:
        """Keep the field (run.roster) within the rank cap; overflow → bench.
        Buying can append a fresh champion to roster beyond the cap — push the
        excess to the bench so the board never exceeds tempest_rank (V.22)."""
        cap = _cap()
        if len(run.roster) > cap:
            overflow = run.roster[cap:]
            del run.roster[cap:]
            run.bench.extend(overflow)

    def _free_cell() -> tuple[int, int] | None:
        used = set(team_positions.values())
        for q in range(ALLIED_ZONE_MAX_Q):
            for r in range(BOARD_HEIGHT):
                if (q, r) not in used:
                    return (q, r)
        return None

    def _auto_place() -> None:
        """Default formation packing — champion at roster index i → (i//7, i%7),
        mirroring engine.assign_spawns so the result is byte-identical to
        positions=None (V.62/V.2)."""
        team_positions.clear()
        for i, champ in enumerate(run.roster):
            team_positions[champ.id] = (i // BOARD_HEIGHT, i % BOARD_HEIGHT)

    def _ensure_placed() -> None:
        """Every field champion gets a cell; drop cells for non-field ids."""
        valid_ids = {c.id for c in run.roster}
        for cid in [k for k in team_positions if k not in valid_ids]:
            del team_positions[cid]
        for champ in run.roster:
            if champ.id not in team_positions:
                cell = _free_cell()
                if cell is not None:
                    team_positions[champ.id] = cell

    def _champ_by_id(cid: str) -> Champion | None:
        for c in (*run.roster, *run.bench):
            if c.id == cid:
                return c
        return None

    # --- placement moves (drag/drop) -------------------------------------------
    def _place_on_cell(champ_id: str, cell: tuple[int, int]) -> None:
        """Drop a champion (from bench or board) onto a board cell."""
        champ = _champ_by_id(champ_id)
        if champ is None:
            return
        from_bench = champ in run.bench
        if from_bench:
            if len(run.roster) >= _cap():
                _flash(f"Field is full (rank {_cap()}). Bench a unit first.")
                return
            run.bench.remove(champ)
            run.roster.append(champ)
        # If the target cell is occupied by another champion, swap cells.
        occupant = next((cid for cid, c in team_positions.items() if c == cell), None)
        if occupant is not None and occupant != champ_id:
            old = team_positions.get(champ_id)
            if old is not None:
                team_positions[occupant] = old
            else:
                del team_positions[occupant]
                # occupant stays on board only if the dragged one had a cell;
                # otherwise push the displaced occupant to the first free cell.
                free = _free_cell()
                if free is not None:
                    team_positions[occupant] = free
        team_positions[champ_id] = cell
        _render()

    def _send_to_bench(champ_id: str) -> None:
        champ = _champ_by_id(champ_id)
        if champ is None or champ in run.bench:
            return
        run.roster.remove(champ)
        run.bench.append(champ)
        team_positions.pop(champ_id, None)
        _render()

    # --- economy actions (all through game/) -----------------------------------
    def _after_economy() -> None:
        _normalize_roster()
        _ensure_placed()
        _render()

    def _buy(slot: int) -> None:
        if buy_from_shop(run, slot):
            _after_economy()
        else:
            _flash("Can't buy (unaffordable, maxed, or empty slot).")

    def _reroll() -> None:
        if not reroll_shop(run):
            _flash("Can't reroll (not enough Amber).")
        _render()

    def _sell(champ_id: str) -> None:
        if sell_champion(run, champ_id):
            team_positions.pop(champ_id, None)
            if state["selected"] == champ_id:
                state["selected"] = None
            _after_economy()

    def _rank_up() -> None:
        if not try_rank_up_with_amber(run):
            _flash("Can't rank up (max rank or not enough Amber).")
        _render()

    # --- start combat -----------------------------------------------------------
    def _start_combat(_e: object = None) -> None:
        team = [c for c in run.roster if c.id in team_positions]
        if not team:
            _flash("Place at least one champion on the board.")
            return
        positions = {c.id: team_positions[c.id] for c in team}
        try:
            validate_team_positions(team, positions)
        except ValueError as exc:
            _flash(str(exc))
            return
        session = CombatSession(
            team=team,
            enemies=enc.enemies,
            weather=node.weather,          # deterministic combat weather (V.2/V.66)
            run_mods=_run_mods(),
            node_id=f"n{node.index}-{node.city}",
            map_effect_id=enc.map_effect_id,
            positions=positions,
        )
        on_start_combat(session)

    def _run_mods() -> object:
        """Live augments for combat — shares ``augment_state`` by ref (V.18); the
        combat view runs on a deep clone (V.55) so no side effects leak back."""
        from src.game.augments import RunModifiers
        return RunModifiers.from_run(run)

    # --- transient feedback -----------------------------------------------------
    msg_holder = ft.Container(height=0)

    def _flash(text: str) -> None:
        msg_holder.content = ft.Text(text, size=FONT_SIZE_CAPTION, color=WARNING)
        msg_holder.height = None
        page.update()

    # --- board -----------------------------------------------------------------
    def _token(champ: Champion, *, draggable: bool) -> ft.Control:
        selected = state["selected"] == champ.id
        token = ft.Container(
            width=_TOKEN_R * 2,
            height=_TOKEN_R * 2,
            border_radius=_TOKEN_R,
            bgcolor=AFFINITY_COLORS[champ.affinity],
            border=ft.Border.all(2, TEXT_PRIMARY if selected else SURFACE_ELEVATED),
            alignment=ft.Alignment.CENTER,
            content=ft.Text(_initials(champ.name), size=11, color=BG,
                            weight=ft.FontWeight.BOLD),
            tooltip=f"{champ.name} · L{champ.level} {champ.role}",
            on_click=lambda _e, cid=champ.id: _select(cid),
            data=champ.id,
        )
        if not draggable:
            return token
        return ft.Draggable(
            group=_DRAG_GROUP,
            content=token,
            content_feedback=ft.Container(
                width=_TOKEN_R * 2, height=_TOKEN_R * 2, border_radius=_TOKEN_R,
                bgcolor=AFFINITY_COLORS[champ.affinity], opacity=0.8,
                alignment=ft.Alignment.CENTER,
                content=ft.Text(_initials(champ.name), size=11, color=BG),
            ),
            data=champ.id,
        )

    def _on_cell_accept(cell: tuple[int, int]):
        def handler(e: ft.DragTargetEvent) -> None:
            src = page.get_control(e.src_id)
            cid = getattr(src, "data", None)
            if isinstance(cid, str):
                _place_on_cell(cid, cell)
        return handler

    def _build_board() -> ft.Control:
        layers: list[ft.Control] = []
        # Zone tint + cell drop-targets (deployment zone columns 0..2).
        for q in range(ALLIED_ZONE_MAX_Q):
            for r in range(BOARD_HEIGHT):
                cx, cy = cell_xy(q, r)
                layers.append(
                    ft.Container(
                        left=cx - COL_W / 2, top=cy - ROW_H / 2,
                        width=COL_W, height=ROW_H,
                        content=ft.DragTarget(
                            group=_DRAG_GROUP,
                            content=ft.Container(
                                width=COL_W - 4, height=ROW_H - 4,
                                border_radius=CARD_RADIUS,
                                bgcolor=ft.Colors.with_opacity(0.06, ACCENT),
                                border=ft.Border.all(1, SURFACE_ELEVATED),
                            ),
                            on_accept=_on_cell_accept((q, r)),
                        ),
                    )
                )
        # Champion tokens at their placed cells.
        for champ in run.roster:
            cell = team_positions.get(champ.id)
            if cell is None:
                continue
            cx, cy = cell_xy(*cell)
            layers.append(
                ft.Container(left=cx - _TOKEN_R, top=cy - _TOKEN_R,
                             content=_token(champ, draggable=True))
            )
        return ft.Container(
            width=BOARD_W, height=BOARD_H,
            content=ft.Stack(layers),
            bgcolor=SURFACE, border_radius=CARD_RADIUS,
        )

    # --- bench (drop target) ----------------------------------------------------
    def _build_bench() -> ft.Control:
        slots: list[ft.Control] = [
            ft.Text("Bench", size=FONT_SIZE_CAPTION, color=TEXT_MUTED),
        ]
        for champ in run.bench:
            slots.append(_token(champ, draggable=True))
        if not run.bench:
            slots.append(ft.Text("(drag units here to bench)", size=FONT_SIZE_CAPTION,
                                 color=TEXT_MUTED))

        def _bench_accept(e: ft.DragTargetEvent) -> None:
            src = page.get_control(e.src_id)
            cid = getattr(src, "data", None)
            if isinstance(cid, str):
                _send_to_bench(cid)

        return ft.DragTarget(
            group=_DRAG_GROUP,
            content=ft.Container(
                ft.Row(slots, spacing=SPACING_SM, wrap=True,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=SURFACE, border_radius=CARD_RADIUS, padding=SPACING_MD,
            ),
            on_accept=_bench_accept,
        )

    # --- shop -------------------------------------------------------------------
    def _build_shop() -> ft.Control:
        rows: list[ft.Control] = [
            ft.Row(
                [
                    ft.Text("Shop", size=FONT_SIZE_H3, color=TEXT_PRIMARY,
                            weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.OutlinedButton(
                        f"Reroll ({reroll_cost(run.shop_rerolls)})",
                        on_click=lambda _e: _reroll(),
                    ),
                ],
            ),
        ]
        for slot, cid in enumerate(run.shop_offers):
            if cid is None:
                rows.append(ft.Container(
                    ft.Text("— sold —", size=FONT_SIZE_CAPTION, color=TEXT_MUTED),
                    bgcolor=SURFACE_ELEVATED, border_radius=CARD_RADIUS,
                    padding=SPACING_SM,
                ))
                continue
            cdef = CHAMPION_DEF_BY_ID.get(cid)
            if cdef is None:
                continue
            cost = champion_cost(cdef.tier)
            affordable = run.amber >= cost
            rows.append(
                ft.Container(
                    ft.Row(
                        [
                            ft.Container(width=10, height=10, border_radius=5,
                                         bgcolor=AFFINITY_COLORS[cdef.affinity]),
                            ft.Text(cdef.name, size=FONT_SIZE_BODY, color=TEXT_PRIMARY,
                                    expand=True, no_wrap=True),
                            ft.Text(f"T{cdef.tier}", size=FONT_SIZE_CAPTION,
                                    color=TEXT_MUTED),
                            ft.FilledButton(
                                f"{cost}⨀",
                                on_click=lambda _e, s=slot: _buy(s),
                                disabled=not affordable,
                                style=ft.ButtonStyle(bgcolor=ACCENT if affordable else SURFACE_ELEVATED),
                            ),
                        ],
                        spacing=SPACING_SM,
                    ),
                    bgcolor=SURFACE_ELEVATED, border_radius=CARD_RADIUS,
                    padding=ft.Padding(left=SPACING_SM, right=SPACING_SM, top=4, bottom=4),
                )
            )
        return ft.Column(rows, spacing=SPACING_SM)

    # --- enemy preview ----------------------------------------------------------
    def _build_enemy_preview() -> ft.Control:
        if node.node_type in _NO_FIGHT:
            return ft.Text("No fight here.", size=FONT_SIZE_CAPTION, color=TEXT_MUTED)
        team_affinities = {c.affinity for c in run.roster}
        rows: list[ft.Control] = []
        for e in enc.enemies[:10]:
            # Affinity clash hint: does any team affinity prey on / hunt this enemy?
            hint = "·"
            hint_color = TEXT_MUTED
            for aff in team_affinities:
                rel = ring_relation(aff, e.affinity)
                if rel in (RingRelation.PRIMARY_PREDATOR, RingRelation.SECONDARY_PREDATOR):
                    hint, hint_color = "↑", SUCCESS
                    break
                if rel in (RingRelation.PRIMARY_PREY, RingRelation.SECONDARY_PREY):
                    hint, hint_color = "↓", DANGER
            rows.append(
                ft.Row(
                    [
                        ft.Container(width=8, height=8, border_radius=4,
                                     bgcolor=AFFINITY_COLORS[e.affinity]),
                        ft.Text(e.name, size=FONT_SIZE_CAPTION, color=TEXT_PRIMARY,
                                expand=True, no_wrap=True),
                        ft.Text(hint, size=FONT_SIZE_CAPTION, color=hint_color),
                        ft.Text(f"T{e.tier} {e.max_hp}hp", size=FONT_SIZE_CAPTION,
                                color=TEXT_MUTED),
                    ],
                    spacing=SPACING_SM,
                )
            )
        if len(enc.enemies) > 10:
            rows.append(ft.Text(f"+{len(enc.enemies) - 10} more", size=FONT_SIZE_CAPTION,
                                color=TEXT_MUTED))
        header = f"Enemies ({len(enc.enemies)})"
        if enc.map_effect_id:
            header += f" · map: {enc.map_effect_id}"
        return ft.Column(
            [ft.Text(header, size=FONT_SIZE_H3, color=TEXT_PRIMARY,
                     weight=ft.FontWeight.BOLD)] + rows,
            spacing=SPACING_XS,
        )

    # --- stat inspect (tooltip panel) ------------------------------------------
    def _stat_row(label: str, value: str) -> ft.Control:
        return ft.Row(
            [ft.Text(label, size=11, color=TEXT_MUTED, width=64),
             ft.Text(value, size=11, color=TEXT_PRIMARY)],
            spacing=SPACING_SM,
        )

    def _build_inspect() -> ft.Control:
        cid = state["selected"]
        champ = _champ_by_id(cid) if isinstance(cid, str) else None
        if champ is None:
            return ft.Text("Tap a champion to inspect.", size=FONT_SIZE_CAPTION,
                           color=TEXT_MUTED)
        # Raw sheet + a couple of derived rates (read straight off the Champion).
        rows: list[ft.Control] = [
            ft.Text(champ.name, size=FONT_SIZE_H3, color=AFFINITY_COLORS[champ.affinity],
                    weight=ft.FontWeight.BOLD),
            ft.Text(f"{champ.affinity.value} · {champ.role} · L{champ.level} T{champ.tier}",
                    size=FONT_SIZE_CAPTION, color=TEXT_MUTED),
        ]
        primary = [("HP", f"{champ.max_hp}"), ("STR", f"{champ.strength}"),
                   ("INT", f"{champ.intelligence}"), ("AS", f"{champ.attack_speed:.1f}"),
                   ("range", f"{champ.attack_range}")]
        premium = [("armor", f"{champ.armor}"), ("res", f"{champ.resistance}"),
                   ("MS", f"{champ.move_speed}"), ("MR", f"{champ.mana_regen}"),
                   ("crit", f"{champ.crit_chance * 100:.0f}%")]
        rows.append(ft.Row([
            ft.Column([_stat_row(l, v) for l, v in primary], spacing=2, expand=True),
            ft.Column([_stat_row(l, v) for l, v in premium], spacing=2, expand=True),
        ], spacing=SPACING_SM))
        if champ.items:
            rows.append(_stat_row("items", ", ".join(champ.items)))
        if champ.traits:
            rows.append(_stat_row("traits", ", ".join(champ.traits)))
        # Sell control (only for owned, copy-tracked units).
        if champ.id in run.champion_copies:
            rows.append(ft.Container(height=SPACING_XS))
            rows.append(ft.OutlinedButton(
                "Sell", on_click=lambda _e, c=champ.id: _sell(c),
                style=ft.ButtonStyle(color=DANGER),
            ))
        return ft.Column(rows, spacing=SPACING_XS, scroll=ft.ScrollMode.AUTO)

    def _select(cid: str) -> None:
        state["selected"] = cid
        _render()

    # --- holders + render -------------------------------------------------------
    board_holder = ft.Container()
    bench_holder = ft.Container()
    shop_holder = ft.Container(bgcolor=SURFACE, border_radius=CARD_RADIUS,
                               padding=SPACING_MD)
    preview_holder = ft.Container(bgcolor=SURFACE, border_radius=CARD_RADIUS,
                                  padding=SPACING_MD)
    inspect_holder = ft.Container(bgcolor=SURFACE, border_radius=CARD_RADIUS,
                                  padding=SPACING_MD, width=300)
    resources_holder = ft.Row(spacing=SPACING_SM)

    def _resources() -> list[ft.Control]:
        return [
            _chip("Amber", f"{run.amber}", WARNING),
            _chip("Rank", f"{run.tempest_rank}", ACCENT),
            _chip("Field", f"{len(run.roster)}/{_cap()}", TEXT_PRIMARY),
            ft.OutlinedButton("Rank Up", on_click=lambda _e: _rank_up()),
        ]

    def _render() -> None:
        board_holder.content = _build_board()
        bench_holder.content = _build_bench()
        shop_holder.content = _build_shop()
        preview_holder.content = _build_enemy_preview()
        inspect_holder.content = _build_inspect()
        resources_holder.controls = _resources()
        page.update()

    # --- top bar ----------------------------------------------------------------
    type_color = DANGER if node.node_type == NodeType.BOSS_FIGHT else ACCENT
    top_bar = ft.Row(
        [
            ft.Text(f"Prep — Node {node.index}: {node.city}", size=FONT_SIZE_DISPLAY,
                    weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ft.Container(
                ft.Text(node.node_type.value.replace("_", " "), size=FONT_SIZE_CAPTION,
                        color=TEXT_PRIMARY),
                bgcolor=type_color, border_radius=CARD_RADIUS,
                padding=ft.Padding(left=8, right=8, top=2, bottom=2),
            ),
            weather_badge(weather=node.weather, size="sm"),
            ft.Container(expand=True),
            resources_holder,
            ft.OutlinedButton("← Trail", on_click=lambda _e: on_back()),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=SPACING_MD,
    )

    # --- bottom action row ------------------------------------------------------
    bottom = ft.Row(
        [
            ft.OutlinedButton("Auto-Place", on_click=lambda _e: (_auto_place(), _render())),
            ft.OutlinedButton("Reset", on_click=lambda _e: (_auto_place(), _render())),
            ft.Container(expand=True),
            msg_holder,
            ft.FilledButton("Start Combat ▶", on_click=_start_combat,
                            style=ft.ButtonStyle(bgcolor=ACCENT)),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=SPACING_MD,
    )

    # --- assembly ---------------------------------------------------------------
    left_col = ft.Column(
        [
            ft.Container(board_holder, alignment=ft.Alignment.CENTER),
            bench_holder,
        ],
        spacing=SPACING_MD, expand=True, scroll=ft.ScrollMode.AUTO,
    )
    right_col = ft.Column(
        [shop_holder, preview_holder, inspect_holder],
        spacing=SPACING_MD, width=320, scroll=ft.ScrollMode.AUTO,
    )
    body = ft.Column(
        [
            top_bar,
            ft.Divider(height=1, color=SURFACE_ELEVATED),
            ft.Row([left_col, right_col], spacing=SPACING_LG,
                   vertical_alignment=ft.CrossAxisAlignment.START, expand=True),
            bottom,
        ],
        spacing=SPACING_MD, expand=True,
    )
    root = ft.Container(bgcolor=BG, expand=True, padding=SPACING_XL, content=body)
    view = ft.View(route="/prep", controls=[root], padding=0)

    # Initial team layout: cap the field, auto-place into the default formation.
    _normalize_roster()
    _auto_place()
    _render()
    return view


def _chip(label: str, value: str, color: str) -> ft.Control:
    return ft.Container(
        ft.Row(
            [
                ft.Text(label, size=FONT_SIZE_CAPTION, color=TEXT_MUTED),
                ft.Text(value, size=FONT_SIZE_BODY, color=color,
                        weight=ft.FontWeight.BOLD),
            ],
            spacing=SPACING_XS, tight=True,
        ),
        bgcolor=SURFACE_ELEVATED, border_radius=CARD_RADIUS,
        padding=ft.Padding(left=10, right=10, top=4, bottom=4),
    )
