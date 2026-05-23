# T21 Plan — Challenge & Boss Encounters

> **Status:** comprehensive design — ready for admin review & decision on open items.
> **Depends:** T.19 (squad primitive, seed channels), T.20 (abilities, phase hook,
> effect system).
> **Design authority:** `boss_roster.md` for boss identities/kits, `effect_systems_design.md`
> for phase hooks and map effects.

---

## 1. Scope

T21 designs the two **authored-difficulty** encounter types: optional spirit-faction
**challenges** and 2-phase **bosses**. Both use the T19 squad-roll primitive but
have their own budgets, affinity rules, and unique mechanics.

**Primary outputs:**
- Challenge generation in `src/game/encounter.py`
- Boss set-piece data in `src/game/content.py` (or `src/game/bosses/data.py`)
- Map effect system in `src/game/combat/map_effects.py` (new)

**Test output:** `tests/game/test_challenge_boss.py`

**Out of scope:** individual boss ability implementations (downstream T20 content),
map effect visual presentation (UI task).

---

## 2. Challenge Encounters

### 2.1 Overview

6 challenge nodes, one per stage, each with a **fixed authored affinity matching
the stage affinity** (per `boss_roster.md` §1.1). Challenges are optional —
the player may skip them — but engaging yields above-average Amber and drops.

The challenge uses the **same stage affinity as the boss** — one stage, one
element, one identity. This was decided in `boss_roster.md` §1.1 and supersedes
the earlier per-challenge weather table.

| Stage | Continent | Stage affinity | Challenge affinity | Rationale |
|---|---|---|---|---|
| 1 | Europe | Clear | **Clear** | Tutorial — weather muted |
| 2 | Africa | Mist | **Mist** | Desert sandstorm elemental |
| 3 | Asia | Thunder | **Thunder** | Monsoon storm elemental |
| 4 | Oceania | Cloudy | **Cloudy** | Marine-layer overcast |
| 5 | South America | Rain | **Rain** | Amazon monsoon |
| 6 | North America | Snow | **Snow** | NYC winter |

### 2.2 Challenge team size

Challenge team sizes scale with expected player board cap and sit **at or above**
the player's expected cap to make them a genuine optional test:

| Stage | Expected player cap | Challenge team size | Over-cap |
|---|---|---|---|
| 1 | 2–3 | **4** | +1–2 |
| 2 | 3–4 | **5** | +1–2 |
| 3 | 5–6 | **7** | +1–2 |
| 4 | 6–7 | **8** | +1–2 |
| 5 | 7–8 | **9** | +1–2 |
| 6 | 8–10 | **11** | +1–2 |

> **⚠ DECISION NEEDED:** Whether challenge team sizes should exceed player cap
> by +1 (tight) or +2 (hard). The above uses +1 for early stages, +2 for later.
> **Recommendation:** +1 for stages 1–3, +2 for stages 4–6. This gives early
> challenges a "tough but fair" feel while late challenges feel like genuine
> gauntlets.

### 2.3 Roster composition — spirit faction

Challenge enemies are drawn from the **spirit/elemental faction** (corrupted
wildlife and elementals from `enemy_roster.md`), not from the human faction used
by FIGHT nodes. This makes challenges feel thematically distinct — you fight
the land's angry weather, not more soldiers.

**Affinity distribution within the squad:**

- **50% challenge-affinity** — enemies whose affinity matches the stage affinity
  (the thematic core).
- **30% live-weather-affinity** — enemies whose affinity matches the **live
  node weather** at the time of engagement. This creates the interaction between
  live weather and the authored encounter.
- **20% random** — any of the 6 affinities (variety).

```
random_slots    = max(1, round(0.2 * team_size))
live_wx_slots   = max(1, round(0.3 * team_size))
challenge_slots = team_size - random_slots - live_wx_slots
```

> **⚠ DECISION NEEDED:** Whether the 30% bucket uses **live weather** or stage
> affinity. If live weather: the challenge composition shifts between runs,
> creating variety. If stage affinity: up to 80% of the squad shares one
> element, making it a hard mono-affinity wall the player can counter-pick
> cleanly. **Recommendation:** live weather for the 30% bucket — it creates
> meaningful run-to-run variety and rewards reading the weather forecast.

When live weather == challenge affinity, the two buckets stack → up to 80%
one affinity. This is natural and intended — an unlucky draw that the player
can see coming.

### 2.4 Challenge power budget

Challenge budgets use the T19 `stage_base` curve with a **1.3× multiplier**:

```python
challenge_budget = stage_base(stage.index) * 1.3 * rng.uniform(0.90, 1.10)
```

The variance band is tighter (±10%) than regular fights (±15%) because
challenges should feel tuned, not random.

### 2.5 Challenge rewards

