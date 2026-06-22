from src.game.combat import (
    BOARD_HEIGHT,
    BOARD_WIDTH,
    ENERGY_THRESHOLD,
    MAX_TICKS,
    ROUND_TICKS,
    hex_distance,
    resolve_combat,
)
from src.game.combat.engine import _next_step_toward, _select_target, _slow_factor
from src.game.status import StatusInstance
from src.game.models import (
    Champion,
    CombatOutcome,
    Enemy,
    WeatherState,
)
from src.game.piece import Piece
from src.game.registries import register_ability_mana

# Test ability "zap" is unregistered; author its mana cost low (T.29c/V.48:
# cost lives on the ability def, default 300_000 — too high to fill in these
# short fights). Matches the pre-T.29c per-piece ability_cost=100 these used.
register_ability_mana("zap", mana_cost=100)

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
    active_abilities=["zap"],
    passive_ability="none",
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


def _piece(
    piece_id: str,
    q: int,
    r: int,
    *,
    is_enemy: bool = False,
    attack_range: int = 1,
    threat: int = 10,
    hp: int = 100,
) -> Piece:
    """A minimal runtime Piece for exercising engine helpers directly."""
    return Piece(
        id=piece_id,
        base_stats={"attack_range": float(attack_range), "threat": float(threat)},
        is_enemy=is_enemy,
        hp=float(hp),
        max_hp=float(hp),
        position_q=q,
        position_r=r,
    )


# --- Slow soft-CC (B.25): `slow` throttles meter advancement ------------------


def test_slow_factor_scales_with_stacks_and_floors():
    p = _piece("s", 0, 0)
    assert _slow_factor(p) == 1.0  # no slow
    p.statuses.append(StatusInstance(status_id="slow", remaining_ticks=99, stacks=1))
    assert _slow_factor(p) == 0.85
    p.statuses[0].stacks = 2
    assert abs(_slow_factor(p) - 0.70) < 1e-9
    p.statuses[0].stacks = 10  # floored — soft CC never hard-locks
    assert _slow_factor(p) == 0.40


def test_slow_changes_combat_outcome_end_to_end():
    # Keep weather FIXED (SNOW) and toggle only Living World, whose sole SNOW effect
    # is applying `slow` to enemies — so any diff is attributable to `slow`, not to
    # Weather Favor (B.25). Comparing CLEAR vs SNOW would be confounded by weather.
    from src.game.augments import RunModifiers
    from src.game.content import CHAMPION_ROSTER, ENEMY_ROSTER

    team = list(CHAMPION_ROSTER.values())[:6]
    enemies = list(ENEMY_ROSTER.values())[:6]
    base = resolve_combat(team, enemies, WeatherState.SNOW)
    slowed = resolve_combat(team, enemies, WeatherState.SNOW,
                            run_mods=RunModifiers(augments=["living_world"], augment_state={}))
    assert base.to_dict() != slowed.to_dict()


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
    assert result.duration_ticks >= MAX_TICKS
    assert result.turns == 0
    assert result.rounds >= MAX_TICKS // ROUND_TICKS


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
    piece = _piece("hero", 0, 0)
    # Identical threat, distance, hp%, hp — only piece id differs.
    a = _piece("a_mob", 9, 0, is_enemy=True)
    b = _piece("z_mob", 9, 0, is_enemy=True)
    assert _select_target(piece, [b, a]) is a


def test_dead_target_triggers_retarget():
    team = [_champ(id="hero", attack_range=12, attack_speed=60_000, strength=100)]
    enemies = [
        _enemy(id="first", attack_speed=0, move_speed=0, max_hp=30),
        _enemy(id="second", attack_speed=0, move_speed=0, max_hp=30),
    ]
    result = resolve_combat(team, enemies, WeatherState.CLEAR)
    attacks = [e for e in result.events if e.event_type == "attack"]
    # With T24 formation planner, "second" is placed closer to hero (center-out
    # packing: row 2 vs row 3) so gets targeted first by proximity tiebreak.
    assert attacks[0].target_id == "second"
    assert attacks[1].target_id == "first"
    assert result.outcome == CombatOutcome.WIN


# --- 6.5 Pathing -------------------------------------------------------------


def test_path_routes_around_blocker():
    piece = _piece("hero", 0, 0, attack_range=1)
    enemy = _piece("mob", 2, 0, is_enemy=True)
    occupied = {(1, 0), (2, 0)}  # direct route + enemy cell blocked
    step = _next_step_toward(piece, [enemy], occupied)
    assert step == (0, 1)


def test_no_path_returns_none():
    piece = _piece("hero", 0, 0, attack_range=1)
    enemy = _piece("mob", 5, 5, is_enemy=True)
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
    # Affinity Clash at CLEAR weather (Weather Favor inert). Enemy is RAIN-affinity:
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

    # Raw auto = 1.0 * 50 = 50; enemy armor 0. Predator x1.30 -> 65, prey x0.70 -> 35.
    assert predator_hit == 65
    assert prey_hit == 35


# --- 6.x Penetration ---------------------------------------------------------


def test_penetration_erodes_target_mitigation():
    # Target armor 100 -> reduction 100/200 = 0.5; raw auto STR 50 -> 25 dealt.
    # Flat pen 50: armor 50 -> 50/150 reduction -> 50 * (2/3) ~= 33.
    # 100% pen: armor 0 -> no reduction -> 50 dealt.
    def _first_hit(**champ_over):
        team = [
            _champ(
                id="hero",
                attack_range=12,
                attack_speed=60_000,
                strength=50,
                **champ_over,
            )
        ]
        enemies = [
            _enemy(id="mob", attack_speed=0, move_speed=0, max_hp=100_000, armor=100)
        ]
        result = resolve_combat(team, enemies, WeatherState.CLEAR)
        return next(e for e in result.events if e.event_type == "attack").amount

    base = _first_hit()
    flat = _first_hit(penetration=50)
    full = _first_hit(penetration_pct=1.0)
    assert base == 25
    assert full == 50
    assert base < flat < full


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
            mana_regen=1,
            intelligence=20,
            strength=0,
        )
    ]
    enemies = [_enemy(id="mob", attack_speed=0, move_speed=0, max_hp=1000, resistance=0)]
    result = resolve_combat(team, enemies, WeatherState.CLEAR)
    casts = [e for e in result.events if e.event_type == "cast"]
    assert casts, "expected at least one cast"
    # T.30 §4 fix: fallback scales on max(STR, INT) * (STR_COEFF + INT_COEFF)
    # = (0.2 + 4.2) * max(0, 20) = 4.4 * 20 = 88
    assert casts[0].amount == 88


def test_board_constants():
    assert BOARD_WIDTH * BOARD_HEIGHT == 70
    assert ENERGY_THRESHOLD == 60_000
