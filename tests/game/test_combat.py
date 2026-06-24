import pytest

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
    # Symmetric idle 1v1 → sudden death wipes both on the same tick → true DRAW
    # (no survivors, V.60). DRAW is by survivors, not by the timed_out flag.
    team = [_champ(id="hero", attack_range=1, move_speed=0, attack_speed=10_000)]
    enemies = [_enemy(id="mob", attack_range=1, move_speed=0, attack_speed=10_000)]
    result = resolve_combat(team, enemies, WeatherState.CLEAR)
    assert result.outcome == CombatOutcome.DRAW
    assert result.timed_out is True
    assert not result.surviving_team_ids and not result.surviving_enemy_ids  # true mutual wipe
    assert result.duration_ticks >= MAX_TICKS
    assert result.turns == 0
    assert result.rounds >= MAX_TICKS // ROUND_TICKS


def test_timed_out_with_survivor_is_win_loss_not_draw():
    """V.60: a fight that times out but has a clear survivor resolves WIN/LOSS —
    `timed_out` must not force DRAW. Asymmetric idle: the tankier side outlasts
    the sudden-death DOT and survives, so the other side loses."""
    team = [_champ(id="hero", attack_range=1, move_speed=0, attack_speed=10_000, max_hp=400_000)]
    enemies = [_enemy(id="mob", attack_range=1, move_speed=0, attack_speed=10_000, max_hp=100)]
    result = resolve_combat(team, enemies, WeatherState.CLEAR)
    assert result.timed_out is True
    assert result.outcome == CombatOutcome.WIN  # hero outlasts → survivor → not DRAW
    assert result.surviving_team_ids and not result.surviving_enemy_ids


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


# --- T.37a: combat-view replay backend — event stream + initial snapshot -----


def _recorder_harness():
    """A CombatContext + registered recorder over two live pieces (src, tgt)."""
    from src.game.effects import EventBus
    from src.game.combat.context import CombatContext
    from src.game.combat.recorder import BattleResultRecorder

    src = Piece(id="src", base_stats={"strength": 50.0, "attack_range": 1.0},
                hp=200.0, max_hp=200.0, position_q=0, position_r=0)
    tgt = Piece(id="tgt", base_stats={"attack_range": 1.0}, is_enemy=True,
                hp=200.0, max_hp=200.0, position_q=1, position_r=0)
    pieces = [src, tgt]
    bus = EventBus()
    rec = BattleResultRecorder(pieces, WeatherState.CLEAR, node_id="n")
    rec.register(bus)
    ctx = CombatContext(pieces, bus, WeatherState.CLEAR, seed=1)
    ctx.current_tick = 5
    return ctx, rec, src, tgt


def _types(rec):
    return [e.event_type for e in rec._events]


def test_recorder_emits_heal_dot_status_spawn_despawn_beats():
    from src.game.effects import SourceTag
    from src.game.combat.recorder import (
        EVENT_HEAL, EVENT_DOT, EVENT_STATUS, EVENT_STATUS_EXPIRE,
        EVENT_SPAWN, EVENT_DESPAWN,
    )
    ctx, rec, src, tgt = _recorder_harness()

    tgt.hp = 100.0
    ctx.heal(src, tgt, 40.0)                       # heal beat (+40 → hp_after 140)
    ctx.deal_damage(src, tgt, 30.0, SourceTag.DOT)  # dot beat
    ctx.apply_status(tgt, "burn", duration_ticks=300)  # status apply
    ctx.remove_status(tgt, "burn")                  # status expire

    summon = Piece(id="turret", base_stats={"attack_range": 1.0}, is_enemy=True,
                   hp=50.0, max_hp=50.0, summon=True)
    ctx.spawn(summon, 4, 2)                          # spawn beat
    ctx.expire_summon(summon)                        # despawn beat (NOT death)

    types = _types(rec)
    # exactly one beat per kind, no drops, no death for the expiry
    assert types.count(EVENT_HEAL) == 1
    assert types.count(EVENT_DOT) == 1
    assert types.count(EVENT_STATUS) == 1
    assert types.count(EVENT_STATUS_EXPIRE) == 1
    assert types.count(EVENT_SPAWN) == 1
    assert types.count(EVENT_DESPAWN) == 1
    assert "death" not in types

    heal = next(e for e in rec._events if e.event_type == EVENT_HEAL)
    assert heal.amount == 40 and heal.hp_after == 140
    # T.12c-B view contract: the heal beat names the healed piece (ally-halo VFX
    # finds its cell by target_id) and the status beat names the afflicted piece +
    # status id (apply-flash finds the cell by actor_id, colours by note).
    assert heal.target_id == tgt.id
    status = next(e for e in rec._events if e.event_type == EVENT_STATUS)
    assert status.actor_id == tgt.id and status.note == "burn"
    dot = next(e for e in rec._events if e.event_type == EVENT_DOT)
    assert dot.hp_after == int(tgt.hp)
    # T.37c: spawn carries structured coords, not a parsed `note` string (B.28).
    spawn = next(e for e in rec._events if e.event_type == EVENT_SPAWN)
    assert (spawn.dest_q, spawn.dest_r) == (4, 2)


