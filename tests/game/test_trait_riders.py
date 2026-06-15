"""T.28c — trait mechanic + apex riders (deterministic hook idioms over `ctx`).

Each rider is exercised against a real `CombatContext` (no parallel fakes), then
one integration test resolves a multi-trait battle twice to assert byte-identical
determinism (V.2/V.14).
"""

from src.game.combat.context import CombatContext
from src.game.content import build_champion_at_level, build_enemy_at_level
from src.game.effects import EventBus
from src.game.events import (
    AttackEvent,
    CastEvent,
    DamageEvent,
    DeathEvent,
    HealEvent,
    KillEvent,
)
from src.game.loadout import piece_from_champion, piece_from_enemy
from src.game.models import WeatherState
from src.game.traits import mechanics as m


def _piece(cid: str, q: int, r: int, enemy: bool):
    if cid.startswith("enemy_"):
        p = piece_from_enemy(build_enemy_at_level(cid, 1))
    else:
        p = piece_from_champion(build_champion_at_level(cid, 1))
    p.position_q, p.position_r = q, r
    p.is_enemy = enemy
    p.hp = p.max_hp
    return p


def _ctx(pieces):
    return CombatContext(pieces, EventBus(), WeatherState.CLEAR)


# --- damage riders --------------------------------------------------------

def test_bonus_auto_damage_extra_hit():
    owner = _piece("champ_sunmane_lion", 0, 0, False)
    enemy = _piece("enemy_conscript", 1, 0, True)
    ctx = _ctx([owner, enemy])
    [h] = m.bonus_auto_damage(0.3)(owner, "sid")
    before = enemy.hp
    h.handler(ctx, AttackEvent(attacker=owner, target=enemy))
    assert enemy.hp < before


def test_bonus_auto_damage_ignores_other_attackers():
    owner = _piece("champ_sunmane_lion", 0, 0, False)
    other = _piece("champ_dawnwisp", 0, 1, False)
    enemy = _piece("enemy_conscript", 1, 0, True)
    ctx = _ctx([owner, other, enemy])
    [h] = m.bonus_auto_damage(0.3)(owner, "sid")
    before = enemy.hp
    h.handler(ctx, AttackEvent(attacker=other, target=enemy))
    assert enemy.hp == before


def test_empowered_shot_fires_every_nth():
    owner = _piece("champ_sunmane_lion", 0, 0, False)
    enemy = _piece("enemy_conscript", 1, 0, True)
    ctx = _ctx([owner, enemy])
    [h] = m.empowered_shot(every_n=3, mult=0.5)(owner, "sid")
    enemy.hp = enemy.max_hp
    for _ in range(2):
        before = enemy.hp
        h.handler(ctx, AttackEvent(attacker=owner, target=enemy))
        assert enemy.hp == before  # no empowered hit yet
    before = enemy.hp
    h.handler(ctx, AttackEvent(attacker=owner, target=enemy))  # 3rd
    assert enemy.hp < before


def test_cleave_hits_neighbour_of_target():
    owner = _piece("champ_sunmane_lion", 0, 0, False)
    target = _piece("enemy_conscript", 1, 0, True)
    neighbour = _piece("enemy_levyman", 1, 1, True)  # adjacent to target
    ctx = _ctx([owner, target, neighbour])
    [h] = m.cleave(0.5)(owner, "sid")
    before = neighbour.hp
    h.handler(ctx, AttackEvent(attacker=owner, target=target))
    assert neighbour.hp < before


def test_attack_lifesteal_only_on_basic():
    owner = _piece("champ_sunmane_lion", 0, 0, False)
    enemy = _piece("enemy_conscript", 1, 0, True)
    ctx = _ctx([owner, enemy])
    [h] = m.attack_lifesteal(0.5)(owner, "sid")
    owner.hp = 0.5 * owner.max_hp
    h.handler(ctx, DamageEvent(attacker=owner, target=enemy, amount=100.0, tag="basic_attack"))
    assert owner.hp > 0.5 * owner.max_hp
    healed = owner.hp
    h.handler(ctx, DamageEvent(attacker=owner, target=enemy, amount=100.0, tag="ability"))
    assert owner.hp == healed  # ability hits don't lifesteal


def test_high_hp_bonus_only_above_threshold():
    owner = _piece("champ_sunmane_lion", 0, 0, False)
    enemy = _piece("enemy_conscript", 1, 0, True)
    ctx = _ctx([owner, enemy])
    [h] = m.high_hp_bonus(0.4, threshold=0.6)(owner, "sid")
    enemy.hp = enemy.max_hp  # full → above threshold
    before = enemy.hp
    h.handler(ctx, DamageEvent(attacker=owner, target=enemy, amount=10.0, tag="basic_attack"))
    assert enemy.hp < before
    enemy.hp = 0.3 * enemy.max_hp  # below threshold
    low = enemy.hp
    h.handler(ctx, DamageEvent(attacker=owner, target=enemy, amount=10.0, tag="basic_attack"))
    assert enemy.hp == low
    # ITEM_PROC re-entry is ignored (no recursion / no double bonus)
    enemy.hp = enemy.max_hp
    mid = enemy.hp
    h.handler(ctx, DamageEvent(attacker=owner, target=enemy, amount=10.0, tag="item_proc"))
    assert enemy.hp == mid


# --- shields / sustain ----------------------------------------------------

def test_start_shield_grants_barrier():
    owner = _piece("champ_aegis_tortoise", 0, 0, False)
    ctx = _ctx([owner])
    [h] = m.start_shield(0.25)(owner, "sid")
    h.handler(ctx, object())
    assert owner.barrier_total == 0.25 * owner.max_hp


