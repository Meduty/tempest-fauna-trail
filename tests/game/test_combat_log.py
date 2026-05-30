from src.game.combat import resolve_combat
from src.game.combat_log import (
    format_combat_log,
    group_events_by_tick,
    render_combat_log,
)
from src.game.models import Champion, Enemy, WeatherState

_DEFAULTS = dict(
    id="champ",
    name="Champ",
    affinity=WeatherState.CLEAR,
    role="attacker",
    tier=1,
    level=1,
    max_hp=100,
    strength=20,
    intelligence=0,
    attack_speed=10_000,
    move_speed=10_000,
    mana_regen=0,
    threat=10,
    armor=0,
    resistance=0,
    attack_range=1,
    active_ability="zap",
    passive_ability="none",
    ability_cost=100,
)


def _champ(**over) -> Champion:
    data = dict(_DEFAULTS)
    data.update(over)
    return Champion(**data)


def _enemy(**over) -> Enemy:
    data = dict(_DEFAULTS)
    data["id"] = "enemy"
    data["name"] = "Enemy"
    data.update(over)
    return Enemy(**data)


def _quick_win():
    team = [_champ(id="hero", attack_range=12, attack_speed=60_000, strength=50)]
    enemies = [_enemy(id="mob", attack_speed=0, move_speed=0, max_hp=30)]
    return team, enemies, resolve_combat(team, enemies, WeatherState.RAIN, node_id="n1")


def test_group_events_by_tick_contiguous_and_ordered():
    team, enemies, result = _quick_win()
    grouped = group_events_by_tick(result)
    ticks = [tick for tick, _ in grouped]
    assert ticks == sorted(ticks)
    # Every event belongs to exactly its tick bucket.
    for tick, events in grouped:
        assert all(e.tick == tick for e in events)
    flat = [e for _, events in grouped for e in events]
    assert flat == result.events


def test_log_has_header_footer_and_attack_line():
    team, enemies, result = _quick_win()
    lines = format_combat_log(result, team=team, enemies=enemies)
    text = "\n".join(lines)
    assert lines[0] == "=== Tempest Fauna Trail — Combat Log ==="
    assert "Node: n1 | Weather: rain" in text
    assert "[tick 0001]" in text
    assert "hero attacks mob — 50 physical" in text
    assert "mob is defeated by hero" in text
    assert "=== Result: WIN ===" in text
    assert "Survivors: hero" in text
    assert "Damage dealt: hero 50" in text


def test_log_tracks_running_hp_when_rosters_given():
    team, enemies, result = _quick_win()
    text = render_combat_log(result, team=team, enemies=enemies)
    assert "(mob: 30 -> 0)" in text


def test_log_omits_hp_trace_without_rosters():
    _, _, result = _quick_win()
    text = render_combat_log(result)
    assert "hero attacks mob — 50 physical" in text
    assert "->" not in text  # no HP trace, no move targets in this fight


def test_log_handles_stalemate_with_no_events():
    team = [_champ(id="hero", attack_range=1, move_speed=0)]
    enemies = [_enemy(id="mob", attack_range=1, move_speed=0)]
    result = resolve_combat(team, enemies, WeatherState.CLEAR)
    text = render_combat_log(result, team=team, enemies=enemies)
    assert "=== Result: DRAW ===" in text
    assert "timed out" in text


def test_cast_and_move_lines_render():
    team = [
        _champ(
            id="hero",
            attack_range=1,
            attack_speed=60_000,
            move_speed=60_000,
            mana_regen=1,
            ability_cost=6,
            intelligence=20,
            strength=0,
        )
    ]
    enemies = [_enemy(id="mob", attack_speed=0, move_speed=0, max_hp=1000, resistance=0)]
    result = resolve_combat(team, enemies, WeatherState.CLEAR)
    text = render_combat_log(result, team=team, enemies=enemies)
    # T.30 §4 fix: fallback = (0.2+4.2)*max(0,20) = 88
    assert "hero casts at mob — 88 magical" in text
    assert "hero moves to (" in text


def test_log_is_deterministic():
    team, enemies, result = _quick_win()
    first = render_combat_log(result, team=team, enemies=enemies)
    second = render_combat_log(result, team=team, enemies=enemies)
    assert first == second
