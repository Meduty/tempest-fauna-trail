"""T.28a — trait framework, resolution, roster reconciliation, V-guard.

Covers the declarative half: counting (V.21), scope, affinity synthesis,
dynamic thresholds (Packmate @full-board), HP re-sync, vocabulary, and the
V.22 roster guard. Mechanic primitives (kiting/revive/…) are T.28b/c.
"""

import pytest

from src.game.content import (
    CALLING_TAGS,
    CHAMPION_DEF_BY_ID,
    KINSHIP_TAGS,
    build_champion_at_level,
)
from src.game.loadout import compile_loadout
from src.game.models import BattleResult, CombatOutcome, WeatherState
from src.game.registries import TRAIT_REGISTRY
from src.game.traits import TraitScope, _resolve_traits, affinity_trait
from src.game.piece import Piece


def _team(*ids):
    return [build_champion_at_level(cid, 1) for cid in ids]


def _pieces(team, weather=WeatherState.CLEAR):
    pieces, _bus, acts = compile_loadout(team, [], weather, seed=42)
    return pieces, acts


# --------------------------------------------------------------------------
# Registration + vocabulary
# --------------------------------------------------------------------------
def test_all_25_traits_registered():
    # T.29d added the Multicaster Calling (12 → 13 callings; 24 → 25 traits).
    expected = KINSHIP_TAGS | CALLING_TAGS | {
        "Sunlit", "Overcast", "Shrouded", "Stormfed", "Frostbound", "Galvanized",
    }
    assert expected <= set(TRAIT_REGISTRY)
    assert len(TRAIT_REGISTRY) == 25


def test_calling_vocab_is_the_thirteen_catalog_callings():
    # B.9: 4 dead T.5 tags dropped, Packmate added. T.29d: +Multicaster.
    assert CALLING_TAGS == frozenset({
        "Hunter", "Guardian", "Mystic", "Warden", "Stalker", "Bruiser",
        "Skirmisher", "Channeler", "Mender", "Trickster", "Packmate", "Primordial",
        "Multicaster",
    })
    for dead in ("Bulwark", "Drifter", "Harbinger", "Emissary"):
        assert dead not in CALLING_TAGS


# --------------------------------------------------------------------------
# V.22 roster guard
# --------------------------------------------------------------------------
def test_every_champion_tag_resolves_and_has_kinship_and_calling():
    for cid, d in CHAMPION_DEF_BY_ID.items():
        kin = [t for t in d.traits if t in KINSHIP_TAGS]
        call = [t for t in d.traits if t in CALLING_TAGS]
        assert len(kin) >= 1, f"{cid}: needs >=1 Kinship"
        assert len(call) >= 1, f"{cid}: needs >=1 Calling"
        for tag in d.traits:
            assert tag in TRAIT_REGISTRY, f"{cid}: tag {tag} not in TRAIT_REGISTRY"
        if d.tier == 10:
            assert "Primordial" in d.traits


def test_exactly_one_tier10_primordial_per_kinship():
    by_kin = {}
    for d in CHAMPION_DEF_BY_ID.values():
        if d.tier != 10:
            continue
        kin = [t for t in d.traits if t in KINSHIP_TAGS]
        assert len(kin) == 1, f"{d.id}: T10 must have exactly one kinship"
        by_kin.setdefault(kin[0], []).append(d.id)
    assert set(by_kin) == KINSHIP_TAGS, "every kinship needs a T10 anchor"
    assert all(len(v) == 1 for v in by_kin.values()), "exactly one T10 per kinship"


def test_packmate_has_carriers():
    carriers = [d.id for d in CHAMPION_DEF_BY_ID.values() if "Packmate" in d.traits]
    assert len(carriers) >= 8
    assert all(CHAMPION_DEF_BY_ID[c].tier <= 3 for c in carriers), "Packmate = cheap T1-3"


# --------------------------------------------------------------------------
# Counting (V.21)
# --------------------------------------------------------------------------
def test_counts_unique_champion_ids_not_copies():
    # Two copies of one Beast champion count once.
    champ = build_champion_at_level("champ_sunmane_lion", 1)  # Beast Bruiser
    cleared = _resolve_traits([_p(champ), _p(champ)], board_cap=2)
    # Beast needs @2 — only 1 unique id, so Beast not cleared.
    assert "Beast" not in cleared


