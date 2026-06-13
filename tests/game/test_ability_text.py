"""T.34 — ability description / tooltip renderer tests.

Covers V.38 (every roster ability id resolves in ABILITY_META; render is pure
and reads numbers via source.stat()) and V.39 (TICKS_PER_SECOND display
convention). Scope grows with the substeps:

    T.34a — champions   (this file's CHAMPION_IDS)
    T.34b — + enemies
    T.34c — + bosses

Run with ``UPDATE_ABILITY_SNAPSHOT=1 uv run pytest tests/game/test_ability_text.py``
to regenerate the golden formula snapshot after an intentional change.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

# Importing the content package triggers the @register decorators that also
# populate ABILITY_META (champions.py assigns at import time).
import src.game.abilities  # noqa: F401  (registers handlers + metas)
from src.game.ability_text import TICKS_PER_SECOND, render, render_for, ticks_to_s
from src.game.content import (
    CHAMPION_ROSTER,
    ENEMY_ROSTER,
    _CHAMPION_DEFS,
    _ENEMY_DEFS,
)
from src.game.registries import ABILITY_META, _eval_scaling

SNAPSHOT_PATH = Path(__file__).parent / "ability_formulas.snapshot.json"

# Champion roster ability-id coverage set (the V.38 guarantee for T.34a).
CHAMPION_IDS = sorted(
    {a for d in _CHAMPION_DEFS for a in (d.active_ability, d.passive_ability)}
)
# Enemy roster ability-id coverage set (T.34b).
ENEMY_IDS = sorted(
    {a for d in _ENEMY_DEFS for a in (d.active_ability, d.passive_ability)}
)

# Boss ability-id coverage set (T.34c) — V.15 field-set over all 6 BossDdefs.
_BOSS_FIELDS = (
    "phase1_active", "phase1_passive", "phase1_phase_hook",
    "phase2_active", "phase2_passive", "on_death_hook",
)


def _boss_id_to_sheet() -> dict[str, object]:
    """Map every boss ability id to the boss's compiled Enemy sheet.

    Bosses have no draft roster entry; each id (incl. phase2 / hooks) renders
    against the same boss Enemy (authored stats), which exposes `.stat()`.
    """
    from src.game.bosses.data import get_boss_def

    out: dict[str, object] = {}
    for stage in range(1, 7):
        d = get_boss_def(stage)
        sheet = d.build_enemy()
        for f in _BOSS_FIELDS:
            out[getattr(d, f)] = sheet
    return out


_BOSS_SHEETS = _boss_id_to_sheet()
BOSS_IDS = sorted(_BOSS_SHEETS)

# All roster sheets (Champion + Enemy) keyed by id, for source lookups.
_ALL_SHEETS = {**CHAMPION_ROSTER, **ENEMY_ROSTER}


def _source_for(ability_id: str) -> object:
    """The render source (sheet) that owns this ability id."""
    if ability_id in _BOSS_SHEETS:
        return _BOSS_SHEETS[ability_id]
    return next(
        s for s in _ALL_SHEETS.values()
        if ability_id in (s.active_ability, s.passive_ability)
    )


# ---------------------------------------------------------------------------
# Coverage / V.38 guard
# ---------------------------------------------------------------------------


def test_all_champion_abilities_have_meta() -> None:
    """Every champion active/passive id resolves in ABILITY_META (V.38)."""
    missing = [aid for aid in CHAMPION_IDS if aid not in ABILITY_META]
    assert not missing, f"champion ability ids without AbilityMeta: {missing}"


def test_all_enemy_abilities_have_meta() -> None:
    """Every enemy active/passive id resolves in ABILITY_META (V.38, T.34b)."""
    missing = [aid for aid in ENEMY_IDS if aid not in ABILITY_META]
    assert not missing, f"enemy ability ids without AbilityMeta: {missing}"


def test_all_boss_abilities_have_meta() -> None:
    """Every boss ability id (V.15 field-set) resolves in ABILITY_META (V.38, T.34c)."""
    missing = [aid for aid in BOSS_IDS if aid not in ABILITY_META]
    assert not missing, f"boss ability ids without AbilityMeta: {missing}"


def test_champion_id_count() -> None:
    # 60 champions x (active + passive) = 120 ids (content budget).
    assert len(CHAMPION_IDS) == 120


def test_enemy_id_count() -> None:
    # 60 enemies x (active + passive) = 120 ids.
    assert len(ENEMY_IDS) == 120


def test_boss_id_count() -> None:
    # 6 bosses x 6 V.15 fields = 36 ids.
    assert len(BOSS_IDS) == 36


# ---------------------------------------------------------------------------
# Render smoke — no leftover tokens, formula well-formed, both source types
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ability_id", CHAMPION_IDS + ENEMY_IDS + BOSS_IDS)
def test_render_smoke_against_sheet(ability_id: str) -> None:
    # Render against the owning sheet (Champion, Enemy, or boss Enemy).
    sheet = _source_for(ability_id)
    r = render(ABILITY_META[ability_id], sheet)
    assert r.name, f"{ability_id} has empty name"
    assert r.text, f"{ability_id} has empty text"
    assert not re.search(r"\{\w+\}", r.text), f"{ability_id} left an unfilled token: {r.text!r}"
    # formula has one line per term; each line starts with a rounded int.
    for line in (r.formula.splitlines() if r.formula else []):
        assert re.match(r"^-?\d+ = ", line), f"{ability_id} malformed formula line: {line!r}"


def test_render_against_live_piece() -> None:
    """render() serves a live Piece (combat source) as well as a Champion."""
    from src.game.loadout import compile_loadout
    from src.game.content import build_champion_at_level, ENEMY_ROSTER, build_enemy_at_level
    from src.game.models import WeatherState

    team = [build_champion_at_level("champ_dawnwisp", 3)]
    foes = [build_enemy_at_level(sorted(ENEMY_ROSTER)[0], 3)]
    pieces, _bus, _ta = compile_loadout(team, foes, WeatherState.CLEAR, seed=42)
    piece = next(p for p in pieces if "dawnwisp" in p.id)
    r = render_for("champ_dawnwisp.active", piece)
    assert r is not None and r.text and not re.search(r"\{\w+\}", r.text)


def test_render_for_unknown_id_returns_none() -> None:
    assert render_for("champ_does_not_exist.active", CHAMPION_ROSTER["champ_dawnwisp"]) is None


# ---------------------------------------------------------------------------
# Number correctness — tooltip number == what the handler computes
# ---------------------------------------------------------------------------


def test_term_numbers_match_eval_scaling() -> None:
    """Each rendered term equals _eval_scaling(base, scaling, source) rounded."""
    sampled = [
        "champ_dawnwisp.active",           # flat + single stat (heal)
        "champ_veldt_pronghorn.active",    # single stat (physical)
        "champ_aurion.active",             # two-stat str+int
        "champ_eclipse_jaguar.active",     # multi-term
    ]
    for aid in sampled:
        champ = next(
            c for c in CHAMPION_ROSTER.values()
            if aid in (c.active_ability, c.passive_ability)
        )
        meta = ABILITY_META[aid]
        for term in meta.terms:
            expected = round(_eval_scaling(term.base, term.scaling, champ))
            assert str(expected) in render(meta, champ).text or str(expected) in render(meta, champ).formula


# ---------------------------------------------------------------------------
# Champion.stat adapter (the §2 gap this task closes)
# ---------------------------------------------------------------------------


def test_champion_stat_returns_base_field() -> None:
    c = CHAMPION_ROSTER["champ_dawnwisp"]
    assert c.stat("intelligence") == float(c.intelligence)
    assert c.stat("strength") == float(c.strength)


def test_champion_stat_unknown_key_is_zero() -> None:
    assert CHAMPION_ROSTER["champ_dawnwisp"].stat("nonexistent") == 0.0


def test_enemy_stat_parity() -> None:
    """Enemy.stat mirrors Champion.stat (T.34b parity adapter)."""
    e = next(iter(ENEMY_ROSTER.values()))
    assert e.stat("intelligence") == float(e.intelligence)
    assert e.stat("strength") == float(e.strength)
    assert e.stat("nonexistent") == 0.0


def test_scaling_term_resolves_nonzero_against_champion() -> None:
    """The bug §2 flags: a scaling term must not zero against a base Champion."""
    c = CHAMPION_ROSTER["champ_dawnwisp"]
    meta = ABILITY_META["champ_dawnwisp.active"]
    assert meta.terms[0].eval(c) > meta.terms[0].base


# ---------------------------------------------------------------------------
# Determinism — render is pure; identical source -> identical output
# ---------------------------------------------------------------------------


def test_render_is_pure() -> None:
    c = CHAMPION_ROSTER["champ_aurion"]
    meta = ABILITY_META["champ_aurion.active"]
    assert render(meta, c) == render(meta, c)


# ---------------------------------------------------------------------------
# Tick -> seconds (V.39)
# ---------------------------------------------------------------------------


def test_ticks_per_second_constant() -> None:
    assert TICKS_PER_SECOND == 100


def test_ticks_to_s_formats() -> None:
    assert ticks_to_s(200) == "2"
    assert ticks_to_s(600) == "6"
    assert ticks_to_s(150) == "1.5"


def test_mechanics_modules_do_not_convert_ticks() -> None:
    """V.39: no game-logic module references TICKS_PER_SECOND (ticks-only)."""
    root = Path(__file__).parents[2] / "src" / "game"
    offenders = []
    for sub in ("combat", "status.py", "piece.py"):
        target = root / sub
        files = target.rglob("*.py") if target.is_dir() else [target]
        for f in files:
            if "TICKS_PER_SECOND" in f.read_text():
                offenders.append(str(f.relative_to(root)))
    assert not offenders, f"mechanics modules must stay ticks-only: {offenders}"


# ---------------------------------------------------------------------------
# Golden snapshot — pins the rendered formula (headline numbers) per id
# ---------------------------------------------------------------------------


def _current_formulas() -> dict[str, str]:
    out: dict[str, str] = {}
    for aid in CHAMPION_IDS + ENEMY_IDS + BOSS_IDS:
        out[aid] = render(ABILITY_META[aid], _source_for(aid)).formula
    return out


def test_formula_snapshot() -> None:
    current = _current_formulas()
    if os.environ.get("UPDATE_ABILITY_SNAPSHOT"):
        SNAPSHOT_PATH.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        pytest.skip("snapshot regenerated")
    assert SNAPSHOT_PATH.exists(), "run with UPDATE_ABILITY_SNAPSHOT=1 to create it"
    golden = json.loads(SNAPSHOT_PATH.read_text())
    assert current == golden, "rendered formulas drifted from golden snapshot"
