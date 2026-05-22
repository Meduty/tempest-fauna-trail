# T5 Plan - Content Roster (`src/game/content.py`)

## 1. Scope

T5 delivers the full authored content tables that downstream systems consume at
runtime. All three rosters live in one module; nothing here touches Flet (V.1).

Primary output: `src/game/content.py`

Test output: `tests/game/test_content.py`

T5 delivers:

1. **Champion roster** — 60 `Champion` instances (6 affinities × 10 tiers),
   each at `level=1`, stats derived from archetype base tables via
   `game/scaling.scale_stat()`.
2. **Enemy roster** — 60 `Enemy` instances (30 `CLEAR`-affinity humans + 6
   corrupted wildlife per non-`CLEAR` weather), same derivation approach.
3. **Trait tag constants** — `KINSHIP_TAGS`, `CALLING_TAGS`, `ALL_TRAIT_TAGS`
   frozensets that gate `Champion.traits` validation.

Out of scope for T5:

- Ability effects — `active_ability` and `passive_ability` are stored as
  descriptive slug strings only. T20 wires them to callables.
- Trait breakpoint bonuses — tags are authored here; bonus resolution is T22.
- Boss roster — authored in `boss_roster.md`; instantiated in T21.
- Level-up stat derivation at play-time — T22 calls `scale_stat(base, tier, L)`
  at level-up; T5 only stores `level=1` entries.
- Encounter assignment — which enemies appear at which node is T19.
- Enemy formation — T24.

## 2. Prerequisites

**T18 must be completed before T5.** `content.py` imports and calls
`game.scaling.scale_stat(base, tier, level)` to produce every scaled stat. The
flat stats (attack_speed, move_speed, mana_regen, threat, attack_range,
ability_cost) are copied directly from the archetype base tables defined in §4.

## 3. Public Surface (`src/game/content.py`)

```python
# --- Roster tables -----------------------------------------------------------
CHAMPION_ROSTER: dict[str, Champion]   # 60 entries; keys are champion ids
ENEMY_ROSTER:    dict[str, Enemy]      # 60 entries; keys are enemy ids

# --- Trait constants ---------------------------------------------------------
KINSHIP_TAGS:   frozenset[str]   # 6 origin traits
CALLING_TAGS:   frozenset[str]   # ~9 role/calling tags + "Primordial"
ENEMY_TAGS:     frozenset[str]   # opaque enemy-matching tags
ALL_TRAIT_TAGS: frozenset[str]   # KINSHIP_TAGS | CALLING_TAGS (for champion validation)

# --- Lookup helpers ----------------------------------------------------------
def get_champion(champion_id: str) -> Champion        # raises KeyError on miss
def get_enemy(enemy_id: str) -> Enemy                 # raises KeyError on miss
def champions_by_affinity(weather: WeatherState) -> list[Champion]   # 10 items
def enemies_by_affinity(weather: WeatherState) -> list[Enemy]        # 6 or 30
```

All helpers are pure functions with no side effects.

## 4. Stat Block Generation via Axis Composition

### 4.0 Design principle

Stats are generated compositionally from **4 orthogonal axes**. Each axis
provides stat multipliers applied in sequence to a single standard base. No
per-combination templates exist — each unit declares 4 axis tags and the
formula produces the stat block.

### 4.1 Standard base (T1 L1)

Scaled stats (multiplied by T18 `stat_multiplier(tier, 1)` before storage):

| Stat | Base |
|------|------|
| max_hp | 600 |
| strength | 50 |
| intelligence | 50 |
| armor | 25 |
| resistance | 25 |

Flat stats (never scaled — same value at every tier):

| Stat | Base | Note |
|------|------|------|
| attack_speed | 100 | range + playstyle axes |
| mana_regen | 10 | playstyle axis |
| move_speed | 90 | authored per-unit |
| threat | 60 | authored per-unit |
| attack_range | 2 | set by range axis (not a multiplier) |
| ability_cost | 36,000 | authored per-unit; ability-specific override allowed |

`crit_chance`, `penetration`, `penetration_pct` default to `0.0 / 0 / 0.0`
for all T5 units; T20 sets non-zero values per ability kit.

### 4.2 Axis weight tables

#### Axis A — Primary stat

| Tag | STR× | INT× |
|-----|------|------|
| `str` | 1.8 | 0.2 |
| `int` | 0.2 | 1.8 |
| `hybrid` | 1.0 | 1.0 |

#### Axis B — Range

