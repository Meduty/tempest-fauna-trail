"""T.28b — trait combat primitives batch 1 (deterministic, RNG-free).

Hook-builders are unit-tested against a recording fake ctx; untargetable is
tested through the engine's `_opponents` filter. Movement/targeting/death
primitives (kiting, taunt, backline, revive) are the remaining T.28b work.
"""

from types import SimpleNamespace

from src.game.combat.engine import _opponents
from src.game.content import build_champion_at_level
from src.game.loadout import piece_from_champion
from src.game.traits import mechanics as m


class FakeCtx:
    def __init__(self):
        self.current_tick = 0
        self.barriers = []
        self.heals = []
        self.mods = []
        self.statuses = []

    def grant_barrier(self, target, amount, duration_ticks=0):
        self.barriers.append((target, amount, duration_ticks))

    def heal(self, source, target, amount):
        self.heals.append((target, amount))
        return amount

    def apply_modifier(self, target, modifier):
        self.mods.append((target, modifier))

    def apply_status(self, target, status_id, duration, source_id=""):
        self.statuses.append((target, status_id, duration))


def _owner():
    p = piece_from_champion(build_champion_at_level("champ_sunmane_lion", 1))
    p.hp = p.max_hp
    return p


def _dmg_event(owner, tag="basic_attack"):
    return SimpleNamespace(target=owner, tag=tag)


# --------------------------------------------------------------------------
def test_second_wind_grants_decaying_shield_once_below_threshold():
    owner = _owner()
    ctx = FakeCtx()
    [hook] = m.second_wind(threshold=0.6, shield_frac=0.4, duration=1200)(owner, "trait:Primordial@2")
    # Above threshold → nothing.
    owner.hp = 0.9 * owner.max_hp
    hook.handler(ctx, _dmg_event(owner))
    assert ctx.barriers == []
    # Below threshold → one decaying shield.
    owner.hp = 0.5 * owner.max_hp
    hook.handler(ctx, _dmg_event(owner))
    assert len(ctx.barriers) == 1
    tgt, amount, dur = ctx.barriers[0]
    assert tgt is owner and amount == 0.4 * owner.max_hp and dur == 1200
    # Once per combat.
    hook.handler(ctx, _dmg_event(owner))
    assert len(ctx.barriers) == 1


def test_tidal_hot_heals_on_cadence():
    owner = _owner()
    ctx = FakeCtx()
    [hook] = m.tidal_hot(interval=4, heal_frac=0.02)(owner, "trait:Tidekin@5")
    for _ in range(8):
        hook.handler(ctx, SimpleNamespace())
    assert len(ctx.heals) == 2  # ticks 4 and 8
    assert ctx.heals[0] == (owner, 0.02 * owner.max_hp)


def test_enrage_bursts_once_below_threshold():
    owner = _owner()
    ctx = FakeCtx()
    [hook] = m.enrage(threshold=0.25)(owner, "trait:Beast@8")
    owner.hp = 0.5 * owner.max_hp
    hook.handler(ctx, _dmg_event(owner))
    assert ctx.mods == []  # above threshold
    owner.hp = 0.2 * owner.max_hp
    hook.handler(ctx, _dmg_event(owner))
    assert len(ctx.mods) == 3  # attack_speed, milli_AS, strength
    hook.handler(ctx, _dmg_event(owner))
    assert len(ctx.mods) == 3  # once only


def test_time_ramp_stacks_to_cap():
    owner = _owner()
    ctx = FakeCtx()
    [hook] = m.time_ramp(interval=2, per=0.03, cap=3)(owner, "trait:Skirmisher@2")
    for _ in range(20):
        hook.handler(ctx, SimpleNamespace())
    # 3 stacks × (attack_speed + milli_AS) = 6 modifiers, capped.
    assert len(ctx.mods) == 6
    stats = {mod.stat for _t, mod in ctx.mods}
    assert stats == {"attack_speed", "milli_AS"}


def test_dodge_negates_every_nth_basic_attack():
    owner = _owner()
    ctx = FakeCtx()
    [hook] = m.dodge(every_n=3)(owner, "trait:Skirmisher@4")
    results = [hook.handler(ctx, _dmg_event(owner), 100.0) for _ in range(6)]
    assert results == [100.0, 100.0, 0.0, 100.0, 100.0, 0.0]


def test_dodge_ignores_non_basic_attacks():
    owner = _owner()
    ctx = FakeCtx()
    [hook] = m.dodge(every_n=2)(owner, "sid")
    # ability hits never count toward the dodge cadence.
    assert hook.handler(ctx, _dmg_event(owner, tag="ability"), 50.0) == 50.0
    assert hook.handler(ctx, _dmg_event(owner, tag="ability"), 50.0) == 50.0


def test_untargetable_opener_applies_status_at_combat_start():
    owner = _owner()
    ctx = FakeCtx()
    [hook] = m.untargetable_opener(duration=150)(owner, "trait:Spirit@5")
    hook.handler(ctx, SimpleNamespace())
    assert ctx.statuses == [(owner, "untargetable", 150)]


# --------------------------------------------------------------------------
def test_untargetable_excluded_from_target_selection():
    attacker = piece_from_champion(build_champion_at_level("champ_sunmane_lion", 1))
    attacker.is_enemy = False
    a = piece_from_champion(build_champion_at_level("champ_reedbank_otter", 1))
    b = piece_from_champion(build_champion_at_level("champ_will_o_fawn", 1))
    for e in (a, b):
        e.is_enemy = True
    pieces = [attacker, a, b]
    assert {p.id for p in _opponents(attacker, pieces)} == {a.id, b.id}
    # Make `a` untargetable → only `b` remains a valid target.
    from src.game.status import StatusInstance
    a.statuses.append(StatusInstance(status_id="untargetable", remaining_ticks=100))
    assert [p.id for p in _opponents(attacker, pieces)] == [b.id]
