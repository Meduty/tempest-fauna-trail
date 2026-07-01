"""Loadout compiler — the isolation boundary (T20).

This is the ONLY module that imports both content registries and combat types.
It compiles a team + enemies into combat-ready Pieces and an EventBus.

Currently implements:
1. Build Pieces from Champion/Enemy models (fresh instances, not deep-copies of Run state)
2. Apply champion/enemy passive bundles

Full application order (items, traits, augments, boss phase-1 passives, etc.) is
planned per effect_systems_design.md §10.1 and will be added as those systems are built.
"""

from __future__ import annotations

from typing import Any

from src.game.effects import EffectBundle, EventBus, Modifier, Lifetime
from src.game.models import Champion, Enemy, WeatherState
from src.game.piece import ActiveSlot, Piece
from src.game.registries import (
    PASSIVE_REGISTRY,
    ability_mana,
)
from src.game.rng import SeededRng
from src.game.status import StatusInstance
from src.game.weather_effects import CombatModifier, WEATHER_BUFF_BASE, combat_modifier
from src.game import abilities as _abilities  # noqa: F401 — triggers @register decorators


# Player deployment zone — columns 0..ALLIED_ZONE_MAX_Q-1 (cols 0–2), matching the
# T.24 enemy-formation player half (player 0–2 / enemy 7–9). The Prep view confines
# hand-placement to this zone (V.68); the V.62 engine guard underneath still checks
# on-board / no-dup / known-piece across both sides.
ALLIED_ZONE_MAX_Q = 3


def validate_team_positions(
    team: list[Champion],
    positions: dict[str, tuple[int, int]],
    *,
    zone_max_q: int = ALLIED_ZONE_MAX_Q,
) -> None:
    """Validate a Prep hand-placement (champion_id → (q, r)) **team-only** (V.68).

    A team-only superset of the V.62 engine guard: it additionally knows which
    pieces are the player's (roster ids) and confines them to the allied
    deployment zone. Raises ``ValueError`` unless **every key names a champion in
    ``team``**, **every cell is in-zone** (``0 <= q < zone_max_q``,
    ``0 <= r < BOARD_HEIGHT``), and **no two share a cell**. Empty ``positions``
    (Auto-Place) passes — combat then uses the default formation (byte-identical,
    V.2). Call before building the ``CombatSession``; the engine re-checks
    on-board/no-dup/known-piece for both sides under V.62.
    """
    from src.game.combat.engine import BOARD_HEIGHT

    team_ids = {champion.id for champion in team}
    seen: dict[tuple[int, int], str] = {}
    for champ_id, cell in positions.items():
        if champ_id not in team_ids:
            raise ValueError(
                f"team_positions[{champ_id!r}] names no champion on the team "
                f"(roster ids: {sorted(team_ids)})."
            )
        q, r = cell
        if not (0 <= q < zone_max_q):
            raise ValueError(
                f"team_positions[{champ_id!r}] = ({q},{r}) is outside the allied "
                f"deployment zone (columns 0..{zone_max_q - 1})."
            )
        if not (0 <= r < BOARD_HEIGHT):
            raise ValueError(
                f"team_positions[{champ_id!r}] = ({q},{r}) row is off-board "
                f"(0..{BOARD_HEIGHT - 1})."
            )
        if cell in seen:
            raise ValueError(
                f"team_positions: {champ_id!r} and {seen[cell]!r} both placed on "
                f"cell ({q},{r})."
            )
        seen[cell] = champ_id


def make_slot(ability_id: str) -> ActiveSlot:
    """Build an `ActiveSlot` seeded from the ability's `ABILITY_MANA` statline
    (V.48, T.29c). Cost/cap/start/priority are authored on the ability def, not
    the piece. `current_mana` is seeded from `start_mana` at combat start."""
    m = ability_mana(ability_id)
    slot = ActiveSlot(
        ability_id=ability_id,
        mana_cost=m.mana_cost,
        max_mana=m.max_mana,
        start_mana=m.start_mana,
        priority=m.priority,
    )
    # Combat-start fill (V.48). Start-mana items (T.29d) bump start_mana then
    # re-seed; default start_mana=0 ⇒ current_mana=0 (byte-identical anchor).
    slot.current_mana = float(min(slot.max_mana, slot.start_mana))
    return slot


