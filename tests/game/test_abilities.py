"""Tests for the ability framework (T20) — abilities, passives, combat context."""

from __future__ import annotations

import pytest

from src.game.abilities import reference  # Trigger registrations
from src.game.combat.context import CombatContext, hex_distance
from src.game.combat.engine import run, process_statuses, process_casts, expire_modifiers
from src.game.effects import (
    EffectBundle,
    EventBus,
    Hook,
    HookScope,
    Lifetime,
    Modifier,
    SourceTag,
)
from src.game.events import DamageEvent, AttackEvent, DeathEvent
from src.game.loadout import (
    apply_bundle,
    compile_loadout,
    piece_from_champion,
    piece_from_enemy,
)
from src.game.models import Champion, Enemy, WeatherState
from src.game.piece import ActiveSlot, Piece
from src.game.registries import ABILITY_REGISTRY, PASSIVE_REGISTRY
from src.game.status import STATUS_DEFS, StatusGate, StatusInstance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_piece(
    id: str = "test_piece",
    hp: float = 1000.0,
    strength: float = 50.0,
    intelligence: float = 50.0,
    is_enemy: bool = False,
    affinity: WeatherState = WeatherState.CLEAR,
    **kwargs,
) -> Piece:
    """Create a test piece with sensible defaults."""
    piece = Piece(
        id=id,
        base_stats={
            "hp": hp,
            "strength": strength,
            "intelligence": intelligence,
            "attack_speed": kwargs.get("attack_speed", 100.0),
            "move_speed": kwargs.get("move_speed", 90.0),
            "mana_regen": kwargs.get("mana_regen", 10.0),
            "threat": kwargs.get("threat", 60.0),
            "armor": kwargs.get("armor", 25.0),
            "resistance": kwargs.get("resistance", 25.0),
            "attack_range": kwargs.get("attack_range", 2.0),
            "crit_chance": kwargs.get("crit_chance", 0.0),
            "penetration": kwargs.get("penetration", 0.0),
            "penetration_pct": kwargs.get("penetration_pct", 0.0),
        },
        affinity=affinity,
        is_enemy=is_enemy,
        hp=hp,
        max_hp=hp,
    )
    return piece


def _make_ctx(
    team: list[Piece] | None = None,
    enemies: list[Piece] | None = None,
    weather: WeatherState = WeatherState.CLEAR,
    seed: int = 42,
) -> CombatContext:
    """Create a CombatContext with given pieces."""
    pieces = []
    if team:
        pieces.extend(team)
    if enemies:
        pieces.extend(enemies)
    bus = EventBus()
    return CombatContext(pieces, bus, weather, seed)


# ---------------------------------------------------------------------------
# Active ability tests
# ---------------------------------------------------------------------------


class TestSmashAbility:
    """Test smash — simple active: single-target STR damage."""

    def test_smash_deals_damage(self):
        attacker = _make_piece("attacker", strength=100.0)
        target = _make_piece("target", hp=2000.0, is_enemy=True)
        ctx = _make_ctx(team=[attacker], enemies=[target])

        handler = ABILITY_REGISTRY["smash"]
        handler(ctx, attacker, [target])

        # smash: 100 base + strength(100) * 1.5 = 250 raw before mitigation
        assert target.hp < 2000.0

    def test_smash_targets_primary(self):
        attacker = _make_piece("attacker", strength=100.0)
        target1 = _make_piece("target1", hp=2000.0, is_enemy=True)
        target2 = _make_piece("target2", hp=500.0, is_enemy=True)
        # Position target2 closer
        target2.position_q = 1
        target1.position_q = 5
        ctx = _make_ctx(team=[attacker], enemies=[target1, target2])

        handler = ABILITY_REGISTRY["smash"]
        handler(ctx, attacker, [target1, target2])

        # Primary target (closest) should take damage
        assert target2.hp < 500.0


