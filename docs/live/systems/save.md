# Save / serialization

> **Status: LIVING** — must match `Run`/`BattleResult` (de)serialization in `src/game/models.py`. Audited by `/check`.
> **Scope:** how game state round-trips to/from JSON. **Reconciled:** 2026-06-05.
>
> 🔶 **STUB** — anchors only; prose TBD. A dedicated save.py module is planned (T.14); today serialization lives on the models. Note: `BattleResult.piece_max_hp` is back-compat optional (pre-field saves → {}).

## Where it lives
- `models.py` — `Run.to_dict`/`from_dict`, `BattleResult.to_dict`/`from_dict`, gold→amber back-compat read (B.4).