def _p(champion) -> Piece:
    from src.game.loadout import piece_from_champion
    return piece_from_champion(champion)


def test_highest_cleared_breakpoint_wins():
    # 4 Clear champions → Sunlit @4 (not @2).
    team = _team(
        "champ_dawnwisp", "champ_veldt_pronghorn",
        "champ_ember_salamander", "champ_goldcrest_lark",
    )
    pieces = [_p(c) for c in team]
    cleared = _resolve_traits(pieces, board_cap=4)
    assert "Sunlit" in cleared
    _bp, count, thr = cleared["Sunlit"]
    assert count == 4 and thr == 4


# --------------------------------------------------------------------------
# Scope + enemies never light up
# --------------------------------------------------------------------------
def test_enemies_never_light_up():
    from src.game.content import build_enemy_at_level
    enemies = [build_enemy_at_level("enemy_conscript", 1) for _ in range(4)]
    _pieces_, _bus, acts = compile_loadout([], enemies, WeatherState.CLEAR, seed=42)
    assert acts == []


def test_per_trait_piece_scope_hits_only_carriers():
    # 2 Bruisers (Beast Bruiser) + 1 non-Bruiser of same affinity.
    team = _team("champ_sunmane_lion", "champ_thunderclap_gorilla", "champ_dawnwisp")
    pieces, _acts = _pieces(team)
    bruisers = [p for p in pieces if "Bruiser" in p.traits]
    non = [p for p in pieces if "Bruiser" not in p.traits]
    # Bruiser @2 is PER_TRAIT_PIECE +hp; carriers get an hp modifier, non-carrier doesn't.
    def has_bruiser_mod(p):
        return any(m.source_id.startswith("trait:Bruiser@") for m in p.modifiers)
    assert all(has_bruiser_mod(p) for p in bruisers)
    assert not any(has_bruiser_mod(p) for p in non)


# --------------------------------------------------------------------------
# Affinity synthesis — weather-independent
# --------------------------------------------------------------------------
def test_affinity_trait_count_is_weather_independent():
    team = _team(
        "champ_dawnwisp", "champ_veldt_pronghorn", "champ_ember_salamander",
    )  # 3 Clear → Sunlit @2
    _p1, acts_clear = _pieces(team, WeatherState.CLEAR)
    _p2, acts_snow = _pieces(team, WeatherState.SNOW)
    sun_clear = [a for a in acts_clear if a[0] == "Sunlit"]
    sun_snow = [a for a in acts_snow if a[0] == "Sunlit"]
    assert sun_clear == sun_snow == [("Sunlit", 3, 2)]


def test_affinity_trait_mapping():
    assert affinity_trait(WeatherState.CLEAR) == "Sunlit"
    assert affinity_trait(WeatherState.THUNDER) == "Galvanized"


# --------------------------------------------------------------------------
# Dynamic threshold — Packmate @full-board
# --------------------------------------------------------------------------
def test_packmate_full_board_dynamic_threshold():
    # 5 Packmate champions, board cap 5 → @full-board (==5) beats fixed @4.
    team = _team(
        "champ_veldt_pronghorn", "champ_springfrog", "champ_snowpelt_cub",
        "champ_pebbleback_pangolin", "champ_sparkfly",
    )
    pieces = [_p(c) for c in team]
    cleared = _resolve_traits(pieces, board_cap=len(pieces))
    assert "Packmate" in cleared
    _bp, count, thr = cleared["Packmate"]
    assert count == 5 and thr == 5  # dynamic full-board, not the fixed @4


# --------------------------------------------------------------------------
# HP re-sync — hp-mul trait modifiers bite the cached max_hp
# --------------------------------------------------------------------------
def test_hp_modifier_raises_max_hp():
    base = build_champion_at_level("champ_sunmane_lion", 1).max_hp
    # 2 Bruisers (Beast Bruiser) → Beast @2 +hp and Bruiser @2 +hp.
    team = _team("champ_sunmane_lion", "champ_thunderclap_gorilla")
    pieces, _acts = _pieces(team)
    lion = next(p for p in pieces if p.id == "champ_sunmane_lion")
    assert lion.max_hp > base
    assert lion.hp == lion.max_hp  # starts full


