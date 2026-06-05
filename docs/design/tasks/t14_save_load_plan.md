# T.14 Plan — Save / Load (JSON Run persistence)

> **Status:** plan — ready for review. (§T.14 status flip ❌ Not started → 📋 Plan / build.)
> **Depends:** T.1 (✅ done — model (de)serialization already lives on the dataclasses). No unbuilt deps. T.9 menu / T.10 run-start (📋, unbuilt) are *consumers* of this layer, not blockers — that's why scope stays minimal (no slot-UI here).
> **Resolves:** SPEC §T.14.
> **Design source of truth:** [docs/live/systems/save.md](../../live/systems/save.md) (LIVING — the current (de)serialization contract), SPEC §V.1, §B.4. No frozen design doc exists for save (it was always "the model is the schema").
> **What this plan adds beyond those:** the **file-I/O layer** the living doc says is "planned (T.14), not yet created" — `game/save.py`: atomic write, schema-version gate, typed errors, default-dir helper. The (de)serialization contract itself is **already built and tested**; this task does not re-implement it.

## 1. Scope

**In scope (`src/game/save.py` + tests):**
- `save_run(run: Run, path: str | Path) -> None` — serialize `run.to_dict()` → JSON, **atomic** write (temp file + `os.replace`), create parent dir if missing.
- `load_run(path: str | Path) -> Run` — read JSON → `Run.from_dict`, with schema-version gate + typed errors.
- `CURRENT_SCHEMA_VERSION: int` constant (= `1`) — first central home for the value (today it's hardcoded at every test Run construction).
- `default_save_dir() -> Path` — platform-appropriate app-data dir (`~/.local/share/tempest-fauna-trail/saves` style via a small resolver; no new dep). Helper only; core fns take an **explicit path**.
- Typed errors: `SaveError(Exception)` base; `CorruptSaveError(SaveError)` (bad JSON / missing required keys); `UnsupportedSchemaError(SaveError)` (file `schema_version` > `CURRENT_SCHEMA_VERSION`).
- Tests: `tests/game/test_save.py`.

**Out of scope (and why):**
- Slot management (named slots, `list_saves`, `delete_save`, autosave) → **T.9** when the menu actually consumes it. Building it now = speculative API with no caller (per user decision: minimal path API).
- `Run` factory / `schema_version` assignment at run creation → **T.10** (run_init). This task only *reads/writes* the value, it doesn't decide who stamps it.
- UI "Load game" wiring → **T.9 / T.15**.
- Any change to `to_dict`/`from_dict` shape → already correct; T.14 must not touch the contract (only consume it).
- Migration *logic* for v2+ → none exists yet (we're at v1). This task lays the **gate + hook point**, not a migration.

## 2. The gap today

| piece | where | state |
|---|---|---|
| `Run.to_dict` / `from_dict` (+ all nested) | `models.py:594` / `:616` | ✅ built |
| `gold`→`amber` back-compat | `models.py:636` | ✅ (B.4) |
| `BattleResult.piece_max_hp` optional default | `models.py:456`+ | ✅ |
| schema_version validate (`>= 1`) | `models.py:504` | ✅ (lower bound only — no upper/“future version” gate) |
| Round-trip test | `tests/game/test_models.py:116` | ✅ |
| **File I/O (`game/save.py`)** | — | ❌ does not exist |
| `CURRENT_SCHEMA_VERSION` constant | — | ❌ (value `1` hardcoded in tests only) |
| Atomic write / corrupt-file handling / typed errors | — | ❌ |
| Default save-dir resolver | — | ❌ |

## 3. Architecture

`game/save.py` is a thin I/O wrapper over the existing model contract. Data flow:

```
save_run(run, path):  run.to_dict() ──json.dumps──► <path>.tmp ──os.replace──► <path>
load_run(path):       <path> ──json.loads──► Run.from_dict(payload) ──► Run
```

- **Where it plugs in:** consumes `Run.to_dict`/`Run.from_dict` (`models.py:594`/`:616`) only. Zero new coupling into combat/economy. Future `Champion.items` (T.29) / `Run.active_augments` (T.31) ride for free — they land as new dataclass fields with `.get(key, default)` back-compat, exactly as save.md mandates; save.py needs no change when they're added.
- **V.1 compliance:** `save.py` imports `json`, `os`, `pathlib` — **no Flet**. The invariant bans only Flet imports; file I/O in `game/` is sanctioned (SPEC §T.14 names the module `game/save.py`). CLAUDE.md's looser "no I/O in game logic" phrasing yields to SPEC here — note this conflict in the journal.
- **Atomic write:** write to `path.with_suffix(path.suffix + ".tmp")`, `flush`+`fsync`, then `os.replace(tmp, path)` (atomic on POSIX + Windows same-filesystem). Prevents a half-written save on crash/power-loss. Clean up tmp on serialization failure.
- **Schema gate (load):** read `payload.get("schema_version")` (never bare subscript); if `None`/not-int → `CorruptSaveError`; if `> CURRENT_SCHEMA_VERSION` → `UnsupportedSchemaError` (a newer build wrote it; we won't silently mis-read); if `< 1` → `CorruptSaveError`. Equal/older → hand to `from_dict` (whose `.get` defaults already absorb older shapes). This is the **hook point** where a future v1→v2 migration slots in, before `from_dict`.
- **Error mapping (load):** `FileNotFoundError` → propagate as-is (callers distinguish "no save" cleanly — do **not** wrap, so T.9 can `except FileNotFoundError`). `json.JSONDecodeError` → wrap in `CorruptSaveError`. **`from_dict` raises plain `ValueError` (its `__post_init__` validators + `_parse_enum`, `models.py:68,75,80,504-528`) and `KeyError`/`TypeError` for missing/mistyped required keys** — catch `(KeyError, ValueError, TypeError)` around the `from_dict` call → wrap in `CorruptSaveError` (chained `from e`). A JSON-valid but semantically-broken save (bad enum string, `tempest_rank=11`, empty route) must surface as `CorruptSaveError`, never a raw `ValueError`.

### 3.1 Determinism / RNG
None — pure I/O, no cadence mechanic, no RNG. (V.2/V.14 untouched.)

## 4. Decisions (resolved with user, overridable)

| # | Decision | Choice | Rationale |
|---|---|---|---|
| D1 | API surface | **Minimal path API** + `default_save_dir()` helper | No slot-UI consumer until T.9; avoid speculative API. |
| D2 | Save location | **Explicit path** in core fns; `default_save_dir()` resolves app-data dir for the future UI | Keeps core headless/testable; gives UI a sane home without a repo-local `saves/`. |
| D3 | `battle_log` persistence | **Persist full** | Preserve the round-trip-identity invariant (save.md) exactly; revisit only if bloat proves real (then needs a §V amendment). |
| D4 | Robustness | **Atomic write + typed errors + schema gate + `CURRENT_SCHEMA_VERSION`** | Prevents corrupt saves; sets the migration seam; lets callers branch on error kind. |

## 5. Authored values
- `CURRENT_SCHEMA_VERSION = 1` (matches every existing `schema_version=1`).
- Default dir name: `tempest-fauna-trail/saves`, file extension `.json` (UTF-8, `indent=2` for human-diffable saves — size is not a constraint per D3).

## 6. Content / roster audit
N/A — no roster/content vocabulary touched. One drift note: `schema_version=1` is currently duplicated across 4 test sites; introducing `CURRENT_SCHEMA_VERSION` gives them a single source (optional follow-up to point tests at it — not required for T.14 to land).

## 7. Open questions
**Resolved here:** all four forks (D1–D4) via `AskUserQuestion`, all "Recommended".
**Still open / deferred:** slot/autosave model (T.9); who stamps `schema_version` at run creation (T.10); first real migration (whenever a breaking field lands — the gate is ready).

## 8. Test plan (`tests/game/test_save.py`)
1. **Round-trip through disk** — build a representative `Run` (roster+bench+route+battle_log+economy fields), `save_run` then `load_run`, assert `loaded.to_dict() == run.to_dict()` (and a field-level spot check). Extends the in-memory round-trip already in `test_models.py`.
2. **Atomic write** — `save_run` to a path, assert no `.tmp` left behind; assert parent dir auto-created.
3. **Atomic overwrite** — save twice (different runs) to same path, assert second fully replaces first (no merge/partial).
4. **`FileNotFoundError`** — `load_run` on a missing path raises `FileNotFoundError` (not wrapped).
5. **`CorruptSaveError` (malformed)** — write garbage / `{}` / valid-JSON-missing-`run_id` → `CorruptSaveError`.
6. **`CorruptSaveError` (semantically invalid)** — write a JSON-valid payload that fails a `Run` validator (`tempest_rank = 11`, or a bad enum string for `status`) → `CorruptSaveError`, **not** raw `ValueError`. Guards the error-wrapping contract.
7. **`UnsupportedSchemaError`** — write a payload with `schema_version = CURRENT_SCHEMA_VERSION + 1` → raises. Also: missing/non-int `schema_version` → `CorruptSaveError`.
8. **Back-compat read** — write a legacy-shaped payload (`"gold"` instead of `"amber"`, no `tempest`/`shop_offers`) directly to disk, `load_run`, assert `amber`/`tempest` defaults applied (guards B.4 survives the file layer).
9. **`default_save_dir()`** — returns an absolute `Path` ending in `tempest-fauna-trail/saves`; does not create the dir as a side effect of *calling* it (creation happens on save).

All tests use `tmp_path`; no real home-dir writes. No RNG/determinism test needed (pure I/O).

## 9. Acceptance criteria
1. `game/save.py` exists exporting `save_run`, `load_run`, `default_save_dir`, `CURRENT_SCHEMA_VERSION`, `SaveError`, `CorruptSaveError`, `UnsupportedSchemaError`. No Flet import (V.1).
2. `save_run` writes atomically (temp + `os.replace`), creates parent dirs, leaves no `.tmp`.
3. `load_run` round-trips a current `Run` byte-for-byte at the `to_dict` level, applies legacy back-compat, and raises `CorruptSaveError` for malformed/semantically-invalid/bad-schema-field payloads (incl. wrapping `from_dict`'s `ValueError`/`KeyError`/`TypeError`) and `UnsupportedSchemaError` for future versions; `FileNotFoundError` passes through unwrapped.
4. `tests/game/test_save.py` (9 cases above) green; full `uv run pytest` green.
5. `docs/live/systems/save.md` updated: "Planned file I/O" row flips to built, file-map + invariant section cite `save.py` symbols. `/check` clean.

## 10. SPEC changes needed (for `/spec`)
- **§T.14 status:** ❌ Not started → ✅ Done (on landing). Files col already correct (`game/save.py`).
- **New §V invariant (proposed):** *V.36 — `game/save.py` is the sole file-I/O home for `Run` persistence: atomic write (temp + `os.replace`), and load gates on `schema_version` (`> CURRENT_SCHEMA_VERSION` → `UnsupportedSchemaError`, `< 1`/missing → `CorruptSaveError`) before `Run.from_dict`. Round-trip identity (`load_run(save_run(x)) ≈ x` at `to_dict` level) holds for current data; older payloads load via `.get` back-compat (B.4). No Flet import (extends V.1).* — confirm wording with user before `/spec`.
- **§B:** none (no bug found).
- **§D:** none.
- **Implementation Order:** standalone — no reorder; slots into the existing chain before T.9 (menu "load game" will depend on it).

## 11. LIVING docs to update
- [docs/live/systems/save.md](../../live/systems/save.md) — flip the "Planned file I/O — game/save.py (T.14, not yet created)" line to a built entry; add `save.py` symbols to the file map (`save_run`/`load_run`/`default_save_dir`/`CURRENT_SCHEMA_VERSION`/error types); note atomic-write + schema-gate in the invariant section. Must match code taxonomy; `/check` must pass.
- ARCHITECTURE.md — add `game/save.py` to the system map (one line under game/ persistence).
- FROZEN docs: none.
