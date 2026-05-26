"""End-to-end smoke tests for the playtest CLI scripts.

Each test invokes the script's `main()` directly (no subprocess) and asserts
the exit code and a small piece of expected stdout.
"""
from __future__ import annotations

import io
from contextlib import redirect_stdout

from tools.playtest import inspect, inspect_node, sim_fight, sim_node, sim_run


def _capture(fn, argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = fn(argv)
    return code, buf.getvalue()


class TestSimFight:
    def test_resolves_and_prints_log(self) -> None:
        code, out = _capture(
            sim_fight.main,
            [
                "--team", "champ_dawnwisp,champ_veldt_pronghorn,champ_aegis_tortoise",
                "--enemies", "enemy_conscript,enemy_levyman",
                "--weather", "rain",
            ],
        )
        assert code == 0
        assert "Tempest Fauna Trail" in out
        assert "Result:" in out
        assert "champ_dawnwisp" in out


class TestInspect:
    def test_champion_filter_by_affinity(self) -> None:
        code, out = _capture(
            inspect.main,
            ["--kind", "champion", "--affinity", "thunder"],
        )
        assert code == 0
        assert "thunder" in out
        # 10 thunder champions in the roster
        assert "10 matching" in out

    def test_enemy_filter_by_tier(self) -> None:
        code, out = _capture(
            inspect.main,
            ["--kind", "enemy", "--tier", "1"],
        )
        assert code == 0
        assert "matching" in out
        assert "enemy_conscript" in out

    def test_show_favor(self) -> None:
        code, out = _capture(
            inspect.main,
            ["--kind", "champion", "--affinity", "rain", "--show-favor", "thunder"],
        )
        assert code == 0
        assert "Weather Favor applied" in out

    def test_empty_filter_exits_nonzero(self) -> None:
        code, _out = _capture(
            inspect.main,
            ["--kind", "champion", "--affinity", "clear", "--tier", "11"],
        )
        # tier 11 doesn't exist → empty → exit 1
        assert code == 1


class TestInspectNode:
    def test_fight_node(self) -> None:
        code, out = _capture(
            inspect_node.main,
            ["--stage", "1", "--node-index", "1", "--run-seed", "0"],
        )
        assert code == 0
        assert "Lisbon" in out  # Stage-1 node-1 city
        assert "Enemy squad" in out

    def test_boss_node(self) -> None:
        code, out = _capture(
            inspect_node.main,
            ["--stage", "1", "--node-index", "10", "--run-seed", "0"],
        )
        assert code == 0
        assert "boss_holloway" in out
        assert "map effect" in out

    def test_challenge_node(self) -> None:
        # Stage 2 has a challenge somewhere — pick first stage-2 node and try
        # all positions until we hit a CHALLENGE type. Stage 2 node types
        # default to STAGE_DEFAULT_TYPES, which includes one CHALLENGE.
        from src.game.models import NodeType
        from src.game.route import STAGES

        stage = STAGES[1]
        position = next(
            (i for i, t in enumerate(stage.node_types) if t == NodeType.CHALLENGE),
            None,
        )
        if position is None:
            return  # No challenge in stage 2 — nothing to test here
        node_index = sum(len(s.node_cities) for s in STAGES[:1]) + position + 1
        code, out = _capture(
            inspect_node.main,
            ["--stage", "2", "--node-index", str(node_index), "--run-seed", "0"],
        )
        assert code == 0
        assert "Reward" in out


class TestSimNode:
    def test_fight_node_runs(self) -> None:
        code, out = _capture(
            sim_node.main,
            ["--stage", "1", "--node-index", "1", "--run-seed", "12345"],
        )
        assert code == 0
        assert "Result:" in out

    def test_unknown_node_type_exits_nonzero(self) -> None:
        # Pick an AUGMENT node (stage 1 has one at position 2 — node 3).
        # If the route changes, this will need adjusting.
        from src.game.models import NodeType
        from src.game.route import STAGES

        stage = STAGES[0]
        pos = next(
            (i for i, t in enumerate(stage.node_types) if t == NodeType.AUGMENT),
            None,
        )
        if pos is None:
            return
        node_index = pos + 1
        code, _out = _capture(
            sim_node.main,
            ["--stage", "1", "--node-index", str(node_index), "--run-seed", "0"],
        )
        # Non-combat node → exit 2
        assert code == 2


class TestSimRun:
    def test_quiet_summary(self) -> None:
        code, out = _capture(
            sim_run.main,
            [
                "--run-seed", "12345",
                "--weather-strategy", "stage-affinity",
                "--quiet",
            ],
        )
        # Exit 0 (full clear) or 1 (team wiped) are both fine — both prove
        # the walk completed without an exception.
        assert code in {0, 1}
        assert "Run summary" in out
        assert "Nodes cleared" in out

    def test_csv_output(self, tmp_path) -> None:
        csv_path = tmp_path / "run.csv"
        code, _out = _capture(
            sim_run.main,
            [
                "--run-seed", "12345",
                "--weather-strategy", "city-default",
                "--quiet",
                "--csv", str(csv_path),
            ],
        )
        assert code in {0, 1}
        assert csv_path.exists()
        content = csv_path.read_text()
        assert "node_index,stage,node_type" in content.splitlines()[0]
