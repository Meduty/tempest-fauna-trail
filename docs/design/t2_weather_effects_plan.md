# T2 Plan - Weather Effects (`src/game/weather_effects.py`)

## 1. Scope

T2 delivers the weather → combat modifier system. Pure logic, zero I/O, zero
Flet (V.1 holds).

Primary output: `src/game/weather_effects.py`

Test output: `tests/game/test_weather_effects.py`

This revision replaces the original symmetric "Variant B" matrix with a
**directional predator/prey ring** and splits weather into **two decoupled
systems** (§4). It supersedes the pre-rework §3/§4/§10.

## 2. Weather State Enum (6 values) — implemented

`WeatherState` already carries the 6 values and `from_openweather_id` (see
`models.py`). Mapping is unchanged:

| OpenWeather ID range | OW main | `WeatherState` |
|---|---|---|
| 200–232 | Thunderstorm | `THUNDER` |
| 300–321 + 500–531 | Drizzle + Rain | `RAIN` |
| 600–622 | Snow | `SNOW` |
| 701–781 | Atmosphere (mist/fog/haze) | `MIST` |
| 800 | Clear | `CLEAR` |
| 801–804 | Clouds | `CLOUDY` |

No enum change in this revision.

## 3. The Affinity Cycle — Directional Predator/Prey Ring

The 5 active weathers form a **directed ring** ordered as a meteorological
intensity ramp:

```
MIST → CLOUDY → RAIN → SNOW → THUNDER → (back to MIST)
```

`CLEAR` sits OUTSIDE the ring — no prey, no predator, inert in both systems.

For any weather `W` at ring index `i`:

- **primary prey** = `i-1` (the previous, milder stage `W` overtakes)
- **secondary prey** = `i-2`
- **primary predator** = `i+1` (the stage that overtakes `W`)
- **secondary predator** = `i+2`

In a 5-ring every active pair is related — 2 prey + 2 predators, no neutral
pair among the active five. Only `CLEAR` is unrelated to everything.

| Weather | primary prey | secondary prey | primary predator | secondary predator |
|---|---|---|---|---|
| `MIST` | Thunder | Snow | Cloudy | Rain |
| `CLOUDY` | Mist | Thunder | Rain | Snow |
| `RAIN` | Cloudy | Mist | Snow | Thunder |
| `SNOW` | Rain | Cloudy | Thunder | Mist |
| `THUNDER` | Snow | Rain | Mist | Cloudy |

Single primitive `ring_relation(a, b)` answers "how does `a` stand relative to
`b`" and feeds **both** systems below. `RingRelation` ∈ {`SELF`,
`PRIMARY_PREDATOR`, `SECONDARY_PREDATOR`, `SECONDARY_PREY`, `PRIMARY_PREY`,
`NEUTRAL`}. `NEUTRAL` iff either side is `CLEAR`.

```
d = (index(a) - index(b)) mod 5
0 -> SELF   1 -> PRIMARY_PREDATOR   2 -> SECONDARY_PREDATOR
3 -> SECONDARY_PREY                 4 -> PRIMARY_PREY
```

## 4. Two Decoupled Systems

Weather contributes **two independent modifiers**. They answer different
questions and are **never summed into one "best affinity" score**:

- **System A — Node Weather** (§5): does the node's weather suit my piece's
  affinity? Determined by the piece's affinity vs the *node weather*.
  **Enemy-independent.** A Rain team always wants Rain weather, no matter who
  it fights.
- **System B — Damage Triangle** (§6): does my affinity beat the enemy's
  affinity? Determined by *attacker affinity vs defender affinity*.
  **Weather-independent.** A Rain team always dislikes Snow enemies, no matter
  the weather.

Worked case: a Rain team at a Rain node fighting Snow enemies has **great
weather (A)** and a **bad matchup (B)** at the same time — both facts hold,
neither cancels the other. The player evaluates the two axes separately.

## 5. System A — Node Weather → Affinity Buff/Debuff

The node's weather `W` buffs/debuffs every piece by its `affinity` `A`, on five
tiers. **Self is the strict maximum** — a piece is strongest in its own
weather, full stop.

