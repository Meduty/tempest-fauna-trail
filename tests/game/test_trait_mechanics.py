"""T.28b — trait combat primitives (deterministic, RNG-free).

Hook-builders are unit-tested against a recording fake ctx; the engine-behaviour
arms (kiting, backline, taunt) are tested through the real engine helpers
(`_kite_step`, `_select_target`, `_opponents`); revive through `ctx.revive`.
"""

from types import SimpleNamespace

from src.game.combat.engine import (
    _backline_subset,
    _kite_step,
    _opponents,
    _select_target,
    _taunt_target,
)
from src.game.content import build_champion_at_level
from src.game.loadout import piece_from_champion
from src.game.status import StatusInstance
from src.game.traits import mechanics as m


class FakeCtx:
    def __init__(self):
        self.current_tick = 0
        self.barriers = []
        self.heals = []
        self.mods = []
        self.statuses = []
        self.revived = []
        self._mender_revive_used = False

    def grant_barrier(self, target, amount, duration_ticks=0):
        self.barriers.append((target, amount, duration_ticks))

    def heal(self, source, target, amount):
        self.heals.append((target, amount))
        return amount

    def apply_modifier(self, target, modifier):
        self.mods.append((target, modifier))
        target.modifiers.append(modifier)  # mirror real ctx so .stat() reflects it

    def apply_status(self, target, status_id, duration, source_id=""):
        self.statuses.append((target, status_id, duration))

    def revive(self, target, hp_frac=0.3):
        if target.alive:
            return False
        target.alive = True
        target.hp = max(1.0, target.max_hp * hp_frac)
        self.revived.append((target, hp_frac))
        return True


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
    assert len(ctx.mods) == 2  # attack_speed, strength (no milli_AS rider — T.29-pre)
    hook.handler(ctx, _dmg_event(owner))
    assert len(ctx.mods) == 2  # once only


def test_time_ramp_stacks_to_cap():
    owner = _owner()
    ctx = FakeCtx()
    [hook] = m.time_ramp(interval=2, per=0.03, cap=3)(owner, "trait:Skirmisher@2")
    for _ in range(20):
        hook.handler(ctx, SimpleNamespace())
    # 3 stacks × attack_speed = 3 modifiers, capped (no milli_AS rider — T.29-pre).
    assert len(ctx.mods) == 3
    stats = {mod.stat for _t, mod in ctx.mods}
    assert stats == {"attack_speed"}


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


def test_hexproof_opener_applies_status_at_combat_start():
    owner = _owner()
    ctx = FakeCtx()
    [hook] = m.hexproof_opener(duration=150)(owner, "trait:Spirit@5")
    hook.handler(ctx, SimpleNamespace())
    assert ctx.statuses == [(owner, "hexproof", 150)]


# --------------------------------------------------------------------------
# Engine-behaviour arms: kiting / backline / taunt / revive
# --------------------------------------------------------------------------

from src.game.combat.context import hex_distance
from src.game.effects import Lifetime, Modifier


def _at(champ_id: str, q: int, r: int, enemy: bool):
    p = piece_from_champion(build_champion_at_level(champ_id, 1))
    p.position_q, p.position_r = q, r
    p.is_enemy = enemy
    p.hp = p.max_hp
    return p


def _set_range(piece, value):
    piece.modifiers.append(Modifier("attack_range", "set", float(value), Lifetime.COMBAT, ""))


def test_kiting_arms_flag_and_grants_melee_range():
    owner = _owner()
    base = int(owner.stat("attack_range"))
    ctx = FakeCtx()
    [hook] = m.kiting()(owner, "trait:Skyborn@2")
    hook.handler(ctx, SimpleNamespace())
    assert owner.is_kiter is True
    expected = base + 1 if base <= 1 else base
    assert int(owner.stat("attack_range")) == expected


def test_kiting_no_double_range_for_already_ranged():
    owner = _owner()
    _set_range(owner, 3)
    ctx = FakeCtx()
    [hook] = m.kiting()(owner, "sid")
    hook.handler(ctx, SimpleNamespace())
    assert int(owner.stat("attack_range")) == 3  # already ranged → no bonus


def test_backline_seeker_arms_flag():
    owner = _owner()
    ctx = FakeCtx()
    [hook] = m.backline_seeker()(owner, "trait:Stalker@2")
    hook.handler(ctx, SimpleNamespace())
    assert owner.seeks_backline is True


def test_revive_first_ally_reverses_one_death():
    owner = _at("champ_sunmane_lion", 0, 0, False)
    ctx = FakeCtx()
    [hook] = m.revive_first_ally(hp_frac=0.3)(owner, "trait:Mender@6")

    dead = _at("champ_reedbank_otter", 1, 0, False)
    dead.alive, dead.hp = False, 0.0
    hook.handler(ctx, SimpleNamespace(victim=dead))
    assert dead.alive is True
    assert dead.hp == 0.3 * dead.max_hp
    assert len(ctx.revived) == 1

    # The second ally death the same combat is NOT revived.
    dead2 = _at("champ_will_o_fawn", 2, 0, False)
    dead2.alive, dead2.hp = False, 0.0
    hook.handler(ctx, SimpleNamespace(victim=dead2))
    assert dead2.alive is False
    assert len(ctx.revived) == 1


