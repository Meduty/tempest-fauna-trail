# T19 Plan — Encounter Generation (`src/game/encounter.py`)

> **Status:** comprehensive design — ready for admin review & decision on open items.
> **Depends:** T.1 (models), T.4 (route), T.5 (content/enemy roster), T.18 (power).
> **Feeds into:** T.21 (challenges & bosses reuse `roll_squad`), T.24 (formation consumes squads).

---

## 1. Scope

T19 fills route nodes with **procedurally generated, seed-deterministic
encounters**. It covers `FIGHT` and `REWARD` enemy squads, and exposes the
generic squad-roll primitive that T21 reuses for challenges and bosses.
`AUGMENT` and `SUPPLY` *offer payloads* are authored by T22 using the same
sub-seed channels defined here.

**Primary output:** `src/game/encounter.py`
**Test output:** `tests/game/test_encounter.py`

**Out of scope:**
- Challenge/boss encounter authoring (T21)
- Augment/supply *content* (T22) — T19 provides the seed channels only
- The power scalar itself (T18 — already shipped)
- Enemy formation/placement (T24)

---

## 2. Determinism Model

### 2.1 Root seed

`Run.seed` (already on the model) is the single root of randomness for the
entire run. Every procedural decision is a pure function of this seed plus
node/channel indices — **no** external state, **no** clock, **no**
`random.random()`.

### 2.2 Sub-seed derivation

Per-node, per-channel sub-seeds isolate randomness so that:
- Node 5's squad is independent of node 4's.
- A reroll at one node cannot shift outcomes at another.
- Challenge/boss channels (T21) are independent of fight channels.

```python
# Channel constants
CH_ENEMIES  = 0   # FIGHT / REWARD squad
CH_AUGMENT  = 1   # AUGMENT offer roll
CH_SUPPLY   = 2   # SUPPLY offer roll
CH_REROLL   = 3   # Reroll variant (augment / supply)
CH_CHALLENGE = 4  # Challenge encounter (T21)
CH_BOSS     = 5   # Boss supporting cast (T21)
CH_SHOP     = 6   # Champion shop offers (T22)

def derive_seed(run_seed: int, node_index: int, channel: int) -> int:
    """Deterministic sub-seed. Integer-only, no hash()."""
    return (run_seed * 2654435761 + node_index * 40503 + channel * 97) & 0xFFFFFFFF
```

**Critical rule:** never feed `hash("string")` into an RNG —
`PYTHONHASHSEED` randomizes str hashing per process and silently drifts runs.
All channels are integer constants.

### 2.3 RNG usage

Each generation function creates a `random.Random(sub_seed)` instance from its
derived seed. This is a **local** RNG — it is never shared across calls, never
stored, and never reused. The generation function is pure:

```python
def roll_squad(run_seed: int, node_index: int, ...) -> list[Enemy]:
    rng = Random(derive_seed(run_seed, node_index, CH_ENEMIES))
    ...
```

---

## 3. Enemy Pool & Filtering

### 3.1 Enemy archetype fields used for generation

Each enemy in the `ENEMY_ROSTER` (from `content.py` / `enemy_roster.md`) carries:

| Field | Type | Use in generation |
|---|---|---|
| `id` | `str` | Unique identifier |
| `affinity` | `WeatherState` | Affinity theming — filtered by stage/node |
| `tier` | `int` 1–10 | Determines `P` (power budget cost) |
| `tags` | `frozenset[str]` | `human`, `corrupted`, `beast`, `spirit`, `machine` — faction filtering |
| `primary_stat` | `str` | Used by T24 for role bucketing |
| `range_` | `str` | `melee` / `ranged` — used by T24 for placement |
| `durability` | `str` | Used by T24 for front/back placement |

### 3.2 Faction filtering

- **`FIGHT` and `REWARD` nodes:** draw from the **full pool** of enemies
  (all factions). This avoids a contradiction where players would exclusively
  face CLEAR-affinity enemies (the human roster is predominantly CLEAR),
  undermining the theme-weight system in §3.4.
- **`CHALLENGE` nodes (T21):** draw from `spirit`-tagged enemies (weather
  elementals).
- **`BOSS_FIGHT` nodes (T21):** supporting cast drawn from mixed
  `human`+`corrupted` by stage; the boss itself is authored.