| `ring_relation(A, W)` | Tier | Magnitude |
|---|---|---|
| `SELF` (`A == W`) | strong buff | `+10%` |
| `PRIMARY_PREDATOR` (`A` hunts `W`) | medium buff | `+6%` |
| `SECONDARY_PREDATOR` | weak buff | `+3%` |
| `PRIMARY_PREY` (`W` hunts `A`) | medium debuff | `−6%` |
| `SECONDARY_PREY` | weak debuff | `−3%` |
| `NEUTRAL` (Clear on either side) | none | identity |

Magnitude = `±10% × tier_scalar`, with `tier_scalar = {strong: 1.0,
medium: 0.6, weak: 0.3}`. Buffs use all three tiers; debuffs only reach medium
(no strong debuff — weather is net-kind, a bad-weather node never bricks a team
on its own).

### 5.1 Affinity perspective (what each weather does to each affinity)

| Affinity | strong+ | medium+ | weak+ | medium− | weak− |
|---|---|---|---|---|---|
| `MIST` | Mist | Thunder | Snow | Cloudy | Rain |
| `CLOUDY` | Cloudy | Mist | Thunder | Rain | Snow |
| `RAIN` | Rain | Cloudy | Mist | Snow | Thunder |
| `SNOW` | Snow | Rain | Cloudy | Thunder | Mist |
| `THUNDER` | Thunder | Snow | Rain | Mist | Cloudy |
| `CLEAR` | — | — | — | — | — |

