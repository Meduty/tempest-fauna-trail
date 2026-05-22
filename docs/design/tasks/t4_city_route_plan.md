# T4 Plan - City Route (`src/game/route.py`)

## 1. Scope

T4 delivers the fixed, staged world route the player travels: an around-the-world
tour of six continents, each a stage of ordered encounter nodes ending in a boss,
the route-final node a grand boss in New York.

Primary output:

- `src/game/route.py`

Test output:

- `tests/game/test_route.py`

Prerequisite model change (see §5):

- `src/game/models.py` — extend `NodeType` with `SUPPLY` and `CHALLENGE`.

Out of scope for T4:

- Actual enemy stat content — T4 names enemy **pools** and assigns them to
  nodes; T5 fills the pools with `Enemy` instances.
- Reward / augment / supply payload content — T4 assigns **placeholder** table
  ids; real loot/augment/shop tables are later content work.
- Route map rendering — T4 stores geographic coordinates; T11 projects them.
- Branching / merging route topology — MVP route is a single linear chain.
- Procedural encounter generation — T19. T4 only assigns pool / table ids.
- Live weather — T4 seeds a placeholder `default_weather` per city; T6 refreshes
  it per node from OpenWeather.

## 1.1 Key concept — stage affinity vs. node weather

Two distinct weather-flavoured properties exist on the route. **Do not conflate
them** (the original T4 draft did — it gave one hub city per stage and let the
whole stage share one weather; this revision fixes that):

| Property | Granularity | Source | Used by |
|---|---|---|---|
| **Stage affinity** | Per **stage** (6 total) | **Authored**, fixed for the whole game | Boss + challenge encounters (`boss_roster.md`, `t21_challenge_boss_plan.md`) |
| **Node weather** | Per **node / city** (~50) | **Live** OpenWeather data per city (T6); `default_weather` placeholder until then | Weather Systems A/B at fight time (`weather_effects.py`) |

A stage has **one authored affinity**. Every node in that stage is a **different
real city** with its **own live weather**, which may differ from the stage
affinity and from every sibling node. The boss/challenge of a stage use the
stage affinity; ordinary fights use the node's live weather. The six stage
affinities — one per `WeatherState` — are locked in `boss_roster.md` §1.1.

## 2. Inputs and Outputs

T4 has no runtime inputs — the route is static content. It exposes a builder
plus the data catalogs behind it.

### 2.1 Public surface

```python
def build_route() -> list[Node]
def get_city(city_id: str) -> CityDef
def stage_of(node_index: int) -> StageDef

CITIES: dict[str, CityDef]          # city catalog, keyed by city id (~50 entries)
STAGES: tuple[StageDef, ...]        # ordered continent stages
ROUTE_NODE_COUNT: int               # 50 — derived, asserted in tests
```

`stage_of(node_index).affinity` is how T19/T21 read a stage's authored affinity.

### 2.2 Output contract

`build_route()` returns a fresh `list[Node]` (length `ROUTE_NODE_COUNT`):

- Nodes are ordered, `index` runs `1..50` with no gaps.
- Every node is materialized in `NodeState.UPCOMING`. Marking the first node
  `CURRENT` is a run-initialization concern (T14/T15), not route definition.
- Each call returns an independent, equal list (deterministic, no shared
  mutable state — callers may mutate node `state` freely).
- The returned list is valid input to `Run` construction.

## 3. Route Structure (MVP Lock)

### 3.1 Stages — around the world

Six stages, one per continent, played in fixed order. Each stage has a continent
name, an authored **affinity**, a **difficulty** ordinal, and a list of cities —
**one city per node**.

| Stage | Continent | Affinity | Difficulty | Nodes |
|---|---|---|---|---|
| 1 | Europe | `CLEAR` | 1 | 10 |
| 2 | Africa | `MIST` | 2 | 8 |
| 3 | Asia | `THUNDER` | 3 | 8 |
| 4 | Oceania | `CLOUDY` | 4 | 8 |
| 5 | South America | `RAIN` | 5 | 8 |
| 6 | North America | `SNOW` | 6 | 8 |

Stage affinities are the locked per-stage table from `boss_roster.md` §1.1 —
every `WeatherState` used exactly once, stage 1 `CLEAR` so the on-ramp plays with
the weather systems muted. `difficulty` is an ordinal handed to T5/T18 for enemy
scaling.

