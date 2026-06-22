# Augments — run-long modifiers

> **Status: LIVING** — audited by `/check`. **Reconciled:** 2026-06-22 (T.31 landed).
> **Scope:** augment model, registry, offer/reroll, quality curve, the `RunModifiers`
> combat seam, quest trackers. Code: [`src/game/augments.py`](../../../src/game/augments.py).
> Design: `docs/design/tasks/t31_augment_system_plan.md`, `docs/design/content/augment_catalog.md`.

## Model

`Augment(id, name, scope, quality, handler, piece_filter, quest_tracker, blurb)` —
frozen dataclass, registered via `@register_augment(...)` into `AUGMENT_REGISTRY`
(`registries.py`). Importing `src.game.augments` populates it (mirrors abilities).

- **`AugmentScope`** = `TEAM` | `PIECE` | `RUN` — selects the **handler signature**:
  - `TEAM`: `handler(team: list[Piece], state: dict) -> EffectBundle` — modifiers/statuses
    applied to **each** team piece; hooks subscribed **once** (global, close over `team`).
  - `PIECE`: `handler(piece: Piece, state: dict) -> EffectBundle` — applied to each team
    piece passing `piece_filter`; hooks close over that piece.
  - `RUN`: `handler(run: Run) -> None` — mutates `Run` once at **pick time**, no bundle.
  - `state` is `RunModifiers.augment_state` — read by run-scaling augments (`the_uprising`)
    and Crest bonuses.
- **`AugmentQuality`** = `COMMON` | `RARE` | `EPIC` | `PRISMATIC`.
- **54 registered** (~50 catalog across 13/13/16/12 by quality + 3 Primordial-unlock RUN
  augments). Counts: TEAM 30 · RUN 19 · PIECE 5.

`Modifier.source_id` is `augment:<id>` (V.45). All handlers RNG-free (V.2/V.14). Stat
magnitudes are **MVP `mul` values** (catalog ships concepts only) — a tuning surface (D.11).

## Combat seam (V.2 amendment, V.18)

`resolve_combat(..., run_mods=None)` / `resolve_boss_combat(..., run_mods=None)` thread a
`RunModifiers(augments, augment_state, run=None)`. `None` ⇒ every non-augment caller (all
balance sims) is **byte-for-byte identical** — guarded by `test_augments.py::test_none_run_mods_byte_identical`.

`compile_loadout(..., run_mods=None)` applies augments in the documented order
([loadout.py](../../../src/game/loadout.py)):
- **step 3** — trait resolution reads `augment_state["trait_bonus"]` (Crest/Crown/Worldroot
  inject virtual carriers into `_resolve_traits` before breakpoint selection).
- **step 3.5** — flags `piece._has_active_synergy` (the `built_different` filter).
- **step 6** — `apply_run_augments` builds TEAM/PIECE bundles fresh (V.18: never persisted).
- **step 9** — `wire_quest_trackers` subscribes quest trackers (no-op unless `run_mods.run` set).

## Offers, reroll, quality curve

- `generate_augment_offer(run_seed, node_index, stage_index, *, rerolled=False, exclude=())`
  — deterministic 1-of-3 via `augment_seed` (`CH_AUGMENT`/`CH_REROLL`). Rolls a quality by
  the stage curve, then a uniform unpicked augment of that quality. No dups; excludes active.
- **Prismatic gated to stage ≥ 2** (D3).
- `quality_weights_for_stage(i)` — per-stage Common→Prismatic weights (`_STAGE_WEIGHTS`,
  §5 curve; tuning surface). Prismatic 0 at stage 1, non-decreasing after.
- `apply_augment(run, augment)` — appends id to `run.active_augments`; RUN handlers fire;
  quest augments seed `augment_state`.

## Quest trackers (§9.3)

`QUEST_TRACKER_REGISTRY` + `QUEST_TRACKER_EVENTS` (`register_quest_tracker`). Run-level bus
subscribers that survive across combats, mutating persistent `Run` state. MVP quests:
`scouts_pay`, `prospector`, `stormbound_trail`, `bloodless_victory`, `the_uprising`,
`the_long_hunt`.

## Known simplifications (flagged, follow-ups)

- **Living World** (`living_world`) — **redesigned weather-driven** (away from the boss-only
  catalog concept, which was inert on 44/50 nodes). Each live weather grants a bespoke team boon
  echoing its @10 affinity: CLEAR=regen+STR/INT, CLOUDY=−18% incoming, MIST=`hexproof` opener,
  RAIN=mana-regen+lifesteal, SNOW=2 `slow` stacks on enemies, THUNDER=AS+lightning-on-hit. Works every
  fight. (SNOW dogfoods the B.25/V.53 fix — `slow` now throttles meter advancement.)
- **The Long Hunt** keys on **boss-id kills**, not a `boss_phase2` victim tag (none exists
  yet) (D5).
- **Primordial Bond** grants a stat tier + once-per-combat barrier; the `@2`-breakpoint-for-free
  and `@3` fixpoint tier-up (D.20) are **deferred** (D8).
- **Trail Rations / Adrenal Glands / Heart of the Storm** — modelled as steady stat/regen
  buffs rather than exact catalog mechanics (D1).
- `salvage_rights` sets `augment_state["salvage_bonus"]`; the sell path (economy.py, T.22)
  must read it.
