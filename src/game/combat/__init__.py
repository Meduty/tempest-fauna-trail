"""Combat engine subpackage (T20/T26 unified).

`resolve_combat` is the single public combat entry point — it wires the
pipeline and delegates to the unified tick loop in `engine`.

HARD RULE: combat/ may import effects.py, registries.py, events.py, status.py,
           stdlib. combat/ may NEVER import content modules at module scope
           (abilities/, items/, traits/, …) — see resolve.py for the deferred
           pattern that keeps the boundary acyclic.
"""

from src.game.combat.context import CombatContext, hex_distance
from src.game.combat.engine import (  # noqa: F401
    run,
    TICK_MS,
    ROUND_TICKS,
    ENERGY_THRESHOLD,
    MAX_TICKS,
    BOARD_WIDTH,
    BOARD_HEIGHT,
    HEX_DIRECTIONS,
)
from src.game.combat.recorder import (  # noqa: F401
    EVENT_MOVE,
    EVENT_ATTACK,
    EVENT_CAST,
    EVENT_DEATH,
    EVENT_HEAL,
    EVENT_DOT,
    EVENT_STATUS,
    EVENT_STATUS_EXPIRE,
    EVENT_SPAWN,
    EVENT_DESPAWN,
)
from src.game.combat.resolve import resolve_combat
from src.game.combat.replay import (  # noqa: F401
    inspect_at_tick,
    PieceView,
    SlotView,
    StatusView,
)

__all__ = [
    "CombatContext",
    "run",
    "hex_distance",
    "resolve_combat",
    "inspect_at_tick",
    "PieceView",
    "SlotView",
    "StatusView",
    "TICK_MS",
    "ROUND_TICKS",
    "ENERGY_THRESHOLD",
    "MAX_TICKS",
    "BOARD_WIDTH",
    "BOARD_HEIGHT",
    "HEX_DIRECTIONS",
    "EVENT_MOVE",
    "EVENT_ATTACK",
    "EVENT_CAST",
    "EVENT_DEATH",
    "EVENT_HEAL",
    "EVENT_DOT",
    "EVENT_STATUS",
    "EVENT_STATUS_EXPIRE",
    "EVENT_SPAWN",
    "EVENT_DESPAWN",
]
