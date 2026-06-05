"""Canonical same-tick total order — B.14 fix / V.34 (T.33a).

The combat tiebreak must be a side-independent total order
`(-AS_int, -milli_AS, champion_id, load_order, kind)`, so equal-attack-speed
ties never systematically favour the player team.
"""
from src.game.combat.engine import _KIND_ACTION, _event_sort_key
from src.game.loadout import compile_loadout
from src.game.models import WeatherState
from src.game.piece import Piece


def _piece(id, as_, milli, *, is_enemy=False, formation_index=0, load_order=0):
    return Piece(
        id=id,
        base_stats={"attack_speed": float(as_), "milli_AS": float(milli)},
        is_enemy=is_enemy,
        formation_index=formation_index,
        load_order=load_order,
    )


class TestSortKeySideIndependent:
    def test_tie_broken_by_load_order_not_side(self):
        # Identical AS+milli. Team has the LOWER formation_index (the old bias
        # would make it act first); the enemy has the lower load_order.
        team = _piece("champ_x", 100, 100_000, is_enemy=False, formation_index=0, load_order=5)
        enemy = _piece("champ_x", 100, 100_000, is_enemy=True, formation_index=1, load_order=2)
        order = sorted([(team, _KIND_ACTION), (enemy, _KIND_ACTION)], key=_event_sort_key)
        assert order[0][0].is_enemy, "tie must break by load_order, not by side"

    def test_milli_breaks_same_int_as(self):
        # 100.4 vs 100.6 both round to int AS 100 → the genuinely faster (higher
        # milli) acts first, overriding champion_id and load_order.
        slow = _piece("aaa", 100, 100_400, load_order=0)  # alphabetically first, lowest load_order
        fast = _piece("zzz", 100, 100_600, load_order=9)
        order = sorted([(slow, _KIND_ACTION), (fast, _KIND_ACTION)], key=_event_sort_key)
        assert order[0][0].id == "zzz", "higher milli_AS must act first"

    def test_movement_before_action_for_same_piece(self):
        from src.game.combat.engine import _KIND_MOVEMENT
        p = _piece("p", 100, 100_000)
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

    def test_ability_cost_lifted(self):
        from src.game.content import _ABILITY_COST, get_champion
        from src.game.loadout import DEFAULT_ABILITY_COST
        assert _ABILITY_COST == 300_000
        assert DEFAULT_ABILITY_COST == 300_000
        assert get_champion("champ_dawnwisp").ability_cost == 300_000


class TestMilliTracksAttackSpeed:
    def test_milli_tracks_as_through_weather(self):
        # Weather scales attack_speed via as_mult; milli_AS must ride the same
        # mult or sub-integer ordering goes stale post-weather (V.34).
        from src.game.content import build_champion_at_level
        from src.game.loadout import _apply_weather_to_piece, piece_from_champion
        p = piece_from_champion(build_champion_at_level("champ_sparkfly", 1))
        _apply_weather_to_piece(p, WeatherState.RAIN)  # buffs THUNDER attack_speed
        as_, milli = p.base_stats["attack_speed"], p.base_stats["milli_AS"]
        # milli stays within one AS-unit of attack_speed×1000 (rounding aside).
        assert abs(milli - as_ * 1000) < 1000, f"milli {milli} desynced from AS {as_}"

    def test_milli_scales_with_level(self):
        from src.game.content import build_champion_at_level
        c1 = build_champion_at_level("champ_dawnwisp", 1)
        c3 = build_champion_at_level("champ_dawnwisp", 3)
        assert c3.milli_AS > c1.milli_AS
        assert abs(c1.milli_AS - c1.attack_speed * 1000) < 1000
