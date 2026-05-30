"""T.30 ability catalog tests — CI guard + smoke tests.

Tests:
1. Resolution guard: all roster ability IDs resolve in registries
2. Per-piece smoke: basic ability execution produces expected effects
3. Scaling correctness: STR abilities scale with STR, INT with INT
4. Boss phase hooks: phase transition works correctly
5. Summon lifecycle: spawn + despawn
"""

from __future__ import annotations

import src.game.abilities  # Trigger registration  # noqa: F401
from src.game.combat.context import CombatContext
from src.game.content import _CHAMPION_DEFS, _ENEMY_DEFS
from src.game.effects import EventBus, Lifetime, Modifier, SourceTag
from src.game.models import WeatherState
from src.game.piece import ActiveSlot, Piece
from src.game.registries import ABILITY_REGISTRY, PASSIVE_REGISTRY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_piece(
    piece_id: str = "test_piece",
    *,
    is_enemy: bool = False,
    strength: float = 100.0,
    intelligence: float = 100.0,
    max_hp: float = 1000.0,
    armor: float = 25.0,
    resistance: float = 25.0,
    attack_speed: float = 100.0,
    attack_range: float = 2.0,
    active_id: str = "",
    passive_id: str = "",
) -> Piece:
    stats = {
        "max_hp": max_hp,
        "strength": strength,
        "intelligence": intelligence,
        "armor": armor,
        "resistance": resistance,
        "attack_speed": attack_speed,
        "mana_regen": 10,
        "move_speed": 90,
        "threat": 60,
        "attack_range": attack_range,
        "ability_cost": 36_000,
        "crit_chance": 0.0,
        "penetration": 0,
        "penetration_pct": 0.0,
    }
    piece = Piece(
        id=piece_id,
        base_stats=stats,
        affinity=WeatherState.CLEAR,
        is_enemy=is_enemy,
        hp=max_hp,
        max_hp=max_hp,
        position_q=0 if not is_enemy else 5,
        position_r=3,
    )
    if active_id:
        piece.actives = [ActiveSlot(ability_id=active_id, cost=36_000)]
    if passive_id:
        piece.passives = [passive_id]
    return piece


def _make_ctx(pieces: list[Piece]) -> CombatContext:
    bus = EventBus()
    return CombatContext(pieces, bus, WeatherState.CLEAR, seed=42)


# ---------------------------------------------------------------------------
# 1. Resolution Guard (CI guard — §3)
# ---------------------------------------------------------------------------


def test_all_champion_abilities_resolve():
    """Every champion roster active_ability resolves in ABILITY_REGISTRY."""
    for d in _CHAMPION_DEFS:
        assert d.active_ability in ABILITY_REGISTRY, (
            f"Champion {d.id}: active_ability '{d.active_ability}' not in ABILITY_REGISTRY"
        )


def test_all_champion_passives_resolve():
    """Every champion roster passive_ability resolves in PASSIVE_REGISTRY."""
    for d in _CHAMPION_DEFS:
        assert d.passive_ability in PASSIVE_REGISTRY, (
            f"Champion {d.id}: passive_ability '{d.passive_ability}' not in PASSIVE_REGISTRY"
        )


def test_all_enemy_abilities_resolve():
    """Every enemy roster active_ability resolves in ABILITY_REGISTRY."""
    for d in _ENEMY_DEFS:
        assert d.active_ability in ABILITY_REGISTRY, (
            f"Enemy {d.id}: active_ability '{d.active_ability}' not in ABILITY_REGISTRY"
        )


def test_all_enemy_passives_resolve():
    """Every enemy roster passive_ability resolves in PASSIVE_REGISTRY."""
    for d in _ENEMY_DEFS:
        assert d.passive_ability in PASSIVE_REGISTRY, (
            f"Enemy {d.id}: passive_ability '{d.passive_ability}' not in PASSIVE_REGISTRY"
        )


