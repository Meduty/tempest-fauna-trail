"""Mana primitive — per-slot pools, weighted-rank charge cycle, ≤1 cast/window,
overflow carry (T.29c, V.48)."""

from __future__ import annotations

from src.game.piece import ActiveSlot, Piece
from src.game.combat.engine import _charge_mana, process_casts
from src.game.registries import (
    ABILITY_MANA,
    ability_mana,
    register_ability_mana,
    DEFAULT_MANA_COST,
)


# --- ActiveSlot defaults (V.48) ---------------------------------------------

def test_max_mana_defaults_to_double_cost():
    s = ActiveSlot(ability_id="a", mana_cost=300_000)
    assert s.max_mana == 600_000  # 2× cost overload headroom


def test_priority_normalized_to_at_least_one():
    assert ActiveSlot("a", mana_cost=1, priority=0).priority == 1
    assert ActiveSlot("a", mana_cost=1, priority=3).priority == 3


def test_explicit_max_mana_respected():
    assert ActiveSlot("a", mana_cost=100, max_mana=1000).max_mana == 1000


# --- ABILITY_MANA registry ---------------------------------------------------

def test_default_ability_mana():
    m = ability_mana("nonexistent-id")
    assert m.mana_cost == DEFAULT_MANA_COST == 300_000
    assert m.priority == 1


def test_register_ability_mana_roundtrip():
    register_ability_mana("test:cheap_spell", mana_cost=120_000, priority=2)
    try:
        m = ability_mana("test:cheap_spell")
        assert (m.mana_cost, m.priority) == (120_000, 2)
    finally:
        ABILITY_MANA.pop("test:cheap_spell", None)


# --- Weighted-rank charge cycle (T3) ----------------------------------------

def _piece_with_slots(specs: list[tuple[int, int]]) -> Piece:
    """specs = [(mana_cost, priority), ...]; high max_mana so nothing caps."""
    p = Piece(id="p")
    p.actives = [
        ActiveSlot(ability_id=f"s{i}", mana_cost=c, max_mana=10_000_000, priority=pr)
        for i, (c, pr) in enumerate(specs)
    ]
    return p


def test_single_slot_charges_every_tick():
    p = _piece_with_slots([(300_000, 1)])
    for _ in range(5):
        _charge_mana(p, 100)
    assert p.actives[0].current_mana == 500.0


def test_weighted_cycle_distributes_by_priority():
    # priorities 3,2,1 → cycle [s0,s0,s0,s1,s1,s2]; 6 ticks of 10 mana each.
    p = _piece_with_slots([(1_000, 3), (1_000, 2), (1_000, 1)])
    for _ in range(6):
        _charge_mana(p, 10)
    assert p.actives[0].current_mana == 30.0  # 3 ticks
    assert p.actives[1].current_mana == 20.0  # 2 ticks
    assert p.actives[2].current_mana == 10.0  # 1 tick
    # Total throughput == mana_regen/tick * ticks, regardless of slot count.
    assert sum(s.current_mana for s in p.actives) == 60.0


def test_charge_cycle_skips_full_slots():
    p = _piece_with_slots([(1_000, 1), (1_000, 1)])
    p.actives[0].max_mana = 5  # fill fast
    p.actives[0].current_mana = 5.0  # already full
    _charge_mana(p, 10)  # cursor at 0 → slot0 full → route to slot1
    assert p.actives[1].current_mana == 10.0
    assert p.actives[0].current_mana == 5.0


# --- One cast per window + overflow carry (T4 / V.48) ------------------------

class _FakeCtx:
    def __init__(self):
        self.casts: list[int] = []

    def cast_ability(self, piece, slot_idx):
        self.casts.append(slot_idx)


def test_one_cast_per_window_highest_priority():
    register_ability_mana("test:reg", mana_cost=100, priority=1)
    # Two ready slots; only the highest priority casts this window.
    import src.game.registries as reg
    reg.ABILITY_REGISTRY["test:reg"] = lambda *a, **k: None
    reg.ABILITY_REGISTRY["test:reg2"] = lambda *a, **k: None
    try:
        p = Piece(id="p")
        p.actives = [
            ActiveSlot("test:reg", mana_cost=100, max_mana=1000, current_mana=250, priority=1),
            ActiveSlot("test:reg2", mana_cost=100, max_mana=1000, current_mana=250, priority=5),
        ]
        ctx = _FakeCtx()
        process_casts(ctx, p)
        assert ctx.casts == [1]  # only the priority-5 slot cast (one cast)
        # Overflow carries: 250 - 100 = 150 on the slot that cast.
        assert p.actives[1].current_mana == 150.0
        assert p.actives[0].current_mana == 250.0  # untouched, still ready
    finally:
        reg.ABILITY_REGISTRY.pop("test:reg", None)
        reg.ABILITY_REGISTRY.pop("test:reg2", None)
        ABILITY_MANA.pop("test:reg", None)


# --- Grievous antiheal primitive (item rebalance) ---------------------------

def test_grievous_halves_incoming_heal():
    from src.game.combat.context import CombatContext
    from src.game.effects import EventBus
    from src.game.models import WeatherState
    p = Piece(id="h", base_stats={"hp": 1000.0})
    p.max_hp = 1000.0
    p.hp = 100.0
    ctx = CombatContext([p], EventBus(), WeatherState.CLEAR, seed=1)
    assert ctx.heal(p, p, 200.0) == 200.0  # no grievous → full
    p.hp = 100.0
    ctx.apply_status(p, "grievous", 200)
    assert ctx.heal(p, p, 200.0) == 100.0  # grievous → ×0.5
