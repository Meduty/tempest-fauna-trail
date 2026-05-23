# T6 Plan — OpenWeather Client (`src/api/weather.py`)

## 1. Scope

T6 delivers the HTTP client that fetches current weather from the OpenWeather
API and returns a `WeatherState` enum. It bridges the external API and the
game's internal weather model.

Primary output: `src/api/weather.py`

Test output: `tests/api/test_weather.py`

## 2. Prerequisites

- **T.1** — `WeatherState` enum with `from_openweather_id(weather_id)` mapping
  (already implemented in `src/game/models.py`).
- `requests` library (already in `requirements.txt`).
- `python-dotenv` for env var loading (already in `requirements.txt`).

## 3. Design Decisions

### 3.1 Query by coordinates (lat/lon)

The client queries by latitude/longitude (from `CityDef` in `game/route.py`)
rather than by city name. This avoids ambiguity issues (e.g., "Santiago" in
multiple countries) and matches the integration test pattern already in place.

### 3.2 Failure handling (V.3)

API failure never crashes the app. On any HTTP or parsing error, the client
returns a fallback `WeatherState` (default: the city's `default_weather` from
`CityDef`, or `WeatherState.CLEAR` if none provided).

### 3.3 Threading (V.4)

The client itself is synchronous — callers must invoke it from a worker thread.
This keeps the client simple and testable; threading responsibility lives in
the UI layer.

### 3.4 API key source

Read from `os.environ["OPENWEATHER_API_KEY"]`. Raise a clear error at client
construction if the key is missing.

## 4. Public Surface

```python
@dataclass
class WeatherResult:
    """Parsed weather response for a single location."""
    state: WeatherState
    temperature: float        # Celsius
    icon_code: str            # e.g. "10d" — for UI icon URL
    description: str          # e.g. "light rain"
    weather_id: int           # raw OW weather condition id

class WeatherClient:
    """Synchronous OpenWeather API client."""

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize with explicit key or fall back to env var."""

    def fetch_weather(
        self, lat: float, lon: float, *, fallback: WeatherState = WeatherState.CLEAR
    ) -> WeatherResult:
        """Fetch current weather for coordinates.

        Returns parsed result on success.
        Returns a fallback WeatherResult on any failure (network, timeout, parse).
        Never raises.
        """
```

## 5. Implementation Details

### 5.1 Endpoint

```
GET https://api.openweathermap.org/data/2.5/weather
    ?lat={lat}&lon={lon}&appid={key}&units=metric
```

### 5.2 Response parsing

Extract from JSON response:
- `weather[0].id` → `WeatherState.from_openweather_id(id)`
- `weather[0].icon` → icon code string
- `weather[0].description` → description string
- `main.temp` → temperature float

### 5.3 Error handling

Wrap entire fetch+parse in try/except. On any exception:
1. Log warning (to stderr or logging module).
2. Return `WeatherResult(state=fallback, temperature=0.0, icon_code="01d",
   description="unknown", weather_id=800)`.

### 5.4 Timeout

HTTP timeout: 10 seconds (matches integration test).

## 6. Test Plan (`tests/api/test_weather.py`)

All tests mock `requests.get` — no real network calls.

### 6.1 Successful fetch
- Mock valid 200 response → returns correct `WeatherResult` with mapped state.

### 6.2 HTTP error
- Mock 401/500 response → returns fallback `WeatherResult`.

### 6.3 Network timeout
- Mock `requests.exceptions.Timeout` → returns fallback.

### 6.4 Malformed JSON
- Mock response with broken body → returns fallback.

### 6.5 Missing API key
- No key in env or constructor → raises `ValueError` at construction.

### 6.6 All WeatherState mappings
- Parametrize with sample OW ids from each group → correct state.

## 7. Out of Scope (T6)

| Item | Handled in |
|------|------------|
| Response caching (TTL) | T7 |
| Threading / async wrapper | UI layer (T11, T15) |
| Batch multi-city fetch | T11 (map view) |
| Rate limiting | Caller responsibility |

## 8. Acceptance Criteria

- [x] `WeatherClient` can be instantiated with explicit key or env var.
- [x] `fetch_weather()` returns correct `WeatherResult` on happy path.
- [x] `fetch_weather()` never raises — returns fallback on any failure.
- [x] All 6 weather states map correctly from sample OW ids.
- [x] Unit tests pass with mocked HTTP.
- [x] No Flet imports (V.1 — this is in `api/`, not `game/`).