def test_all_boss_abilities_resolve():
    """Every BossDef phase1/2 active and passive resolves in the registries."""
    from src.game.bosses.data import BOSS_DEFS

    for boss in BOSS_DEFS.values():
        for field_name, ability_id, registry in (
            ("phase1_active", boss.phase1_active, ABILITY_REGISTRY),
            ("phase1_passive", boss.phase1_passive, PASSIVE_REGISTRY),
            ("phase1_phase_hook", boss.phase1_phase_hook, PASSIVE_REGISTRY),
            ("phase2_active", boss.phase2_active, ABILITY_REGISTRY),
            ("phase2_passive", boss.phase2_passive, PASSIVE_REGISTRY),
            ("on_death_hook", boss.on_death_hook, PASSIVE_REGISTRY),
        ):
            if ability_id:
                assert ability_id in registry, (
                    f"Boss {boss.id}: {field_name} '{ability_id}' not in registry"
                )


# ---------------------------------------------------------------------------
# 2. Smoke tests — basic ability execution
# ---------------------------------------------------------------------------


def test_dawnwisp_heals_ally():
    """Dawnwisp active heals lowest HP ally."""
    healer = _make_piece("healer", intelligence=100.0, active_id="champ_dawnwisp.active")
    ally = _make_piece("ally", max_hp=500.0)
    ally.hp = 200.0
    ally.is_enemy = False
    enemy = _make_piece("enemy", is_enemy=True)
    ctx = _make_ctx([healer, ally, enemy])
    handler = ABILITY_REGISTRY["champ_dawnwisp.active"]
    handler(ctx, healer, [enemy])
    assert ally.hp > 200.0, "Dawnwisp should have healed the ally"


def test_ember_salamander_burns_target():
    """Ember Salamander active applies burn."""
    caster = _make_piece("caster", intelligence=100.0, active_id="champ_ember_salamander.active")
    target = _make_piece("target", is_enemy=True, max_hp=2000.0)
    ctx = _make_ctx([caster, target])
    handler = ABILITY_REGISTRY["champ_ember_salamander.active"]
    handler(ctx, caster, [target])
    assert target.hp < 2000.0, "Should have dealt damage"
    assert target.has_status("burn"), "Should have applied burn"


def test_sunmane_lion_self_heals():
    """Sunmane Lion active heals self after damage."""
    lion = _make_piece("lion", strength=150.0, active_id="champ_sunmane_lion.active")
    lion.hp = 500.0
    target = _make_piece("target", is_enemy=True, max_hp=2000.0)
    ctx = _make_ctx([lion, target])
    handler = ABILITY_REGISTRY["champ_sunmane_lion.active"]
    handler(ctx, lion, [target])
    assert lion.hp > 500.0, "Should have healed self"


def test_sparkfly_stuns_target():
    """Sparkfly active stuns the target."""
    caster = _make_piece("caster", intelligence=50.0, active_id="champ_sparkfly.active")
    target = _make_piece("target", is_enemy=True, max_hp=2000.0)
    ctx = _make_ctx([caster, target])
    handler = ABILITY_REGISTRY["champ_sparkfly.active"]
    handler(ctx, caster, [target])
    assert target.has_status("stun"), "Should have applied stun"


# ---------------------------------------------------------------------------
# 3. Scaling correctness
# ---------------------------------------------------------------------------


def test_str_ability_scales_with_strength():
    """Veldt Pronghorn active (STR-scaling) does more damage with higher STR."""
    target_low = _make_piece("target_low", is_enemy=True, max_hp=5000.0)
    target_high = _make_piece("target_high", is_enemy=True, max_hp=5000.0)

    caster_low = _make_piece("low_str", strength=50.0, active_id="champ_veldt_pronghorn.active")
    caster_high = _make_piece("high_str", strength=200.0, active_id="champ_veldt_pronghorn.active")

    ctx_low = _make_ctx([caster_low, target_low])
    ctx_high = _make_ctx([caster_high, target_high])

    handler = ABILITY_REGISTRY["champ_veldt_pronghorn.active"]
    handler(ctx_low, caster_low, [target_low])
    handler(ctx_high, caster_high, [target_high])

    dmg_low = 5000.0 - target_low.hp
    dmg_high = 5000.0 - target_high.hp
    assert dmg_high > dmg_low, "Higher STR should deal more damage"


