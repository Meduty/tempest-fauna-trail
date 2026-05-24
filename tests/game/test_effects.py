"""Tests for the effect substrate (T20) — effects.py."""

from __future__ import annotations

import pytest

from src.game.effects import (
    EffectBundle,
    EventBus,
    Hook,
    HookScope,
    Lifetime,
    Modifier,
    SourceTag,
    compute_stat,
)


# ---------------------------------------------------------------------------
# Modifier computation tests
# ---------------------------------------------------------------------------


class TestComputeStat:
    """Test (base + adds) × muls; set override; lifetime not relevant to compute."""

    def _make_piece(self, base_stats, modifiers=None):
        """Helper: minimal piece-like object."""
        class FakePiece:
            pass
        p = FakePiece()
        p.base_stats = base_stats
        p.modifiers = modifiers or []
        return p

    def test_base_only(self):
        p = self._make_piece({"strength": 50.0})
        assert compute_stat(p, "strength") == 50.0

    def test_missing_stat_defaults_to_zero(self):
        p = self._make_piece({})
        assert compute_stat(p, "strength") == 0.0

    def test_additive_modifiers(self):
        p = self._make_piece({"strength": 50.0}, [
            Modifier("strength", "add", 10.0),
            Modifier("strength", "add", 5.0),
        ])
        assert compute_stat(p, "strength") == 65.0

    def test_multiplicative_modifiers(self):
        p = self._make_piece({"strength": 100.0}, [
            Modifier("strength", "mul", 1.5),
        ])
        assert compute_stat(p, "strength") == 150.0

    def test_add_then_mul(self):
        """(base + adds) × muls."""
        p = self._make_piece({"strength": 100.0}, [
            Modifier("strength", "add", 50.0),
            Modifier("strength", "mul", 2.0),
        ])
        assert compute_stat(p, "strength") == 300.0  # (100+50)*2

    def test_multiple_muls_chain(self):
        p = self._make_piece({"hp": 1000.0}, [
            Modifier("hp", "mul", 1.5),
            Modifier("hp", "mul", 2.0),
        ])
        assert compute_stat(p, "hp") == 3000.0  # 1000 * 1.5 * 2.0

    def test_set_overrides_all(self):
        p = self._make_piece({"strength": 100.0}, [
            Modifier("strength", "add", 50.0),
            Modifier("strength", "mul", 2.0),
            Modifier("strength", "set", 999.0),
        ])
        assert compute_stat(p, "strength") == 999.0

    def test_last_set_wins(self):
        p = self._make_piece({"strength": 100.0}, [
            Modifier("strength", "set", 500.0),
            Modifier("strength", "set", 999.0),
        ])
        assert compute_stat(p, "strength") == 999.0

    def test_different_stats_independent(self):
        p = self._make_piece({"strength": 50.0, "intelligence": 80.0}, [
            Modifier("strength", "add", 10.0),
            Modifier("intelligence", "add", 20.0),
        ])
        assert compute_stat(p, "strength") == 60.0
        assert compute_stat(p, "intelligence") == 100.0


# ---------------------------------------------------------------------------
# EventBus tests
# ---------------------------------------------------------------------------


