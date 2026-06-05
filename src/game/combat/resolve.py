"""Public combat entry point.

`resolve_combat` is a pure, deterministic function: identical inputs always
produce a byte-equal `BattleResult` (V.2). It wires the combat pipeline:
`compile_loadout` builds weather-modified Pieces, `engine.run` runs the tick
simulation, and `BattleResultRecorder` builds the result.

Weather Favor is folded into piece base stats at compile time; Affinity Clash
(the affinity damage triangle) is resolved per hit during damage application.
"""

from __future__ import annotations

from src.game.models import BattleResult, Champion, Enemy, WeatherState


def resolve_combat(
    team: list[Champion],
    enemies: list[Enemy],
    weather: WeatherState,
    *,
    node_id: str = "",
) -> BattleResult:
    """Resolve one battle from start to finish; pure and deterministic."""
    # Deferred imports keep the content↔combat boundary acyclic: loadout pulls
    # in the ability/passive registries, which must finish importing first.
    from src.game.combat.context import CombatContext
    from src.game.combat.engine import run as run_combat, assign_spawns
    from src.game.combat.recorder import BattleResultRecorder
    from src.game.loadout import compile_loadout

    # Build pieces with weather favor applied. compile_loadout assigns
    # formation_index (input order) + load_order (seeded, side-independent) — V.34.
    pieces, bus = compile_loadout(team, enemies, weather, seed=42)

    # Assign spawn positions.
    assign_spawns(pieces)

    # Wire the recorder to the event bus and run the loop.
    recorder = BattleResultRecorder(pieces, weather, node_id)
    recorder.register(bus)

    ctx = CombatContext(pieces, bus, weather, seed=42)
    winner = run_combat(ctx, recorder)

    return recorder.build_result(winner)
