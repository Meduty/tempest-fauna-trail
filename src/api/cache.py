"""Per-city weather cache for the 50-node route.

Thread-safe. Holds one of three states per city: UNKNOWN, LIVE, SUBSTITUTE.
The engine never reads None — callers always get a CacheEntry (V.9).

No Flet imports. No game-state writes (V.10).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum

from src.api.weather import WeatherClient, WeatherResult
from src.game.route import CityDef


class CacheState(str, Enum):
    """Possible states of a per-city cache slot."""

    UNKNOWN = "unknown"
    LIVE = "live"
    SUBSTITUTE = "substitute"


@dataclass
class CacheEntry:
    """Snapshot of a single city's cached weather."""

    city_id: str
    state: CacheState
    result: WeatherResult | None = None  # None only when UNKNOWN
    fetched_at: float | None = None  # None only when UNKNOWN


class WeatherCache:
    """Thread-safe per-city weather cache.

    Initialize with ordered city IDs; all start as UNKNOWN.
    """

    def __init__(self, city_ids: list[str]) -> None:
        self._city_ids = list(city_ids)
        self._lock = threading.Lock()
        self._entries: dict[str, CacheEntry] = {
            cid: CacheEntry(city_id=cid, state=CacheState.UNKNOWN)
            for cid in self._city_ids
        }

    @property
    def city_ids(self) -> list[str]:
        """Ordered list of city IDs managed by this cache."""
        return list(self._city_ids)

    def get(self, city_id: str) -> CacheEntry:
        """Return current cache entry for a city. Thread-safe."""
        with self._lock:
            entry = self._entries[city_id]
            # Return a copy to avoid races on mutable reads
            return CacheEntry(
                city_id=entry.city_id,
                state=entry.state,
                result=entry.result,
                fetched_at=entry.fetched_at,
            )

    def set_live(self, city_id: str, result: WeatherResult) -> None:
        """Mark city as LIVE with fresh weather data."""
        now = time.time()
        with self._lock:
            entry = self._entries[city_id]
            entry.state = CacheState.LIVE
            entry.result = result
            entry.fetched_at = now

    def set_substitute(self, city_id: str, result: WeatherResult) -> None:
        """Mark city as SUBSTITUTE (fetch failed, holding default weather)."""
        now = time.time()
        with self._lock:
            entry = self._entries[city_id]
            entry.state = CacheState.SUBSTITUTE
            entry.result = result
            entry.fetched_at = now

    def all_entries(self) -> dict[str, CacheEntry]:
        """Snapshot of all cache entries. Thread-safe."""
        with self._lock:
            return {
                cid: CacheEntry(
                    city_id=e.city_id,
                    state=e.state,
                    result=e.result,
                    fetched_at=e.fetched_at,
                )
                for cid, e in self._entries.items()
            }


def fetch_and_cache(
    cache: WeatherCache,
    client: WeatherClient,
    city_id: str,
    city_def: CityDef,
) -> CacheEntry:
    """Fetch weather for a city and update cache. Returns the new entry.

    On success → set_live. On failure (is_fallback) → set_substitute.
    Synchronous — caller must be on a worker thread (V.4).
    """
    result = client.fetch_weather(
        lat=city_def.latitude,
        lon=city_def.longitude,
        fallback=city_def.default_weather,
    )
    if result.is_fallback:
        cache.set_substitute(city_id, result)
    else:
        cache.set_live(city_id, result)
    return cache.get(city_id)
