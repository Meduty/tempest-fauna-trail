"""Integration tests: OpenWeather API against every city in the route.

Skipped automatically when OPENWEATHER_API_KEY is not set.

Run explicitly:
    pytest tests/api/test_weather_integration.py -v -m integration

What each test does
-------------------
* Calls GET /data/2.5/weather?lat=<lat>&lon=<lon>&appid=<key>&units=metric
  for each of the 50 cities in route.CITIES.
* Asserts the API returns HTTP 200.
* Asserts the response body has the expected shape (coord, weather, main).
* Asserts weather[0].id can be mapped to a WeatherState via
  WeatherState.from_openweather_id.
* Asserts the returned coord is within COORD_TOLERANCE degrees of our stored
  values (OpenWeather rounds coordinates to ~2 decimal places).
"""
from __future__ import annotations

import os
import time

import pytest
import requests

from src.game.models import WeatherState
from src.game.route import CITIES, CityDef

# Degrees of tolerance when comparing stored lat/lon against what OpenWeather
# returns — tight (0.05°) since we query by coordinates directly; OW rounds
# to ~2 decimal places (~1 km).
COORD_TOLERANCE = 0.05

_OW_BASE = "https://api.openweathermap.org/data/2.5/weather"
_GEO_BASE = "http://api.openweathermap.org/geo/1.0/direct"
_RATE_DELAY = 0.1  # seconds between requests to stay within free-tier rate limit

# ISO 3166-1 alpha-2 codes for the countries used in route.CITIES.
# Used to disambiguate geocoding queries (e.g. "Santiago,CL" not "Santiago,DO").
_COUNTRY_ISO: dict[str, str] = {
    "Portugal": "PT",
    "Spain": "ES",
    "France": "FR",
    "United Kingdom": "GB",
    "Belgium": "BE",
    "Netherlands": "NL",
    "Germany": "DE",
    "Czech Republic": "CZ",
    "Italy": "IT",
    "Austria": "AT",
    "Morocco": "MA",
    "Senegal": "SN",
    "Nigeria": "NG",
    "Ghana": "GH",
    "Ethiopia": "ET",
    "Kenya": "KE",
    "Egypt": "EG",
    "India": "IN",
    "Thailand": "TH",
    "Singapore": "SG",
    "Indonesia": "ID",
    "China": "CN",
    "South Korea": "KR",
    "Japan": "JP",
    "Australia": "AU",
    "Papua New Guinea": "PG",
    "New Zealand": "NZ",
    "Colombia": "CO",
    "Ecuador": "EC",
    "Peru": "PE",
    "Chile": "CL",
    "Argentina": "AR",
    "Uruguay": "UY",
    "Brazil": "BR",
    "Mexico": "MX",
    "United States": "US",
    "Canada": "CA",
}

# Tolerance for geocoding coord check — looser than weather endpoint because
# OW's geocoder may resolve to the city centroid rather than the exact point
# we stored (e.g. city hall vs. geographic centre).
GEOCODE_TOLERANCE = 0.5


def _api_key() -> str:
    return os.environ["OPENWEATHER_API_KEY"]


def _skip_no_key() -> None:
    if not os.environ.get("OPENWEATHER_API_KEY"):
        pytest.skip("OPENWEATHER_API_KEY not set — integration test skipped")


def _fetch(lat: float, lon: float) -> requests.Response:
    """Fetch current weather by coordinates; return the Response object."""
    resp = requests.get(
        _OW_BASE,
        params={"lat": lat, "lon": lon, "appid": _api_key(), "units": "metric"},
        timeout=10,
    )
    return resp