| Tag | max_hp× | armor× | res× | AS× | attack_range |
|-----|---------|--------|------|-----|--------------|
| `melee` | 1.0 | 1.3 | 1.2 | 1.1 | 1 |
| `ranged` | 0.9 | 0.8 | 0.8 | 0.9 | 3 |

#### Axis C — Durability

| Tag | max_hp× | armor× | res× | STR× | INT× |
|-----|---------|--------|------|------|------|
| `squishy` | 0.65 | 0.65 | 0.65 | 1.25 | 1.25 |
| `standard` | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| `tanky_hp` | 1.8 | 0.8 | 0.8 | 0.55 | 0.55 |
| `tanky_arm` | 0.9 | 2.0 | 2.0 | 0.55 | 0.55 |

#### Axis D — Playstyle

Controls AS vs MR split — this directly determines the cast period P.

| Tag | AS× | MR× |
|-----|-----|-----|
| `auto` | 1.3 | 0.6 |
| `hybrid` | 1.0 | 1.0 |
| `ability` | 0.75 | 1.5 |

### 4.3 Cast period (informational)

The **cast period** P describes cast frequency from flat stats — useful for
understanding tempo, not for computing damage:

```
P = ability_cost × attack_speed / (mana_regen × ENERGY_THRESHOLD)
```

At standard base (ability_cost=36,000, AS=100, MR=10): **P = 6.0**.

**Damage scaling is not derived from P.** The T3 MVP fallback cast path uses
global constants (`ABILITY_STR_COEFF=0.2`, `ABILITY_INT_COEFF=4.2`). These
are placeholders — once T20 lands, every ability owns its own handler and
computes damage from whatever stats are relevant:

```python
# e.g. scales with INT (AP)
def thunder_crash(ctx, actor, targets):
    amt = 50 + actor.base_stats["intelligence"] * 2.0
    ctx.deal_damage(actor, targets[0], amt, SourceTag.ABILITY)

# e.g. scales with target's max HP
def rending_strike(ctx, actor, targets):
    amt = targets[0].base_stats["max_hp"] * 0.18
    ctx.deal_damage(actor, targets[0], amt, SourceTag.ABILITY)

# e.g. scales with own armor (bruiser tank)
def iron_shell(ctx, actor, targets):
    amt = actor.base_stats["armor"] * 3.5
    ctx.deal_damage(actor, targets[0], amt, SourceTag.ABILITY)
```

The piece carries raw stats (`intelligence`, `strength`, `armor`, `max_hp`,
…); the ability author decides what to scale with. No scaling coefficient
lives on the piece model.

Playstyle axis shapes DPS budget via AS/MR split, not ability damage formula:

| Playstyle | AS  | MR | P   | effect                            |
|-----------|-----|----|-----|-----------------------------------|
| `ability` | 75  | 15 | 3.0 | frequent casts, fewer autos       |
| `hybrid`  | 100 | 10 | 6.0 | balanced                          |
| `auto`    | 130 | 6  | 13.0| rare casts, many autos            |

### 4.4 Composition formula

```python
def compose_stats(
    primary_stat: str,  # "str" | "int" | "hybrid"
    range_: str,        # "melee" | "ranged"
    durability: str,    # "squishy" | "standard" | "tanky_hp" | "tanky_arm"
    playstyle: str,     # "auto" | "hybrid" | "ability"
    tier: int,
    *,
    ability_cost: int = 36_000,
) -> dict[str, Any]:
    stats = dict(_BASE_STATS)
    for axis_weights in (
        _PRIMARY_STAT[primary_stat],
        _RANGE[range_],
        _DURABILITY[durability],
        _PLAYSTYLE[playstyle],
    ):
        for k, v in axis_weights.items():
            if k != "attack_range":
                stats[k] = stats[k] * v

    stats["attack_range"] = _RANGE[range_]["attack_range"]
    stats["ability_cost"] = ability_cost

    s = stat_multiplier(tier, 1)
    for k in ("max_hp", "strength", "intelligence", "armor", "resistance"):
        stats[k] = round(stats[k] * s)

    return stats
```

`compose_stats()` returns the **archetype baseline** — the budget-correct stat
block for a unit of this archetype at this tier. Individual champions then apply
additive `stat_overrides` on top of this baseline to express their unique feel
(see §5.2). The axis system guarantees all units sharing an archetype code start
from the same power budget; overrides redistribute within it.

### 4.5 Axis tag assignments per archetype