def test_revive_shared_once_across_carriers():
    o1 = _at("champ_sunmane_lion", 0, 0, False)
    o2 = _at("champ_reedbank_otter", 1, 0, False)
    ctx = FakeCtx()
    [h1] = m.revive_first_ally()(o1, "sid")
    [h2] = m.revive_first_ally()(o2, "sid")

    dead = _at("champ_will_o_fawn", 2, 0, False)
    dead.alive, dead.hp = False, 0.0
    h1.handler(ctx, SimpleNamespace(victim=dead))
    assert dead.alive is True

    dead2 = _at("champ_sunmane_lion", 3, 0, False)
    dead2.id = "other"
    dead2.alive, dead2.hp = False, 0.0
    h2.handler(ctx, SimpleNamespace(victim=dead2))  # flag shared on ctx → no revive
    assert dead2.alive is False


def test_revive_ignores_enemy_deaths():
    owner = _at("champ_sunmane_lion", 0, 0, False)
    enemy = _at("champ_reedbank_otter", 1, 0, True)
    enemy.alive, enemy.hp = False, 0.0
    ctx = FakeCtx()
    [hook] = m.revive_first_ally()(owner, "sid")
    hook.handler(ctx, SimpleNamespace(victim=enemy))
    assert enemy.alive is False
    assert ctx._mender_revive_used is False


def test_taunt_forces_taunter_as_target():
    attacker = _at("champ_sunmane_lion", 0, 0, False)
    e1 = _at("champ_reedbank_otter", 1, 0, True)
    e2 = _at("champ_will_o_fawn", 4, 0, True)
    cands = [e1, e2]
    assert _taunt_target(attacker, cands) is None  # no status
    attacker.statuses.append(
        StatusInstance(status_id="taunt", remaining_ticks=100, source_id=e2.id)
    )
    assert _taunt_target(attacker, cands) is e2
    assert _select_target(attacker, cands) is e2  # taunt overrides default priority


def test_backline_seeker_targets_deepest_enemy():
    seeker = _at("champ_sunmane_lion", 0, 0, False)
    seeker.seeks_backline = True
    front = _at("champ_reedbank_otter", 2, 0, True)
    back = _at("champ_will_o_fawn", 6, 0, True)
    assert _select_target(seeker, [front, back]) is back
    assert _backline_subset([front, back]) == [back]


def test_kite_step_retreats_from_lone_melee():
    kiter = _at("champ_sunmane_lion", 5, 3, False)
    _set_range(kiter, 2)
    threat = _at("champ_reedbank_otter", 5, 2, True)  # adjacent
    _set_range(threat, 1)  # melee
    step = _kite_step(kiter, [threat], 2, [kiter, threat])
    assert step is not None
    assert hex_distance(step[0], step[1], 5, 2) > 1  # stepped away


def test_kite_step_plants_when_two_melee_adjacent():
    kiter = _at("champ_sunmane_lion", 5, 3, False)
    _set_range(kiter, 2)
    t1 = _at("champ_reedbank_otter", 5, 2, True)
    t2 = _at("champ_will_o_fawn", 6, 3, True)
    _set_range(t1, 1)
    _set_range(t2, 1)
    assert _kite_step(kiter, [t1, t2], 2, [kiter, t1, t2]) is None


def test_kite_step_none_without_melee_threat():
    kiter = _at("champ_sunmane_lion", 5, 3, False)
    _set_range(kiter, 2)
    ranged = _at("champ_reedbank_otter", 5, 1, True)  # dist 2, not adjacent
    _set_range(ranged, 3)
    assert _kite_step(kiter, [ranged], 2, [kiter, ranged]) is None


def test_kite_step_plants_when_cornered():
    kiter = _at("champ_sunmane_lion", 0, 0, False)
    _set_range(kiter, 2)
    threat = _at("champ_reedbank_otter", 1, 0, True)  # adjacent; occupies the one improving tile
    _set_range(threat, 1)
    assert _kite_step(kiter, [threat], 2, [kiter, threat]) is None


# --------------------------------------------------------------------------
def test_hexproof_excluded_from_target_selection():
    attacker = piece_from_champion(build_champion_at_level("champ_sunmane_lion", 1))
    attacker.is_enemy = False
    a = piece_from_champion(build_champion_at_level("champ_reedbank_otter", 1))
    b = piece_from_champion(build_champion_at_level("champ_will_o_fawn", 1))
    for e in (a, b):
        e.is_enemy = True
    pieces = [attacker, a, b]
    assert {p.id for p in _opponents(attacker, pieces)} == {a.id, b.id}
    # Make `a` hexproof → only `b` remains a valid auto-attack target.
    from src.game.status import StatusInstance
    a.statuses.append(StatusInstance(status_id="hexproof", remaining_ticks=100))
    assert [p.id for p in _opponents(attacker, pieces)] == [b.id]
    # A pierces_hexproof attacker sees `a` again.
    attacker.pierces_hexproof = True
    assert {p.id for p in _opponents(attacker, pieces)} == {a.id, b.id}
