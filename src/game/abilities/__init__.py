"""Abilities package (T20 + T30).

Importing this package triggers all @register decorators for abilities.
"""

from src.game.abilities import reference  # noqa: F401 — triggers @register decorators
from src.game.abilities import champions  # noqa: F401 — triggers @register decorators
from src.game.abilities import enemies  # noqa: F401 — triggers @register decorators
from src.game.abilities import bosses as _bosses  # noqa: F401 — triggers @register decorators