| Old archetype label | primary_stat | range | durability | playstyle |
|---------------------|-------------|-------|------------|-----------|
| Tank-HP | `str` | `melee` | `tanky_hp` | `hybrid` |
| Tank-ARM | `str` | `melee` | `tanky_arm` | `hybrid` |
| Tank-STR / ADC-STR Warrior | `str` | `melee` | `standard` | `auto` |
| Tank-INT | `int` | `melee` | `tanky_hp` | `ability` |
| APC-INT Mage | `int` | `ranged` | `squishy` | `ability` |
| APC-STR Mage | `str` | `ranged` | `squishy` | `ability` |
| APC-INT Assn | `int` | `melee` | `squishy` | `ability` |
| APC-STR Assn | `str` | `melee` | `squishy` | `auto` |
| ADC-STR Marksman | `str` | `ranged` | `standard` | `auto` |
| ADC-INT Warrior | `int` | `melee` | `standard` | `ability` |
| ADC-INT Marksman / SUP | `int` | `ranged` | `standard` | `ability` |
| Hybrid-Tank/DMG | `hybrid` | `melee` | `tanky_hp` | `hybrid` |
| Hybrid-INT/STR / Hybrid-APC/ADC | `hybrid` | `ranged` | `standard` | `hybrid` |

Units that differ within a tag (e.g. Tank-STR vs ADC-STR Warrior) are
differentiated by per-unit `ability_cost`, `move_speed`, `threat`, and ability
design (T20) — not by axis configuration.

## 5. Champion Roster Construction

### 5.1 Source

The 60 champion designs are authored in
`docs/design/content/champion_roster.md`. Each entry provides:
- `name`, `tier`, `affinity`, archetype tag
- `traits` — `[Kinship, Calling]`; T10 legendaries add `"Primordial"`
- `active_ability` / `passive_ability` — descriptive slugs for T20

### 5.2 Generation pattern

Each champion is declared as a `ChampionDef` — a plain dataclass that records
its archetype axes, identity fields, and per-unit stat tuning:

```python
@dataclass
class ChampionDef:
    id: str
    name: str
    affinity: WeatherState
    tier: int
    primary_stat: str      # "str" | "int" | "hybrid"
    range_: str            # "melee" | "ranged"
    durability: str        # "squishy" | "standard" | "tanky_hp" | "tanky_arm"
    playstyle: str         # "auto" | "hybrid" | "ability"
    traits: list[str]
    active_ability: str
    passive_ability: str
    ability_cost: int = 36_000
    move_speed: int = 90
    threat: int = 60
    stat_overrides: dict[str, int] = field(default_factory=dict)
    # Keys: any scalable stat — "max_hp", "strength", "intelligence",
    # "armor", "resistance". Values: additive delta from archetype baseline.
    # Example: {"intelligence": +15, "strength": -10} shifts budget toward INT.
```

`_build_champion` materialises a `ChampionDef` into a `Champion`:

```python
def _build_champion(d: ChampionDef) -> Champion:
    base = compose_stats(
        d.primary_stat, d.range_, d.durability, d.playstyle,
        d.tier, ability_cost=d.ability_cost,
    )
    stats = {k: base[k] + d.stat_overrides.get(k, 0) for k in base}
    return Champion(
        id=d.id, name=d.name, affinity=d.affinity,
        role=_ROLE_FROM_AXES[d.primary_stat][d.range_],
        tier=d.tier, level=1,
        max_hp=max(1, stats["max_hp"]),
        strength=max(0, stats["strength"]),
        intelligence=max(0, stats["intelligence"]),
        armor=max(0, stats["armor"]),
        resistance=max(0, stats["resistance"]),
        attack_speed=int(stats["attack_speed"]),
        mana_regen=int(stats["mana_regen"]),
        move_speed=d.move_speed,
        threat=d.threat,
        attack_range=stats["attack_range"],
        ability_cost=d.ability_cost,
        traits=d.traits,
        active_ability=d.active_ability,
        passive_ability=d.passive_ability,
    )
```

`CHAMPION_ROSTER` is built by calling `_build_champion(d)` for every
`ChampionDef` in the authored list and collecting into a `dict` keyed by `id`.

**Budget invariant:** `stat_overrides` on scalable stats should roughly sum to
zero in equivalent combat value (e.g. `+INT` offset by `-STR`). A
module-level assertion at import time flags any champion whose override sum
exceeds ±15% of the baseline total stat budget:

```python
def _assert_budget(d: ChampionDef, base: dict) -> None:
    scalable = ("max_hp", "strength", "intelligence", "armor", "resistance")
    budget = sum(base[k] for k in scalable)
    drift = sum(d.stat_overrides.get(k, 0) for k in scalable)
    assert abs(drift / budget) <= 0.15, (
        f"{d.id}: stat_overrides drift {drift/budget:.1%} exceeds ±15% budget"
    )
```

### 5.3 Champion ID convention

`"champ_{snake_case_name}"` — e.g. `"champ_dawnwisp"`,
`"champ_veldt_pronghorn"`, `"champ_aurion"`.

### 5.4 Ability slug convention

`active_ability` = `"{champion_id}.active"`, `passive_ability` =
`"{champion_id}.passive"`. T20 looks these up in the ability registry.

## 6. Trait Tag Constants

Defined from `docs/design/content/trait_catalog.md`:

```python
KINSHIP_TAGS = frozenset({
    "Beast", "Skyborn", "Scaled", "Tidekin", "Swarm", "Spirit",
})

CALLING_TAGS = frozenset({
    "Skirmisher", "Warden", "Mender", "Mystic", "Bulwark",
    "Drifter", "Harbinger", "Emissary", "Primordial",
})

ALL_TRAIT_TAGS = KINSHIP_TAGS | CALLING_TAGS

ENEMY_TAGS = frozenset({
    "human", "beast", "corrupted", "machine",
})
```

Every champion's `traits` list must be a non-empty subset of `ALL_TRAIT_TAGS`.
This is enforced in `Champion.__post_init__` (T1 validation already checks for
non-empty strings and uniqueness; T5 adds the tag-set membership check in a
module-level assert during roster construction, not in the model itself — the
model stays content-agnostic per V.1).

## 7. Enemy Roster

### 7.1 Source

Full 60-enemy design in `docs/design/content/enemy_roster.md`.

Distribution:
- 30 `CLEAR`-affinity humans (tiers 1-6, see tier table in enemy_roster.md)
- 6 corrupted wildlife per non-`CLEAR` weather (Rain, Snow, Cloudy, Mist,
  Thunder), spread across tiers 3-7

### 7.2 Generation pattern

Enemies use the same `EnemyDef` + `_build_enemy` pattern as champions (§5.2),
with the same `stat_overrides` tuning mechanism. The `EnemyDef` omits `traits`
(enemies have no synergy system) and replaces it with a `tags` field used by
T24/augment matchers:

```python
@dataclass
class EnemyDef:
    id: str
    name: str
    affinity: WeatherState
    tier: int
    primary_stat: str
    range_: str
    durability: str
    playstyle: str
    tags: frozenset[str]           # "human", "beast", "corrupted", "machine"
    active_ability: str
    passive_ability: str
    ability_cost: int = 36_000
    move_speed: int = 90
    threat: int = 60
    stat_overrides: dict[str, int] = field(default_factory=dict)
```

Enemy ID convention: `"enemy_{snake_case_name}"`.

Enemy `active_ability` / `passive_ability` are slug strings using the same
`"{enemy_id}.active"` convention as champions.

Enemy `tags` are **not** stored in the `Enemy` model (the model has no `tags`
field in T1). Tags are stored separately as a module-level mapping:

```python
ENEMY_TAGS_MAP: dict[str, frozenset[str]] = {
    "enemy_company_rifleman": frozenset({"human"}),
    ...
}
```

`T24` and augment matchers read this dict. It does not affect combat math.

### 7.3 CLEAR-affinity tier/count distribution

Per `enemy_roster.md` §"Tier distribution":

| Tier | Clear count |
|------|-------------|
| 1    | 5           |
| 2    | 4           |
| 3    | 3           |
| 4    | 3           |
| 5    | 3           |
| 6    | 4           |
| 7–10 | 4 + (reserved for T21 bosses) |

Tiers 7+ CLEAR enemies are authored but marked for boss/sub-boss use (T21);
they still live in `ENEMY_ROSTER` and can be drawn by encounter gen.

### 7.4 Non-CLEAR distribution

One enemy per non-CLEAR weather per tier-band:
- Rain / Snow / Cloudy / Mist / Thunder: 2 at tier 3–4, 2 at tier 5–6, 2 at
  tier 7–8 (not all weather-tiers need exact same spread — see enemy_roster.md).

## 8. Module Structure