class TestThunderCrashAbility:
    """Test thunder_crash — factory cone AOE."""

    def test_thunder_crash_deals_damage(self):
        attacker = _make_piece("attacker", intelligence=100.0)
        target = _make_piece("target", hp=5000.0, is_enemy=True)
        target.position_q = 1
        ctx = _make_ctx(team=[attacker], enemies=[target])

        handler = ABILITY_REGISTRY["thunder_crash"]
        handler(ctx, attacker, [target])

        assert target.hp < 5000.0

    def test_thunder_crash_weather_boost(self):
        attacker = _make_piece("attacker", intelligence=100.0)
        target_clear = _make_piece("t1", hp=5000.0, is_enemy=True)
        target_thunder = _make_piece("t2", hp=5000.0, is_enemy=True)
        target_clear.position_q = 1
        target_thunder.position_q = 1

        # Clear weather
        ctx_clear = _make_ctx(team=[attacker], enemies=[target_clear], weather=WeatherState.CLEAR)
        ABILITY_REGISTRY["thunder_crash"](ctx_clear, attacker, [target_clear])
        clear_damage = 5000.0 - target_clear.hp

        # Thunder weather (reset attacker)
        attacker2 = _make_piece("attacker2", intelligence=100.0)
        ctx_thunder = _make_ctx(team=[attacker2], enemies=[target_thunder], weather=WeatherState.THUNDER)
        ABILITY_REGISTRY["thunder_crash"](ctx_thunder, attacker2, [target_thunder])
        thunder_damage = 5000.0 - target_thunder.hp

        # Thunder should deal more damage (1.5x bonus)
        assert thunder_damage > clear_damage


class TestHealPulse:
    """Test heal_pulse — heal lowest ally."""

    def test_heals_lowest_ally(self):
        healer = _make_piece("healer", intelligence=100.0)
        wounded = _make_piece("wounded", hp=200.0)
        wounded.max_hp = 1000.0
        healthy = _make_piece("healthy", hp=900.0)
        healthy.max_hp = 1000.0

        ctx = _make_ctx(team=[healer, wounded, healthy], enemies=[_make_piece("e", is_enemy=True)])

        handler = ABILITY_REGISTRY["heal_pulse"]
        handler(ctx, healer, [])

        assert wounded.hp > 200.0
        assert healthy.hp == 900.0  # Not healed


# ---------------------------------------------------------------------------
# Passive ability tests
# ---------------------------------------------------------------------------


class TestStaticBuildup:
    """Test static_buildup passive — on_attack_landed in Thunder applies 'charged'."""

    def test_applies_charged_in_thunder(self):
        attacker = _make_piece("attacker", affinity=WeatherState.THUNDER)
        target = _make_piece("target", hp=2000.0, is_enemy=True)
        ctx = _make_ctx(team=[attacker], enemies=[target], weather=WeatherState.THUNDER)

        # Register the passive
        bundle = PASSIVE_REGISTRY["static_buildup"](attacker)
        apply_bundle(attacker, bundle, ctx.bus)

        # Simulate attack landed
        event = AttackEvent(attacker=attacker, target=target, amount=50.0)
        ctx.bus.fire("on_attack_landed", event, ctx=ctx)

        assert target.has_status("charged")

    def test_no_charged_in_clear(self):
        attacker = _make_piece("attacker", affinity=WeatherState.THUNDER)
        target = _make_piece("target", hp=2000.0, is_enemy=True)
        ctx = _make_ctx(team=[attacker], enemies=[target], weather=WeatherState.CLEAR)

        bundle = PASSIVE_REGISTRY["static_buildup"](attacker)
        apply_bundle(attacker, bundle, ctx.bus)

        event = AttackEvent(attacker=attacker, target=target, amount=50.0)
        ctx.bus.fire("on_attack_landed", event, ctx=ctx)

        assert not target.has_status("charged")


