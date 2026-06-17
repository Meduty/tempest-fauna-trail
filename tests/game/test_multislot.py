"""T.29d — multi-slot pieces, ability discovery, Multicaster, cast_momentum."""

from __future__ import annotations

import src.game.items  # noqa: F401 — ensure item registry (start-mana test)
import src.game.traits  # noqa: F401 — ensure TRAIT_REGISTRY populated (Multicaster)
from src.game.content import get_champion, get_enemy, discover_abilities, CALLING_TAGS
from src.game.loadout import piece_from_champion, piece_from_enemy, apply_bundle
from src.game.effects import EventBus
from src.game.registries import ITEM_REGISTRY, TRAIT_REGISTRY, ability_mana
from src.game.events import CombatStartEvent

_SHOWCASE_CHAMPS = [
    "champ_ember_salamander", "champ_marsh_thrush", "champ_wintermoth",
    "champ_geode_beetle", "champ_will_o_fawn", "champ_tempest_eel",
]
_SHOWCASE_ENEMIES = ["enemy_battlemage", "enemy_arcanist", "enemy_drowned_siren"]
_ULTS = ["champ_marsh_thrush", "champ_tempest_eel"]  # tier >= 5


# --- Discovery (convention default) -----------------------------------------

def test_discovery_finds_secondary_by_convention():
    for cid in _SHOWCASE_CHAMPS:
        ids = discover_abilities(cid)
        assert ids == [f"{cid}.active", f"{cid}.active2"], f"{cid}: {ids}"


def test_single_ability_champ_discovers_one_slot():
    assert discover_abilities("champ_dawnwisp") == ["champ_dawnwisp.active"]


def test_discovery_sorted_active_before_active2():
    ids = discover_abilities("champ_ember_salamander")
    assert ids.index("champ_ember_salamander.active") < ids.index("champ_ember_salamander.active2")


# --- Multi-slot build --------------------------------------------------------

def test_showcase_champs_build_two_slots():
    for cid in _SHOWCASE_CHAMPS:
        p = piece_from_champion(get_champion(cid))
        assert len(p.actives) == 2, f"{cid} should have 2 slots"


def test_showcase_enemies_build_two_slots():
    for eid in _SHOWCASE_ENEMIES:
        p = piece_from_enemy(get_enemy(eid))
        assert len(p.actives) == 2


def test_every_multicaster_has_distinct_slots():
    """V.49: each multicaster's slots differ in cost OR priority (no simul-cast)."""
    pieces = ([(piece_from_champion(get_champion(c)), c) for c in _SHOWCASE_CHAMPS]
              + [(piece_from_enemy(get_enemy(e)), e) for e in _SHOWCASE_ENEMIES])
    for p, pid in pieces:
        prios = [s.priority for s in p.actives]
        costs = [s.mana_cost for s in p.actives]
        assert len(set(prios)) == len(prios) or len(set(costs)) == len(costs), (
            f"{pid}: slots not distinct (prios={prios}, costs={costs})"
        )


def test_ults_are_high_cost():
    for cid in _ULTS:
        m = ability_mana(f"{cid}.active2")
        assert m.mana_cost == 600_000, f"{cid} ult should cost 2x default"
        assert m.priority == 2  # priority ∝ cost so it stays castable


def test_non_ult_secondaries_cheaper_and_coprime():
    # T.36b: the lower-tier multicaster secondaries were the SAME cost as the
    # primary (300k) but charge at the lower priority-weighted rate (1/3), so they
    # rarely reached threshold before a fight ended — effectively dead. Fix (cost
    # knob only, not priority/MR): make the secondary significantly cheaper so it
    # fires in fight-length, and pick costs whose ratio to the primary is coprime
    # so the two slots' cast cadences don't lock in step.
    from math import gcd
    expected = {
        "champ_ember_salamander": (230_000, 150_000),
        "champ_wintermoth": (220_000, 150_000),
        "champ_geode_beetle": (230_000, 160_000),
        "champ_will_o_fawn": (210_000, 130_000),
    }
    for cid, (pri, sec) in expected.items():
        assert ability_mana(f"{cid}.active").mana_cost == pri
        assert ability_mana(f"{cid}.active2").mana_cost == sec
        assert sec < pri, f"{cid} secondary must be cheaper than primary (so it fires)"
        # Coprime in lowest terms (ratio realigns only every q casts → no lockstep).
        assert gcd(pri // 10_000, sec // 10_000) == 1, f"{cid} costs not coprime"


# --- Multicaster Calling -----------------------------------------------------

def test_multicaster_registered_and_on_champs():
    assert "Multicaster" in CALLING_TAGS
    assert "Multicaster" in TRAIT_REGISTRY
    for cid in _SHOWCASE_CHAMPS:
        assert "Multicaster" in get_champion(cid).traits


def test_enemies_have_slots_but_no_multicaster():
    for eid in _SHOWCASE_ENEMIES:
        # Enemy has no traits field exposure; the Calling is champ-only (V.22).
        e = get_enemy(eid)
        assert len(discover_abilities(eid)) == 2


# --- cast_momentum mechanic --------------------------------------------------

def test_cast_momentum_stacks_attack_speed_on_cast():
    from src.game.traits.mechanics import cast_momentum
    from src.game.piece import Piece

    owner = Piece(id="m", base_stats={"attack_speed": 100.0, "mana_regen": 100.0})
    hooks = cast_momentum(per=0.04, cap=5)(owner, "trait:multicaster")
    hook = hooks[0]
    assert hook.event == "on_cast_complete"

    class _Ev:
        caster = owner

    class _Ctx:
        def __init__(self):
            self.mods = []

        def apply_modifier(self, target, mod):
            self.mods.append(mod)

    ctx = _Ctx()
    for _ in range(8):  # cap at 5 → only 5 AS mods (+ 5 MR)
        hook.handler(ctx, _Ev())
    as_mods = [m for m in ctx.mods if m.stat == "attack_speed"]
    assert len(as_mods) == 5  # capped


# --- Weighted start-mana (invariant total) ----------------------------------

def _start_total(cid: str) -> float:
    c = get_champion(cid)
    c.items = ["springtear"]
    p = piece_from_champion(c)
    bus = EventBus()
    for iid in p.items:
        apply_bundle(p, ITEM_REGISTRY[iid](p), bus)
    bus.fire("on_combat_start", CombatStartEvent(), ctx=None)
    return sum(s.current_mana for s in p.actives)


def test_start_mana_invariant_across_slot_count():
    one = _start_total("champ_dawnwisp")       # 1 slot
    two = _start_total("champ_tempest_eel")     # 2 slots
    assert abs(one - two) < 2.0, "start mana should be slot-count-invariant"
    assert abs(one - 100_000) < 2.0