class TestEventBus:
    """Test hook dispatch, priority ordering, and scope dedup."""

    def test_basic_fire(self):
        bus = EventBus()
        results = []
        hook = Hook("on_test", lambda ctx, ev: results.append(ev))
        bus.subscribe(hook)
        bus.fire("on_test", "hello", ctx=None)
        assert results == ["hello"]

    def test_priority_ordering(self):
        bus = EventBus()
        order = []
        bus.subscribe(Hook("on_test", lambda ctx, ev: order.append("low"), priority=0))
        bus.subscribe(Hook("on_test", lambda ctx, ev: order.append("high"), priority=10))
        bus.fire("on_test", None, ctx=None)
        assert order == ["high", "low"]

    def test_unsubscribe(self):
        bus = EventBus()
        results = []
        hook = Hook("on_test", lambda ctx, ev: results.append(1))
        hook_id = bus.subscribe(hook)
        bus.fire("on_test", None, ctx=None)
        assert results == [1]
        bus.unsubscribe(hook_id)
        bus.fire("on_test", None, ctx=None)
        assert results == [1]  # No second fire

    def test_scope_per_hit(self):
        """PER_HIT fires every time."""
        bus = EventBus()
        count = [0]
        hook = Hook("on_test", lambda ctx, ev: count.__setitem__(0, count[0] + 1),
                    scope=HookScope.PER_HIT)
        bus.subscribe(hook)
        bus.fire("on_test", None, ctx=None)
        bus.fire("on_test", None, ctx=None)
        bus.fire("on_test", None, ctx=None)
        assert count[0] == 3

    def test_scope_once_per_combat(self):
        """ONCE_PER_COMBAT fires only once until reset."""
        bus = EventBus()
        count = [0]
        hook = Hook("on_test", lambda ctx, ev: count.__setitem__(0, count[0] + 1),
                    scope=HookScope.ONCE_PER_COMBAT)
        bus.subscribe(hook)
        bus.fire("on_test", None, ctx=None)
        bus.fire("on_test", None, ctx=None)
        assert count[0] == 1
        bus.reset_combat()
        bus.fire("on_test", None, ctx=None)
        assert count[0] == 2

    def test_scope_once_per_cast(self):
        """ONCE_PER_CAST fires once per cast_id."""
        bus = EventBus()
        count = [0]
        hook = Hook("on_test", lambda ctx, ev: count.__setitem__(0, count[0] + 1),
                    scope=HookScope.ONCE_PER_CAST)
        bus.subscribe(hook)
        bus.fire("on_test", None, cast_id=1, ctx=None)
        bus.fire("on_test", None, cast_id=1, ctx=None)
        assert count[0] == 1  # Deduped within same cast
        bus.fire("on_test", None, cast_id=2, ctx=None)
        assert count[0] == 2  # New cast fires again

    def test_scope_once_per_target(self):
        """ONCE_PER_TARGET fires once per (cast_id, target)."""
        bus = EventBus()
        count = [0]
        hook = Hook("on_test", lambda ctx, ev: count.__setitem__(0, count[0] + 1),
                    scope=HookScope.ONCE_PER_TARGET)
        bus.subscribe(hook)

        class FakeTarget:
            def __init__(self, id):
                self.id = id

        class FakeEvent:
            def __init__(self, target):
                self.target = target

        t1 = FakeTarget("a")
        t2 = FakeTarget("b")
        bus.fire("on_test", FakeEvent(t1), cast_id=1, ctx=None)
        bus.fire("on_test", FakeEvent(t1), cast_id=1, ctx=None)  # Same target, same cast
        assert count[0] == 1
        bus.fire("on_test", FakeEvent(t2), cast_id=1, ctx=None)  # Different target
        assert count[0] == 2

    def test_fire_reducing(self):
        """fire_reducing passes value through hooks."""
        bus = EventBus()
        # Hook that halves the value
        hook = Hook("on_damage_pre", lambda ctx, ev, val: val * 0.5)
        bus.subscribe(hook)
        result = bus.fire_reducing("on_damage_pre", None, 100.0, ctx=None)
        assert result == 50.0

    def test_fire_reducing_chain(self):
        """Multiple reducing hooks chain."""
        bus = EventBus()
        bus.subscribe(Hook("on_damage_pre", lambda ctx, ev, val: val * 0.5, priority=10))
        bus.subscribe(Hook("on_damage_pre", lambda ctx, ev, val: val - 10, priority=0))
        result = bus.fire_reducing("on_damage_pre", None, 100.0, ctx=None)
        # High priority fires first: 100 * 0.5 = 50, then 50 - 10 = 40
        assert result == 40.0

    def test_no_hooks_for_event(self):
        """Firing an event with no subscribers is a no-op."""
        bus = EventBus()
        bus.fire("nonexistent_event", None, ctx=None)  # Should not raise

    def test_clear_cast(self):
        """clear_cast removes per-cast dedup entries."""
        bus = EventBus()
        count = [0]
        hook = Hook("on_test", lambda ctx, ev: count.__setitem__(0, count[0] + 1),
                    scope=HookScope.ONCE_PER_CAST)
        bus.subscribe(hook)
        bus.fire("on_test", None, cast_id=1, ctx=None)
        assert count[0] == 1
        bus.clear_cast(1)
        bus.fire("on_test", None, cast_id=1, ctx=None)
        assert count[0] == 2


# ---------------------------------------------------------------------------
# EffectBundle tests
# ---------------------------------------------------------------------------


class TestEffectBundle:
    """Test EffectBundle as a data container."""

    def test_empty_bundle(self):
        bundle = EffectBundle()
        assert bundle.modifiers == []
        assert bundle.hooks == []
        assert bundle.statuses == []
        assert bundle.granted_abilities == []
        assert bundle.granted_traits == []

    def test_bundle_with_content(self):
        mod = Modifier("strength", "add", 10.0)
        hook = Hook("on_test", lambda ctx, ev: None)
        bundle = EffectBundle(
            modifiers=[mod],
            hooks=[hook],
            statuses=[("burn", 100)],
            granted_abilities=["smash"],
            granted_traits=["stormcaller"],
        )
        assert len(bundle.modifiers) == 1
        assert len(bundle.hooks) == 1
        assert bundle.statuses == [("burn", 100)]
        assert bundle.granted_abilities == ["smash"]
        assert bundle.granted_traits == ["stormcaller"]


# ---------------------------------------------------------------------------
# Lifetime and SourceTag enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_lifetime_values(self):
        assert Lifetime.PERMANENT == "permanent"
        assert Lifetime.COMBAT == "combat"
        assert Lifetime.TIMED == "timed"

    def test_source_tag_values(self):
        assert SourceTag.BASIC_ATTACK == "basic_attack"
        assert SourceTag.ABILITY == "ability"
        assert SourceTag.DOT == "dot"
        assert SourceTag.TRUE == "true"

    def test_hook_scope_values(self):
        assert HookScope.PER_HIT == "per_hit"
        assert HookScope.ONCE_PER_COMBAT == "once_per_combat"
        assert HookScope.ONCE_PER_CAST == "once_per_cast"
        assert HookScope.ONCE_PER_TARGET == "once_per_target"