class TestPhaseHook:
    """Test phase_hook_test — grants ability at 50% HP."""

    def test_grants_ability_below_50_pct(self):
        boss = _make_piece("boss", hp=1000.0)
        boss.max_hp = 1000.0
        boss.actives = [ActiveSlot("smash", mana_cost=36_000)]

        ctx = _make_ctx(team=[boss], enemies=[_make_piece("e", is_enemy=True)])

        bundle = PASSIVE_REGISTRY["phase_hook_test"](boss)
        apply_bundle(boss, bundle, ctx.bus)

        # Reduce HP below 50%
        boss.hp = 400.0

        # Fire damage taken event
        event = DamageEvent(
            attacker=_make_piece("e", is_enemy=True), target=boss,
            amount=100.0, tag="ability",
        )
        ctx.bus.fire("on_damage_taken", event, ctx=ctx)

        # Should now have 2 actives
        assert len(boss.actives) == 2

    def test_once_per_combat(self):
        """Phase hook fires only once."""
        boss = _make_piece("boss", hp=1000.0)
        boss.max_hp = 1000.0
        boss.actives = [ActiveSlot("smash", mana_cost=36_000)]

        ctx = _make_ctx(team=[boss], enemies=[_make_piece("e", is_enemy=True)])

        bundle = PASSIVE_REGISTRY["phase_hook_test"](boss)
        apply_bundle(boss, bundle, ctx.bus)

        boss.hp = 400.0
        event = DamageEvent(
            attacker=_make_piece("e", is_enemy=True), target=boss,
            amount=100.0, tag="ability",
        )
        ctx.bus.fire("on_damage_taken", event, ctx=ctx)
        ctx.bus.fire("on_damage_taken", event, ctx=ctx)

        # Still only 2 actives (didn't fire twice)
        assert len(boss.actives) == 2


class TestSunlitVigor:
    """Test sunlit_vigor — CLEAR affinity buff in CLEAR weather."""

    def test_buffs_in_clear_weather(self):
        piece = _make_piece("sunny", affinity=WeatherState.CLEAR)
        ctx = _make_ctx(team=[piece], enemies=[_make_piece("e", is_enemy=True)],
                       weather=WeatherState.CLEAR)

        bundle = PASSIVE_REGISTRY["sunlit_vigor"](piece)
        apply_bundle(piece, bundle, ctx.bus)

        from src.game.events import CombatStartEvent
        ctx.bus.fire("on_combat_start", CombatStartEvent(), ctx=ctx)

        # Should have +15 STR and +15 INT modifiers
        assert piece.stat("strength") == 50.0 + 15.0
        assert piece.stat("intelligence") == 50.0 + 15.0

    def test_no_buff_in_rain(self):
        piece = _make_piece("sunny", affinity=WeatherState.CLEAR)
        ctx = _make_ctx(team=[piece], enemies=[_make_piece("e", is_enemy=True)],
                       weather=WeatherState.RAIN)

        bundle = PASSIVE_REGISTRY["sunlit_vigor"](piece)
        apply_bundle(piece, bundle, ctx.bus)

        from src.game.events import CombatStartEvent
        ctx.bus.fire("on_combat_start", CombatStartEvent(), ctx=ctx)

        assert piece.stat("strength") == 50.0
        assert piece.stat("intelligence") == 50.0


# ---------------------------------------------------------------------------
# Status effect tests
# ---------------------------------------------------------------------------


class TestStatusGates:
    """Test status gates block correct actions."""

    def test_stun_blocks_action(self):
        piece = _make_piece("test")
        piece.statuses.append(StatusInstance("stun", remaining_ticks=100))
        assert piece.is_gated(StatusGate.BLOCKS_ACTION)

    def test_silence_blocks_cast(self):
        piece = _make_piece("test")
        piece.statuses.append(StatusInstance("silence", remaining_ticks=100))
        assert piece.is_gated(StatusGate.BLOCKS_CAST)
        assert not piece.is_gated(StatusGate.BLOCKS_ACTION)

    def test_disarm_blocks_attack(self):
        piece = _make_piece("test")
        piece.statuses.append(StatusInstance("disarm", remaining_ticks=100))
        assert piece.is_gated(StatusGate.BLOCKS_ATTACK)
        assert not piece.is_gated(StatusGate.BLOCKS_CAST)

    def test_root_blocks_movement(self):
        piece = _make_piece("test")
        piece.statuses.append(StatusInstance("root", remaining_ticks=100))
        assert piece.is_gated(StatusGate.BLOCKS_MOVEMENT)
        assert not piece.is_gated(StatusGate.BLOCKS_ACTION)

    def test_frozen_blocks_action_and_movement(self):
        piece = _make_piece("test")
        piece.statuses.append(StatusInstance("frozen", remaining_ticks=100))
        assert piece.is_gated(StatusGate.BLOCKS_ACTION)
        assert piece.is_gated(StatusGate.BLOCKS_MOVEMENT)