Upon clearing a challenge, the player receives:
- **Amber:** `2 × stage.index` (double the normal fight payout)
- **Guaranteed item component drop** (one random base component)
- **Tempest bonus:** `+1` extra Tempest beyond the normal `+2` per fight

> **⚠ DECISION NEEDED:** Whether challenges also grant a **trait-themed
> component** (e.g. a Mist challenge drops a Wardpelt) or a fully random one.
> **Recommendation:** themed — it reinforces the stage identity and gives
> players a reason to prefer certain challenges.

### 2.6 Determinism

```python
rng = Random(derive_seed(run_seed, node_index, CH_CHALLENGE))
```

The roster depends on `(seed, node_index, CH_CHALLENGE)`. Live weather affects
the 30% bucket — same seed + same live weather → identical roster. Different
live weather → different 30% bucket → different roster. This is the intended
weather-driven variance.

---

## 3. Boss Encounters

### 3.1 Fixed affinity per stage — confirmed

Per `boss_roster.md` §1.1, boss affinity is a **stage property**, not live
weather. This is a locked decision:

| Stage | Boss | Affinity |
|---|---|---|
| 1 | Foundry-Lord Holloway | **Clear** |
| 2 | Solar Overseer Vance | **Mist** |
| 3 | Grid-Director Strand | **Thunder** |
| 4 | Clearance-Marshal Vossberg | **Cloudy** |
| 5 | Dredge-Admiral Crège | **Rain** |
| 6 | The Iron Emperor | **Snow** |

**Live weather still matters** through three layers (`boss_roster.md` §1.2):
1. Weather Favor buff/debuff on the boss (live weather vs. boss affinity)
2. Player prep fork (weather-fit vs. type-advantage team)
3. Luck — sometimes live weather debuffs the boss

### 3.2 Two-phase mechanic

At **50% HP**, the boss enters Phase 2:
- Gains **+1 active ability** and **+1 passive ability** (the unleashed beast)
- Transition fires via the phase hook (`effect_systems_design.md` §6.6)
- `ONCE_PER_COMBAT` scope prevents re-triggering

Phase 2 cardinality:
| Phase | Actives | Passives |
|---|---|---|
| Phase 1 | 1 | 1 |
| Phase 2 | 2 | 2 |

Implementation uses `EffectBundle` + `ctx.register_bundle` — the same path used
for all mid-combat modifications.

### 3.3 Boss supporting cast

Each boss arrives with a curated squad drawn from `enemy_roster.md`:

| Boss | Supporting cast (from `boss_roster.md`) |
|---|---|
| Holloway | 2× Heavy Knight, 2× Steam Engineer, 4× Conscript |
| Vance | 2× Battlemage, 1× Company Captain, 4× Picket |
| Strand | 2× Arcanist, 1× Riflemaster, 3× Capture-Rig Wolf |
| Vossberg | 1× Lord Commander, 2× Gunslinger, 4× Conscript |
| Crège | 1× Iron Maiden, 2× Cannoneer, 3× Blight Lurker |
| Iron Emperor | Authored separately — the grand finale |

Supporting cast is **fixed** (not rolled from a pool) — the boss fight is a
hand-built set-piece. The `CH_BOSS` seed channel is reserved for any minor
variance within the cast (e.g. stat jitter), but the roster itself is authored.

> **⚠ DECISION NEEDED:** Whether boss supporting cast stats should **scale with
> player stage progression** (so a boss replayed in a long-run New Game+ mode
> stays threatening) or use **fixed tier-appropriate stats**. For the base game
> (one run = one pass through 6 stages), fixed is sufficient.
> **Recommendation:** fixed for MVP. Add a `boss_scaling_factor` multiplier
> for NG+ later.

### 3.4 Boss power budget

Boss encounters have **authored budgets**, not formula-driven ones:

```python
BOSS_BUDGETS: dict[int, float] = {
    1: 6.0,    # Holloway — slightly above stage 1's expected player power
    2: 15.0,   # Vance
    3: 28.0,   # Strand
    4: 42.0,   # Vossberg
    5: 60.0,   # Crège
    6: 90.0,   # Iron Emperor
}
```

These include the boss + supporting cast total P. The boss itself is a T10
piece (`P(10,1) = 6.2`); the difference is the supporting cast budget.

> **⚠ DECISION NEEDED:** Exact boss budget values. The above are estimates.
> **Recommendation:** playtest-tunable constants, not formula-derived.

---

## 4. Map Effect System

### 4.1 Motivation

Boss fights use **one authored arena effect** that modifies the hex board during
combat. Map effects are the game's most dramatic environmental mechanic — each
boss fight has a unique spatial puzzle.

### 4.2 The six map effects

Per `boss_roster.md` §1.4:

