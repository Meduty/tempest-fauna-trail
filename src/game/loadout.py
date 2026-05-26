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

from src.game.effects import EffectBundle, EventBus, Hook, Modifier, Lifetime
from src.game.models import Champion, Enemy, WeatherState
from src.game.piece import ActiveSlot, Piece
from src.game.registries import ABILITY_REGISTRY, PASSIVE_REGISTRY
from src.game.status import StatusInstance
from src.game import abilities as _abilities  # noqa: F401 — triggers @register decorators

DEFAULT_ABILITY_COST = 36_000


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
        # Look up cost from registry meta if available
        target.actives.append(ActiveSlot(
            ability_id=ability_id,
            cost=DEFAULT_ABILITY_COST,
        ))

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
        is_enemy=False,
        passives=[champion.passive_ability] if champion.passive_ability else [],
    )
    # Set up active ability slot (0 starting mana by default)
    if champion.active_ability:
        piece.actives.append(ActiveSlot(
            ability_id=champion.active_ability,
            cost=champion.ability_cost,
            current_mana=0.0,
        ))
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
        is_enemy=True,
        passives=[enemy.passive_ability] if enemy.passive_ability else [],
    )
    # Set up active ability slot
    if enemy.active_ability:
        piece.actives.append(ActiveSlot(
            ability_id=enemy.active_ability,
            cost=enemy.ability_cost,
            current_mana=0.0,
        ))
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


def compile_loadout(
    team: list[Champion],
    enemies: list[Enemy],
    weather: WeatherState,
    seed: int = 42,
) -> tuple[list[Piece], EventBus]:
    """Compile team and enemies into combat-ready Pieces with an EventBus.

    Returns (pieces, bus) ready for CombatContext.
    """
    bus = EventBus()

    # 1. Build pieces from models
    pieces: list[Piece] = []
    for champ in team:
        pieces.append(piece_from_champion(champ))
    for enemy in enemies:
        pieces.append(piece_from_enemy(enemy))

    # 7. Apply champion passive bundles
    for piece in pieces:
        for passive_id in piece.passives:
            if passive_id and passive_id in PASSIVE_REGISTRY:
                factory = PASSIVE_REGISTRY[passive_id]
                bundle = factory(piece)
                if bundle:
                    apply_bundle(piece, bundle, bus)

    return pieces, bus
