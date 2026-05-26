# T21 Plan — Challenge & Boss Encounters

> **Status:** design finalised & decisions resolved — implementing.
> **Depends:** T.19 (squad primitive, seed channels), T.20 (abilities, phase hook,
> effect system).
> **Design authority:** `boss_roster.md` for boss identities/kits, `effect_systems_design.md`
> for phase hooks and map effects.

---

## 1. Scope

T21 designs the two **authored-difficulty** encounter types: optional
**champion-faction challenges** and 2-phase **bosses**. Both use the T19 squad-roll
primitive but have their own budgets, affinity rules, and unique mechanics.

**Primary outputs:**
- Challenge generation in `src/game/encounter.py`
- Boss set-piece data in `src/game/bosses/data.py`
- Map effect system in `src/game/map_effects.py` (new)
- Board state layer in `src/game/board.py` (new)

**Test output:** `tests/game/test_challenge_boss.py`

**Out of scope:** individual boss ability implementations (downstream T20 content),
map effect visual presentation (UI task). Living World augment deferred (see §6).

---

## 2. Challenge Encounters

### 2.1 Overview

6 challenge nodes, one per stage, each with a **fixed authored affinity matching
the stage affinity** (per `boss_roster.md` §1.1). Challenges are optional —
the player may skip them — but engaging yields above-average Amber and drops.

The challenge uses the **same stage affinity as the boss** — one stage, one
element, one identity.

| Stage | Continent | Stage affinity | Challenge affinity |
|---|---|---|---|
| 1 | Europe | Clear | **Clear** |
| 2 | Africa | Mist | **Mist** |
| 3 | Asia | Thunder | **Thunder** |
| 4 | Oceania | Cloudy | **Cloudy** |
| 5 | South America | Rain | **Rain** |
| 6 | North America | Snow | **Snow** |

### 2.2 Challenge team size

Challenge team sizes sit **at or above** the player's expected cap (+1 early,
+2 late) to make them a genuine optional test:

| Stage | Expected player cap | Challenge team size |
|---|---|---|
| 1 | 2–3 | **4** |
| 2 | 3–4 | **5** |
| 3 | 5–6 | **7** |
| 4 | 6–7 | **8** |
| 5 | 7–8 | **9** |
| 6 | 8–10 | **11** |

### 2.3 Roster composition — champion faction

**Decision (finalised):** Challenge enemies are drawn from the **Champion roster**,
not from the enemy/corrupted-wildlife roster. The player fights pieces they
recognise as their *own faction* — Sunmane Lions, Glacierback Mammoths,
Spectral Herons — turned against them. This is the defining characteristic of
a challenge: you face your own faction's finest.

Normal fights and boss fights draw from the enemy (Reclamation) roster. The
challenge is the one encounter type where you fight champion-calibre pieces.

**Affinity distribution within the squad:**

- **50% challenge-affinity** — champions whose affinity matches the stage affinity.
- **30% live-weather-affinity** — champions whose affinity matches the **live
  node weather** at the time of engagement. Creates run-to-run variety.
- **20% random** — any of the 6 affinities.

```
random_slots    = max(1, round(0.20 * team_size))
live_wx_slots   = max(1, round(0.30 * team_size))
challenge_slots = team_size - random_slots - live_wx_slots
```

When live weather == challenge affinity, the two buckets stack → up to 80%
one affinity. Natural and intended — an unlucky draw the player can see coming.

T10 Primordials are excluded from challenge pools (reserved for authored content).

### 2.4 Challenge power budget

```python
challenge_budget = stage_base(stage.index) * 1.3 * rng.uniform(0.90, 1.10)
```

The variance band is tighter (±10%) than regular fights (±15%) because
challenges should feel tuned, not random.

### 2.5 Challenge rewards

Upon clearing a challenge, the player receives:

- **Amber:** `2 × stage.index` (double the normal fight payout)
- **Champion offer:** one of the champions from the defeated enemy team (the
  player may recruit them)
- **Random base component:** one random base component from the standard pool
- **Themed component:** one base component thematically linked to the stage
  affinity (e.g. Mist challenge → Cloak; Thunder challenge → Rod)
- **Tempest bonus:** `+1` extra Tempest beyond the normal `+2` per fight

The themed component reinforces stage identity and gives players a reason to
prefer certain challenges. Champion offer is the key narrative payoff: you
recruit the champion that was standing against you.

### 2.6 Determinism

```python
rng = Random(derive_seed(run_seed, node_index, CH_CHALLENGE))
```

The roster depends on `(seed, node_index, CH_CHALLENGE)`. Live weather affects
the 30% bucket — same seed + same live weather → identical roster.

