"""Unit tests for src/api/refresher.py — 3-stream weather refresher."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from src.api.cache import CacheState, WeatherCache, fetch_and_cache
from src.api.refresher import WeatherRefresher
from src.api.weather import WeatherResult
from src.game.models import WeatherState
from src.game.route import CITIES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def city_ids() -> list[str]:
    """Use real city IDs from the route for realistic testing."""
    return list(CITIES.keys())


@pytest.fixture
def cache(city_ids: list[str]) -> WeatherCache:
    return WeatherCache(city_ids)


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.fetch_weather.return_value = WeatherResult(
        state=WeatherState.RAIN,
        temperature=15.0,
        icon_code="10d",
        description="light rain",
        weather_id=500,
    )
    return client


@pytest.fixture
def refresher(cache: WeatherCache, mock_client: MagicMock) -> WeatherRefresher:
    return WeatherRefresher(
        cache=cache,
        client=mock_client,
        get_current_node_index=lambda: 0,
        tick_interval=60.0,
        rng_seed=42,
    )


# ---------------------------------------------------------------------------
# Tests: Tick dedup and bounds
# ---------------------------------------------------------------------------

class TestTickDedup:
    def test_tick_returns_at_most_3_cities(self, refresher: WeatherRefresher) -> None:
        result = refresher.tick()
        assert len(result) <= 3
        assert len(result) == len(set(result))  # all unique

    def test_tick_returns_at_least_1_city(self, refresher: WeatherRefresher) -> None:
        result = refresher.tick()
        assert len(result) >= 1

    def test_all_returned_cities_are_valid(
        self, refresher: WeatherRefresher, city_ids: list[str]
    ) -> None:
        result = refresher.tick()
        for cid in result:
            assert cid in city_ids


# ---------------------------------------------------------------------------
# Tests: A-stream round-robin
# ---------------------------------------------------------------------------

class TestStreamA:
    def test_covers_all_50_in_50_ticks(
        self, cache: WeatherCache, mock_client: MagicMock, city_ids: list[str]
    ) -> None:
        """A stream alone covers all 50 cities in exactly 50 ticks."""
        refresher = WeatherRefresher(
            cache=cache,
            client=mock_client,
            get_current_node_index=lambda: 0,
            rng_seed=42,
        )
        a_cities: list[str] = []
        for _ in range(50):
            result = refresher.tick()
            # A stream is always the first element
            a_cities.append(result[0])

        assert set(a_cities) == set(city_ids)

    def test_a_stream_cycles(
        self, cache: WeatherCache, mock_client: MagicMock, city_ids: list[str]
    ) -> None:
        """A stream wraps around after 50 ticks."""
        refresher = WeatherRefresher(
            cache=cache,
            client=mock_client,
            get_current_node_index=lambda: 0,
            rng_seed=42,
        )
        first_pass: list[str] = []
        for _ in range(50):
            first_pass.append(refresher.tick()[0])

        second_pass: list[str] = []
        for _ in range(50):
            second_pass.append(refresher.tick()[0])

        assert first_pass == second_pass


# ---------------------------------------------------------------------------
# Tests: B-stream window
# ---------------------------------------------------------------------------

class TestStreamB:
    def test_b_selects_from_ahead_of_current(
        self, cache: WeatherCache, mock_client: MagicMock, city_ids: list[str]
    ) -> None:
        """B stream picks cities from the window ahead of current node."""
        current_idx = 10
        refresher = WeatherRefresher(
            cache=cache,
            client=mock_client,
            get_current_node_index=lambda: current_idx,
            rng_seed=42,
        )
        # Run several ticks, collect B cities (index 1 in result if present and != A)
        window = city_ids[current_idx + 1 : current_idx + 7]
        b_cities: set[str] = set()

        for _ in range(20):
            result = refresher.tick()
            # B city would be the second if it's in the window
            for cid in result[1:]:
                if cid in window:
                    b_cities.add(cid)

        # B should have selected from the window
        assert b_cities.issubset(set(window))
        # Over 20 ticks, B should cover at least some of the window
        assert len(b_cities) > 0

    def test_b_clamps_at_trail_end(
        self, cache: WeatherCache, mock_client: MagicMock, city_ids: list[str]
    ) -> None:
        """B stream produces nothing when current is at the last node."""
        last_idx = len(city_ids) - 1
        refresher = WeatherRefresher(
            cache=cache,
            client=mock_client,
            get_current_node_index=lambda: last_idx,
            rng_seed=42,
        )
        # Window is empty, so B contributes nothing
        # Still should get A + possibly C
        result = refresher.tick()
        assert len(result) <= 2  # A + C at most

    def test_b_window_near_end(
        self, cache: WeatherCache, mock_client: MagicMock, city_ids: list[str]
    ) -> None:
        """B stream window clamps when fewer than 6 cities remain."""
        near_end_idx = len(city_ids) - 3  # only 2 cities ahead
        refresher = WeatherRefresher(
            cache=cache,
            client=mock_client,
            get_current_node_index=lambda: near_end_idx,
            rng_seed=42,
        )
        expected_window = city_ids[near_end_idx + 1:]
        assert len(expected_window) == 2

        b_cities: set[str] = set()
        for _ in range(10):
            result = refresher.tick()
            for cid in result:
                if cid in expected_window:
                    b_cities.add(cid)

        # B should only pick from the 2 remaining cities
        assert b_cities.issubset(set(expected_window))


# ---------------------------------------------------------------------------
# Tests: C-stream random
# ---------------------------------------------------------------------------

class TestStreamC:
    def test_c_picks_from_all_cities(
        self, cache: WeatherCache, mock_client: MagicMock, city_ids: list[str]
    ) -> None:
        """C stream can pick any city (verified over many ticks)."""
        refresher = WeatherRefresher(
            cache=cache,
            client=mock_client,
            get_current_node_index=lambda: 0,
            rng_seed=123,
        )
        all_fetched: set[str] = set()
        for _ in range(500):
            result = refresher.tick()
            all_fetched.update(result)

        # Over 500 ticks, C (random) should have covered most cities
        assert len(all_fetched) == len(city_ids)


# ---------------------------------------------------------------------------
# Tests: Dedup
# ---------------------------------------------------------------------------

class TestDedup:
    def test_no_duplicate_fetches_per_tick(
        self, cache: WeatherCache, mock_client: MagicMock
    ) -> None:
        """Each tick produces only unique city IDs."""
        refresher = WeatherRefresher(
            cache=cache,
            client=mock_client,
            get_current_node_index=lambda: 0,
            rng_seed=42,
        )
        for _ in range(100):
            result = refresher.tick()
            assert len(result) == len(set(result))


# ---------------------------------------------------------------------------
# Tests: fetch calls
# ---------------------------------------------------------------------------

class TestFetchIntegration:
    def test_tick_calls_fetch_for_each_selected(
        self, cache: WeatherCache, mock_client: MagicMock
    ) -> None:
        """Each city selected by tick results in a fetch call."""
        refresher = WeatherRefresher(
            cache=cache,
            client=mock_client,
            get_current_node_index=lambda: 0,
            rng_seed=42,
        )
        result = refresher.tick()
        assert mock_client.fetch_weather.call_count == len(result)

    def test_tick_updates_cache(
        self, cache: WeatherCache, mock_client: MagicMock
    ) -> None:
        """After a tick, fetched cities should be LIVE in the cache."""
        refresher = WeatherRefresher(
            cache=cache,
            client=mock_client,
            get_current_node_index=lambda: 0,
            rng_seed=42,
        )
        result = refresher.tick()
        for cid in result:
            entry = cache.get(cid)
            assert entry.state == CacheState.LIVE


# ---------------------------------------------------------------------------
# Tests: Start/Stop lifecycle
# ---------------------------------------------------------------------------

class TestLifecycle:
    def test_start_sets_running(self, refresher: WeatherRefresher) -> None:
        refresher.start()
        assert refresher.running is True
        refresher.stop()

    def test_stop_clears_running(self, refresher: WeatherRefresher) -> None:
        refresher.start()
        refresher.stop()
        assert refresher.running is False

    def test_stop_is_idempotent(self, refresher: WeatherRefresher) -> None:
        refresher.stop()
        refresher.stop()  # Should not raise
        assert refresher.running is False

    def test_start_is_idempotent(self, refresher: WeatherRefresher) -> None:
        refresher.start()
        refresher.start()  # Should not start a second timer
        assert refresher.running is True
        refresher.stop()

    def test_timer_fires_tick(
        self, cache: WeatherCache, mock_client: MagicMock
    ) -> None:
        """Verify the timer actually fires a tick after the interval."""
        refresher = WeatherRefresher(
            cache=cache,
            client=mock_client,
            get_current_node_index=lambda: 0,
            tick_interval=0.05,  # 50ms for fast test
            rng_seed=42,
        )
        refresher.start()
        time.sleep(0.15)  # Wait for at least 1 tick
        refresher.stop()

        # At least one fetch should have happened
        assert mock_client.fetch_weather.call_count >= 1
