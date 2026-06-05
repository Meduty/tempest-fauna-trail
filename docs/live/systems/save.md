# Save / serialization

> **Status: LIVING** — must match `Run`/`BattleResult` (de)serialization in `src/game/models.py`. Audited by `/check`.
> **Scope:** how game state round-trips to/from JSON, and the back-compat rules. **Reconciled:** 2026-06-05.
>
> Citations by symbol, not line. A dedicated game/save.py (file I/O) is planned (T.14); **today the (de)serialization contract lives on the model dataclasses** — this doc tracks that contract.

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
- New optional fields follow the same pattern: `payload.get(key, default)`,
  never a hard `payload[key]`, so old saves still load.

`schema_version` exists to gate breaking migrations; bump it when a change can't
be handled by a `.get` default.

## Invariant

- Round-trip identity: `from_dict(x.to_dict()) == x` for current data, and
  old-shaped payloads load without error (back-compat). `/check` and
  `tests/game/test_models.py` guard this.

## File map

| Concern | Symbol |
|---|---|
| Root state + nesting | `models.py::Run.to_dict` / `Run.from_dict` |
| Battle records | `models.py::BattleResult.to_dict` / `from_dict` (`piece_max_hp` optional) |
| Per-entity | `Champion` / `Enemy` / `Node` / `BattleEvent` `.to_dict`/`.from_dict` |
| Legacy key read | `Run.from_dict` `gold`→`amber` (B.4) |
| Planned file I/O | game/save.py (T.14, not yet created) |