def test_move_and_spawn_carry_structured_coords():
    """T.37c: `move`/`spawn` beats expose `dest_q`/`dest_r` int fields (B.28)."""
    from src.game.combat.recorder import EVENT_MOVE
    ctx, rec, src, tgt = _recorder_harness()
    rec.record_move("hero", tick=7, dest_q=3, dest_r=5)
    mv = next(e for e in rec._events if e.event_type == EVENT_MOVE)
    assert (mv.dest_q, mv.dest_r) == (3, 5)
    assert mv.note == ""  # destination no longer hidden in the note string


def test_battle_event_dest_coords_round_trip_and_legacy_default():
    """`dest_q`/`dest_r` survive serialization; legacy payloads default to -1."""
    from src.game.models import BattleEvent
    from src.game.combat.recorder import EVENT_MOVE
    ev = BattleEvent(tick=2, actor_id="hero", target_id=None,
                     event_type=EVENT_MOVE, dest_q=4, dest_r=1)
    back = BattleEvent.from_dict(ev.to_dict())
    assert (back.dest_q, back.dest_r) == (4, 1)
    legacy = BattleEvent.from_dict({"tick": 1, "actor_id": "x",
                                    "target_id": None, "event_type": EVENT_MOVE})
    assert (legacy.dest_q, legacy.dest_r) == (-1, -1)


def test_status_beat_fires_once_per_acquisition_not_per_reapply():
    """V.54: a `status` beat fires on acquisition only — re-applies/refreshes of
    an already-held status emit no new beat (kills sudden-death/poison spam).
    A fresh acquisition after expiry beats again."""
    from src.game.combat.recorder import EVENT_STATUS, EVENT_STATUS_EXPIRE
    ctx, rec, _src, tgt = _recorder_harness()

    ctx.apply_status(tgt, "burn", duration_ticks=300)
    ctx.apply_status(tgt, "burn", duration_ticks=300)  # refresh — no new beat
    ctx.apply_status(tgt, "burn", duration_ticks=300)  # refresh — no new beat
    assert sum(1 for e in rec._events if e.event_type == EVENT_STATUS) == 1

    ctx.remove_status(tgt, "burn")
    assert sum(1 for e in rec._events if e.event_type == EVENT_STATUS_EXPIRE) == 1
    ctx.apply_status(tgt, "burn", duration_ticks=300)  # re-acquired after expiry → beats again
    assert sum(1 for e in rec._events if e.event_type == EVENT_STATUS) == 2


def test_true_damage_dot_emits_dot_beat_via_is_dot():
    """V.54 (T.12b): a true-damage DOT tick (sudden_death) emits a `dot` beat when
    is_dot=True — it was silent before (SourceTag.TRUE matched no beat branch),
    which made sudden death instakill with no animation."""
    from src.game.combat.recorder import EVENT_DOT
    from src.game.effects import SourceTag

    ctx, rec, src, tgt = _recorder_harness()
    tgt.hp = 1000.0
    ctx.deal_damage(src, tgt, 50.0, SourceTag.TRUE, is_dot=True)  # sudden-death-style tick
    dots = [e for e in rec._events if e.event_type == EVENT_DOT]
    assert len(dots) == 1 and dots[0].hp_after == int(tgt.hp)

    # without is_dot, true damage stays beatless (the old silent path)
    ctx2, rec2, s2, t2 = _recorder_harness()
    ctx2.deal_damage(s2, t2, 50.0, SourceTag.TRUE)
    assert not [e for e in rec2._events if e.event_type == EVENT_DOT]


