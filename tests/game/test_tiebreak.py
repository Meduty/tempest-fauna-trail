"""Canonical same-tick total order — B.14 fix / V.34 (T.33a, amended T.29-pre).

The combat tiebreak must be a side-independent total order
`(-round(attack_speed×1000), champion_id, load_order, kind)`, so equal-attack-speed
ties never systematically favour the player team. `attack_speed` is a float
(T.29-pre); sub-integer order derives from it directly — there is no `milli_AS`.
"""
from src.game.combat.engine import _KIND_ACTION, _event_sort_key
from src.game.effects import EventBus, Lifetime, Modifier
from src.game.loadout import compile_loadout
from src.game.models import WeatherState
from src.game.piece import Piece


def _piece(id, as_, *, is_enemy=False, formation_index=0, load_order=0):
    return Piece(
        id=id,
        base_stats={"attack_speed": float(as_)},
        is_enemy=is_enemy,
        formation_index=formation_index,
        load_order=load_order,
    )


class TestSortKeySideIndependent:
    def test_tie_broken_by_load_order_not_side(self):
        # Identical AS. Team has the LOWER formation_index (the old bias would make
        # it act first); the enemy has the lower load_order.
        team = _piece("champ_x", 100.0, is_enemy=False, formation_index=0, load_order=5)
        enemy = _piece("champ_x", 100.0, is_enemy=True, formation_index=1, load_order=2)
        order = sorted([(team, _KIND_ACTION), (enemy, _KIND_ACTION)], key=_event_sort_key)
        assert order[0][0].is_enemy, "tie must break by load_order, not by side"

    def test_fraction_breaks_same_int_as(self):
        # 100.4 vs 100.6 both truncate to int AS 100 → the genuinely faster (higher
        # float) acts first, overriding champion_id and load_order.
        slow = _piece("aaa", 100.4, load_order=0)  # alphabetically first, lowest load_order
        fast = _piece("zzz", 100.6, load_order=9)
        order = sorted([(slow, _KIND_ACTION), (fast, _KIND_ACTION)], key=_event_sort_key)
        assert order[0][0].id == "zzz", "higher float attack_speed must act first"

    def test_movement_before_action_for_same_piece(self):
        from src.game.combat.engine import _KIND_MOVEMENT
        p = _piece("p", 100.0)
        order = sorted([(p, _KIND_ACTION), (p, _KIND_MOVEMENT)], key=_event_sort_key)
        assert order[0][1] == _KIND_MOVEMENT


class TestLoadOrderAssignment:
    def _mirror(self):
        from src.game.content import CHAMPION_DEF_BY_ID, build_champion_at_level
        from src.game.encounter import _champion_def_to_enemy
        ids = ["champ_ember_salamander", "champ_torrent_heron", "champ_aegis_tortoise"]
        team = [build_champion_at_level(i, 1) for i in ids]
        enemies = [_champion_def_to_enemy(CHAMPION_DEF_BY_ID[i], 1) for i in ids]
        return team, enemies

    def test_compile_loadout_assigns_formation_index_and_load_order(self):
        team, enemies = self._mirror()
        pieces, _, _ = compile_loadout(team, enemies, WeatherState.CLEAR, seed=42)
        n = len(pieces)
        assert [p.formation_index for p in pieces] == list(range(n)), "formation_index = input order"
        assert sorted(p.load_order for p in pieces) == list(range(n)), "load_order is a permutation"

    def test_load_order_is_side_mixed(self):
        # The seeded permutation must NOT be team-block-then-enemy: at least one
        # enemy outranks (lower load_order than) at least one team piece.
        team, enemies = self._mirror()
        pieces, _, _ = compile_loadout(team, enemies, WeatherState.CLEAR, seed=42)
        team_lo = [p.load_order for p in pieces if not p.is_enemy]
        enemy_lo = [p.load_order for p in pieces if p.is_enemy]
        assert min(enemy_lo) < max(team_lo), "load_order must mix sides (not team-first)"

    def test_deterministic(self):
        team, enemies = self._mirror()
        a = [p.load_order for p in compile_loadout(team, enemies, WeatherState.CLEAR, seed=42)[0]]
        b = [p.load_order for p in compile_loadout(team, enemies, WeatherState.CLEAR, seed=42)[0]]
        assert a == b, "load_order must be deterministic for a fixed seed (V.2/V.14)"


class TestBaselineParity:
    def test_speed_baselines_all_100(self):
        from src.game.content import _BASE_STATS
        assert _BASE_STATS["attack_speed"] == 100
        assert _BASE_STATS["move_speed"] == 100
        assert _BASE_STATS["mana_regen"] == 100

    def test_default_mana_cost_on_slot(self):
        # T.29c/V.48: cost lives on the ability def (ABILITY_MANA), default
        # 300_000; a built piece's slot carries it (+ max_mana = 2× default).
        from src.game.registries import DEFAULT_MANA_COST
        from src.game.content import get_champion
        from src.game.loadout import piece_from_champion
        assert DEFAULT_MANA_COST == 300_000
        piece = piece_from_champion(get_champion("champ_dawnwisp"))
        assert piece.actives[0].mana_cost == 300_000
        assert piece.actives[0].max_mana == 600_000


class TestFloatAttackSpeedOrder:
    """attack_speed is a float; an AS mul moves cadence AND tie-order together
    (T.29-pre, B.18) — no separate milli_AS field to desync."""

    def test_as_mul_moves_sort_key(self):
        # Two identical pieces; buff one's attack_speed by ×1.05. The buffed piece
        # must now sort first — the float drives the key directly.
        base = _piece("dup", 100.0, load_order=0)
        buffed = _piece("dup", 100.0, load_order=1)
        buffed.modifiers.append(Modifier("attack_speed", "mul", 1.05, Lifetime.COMBAT, "trait:test"))
        order = sorted([(base, _KIND_ACTION), (buffed, _KIND_ACTION)], key=_event_sort_key)
        assert order[0][0] is buffed, "an attack_speed mul must move the tie-order"

    def test_weather_buff_moves_sort_key(self):
        # Weather Favor is now a source="weather:" modifier; a favorable AS buff
        # must reorder the piece (RAIN buffs a THUNDER piece's attack_speed).
        from src.game.content import build_champion_at_level
        from src.game.loadout import _apply_weather_to_piece, piece_from_champion
        bus = EventBus()
        p = piece_from_champion(build_champion_at_level("champ_sparkfly", 1))
        before = p.stat("attack_speed")
        _apply_weather_to_piece(p, WeatherState.RAIN, bus)
        after = p.stat("attack_speed")
        assert after > before, "favorable weather must raise attack_speed"
        assert -round(after * 1000) < -round(before * 1000), "sort key must reflect the buff"

    def test_attack_speed_is_float_and_scales_with_level(self):
        from src.game.content import build_champion_at_level
        c1 = build_champion_at_level("champ_dawnwisp", 1)
        c3 = build_champion_at_level("champ_dawnwisp", 3)
        assert isinstance(c1.attack_speed, float)
        assert c3.attack_speed > c1.attack_speed
