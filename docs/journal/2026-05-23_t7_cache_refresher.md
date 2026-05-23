# T7 — Cache + Refresher Implementation

**Date**: 2026-05-23

## Context

T.7 builds the weather data layer between the T.6 `WeatherClient` and the game
engine. Without it, every weather lookup would hit the OpenWeather API directly,
which is untenable for 50 nodes on a free-tier key (60 calls/min limit).

## Decisions

### Cache Module (`src/api/cache.py`)

- **Three-state model**: `UNKNOWN` → `LIVE` / `SUBSTITUTE`. The engine never
  sees `None` (V.9). `SUBSTITUTE` holds the city's authored default weather
  when a fetch fails.
- **Thread-safe**: single `threading.Lock` protects all mutations. `get()`
  returns a copy of the entry to prevent external mutation races.
- **`fetch_and_cache` helper**: single call that fetches via `WeatherClient`,
  classifies the result (fallback → SUBSTITUTE, success → LIVE), and updates
  the cache. Used by both the refresher and the sync-on-advance path.

### Refresher Module (`src/api/refresher.py`)

- **3-stream selection per tick**:
  - A: sequential round-robin over all 50 cities (guarantees ≤ 50 min staleness)
  - B: round-robin over a lookahead window `[current+1 .. current+6]`
    (count-clamped at trail end)
  - C: uniform random pick from all 50
- **Dedup**: A picks first, B skips if duplicate, C skips if duplicate → ≤ 3
  unique fetches per tick.
- **Daemon timer**: `threading.Timer` re-armed after each tick. `stop()` cancels
  cleanly. Start is idempotent.
- **No backoff**: per spec, failed fetches just produce SUBSTITUTE and the
  stream keeps going next tick.

### What's NOT in T.7

- **Locking weather into `Run`**: that's the game engine's job (when advancing).
  The cache doesn't know about `Run` or `Node` (V.10).
- **UI staleness indicators**: deferred to D.17.
- **Init orchestration** (alloc cache, sync tick #1, start refresher): will live
  in the app wiring layer (T.15) or a dedicated init helper.

## Testing

29 unit tests covering:
- Cache state machine transitions
- `fetch_and_cache` success/failure paths
- Thread-safety under concurrent reads/writes
- A-stream full coverage in 50 ticks
- B-stream window clamping at trail end
- C-stream randomness coverage
- Dedup uniqueness guarantee
- Timer lifecycle (start/stop/idempotent)
- Timer actually fires ticks (fast-interval integration)

## Open Items

None — all design questions were pre-decided in SPEC §V.9-V.13 and the T.7
planning notes. No ambiguity encountered during implementation.