### 3.3 Tier eligibility by stage

Tier gates are **soft** — all tiers are eligible at all stages but heavily
weighted toward stage-appropriate ones. The real balancing factor is the
**power budget** (§4), not tier gating. The soft-gate weighting gives a
natural difficulty ramp while allowing occasional variety:

| Stage | Preferred tier centre | Weight distribution |
|---|---|---|
| 1 | T1–3 | Strong preference for T1–3, diminishing for T4+ |
| 2 | T2–4 | Strong preference for T2–4 |
| 3 | T3–5 | Strong preference for T3–5 |
| 4 | T4–6 | Strong preference for T4–6 |
| 5 | T5–7 | Strong preference for T5–7 |
| 6 | T6–9 | Strong preference for T6–9 (T10 reserved for bosses) |

Implementation: tier weight = `1.0` if within preferred range, `0.3` if ±1
of range, `0.1` if further out. T10 enemies never appear in standard
encounter generation (boss-only).

### 3.4 Affinity theming

For `FIGHT`/`REWARD` squads, the full enemy pool is available but weighted by
affinity theme to maintain continental identity:

- **50% of squad slots:** `CLEAR`-affinity enemies (weather-indifferent core).
- **30% of squad slots:** enemies whose affinity matches the **stage affinity**
  (the corrupted wildlife thematic to this continent).
- **20% of squad slots:** enemies with **any** non-Clear affinity (variety).

Integer slot rounding:
```
any_slots   = max(1, round(0.2 * team_size))
stage_slots = max(1, round(0.3 * team_size))
clear_slots = team_size - any_slots - stage_slots
```

Stage affinity is used (not live weather) — it matches boss/challenge theming
and keeps the "continent = element" identity clean. Live weather already
influences combat through Weather Favor / Affinity Clash at fight time.

---

## 4. Node Budgets & Difficulty Curve

### 4.1 Power budget formula

Every combat node has a **total enemy power budget** in `P` units (from T18).
The budget determines how many and which enemies appear:

```
node_budget = stage_base[stage] × type_mult[node_type] × variance_roll
```

| Parameter | Values |
|---|---|
| `stage_base` | See §4.2 |
| `type_mult` | `REWARD: 0.5` · `FIGHT: 1.0` · `CHALLENGE: 1.3` · `BOSS_FIGHT: authored` |
| `variance_roll` | `rng.uniform(0.85, 1.15)` — ±15% randomness per node |

**Absolute, not player-relative.** A relative curve rubber-bands and is
exploitable by deliberate under-levelling. The player's expected power is
tracked by the Tempest progression (T22) but never read by encounter generation.

### 4.2 Stage base curve

The `stage_base` values account for the fact that players retain some mid-tier
champions throughout the game (T5–7 pieces kept from earlier stages), and by
mid-game most pieces are L2 (P × 2.0). All squad size maxes are +1 from the
naive estimate. Stage base is multiplied by a **Difficulty Coefficient (DC)**
which defaults to 1.0 and is the primary player-facing difficulty dial.

After each completed playthrough, a new DC tier is unlocked: DC × 1.1 with
name "DC +N" (where N is the increment count). This allows escalating
challenge for experienced players.

**Proposed `stage_base` values (total enemy P budget per FIGHT node at DC=1.0):**

| Stage | Expected player team P | `stage_base` | Squad size max |
|---|---|---|---|
| 1 | ~2–4 P (1–3 T2–3 champs) | **3.5** | 4 |
| 2 | ~8–12 P (3–4 T3–4, some L2) | **9.0** | 5 |
| 3 | ~16–22 P (5–6 T4–5, mostly L2) | **18.0** | 6 |
| 4 | ~25–35 P (6–7 T5–6, L2) | **28.0** | 7 |
| 5 | ~38–50 P (7–8 T6–7, L2) | **42.0** | 8 |
| 6 | ~55–80 P (8–10 T7–9, L2+kept pieces) | **65.0** | 10 |

The formula `stage_base ≈ 3.5 × 1.8^(stage-1)` approximates these.

**DC application:** `effective_base = stage_base[stage] × DC`

DC is stored on the `Run` and defaults to `1.0`. The settings/meta-progression
system (T22) manages unlocking higher DC tiers.