def test_deal_damage_rejects_unknown_damage_type():
    """V.58 (B.29): `damage_type` is a closed vocabulary — `deal_damage` raises
    on anything outside {physical, magical, true} so a typo like the old "magic"
    can never silently fall through to the armor branch again."""
    from src.game.combat.context import _VALID_DAMAGE_TYPES
    assert _VALID_DAMAGE_TYPES == frozenset({"physical", "magical", "true"})

    ctx, _rec, src, tgt = _recorder_harness()
    from src.game.effects import SourceTag
    # valid types do not raise
    for dt in ("physical", "magical", "true"):
        ctx.deal_damage(src, tgt, 10.0, SourceTag.ABILITY, damage_type=dt)
    # the old typo now raises
    with pytest.raises(ValueError):
        ctx.deal_damage(src, tgt, 10.0, SourceTag.ABILITY, damage_type="magic")


def test_magical_mitigates_by_resistance_not_armor():
    """B.29 regression: magical damage keys off resistance, physical off armor."""
    from src.game.effects import SourceTag
    # high resistance, zero armor → magical should be heavily reduced, physical not
    ctx_a, _a, src_a, tgt_a = _recorder_harness()
    ctx_b, _b, src_b, tgt_b = _recorder_harness()
    for t in (tgt_a, tgt_b):
        t.base_stats["resistance"] = 200.0
        t.base_stats["armor"] = 0.0
        t.hp = t.max_hp = 100000.0
    mag = ctx_a.deal_damage(src_a, tgt_a, 1000.0, SourceTag.ABILITY, damage_type="magical")
    phys = ctx_b.deal_damage(src_b, tgt_b, 1000.0, SourceTag.ABILITY, damage_type="physical")
    assert mag < phys  # resistance bit the magical hit, armor (0) left physical intact


def test_ability_damage_emits_ability_beat_excluded_from_turns():
    """T.37: ability damage emits an `ability` beat (separate from the `cast`
    activation marker) carrying final post-mitigation amount + damage_type +
    hp_after; `turns` counts attack+cast only ⇒ byte-identical sims (V.54)."""
    from src.game.combat import (
        EVENT_ABILITY, EVENT_ATTACK, EVENT_CAST, resolve_combat,
    )
    from src.game.content import CHAMPION_ROSTER, ENEMY_ROSTER
    from src.game.models import WeatherState

    team = [CHAMPION_ROSTER["champ_aurion"]]
    enemies = list(ENEMY_ROSTER.values())[:6]
    result = resolve_combat(team, enemies, WeatherState.CLEAR)

    ability = [e for e in result.events if e.event_type == EVENT_ABILITY]
    assert ability, "expected ability-damage beats from a registered caster"
    for e in ability:
        assert e.amount > 0                       # final post-mitigation figure
        assert e.hp_after >= 0                     # HP truth stamped
        assert e.note in ("physical", "magical", "magic", "true")
        assert e.event_type != EVENT_CAST          # distinct from the activation marker

    # turns excludes ability beats → unchanged vs pre-`ability` (byte-identical)
    atk = sum(1 for e in result.events if e.event_type == EVENT_ATTACK)
    cast = sum(1 for e in result.events if e.event_type == EVENT_CAST)
    assert result.turns == atk + cast