---

## 3. Boss Encounters

### 3.1 Fixed affinity per stage — confirmed

Per `boss_roster.md` §1.1, boss affinity is a **stage property**, not live
weather. Locked decision:

| Stage | Boss | Affinity |
|---|---|---|
| 1 | Foundry-Lord Holloway | **Clear** |
| 2 | Solar Overseer Vance | **Mist** |
| 3 | Grid-Director Strand | **Thunder** |
| 4 | Clearance-Marshal Vossberg | **Cloudy** |
| 5 | Dredge-Admiral Crège | **Rain** |
| 6 | The Iron Emperor | **Snow** |

### 3.2 Two-phase mechanic

At **50% HP**, the boss enters Phase 2:
- Gains **+1 active ability** and **+1 passive ability**
- Transition fires via the phase hook (`effect_systems_design.md` §6.6)
- `ONCE_PER_COMBAT` scope prevents re-triggering

### 3.3 Boss supporting cast

Each boss has a **fixed core cast** plus a small **variable add pool** for
variety across runs. The core cast is always present; variable adds are drawn
deterministically from `CH_BOSS` seed channel.

| Boss | Fixed core | Variable pool (draw N) |
|---|---|---|
| Holloway | 2× Heavy Knight, 2× Steam Engineer | draw 3–5 from [Conscript, Levyman, Pikeman, Field Medic] |
| Vance | 2× Battlemage, 1× Company Captain | draw 3–4 from [Picket, Crossbow Levy, Sergeant-at-Arms] |
| Strand | 2× Arcanist, 1× Riflemaster | draw 2–3 from [Capture-Rig Wolf, Stormhawk, Voltaic Diviner] |
| Vossberg | 1× Lord Commander, 2× Gunslinger | draw 3–5 from [Conscript, Pikeman, Field Chaplain] |
| Crège | 1× Iron Maiden, 2× Cannoneer | draw 2–3 from [Blight Lurker, Drowned Siren, Dredge-Hulk] |
| Iron Emperor | 2× Archmagus Imperator, 2× Hierarch | draw 3–4 from [Conscript, Pikeman, Crossbow Levy, Heavy Knight, Battlemage] |

**Iron Emperor authored finale:** The Iron Emperor is the run's last test — every
lesson combined. He gains focus-fire (Decree of Iron), scaling from his living
support (Tribute), a channel finisher (Reclamation), and phase-2 passive that
accelerates the arena's frozen compression (The Wound Spreads). His variable
adds are drawn from both human infantry and mid-tier elites — the world's last
army — making each Emperor fight feel slightly different while keeping the core
encounter recognisable. Stats are Tier-10 authored, not formula-generated.

Fixed stats (MVP, tunable):
- HP: 3000, STR: 180, INT: 180, Armor: 80, Resistance: 80

### 3.4 Boss power budget

Boss encounters have **authored budgets**, not formula-driven ones:

```python
BOSS_BUDGETS: dict[int, float] = {
    1: 6.0,    # Holloway
    2: 15.0,   # Vance
    3: 28.0,   # Strand
    4: 42.0,   # Vossberg
    5: 60.0,   # Crège
    6: 90.0,   # Iron Emperor
}
```

Playtest-tunable constants.

---

## 4. Map Effect System

### 4.1 Motivation

Boss fights use **one authored arena effect** that modifies the hex board during
combat. Map effects are the game's most dramatic environmental mechanic — each
boss fight has a unique spatial flavour.

### 4.2 The six map effects (auto-battle-aware design)

Since players do not control pieces during combat, all map effects are designed
to be meaningful **from the prep-phase positioning decision**, not real-time
control. Tiles are visible during planning so players can make informed
placement choices. Effects influence pathing, targeting, and the deterministic
behaviour of pieces.

| Boss (affinity) | Map effect | Mechanic |
|---|---|---|
| Holloway (Clear) | **Sunlit tiles** | 2–3 cells glow with direct sunlight. A piece standing on a sunlit tile receives heal-over-time and a damage buff for as long as it occupies the tile. Buff drops immediately on vacating. Both teams benefit — positional advantage decided in Prep. |
| Vance (Mist) | **Fog** | Pieces beyond range 2 of each other are untargetable. Forces all pieces to close distance; ranged pieces effectively become melee-range. Prep choice: how to arrange ranged vs. melee. |
| Strand (Thunder) | **Hazard tiles** | 4–6 designated cells deal `true` damage every 60 ticks to occupants. Tiles shift every round (~600 ticks). Initial positions are visible in Prep. |
| Vossberg (Cloudy) | **Defensive ley cells** | 2–3 contested tiles grant defensive stat buffs (damage reduction, HP regen) to the **holding team** (whoever has a piece on the cell). Ownership transfers by stepping onto a cell. Buff drops immediately on vacating. Prep placement determines early control. |
| Crège (Rain) | **Flood lanes** | One board column floods and becomes impassable; shifts one column each round. Reshapes lanes and pathing mid-fight. Prep arrangement matters for which pieces get cut off. |
| Iron Emperor (Snow) | **Slow tiles** | Frozen tiles radiate from the arena edges inward over the fight, slowing movement of any piece standing on them. Spread accelerates in Phase 2 (The Wound Spreads). Compresses the effective combat zone without disabling tiles entirely. |

