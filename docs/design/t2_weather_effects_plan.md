# T2 Plan - Weather Effects (`src/game/weather_effects.py`)

## 1. Scope

T2 delivers the weather → combat/shop modifier system. It is pure logic, zero I/O, zero Flet (V.1 holds).

Primary output:

- `src/game/weather_effects.py`

Secondary touches (required for T2 to be coherent):

- `src/game/models.py` — extend `WeatherState` to 6 values; rename `Champion.affinity` and `Enemy.weakness` to a single `affinity: WeatherState` field on every piece.
- `SPEC.md` — update §I (OpenWeather mapping), §V.5/V.6, §Content tables.

## 2. Weather State Enum (6 values)

Mapped 1:1 to OpenWeather "main group" derived from the condition ID range.

| OpenWeather ID range | OW main | `WeatherState` |
|---|---|---|
| 200–232 | Thunderstorm | `THUNDER` |
| 300–321 + 500–531 | Drizzle + Rain | `RAIN` |
| 600–622 | Snow | `SNOW` |
| 701–781 | Atmosphere (mist/fog/haze/dust/smoke) | `MIST` |
| 800 | Clear | `CLEAR` |
| 801–804 | Clouds | `CLOUDY` |

Drizzle merges into Rain (same combat behavior; not worth a 7th state).

`WeatherState.from_openweather_id(int) -> WeatherState` lives on the enum in `models.py` so T6 (API client) can use it without importing `weather_effects`.

## 3. Affinity Wheel — Pentagon Cycle + Neutral Clear

Each piece has exactly one `affinity: WeatherState`. The 5 active weathers form a pentagon ordered by precipitation life-cycle:

```
Cloudy → Mist → Snow → Rain → Thunder → (back to Cloudy)
```

`CLEAR` sits OUTSIDE the pentagon as a universal neutral — Clear affinity is immune to all weathers; Clear weather has no effects on any affinity.

### Relationship rule (Variant B — "both neighbours buff, diagonals debuff")

For each active weather W at position `i` in the cycle:

- **Buffs** affinity at `i` (self), `i+1` (CW neighbour), `i-1` (CCW neighbour) → 3 affinities buffed.
- **Debuffs** affinities at `i+2` and `i-2` (the 2 diagonal affinities) → 2 affinities debuffed.
- All edges are MUTUAL — adjacency on the cycle = mutual buff; diagonal across the pentagon = mutual debuff. No directional asymmetry anywhere.

Among active weathers/affinities the relationship graph is `K5` (complete), partitioned cleanly into 5 mutual buff edges + 5 mutual debuff edges.

## 4. Buff / Debuff Matrix

### 4.1 Weather perspective

| Weather | Buffs (self + 2 neighbours) | Debuffs (2 diagonals) |
|---|---|---|
| `CLOUDY` | Cloudy, Mist, Thunder | Snow, Rain |
| `MIST` | Mist, Cloudy, Snow | Rain, Thunder |
| `SNOW` | Snow, Mist, Rain | Thunder, Cloudy |
| `RAIN` | Rain, Snow, Thunder | Cloudy, Mist |
| `THUNDER` | Thunder, Rain, Cloudy | Mist, Snow |
| `CLEAR` | — | — |

### 4.2 Affinity perspective (derived, must match above)

| Affinity | Strong (3 weathers) | Weak (2 weathers) | Neutral |
|---|---|---|---|
| `CLOUDY` | Cloudy, Mist, Thunder | Snow, Rain | Clear |
| `MIST` | Mist, Cloudy, Snow | Rain, Thunder | Clear |
| `SNOW` | Snow, Mist, Rain | Thunder, Cloudy | Clear |
| `RAIN` | Rain, Snow, Thunder | Cloudy, Mist | Clear |
| `THUNDER` | Thunder, Rain, Cloudy | Mist, Snow | Clear |
| `CLEAR` | — | — | all 6 |

