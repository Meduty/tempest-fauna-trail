# T4 Plan - City Route (`src/game/route.py`)

## 1. Scope

T4 delivers the fixed, staged world route the player travels: an around-the-world
tour of six continents, each a stage of ordered encounter nodes ending in a boss,
with the final node a grand boss in a famous North American city.

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
- Branching / merging route topology — MVP route is a single linear chain
  (D.1 branch/merge rules stay deferred).
- Procedural encounter generation (enemy squad rolls, augment/supply offers) —
  T19. T4 only assigns pool / table ids to nodes.
- Live weather — T4 seeds a placeholder `default_weather` per city; T6 refreshes
  it from OpenWeather.

## 2. Inputs and Outputs

T4 has no runtime inputs — the route is static content. It exposes a builder
plus the data catalogs behind it.

### 2.1 Public surface

```python
def build_route() -> list[Node]
def get_city(city_id: str) -> CityDef
def stage_of(node_index: int) -> StageDef

CITIES: dict[str, CityDef]          # city catalog, keyed by city id
STAGES: tuple[StageDef, ...]        # ordered continent stages
ROUTE_NODE_COUNT: int               # 50 — derived, asserted in tests
```

### 2.2 Output contract

`build_route()` returns a fresh `list[Node]` (length `ROUTE_NODE_COUNT`):

- Nodes are ordered, `index` runs `1..50` with no gaps.
- Every node is materialized in `NodeState.UPCOMING`. Marking the first node
  `CURRENT` is a run-initialization concern (T14/T15), not route definition —
  this keeps `route.py` pure static data.
- Each call returns an independent, equal list (deterministic, no shared
  mutable state — callers may mutate node `state` freely).
- The returned list is valid input to `Run` construction: unique indexes,
  non-empty, final node is the route boss.

## 3. Route Structure (MVP Lock)

These choices lock open item D.1 (route topology) for the MVP.

### 3.1 Stages — around the world

Six stages, one per continent, played in fixed order:

| Stage | Continent | Hub City | Country | Enemy theme |
|---|---|---|---|---|
| 1 | Europe | London | United Kingdom | Smog bots |
| 2 | Africa | Cairo | Egypt | Heat mechs |
| 3 | Asia | Tokyo | Japan | Storm sentinels |
| 4 | Oceania | Sydney | Australia | Wildfire units |
| 5 | South America | Rio de Janeiro | Brazil | Monsoon walkers |
| 6 | North America | New York | United States | Grand boss (live NYC weather) |

One hub city per stage keeps the city catalog at six, inside the SPEC content
budget (~6 cities). All nodes within a stage are located at that stage's hub
city and therefore share its (live) weather.

### 3.2 Node sequences

Each stage is a linear, ordered sequence of typed encounter nodes.

- **Stage 1 (Europe)** — 10 nodes, a gentle on-ramp:
  `Reward, Reward, Augment, Combat, Combat, Supply, Combat, Challenge, Reward, Boss`
- **Stages 2-6** — 8 nodes each:
  `Combat, Augment, Combat, Supply, Combat, Challenge, Reward, Boss`

Total: `10 + 5 × 8 = 50` nodes. There are 6 Challenge nodes (one per stage); the
stage-1 challenge is the `CLEAR`-affinity challenge. Encounter words map to
`NodeType` as:

| Sequence word | `NodeType` | Encounter id field set |
|---|---|---|
| Combat | `FIGHT` | `enemy_pool_id` |
| Challenge | `CHALLENGE` *(new)* | `enemy_pool_id` (elite pool) |
| Boss | `BOSS_FIGHT` | `enemy_pool_id` (boss pool) |
| Reward | `REWARD` | `enemy_pool_id` (easy squad) + `reward_table_id` |
| Augment | `AUGMENT` | `augment_pool_id` |
| Supply | `SUPPLY` *(new)* | none (placeholder — see §4.4) |

`REWARD` is an easy fight with guaranteed loot, not a pure non-combat node — it
draws a reduced-budget squad (T19) and rolls a drop table.

### 3.3 Boss nodes

Every stage ends in a `BOSS_FIGHT` node (a stage boss). The route-final node —
Stage 6 / New York — is the grand boss in a famous city, satisfying V.7. Stage
bosses 1-5 use the same node type but draw from per-stage boss pools.

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

`frozen=True` — cities are immutable content. Coordinates are real geographic
lat/lon; T11 owns the projection to canvas pixels, so `route.py` stays
rendering-agnostic.

City catalog (`CITIES`):

| id | name | lat | lon | default_weather |
|---|---|---|---|---|
| `city_london` | London | 51.5074 | -0.1278 | `CLOUDY` |
| `city_cairo` | Cairo | 30.0444 | 31.2357 | `CLEAR` |
| `city_tokyo` | Tokyo | 35.6762 | 139.6503 | `THUNDER` |
| `city_sydney` | Sydney | -33.8688 | 151.2093 | `CLEAR` |
| `city_rio` | Rio de Janeiro | -22.9068 | -43.1729 | `RAIN` |
| `city_new_york` | New York | 40.7128 | -74.0060 | `CLOUDY` |