_HEARTWOOD_MULT = 1.5  # D.21 MVP: Glimmerdust upgrades an item's modifiers ×1.5


def _heartwood_scale(bundle: EffectBundle) -> EffectBundle:
    """Scale a bundle's stat modifiers for a Heartwood (Glimmerdust) upgrade —
    `mul` bonus and `add` value ×1.5; hooks/procs/granted_traits untouched (D.21)."""
    import dataclasses

    scaled = []
    for m in bundle.modifiers:
        if m.op == "mul":
            value = 1.0 + (m.value - 1.0) * _HEARTWOOD_MULT
        elif m.op == "add":
            value = m.value * _HEARTWOOD_MULT
        else:
            value = m.value
        scaled.append(Modifier(m.stat, m.op, value, m.lifetime, m.source_id, m.expires_at_tick))
    return dataclasses.replace(bundle, modifiers=scaled)


def apply_bundle(
    target: Piece,
    bundle: EffectBundle,
    bus: EventBus,
    ctx: Any = None,
) -> None:
    """Apply an EffectBundle to a target piece.

    Same function used by compile_loadout (pre-combat) and
    ctx.register_bundle (mid-combat, e.g. boss phase hook).
    """
    for trait_id in bundle.granted_traits:
        if trait_id not in target.traits:
            target.traits.append(trait_id)

    for mod in bundle.modifiers:
        target.modifiers.append(mod)

    for status_id, duration in bundle.statuses:
        if ctx:
            ctx.apply_status(target, status_id, duration)
        else:
            target.statuses.append(StatusInstance(
                status_id=status_id,
                remaining_ticks=duration,
            ))

    for ability_id in bundle.granted_abilities:
        target.actives.append(make_slot(ability_id))

    for hook in bundle.hooks:
        bus.subscribe(hook)


def piece_from_champion(champion: Champion) -> Piece:
    """Build a Piece from a Champion model for combat."""
    piece = Piece(
        id=champion.id,
        base_stats={
            "hp": float(champion.max_hp),
            "strength": float(champion.strength),
            "intelligence": float(champion.intelligence),
            "attack_speed": float(champion.attack_speed),
            "move_speed": float(champion.move_speed),
            "mana_regen": float(champion.mana_regen),
            "threat": float(champion.threat),
            "armor": float(champion.armor),
            "resistance": float(champion.resistance),
            "attack_range": float(champion.attack_range),
            "crit_chance": champion.crit_chance,
            "penetration": float(champion.penetration),
            "penetration_pct": champion.penetration_pct,
        },
        affinity=champion.affinity,
        traits=list(champion.traits),
        role=champion.role,
        is_enemy=False,
        level=champion.level,
        passives=[champion.passive_ability] if champion.passive_ability else [],
        items=list(champion.items),
    )
    # One ActiveSlot per ability (T.29d, V.49) — mana statline from the ability
    # def (V.48). Single-ability champs ⇒ one slot ⇒ byte-identical.
    for ability_id in champion.active_abilities:
        piece.actives.append(make_slot(ability_id))
    # Set HP
    piece.hp = float(champion.max_hp)
    piece.max_hp = float(champion.max_hp)
    return piece


def piece_from_enemy(enemy: Enemy) -> Piece:
    """Build a Piece from an Enemy model for combat."""
    piece = Piece(
        id=enemy.id,
        base_stats={
            "hp": float(enemy.max_hp),
            "strength": float(enemy.strength),
            "intelligence": float(enemy.intelligence),
            "attack_speed": float(enemy.attack_speed),
            "move_speed": float(enemy.move_speed),
            "mana_regen": float(enemy.mana_regen),
            "threat": float(enemy.threat),
            "armor": float(enemy.armor),
            "resistance": float(enemy.resistance),
            "attack_range": float(enemy.attack_range),
            "crit_chance": enemy.crit_chance,
            "penetration": float(enemy.penetration),
            "penetration_pct": enemy.penetration_pct,
        },
        affinity=enemy.affinity,
        traits=[],
        role=enemy.role,
        is_enemy=True,
        level=enemy.level,
        passives=[enemy.passive_ability] if enemy.passive_ability else [],
    )
    # One ActiveSlot per ability (T.29d, V.49). Enemies may field >1 slot.
    for ability_id in enemy.active_abilities:
        piece.actives.append(make_slot(ability_id))
    # Set HP
    piece.hp = float(enemy.max_hp)
    piece.max_hp = float(enemy.max_hp)
    return piece


