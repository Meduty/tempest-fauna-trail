"""OpenWeather API client — fetch current weather, parse to WeatherState.

Synchronous client. Callers must invoke from a worker thread (V.4).
Never raises on fetch failures — returns a fallback result (V.3).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import requests

from src.game.models import WeatherState

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
_TIMEOUT = 10  # seconds
_FALLBACK_WEATHER = {
    WeatherState.CLEAR: ("01d", 800),
    WeatherState.CLOUDY: ("03d", 803),
    WeatherState.MIST: ("50d", 701),
    WeatherState.RAIN: ("10d", 500),
    WeatherState.SNOW: ("13d", 600),
    WeatherState.THUNDER: ("11d", 200),
}


@dataclass(frozen=True)
class WeatherResult:
    """Parsed weather response for a single location."""

    state: WeatherState
    temperature: float  # Celsius
    icon_code: str  # e.g. "10d"
    description: str  # e.g. "light rain"
    weather_id: int  # raw OW weather condition id
    is_fallback: bool = False  # True when the result came from a failed fetch
    error: str | None = None  # Human-readable error reason when is_fallback is True


def _fallback_result(fallback: WeatherState, error: str) -> WeatherResult:
    """Build a safe fallback result when the API call fails."""
    icon_code, weather_id = _FALLBACK_WEATHER[fallback]
    return WeatherResult(
        state=fallback,
        temperature=0.0,
        icon_code=icon_code,
        description="unknown",
        weather_id=weather_id,
        is_fallback=True,
        error=error,
    )


class WeatherClient:
    """Synchronous OpenWeather API client.

    Instantiate with an explicit API key or let it read from the
    OPENWEATHER_API_KEY environment variable.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("OPENWEATHER_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "OpenWeather API key required — pass api_key or set "
                "OPENWEATHER_API_KEY environment variable."
            )

    def fetch_weather(
        self,
        lat: float,
        lon: float,
        *,
        fallback: WeatherState = WeatherState.CLEAR,
    ) -> WeatherResult:
        """Fetch current weather for coordinates.

        Returns parsed WeatherResult on success.
        Returns a fallback WeatherResult on any failure (V.3).
        Never raises.
        """
        try:
            resp = requests.get(
                _BASE_URL,
                params={
                    "lat": lat,
                    "lon": lon,
                    "appid": self._api_key,
                    "units": "metric",
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()

            data = resp.json()
            weather_entry = data["weather"][0]
            weather_id: int = weather_entry["id"]

            return WeatherResult(
                state=WeatherState.from_openweather_id(weather_id),
                temperature=float(data["main"]["temp"]),
                icon_code=str(weather_entry["icon"]),
                description=str(weather_entry["description"]),
                weather_id=weather_id,
            )

        except Exception as exc:  # noqa: BLE001
            logger.warning("Weather fetch failed (lat=%.2f, lon=%.2f): %s", lat, lon, exc)
            return _fallback_result(fallback, error=str(exc))