Narrative: a piece is **strongest at home**, **decent on its hunting grounds**
(its prey's weather), and **weak in its predator's territory**. `CLEAR`
affinity is untouched by every weather; `CLEAR` weather touches no affinity.

### 5.2 Per-weather stat effect (unique per weather)

Each weather owns one buff stat-set and one debuff stat-set. The base
magnitudes below are the **strong tier** (`±10%`); `combat_modifier` scales the
deviation from `1.0` by `tier_scalar`.

| Weather | Buff stats | Debuff stats | Flavor |
|---|---|---|---|
| `CLOUDY` | `HP`, `RES` | `AS` | Insulating cover; haze slows attack cadence |
| `MIST` | `MS`, `THR` | `attack_range` | Vanish-step + ambush; sight collapses |
| `SNOW` | `Armor`, `RES` | `MS` | Frosted hide; cold locks limbs |
| `RAIN` | `AS`, `MR` | `STR` | Slick momentum + mana flow; soaked grip |
| `THUNDER` | `STR`, `AS` | `INT`, `MR` | Charged power; static jams casting |

- `MIST` debuff is the only flat-integer effect: base `attack_range −1`.
  Scaled-and-rounded it yields `−1` at the medium tier and `0` at the weak
  tier automatically (`round(-0.6) == -1`, `round(-0.3) == 0`) — no
  special-case branch needed. Clamp `attack_range ≥ 1`.
- Applied **at combat init** as a one-shot snapshot (matches the combat
  proposal — the simulator runs off snapshotted stats). Mid-fight weather
  change is out of scope.

## 6. System B — Affinity Damage Triangle

Every instance of damage (auto-attack **and** ability) is flagged with the
**attacker's affinity**. A single multiplier is applied per hit, from
`ring_relation(attacker_affinity, defender_affinity)`:

| Attacker vs defender | × dealt |
|---|---|
| `PRIMARY_PREDATOR` | `1.10` |
| `SECONDARY_PREDATOR` | `1.05` |
| `SELF` (mirror) / `NEUTRAL` (Clear) | `1.00` |
| `SECONDARY_PREY` | `0.95` |
| `PRIMARY_PREY` | `0.90` |

One modifier per hit — **not** a double-apply. The predator's edge is emergent:
its outgoing hits ride `1.10` while the prey's return hits ride `0.90`, so the
exchange ratio is `1.10 / 0.90 ≈ 1.22×` for a primary counter (`1.05 / 0.95 ≈
1.11×` for a secondary). A hard counter is a real edge, still beatable —
deliberately tamer than a raw `±20%` (`1.5×` exchange) would be.

`CLEAR` attackers and `CLEAR` defenders always resolve to `1.00` — `CLEAR`
neither counters nor is countered.

## 7. Shop Drop Weight (Prep Phase)

`shop_weight` biases the Prep shop toward affinities the **upcoming node
weather** favours (System A only — matchup bias would need an enemy preview,
deferred). Consumer arrives with the shop task (post-T5).

| `ring_relation(affinity, weather)` | weight |
|---|---|
| `SELF` | `2.0` |
| `PRIMARY_PREDATOR` | `1.5` |
| `SECONDARY_PREDATOR` | `1.2` |
| `SECONDARY_PREY` | `0.8` |
| `PRIMARY_PREY` | `0.6` |
| `NEUTRAL` (Clear either side) | `1.0` |

## 8. Module API (`src/game/weather_effects.py`)

```python
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from src.game.models import WeatherState

class RingRelation(str, Enum):
    SELF = "self"
    PRIMARY_PREDATOR = "primary_predator"
    SECONDARY_PREDATOR = "secondary_predator"
    SECONDARY_PREY = "secondary_prey"
    PRIMARY_PREY = "primary_prey"
    NEUTRAL = "neutral"                       # Clear on either side

CYCLE_ORDER: tuple[WeatherState, ...]         # (MIST, CLOUDY, RAIN, SNOW, THUNDER)

# Tier scalars for System A magnitude.
TIER_SCALAR: dict[str, float]                 # strong 1.0 / medium 0.6 / weak 0.3

@dataclass(frozen=True, slots=True)
class CombatModifier:
    str_mult: float = 1.0
    int_mult: float = 1.0
    as_mult: float = 1.0
    ms_mult: float = 1.0
    mr_mult: float = 1.0
    hp_mult: float = 1.0
    armor_mult: float = 1.0
    res_mult: float = 1.0
    thr_mult: float = 1.0
    attack_range_delta: int = 0

IDENTITY: CombatModifier
WEATHER_BUFF_BASE: dict[WeatherState, CombatModifier]    # strong-tier buff effect
WEATHER_DEBUFF_BASE: dict[WeatherState, CombatModifier]  # strong-tier debuff effect
DAMAGE_MULT: dict[RingRelation, float]                   # System B table

def ring_relation(a: WeatherState, b: WeatherState) -> RingRelation

# System A
def combat_modifier(affinity: WeatherState, weather: WeatherState) -> CombatModifier
    # picks buff/debuff base by ring_relation, scales deviation by tier scalar

# System B
def damage_modifier(attacker_affinity: WeatherState,
                    defender_affinity: WeatherState) -> float

def shop_weight(affinity: WeatherState, weather: WeatherState) -> float

# Combat-init bridge — System A only. Does NOT mutate the piece; copies
# piece.affinity into the snapshot so the combat engine can do System B per hit.
def apply_weather(piece, weather: WeatherState) -> CombatPieceState
```

`apply_weather` (formerly `apply_modifier`) applies **only System A** at combat
init. **System B is not snapshottable** — its multiplier depends on the
defender, so it is resolved per hit inside the combat engine via
`damage_modifier`. This requires the snapshot to carry affinity (§10.1).

## 9. Tests (`tests/game/test_weather_effects.py`)

Ring + relation:

- `CYCLE_ORDER` is exactly `(MIST, CLOUDY, RAIN, SNOW, THUNDER)`; `CLEAR` absent.
- `ring_relation` returns the correct member for all `6×6` affinity pairs;
  `NEUTRAL` whenever either side is `CLEAR`; `SELF` on the diagonal.
- Directionality: `ring_relation(a, b) == PRIMARY_PREDATOR` ⇔
  `ring_relation(b, a) == PRIMARY_PREY` (same for secondary).

System A:

- `combat_modifier`: `SELF` → strong (`+10%`), `PRIMARY_PREDATOR` → medium
  (`+6%`), `SECONDARY_PREDATOR` → weak (`+3%`), `PRIMARY_PREY` → medium
  (`−6%`), `SECONDARY_PREY` → weak (`−3%`).
- Self is the strict maximum buff for every affinity.
- `combat_modifier` returns `IDENTITY` whenever either side is `CLEAR`.
- §5.1 affinity-perspective matrix matches `combat_modifier` for every pair.
- `MIST` debuff: `attack_range_delta == -1` at medium tier, `0` at weak tier.

System B:

- `damage_modifier`: `1.10 / 1.05 / 1.00 / 0.95 / 0.90` by relation.
- Mirror (`a == a`) and any `CLEAR` pairing → `1.00`.
- Monotonic: predator `> 1.0 >` prey; primary magnitude `>` secondary.
- Exchange ratio `damage_modifier(pred, prey) / damage_modifier(prey, pred)`
  ≈ `1.22` (primary), `≈ 1.11` (secondary).

Other:

- `shop_weight`: `2.0 / 1.5 / 1.2 / 0.8 / 0.6` by relation, `1.0` for `CLEAR`.
- `apply_weather` scales stats by System A, clamps `attack_range ≥ 1`, and
  copies `piece.affinity` onto the returned `CombatPieceState`.
- Determinism: repeated calls with identical args return equal objects.

## 10. Changes Required Outside `weather_effects.py`

### 10.1 `src/game/models.py`

- **`CombatPieceState` gains `affinity: WeatherState`** — the combat engine
  needs each piece's affinity at damage time for System B (target-dependent,
  cannot be pre-snapshotted). Update `__post_init__`, `to_dict`, `from_dict`.