| Boss (affinity) | Map effect | Mechanic |
|---|---|---|
| Holloway (Clear) | **Spawn rifts** | Cells periodically open and spawn weak adds (Conscript-tier). 1–2 adds every ~300 ticks. |
| Vance (Mist) | **Fog** | Pieces beyond range 2 of each other are untargetable. Forces close-range combat. |
| Strand (Thunder) | **Hazard tiles** | Designated cells deal `true` damage per tick to occupants. Tiles shift every ~600 ticks. |
| Vossberg (Cloudy) | **Ley cells** | Contested tiles grant stat buffs to whichever team holds them. 2–3 ley cells on the board. |
| Crège (Rain) | **Flood lanes** | One board column is impassable; shifts one column per round. Reshapes lanes. |
| Iron Emperor (Snow) | **Collapsing arena** | Edge rows disable (become impassable) over the fight. Arena shrinks every ~600 ticks. |

### 4.3 Map effect architecture

Map effects require a **new combat engine extension** — board-cell modifiers.
This is a `SPEC D.3` deferred item that T21 forces to the surface.

```python
@dataclass
class CellModifier:
    cell: tuple[int, int]           # (q, r) hex coordinate
    kind: str                        # "hazard" | "impassable" | "ley" | "fog" | "rift"
    owner: str                       # "boss:strand" — source for attribution
    tick_damage: float = 0.0         # per-tick damage (hazard tiles)
    stat_buffs: dict[str, float] | None = None   # ley cell grants
    spawn_template: str | None = None  # rift spawns this enemy id
    active: bool = True

class BoardState:
    cells: dict[tuple[int, int], list[CellModifier]]

    def modifiers_at(self, q: int, r: int) -> list[CellModifier]: ...
    def is_passable(self, q: int, r: int) -> bool: ...
    def add_modifier(self, mod: CellModifier) -> None: ...
    def remove_modifier(self, cell: tuple[int, int], kind: str) -> None: ...
```

### 4.4 Map effect processing in the tick loop

Each tick, after piece meter updates and before action resolution:

```python
def _process_map_effects(ctx: CombatContext) -> None:
    for piece in ctx.living_pieces():
        for mod in ctx.board.modifiers_at(piece.q, piece.r):
            if mod.kind == "hazard" and mod.tick_damage > 0:
                ctx.deal_damage(None, piece, mod.tick_damage, SourceTag.TRUE)
            elif mod.kind == "ley" and mod.stat_buffs:
                # Grant/remove buffs based on which team holds the cell
                ...
```

Periodic effects (spawn rifts, flood lane shifts, arena collapse) fire on
**round boundaries** (every 600 ticks):

```python
def _process_round_effects(ctx: CombatContext, round_num: int) -> None:
    for effect in ctx.map_effects:
        effect.on_round(ctx, round_num)
```

### 4.5 Map effect authoring

Each boss has a `MapEffect` class or factory:

```python
class HazardTilesEffect:
    """Strand's capture-grid. Tiles shift every round."""
    def __init__(self, board: BoardState, rng: SeededRng):
        self._place_initial_hazards(board, rng)

    def on_round(self, ctx: CombatContext, round_num: int) -> None:
        self._shift_hazards(ctx.board, ctx.rng)
```

> **⚠ DECISION NEEDED:** Whether map effects should be **weather-themed** (the
> six boss map effects double as generic weather-map effects usable by
> challenges and weather-themed encounters) or **boss-specific** (each boss has
> a unique map effect that only appears in its fight).
>
> **Recommendation:** boss-specific for MVP. The six map effects are authored
> for specific bosses and carry the boss's narrative flavor (Strand's
> capture-grid, Crège's dredge-wake). Making them generic requires abstracting
> away the narrative, which dilutes the boss identity. If challenges want map
> effects later, they can use simplified versions (e.g. "3 random hazard tiles"
> without the Strand narrative wrapper).
>
> **Alternative (challenge map effects):** if challenges should also have map
> effects, define a **simplified weather-themed variant** per affinity:
>
> | Affinity | Challenge map effect | Simplified version of |
> |---|---|---|
> | Clear | Minor spawn rift (1 add, slower) | Holloway's spawn rifts |
> | Mist | Light fog (range 3 limit, not 2) | Vance's fog |
> | Thunder | Fewer hazard tiles, less damage | Strand's hazard tiles |
> | Cloudy | 1 ley cell (not 2–3) | Vossberg's ley cells |
> | Rain | Narrower flood (1 column) | Crège's flood lanes |
> | Snow | Slower arena collapse | Iron Emperor's collapse |
>
> This preserves boss uniqueness while giving challenges their own spatial
> puzzle. **Recommendation for challenges:** no map effects for MVP — the
> elemental squad composition already differentiates challenges. Add simplified
> map effects in a post-MVP pass.

---

## 5. Boss On-Death Effects