`default_weather` is a climate-flavored placeholder only. It guarantees
`Node.weather` is populated before any API call; T6 overwrites it with live
OpenWeather data, and V.3 falls back to it (or `CLEAR`) on API failure.

### 4.2 `StageDef`

```python
@dataclass(frozen=True)
class StageDef:
    index: int                       # 1..6
    name: str                        # continent name
    city_id: str                     # hub city, key into CITIES
    node_types: tuple[NodeType, ...] # ordered encounter sequence
    difficulty: int                  # 1..6, monotonically increasing
```

`difficulty` is an ordinal handed to T5 so it can scale enemy tiers along the
route (stage 1 easiest, stage 6 hardest). T4 does not fix enemy stats or tiers.

### 4.3 Enemy pool id scheme

T4 assigns pool ids; T5 defines what is in each pool.

- Pattern: `pool_{continent}_{class}` where `class ∈ {standard, elite, boss}`.
- `FIGHT` and `REWARD` → `pool_{continent}_standard` (`REWARD` applies a reduced
  encounter budget — see T19)
- `CHALLENGE` → `pool_{continent}_elite`
- `BOSS_FIGHT` → `pool_{continent}_boss`

Six continents × three classes = 18 pool ids. Example: a Combat node in Stage 3
gets `enemy_pool_id = "pool_asia_standard"`; the Stage 6 boss gets
`pool_north_america_boss`.

### 4.4 Reward / augment / supply placeholders

Per the "simple or placeholder first" decision:

- `REWARD` nodes → easy-fight `enemy_pool_id` (§4.3) **plus**
  `reward_table_id = "reward_basic"` for the guaranteed drop.
- `AUGMENT` nodes → `augment_pool_id = "augment_basic"`.
- `SUPPLY` nodes → no id field set. MVP supply (shop) content is resolved
  globally by `node_type == SUPPLY`; no per-node id is needed yet. A future
  `Node.shop_pool_id` is noted as a follow-up (§10) but is **not** required for
  T4 and is deliberately excluded to keep the T1 model change minimal.

## 5. Model Prerequisites (`NodeType` extension)

The user's node vocabulary needs two `NodeType` members beyond the current
`FIGHT / REWARD / AUGMENT / BOSS_FIGHT`. This is a small, additive T1 change and
is the only model edit T4 requires.

### Step 0 — extend `NodeType`

```python
class NodeType(str, Enum):
    FIGHT = "fight"
    REWARD = "reward"
    AUGMENT = "augment"
    SUPPLY = "supply"        # new — shop / resupply stop
    CHALLENGE = "challenge"  # new — elite optional-difficulty fight
    BOSS_FIGHT = "boss_fight"
```

Additive only — no existing value changes, so `Node.to_dict()` / `from_dict()`
need no code change (they already round-trip the enum by value). Required
synchronization:

- Update `docs/design/tasks/t1_model_contracts.md` §1 to list the two new members.
- Add a `tests/game/test_models.py` case round-tripping `SUPPLY` and
  `CHALLENGE` if the existing enum coverage is value-specific.
- Add a SPEC.md §B (Bugs / Backprop) entry recording the enum extension and its
  origin (T4 route vocabulary).

## 6. Implementation Steps

### Step 1 — module and catalogs

Create `src/game/route.py`. Import `Node`, `NodeType`, `NodeState`,
`WeatherState` from `models`. No Flet imports (V.1). Define `CityDef`,
`StageDef`, the `CITIES` dict, and the `STAGES` tuple (§3, §4).

### Step 2 — node id and index scheme

- `index`: global running counter `1..50`.
- `Node.id`: `f"node_{index:02d}"` (`node_01` … `node_50`) — unique, stable,
  sort-friendly.

### Step 3 — `build_route()`

Walk `STAGES` in order; for each stage walk `node_types` in order and
materialize one `Node` per entry:

- `city` = hub city `name`; `weather` = hub city `default_weather`.
- `node_type` from the sequence; `state = NodeState.UPCOMING`.
- Encounter id fields per §4.3 / §4.4 (`enemy_pool_id`, `reward_table_id`,
  `augment_pool_id`); leave others `None`.

Return the assembled list. Construct fresh `Node` objects on every call so
callers can mutate node state without cross-contaminating later calls.

### Step 4 — lookup helpers

- `get_city(city_id)` — `CITIES` lookup; raise `KeyError` with a clear message
  on miss.
- `stage_of(node_index)` — map a 1-based node index back to its `StageDef`.

### Step 5 — self-consistency assertions