def attach_map_effect(effect_id: str, ctx: Any, seed: int) -> Any:
    """Instantiate and register a MapEffect with a CombatContext.

    This is the canonical wiring call for boss fights. Call it AFTER building
    CombatContext and BEFORE calling combat/loop.run(ctx). The map effect will
    subscribe its hooks to ctx.bus and write initial state to ctx.board_state
    when on_combat_start fires inside run().

    ctx is duck-typed — CombatContext is not imported here (isolation rule).
    loadout.py is the designated cross-boundary module (content ↔ combat).

    Args:
        effect_id: Map effect id from BossEncounterResult.map_effect_id.
        ctx:       A CombatContext (or any object exposing .board_state + .bus).
        seed:      Deterministic seed for the effect's internal RNG.
                   Use derive_seed(run_seed, node_index, CH_BOSS) for boss fights.

    Returns:
        The registered MapEffect instance (retained if the caller needs it).
    """
    from src.game.map_effects import build_map_effect

    effect = build_map_effect(effect_id, ctx.board_state, seed)
    effect.register(ctx.bus)
    return effect


def _weather_modifiers(modifier: CombatModifier, weather: WeatherState) -> list[Modifier]:
    """Translate a Weather Favor `CombatModifier` into source-tagged `Modifier`s (V.42).

    Each `*_mult ≠ 1.0` → a `("<stat>","mul",mult)`; `attack_range_delta ≠ 0` →
    a `("attack_range","add",delta)`. All tagged `source_id="weather:<state>"` so
    the contribution is attributable (V.45 `stat_breakdown`). `CLEAR`/IDENTITY →
    no modifiers (inert).
    """
    src = f"weather:{weather.value}"
    mods: list[Modifier] = []
    for stat, mult in (
        ("hp", modifier.hp_mult),
        ("strength", modifier.str_mult),
        ("intelligence", modifier.int_mult),
        ("attack_speed", modifier.as_mult),
        ("move_speed", modifier.ms_mult),
        ("mana_regen", modifier.mr_mult),
        ("threat", modifier.thr_mult),
        ("armor", modifier.armor_mult),
        ("resistance", modifier.res_mult),
    ):
        if mult != 1.0:
            mods.append(Modifier(stat, "mul", mult, Lifetime.COMBAT, src))
    if modifier.attack_range_delta:
        mods.append(
            Modifier("attack_range", "add", float(modifier.attack_range_delta), Lifetime.COMBAT, src)
        )
    return mods


def _apply_weather_to_piece(piece: Piece, weather: WeatherState, bus: EventBus) -> None:
    """Apply Weather Favor as `source="weather:<state>"` modifiers (V.42).

    Weather is **no longer folded into `base_stats`** — it composes through
    `compute_stat` `(base+Σadds)×Πmuls` like every other modifier source, so it is
    uniformly attributable (`stat_breakdown`, V.45) and scales item/augment adds.
    Resources are reconciled afterwards (`max_hp`/`hp` from `stat("hp")`), never
    `Modifier`'d directly (V.43). `attack_range` underflow is caught by the
    `_STAT_FLOORS` clamp in `compute_stat` (≥ 1), replacing the old inline `max(1,…)`.

    Scaled @8 (T.28d): a `weather_favored` piece always gets the favorable buff
    pack regardless of affinity (`CLEAR` stays inert → IDENTITY → no modifiers).
    The flag is set by `mark_weather_overrides` before this runs.
    """
    if piece.weather_favored:
        modifier = WEATHER_BUFF_BASE[weather]
    else:
        modifier = combat_modifier(piece.affinity, weather)

    mods = _weather_modifiers(modifier, weather)
    if mods:
        apply_bundle(piece, EffectBundle(modifiers=mods), bus)

    # Resource reconcile (V.43): pieces start each combat at full HP; seed
    # max_hp/hp from stat("hp") now that the weather hp mul (if any) is in place.
    new_max_hp = max(1.0, piece.stat("hp"))
    piece.max_hp = new_max_hp
    piece.hp = new_max_hp


