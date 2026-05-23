# T7 Plan — Cache + Refresher (`src/api/cache.py`, `src/api/refresher.py`)

## 1. Scope

T7 delivers a per-city weather cache and a background tick refresher that keeps
weather data fresh across all 50 route nodes. It sits between the T.6
`WeatherClient` and the game engine, ensuring weather is always available
without blocking the main thread.

Primary outputs:
- `src/api/cache.py` — stateless per-city weather cache
- `src/api/refresher.py` — 3-stream background tick refresher

Test outputs:
- `tests/api/test_cache.py`
- `tests/api/test_refresher.py`

## 2. Prerequisites

- **T.6** — `WeatherClient` with `fetch_weather(lat, lon, fallback=...)` (done).
- **T.4** — `CITIES` dict with `CityDef` (lat/lon/default_weather) and
  `STAGES` with ordered city IDs (done).
- **T.1** — `WeatherState` enum, `Run` with `current_node_index` (done).

## 3. Design Decisions

### 3.1 Cache States (V.9)

Each city slot holds one of three states:

| State | Meaning | Data |
|-------|---------|------|
| `unknown` | Never fetched; initial state | `None` |
| `live` | Successfully fetched | `WeatherResult` + `fetched_at: float` (time.time()) |
| `substitute` | Fetch failed; holding city default | `WeatherResult(is_fallback=True)` + `fetched_at` |

The engine never sees `None` — callers use `get()` which returns a
`CacheEntry` that is always one of these three tagged variants.

### 3.2 Cache is Stateless re: Game (V.10)

The cache is a flat dict keyed by city_id. It has no knowledge of `Run`,
`Node`, or game state. The refresher reads `Run.current_node_index` (via a
callable) solely for B-stream window computation; it never writes game state.

### 3.3 Locked Weather (V.12)

Locking is NOT managed by the cache module. When the game advances to a node,
the engine snapshots `cache.get(city_id)` into the `Run`'s node weather. Once
locked, the engine reads from `Run`, not from the cache. The cache may
continue refreshing that city — harmless.

### 3.4 Advance-to-Unknown (V.13)

When the engine advances to a node whose cache state is `unknown`, it performs
one synchronous fetch (on the calling thread — expected to be a worker thread)
and locks the result. On fetch fail, lock `substitute` with
`CITIES[city_id].default_weather`. This is a caller-side concern handled by a
helper function in `cache.py`.

### 3.5 Three Refresh Streams (V.11)

Per tick (1/min), the refresher selects up to 3 cities to refresh:

| Stream | Strategy | Purpose |
|--------|----------|---------|
| A | Full round-robin over all 50 cities | Bounds max staleness ≤ 50 min |
| B | Round-robin over window `[current+1 .. current+6]`, count-clamped at trail end | Keeps upcoming nodes fresh |
| C | Uniform random over all 50 cities | Probabilistic freshness boost |

**Dedup order**: A picks first, B picks next (skip if same as A), C picks last
(skip if same as A or B). Result: ≤ 3 unique cities per tick → ≤ 3 API calls/min.

### 3.6 Init Behavior

On `Run` start:
1. Allocate cache: 50× `unknown`
2. Fire tick #1 synchronously: fetches stream A (city 0), B (city 1), C (random)
3. Lock node 0 weather from tick-1 result
4. Start background timer thread

### 3.7 Threading (V.4)

- The refresher runs on a daemon `threading.Timer` (re-armed every 60s).
- All `WeatherClient.fetch_weather` calls happen on the refresher thread.
- `cache.get()` and `cache.set()` are thread-safe (use `threading.Lock`).
- The advance-to-unknown sync fetch runs on the caller's worker thread.

### 3.8 No Backoff

On repeated fetch failures, streams keep firing at 3/min. Failed fetches
produce `substitute` entries that are retried on the next tick that selects
that city.

## 4. Public Surface

### 4.1 `src/api/cache.py`

```python
from enum import Enum
from dataclasses import dataclass
from src.api.weather import WeatherResult

class CacheState(str, Enum):
    UNKNOWN = "unknown"
    LIVE = "live"
    SUBSTITUTE = "substitute"

@dataclass
class CacheEntry:
    city_id: str
    state: CacheState
    result: WeatherResult | None  # None only when state == UNKNOWN
    fetched_at: float | None      # None only when state == UNKNOWN

class WeatherCache:
    """Thread-safe per-city weather cache for the 50-node route."""

    def __init__(self, city_ids: list[str]) -> None:
        """Initialize all cities to UNKNOWN state."""

    def get(self, city_id: str) -> CacheEntry:
        """Return the current cache entry for a city. Never raises."""

    def set_live(self, city_id: str, result: WeatherResult) -> None:
        """Mark city as LIVE with fresh weather data."""

    def set_substitute(self, city_id: str, result: WeatherResult) -> None:
        """Mark city as SUBSTITUTE (fetch failed, holding default weather)."""

    def all_entries(self) -> dict[str, CacheEntry]:
        """Snapshot of all cache entries (for diagnostics/UI)."""

    @property
    def city_ids(self) -> list[str]:
        """Ordered list of city IDs managed by this cache."""

def fetch_and_cache(
    cache: WeatherCache,
    client: WeatherClient,
    city_id: str,
    city_def: CityDef,
) -> CacheEntry:
    """Fetch weather for a city and update cache. Returns the new entry.
    
    On success → set_live. On failure (is_fallback) → set_substitute.
    Synchronous — caller must be on a worker thread (V.4).
    """
```

