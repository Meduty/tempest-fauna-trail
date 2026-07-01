# Save / serialization

> **Status: LIVING** — must match `Run`/`BattleResult` (de)serialization in `src/game/models.py` + the file-I/O layer in `src/game/save.py`. Audited by `/check`.
> **Scope:** how game state round-trips to/from JSON, the back-compat rules, and the file read/write contract. **Reconciled:** 2026-07-01.
>
> Citations by symbol, not line. The (de)serialization contract lives on the **model dataclasses**; the **file I/O** (atomic write, schema gate, typed errors) lives in `game/save.py` (T.14).

## The model is the schema

Every persisted dataclass has `to_dict() -> dict` and `@classmethod from_dict(payload)`:
`Run`, `Champion`, `Enemy`, `Node`, `BattleEvent`, `BattleResult`. `Run` is the
root — it holds all game state and serializes its nested objects.

`Run` fields (root): `run_id`, `schema_version` (≥ 1, validated), `seed`, the
route `Node`s, the champion roster, `amber` (economy), `battle_log`
(`list[BattleResult]`), status. `Run.to_dict` nests each child's `to_dict`;
`from_dict` rebuilds them.

## Back-compat rules (the part that bites)

`from_dict` must tolerate older payloads. Current rules:

- **`amber` ← `gold`** — old saves used `"gold"`; `Run.from_dict` reads the
  legacy `gold` key when `amber` is absent (B.4).
- **`BattleResult.piece_max_hp`** — added later; `from_dict` defaults it to `{}`
  for pre-field saves (the combat-log HP trace is just empty for them). See
  [combat.md](combat.md).
- **`Node.weather_state` / `Node.weather_locked`** (T.39) — `Node.from_dict`
  reads `payload.get("weather_state", "unknown")` (→ `NodeWeatherState.UNKNOWN`)
  and `payload.get("weather_locked", False)`, so pre-T.39 saves load with no
  `schema_version` bump. See [weather_api.md](weather_api.md).
- New optional fields follow the same pattern: `payload.get(key, default)`,
  never a hard `payload[key]`, so old saves still load. The *required* keys
  (`schema_version`, and whatever `Run.from_dict` reads unconditionally) are the
  only ones that can raise `CorruptSaveError`.

`schema_version` exists to gate breaking migrations; bump it when a change can't
be handled by a `.get` default.

## File I/O (`game/save.py`, T.14)

The disk layer over the model contract. Imports only `json`/`os`/`pathlib` — no
Flet (V.1).

- **`CURRENT_SCHEMA_VERSION`** (`= 1`) — the single source for the version this
  build writes/reads (was hardcoded per-Run before T.14).
- **`save_run(run, path)`** — `run.to_dict()` → JSON, **atomic**: writes
  `<path>.tmp`, `flush`+`fsync`, then `os.replace` onto `path`; auto-creates
  parent dirs; removes the temp on any failure. Readers never see a partial file.
- **`load_run(path)`** — reads + gates on `schema_version` (see errors below),
  then `Run.from_dict`. The migration hook sits between the gate and `from_dict`.
- **`default_save_dir()`** — platform app-data dir (`%APPDATA%` / macOS
  `Application Support` / `$XDG_DATA_HOME`) `…/tempest-fauna-trail/saves`. Helper
  only; core fns take an explicit path. Does **not** create the dir (save does).
- **Errors:** `SaveError` (base) → `CorruptSaveError` (bad JSON, missing/mistyped
  required keys incl. `schema_version`, or a payload that fails `Run`
  validation — `from_dict`'s `ValueError`/`KeyError`/`TypeError` are wrapped),
  `UnsupportedSchemaError` (`schema_version` > `CURRENT_SCHEMA_VERSION`).
  `FileNotFoundError` is **not** wrapped — callers branch on "no save yet".

## Invariant

- Round-trip identity: `from_dict(x.to_dict()) == x` for current data, and
  old-shaped payloads load without error (back-compat). `/check`,
  `tests/game/test_models.py`, and `tests/game/test_save.py` (through disk)
  guard this.
- File safety: `save_run` is atomic (temp + `os.replace`); `load_run` never
  returns a `Run` from a future-schema or invalid file — it raises a typed
  `SaveError`. (V.36)

## File map

| Concern | Symbol |
|---|---|
| Root state + nesting | `models.py::Run.to_dict` / `Run.from_dict` |
| Battle records | `models.py::BattleResult.to_dict` / `from_dict` (`piece_max_hp` optional) |
| Per-entity | `Champion` / `Enemy` / `Node` / `BattleEvent` `.to_dict`/`.from_dict` |
| Legacy key read | `Run.from_dict` `gold`→`amber` (B.4) |
| File read/write | `save.py::save_run` / `load_run` (atomic, schema-gated) |
| Save version constant | `save.py::CURRENT_SCHEMA_VERSION` |
| Default save location | `save.py::default_save_dir` |
| Typed errors | `save.py::SaveError` / `CorruptSaveError` / `UnsupportedSchemaError` |
