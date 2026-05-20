---
paths:
  - "src/api/**/*.py"
---

# API Rules

- All HTTP calls wrapped in try/except — log failures, return cached or default
- Cache as JSON with timestamps, 1h TTL
- API key from `os.environ["OPENWEATHER_API_KEY"]` — never hardcode or log
- Mock responses in tests with `unittest.mock.patch`
- No blocking I/O on main thread
