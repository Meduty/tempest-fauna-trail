"""T.28d — hexproof targeting (V.40), CC-immunity, weather override, reduced echo,
and the new affinity-@10 / fold-in mechanic builders. All deterministic (V.2/V.14).

Mirrors test_trait_riders' real-CombatContext style (no parallel fakes).
"""

from src.game.combat.context import CombatContext
from src.game.combat.engine import _opponents
from src.game.content import build_champion_at_level, build_enemy_at_level
from src.game.effects import EventBus, SourceTag
from src.game.events import DamageEvent
from src.game.loadout import (
    _apply_weather_to_piece,
    compile_loadout,
    piece_from_champion,
    piece_from_enemy,
)
from src.game.models import WeatherState
from src.game.registries import TRAIT_REGISTRY
from src.game.status import StatusInstance
from src.game.targeting import (
    enemies_in_radius,
    furthest_enemy,
    lowest_hp_enemy,
    primary_target,
)
from src.game.traits import mechanics as m


def _piece(cid, q, r, enemy):
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


def _hexproof(piece):
    piece.statuses.append(StatusInstance(status_id="hexproof", remaining_ticks=100))


# --- V.40: hexproof targeting ------------------------------------------------

def test_single_target_helpers_skip_hexproof():
    actor = _piece("champ_sunmane_lion", 0, 0, False)
    enemy = _piece("enemy_conscript", 1, 0, True)
    ctx = _ctx([actor, enemy])
    # Visible while not hexproof.
    assert primary_target(actor, ctx) is enemy
    assert lowest_hp_enemy(actor, ctx) is enemy
    assert furthest_enemy(actor, ctx) is enemy
    # Hexproof → unacquirable as a single target.
    _hexproof(enemy)
    assert primary_target(actor, ctx) is None
    assert lowest_hp_enemy(actor, ctx) is None
    assert furthest_enemy(actor, ctx) is None


def test_auto_attack_excludes_hexproof():
    actor = _piece("champ_sunmane_lion", 0, 0, False)
    enemy = _piece("enemy_conscript", 1, 0, True)
    pieces = [actor, enemy]
    assert _opponents(actor, pieces) == [enemy]
    _hexproof(enemy)
    assert _opponents(actor, pieces) == []


def test_aoe_still_hits_hexproof():
    actor = _piece("champ_sunmane_lion", 0, 0, False)
    enemy = _piece("enemy_conscript", 1, 0, True)
    ctx = _ctx([actor, enemy])
    _hexproof(enemy)
    # AoE / untargeted paths iterate enemies_of directly → still see the piece.
    assert enemy in enemies_in_radius(0, 0, 3, actor, ctx)
    assert enemy in list(ctx.enemies_of(actor))


def test_pierces_hexproof_bypasses():
    actor = _piece("champ_sunmane_lion", 0, 0, False)
    enemy = _piece("enemy_conscript", 1, 0, True)
    ctx = _ctx([actor, enemy])
    _hexproof(enemy)
    actor.pierces_hexproof = True
    assert primary_target(actor, ctx) is enemy
    assert lowest_hp_enemy(actor, ctx) is enemy
    assert _opponents(actor, [actor, enemy]) == [enemy]


def test_pierce_hexproof_builder_sets_flag():
    owner = _piece("champ_aurion", 0, 0, False)
    ctx = _ctx([owner])
    [h] = m.pierce_hexproof()(owner, "trait:Spirit@8")
    assert owner.pierces_hexproof is False
    h.handler(ctx, None)
    assert owner.pierces_hexproof is True


# --- Scaled @5: hard-CC immunity --------------------------------------------

def test_cc_immune_blocks_hard_cc_only():
    owner = _piece("champ_snowpelt_cub", 0, 0, False)
    ctx = _ctx([owner])
    owner.cc_immune = True
    for hard in ("stun", "root", "silence", "disarm", "frozen", "fear"):
        ctx.apply_status(owner, hard, 100)
        assert not owner.has_status(hard), f"{hard} should be blocked"
    # Soft CC + DoTs still land.
    for soft in ("slow", "burn", "poison"):
        ctx.apply_status(owner, soft, 100)
        assert owner.has_status(soft), f"{soft} should still apply"


