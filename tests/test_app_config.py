"""Tests for src/app_config.py — settings-menu API-key persistence."""
from __future__ import annotations

from pathlib import Path

import pytest

from src import app_config


@pytest.fixture
def cfg_path(tmp_path: Path) -> Path:
    return tmp_path / "config.json"


def test_load_missing_returns_empty(cfg_path: Path) -> None:
    assert app_config.load_config(cfg_path) == {}


def test_save_and_read_key(cfg_path: Path) -> None:
    app_config.save_api_key("abc123", cfg_path)
    assert app_config.stored_api_key(cfg_path) == "abc123"
    assert cfg_path.exists()


def test_save_strips_whitespace(cfg_path: Path) -> None:
    app_config.save_api_key("  spaced  ", cfg_path)
    assert app_config.stored_api_key(cfg_path) == "spaced"


def test_blank_key_clears(cfg_path: Path) -> None:
    app_config.save_api_key("k", cfg_path)
    app_config.save_api_key("   ", cfg_path)
    assert app_config.stored_api_key(cfg_path) is None


def test_env_var_wins_over_file(cfg_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app_config.save_api_key("file_key", cfg_path)
    monkeypatch.setenv("OPENWEATHER_API_KEY", "env_key")
    assert app_config.resolve_api_key(cfg_path) == "env_key"


def test_file_key_used_when_env_absent(
    cfg_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)
    app_config.save_api_key("file_key", cfg_path)
    assert app_config.resolve_api_key(cfg_path) == "file_key"


def test_resolve_none_when_nothing_set(
    cfg_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)
    assert app_config.resolve_api_key(cfg_path) is None


def test_blank_env_falls_through_to_file(
    cfg_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENWEATHER_API_KEY", "   ")
    app_config.save_api_key("file_key", cfg_path)
    assert app_config.resolve_api_key(cfg_path) == "file_key"


def test_save_is_atomic_no_tmp_left(cfg_path: Path) -> None:
    app_config.save_api_key("k", cfg_path)
    leftovers = list(cfg_path.parent.glob("*.tmp"))
    assert leftovers == []


def test_corrupt_file_reads_as_empty(cfg_path: Path) -> None:
    cfg_path.write_text("{not json", encoding="utf-8")
    assert app_config.load_config(cfg_path) == {}
    assert app_config.stored_api_key(cfg_path) is None
