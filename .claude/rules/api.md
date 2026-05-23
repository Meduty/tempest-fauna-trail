---
paths:
  - "src/api/**/*.py"
---

# API Rules

- All HTTP calls wrapped in try/except — log failures, return per-city `default_weather` substitute (SPEC V.3)
- Cache + refresher follow T.7 model: stateless cache with `unknown`/`live`+`fetched_at`/`substitute` states; 3-stream tick refresher (A full RR, B near window, C random) → ≤3 API calls/min (SPEC §V.9-V.13)
- API key from `os.environ["OPENWEATHER_API_KEY"]` — never hardcode or log
- Mock responses in tests with `unittest.mock.patch`; live API tests marked `@pytest.mark.integration`
- No blocking I/O on main thread (V.4)