def test_attack_beat_hp_after_is_exact_under_barrier():
    """V.54 guard: `amount` is full pre-barrier damage (DPS accounting), but
    `hp_after` is the real HP — so a barrier makes amount != HP-delta, yet the
    bar still reconstructs exactly."""
    from src.game.combat.recorder import EVENT_ATTACK
    ctx, rec, src, tgt = _recorder_harness()

    before = tgt.hp
    ctx.grant_barrier(tgt, 10_000.0)   # soaks everything
    ctx.trigger_basic_attack(src, tgt)

    atk = next(e for e in rec._events if e.event_type == EVENT_ATTACK)
    assert atk.amount > 0                # pre-barrier damage was dealt for accounting
    assert tgt.hp == before             # but barrier ate it — no HP lost
    assert atk.hp_after == int(tgt.hp)  # hp_after is exact (subtraction would drift)
    assert atk.barrier_after == int(tgt.barrier_total)


def test_initial_pieces_snapshot_and_board_dims():
    team = [_champ(id="hero", strength=40)]
    enemies = [_enemy(id="mob", max_hp=60)]
    result = resolve_combat(team, enemies, WeatherState.CLEAR)

    ids = {s.id for s in result.initial_pieces}
    assert ids == {"hero", "mob"}
    assert result.board_width == BOARD_WIDTH
    assert result.board_height == BOARD_HEIGHT
    hero = next(s for s in result.initial_pieces if s.id == "hero")
    assert hero.is_enemy is False and hero.spawn_tick == 0
    assert (hero.q, hero.r) == (0, 0)          # assign_spawns left-column pack
    mob = next(s for s in result.initial_pieces if s.id == "mob")
    assert mob.is_enemy is True


def test_battleresult_roundtrip_with_snapshot_and_legacy_default():
    team = [_champ(id="hero", strength=40)]
    enemies = [_enemy(id="mob", max_hp=60)]
    result = resolve_combat(team, enemies, WeatherState.CLEAR)

    from src.game.models import BattleResult
    assert BattleResult.from_dict(result.to_dict()).to_dict() == result.to_dict()

    # Pre-T.37 saves have no initial_pieces/board dims → empty/0 defaults.
    legacy = result.to_dict()
    del legacy["initial_pieces"]
    del legacy["board_width"]
    del legacy["board_height"]
    loaded = BattleResult.from_dict(legacy)
    assert loaded.initial_pieces == [] and loaded.board_width == 0


# --- T.12c: targeting footprints (observer-only telemetry, V.61) -------------


def test_footprint_recorded_for_radius_and_line_during_cast():
    """V.61 §6 guard: a radius helper records a `circle` (center+radius) and a
    line helper a `line` (dir+length) when a cast is in flight, and the recorded
    geometry **contains every hit target** (footprint cells ⊇ hits)."""
    from src.game.combat.context import hex_distance
    from src.game.targeting import enemies_in_radius, line_targets

    ctx, rec, src, tgt = _recorder_harness()  # src @(0,0), enemy tgt @(1,0)
    ctx._current_cast_id = 7  # enter a cast scope (set by cast_ability in real fights)

    hits = enemies_in_radius(0, 0, 2, src, ctx)
    assert tgt in hits  # tgt @(1,0) is within radius 2 of (0,0)
    circ = next(f for f in rec._footprints if f.kind == "circle")
    assert (circ.center_q, circ.center_r, circ.radius, circ.cast_id) == (0, 0, 2, 7)
    # footprint ⊇ hits: every hit lies within the recorded circle
    for h in hits:
        assert hex_distance(circ.center_q, circ.center_r, h.position_q, h.position_r) <= circ.radius

    line_hits = line_targets(src, (1, 0), 3, ctx)
    assert tgt in line_hits  # tgt @(1,0) is on the line q=1..3, r=0
    line = next(f for f in rec._footprints if f.kind == "line")
    assert (line.center_q, line.center_r, line.direction, line.length) == (0, 0, (1, 0), 3)


def test_footprint_not_recorded_outside_a_cast():
    """V.61: idle / AI / passive target queries (no cast in flight) record no
    footprint — capture is scoped to `current_cast_id`."""
    from src.game.targeting import enemies_in_radius

    ctx, rec, src, _tgt = _recorder_harness()
    assert ctx.current_cast_id is None
    enemies_in_radius(0, 0, 3, src, ctx)
    assert rec._footprints == []