### 4.3 Squad packing algorithm

Instead of a weighted greedy approach (which tends to produce 1 expensive + 1
cheap pick), `roll_squad` uses a **template-based smart-pick** algorithm:

1. **Select a composition template** based on squad size. Templates define
   target distributions for role-tags, tier spread, and levels. Example
   templates: "balanced" (DPS ≈ Tank+Warrior, +1 SUP), "rush" (heavy DPS),
   "fortress" (tank-heavy + sup).

2. **Fill template slots** by picking from the pool with fuzzy acceptance:
   - Each slot has a target role/tier/affinity
   - Pick candidates matching the target; if none fit, widen criteria
   - If a rolled team doesn't meet composition criteria, **reroll** (up to
     5 attempts) by continuing the same deterministic RNG stream

3. **Budget validation** — the composed squad's total P must be within
   budget ± tolerance. If over-budget after template fill, swap the most
   expensive piece for a cheaper alternative.

Generic composition target: `(DPS ≈ Tank + Warrior) + 1 SUP` with fuzzy
logic allowing deviation for interesting encounters. No rigid role matrix.

**Determinism:** All encounter lists are generated at trail creation time.
This is achieved via per-node seed derivation — encounters can be lazily
regenerated from seed at any point, or pre-generated and stored as enemy IDs
in the run save file.

```python
def roll_squad(
    rng: Random,
    budget: float,
    pool: list[EnemyDef],
    *,
    min_count: int = 2,
    max_count: int = 10,
    max_dupes: int = 2,
) -> list[Enemy]:
    """Template-based squad generation. Deterministic given rng state."""
    ...
```

> **Champion shop touchpoint:** The champion shop (T22) also needs pre-drawn
> seeds for its random offers. Since shop contents change based on player
> leveling choices, the shop uses a **seed channel per shop visit** (derived
> from run_seed + visit_index + CH_SHOP). The shop pool is filtered by
> unlocked tiers at visit time, but the RNG sequence is fixed. This means
> a player who levels differently sees different champions but the randomness
> is still reproducible from (seed, visit_index, tier_unlock_state).

### 4.4 Enemy leveling within squads

The **full roster of enemy levels (L1–L3)** is applicable for squad generation.
Since enemies exist at all levels in the content system, the encounter
generator uses them all. Level is selected as part of the template-based
picking: early stages favour L1, mid-game introduces L2, and late-game can
include L3 elites. The power budget naturally constrains this — an L2 enemy
costs more P, so fewer fit in the budget.

Level selection weights by stage:
| Stage | L1 weight | L2 weight | L3 weight |
|---|---|---|---|
| 1 | 1.0 | 0.0 | 0.0 |
| 2 | 0.8 | 0.2 | 0.0 |
| 3 | 0.5 | 0.5 | 0.0 |
| 4 | 0.3 | 0.6 | 0.1 |
| 5 | 0.1 | 0.7 | 0.2 |
| 6 | 0.0 | 0.6 | 0.4 |

---

## 5. Per-Node-Type Generation

### 5.1 `FIGHT` nodes

The bread-and-butter encounter. Pure combat, no reward beyond Amber and
Tempest progression.

```python
def generate_fight(run_seed: int, node_index: int, stage: StageDef, dc: float = 1.0) -> list[Enemy]:
    rng = Random(derive_seed(run_seed, node_index, CH_ENEMIES))
    budget = stage_base(stage.index) * dc * 1.0 * rng.uniform(0.85, 1.15)
    pool = filter_pool()
    return roll_squad(rng, budget, pool)
```

### 5.2 `REWARD` nodes

An easy fight with guaranteed loot. Budget is halved; drop table rolled
separately.

```python
def generate_reward(run_seed: int, node_index: int, stage: StageDef, dc: float = 1.0) -> tuple[list[Enemy], RewardDrop]:
    rng = Random(derive_seed(run_seed, node_index, CH_ENEMIES))
    budget = stage_base(stage.index) * dc * 0.5 * rng.uniform(0.85, 1.15)
    pool = filter_pool()
    squad = roll_squad(rng, budget, pool)

    # Drop table is a separate seed channel for isolation
    drop_rng = Random(derive_seed(run_seed, node_index, CH_SUPPLY))
    drop = roll_reward_drop(drop_rng, stage)
    return squad, drop
```