def test_cc_immunity_builder_arms_flag():
    owner = _piece("champ_snowpelt_cub", 0, 0, False)
    ctx = _ctx([owner])
    [h] = m.cc_immunity()(owner, "trait:Scaled@5")
    h.handler(ctx, None)
    assert owner.cc_immune is True


# --- Scaled @8: favorable weather override ----------------------------------

def test_weather_favored_uses_buff_pack_regardless_of_affinity():
    # CLEAR affinity in SNOW weather is normally neutral (IDENTITY); the override
    # forces the SNOW buff pack (armor/resistance up).
    base = _piece("champ_snowpelt_cub", 0, 0, False)
    base.affinity = WeatherState.CLEAR
    flagged = _piece("champ_snowpelt_cub", 0, 0, False)
    flagged.affinity = WeatherState.CLEAR
    flagged.weather_favored = True
    _apply_weather_to_piece(base, WeatherState.SNOW, EventBus())
    _apply_weather_to_piece(flagged, WeatherState.SNOW, EventBus())
    # Weather is now source-tagged modifiers (T.29-pre), read via stat().
    assert flagged.stat("armor") > base.stat("armor")
    assert flagged.stat("resistance") > base.stat("resistance")


# --- Spirit @8: reduced-potency echo ----------------------------------------

def test_echo_potency_scales_damage():
    attacker = _piece("champ_sunmane_lion", 0, 0, False)
    full_t = _piece("enemy_conscript", 1, 0, True)
    red_t = _piece("enemy_conscript", 1, 1, True)
    ctx = _ctx([attacker, full_t, red_t])
    full = ctx.deal_damage(attacker, full_t, 100.0, SourceTag.ABILITY)
    ctx._echo_potency = 0.6
    reduced = ctx.deal_damage(attacker, red_t, 100.0, SourceTag.ABILITY)
    assert reduced < full
    assert abs(reduced - 0.6 * full) < 1e-6
    # Restored default leaves damage full again.
    ctx._echo_potency = 1.0
    assert ctx.deal_damage(attacker, _piece("enemy_conscript", 2, 0, True), 100.0,
                           SourceTag.ABILITY) == full


# --- new mechanic builders --------------------------------------------------

def test_crit_arc_splashes_on_crit_only():
    owner = _piece("champ_sunmane_lion", 0, 0, False)
    target = _piece("enemy_conscript", 2, 0, True)
    neighbour = _piece("enemy_conscript", 2, 1, True)  # adjacent to target
    ctx = _ctx([owner, target, neighbour])
    [h] = m.crit_arc(0.5)(owner, "trait:Galvanized@10")
    before = neighbour.hp
    # Non-crit → no arc.
    h.handler(ctx, DamageEvent(attacker=owner, target=target, amount=100.0,
                               tag=SourceTag.BASIC_ATTACK.value, is_crit=False))
    assert neighbour.hp == before
    # Crit → arc to the neighbour.
    h.handler(ctx, DamageEvent(attacker=owner, target=target, amount=100.0,
                               tag=SourceTag.BASIC_ATTACK.value, is_crit=True))
    assert neighbour.hp < before


def test_chill_attackers_slows_the_attacker():
    owner = _piece("champ_snowpelt_cub", 0, 0, False)
    attacker = _piece("enemy_conscript", 1, 0, True)
    ctx = _ctx([owner, attacker])
    [h] = m.chill_attackers(200)(owner, "trait:Frostbound@10")
    h.handler(ctx, DamageEvent(attacker=attacker, target=owner, amount=10.0,
                               tag=SourceTag.BASIC_ATTACK.value))
    assert attacker.has_status("slow")
    assert not owner.has_status("slow")


