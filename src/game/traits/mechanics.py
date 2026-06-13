"""Trait mechanic hook-builders (T.28b) — the non-stat riders.

Each public function returns a *builder* `(owner, source_id) -> list[Hook]`,
plugged into a trait rung as its 5th tuple element (see `_packs.define_trait`).
All deterministic — cadence counters / HP thresholds, never RNG (V.2/V.14/V.37).

Hook riders: second-wind decaying-shield, tidal HoT, enrage, time-ramp,
deterministic dodge, hexproof opener, plus the engine-behaviour arms —
`kiting` (Skyborn), `backline_seeker` (Stalker), `revive_first_ally` (Mender).
Taunt is a status honored by the engine (no T.28b trait wires it; Trickster
casts apply it in T.28c). The movement/targeting/death logic these arm lives in
`combat/engine.py` + `combat/context.revive`.
"""

from __future__ import annotations

from typing import Any, Callable

from src.game.effects import Hook, HookScope, Lifetime, Modifier, SourceTag
from src.game.piece import Piece

HookBuilder = Callable[[Piece, str], list[Hook]]


def _hp_frac(piece: Piece) -> float:
    return piece.hp / piece.max_hp if piece.max_hp > 0 else 0.0


def _dist(a: Piece, b: Piece) -> int:
    from src.game.combat.context import hex_distance
    return hex_distance(a.position_q, a.position_r, b.position_q, b.position_r)


def _enemies(ctx: Any, of: Piece) -> list[Piece]:
    """Living enemies of `of`, id-sorted for determinism."""
    return sorted(ctx.enemies_of(of), key=lambda e: e.id)


def _allies(ctx: Any, of: Piece) -> list[Piece]:
    return sorted(ctx.allies_of(of), key=lambda a: a.id)


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


def hexproof_opener(duration: int = 150, trait: str = "") -> HookBuilder:
    """Hexproof for the opening `duration` ticks (Spirit/Shrouded). The piece still
    acts; it can't be acquired as a single target (StatusGate.HEXPROOF, V.40) —
    AoE still hits. `trait` guards a TEAM_WIDE apply to carriers only (a signature
    opener stays a carrier perk); empty on a PER rung where every target is a carrier."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            if trait and trait not in owner.traits:
                return
            ctx.apply_status(owner, "hexproof", duration, source_id=owner.id)

        return [Hook("on_combat_start", hook, scope=HookScope.PER_HIT)]

    return build


# ===========================================================================
# T.28c — mechanic + apex riders (hook idioms over the existing ctx mutators).
# Secondary/"proc" damage uses SourceTag.ITEM_PROC — the existing tag for
# follow-up hits that must NOT re-fire on-attack/on-ability hooks (so no
# recursion). All deterministic: cadence counters / hp-frac / id-sorted picks.
# NOTE: trait resolution applies only the *highest cleared* rung's bundle, so a
# rung re-includes every mechanic it should still grant (see kinships/callings).
# ===========================================================================


def bonus_auto_damage(frac: float = 0.12) -> HookBuilder:
    """Extra physical damage on each of the carrier's basic attacks (Hunter).
    Team-safe: at a TEAM rung every ally's autos gain it (the Hunter aura)."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            if event.attacker is not owner or not owner.alive:
                return
            ctx.deal_damage(owner, event.target, frac * owner.stat("strength"),
                            SourceTag.ITEM_PROC, damage_type="physical")

        return [Hook("on_attack_landed", hook, scope=HookScope.PER_HIT)]

    return build


def empowered_shot(every_n: int = 4, mult: float = 0.8) -> HookBuilder:
    """Every Nth basic attack lands an empowered follow-up (Hunter), cadence-based."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        state = {"n": 0}

        def hook(ctx: Any, event: Any) -> None:
            if event.attacker is not owner or not owner.alive:
                return
            state["n"] += 1
            if state["n"] % every_n == 0:
                ctx.deal_damage(owner, event.target, mult * owner.stat("strength"),
                                SourceTag.ITEM_PROC, damage_type="physical")

        return [Hook("on_attack_landed", hook, scope=HookScope.PER_HIT)]

    return build


def cleave(frac: float = 0.3) -> HookBuilder:
    """Basic attacks splash to one enemy adjacent to the struck target (Hunter)."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            if event.attacker is not owner or not owner.alive:
                return
            target = event.target
            adj = [e for e in _enemies(ctx, owner)
                   if e is not target and _dist(e, target) <= 1]
            if adj:
                ctx.deal_damage(owner, adj[0], frac * owner.stat("strength"),
                                SourceTag.ITEM_PROC, damage_type="physical")

        return [Hook("on_attack_landed", hook, scope=HookScope.PER_HIT)]

    return build


