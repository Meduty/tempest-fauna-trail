# T.28a — Synergy trait framework + declarative content + roster rebalance

**Date:** 2026-06-05
**Task:** SPEC §T.28a. Status 📋 → ✅.
**Plan:** [t28_trait_effects_plan.md](../design/tasks/t28_trait_effects_plan.md) ·
**Design:** [trait_catalog.md](../design/content/trait_catalog.md) v2.1.

## What shipped
- `src/game/traits/` package: `types.py` (`TraitScope`, `TraitBreakpoint`,
  `DynamicThreshold`), `_packs.py` (`stat_pack_bundle` + `define_trait`
  shorthand), `affinities/kinships/callings.py` (all **24** trait factories with
  declarative stat-pack rungs), `__init__.py` (`affinity_trait` synthesis,
  `_resolve_traits`, `resolve_and_apply_traits`).
- `compile_loadout`: trait step 3 (between weather and passives); now returns a
  **3-tuple** `(pieces, bus, trait_activations)`; HP re-sync so `hp`-mul mods bite.
- `BattleResult.trait_activations` + serialization; recorder threads it;
  `resolve.py`/`_common.py`/2 tests updated for the new return arity.
- **Roster rebalance** (`content.py`): kinship pools hit targets exactly (Beast
  14 / Spirit 11 / Skyborn 9 / Scaled 9 / Tidekin 9 / Swarm 8 = 60); one Tier-10
  per kinship; Packmate filled (8 cheap T1–3 secondaries); Hunter nudged
  lower-tier; 4 dead Calling tags dropped (B.9). Calling pools sum 87.
- `tests/game/test_traits.py` (15 cases). Full suite **713 passed / 101 skipped**.
- LIVING docs: `traits.md` 🔶STUB → 🔶PARTIAL (declarative half), ARCHITECTURE map.

## Process notes (AI collaboration)
- **The design phase dwarfed the build.** Most of this task's value was the long
  catalog v2.1 collaboration (apex=`min(pool,cap)`, emblem−1, single-step ladders,
  TFT-researched breakpoint counts, kiting rework, diversified cheat-death, T10
  augment-gate). The code was almost mechanical once the design was nailed — the
  right ratio for a content system. Spec/design discipline paid off.
- **Verify-before-build caught three integration traps that the design docs could
  not know:**
  1. `Piece.base_stats` HP key is **`"hp"` not `"max_hp"`**, and `max_hp` is a
     *cached field the engine reads directly* — not via `compute_stat`. So `hp`-mul
     modifiers are inert unless re-synced. Added an explicit `max_hp = hp =
     stat("hp")` re-sync in the trait step. A blind port would have shipped
     dead HP bonuses (the single most common trait stat).
  2. The combat engine reads stats via `piece.stat()` → `compute_stat` for
     everything *except* HP, so str/armor/AS/etc. modifiers "just work" — only HP
     needed special handling. Confirmed by grep, not assumed.
  3. The **barrier system already exists (V.28)** — flagged for T.28b so
     shields/second-wind reuse `grant_barrier` instead of a new absorb field.
- **Identical trait-lists forced full-line edits.** Several champions share the
  exact `["Beast","Bruiser","Mender"]` / `["Spirit","Primordial","Channeler"]`
  trait tuples, so `Edit` on the traits fragment alone would be ambiguous — every
  roster edit used the full id-bearing line. The roster counts were then verified
  by script (hit every target exactly) before trusting them.
- **Scope honesty: stat-now, mechanic-later.** T.28a authors the *stat-pack*
  portion of every rung; the catalog's mechanic riders (kiting/revive/echo/…)
  layer onto the same trait ids in b/c. Every rung still does *something* (a stat
  bump), so no breakpoint is a live no-op — but the doc + comments are explicit
  that e.g. "Mender @6 revive" is currently just a small team-HP pack.
- **Determinism preserved.** Resolution is a pure function of `(team, board_cap)`;
  the full suite (incl. sims) stayed green with traits active. Sims now include
  trait effects (correct), which will shift balance baselines — a re-baseline is a
  follow-up, not a T.28a blocker.
- **Checkpoint-committed mid-task** (framework before the 22-edit roster surgery)
  to protect a green state before the riskiest part — a deliberate habit on long
  builds.

## Prompting-strategy reflection
- **Heavy front-loaded design via `AskUserQuestion` + iterative critique paid off
  enormously here.** The user drove ~8 rounds of design refinement (apex rule,
  breakpoint counts, kiting, cheat-death, T10 access) *before* a line of code. By
  build time there were zero open design questions, so the build was a single
  uninterrupted pass. Contrast with diving into code early, which would have
  thrashed against undecided mechanics.
- **TFT web-research mid-design** (`WebSearch`/`WebFetch` for Set 16 breakpoint
  distributions) turned a hand-wave ("more breakpoints") into concrete, sourced
  numbers (~⅓ start at 1; 4–5 modal; single-step ladders common). Grounding a
  game-design call in real reference data beat inventing it.
- **Self-review as a distinct step keeps finding real bugs** (the apex-vs-pool
  contradiction I'd written into the catalog; the no-T10-acquisition gap). Worth
  the tokens every time.

## Deferred to T.28b/c
Mechanic primitives (kiting + guardrails, revive-once, second-wind decaying-shield
reusing V.28 barriers, tidal HoT, untargetable/taunt/dodge, time-ramp/enrage,
echo/aura/splash/spawns/empowered-shot/weather-as-buff), Packmate `@full-board`
*effect*, and the apex effects. Sim re-baseline once mechanics land.