- `Champion` / `Enemy` already carry `affinity`; `WeatherState` already has 6
  values + `from_openweather_id`. No change there.

### 10.2 `src/game/combat.py` (T3 — already implemented)

- The damage step multiplies raw damage by
  `damage_modifier(attacker.affinity, defender.affinity)` before armor/resist.
  New per-hit hook; T3 is shipped → this is an edit + full retest.
- `apply_modifier` call sites rename to `apply_weather`.

### 10.3 T20 (ability framework)

- Ability damage must route through the same affinity-tagged damage path so
  System B applies to spells, not only auto-attacks. Note as a T20 dependency.

### 10.4 `SPEC.md`

- V.5 / V.6 unchanged (enum + single `affinity` field still hold).
- New B-section backprop entries: `CombatPieceState.affinity` field add; the
  T3 `combat.py` damage-hook edit + retest.
- D-section: record the two-system weather model and that System B per-hit
  resolution is a combat-engine extension.
- §T.2 row: effort stays M (matrix + two systems + tests).

### 10.5 Existing tests

- `tests/game/test_weather_effects.py` is rewritten for the new ring and the
  two systems. `test_combat.py` updates for the System B damage hook and the
  new `CombatPieceState.affinity` field.

## 11. Locked Decisions

- **Cycle**: directed ring `MIST → CLOUDY → RAIN → SNOW → THUNDER`; `CLEAR`
  outside, inert in both systems.
- **Two decoupled systems**: System A (node weather, enemy-independent) and
  System B (damage triangle, weather-independent) are evaluated separately,
  never summed.
- **System A tiers**: strong / medium / weak buff = `+10% / +6% / +3%` for
  self / primary predator / secondary predator; medium / weak debuff =
  `−6% / −3%` for primary / secondary prey. No strong debuff.
- **System B**: `1.10 / 1.05 / 1.00 / 0.95 / 0.90` per hit, attacker-flagged,
  one modifier per hit.
- **Self is the strict System-A maximum** — a piece is strongest in its own
  weather.
- **Timing**: System A at combat init (snapshot); System B per hit in the
  combat engine.

## 12. Implementation Order

1. Add `CombatPieceState.affinity` (models.py) + `to_dict`/`from_dict`.
2. Rewrite `weather_effects.py`: `CYCLE_ORDER`, `ring_relation`, `RingRelation`,
   `combat_modifier` (tier-scaled), `damage_modifier`, `shop_weight`,
   `apply_weather`.
3. Wire System B into `combat.py` damage resolution; rename `apply_modifier`
   call sites to `apply_weather`.
4. Rewrite `tests/game/test_weather_effects.py`; update `test_combat.py`.
5. Update `SPEC.md` per §10.4.
6. Re-run `pytest tests/`.

Estimated effort: M.