### 5.3 `AUGMENT` nodes (seed channels only)

T19 provides `CH_AUGMENT` and `CH_REROLL` channels. The actual offer logic
lives in T22 (`augments.py`). T19's contract:

```python
def augment_seed(run_seed: int, node_index: int, rerolled: bool = False) -> int:
    channel = CH_REROLL if rerolled else CH_AUGMENT
    return derive_seed(run_seed, node_index, channel)
```

### 5.4 `SUPPLY` nodes (seed channels only)

Same pattern — T19 provides `CH_SUPPLY` and `CH_REROLL`; T22 owns the logic.

### 5.5 `CHALLENGE` and `BOSS_FIGHT` nodes

Delegated entirely to T21. T19 provides `CH_CHALLENGE` and `CH_BOSS` channels.
T21 uses `roll_squad` with spirit-faction pools and authored boss data.

---

## 6. Squad Composition Rules (Team Balance)

Beyond raw budget filling, squads should feel like a **coherent force**, not a
random pile of stat-sticks. The following composition rules apply:

### 6.1 Role distribution targets

Generic composition target: **(DPS ≈ Tank + Warrior) + 1 SUP**. The system
uses fuzzy logic and allows deviation for interesting encounters — no rigid
role matrix.

Guidelines (soft, not enforced as hard constraints):
- At least 1 "tanky" piece (tanky_hp or tanky_arm durability) for squads ≥ 3
- At least 1 "support" piece (ability-focused int/ranged) for squads ≥ 5
- Remaining slots filled freely with DPS-oriented pieces
- Occasional "all-DPS rush" or "double-tank fortress" compositions are allowed
  for variety (the template system picks these ~20% of the time)

### 6.2 Duplicate limits

No more than **2 copies** of the same enemy type per squad (prevents
monotonous "6 Conscripts" waves). Exception: T1 filler in small early squads.

### 6.3 Affinity distribution within squads

Per §3.4: 50% Clear / 30% stage-themed / 20% any. Applied after role slots
are determined — each slot is then filtered to the appropriate affinity bucket
before picking an enemy.

---

## 7. Persistence & Content Versioning

### 7.1 Hybrid persistence

- **Stored in `Run` (save file):** `seed`, per-node `state` (upcoming/current/
  cleared), per-node `rerolled: bool`, per-node `pick_index: int | None`
  (for AUGMENT/SUPPLY choices).
- **Regenerated on demand:** enemy squads and offer lists — pure
  `f(seed, node_index, channel)`. Nothing extra to save.
- **No `Node` model change.** Nodes keep their pool ids from T4; the actual
  squad is materialized on arrival.

### 7.2 Content version guard

Add `Run.content_version: str` alongside the existing `Run.schema_version`.
Content edits (adding/removing enemies, changing roster stats) change
generation output for a given seed.

On save-load, if `content_version` mismatches:
- **Cleared nodes:** no impact (results already stored).
- **Upcoming nodes:** regeneration produces different squads — acceptable, the
  player hasn't seen them yet.
- **Current node (mid-fight):** warn the player; optionally offer to restart
  the current node.

**Decision:** Define the `content_version` field in T19 models, populate it
from a constant in `content.py`. Mismatch-handling UI deferred to T14.

---

## 8. Subtask Split with T21 and T24

### T19 owns:
- `derive_seed`, channel constants, `roll_squad` primitive
- `generate_fight`, `generate_reward` (human-faction squads)
- Budget formula and `stage_base` curve
- Affinity/tier filtering and composition rules
- Seed channels for AUGMENT/SUPPLY (consumed by T22)

### T21 consumes:
- `roll_squad` for challenge spirit-faction squads
- `CH_CHALLENGE` channel for challenge roster generation
- `CH_BOSS` channel for boss supporting cast
- Boss/challenge budgets are **authored** in T21, not computed by T19

### T24 consumes:
- The `list[Enemy]` output of `roll_squad` / T21 generators
- Enemy role/range/durability fields for placement bucketing
- T24 never modifies squads — it only positions them

---

## 9. Public API Surface

