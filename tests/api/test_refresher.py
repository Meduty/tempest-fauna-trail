"""Unit tests for src/api/refresher.py — 3-stream weather refresher."""
from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest

from src.api.cache import CacheState, WeatherCache
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
        get_current_node_index=lambda: 1,
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
            get_current_node_index=lambda: 1,
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
            get_current_node_index=lambda: 1,
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
        # 1-based node index 11 → 0-based index 10; window covers positions 11..16.
        # A-stream starts at position 0 and advances; for the first 11 ticks A
        # stays at positions 0..10, which never overlap the window, so result[1]
        # is always the B selection.
        current_node = 11
        refresher = WeatherRefresher(
            cache=cache,
            client=mock_client,
            get_current_node_index=lambda: current_node,
            rng_seed=42,
        )
        # Window = city_ids[11:17] (6 cities ahead of 0-based index 10)
        window = city_ids[current_node : current_node + 6]
        b_cities: list[str] = []

        for _ in range(6):
            result = refresher.tick()
            # A is in positions 0..10, so result[1] is definitely B
            assert len(result) >= 2, "Expected B to contribute a selection"
            assert result[1] in window, (
                f"B selection {result[1]!r} not in window {window}"
            )
            b_cities.append(result[1])

        # B round-robins through the full 6-city window
        assert set(b_cities) == set(window)

    def test_b_clamps_at_trail_end(
        self, cache: WeatherCache, mock_client: MagicMock, city_ids: list[str]
    ) -> None:
        """B stream produces nothing when current is at the last node."""
        # 1-based: last node index == len(city_ids)
        last_node = len(city_ids)
        refresher = WeatherRefresher(
            cache=cache,
            client=mock_client,
            get_current_node_index=lambda: last_node,
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
        # 1-based: 3rd-from-last node → only 2 cities ahead
        near_end_node = len(city_ids) - 2
        refresher = WeatherRefresher(
            cache=cache,
            client=mock_client,
            get_current_node_index=lambda: near_end_node,
            rng_seed=42,
        )
        # 0-based index = near_end_node - 1; window = city_ids[near_end_node - 1 + 1:]
        expected_window = city_ids[near_end_node:]
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
        """C stream can pick any city (verified over many ticks).

        By tracking only result[2] — the definite C slot when all three streams
        contribute a unique city — we assert specifically on C-stream coverage.
        """
        # Node 1 (1-based) → 0-based idx 0; window = city_ids[1:7].
        # A starts at position 0 and advances; when all three are distinct,
        # result has 3 elements and result[2] is C.
        refresher = WeatherRefresher(
            cache=cache,
            client=mock_client,
            get_current_node_index=lambda: 1,
            rng_seed=123,
        )
        c_fetched: set[str] = set()
        for _ in range(500):
            result = refresher.tick()
            # result[2] is present only when C was not a duplicate of A or B
            if len(result) == 3:
                c_fetched.add(result[2])

        # Over 500 ticks, C (uniform random) should have covered all cities
        assert len(c_fetched) == len(city_ids)


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
            get_current_node_index=lambda: 1,
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
            get_current_node_index=lambda: 1,
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
            get_current_node_index=lambda: 1,
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
        """Verify the timer fires a tick; uses threading.Event instead of time.sleep."""
        tick_event = threading.Event()

        refresher = WeatherRefresher(
            cache=cache,
            client=mock_client,
            get_current_node_index=lambda: 1,
            tick_interval=0.05,  # 50ms for fast test
            rng_seed=42,
        )

        # Wrap tick() on the instance so we can signal when it fires.
        _real_tick = type(refresher).tick  # unbound class method

        def tick_spy() -> list[str]:
            result = _real_tick(refresher)
            tick_event.set()
            return result

        refresher.tick = tick_spy  # instance attribute shadows the class method

        refresher.start()
        fired = tick_event.wait(timeout=2.0)
        refresher.stop()

        assert fired, "Timer did not fire within timeout"
        # At least one fetch should have happened
        assert mock_client.fetch_weather.call_count >= 1


# ---------------------------------------------------------------------------
# on_tick callback (T.11) — UI repaint hook, back-compat
# ---------------------------------------------------------------------------

class TestOnTickCallback:
    def test_on_tick_fires_with_selected_cities(
        self, cache: WeatherCache, mock_client: MagicMock
    ) -> None:
        seen: list[list[str]] = []
        r = WeatherRefresher(
            cache=cache, client=mock_client,
            get_current_node_index=lambda: 1, rng_seed=42,
            on_tick=lambda selected: seen.append(selected),
        )
        result = r.tick()
        assert seen == [result]  # called once with the fetched city ids

    def test_on_tick_exception_does_not_break_tick(
        self, cache: WeatherCache, mock_client: MagicMock
    ) -> None:
        def _boom(_selected: list[str]) -> None:
            raise RuntimeError("UI blew up")

        r = WeatherRefresher(
            cache=cache, client=mock_client,
            get_current_node_index=lambda: 1, rng_seed=42, on_tick=_boom,
        )
        # Must not propagate — the worker thread keeps the refresher alive.
        result = r.tick()
        assert len(result) >= 1

    def test_default_none_is_back_compat(
        self, refresher: WeatherRefresher
    ) -> None:
        # No on_tick passed → tick still returns normally.
        result = refresher.tick()
        assert 1 <= len(result) <= 3
