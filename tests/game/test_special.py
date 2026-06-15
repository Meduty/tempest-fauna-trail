"""T.29b — emblems + special run-actions + heartwood (Glimmerdust)."""

from __future__ import annotations

from src.game.models import Run, RunStatus, NodeState
from src.game.route import build_route
from src.game.content import get_champion
from src.game.registries import ITEM_REGISTRY, RUN_ACTION_REGISTRY
from src.game.items import combine
from src.game.items.special import HEARTWOOD_PREFIX, decompose


def _run(**inv) -> Run:
    route = build_route()
    for node in route:
        node.state = NodeState.CURRENT if node.index == 1 else NodeState.UPCOMING
    return Run(
        run_id="r", schema_version=1, seed=42, status=RunStatus.IN_PROGRESS,
        roster=[], bench=[], route=route, current_node_index=1,
        inventory=dict(inv),
    )


# --- Emblems -----------------------------------------------------------------

def test_six_emblems_registered_and_grant_kinship():
    from src.game.loadout import piece_from_champion, apply_bundle
    from src.game.effects import EventBus
    pairs = {
        "beast_emblem": "Beast", "skyborn_emblem": "Skyborn", "scaled_emblem": "Scaled",
        "tidekin_emblem": "Tidekin", "swarm_emblem": "Swarm", "spirit_emblem": "Spirit",
    }
    for emblem, kinship in pairs.items():
        assert emblem in ITEM_REGISTRY
        p = piece_from_champion(get_champion("champ_veldt_pronghorn"))  # not Spirit-native
        apply_bundle(p, ITEM_REGISTRY[emblem](p), EventBus())
        assert kinship in p.traits


def test_gem_branch_crafts_emblems():
    assert combine("spirit_gem", "fang") == "beast_emblem"
    assert combine("spirit_gem", "heartseed") == "spirit_emblem"
    assert combine("spirit_gem", "keen_claw") is None  # unmapped component


# --- decompose ---------------------------------------------------------------

def test_decompose():
    assert decompose("fang") == ["fang"]
    assert sorted(decompose("huntress_talon")) == ["fang", "talon"]
    assert decompose("beast_emblem") == ["spirit_gem", "fang"]
    assert sorted(decompose(HEARTWOOD_PREFIX + "huntress_talon")) == ["fang", "talon"]


# --- Run actions -------------------------------------------------------------

def test_reforger_recombines():
    run = _run(huntress_talon=1)
    RUN_ACTION_REGISTRY["reforger"](run, "huntress_talon")
    assert run.inventory.get("huntress_talon", 0) == 0
    assert sum(run.inventory.values()) == 1  # one new combined item exists


def test_unbinding_totem_strips_to_components():
    champ = get_champion("champ_dawnwisp")
    champ.items = ["huntress_talon", "fang"]
    run = _run()
    run.roster = [champ]
    RUN_ACTION_REGISTRY["unbinding_totem"](run, champ.id)
    assert champ.items == []
    assert run.inventory["fang"] == 2  # 1 from huntress_talon + 1 raw
    assert run.inventory["talon"] == 1


def test_echo_acorn_adds_bench_copy():
    run = _run()
    RUN_ACTION_REGISTRY["echo_acorn"](run, "champ_dawnwisp")
    assert len(run.bench) == 1 and run.bench[0].id == "champ_dawnwisp"
    assert run.champion_copies["champ_dawnwisp"] == 1


def test_glimmerdust_upgrades_to_heartwood():
    run = _run(apex_fang=1)
    RUN_ACTION_REGISTRY["glimmerdust"](run, "apex_fang")
    assert run.inventory.get("apex_fang", 0) == 0
    assert run.inventory[HEARTWOOD_PREFIX + "apex_fang"] == 1
    # raw components / already-heartwood are no-ops
    run2 = _run(fang=1)
    RUN_ACTION_REGISTRY["glimmerdust"](run2, "fang")
    assert run2.inventory["fang"] == 1


def test_reclaimers_cache_salvages_to_amber():
    run = _run(fang=2, talon=1)
    RUN_ACTION_REGISTRY["reclaimers_cache"](run, ["fang", "fang", "talon"])
    assert run.amber == 30  # 3 components × 10
    assert "fang" not in run.inventory and "talon" not in run.inventory


# --- Heartwood combat scaling (D.21 MVP) -------------------------------------

def test_heartwood_scales_modifiers_x15():
    from src.game.loadout import piece_from_champion, _heartwood_scale
    piece = piece_from_champion(get_champion("champ_veldt_pronghorn"))
    bundle = ITEM_REGISTRY["worldroot_bloom"](piece)   # +30% INT (mul 1.30)
    scaled = _heartwood_scale(bundle)
    # base mul 1.30 → heartwood 1 + 0.30*1.5 = 1.45
    assert any(abs(m.value - 1.45) < 1e-9 for m in scaled.modifiers)
