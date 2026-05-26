"""Boss encounter definitions (T21).

Public API:
  BOSS_DEFS           — dict[int, BossDef]  (stage index → definition)
  BossDef             — authored boss data
  BossCastEntry       — one element of a supporting cast
  BossEncounterResult — returned by encounter.generate_boss_encounter()
  get_boss_def(stage_index) → BossDef
"""

from .data import (
    BossCastEntry,
    BossDef,
    BossEncounterResult,
    BOSS_DEFS,
    get_boss_def,
)

__all__ = [
    "BossCastEntry",
    "BossDef",
    "BossEncounterResult",
    "BOSS_DEFS",
    "get_boss_def",
]
