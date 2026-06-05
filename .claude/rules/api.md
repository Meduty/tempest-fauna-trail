---
paths:
  - "src/api/**/*.py"
---

# API Rules

> **Before editing:** complete the required reading in [CLAUDE.md](../../CLAUDE.md) → "Required reading before any task work" — SPEC.md, ARCHITECTURE.md (§10 API layer), **the LIVING doc [docs/live/systems/weather_api.md](../../docs/live/systems/weather_api.md)**, the task plan doc, the touched design docs, and the touched code.
>
> **After editing:** update `docs/live/systems/weather_api.md` in the same change (real code taxonomy; flip 🔶→✅ if you made it true), then run `/check`. A stale living doc is a bug.

- All HTTP calls wrapped in try/except — log failures, return per-city `default_weather` substitute (SPEC V.3)
- Cache + refresher follow T.7 model: stateless cache with `unknown`/`live`+`fetched_at`/`substitute` states; 3-stream tick refresher (A full RR, B near window, C random) → ≤3 API calls/min (SPEC §V.9-V.13)
- API key from `os.environ["OPENWEATHER_API_KEY"]` — never hardcode or log
- Mock responses in tests with `unittest.mock.patch`; live API tests marked `@pytest.mark.integration`
- No blocking I/O on main thread (V.4)