```
src/game/content.py
├── _BASE_STATS: dict[str, float]            # standard T1L1 base values
├── _PRIMARY_STAT, _RANGE, _DURABILITY, _PLAYSTYLE  # axis weight dicts
├── _ROLE_FROM_AXES: dict[str, dict[str, str]]       # (primary_stat, range) → role
├── compose_stats(primary_stat, range_, durability, playstyle, tier, *, ability_cost)
│                                            → dict[str, Any]
├── ChampionDef  (dataclass)                 # authored champion declaration
├── EnemyDef     (dataclass)                 # authored enemy declaration
├── _assert_budget(def, base)               # budget-drift guard (called at module load)
├── _build_champion(ChampionDef) → Champion  # private factory
├── _build_enemy(EnemyDef)       → Enemy     # private factory
│
├── KINSHIP_TAGS, CALLING_TAGS, ALL_TRAIT_TAGS, ENEMY_TAGS   # frozensets
├── CHAMPION_ROSTER: dict[str, Champion]                      # 60 entries
├── ENEMY_ROSTER:    dict[str, Enemy]                         # 60 entries
├── ENEMY_TAGS_MAP:  dict[str, frozenset[str]]                # tag lookup
│
├── get_champion(id) → Champion
├── get_enemy(id) → Enemy
├── champions_by_affinity(weather) → list[Champion]
└── enemies_by_affinity(weather)   → list[Enemy]
```

Private helpers are prefixed with `_` and not part of the public surface.
`compose_stats` is public so T22 can re-derive stats at level-up without
duplicating axis logic.

## 9. Out of Scope (T5)

| Item | Handled in |
|------|------------|
| Ability effect callables | T20 |
| Trait breakpoint bonus resolution | T22 |
| Level-up (L2 / L3) stat derivation | T22 |
| Boss pieces + phase data | T21 |
| Encounter node assignments | T19 |
| Enemy formation planner | T24 |
| Augment/item content | T22 |
| Shop offer weights | T22 |

## 10. Acceptance Criteria / Test Plan (`tests/game/test_content.py`)

### 10.1 Schema correctness
- Every champion in `CHAMPION_ROSTER` constructs without raising `ValueError`
  (the `Champion.__post_init__` validator passes for all 60 entries).
- Every enemy in `ENEMY_ROSTER` constructs without raising `ValueError`.

### 10.2 Roster shape
- `len(CHAMPION_ROSTER) == 60`
- For each `WeatherState`, `len(champions_by_affinity(w)) == 10`
- `len(ENEMY_ROSTER) == 60`
- `len(enemies_by_affinity(WeatherState.CLEAR)) == 30`
- For each non-`CLEAR` `WeatherState`, `len(enemies_by_affinity(w)) == 6`

### 10.3 ID uniqueness and format
- No duplicate champion IDs; no duplicate enemy IDs; champion/enemy ID
  namespaces are disjoint.
- All champion IDs match `re.fullmatch(r"champ_[a-z0-9_]+", id)`.
- All enemy IDs match `re.fullmatch(r"enemy_[a-z0-9_]+", id)`.

### 10.4 Level lock
- All stored champions have `level == 1`.
- All stored enemies have `level == 1`.

### 10.5 Trait validity
- For every champion, each tag in `traits` is a member of `ALL_TRAIT_TAGS`.
- Every T10 champion has `"Primordial"` in its traits.
- No champion has an empty `traits` list.

### 10.6 Stat monotonicity (scaling sanity)
- For any two champions sharing the same archetype template, the higher-tier
  one has greater `max_hp`, `strength` + `intelligence` (primary stat), and
  `armor + resistance` than the lower-tier one (i.e., `scale_stat` is
  strictly monotone in `tier`).
- Flat stats (`attack_speed`, `attack_range`) are identical for same-template
  champions regardless of tier.

### 10.7 Lookup helpers
- `get_champion("champ_dawnwisp")` returns the correct champion object.
- `get_champion("nonexistent_id")` raises `KeyError`.
- `get_enemy("enemy_company_rifleman")` returns the correct enemy object.
- `champions_by_affinity(WeatherState.CLEAR)` returns exactly 10 champions all
  with `affinity == WeatherState.CLEAR`.

### 10.8 Enemy tags map
- Every key in `ENEMY_TAGS_MAP` exists as a key in `ENEMY_ROSTER`.
- Every value in `ENEMY_TAGS_MAP` is a non-empty `frozenset` of strings from
  `ENEMY_TAGS`.