Each boss has a **scripted on-death event** (from `boss_roster.md`):

| Boss | On-death effect |
|---|---|
| Holloway | Delayed AOE detonation centered on wreck (few ticks after death) |
| Vance | Sun-Husk collapses → heals player team briefly |
| Strand | Uncontrolled lightning strike at boss tile, damages adjacent |
| Vossberg | Fire gutters out; burning tiles extinguish in a wave |
| Crège | Leviathan sinks; silt drains, board clears of slow |
| Iron Emperor | Authored finale (TBD) |

Implementation: an `on_death` hook registered by the boss's passive at combat
start. The hook fires via the standard `on_death` event from the event bus.

---

## 6. Prismatic Augment: "Living World"

The Prismatic augment **Living World** (`augment_catalog.md` §4) flips the boss
map effect to benefit the player instead of harming them. Implementation:

```python
# When Living World is active, map effects targeting enemies flip to targeting allies
# and vice versa, or neutral effects become player-favorable.
```

> **⚠ DECISION NEEDED:** Whether Living World should **invert** map effects
> (hazard tiles damage enemies, ley cells always favor the player) or
> **suppress** them (map effects are disabled entirely). Inversion is more
> interesting but requires per-effect inversion logic.
> **Recommendation:** invert — it's the kind of dramatic, game-warping effect
> a Prismatic augment should be.

---

## 7. Subtask Split

### T21 owns:
- Challenge generation (affinity rules, spirit-faction pool, challenge budgets)
- Boss data (supporting cast rosters, authored budgets)
- Map effect system (`CellModifier`, `BoardState` extensions, per-boss effects)
- Boss on-death hooks
- Challenge reward structure

### T19 provides:
- `derive_seed`, `CH_CHALLENGE`, `CH_BOSS` channels
- `roll_squad` primitive for challenge roster generation
- `filter_pool` for spirit-faction filtering

### T20 provides:
- Phase hook mechanism (`ONCE_PER_COMBAT` scope)
- `EffectBundle` + `ctx.register_bundle` for mid-combat ability grants
- Event bus for on-death hooks
- All ability/status infrastructure

### T24 consumes:
- Boss supporting cast placement (same rules as regular squads, but the boss
  itself is placed at a **fixed authored position** — center-back of the
  enemy formation)

---

## 8. Test Plan

See T.16 for full test details. Summary:

1. **Challenge determinism:** same `(seed, node_index, CH_CHALLENGE)` → identical
   roster. Different seeds or different live weather → different rosters.
2. **Challenge affinity distribution:** 50/30/20 split verified per §2.3.
3. **Challenge team size:** matches stage table §2.2.
4. **Challenge spirit faction:** all enemies have spirit/corrupted tags.
5. **Boss phase transition:** fires once at 50% HP; grants +1 active +1 passive.
6. **Boss supporting cast:** exact roster per §3.3.
7. **Map effects — hazard tiles:** occupant takes per-tick `true` damage.
8. **Map effects — fog:** targets beyond range 2 are untargetable.
9. **Map effects — flood lanes:** column is impassable; shifts per round.
10. **Map effects — ley cells:** stat buffs apply to holding team.
11. **Map effects — spawn rifts:** adds spawn on schedule.
12. **Map effects — collapsing arena:** edge rows disable over time.
13. **Boss on-death:** hook fires; per-boss effect resolves.
14. **Determinism:** boss fight with fixed seed → byte-equal `BattleResult`.

---

## 9. Acceptance Criteria

1. 6 challenges generated per §2; 6 bosses authored per §3.
2. Challenge determinism and the affinity distribution hold.
3. Boss phase-2 abilities resolve via T20.
4. Map effect system exists and at least hazard tiles + collapsing arena are
   functional.
5. Boss on-death hooks fire correctly.
6. `tests/game/test_challenge_boss.py` passes.

---

## 10. Open Items Summary

| # | Question | Recommendation | Impact if deferred |
|---|---|---|---|
| 1 | Challenge team size: +1 or +2 over player cap | +1 early, +2 late | Medium — affects difficulty |
| 2 | Challenge 30% bucket: live weather or stage affinity | Live weather | Low — variety vs. predictability |
| 3 | Challenge rewards: themed or random component | Themed | Low — flavor only |
| 4 | Boss supporting cast scaling for NG+ | Fixed for MVP | Zero — no NG+ yet |
| 5 | Exact boss budget values | Playtest-tunable constants | Must be tuned |
| 6 | Map effects for challenges | No map effects for MVP | Low — squad comp differentiates |
| 7 | Living World augment: invert or suppress map effects | Invert | Low — can ship either |
| 8 | Iron Emperor on-death effect | TBD — author with finale narrative | Low — one boss |
| 9 | Boss ability kits (individual implementations) | Downstream T20 content | Must be done before boss fights work |
