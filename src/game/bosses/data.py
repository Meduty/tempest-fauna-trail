"""Boss definitions and supporting cast rosters (T21).

Six bosses, one per stage, authored as Tier-10 Reclamation commanders.
Each boss has:
  - Authored (non-formula) stats — tunable constants
  - Fixed core supporting cast + variable add pool (seeded randomness)
  - Two-phase ability kit (phase 2 unlocks at 50% HP via phase hook passive)
  - One map effect (decoupled system — see map_effects.py)
  - On-death hook id (resolved in abilities system)

See:
  boss_roster.md  — narrative identity and design intent
  t21_challenge_boss_plan.md §3 — architectural decisions
  effect_systems_design.md §6.6 — boss phase hook mechanics

No Flet imports (V.1). No I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import Final

from src.game.models import Enemy, WeatherState
from src.game.registries import register_ability_mana


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class BossCastEntry:
    """One unit in a boss's supporting cast."""
    enemy_id: str
    count: int
    level: int = 1


@dataclass
class BossDef:
    """Authored definition for one stage boss.

    Authored stats are not power-formula-derived — they are hand-tuned
    constants (see t21_challenge_boss_plan.md §3.4).
    """
    id: str
    name: str
    stage_index: int
    affinity: WeatherState

    # Authored base stats (Tier-10, non-formula)
    max_hp: int
    strength: int
    intelligence: int
    armor: int
    resistance: int
    attack_speed: int = 110
    mana_regen: int = 12
    move_speed: int = 80
    threat: int = 90
    attack_range: int = 2
    ability_cost: int = 480_000      # mana units (mana_regen ticks to fill)
    # Combat-purpose axis (T.32, V.31). Bosses are authored set-pieces (role stays
    # "boss", outside the 8-role classifier), but still carry a valid `intent`;
    # multi-threat 2-phase commanders default to `hybrid`.
    intent: str = "hybrid"

    # Phase 1 kit
    phase1_active: str = ""
    phase1_passive: str = ""
    phase1_phase_hook: str = ""   # passive that monitors HP → triggers phase 2

    # Phase 2 additions (granted at 50% HP)
    phase2_active: str = ""
    phase2_passive: str = ""

    # On-death hook ability id (registered as passive at combat start)
    on_death_hook: str = ""

    # Supporting cast
    fixed_cast: list[BossCastEntry] = field(default_factory=list)
    variable_cast_pool: list[str] = field(default_factory=list)  # enemy_ids
    variable_cast_count_min: int = 0
    variable_cast_count_max: int = 0

    # Map effect
    map_effect_id: str = ""

    # Budget (total P including supporting cast)
    budget: float = 6.0

    # T24: Authored spawn position (col, row) for formation planner.
    # Melee bosses start at (7, 3) — frontline center.
    # Ranged/caster bosses start at (9, 3) — backline center.
    spawn_position: tuple[int, int] = (9, 3)

    def build_enemy(self) -> Enemy:
        """Instantiate the boss as an Enemy object."""
        return Enemy(
            id=self.id,
            name=self.name,
            affinity=self.affinity,
            role="boss",
            role_code="boss",
            intent=self.intent,
            tier=10,
            level=1,
            max_hp=self.max_hp,
            strength=self.strength,
            intelligence=self.intelligence,
            armor=self.armor,
            resistance=self.resistance,
            attack_speed=self.attack_speed,
            mana_regen=self.mana_regen,
            move_speed=self.move_speed,
            threat=self.threat,
            attack_range=self.attack_range,
            active_abilities=[self.phase1_active] if self.phase1_active else [],
            passive_ability=self.phase1_passive,
        )


@dataclass
class BossEncounterResult:
    """Returned by generate_boss_encounter(). Consumed by combat init and UI."""
    stage_index: int
    boss_def: BossDef
    boss_enemy: Enemy
    supporting_cast: list[Enemy]
    map_effect_id: str

    @property
    def all_enemies(self) -> list[Enemy]:
        """Boss + full supporting cast (boss first)."""
        return [self.boss_enemy] + self.supporting_cast


# ---------------------------------------------------------------------------
# Stage 1 — Foundry-Lord Holloway (Clear)
# ---------------------------------------------------------------------------

_HOLLOWAY = BossDef(
    id="boss_holloway",
    name="Foundry-Lord Holloway",
    stage_index=1,
    affinity=WeatherState.CLEAR,
    # Stats: slow, armoured frontline; Clear-neutral so no weather modifier
    max_hp=900,
    strength=80,
    intelligence=20,
    armor=55,
    resistance=35,
    attack_speed=90,
    move_speed=75,
    threat=100,
    attack_range=1,
    ability_cost=420_000,
    # Abilities (implemented downstream in T20 content)
    phase1_active="holloway.pressure_vent",
    phase1_passive="holloway.stoke_the_fires",
    phase1_phase_hook="holloway.phase_hook",
    phase2_active="holloway.magma_heave",
    phase2_passive="holloway.cinder_husk",
    on_death_hook="holloway.boiler_burst",
    # Supporting cast: fixed core + variable infantry
    fixed_cast=[
        BossCastEntry("enemy_heavy_knight", 2, level=1),
        BossCastEntry("enemy_steam_engineer", 2, level=1),
    ],
    variable_cast_pool=[
        "enemy_conscript",
        "enemy_levyman",
        "enemy_pikeman",
        "enemy_field_medic",
    ],
    variable_cast_count_min=3,
    variable_cast_count_max=5,
    map_effect_id="sunlit_tiles",
    budget=6.0,
    spawn_position=(7, 3),  # Melee frontline boss
)