```python
# --- Seed derivation ---
def derive_seed(run_seed: int, node_index: int, channel: int) -> int: ...

# --- Squad generation ---
def roll_squad(
    rng: Random,
    budget: float,
    pool: list[EnemyDef],
    *,
    min_count: int = 2,
    max_count: int = 10,
    max_dupes: int = 2,
    stage_index: int = 1,
) -> list[Enemy]: ...

# --- Per-node generators ---
def generate_fight(run_seed: int, node_index: int, stage: StageDef, dc: float = 1.0) -> list[Enemy]: ...
def generate_reward(run_seed: int, node_index: int, stage: StageDef, dc: float = 1.0) -> list[Enemy]: ...

# --- Seed-only helpers for T22 ---
def augment_seed(run_seed: int, node_index: int, rerolled: bool = False) -> int: ...
def supply_seed(run_seed: int, node_index: int, rerolled: bool = False) -> int: ...

# --- Pool filtering ---
def filter_pool(*, tier_range: tuple[int, int] | None = None) -> list[EnemyDef]: ...

# --- Difficulty ---
DEFAULT_DC: float  # 1.0
def next_dc(current_dc: float) -> float: ...  # current × 1.1
```

All functions are **pure, zero Flet imports** (V.1).

---

## 10. Test Plan

See T.16 plan for full test details. Summary:

1. **Determinism:** same `seed` → byte-equal squads; two process runs with
   different `PYTHONHASHSEED` match.
2. **Sub-seed isolation:** changing node 4's outcome does not shift node 5.
3. **Budget adherence:** `Σ enemy power ≤ node_budget + BUDGET_TOLERANCE`.
4. **Composition rules:** role minimums met, duplicate limits respected, affinity
   distribution matches targets.
5. **Tier gating:** no enemy tier appears outside its stage-eligible range.
6. **Reroll:** the `CH_REROLL` channel yields a different, still-deterministic
   offer; non-rerolled nodes are unaffected.
7. **Edge cases:** budget = 0 produces minimum squad; single-enemy pool;
   empty-after-filter pool raises clear error.

---

## 11. Acceptance Criteria

1. `src/game/encounter.py` exists, pure, zero Flet imports.
2. Encounters are a deterministic function of `(seed, node_index, channel)`.
3. Squad budgets respected; reroll isolated.
4. Role composition rules enforced.
5. Tier gating by stage enforced.
6. The `content_version` field is defined.
7. `tests/game/test_encounter.py` passes.

---

## 12. Open Items Summary

| # | Question | Decision | Notes |
|---|---|---|---|
| 1 | Hard tier gates vs. weighted off-tier slots | **Soft gates (weighted)** | Power budget is the balancing factor |
| 2 | Affinity theming: stage affinity vs. live weather | **Stage affinity** | Live weather affects combat, not composition |
| 3 | Exact `stage_base` curve values | **Formula + DC scaling** | DC × 1.1 unlocked per playthrough |
| 4 | Greedy vs. template-based squad packing | **Template-based with fuzzy reroll** | Better variety and composition quality |
| 5 | Enemy leveling (L1-only vs. all levels) | **Full L1–L3 roster used** | Stage-weighted level selection |
| 6 | `content_version` timing (T19 vs. T14) | **Field in T19, UI in T14** | Cheap addition now |
| 7 | Faction filtering for FIGHT/REWARD | **Full pool (all factions)** | Avoids CLEAR-only contradiction |

---

## 13. Champion Shop Touchpoints (Brainstorm)

The champion shop system (planned for T22) has significant interaction with
T19's seed/determinism model:

**Touch points:**
- Shop offers use `CH_SHOP = 6` seed channel, derived per shop-visit index
- Shop pool filtered by player's current tier-unlock state (progression-dependent)
- The *sequence* of RNG draws is fixed per seed, but *which* draws are valid
  depends on player state at visit time

**Suggested implementation timing:**
- T19 defines `CH_SHOP` channel constant (done here)
- T22 implements the actual shop logic using `derive_seed(run_seed, visit_index, CH_SHOP)`
- Shop randomness is reproducible from `(seed, visit_index, tier_unlock_bitmap)`

**Handling non-determinism from player choices:**
- The shop seed is fixed, but the pool filter varies with player progression
- This is acceptable: two players with same seed but different choices see
  different shops (the randomness is still seeded, just filtered differently)
- For replay/spectate features, the full choice history would need to be saved