### 4.3 Fairness invariants (must hold in tests)

- Every active affinity has exactly 3 strong + 2 weak weathers, with Clear as the sole neutral.
- Every active weather buffs exactly 3 affinities + debuffs exactly 2 affinities.
- All buff edges are mutual: `W buffs affinity T ⇔ T's weather buffs affinity W` (for active weathers).
- All debuff edges are mutual: same.
- No affinity is both strong and weak under the same weather.
- Clear affinity is immune to all weathers; Clear weather has no effect on any affinity. Symmetric inertness.

### 4.4 Narrative

**Buff neighbours (life-cycle siblings — mutual):**

- Cloudy ↔ Mist: atmospheric family (clouds settle into haze, and back)
- Mist ↔ Snow: cold humidity (haze freezes; snow exhales fog)
- Snow ↔ Rain: precipitation phases (snow thaws to rain; rain freezes to snow)
- Rain ↔ Thunder: storm pair (rain feeds the storm)
- Thunder ↔ Cloudy: storms come from clouds and leave them behind

**Debuff diagonals (climate-stage mismatch — mutual):**

- Cloudy ↔ Snow, Cloudy ↔ Rain (cloudy = pre-precipitation, active precip outpaces it)
- Mist ↔ Rain, Mist ↔ Thunder (haze opposes active precipitation/lightning)
- Snow ↔ Thunder (frozen calm vs energy peak)

Uniform frame: "affinity is tuned to its climate stage; weathers two stages away aren't its element → debuffed."

## 5. Per-Weather Effects (Unique)

To keep scope tight: each weather has **one unique buff stat-effect** applied to all buffed pieces, and **one unique debuff stat-effect** applied to all debuffed pieces. Single multiplier path; no per-affinity branching inside a weather.

Magnitudes are flat ±10%. Under Variant B (§3) each weather buffs 3 affinities, so a single team can stack the same weather buff across multiple pieces; ±10% keeps team-wide stacking from running away. Stats from combat proposal §4.2. Clear is omitted — Clear weather is fully inert.

| Weather | Buff (3 buffed affinities) | Debuff (2 debuffed affinities) | Flavor |
|---|---|---|---|
| `CLOUDY` | `HP ×1.10`, `RES ×1.10` | `AS ×0.90` | Insulating cover; reduced visibility slows attack cadence |
| `MIST` | `MS ×1.10`, `THR ×1.10` | `attack_range -1` (min 1) | Vanish-step + ambush priority; sight collapses at range |
| `SNOW` | `Armor ×1.10`, `RES ×1.10` | `MS ×0.90` | Frosted hide; cold locks limbs and slows movement |
| `RAIN` | `AS ×1.10`, `MR ×1.10` | `STR ×0.90` | Slick momentum + mana flow; rain-soaked grip kills power |
| `THUNDER` | `STR ×1.10`, `AS ×1.10` | `INT ×0.90`, `MR ×0.90` | Charged power; static interferes with casting |
| `CLEAR` | — | — | Inert: no buff, no debuff |

Notes:

- Multipliers apply to the piece's resolved (tier+level) stats at combat init — one-shot snapshot, not per-tick (matches combat proposal §7 which already runs from snapshotted stats).
- `MIST` debuff is the only flat-integer adjustment (range stat is small-integer; a multiplier would be lossy). Clamp at 1.
- A piece is never both buffed and debuffed by the same weather (guaranteed by §4 fairness check).
- A piece can be neither buffed nor debuffed only when (a) the weather is `CLEAR`, or (b) the piece's affinity is `CLEAR`. Otherwise every active weather hits every active piece (Variant B: full K5 coverage).

## 6. Shop Drop Weight (Prep Phase)

Used by future shop roll logic. T2 exposes the function; consumer arrives with the shop task (post-T5).