# ---------------------------------------------------------------------------
# Stage 2 — Solar Overseer Vance (Mist)
# ---------------------------------------------------------------------------

_VANCE = BossDef(
    id="boss_vance",
    name="Solar Overseer Vance",
    stage_index=2,
    affinity=WeatherState.MIST,
    # Stats: fragile caster; high INT, low armour — rewards hunting her down
    max_hp=700,
    strength=40,
    intelligence=130,
    armor=25,
    resistance=50,
    attack_speed=95,
    move_speed=85,
    threat=70,
    attack_range=4,
    ability_cost=440_000,
    phase1_active="vance.focusing_lens",
    phase1_passive="vance.glare",
    phase1_phase_hook="vance.phase_hook",
    phase2_active="vance.sunflare_pounce",
    phase2_passive="vance.drought_aura",
    on_death_hook="vance.sun_husk_collapse",
    fixed_cast=[
        BossCastEntry("enemy_battlemage", 2, level=1),
        BossCastEntry("enemy_company_captain", 1, level=1),
    ],
    variable_cast_pool=[
        "enemy_picket",
        "enemy_crossbow_levy",
        "enemy_sergeant_at_arms",
    ],
    variable_cast_count_min=3,
    variable_cast_count_max=4,
    map_effect_id="fog",
    budget=15.0,
    spawn_position=(9, 3),  # Ranged caster boss
)

# ---------------------------------------------------------------------------
# Stage 3 — Grid-Director Strand (Thunder)
# ---------------------------------------------------------------------------

_STRAND = BossDef(
    id="boss_strand",
    name="Grid-Director Strand",
    stage_index=3,
    affinity=WeatherState.THUNDER,
    # Stats: fast, fragile caster riding the tempo — punish the discharge windows
    max_hp=800,
    strength=50,
    intelligence=150,
    armor=30,
    resistance=35,
    attack_speed=130,
    move_speed=90,
    threat=75,
    attack_range=3,
    ability_cost=380_000,
    phase1_active="strand.arc_cascade",
    phase1_passive="strand.overcharged",
    phase1_phase_hook="strand.phase_hook",
    phase2_active="strand.thunderhead",
    phase2_passive="strand.stormform",
    on_death_hook="strand.lightning_strike",
    fixed_cast=[
        BossCastEntry("enemy_arcanist", 2, level=1),
        BossCastEntry("enemy_riflemaster", 1, level=1),
    ],
    variable_cast_pool=[
        "enemy_capture_rig_wolf",
        "enemy_stormhawk",
        "enemy_voltaic_diviner",
    ],
    variable_cast_count_min=2,
    variable_cast_count_max=3,
    map_effect_id="hazard_tiles",
    budget=28.0,
    spawn_position=(9, 3),  # Ranged caster boss
)

# ---------------------------------------------------------------------------
# Stage 4 — Clearance-Marshal Vossberg (Cloudy)
# ---------------------------------------------------------------------------

_VOSSBERG = BossDef(
    id="boss_vossberg",
    name="Clearance-Marshal Vossberg",
    stage_index=4,
    affinity=WeatherState.CLOUDY,
    # Stats: aggressive frontline brawler — always in your face
    max_hp=1100,
    strength=140,
    intelligence=40,
    armor=60,
    resistance=45,
    attack_speed=105,
    move_speed=95,
    threat=110,
    attack_range=1,
    ability_cost=400_000,
    phase1_active="vossberg.scorched_advance",
    phase1_passive="vossberg.no_quarter",
    phase1_phase_hook="vossberg.phase_hook",
    phase2_active="vossberg.wildfire_leap",
    phase2_passive="vossberg.feeding_frenzy",
    on_death_hook="vossberg.fire_gutters_out",
    fixed_cast=[
        BossCastEntry("enemy_lord_commander", 1, level=1),
        BossCastEntry("enemy_gunslinger", 2, level=1),
    ],
    variable_cast_pool=[
        "enemy_conscript",
        "enemy_pikeman",
        "enemy_field_chaplain",
    ],
    variable_cast_count_min=3,
    variable_cast_count_max=5,
    map_effect_id="defensive_ley",
    budget=42.0,
    spawn_position=(7, 3),  # Melee frontline boss
)

