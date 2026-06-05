# Abilities & passives — id resolution

> **Status: LIVING** — must match `src/game/abilities/` + `registries.py`. Audited by `/check`.
> **Scope:** how a roster ability/passive id becomes a runtime handler, and the resolution guarantee (T.30). **Reconciled:** 2026-06-05.
>
> Citations by symbol, not line. The *kits* (what each ability does, by lore) live in the frozen `docs/design/content/ABILITY_CATALOG_CHAMPIONS.md` / `ABILITY_CATALOG_ENEMIES.md`. The framework they plug into is [../systems/effects.md](../systems/effects.md).

## Id convention

A `Champion`/`Enemy` carries `active_ability` / `passive_ability` **string ids**,
authored as prefixed ids in `content.py` (`active_ability = f"{id}.active"`,
e.g. `champ_torrent_heron.active`). Handlers register under those exact ids — the
T.30 fix was aligning the two (previously short ids vs prefixed ids meant 0/240
resolved and every piece ran the generic fallback).

## Registration

Handlers live in `abilities/champions.py`, `abilities/enemies.py`,
`abilities/bosses.py` (+ `abilities/reference.py` for shared/example kits) and
register at import via decorators from `registries.py`:

- `@register_active(ability_id)` → `ABILITY_REGISTRY`
- `@register_passive(passive_id)` → `PASSIVE_REGISTRY`
- `register_active_simple(id, SimpleActive(...))` — declarative single-target
  spec abilities (no hand-written handler).

`compile_loadout` imports the `abilities` package, which triggers every
decorator, populating the registries before any combat.

## Counts (verified; `/check` re-checks)

- `len(ABILITY_REGISTRY)` = **135**, `len(PASSIVE_REGISTRY)` = **147** (shared
  handlers serve multiple roster ids; the guarantee below is per-roster-id, not
  per-handler).

## The resolution guarantee (CI-guarded)

Every ability/passive id referenced by the roster must resolve to a registered
handler — enforced by a guard test (SPEC §V.15/§V.17). An unregistered id is a
build failure, not a silent generic-fallback. The loop's unregistered-ability
path (`engine._resolve_action`) is only a defensive fallback, not the norm.

## File map

| Concern | Symbol |
|---|---|
| Champion kits | `abilities/champions.py` |
| Enemy kits | `abilities/enemies.py` |
| Boss kits (2-phase) | `abilities/bosses.py` |
| Shared/declarative | `abilities/reference.py`, `registries.register_active_simple` |
| Registries + decorators | `registries.py` (`ABILITY_REGISTRY`, `PASSIVE_REGISTRY`, `@register_active`/`@register_passive`) |
| id source on the model | `content.py` (`active_ability`/`passive_ability`) |