def test_int_ability_scales_with_intelligence():
    """Tempest Eel active (INT-scaling) does more damage with higher INT."""
    target_low = _make_piece("target_low", is_enemy=True, max_hp=5000.0)
    target_high = _make_piece("target_high", is_enemy=True, max_hp=5000.0)

    caster_low = _make_piece("low_int", intelligence=50.0, active_id="champ_tempest_eel.active")
    caster_high = _make_piece("high_int", intelligence=200.0, active_id="champ_tempest_eel.active")

    ctx_low = _make_ctx([caster_low, target_low])
    ctx_high = _make_ctx([caster_high, target_high])

    handler = ABILITY_REGISTRY["champ_tempest_eel.active"]
    handler(ctx_low, caster_low, [target_low])
    handler(ctx_high, caster_high, [target_high])

    dmg_low = 5000.0 - target_low.hp
    dmg_high = 5000.0 - target_high.hp
    assert dmg_high > dmg_low, "Higher INT should deal more damage"


# ---------------------------------------------------------------------------
# 4. Boss phase hook
# ---------------------------------------------------------------------------


def test_holloway_phase_hook_triggers_at_50pct():
    """Holloway phase hook triggers when HP drops below 50%."""
    from src.game.loadout import apply_bundle

    boss = _make_piece("boss_holloway", is_enemy=True, strength=80.0, max_hp=900.0,
                       active_id="holloway.pressure_vent")
    boss.hp = 900.0
    champion = _make_piece("champion", strength=200.0)

    ctx = _make_ctx([boss, champion])
    # Apply phase hook passive
    bundle = PASSIVE_REGISTRY["holloway.phase_hook"](boss)
    apply_bundle(boss, bundle, ctx.bus, ctx=ctx)

    # Damage boss below 50%
    boss.hp = 440.0
    from src.game.events import DamageEvent
    event = DamageEvent(attacker=champion, target=boss, amount=10.0, tag="ability")
    ctx.bus.fire("on_damage_taken", event, ctx=ctx)

    # Phase hook should have swapped the active ability
    assert boss.actives[0].ability_id == "holloway.magma_heave"


# ---------------------------------------------------------------------------
# 5. Summon lifecycle
# ---------------------------------------------------------------------------


def test_umbra_spawns_clones():
    """Umbra active spawns clone pieces."""
    umbra = _make_piece("champ_umbra", intelligence=100.0, active_id="champ_umbra.active")
    enemy = _make_piece("enemy", is_enemy=True, max_hp=2000.0)
    ctx = _make_ctx([umbra, enemy])

    handler = ABILITY_REGISTRY["champ_umbra.active"]
    handler(ctx, umbra, [enemy])

    # Should have spawned 2 clones
    all_pieces = ctx.all_pieces()
    clones = [p for p in all_pieces if p.summon]
    assert len(clones) == 2, f"Expected 2 clones, got {len(clones)}"
    assert all(c.summon_owner_id == "champ_umbra" for c in clones)
    assert all(c.alive for c in clones)


def test_summon_expires():
    """Summons expire via the real combat loop when their tick passes."""
    from src.game.combat import loop_new

    # Use large HP so neither piece dies before the summon expiry at tick 100.
    # At tick 100 no auto-attacks have fired yet (energy threshold requires 600 ticks
    # of regen at default attack_speed=100 to overflow 60_000).
    piece = _make_piece("summoned", is_enemy=True, max_hp=100_000.0)
    piece.summon = True
    piece.summon_expires_tick = 100
    piece.position_q = 9
    piece.position_r = 3

    hero = _make_piece("hero", max_hp=100_000.0)
    hero.position_q = 0
    hero.position_r = 3

    ctx = _make_ctx([piece, hero])

    assert piece.alive, "Summon should be alive before the loop runs"

    # Drive the real combat loop — the loop despawns expired summons at tick 100.
    result = loop_new.run(ctx)

    assert not piece.alive, "Summon should be despawned by the combat loop"
    assert piece.hp == 0.0
    assert result == "team", "Hero should win once the only enemy summon expires"


