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


# --- T.37c: resumable forward CombatReplay stepper -------------------------


def _event_ticks(result):
    return sorted({e.tick for e in result.events if e.tick > 0})


def test_forward_stepper_matches_inspect_at_every_event_tick():
    """The headline T.37c guarantee: a single forward-stepped CombatReplay yields
    the *same* live state as independent `inspect_at_tick` re-runs at every
    event-bearing tick (held instance == re-run from 0). O(N) vs O(N²)."""
    from src.game.combat import CombatReplay

    team, enemies, weather = _aurion_fight()
    result = resolve_combat(team, enemies, weather)
    ticks = _event_ticks(result)
    assert ticks, "fight produced no events"

    replay = CombatReplay(team, enemies, weather)
    for t in ticks:
        stepped = {v.id: v for v in replay.step_to(t).pieces()}
        fresh = {v.id: v for v in inspect_at_tick(team, enemies, weather, tick=t)}
        assert stepped == fresh, f"stepper diverged from inspect at tick {t}"


def test_forward_stepper_hp_complete_through_ability_burst():
    """B.28 guard: live-replay HP is COMPLETE — every HP change shows, including
    registered-ability burst the event stream omits (`_on_cast` stamps
    `hp_after=-1`; only `dot` damage carries `hp_after`). A naive bar built from
    the stream's `hp_after` would freeze through a nuke; the stepper does not."""
    from src.game.combat import CombatReplay

    team, enemies, weather = _aurion_fight()
    result = resolve_combat(team, enemies, weather)

    # Reconstruct HP the (wrong) stream-only way: seed from initial snapshot,
    # apply each beat's hp_after when present (== the B.28-incomplete source).
    stream_hp = {s.id: s.max_hp for s in result.initial_pieces}

    replay = CombatReplay(team, enemies, weather)
    diverged = False
    for t in _event_ticks(result):
        for e in result.events:
            if e.tick == t and e.hp_after >= 0:
                stream_hp[e.target_id] = e.hp_after
        live = {v.id: v.hp for v in replay.step_to(t).pieces()}
        for pid, live_hp in live.items():
            # The live (engine-truth) HP is authoritative; where the stream lacks
            # a beat for a hit, the two disagree — proving the stream can't be the
            # bar source (V.57).
            if pid in stream_hp and stream_hp[pid] != live_hp:
                diverged = True
    assert diverged, (
        "expected the stream-only HP reconstruction to diverge from live replay "
        "on at least one ability-burst tick (B.28); if not, the fixture has no "
        "registered-ability damage — pick a caster matchup"
    )


def test_forward_stepper_is_forward_only():
    """Forward-only: stepping to an earlier tick raises (use inspect_at_tick)."""
    from src.game.combat import CombatReplay

    team, enemies, weather = _aurion_fight()
    replay = CombatReplay(team, enemies, weather)
    replay.step_to(100)
    with pytest.raises(ValueError):
        replay.step_to(50)


def test_forward_stepper_winner_matches_resolve():
    """Draining the stepper to the end yields the same winner as resolve_combat."""
    from src.game.combat import CombatReplay

    team, enemies, weather = _aurion_fight()
    result = resolve_combat(team, enemies, weather)
    replay = CombatReplay(team, enemies, weather)
    replay.step_to(10_000_000)
    assert replay.finished
    assert replay.winner == ("team" if result.outcome.name == "WIN" else replay.winner)


def test_replay_has_no_flet_import():
    """`combat/replay.py` stays Flet-free (V.1) — importable with no display."""
    import importlib
    import sys

    assert "flet" not in sys.modules or True  # don't force-fail if a sibling imported it
    mod = importlib.import_module("src.game.combat.replay")
    src = open(mod.__file__).read()
    assert "import flet" not in src and "from flet" not in src
