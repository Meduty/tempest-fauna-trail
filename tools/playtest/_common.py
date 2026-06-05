"""Shared helpers for the playtest CLI tools.

Pure utility layer: id parsing, table formatting, default-team picker, and
the boss combat helper that composes the primitives `resolve_combat` cannot
(map effects).
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Iterable, Literal

from src.game.bosses.data import BossEncounterResult
from src.game.combat.context import CombatContext
from src.game.combat.engine import assign_spawns, run as run_combat
from src.game.combat.recorder import BattleResultRecorder
from src.game.content import (
    CHAMPION_ROSTER,
    ENEMY_ROSTER,
    get_champion,
    get_enemy,
)
from src.game.loadout import attach_map_effect, compile_loadout
from src.game.models import BattleResult, Champion, Enemy, WeatherState
from src.game.route import STAGES


# ---------------------------------------------------------------------------
# Argparse parsers (shared)
# ---------------------------------------------------------------------------


def parse_weather(raw: str) -> WeatherState:
    try:
        return WeatherState(raw.lower())
    except ValueError as exc:
        valid = ", ".join(w.value for w in WeatherState)
        raise argparse.ArgumentTypeError(
            f"Unknown weather {raw!r}. Expected one of: {valid}."
        ) from exc


def parse_champion_ids(raw: str) -> list[Champion]:
    if not raw:
        return []
    return [_lookup_champion(token.strip()) for token in raw.split(",") if token.strip()]


def parse_enemy_ids(raw: str) -> list[Enemy]:
    if not raw:
        return []
    return [_lookup_enemy(token.strip()) for token in raw.split(",") if token.strip()]


def _lookup_champion(champion_id: str) -> Champion:
    if champion_id not in CHAMPION_ROSTER:
        raise argparse.ArgumentTypeError(
            f"Unknown champion id {champion_id!r}. "
            f"Try `inspect --kind champion` to list valid ids."
        )
    return get_champion(champion_id)


def _lookup_enemy(enemy_id: str) -> Enemy:
    if enemy_id not in ENEMY_ROSTER:
        raise argparse.ArgumentTypeError(
            f"Unknown enemy id {enemy_id!r}. "
            f"Try `inspect --kind enemy` to list valid ids."
        )
    return get_enemy(enemy_id)


# ---------------------------------------------------------------------------
# Default team picker
# ---------------------------------------------------------------------------


_DEFAULT_TEAM_TIER_BY_STAGE: dict[int, int] = {
    1: 1,
    2: 2,
    3: 3,
    4: 4,
    5: 5,
    6: 6,
}


def default_team(stage_index: int = 1, size: int = 3) -> list[Champion]:
    """Pick a budget-appropriate stub team for a stage.

    Strategy: take champions at tier == stage's typical tier, spreading across
    affinities for variety. Deterministic — same inputs always return the
    same champions. Used by sim_run when `--team` is omitted.
    """
    tier = _DEFAULT_TEAM_TIER_BY_STAGE.get(stage_index, 1)
    pool = [c for c in CHAMPION_ROSTER.values() if c.tier == tier]
    pool.sort(key=lambda c: (c.affinity.value, c.id))
    if not pool:
        # Fallback — shouldn't happen with the shipped roster
        pool = sorted(CHAMPION_ROSTER.values(), key=lambda c: c.id)
    return pool[:size]


# ---------------------------------------------------------------------------
# Boss combat helper
# ---------------------------------------------------------------------------


def resolve_boss_combat(
    team: list[Champion],
    encounter: BossEncounterResult,
    weather: WeatherState,
    *,
    run_seed: int = 42,
    node_id: str = "",
) -> BattleResult:
    """Resolve a boss fight, attaching the encounter's map effect.

    `resolve_combat` cannot do this because it doesn't accept a map effect.
    This composes the same primitives manually.
    """
    enemies = encounter.all_enemies
    # compile_loadout assigns formation_index + load_order (V.34).
    pieces, bus, trait_activations = compile_loadout(team, enemies, weather, seed=run_seed)
    assign_spawns(pieces)

    recorder = BattleResultRecorder(pieces, weather, node_id, trait_activations)
    recorder.register(bus)

    ctx = CombatContext(pieces, bus, weather, seed=run_seed)
    if encounter.map_effect_id:
        attach_map_effect(encounter.map_effect_id, ctx, seed=run_seed)

    winner = run_combat(ctx, recorder)
    return recorder.build_result(winner)


# ---------------------------------------------------------------------------
# Table formatter
# ---------------------------------------------------------------------------


@dataclass
class Column:
    header: str
    width: int
    align: Literal["left", "right"] = "left"


def format_table(columns: list[Column], rows: Iterable[list[str]]) -> list[str]:
    """Render an aligned text table. Returns list of lines (no trailing \\n)."""
    def fmt_cell(value: str, col: Column) -> str:
        value = str(value)
        if len(value) > col.width:
            value = value[: col.width - 1] + "…"
        if col.align == "right":
            return value.rjust(col.width)
        return value.ljust(col.width)

    lines: list[str] = []
    header = "  ".join(fmt_cell(c.header, c) for c in columns)
    lines.append(header)
    lines.append("  ".join("-" * c.width for c in columns))
    for row in rows:
        cells = [fmt_cell(row[i] if i < len(row) else "", columns[i]) for i in range(len(columns))]
        lines.append("  ".join(cells))
    return lines


# ---------------------------------------------------------------------------
# Stage / node lookup
# ---------------------------------------------------------------------------


def stage_def(stage_index: int):
    """Return STAGES[stage_index - 1]; raises ArgumentTypeError on bad index."""
    if not 1 <= stage_index <= len(STAGES):
        raise argparse.ArgumentTypeError(
            f"Stage index {stage_index} out of range (1..{len(STAGES)})."
        )
    return STAGES[stage_index - 1]


def node_position_in_stage(stage_index: int, node_index: int) -> int:
    """Map a 1-based absolute node_index to a 0-based position inside the stage."""
    nodes_before = sum(len(STAGES[i].node_cities) for i in range(stage_index - 1))
    pos = node_index - nodes_before - 1
    stage = stage_def(stage_index)
    if not 0 <= pos < len(stage.node_cities):
        raise argparse.ArgumentTypeError(
            f"Node index {node_index} not in stage {stage_index} "
            f"(stage covers nodes {nodes_before + 1}..{nodes_before + len(stage.node_cities)})."
        )
    return pos


# ---------------------------------------------------------------------------
# Champion / enemy stat row formatter
# ---------------------------------------------------------------------------


CHAMPION_COLUMNS: list[Column] = [
    Column("id", 32),
    Column("name", 26),
    Column("affinity", 8),
    Column("role", 12),
    Column("intent", 7),
    Column("T/L", 5),
    Column("HP", 5, "right"),
    Column("STR", 4, "right"),
    Column("INT", 4, "right"),
    Column("AS", 4, "right"),
    Column("MS", 4, "right"),
    Column("MR", 4, "right"),
    Column("ARM", 4, "right"),
    Column("RES", 4, "right"),
    Column("RNG", 4, "right"),
]

ENEMY_COLUMNS = CHAMPION_COLUMNS  # same shape


def champion_row(c: Champion) -> list[str]:
    return [
        c.id,
        c.name,
        c.affinity.value,
        c.role,
        c.intent,
        f"{c.tier}/{c.level}",
        str(c.max_hp),
        str(c.strength),
        str(c.intelligence),
        str(c.attack_speed),
        str(c.move_speed),
        str(c.mana_regen),
        str(c.armor),
        str(c.resistance),
        str(c.attack_range),
    ]


def enemy_row(e: Enemy) -> list[str]:
    return [
        e.id,
        e.name,
        e.affinity.value,
        e.role,
        e.intent,
        f"{e.tier}/{e.level}",
        str(e.max_hp),
        str(e.strength),
        str(e.intelligence),
        str(e.attack_speed),
        str(e.move_speed),
        str(e.mana_regen),
        str(e.armor),
        str(e.resistance),
        str(e.attack_range),
    ]
