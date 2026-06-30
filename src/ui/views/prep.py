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
from src.game.content import CHAMPION_DEF_BY_ID, build_champion_at_level
from src.game.economy import (
    LEVEL_COPY_THRESHOLDS,
    MAX_LEVEL,
    champion_cost,
    is_max_rank,
    level_from_copies,
    rank_up_cost_amber,
    sell_champion,
    tempest_threshold,
    try_rank_up_with_amber,
)
from src.game.encounter import node_encounter
from src.game.inventory import equip_item, unequip_item
from src.game.describe import render_item
from src.game.items.base import BASE_COMPONENTS, SPIRIT_GEM
from src.game import augments as _augments  # noqa: F401 — populate AUGMENT_REGISTRY
from src.game.registries import AUGMENT_REGISTRY
from src.game.traits import preview_team_traits
from src.game.loadout import ALLIED_ZONE_MAX_Q, validate_team_positions
from src.game.models import Champion, Node, NodeType, Run, WeatherState
from src.game.shop import (
    RANK_TIER_WEIGHTS,
    buy_from_shop,
    refresh_shop,
    reroll_cost,
    reroll_shop,
    toggle_shop_freeze,
)
from src.game.weather_effects import (
    CombatModifier,
    RingRelation,
    combat_modifier,
    ring_relation,
)
from src.ui.combat_playback import CombatSession
from src.ui.components.board_geometry import BOARD_H, BOARD_W, COL_W, ROW_H, cell_xy
from src.ui.components.iconography import (
    affinity_marker,
    clash_legend,
    clash_marker,
    favor_tone,
    rich_tooltip,
)
from src.ui.components.infocard import (
    PieceInfo,
    infocard_abilities,
    infocard_header,
    infocard_stat_grid,
)
from src.ui.components.trait_synergies import trait_synergies_panel
from src.ui.components.weather_badge import weather_badge
from src.viz.affinity_clash_heatmap import build_affinity_clash_heatmap
from src.ui.theme import (
    ACCENT,
    AFFINITY_COLORS,
    BG,
    CARD_RADIUS,
    DANGER,
    FONT_SIZE_BODY,
    FONT_SIZE_CAPTION,
    FONT_SIZE_DISPLAY,
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


# Weather Favor presentation (V.5/T.2) — relation → (label, color-token name).
# Buffs reach strong/medium/weak; debuffs only medium/weak (no strong debuff).
_FAVOR_LABEL: dict[RingRelation, str] = {
    RingRelation.SELF: "buffed (strong)",
    RingRelation.PRIMARY_PREDATOR: "buffed (medium)",
    RingRelation.SECONDARY_PREDATOR: "buffed (weak)",
    RingRelation.SECONDARY_PREY: "debuffed (weak)",
    RingRelation.PRIMARY_PREY: "debuffed (medium)",
    RingRelation.NEUTRAL: "no effect",
}

# CombatModifier field → display label, in render order.
_MOD_FIELDS: tuple[tuple[str, str], ...] = (
    ("str_mult", "STR"), ("int_mult", "INT"), ("as_mult", "AS"),
    ("ms_mult", "MS"), ("mr_mult", "MR"), ("hp_mult", "HP"),
    ("armor_mult", "armor"), ("res_mult", "RES"), ("thr_mult", "threat"),
)


def _item_label(item_id: str) -> str:
    """snake_case item id → Title Case display (stopgap until the item render-layer
    lands authored names — see the deferred trait/item/augment text system)."""
    return item_id.replace("_", " ").title()


def _item_kind(item_id: str) -> str:
    """Classify an item id for display: ``component`` (raw, can still fuse),
    ``gem`` (Spirit Gem → emblem), or ``combined`` (terminal, won't fuse).

    Mirrors the combine rules in ``items.combine`` (B.34): only raw components
    (and Spirit Gem) are recipe inputs; everything else is a finished item."""
    if item_id in BASE_COMPONENTS:
        return "component"
    if item_id == SPIRIT_GEM:
        return "gem"
    return "combined"


def _favor_deltas(mod: CombatModifier) -> str:
    """Human summary of a CombatModifier's deviations (e.g. ``+30% HP, +30% RES``)."""
    parts: list[str] = []
    for field_name, label in _MOD_FIELDS:
        mult = getattr(mod, field_name)
        if abs(mult - 1.0) >= 0.005:
            parts.append(f"{(mult - 1.0) * 100:+.0f}% {label}")
    if mod.attack_range_delta:
        parts.append(f"{mod.attack_range_delta:+d} range")
    return ", ".join(parts)


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
    # team_positions: champion_id -> (q, r) board cell, **persisted on the Run** so
    # the formation survives Prep→Combat→Prep + Save&Exit. The board shows run.roster
    # (the deployable field, capped at tempest_rank); run.bench holds reserves.
    team_positions: dict[str, tuple[int, int]] = run.team_positions
    # `selected` = owned champ id (board/bench inspect); `shop_sel` = shop offer
    # champion id under preview. Mutually exclusive — selecting one clears the other.
    state: dict[str, object] = {"selected": None, "shop_sel": None}

    enc = node_encounter(run.seed, node, weather=node.weather)

    # Auto-reroll the shop on every Prep entry (V.75) — frozen slots persist across
    # phases (refresh_shop keeps them). Idempotent on re-entry of the same node
    # (deterministic roll, V.2). The view mutates the shop only through game/shop.
    refresh_shop(run)

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
        # If the target cell is occupied by another champion, relocate it. Reserve
        # the dragged unit's target cell *first* so the occupant can't be reassigned
        # back onto it (a board→board drag swaps into the dragged unit's old cell;
        # a bench drop sends the occupant to a different free cell, else the bench).
        occupant = next((cid for cid, c in team_positions.items() if c == cell), None)
        old = team_positions.get(champ_id)
        team_positions[champ_id] = cell
        if occupant is not None and occupant != champ_id:
            if old is not None:
                team_positions[occupant] = old
            else:
                free = _free_cell()  # target cell now reserved → never returned
                if free is not None:
                    team_positions[occupant] = free
                else:
                    occ = _champ_by_id(occupant)
                    if occ is not None and occ in run.roster:
                        run.roster.remove(occ)
                        run.bench.append(occ)
                    team_positions.pop(occupant, None)
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

    def _buy_by_id(cid: str) -> None:
        """Buy from the first shop slot offering ``cid`` (preview-panel Buy)."""
        slot = next((i for i, c in enumerate(run.shop_offers) if c == cid), None)
        if slot is None:
            _flash("That offer is gone.")
            return
        if buy_from_shop(run, slot):
            state["shop_sel"] = None
            _after_economy()
        else:
            _flash("Can't buy (unaffordable, maxed, or empty slot).")

    def _reroll() -> None:
        if not reroll_shop(run):
            _flash("Can't reroll (not enough Amber).")
        _render()

    def _toggle_freeze(slot: int) -> None:
        toggle_shop_freeze(run, slot)
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

    # --- items (equip seam, T.23b — all through game/inventory.py, V.63) --------
    def _equip(item_id: str) -> None:
        champ = _champ_by_id(state["selected"]) if isinstance(state["selected"], str) else None
        if champ is None:
            _flash("Select a champion first.")
            return
        if equip_item(run, champ, item_id):
            _render()
        else:
            _flash("Can't equip (no free slot and no combine).")

    def _unequip(item_id: str) -> None:
        champ = _champ_by_id(state["selected"]) if isinstance(state["selected"], str) else None
        if champ is not None and unequip_item(run, champ, item_id):
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

    # --- shop (top strip — horizontal 5-slot rail) -----------------------------
    def _shop_slot_card(slot: int, cid: str | None) -> ft.Control:
        if cid is None:
            return ft.Container(
                ft.Text("— sold —", size=FONT_SIZE_CAPTION, color=TEXT_MUTED,
                        text_align=ft.TextAlign.CENTER),
                width=140, height=84, alignment=ft.Alignment.CENTER,
                bgcolor=SURFACE_ELEVATED, border_radius=CARD_RADIUS,
            )
        cdef = CHAMPION_DEF_BY_ID.get(cid)
        if cdef is None:
            return ft.Container(width=140, height=84)
        cost = champion_cost(cdef.tier)
        affordable = run.amber >= cost
        owned = run.champion_copies.get(cid, 0)
        frozen = slot < len(run.shop_frozen) and run.shop_frozen[slot]
        border_color = ACCENT if state["shop_sel"] == cid else (ACCENT if frozen else None)
        return ft.Container(
            ft.Column(
                [
                    ft.Row([
                        affinity_marker(cdef.affinity, size=14),
                        ft.Text(cdef.name, size=FONT_SIZE_CAPTION, color=TEXT_PRIMARY,
                                expand=True, no_wrap=True),
                        ft.Container(
                            ft.Text("❄" if frozen else "✛", size=12,
                                    color=ACCENT if frozen else TEXT_MUTED),
                            on_click=lambda _e, s=slot: _toggle_freeze(s),
                            tooltip="Unfreeze slot" if frozen else "Freeze slot (kept on reroll)",
                            padding=2,
                        ),
                    ], spacing=SPACING_XS),
                    ft.Row([
                        ft.Text(f"T{cdef.tier}", size=FONT_SIZE_CAPTION, color=TEXT_MUTED),
                        *([ft.Text(f"●{owned}", size=FONT_SIZE_CAPTION, color=ACCENT,
                                   tooltip="copies owned (3 combine → next level)")] if owned else []),
                        ft.Container(expand=True),
                    ], spacing=SPACING_XS),
                    ft.FilledButton(
                        f"Buy {cost}⨀", width=124, height=28,
                        on_click=lambda _e, s=slot: _buy(s),
                        disabled=not affordable,
                        style=ft.ButtonStyle(bgcolor=ACCENT if affordable else SURFACE_ELEVATED),
                    ),
                ],
                spacing=4, tight=True,
            ),
            width=140, height=84,
            bgcolor=SURFACE_ELEVATED, border_radius=CARD_RADIUS,
            padding=ft.Padding(left=SPACING_SM, right=SPACING_SM, top=6, bottom=6),
            border=ft.Border.all(2 if frozen else 1, border_color) if border_color else None,
            on_click=lambda _e, c=cid: _select_shop(c),
            tooltip="Inspect — role, abilities, stats",
        )

    def _build_shop() -> ft.Control:
        header = ft.Row([
            ft.Text("Shop", size=FONT_SIZE_H3, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
            ft.Text(f"Rank {run.tempest_rank} odds", size=FONT_SIZE_CAPTION, color=TEXT_MUTED),
            ft.Container(expand=True),
            _chip("Amber", f"{run.amber}", WARNING),
            ft.OutlinedButton(
                f"Reroll ({reroll_cost(run.shop_rerolls)}⨀)",
                on_click=lambda _e: _reroll(),
            ),
        ], spacing=SPACING_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        rail = ft.Row(
            [_shop_slot_card(slot, cid) for slot, cid in enumerate(run.shop_offers)],
            spacing=SPACING_SM, scroll=ft.ScrollMode.AUTO,
        )
        return ft.Column([header, rail], spacing=SPACING_SM)

    # --- enemy preview ----------------------------------------------------------
    def _build_enemy_preview() -> ft.Control:
        if node.node_type in _NO_FIGHT:
            return ft.Text("No fight here.", size=FONT_SIZE_CAPTION, color=TEXT_MUTED)
        team_affinities = {c.affinity for c in run.roster}
        rows: list[ft.Control] = []
        for e in enc.enemies[:10]:
            # Affinity clash hint: the strongest relation any team affinity has to
            # this enemy (predator ▲ green, prey ▼ red, neutral · muted).
            best_rel = RingRelation.NEUTRAL
            for aff in team_affinities:
                rel = ring_relation(aff, e.affinity)
                if rel in (RingRelation.PRIMARY_PREDATOR, RingRelation.SECONDARY_PREDATOR):
                    best_rel = rel
                    break
                if rel in (RingRelation.PRIMARY_PREY, RingRelation.SECONDARY_PREY):
                    best_rel = rel
            hint, hint_color = clash_marker(best_rel)
            rows.append(
                ft.Row(
                    [
                        affinity_marker(e.affinity, size=13),
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
            [ft.Row([ft.Text(header, size=FONT_SIZE_H3, color=TEXT_PRIMARY,
                             weight=ft.FontWeight.BOLD, expand=True),
                     clash_legend()],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER)] + rows,
            spacing=SPACING_XS,
        )

    # --- augments panel (T.31) -------------------------------------------------
    def _build_augments() -> ft.Control:
        rows: list[ft.Control] = [
            ft.Text("Augments", size=FONT_SIZE_H3, color=TEXT_PRIMARY,
                    weight=ft.FontWeight.BOLD),
        ]
        if not run.active_augments:
            rows.append(ft.Text("None yet — earned at Augment nodes.",
                                size=FONT_SIZE_CAPTION, color=TEXT_MUTED))
        for aid in run.active_augments:
            aug = AUGMENT_REGISTRY.get(aid)
            name = aug.name if aug is not None else aid
            blurb = aug.blurb if aug is not None else ""
            rows.append(ft.Container(
                ft.Text(name, size=11, color=TEXT_PRIMARY, no_wrap=True),
                bgcolor=SURFACE_ELEVATED, border_radius=CARD_RADIUS,
                padding=ft.Padding(left=8, right=8, top=3, bottom=3),
                tooltip=blurb or None,
            ))
        return ft.Column(rows, spacing=SPACING_XS)

    # --- traits panel (T.28a) --------------------------------------------------
    def _build_traits() -> ft.Control:
        """Live trait synergies for the **placed** team (preview_team_traits, V.21).
        Active synergies read prominently, dormant ones greyed (TFT-style) — via
        the shared ``trait_synergies_panel`` component (also used by Combat)."""
        placed = [c for c in run.roster if c.id in team_positions]
        # Augment Crest/Crown trait bonus (V.21) — match what combat will clear.
        bonus = run.augment_state.get("trait_bonus")
        previews = preview_team_traits(
            placed, board_cap=len(placed), bonus_counts=bonus) if placed else []
        return trait_synergies_panel(previews)

    # --- items bench (T.23b) — inventory components, click to equip on selected -
    def _build_items() -> ft.Control:
        rows: list[ft.Control] = [
            ft.Text("Items", size=FONT_SIZE_H3, color=TEXT_PRIMARY,
                    weight=ft.FontWeight.BOLD),
        ]
        inv = [(iid, n) for iid, n in run.inventory.items() if n > 0]
        if not inv:
            rows.append(ft.Text("No components — won at Reward nodes.",
                                size=FONT_SIZE_CAPTION, color=TEXT_MUTED))
        else:
            sel = isinstance(state["selected"], str) and _champ_by_id(state["selected"]) is not None
            rows.append(ft.Text(
                "Click to equip on selected unit." if sel else "Select a unit to equip.",
                size=10, color=TEXT_MUTED))
            rows.append(ft.Row(
                [_item_chip(iid, equipped=False, count=n) for iid, n in inv],
                spacing=SPACING_XS, wrap=True,
            ))
        return ft.Column(rows, spacing=SPACING_XS)

    # --- weather favor panel (T.2) ---------------------------------------------
    def _build_weather_panel() -> ft.Control:
        """The upcoming-fight weather + how it buffs/debuffs each affinity.

        Combat always uses ``node.weather`` (V.2/V.66). For each affinity we read
        ``combat_modifier(affinity, node.weather)`` — the same Weather Favor the
        engine applies at init — and summarize its stat deltas. CLEAR is inert.
        Affinities the team fields are marked so the player sees their own stakes.
        """
        w = node.weather
        team_affs = {c.affinity for c in run.roster}
        rows: list[ft.Control] = [
            ft.Row([
                ft.Text("Combat weather", size=FONT_SIZE_H3, color=TEXT_PRIMARY,
                        weight=ft.FontWeight.BOLD),
                weather_badge(weather=w, size="sm"),
            ], spacing=SPACING_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ]
        if w == WeatherState.CLEAR:
            rows.append(ft.Text("Clear — no affinity favored.", size=FONT_SIZE_CAPTION,
                                color=TEXT_MUTED))
            return ft.Column(rows, spacing=SPACING_XS)
        # Order: strongest buff → strongest debuff, by ring relation to the weather.
        _order = [RingRelation.SELF, RingRelation.PRIMARY_PREDATOR,
                  RingRelation.SECONDARY_PREDATOR, RingRelation.SECONDARY_PREY,
                  RingRelation.PRIMARY_PREY]
        affs = [a for a in WeatherState if a != WeatherState.CLEAR]
        affs.sort(key=lambda a: _order.index(ring_relation(a, w)))
        for aff in affs:
            rel = ring_relation(aff, w)
            mod = combat_modifier(aff, w)
            deltas = _favor_deltas(mod)
            tone = favor_tone(rel)
            mine = aff in team_affs
            # Header: affinity glyph + a tone-tinted favor badge; "◀ you" flags own stakes.
            header = ft.Row([
                affinity_marker(aff, size=13),
                ft.Text(aff.value, size=11, color=TEXT_PRIMARY, no_wrap=True,
                        weight=ft.FontWeight.BOLD),
                ft.Container(
                    ft.Text(_FAVOR_LABEL[rel], size=9, color=tone, no_wrap=True),
                    bgcolor=ft.Colors.with_opacity(0.15, tone),
                    border_radius=CARD_RADIUS,
                    padding=ft.Padding(left=6, right=6, top=1, bottom=1),
                ),
                ft.Container(expand=True),
                *([ft.Text("◀ you", size=10, color=ACCENT,
                           weight=ft.FontWeight.BOLD)] if mine else []),
            ], spacing=SPACING_XS, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            # Stat deltas as discrete chips — size to content, never char-wrap.
            chips = [
                ft.Container(
                    ft.Text(part, size=10, color=tone, no_wrap=True),
                    bgcolor=SURFACE,
                    border_radius=CARD_RADIUS,
                    padding=ft.Padding(left=5, right=5, top=1, bottom=1),
                )
                for part in (deltas.split(", ") if deltas else [])
            ] or [ft.Text("—", size=10, color=TEXT_MUTED)]
            rows.append(ft.Container(
                ft.Column([
                    header,
                    ft.Row(chips, spacing=4, wrap=True, run_spacing=4),
                ], spacing=4),
                bgcolor=SURFACE_ELEVATED,
                border=ft.Border(left=ft.BorderSide(2, tone)),
                border_radius=CARD_RADIUS,
                padding=ft.Padding(left=8, right=8, top=5, bottom=5),
            ))
        return ft.Column(rows, spacing=SPACING_XS)

    # --- affinity-clash heatmap (T.2 viz) --------------------------------------
    def _build_clash_heatmap() -> ft.Control:
        """The Affinity Clash damage triangle (per-hit `damage_modifier`) as a
        colored matrix. The team's affinities accent their attacker rows so the
        player reads their own damage stakes. Static rule — independent of the
        node weather (which the separate Weather Favor panel covers)."""
        team_affs = {c.affinity for c in run.roster}
        return build_affinity_clash_heatmap(highlight=team_affs)

    # --- shop tier-odds panel (SPEC §D.15 / §V.20) -----------------------------
    def _tier_pct(rank: int) -> list[tuple[int, float]]:
        """Normalized per-tier draw probability at a Tempest rank (weights → %)."""
        weights = RANK_TIER_WEIGHTS.get(rank, {})
        total = sum(weights.values()) or 1.0
        return [(t, weights[t] / total * 100.0) for t in sorted(weights)]

    def _odds_column(rank: int, title: str, *, dim: bool = False) -> ft.Control:
        head_color = TEXT_MUTED if dim else TEXT_PRIMARY
        bars: list[ft.Control] = [
            ft.Text(title, size=11, color=head_color, weight=ft.FontWeight.BOLD),
        ]
        for tier, pct in _tier_pct(rank):
            bars.append(ft.Row([
                ft.Text(f"T{tier}", size=10, color=TEXT_MUTED, width=22),
                ft.Container(
                    width=max(2.0, pct * 1.1), height=7, border_radius=3,
                    bgcolor=ft.Colors.with_opacity(0.45 if dim else 1.0, ACCENT),
                ),
                ft.Text(f"{pct:.0f}%", size=10, color=head_color),
            ], spacing=SPACING_XS, vertical_alignment=ft.CrossAxisAlignment.CENTER))
        return ft.Column(bars, spacing=2, expand=True)

    def _build_shop_odds() -> ft.Control:
        """Shop tier-probability distribution at the current Tempest rank.

        Tier odds are gated by **Tempest rank** (``RANK_TIER_WEIGHTS``, V.20) —
        ranking up both widens the team cap *and* lifts/widens the tier band.
        Showing the next rank beside the current one quantifies exactly what a
        rank-up buys, so the player can judge whether the Amber rush is worth it.
        """
        rank = run.tempest_rank
        cols: list[ft.Control] = [_odds_column(rank, f"Rank {rank} (now)")]
        if (rank + 1) in RANK_TIER_WEIGHTS:
            cols.append(_odds_column(rank + 1, f"Rank {rank + 1} (next)", dim=True))
        return ft.Column([
            ft.Text("Shop tier odds", size=FONT_SIZE_H3, color=TEXT_PRIMARY,
                    weight=ft.FontWeight.BOLD),
            ft.Row(cols, spacing=SPACING_MD,
                   vertical_alignment=ft.CrossAxisAlignment.START),
            ft.Text("Odds follow your Tempest rank — ranking up widens the team cap "
                    "and lifts the tier band shown here.",
                    size=10, color=TEXT_MUTED),
        ], spacing=SPACING_XS)

    # --- stat inspect (tooltip panel) ------------------------------------------
    def _item_chip(item_id: str, *, equipped: bool, count: int = 0) -> ft.Control:
        kind = _item_kind(item_id)
        # Authored name + blurb + derived stat line via the shared render-layer
        # (T.41a/V.78); _item_label is a defensive fallback (every registered item
        # has ITEM_META, V.78).
        rendered = render_item(item_id)
        label = rendered.name if rendered is not None else _item_label(item_id)
        if count > 1:
            label = f"{label} ×{count}"
        # Kind drives colour + a marker so a raw component (can still fuse) reads
        # differently from a finished combined item (terminal). See _item_kind.
        marker, marker_color, kind_tip = {
            "component": ("◆", ACCENT, "Raw component — equip a 2nd raw component "
                          "on this unit to fuse them."),
            "gem": ("✧", WARNING, "Spirit Gem — fuse with a component to craft an emblem."),
            "combined": ("✦", SUCCESS, "Combined item — final, won't fuse further."),
        }[kind]
        action_tip = "Click to unequip." if equipped else "Click to equip on selected unit."
        # Tooltip: name · stat line — blurb, then the kind + action hint.
        desc_lines: list[str] = []
        if rendered is not None:
            head = rendered.name
            if rendered.stat_line:
                head = f"{head} · {rendered.stat_line}"
            desc_lines.append(head)
            if rendered.text:
                desc_lines.append(rendered.text)
        desc_lines.append(f"{kind_tip} {action_tip}")
        return ft.Container(
            ft.Row(
                [
                    ft.Text(marker, size=10, color=marker_color),
                    ft.Text(label, size=10, color=TEXT_PRIMARY),
                    ft.Text("×" if equipped else "+", size=10,
                            color=DANGER if equipped else SUCCESS,
                            weight=ft.FontWeight.BOLD),
                ],
                spacing=4, tight=True,
            ),
            bgcolor=SURFACE_ELEVATED, border_radius=CARD_RADIUS,
            border=ft.Border.all(1, marker_color) if kind != "component" else None,
            padding=ft.Padding(left=6, right=6, top=2, bottom=2),
            tooltip=rich_tooltip("\n".join(desc_lines), tone=marker_color),
            on_click=(lambda _e, i=item_id: _unequip(i)) if equipped
            else (lambda _e, i=item_id: _equip(i)),
        )

    def _champ_info(champ: Champion) -> PieceInfo:
        """Normalize a `Champion` into the shared `PieceInfo` the infocard core
        consumes (V.82). Stats are pre-formatted here; numbers render against
        `champ` (Champion exposes `.stat()`, V.38)."""
        rc = f" [{champ.role_code}]" if champ.role_code else ""
        return PieceInfo(
            name=champ.name,
            affinity=champ.affinity,
            role=champ.role,
            traits=tuple(champ.traits),
            primary_stats=(("HP", f"{champ.max_hp}"), ("STR", f"{champ.strength}"),
                           ("INT", f"{champ.intelligence}"),
                           ("AS", f"{champ.attack_speed:.1f}"),
                           ("range", f"{champ.attack_range}")),
            premium_stats=(("armor", f"{champ.armor}"), ("res", f"{champ.resistance}"),
                           ("MS", f"{champ.move_speed}"), ("MR", f"{champ.mana_regen}"),
                           ("crit", f"{champ.crit_chance * 100:.0f}%")),
            actives=tuple(champ.active_abilities),
            passive=champ.passive_ability or "",
            stat_src=champ,
            subtitle=f"{champ.affinity.value} · {champ.role}{rc} · L{champ.level} T{champ.tier}",
        )

    def _champ_header(champ: Champion) -> list[ft.Control]:
        """Shared identity header (role glyph + name + affinity/trait cluster +
        subtitle, V.82) plus Prep's copy-level line underneath."""
        return [infocard_header(_champ_info(champ)), _level_line(champ.id)]

    def _traits_chips(champ: Champion) -> list[ft.Control]:
        """Trait tags as chips (Kinship/Calling + any authored tags). Shown in the
        shop preview + owned inspect so the player can read synergies pre-buy."""
        if not champ.traits:
            return []
        chips = [
            ft.Container(
                ft.Text(t, size=10, color=TEXT_PRIMARY),
                bgcolor=SURFACE_ELEVATED, border_radius=CARD_RADIUS,
                padding=ft.Padding(left=6, right=6, top=2, bottom=2),
            )
            for t in champ.traits
        ]
        return [ft.Row(chips, spacing=SPACING_XS, wrap=True)]

    def _level_line(cid: str) -> ft.Control:
        """Copy-combine progress (3 copies → L2, 9 → L3). Buying duplicates of a
        champion auto-levels it (TFT-style); this line surfaces that progress."""
        copies = run.champion_copies.get(cid, 0)
        if copies >= LEVEL_COPY_THRESHOLDS[-1]:
            return ft.Text(f"★ L{MAX_LEVEL} maxed · {copies}/{copies} copies",
                           size=10, color=WARNING)
        nxt = next(t for t in LEVEL_COPY_THRESHOLDS if t > copies)
        nxt_lvl = level_from_copies(nxt)
        if copies == 0:
            txt = f"not owned · {nxt} copies → L{nxt_lvl}"
        else:
            lvl = level_from_copies(copies)
            txt = f"L{lvl} · {copies}/{nxt} copies → L{nxt_lvl}"
        return ft.Text(txt, size=10, color=ACCENT)

    def _stat_grid(champ: Champion) -> ft.Control:
        return infocard_stat_grid(_champ_info(champ))

    def _ability_block(champ: Champion) -> list[ft.Control]:
        """Actives + passive via the shared core (name + inline-iconed blurb +
        formula, V.82). Numbers render against ``champ`` (V.38)."""
        return infocard_abilities(_champ_info(champ))

    def _build_shop_preview(cid: str) -> ft.Control:
        cdef = CHAMPION_DEF_BY_ID.get(cid)
        if cdef is None:
            return ft.Text("Unknown champion.", size=FONT_SIZE_CAPTION, color=TEXT_MUTED)
        champ = build_champion_at_level(cid, 1)   # read-only stat/ability sheet
        cost = champion_cost(cdef.tier)
        affordable = run.amber >= cost
        return ft.Column(
            [
                ft.Text("Shop preview", size=10, color=TEXT_MUTED),
                *_champ_header(champ),
                *_traits_chips(champ),
                _stat_grid(champ),
                ft.Divider(height=8, color=SURFACE_ELEVATED),
                *_ability_block(champ),
                ft.Container(height=SPACING_XS),
                ft.FilledButton(
                    f"Buy {cost}⨀",
                    on_click=lambda _e, c=cid: _buy_by_id(c),
                    disabled=not affordable,
                    style=ft.ButtonStyle(bgcolor=ACCENT if affordable else SURFACE_ELEVATED),
                ),
            ],
            spacing=SPACING_XS, scroll=ft.ScrollMode.AUTO,
        )

    def _build_inspect() -> ft.Control:
        shop_cid = state["shop_sel"]
        if isinstance(shop_cid, str):
            return _build_shop_preview(shop_cid)
        cid = state["selected"]
        champ = _champ_by_id(cid) if isinstance(cid, str) else None
        if champ is None:
            return ft.Text("Tap a champion (board, bench, or shop) to inspect.",
                           size=FONT_SIZE_CAPTION, color=TEXT_MUTED)
        # Raw sheet + a couple of derived rates (read straight off the Champion).
        rows: list[ft.Control] = [*_champ_header(champ), *_traits_chips(champ),
                                  _stat_grid(champ)]
        # Abilities — actives + passive, live-rendered (T.34/V.38).
        rows.append(ft.Divider(height=8, color=SURFACE_ELEVATED))
        rows.extend(_ability_block(champ))
        # Equipped items — unequip on click (T.23b). The inventory **bench** lives
        # in the left Items panel (click a component there to equip onto this unit).
        rows.append(ft.Divider(height=8, color=SURFACE_ELEVATED))
        rows.append(ft.Text(f"Items ({len(champ.items)}/3)", size=11, color=TEXT_MUTED))
        if champ.items:
            rows.append(ft.Row([_item_chip(i, equipped=True) for i in champ.items],
                               spacing=SPACING_XS, wrap=True))
        else:
            rows.append(ft.Text("(none equipped)", size=11, color=TEXT_MUTED))
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
        state["shop_sel"] = None
        _render()

    def _select_shop(cid: str) -> None:
        state["shop_sel"] = cid
        state["selected"] = None
        _render()

    # --- holders + render -------------------------------------------------------
    def _panel() -> ft.Container:
        return ft.Container(bgcolor=SURFACE, border_radius=CARD_RADIUS, padding=SPACING_MD)

    board_holder = ft.Container()
    bench_holder = ft.Container()
    shop_holder = _panel()
    odds_holder = _panel()
    weather_holder = _panel()
    clash_holder = _panel()
    augments_holder = _panel()
    traits_holder = _panel()
    items_holder = _panel()
    preview_holder = _panel()
    inspect_holder = ft.Container(bgcolor=SURFACE, border_radius=CARD_RADIUS,
                                  padding=SPACING_MD)
    resources_holder = ft.Row(spacing=SPACING_SM)

    def _resources() -> list[ft.Control]:
        controls: list[ft.Control] = [
            _chip("Amber", f"{run.amber}", WARNING),
            _chip("Rank", f"{run.tempest_rank}", ACCENT),
            _chip("Field", f"{len(run.roster)}/{_cap()}", TEXT_PRIMARY),
        ]
        if is_max_rank(run.tempest_rank):
            controls.append(_chip("Tempest", "MAX", TEXT_MUTED))
            controls.append(ft.OutlinedButton("Rank Up", disabled=True))
        else:
            need = tempest_threshold(run.tempest_rank)
            cost = rank_up_cost_amber(run.tempest, run.tempest_rank)
            controls.append(_chip("Tempest", f"{run.tempest}/{need}", ACCENT))
            controls.append(ft.OutlinedButton(
                f"Rank Up ({cost}⨀)",
                on_click=lambda _e: _rank_up(),
                disabled=cost > run.amber,
                tooltip=(f"Rank {run.tempest_rank}→{run.tempest_rank + 1}: needs {need} "
                         f"Tempest (have {run.tempest}). Pay {cost} Amber to finish now "
                         f"(1 Amber = 1 Tempest)."),
            ))
        return controls

    def _render() -> None:
        board_holder.content = _build_board()
        bench_holder.content = _build_bench()
        shop_holder.content = _build_shop()
        odds_holder.content = _build_shop_odds()
        weather_holder.content = _build_weather_panel()
        clash_holder.content = _build_clash_heatmap()
        augments_holder.content = _build_augments()
        traits_holder.content = _build_traits()
        items_holder.content = _build_items()
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

    # --- assembly (TFT-style: shop on top · left info · center board · right sheet)
    # Left rail — weather + synergies + augments + item bench + shop odds.
    left_col = ft.Column(
        [weather_holder, clash_holder, traits_holder, augments_holder,
         items_holder, odds_holder],
        spacing=SPACING_MD, width=250, scroll=ft.ScrollMode.AUTO,
    )
    # Center — the hex board (the "map"), the bench below it, then the actions.
    center_col = ft.Column(
        [
            ft.Container(board_holder, alignment=ft.Alignment.CENTER),
            bench_holder,
            bottom,
        ],
        spacing=SPACING_MD, expand=True,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        scroll=ft.ScrollMode.AUTO,
    )
    # Right — the champion sheet (tooltips) + the deterministic enemy preview.
    right_col = ft.Column(
        [inspect_holder, preview_holder],
        spacing=SPACING_MD, width=300, scroll=ft.ScrollMode.AUTO,
    )
    body = ft.Column(
        [
            top_bar,
            ft.Divider(height=1, color=SURFACE_ELEVATED),
            shop_holder,
            ft.Row([left_col, center_col, right_col], spacing=SPACING_LG,
                   vertical_alignment=ft.CrossAxisAlignment.START, expand=True),
        ],
        spacing=SPACING_MD, expand=True,
    )
    root = ft.Container(bgcolor=BG, expand=True, padding=SPACING_XL, content=body)
    view = ft.View(route="/prep", controls=[root], padding=0)

    # Initial team layout: cap the field, then **restore the persisted formation**
    # (run.team_positions). First-ever Prep entry has none → default auto-place;
    # otherwise prune stale ids + fill any newly-added champions (V.2 packing).
    _normalize_roster()
    if not team_positions:
        _auto_place()
    else:
        _ensure_placed()
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