### 3.2 Node sequences

Each stage is a linear, ordered sequence of typed encounter nodes.

- **Stage 1 (Europe)** — 10 nodes, a gentle on-ramp:
  `Reward, Reward, Augment, Combat, Combat, Supply, Combat, Challenge, Reward, Boss`
- **Stages 2-6** — 8 nodes each:
  `Combat, Augment, Combat, Supply, Combat, Challenge, Reward, Boss`

Total: `10 + 5 × 8 = 50` nodes. There are 6 Challenge nodes (one per stage) and
6 Boss nodes (the last node of each stage). Encounter words map to `NodeType`:

| Sequence word | `NodeType` | Encounter id field set |
|---|---|---|
| Combat | `FIGHT` | `enemy_pool_id` |
| Challenge | `CHALLENGE` | `enemy_pool_id` (elite pool) |
| Boss | `BOSS_FIGHT` | `enemy_pool_id` (boss pool) |
| Reward | `REWARD` | `enemy_pool_id` (easy squad) + `reward_table_id` |
| Augment | `AUGMENT` | `augment_pool_id` |
| Supply | `SUPPLY` | none (placeholder — see §4.4) |

### 3.3 Boss nodes

Every stage ends in a `BOSS_FIGHT` node. The six boss cities are the marquee
city of each stage: **Vienna, Cairo, Tokyo, Sydney, Rio de Janeiro, New York**.
The stage-1 boss fight is in **Vienna**; the route-final node — Stage 6 / New
York — is the grand boss, satisfying `SPEC V.7`. Boss kits are in
`boss_roster.md`.

## 4. Data Definitions

### 4.1 `CityDef`

```python
@dataclass(frozen=True)
class CityDef:
    id: str
    name: str
    country: str
    continent: str
    latitude: float          # real-world geographic coordinate
    longitude: float
    default_weather: WeatherState   # placeholder until T6 live fetch
```

`frozen=True` — cities are immutable content. `default_weather` is a
climate-flavoured placeholder only; T6 overwrites each node's weather with live
OpenWeather data per city, and `V.3` falls back to it (or `CLEAR`) on API
failure. The route now carries **one city per node** — ~50 cities total.

**City catalog (`CITIES`)** — grouped by stage. City ids follow
`city_<name_snake_case>` (e.g. `city_vienna`, `city_new_york`,
`city_addis_ababa`). Coordinates are real lat/lon, approximate to ~2 decimal
places — verify against a gazetteer before T11 projection work.

#### Stage 1 — Europe (10)

| # | City id | Name | Country | Lat | Lon | `default_weather` |
|---|---|---|---|---|---|---|
| 1 | `city_lisbon` | Lisbon | Portugal | 38.72 | -9.14 | `CLEAR` |
| 2 | `city_madrid` | Madrid | Spain | 40.42 | -3.70 | `CLEAR` |
| 3 | `city_paris` | Paris | France | 48.86 | 2.35 | `CLOUDY` |
| 4 | `city_london` | London | United Kingdom | 51.51 | -0.13 | `CLOUDY` |
| 5 | `city_brussels` | Brussels | Belgium | 50.85 | 4.35 | `RAIN` |
| 6 | `city_amsterdam` | Amsterdam | Netherlands | 52.37 | 4.90 | `RAIN` |
| 7 | `city_berlin` | Berlin | Germany | 52.52 | 13.40 | `CLOUDY` |
| 8 | `city_prague` | Prague | Czechia | 50.08 | 14.44 | `CLOUDY` |
| 9 | `city_rome` | Rome | Italy | 41.90 | 12.50 | `CLEAR` |
| 10 | `city_vienna` | Vienna | Austria | 48.21 | 16.37 | `CLOUDY` |

#### Stage 2 — Africa (8)