def ability_crit() -> HookBuilder:
    """Let the carrier's abilities crit (Mystic) — flips the existing
    `Piece.ability_can_crit` field the damage pipeline already reads."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            owner.ability_can_crit = True

        return [Hook("on_combat_start", hook, scope=HookScope.PER_HIT)]

    return build


def ability_splash(frac: float = 0.4, count: int = 1) -> HookBuilder:
    """The carrier's ability damage splashes to up to `count` enemies adjacent to
    the struck target (Mystic). Splash uses ITEM_PROC so it never re-splashes."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            if event.attacker is not owner or not owner.alive:
                return
            target = event.target
            adj = [e for e in _enemies(ctx, owner)
                   if e is not target and _dist(e, target) <= 1]
            for e in adj[:count]:
                ctx.deal_damage(owner, e, frac * event.amount,
                                SourceTag.ITEM_PROC, damage_type="magical")

        return [Hook("on_ability_damage", hook, scope=HookScope.PER_HIT)]

    return build


def start_shield(frac: float = 0.2, duration: int = 0) -> HookBuilder:
    """Grant the carrier a barrier at combat start (Guardian/Warden opener).
    Team-safe at a TEAM rung. Reuses the V.28 barrier pool."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            ctx.grant_barrier(owner, frac * owner.max_hp, duration)

        return [Hook("on_combat_start", hook, scope=HookScope.PER_HIT)]

    return build


def periodic_shield(interval: int = 600, frac: float = 0.15, duration: int = 600,
                    allies: bool = False) -> HookBuilder:
    """Re-shield the carrier (and adjacent allies if `allies`) every `interval`
    ticks (Guardian @6+ round-refresh). Reuses V.28 barriers."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        state = {"t": 0}

        def hook(ctx: Any, event: Any) -> None:
            if not owner.alive:
                return
            state["t"] += 1
            if state["t"] % interval == 0:
                ctx.grant_barrier(owner, frac * owner.max_hp, duration)
                if allies:
                    for a in _allies(ctx, owner):
                        if a is not owner and _dist(a, owner) <= 1:
                            ctx.grant_barrier(a, frac * a.max_hp, duration)

        return [Hook("on_tick", hook, scope=HookScope.PER_HIT)]

    return build


def attack_lifesteal(frac: float = 0.12) -> HookBuilder:
    """Heal the carrier for a fraction of basic-attack damage dealt (Bruiser).
    Team-safe at a TEAM rung."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            if event.attacker is not owner or not owner.alive:
                return
            if event.tag == SourceTag.BASIC_ATTACK.value:
                ctx.heal(owner, owner, frac * event.amount)

        return [Hook("on_damage_dealt", hook, scope=HookScope.PER_HIT)]

    return build


def high_hp_bonus(frac: float = 0.2, threshold: float = 0.6) -> HookBuilder:
    """Bonus damage when the carrier strikes a high-HP target (Stalker @5+).
    Only basic/ability hits trigger it (ITEM_PROC is skipped → no recursion)."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            if event.attacker is not owner or not owner.alive:
                return
            if event.tag not in (SourceTag.BASIC_ATTACK.value, SourceTag.ABILITY.value):
                return
            t = event.target
            if t.max_hp > 0 and t.hp / t.max_hp > threshold:
                ctx.deal_damage(owner, t, frac * owner.stat("strength"),
                                SourceTag.ITEM_PROC, damage_type="physical")

        return [Hook("on_damage_dealt", hook, scope=HookScope.PER_HIT)]

    return build


def mana_on_kill(frac_of_cost: float = 0.4) -> HookBuilder:
    """Refund mana to the carrier on a takedown (Stalker @5+)."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            if event.killer is not owner or not owner.alive or not owner.actives:
                return
            ctx.gain_mana(owner, frac_of_cost * owner.actives[0].cost)

        return [Hook("on_kill", hook, scope=HookScope.PER_HIT)]

    return build


def hexproof_after_kill(duration: int = 120) -> HookBuilder:
    """Brief hexproof window after the carrier scores a takedown (Stalker @7)."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            if event.killer is not owner or not owner.alive:
                return
            ctx.apply_status(owner, "hexproof", duration, source_id=owner.id)

        return [Hook("on_kill", hook, scope=HookScope.PER_HIT)]

    return build


