"""Augment system tests (T.31) — offers, scopes, combat seam, quests, V.17 guard."""

from __future__ import annotations

import pytest

from src.game.augments import (
    AugmentQuality,
    AugmentScope,
    RunModifiers,
    apply_augment,
    generate_augment_offer,
    quality_weights_for_stage,
)
from src.game.combat import resolve_combat
from src.game.content import CHAMPION_ROSTER, ENEMY_ROSTER, KINSHIP_TAGS
from src.game.models import NodeState, Run, RunStatus, WeatherState
from src.game.registries import AUGMENT_REGISTRY
from src.game.route import build_route


# Importing the package populates the registry (mirrors the abilities pattern).
import src.game.augments  # noqa: E402,F401


def _team(n: int = 6):
    return list(CHAMPION_ROSTER.values())[:n]


def _enemies(n: int = 4):
    return list(ENEMY_ROSTER.values())[:n]


def _fresh_run(**kw) -> Run:
    route = build_route()
    for node in route:
        node.state = NodeState.CURRENT if node.index == 1 else NodeState.UPCOMING
    base = dict(
        run_id="t", schema_version=1, seed=7, status=RunStatus.IN_PROGRESS,
        roster=_team(), bench=[], route=route, current_node_index=1, amber=40, tempest_rank=3,
    )
    base.update(kw)
    return Run(**base)


# ---------------------------------------------------------------------------
# Registry / catalog coverage
# ---------------------------------------------------------------------------


def test_registry_populated():
    assert len(AUGMENT_REGISTRY) >= 50  # ~50 catalog + 3 Primordial unlocks


def test_all_four_qualities_present():
    qualities = {a.quality for a in AUGMENT_REGISTRY.values()}
    assert qualities == set(AugmentQuality)


def test_all_three_scopes_present():
    scopes = {a.scope for a in AUGMENT_REGISTRY.values()}
    assert scopes == set(AugmentScope)


# ---------------------------------------------------------------------------
# V.17 — every active augment + quest-tracker id resolves
# ---------------------------------------------------------------------------


def test_v17_quest_trackers_resolve():
    from src.game.augments import QUEST_TRACKER_EVENTS, QUEST_TRACKER_REGISTRY

    for aug in AUGMENT_REGISTRY.values():
        if aug.quest_tracker is not None:
            assert aug.quest_tracker in QUEST_TRACKER_REGISTRY, aug.id
            assert aug.quest_tracker in QUEST_TRACKER_EVENTS, aug.id


def test_v17_active_augments_resolve():
    # Any id a Run records must resolve (the run-side of V.17).
    run = _fresh_run()
    for aug in AUGMENT_REGISTRY.values():
        apply_augment(run, aug)
    assert all(aid in AUGMENT_REGISTRY for aid in run.active_augments)


# ---------------------------------------------------------------------------
# Offer generation — determinism, gating, dedup
# ---------------------------------------------------------------------------


def test_offer_deterministic():
    a = generate_augment_offer(11, 4, 3)
    b = generate_augment_offer(11, 4, 3)
    assert [x.id for x in a] == [x.id for x in b]
    assert len(a) == 3


def test_offer_no_duplicates():
    offer = generate_augment_offer(99, 2, 4)
    assert len({x.id for x in offer}) == len(offer)


def test_offer_excludes_active():
    offer = generate_augment_offer(5, 1, 3)
    keep = offer[0].id
    again = generate_augment_offer(5, 1, 3, exclude=(keep,))
    assert keep not in {x.id for x in again}


def test_reroll_differs():
    base = generate_augment_offer(8, 6, 4)
    rerolled = generate_augment_offer(8, 6, 4, rerolled=True)
    assert [x.id for x in base] != [x.id for x in rerolled]


def test_prismatic_gated_stage1():
    # Over many seeds, no Prismatic ever appears at stage 1.
    for seed in range(50):
        offer = generate_augment_offer(seed, 1, 1)
        assert all(x.quality is not AugmentQuality.PRISMATIC for x in offer)


def test_prismatic_appears_late():
    seen = set()
    for seed in range(80):
        for x in generate_augment_offer(seed, 5, 6):
            seen.add(x.quality)
    assert AugmentQuality.PRISMATIC in seen


def test_quality_curve_monotone_prismatic():
    # Prismatic weight is 0 at stage 1 and non-decreasing thereafter.
    weights = [quality_weights_for_stage(s)[AugmentQuality.PRISMATIC] for s in range(1, 7)]
    assert weights[0] == 0
    assert weights == sorted(weights)


# ---------------------------------------------------------------------------
# Combat seam — back-compat + scope dispatch
# ---------------------------------------------------------------------------