class TestStatusLifecycle:
    """Test status apply, expire, stacking."""

    def test_apply_status(self):
        piece = _make_piece("test", is_enemy=True)
        ctx = _make_ctx(enemies=[piece])
        ctx.apply_status(piece, "burn", duration_ticks=100)
        assert piece.has_status("burn")
        assert piece.get_status("burn").remaining_ticks == 100

    def test_status_refresh(self):
        """Stun uses refresh: reapply resets duration."""
        piece = _make_piece("test", is_enemy=True)
        ctx = _make_ctx(enemies=[piece])
        ctx.apply_status(piece, "stun", duration_ticks=50)
        ctx.apply_status(piece, "stun", duration_ticks=100)
        assert piece.get_status("stun").remaining_ticks == 100

    def test_status_stacking(self):
        """Poison uses stack: adds stacks."""
        piece = _make_piece("test", is_enemy=True)
        ctx = _make_ctx(enemies=[piece])
        ctx.apply_status(piece, "poison", duration_ticks=100, stacks=1)
        ctx.apply_status(piece, "poison", duration_ticks=100, stacks=1)
        assert piece.status_stacks("poison") == 2

    def test_status_expiry(self):
        """Statuses expire when remaining_ticks reaches 0."""
        piece = _make_piece("test", is_enemy=True)
        piece.statuses.append(StatusInstance("burn", remaining_ticks=1))
        ctx = _make_ctx(enemies=[piece])
        process_statuses(ctx, [piece])
        assert not piece.has_status("burn")

    def test_remove_status(self):
        piece = _make_piece("test", is_enemy=True)
        ctx = _make_ctx(enemies=[piece])
        ctx.apply_status(piece, "stun", duration_ticks=100)
        assert piece.has_status("stun")
        ctx.remove_status(piece, "stun")
        assert not piece.has_status("stun")


# ---------------------------------------------------------------------------
# Damage pipeline tests
# ---------------------------------------------------------------------------


class TestDamagePipeline:
    """Test the full damage pipeline through CombatContext."""

    def test_basic_damage(self):
        attacker = _make_piece("attacker", strength=100.0)
        target = _make_piece("target", hp=2000.0, is_enemy=True)
        ctx = _make_ctx(team=[attacker], enemies=[target])

        final = ctx.deal_damage(attacker, target, 100.0, SourceTag.ABILITY)
        assert final > 0
        assert target.hp < 2000.0

    def test_mitigation_reduces_damage(self):
        attacker = _make_piece("attacker")
        low_res = _make_piece("low", hp=2000.0, is_enemy=True, resistance=0.0)
        high_res = _make_piece("high", hp=2000.0, is_enemy=True, resistance=100.0)

        ctx1 = _make_ctx(team=[attacker], enemies=[low_res])
        ctx2 = _make_ctx(team=[attacker], enemies=[high_res])

        d1 = ctx1.deal_damage(attacker, low_res, 100.0, SourceTag.ABILITY)
        d2 = ctx2.deal_damage(attacker, high_res, 100.0, SourceTag.ABILITY)

        assert d1 > d2  # Higher resistance = less magical damage

    def test_true_damage_ignores_mitigation(self):
        attacker = _make_piece("attacker")
        target = _make_piece("target", hp=2000.0, is_enemy=True, armor=200.0, resistance=200.0)
        ctx = _make_ctx(team=[attacker], enemies=[target])

        final = ctx.deal_damage(attacker, target, 100.0, SourceTag.TRUE)
        assert final == 100.0

    def test_kill_on_lethal_damage(self):
        attacker = _make_piece("attacker")
        target = _make_piece("target", hp=10.0, is_enemy=True, armor=0.0, resistance=0.0)
        ctx = _make_ctx(team=[attacker], enemies=[target])

        ctx.deal_damage(attacker, target, 9999.0, SourceTag.ABILITY)
        assert not target.alive

    def test_pre_damage_hook_modifies_damage(self):
        attacker = _make_piece("attacker")
        target = _make_piece("target", hp=2000.0, is_enemy=True, resistance=0.0)
        bus = EventBus()
        # Hook that doubles damage
        bus.subscribe(Hook("on_damage_pre", lambda ctx, ev, val: val * 2.0))
        ctx = CombatContext([attacker, target], bus, WeatherState.CLEAR)

        final = ctx.deal_damage(attacker, target, 100.0, SourceTag.ABILITY)
        # 100 * affinity(1.0) * 2.0 hook = 200 (no mitigation since res=0)
        assert final == 200.0

    def test_crit_multiplier(self):
        attacker = _make_piece("attacker", crit_chance=1.0)  # Always crits
        target = _make_piece("target", hp=5000.0, is_enemy=True, resistance=0.0)
        ctx = _make_ctx(team=[attacker], enemies=[target])

        final = ctx.deal_damage(attacker, target, 100.0, SourceTag.BASIC_ATTACK)
        # 100 * 1.0 affinity * 1.5 crit = 150
        assert final == 150.0


