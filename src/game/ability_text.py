"""Ability description renderer (T.34, T.35a) — pure, no Flet, no I/O (V.1).

Turns an ``AbilityMeta`` + a render *source* into a ``RenderedAbility`` with a
player-facing ``text`` (blurb + clauses with ``{label}`` tokens replaced by live
numbers) and a ``formula`` (one human-readable line per ``Magnitude``). The
source is **structurally typed**: any object exposing ``.stat(name) -> float``
(and ``.max_hp`` for ``PctResource``) — a live ``Piece`` (combat, with modifiers)
or a base ``Champion``/``Enemy`` (roster sheet, via their ``.stat()`` adapters).
One call serves both UI contexts.

T.35a: the renderer is **pure per-kind dispatch** over the closed ``Magnitude``
family (``ScalingTerm``/``PctResource``/``MaxOfTerm``/``SetByCaller``, V.46) —
each kind self-describes via ``eval``/``render_formula``/``render_inline``, so
there is no kind-specific branching here. Numbers come from the same
``Magnitude`` objects the handlers read (source-of-truth B, V.38) — the tooltip
number is exactly the number combat computes. ``Clause`` carries optional
``terms`` + a ``{token}`` ``template`` so Tier-B prose pulls live numbers (A1).

``TICKS_PER_SECOND = 100`` is the single source for the ``100 ticks = 1 second``
display convention (V.39): mechanics stay in ticks, this module (and ``ui/``,
which imports the constant from here) is the only place ticks become seconds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.game.registries import AbilityMeta

# V.39 — canonical display convention. Ticks in code; seconds only here + ui/.
TICKS_PER_SECOND = 100


@dataclass(frozen=True)
class RenderedAbility:
    """A rendered ability tooltip — pure data, no UI dependency."""

    name: str
    text: str                       # blurb + clauses with {tokens} replaced by live numbers
    formula: str                    # one line per Magnitude, "267 = 80 + 220% INT (INT 85)"
    tags: tuple[str, ...]


def ticks_to_s(ticks: float) -> str:
    """Format a tick count as seconds (V.39). Trims a trailing ``.0``.

    ``ticks_to_s(200) -> "2"``; ``ticks_to_s(150) -> "1.5"``.
    """
    secs = ticks / TICKS_PER_SECOND
    if secs == int(secs):
        return str(int(secs))
    return f"{secs:g}"


def render(meta: AbilityMeta, source: object) -> RenderedAbility:
    """Render ``meta`` against ``source`` (any object with ``.stat(name)``).

    Pure per-kind dispatch: every ``Magnitude`` (headline ``meta.terms`` and any
    ``clause.terms``) self-renders. Token substitution draws from all of them.
    """
    all_terms = list(meta.terms)
    for c in meta.clauses:
        all_terms.extend(c.terms)
    values = {t.label: t.render_token(source) for t in all_terms}

    def _sub(match: re.Match) -> str:
        key = match.group(1)
        return values.get(key, match.group(0))

    full = meta.blurb
    inline = "; ".join(s for s in (t.render_inline(source) for t in meta.terms) if s)
    if inline:
        full = full + f" ({inline})"
    for c in meta.clauses:
        full = full + " " + (c.template if c.template else c.text)
    text = re.sub(r"\{(\w+)\}", _sub, full)

    formula = "\n".join(t.render_formula(source) for t in all_terms)
    return RenderedAbility(name=meta.name, text=text, formula=formula, tags=meta.tags)


def render_for(ability_id: str, source: object) -> RenderedAbility | None:
    """Look up ``ability_id`` in ``ABILITY_META`` and render it, or ``None``."""
    from src.game.registries import ABILITY_META

    meta = ABILITY_META.get(ability_id)
    if meta is None:
        return None
    return render(meta, source)
