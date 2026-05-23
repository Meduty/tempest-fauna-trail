"""Unit tests for src/api/weather.py — WeatherClient.

All tests mock requests.get; no real network calls.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.api.weather import WeatherClient, WeatherResult, _fallback_result
from src.game.models import WeatherState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client() -> WeatherClient:
    """Client with a dummy key — no env var needed."""
    return WeatherClient(api_key="test_key_123")


def _mock_response(status: int = 200, json_data: dict | None = None) -> MagicMock:
    """Build a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data or {}
    if status >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            f"HTTP {status}"
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


_VALID_RESPONSE = {
    "coord": {"lat": 48.86, "lon": 2.35},
    "weather": [
        {"id": 500, "main": "Rain", "description": "light rain", "icon": "10d"}
    ],
    "main": {"temp": 14.5, "feels_like": 12.0, "humidity": 82, "pressure": 1013},
    "name": "Paris",
}


# ---------------------------------------------------------------------------
# Tests: construction
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_explicit_key(self) -> None:
        client = WeatherClient(api_key="my_key")
        assert client._api_key == "my_key"

    def test_env_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENWEATHER_API_KEY", "env_key")
        client = WeatherClient()
        assert client._api_key == "env_key"

    def test_missing_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)
        with pytest.raises(ValueError, match="API key required"):
            WeatherClient()


# ---------------------------------------------------------------------------
# Tests: successful fetch
# ---------------------------------------------------------------------------

class TestSuccessfulFetch:
    @patch("src.api.weather.requests.get")
    def test_returns_correct_result(self, mock_get: MagicMock, client: WeatherClient) -> None:
        mock_get.return_value = _mock_response(200, _VALID_RESPONSE)

        result = client.fetch_weather(48.86, 2.35)

        assert result.state == WeatherState.RAIN
        assert result.temperature == 14.5
        assert result.icon_code == "10d"
        assert result.description == "light rain"
        assert result.weather_id == 500
        assert result.is_fallback is False
        assert result.error is None

    @patch("src.api.weather.requests.get")
    def test_passes_correct_params(self, mock_get: MagicMock, client: WeatherClient) -> None:
        mock_get.return_value = _mock_response(200, _VALID_RESPONSE)

        client.fetch_weather(48.86, 2.35)

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        assert params["lat"] == 48.86
        assert params["lon"] == 2.35
        assert params["appid"] == "test_key_123"
        assert params["units"] == "metric"


# ---------------------------------------------------------------------------
# Tests: failure modes (V.3 — never crashes)
# ---------------------------------------------------------------------------

class TestFailureModes:
    @patch("src.api.weather.requests.get")
    def test_http_error_returns_fallback(self, mock_get: MagicMock, client: WeatherClient) -> None:
        mock_get.return_value = _mock_response(401)

        result = client.fetch_weather(48.86, 2.35, fallback=WeatherState.CLOUDY)

        assert result.state == WeatherState.CLOUDY
        assert result.temperature == 0.0
        assert result.is_fallback is True
        assert result.error is not None

    @patch("src.api.weather.requests.get")
    def test_timeout_returns_fallback(self, mock_get: MagicMock, client: WeatherClient) -> None:
        mock_get.side_effect = requests.exceptions.Timeout("timed out")

        result = client.fetch_weather(0.0, 0.0)

        assert result.state == WeatherState.CLEAR  # default fallback
        assert result.is_fallback is True
        assert "timed out" in result.error

    @patch("src.api.weather.requests.get")
    def test_connection_error_returns_fallback(self, mock_get: MagicMock, client: WeatherClient) -> None:
        mock_get.side_effect = requests.exceptions.ConnectionError("no network")

        result = client.fetch_weather(0.0, 0.0, fallback=WeatherState.SNOW)

        assert result.state == WeatherState.SNOW
        assert result.is_fallback is True
        assert "no network" in result.error

    @patch("src.api.weather.requests.get")
    def test_malformed_json_returns_fallback(self, mock_get: MagicMock, client: WeatherClient) -> None:
        resp = _mock_response(200)
        resp.json.side_effect = ValueError("bad json")
        mock_get.return_value = resp

        result = client.fetch_weather(0.0, 0.0)

        assert result.state == WeatherState.CLEAR
        assert result.is_fallback is True
        assert "bad json" in result.error

    @patch("src.api.weather.requests.get")
    def test_missing_weather_key_returns_fallback(self, mock_get: MagicMock, client: WeatherClient) -> None:
        mock_get.return_value = _mock_response(200, {"main": {"temp": 10}})

        result = client.fetch_weather(0.0, 0.0, fallback=WeatherState.MIST)

        assert result.state == WeatherState.MIST
        assert result.is_fallback is True
        assert result.error is not None


# ---------------------------------------------------------------------------
# Tests: WeatherState mapping coverage
# ---------------------------------------------------------------------------

class TestWeatherStateMapping:
    @pytest.mark.parametrize(
        "weather_id,expected_state",
        [
            (200, WeatherState.THUNDER),
            (210, WeatherState.THUNDER),
            (300, WeatherState.RAIN),
            (500, WeatherState.RAIN),
            (600, WeatherState.SNOW),
            (622, WeatherState.SNOW),
            (701, WeatherState.MIST),
            (741, WeatherState.MIST),
            (800, WeatherState.CLEAR),
            (801, WeatherState.CLOUDY),
            (804, WeatherState.CLOUDY),
        ],
    )
    @patch("src.api.weather.requests.get")
    def test_all_weather_groups(
        self,
        mock_get: MagicMock,
        client: WeatherClient,
        weather_id: int,
        expected_state: WeatherState,
    ) -> None:
        response_data = {
            "weather": [{"id": weather_id, "main": "X", "description": "x", "icon": "01d"}],
            "main": {"temp": 20.0},
        }
        mock_get.return_value = _mock_response(200, response_data)

        result = client.fetch_weather(0.0, 0.0)

        assert result.state == expected_state


# ---------------------------------------------------------------------------
# Tests: fallback helper
# ---------------------------------------------------------------------------

class TestFallbackResult:
    def test_fallback_uses_given_state(self) -> None:
        result = _fallback_result(WeatherState.THUNDER, error="some error")
        assert result.state == WeatherState.THUNDER
        assert result.temperature == 0.0
        assert result.icon_code == "01d"
        assert result.is_fallback is True
        assert result.error == "some error"
        assert isinstance(result, WeatherResult)
