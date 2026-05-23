"""Unit tests for src/api/cache.py — per-city weather cache."""
from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

from src.api.cache import CacheEntry, CacheState, WeatherCache, fetch_and_cache
from src.api.weather import WeatherResult
from src.game.models import WeatherState
from src.game.route import CityDef


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def city_ids() -> list[str]:
    return [f"city_{i}" for i in range(50)]


@pytest.fixture
def cache(city_ids: list[str]) -> WeatherCache:
    return WeatherCache(city_ids)


@pytest.fixture
def live_result() -> WeatherResult:
    return WeatherResult(
        state=WeatherState.RAIN,
        temperature=15.0,
        icon_code="10d",
        description="light rain",
        weather_id=500,
    )


@pytest.fixture
def fallback_result() -> WeatherResult:
    return WeatherResult(
        state=WeatherState.CLEAR,
        temperature=0.0,
        icon_code="01d",
        description="unknown",
        weather_id=800,
        is_fallback=True,
        error="timeout",
    )


@pytest.fixture
def city_def() -> CityDef:
    return CityDef(
        id="city_0",
        name="TestCity",
        country="TC",
        continent="TestContinent",
        latitude=10.0,
        longitude=20.0,
        default_weather=WeatherState.CLEAR,
    )


# ---------------------------------------------------------------------------
# Tests: Initialization
# ---------------------------------------------------------------------------

class TestCacheInit:
    def test_all_entries_start_unknown(self, cache: WeatherCache, city_ids: list[str]) -> None:
        for cid in city_ids:
            entry = cache.get(cid)
            assert entry.state == CacheState.UNKNOWN
            assert entry.result is None
            assert entry.fetched_at is None

    def test_city_ids_property(self, cache: WeatherCache, city_ids: list[str]) -> None:
        assert cache.city_ids == city_ids

    def test_unknown_city_raises_keyerror(self, cache: WeatherCache) -> None:
        with pytest.raises(KeyError):
            cache.get("nonexistent_city")


# ---------------------------------------------------------------------------
# Tests: State transitions
# ---------------------------------------------------------------------------

class TestCacheStateTransitions:
    def test_set_live(self, cache: WeatherCache, live_result: WeatherResult) -> None:
        cache.set_live("city_0", live_result)
        entry = cache.get("city_0")
        assert entry.state == CacheState.LIVE
        assert entry.result == live_result
        assert entry.fetched_at is not None

    def test_set_substitute(self, cache: WeatherCache, fallback_result: WeatherResult) -> None:
        cache.set_substitute("city_0", fallback_result)
        entry = cache.get("city_0")
        assert entry.state == CacheState.SUBSTITUTE
        assert entry.result == fallback_result
        assert entry.fetched_at is not None

    def test_live_overwrites_substitute(
        self, cache: WeatherCache, live_result: WeatherResult, fallback_result: WeatherResult
    ) -> None:
        cache.set_substitute("city_0", fallback_result)
        cache.set_live("city_0", live_result)
        entry = cache.get("city_0")
        assert entry.state == CacheState.LIVE
        assert entry.result == live_result

    def test_substitute_overwrites_live(
        self, cache: WeatherCache, live_result: WeatherResult, fallback_result: WeatherResult
    ) -> None:
        cache.set_live("city_0", live_result)
        cache.set_substitute("city_0", fallback_result)
        entry = cache.get("city_0")
        assert entry.state == CacheState.SUBSTITUTE


# ---------------------------------------------------------------------------
# Tests: all_entries
# ---------------------------------------------------------------------------

class TestAllEntries:
    def test_returns_all_cities(self, cache: WeatherCache, city_ids: list[str]) -> None:
        entries = cache.all_entries()
        assert set(entries.keys()) == set(city_ids)

    def test_snapshot_is_independent(
        self, cache: WeatherCache, live_result: WeatherResult
    ) -> None:
        entries = cache.all_entries()
        cache.set_live("city_0", live_result)
        # Original snapshot unchanged
        assert entries["city_0"].state == CacheState.UNKNOWN


# ---------------------------------------------------------------------------
# Tests: fetch_and_cache
# ---------------------------------------------------------------------------

class TestFetchAndCache:
    def test_success_sets_live(
        self, cache: WeatherCache, live_result: WeatherResult, city_def: CityDef
    ) -> None:
        client = MagicMock()
        client.fetch_weather.return_value = live_result

        entry = fetch_and_cache(cache, client, "city_0", city_def)

        assert entry.state == CacheState.LIVE
        assert entry.result == live_result
        client.fetch_weather.assert_called_once_with(
            lat=city_def.latitude,
            lon=city_def.longitude,
            fallback=city_def.default_weather,
        )

    def test_failure_sets_substitute(
        self, cache: WeatherCache, fallback_result: WeatherResult, city_def: CityDef
    ) -> None:
        client = MagicMock()
        client.fetch_weather.return_value = fallback_result

        entry = fetch_and_cache(cache, client, "city_0", city_def)

        assert entry.state == CacheState.SUBSTITUTE
        assert entry.result == fallback_result


# ---------------------------------------------------------------------------
# Tests: Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_set_get(self, cache: WeatherCache) -> None:
        """Concurrent set_live and get should not corrupt state."""
        results = []

        def writer() -> None:
            for i in range(100):
                result = WeatherResult(
                    state=WeatherState.RAIN,
                    temperature=float(i),
                    icon_code="10d",
                    description="rain",
                    weather_id=500,
                )
                cache.set_live("city_0", result)

        def reader() -> None:
            for _ in range(100):
                entry = cache.get("city_0")
                results.append(entry)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No exceptions raised, all entries have valid state
        for entry in results:
            assert entry.state in (CacheState.UNKNOWN, CacheState.LIVE)
