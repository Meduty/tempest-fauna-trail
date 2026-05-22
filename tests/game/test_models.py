import pytest

from src.game.models import (
    BattleEvent,
    BattleResult,
    Champion,
    CombatOutcome,
    CombatPieceState,
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
            active_ability="Solar Pounce",
            passive_ability="Kindled Claws",
            ability_cost=100,
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
        gold=10,
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


def test_combat_piece_state_clamps_hp_to_max() -> None:
    piece = CombatPieceState(
        piece_id="champ_blaze_fox",
        is_enemy=False,
        affinity=WeatherState.CLEAR,
        tier=3,
        level=1,
        max_hp=100,
        hp=120,
        strength=20,
        intelligence=10,
        attack_speed=100,
        move_speed=100,
        mana_regen=5,
        threat=20,
        armor=5,
        resistance=4,
        attack_range=1,
        ability_cost=100,
        mana=120,
    )

    assert piece.hp == 100
    assert piece.mana == 100


def test_penetration_fields_roundtrip_and_validate() -> None:
    champ = _make_roster()[0]
    champ.penetration = 25
    champ.penetration_pct = 0.4

    loaded = Champion.from_dict(champ.to_dict())
    assert loaded.penetration == 25
    assert loaded.penetration_pct == 0.4

    with pytest.raises(ValueError, match="penetration_pct"):
        Champion.from_dict({**champ.to_dict(), "penetration_pct": 1.5})
