# Weather API — fetch, cache, refresher

> **Status: LIVING** — must match `src/api/weather.py`, `api/cache.py`, `api/refresher.py`. Audited by `/check`.
> **Scope:** OpenWeather client, per-city cache states, and the 3-stream tick refresher (≤3 calls/min). **Reconciled:** 2026-07-01.
>
> Citations by symbol, not line. Design (frozen): `docs/design/tasks/t6_*`, `t7_*`. This layer is the *only* I/O in the project — `src/game/` never touches it (V.1).

## Client — `api/weather.py`

`WeatherClient(api_key=None)` reads `OPENWEATHER_API_KEY` from env (raises
`ValueError` if neither arg nor env is set; the key is never logged, V.3).
`fetch_weather(lat, lon, *, fallback=WeatherState.CLEAR)` hits OpenWeather
(`/data/2.5/weather`, `units=metric`, 10 s timeout) and returns a **frozen**
`WeatherResult(state, temperature, icon_code, description, weather_id,
is_fallback=False, error=None)`. On **any** exception (network, HTTP status,
parse) it logs a warning and returns `_fallback_result(fallback, error=str(exc))`
— a `WeatherResult` flagged `is_fallback=True` carrying the caller's `fallback`
state (`fetch_and_cache` passes the city's `default_weather`) — it **never
raises** (V.3/V.4). The OpenWeather condition-id → `WeatherState` mapping lives on
`WeatherState.from_openweather_id` (`models.py`); each fallback state has a
canned `(icon_code, weather_id)` in `_FALLBACK_WEATHER` (e.g. `RAIN → ("10d",
500)`, `THUNDER → ("11d", 200)`).

## Cache — `api/cache.py`

`WeatherCache` holds one `CacheEntry` per `city_id` with a `CacheState`:

| `CacheState` | Meaning | `fetched_at` |
|---|---|---|
| `UNKNOWN` | never fetched | `None` |
| `LIVE` | real fetch succeeded | set |
| `SUBSTITUTE` | fetch failed → city-default weather | set |

`set_live` / `set_substitute` update an entry; `fetch_and_cache(client, cache,
city_id, ...)` does the round trip — success → `set_live`, `is_fallback` →
`set_substitute`. Advancing to an `UNKNOWN` city triggers a synchronous fetch.

## Refresher — `api/refresher.py`

`WeatherRefresher` ticks once per `tick_interval` (default 60 s) on a daemon
thread (HTTP off the main thread, V.4). Each `tick()` picks **≤3 unique** cities
across three streams and fetches each, returning the fetched `city_id`s:

- **A** — full round-robin over all cities (`_a_pointer`).
- **B** — round-robin within the window `[current+1 .. current+6]` (`_b_pointer`).
  `get_current_node_index()` returns the **1-based** `Run.current_node_index`;
  the refresher converts to a 0-based list offset internally.
- **C** — uniform random (seedable via `rng_seed` for tests).

Dedupe across streams (a `seen` set; B and C only append if unseen) keeps it to
≤3 API calls/min (V.11 — ≤50 min staleness via stream A). `start()` arms a
daemon `threading.Timer` that re-arms itself each tick; `stop()` is idempotent;
`running` reflects timer state. Each `tick()` fetches via `fetch_and_cache`
(exceptions per city are logged, never propagated) and then fires the optional
`on_tick(fetched_ids)` callback (T.11) on the worker thread so a UI can repaint
when entries flip LIVE/SUBSTITUTE — a callback exception is logged, never
allowed to kill the refresher. `on_tick=None` (default) keeps every existing
caller byte-identical.

## Node weather lifecycle — persisted on the `Run` (T.39, V.73)

The cache/refresher are **fetch-scheduling + freshness** only; the **persisted source
of truth is the `Run` `Node`**. Each `Node` (`game/models.py`) carries:

| Field | Meaning |
|---|---|
| `weather: WeatherState` | the **effective** game weather all systems read — `default_weather` placeholder until a live fetch overwrites it (T4 §2) |
| `weather_state: NodeWeatherState` | `UNKNOWN` (never fetched → display `?`) / `LIVE` / `SUBSTITUTE` — distinct from `api.cache.CacheState` (game-local enum; importing CacheState would cycle) |
| `weather_locked: bool` | frozen for the run; the refresher skips it |

The Trail copies fetched cache values onto the `Run` via the **pure game-side mutators**
`Run.set_node_live_weather(node_index, weather, *, is_substitute)` and
`Run.lock_node_weather(node_index)` only — the cache/refresher never touch game state
(V.10). `set_node_live_weather` is a **no-op on a locked node**. The **current** node's
weather **locks at the Trail→Prep transition** (`trail.py::_play_next` → `lock_node_weather`,
persisted by `main._push_prep`'s `save_run`); an `UNKNOWN` node freezes `default_weather`
flagged `SUBSTITUTE`. Locking before the fight keeps the CHALLENGE squad roll +
`generate_node_reward` byte-identical (load-bearing for V.70). Pre-T.39 saves lack the two
new fields → `UNKNOWN`/`False` on read (no `schema_version` bump).

## Invariants this system owns

- **V.3** — the API key is never logged.
- **V.4** — all HTTP runs on a worker thread; a fetch failure never crashes
  (falls back to substitute weather).
- **V.1** — game logic has zero dependence on this layer; it consumes only the
  resulting `WeatherState`.

## File map

| Concern | Symbol |
|---|---|
| HTTP client + fallback | `api/weather.py` (`WeatherClient.fetch_weather`, `WeatherResult`, `_fallback_result`) |
| Per-city cache | `api/cache.py` (`WeatherCache`, `CacheEntry`, `CacheState`, `fetch_and_cache`) |
| 3-stream tick loop | `api/refresher.py` (`WeatherRefresher.tick`) |
| id → state mapping | `models.py::WeatherState.from_openweather_id` |
| persisted node lifecycle | `models.py` (`Node.weather`/`weather_state`/`weather_locked`, `NodeWeatherState`, `Run.set_node_live_weather`/`lock_node_weather`); write-through + lock in `ui/views/trail.py` |