At module import, assert `len(build_route()) == ROUTE_NODE_COUNT` and that every
`StageDef.city_id` exists in `CITIES`. Fails fast on content typos.

## 7. Test Plan (`tests/game/test_route.py`)

### 7.1 Shape

- `build_route()` returns exactly 50 nodes; indexes are `1..50`, contiguous,
  unique.
- Node ids are unique and match `node_{index:02d}`.

### 7.2 Stage structure

- Node-type sequence of stage 1 equals the 10-entry Europe sequence.
- Each of stages 2-6 equals the 8-entry sequence.
- Every stage's final node is `BOSS_FIGHT`.
- Exactly 6 `CHALLENGE` nodes exist, one in each stage.
- The route-final node (index 50) is `BOSS_FIGHT`, city New York — the famous-
  city grand boss (V.7).

### 7.3 City data

- All six cities have non-empty name/country/continent and finite lat/lon in
  valid ranges (`-90..90`, `-180..180`).
- Every node's `city` resolves to a `CityDef`.
- All nodes within one stage share the hub city and its `default_weather`.

### 7.4 Encounter ids

- `FIGHT` / `REWARD` / `CHALLENGE` / `BOSS_FIGHT` nodes have a non-`None`
  `enemy_pool_id` matching the `pool_{continent}_{class}` pattern.
- `REWARD` → `reward_basic` plus a standard `enemy_pool_id`; `AUGMENT` →
  `augment_basic`; `SUPPLY` → no encounter id fields set.

### 7.5 Determinism and isolation

- Two `build_route()` calls yield node lists with equal `to_dict()` output.
- Mutating a node's `state` in one returned list does not affect a subsequent
  call's list.

### 7.6 `Run` integration

- A `build_route()` result is accepted by `Run` construction (unique indexes,
  non-empty). Setting node 1 to `CURRENT` and `status=IN_PROGRESS` passes
  `Run` validation.

### 7.7 Model extension

- `NodeType.SUPPLY` and `NodeType.CHALLENGE` exist and round-trip through
  `Node.to_dict()` / `from_dict()`.

## 8. Acceptance Criteria

T4 is complete when all are true:

1. `NodeType` carries `SUPPLY` and `CHALLENGE`; `t1_model_contracts.md` and the
   SPEC.md §B log are synced.
2. `src/game/route.py` exists, has zero Flet imports (V.1), and exposes
   `build_route`, `get_city`, `stage_of`, `CITIES`, `STAGES`.
3. `build_route()` yields 50 valid, UPCOMING `Node`s across 6 continent stages
   with the locked §3.2 sequences.
4. Cities carry real geographic lat/lon; the route ends in a New York
   `BOSS_FIGHT` (V.7).
5. Combat/challenge/boss nodes carry enemy pool ids; reward/augment carry
   placeholder table ids.
6. `tests/game/test_route.py` passes; existing tests still pass.

## 9. Risks and Mitigations

- Risk: 50 nodes (≈38 fights) is a lot of content for a 2-student MVP.
  - Mitigation: T4 only defines structure and pool ids; fight *count* is cheap
    because T5 reuses ~5 enemy archetypes scaled by stage `difficulty`. Node
    sequences live in `STAGES` and can be shortened in one place if needed.

- Risk: `default_weather` placeholders drift from reality and mislead players.
  - Mitigation: placeholders are explicitly transient; T6 overwrites per city
    on load, and they exist only to keep `Node.weather` populated offline.

- Risk: SPEC example city table (Reykjavik, Mumbai) diverges from the chosen
  six hubs.
  - Mitigation: §10 flags the SPEC "Cities examples" table for a refresh; the
    table is illustrative, not contractual.

## 10. SPEC Reconciliation / Open Items

- **V.7**: updated to "one per continent, up to 6" — the route uses 6 stages.
- **D.1**: route topology is now locked as a linear 6-stage / 50-node chain.
  Branch/merge remains deferred — D.1 narrowed to "branching only".
- **D.2**: boss city locked to New York; per-stage boss pools named. Boss enemy
  *kits* and finale mechanics stay open (T5 / ability framework). The final boss
  uses live NYC weather like all other bosses — no special weather cycling.
- **SPEC "Cities examples" table**: refresh to the six chosen hubs (drops
  Reykjavik and Mumbai, adds Rio de Janeiro for South America).
- **`Node.shop_pool_id`**: a future field for per-node supply/shop content.
  Out of T4 scope; MVP supply content is resolved globally by node type.

## 11. Follow-up Tasks (Post-T4)

- T5 fills the 18 enemy pools and the reward/augment/supply placeholder tables.
- Add `Node.shop_pool_id` if supply nodes need per-node shop inventories.
- Revisit branching topology (D.1) for optional-path challenge nodes.
- Per-stage multi-city routes (more than one hub per continent) for a richer
  route map, once the content budget allows.