# ---------------------------------------------------------------------------
# Per-city parametrised test
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.parametrize("city_id,city", list(CITIES.items()))
def test_openweather_city(city_id: str, city: CityDef) -> None:
    """Each city in route.CITIES must return a valid OpenWeather response."""
    _skip_no_key()

    time.sleep(_RATE_DELAY)

    resp = _fetch(city.latitude, city.longitude)

    # --- HTTP status -------------------------------------------------------
    assert resp.status_code == 200, (
        f"[{city_id}] {city.name}: HTTP {resp.status_code} — {resp.text[:200]}"
    )

    data = resp.json()

    # --- Required top-level keys -------------------------------------------
    for key in ("coord", "weather", "main", "name"):
        assert key in data, f"[{city_id}] response missing key {key!r}"

    # --- coord shape and range ---------------------------------------------
    coord = data["coord"]
    assert "lat" in coord and "lon" in coord, (
        f"[{city_id}] coord missing lat/lon"
    )
    api_lat: float = coord["lat"]
    api_lon: float = coord["lon"]
    assert -90.0 <= api_lat <= 90.0, f"[{city_id}] API lat {api_lat} out of range"
    assert -180.0 <= api_lon <= 180.0, f"[{city_id}] API lon {api_lon} out of range"

    # --- coord close to our stored value ------------------------------------
    assert abs(api_lat - city.latitude) <= COORD_TOLERANCE, (
        f"[{city_id}] latitude mismatch: stored={city.latitude}, "
        f"API={api_lat}, diff={abs(api_lat - city.latitude):.4f}°"
    )
    assert abs(api_lon - city.longitude) <= COORD_TOLERANCE, (
        f"[{city_id}] longitude mismatch: stored={city.longitude}, "
        f"API={api_lon}, diff={abs(api_lon - city.longitude):.4f}°"
    )

    # --- weather array -----------------------------------------------------
    assert isinstance(data["weather"], list) and len(data["weather"]) >= 1, (
        f"[{city_id}] weather array empty or missing"
    )
    weather_entry = data["weather"][0]
    for key in ("id", "main", "description", "icon"):
        assert key in weather_entry, (
            f"[{city_id}] weather[0] missing key {key!r}"
        )

    # --- weather id maps to a WeatherState ----------------------------------
    weather_id: int = weather_entry["id"]
    try:
        state = WeatherState.from_openweather_id(weather_id)
    except ValueError as exc:
        pytest.fail(
            f"[{city_id}] weather id {weather_id} could not be mapped to "
            f"WeatherState: {exc}"
        )
    assert isinstance(state, WeatherState)

    # --- main temperature block --------------------------------------------
    main = data["main"]
    for key in ("temp", "feels_like", "humidity", "pressure"):
        assert key in main, f"[{city_id}] main block missing key {key!r}"
    assert isinstance(main["temp"], (int, float)), (
        f"[{city_id}] main.temp is not a number"
    )


# ---------------------------------------------------------------------------
# Bulk summary test (single call, skips gracefully)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_all_50_cities_reachable() -> None:
    """Smoke test: all 50 cities return HTTP 200 from OpenWeather.

    Reports every failing city at once rather than stopping on the first error.
    """
    _skip_no_key()

    failures: list[str] = []
    for city_id, city in CITIES.items():
        time.sleep(_RATE_DELAY)
        resp = _fetch(city.latitude, city.longitude)
        if resp.status_code != 200:
            failures.append(
                f"{city_id} ({city.name}): HTTP {resp.status_code}"
            )

    assert not failures, (
        f"{len(failures)} city/cities failed OpenWeather lookup:\n"
        + "\n".join(f"  - {f}" for f in failures)
    )


# ---------------------------------------------------------------------------
# Geocoding coord verification tests  (geo/1.0/direct)
# ---------------------------------------------------------------------------

def _geocode(city_name: str, country: str) -> requests.Response:
    """Call OW Geocoding API with city name + ISO country code."""
    country_code = _COUNTRY_ISO.get(country, "")
    q = f"{city_name},{country_code}" if country_code else city_name
    return requests.get(
        _GEO_BASE,
        params={"q": q, "limit": 3, "appid": _api_key()},
        timeout=10,
    )


@pytest.mark.integration
@pytest.mark.parametrize("city_id,city", list(CITIES.items()))
def test_geocode_coords(city_id: str, city: CityDef) -> None:
    """OW Geocoding API must resolve each city to coords within GEOCODE_TOLERANCE.

    Queries geo/1.0/direct?q={name},{country_code}&limit=3 and takes the
    result closest to our stored coordinates.  A mismatch > 0.5° means our
    stored lat/lon diverges from where OW's own geocoder thinks the city is.
    """
    _skip_no_key()

    time.sleep(_RATE_DELAY)

    resp = _geocode(city.name, city.country)

    assert resp.status_code == 200, (
        f"[{city_id}] {city.name}: Geocoding HTTP {resp.status_code} — "
        f"{resp.text[:200]}"
    )

    results: list[dict] = resp.json()
    assert len(results) > 0, (
        f"[{city_id}] {city.name}: Geocoding returned empty list"
    )

    # Take whichever result is closest to our stored coords
    best = min(
        results,
        key=lambda r: abs(r["lat"] - city.latitude) + abs(r["lon"] - city.longitude),
    )
    lat_diff = abs(best["lat"] - city.latitude)
    lon_diff = abs(best["lon"] - city.longitude)

    assert lat_diff <= GEOCODE_TOLERANCE, (
        f"[{city_id}] {city.name}: geocoded lat {best['lat']:.4f} vs stored "
        f"{city.latitude:.4f} — diff {lat_diff:.4f}° > {GEOCODE_TOLERANCE}°"
    )
    assert lon_diff <= GEOCODE_TOLERANCE, (
        f"[{city_id}] {city.name}: geocoded lon {best['lon']:.4f} vs stored "
        f"{city.longitude:.4f} — diff {lon_diff:.4f}° > {GEOCODE_TOLERANCE}°"
    )