**Design rationale for Clear and Cloudy (replacing original designs):**

Clear (Holloway) originally spawned Rift adds — replaced with Sunlit Tiles because:
- Spawn rifts are too powerful as a first boss mechanic (extra units on the field)
- "Spawn twice per round" is swingy and doesn't feel like *clear* weather
- Sunlit tiles teach the board-state concept cleanly as the tutorial boss
- Both teams benefit — no unfair asymmetry for a tutorial encounter

Cloudy (Vossberg) originally granted generic stat buffs to ley-cell holders —
refined to **defensive** buffs specifically: damage reduction, armor, HP regen.
This fits a cloudy/overcast thematic identity (shelter, endurance, covering) and
rewards holding ground rather than attacking (which pairs well with Vossberg's
aggressive "he never stops moving forward" feel — the player is defending ley
cells while Vossberg advances).

Iron Emperor originally disabled edge tiles (collapsing arena) — replaced with
**slow tiles** because:
- Disabling tiles removes play space entirely, which is frustrating without player control
- Slow tiles compress the *effective* combat zone without hard barriers
- The spreading cold imagery fits Snow affinity thematically
- Players can still fight on slow tiles — at a movement penalty

### 4.3 Map effect architecture

Map effects live in `src/game/map_effects.py` and are **decoupled from bosses**.
The `BoardState` data layer lives in `src/game/board.py` (imported by both
`combat/context.py` and `map_effects.py` — no circular imports).

```python
# src/game/board.py
@dataclass
class CellModifier:
    cell: tuple[int, int]           # (q, r) hex coordinate
    kind: str                        # "sunlit" | "hazard" | "ley" | "fog" | "flood" | "slow"
    owner: str                       # source id, e.g. "boss:holloway"
    active: bool = True
    # Kind-specific
    heal_per_interval: float = 0.0  # sunlit: heal per 60 ticks
    damage_buff_pct: float = 0.0    # sunlit: damage multiplier bonus
    damage_interval: int = 60       # hazard: deal damage every N ticks
    damage_amount: float = 0.0      # hazard: true damage per interval
    holding_team: str | None = None # ley: "player" | "enemy" | None

class BoardState:
    """Live board-cell modifier state during combat."""
    cell_modifiers: dict[tuple[int, int], list[CellModifier]]
    impassable_columns: set[int]    # flood lanes
    fog_range: int | None           # None = no fog; int = max targetable range
    slow_cells: set[tuple[int, int]]  # slow tiles
    ley_cells: list[tuple[int, int]]  # ley cell positions
```

### 4.4 Map effect processing in the tick loop

Map effects subscribe to the event bus at `on_combat_start`. Each effect
registers `on_tick` and/or round-boundary hooks.

Round boundaries fire every 600 ticks via the `on_tick` handler checking
`tick % ROUND_TICKS == 0`.

Sunlit tile buff: TIMED Modifier applied every 2 ticks on pieces standing on
the cell; expires naturally when the piece moves off (no refresh means the
modifier expires after 2 ticks and is not reapplied).

Hazard tile damage: deals `SourceTag.TRUE` damage; interval-gated by
`tick % damage_interval == 0`.

Ley cell ownership: tracked on `CellModifier.holding_team`; defensive
modifier applied/removed as ownership changes.

Slow tiles: apply `slow` status to pieces on slow cells each tick.

### 4.5 Map effects are decoupled from bosses

Map effects are standalone objects instantiated in `bosses/data.py` and passed
via `BossEncounterResult`. In MVP, only boss fights use map effects. Future
changes (augments, champion passives) can introduce map effects without touching
boss code.

Each boss has one authored effect matching its stage affinity. The system is
open for extension: any encounter result can carry a map effect list.

---

## 5. Boss On-Death Effects

Each boss has a scripted on-death hook registered at combat start as a passive.

