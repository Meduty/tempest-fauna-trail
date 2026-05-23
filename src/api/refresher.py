"""Background 3-stream weather refresher.

Ticks once per minute, picks up to 3 unique cities per tick (A/B/C streams),
fetches each via WeatherClient, updates the shared WeatherCache.

Invariants: V.10 (stateless re: game), V.11 (≤3 calls/min, ≤50 min staleness).
"""
from __future__ import annotations

import logging
import random
import threading
from typing import Callable

from src.api.cache import WeatherCache, fetch_and_cache
from src.api.weather import WeatherClient
from src.game.route import CITIES, CityDef

logger = logging.getLogger(__name__)


class WeatherRefresher:
    """Background 3-stream weather refresher. Ticks once per minute."""

    def __init__(
        self,
        cache: WeatherCache,
        client: WeatherClient,
        get_current_node_index: Callable[[], int],
        *,
        tick_interval: float = 60.0,
        rng_seed: int | None = None,
    ) -> None:
        """
        Args:
            cache: The shared WeatherCache instance.
            client: WeatherClient for API calls.
            get_current_node_index: Callable returning the current 1-based node
                index (matches ``Run.current_node_index``). The refresher
                converts this to a 0-based list offset internally.
            tick_interval: Seconds between ticks (default 60).
            rng_seed: Optional seed for C-stream random (for testing).
        """
        if tick_interval <= 0:
            raise ValueError(f"tick_interval must be > 0, got {tick_interval!r}")

        self._cache = cache
        self._client = client
        self._get_current_node_index = get_current_node_index
        self._tick_interval = tick_interval
        self._rng = random.Random(rng_seed)

        self._city_ids = cache.city_ids
        self._num_cities = len(self._city_ids)

        if self._num_cities == 0:
            raise ValueError("WeatherCache must manage at least one city.")

        # Stream pointers
        self._a_pointer: int = 0  # round-robin over all cities
        self._b_pointer: int = 0  # round-robin within B window

        # Timer state
        self._timer: threading.Timer | None = None
        self._running = False
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        """Whether the refresher timer is active."""
        return self._running

    def start(self) -> None:
        """Start the background tick timer (daemon thread)."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._schedule_next_tick()

    def stop(self) -> None:
        """Stop the refresher. Idempotent."""
        with self._lock:
            self._running = False
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def tick(self) -> list[str]:
        """Execute one tick: pick up to 3 deduped cities, fetch each.

        Returns list of city_ids that were fetched this tick.
        Exposed publicly for testing; normally called by the timer.
        """
        selected: list[str] = []
        seen: set[str] = set()

        # Stream A: full round-robin over all 50 cities
        a_city = self._city_ids[self._a_pointer % self._num_cities]
        self._a_pointer = (self._a_pointer + 1) % self._num_cities
        selected.append(a_city)
        seen.add(a_city)

        # Stream B: round-robin over window [current+1 .. current+6] (0-based list offset).
        # get_current_node_index() returns the 1-based node index; convert to 0-based.
        current_idx0 = self._get_current_node_index() - 1
        window_start = current_idx0 + 1
        window_end = min(window_start + 6, self._num_cities)
        window = self._city_ids[window_start:window_end]

        if window:
            b_city = window[self._b_pointer % len(window)]
            self._b_pointer = (self._b_pointer + 1) % len(window)
            if b_city not in seen:
                selected.append(b_city)
                seen.add(b_city)

        # Stream C: uniform random over all 50 cities
        c_city = self._city_ids[self._rng.randint(0, self._num_cities - 1)]
        if c_city not in seen:
            selected.append(c_city)
            seen.add(c_city)

        # Fetch each selected city
        for city_id in selected:
            city_def = self._get_city_def(city_id)
            try:
                fetch_and_cache(self._cache, self._client, city_id, city_def)
            except Exception:  # noqa: BLE001
                logger.warning("Refresher fetch failed for %s", city_id, exc_info=True)

        return selected

    def _get_city_def(self, city_id: str) -> CityDef:
        """Look up CityDef from the route module."""
        return CITIES[city_id]

    def _schedule_next_tick(self) -> None:
        """Arm the next timer tick."""
        self._timer = threading.Timer(self._tick_interval, self._on_tick)
        self._timer.daemon = True
        self._timer.start()

    def _on_tick(self) -> None:
        """Timer callback: execute tick, then re-arm if still running."""
        try:
            self.tick()
        except Exception:  # noqa: BLE001
            logger.exception("Refresher tick failed unexpectedly")
        finally:
            with self._lock:
                if self._running:
                    self._schedule_next_tick()
