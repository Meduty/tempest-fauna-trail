"""T.12a — pure combat-playback model (cues + action-queue projection).

The model is Flet-free and carries NO resource numbers (V.57); resource fidelity
is owned + tested by T.37c (`CombatReplay` == `inspect_at_tick`). These tests
target only the cue/queue derivation + the view↔stepper drive contract.
"""

import dataclasses

import pytest

from src.game.combat import (
    CombatReplay,
    EVENT_ATTACK,
    EVENT_CAST,
    EVENT_MOVE,
    ROUND_TICKS,
    resolve_combat,
)
from src.game.content import CHAMPION_ROSTER, ENEMY_ROSTER
from src.game.models import WeatherState
from src.ui.combat_playback import (
    CombatSession,
    Playback,
    Step,
    build_playback,
)


def _fight():
    team = [CHAMPION_ROSTER["champ_aurion"]]
    enemies = list(ENEMY_ROSTER.values())[:6]
    return team, enemies, WeatherState.CLEAR


def _result():
    team, enemies, weather = _fight()
    return resolve_combat(team, enemies, weather), team, enemies, weather


def test_one_step_per_event_bearing_tick_covering_every_event():
    result, *_ = _result()
    pb = build_playback(result)
    # one step per distinct event tick, ascending
    ticks = [s.tick for s in pb.steps]
    assert ticks == sorted(set(ticks))
    # every event lands in exactly one step
    total_beats = sum(len(s.beats) for s in pb.steps)
    assert total_beats == len(result.events)
    for s in pb.steps:
        assert s.round == s.tick // ROUND_TICKS
        assert all(b.tick == s.tick for b in s.beats)


def test_model_carries_no_resource_numbers():
    """B.28 regression guard: the playback model must NOT reconstruct hp/mana/
    barrier from the stream — those come from the live stepper (V.57)."""
    forbidden = {"hp", "max_hp", "barrier", "mana", "hp_after", "barrier_after"}
    for cls in (Playback, Step):
        names = {f.name for f in dataclasses.fields(cls)}
        assert not (names & forbidden), f"{cls.__name__} leaks resource state: {names & forbidden}"


def test_queue_projects_current_plus_two_rounds():
    result, *_ = _result()
    pb = build_playback(result)
    if not pb.steps:
        pytest.skip("no events")
    q = pb.queue(0)
    now = pb.tick_at(0)
    cur_round = now // ROUND_TICKS
    assert all(e.tick >= now for e in q)
    assert all(cur_round <= e.round <= cur_round + 2 for e in q)
    # only action kinds appear
    assert all(e.kind in {EVENT_MOVE, EVENT_ATTACK, EVENT_CAST} for e in q)
    # ordered by tick
    assert [e.tick for e in q] == sorted(e.tick for e in q)


def test_queue_slides_forward_as_cursor_advances():
    result, *_ = _result()
    pb = build_playback(result)
    if len(pb.steps) < 2:
        pytest.skip("fight too short")
    early = pb.queue(0)
    late = pb.queue(len(pb.steps) - 1)
    # the late window never references ticks before the late cursor
    late_now = pb.tick_at(len(pb.steps) - 1)
    assert all(e.tick >= late_now for e in late)
    # earlier window starts no later than the later one
    if early and late:
        assert early[0].tick <= late[0].tick


def test_build_playback_is_deterministic():
    result, *_ = _result()
    a = build_playback(result)
    b = build_playback(result)
    assert [s.tick for s in a.steps] == [s.tick for s in b.steps]
    assert [(e.tick, e.actor_id, e.kind) for e in a.queue(0)] == \
           [(e.tick, e.actor_id, e.kind) for e in b.queue(0)]


def test_view_stepper_drive_loop_reaches_survivors():
    """The view's drive contract (pure, no Flet): walk the steps, advancing one
    forward `CombatReplay`, and the final live board matches the resolved
    survivors. This is what `ui/views/combat.py` does between renders."""
    result, team, enemies, weather = _result()
    pb = build_playback(result)
    replay = CombatReplay(team, enemies, weather)
    for s in pb.steps:
        replay.step_to(s.tick)
    replay.step_to(10_000_000)  # drain to the end
    alive_team = {v.id for v in replay.pieces() if v.alive and not v.is_enemy}
    alive_enemy = {v.id for v in replay.pieces() if v.alive and v.is_enemy}
    assert alive_team == set(result.surviving_team_ids)
    assert alive_enemy == set(result.surviving_enemy_ids)


def test_combat_session_is_flet_free_value_bundle():
    team, enemies, weather = _fight()
    s = CombatSession(team=team, enemies=enemies, weather=weather)
    assert s.run_mods is None and s.node_id == ""
    # frozen
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.node_id = "x"


def test_combat_playback_has_no_flet_import():
    import src.ui.combat_playback as mod
    src = open(mod.__file__).read()
    assert "import flet" not in src and "from flet" not in src
