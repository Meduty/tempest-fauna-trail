# Augments — run-long modifiers

> **Status: LIVING** — audited by `/check`. **Reconciled:** 2026-07-01 (T.31 + T.42a reroll).
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
- **54 registered** = 51 catalog augments + 3 Primordial-unlock RUN augments
  (`unlock_verdant`/`unlock_tempest`/`unlock_stoneveil`, EPIC — gate the T10 late
  shop, T.28a/V.37). By quality: **COMMON 13 · RARE 13 · EPIC 16 · PRISMATIC 12**
  (the 3 unlocks fall in the 16 EPIC). By scope: **TEAM 30 · RUN 19 · PIECE 5**.

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

- `generate_augment_offer(run_seed, node_index, stage_index, *, reroll_count=0, exclude=())`
  — deterministic 1-of-3 via `augment_seed(run_seed, node_index, reroll_count)`
  ([encounter.py](../../../src/game/encounter.py), V.84). For each of 3 slots: roll a
  quality by the stage curve (`_weighted_quality`), then pop a uniform augment from that
  quality's pool. No dups within the offer; `exclude` (already-active ids) filtered out;
  qualities with weight 0 skipped. `reroll_count` selects the draw: `0` → `CH_AUGMENT`
  (fresh node offer), `1` → `CH_REROLL` (first reroll — **both byte-identical to the
  pre-reroll channels**), `≥2` → `CH_REROLL` strided by `AUGMENT_REROLL_STRIDE` for
  awarded/banked rerolls (T.42a) — replaces the old `rerolled: bool` arg.
- `rerolls_available(run, reroll_count)` / `reroll_augment_offer(run, node_index, stage_index,
  reroll_count)` — game-side reroll bookkeeping (**1 base free reroll per node visit** +
  `augment_state["banked_rerolls"]`; only `component_stipend` banks one). `rerolls_available`
  = `(1 if reroll_count == 0 else 0) + banked`. `reroll_augment_offer` spends the free reroll
  first, then decrements `banked_rerolls`, and returns `(new_offer, new_count, left)` at
  `reroll_count + 1` — or `None` when exhausted (view disables the button). Keeps the view
  Flet-free of game logic per V.63.
- **Prismatic gated to stage ≥ 2** (D3).
- `quality_weights_for_stage(i)` — per-stage Common→Prismatic weights (`_STAGE_WEIGHTS`,
  §5 curve; tuning surface). Prismatic 0 at stage 1, non-decreasing after.
- `apply_augment(run, augment)` — appends id to `run.active_augments`; **RUN** handlers
  fire immediately (mutate Amber/items/Tempest/state); TEAM/PIECE just record the id (their
  bundle rebuilds fresh each combat, V.18); a `quest_tracker` seeds its `augment_state` slot.
- **Node resolution.** Picking an augment is the AUGMENT node's *pick* — the view calls
  `apply_augment`, then `economy.resolve_nonfight_node(run)` marks the node CLEARED +
  advances (V.83): **no income, tempest, Hearts, or `battle_log`** (no fight occurred).

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
