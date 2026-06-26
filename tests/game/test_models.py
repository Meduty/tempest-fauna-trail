import pytest

from src.game.models import (
    BattleEvent,
    BattleResult,
    Champion,
    CombatOutcome,
    Node,
    NodeState,
    NodeType,
    Run,
    RunStatus,
    WeatherState,
)


def _make_route() -> list[Node]:
    return [
        Node(
            id="node_01",
            index=1,
            city="Reykjavik",
            weather=WeatherState.SNOW,
            node_type=NodeType.FIGHT,
            state=NodeState.CURRENT,
            enemy_pool_id="pool_frost",
        ),
        Node(
            id="node_02",
            index=2,
            city="London",
            weather=WeatherState.RAIN,
            node_type=NodeType.REWARD,
            state=NodeState.UPCOMING,
            reward_table_id="reward_basic",
        ),
        Node(
            id="node_03",
            index=3,
            city="New York",
            weather=WeatherState.THUNDER,
            node_type=NodeType.BOSS_FIGHT,
            state=NodeState.UPCOMING,
            enemy_pool_id="pool_boss",
        ),
    ]


def _make_roster() -> list[Champion]:
    return [
        Champion(
            id="champ_blaze_fox",
            name="Blaze Fox",
            affinity=WeatherState.CLEAR,
            role="attacker",
            tier=3,
            level=1,
            max_hp=80,
            strength=18,
            intelligence=10,
            attack_speed=100,
            move_speed=100,
            mana_regen=5,
            threat=20,
            armor=8,
            resistance=6,
            attack_range=1,
            active_abilities=["Solar Pounce"],
            passive_ability="Kindled Claws",
            traits=["Mammal", "Hunter"],
        )
    ]


def _make_run() -> Run:
    return Run(
        run_id="run_001",
        schema_version=1,
        seed=42,
        status=RunStatus.IN_PROGRESS,
        roster=_make_roster(),
        bench=[],
        route=_make_route(),
        current_node_index=1,
        battle_log=[],
        inventory={"potion_small": 2},
        amber=10,
    )


def test_weather_state_roundtrip_through_run_serialization() -> None:
    run = _make_run()
    payload = run.to_dict()

    loaded = Run.from_dict(payload)
    assert loaded.roster[0].affinity == WeatherState.CLEAR
    assert loaded.roster[0].traits == ["Mammal", "Hunter"]
    assert loaded.route[0].weather == WeatherState.SNOW


def test_invalid_enum_parse_raises_clear_error() -> None:
    payload = {
        "id": "node_bad",
        "index": 1,
        "city": "Nowhere",
        "weather": "windy",
        "node_type": "fight",
        "state": "current",
    }

    with pytest.raises(ValueError, match="Invalid 'weather': 'windy'"):
        Node.from_dict(payload)


def test_run_to_dict_from_dict_roundtrip() -> None:
    run = _make_run()
    run.mark_current_node_cleared()
    run.advance_to_next_node()

    event = BattleEvent(
        tick=42,
        actor_id="champ_blaze_fox",
        target_id="frost_drone",
        event_type="attack",
        amount=12,
        note="crit",
    )
    run.battle_log.append(
        BattleResult(
            node_id="node_01",
            weather=WeatherState.SNOW,
            outcome=CombatOutcome.WIN,
            rounds=1,
            turns=8,
            duration_ticks=493,
            team_damage_dealt={"champ_blaze_fox": 48},
            team_damage_taken={"champ_blaze_fox": 12},
            surviving_team_ids=["champ_blaze_fox"],
            surviving_enemy_ids=[],
            timed_out=False,
            events=[event],
        )
    )

    payload = run.to_dict()
    loaded = Run.from_dict(payload)

    assert loaded.to_dict() == payload


def test_run_amber_serialization_and_legacy_gold_read() -> None:
    # New shape writes "amber".
    run = _make_run()
    assert run.to_dict()["amber"] == 10
    assert "gold" not in run.to_dict()

    # Legacy saves used "gold"; from_dict must still read it (SPEC B.4).
    legacy = run.to_dict()
    legacy["gold"] = legacy.pop("amber")
    assert Run.from_dict(legacy).amber == 10


def test_run_tempest_defaults_and_serialization() -> None:
    run = _make_run()
    assert run.tempest == 0
    assert run.tempest_rank == 1
    payload = run.to_dict()
    assert payload["tempest"] == 0 and payload["tempest_rank"] == 1
    assert Run.from_dict(payload).tempest_rank == 1


def test_run_advance_updates_node_states() -> None:
    run = _make_run()

    run.mark_current_node_cleared()
    run.advance_to_next_node()

    assert run.current_node_index == 2
    assert run.route[0].state == NodeState.CLEARED
    assert run.route[1].state == NodeState.CURRENT


