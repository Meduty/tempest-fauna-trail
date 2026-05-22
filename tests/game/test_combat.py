from src.game.combat import (
    BOARD_HEIGHT,
    BOARD_WIDTH,
    ENERGY_THRESHOLD,
    MAX_TICKS,
    ROUND_TICKS,
    _next_step_toward,
    _select_target,
    effective_as,
    effective_mr_tick,
    effective_ms,
    hex_distance,
    resolve_combat,
)
from src.game.models import (
    Champion,
    CombatOutcome,
    CombatPieceState,
    Enemy,
    WeatherState,
)

# --- Factories ---------------------------------------------------------------

_CHAMP_DEFAULTS = dict(
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
    data = dict(_CHAMP_DEFAULTS)
    data.update(over)
    return Champion(**data)


def _enemy(**over) -> Enemy:
    data = dict(_CHAMP_DEFAULTS)
    data["id"] = "enemy"
    data["name"] = "Enemy"
    data.update(over)
    return Enemy(**data)


def _state(
    piece_id: str,
    is_enemy: bool,
    q: int,
    r: int,
    attack_range: int = 1,
    affinity: WeatherState = WeatherState.CLEAR,
) -> CombatPieceState:
    return CombatPieceState(
        piece_id=piece_id,
        is_enemy=is_enemy,
        affinity=affinity,
        tier=1,
        level=1,
        max_hp=100,
        hp=100,
        strength=10,
        intelligence=0,
        attack_speed=100,
        move_speed=100,
        mana_regen=0,
        threat=10,
        armor=0,
        resistance=0,
        attack_range=attack_range,
        ability_cost=100,
        position_q=q,
        position_r=r,
    )


# --- 6.1 Determinism ---------------------------------------------------------


def test_resolve_combat_is_deterministic():
    team = [_champ(id="c1", attack_range=12, attack_speed=30_000, strength=12)]
    enemies = [_enemy(id="e1", attack_range=12, attack_speed=25_000, strength=8, max_hp=70)]
    first = resolve_combat(team, enemies, WeatherState.RAIN, node_id="n1")
    second = resolve_combat(team, enemies, WeatherState.RAIN, node_id="n1")
    assert first.to_dict() == second.to_dict()


# --- 6.2 Basic outcomes ------------------------------------------------------


def test_favorable_matchup_wins():
    team = [_champ(id="hero", attack_range=12, attack_speed=60_000, strength=50)]
    enemies = [_enemy(id="mob", attack_speed=0, move_speed=0, max_hp=30)]
    result = resolve_combat(team, enemies, WeatherState.CLEAR)
    assert result.outcome == CombatOutcome.WIN
    assert result.surviving_team_ids == ["hero"]
    assert result.surviving_enemy_ids == []
    assert result.duration_ticks == 1


def test_inverted_matchup_loses():
    team = [_champ(id="hero", attack_range=12, attack_speed=60_000, strength=0, max_hp=10)]
    enemies = [_enemy(id="boss", attack_range=12, attack_speed=60_000, strength=100, max_hp=1000)]
    result = resolve_combat(team, enemies, WeatherState.CLEAR)
    assert result.outcome == CombatOutcome.LOSS
    assert result.surviving_team_ids == []
    assert result.surviving_enemy_ids == ["boss"]


def test_stalemate_reaches_draw_timeout():
    team = [_champ(id="hero", attack_range=1, move_speed=0, attack_speed=10_000)]
    enemies = [_enemy(id="mob", attack_range=1, move_speed=0, attack_speed=10_000)]
    result = resolve_combat(team, enemies, WeatherState.CLEAR)
    assert result.outcome == CombatOutcome.DRAW
    assert result.timed_out is True
    assert result.duration_ticks == MAX_TICKS
    assert result.turns == 0
    assert result.rounds == MAX_TICKS // ROUND_TICKS


# --- 6.3 Meter semantics -----------------------------------------------------


def test_action_overflow_carries_after_trigger():
    # attack_speed 25000: meter crosses threshold at ticks 3 and 5 only when
    # overflow is preserved (without carry the second trigger lands at tick 6).
    team = [_champ(id="hero", attack_range=12, attack_speed=25_000, strength=10)]
    enemies = [_enemy(id="dummy", attack_speed=0, move_speed=0, max_hp=100_000)]
    result = resolve_combat(team, enemies, WeatherState.CLEAR)
    attack_ticks = [e.tick for e in result.events if e.event_type == "attack"]
    assert attack_ticks[:2] == [3, 5]


def test_movement_holds_when_in_range():
    team = [_champ(id="hero", attack_range=12, attack_speed=60_000, move_speed=200_000, strength=50)]
    enemies = [_enemy(id="mob", attack_speed=0, move_speed=0, max_hp=30)]
    result = resolve_combat(team, enemies, WeatherState.CLEAR)
    assert result.outcome == CombatOutcome.WIN
    assert [e for e in result.events if e.event_type == "move"] == []


def test_idle_hold_produces_no_actions():
    # Out of range, immobile, no mana: every action trigger idle-holds.
    team = [_champ(id="hero", attack_range=1, move_speed=0, attack_speed=60_000)]
    enemies = [_enemy(id="mob", attack_range=1, move_speed=0, attack_speed=60_000)]
    result = resolve_combat(team, enemies, WeatherState.CLEAR)
    assert result.turns == 0
    assert result.outcome == CombatOutcome.DRAW


# --- 6.4 Targeting -----------------------------------------------------------


def test_threat_priority_beats_distance():
    # enemy idx0 spawns closer (9,0); idx1 farther (9,1) but higher threat.
    team = [_champ(id="hero", attack_range=12, attack_speed=60_000, strength=20)]
    enemies = [
        _enemy(id="near", threat=0, attack_speed=0, move_speed=0, max_hp=500),
        _enemy(id="far", threat=100, attack_speed=0, move_speed=0, max_hp=500),
    ]
    result = resolve_combat(team, enemies, WeatherState.CLEAR)
    first_attack = next(e for e in result.events if e.event_type == "attack")
    assert first_attack.target_id == "far"


def test_select_target_tie_chain_falls_to_piece_id():
    piece = _state("hero", False, 0, 0)
    # Identical threat, distance, hp%, hp — only piece_id differs.
    a = _state("a_mob", True, 9, 0)
    b = _state("z_mob", True, 9, 0)
    assert _select_target(piece, [b, a]) is a


def test_dead_target_triggers_retarget():
    team = [_champ(id="hero", attack_range=12, attack_speed=60_000, strength=100)]
    enemies = [
        _enemy(id="first", attack_speed=0, move_speed=0, max_hp=30),
        _enemy(id="second", attack_speed=0, move_speed=0, max_hp=30),
    ]
    result = resolve_combat(team, enemies, WeatherState.CLEAR)
    attacks = [e for e in result.events if e.event_type == "attack"]
    assert attacks[0].target_id == "first"
    assert attacks[1].target_id == "second"
    assert result.outcome == CombatOutcome.WIN


# --- 6.5 Pathing -------------------------------------------------------------


def test_path_routes_around_blocker():
    piece = _state("hero", False, 0, 0, attack_range=1)
    enemy = _state("mob", True, 2, 0)
    occupied = {(1, 0), (2, 0)}  # direct route + enemy cell blocked
    step = _next_step_toward(piece, [enemy], occupied)
    assert step == (0, 1)


def test_no_path_returns_none():
    piece = _state("hero", False, 0, 0, attack_range=1)
    enemy = _state("mob", True, 5, 5)
    occupied = {(1, 0), (0, 1), (5, 5)}  # both reachable neighbours blocked
    assert _next_step_toward(piece, [enemy], occupied) is None


def test_hex_distance():
    assert hex_distance(0, 0, 0, 0) == 0
    assert hex_distance(0, 0, 2, 0) == 2
    assert hex_distance(0, 0, 0, 3) == 3
    assert hex_distance(0, 0, 9, 0) == 9


# --- 6.6 Weather integration -------------------------------------------------


def test_weather_modifiers_change_combat_output():
    # THUNDER buffs THUNDER-affinity pieces (STR x1.10) -> harder first hit.
    team = [
        _champ(
            id="hero",
            affinity=WeatherState.THUNDER,
            attack_range=12,
            attack_speed=60_000,
            strength=50,
        )
    ]
    enemies = [_enemy(id="mob", attack_speed=0, move_speed=0, max_hp=1000)]

    clear = resolve_combat(team, enemies, WeatherState.CLEAR)
    thunder = resolve_combat(team, enemies, WeatherState.THUNDER)

    clear_hit = next(e for e in clear.events if e.event_type == "attack").amount
    thunder_hit = next(e for e in thunder.events if e.event_type == "attack").amount
    assert thunder_hit > clear_hit


def test_affinity_damage_triangle_scales_hits():
    # System B at CLEAR weather (System A inert). Enemy is RAIN-affinity:
    # SNOW preys on RAIN (predator, x1.10); CLOUDY is RAIN's prey (x0.90).
    enemies = [
        _enemy(
            id="mob",
            affinity=WeatherState.RAIN,
            attack_speed=0,
            move_speed=0,
            max_hp=1000,
        )
    ]
    predator = [
        _champ(
            id="hero",
            affinity=WeatherState.SNOW,
            attack_range=12,
            attack_speed=60_000,
            strength=50,
        )
    ]
    prey = [
        _champ(
            id="hero",
            affinity=WeatherState.CLOUDY,
            attack_range=12,
            attack_speed=60_000,
            strength=50,
        )
    ]

    predator_hit = next(
        e
        for e in resolve_combat(predator, enemies, WeatherState.CLEAR).events
        if e.event_type == "attack"
    ).amount
    prey_hit = next(
        e
        for e in resolve_combat(prey, enemies, WeatherState.CLEAR).events
        if e.event_type == "attack"
    ).amount

    # Raw auto = 1.0 * 50 = 50; enemy armor 0. Predator x1.10 -> 55, prey x0.90 -> 45.
    assert predator_hit == 55
    assert prey_hit == 45


# --- 6.7 BattleResult integrity ----------------------------------------------


def test_battle_result_integrity():
    team = [_champ(id="hero", attack_range=12, attack_speed=40_000, strength=30)]
    enemies = [_enemy(id="mob", attack_range=12, attack_speed=20_000, strength=10, max_hp=120)]
    result = resolve_combat(team, enemies, WeatherState.CLEAR, node_id="node-7")

    # turns counts exactly the auto + cast events.
    action_events = [e for e in result.events if e.event_type in ("attack", "cast")]
    assert result.turns == len(action_events)

    # rounds derives from duration.
    assert result.rounds == (result.duration_ticks + ROUND_TICKS - 1) // ROUND_TICKS

    # Damage dealt by attackers equals damage taken by victims, event by event.
    dealt_total = sum(e.amount for e in action_events)
    assert dealt_total == sum(result.team_damage_dealt.values())
    assert dealt_total == sum(result.team_damage_taken.values())

    # Survivors and the dead are mutually exclusive and consistent.
    survivors = set(result.surviving_team_ids) | set(result.surviving_enemy_ids)
    dead = {e.actor_id for e in result.events if e.event_type == "death"}
    assert survivors.isdisjoint(dead)
    assert result.node_id == "node-7"


def test_cast_path_consumes_mana_and_deals_magic_damage():
    team = [
        _champ(
            id="hero",
            attack_range=12,
            attack_speed=60_000,
            mana_regen=50,
            ability_cost=100,
            intelligence=20,
            strength=0,
        )
    ]
    enemies = [_enemy(id="mob", attack_speed=0, move_speed=0, max_hp=1000, resistance=0)]
    result = resolve_combat(team, enemies, WeatherState.CLEAR)
    casts = [e for e in result.events if e.event_type == "cast"]
    assert casts, "expected at least one cast"
    # Ability raw damage = 0.2*STR + 4.2*INT = 84 with STR 0, INT 20.
    assert casts[0].amount == 84


# --- Effective stat helpers --------------------------------------------------


def test_effective_stat_helpers_are_integer_identities():
    piece = _state("hero", False, 0, 0)
    assert effective_as(piece) == piece.attack_speed
    assert effective_ms(piece) == piece.move_speed
    assert effective_mr_tick(piece) == piece.mana_regen


def test_board_constants():
    assert BOARD_WIDTH * BOARD_HEIGHT == 70
    assert ENERGY_THRESHOLD == 60_000