# ---------------------------------------------------------------------------
# Combat loop integration tests
# ---------------------------------------------------------------------------


class TestCombatLoop:
    """Integration tests for the full combat loop."""

    def test_simple_combat_resolves(self):
        """Two pieces fight; one should win."""
        team_piece = _make_piece("hero", hp=500.0, strength=80.0)
        team_piece.actives = [ActiveSlot("smash", mana_cost=100, current_mana=0.0)]
        enemy_piece = _make_piece("baddie", hp=300.0, strength=30.0, is_enemy=True)
        enemy_piece.actives = [ActiveSlot("smash", mana_cost=100, current_mana=0.0)]

        bus = EventBus()
        ctx = CombatContext([team_piece, enemy_piece], bus, WeatherState.CLEAR, seed=42)
        winner = run(ctx)

        # One side should win (not a draw given stat disparity)
        assert winner in ("team", "enemy")

    def test_status_gates_prevent_casting(self):
        """Silenced piece should not cast."""
        piece = _make_piece("caster")
        piece.actives = [ActiveSlot("smash", mana_cost=10, current_mana=10.0)]
        piece.statuses.append(StatusInstance("silence", remaining_ticks=100))

        ctx = _make_ctx(team=[piece], enemies=[_make_piece("e", is_enemy=True)])
        process_casts(ctx, piece)

        # Mana should not have been spent (cast blocked)
        assert piece.actives[0].current_mana == 10.0


# ---------------------------------------------------------------------------
# Loadout compiler tests
# ---------------------------------------------------------------------------


class TestLoadout:
    """Test piece_from_champion and compile_loadout."""

    def test_piece_from_champion(self):
        champ = Champion(
            id="test_champ", name="Tester", affinity=WeatherState.CLEAR,
            role="tank", tier=1, level=1, max_hp=1000, strength=50,
            intelligence=30, attack_speed=100, move_speed=90, mana_regen=10,
            threat=60, armor=25, resistance=25, attack_range=1,
            active_abilities=["smash"], passive_ability="",
        )
        piece = piece_from_champion(champ)
        assert piece.id == "test_champ"
        assert piece.hp == 1000.0
        assert piece.stat("strength") == 50.0
        assert len(piece.actives) == 1
        assert piece.actives[0].ability_id == "smash"
        assert piece.actives[0].current_mana == 0.0  # 0 starting mana

    def test_compile_loadout(self):
        champ = Champion(
            id="test_champ", name="Tester", affinity=WeatherState.CLEAR,
            role="tank", tier=1, level=1, max_hp=1000, strength=50,
            intelligence=30, attack_speed=100, move_speed=90, mana_regen=10,
            threat=60, armor=25, resistance=25, attack_range=1,
            active_abilities=["smash"], passive_ability="",
        )
        enemy = Enemy(
            id="test_enemy", name="Baddie", affinity=WeatherState.RAIN,
            role="fighter", tier=1, level=1, max_hp=800, strength=40,
            intelligence=20, attack_speed=90, move_speed=80, mana_regen=8,
            threat=50, armor=20, resistance=20, attack_range=1,
            active_abilities=["smash"], passive_ability="",
        )
        pieces, bus, _ = compile_loadout([champ], [enemy], WeatherState.CLEAR)
        assert len(pieces) == 2
        assert pieces[0].is_enemy is False
        assert pieces[1].is_enemy is True