# ---------------------------------------------------------------------------
# Stage 5 — Dredge-Admiral Crège (Rain)
# ---------------------------------------------------------------------------

_CREGE = BossDef(
    id="boss_crege",
    name="Dredge-Admiral Crège",
    stage_index=5,
    affinity=WeatherState.RAIN,
    # Stats: control bruiser; pulls pieces to her position and bogs the board
    max_hp=1350,
    strength=110,
    intelligence=80,
    armor=60,
    resistance=50,
    attack_speed=100,
    move_speed=80,
    threat=90,
    attack_range=3,
    ability_cost=460_000,
    phase1_active="crege.harpoon_winch",
    phase1_passive="crege.dredged_depths",
    phase1_phase_hook="crege.phase_hook",
    phase2_active="crege.maelstrom_jaws",
    phase2_passive="crege.drowning_tide",
    on_death_hook="crege.silt_drains",
    fixed_cast=[
        BossCastEntry("enemy_iron_maiden", 1, level=1),
        BossCastEntry("enemy_cannoneer", 2, level=1),
    ],
    variable_cast_pool=[
        "enemy_blight_lurker",
        "enemy_drowned_siren",
        "enemy_dredge_hulk",
    ],
    variable_cast_count_min=2,
    variable_cast_count_max=3,
    map_effect_id="flood_lanes",
    budget=60.0,
    spawn_position=(9, 3),  # Ranged control boss
)

# ---------------------------------------------------------------------------
# Stage 6 — The Iron Emperor (Snow) — Grand Finale
# ---------------------------------------------------------------------------
# The Iron Emperor is the run's last test. He synthesises every lesson:
#   - Decree of Iron (focus-fire target marking like Vance)
#   - Tribute (scales with living allies like Holloway's Stoke)
#   - Reclamation (channel finisher with a "race the clock" feel)
#   - The Wound Spreads (phase-2 passive: slow-tile spread accelerates)
#
# His supporting cast mixes elite humans (fixed core) with a variable wave
# of infantry + mid-tier elites — the world's last army. Each Emperor fight
# feels slightly different at the edges while keeping the core recognisable.
#
# Stats are significantly higher than other bosses (he is the final wall):
#   HP: 3000, STR: 180, INT: 180, Armor: 80, Resistance: 80

_IRON_EMPEROR = BossDef(
    id="boss_iron_emperor",
    name="The Iron Emperor",
    stage_index=6,
    affinity=WeatherState.SNOW,
    # Authored finale stats — tunable, not formula-derived
    max_hp=3000,
    strength=180,
    intelligence=180,
    armor=80,
    resistance=80,
    attack_speed=110,
    mana_regen=15,
    move_speed=80,
    threat=120,
    attack_range=2,
    ability_cost=520_000,
    # Phase 1: commanding, deliberate, relies on his army
    phase1_active="iron_emperor.decree_of_iron",
    phase1_passive="iron_emperor.tribute",
    phase1_phase_hook="iron_emperor.phase_hook",
    # Phase 2: the World-Engine tears loose; board compresses as he falls
    phase2_active="iron_emperor.reclamation",
    phase2_passive="iron_emperor.the_wound_spreads",
    on_death_hook="iron_emperor.world_engine_dark",
    # Core cast: apex-tier elites that never vary
    fixed_cast=[
        BossCastEntry("enemy_archmagus_imperator", 2, level=1),
        BossCastEntry("enemy_hierarch", 2, level=1),
    ],
    # Variable adds: a mix of infantry and mid-tier elites (3–4 random each fight)
    variable_cast_pool=[
        "enemy_conscript",
        "enemy_pikeman",
        "enemy_crossbow_levy",
        "enemy_heavy_knight",
        "enemy_battlemage",
    ],
    variable_cast_count_min=3,
    variable_cast_count_max=4,
    map_effect_id="slow_tiles",
    budget=90.0,
    spawn_position=(8, 3),  # Hybrid commander — midline center
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

BOSS_DEFS: Final[dict[int, BossDef]] = {
    1: _HOLLOWAY,
    2: _VANCE,
    3: _STRAND,
    4: _VOSSBERG,
    5: _CREGE,
    6: _IRON_EMPEROR,
}


# Author each boss's per-ability mana cost on the ability def (V.48, T.29c).
# `BossDef.ability_cost` stays the authoring knob; the deprecated per-piece
# `ability_cost` stat is gone, so the value is registered into ABILITY_MANA for
# the boss's phase-1 and phase-2 actives (phase-2 swaps inherit the same cost).
for _boss in BOSS_DEFS.values():
    for _abid in (_boss.phase1_active, _boss.phase2_active):
        if _abid:
            register_ability_mana(_abid, mana_cost=_boss.ability_cost)


def get_boss_def(stage_index: int) -> BossDef:
    """Return the BossDef for the given stage (1-6)."""
    if stage_index not in BOSS_DEFS:
        raise ValueError(f"No boss defined for stage {stage_index}")
    return BOSS_DEFS[stage_index]