def test_run_complete_on_final_node_cleared() -> None:
    run = _make_run()

    run.mark_current_node_cleared()
    run.advance_to_next_node()
    run.mark_current_node_cleared()
    run.advance_to_next_node()
    run.mark_current_node_cleared()
    run.advance_to_next_node()

    assert run.status == RunStatus.VICTORY
    assert run.is_complete()


def test_run_validation_requires_single_current_node() -> None:
    bad_route = _make_route()
    bad_route[1].state = NodeState.CURRENT

    with pytest.raises(ValueError, match="exactly one node"):
        Run(
            run_id="run_bad",
            schema_version=1,
            seed=7,
            status=RunStatus.IN_PROGRESS,
            roster=_make_roster(),
            bench=[],
            route=bad_route,
            current_node_index=1,
        )


def test_penetration_fields_roundtrip_and_validate() -> None:
    champ = _make_roster()[0]
    champ.penetration = 25
    champ.penetration_pct = 0.4

    loaded = Champion.from_dict(champ.to_dict())
    assert loaded.penetration == 25
    assert loaded.penetration_pct == 0.4

    with pytest.raises(ValueError, match="penetration_pct"):
        Champion.from_dict({**champ.to_dict(), "penetration_pct": 1.5})


# --- T.39 — persistent node weather lifecycle + Prep-entry lock (V.73) ---------

def test_node_weather_lifecycle_defaults_and_roundtrip() -> None:
    """New fields default to UNKNOWN/False and round-trip through to_dict/from_dict."""
    from src.game.models import NodeWeatherState

    node = Node(id="n", index=1, city="X", weather=WeatherState.CLEAR)
    assert node.weather_state is NodeWeatherState.UNKNOWN
    assert node.weather_locked is False

    node.weather_state = NodeWeatherState.LIVE
    node.weather_locked = True
    loaded = Node.from_dict(node.to_dict())
    assert loaded.weather_state is NodeWeatherState.LIVE
    assert loaded.weather_locked is True


def test_node_weather_backcompat_pre_t39_save() -> None:
    """Pre-T.39 payloads (fields absent) load as UNKNOWN/False — no schema bump."""
    from src.game.models import NodeWeatherState

    payload = {
        "id": "node_01", "index": 1, "city": "Reykjavik",
        "weather": "snow", "node_type": "fight", "state": "current",
    }
    node = Node.from_dict(payload)
    assert node.weather_state is NodeWeatherState.UNKNOWN
    assert node.weather_locked is False
    assert node.weather == WeatherState.SNOW


def test_set_node_live_weather_sets_state() -> None:
    from src.game.models import NodeWeatherState

    run = _make_run()
    run.set_node_live_weather(1, WeatherState.THUNDER, is_substitute=False)
    assert run.route[0].weather == WeatherState.THUNDER
    assert run.route[0].weather_state is NodeWeatherState.LIVE

    run.set_node_live_weather(2, WeatherState.MIST, is_substitute=True)
    assert run.route[1].weather == WeatherState.MIST
    assert run.route[1].weather_state is NodeWeatherState.SUBSTITUTE


def test_set_node_live_weather_is_noop_on_locked_node() -> None:
    run = _make_run()
    frozen = run.lock_node_weather(1)
    # Refresher tick tries to overwrite a locked node → ignored.
    run.set_node_live_weather(1, WeatherState.CLOUDY, is_substitute=False)
    assert run.route[0].weather == frozen  # unchanged


def test_lock_node_weather_freezes_and_is_idempotent() -> None:
    from src.game.models import NodeWeatherState

    run = _make_run()
    # Node 1 fetched LIVE first → lock preserves the live value + state.
    run.set_node_live_weather(1, WeatherState.RAIN, is_substitute=False)
    assert run.lock_node_weather(1) == WeatherState.RAIN
    assert run.route[0].weather_locked is True
    assert run.route[0].weather_state is NodeWeatherState.LIVE
    # Second call: no-op.
    assert run.lock_node_weather(1) == WeatherState.RAIN


def test_lock_unknown_node_freezes_default_as_substitute() -> None:
    """Locking a never-fetched node freezes default_weather flagged SUBSTITUTE (V.13)."""
    from src.game.models import NodeWeatherState

    run = _make_run()  # node 1 starts UNKNOWN, weather=SNOW (the placeholder)
    assert run.route[0].weather_state is NodeWeatherState.UNKNOWN
    assert run.lock_node_weather(1) == WeatherState.SNOW
    assert run.route[0].weather_state is NodeWeatherState.SUBSTITUTE
    assert run.route[0].weather_locked is True


def test_lock_node_weather_unknown_index_raises() -> None:
    run = _make_run()
    with pytest.raises(ValueError, match="No route node with index 99"):
        run.lock_node_weather(99)
