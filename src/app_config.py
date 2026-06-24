"""User app config — the OpenWeather API key (settings-menu persistence).

Flet-free (V.1) file-I/O layer for **non-run** user settings, kept separate from
`game/save.py` (which is the sole home for *`Run`* persistence, V.36). Today it
holds one thing: the OpenWeather API key, settable from the in-app Settings menu so
a player never has to touch `.env`/shell.

Resolution order for the live key (`resolve_api_key`): the `OPENWEATHER_API_KEY`
environment variable **wins** (CI / `.env` / explicit export), then the saved
config file, then `None` (no live weather — the Trail shows `?`, V.66). The key is
**never logged** (V.3); the file lives in the platform user-data dir alongside saves.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

_APP_DIR_NAME = "tempest-fauna-trail"
_CONFIG_FILE = "config.json"
_API_KEY_FIELD = "openweather_api_key"
_ENV_VAR = "OPENWEATHER_API_KEY"


def _app_data_root() -> Path:
    """Platform user-data root (mirrors `save.default_save_dir`'s base)."""
    if os.name == "nt":
        base = os.environ.get("APPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_DATA_HOME")
        root = Path(base) if base else Path.home() / ".local" / "share"
    return root / _APP_DIR_NAME


def default_config_path() -> Path:
    """Path to the user config JSON (sibling of the `saves/` dir). Not created here."""
    return (_app_data_root() / _CONFIG_FILE).resolve()


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Return the saved config dict, or ``{}`` if absent/unreadable (never raises)."""
    p = path or default_config_path()
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_api_key(key: str, path: Path | None = None) -> None:
    """Persist the OpenWeather API key atomically (temp → `os.replace`).

    A blank/whitespace key clears the stored value. Never logs the key (V.3).
    """
    p = path or default_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    config = load_config(p)
    cleaned = key.strip()
    if cleaned:
        config[_API_KEY_FIELD] = cleaned
    else:
        config.pop(_API_KEY_FIELD, None)
    tmp = p.with_suffix(p.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, p)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def stored_api_key(path: Path | None = None) -> str | None:
    """The key saved in the config file (ignoring env), or ``None``."""
    val = load_config(path).get(_API_KEY_FIELD)
    return val if isinstance(val, str) and val.strip() else None


def resolve_api_key(path: Path | None = None) -> str | None:
    """The effective live API key: env var wins, then config file, then ``None``."""
    env = os.environ.get(_ENV_VAR, "").strip()
    if env:
        return env
    return stored_api_key(path)