```
shop_weight(affinity, weather):
    if affinity == CLEAR or weather == CLEAR: return 1.0   # Clear is inert
    if affinity == weather:                   return 2.0   # exact match — strongest pull
    if relation(affinity, weather) == STRONG: return 1.5   # neighbour (cycle-adjacent) affinity
    if relation(affinity, weather) == WEAK:   return 0.5   # diagonal — weather counters this affinity
    return 1.0                                          # only reachable when one side is Clear
```

`STRONG` here includes the self-match case; the function still distinguishes the two for the 2.0 boost on exact match. Among active (non-Clear) pairs there is no "active neutral" — every pair is either STRONG or WEAK (Variant B fills K5).

## 7. Module API (`src/game/weather_effects.py`)

```python
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from src.game.models import WeatherState

class Relation(str, Enum):
    STRONG = "strong"  # piece buffed
    WEAK = "weak"      # piece debuffed
    NEUTRAL = "neutral"

CYCLE_ORDER: tuple[WeatherState, ...]  # (CLOUDY, MIST, SNOW, RAIN, THUNDER)
BUFFED_AFFINITIES: dict[WeatherState, frozenset[WeatherState]]   # 3 per active weather, empty for CLEAR
DEBUFFED_AFFINITIES: dict[WeatherState, frozenset[WeatherState]] # 2 per active weather, empty for CLEAR

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

WEATHER_BUFFS: dict[WeatherState, CombatModifier]
WEATHER_DEBUFFS: dict[WeatherState, CombatModifier]
IDENTITY: CombatModifier

def relation(affinity: WeatherState, weather: WeatherState) -> Relation
def combat_modifier(affinity: WeatherState, weather: WeatherState) -> CombatModifier
def shop_weight(affinity: WeatherState, weather: WeatherState) -> float

# Apply helper — does NOT mutate piece; returns a stat dict the combat init reads.
def apply_modifier(piece, weather: WeatherState) -> CombatPieceState
```

`apply_modifier` is the bridge for T3 (combat). It pulls `piece.affinity`, looks up `combat_modifier(...)`, applies multipliers to the piece's resolved stats, and emits the `CombatPieceState` snapshot the simulator iterates on. Keeps weather logic fully out of T3.

## 8. Tests (`tests/game/test_weather_effects.py`)

Fairness invariants:

- `CYCLE_ORDER` contains exactly the 5 active weathers; `CLEAR` is not in it.
- For every active weather `w`: `len(BUFFED_AFFINITIES[w]) == 3` (self + 2 cycle neighbours).
- For every active weather `w`: `len(DEBUFFED_AFFINITIES[w]) == 2` (the 2 diagonal affinities).
- `BUFFED_AFFINITIES[CLEAR]` and `DEBUFFED_AFFINITIES[CLEAR]` are empty sets.
- Mutual buff edges: for active `w1`, `w2`, `w2 in BUFFED_AFFINITIES[w1] ⇔ w1 in BUFFED_AFFINITIES[w2]`.
- Mutual debuff edges: same condition on `DEBUFFED_AFFINITIES`.
- For each active affinity, exactly 3 weathers list it as buffed, exactly 2 list it as debuffed, exactly 1 (`CLEAR`) treats it as neutral.
- `CLEAR` affinity appears in zero `BUFFED_AFFINITIES`/`DEBUFFED_AFFINITIES` sets across all weathers.
- No affinity is both buffed and debuffed by the same weather.

Function behavior:

- `relation(affinity, weather)` returns expected `Relation` for representative cases (self-match, neighbour, diagonal, Clear-affinity, Clear-weather).
- `combat_modifier` returns `IDENTITY` whenever either side is `CLEAR`.
- `combat_modifier` returns `WEATHER_BUFFS[weather]` when relation is `STRONG`.
- `combat_modifier` returns `WEATHER_DEBUFFS[weather]` when relation is `WEAK`.
- `shop_weight` returns 2.0 on exact match, 1.5 on neighbour, 0.5 on diagonal, 1.0 whenever either side is `CLEAR`.
- `apply_modifier` scales stats correctly and clamps `attack_range >= 1`.