| # | City id | Name | Country | Lat | Lon | `default_weather` |
|---|---|---|---|---|---|---|
| 1 | `city_casablanca` | Casablanca | Morocco | 33.57 | -7.59 | `CLEAR` |
| 2 | `city_marrakesh` | Marrakesh | Morocco | 31.63 | -7.99 | `CLEAR` |
| 3 | `city_dakar` | Dakar | Senegal | 14.72 | -17.47 | `CLEAR` |
| 4 | `city_lagos` | Lagos | Nigeria | 6.52 | 3.38 | `RAIN` |
| 5 | `city_accra` | Accra | Ghana | 5.56 | -0.20 | `RAIN` |
| 6 | `city_addis_ababa` | Addis Ababa | Ethiopia | 9.03 | 38.74 | `RAIN` |
| 7 | `city_nairobi` | Nairobi | Kenya | -1.29 | 36.82 | `CLOUDY` |
| 8 | `city_cairo` | Cairo | Egypt | 30.04 | 31.24 | `CLEAR` |

#### Stage 3 — Asia (8)

| # | City id | Name | Country | Lat | Lon | `default_weather` |
|---|---|---|---|---|---|---|
| 1 | `city_mumbai` | Mumbai | India | 19.08 | 72.88 | `RAIN` |
| 2 | `city_delhi` | Delhi | India | 28.61 | 77.21 | `MIST` |
| 3 | `city_bangkok` | Bangkok | Thailand | 13.76 | 100.50 | `THUNDER` |
| 4 | `city_singapore` | Singapore | Singapore | 1.35 | 103.82 | `THUNDER` |
| 5 | `city_jakarta` | Jakarta | Indonesia | -6.21 | 106.85 | `RAIN` |
| 6 | `city_hong_kong` | Hong Kong | China | 22.32 | 114.17 | `THUNDER` |
| 7 | `city_seoul` | Seoul | South Korea | 37.57 | 126.98 | `SNOW` |
| 8 | `city_tokyo` | Tokyo | Japan | 35.68 | 139.65 | `THUNDER` |

#### Stage 4 — Oceania (8)

| # | City id | Name | Country | Lat | Lon | `default_weather` |
|---|---|---|---|---|---|---|
| 1 | `city_perth` | Perth | Australia | -31.95 | 115.86 | `CLEAR` |
| 2 | `city_adelaide` | Adelaide | Australia | -34.93 | 138.60 | `CLEAR` |
| 3 | `city_melbourne` | Melbourne | Australia | -37.81 | 144.96 | `CLOUDY` |
| 4 | `city_brisbane` | Brisbane | Australia | -27.47 | 153.03 | `RAIN` |
| 5 | `city_port_moresby` | Port Moresby | Papua New Guinea | -9.44 | 147.18 | `RAIN` |
| 6 | `city_auckland` | Auckland | New Zealand | -36.85 | 174.76 | `RAIN` |
| 7 | `city_wellington` | Wellington | New Zealand | -41.29 | 174.78 | `CLOUDY` |
| 8 | `city_sydney` | Sydney | Australia | -33.87 | 151.21 | `CLOUDY` |

#### Stage 5 — South America (8)

| # | City id | Name | Country | Lat | Lon | `default_weather` |
|---|---|---|---|---|---|---|
| 1 | `city_bogota` | Bogotá | Colombia | 4.71 | -74.07 | `RAIN` |
| 2 | `city_quito` | Quito | Ecuador | -0.18 | -78.47 | `RAIN` |
| 3 | `city_lima` | Lima | Peru | -12.05 | -77.04 | `MIST` |
| 4 | `city_santiago` | Santiago | Chile | -33.45 | -70.67 | `CLEAR` |
| 5 | `city_buenos_aires` | Buenos Aires | Argentina | -34.60 | -58.38 | `CLOUDY` |
| 6 | `city_montevideo` | Montevideo | Uruguay | -34.90 | -56.16 | `RAIN` |
| 7 | `city_sao_paulo` | São Paulo | Brazil | -23.55 | -46.63 | `RAIN` |
| 8 | `city_rio_de_janeiro` | Rio de Janeiro | Brazil | -22.91 | -43.17 | `RAIN` |

#### Stage 6 — North America (8)

| # | City id | Name | Country | Lat | Lon | `default_weather` |
|---|---|---|---|---|---|---|
| 1 | `city_mexico_city` | Mexico City | Mexico | 19.43 | -99.13 | `CLOUDY` |
| 2 | `city_houston` | Houston | United States | 29.76 | -95.37 | `THUNDER` |
| 3 | `city_miami` | Miami | United States | 25.76 | -80.19 | `THUNDER` |
| 4 | `city_los_angeles` | Los Angeles | United States | 34.05 | -118.24 | `CLEAR` |
| 5 | `city_chicago` | Chicago | United States | 41.88 | -87.63 | `SNOW` |
| 6 | `city_toronto` | Toronto | Canada | 43.65 | -79.38 | `SNOW` |
| 7 | `city_boston` | Boston | United States | 42.36 | -71.06 | `SNOW` |
| 8 | `city_new_york` | New York | United States | 40.71 | -74.01 | `SNOW` |

