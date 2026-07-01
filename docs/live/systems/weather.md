# Weather — Favor & Affinity Clash

> **Status: LIVING** — must match `src/game/weather_effects.py` + `loadout._apply_weather_to_piece`. Audited by `/check`.
> **Scope:** the two decoupled weather systems and the single place each is applied. **Reconciled:** 2026-07-01 @ refactor/combat-engine-single-source.

Six weather states (V.5): `CLEAR, CLOUDY, MIST, RAIN, SNOW, THUNDER`. Each piece
carries exactly one `affinity: WeatherState` (V.6). `CLEAR` sits outside the
predator/prey ring and is inert in both systems. The two systems are **never
summed**:

### The predator/prey ring (`ring_relation`)

The five active weathers form a directed cycle
`CYCLE_ORDER = (MIST, CLOUDY, RAIN, SNOW, THUNDER)`. For member `i`: `i-1` is its
**primary prey**, `i-2` its **secondary prey**; `i+1`/`i+2` are its primary/
secondary **predators** (mod 5). `ring_relation(a, b)` returns `a`'s relation to
`b` — `SELF` / `PRIMARY_PREDATOR` / `SECONDARY_PREDATOR` / `SECONDARY_PREY` /
`PRIMARY_PREY`, or `NEUTRAL` whenever either side is `CLEAR`. Both systems key
off this one function.