def compile_loadout(
    team: list[Champion],
    enemies: list[Enemy],
    weather: WeatherState,
    seed: int = 42,
    run_mods: Any = None,
) -> tuple[list[Piece], EventBus, list[tuple[str, int, int]]]:
    """Compile team and enemies into combat-ready Pieces with an EventBus.

    Returns (pieces, bus, trait_activations) ready for CombatContext.
    trait_activations is the cleared player-team trait breakpoints (T.28a),
    surfaced for the BattleResult record.

    `run_mods` (a `RunModifiers`, T.31) threads active augments: TEAM/PIECE bundles
    apply at step 6 (after traits/items), quest trackers wire at step 9. `None`
    leaves every non-augment caller byte-for-byte unchanged (V.2/V.18).
    """
    from src.game.bosses.data import BOSS_DEFS
    _boss_defs_by_id = {boss.id: boss for boss in BOSS_DEFS.values()}

    bus = EventBus()

    # 1. Build pieces from models
    pieces: list[Piece] = []
    for champ in team:
        pieces.append(piece_from_champion(champ))
    for enemy in enemies:
        pieces.append(piece_from_enemy(enemy))

    # 1b. Uniquify duplicate piece ids (B.65). Encounters routinely field several
    # enemies of the same type (and challenge squads reuse champion ids), so
    # `piece.id` (= the def id) collides across twins. Combat resolves by object
    # identity so the fight itself is unaffected, but the recorded event stream,
    # the per-id damage tallies, and the combat view's control keys (`tok-`/`mp-`/
    # `hp-`/`st-`) all key on the string id — collisions made the view animate one
    # piece's bars/FX between its twins ("glitching from piece to piece") and drew
    # swooshes from the wrong twin. Suffix the 2nd+ occurrence deterministically
    # (assembly order ⇒ reproducible, V.2), before any hook closes over the piece.
    _seen: dict[str, int] = {}
    for piece in pieces:
        n = _seen.get(piece.id, 0)
        _seen[piece.id] = n + 1
        if n:
            piece.id = f"{piece.id}#{n}"

    # 2. Apply Weather Favor as source="weather:<state>" modifiers (V.42). First
    # mark Scaled @8 carriers so their weather is overridden to the favorable pack
    # (T.28d — resolved before step 2 so the weather modifiers land ahead of the
    # trait bundles in step 3).
    from src.game.traits import mark_weather_overrides
    mark_weather_overrides(pieces)
    for piece in pieces:
        _apply_weather_to_piece(piece, weather, bus)

    # 2.5 Apply item bundles (T.29a, V.23). Item granted_traits (T.29b emblems)
    # must land here, before step 3, so emblem wearers count toward Kinship
    # breakpoints during trait resolution.  Champions build their piece.items list
    # in piece_from_champion above; enemies carry no items (plan §scope).
    from src.game.registries import ITEM_REGISTRY
    import src.game.items  # noqa: F401 — side-effect: populates ITEM_REGISTRY
    from src.game.items.special import HEARTWOOD_PREFIX
    for piece in pieces:
        for item_id in piece.items:
            base_id = item_id
            heartwood = item_id.startswith(HEARTWOOD_PREFIX)
            if heartwood:
                base_id = item_id[len(HEARTWOOD_PREFIX):]
            factory = ITEM_REGISTRY.get(base_id)
            if factory is not None:
                bundle = factory(piece)
                if bundle is not None:
                    if heartwood:
                        bundle = _heartwood_scale(bundle)  # D.21 MVP: ×1.5 modifiers
                    apply_bundle(piece, bundle, bus)

    # 3. Resolve + apply synergy trait breakpoints (player team only — V.22).
    # Slots between weather (step 2) and passives (step 7); §10.1 order. Item
    # `granted_traits` (T.29) will apply just before this so emblems are counted.
    # Augment Crest/Crown/Worldroot bonuses (T.31) inject virtual carriers here.
    from src.game.traits import resolve_and_apply_traits
    bonus_counts = None
    if run_mods is not None and getattr(run_mods, "augment_state", None):
        bonus_counts = run_mods.augment_state.get("trait_bonus")
    trait_activations = resolve_and_apply_traits(pieces, bus, bonus_counts)

    # 3.5 Flag pieces with no active synergy breakpoint (augment Built Different
    # filter, T.31). `_has_active_synergy` is True if the piece carries any tag
    # that cleared a breakpoint this combat.
    _active_tags = {tag for tag, _c, _t in trait_activations}
    from src.game.traits import _piece_tags
    for piece in pieces:
        if piece.is_enemy:
            continue
        piece._has_active_synergy = bool(_active_tags & set(_piece_tags(piece)))

    # 6. Apply active augment bundles (T.31, V.18) — TEAM/PIECE handlers rebuild
    # fresh each combat from run_mods.augments; PIECE-filtered then TEAM. Sits after
    # traits/items so augments are the loudest layer (§10.1). RUN augments already
    # mutated Run at pick time. `run_mods=None` ⇒ no-op (back-compat).
    if run_mods is not None:
        import src.game.augments as _augments  # noqa: F401 — populates AUGMENT_REGISTRY
        _augments.apply_run_augments(pieces, bus, run_mods)
        # Re-seed team max_hp/hp so augment `hp` muls actually bite: the engine
        # reads the cached `max_hp`/`hp` fields, not `stat("hp")` (same reason the
        # weather + trait passes resync). Augments touch the player team only
        # (V.22). Gated on run_mods so the non-augment path stays byte-identical.
        for piece in pieces:
            if not piece.is_enemy:
                new_hp = max(1.0, piece.stat("hp"))
                piece.max_hp = new_hp
                piece.hp = new_hp

    # 7. Apply champion/enemy passive bundles
    for piece in pieces:
        for passive_id in piece.passives:
            if passive_id and passive_id in PASSIVE_REGISTRY:
                factory = PASSIVE_REGISTRY[passive_id]
                bundle = factory(piece)
                if bundle:
                    apply_bundle(piece, bundle, bus)

    # 8. Apply boss-specific phase hook and on-death hook.
    # BossDef.build_enemy() only carries phase1_passive; the phase transition
    # hook and on-death hook must be wired separately so they are subscribed
    # at combat start and fire correctly during a real encounter.
    for piece in pieces:
        if piece.id in _boss_defs_by_id:
            boss_def = _boss_defs_by_id[piece.id]
            for extra_id in (boss_def.phase1_phase_hook, boss_def.on_death_hook):
                if extra_id and extra_id in PASSIVE_REGISTRY:
                    factory = PASSIVE_REGISTRY[extra_id]
                    bundle = factory(piece)
                    if bundle:
                        apply_bundle(piece, bundle, bus)

    # 9. Wire active quest trackers as Run-level bus subscribers (T.31, §9.3).
    # No-op unless run_mods carries a live Run (pure sims pass None).
    if run_mods is not None:
        import src.game.augments as _augments  # noqa: F401
        _augments.wire_quest_trackers(bus, run_mods)

    # Tie-break setup (V.34): formation_index = input order (enemy formation key);
    # load_order = a seeded, side-independent permutation (NOT team-block-then-enemy)
    # so same-tick AS ties resolve fairly — never systematically toward the team.
    order = list(range(len(pieces)))
    SeededRng(seed).shuffle(order)
    for index, piece in enumerate(pieces):
        piece.formation_index = index
        piece.load_order = order[index]

    return pieces, bus, trait_activations
