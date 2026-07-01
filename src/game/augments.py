"""Augment system (T.31) — effect_systems_design.md §9 + augment_catalog.md.

Run-long, game-changing modifiers picked 1-of-3 at each `AUGMENT` node. Three
scopes share one registry (`AUGMENT_REGISTRY`):

| Scope | Handler signature          | Effect                                            |
|-------|----------------------------|---------------------------------------------------|
| TEAM  | `(team, state) -> Bundle`  | modifiers→each team piece; hooks subscribed once  |
| PIECE | `(piece, state) -> Bundle` | bundle applied to each team piece passing filter  |
| RUN   | `(run) -> None`            | mutates `Run` at pick time, no combat bundle      |

`state` is the mutable `RunModifiers.augment_state` dict (quest progress + RUN
flags) — passed to every TEAM/PIECE handler so run-scaling augments (The Uprising)
and crest bonuses can read accumulated state. TEAM/PIECE handlers close over the
*live* combat `team` list, so their hooks need no side-inspection (V.18: rebuilt
fresh each combat, never persisted).

All handlers are RNG-free and deterministic (V.2/V.14). `Modifier.source_id` uses
the `augment:<id>` prefix (V.45). Stat magnitudes are MVP picks (catalog ships
*concepts only*); they are a balance-tuning surface (D.11), expressed as `mul`
where they must scale across the 10-tier stat spread (FORMAT.md).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

from src.game.effects import (
    EffectBundle,
    Hook,
    HookScope,
    Lifetime,
    Modifier,
    SourceTag,
)
from src.game.encounter import augment_seed
from src.game.items.base import BASE_COMPONENTS
from src.game.models import WeatherState
from src.game.registries import AUGMENT_REGISTRY
from src.game.rng import SeededRng
from src.game.weather_effects import (
    WEATHER_BUFF_BASE,
    RingRelation,
    combat_modifier,
    ring_relation,
)

if TYPE_CHECKING:
    from src.game.models import Run


# ---------------------------------------------------------------------------
# Scope / quality enums + the Augment record
# ---------------------------------------------------------------------------


class AugmentScope(Enum):
    PIECE = "piece"
    TEAM = "team"
    RUN = "run"


class AugmentQuality(Enum):
    COMMON = "common"
    RARE = "rare"
    EPIC = "epic"
    PRISMATIC = "prismatic"


@dataclass(frozen=True)
class Augment:
    id: str
    name: str
    scope: AugmentScope
    quality: AugmentQuality
    handler: Callable
    piece_filter: Callable[[Any], bool] | None = None  # PIECE only
    quest_tracker: str | None = None
    blurb: str = ""


# ---------------------------------------------------------------------------
# Quest-tracker registry (Run-level subscribers; §9.3)
# ---------------------------------------------------------------------------

# id -> tracker(run, event_name, event) -> None
QUEST_TRACKER_REGISTRY: dict[str, Callable] = {}
# id -> list of event names the tracker subscribes to
QUEST_TRACKER_EVENTS: dict[str, list[str]] = {}


def register_quest_tracker(tracker_id: str, *, events: list[str]) -> Callable:
    """Register a Run-level quest tracker + its subscribed event set (§9.3)."""

    def decorator(fn: Callable) -> Callable:
        QUEST_TRACKER_REGISTRY[tracker_id] = fn
        QUEST_TRACKER_EVENTS[tracker_id] = list(events)
        return fn

    return decorator


def register_augment(
    augment_id: str,
    *,
    name: str,
    scope: AugmentScope,
    quality: AugmentQuality,
    piece_filter: Callable[[Any], bool] | None = None,
    quest_tracker: str | None = None,
    blurb: str = "",
) -> Callable:
    """Decorator: register an augment handler into `AUGMENT_REGISTRY`."""

    def decorator(fn: Callable) -> Augment:
        aug = Augment(
            id=augment_id,
            name=name,
            scope=scope,
            quality=quality,
            handler=fn,
            piece_filter=piece_filter,
            quest_tracker=quest_tracker,
            blurb=blurb,
        )
        AUGMENT_REGISTRY[augment_id] = aug
        return aug

    return decorator


# ---------------------------------------------------------------------------
# RunModifiers — the optional combat seam (V.2 amendment)
# ---------------------------------------------------------------------------


@dataclass
class RunModifiers:
    """Active augment ids + mutable quest/flag state, threaded into combat.

    `None` default on `resolve_combat`/`compile_loadout` ⇒ all non-augment
    callers (every balance sim) stay byte-for-byte identical (V.2). `augment_state`
    is shared by reference with `Run.augment_state` so quest trackers writing here
    persist across combats.
    """

    augments: list[str] = field(default_factory=list)
    augment_state: dict[str, Any] = field(default_factory=dict)
    # Optional back-ref to the live Run, set by the walker (sim_run) so quest
    # trackers can mutate persistent Run state (amber/inventory). Pure sims leave
    # it None ⇒ trackers are not wired (deterministic, back-compat).
    run: Any = None

    @classmethod
    def from_run(cls, run: Run) -> RunModifiers:
        return cls(augments=list(run.active_augments), augment_state=run.augment_state, run=run)


# ---------------------------------------------------------------------------
# Small authoring helpers
# ---------------------------------------------------------------------------

_PREDATOR_RELATIONS = (RingRelation.PRIMARY_PREDATOR, RingRelation.SECONDARY_PREDATOR)
_PREY_RELATIONS = (RingRelation.PRIMARY_PREY, RingRelation.SECONDARY_PREY)


def _mods(aug_id: str, *, lifetime: Lifetime = Lifetime.COMBAT, expires: int | None = None, **stat_ops: Any) -> list[Modifier]:
    """Build `Modifier`s from ``stat=("op", value)`` kwargs, tagged ``augment:<id>``."""
    src = f"augment:{aug_id}"
    out: list[Modifier] = []
    for stat, (op, value) in stat_ops.items():
        out.append(Modifier(stat, op, float(value), lifetime, src, expires))
    return out


def _team_set(team: list[Any]) -> set[int]:
    return {id(p) for p in team}


def _stat_pack(aug_id: str, **muls: float) -> Callable:
    """A TEAM handler that grants flat ``mul`` stat modifiers to the whole team."""

    def handler(team: list[Any], state: dict[str, Any]) -> EffectBundle:
        return EffectBundle(modifiers=_mods(aug_id, **{k: ("mul", v) for k, v in muls.items()}))

    return handler


# ===========================================================================
# 1. COMMON — stat packs + small economy (legible filler)
# ===========================================================================

register_augment("thicker_hides", name="Thicker Hides", scope=AugmentScope.TEAM,
                 quality=AugmentQuality.COMMON, blurb="Allies gain Health.")(
    _stat_pack("thicker_hides", hp=1.18))

register_augment("sharpened_fangs", name="Sharpened Fangs", scope=AugmentScope.TEAM,
                 quality=AugmentQuality.COMMON, blurb="Allies gain Strength.")(
    _stat_pack("sharpened_fangs", strength=1.18))

register_augment("quick_wits", name="Quick Wits", scope=AugmentScope.TEAM,
                 quality=AugmentQuality.COMMON, blurb="Allies gain Intelligence.")(
    _stat_pack("quick_wits", intelligence=1.18))

register_augment("fleetfoot", name="Fleetfoot", scope=AugmentScope.TEAM,
                 quality=AugmentQuality.COMMON, blurb="Allies gain Move Speed.")(
    _stat_pack("fleetfoot", move_speed=1.15))

register_augment("pack_instinct", name="Pack Instinct", scope=AugmentScope.TEAM,
                 quality=AugmentQuality.COMMON, blurb="Allies gain a little of every combat stat.")(
    _stat_pack("pack_instinct", hp=1.07, strength=1.07, intelligence=1.07,
               attack_speed=1.07, armor=1.07, resistance=1.07))


@register_augment("second_wind", name="Second Wind", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.COMMON, blurb="Allies regenerate Health each round.")
def second_wind(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    """HoT: every 100 ticks ('round') heal 2% max HP. Global on_tick over `team`."""
    members = list(team)

    def hook(ctx: Any, event: Any) -> None:
        if event.tick % 100 != 0 or event.tick == 0:
            return
        for p in members:
            if ctx.is_alive(p):
                ctx.heal(p, p, 0.02 * p.max_hp)

    return EffectBundle(hooks=[Hook("on_tick", hook, scope=HookScope.PER_HIT)])


@register_augment("opening_howl", name="Opening Howl", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.COMMON, blurb="Allies gain Attack Speed for the first round (600 ticks).")
def opening_howl(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    return EffectBundle(modifiers=_mods("opening_howl", lifetime=Lifetime.TIMED, expires=600,
                                        attack_speed=("mul", 1.30)))


@register_augment("trail_rations", name="Trail Rations", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.COMMON, blurb="Allies cast sooner each fight (mana regen).")
def trail_rations(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    # NOTE (D1): catalog says "start each fight with partial mana"; modelled as a
    # mana-regen buff (start_mana is per-ActiveSlot, not a bundle stat). Reclassified
    # RUN→TEAM since it is a run-long *combat* buff (V.18 semantics), not a Run mutation.
    return EffectBundle(modifiers=_mods("trail_rations", mana_regen=("mul", 1.30)))


@register_augment("forage", name="Forage", scope=AugmentScope.RUN,
                  quality=AugmentQuality.COMMON, blurb="Gain two random base components.")
def forage(run: Run) -> None:
    rng = SeededRng(_run_action_seed(run, "forage"))
    comps = sorted(BASE_COMPONENTS)
    for _ in range(2):
        c = comps[rng.randint(0, len(comps) - 1)]
        run.inventory[c] = run.inventory.get(c, 0) + 1


@register_augment("amber_vein", name="Amber Vein", scope=AugmentScope.RUN,
                  quality=AugmentQuality.COMMON, blurb="Immediately gain Amber.")
def amber_vein(run: Run) -> None:
    run.amber += 8


@register_augment("scouts_pay", name="Scout's Pay", scope=AugmentScope.RUN,
                  quality=AugmentQuality.COMMON, quest_tracker="scouts_pay_progress",
                  blurb="Gain bonus Amber after each of the next several fights.")
def scouts_pay(run: Run) -> None:
    run.augment_state.setdefault("scouts_pay", {"fights": 5})


@register_quest_tracker("scouts_pay_progress", events=["on_combat_end"])
def scouts_pay_progress(run: Run, event_name: str, event: Any, ctx: Any = None) -> None:
    st = run.augment_state.get("scouts_pay")
    if not st or st["fights"] <= 0:
        return
    if getattr(event, "winner", None) == "team":
        st["fights"] -= 1
        run.amber += 4


@register_augment("salvage_rights", name="Salvage Rights", scope=AugmentScope.RUN,
                  quality=AugmentQuality.COMMON, blurb="Selling a champion recovers extra Amber.")
def salvage_rights(run: Run) -> None:
    # Flag consumed by the T.22 sell path (economy.py). MVP: stores the bonus.
    run.augment_state["salvage_bonus"] = run.augment_state.get("salvage_bonus", 0) + 2


@register_augment("prospector", name="Prospector", scope=AugmentScope.RUN,
                  quality=AugmentQuality.COMMON, quest_tracker="prospector_progress",
                  blurb="Bank a target amount of Amber at once → free component.")
def prospector(run: Run) -> None:
    run.augment_state.setdefault("prospector", {"target": 30, "done": False})


@register_quest_tracker("prospector_progress", events=["on_combat_end"])
def prospector_progress(run: Run, event_name: str, event: Any, ctx: Any = None) -> None:
    st = run.augment_state.get("prospector")
    if not st or st["done"]:
        return
    if run.amber >= st["target"]:
        run.inventory["fang"] = run.inventory.get("fang", 0) + 1  # free component payout
        st["done"] = True


# ===========================================================================
# 2. RARE — weather payoffs, light trait support, build-shapers
# ===========================================================================


@register_augment("stormchasers_pact", name="Stormchaser's Pact", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.RARE, blurb="Allies that hunt the live weather deal bonus damage.")
def stormchasers_pact(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    members = _team_set(team)

    def hook(ctx: Any, event: Any, value: float) -> float:
        atk = event.attacker
        if atk is None or id(atk) not in members:
            return value
        if ring_relation(atk.affinity, ctx.weather) in _PREDATOR_RELATIONS:
            return value * 1.20
        return value

    return EffectBundle(hooks=[Hook("on_damage_pre", hook, priority=30, scope=HookScope.PER_HIT)])


@register_augment("stubborn_roots", name="Stubborn Roots", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.RARE, blurb="Prey allies ignore the Weather Favor debuff.")
def stubborn_roots(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    members = list(team)

    def hook(ctx: Any, event: Any) -> None:
        for p in members:
            if ring_relation(p.affinity, ctx.weather) not in _PREY_RELATIONS:
                continue
            mod = combat_modifier(p.affinity, ctx.weather)
            # Cancel each debuff mul (<1) with its exact inverse.
            for stat, mult in (
                ("hp", mod.hp_mult), ("strength", mod.str_mult), ("intelligence", mod.int_mult),
                ("attack_speed", mod.as_mult), ("move_speed", mod.ms_mult), ("mana_regen", mod.mr_mult),
                ("threat", mod.thr_mult), ("armor", mod.armor_mult), ("resistance", mod.res_mult),
            ):
                if mult < 1.0 and mult != 0.0:
                    ctx.apply_modifier(p, Modifier(stat, "mul", 1.0 / mult, Lifetime.COMBAT, "augment:stubborn_roots"))

    return EffectBundle(hooks=[Hook("on_combat_start", hook, scope=HookScope.PER_HIT)])


@register_augment("slow_burn", name="Slow Burn", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.RARE, blurb="Allies gain stacking power the longer they survive.")
def slow_burn(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    members = list(team)

    def hook(ctx: Any, event: Any) -> None:
        if event.tick % 200 != 0 or event.tick == 0:
            return
        for p in members:
            if ctx.is_alive(p):
                ctx.apply_modifier(p, Modifier("strength", "mul", 1.04, Lifetime.COMBAT, "augment:slow_burn"))
                ctx.apply_modifier(p, Modifier("intelligence", "mul", 1.04, Lifetime.COMBAT, "augment:slow_burn"))

    return EffectBundle(hooks=[Hook("on_tick", hook, scope=HookScope.PER_HIT)])


@register_augment("adrenal_glands", name="Adrenal Glands", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.RARE, blurb="Each ally's first cast each combat is empowered.")
def adrenal_glands(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    # D1 simplification: a timed opening INT/STR steroid (≈ "first cast empowered")
    # rather than per-cast amplification, which would need a generic cast-damage hook.
    return EffectBundle(modifiers=_mods("adrenal_glands", lifetime=Lifetime.TIMED, expires=400,
                                        strength=("mul", 1.18), intelligence=("mul", 1.18)))


register_augment("glass_fang", name="Glass Fang", scope=AugmentScope.TEAM,
                 quality=AugmentQuality.RARE, blurb="Big Strength and Intelligence, less Health.")(
    _stat_pack("glass_fang", strength=1.30, intelligence=1.30, hp=0.80))


@register_augment("first_blood", name="First Blood", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.RARE, blurb="The first enemy your team kills grants a power surge.")
def first_blood(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    members = list(team)
    fired = {"done": False}

    def hook(ctx: Any, event: Any) -> None:
        if fired["done"]:
            return
        killer = event.killer
        if killer is None or id(killer) not in {id(p) for p in members}:
            return
        fired["done"] = True
        for p in members:
            if ctx.is_alive(p):
                ctx.apply_modifier(p, Modifier("strength", "mul", 1.15, Lifetime.TIMED, "augment:first_blood", (ctx.current_tick + 400)))
                ctx.apply_modifier(p, Modifier("intelligence", "mul", 1.15, Lifetime.TIMED, "augment:first_blood", (ctx.current_tick + 400)))

    return EffectBundle(hooks=[Hook("on_kill", hook, scope=HookScope.PER_HIT)])


@register_augment("kinship_crest", name="Kinship Crest", scope=AugmentScope.RUN,
                  quality=AugmentQuality.RARE, blurb="Your board counts as +1 toward a chosen Kinship.")
def kinship_crest(run: Run) -> None:
    _add_trait_bonus(run, _dominant_kinship(run), 1)


@register_augment("calling_crest", name="Calling Crest", scope=AugmentScope.RUN,
                  quality=AugmentQuality.RARE, blurb="Your board counts as +1 toward a chosen Calling.")
def calling_crest(run: Run) -> None:
    _add_trait_bonus(run, _dominant_calling(run), 1)


@register_augment("sharpshooter", name="Sharpshooter", scope=AugmentScope.PIECE,
                  quality=AugmentQuality.RARE, piece_filter=lambda p: "Hunter" in p.traits,
                  blurb="Hunter allies gain Attack Range.")
def sharpshooter(piece: Any, state: dict[str, Any]) -> EffectBundle:
    return EffectBundle(modifiers=_mods("sharpshooter", attack_range=("add", 1.0)))


@register_augment("phalanx_drill", name="Phalanx Drill", scope=AugmentScope.PIECE,
                  quality=AugmentQuality.RARE, piece_filter=lambda p: "Guardian" in p.traits,
                  blurb="Guardian allies raise Threat and toughen.")
def phalanx_drill(piece: Any, state: dict[str, Any]) -> EffectBundle:
    # D1: catalog adds a taunt-on-cast; MVP keeps the Threat raise + armor (taunt
    # would need a per-cast hook). Threat draws aggro via the engine's targeting.
    return EffectBundle(modifiers=_mods("phalanx_drill", threat=("mul", 1.5), armor=("mul", 1.15)))


@register_augment("component_stipend", name="Component Stipend", scope=AugmentScope.RUN,
                  quality=AugmentQuality.RARE, blurb="Gain a base component plus a banked reroll.")
def component_stipend(run: Run) -> None:
    run.inventory["keen_claw"] = run.inventory.get("keen_claw", 0) + 1
    run.augment_state["banked_rerolls"] = run.augment_state.get("banked_rerolls", 0) + 1


@register_augment("tempest_surge", name="Tempest Surge", scope=AugmentScope.RUN,
                  quality=AugmentQuality.RARE, blurb="Immediately gain Tempest — the board cap climbs sooner.")
def tempest_surge(run: Run) -> None:
    run.tempest += 4


@register_augment("stormbound_trail", name="Stormbound Trail", scope=AugmentScope.RUN,
                  quality=AugmentQuality.RARE, quest_tracker="stormbound_trail_progress",
                  blurb="Win fights in stormy weather → Kinship emblem.")
def stormbound_trail(run: Run) -> None:
    run.augment_state.setdefault("stormbound_trail", {"wins": 0, "target": 4, "done": False})


@register_quest_tracker("stormbound_trail_progress", events=["on_combat_end"])
def stormbound_trail_progress(run: Run, event_name: str, event: Any, ctx: Any = None) -> None:
    st = run.augment_state.get("stormbound_trail")
    if not st or st["done"]:
        return
    if getattr(event, "winner", None) != "team":
        return
    # Only stormy (non-CLEAR) wins count — read the live weather off `ctx`
    # (CombatEndEvent carries none). If ctx is absent (untracked call), don't count.
    if ctx is None or ctx.weather is WeatherState.CLEAR:
        return
    st["wins"] += 1
    if st["wins"] >= st["target"]:
        run.inventory["emblem_beast"] = run.inventory.get("emblem_beast", 0) + 1
        st["done"] = True


# ===========================================================================
# 3. EPIC — identity-defining power spikes
# ===========================================================================


@register_augment("apex_predators", name="Apex Predators", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.EPIC, blurb="Your predator damage multipliers are amplified.")
def apex_predators(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    members = _team_set(team)

    def hook(ctx: Any, event: Any, value: float) -> float:
        atk = event.attacker
        if atk is None or id(atk) not in members:
            return value
        if ring_relation(atk.affinity, ctx.weather) in _PREDATOR_RELATIONS:
            return value * 1.30
        return value

    return EffectBundle(hooks=[Hook("on_damage_pre", hook, priority=30, scope=HookScope.PER_HIT)])


@register_augment("eye_of_the_storm", name="Eye of the Storm", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.EPIC, blurb="At combat start the team gains the live weather's favor buff.")
def eye_of_the_storm(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    members = list(team)

    def hook(ctx: Any, event: Any) -> None:
        buff = WEATHER_BUFF_BASE.get(ctx.weather)
        if buff is None:
            return  # CLEAR → inert
        for p in members:
            for stat, mult in (
                ("strength", buff.str_mult), ("intelligence", buff.int_mult),
                ("attack_speed", buff.as_mult), ("armor", buff.armor_mult), ("resistance", buff.res_mult),
            ):
                if mult != 1.0:
                    ctx.apply_modifier(p, Modifier(stat, "mul", mult, Lifetime.COMBAT, "augment:eye_of_the_storm"))

    return EffectBundle(hooks=[Hook("on_combat_start", hook, scope=HookScope.PER_HIT)])


@register_augment("doldrums_blessing", name="Doldrums Blessing", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.EPIC, blurb="While the weather is CLEAR, the team gains a large stat pack.")
def doldrums_blessing(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    members = list(team)

    def hook(ctx: Any, event: Any) -> None:
        if ctx.weather is not WeatherState.CLEAR:
            return
        for p in members:
            for stat in ("strength", "intelligence", "hp", "armor", "resistance"):
                ctx.apply_modifier(p, Modifier(stat, "mul", 1.25, Lifetime.COMBAT, "augment:doldrums_blessing"))

    return EffectBundle(hooks=[Hook("on_combat_start", hook, scope=HookScope.PER_HIT)])


@register_augment("built_different", name="Built Different", scope=AugmentScope.PIECE,
                  quality=AugmentQuality.EPIC,
                  piece_filter=lambda p: not getattr(p, "_has_active_synergy", False),
                  blurb="Allies with no active synergy gain large stats.")
def built_different(piece: Any, state: dict[str, Any]) -> EffectBundle:
    # D1: the "no active breakpoint" test is approximated by a flag the loadout
    # sets after trait resolution (`_has_active_synergy`); see loadout step 6.
    return EffectBundle(modifiers=_mods("built_different", strength=("mul", 1.35),
                                        intelligence=("mul", 1.35), hp=("mul", 1.25)))


@register_augment("living_tide", name="Living Tide", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.EPIC, blurb="Allies heal for a share of all damage they deal.")
def living_tide(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    members = _team_set(team)

    def hook(ctx: Any, event: Any) -> None:
        atk = event.attacker
        if atk is None or id(atk) not in members or not ctx.is_alive(atk):
            return
        ctx.heal(atk, atk, 0.18 * max(0.0, event.amount))

    return EffectBundle(hooks=[Hook("on_damage_dealt", hook, scope=HookScope.PER_HIT)])


@register_augment("overclock", name="Overclock", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.EPIC, blurb="Allies' meters fill faster for the opening, then normalize.")
def overclock(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    return EffectBundle(modifiers=_mods("overclock", lifetime=Lifetime.TIMED, expires=500,
                                        attack_speed=("mul", 1.25), move_speed=("mul", 1.25),
                                        mana_regen=("mul", 1.25)))


@register_augment("hexproof_pack", name="Hexproof Pack", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.EPIC, blurb="The first crowd-control on each ally each combat is ignored.")
def hexproof_pack(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    members = list(team)

    def hook(ctx: Any, event: Any) -> None:
        for p in members:
            p.cc_immune = True  # opening CC-immunity (D4: reuses the Scaled @5 primitive)

    def drop(ctx: Any, event: Any) -> None:
        if event.tick == 150:
            for p in members:
                p.cc_immune = False

    return EffectBundle(hooks=[
        Hook("on_combat_start", hook, scope=HookScope.PER_HIT),
        Hook("on_tick", drop, scope=HookScope.PER_HIT),
    ])


@register_augment("ambush", name="Ambush", scope=AugmentScope.PIECE,
                  quality=AugmentQuality.EPIC, piece_filter=lambda p: "Stalker" in p.traits,
                  blurb="Stalker allies begin combat seeking the enemy backline, with bonus power.")
def ambush(piece: Any, state: dict[str, Any]) -> EffectBundle:
    def hook(ctx: Any, event: Any) -> None:
        piece.seeks_backline = True

    return EffectBundle(modifiers=_mods("ambush", strength=("mul", 1.20), intelligence=("mul", 1.20)),
                        hooks=[Hook("on_combat_start", hook, scope=HookScope.PER_HIT)])


@register_augment("twin_fang", name="Twin Fang", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.EPIC, blurb="Your highest-Tier ally gains a second copy of its ability.")
def twin_fang(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    members = list(team)

    def hook(ctx: Any, event: Any) -> None:
        from src.game.loadout import make_slot
        candidates = [p for p in members if p.actives]
        if not candidates:
            return
        target = max(candidates, key=lambda p: (p.level, p.id))  # deterministic "chosen"
        target.actives.append(make_slot(target.actives[0].ability_id))

    return EffectBundle(hooks=[Hook("on_combat_start", hook, scope=HookScope.PER_HIT)])


@register_augment("pack_tactics", name="Pack Tactics", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.EPIC, blurb="Allies adjacent to an ally deal bonus damage.")
def pack_tactics(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    members = list(team)
    member_ids = {id(p) for p in members}

    def hook(ctx: Any, event: Any, value: float) -> float:
        from src.game.combat.context import hex_distance
        atk = event.attacker
        if atk is None or id(atk) not in member_ids:
            return value
        for ally in members:
            if ally is atk or not ctx.is_alive(ally):
                continue
            if hex_distance(atk.position_q, atk.position_r, ally.position_q, ally.position_r) == 1:
                return value * 1.15
        return value

    return EffectBundle(hooks=[Hook("on_damage_pre", hook, priority=25, scope=HookScope.PER_HIT)])


@register_augment("kinship_crown", name="Kinship Crown", scope=AugmentScope.RUN,
                  quality=AugmentQuality.EPIC, blurb="Your board counts as +2 toward a chosen Kinship.")
def kinship_crown(run: Run) -> None:
    _add_trait_bonus(run, _dominant_kinship(run), 2)


@register_augment("emblem_of_the_wild", name="Emblem of the Wild", scope=AugmentScope.RUN,
                  quality=AugmentQuality.EPIC, blurb="Gain a Spirit Gem and a chosen component.")
def emblem_of_the_wild(run: Run) -> None:
    run.inventory["spirit_gem"] = run.inventory.get("spirit_gem", 0) + 1
    run.inventory["fang"] = run.inventory.get("fang", 0) + 1


@register_augment("bloodless_victory", name="Bloodless Victory", scope=AugmentScope.RUN,
                  quality=AugmentQuality.EPIC, quest_tracker="bloodless_victory_progress",
                  blurb="Win fights with no ally deaths → special item.")
def bloodless_victory(run: Run) -> None:
    run.augment_state.setdefault("bloodless_victory", {"wins": 0, "target": 3, "done": False})


@register_quest_tracker("bloodless_victory_progress", events=["on_death", "on_combat_end"])
def bloodless_victory_progress(run: Run, event_name: str, event: Any, ctx: Any = None) -> None:
    st = run.augment_state.get("bloodless_victory")
    if not st or st["done"]:
        return
    if event_name == "on_death":
        victim = getattr(event, "victim", None)
        if victim is not None and not victim.is_enemy:
            st["_dirty"] = True  # an ally died this combat
    elif event_name == "on_combat_end":
        deathless = not st.pop("_dirty", False)
        if getattr(event, "winner", None) == "team" and deathless:
            st["wins"] += 1
            if st["wins"] >= st["target"]:
                run.inventory["spellfang_crown"] = run.inventory.get("spellfang_crown", 0) + 1
                st["done"] = True


# ===========================================================================
# 4. PRISMATIC — run-defining (gated to stage ≥ 2, D3)
# ===========================================================================


@register_augment("the_uprising", name="The Uprising", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.PRISMATIC, quest_tracker="uprising_progress",
                  blurb="The team's power grows with every fight already won this run.")
def the_uprising(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    wins = int(state.get("uprising_wins", 0))
    boost = 1.0 + 0.04 * wins  # +4% str/int/hp per prior win
    return EffectBundle(modifiers=_mods("the_uprising", strength=("mul", boost),
                                        intelligence=("mul", boost), hp=("mul", boost)))


@register_quest_tracker("uprising_progress", events=["on_combat_end"])
def uprising_progress(run: Run, event_name: str, event: Any, ctx: Any = None) -> None:
    if getattr(event, "winner", None) == "team":
        run.augment_state["uprising_wins"] = run.augment_state.get("uprising_wins", 0) + 1


@register_augment("one_with_the_sky", name="One With the Sky", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.PRISMATIC, blurb="Every ally's affinity is treated as the live weather.")
def one_with_the_sky(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    members = list(team)

    def hook(ctx: Any, event: Any) -> None:
        for p in members:
            p.affinity = ctx.weather  # never prey, never weather-debuffed (pieces rebuilt per combat)

    return EffectBundle(hooks=[Hook("on_combat_start", hook, priority=100, scope=HookScope.PER_HIT)])


@register_augment("heart_of_the_storm", name="Heart of the Storm", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.PRISMATIC, blurb="The weather sits one step in your favour all fight.")
def heart_of_the_storm(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    # D1: the catalog shifts the ring each round; MVP grants a steady predator-tier
    # team damage amp (weather is fixed per combat in this engine).
    members = _team_set(team)

    def hook(ctx: Any, event: Any, value: float) -> float:
        atk = event.attacker
        if atk is None or id(atk) not in members:
            return value
        return value * 1.20

    return EffectBundle(hooks=[Hook("on_damage_pre", hook, priority=20, scope=HookScope.PER_HIT)])


@register_augment("apex_instinct", name="Apex Instinct", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.PRISMATIC, blurb="Abilities can crit team-wide, and crit damage is amplified.")
def apex_instinct(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    members = list(team)

    def hook(ctx: Any, event: Any) -> None:
        for p in members:
            p.ability_can_crit = True
            ctx.apply_modifier(p, Modifier("crit_chance", "add", 0.15, Lifetime.COMBAT, "augment:apex_instinct"))

    return EffectBundle(hooks=[Hook("on_combat_start", hook, scope=HookScope.PER_HIT)])


@register_augment("endless_swarm", name="Endless Swarm", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.PRISMATIC, blurb="A dying ally leaves a fighting echo on its tile.")
def endless_swarm(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    member_ids = {id(p) for p in team}
    spawned: set[str] = set()

    def hook(ctx: Any, event: Any) -> None:
        victim = event.victim
        if victim is None or id(victim) not in member_ids or victim.id in spawned:
            return
        spawned.add(victim.id)
        ctx.spawn(_echo_of(victim), victim.position_q, victim.position_r)

    return EffectBundle(hooks=[Hook("on_death", hook, scope=HookScope.PER_HIT)])


@register_augment("worldroot_crown", name="Worldroot Crown", scope=AugmentScope.RUN,
                  quality=AugmentQuality.PRISMATIC, blurb="Your board counts as +1 toward every Kinship.")
def worldroot_crown(run: Run) -> None:
    from src.game.content import KINSHIP_TAGS
    for tag in KINSHIP_TAGS:
        _add_trait_bonus(run, tag, 1)


@register_augment("sanctuary", name="Sanctuary", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.PRISMATIC, blurb="The first ally that would die each fight is revived once.")
def sanctuary(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    member_ids = {id(p) for p in team}
    fired = {"done": False}

    def hook(ctx: Any, event: Any) -> None:
        if fired["done"]:
            return
        victim = event.victim
        if victim is None or id(victim) not in member_ids:
            return
        fired["done"] = True
        ctx.revive(victim, hp_frac=0.3)  # D4: reuses ctx.revive (the Mender primitive)

    return EffectBundle(hooks=[Hook("on_death", hook, priority=200, scope=HookScope.PER_HIT)])


@register_augment("living_world", name="Living World", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.PRISMATIC,
                  blurb="The live weather fights beside you — the sky's power becomes your team's.")
def living_world(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    """The world backs you up: each weather grants a bespoke team boon echoing its
    @10 affinity identity (Sunlit/Overcast/Shrouded/Tidekin/Frostbound/Stormfed).

    Weather is fixed per combat, so the active boon is decided at `on_combat_start`;
    the always-subscribed reducing/proc hooks self-gate on `ctx.weather` (cheap,
    correct). Works on every node (weather is always live) — a true Prismatic.
    All values are MVP tuning picks (D1). RNG-free (V.2/V.14)."""
    members = list(team)
    member_ids = {id(p) for p in members}
    SRC = "augment:living_world"

    def on_start(ctx: Any, event: Any) -> None:
        w = ctx.weather
        if w is WeatherState.CLEAR:  # Radiance — Sunlit
            for p in members:
                ctx.apply_modifier(p, Modifier("strength", "mul", 1.10, Lifetime.COMBAT, SRC))
                ctx.apply_modifier(p, Modifier("intelligence", "mul", 1.10, Lifetime.COMBAT, SRC))
        elif w is WeatherState.RAIN:  # Flow — Tidekin
            for p in members:
                ctx.apply_modifier(p, Modifier("mana_regen", "mul", 1.40, Lifetime.COMBAT, SRC))
        elif w is WeatherState.THUNDER:  # Galvanize — Stormfed
            for p in members:
                ctx.apply_modifier(p, Modifier("attack_speed", "mul", 1.30, Lifetime.COMBAT, SRC))
        elif w is WeatherState.MIST:  # Veil — Shrouded: open untargetable behind the mist
            for p in members:
                ctx.apply_status(p, "hexproof", 250)
        elif w is WeatherState.SNOW:  # Frostbite — Frostbound: the cold pins your foes
            # 2 slow stacks all fight (~0.70 cadence). `slow` now throttles meter
            # advancement (B.25); stacks intensify if other frost sources add more.
            for p in ctx.living_pieces():
                if p.is_enemy:
                    ctx.apply_status(p, "slow", 99_999, stacks=2)
        # CLOUDY (Cover) is handled entirely by the reducing hook below.

    def on_tick(ctx: Any, event: Any) -> None:
        if ctx.weather is not WeatherState.CLEAR:
            return
        if event.tick % 100 == 0 and event.tick != 0:
            for p in members:
                if ctx.is_alive(p):
                    ctx.heal(p, p, 0.03 * p.max_hp)

    def on_incoming(ctx: Any, event: Any, value: float) -> float:
        if ctx.weather is WeatherState.CLOUDY and event.target is not None and id(event.target) in member_ids:
            return value * 0.82  # Cover — Overcast: the clouds shield you
        return value

    def on_dealt(ctx: Any, event: Any) -> None:
        if ctx.weather is not WeatherState.RAIN:
            return
        atk = event.attacker
        if atk is not None and id(atk) in member_ids and ctx.is_alive(atk):
            ctx.heal(atk, atk, 0.12 * max(0.0, event.amount))

    def on_strike(ctx: Any, event: Any) -> None:
        if ctx.weather is not WeatherState.THUNDER:
            return
        atk, tgt = event.attacker, event.target
        if atk is None or tgt is None or id(atk) not in member_ids:
            return
        bolt = 0.30 * max(atk.stat("strength"), atk.stat("intelligence"))
        if bolt > 0:
            ctx.deal_damage(atk, tgt, bolt, SourceTag.ABILITY)

    return EffectBundle(hooks=[
        Hook("on_combat_start", on_start, scope=HookScope.PER_HIT),
        Hook("on_tick", on_tick, scope=HookScope.PER_HIT),
        Hook("on_damage_pre", on_incoming, priority=15, scope=HookScope.PER_HIT),
        Hook("on_damage_dealt", on_dealt, scope=HookScope.PER_HIT),
        Hook("on_attack_landed", on_strike, scope=HookScope.PER_HIT),
    ])


@register_augment("primordial_bond", name="Primordial Bond", scope=AugmentScope.PIECE,
                  quality=AugmentQuality.PRISMATIC, piece_filter=lambda p: "Primordial" in p.traits,
                  blurb="Your Tier-10 Primordial gains a free power tier and a second wind.")
def primordial_bond(piece: Any, state: dict[str, Any]) -> EffectBundle:
    # D4/D8: the @2 breakpoint-for-free + @3 fixpoint tier-up (D.20) is deferred;
    # MVP grants a large stat tier + a once-per-combat decaying barrier (second wind).
    def hook(ctx: Any, event: Any) -> None:
        ctx.grant_barrier(piece, 0.35 * piece.max_hp, duration_ticks=300)

    return EffectBundle(modifiers=_mods("primordial_bond", strength=("mul", 1.25),
                                        intelligence=("mul", 1.25), hp=("mul", 1.20)),
                        hooks=[Hook("on_combat_start", hook, scope=HookScope.ONCE_PER_COMBAT)])


@register_augment("threefold_bloom", name="Threefold Bloom", scope=AugmentScope.TEAM,
                  quality=AugmentQuality.PRISMATIC, blurb="Your three highest-Tier allies gain a free slot of stats.")
def threefold_bloom(team: list[Any], state: dict[str, Any]) -> EffectBundle:
    members = list(team)

    def hook(ctx: Any, event: Any) -> None:
        top = sorted(members, key=lambda p: (-p.level, p.id))[:3]
        for p in top:
            for stat in ("strength", "intelligence", "hp"):
                ctx.apply_modifier(p, Modifier(stat, "mul", 1.25, Lifetime.COMBAT, "augment:threefold_bloom"))

    return EffectBundle(hooks=[Hook("on_combat_start", hook, scope=HookScope.PER_HIT)])


@register_augment("tempest_ascendant", name="Tempest Ascendant", scope=AugmentScope.RUN,
                  quality=AugmentQuality.PRISMATIC, blurb="Immediately raise the board cap by two ranks.")
def tempest_ascendant(run: Run) -> None:
    run.tempest_rank = min(10, run.tempest_rank + 2)


@register_augment("the_long_hunt", name="The Long Hunt", scope=AugmentScope.RUN,
                  quality=AugmentQuality.PRISMATIC, quest_tracker="the_long_hunt_progress",
                  blurb="Land the killing blow on each stage boss → Prismatic payout.")
def the_long_hunt(run: Run) -> None:
    run.augment_state.setdefault("the_long_hunt", {"bosses": [], "done": False})


@register_quest_tracker("the_long_hunt_progress", events=["on_kill"])
def the_long_hunt_progress(run: Run, event_name: str, event: Any, ctx: Any = None) -> None:
    st = run.augment_state.get("the_long_hunt")
    if not st or st["done"]:
        return
    from src.game.bosses.data import BOSS_DEFS
    victim = getattr(event, "victim", None)
    boss_ids = {b.id for b in BOSS_DEFS.values()}
    # D5: no `boss_phase2` victim tag exists yet — keyed on boss-id kills instead.
    if victim is not None and victim.id in boss_ids and victim.id not in st["bosses"]:
        st["bosses"].append(victim.id)
        if len(st["bosses"]) >= 6:
            run.inventory["spirit_gem"] = run.inventory.get("spirit_gem", 0) + 2
            st["done"] = True


# ===========================================================================
# 5. Primordial-unlock RUN augments (T.28a/V.37 — gate the T10 shop access)
# ===========================================================================

for _uid, _name, _pair in (
    ("unlock_verdant", "Verdant Communion", "Verdant"),
    ("unlock_tempest", "Tempest Communion", "Tempest"),
    ("unlock_stoneveil", "Stoneveil Communion", "Stoneveil"),
):
    def _make_unlock(pair: str) -> Callable:
        def handler(run: Run) -> None:
            unlocked = run.augment_state.setdefault("primordial_unlock", [])
            if pair not in unlocked:
                unlocked.append(pair)
        return handler

    register_augment(_uid, name=_name, scope=AugmentScope.RUN, quality=AugmentQuality.EPIC,
                     blurb=f"Unlock the {_pair} Tier-10 Primordial in the late shop.")(_make_unlock(_pair))


# ---------------------------------------------------------------------------
# Internal helpers (trait bonus, dominant trait, echo spawn, run seed)
# ---------------------------------------------------------------------------


def _add_trait_bonus(run: Run, tag: str | None, amount: int) -> None:
    if not tag:
        return
    bonus = run.augment_state.setdefault("trait_bonus", {})
    bonus[tag] = bonus.get(tag, 0) + amount


def _dominant_kinship(run: Run) -> str | None:
    from src.game.content import KINSHIP_TAGS
    return _dominant_tag(run, KINSHIP_TAGS)


def _dominant_calling(run: Run) -> str | None:
    from src.game.content import CALLING_TAGS
    return _dominant_tag(run, CALLING_TAGS)


def _dominant_tag(run: Run, vocab: Any) -> str | None:
    counts: dict[str, int] = defaultdict(int)
    for champ in run.roster:
        for tag in champ.traits:
            if tag in vocab:
                counts[tag] += 1
    if not counts:
        return None
    # Deterministic: highest count, ties broken by tag name.
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def _echo_of(victim: Any) -> Any:
    """A weaker fighting echo of a dying piece (Endless Swarm). Half stats, no items."""
    from src.game.piece import Piece

    echo = Piece(
        id=f"{victim.id}#echo",
        base_stats={k: v * 0.5 for k, v in victim.base_stats.items()},
        affinity=victim.affinity,
        traits=[],
        is_enemy=victim.is_enemy,
        level=victim.level,
    )
    echo.max_hp = max(1.0, victim.max_hp * 0.5)
    echo.hp = echo.max_hp
    echo.summon = True
    for slot in victim.actives:
        from src.game.loadout import make_slot
        echo.actives.append(make_slot(slot.ability_id))
    return echo


def _run_action_seed(run: Run, salt: str) -> int:
    """A deterministic seed for a RUN-augment's randomness (V.2/V.14).

    Python's built-in `hash()` is per-process randomized for strings/tuples, so
    `zlib.crc32` is used for a stable salt mix instead (B-class determinism bug).
    """
    import zlib

    return (
        (run.seed & 0x7FFFFFFF)
        ^ ((run.current_node_index * 2654435761) & 0x7FFFFFFF)
        ^ zlib.crc32(salt.encode())
    ) & 0x7FFFFFFF


# ===========================================================================
# Quality-weight curve + offer generation (§5)
# ===========================================================================

_STAGE_WEIGHTS: dict[int, dict[AugmentQuality, int]] = {
    1: {AugmentQuality.COMMON: 70, AugmentQuality.RARE: 25, AugmentQuality.EPIC: 5, AugmentQuality.PRISMATIC: 0},
    2: {AugmentQuality.COMMON: 50, AugmentQuality.RARE: 30, AugmentQuality.EPIC: 17, AugmentQuality.PRISMATIC: 3},
    3: {AugmentQuality.COMMON: 35, AugmentQuality.RARE: 33, AugmentQuality.EPIC: 25, AugmentQuality.PRISMATIC: 7},
    4: {AugmentQuality.COMMON: 22, AugmentQuality.RARE: 33, AugmentQuality.EPIC: 33, AugmentQuality.PRISMATIC: 12},
    5: {AugmentQuality.COMMON: 12, AugmentQuality.RARE: 30, AugmentQuality.EPIC: 40, AugmentQuality.PRISMATIC: 18},
    6: {AugmentQuality.COMMON: 5, AugmentQuality.RARE: 25, AugmentQuality.EPIC: 45, AugmentQuality.PRISMATIC: 25},
}


def quality_weights_for_stage(stage_index: int) -> dict[AugmentQuality, int]:
    """Per-stage Common→Prismatic offer weights (§5; tuning surface, D.11)."""
    idx = max(1, min(6, stage_index))
    return dict(_STAGE_WEIGHTS[idx])


def _weighted_quality(rng: SeededRng, qualities: list[AugmentQuality], weights: list[int]) -> AugmentQuality:
    total = sum(weights)
    r = rng.random() * total
    acc = 0.0
    for q, w in zip(qualities, weights):
        acc += w
        if r < acc:
            return q
    return qualities[-1]


def generate_augment_offer(
    run_seed: int,
    node_index: int,
    stage_index: int,
    *,
    reroll_count: int = 0,
    exclude: tuple[str, ...] = (),
) -> list[Augment]:
    """Deterministic 1-of-3 augment offer (V.2/V.14).

    Picks 3 distinct augments: roll a quality by the stage curve, then a uniform
    unpicked augment of that quality. Excludes `exclude` (already-active) ids and
    avoids duplicates within the offer. Prismatic gated to stage ≥ 2 (D3).

    ``reroll_count`` selects the offer draw (V.84): ``0`` = the fresh node offer,
    ``1`` = the first reroll (legacy byte-identical), ``>= 2`` = awarded/banked
    rerolls. Purely seed-driven — RNG-free selection, so replays stay stable.
    """
    rng = SeededRng(augment_seed(run_seed, node_index, reroll_count))
    excluded = set(exclude)
    weights = quality_weights_for_stage(stage_index)

    pool: dict[AugmentQuality, list[Augment]] = defaultdict(list)
    for aug in sorted(AUGMENT_REGISTRY.values(), key=lambda a: a.id):
        if aug.id in excluded:
            continue
        if aug.quality is AugmentQuality.PRISMATIC and stage_index < 2:
            continue
        if weights.get(aug.quality, 0) <= 0:
            continue
        pool[aug.quality].append(aug)

    offer: list[Augment] = []
    for _ in range(3):
        avail = [q for q in (AugmentQuality.COMMON, AugmentQuality.RARE,
                             AugmentQuality.EPIC, AugmentQuality.PRISMATIC) if pool.get(q)]
        if not avail:
            break
        q = _weighted_quality(rng, avail, [weights[x] for x in avail])
        lst = pool[q]
        chosen = lst.pop(rng.randint(0, len(lst) - 1))
        offer.append(chosen)
    return offer


# ===========================================================================
# Reroll bookkeeping (T.42a, V.84) — game-side so the view stays Flet-free of
# game logic (V.63). 1 base free reroll per node visit + any awarded/banked
# rerolls in `augment_state["banked_rerolls"]`.
# ===========================================================================


def rerolls_available(run: Run, reroll_count: int) -> int:
    """How many more rerolls the player may take, given rerolls already used.

    The first reroll of a node visit (``reroll_count == 0``) is free; every
    reroll after that spends one banked/awarded reroll (V.84).
    """
    banked = run.augment_state.get("banked_rerolls", 0)
    free = 1 if reroll_count == 0 else 0
    return free + banked


def reroll_augment_offer(
    run: Run, node_index: int, stage_index: int, reroll_count: int
) -> tuple[list[Augment], int, int] | None:
    """Consume one reroll and return ``(new_offer, new_reroll_count, left)``.

    ``reroll_count`` is how many rerolls the view has already taken this node
    visit. Returns ``None`` when no reroll is available (the view disables the
    button). The free base reroll is spent first; subsequent rerolls decrement
    ``augment_state["banked_rerolls"]``. Deterministic (V.2/V.14) — the new offer
    comes straight from ``generate_augment_offer`` at ``reroll_count + 1``.
    """
    if rerolls_available(run, reroll_count) <= 0:
        return None
    if reroll_count >= 1:  # the free base reroll is count 0 -> 1; later ones bank
        run.augment_state["banked_rerolls"] = (
            run.augment_state.get("banked_rerolls", 0) - 1
        )
    new_count = reroll_count + 1
    offer = generate_augment_offer(
        run.seed,
        node_index,
        stage_index,
        reroll_count=new_count,
        exclude=tuple(run.active_augments),
    )
    return offer, new_count, rerolls_available(run, new_count)


# ===========================================================================
# Pick / apply at node resolution
# ===========================================================================


def apply_augment(run: Run, augment: Augment) -> None:
    """Resolve a picked augment into `Run` state (V.18).

    RUN scope mutates `Run` immediately (Amber/items/Tempest/state). TEAM/PIECE
    scope just records the id — its combat bundle is rebuilt fresh each combat in
    `compile_loadout`. Quest augments seed their `augment_state` slot.
    """
    if augment.id not in run.active_augments:
        run.active_augments.append(augment.id)
    if augment.scope is AugmentScope.RUN:
        augment.handler(run)
    if augment.quest_tracker:
        run.augment_state.setdefault(augment.id, {})


# ===========================================================================
# Combat-time application (called by compile_loadout, step 6 + 9)
# ===========================================================================


def apply_run_augments(pieces: list[Any], bus: Any, run_mods: RunModifiers | None) -> None:
    """Apply active TEAM/PIECE augment bundles + wire quest trackers (V.18, §10.1).

    Player team only (mirrors V.22). RUN augments already mutated `Run` at pick
    time, so they are skipped here. `run_mods=None` ⇒ no-op (back-compat).
    """
    if run_mods is None or not run_mods.augments:
        return
    from src.game.loadout import apply_bundle

    team = [p for p in pieces if not p.is_enemy]
    state = run_mods.augment_state

    for aug_id in run_mods.augments:
        aug = AUGMENT_REGISTRY.get(aug_id)
        if aug is None:
            continue
        if aug.scope is AugmentScope.TEAM:
            bundle = aug.handler(team, state)
            _apply_team_bundle(team, bundle, bus)
        elif aug.scope is AugmentScope.PIECE:
            for piece in team:
                if aug.piece_filter is None or aug.piece_filter(piece):
                    apply_bundle(piece, aug.handler(piece, state), bus)
        # RUN: nothing at combat time.


def _apply_team_bundle(team: list[Any], bundle: EffectBundle, bus: Any) -> None:
    """Apply a TEAM bundle: modifiers/statuses/grants to each piece, hooks ONCE."""
    from src.game.loadout import apply_bundle
    from dataclasses import replace

    # Modifiers/statuses/grants per piece; hooks subscribed once (global, close over team).
    per_piece = replace(bundle, hooks=[])
    for piece in team:
        apply_bundle(piece, per_piece, bus)
    for hook in bundle.hooks:
        bus.subscribe(hook)


def wire_quest_trackers(bus: Any, run_mods: RunModifiers | None) -> None:
    """Subscribe active quest trackers as Run-level bus hooks (§9.3).

    The tracker closes over the live `Run`; it fires during combat but mutates
    persistent `Run.augment_state`, surviving across fights. Low priority so
    quest progress is observed after combat resolves its own state. No-op unless
    the seam carries a live `Run` (pure sims pass `run_mods=None` or no run-ref).
    """
    if run_mods is None or run_mods.run is None:
        return
    run = run_mods.run
    for aug_id in run.active_augments:
        aug = AUGMENT_REGISTRY.get(aug_id)
        if aug is None or not aug.quest_tracker:
            continue
        tracker = QUEST_TRACKER_REGISTRY.get(aug.quest_tracker)
        if tracker is None:
            continue
        for event_name in QUEST_TRACKER_EVENTS.get(aug.quest_tracker, ()):
            bus.subscribe(Hook(
                event=event_name,
                handler=lambda ctx, ev, t=tracker, en=event_name: t(run, en, ev, ctx),
                priority=-100,
                scope=HookScope.PER_HIT,
            ))
