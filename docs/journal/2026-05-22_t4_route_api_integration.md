# Journal - 2026-05-22 (T4 Route Implementation + API Integration Tests)

## Scope and User Intent

Implementation session. Goal: deliver T4 (`src/game/route.py`), verify all 50
city coordinates, wire up the OpenWeather API key, and prove both the weather
and geocoding endpoints work against the live API.

Started from: T1-T3 implemented and green. T4 plan written (`t4_city_route_plan.md`).
SPEC §T.4 acceptance criteria used as the test target.

## Chronological Protocol

1. **`NodeType` extension.** Read `src/game/models.py`; found `SUPPLY` and
   `CHALLENGE` missing from the enum. Added both values additively — no existing
   code touched.

2. **`src/game/route.py` implementation.** Wrote the full module:
   - `CityDef` frozen dataclass (`id`, `name`, `country`, `continent`,
     `latitude`, `longitude`, `default_weather`).
   - `StageDef` frozen dataclass (`index`, `name`, `affinity`, `node_cities`,
     `node_types`, `difficulty`).
   - `CITIES: dict[str, CityDef]` — 50 entries across 6 continents (Europe 10,
     Africa 8, Asia 8, Oceania 8, South America 8, North America 8).
   - `STAGES: tuple[StageDef, ...]` — 6 stages; stage 1 CLEAR diff=1 10 nodes,
     stages 2-6 each 8 nodes with one boss city at the end.
   - Boss cities: Vienna (S1), Cairo (S2), Tokyo (S3), Sydney (S4), Rio (S5),
     New York (S6).
   - Helpers: `build_route() -> list[Node]`, `get_city(id) -> CityDef`,
     `stage_of(node_index) -> StageDef`.

3. **Coordinate verification via OSM Nominatim.** All 50 city lat/lon values
   checked against Nominatim. Found 8 errors; corrected:
   Tokyo lon (139.65→139.76), Singapore (1.35,103.82→1.29,103.85),
   Lagos lat (6.52→6.46), Hong Kong lat (22.32→22.28),
   Quito (-0.18/-78.47→-0.22/-78.51), Rio lon (-43.17→-43.21),
   Jakarta lat (-6.21→-6.18), Casablanca (33.57/-7.59→33.59/-7.62).

4. **`tests/game/test_route.py`.** Wrote 36 tests in 7 classes:
   `TestShape`, `TestStageStructure`, `TestCityData`, `TestEncounterIds`,
   `TestDeterminism`, `TestRunIntegration`, `TestLookupHelpers`. All pass.

5. **`.env` + dotenv setup.** Added `python-dotenv>=1.0.0` to
   `pyproject.toml` and `requirements.txt`. Created root `conftest.py` that
   auto-loads `.env` before every pytest session. Created `.env.example`.
   Confirmed `.env` already in `.gitignore`.

6. **`tests/api/test_weather_integration.py` — initial version.** 51 tests:
   50 per-city parametrised (`test_openweather_city`) + 1 bulk smoke
   (`test_all_50_cities_reachable`). Registered `integration` marker in
   `pyproject.toml`. All 51 returned HTTP 401 — API key not yet activated
   (new OW keys take up to 2 h).

7. **Endpoint correction.** User pointed out OW docs: `?q=city_name` is
   deprecated; canonical endpoint is `?lat=&lon=`. Switched `_fetch()` to use
   `lat`/`lon` params and tightened `COORD_TOLERANCE` from 1.0° to 0.05°
   (OW echoes back our coords rounded to ~2 dp). Tests still 401 — key pending.

8. **Geocoding API discovery.** User pointed to `openweathermap.org/api/geocoding-api`.
   Fetched the docs: `GET /geo/1.0/direct?q={name},{country_code}&limit=N&appid={key}`
   returns `[{lat, lon, name, country}]` using the same key. Since switching to
   lat/lon for the weather endpoint made the coord echo-check trivial, this API
   provides genuine independent coord verification (by city name rather than
   by coordinate).

9. **Geocoding tests added.** Extended the integration test file:
   - `_GEO_BASE` constant.
   - `_COUNTRY_ISO: dict[str, str]` — 37 ISO 3166-1 alpha-2 codes covering
     every country in `CITIES`, used to build unambiguous `?q=Name,CC` queries
     (e.g. `Santiago,CL` not `Santiago`).
   - `GEOCODE_TOLERANCE = 0.5°` (looser than the weather check since geocoders
     return city centroids, not the exact point stored).
   - `_geocode(city_name, country)` helper.
   - `test_geocode_coords[city_*]` — 50 parametrised tests; takes the closest
     of up to 3 returned candidates and asserts lat/lon within tolerance.
   - Total integration tests: 101.

10. **Key activated; all 101 pass.** Re-ran `pytest tests/api/test_weather_integration.py
    -v -m integration`. 101 passed in ~24 s. Both endpoint types (weather and
    geocoding) confirmed working against all 50 cities.

## Decisions and Rationale

- **lat/lon over `?q=name`** — OW explicitly froze bug-fixing on the name
  endpoint; lat/lon is the current recommended path and avoids UTF-8 city-name
  disambiguation issues.
- **Geocoding at 0.5° tolerance** — geocoders resolve to administrative
  centroids which can be ~30 km from a point near city hall; 0.5° ≈ 55 km is
  the smallest round number that clears all 50 cities without false positives.
- **`limit=3` with best-match selection** — some cities have near-duplicate
  entries in OW's database (e.g. district vs. metro area); taking the closest
  candidate avoids false failures.
- **ISO country codes in test file, not in `CityDef`** — country codes are
  test-only infrastructure; `CityDef` exposes the human-readable country name
  used in UI copy. No game logic needs ISO codes.

## Issues Encountered and Resolved

| # | Issue | Resolution |
|---|-------|------------|
| 1 | `NodeType` missing `SUPPLY`, `CHALLENGE` | Added values additively |
| 2 | 8 city coords wrong vs. Nominatim | Corrected directly in `route.py` |
| 3 | Integration tests 401 for ~2 h | Waited for OW key activation |
| 4 | `?q=name` deprecated | Switched `_fetch()` to `lat`/`lon` params |
| 5 | Coord echo-check trivial after lat/lon switch | Added geocoding API tests for genuine coord verification |

## Repo Changes Summary

- Modified: `src/game/models.py` — added `NodeType.SUPPLY`, `NodeType.CHALLENGE`
- Added: `src/game/route.py` — 50-city route, 6 stages, helpers
- Added: `tests/game/test_route.py` — 36 unit tests (all pass)
- Modified: `pyproject.toml` — `python-dotenv` dep, `integration` marker, `testpaths`
- Modified: `requirements.txt` — `python-dotenv>=1.0.0`
- Added: `conftest.py` (project root) — dotenv auto-load
- Added: `.env.example`
- Added: `tests/api/__init__.py`
- Added: `tests/api/test_weather_integration.py` — 101 integration tests (all pass)

## Test Counts at Session End

| Suite | Count | Status |
|-------|-------|--------|
| Unit tests (game logic) | 99 | ✅ pass |
| Integration tests (OpenWeather) | 101 | ✅ pass |
| **Total** | **200** | **✅** |