# --------------------------------------------------------------------------
# Determinism + BattleResult record
# --------------------------------------------------------------------------
def test_resolution_is_deterministic():
    team = _team("champ_sunmane_lion", "champ_thunderclap_gorilla", "champ_dawnwisp")
    a = _pieces(team)[1]
    b = _pieces(team)[1]
    assert a == b


def test_trait_activations_on_battle_result_roundtrip():
    br = BattleResult(
        node_id="n", weather=WeatherState.CLEAR, outcome=CombatOutcome.WIN,
        rounds=1, turns=1, duration_ticks=10,
        team_damage_dealt={}, team_damage_taken={},
        surviving_team_ids=[], surviving_enemy_ids=[],
        trait_activations=[("Beast", 4, 4), ("Sunlit", 3, 2)],
    )
    loaded = BattleResult.from_dict(br.to_dict())
    assert loaded.trait_activations == [("Beast", 4, 4), ("Sunlit", 3, 2)]
    assert loaded.to_dict() == br.to_dict()


# --- V.41: cumulative rungs ------------------------------------------------

# Owner flags a trait rider may arm at combat start; surfaced in the signature.
_RIDER_FLAGS = ("is_kiter", "seeks_backline", "cc_immune", "pierces_hexproof",
                "ability_can_crit")
# Carrier-MOVEMENT may legitimately drop at a TEAM_WIDE apex (the documented
# exception — applying kiting/backline team-wide would make every ally kite/seek).
_MOVEMENT_FLAGS = {"flag:is_kiter", "flag:seeks_backline"}


class _RecCtx:
    """Records the observable effects an on_combat_start rider produces."""
    def __init__(self):
        self.current_tick = 0
        self.statuses: list[str] = []
        self.barriers: list[float] = []

    def apply_status(self, target, status_id, duration, **kw):
        self.statuses.append(status_id)

    def grant_barrier(self, target, amount, duration_ticks=0):
        self.barriers.append(amount)

    def apply_modifier(self, target, modifier):
        pass


def _rung_signature(trait_id, bp):
    """A set of mechanic 'fingerprints' a rung grants a CARRIER: non-combat-start
    hook events (`hook:<event>`), plus on_combat_start effects (`flag:*`,
    `status:*`, `barrier`). Probed as a carrier so trait-guarded signatures count."""
    from src.game.events import CombatStartEvent
    from src.game.loadout import piece_from_champion

    owner = piece_from_champion(build_champion_at_level("champ_sunmane_lion", 1))
    owner.traits = [trait_id]
    owner.hp = owner.max_hp
    bundle = bp.bundle_factory(owner)
    rec = _RecCtx()
    sig: set[str] = set()
    for hook in bundle.hooks:
        if hook.event == "on_combat_start":
            hook.handler(rec, CombatStartEvent())
        else:
            sig.add(f"hook:{hook.event}")
    for flag in _RIDER_FLAGS:
        if getattr(owner, flag):
            sig.add(f"flag:{flag}")
    for sid in rec.statuses:
        sig.add(f"status:{sid}")
    if rec.barriers:
        sig.add("barrier")
    return sig


def test_trait_rungs_are_cumulative_for_mechanics():
    """V.41 — a higher rung re-includes every mechanic a lower cleared rung grants
    (resolution applies only the single highest cleared rung, so re-inclusion is
    manual). Sole exception: carrier-MOVEMENT (kiting/backline) may drop at a
    TEAM_WIDE apex. Catches the silent-drop bug class (B.15-adjacent, B.16)."""
    for trait_id, factory in TRAIT_REGISTRY.items():
        rungs = sorted(
            factory(),
            key=lambda b: b.count if not callable(b.count) else 10_000,
        )
        for lo, hi in zip(rungs, rungs[1:]):
            sig_lo = _rung_signature(trait_id, lo)
            sig_hi = _rung_signature(trait_id, hi)
            allowed = _MOVEMENT_FLAGS if hi.scope is TraitScope.TEAM_WIDE else set()
            dropped = sig_lo - sig_hi - allowed
            assert not dropped, (
                f"{trait_id}: rung {hi.count} drops {sorted(dropped)} present at the "
                f"lower rung {lo.count} (cumulative-rung violation, V.41)"
            )