| Boss | On-death |
|---|---|
| Holloway | Delayed AOE detonation centred on wreck (fires 30 ticks after death) |
| Vance | Sun-Husk collapses → small heal on player team |
| Strand | Uncontrolled lightning strike hits boss tile + adjacents |
| Vossberg | Burning tiles (from Scorched Advance trail) extinguish in a wave |
| Crège | Silt drains; slow cleared from all pieces |
| Iron Emperor | World-Engine goes dark; freed corrupted pieces linger (no longer hostile — cosmetic) |

On-death hooks are simple and brief. Most boss fights end with the boss's death,
so elaborate post-death sequences rarely play out in full. Implementations are
kept to ≤10 lines each.

---

## 6. Living World Augment — Deferred

The **Living World** Prismatic augment (which would flip map effects to benefit
the player) is **deferred** until map effects are fully validated and weather map
effects are designed for non-boss encounters. The deferral rationale:

- Some map effects cannot be trivially made "beneficial" without redesign
- Map effects for non-boss encounters are themselves deferred (MVP: boss-only)
- Living World would require per-effect inversion logic — unnecessary scope now

Living World remains in `augment_catalog.md §4` as a planned Prismatic.

---

## 7. Subtask Split

### T21 owns:
- Challenge generation (champion-faction pool, affinity rules, challenge budgets)
- Boss data (supporting cast rosters, authored budgets, Iron Emperor stats)
- Map effect system (`BoardState`, `CellModifier`, `MapEffect` base, 6 concrete effects)
- Boss on-death hooks
- Challenge reward structure (`ChallengeReward` dataclass)

### T19 provides:
- `derive_seed`, `CH_CHALLENGE`, `CH_BOSS` channels
- `roll_squad` primitive for general squad generation

### T20 provides:
- Phase hook mechanism (`ONCE_PER_COMBAT` scope)
- `EffectBundle` + `ctx.register_bundle` for mid-combat ability grants
- Event bus for on-death hooks

### T24 consumes:
- Boss supporting cast placement (same formation rules; boss at authored position)

---

## 8. Test Plan

1. **Challenge determinism:** same `(seed, node_index, CH_CHALLENGE)` + weather → identical roster.
2. **Challenge affinity distribution:** 50/30/20 split verified per §2.3.
3. **Challenge team size:** matches stage table §2.2.
4. **Challenge champion faction:** all challenge pieces are from the champion roster.
5. **Boss supporting cast:** core cast always present; variable adds from seeded pool.
6. **Map effects — sunlit tiles:** pieces on sunlit tiles receive heal + damage buff modifier.
7. **Map effects — fog:** fog_range set on BoardState; targeting helpers respect it.
8. **Map effects — hazard tiles:** occupant takes true damage at correct interval.
9. **Map effects — ley cells:** defensive buffs apply to holding team.
10. **Map effects — flood lanes:** column marked impassable; shifts per round.
11. **Map effects — slow tiles:** slow status applied to pieces on slow cells.
12. **BoardState determinism:** same seed → identical cell placements.
13. **Challenge reward:** ChallengeReward contains champion_offer from team, themed component.

---

## 9. Acceptance Criteria

1. 6 challenges generated per §2; champion-faction roster only.
2. Challenge determinism and affinity distribution hold.
3. 6 boss definitions authored per §3; Iron Emperor has authored stats.
4. Map effect system exists; all 6 effects instantiable and hookable.
5. `tests/game/test_challenge_boss.py` passes.

---

## 10. Decisions of Record

| # | Decision | Rationale |
|---|---|---|
| 1 | Challenge faction = champion roster | Fights feel distinct from normal encounters; narrative payoff ("you fight your own") |
| 2 | Challenge reward includes champion offer | Champion recruited from the defeated team is the narrative climax of a challenge |
| 3 | Iron Emperor gets slow tiles, not collapsing arena | Disabling tiles removes control without player agency; slow tiles compress the zone without hard barriers |
| 4 | Holloway gets Sunlit Tiles, not Spawn Rifts | Tutorial boss should teach the map concept cleanly, not add chaos; neutral benefit fits Clear affinity |
| 5 | Vossberg gets Defensive Ley Cells | Shields the "hold ground" identity; matches cloudy/overcast "endurance" theme |
| 6 | Hazard tile damage is interval-based (every 60 ticks) | Per-tick damage is too fine-grained and punishes any board overlap harshly; intervals feel more intentional |
| 7 | Map effects are decoupled from bosses | Allows future augments/passives to use map effects; boss code stays self-contained |
| 8 | Living World augment deferred | Can't cleanly invert all effects; non-boss map effects not designed yet |
| 9 | Boss adds have variable pool component | Slight variation across runs without breaking authored feel |
| 10 | Sudden death remains timeout-only | Iron Emperor's pressure comes from slow tiles, not game-over escalation |