def test_burst_reduction_caps_single_hit():
    owner = _piece("champ_snowpelt_cub", 0, 0, False)
    ctx = _ctx([owner])
    [h] = m.burst_reduction(0.25)(owner, "trait:Overcast@10")
    cap = 0.25 * owner.max_hp
    huge = owner.max_hp * 2
    assert h.handler(ctx, DamageEvent(attacker=None, target=owner, amount=huge,
                                      tag=SourceTag.ABILITY.value), huge) == cap
    small = cap * 0.5
    assert h.handler(ctx, DamageEvent(attacker=None, target=owner, amount=small,
                                      tag=SourceTag.ABILITY.value), small) == small


def test_kite_reward_bonus_vs_unreachable_target():
    owner = _piece("champ_goldcrest_lark", 0, 0, False)
    target = _piece("enemy_conscript", 4, 0, True)  # far away
    target.base_stats["attack_range"] = 1.0  # cannot reach back across the gap
    ctx = _ctx([owner, target])
    [h] = m.kite_reward(0.3)(owner, "trait:Skyborn@3")
    before = target.hp
    # ITEM_PROC (a follow-up) must not trigger another kite-reward (no recursion).
    h.handler(ctx, DamageEvent(attacker=owner, target=target, amount=10.0,
                               tag=SourceTag.ITEM_PROC.value))
    assert target.hp == before
    # A basic hit on an unreachable target → bonus damage.
    h.handler(ctx, DamageEvent(attacker=owner, target=target, amount=10.0,
                               tag=SourceTag.BASIC_ATTACK.value))
    assert target.hp < before


def test_ally_tidal_heals_lowest_ally():
    owner = _piece("champ_springfrog", 0, 0, False)
    hurt = _piece("champ_sunmane_lion", 0, 1, False)
    # A small absolute HP keeps `hurt` unambiguously the lowest-HP ally regardless
    # of roster stat drift (T.36b made sunmane tanky_hp, so 50%·max_hp now exceeds
    # springfrog's full HP and the heal would correctly pick the owner instead).
    hurt.hp = 10.0
    ctx = _ctx([owner, hurt])
    [h] = m.ally_tidal(interval=1, heal_frac=0.1)(owner, "trait:Tidekin@3")
    before = hurt.hp
    h.handler(ctx, None)
    assert hurt.hp > before


# --- affinity @10 structural guards -----------------------------------------

def _apex_bundle(trait_id, count=10):
    """Build the highest-rung bundle for a trait against a throwaway carrier."""
    owner = _piece("champ_sunmane_lion", 0, 0, False)
    bps = TRAIT_REGISTRY[trait_id]()
    apex = max((b for b in bps if not callable(b.count) and b.count <= count),
               key=lambda b: b.count)
    return apex.bundle_factory(owner), apex


def test_affinity_at10_riders_present():
    for trait_id in ("Galvanized", "Frostbound", "Shrouded", "Overcast"):
        bundle, apex = _apex_bundle(trait_id)
        assert apex.count == 10
        assert bundle.hooks, f"{trait_id} @10 should carry a mechanic rider"


def test_sunlit_at10_is_stat_only_with_premium():
    bundle, apex = _apex_bundle("Sunlit")
    assert apex.count == 10
    assert not bundle.hooks, "Sunlit @10 stays stat-only (no rider)"
    stats = {mod.stat for mod in bundle.modifiers}
    assert "crit_chance" in stats and "penetration_pct" in stats


def test_stormfed_at10_haste_is_stat_only():
    bundle, apex = _apex_bundle("Stormfed")
    assert apex.count == 10
    assert not bundle.hooks  # mana-haste is a stat, not a hook
    assert any(mod.stat == "mana_regen" for mod in bundle.modifiers)


# --- determinism (V.2/V.14) -------------------------------------------------

def test_t28d_trait_battle_is_deterministic():
    def make():
        team = [
            build_champion_at_level("champ_aurion", 1),       # Spirit/Primordial
            build_champion_at_level("champ_snowpelt_cub", 1),  # Guardian/Scaled-ish
            build_champion_at_level("champ_goldcrest_lark", 1),
            build_champion_at_level("champ_sunmane_lion", 1),
        ]
        enemies = [build_enemy_at_level("enemy_conscript", 1) for _ in range(4)]
        return team, enemies

    from src.game.combat.resolve import resolve_combat
    t1, e1 = make()
    t2, e2 = make()
    r1 = resolve_combat(t1, e1, WeatherState.SNOW)
    r2 = resolve_combat(t2, e2, WeatherState.SNOW)
    assert r1.to_dict() == r2.to_dict()