### 4.2 `src/api/refresher.py`

```python
from typing import Callable

class WeatherRefresher:
    """Background 3-stream weather refresher. Ticks once per minute."""

    def __init__(
        self,
        cache: WeatherCache,
        client: WeatherClient,
        get_current_node_index: Callable[[], int],
        tick_interval: float = 60.0,
    ) -> None:
        """
        Args:
            cache: The shared WeatherCache instance.
            client: WeatherClient for API calls.
            get_current_node_index: Callable returning current 0-based index
                into the cache's city_ids list.
            tick_interval: Seconds between ticks (default 60).
        """

    def start(self) -> None:
        """Start the background tick timer (daemon thread)."""

    def stop(self) -> None:
        """Stop the refresher. Idempotent."""

    def tick(self) -> list[str]:
        """Execute one tick: pick 3 deduped cities, fetch each.
        
        Returns list of city_ids that were fetched this tick.
        Exposed publicly for testing; normally called by the timer.
        """

    @property
    def running(self) -> bool:
        """Whether the refresher timer is active."""
```

## 5. Implementation Details

### 5.1 Stream Selection Algorithm

```
A_pointer: cycles 0..49, advances +1 per tick
B_pointer: cycles 0..min(5, remaining_nodes-1), advances +1 per tick
           window = city_ids[current_node_index .. current_node_index+6] (clamped)
C_index:   random.randint(0, 49) per tick (no freshness check, no re-roll)
```

Dedup: build set `{A_city}`, add B if not in set, add C if not in set.
Fetch each in order.

### 5.2 B-Stream Window Clamping

All indices are 0-based into the `city_ids` list.

`window_start = current_node_index + 1` (first city *ahead* of current)
`window_end = min(window_start + 6, len(city_ids))` (exclusive upper bound)
`window = city_ids[window_start : window_end]` → up to 6 cities

If window is empty (player at or past last node), B produces nothing for that tick.

B round-robin wraps within its own window slice, not globally.

### 5.3 Thread Safety

- `WeatherCache` uses a single `threading.Lock` for all mutations.
- `get()` acquires lock, copies entry, releases. Reads are fast.
- Refresher tick acquires NO lock on cache directly — it calls
  `fetch_and_cache()` which internally calls `cache.set_*()`.

### 5.4 Timer Implementation

Use `threading.Timer` (daemon=True), re-armed at end of each tick.
`stop()` cancels the pending timer. The refresher holds a reference to
the current timer for cancellation.

## 6. Test Plan

### 6.1 `tests/api/test_cache.py`

| Test | Validates |
|------|-----------|
| Init creates all UNKNOWN entries | V.9 |
| `set_live` transitions to LIVE | State machine |
| `set_substitute` transitions to SUBSTITUTE | State machine |
| `get` returns UNKNOWN for unfetched city | V.9 |
| `fetch_and_cache` success → LIVE | Integration |
| `fetch_and_cache` failure → SUBSTITUTE | V.3, V.13 |
| Thread safety: concurrent set/get | V.4 |

### 6.2 `tests/api/test_refresher.py`

| Test | Validates |
|------|-----------|
| `tick()` returns ≤ 3 unique city_ids | V.11 |
| A stream round-robins all 50 over 50 ticks | V.11 staleness bound |
| B stream selects from window ahead of current | V.10, V.11 |
| B stream clamps at trail end | Edge case |
| C stream picks random city | V.11 |
| Dedup removes duplicates across streams | V.11 |
| `start()`/`stop()` lifecycle | Timer management |
| Tick calls `fetch_and_cache` for each selected city | Integration |

## 7. Integration Points

| Consumer | How it uses T.7 |
|----------|-----------------|
| Game engine (advance) | Calls `cache.get(city_id)` on advance; if UNKNOWN, calls `fetch_and_cache` synchronously then locks |
| Map view (T.11) | Reads `cache.all_entries()` for weather icons |
| UI age indicator (D.17) | Reads `CacheEntry.fetched_at` for staleness warnings |
| Run init | Creates cache, fires sync tick #1, starts refresher |

## 8. Out of Scope (T.7)

| Item | Handled in |
|------|------------|
| Node weather locking into `Run` | Game engine / T.14 |
| UI age/substitute warnings | D.17 |
| Backoff / exponential retry | Explicitly excluded per spec |
| Batch multi-city fetch | Not available on free tier |

## 9. Acceptance Criteria

- [ ] `WeatherCache` initializes 50 cities to `UNKNOWN`
- [ ] `fetch_and_cache` correctly sets `LIVE` on success, `SUBSTITUTE` on fail
- [ ] `WeatherRefresher.tick()` produces ≤ 3 unique city fetches per tick
- [ ] A stream alone covers all 50 cities in 50 ticks (staleness ≤ 50 min)
- [ ] B stream window is correctly clamped at trail end
- [ ] Dedup prevents duplicate fetches within a single tick
- [ ] Thread safety: concurrent access doesn't corrupt cache
- [ ] `start()`/`stop()` correctly manage daemon timer lifecycle
- [ ] All unit tests pass
- [ ] No Flet imports in `api/` modules (V.1 not applicable but good hygiene)