def test_footprint_capture_is_observer_only_byte_identical():
    """V.61/V.2: footprint capture is observer-only — a real radius-casting fight
    records footprints, yet `resolve_combat` stays byte-identical run-to-run, and
    the no-subscriber `CombatReplay` path reaches the same survivors (capture never
    changes targeting results or damage)."""
    from src.game.combat import CombatReplay, resolve_combat
    from src.game.content import CHAMPION_ROSTER, ENEMY_ROSTER

    team = [CHAMPION_ROSTER["champ_aurion"]]  # active = radius-2 AoE
    enemies = list(ENEMY_ROSTER.values())[:6]
    r1 = resolve_combat(team, enemies, WeatherState.CLEAR)
    r2 = resolve_combat(team, enemies, WeatherState.CLEAR)

    assert r1.footprints, "expected recorded footprints from a radius caster"
    assert all(f.kind == "circle" for f in r1.footprints)
    # determinism: capture is byte-identical
    assert r1.to_dict() == r2.to_dict()

    # the inspect/replay path has no recorder subscribed → on_footprint no-ops →
    # combat unaffected: same survivors as the recorded resolve.
    replay = CombatReplay(team, enemies, WeatherState.CLEAR)
    replay.step_to(10_000_000)
    alive = {v.id for v in replay.pieces() if v.alive and not v.is_enemy}
    assert alive == set(r1.surviving_team_ids)


def test_footprints_round_trip_and_legacy_default():
    """`BattleResult.footprints` (+ the `cast_id` beat field) survive serialization;
    pre-T.12c payloads default to an empty footprint list."""
    from src.game.models import BattleResult, Footprint
    from src.game.content import CHAMPION_ROSTER, ENEMY_ROSTER

    team = [CHAMPION_ROSTER["champ_aurion"]]
    enemies = list(ENEMY_ROSTER.values())[:6]
    result = resolve_combat(team, enemies, WeatherState.CLEAR)
    assert result.footprints
    assert BattleResult.from_dict(result.to_dict()).to_dict() == result.to_dict()
    back = BattleResult.from_dict(result.to_dict())
    assert all(isinstance(f, Footprint) for f in back.footprints)

    legacy = result.to_dict()
    del legacy["footprints"]
    assert BattleResult.from_dict(legacy).footprints == []


# --- T.23-prep / dev-harness: starting-position override ---------------------


def test_positions_override_places_pieces_and_none_is_byte_identical():
    """An explicit `positions` override (both sides) places pieces at the given
    cells (over `assign_spawns`); `positions=None` leaves the deterministic
    default formation byte-identical."""
    team = [_champ(id="hero", strength=40)]
    enemies = [_enemy(id="mob", max_hp=60)]
    placed = resolve_combat(team, enemies, WeatherState.CLEAR, positions={"hero": (3, 5), "mob": (6, 1)})
    snap = {s.id: (s.q, s.r) for s in placed.initial_pieces}
    assert snap["hero"] == (3, 5) and snap["mob"] == (6, 1)

    a = resolve_combat(team, enemies, WeatherState.CLEAR)
    b = resolve_combat(team, enemies, WeatherState.CLEAR, positions=None)
    assert a.to_dict() == b.to_dict()  # default path unchanged


def test_positions_override_rejects_offboard_and_duplicate_cell():
    """Engine-level guard: an off-board cell or two pieces on the same cell raise
    before the sim runs (T.23 layers the prep zone/roster validation on top)."""
    team = [_champ(id="hero")]
    enemies = [_enemy(id="mob")]
    with pytest.raises(ValueError):
        resolve_combat(team, enemies, WeatherState.CLEAR, positions={"hero": (BOARD_WIDTH, 0)})
    with pytest.raises(ValueError):
        resolve_combat(team, enemies, WeatherState.CLEAR,
                       positions={"hero": (2, 2), "mob": (2, 2)})


def test_positions_override_rejects_unknown_piece_id():
    """Engine-level guard: a `positions` key naming no piece in this combat (e.g. a
    typo'd id) raises rather than silently dropping the placement."""
    team = [_champ(id="hero")]
    enemies = [_enemy(id="mob")]
    with pytest.raises(ValueError):
        resolve_combat(team, enemies, WeatherState.CLEAR, positions={"typo_id": (3, 3)})