Determinism:

- Repeated calls with identical args return identical objects (or equal frozen dataclasses).

## 9. Changes Required Outside `weather_effects.py`

### 9.1 `src/game/models.py`

- `WeatherState`: drop `STORM`, `HEAT`; add `CLOUDY`, `MIST`, `SNOW`, `THUNDER`. Keep `CLEAR`, `RAIN`.
- Add `WeatherState.from_openweather_id(int) -> WeatherState` classmethod (raises on unknown id; T6 catches and falls back to `CLEAR` per V.3).
- `Champion`: rename `affinity` → `affinity`. Same type.
- `Enemy`: drop `weakness`; add `affinity: WeatherState`. Weakness now derives from `DEBUFFED_AFFINITIES`.
- Update `to_dict`/`from_dict` field names accordingly.

### 9.2 `SPEC.md`

- §I OpenWeather: rewrite mapping table to match §2.
- §V.5: "Weather state enum: exactly 6 values (Clear, Cloudy, Mist, Rain, Snow, Thunder), mapped 1:1 to OpenWeather id main groups."
- §V.6: "Each piece (Champion, Enemy) has exactly one `affinity` field with a `WeatherState` value."
- §Content "Weather States" table: replace with the 6-state version from §5 (buff/debuff summary).
- §Content "Champions" table: rename `Affinity` column → `Affinity`; remap Storm→Thunder, Heat→Clear (Blaze Fox & Ember Salamander still sun-themed), Cold→Snow. Add a couple Mist/Cloudy affinities for coverage.
- §T.2 row: bump Est S → M (matrix + per-weather effects + tests, not just a lookup dict).

### 9.3 Existing tests under `tests/game/`

- Any test referencing `STORM`/`HEAT` or `affinity`/`weakness` needs renaming. Likely small touchup; T1 tests use these names directly.

## 10. Locked Decisions

- **Matrix structure**: Variant B (both-neighbours buff + diagonal debuffs), pentagon cycle `Cloudy → Mist → Snow → Rain → Thunder`. Clear is universal neutral.
- **Magnitudes**: flat ±10% across all effects. Chosen because each weather buffs 3 affinities (Variant B), so team-wide stacking would amplify a larger multiplier into runaway team boosts. ±10% × 3 stacked pieces ≈ 30% team boost ceiling — strong but not oppressive.
- **`MIST` debuff** stays flat `-1 attack_range` (min 1). Only flat-integer effect; flavor justifies the asymmetry.
- **Modifier application timing**: at combat init only. One-shot snapshot. Mid-fight weather changes are not in scope.

## 10b. Open Questions (Confirm Before Implementing)

1. **Naming** — rename `Champion.affinity` and `Enemy.weakness` to `affinity` on both? Or keep `affinity` on Champion (existing) and add `affinity` to Enemy too? `affinity` is more neutral; `affinity` carries the existing meaning. Answer: rename to affinity -> affinity and weakness is implied from it due to global type relation
2. **Champion content remap** — when SPEC §Content gets rewritten, redistribute affinity counts so every active affinity + Clear has ≥1 champion in the roster of 8, or keep current 2:2:2:1:1 shape and let some affinities be enemy-only? Current roster has no Mist/Cloudy pieces. Answer: we should have at least one champion per affinity per tier which is 6 * 10 = 60 Champs

## 11. Implementation Order

1. Confirm §10 open questions.
2. Update `WeatherState` enum + add `from_openweather_id` (models.py).
3. Rename `affinity`/`weakness` → `affinity` on Champion + Enemy. Fix existing T1 tests.
4. Write `weather_effects.py` (matrices, modifiers, functions).
5. Write `tests/game/test_weather_effects.py`.
6. Update SPEC.md per §9.2.
7. Re-run `pytest tests/`.

Estimated effort: 1–2 hours total (size M per §9.2).