# ---------------------------------------------------------------------------
# 6. Enemy abilities smoke
# ---------------------------------------------------------------------------


def test_powder_sapper_str_scaling():
    """Powder Sapper (STR piece) ability scales with STR, not just INT."""
    sapper = _make_piece("sapper", is_enemy=True, strength=150.0, intelligence=20.0,
                         active_id="enemy_powder_sapper.active")
    target = _make_piece("target", max_hp=5000.0)
    ctx = _make_ctx([sapper, target])

    handler = ABILITY_REGISTRY["enemy_powder_sapper.active"]
    handler(ctx, sapper, [target])

    dmg = 5000.0 - target.hp
    # With STR 150 and scaling "strength*1.8", damage should be substantial
    assert dmg > 100.0, f"STR-scaling sapper should deal significant damage, got {dmg}"


def test_signal_drummer_aura_buffs_allies():
    """Signal Drummer passive aura buffs nearby ally AS."""
    drummer = _make_piece("drummer", is_enemy=True, intelligence=50.0)
    ally = _make_piece("ally", is_enemy=True)
    enemy = _make_piece("enemy")

    # Place drummer and ally close together
    drummer.position_q = 5
    drummer.position_r = 3
    ally.position_q = 6
    ally.position_r = 3

    ctx = _make_ctx([drummer, ally, enemy])
    bundle = PASSIVE_REGISTRY["enemy_signal_drummer.passive"](drummer)
    from src.game.loadout import apply_bundle
    apply_bundle(drummer, bundle, ctx.bus, ctx=ctx)

    # Simulate tick
    from src.game.events import TickEvent
    ctx.current_tick = 300
    ctx.bus.fire("on_tick", TickEvent(tick=300), ctx=ctx)

    # Ally should have an AS modifier
    as_mods = [m for m in ally.modifiers if m.stat == "attack_speed" and "signal_drummer" in m.source_id]
    assert len(as_mods) > 0, "Signal Drummer should have buffed ally AS"


# ---------------------------------------------------------------------------
# 7. Periodic tick effect (round semantics — G8 amendment)
# ---------------------------------------------------------------------------


def test_snowpelt_cub_gains_hp_every_600_ticks():
    """Snowpelt Cub passive raises max_hp and hp every 600 ticks (not rounds)."""
    from src.game.events import TickEvent
    from src.game.loadout import apply_bundle

    cub = _make_piece("cub", max_hp=500.0)
    cub.hp = 500.0
    enemy = _make_piece("enemy", is_enemy=True)

    ctx = _make_ctx([cub, enemy])
    bundle = PASSIVE_REGISTRY["champ_snowpelt_cub.passive"](cub)
    apply_bundle(cub, bundle, ctx.bus, ctx=ctx)

    initial_max_hp = cub.max_hp
    initial_hp = cub.hp

    # At tick 0, no proc yet
    ctx.current_tick = 0
    ctx.bus.fire("on_tick", TickEvent(tick=0), ctx=ctx)
    assert cub.max_hp == initial_max_hp, "Should not proc at tick 0"

    # At tick 600, should proc: max_hp and hp both increase by 30
    ctx.current_tick = 600
    ctx.bus.fire("on_tick", TickEvent(tick=600), ctx=ctx)
    assert cub.max_hp == initial_max_hp + 30.0, "max_hp should increase by 30 at tick 600"
    assert cub.hp == initial_hp + 30.0, "hp should increase by 30 at tick 600"
