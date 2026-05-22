# T21 Plan - Challenge & Boss Encounters

## 1. Scope

T21 designs the two authored-difficulty encounter types layered on the generic
generator (T19): optional spirit-faction **challenges** and 2-phase **bosses**.

Primary output: `src/game/encounter.py` (challenge rolls), `src/game/content.py`
(boss set-pieces)

Test output: `tests/game/test_challenge_boss.py`

Depends: T19 (squad primitive), T20 (abilities, phase hook).

## 2. Challenge Encounters

- **6 challenge nodes**, one in every stage — one per `WeatherState`. Optional:
  the player may skip; engaging yields above-average Amber and drops.
- **Spirit faction** roster (weather elementals; `CLEAR` spirits use a generic
  / holy theme).
- **Fixed affinity per challenge**, one per weather, assigned by stage. Stage 6
  is always Thunder — the marquee fight at full board size.

| Stage | Fixed weather | Team size |
|---|---|---|
| 1 | Clear | 4 |
| 2 | Cloudy | 5 |
| 3 | Mist | 6 |
| 4 | Snow | 7 |
| 5 | Rain | 8 |
| 6 | Thunder | 10 |

### 2.1 Roster composition (40 / 40 / 20)

Each challenge roster splits into three affinity buckets:

- **40% current-weather** — affinity `==` the node's snapshotted live weather.
- **40% challenge-weather** — affinity `==` the challenge's fixed weather.
- **20% random** — any of the 6 affinities.

Integer slot split (team sizes are not multiples of 5):

```
random    = max(1, round(0.2 * N))
remaining = N - random   ->   split current / challenge,
                              challenge-weather takes the odd slot
```

| Stage | N | current-wx | challenge-wx | random |
|---|---|---|---|---|
| 1 | 4 | 1 | 2 | 1 |
| 2 | 5 | 2 | 2 | 1 |
| 3 | 6 | 2 | 3 | 1 |
| 4 | 7 | 3 | 3 | 1 |
| 5 | 8 | 3 | 3 | 2 |
| 6 | 10 | 4 | 4 | 2 |

### 2.2 Determinism

`rng = Random(derive(seed, weather_id, challenge_index))` — the roster depends
on **all three** of seed, live weather, and challenge index:

- same seed + same weather → identical roster;
- same seed + different weather → current-wx slots differ → different roster;
- same weather + different seed → different roster.

Each challenge also carries an authored `total_power` (T18 budget) that
escalates with team size to track the expected player team-size cap (T22).

### 2.3 Edge cases and rules

- **Current weather == challenge weather** (e.g. stage 6 played in live
  Thunder): the current-wx and challenge-wx buckets stack → up to 80% one
  affinity. Natural — an unlucky roll.
- **`CLEAR` is a real affinity** — `CLEAR` spirits exist (generic / holy
  theme), so no bucket needs a Clear fallback. `CLEAR` weather is inert under
  T2, so the luck layer is muted for the stage-1 challenge.
- Live node weather still applies T2 modifiers at fight time — the luck layer
  (the player is lucky when live weather debuffs the fixed-affinity spirits).
- **No other modifiers** — composition only.

## 3. Boss Encounters

- **6 bosses**, one per stage — authored set-pieces, human faction.
- Boss `affinity == node weather snapshot` → the boss is weather-buffed via T2.
  Exception: `CLEAR` is inert — `CLEAR`-weather bosses get a flat compensating
  stat bump instead.
- **2 phases**: at `50%` HP the boss enters phase 2, which grants `+1 active`
  and `+1 passive` ability (requires the T20 registry + phase hook).
- **1 map effect per boss**, themed by weather:

| Weather | Map effect |
|---|---|
| Thunder | hazard tiles — per-tick damage to occupant |
| Snow | collapsing arena — edge rows disable over time |
| Mist | fog — pieces beyond range X untargetable |
| Rain | flood lanes — a board column impassable / shifts per round |
| Cloudy | ley cells — contested buff tiles |
| Clear | spawn rifts — cells periodically spawn adds |

- Map effects require board-cell modifier support — a new combat-engine
  mechanic (note this dependency on a combat extension).
- **Final boss** (New York, stage 6): the grand boss; optionally cycles through
  weather states mid-fight — depends on mid-fight weather change, currently
  out of T3 scope.

## 4. Test Plan

- Challenge roster is deterministic on `(seed, weather, challenge_index)`;
  differs across seeds and across weathers; identical for matching inputs.
- Challenge roster is spirit faction and matches the §2.1 40/40/20 slot split.
- Boss phase transition fires once at 50% and grants abilities.
- Map effect applies and is deterministic.

## 5. Acceptance Criteria

1. 6 challenges generated per §2; 6 bosses authored per §3.
2. Challenge determinism and the §2.1 40/40/20 composition hold.
3. Boss phase 2 abilities resolve via T20.
4. `tests/game/test_challenge_boss.py` passes.

## 6. Dependencies & Open Items

- Depends: T19, T20; map effects need a combat board-modifier extension.
- Open: boss kits and map-effect exact mechanics; final-boss weather cycle
  (needs mid-fight weather).
