"""Save / load — JSON persistence of Run state (T.14).

This is the **file-I/O layer** over the (de)serialization contract that already
lives on the model dataclasses (`Run.to_dict` / `Run.from_dict`). It adds:

- atomic writes (temp file + ``os.replace``) so a crash mid-write never leaves a
  half-written, unloadable save;
- a ``schema_version`` gate that refuses files written by a newer build
  (``UnsupportedSchemaError``) and rejects malformed/invalid ones
  (``CorruptSaveError``);
- a platform-appropriate ``default_save_dir()`` helper for the future UI.

Core functions take an **explicit path** — they are headless and testable. The
``Run`` (de)serialization contract is *not* re-implemented here; see
``docs/live/systems/save.md``.

Invariants: V.1 (no Flet import — only json/os/pathlib), and the round-trip
identity guarded in ``tests/game/test_save.py``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from src.game.models import Run

#: Schema version this build writes and is able to read. A loaded save whose
#: ``schema_version`` exceeds this was written by a newer build and is refused
#: (``UnsupportedSchemaError``); older/equal versions load via the ``.get``
#: back-compat defaults in ``Run.from_dict``. Bump only for a breaking change
#: that a ``.get`` default cannot absorb — the migration hook is in ``load_run``,
#: just before ``Run.from_dict``.
CURRENT_SCHEMA_VERSION = 1

_SAVE_DIR_NAME = "tempest-fauna-trail"


class SaveError(Exception):
    """Base class for all save/load failures raised by this module."""


class CorruptSaveError(SaveError):
    """The file is not a readable save — bad JSON, missing/mistyped required
    keys, an out-of-range ``schema_version``, or a payload that fails ``Run``
    validation."""


class UnsupportedSchemaError(SaveError):
    """The file's ``schema_version`` is newer than this build can read."""


def save_run(run: Run, path: str | os.PathLike[str]) -> None:
    """Serialize ``run`` to ``path`` as JSON, atomically.

    Writes to a sibling ``<path>.tmp`` (same filesystem), flushes + fsyncs, then
    ``os.replace``s it onto ``path`` — so readers never observe a partial file.
    Creates parent directories as needed. The temp file is removed if
    serialization fails.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(run.to_dict(), handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        # Leave no half-written temp behind on any failure.
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def load_run(path: str | os.PathLike[str]) -> Run:
    """Read a save file and rebuild the ``Run``.

    Raises:
        FileNotFoundError: no file at ``path`` (propagated unwrapped so callers
            can cleanly distinguish "no save yet").
        UnsupportedSchemaError: ``schema_version`` newer than this build reads.
        CorruptSaveError: bad JSON, bad/missing ``schema_version``, missing or
            mistyped required keys, or a payload that fails ``Run`` validation.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")  # FileNotFoundError propagates.

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CorruptSaveError(f"{path}: not valid JSON ({exc})") from exc

    if not isinstance(payload, dict):
        raise CorruptSaveError(f"{path}: top-level JSON is not an object.")

    version = payload.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise CorruptSaveError(
            f"{path}: missing or invalid schema_version ({version!r})."
        )
    if version > CURRENT_SCHEMA_VERSION:
        raise UnsupportedSchemaError(
            f"{path}: schema_version {version} is newer than this build "
            f"supports (max {CURRENT_SCHEMA_VERSION})."
        )

    # Migration hook would slot in here (version < CURRENT_SCHEMA_VERSION):
    # transform `payload` upward before from_dict. None needed at v1.

    try:
        return Run.from_dict(payload)
    except (KeyError, ValueError, TypeError) as exc:
        raise CorruptSaveError(f"{path}: could not rebuild Run ({exc})") from exc


def default_save_dir() -> Path:
    """Return the platform-appropriate save directory for the game.

    Does **not** create the directory — creation happens lazily on
    :func:`save_run`. Resolution:

    - Windows: ``%APPDATA%\\tempest-fauna-trail\\saves``
    - macOS:   ``~/Library/Application Support/tempest-fauna-trail/saves``
    - Linux/other: ``$XDG_DATA_HOME/tempest-fauna-trail/saves`` (falling back to
      ``~/.local/share/...``)
    """
    if os.name == "nt":
        base = os.environ.get("APPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Roaming"
    elif sys_platform_is_darwin():
        root = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_DATA_HOME")
        root = Path(base) if base else Path.home() / ".local" / "share"
    return (root / _SAVE_DIR_NAME / "saves").resolve()


def sys_platform_is_darwin() -> bool:
    """macOS check, isolated so it stays trivially mockable in tests."""
    import sys

    return sys.platform == "darwin"