def test_heal_splash_to_lowest_other_ally():
    owner = _piece("champ_dawnwisp", 0, 0, False)
    hurt = _piece("champ_springfrog", 0, 1, False)
    ctx = _ctx([owner, hurt])
    hurt.hp = 0.3 * hurt.max_hp
    [h] = m.heal_splash(0.5)(owner, "sid")
    before = hurt.hp
    h.handler(ctx, HealEvent(source=owner, target=owner, amount=100.0))
    assert hurt.hp > before


def test_overheal_shield_when_target_near_full():
    owner = _piece("champ_dawnwisp", 0, 0, False)
    ally = _piece("champ_springfrog", 0, 1, False)
    ctx = _ctx([owner, ally])
    ally.hp = ally.max_hp  # full → heal would overheal
    [h] = m.overheal_shield(0.5, threshold=0.95)(owner, "sid")
    h.handler(ctx, HealEvent(source=owner, target=ally, amount=80.0))
    assert ally.barrier_total == 0.5 * 80.0


# --- cast riders ----------------------------------------------------------

def test_taunt_on_cast_marks_nearest_enemy():
    owner = _piece("champ_glade_heron", 0, 0, False)
    near = _piece("enemy_conscript", 1, 0, True)
    far = _piece("enemy_levyman", 5, 0, True)
    ctx = _ctx([owner, near, far])
    [h] = m.taunt_on_cast(300)(owner, "sid")
    h.handler(ctx, CastEvent(caster=owner, ability_id="x", cast_id=1))
    t = near.get_status("taunt")
    assert t is not None and t.source_id == owner.id
    assert far.get_status("taunt") is None


def test_free_cast_refunds_every_nth():
    owner = _piece("champ_dawnwisp", 0, 0, False)
    ctx = _ctx([owner])
    assert owner.actives, "champ needs an ability slot for this test"
    owner.actives[0].current_mana = 0.0
    [h] = m.free_cast(3)(owner, "sid")
    for _ in range(2):
        h.handler(ctx, CastEvent(caster=owner, ability_id="x", cast_id=1))
        assert owner.actives[0].current_mana == 0.0
    h.handler(ctx, CastEvent(caster=owner, ability_id="x", cast_id=1))
    assert owner.actives[0].current_mana == owner.actives[0].mana_cost


def test_mana_on_kill_refunds():
    owner = _piece("champ_dawnwisp", 0, 0, False)  # a caster → has an ability slot
    victim = _piece("enemy_conscript", 1, 0, True)
    ctx = _ctx([owner, victim])
    assert owner.actives, "caster should have an ability slot"
    owner.actives[0].current_mana = 0.0
    [h] = m.mana_on_kill(0.5)(owner, "sid")
    h.handler(ctx, KillEvent(killer=owner, victim=victim))
    assert owner.actives[0].current_mana > 0.0


# --- on-death spawn -------------------------------------------------------

def test_on_death_spawn_leaves_chitin():
    owner = _piece("champ_wintermoth", 3, 3, False)  # a Swarm carrier
    assert "Swarm" in owner.traits
    ctx = _ctx([owner])
    [h] = m.on_death_spawn(0.5)(owner, "sid")
    owner.alive = False  # death path: victim already flagged dead
    h.handler(ctx, DeathEvent(victim=owner, killer=None))
    spawned = [p for p in ctx.all_pieces() if p.summon]
    assert len(spawned) == 1
    c = spawned[0]
    assert c.is_enemy == owner.is_enemy and c.alive and c.summon_owner_id == owner.id
    assert (c.position_q, c.position_r) == (3, 3)


def test_on_death_spawn_guarded_by_trait():
    owner = _piece("champ_sunmane_lion", 0, 0, False)  # not a Swarm carrier
    assert "Swarm" not in owner.traits
    ctx = _ctx([owner])
    [h] = m.on_death_spawn(0.5, trait="Swarm")(owner, "sid")
    owner.alive = False
    h.handler(ctx, DeathEvent(victim=owner, killer=None))
    assert not [p for p in ctx.all_pieces() if p.summon]


def test_on_death_spawn_no_recursive_spawn():
    owner = _piece("champ_wintermoth", 3, 3, False)
    owner.summon = True  # a spawn cannot spawn again
    ctx = _ctx([owner])
    [h] = m.on_death_spawn(0.5)(owner, "sid")
    owner.alive = False
    h.handler(ctx, DeathEvent(victim=owner, killer=None))
    assert not [p for p in ctx.all_pieces() if p.summon and p is not owner]


# --- determinism integration ---------------------------------------------

def test_multi_trait_battle_is_deterministic():
    def make():
        team = [
            build_champion_at_level("champ_dusk_bat", 1),       # Hunter/Swarm
            build_champion_at_level("champ_springfrog", 1),     # Mender/Packmate
            build_champion_at_level("champ_sunmane_lion", 1),   # Bruiser
            build_champion_at_level("champ_snowpelt_cub", 1),   # Guardian
        ]
        enemies = [build_enemy_at_level("enemy_conscript", 1) for _ in range(4)]
        return team, enemies

    from src.game.combat.resolve import resolve_combat
    t1, e1 = make()
    t2, e2 = make()
    r1 = resolve_combat(t1, e1, WeatherState.CLEAR)
    r2 = resolve_combat(t2, e2, WeatherState.CLEAR)
    assert r1.to_dict() == r2.to_dict()
