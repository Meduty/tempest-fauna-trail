"""Trait mechanic hook-builders (T.28b) — the non-stat riders.

Each public function returns a *builder* `(owner, source_id) -> list[Hook]`,
plugged into a trait rung as its 5th tuple element (see `_packs.define_trait`).
All deterministic — cadence counters / HP thresholds, never RNG (V.2/V.14/V.37).

Hook riders: second-wind decaying-shield, tidal HoT, enrage, time-ramp,
deterministic dodge, untargetable opener, plus the engine-behaviour arms —
`kiting` (Skyborn), `backline_seeker` (Stalker), `revive_first_ally` (Mender).
Taunt is a status honored by the engine (no T.28b trait wires it; Trickster
casts apply it in T.28c). The movement/targeting/death logic these arm lives in
`combat/engine.py` + `combat/context.revive`.
"""

from __future__ import annotations

from typing import Any, Callable

from src.game.effects import Hook, HookScope, Lifetime, Modifier
from src.game.piece import Piece

HookBuilder = Callable[[Piece, str], list[Hook]]


def _hp_frac(piece: Piece) -> float:
    return piece.hp / piece.max_hp if piece.max_hp > 0 else 0.0


def second_wind(threshold: float = 0.6, shield_frac: float = 0.4, duration: int = 1200) -> HookBuilder:
    """On dropping below `threshold` HP, grant a decaying shield once per combat
    (Primordial second wind, V.37). Reuses the V.28 barrier pool — bursts can
    still kill through it (not a revive)."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        state = {"used": False}

        def hook(ctx: Any, event: Any) -> None:
            if event.target is not owner or state["used"] or not owner.alive:
                return
            if _hp_frac(owner) < threshold:
                state["used"] = True
                ctx.grant_barrier(owner, owner.max_hp * shield_frac, duration)

        return [Hook("on_damage_taken", hook, scope=HookScope.PER_HIT)]

    return build


def tidal_hot(interval: int = 200, heal_frac: float = 0.02) -> HookBuilder:
    """Heal the carrier a fraction of max HP every `interval` ticks (Tidekin).
    Applied per-target, so a TEAM_WIDE rung gives every ally its own HoT."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        state = {"t": 0}

        def hook(ctx: Any, event: Any) -> None:
            if not owner.alive:
                return
            state["t"] += 1
            if state["t"] % interval == 0:
                ctx.heal(owner, owner, owner.max_hp * heal_frac)

        return [Hook("on_tick", hook, scope=HookScope.PER_HIT)]

    return build


def enrage(threshold: float = 0.25, as_mul: float = 1.5, str_mul: float = 1.3, duration: int = 600) -> HookBuilder:
    """Below `threshold` HP, a one-shot burst of Attack Speed + Strength (Beast).
    Offense, not a save."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        state = {"used": False}

        def hook(ctx: Any, event: Any) -> None:
            if event.target is not owner or state["used"] or not owner.alive:
                return
            if _hp_frac(owner) < threshold:
                state["used"] = True
                exp = ctx.current_tick + duration
                ctx.apply_modifier(owner, Modifier("attack_speed", "mul", as_mul, Lifetime.TIMED, sid, expires_at_tick=exp))
                ctx.apply_modifier(owner, Modifier("milli_AS", "mul", as_mul, Lifetime.TIMED, sid, expires_at_tick=exp))
                ctx.apply_modifier(owner, Modifier("strength", "mul", str_mul, Lifetime.TIMED, sid, expires_at_tick=exp))

        return [Hook("on_damage_taken", hook, scope=HookScope.PER_HIT)]

    return build


def time_ramp(interval: int = 100, per: float = 0.03, cap: int = 8, stat: str = "attack_speed") -> HookBuilder:
    """Stack a small `stat` mul every `interval` ticks up to `cap` (Skirmisher)."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        state = {"t": 0, "stacks": 0}

        def hook(ctx: Any, event: Any) -> None:
            if not owner.alive:
                return
            state["t"] += 1
            if state["t"] % interval == 0 and state["stacks"] < cap:
                state["stacks"] += 1
                ctx.apply_modifier(owner, Modifier(stat, "mul", 1.0 + per, Lifetime.COMBAT, sid))
                if stat == "attack_speed":
                    ctx.apply_modifier(owner, Modifier("milli_AS", "mul", 1.0 + per, Lifetime.COMBAT, sid))

        return [Hook("on_tick", hook, scope=HookScope.PER_HIT)]

    return build


def dodge(every_n: int = 7) -> HookBuilder:
    """Deterministically negate every Nth incoming basic attack (Skirmisher).
    Via the reducing `on_damage_pre` hook; note the engine floors final damage to
    1, so a 'dodge' leaks 1 — a near-total mitigation, RNG-free."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        state = {"n": 0}

        def hook(ctx: Any, event: Any, value: float) -> float:
            if event.target is not owner or event.tag != "basic_attack":
                return value
            state["n"] += 1
            if state["n"] % every_n == 0:
                return 0.0
            return value

        return [Hook("on_damage_pre", hook, scope=HookScope.PER_HIT, priority=50)]

    return build


def kiting() -> HookBuilder:
    """Arm the carrier as a kiter (Skyborn @2) — the engine's movement phase
    retreat-kites lone melee threats (see `engine._kite_step`). Melee Skyborn
    (base attack_range ≤ 1) also gain **+1 Attack Range** so kiting is coherent;
    pieces already at range 2+ (e.g. via Skyborn @5) skip the bonus, no stacking."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            owner.is_kiter = True
            if int(owner.stat("attack_range")) <= 1:
                ctx.apply_modifier(owner, Modifier("attack_range", "add", 1.0, Lifetime.COMBAT, sid))

        return [Hook("on_combat_start", hook, scope=HookScope.PER_HIT)]

    return build


def backline_seeker() -> HookBuilder:
    """Arm the carrier to path/target the enemy backline (Stalker @2) — the engine
    biases movement goals + target selection to the deepest enemy column. No
    teleport (per design); purely a movement/targeting preference."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            owner.seeks_backline = True

        return [Hook("on_combat_start", hook, scope=HookScope.PER_HIT)]

    return build


def revive_first_ally(hp_frac: float = 0.3) -> HookBuilder:
    """The first ally death each combat is reversed once (Mender @6, V.37 — the
    one true revive). The once-per-combat guard is shared across all carriers via
    a flag on `ctx`, so the team-wide apply still triggers exactly once."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            victim = event.victim
            if victim.is_enemy != owner.is_enemy:
                return  # only allies of the carrier (the player team)
            if getattr(ctx, "_mender_revive_used", False):
                return
            ctx._mender_revive_used = True
            ctx.revive(victim, hp_frac)

        return [Hook("on_death", hook, scope=HookScope.PER_HIT)]

    return build


def untargetable_opener(duration: int = 150) -> HookBuilder:
    """Untargetable for the opening `duration` ticks (Spirit). The piece still
    acts; enemies skip it in target selection (StatusGate.UNTARGETABLE)."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            ctx.apply_status(owner, "untargetable", duration, source_id=owner.id)

        return [Hook("on_combat_start", hook, scope=HookScope.PER_HIT)]

    return build
