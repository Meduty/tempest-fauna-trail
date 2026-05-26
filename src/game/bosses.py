"""Boss encounter data (T21) — authored set-piece boss fights.

Each boss is a Tier-10 piece with:
- Two-phase kit (phase hook grants +1 active, +1 passive at 50% HP)
- Fixed supporting cast (with some add variation via seed)
- An authored map effect
- An on-death hook

Depends: T19 (seed channels), T20 (effect/hook framework), map_effects.py.
No Flet imports (V.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final

from src.game.effects import EffectBundle, Hook, HookScope, Modifier, Lifetime, SourceTag
from src.game.events import DamageEvent, DeathEvent, PhaseEvent
from src.game.models import WeatherState
from src.game.scaling import power


# ---------------------------------------------------------------------------
# Boss definition dataclass
# ---------------------------------------------------------------------------


@dataclass
class BossDef:
    """Static definition of a boss encounter."""
    id: str
    name: str
    affinity: WeatherState
    stage: int  # 1-6
    tier: int  # Always 10
    # Axis composition (like EnemyDef)
    primary_stat: str
    range_: str
    durability: str
    playstyle: str
    speed: str
    # Abilities
    phase1_active: str
    phase1_passive: str
    phase2_active: str
    phase2_passive: str
    # Map effect
    map_effect_id: str
    # Supporting cast (list of (enemy_id, count) tuples)
    # The actual adds drawn are varied slightly by seed
    supporting_cast: list[tuple[str, int]]
    # Add pool for variation (if non-empty, some adds are drawn from here)
    add_variation_pool: list[str] = field(default_factory=list)
    add_variation_count: int = 0  # how many adds to replace from the pool
    # On-death hook id
    on_death_hook: str = ""
    # Tags
    tags: frozenset[str] = field(default_factory=lambda: frozenset({"human", "machine"}))
    # Stat overrides
    stat_overrides: dict[str, int] = field(default_factory=dict)
    # Budget
    total_budget: float = 0.0


# ---------------------------------------------------------------------------
# Boss power budgets (authored, tunable)
# ---------------------------------------------------------------------------

BOSS_BUDGETS: Final[dict[int, float]] = {
    1: 6.0,    # Holloway
    2: 15.0,   # Vance
    3: 28.0,   # Strand
    4: 42.0,   # Vossberg
    5: 60.0,   # Crège
    6: 90.0,   # Iron Emperor
}

# Challenge team sizes per stage (§2.2 confirmed)
CHALLENGE_TEAM_SIZES: Final[dict[int, int]] = {
    1: 4,
    2: 5,
    3: 7,
    4: 8,
    5: 9,
    6: 11,
}

# Challenge budget multiplier
CHALLENGE_BUDGET_MULT: Final[float] = 1.3

# Challenge reward: Amber = 2 × stage_index
CHALLENGE_AMBER_MULT: Final[int] = 2

# ---------------------------------------------------------------------------
# The six bosses
# ---------------------------------------------------------------------------

BOSS_DEFS: dict[int, BossDef] = {
    1: BossDef(
        id="boss_holloway",
        name="Foundry-Lord Holloway",
        affinity=WeatherState.CLEAR,
        stage=1,
        tier=10,
        primary_stat="str",
        range_="melee",
        durability="tanky_arm",
        playstyle="hybrid",
        speed="heavy",
        phase1_active="holloway_pressure_vent",
        phase1_passive="holloway_stoke_fires",
        phase2_active="holloway_magma_heave",
        phase2_passive="holloway_cinder_husk",
        map_effect_id="spawn_rifts",
        supporting_cast=[
            ("enemy_heavy_knight", 2),
            ("enemy_steam_engineer", 2),
            ("enemy_conscript", 4),
        ],
        add_variation_pool=["enemy_conscript", "enemy_levyman", "enemy_picket"],
        add_variation_count=2,
        on_death_hook="holloway_on_death",
        tags=frozenset({"human", "machine"}),
        total_budget=BOSS_BUDGETS[1],
    ),
    2: BossDef(
        id="boss_vance",
        name="Solar Overseer Vance",
        affinity=WeatherState.MIST,
        stage=2,
        tier=10,
        primary_stat="int",
        range_="ranged",
        durability="standard",
        playstyle="ability",
        speed="neutral",
        phase1_active="vance_focusing_lens",
        phase1_passive="vance_glare",
        phase2_active="vance_sunflare_pounce",
        phase2_passive="vance_drought_aura",
        map_effect_id="fog",
        supporting_cast=[
            ("enemy_battlemage", 2),
            ("enemy_company_captain", 1),
            ("enemy_picket", 4),
        ],
        add_variation_pool=["enemy_picket", "enemy_crossbow_levy", "enemy_field_medic"],
        add_variation_count=2,
        on_death_hook="vance_on_death",
        tags=frozenset({"human"}),
        total_budget=BOSS_BUDGETS[2],
    ),
    3: BossDef(
        id="boss_strand",
        name="Grid-Director Strand",
        affinity=WeatherState.THUNDER,
        stage=3,
        tier=10,
        primary_stat="int",
        range_="ranged",
        durability="squishy",
        playstyle="ability",
        speed="speedy",
        phase1_active="strand_arc_cascade",
        phase1_passive="strand_overcharged",
        phase2_active="strand_thunderhead",
        phase2_passive="strand_stormform",
        map_effect_id="hazard_tiles",
        supporting_cast=[
            ("enemy_arcanist", 2),
            ("enemy_riflemaster", 1),
            ("enemy_capture_rig_wolf", 3),
        ],
        add_variation_pool=["enemy_capture_rig_wolf", "enemy_stormhawk", "enemy_voltaic_diviner"],
        add_variation_count=1,
        on_death_hook="strand_on_death",
        tags=frozenset({"human", "machine"}),
        total_budget=BOSS_BUDGETS[3],
    ),
    4: BossDef(
        id="boss_vossberg",
        name="Clearance-Marshal Vossberg",
        affinity=WeatherState.CLOUDY,
        stage=4,
        tier=10,
        primary_stat="str",
        range_="melee",
        durability="standard",
        playstyle="auto",
        speed="speedy",
        phase1_active="vossberg_scorched_advance",
        phase1_passive="vossberg_no_quarter",
        phase2_active="vossberg_wildfire_leap",
        phase2_passive="vossberg_feeding_frenzy",
        map_effect_id="ley_cells",
        supporting_cast=[
            ("enemy_lord_commander", 1),
            ("enemy_gunslinger", 2),
            ("enemy_conscript", 4),
        ],
        add_variation_pool=["enemy_conscript", "enemy_levyman", "enemy_pikeman"],
        add_variation_count=2,
        on_death_hook="vossberg_on_death",
        tags=frozenset({"human", "machine"}),
        total_budget=BOSS_BUDGETS[4],
    ),
    5: BossDef(
        id="boss_crege",
        name="Dredge-Admiral Crège",
        affinity=WeatherState.RAIN,
        stage=5,
        tier=10,
        primary_stat="str",
        range_="ranged",
        durability="standard",
        playstyle="hybrid",
        speed="neutral",
        phase1_active="crege_harpoon_winch",
        phase1_passive="crege_dredged_depths",
        phase2_active="crege_maelstrom_jaws",
        phase2_passive="crege_drowning_tide",
        map_effect_id="flood_lanes",
        supporting_cast=[
            ("enemy_iron_maiden", 1),
            ("enemy_cannoneer", 2),
            ("enemy_blight_lurker", 3),
        ],
        add_variation_pool=["enemy_blight_lurker", "enemy_brineblight_berserker", "enemy_dredge_hulk"],
        add_variation_count=1,
        on_death_hook="crege_on_death",
        tags=frozenset({"human", "machine"}),
        total_budget=BOSS_BUDGETS[5],
    ),
    6: BossDef(
        id="boss_iron_emperor",
        name="The Iron Emperor",
        affinity=WeatherState.SNOW,
        stage=6,
        tier=10,
        primary_stat="hybrid",
        range_="ranged",
        durability="tanky_hp",
        playstyle="hybrid",
        speed="heavy",
        phase1_active="emperor_decree_of_iron",
        phase1_passive="emperor_tribute",
        phase2_active="emperor_reclamation",
        phase2_passive="emperor_wound_spreads",
        map_effect_id="collapsing_arena",
        supporting_cast=[
            ("enemy_archmagus_imperator", 2),
            ("enemy_hierarch", 2),
            ("enemy_conscript", 3),
        ],
        add_variation_pool=["enemy_conscript", "enemy_levyman", "enemy_pikeman", "enemy_picket"],
        add_variation_count=2,
        on_death_hook="emperor_on_death",
        tags=frozenset({"human", "machine", "corrupted"}),
        total_budget=BOSS_BUDGETS[6],
    ),
}


# ---------------------------------------------------------------------------
# Boss phase hook factory
# ---------------------------------------------------------------------------


def make_boss_phase_hook(boss_def: BossDef) -> callable:
    """Create a passive factory that registers the boss phase-2 hook.

    Returns a factory (owner) -> EffectBundle per the passive system contract.
    The hook fires ONCE_PER_COMBAT when the boss drops below 50% HP.
    """
    def phase_hook_factory(owner: Any) -> EffectBundle:
        def _on_damage_taken(ctx: Any, event: DamageEvent) -> None:
            if event.target is not owner:
                return
            if not owner.alive:
                return
            hp_pct = owner.hp / owner.max_hp if owner.max_hp > 0 else 1.0
            if hp_pct >= 0.50:
                return
            # Grant phase 2 abilities
            from src.game.piece import ActiveSlot
            owner.actives.append(ActiveSlot(
                ability_id=boss_def.phase2_active,
                cost=36_000,
                priority=10,
            ))
            owner.passives.append(boss_def.phase2_passive)
            # Register phase 2 passive bundle if available
            from src.game.registries import PASSIVE_REGISTRY
            p2_factory = PASSIVE_REGISTRY.get(boss_def.phase2_passive)
            if p2_factory:
                ctx.register_bundle(owner, p2_factory(owner))
            # Fire phase change event
            ctx.fire("on_phase_change", PhaseEvent(piece=owner, new_phase=2))

        return EffectBundle(
            hooks=[Hook(
                event="on_damage_taken",
                handler=_on_damage_taken,
                scope=HookScope.ONCE_PER_COMBAT,
                priority=100,
            )],
        )

    return phase_hook_factory


# ---------------------------------------------------------------------------
# Boss on-death hook factories
# ---------------------------------------------------------------------------


def _holloway_on_death_factory(owner: Any) -> EffectBundle:
    """Holloway: delayed AOE detonation after death."""
    def _on_death(ctx: Any, event: DeathEvent) -> None:
        if event.victim is not owner:
            return
        # Deal AOE damage to all pieces near the boss's last position
        for piece in ctx.living_pieces():
            if piece is owner:
                continue
            from src.game.combat.context import hex_distance
            dist = hex_distance(
                piece.position_q, piece.position_r,
                owner.position_q, owner.position_r,
            )
            if dist <= 2:
                ctx.deal_damage(owner, piece, 30.0, SourceTag.TRUE)

    return EffectBundle(
        hooks=[Hook(
            event="on_death",
            handler=_on_death,
            scope=HookScope.ONCE_PER_COMBAT,
            priority=50,
        )],
    )


def _vance_on_death_factory(owner: Any) -> EffectBundle:
    """Vance: Sun-Husk collapses, briefly heals player team."""
    def _on_death(ctx: Any, event: DeathEvent) -> None:
        if event.victim is not owner:
            return
        # Heal all player pieces for a small amount
        for piece in ctx.living_pieces():
            if not piece.is_enemy:
                ctx.heal(owner, piece, 20.0)

    return EffectBundle(
        hooks=[Hook(
            event="on_death",
            handler=_on_death,
            scope=HookScope.ONCE_PER_COMBAT,
            priority=50,
        )],
    )


def _strand_on_death_factory(owner: Any) -> EffectBundle:
    """Strand: uncontrolled lightning strike at boss tile, damages adjacent."""
    def _on_death(ctx: Any, event: DeathEvent) -> None:
        if event.victim is not owner:
            return
        from src.game.combat.context import hex_distance
        for piece in ctx.living_pieces():
            dist = hex_distance(
                piece.position_q, piece.position_r,
                owner.position_q, owner.position_r,
            )
            if dist <= 1:
                ctx.deal_damage(owner, piece, 40.0, SourceTag.TRUE)

    return EffectBundle(
        hooks=[Hook(
            event="on_death",
            handler=_on_death,
            scope=HookScope.ONCE_PER_COMBAT,
            priority=50,
        )],
    )


def _vossberg_on_death_factory(owner: Any) -> EffectBundle:
    """Vossberg: burning tiles extinguish — remove hazard modifiers."""
    def _on_death(ctx: Any, event: DeathEvent) -> None:
        if event.victim is not owner:
            return
        # Clear any hazard/ley modifiers from the board (narrative: fire goes out)
        if hasattr(ctx, '_board_state'):
            ctx._board_state.remove_by_owner("map_effect:ley_cells")

    return EffectBundle(
        hooks=[Hook(
            event="on_death",
            handler=_on_death,
            scope=HookScope.ONCE_PER_COMBAT,
            priority=50,
        )],
    )


def _crege_on_death_factory(owner: Any) -> EffectBundle:
    """Crège: Leviathan sinks, silt drains, board clears of slow."""
    def _on_death(ctx: Any, event: DeathEvent) -> None:
        if event.victim is not owner:
            return
        # Remove slow status from all player pieces
        for piece in ctx.living_pieces():
            if not piece.is_enemy and piece.has_status("slow"):
                ctx.remove_status(piece, "slow")

    return EffectBundle(
        hooks=[Hook(
            event="on_death",
            handler=_on_death,
            scope=HookScope.ONCE_PER_COMBAT,
            priority=50,
        )],
    )


def _emperor_on_death_factory(owner: Any) -> EffectBundle:
    """Iron Emperor: the World-Engine goes dark. Board collapses stop.

    The corrupted elements settle — a quiet narrative beat.
    """
    def _on_death(ctx: Any, event: DeathEvent) -> None:
        if event.victim is not owner:
            return
        # Stop the collapsing arena
        if hasattr(ctx, '_board_state'):
            ctx._board_state.remove_by_owner("map_effect:collapsing_arena")

    return EffectBundle(
        hooks=[Hook(
            event="on_death",
            handler=_on_death,
            scope=HookScope.ONCE_PER_COMBAT,
            priority=50,
        )],
    )


# On-death factory registry
BOSS_ON_DEATH_FACTORIES: dict[str, callable] = {
    "holloway_on_death": _holloway_on_death_factory,
    "vance_on_death": _vance_on_death_factory,
    "strand_on_death": _strand_on_death_factory,
    "vossberg_on_death": _vossberg_on_death_factory,
    "crege_on_death": _crege_on_death_factory,
    "emperor_on_death": _emperor_on_death_factory,
}


# ---------------------------------------------------------------------------
# Helper: get boss for a stage
# ---------------------------------------------------------------------------


def get_boss_def(stage: int) -> BossDef:
    """Get boss definition for a given stage (1-6)."""
    if stage not in BOSS_DEFS:
        raise ValueError(f"No boss defined for stage {stage}")
    return BOSS_DEFS[stage]