def free_cast(every_n: int = 3) -> HookBuilder:
    """Every Nth cast refunds the carrier's mana, so the next ability is free
    (Channeler @4). Skipped while a recast is mid-flight."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        state = {"n": 0}

        def hook(ctx: Any, event: Any) -> None:
            if event.caster is not owner or not owner.alive or not owner.actives:
                return
            if getattr(ctx, "_in_recast", False):
                return
            state["n"] += 1
            if state["n"] % every_n == 0:
                ctx.gain_mana(owner, owner.actives[0].cost)

        return [Hook("on_cast_complete", hook, scope=HookScope.PER_HIT)]

    return build


def _recast(ctx: Any, owner: Piece, ability_id: str, potency: float = 1.0) -> None:
    """Re-run the carrier's just-finished ability once (Spirit/Channeler echo).
    Reuses `ctx.cast_ability`; a `ctx._in_recast` flag guards re-entry so an echo
    never echoes itself. `potency` (<1.0 for Spirit @8) scales the recast's damage
    via `ctx._echo_potency`, read in `deal_damage` (heals/shields stay full)."""
    if getattr(ctx, "_in_recast", False) or not owner.alive:
        return
    slot_idx = next((i for i, s in enumerate(owner.actives) if s.ability_id == ability_id), None)
    if slot_idx is None:
        return
    ctx._in_recast = True
    ctx._echo_potency = potency
    try:
        ctx.cast_ability(owner, slot_idx=slot_idx)
    finally:
        ctx._in_recast = False
        ctx._echo_potency = 1.0


def recast_first() -> HookBuilder:
    """The carrier's first cast each combat triggers a second time (Channeler @7)."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        state = {"used": False}

        def hook(ctx: Any, event: Any) -> None:
            if event.caster is not owner or state["used"] or getattr(ctx, "_in_recast", False):
                return
            state["used"] = True
            _recast(ctx, owner, event.ability_id)

        return [Hook("on_cast_complete", hook, scope=HookScope.PER_HIT)]

    return build


def echo_cadence(every_n: int = 4, potency: float = 1.0) -> HookBuilder:
    """Every Nth cast echoes — fires a second time (Spirit @5). Caster-gated, so
    team-safe at an apex rung (no-op for pieces with no ability). `potency` < 1.0
    (Spirit @8) makes the echo deal reduced damage."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        state = {"n": 0}

        def hook(ctx: Any, event: Any) -> None:
            if event.caster is not owner or getattr(ctx, "_in_recast", False):
                return
            state["n"] += 1
            if state["n"] % every_n == 0:
                _recast(ctx, owner, event.ability_id, potency=potency)

        return [Hook("on_cast_complete", hook, scope=HookScope.PER_HIT)]

    return build


def cast_shield_lowest(frac: float = 0.2, duration: int = 600) -> HookBuilder:
    """On cast, shield the carrier's lowest-HP ally (Warden)."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            if event.caster is not owner or not owner.alive:
                return
            allies = _allies(ctx, owner)
            if allies:
                target = min(allies, key=lambda a: (a.hp, a.id))
                ctx.grant_barrier(target, frac * target.max_hp, duration)

        return [Hook("on_cast", hook, scope=HookScope.PER_HIT)]

    return build


def slow_on_cast(duration: int = 300, stacks: int = 1, radius: int = 2) -> HookBuilder:
    """The carrier's casts slow nearby enemies (Trickster)."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            if event.caster is not owner or not owner.alive:
                return
            for e in _enemies(ctx, owner):
                if _dist(e, owner) <= radius:
                    ctx.apply_status(e, "slow", duration, stacks=stacks, source_id=owner.id)

        return [Hook("on_cast", hook, scope=HookScope.PER_HIT)]

    return build


def taunt_on_cast(duration: int = 300) -> HookBuilder:
    """The carrier's casts taunt the nearest enemy onto the caster (Trickster @3+).
    Reuses the T.28b `taunt` status the engine already honors."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            if event.caster is not owner or not owner.alive:
                return
            enemies = _enemies(ctx, owner)
            if enemies:
                target = min(enemies, key=lambda e: (_dist(e, owner), e.id))
                ctx.apply_status(target, "taunt", duration, source_id=owner.id)

        return [Hook("on_cast", hook, scope=HookScope.PER_HIT)]

    return build


