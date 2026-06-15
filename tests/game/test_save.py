"""T.14 — file-I/O layer over the Run (de)serialization contract.

The in-memory round-trip is already covered by ``test_models.py``; here we
exercise the disk layer: atomic write, typed errors, schema gate, and that the
B.4 ``gold``→``amber`` back-compat survives a real load.
"""

import json
import os

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
from src.game.save import (
    CURRENT_SCHEMA_VERSION,
    CorruptSaveError,
    UnsupportedSchemaError,
    default_save_dir,
    load_run,
    save_run,
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
            traits=["Mammal", "Hunter"],
        )
    ]


def _make_run() -> Run:
    return Run(
        run_id="run_001",
        schema_version=CURRENT_SCHEMA_VERSION,
        seed=42,
        status=RunStatus.IN_PROGRESS,
        roster=_make_roster(),
        bench=[],
        route=_make_route(),
        current_node_index=1,
        battle_log=[],
        inventory={"potion_small": 2},
        amber=10,
        tempest=3,
        tempest_rank=2,
        champion_copies={"champ_blaze_fox": 3},
        shop_offers=["champ_x", None, "champ_y"],
        shop_rerolls=1,
    )


def _run_with_battle_log() -> Run:
    run = _make_run()
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
            events=[
                BattleEvent(
                    tick=42,
                    actor_id="champ_blaze_fox",
                    target_id="frost_drone",
                    event_type="attack",
                    amount=12,
                    note="crit",
                )
            ],
        )
    )
    return run


# 1. Round-trip through disk (incl. a populated battle_log — persisted in full).
def test_round_trip_through_disk(tmp_path):
    run = _run_with_battle_log()
    path = tmp_path / "slot.json"

    save_run(run, path)
    loaded = load_run(path)

    assert loaded.to_dict() == run.to_dict()
    assert loaded.amber == 10
    assert loaded.tempest_rank == 2
    assert loaded.battle_log[0].events[0].note == "crit"


# 2. Atomic write — no temp left behind, parent dir auto-created.
def test_save_is_atomic_and_creates_parent(tmp_path):
    path = tmp_path / "nested" / "dir" / "slot.json"

    save_run(_make_run(), path)

    assert path.exists()
    assert not (path.with_name(path.name + ".tmp")).exists()
    # No stray temp files anywhere in the save dir.
    assert list(path.parent.glob("*.tmp")) == []


# 3. Atomic overwrite — second save fully replaces the first.
def test_save_overwrites_cleanly(tmp_path):
    path = tmp_path / "slot.json"
    first = _make_run()
    save_run(first, path)

    second = _make_run()
    second.amber = 999
    save_run(second, path)

    loaded = load_run(path)
    assert loaded.amber == 999


# 4. Missing file → FileNotFoundError (unwrapped, so callers branch on it).
def test_load_missing_file_raises_filenotfound(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_run(tmp_path / "does_not_exist.json")


# 5. Malformed payloads → CorruptSaveError.
@pytest.mark.parametrize(
    "content",
    [
        "this is not json",
        "[]",  # valid JSON, wrong top-level type
        json.dumps({}),  # missing schema_version
        json.dumps({"schema_version": 1}),  # missing run_id / route etc.
    ],
)
def test_load_malformed_raises_corrupt(tmp_path, content):
    path = tmp_path / "bad.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(CorruptSaveError):
        load_run(path)


# 6. JSON-valid but semantically invalid (fails a Run validator) → CorruptSaveError,
#    never a raw ValueError. Guards the error-wrapping contract.
def test_load_semantically_invalid_raises_corrupt(tmp_path):
    bad_rank = _make_run().to_dict()
    bad_rank["tempest_rank"] = 11  # out of range -> Run.__post_init__ ValueError
    path = tmp_path / "rank.json"
    path.write_text(json.dumps(bad_rank), encoding="utf-8")
    with pytest.raises(CorruptSaveError):
        load_run(path)

    bad_enum = _make_run().to_dict()
    bad_enum["status"] = "not_a_status"  # _parse_enum ValueError
    path2 = tmp_path / "status.json"
    path2.write_text(json.dumps(bad_enum), encoding="utf-8")
    with pytest.raises(CorruptSaveError):
        load_run(path2)


# 7. Schema gate: future version refused; bad-typed version is corrupt.
def test_load_future_schema_raises_unsupported(tmp_path):
    payload = _make_run().to_dict()
    payload["schema_version"] = CURRENT_SCHEMA_VERSION + 1
    path = tmp_path / "future.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(UnsupportedSchemaError):
        load_run(path)


@pytest.mark.parametrize("version", ["1", 0, -1, True, 1.0, None])
def test_load_bad_schema_version_type_raises_corrupt(tmp_path, version):
    payload = _make_run().to_dict()
    payload["schema_version"] = version
    path = tmp_path / "ver.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CorruptSaveError):
        load_run(path)


# 8. Back-compat read survives the file layer (B.4): legacy "gold", missing
#    later-added optional fields.
def test_load_legacy_gold_payload(tmp_path):
    payload = _make_run().to_dict()
    payload["gold"] = payload.pop("amber")
    payload.pop("tempest")
    payload.pop("shop_offers")
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_run(path)
    assert loaded.amber == 10  # read from legacy "gold"
    assert loaded.tempest == 0  # default applied
    assert loaded.shop_offers == []  # default applied


# 9. default_save_dir — absolute, correct suffix, no side-effecting mkdir.
def test_default_save_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr("src.game.save.sys_platform_is_darwin", lambda: False)
    monkeypatch.setattr(os, "name", "posix")

    d = default_save_dir()

    assert d.is_absolute()
    assert d.parts[-2:] == ("tempest-fauna-trail", "saves")
    assert not d.exists()  # calling it must not create the dir
