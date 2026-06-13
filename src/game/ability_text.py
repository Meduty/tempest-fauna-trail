"""Ability description renderer (T.34) — pure, no Flet, no I/O (V.1).

Turns an ``AbilityMeta`` + a render *source* into a ``RenderedAbility`` with a
player-facing ``text`` (blurb with ``{label}`` tokens replaced by live numbers)
and a ``formula`` (one human-readable line per ``ScalingTerm``). The source is
**structurally typed**: any object exposing ``.stat(name) -> float`` — a live
``Piece`` (combat, with modifiers) or a base ``Champion``/``Enemy`` (roster
sheet, via their ``.stat()`` adapters). One call serves both UI contexts.

Numbers come from ``ScalingTerm.eval`` which delegates to the engine's
``_eval_scaling`` (source-of-truth B, V.38) — the tooltip number is exactly the
number the handler computes.

``TICKS_PER_SECOND = 100`` is the single source for the ``100 ticks = 1 second``
display convention (V.39): mechanics stay in ticks, this module (and ``ui/``,
which imports the constant from here) is the only place ticks become seconds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.game.registries import AbilityMeta, ScalingTerm

# V.39 — canonical display convention. Ticks in code; seconds only here + ui/.
TICKS_PER_SECOND = 100

# Canonical stat name -> short UPPER label for formula pretty-printing.
# Inverse of registries._STAT_ALIASES plus the long names that have no alias.
_STAT_SHORT: dict[str, str] = {
    "strength": "STR",
    "intelligence": "INT",
    "attack_speed": "AS",
    "move_speed": "MS",
    "mana_regen": "MR",
    "armor": "ARM",
    "resistance": "RES",
    "penetration": "PEN",
    "penetration_pct": "PEN%",
    "max_hp": "HP",
    "attack_range": "RNG",
    "crit_chance": "CRIT",
}

_ALIASES: dict[str, str] = {
    "str": "strength",
    "int": "intelligence",
    "atk": "attack_speed",
    "spd": "move_speed",
    "mr": "mana_regen",
    "arm": "armor",
    "res": "resistance",
    "pen": "penetration",
}


@dataclass(frozen=True)
class RenderedAbility:
    """A rendered ability tooltip — pure data, no UI dependency."""

    name: str
    text: str                       # blurb with {tokens} replaced by live numbers
    formula: str                    # one line per term, "267 = 80 + INT×2.2 (INT 85)"
    tags: tuple[str, ...]


def ticks_to_s(ticks: float) -> str:
    """Format a tick count as seconds (V.39). Trims a trailing ``.0``.

    ``ticks_to_s(200) -> "2"``; ``ticks_to_s(150) -> "1.5"``.
    """
    secs = ticks / TICKS_PER_SECOND
    if secs == int(secs):
        return str(int(secs))
    return f"{secs:g}"


def _short(stat_name: str) -> str:
    canon = _ALIASES.get(stat_name, stat_name)
    return _STAT_SHORT.get(canon, canon.upper())


def _format_scaling(term: ScalingTerm, source: object) -> str:
    """Pretty-print a term's scaling string: ``base + STAT×coeff (STAT val)``.

    Mirrors ``_eval_scaling``'s grammar (split on ``+``, ``*`` per part).
    """
    pieces: list[str] = []
    stat_notes: list[str] = []
    if term.base:
        pieces.append(f"{term.base:g}")
    expr = term.scaling.replace("-", "+-") if term.scaling else ""
    for part in expr.split("+"):
        part = part.strip()
        if not part or "*" not in part:
            continue
        stat_name, coeff = part.split("*", 1)
        stat_name = stat_name.strip()
        short = _short(stat_name)
        pieces.append(f"{short}×{float(coeff.strip()):g}")
        canon = _ALIASES.get(stat_name, stat_name)
        val = source.stat(canon) if hasattr(source, "stat") else 0.0
        stat_notes.append(f"{short} {val:g}")
    rhs = " + ".join(pieces) if pieces else "0"
    note = f"  ({', '.join(stat_notes)})" if stat_notes else ""
    return f"{round(term.eval(source))} = {rhs}{note}"


def render(meta: AbilityMeta, source: object) -> RenderedAbility:
    """Render ``meta`` against ``source`` (any object with ``.stat(name)``)."""
    values = {t.label: round(t.eval(source)) for t in meta.terms}

    def _sub(match: re.Match) -> str:
        key = match.group(1)
        return str(values.get(key, match.group(0)))

    full = meta.blurb
    if meta.clauses:
        full = full + " " + " ".join(c.text for c in meta.clauses)
    text = re.sub(r"\{(\w+)\}", _sub, full)

    formula = "\n".join(_format_scaling(t, source) for t in meta.terms)
    return RenderedAbility(name=meta.name, text=text, formula=formula, tags=meta.tags)


def render_for(ability_id: str, source: object) -> RenderedAbility | None:
    """Look up ``ability_id`` in ``ABILITY_META`` and render it, or ``None``."""
    from src.game.registries import ABILITY_META

    meta = ABILITY_META.get(ability_id)
    if meta is None:
        return None
    return render(meta, source)
