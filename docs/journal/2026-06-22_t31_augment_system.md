# T.31 — Augment system (backend-first)

**Date:** 2026-06-22 · **Status:** ✅ Done (engine + ~50 catalog augments + sim_run)

## What landed

The last engine `📋 Plan` task. Full augment system, no Flet:

- **`src/game/augments.py`** — `Augment` / `AugmentScope` / `AugmentQuality`, `@register_augment`,
  `@register_quest_tracker`, **54 augments** (~50 catalog × 4 qualities × 3 scopes + 3 Primordial
  unlocks), deterministic 1-of-3 offers + reroll + Prismatic gating + per-stage quality curve,
  `apply_augment`, `apply_run_augments`, `wire_quest_trackers`, `RunModifiers`.
- **`Run`** gains `active_augments` + `augment_state` (serialized + shape-validated; V.17 via CI test).
- **Combat seam** — `resolve_combat`/`resolve_boss_combat`/`compile_loadout` take `run_mods=None`;
  TEAM/PIECE bundles apply at loadout step 6, quest trackers at step 9, Crest bonuses inject virtual
  carriers into trait resolution (step 3). `None` ⇒ byte-identical (V.2/V.18).
- **`sim_run`** — `--augment-policy {first,random,highest-quality,none}` + interactive `1/2/3/r/s`.
- **`tests/game/test_augments.py`** — 21 tests (offers/gating/dedup, scope dispatch, byte-identical
  back-compat, quest accrual across combats, serialization, V.17 guard).

Suite: **1202 passed** (1181 + 21), zero regression.

## Why these shapes

- **Handler model `(team|piece, state) -> Bundle`** — the design doc's `(team) -> Bundle` had no
  way to read run-progress (The Uprising) or `augment_state`. Passing `state` to every TEAM/PIECE
  handler made run-scaling + Crest bonuses fall out cleanly. TEAM hooks **close over the live combat
  `team`** (rebuilt per combat, V.18) so they need no side-inspection.
- **Scope = handler dispatch, not catalog flavor.** Anything needing a per-owner hook is PIECE;
  pure stat bundles + global-hook effects are TEAM. A few catalog "Run" effects that are really
  *persistent combat buffs* (Trail Rations) were reclassified TEAM — that is exactly the V.18 line
  between "mutates Run once" and "re-applied each combat."
- **`RunModifiers.run` back-ref** — quest trackers must mutate `run.amber`/`inventory`, not just
  `augment_state`; the seam carries an optional live-Run ref the walker sets, `None` for pure sims.
- **Crest/Crown/Worldroot** — added a `bonus_counts` param to `_resolve_traits` (`count = len(ids)
  + bonus`). 2-line, deterministic, lets an augment light up a trait with zero native carriers.

## Decision points flagged (for later discussion)

- **D1** every stat magnitude is invented (catalog ships concepts only) — MVP `mul` values, tuning surface.
- **D4/D8** Living World (hazard-flip), Primordial Bond (`@2`-free), and the Primordial **`@3`
  tier-up** are simplified/deferred — `@3` stays D.20-aspirational (needs a trait fixpoint pass).
- **D5** The Long Hunt keys on boss-id kills (no `boss_phase2` victim tag exists yet).
- Scope reclassifications (Trail Rations etc.) and `salvage_rights` needing the T.22 sell path to
  read its flag.

## Addendum (same day) — Living World redesigned

Walking the decision points with the user, **D4's Living World was reworked** from the
armor-stub into a **weather-driven Prismatic**: each live weather grants a bespoke team boon
(CLEAR regen, CLOUDY −18% incoming, MIST `hexproof` opener, RAIN mana+lifesteal, SNOW enemy
AS/MS −25%, THUNDER AS+lightning). Reasoning: the catalog's "flip the boss arena" concept is
inert on 44/50 nodes (map effects only exist on bosses) — a poor Prismatic. Reframing it onto
the weather (always live, the game's signature lever) makes it a true run-definer that feels like
*the world itself fighting beside you*. Surfaced a **latent engine gap**: the `slow` status is a
no-op marker — slow-tiles apply it but nothing reads it to reduce speed (SNOW uses real stat muls
instead; worth a backprop/V-guard later).

## Process notes (AI collaboration)

- **Spec was already pre-amended.** `/plan` had written the T.31 row, V.2 amendment, V.17, V.18,
  D.11, and the T.22 narrowing during planning — so the `/spec` step collapsed to a single status
  flip. Caught by *reading* SPEC before mutating rather than trusting the plan's "SPEC changes
  needed" list as undone. Lesson: re-derive spec state from the file, not the plan's intent.
- **Design-doc primitives lied, as warned.** `effect_systems_design.md` §9 examples use
  `ability_power` (→ `intelligence`) and `run.bench_items` (→ `run.inventory` dict). Verified every
  stat/field against code first (`compute_stat`, `Run` fields, `Piece` attrs) — `summon` not
  `is_summon`, `attack_speed` is int-scaled ~100 not 0–1.5, which is why values are `mul` not flat.
- **The crash-sweep beat unit-first.** Before writing formal tests I looped **all 54** augments
  through real combat / `apply_augment` and printed tracebacks — surfaced shape bugs (the `summon`
  attr) in one pass instead of 54 red tests. Distrust-the-green instinct: a system that "imports
  fine" isn't a system that "runs 54 handlers fine."
- **Byte-identical guard is the load-bearing test.** `run_mods=None == None == RunModifiers()` is
  what lets every balance sim stay untouched; verified it the moment the seam existed, before
  authoring content, so a later regression would point at the seam not a handler.
- **Prompting strategy.** The driving prompt was "build T.31, flag decision points so we can later
  discuss" — explicit permission to proceed through ~50 invented-value decisions without blocking,
  surfacing them as numbered flags (D1–D9) instead of `AskUserQuestion` round-trips. For a task that
  is 80% mechanical authoring over a fixed substrate, "decide-and-flag" kept momentum where
  "ask-first" would have stalled on every magnitude. The genuine forks (deferring `@3`) were called
  out loudly; the rote ones (stat values) were defaulted and logged.
