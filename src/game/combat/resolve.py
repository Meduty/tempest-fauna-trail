"""Public combat entry point.

`resolve_combat` is a pure, deterministic function: identical inputs always
produce a byte-equal `BattleResult` (V.2). It wires the combat pipeline:
`compile_loadout` builds weather-modified Pieces, `engine.run` runs the tick
simulation, and `BattleResultRecorder` builds the result.

Weather Favor is folded into piece base stats at compile time; Affinity Clash
(the affinity damage triangle) is resolved per hit during damage application.
"""

from __future__ import annotations

from typing import Any

from src.game.models import BattleResult, Champion, Enemy, WeatherState


def resolve_combat(
    team: list[Champion],
    enemies: list[Enemy],
    weather: WeatherState,
    *,
    node_id: str = "",
    run_mods: Any = None,
) -> BattleResult:
    """Resolve one battle from start to finish; pure and deterministic.

    `run_mods` (a `RunModifiers`, T.31) threads active augments + quest state into
    `compile_loadout`. The `None` default leaves every non-augment caller —
    including every balance sim — byte-for-byte unchanged (V.2/V.18).
    """
    from src.game.combat.engine import run as run_combat

    ctx, recorder = build_combat(
        team, enemies, weather, run_mods=run_mods, node_id=node_id, with_recorder=True
    )
    winner = run_combat(ctx, recorder)
    return recorder.build_result(winner)


def resolve_boss_combat(
    team: list[Champion],
    enemies: list[Enemy],
    weather: WeatherState,
    *,
    map_effect_id: str = "",
    run_seed: int = 42,
    node_id: str = "",
    run_mods: Any = None,
) -> BattleResult:
    """Resolve a boss fight — the **single src-side boss entry** (V.59). Same
    primitives as `resolve_combat` plus a board map effect: `build_combat` →
    `attach_map_effect(map_effect_id)` when set → run → result.

    Takes a **`map_effect_id: str`** (never a `bosses/`-content type) so `combat/`
    stays content-import-free — the package HARD RULE; `attach_map_effect` is a
    deferred `loadout` import. Byte-identical to the former `tools/playtest/_common`
    version (V.2 — same primitives, order, default seed); `tools/` delegates here.
    `CombatReplay`/`inspect_at_tick` accept the same `map_effect_id` to replay it.
    """
    from src.game.combat.engine import run as run_combat
    from src.game.loadout import attach_map_effect

    ctx, recorder = build_combat(
        team, enemies, weather, run_mods=run_mods, node_id=node_id, seed=run_seed,
        with_recorder=True,
    )
    if map_effect_id:
        attach_map_effect(map_effect_id, ctx, seed=run_seed)
    winner = run_combat(ctx, recorder)
    return recorder.build_result(winner)


def build_combat(
    team: list[Champion],
    enemies: list[Enemy],
    weather: WeatherState,
    *,
    run_mods: Any = None,
    node_id: str = "",
    seed: int = 42,
    with_recorder: bool = True,
) -> tuple[Any, Any]:
    """Build the combat substrate (pieces + bus + context, optionally a wired
    recorder) up to — but not running — the tick loop. The **single** wiring path
    shared by `resolve_combat` (records a `BattleResult`), the replay
    `inspect_at_tick` (no recorder, reads live state), and `resolve_boss_combat`
    (attaches a map effect to `ctx` before running) — so none of them drift into
    parallel setups. Returns `(ctx, recorder|None)`.
    """
    # Deferred imports keep the content↔combat boundary acyclic: loadout pulls
    # in the ability/passive registries, which must finish importing first.
    from src.game.combat.context import CombatContext
    from src.game.combat.engine import assign_spawns
    from src.game.combat.recorder import BattleResultRecorder
    from src.game.loadout import compile_loadout

    # Build pieces with weather favor applied. compile_loadout assigns
    # formation_index (input order) + load_order (seeded, side-independent) — V.34.
    pieces, bus, trait_activations = compile_loadout(team, enemies, weather, seed=seed, run_mods=run_mods)

    # Assign spawn positions.
    assign_spawns(pieces)

    recorder = None
    if with_recorder:
        recorder = BattleResultRecorder(pieces, weather, node_id, trait_activations)
        recorder.register(bus)

    ctx = CombatContext(pieces, bus, weather, seed=seed)
    return ctx, recorder