def test_weather_override_prepass_marks_scaled_at8():
    # Field 8 Scaled-affinity-independent carriers → Scaled @8 cleared → flagged.
    from src.game.traits import mark_weather_overrides
    scaled_ids = [d.id for d in _scaled_champions()][:8]
    assert len(scaled_ids) >= 8, "need 8 Scaled champions to field the @8 apex"
    team = [piece_from_champion(build_champion_at_level(cid, 1)) for cid in scaled_ids]
    mark_weather_overrides(team)
    assert all(p.weather_favored for p in team)


def _scaled_champions():
    from src.game.content import CHAMPION_ROSTER
    return [c for c in CHAMPION_ROSTER.values() if "Scaled" in c.traits]


# --- carrier-scope at TEAM apex (signature effects don't blanket the squad) -----

def _compile_and_start(champ_ids):
    """Compile a team, fire on_combat_start, return the player pieces."""
    from src.game.combat.context import CombatContext
    from src.game.events import CombatStartEvent
    team = [build_champion_at_level(cid, 1) for cid in champ_ids]
    enemies = [build_enemy_at_level("enemy_conscript", 1) for _ in range(2)]
    pieces, bus, _ = compile_loadout(team, enemies, WeatherState.CLEAR)
    ctx = CombatContext(pieces, bus, WeatherState.CLEAR)
    bus.fire("on_combat_start", CombatStartEvent(), ctx=ctx)
    return [p for p in pieces if not p.is_enemy]


_SCALED8 = [
    "champ_ember_salamander", "champ_aegis_tortoise", "champ_goldhide_rhino",
    "champ_riptide_caiman", "champ_frostplate_tortoise", "champ_pebbleback_pangolin",
    "champ_boulderhide_skink", "champ_voltscale_mamba",
]
_SPIRIT8 = [
    "champ_dawnwisp", "champ_mirage_caracal", "champ_lostlight_wisp",
    "champ_will_o_fawn", "champ_phantom_lynx", "champ_hollow_elk",
    "champ_wraithorn_stag", "champ_marshghast_boar",
]
_SKYBORN5 = [
    "champ_goldcrest_lark", "champ_sunspear_falcon", "champ_marsh_thrush",
    "champ_glade_heron", "champ_hoarfrost_owl",
]
_FILLER = "champ_sunmane_lion"  # Bruiser — not Scaled/Spirit/Skyborn


def test_scaled_at8_cc_immunity_is_carrier_only():
    team = _compile_and_start(_SCALED8 + [_FILLER])
    for p in team:
        if "Scaled" in p.traits:
            assert p.cc_immune, f"{p.id} (Scaled) should be CC-immune at @8"
        else:
            assert not p.cc_immune, f"{p.id} (non-carrier) must NOT get CC-immunity"


def test_spirit_at8_pierce_and_opener_are_carrier_only():
    team = _compile_and_start(_SPIRIT8 + [_FILLER])
    for p in team:
        if "Spirit" in p.traits:
            assert p.pierces_hexproof, f"{p.id} (Spirit) should pierce hexproof at @8"
            assert p.has_status("hexproof"), f"{p.id} (Spirit) should get the opener"
        else:
            assert not p.pierces_hexproof, f"{p.id} must NOT pierce hexproof"
            assert not p.has_status("hexproof"), f"{p.id} must NOT get the opener"


def test_skyborn_kiting_persists_past_at2():
    # 5 Skyborn → @5 cleared; kiting must still arm (cumulative re-include, B.16).
    team = _compile_and_start(_SKYBORN5)
    skyborn = [p for p in team if "Skyborn" in p.traits]
    assert skyborn and all(p.is_kiter for p in skyborn), "Skyborn @5 must keep kiting"
