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

- **`FIGHT` and `REWARD` nodes:** draw from `human`-tagged enemies only (the
  Reclamation's mundane force).
- **`CHALLENGE` nodes (T21):** draw from `spirit`-tagged enemies (weather
  elementals).
- **`BOSS_FIGHT` nodes (T21):** supporting cast drawn from mixed
  `human`+`corrupted` by stage; the boss itself is authored.

### 3.3 Tier eligibility by stage

Not every tier is available at every stage. Enemy tiers are **gated by stage
difficulty** to maintain progression feel:

| Stage | Eligible enemy tiers | Rationale |
|---|---|---|
| 1 | 1–3 | Tutorial — cheap infantry + first corrupted |
| 2 | 1–4 | Introduce mid-tier specialists |
| 3 | 2–5 | Drop T1 filler, add T5 mid-elites |
| 4 | 3–6 | Professional core enters |
| 5 | 4–7 | Senior officers, hybrid corrupted |
| 6 | 5–9 | Full elite range (T10 is bosses only) |

> **⚠ DECISION NEEDED:** These tier gates are a suggestion. An alternative is
> to allow all tiers but weight heavily toward stage-appropriate ones (e.g.
> 80% weight on tiers within ±1 of stage). The hard-gate approach is simpler
> and makes early stages feel distinct; the weighted approach produces
> occasional surprising variety. **Recommendation:** hard-gate for MVP, add
> weighted off-tier "wild card" slots in a later pass.

### 3.4 Affinity theming

For `FIGHT`/`REWARD` squads (human faction), most enemies are `CLEAR`-affinity
(the bulk of the human roster — 50% of all enemies). The remaining 10% per
non-Clear weather are drawn based on the **stage's authored affinity**:

- **50% of squad slots:** `CLEAR`-affinity humans (weather-indifferent core).
- **30% of squad slots:** enemies whose affinity matches the **stage affinity**
  (the corrupted wildlife thematic to this continent).
- **20% of squad slots:** enemies with **any** non-Clear affinity (variety).

Integer slot rounding:
```
any_slots   = max(1, round(0.2 * team_size))
stage_slots = max(1, round(0.3 * team_size))
clear_slots = team_size - any_slots - stage_slots
```

> **⚠ DECISION NEEDED:** Whether to use the stage affinity or the **live node
> weather** for the 30% themed slots. Using stage affinity is more predictable
> for the player and thematically consistent (Africa always has Mist-corrupted
> creatures). Using live weather adds run-to-run variety but muddies the
> continental identity. **Recommendation:** stage affinity — it matches the
> boss/challenge theming and keeps the "continent = element" identity clean.
> Live weather already influences combat through Weather Favor / Affinity
> Clash at fight time, so encounter *composition* doesn't need to react to it
> as well.

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

The `stage_base` values should produce a smooth exponential ramp that
tracks the expected player team power at each stage. Given:
- Player starts at Tempest rank 1 (1 deployed champion)
- By stage 6 end, rank ~8–10 (8–10 deployed champions)
- Champions average tier ~T3 at stage 1, ~T7 at stage 6
- `P(T3,L1) ≈ 1.84`, `P(T7,L1) ≈ 4.13`

**Proposed `stage_base` values (total enemy P budget per FIGHT node):**

| Stage | Expected player team P | Suggested `stage_base` | Squad size (est.) |
|---|---|---|---|
| 1 | ~2–4 P (1–3 T2–3 champs) | **3.0** | 2–3 enemies |
| 2 | ~6–10 P (3–4 T3–4 champs) | **7.0** | 3–4 enemies |
| 3 | ~12–18 P (5–6 T4–5 champs) | **14.0** | 4–5 enemies |
| 4 | ~20–28 P (6–7 T5–6 champs) | **23.0** | 5–6 enemies |
| 5 | ~30–40 P (7–8 T6–7 champs) | **34.0** | 6–7 enemies |
| 6 | ~45–65 P (8–10 T7–9 champs) | **52.0** | 7–9 enemies |

> **⚠ DECISION NEEDED:** These stage_base numbers are derived from rough power
> projections. The exact values are a **tuning job** that requires playtesting.
> The formula `stage_base ≈ 3.0 × 1.6^(stage-1)` gives a smooth exponential
> that roughly matches the above. **Recommendation:** ship the formula as the
> default with a `STAGE_BASE_OVERRIDE: dict[int, float]` for hand-tuning
> after playtest.

### 4.3 Squad packing algorithm

`roll_squad` fills a squad against the budget using a **weighted greedy** approach:

```python
def roll_squad(
    rng: Random,
    budget: float,
    pool: list[EnemyDef],
    *,
    min_count: int = 2,
    max_count: int = 10,
) -> list[Enemy]:
    """Pack enemies into a budget. Deterministic given rng state."""
    squad: list[Enemy] = []
    remaining = budget

    while remaining > 0 and len(squad) < max_count:
        # Filter pool to affordable enemies
        affordable = [e for e in pool if power(e.tier, 1) <= remaining + BUDGET_TOLERANCE]
        if not affordable:
            break

        # Weight toward enemies closer to remaining budget (prefer filling cleanly)
        weights = [_budget_weight(e, remaining) for e in affordable]
        pick = rng.choices(affordable, weights=weights, k=1)[0]

        squad.append(instantiate_enemy(pick, level=1))
        remaining -= power(pick.tier, 1)

    # Ensure minimum squad size
    if len(squad) < min_count:
        cheapest = min(pool, key=lambda e: e.tier)
        while len(squad) < min_count:
            squad.append(instantiate_enemy(cheapest, level=1))

    return squad
```

**Budget weight function:** enemies whose P cost is close to the remaining
budget are weighted higher, producing tight budget-filling without systematic
over-/under-spend:

```python
BUDGET_TOLERANCE = 0.5  # Allow slight overshoot

def _budget_weight(enemy_def: EnemyDef, remaining: float) -> float:
    cost = power(enemy_def.tier, 1)
    if cost > remaining + BUDGET_TOLERANCE:
        return 0.0
    # Prefer enemies that fill ~40-80% of remaining budget
    fill_ratio = cost / max(remaining, 0.01)
    if fill_ratio < 0.2:
        return 0.3    # very cheap filler — low preference
    if fill_ratio <= 0.8:
        return 1.0    # good fit
    return 0.7        # expensive — acceptable but not first choice
```

> **⚠ DECISION NEEDED:** Whether to use `rng.choices` (weighted random) or a
> deterministic greedy "pick highest affordable tier" approach. Weighted random
> produces more varied squads across nodes; greedy produces tighter budgets.
> **Recommendation:** weighted random — variety is more important than
> pixel-perfect budget adherence, and the ±15% variance roll already fuzzes
> budgets.

### 4.4 Enemy leveling within squads

All enemies in standard `FIGHT`/`REWARD` encounters spawn at **level 1**.
Higher difficulty is expressed through higher-tier enemies, not leveled-up
copies.

> **⚠ DECISION NEEDED:** Whether late-stage encounters (stage 5–6) should
> sometimes include **level-2** enemies (representing elite versions). This
> adds variety and threat but complicates the budget math (a L2 T5 enemy costs
> P=3.38, same as a L1 T7). **Recommendation:** defer to post-MVP. Keep L1
> only for now; the tier gate already provides sufficient difficulty scaling.

---

## 5. Per-Node-Type Generation

### 5.1 `FIGHT` nodes

The bread-and-butter encounter. Pure combat, no reward beyond Amber and
Tempest progression.

```python
def generate_fight(run_seed: int, node_index: int, stage: StageDef) -> list[Enemy]:
    rng = Random(derive_seed(run_seed, node_index, CH_ENEMIES))
    budget = stage_base(stage.index) * 1.0 * rng.uniform(0.85, 1.15)
    pool = filter_pool(stage, faction="human")
    return roll_squad(rng, budget, pool)
```

### 5.2 `REWARD` nodes

An easy fight with guaranteed loot. Budget is halved; drop table rolled
separately.

```python
def generate_reward(run_seed: int, node_index: int, stage: StageDef) -> tuple[list[Enemy], RewardDrop]:
    rng = Random(derive_seed(run_seed, node_index, CH_ENEMIES))
    budget = stage_base(stage.index) * 0.5 * rng.uniform(0.85, 1.15)
    pool = filter_pool(stage, faction="human")
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

Each squad aims for a role mix based on squad size:

| Squad size | Tanks | DPS (ADC/APC) | Support | Hybrid |
|---|---|---|---|---|
| 2–3 | 1 | 1–2 | 0 | 0 |
| 4–5 | 1–2 | 2–3 | 0–1 | 0 |
| 6–7 | 2 | 3–4 | 1 | 0–1 |
| 8–10 | 2–3 | 4–5 | 1–2 | 1 |

**Implementation:** the packing algorithm fills role **slots** before budget
slots. First, ensure minimum role counts (at least 1 tank for squads ≥3, at
least 1 support for squads ≥5), then fill remaining slots freely.

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

> **⚠ DECISION NEEDED:** Whether `content_version` lands now (T19) or at T14
> (save/load). **Recommendation:** define the field in T19 models, populate it
> from a constant in `content.py`, but defer the mismatch-handling UI to T14.

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
    role_targets: dict[str, int] | None = None,
    max_dupes: int = 2,
) -> list[Enemy]: ...

# --- Per-node generators ---
def generate_fight(run_seed: int, node_index: int, stage: StageDef) -> list[Enemy]: ...
def generate_reward(run_seed: int, node_index: int, stage: StageDef) -> tuple[list[Enemy], RewardDrop]: ...

# --- Seed-only helpers for T22 ---
def augment_seed(run_seed: int, node_index: int, rerolled: bool = False) -> int: ...
def supply_seed(run_seed: int, node_index: int, rerolled: bool = False) -> int: ...

# --- Pool filtering ---
def filter_pool(stage: StageDef, *, faction: str, tier_range: tuple[int, int] | None = None) -> list[EnemyDef]: ...
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

| # | Question | Recommendation | Impact if deferred |
|---|---|---|---|
| 1 | Hard tier gates vs. weighted off-tier slots | Hard-gate for MVP | Low — can soften later |
| 2 | Affinity theming: stage affinity vs. live weather | Stage affinity | Low — live weather affects combat, not composition |
| 3 | Exact `stage_base` curve values | Formula `3.0 × 1.6^(s-1)` + override dict | Must be tuned in playtest |
| 4 | Greedy vs. weighted-random squad packing | Weighted random | Low — either is deterministic |
| 5 | Enemy leveling (L2 in late stages) | Defer to post-MVP | Low — tier gates suffice |
| 6 | `content_version` timing (T19 vs. T14) | Define field in T19, handle UI in T14 | Low — field is cheap |