50 cities total. `default_weather` is a climate-flavoured placeholder; the boss
city of a stage need not match the stage affinity (e.g. Vienna's placeholder is
`CLOUDY`, but Stage 1's authored affinity is `CLEAR`) — the two properties are
independent by design (§1.1).

### 4.2 `StageDef`

```python
@dataclass(frozen=True)
class StageDef:
    index: int                       # 1..6
    name: str                        # continent name
    affinity: WeatherState           # authored stage affinity (bosses/challenges)
    node_cities: tuple[str, ...]     # one city id per node, in node order
    node_types: tuple[NodeType, ...] # encounter sequence, parallel to node_cities
    difficulty: int                  # 1..6, monotonically increasing
```

Invariant: `len(node_cities) == len(node_types)` for every stage. The two tuples
are walked in lockstep by `build_route()` — node `i` of the stage is
`node_types[i]` at city `node_cities[i]`.

### 4.3 Enemy pool id scheme

T4 assigns pool ids; T5 defines their contents.

- Pattern: `pool_{continent}_{class}` where `class ∈ {standard, elite, boss}`.
- `FIGHT` and `REWARD` → `pool_{continent}_standard` (`REWARD` applies a reduced
  encounter budget — see T19)
- `CHALLENGE` → `pool_{continent}_elite`
- `BOSS_FIGHT` → `pool_{continent}_boss`

Pools stay **continent-keyed, not city-keyed** — one city per node does not
multiply the pool count. Six continents × three classes = 18 pool ids.

### 4.4 Reward / augment / supply placeholders

- `REWARD` nodes → easy-fight `enemy_pool_id` (§4.3) **plus**
  `reward_table_id = "reward_basic"`.
- `AUGMENT` nodes → `augment_pool_id = "augment_basic"`.
- `SUPPLY` nodes → no id field set; MVP supply content is resolved globally by
  `node_type == SUPPLY`.

## 5. Model Prerequisites (`NodeType` extension)

```python
class NodeType(str, Enum):
    FIGHT = "fight"
    REWARD = "reward"
    AUGMENT = "augment"
    SUPPLY = "supply"        # shop / resupply stop
    CHALLENGE = "challenge"  # elite optional-difficulty fight
    BOSS_FIGHT = "boss_fight"
```

Additive only — `Node.to_dict()` / `from_dict()` need no code change. No new
`Node` field is required: `Node` already carries `city` and `weather`, which is
all one-city-per-node needs. Stage affinity lives on `StageDef`, not on `Node` —
consumers reach it via `stage_of(node_index).affinity`.

## 6. Implementation Steps

### Step 1 — module and catalogs

Create `src/game/route.py`. Import `Node`, `NodeType`, `NodeState`,
`WeatherState` from `models`. No Flet imports (V.1). Define `CityDef`,
`StageDef`, the `CITIES` dict (50 entries, §4.1), and the `STAGES` tuple.

### Step 2 — node id and index scheme

- `index`: global running counter `1..50`.
- `Node.id`: `f"node_{index:02d}"` (`node_01` … `node_50`).

### Step 3 — `build_route()`

Walk `STAGES` in order; for each stage zip `node_cities` with `node_types` and
materialize one `Node` per pair:

- `city` = `CITIES[city_id].name`; `weather` = `CITIES[city_id].default_weather`.
- `node_type` from the sequence; `state = NodeState.UPCOMING`.
- Encounter id fields per §4.3 / §4.4.

Construct fresh `Node` objects on every call.

### Step 4 — lookup helpers

- `get_city(city_id)` — `CITIES` lookup; `KeyError` with a clear message on miss.
- `stage_of(node_index)` — map a 1-based node index back to its `StageDef`.

### Step 5 — self-consistency assertions

At module import, assert `len(build_route()) == ROUTE_NODE_COUNT`, that every
city id in every `node_cities` exists in `CITIES`, that
`len(node_cities) == len(node_types)` per stage, and that every city id is used
exactly once across the whole route.

## 7. Test Plan (`tests/game/test_route.py`)

### 7.1 Shape

- `build_route()` returns exactly 50 nodes; indexes `1..50`, contiguous, unique.
- Node ids unique, matching `node_{index:02d}`.

### 7.2 Stage structure

- Node-type sequence of stage 1 equals the 10-entry Europe sequence; stages 2-6
  each equal the 8-entry sequence.
- Every stage's final node is `BOSS_FIGHT`; exactly 6 `CHALLENGE` nodes exist.
- Node 1 (Lisbon) and node 50 (New York `BOSS_FIGHT`) are correct; the stage-1
  boss node is Vienna.
- Each `StageDef.affinity` matches the §3.1 table (one per `WeatherState`).

### 7.3 City data

- `CITIES` has 50 entries; every city has non-empty name/country/continent and
  finite lat/lon in valid ranges (`-90..90`, `-180..180`).
- Every node's `city` resolves to a `CityDef`.
- Every city id appears on exactly one node — one city per node, no repeats.

### 7.4 Encounter ids

- `FIGHT` / `REWARD` / `CHALLENGE` / `BOSS_FIGHT` nodes carry a non-`None`
  `enemy_pool_id` matching `pool_{continent}_{class}`.
- `REWARD` → `reward_basic` + standard pool; `AUGMENT` → `augment_basic`;
  `SUPPLY` → no encounter id fields.

### 7.5 Determinism and isolation

- Two `build_route()` calls yield node lists with equal `to_dict()` output.
- Mutating a returned node's `state` does not affect a subsequent call.

### 7.6 `Run` integration

- A `build_route()` result is accepted by `Run` construction; setting node 1
  `CURRENT` + `status=IN_PROGRESS` passes validation.

## 8. Acceptance Criteria

1. `NodeType` carries `SUPPLY` and `CHALLENGE`.
2. `src/game/route.py` exists, zero Flet imports (V.1), exposes `build_route`,
   `get_city`, `stage_of`, `CITIES`, `STAGES`, `ROUTE_NODE_COUNT`.
3. `build_route()` yields 50 valid `UPCOMING` nodes across 6 continent stages
   with the §3.2 sequences, **one distinct city per node**.
4. `StageDef` carries the authored `affinity` (§3.1); cities carry real lat/lon;
   the route ends in a New York `BOSS_FIGHT` (V.7) and the stage-1 boss is
   Vienna.
5. Combat/challenge/boss nodes carry enemy pool ids; reward/augment carry
   placeholder table ids.
6. `tests/game/test_route.py` passes; existing tests still pass.

## 9. Risks and Mitigations

- Risk: 50 distinct cities is more content than a 6-city budget anticipated.
  - Mitigation: the cost is a one-time data table; pools stay continent-keyed
    (18 ids), enemy archetypes are reused and stage-scaled, and city coordinates
    are the only per-city data the engine needs.
- Risk: 50 hand-entered coordinates drift from reality.
  - Mitigation: coordinates are flagged approximate (§4.1); a verification pass
    against a gazetteer is a T11 prerequisite, not a T4 blocker.
- Risk: `default_weather` placeholders mislead players before T6.
  - Mitigation: placeholders are explicitly transient; T6 overwrites per node.

## 10. SPEC Reconciliation / Open Items

- **Content budget.** `SPEC` / `CLAUDE.md` previously budgeted "~6 cities" —
  superseded: the route now uses ~50 cities, one per node. `SPEC` T.4 line and
  the "Cities examples" table are updated; a `SPEC B` backprop entry records the
  rework.
- **Stage affinity** is the locked `boss_roster.md` §1.1 table — T4 is the code
  home of that data via `StageDef.affinity`.
- **D.1**: linear 6-stage / 50-node chain stays locked; branching deferred.
- **`Node.shop_pool_id`**: still a future field for per-node supply content;
  out of T4 scope.

## 11. Follow-up Tasks (Post-T4)

- T5 fills the 18 enemy pools and the reward/augment/supply placeholder tables.
- T6 wires per-node live weather (50 OpenWeather lookups — mind the 60-call/min
  free-tier limit; cache and batch).
- Revisit branching topology (D.1) for optional-path challenge nodes.
