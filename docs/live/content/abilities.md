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

## Ability descriptions (T.34)

A parallel registry `ABILITY_META: dict[str, AbilityMeta]` (in `registries.py`)
gives each roster ability id a tooltip. `AbilityMeta(name, kind, blurb, terms,
clauses, tags)` is presentation metadata; `ability_text.render(meta, source) ->
RenderedAbility(name, text, formula, tags)` is **pure** (no Flet/I-O, extends
V.1) and reads live numbers via `source.stat(name)`. The same call serves both
contexts — a base `Champion`/`Enemy` (roster sheet, via the `.stat()` field
adapters) and a live `Piece` (combat, with modifiers; **bosses always via the
compiled `Piece`**). `render_for(id, source)` is the dict-lookup convenience.

**Source-of-truth B (V.38):** a handler's headline damage/heal constant lives
**once** in a `ScalingTerm` the handler reads via `term.eval(source)` — the
tooltip renders the same object, so tooltip and combat numbers cannot drift.
`ScalingTerm.eval` delegates to the engine's `_eval_scaling`, keeping
`resolve_combat` byte-identical (V.2/V.14). Secondary/structural constants
(execute multipliers, splash %, %-max-HP heals, summon fractions) are **Tier-B**:
hoisted to a named module constant and described in a `Clause`, not a term.
Caveat: `max_hp`/`hp` are `Piece` attributes, **not** `base_stats` keys, so they
can't be `ScalingTerm` scaling expressions (`stat("max_hp")` is 0) — %-of-max-HP
outlets stay inline + clause. `max()`-of-two-stats outlets likewise stay inline.

**Tick → seconds (V.39):** `TICKS_PER_SECOND = 100` in `ability_text.py` is the
single source for the `100 ticks = 1 second` display convention. Mechanics stay
ticks-only; only `ability_text.render` (and `ui/`, which imports the constant
from here) converts. A coverage guard + golden formula snapshot
(`tests/game/ability_formulas.snapshot.json`) pin every rendered id; regenerate
with `UPDATE_ABILITY_SNAPSHOT=1 uv run pytest tests/game/test_ability_text.py`.

Meta coverage spans **all 276 roster ability ids** (120 champion T.34a + 120
enemy T.34b + 36 boss T.34c — all done). `tools/export_roster.py` serializes the
champion/enemy (and optional boss) rosters with rendered descriptions to JSON.

## File map

| Concern | Symbol |
|---|---|
| Champion kits | `abilities/champions.py` |
| Enemy kits | `abilities/enemies.py` |
| Boss kits (2-phase) | `abilities/bosses.py` |
| Shared/declarative | `abilities/reference.py`, `registries.register_active_simple` |
| Registries + decorators | `registries.py` (`ABILITY_REGISTRY`, `PASSIVE_REGISTRY`, `@register_active`/`@register_passive`) |
| Ability descriptions (T.34) | `registries.py` (`ABILITY_META`, `ScalingTerm`, `Clause`, `AbilityMeta`), `ability_text.py` (`render`, `render_for`, `TICKS_PER_SECOND`) |
| id source on the model | `content.py` (`active_ability`/`passive_ability`) |