def mana_denial_aura(interval: int = 100, amount: float = 5.0, radius: int = 1) -> HookBuilder:
    """Adjacent enemies regenerate mana slower — drain a little each cadence tick
    (Trickster @6)."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        state = {"t": 0}

        def hook(ctx: Any, event: Any) -> None:
            if not owner.alive:
                return
            state["t"] += 1
            if state["t"] % interval != 0:
                return
            for e in _enemies(ctx, owner):
                if _dist(e, owner) <= radius:
                    for slot in e.actives:
                        slot.current_mana = max(0.0, slot.current_mana - amount)

        return [Hook("on_tick", hook, scope=HookScope.PER_HIT)]

    return build


def heal_splash(frac: float = 0.3) -> HookBuilder:
    """A fraction of the carrier's heals splash to its lowest-HP other ally
    (Mender @1+). `ctx._in_heal_splash` guards the heal-fires-on_heal re-entry."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            if event.source is not owner or not owner.alive:
                return
            if getattr(ctx, "_in_heal_splash", False):
                return
            others = [a for a in _allies(ctx, owner) if a is not event.target]
            if not others:
                return
            ctx._in_heal_splash = True
            try:
                target = min(others, key=lambda a: (a.hp, a.id))
                ctx.heal(owner, target, frac * event.amount)
            finally:
                ctx._in_heal_splash = False

        return [Hook("on_heal", hook, scope=HookScope.PER_HIT)]

    return build


def overheal_shield(frac: float = 0.3, duration: int = 600, threshold: float = 0.95) -> HookBuilder:
    """When the carrier heals a near-full ally (the heal would overheal), bank it
    as a barrier instead (Mender @4). Reuses V.28 barriers."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            if event.source is not owner or not owner.alive:
                return
            t = event.target
            if t.max_hp > 0 and t.hp / t.max_hp >= threshold:
                ctx.grant_barrier(t, frac * event.amount, duration)

        return [Hook("on_heal", hook, scope=HookScope.PER_HIT)]

    return build


def on_death_spawn(stat_frac: float = 0.4, trait: str = "Swarm",
                   expires: int = 1200) -> HookBuilder:
    """On the carrier's death, leave a weak summon inheriting a fraction of its
    stats (Swarm chitin). Reuses the existing summon pattern (`Piece` + summon
    flags + `ctx.spawn`). `trait`-guarded so a TEAM-rung apply only spawns for
    actual carriers, not the whole team. Spawns don't spawn (`owner.summon`)."""
    _COMBAT_STATS = (
        "hp", "strength", "intelligence", "attack_speed",
        "move_speed", "mana_regen", "threat", "armor", "resistance",
        "attack_range", "penetration", "penetration_pct", "crit_chance",
    )

    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            if event.victim is not owner or owner.summon:
                return
            if trait not in owner.traits:
                return
            base = {k: owner.base_stats.get(k, 0.0) * stat_frac for k in _COMBAT_STATS}
            base["attack_range"] = max(1.0, base.get("attack_range", 1.0))
            base["crit_chance"] = 0.0
            hp = base.get("hp", 1.0)
            chitin = Piece(
                id=f"{owner.id}#chitin@{ctx.current_tick}",
                base_stats=base,
                affinity=owner.affinity,
                is_enemy=owner.is_enemy,
                hp=hp,
                max_hp=hp,
                summon=True,
                summon_owner_id=owner.id,
                summon_expires_tick=ctx.current_tick + expires,
            )
            ctx.spawn(chitin, owner.position_q, owner.position_r)

        return [Hook("on_death", hook, scope=HookScope.PER_HIT)]

    return build


# ===========================================================================
# T.28d — affinity @10 apex riders + Scaled/Spirit arms + deferred-flavor
# fold-ins. All RNG-free hook idioms (cadence / geometry / event-state).
# ===========================================================================


