"""Combat engine subpackage (T20/T26 unified).

Re-exports CombatContext and run for external callers.
resolve_combat is the single public combat entry point — it delegates to the
new unified loop internally.

HARD RULE: combat/ may import effects.py, registries.py, events.py, status.py, stdlib.
           combat/ may NEVER import content modules (abilities/, items/, traits/, etc.).
"""

from src.game.combat.context import CombatContext, hex_distance
from src.game.combat.loop_new import run

# Backward compatibility: re-export everything from the legacy module
from src.game.combat.legacy import (  # noqa: F401
    resolve_combat,
    TICK_MS,
    ROUND_TICKS,
    ENERGY_THRESHOLD,
    MAX_TICKS,
    BOARD_WIDTH,
    BOARD_HEIGHT,
    HEX_DIRECTIONS,
    AUTO_STR_COEFF,
    AUTO_INT_COEFF,
    ABILITY_STR_COEFF,
    ABILITY_INT_COEFF,
    MITIGATION_CONSTANT,
    CRIT_MULTIPLIER,
    DMG_PHYSICAL,
    DMG_MAGICAL,
    DMG_TRUE,
    EVENT_MOVE,
    EVENT_ATTACK,
    EVENT_CAST,
    EVENT_DEATH,
    effective_as,
    effective_ms,
    effective_mr_tick,
    _next_step_toward,
    _select_target,
    _apply_hit,
    _mitigated_damage,
    _effective_mitigation,
    _assign_spawns,
    _opponents,
    _both_sides_alive,
    _resolve_movement,
    _resolve_action,
    _event_sort_key,
)

__all__ = [
    "CombatContext",
    "run",
    "hex_distance",
    "resolve_combat",
]
