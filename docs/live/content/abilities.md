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

Each scaling term renders its coefficients as **percentages of the source
stat** so players read what a number scales from: `formula` lines read
`550 = 100 + 150% STR + 150% INT  (STR 1.5×150, INT 1.5×150)` — the trailing
note shows each term's contribution math (`coeff×stat`), not the bare stat
value, so the headline number is fully traceable — and `text` carries a
compact inline suffix beside the rendered total (`...550 magic damage. (100
+150% STR +150% INT)`). Pure-flat / no-scaling terms (buffs) add no suffix.

**Source-of-truth B (V.38 + V.46):** every stat-scaled outlet a handler computes
lives **once** in a `Magnitude` the handler reads via `term.eval(...)` — the
tooltip renders the same object, so tooltip and combat numbers cannot drift.
T.35a promoted `ScalingTerm` into a **closed `Magnitude` family** (modeled on
Unreal GAS's `EGameplayEffectModifierMagnitude`), so there is **no** free inline
handler math anymore — the old "Tier-B stays inline + prose" carve-out is gone.
The four kinds (all in `registries.py`, all pure/RNG-free, all self-describing via
`eval`/`render_formula`/`render_inline`/`render_token`):

| kind | shape | absorbs |
|---|---|---|
| `ScalingTerm` | `base + Σ source.stat·coeff` (delegates to `_eval_scaling`) | linear damage/heal/buff/shred |
| `PctResource` | `getattr(obj, resource)·pct`, `of="self"\|"target"` | %-of-max-HP heals (reads `.max_hp` **directly** — `Piece.stat("max_hp")` is 0, see `effects.compute_stat`) |
| `MaxOfTerm` | `base + max(source.stat(s)…)·coeff` | `max(STR,INT)` outlets (non-linear) |
| `SetByCaller` | `base + caller[key]·coeff` (handler injects the runtime value) | per-stack / runtime-count outlets |

`Clause` carries an optional `{token}` `template` + its own `terms`, so a Tier-B
scaler's prose number is filled from the same `Magnitude` the handler reads (A1) —
e.g. Hierarch's `Grants Armor ({armor})…`. `SummonSpec` holds a summon's statline
as `Magnitude` fractions + flat literals (`eval(owner) -> base_stats`), so summon
stats are introspectable, not inline. **A2 guard (`test_no_orphan_stat_reads`,
V.46):** an AST walk fails the build if any handler reads `.stat()`/`.max_hp`
outside a `Magnitude` on its meta — except ids on `_PROSE_ALLOWLIST` (flat
`max_hp +=` growth: `champ_snowpelt_cub.passive`, `champ_glacierback_mammoth.passive`,
`enemy_levyman.passive`). The conversion was **byte-identical** (sim digest unmoved,
V.2/V.14); only the rendered `formula`/`text` of the 15 converted Tier-B abilities
gained their scaling lines.

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
| Ability descriptions (T.34/T.35a) | `registries.py` (`ABILITY_META`, `Magnitude` family: `ScalingTerm`/`PctResource`/`MaxOfTerm`/`SetByCaller`, `Clause` w/ `template`+`terms`, `SummonSpec`, `AbilityMeta`), `ability_text.py` (`render` pure per-kind dispatch, `render_for`, `TICKS_PER_SECOND`) |
| id source on the model | `content.py` (`active_ability`/`passive_ability`) |