def test_none_run_mods_byte_identical():
    team, enemies, w = _team(), _enemies(), WeatherState.CLEAR
    a = resolve_combat(team, enemies, w)
    b = resolve_combat(team, enemies, w, run_mods=None)
    c = resolve_combat(team, enemies, w, run_mods=RunModifiers())
    assert a.to_dict() == b.to_dict() == c.to_dict()


def test_team_augment_shifts_fight():
    team, enemies, w = _team(), _enemies(), WeatherState.CLEAR
    base = resolve_combat(team, enemies, w)
    rm = RunModifiers(augments=["glass_fang"], augment_state={})
    buffed = resolve_combat(team, enemies, w, run_mods=rm)
    assert buffed.to_dict() != base.to_dict()


def test_piece_filter_applies_only_to_matches():
    # sharpshooter only buffs Hunters; a team with no Hunter is unchanged.
    team = [c for c in CHAMPION_ROSTER.values() if "Hunter" not in c.traits][:5]
    enemies, w = _enemies(), WeatherState.CLEAR
    base = resolve_combat(team, enemies, w)
    rm = RunModifiers(augments=["sharpshooter"], augment_state={})
    assert resolve_combat(team, enemies, w, run_mods=rm).to_dict() == base.to_dict()


def test_run_augment_mutates_run_not_combat():
    run = _fresh_run(amber=10)
    apply_augment(run, AUGMENT_REGISTRY["amber_vein"])
    assert run.amber == 18
    assert "amber_vein" in run.active_augments


# ---------------------------------------------------------------------------
# Crest / Worldroot — trait bonus injection
# ---------------------------------------------------------------------------


def test_worldroot_crown_bonuses_every_kinship():
    run = _fresh_run()
    apply_augment(run, AUGMENT_REGISTRY["worldroot_crown"])
    bonus = run.augment_state["trait_bonus"]
    for tag in KINSHIP_TAGS:
        assert bonus.get(tag, 0) >= 1


# ---------------------------------------------------------------------------
# Quest trackers — accumulate across combats, fire once
# ---------------------------------------------------------------------------


def test_quest_tracker_accumulates_across_combats():
    team = sorted(CHAMPION_ROSTER.values(), key=lambda c: -c.tier)[:6]
    enemies = sorted(ENEMY_ROSTER.values(), key=lambda e: e.tier)[:2]
    run = _fresh_run(roster=team, amber=0)
    apply_augment(run, AUGMENT_REGISTRY["the_uprising"])
    rm = RunModifiers.from_run(run)
    for _ in range(3):
        resolve_combat(team, enemies, WeatherState.CLEAR, run_mods=rm)
    assert run.augment_state["uprising_wins"] == 3


# ---------------------------------------------------------------------------
# Serialization round-trip + shape validation
# ---------------------------------------------------------------------------


def test_living_world_active_in_every_weather():
    # The weather-driven Prismatic shifts the fight (or at minimum applies) under
    # each of the 6 weathers — it is never inert (works on all nodes, not bosses).
    team = list(CHAMPION_ROSTER.values())[:6]
    enemies = list(ENEMY_ROSTER.values())[:6]
    rm = lambda: RunModifiers(augments=["living_world"], augment_state={})
    shifts = []
    for w in WeatherState:
        base = resolve_combat(team, enemies, w)
        lw = resolve_combat(team, enemies, w, run_mods=rm())
        shifts.append(base.to_dict() != lw.to_dict())
    # Stat/debuff weathers always shift; Mist (hexproof opener) is situational.
    assert sum(shifts) >= 5


def test_living_world_mist_grants_hexproof():
    from src.game.combat.context import CombatContext
    from src.game.events import CombatStartEvent
    from src.game.loadout import compile_loadout

    team = list(CHAMPION_ROSTER.values())[:4]
    enemies = list(ENEMY_ROSTER.values())[:4]
    rm = RunModifiers(augments=["living_world"], augment_state={})
    pieces, bus, _ = compile_loadout(team, enemies, WeatherState.MIST, run_mods=rm)
    ctx = CombatContext(pieces, bus, WeatherState.MIST, seed=42)
    bus.fire("on_combat_start", CombatStartEvent(), ctx=ctx)
    assert any(p.has_status("hexproof") for p in pieces if not p.is_enemy)


def test_run_augment_state_round_trips():
    run = _fresh_run()
    for aid in ("amber_vein", "kinship_crest", "tempest_surge", "the_long_hunt"):
        apply_augment(run, AUGMENT_REGISTRY[aid])
    restored = Run.from_dict(run.to_dict())
    assert restored.active_augments == run.active_augments
    assert restored.augment_state == run.augment_state


def test_run_rejects_blank_augment_id():
    with pytest.raises(ValueError):
        _fresh_run(active_augments=[""])


def test_run_rejects_duplicate_augment_ids():
    with pytest.raises(ValueError):
        _fresh_run(active_augments=["amber_vein", "amber_vein"])
