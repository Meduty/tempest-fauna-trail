# Weather API — fetch, cache, refresher

> **Status: LIVING** — must match `src/api/weather.py`, `api/cache.py`, `api/refresher.py`. Audited by `/check`.
> **Scope:** OpenWeather client, per-city cache states, and the 3-stream tick refresher (≤3 calls/min). **Reconciled:** 2026-06-05.
>
> 🔶 **STUB** — anchors only; prose TBD. Design (frozen): `docs/design/tasks/t6_*`, `t7_*`. Invariants: V.3 (key never logged), V.4 (HTTP off main thread), V.9–V.13 (cache/refresher).

## Where it lives
- `api/weather.py` — OpenWeather client (lat/lon).
- `api/cache.py` — stateless per-city cache (unknown / live+fetched_at / substitute).
- `api/refresher.py` — 1/min tick, 3 deduped streams.
