# Abilities & passives — id resolution

> **Status: LIVING** — must match `src/game/abilities/` + `registries.py`. Audited by `/check`.
> **Scope:** how roster ability/passive ids resolve to handlers (the T.30 fix). **Reconciled:** 2026-06-05.
>
> 🔶 **STUB** — anchors only; prose TBD. Catalog (frozen): `docs/design/content/ABILITY_CATALOG_CHAMPIONS.md`, `ABILITY_CATALOG_ENEMIES.md`.

## Where it lives
- `abilities/champions.py`, `abilities/enemies.py`, `abilities/bosses.py` — `@register_*` handlers.
- `registries.py` — `ABILITY_REGISTRY`/`PASSIVE_REGISTRY`; ids are prefixed (`champ_x.active`).
- CI guard: every roster ability-id must resolve to a handler.