# ---------------------------------------------------------------------------
# Determinism test
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Same inputs → same outputs."""

    def test_deterministic_combat(self):
        def run_combat():
            team_piece = _make_piece("hero", hp=500.0, strength=80.0)
            team_piece.actives = [ActiveSlot("smash", mana_cost=50, current_mana=0.0)]
            enemy_piece = _make_piece("baddie", hp=300.0, strength=30.0, is_enemy=True)
            enemy_piece.actives = [ActiveSlot("smash", mana_cost=50, current_mana=0.0)]
            bus = EventBus()
            ctx = CombatContext([team_piece, enemy_piece], bus, WeatherState.CLEAR, seed=42)
            winner = run(ctx)
            return winner, team_piece.hp, enemy_piece.hp

        r1 = run_combat()
        r2 = run_combat()
        assert r1 == r2


# ---------------------------------------------------------------------------
# Backward compatibility test
# ---------------------------------------------------------------------------


class TestResolveCombatEntryPoint:
    """The public resolve_combat entry point wires the full pipeline."""

    def test_resolve_combat_entry_point(self):
        from src.game.combat import resolve_combat
        from src.game.models import CombatOutcome

        champ = Champion(
            id="test_champ", name="Tester", affinity=WeatherState.CLEAR,
            role="tank", tier=1, level=1, max_hp=1000, strength=80,
            intelligence=30, attack_speed=100, move_speed=90, mana_regen=10,
            threat=60, armor=25, resistance=25, attack_range=1,
            active_abilities=["smash"], passive_ability="",
        )
        enemy = Enemy(
            id="test_enemy", name="Baddie", affinity=WeatherState.CLEAR,
            role="fighter", tier=1, level=1, max_hp=500, strength=30,
            intelligence=20, attack_speed=80, move_speed=80, mana_regen=8,
            threat=50, armor=20, resistance=20, attack_range=1,
            active_abilities=[], passive_ability="",
        )
        result = resolve_combat([champ], [enemy], WeatherState.CLEAR)
        assert result.outcome == CombatOutcome.WIN


class TestBarrier:
    """Barrier — temp absorb pool consumed before HP (distinct from armor 'shields')."""

    def test_barrier_absorbs_before_hp(self):
        attacker = _make_piece("attacker")
        target = _make_piece("target", hp=2000.0, is_enemy=True, resistance=0.0)
        ctx = _make_ctx(team=[attacker], enemies=[target])
        ctx.grant_barrier(target, 100.0)

        final = ctx.deal_damage(attacker, target, 60.0, SourceTag.TRUE)
        # Damage event still reports full 60; HP untouched, barrier soaks it
        assert final == 60.0
        assert target.hp == 2000.0
        assert target.barrier_total == 40.0

    def test_barrier_spills_remainder_to_hp(self):
        attacker = _make_piece("attacker")
        target = _make_piece("target", hp=2000.0, is_enemy=True, resistance=0.0)
        ctx = _make_ctx(team=[attacker], enemies=[target])
        ctx.grant_barrier(target, 100.0)

        ctx.deal_damage(attacker, target, 150.0, SourceTag.TRUE)
        # 100 soaked, 50 spills to HP, barrier depleted+dropped
        assert target.hp == 1950.0
        assert target.barrier_total == 0.0
        assert target.barriers == []

    def test_barrier_segments_consumed_fifo(self):
        attacker = _make_piece("attacker")
        target = _make_piece("target", hp=2000.0, is_enemy=True, resistance=0.0)
        ctx = _make_ctx(team=[attacker], enemies=[target])
        ctx.grant_barrier(target, 30.0)
        ctx.grant_barrier(target, 50.0)

        ctx.deal_damage(attacker, target, 40.0, SourceTag.TRUE)
        # First segment (30) fully gone, second drained by 10 → 40 left
        assert target.hp == 2000.0
        assert [b.amount for b in target.barriers] == [40.0]

    def test_barrier_expires_on_tick(self):
        target = _make_piece("target", hp=2000.0, is_enemy=True)
        ctx = _make_ctx(team=[], enemies=[target])
        ctx.current_tick = 0
        ctx.grant_barrier(target, 100.0, duration_ticks=100)
        assert target.barrier_total == 100.0

        ctx.current_tick = 100
        expire_modifiers(ctx, [target])
        assert target.barrier_total == 0.0

    def test_zero_barrier_not_added(self):
        target = _make_piece("target", is_enemy=True)
        ctx = _make_ctx(team=[], enemies=[target])
        ctx.grant_barrier(target, 0.0)
        assert target.barriers == []


class TestHierarchBarrier:
    """Hierarch on-death passive — grants allies an INT-scaled barrier (T8)."""

    def test_on_death_grants_allies_barrier(self):
        import src.game.abilities.enemies  # noqa: F401 — ensure registration

        hierarch = _make_piece("hierarch", is_enemy=True, intelligence=100.0)
        ally = _make_piece("ally", hp=2000.0, is_enemy=True)
        ctx = _make_ctx(team=[], enemies=[hierarch, ally])

        bundle = PASSIVE_REGISTRY["enemy_hierarch.passive"](hierarch)
        apply_bundle(hierarch, bundle, ctx.bus)

        ctx.bus.fire("on_death", DeathEvent(victim=hierarch, killer=ally), ctx=ctx)

        # 50 + INT(100)*2.0 = 250 barrier on the surviving ally
        assert ally.barrier_total == 367.0
        # Duration = 600 * level(1); not expired yet at tick 0
        ctx.current_tick = 599
        expire_modifiers(ctx, [ally])
        assert ally.barrier_total == 367.0
        ctx.current_tick = 600
        expire_modifiers(ctx, [ally])
        assert ally.barrier_total == 0.0

    def test_other_deaths_do_not_trigger(self):
        import src.game.abilities.enemies  # noqa: F401

        hierarch = _make_piece("hierarch", is_enemy=True, intelligence=100.0)
        ally = _make_piece("ally", hp=2000.0, is_enemy=True)
        ctx = _make_ctx(team=[], enemies=[hierarch, ally])

        bundle = PASSIVE_REGISTRY["enemy_hierarch.passive"](hierarch)
        apply_bundle(hierarch, bundle, ctx.bus)

        # A different piece dies — passive must not fire
        ctx.bus.fire("on_death", DeathEvent(victim=ally, killer=hierarch), ctx=ctx)
        assert ally.barrier_total == 0.0


class TestGladeHeronRework:
    """Glade Heron: INT->attack-speed haste active + poison-burst passive."""

    def _heron(self, intelligence=200.0):
        import src.game.abilities.champions  # noqa: F401 — ensure registration
        return _make_piece("heron", intelligence=intelligence, attack_speed=100.0)

    def test_active_grants_as_scaled_by_int(self):
        heron = self._heron(intelligence=200.0)
        target = _make_piece("t", is_enemy=True)
        ctx = _make_ctx(team=[heron], enemies=[target])

        ABILITY_REGISTRY["champ_glade_heron.active"](ctx, heron, [])
        # base 100 + INT(200)*1.15 = 330
        assert heron.stat("attack_speed") == 352.0

    def test_active_refreshes_not_stacks(self):
        heron = self._heron(intelligence=200.0)
        target = _make_piece("t", is_enemy=True)
        ctx = _make_ctx(team=[heron], enemies=[target])

        handler = ABILITY_REGISTRY["champ_glade_heron.active"]
        handler(ctx, heron, [])
        handler(ctx, heron, [])
        handler(ctx, heron, [])
        # Still a single haste modifier; AS not multiplied by recasts
        haste = [m for m in heron.modifiers if m.source_id == "ability:champ_glade_heron.haste"]
        assert len(haste) == 1
        assert heron.stat("attack_speed") == 352.0

    def test_passive_applies_poison_per_auto(self):
        heron = self._heron()
        target = _make_piece("t", hp=5000.0, is_enemy=True, resistance=0.0)
        ctx = _make_ctx(team=[heron], enemies=[target])
        bundle = PASSIVE_REGISTRY["champ_glade_heron.passive"](heron)
        apply_bundle(heron, bundle, ctx.bus)

        ctx.bus.fire("on_attack_landed", AttackEvent(attacker=heron, target=target, amount=10.0), ctx=ctx)
        assert target.status_stacks("poison") == 1

    def test_passive_no_burst_below_three_stacks(self):
        heron = self._heron(intelligence=200.0)
        target = _make_piece("t", hp=5000.0, is_enemy=True, resistance=0.0)
        ctx = _make_ctx(team=[heron], enemies=[target])
        bundle = PASSIVE_REGISTRY["champ_glade_heron.passive"](heron)
        apply_bundle(heron, bundle, ctx.bus)

        # First auto -> 1 stack, no burst -> hp unchanged
        ctx.bus.fire("on_attack_landed", AttackEvent(attacker=heron, target=target, amount=10.0), ctx=ctx)
        assert target.hp == 5000.0

    def test_passive_burst_at_three_plus_stacks(self):
        heron = self._heron(intelligence=200.0)
        target = _make_piece("t", hp=5000.0, is_enemy=True, resistance=0.0)
        ctx = _make_ctx(team=[heron], enemies=[target])
        bundle = PASSIVE_REGISTRY["champ_glade_heron.passive"](heron)
        apply_bundle(heron, bundle, ctx.bus)

        # Pre-poison to 2 stacks; next auto adds the 3rd -> burst fires
        ctx.apply_status(target, "poison", duration_ticks=400, stacks=2, source_id=heron.id)
        ctx.bus.fire("on_attack_landed", AttackEvent(attacker=heron, target=target, amount=10.0), ctx=ctx)
        # burst = INT(200)*0.29 = 58, res=0 -> full
        assert target.status_stacks("poison") == 3
        assert target.hp == 5000.0 - 64.0


class TestGladeHeronFlatStacks:
    """Venom Tip applies exactly 1 poison stack per auto, regardless of level."""

    def test_poison_one_stack_per_auto_any_level(self):
        import src.game.abilities.champions  # noqa: F401
        for lvl in (1, 2, 3):
            heron = _make_piece(f"heron_l{lvl}", intelligence=200.0, attack_speed=100.0)
            heron.level = lvl
            target = _make_piece("t", hp=5000.0, is_enemy=True, resistance=0.0)
            ctx = _make_ctx(team=[heron], enemies=[target])
            bundle = PASSIVE_REGISTRY["champ_glade_heron.passive"](heron)
            apply_bundle(heron, bundle, ctx.bus)

            ctx.bus.fire("on_attack_landed", AttackEvent(attacker=heron, target=target, amount=10.0), ctx=ctx)
            assert target.status_stacks("poison") == 1


class TestPoisonPercentageDecay:
    """Poison sheds max(1, trunc(stacks*0.2)) per DOT tick — plateau, no cap."""

    def test_percentage_decay_truncates(self):
        src = _make_piece("s")
        target = _make_piece("t", hp=100000.0, is_enemy=True, resistance=0.0)
        ctx = _make_ctx(team=[src], enemies=[target])
        ctx.apply_status(target, "poison", duration_ticks=10000, stacks=20, source_id=src.id)
        inst = target.get_status("poison")
        inst.ticks_to_next_dot = 1  # fire one DOT tick on next process
        process_statuses(ctx, [target])
        # trunc(20 * 0.2) = 4 -> 16
        assert target.status_stacks("poison") == 16

    def test_decay_floor_is_one(self):
        src = _make_piece("s")
        target = _make_piece("t", hp=100000.0, is_enemy=True, resistance=0.0)
        ctx = _make_ctx(team=[src], enemies=[target])
        ctx.apply_status(target, "poison", duration_ticks=10000, stacks=3, source_id=src.id)
        inst = target.get_status("poison")
        inst.ticks_to_next_dot = 1
        process_statuses(ctx, [target])
        # trunc(3 * 0.2) = trunc(0.6) = 0 -> floored to 1 -> 2
        assert target.status_stacks("poison") == 2