The full ring (each member's prey/predators, `CYCLE_ORDER` order):

| weather | primary prey | secondary prey | secondary predator | primary predator |
|---|---|---|---|---|
| `Mist` | Thunder | Snow | Rain | Cloudy |
| `Cloudy` | Mist | Thunder | Snow | Rain |
| `Rain` | Cloudy | Mist | Thunder | Snow |
| `Snow` | Rain | Cloudy | Mist | Thunder |
| `Thunder` | Snow | Rain | Cloudy | Mist |

(`Clear` is off-ring — `NEUTRAL` to everything.)

## 1. Weather Favor — `combat_modifier`

"Does the node weather suit my affinity?" A 5-tier stat buff/debuff
(`combat_modifier(affinity, weather) -> CombatModifier`) driven by the
directional predator/prey ring. Applied **once at combat init**, in exactly one
place: `loadout._apply_weather_to_piece`. As of **T.29-pre (V.42)** it no longer
folds into `base_stats` — it emits `source="weather:<state>"` **`Modifier`s**
(`*_mult≠1.0 → ("<stat>","mul",mult)`, `attack_range_delta → ("attack_range","add",delta)`)
applied via `apply_bundle`, so weather composes through `compute_stat`
`(base+Σadds)×Πmuls` like every other source — uniformly attributable
(`stat_breakdown`, V.45) and it scales item/augment adds. Values are now
**unrounded floats** (not `round(value×mult)`); `attack_range` underflow is held
≥ 1 by the `_STAT_FLOORS` clamp in `compute_stat` (V.43); HP is reconciled
(`max_hp = hp = stat("hp")`) afterwards since resources are never `Modifier`'d
directly. There is no other application path — the old
`weather_effects.apply_weather` snapshot and the `CombatPieceState` model it
built were removed (one source of truth).

**Magnitude.** `WEATHER_FAVOR_MAGNITUDE = 0.3` sets the strong-tier primary
deviation (±30%); `combat_modifier` scales that deviation from `1.0` by a
per-relation `TIER_SCALAR` — **SELF 1.0, PRIMARY 0.6, SECONDARY 0.3**. Buffs
reach all three tiers; debuffs reach medium **and** weak (`_DEBUFF_RELATIONS` =
primary/secondary prey → `TIER_SCALAR` 0.6 and 0.3), so there is **no strong
debuff** (SELF tier never debuffs). The strong-tier packs
(`WEATHER_BUFF_BASE` / `WEATHER_DEBUFF_BASE`, `CombatModifier` fields):

| weather | buff (self tier) | debuff (prey) |
|---|---|---|
| `CLOUDY` | +30% HP, +30% RES, +15% AS | −AS |
| `MIST` | +30% MS, +30% threat, +15% INT | −1 attack_range |
| `SNOW` | +30% armor, +30% RES, small STR | −MS |
| `RAIN` | +30% AS, +30% mana_regen | −STR |
| `THUNDER` | +30% STR, +30% AS | −INT, −mana_regen |
| `CLEAR` | — (inert) | — |

`attack_range_delta` is an `add` (rounded): `-1` survives the medium tier
(`round(-0.6) = -1`) and vanishes at the weak tier (`round(-0.3) = 0`).

**Favor matrix** — a piece's affinity (row) against the node weather (column).
`combat_modifier` reads `ring_relation(affinity, weather)`: `buff +++` = `SELF`
(scalar 1.0), `buff ++` = `PRIMARY_PREDATOR` (0.6), `buff +` = `SECONDARY_PREDATOR`
(0.3); `deb −−` = `PRIMARY_PREY` (0.6), `deb −` = `SECONDARY_PREY` (0.3); `·` =
`NEUTRAL`/inert (`_BUFF_RELATIONS` = SELF + both predators; debuffs = both prey):

| affinity \ weather | Clear | Mist | Cloudy | Rain | Snow | Thunder |
|---|---|---|---|---|---|---|
| `Clear` | · | · | · | · | · | · |
| `Mist` | · | buff +++ | deb −− | deb − | buff + | buff ++ |
| `Cloudy` | · | buff ++ | buff +++ | deb −− | deb − | buff + |
| `Rain` | · | buff + | buff ++ | buff +++ | deb −− | deb − |
| `Snow` | · | deb − | buff + | buff ++ | buff +++ | deb −− |
| `Thunder` | · | deb −− | deb − | buff + | buff ++ | buff +++ |

## 2. Affinity Clash — `damage_modifier`

"Do I beat this enemy?" A per-hit multiplier `damage_modifier(attacker_affinity,
defender_affinity)` applied on **every damage instance** inside the damage
pipeline (see [combat.md](combat.md#damage-pipeline)). It depends on the
defender, so it can't be pre-snapshotted — it's resolved per hit, not at init.
The multiplier by ring relation of attacker→defender (`DAMAGE_MULT`):

| relation | mult |
|---|---|
| `PRIMARY_PREDATOR` | 1.30 |
| `SECONDARY_PREDATOR` | 1.12 |
| `SELF` / `NEUTRAL` | 1.00 |
| `SECONDARY_PREY` | 0.88 |
| `PRIMARY_PREY` | 0.70 |

**Clash matrix** — attacker affinity (row) vs defender affinity (column), the
per-hit `damage_modifier` multiplier (`DAMAGE_MULT[ring_relation(atk, def)]`):

| atk \ def | Clear | Mist | Cloudy | Rain | Snow | Thunder |
|---|---|---|---|---|---|---|
| `Clear` | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| `Mist` | 1.00 | 1.00 | 0.70 | 0.88 | 1.12 | 1.30 |
| `Cloudy` | 1.00 | 1.30 | 1.00 | 0.70 | 0.88 | 1.12 |
| `Rain` | 1.00 | 1.12 | 1.30 | 1.00 | 0.70 | 0.88 |
| `Snow` | 1.00 | 0.88 | 1.12 | 1.30 | 1.00 | 0.70 |
| `Thunder` | 1.00 | 0.70 | 0.88 | 1.12 | 1.30 | 1.00 |

## Why decoupled

Favor asks about the *node*; Clash asks about the *opponent*. Keeping them
separate means weather tuning and matchup tuning don't entangle. Both read the
same predator/prey ring (`ring_relation`) but apply at different times to
different magnitudes (`combat_modifier` stat packs vs `damage_modifier`
multiplier).

## Also here

`shop_weight(affinity, weather)` — prep-shop pull weight by ring relation
(content economy, not combat). `SHOP_WEIGHT`: SELF 2.0, primary/secondary
predator 1.5 / 1.2, NEUTRAL 1.0, secondary/primary prey 0.8 / 0.6 — pieces that
hunt the upcoming node weather surface more often.

## File map

| Concern | Symbol |
|---|---|
| Ring relation (predator/prey) | `weather_effects.ring_relation` |
| Weather Favor stat pack | `weather_effects.combat_modifier` → `CombatModifier` |
| Weather Favor application (only path) | `loadout._apply_weather_to_piece` |
| Affinity Clash per-hit multiplier | `weather_effects.damage_modifier` |
| Shop pull weight | `weather_effects.shop_weight` |