def crit_arc(frac: float = 0.5) -> HookBuilder:
    """On a crit, arc a fraction of the hit to one enemy adjacent to the struck
    target (Galvanized @10). ITEM_PROC → no re-fire/recursion."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            if event.attacker is not owner or not owner.alive or not event.is_crit:
                return
            target = event.target
            adj = [e for e in _enemies(ctx, owner)
                   if e is not target and _dist(e, target) <= 1]
            if adj:
                ctx.deal_damage(owner, adj[0], frac * event.amount,
                                SourceTag.ITEM_PROC, damage_type="magical")

        return [Hook("on_damage_dealt", hook, scope=HookScope.PER_HIT)]

    return build


def chill_attackers(duration: int = 200, stacks: int = 1) -> HookBuilder:
    """Whoever damages the carrier is slowed (Frostbound @10). Slow has no gate,
    so it lands even on cc_immune attackers; applies to the attacker, not self."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            if event.target is not owner or not owner.alive:
                return
            attacker = event.attacker
            if attacker is not None and attacker.alive and attacker.is_enemy != owner.is_enemy:
                ctx.apply_status(attacker, "slow", duration, stacks=stacks, source_id=owner.id)

        return [Hook("on_damage_taken", hook, scope=HookScope.PER_HIT)]

    return build


def burst_reduction(cap_frac: float = 0.25) -> HookBuilder:
    """Cap any single incoming hit at `cap_frac` of the carrier's max HP
    (Overcast @10 anti-burst). Reducing `on_damage_pre` hook, RNG-free."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any, value: float) -> float:
            if event.target is not owner or owner.max_hp <= 0:
                return value
            return min(value, cap_frac * owner.max_hp)

        return [Hook("on_damage_pre", hook, scope=HookScope.PER_HIT, priority=40)]

    return build


def kite_reward(frac: float = 0.15) -> HookBuilder:
    """Bonus damage when the carrier strikes an enemy that can't reach back —
    the target's attack_range is shorter than the current gap (Skyborn @3 kite
    reward). Basic/ability hits only (ITEM_PROC skipped → no recursion)."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            if event.attacker is not owner or not owner.alive:
                return
            if event.tag not in (SourceTag.BASIC_ATTACK.value, SourceTag.ABILITY.value):
                return
            t = event.target
            if t.stat("attack_range") < _dist(owner, t):
                ctx.deal_damage(owner, t, frac * owner.stat("strength"),
                                SourceTag.ITEM_PROC, damage_type="physical")

        return [Hook("on_damage_dealt", hook, scope=HookScope.PER_HIT)]

    return build


def ally_tidal(interval: int = 200, heal_frac: float = 0.015) -> HookBuilder:
    """Cadence-heal the carrier's lowest-HP ally a fraction of THAT ally's max HP
    (Tidekin @3). Distinct from `tidal_hot` (which heals the carrier itself)."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        state = {"t": 0}

        def hook(ctx: Any, event: Any) -> None:
            if not owner.alive:
                return
            state["t"] += 1
            if state["t"] % interval == 0:
                allies = _allies(ctx, owner)
                if allies:
                    target = min(allies, key=lambda a: (a.hp, a.id))
                    ctx.heal(owner, target, target.max_hp * heal_frac)

        return [Hook("on_tick", hook, scope=HookScope.PER_HIT)]

    return build


def cc_immunity(trait: str = "") -> HookBuilder:
    """Arm the carrier as hard-CC immune (Scaled @5+). Sets `Piece.cc_immune`; the
    `ctx.apply_status` guard then skips gate-bearing statuses (T.28d). `trait` guards
    a TEAM_WIDE apply to carriers only — CC-immunity is a signature defensive perk,
    not a team-wide grant; empty on a PER rung (every target is already a carrier)."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            if trait and trait not in owner.traits:
                return
            owner.cc_immune = True

        return [Hook("on_combat_start", hook, scope=HookScope.PER_HIT)]

    return build


def pierce_hexproof(trait: str = "") -> HookBuilder:
    """Arm the carrier to ignore HEXPROOF in single-target acquisition (Spirit @8,
    V.40). Sets `Piece.pierces_hexproof`, read by `targeting.py` + `_opponents`.
    `trait` guards a TEAM_WIDE apply to carriers only (a Spirit signature, not a
    team grant); empty on a PER rung."""
    def build(owner: Piece, sid: str) -> list[Hook]:
        def hook(ctx: Any, event: Any) -> None:
            if trait and trait not in owner.traits:
                return
            owner.pierces_hexproof = True

        return [Hook("on_combat_start", hook, scope=HookScope.PER_HIT)]

    return build
