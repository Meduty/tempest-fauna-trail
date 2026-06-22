"""T.37b — deterministic replay / inspect-at-tick (V.55)."""

import pytest

from src.game.combat import EVENT_CAST, inspect_at_tick, resolve_combat
from src.game.combat.replay import _clone_run_mods
from src.game.content import CHAMPION_ROSTER, ENEMY_ROSTER
from src.game.models import WeatherState


def _aurion_fight():
    team = [CHAMPION_ROSTER["champ_aurion"]]
    enemies = list(ENEMY_ROSTER.values())[:6]
    return team, enemies, WeatherState.CLEAR


def test_inspect_is_deterministic():
    team, enemies, weather = _aurion_fight()
    a = inspect_at_tick(team, enemies, weather, tick=120)
    b = inspect_at_tick(team, enemies, weather, tick=120)
    assert a == b


def test_inspect_tick0_is_initial_board():
    team, enemies, weather = _aurion_fight()
    result = resolve_combat(team, enemies, weather)
    views = inspect_at_tick(team, enemies, weather, tick=0)

    # tick 0 = state right after on_combat_start: everyone alive, full HP,
    # positions matching the recorded initial snapshot.
    snap = {s.id: s for s in result.initial_pieces}
    assert {v.id for v in views} == set(snap)
    for v in views:
        assert v.alive and v.hp == v.max_hp
        assert (v.q, v.r) == (snap[v.id].q, snap[v.id].r)


def test_inspect_end_matches_resolved_survivors():
    team, enemies, weather = _aurion_fight()
    result = resolve_combat(team, enemies, weather)
    views = inspect_at_tick(team, enemies, weather, tick=10_000_000)

    alive_team = {v.id for v in views if v.alive and not v.is_enemy}
    alive_enemy = {v.id for v in views if v.alive and v.is_enemy}
    assert alive_team == set(result.surviving_team_ids)
    assert alive_enemy == set(result.surviving_enemy_ids)


def test_inspect_tracks_strength_ramp_tick_precisely():
    """The headline V.55 capability: read a piece's *effective* STR at any tick.
    Aurion's Ascendance adds +15 STR on each cast — pin to the real first-cast
    tick from the event stream and assert the inspected stat jumps exactly then."""
    team, enemies, weather = _aurion_fight()
    result = resolve_combat(team, enemies, weather)

    cast_ticks = [e.tick for e in result.events
                  if e.event_type == EVENT_CAST and e.actor_id == "champ_aurion"]
    if not cast_ticks:
        pytest.skip("Aurion did not cast in this fight")
    t = cast_ticks[0]

    def aurion_str(tick):
        v = next(v for v in inspect_at_tick(team, enemies, weather, tick=tick) if v.id == "champ_aurion")
        return v.stats["strength"]

    base = aurion_str(0)
    before = aurion_str(t - 1)
    after = aurion_str(t)
    # Tick-precise: no ramp before the cast tick, a strictly larger *effective*
    # STR at it (the +15 add is scaled by Aurion's STR muls — inspect reports the
    # folded value, not the raw modifier).
    assert before == pytest.approx(base)
    assert after > before


def test_inspect_clone_isolates_augment_state():
    """An inspect re-run must not mutate the caller's run state (V.55)."""
    from src.game.augments import RunModifiers
    rm = RunModifiers(augments=["x"], augment_state={"quest": [1, 2]})
    clone = _clone_run_mods(rm)
    assert clone is not rm
    assert clone.augment_state is not rm.augment_state
    assert clone.augments is not rm.augments
    clone.augment_state["quest"].append(3)
    assert rm.augment_state == {"quest": [1, 2]}  # caller untouched


def test_inspect_returns_readonly_value_structs():
    """No raw Piece / Flet escapes — PieceView is a frozen value struct (V.1)."""
    from src.game.combat.replay import PieceView
    team, enemies, weather = _aurion_fight()
    views = inspect_at_tick(team, enemies, weather, tick=50)
    assert views and all(isinstance(v, PieceView) for v in views)
    with pytest.raises((AttributeError, TypeError)):  # frozen field
        views[0].hp = 0
    with pytest.raises(TypeError):  # stats is a read-only MappingProxyType
        views[0].stats["strength"] = 0.0


def test_inspect_midfight_does_not_finalize_combat():
    """Stopping mid-fight must return without firing end-combat finalization —
    both sides still have living pieces at an early tick (regression: the stop
    used to fall into the post-loop `ctx.end_combat`, mutating the snapshot)."""
    team, enemies, weather = _aurion_fight()
    views = inspect_at_tick(team, enemies, weather, tick=30)
    assert any(v.alive and not v.is_enemy for v in views)
    assert any(v.alive and v.is_enemy for v in views)
