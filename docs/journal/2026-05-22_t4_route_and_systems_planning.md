# Journal - 2026-05-22 (T4 Route + Systems Expansion Planning)

## Scope and User Intent

Planning-only session. No code written, no tests run. Goal: plan T4 (city
route), then — driven by user follow-ups — design the encounter/content systems
that T4 exposed as undefined, split them into dedicated task plans, and
reconcile SPEC.md.

Started from: T1-T3 implemented, T3 journalled. SPEC tasks ran T1-T17.

## Chronological Protocol

1. **T4 plan.** Read `SPEC.md`, `t3_combat_engine_plan.md`,
   `t1_model_contracts.md`, `models.py`. Asked the user three questions (route
   layout, node types, coordinates). Answers: 6 continent stages with authored
   node sequences, all node types (placeholder-first), real-world lat/lon. Wrote
   `docs/design/t4_city_route_plan.md`.

2. **Encounter-generation brainstorm.** User asked how encounter generation
   could work and to brainstorm Challenge/Boss. Established the core split:
   **fixed skeleton + procedural encounter fill**, seed-deterministic via
   per-node sub-seeds, enemy power clustering into budgets, lazy regeneration
   for save stability.

3. **Power formula.** User specified intent; converged on
   `P = √1.5^(T-1) · 1.5^(L-1)` = `1.5 ** ((T-1)/2 + (L-1))` — "two tiers ==
   one level". Analysed `√P` stat coupling and the `Cost = T` economy (U-shaped
   Amber-efficiency; resolved by availability gating, not price). Corrected an
   arithmetic slip: T1L1→T10L3 spread is ~14×, not 21×.

4. **Split into task docs.** User: "split into other t documents." Created five
   plan docs T18-T22. Patched SPEC.md (new T-rows, V.7, D-section, B-section,
   implementation order, cities table). Patched the T4 plan.

5. **Challenge composition.** User: "do both" — hybrid 40% current-weather /
   40% challenge-weather / 20% random, fixed team sizes. Researched TFT team-
   size progression (board cap == player level, 1-10). Set challenge sizes and
   the deterministic integer slot split.

6. **Clear correction + stage-1 challenge.** User corrected: `CLEAR`-affinity
   pieces do exist (generic/holy theme). Added a `CLEAR` challenge to stage 1
   (route back to 50 nodes, 6 challenges — one per weather). Added a planned
   `CLEAR`-weather passive. Rewrote the SPEC D-section to capture every open
   decision (16 entries).

7. **Team-cap mechanic.** Team board cap is driven by an XP-analogue counter:
   start at rank 1, `+2` per fight, raise rank `N` at `2N`; currency can
   complete a rank-up instantly at full remaining cost (all-or-nothing).

8. **Resource naming.** Currency named **Amber**; the team-size counter named
   **Tempest** (`1 Amber : 1 Tempest`). Renamed across the design docs and
   SPEC; the `Run.gold` → `Run.amber` field rename is logged as backprop B.4.

## Repo Changes Summary

- Added: `docs/design/t4_city_route_plan.md`
- Added: `docs/design/t18_power_scaling_plan.md`
- Added: `docs/design/t19_encounter_generation_plan.md`
- Added: `docs/design/t20_ability_framework_plan.md`
- Added: `docs/design/t21_challenge_boss_plan.md`
- Added: `docs/design/t22_meta_progression_plan.md`
- Added: `docs/journal/2026-05-22_t4_route_and_systems_planning.md` (this file)
- Modified: `SPEC.md` — T-table rows T.18-T.22, V.7 (6 stages), full D-section
  rewrite, B-section entries B.1-B.3, T.4/T.18-T.22 planning notes,
  implementation order, cities table.
- No source or test changes.

## Key Design Decisions

### T4 — City Route

- 6 stages, one per continent (Europe → Africa → Asia → Oceania → South America
  → North America), played in fixed order; linear chain, no branching.
- One hub city per stage (London, Cairo, Tokyo, Sydney, Rio de Janeiro,
  New York) — keeps the city catalog at 6, inside the content budget.
- 50 nodes: stage 1 has 10, stages 2-6 have 8 each.
- Real-world lat/lon stored in `CityDef`; T11 projects to canvas.
- Prerequisite model change: `NodeType += SUPPLY, CHALLENGE`.
- `REWARD` redefined: an easy fight with guaranteed loot (carries both
  `enemy_pool_id` and `reward_table_id`); also grants `+1` board cap.

### T18 — Power & Scaling

- `P = 1.5 ** ((T-1)/2 + (L-1))`. Per tier ×√1.5; per level ×1.5.
- Stats couple by `√P` (combat-value linear in `P`); `AS/MS/MR/range/threat`
  stay flat (role identity). The 60-champion roster is derived from ~6-8
  archetypes, not hand-tuned.
- Economy: `Cost(T) = T`; tier balance via progression availability gating.

### T19 — Encounter Generation

- Fixed skeleton, procedural fill. Per-node sub-seeds from `Run.seed`
  (`derive(seed, node_index, channel)`, integer mix — never `hash()` on str).
- Enemy archetypes tagged `faction / affinity / role / power`; node budgets in
  `P` units; greedy squad fill.
- Persistence: store seed + choices, regenerate squads/offers lazily; add a
  `content_version` guard.

### T20 — Ability / Passive / Status Framework

- Resolves SPEC D.3-D.5. Registry + typed event bus + status gates + boss phase
  hook. Bosses are the first consumer — T20 must precede boss content.
- First passive content: a `CLEAR`-weather buff on 1-2 `CLEAR`-affinity pieces
  (`CLEAR` is inert under T2, so the affinity needs this for identity).

### T21 — Challenge & Boss

- 6 challenges, one per stage / per weather. Spirit faction. Affinity fixed per
  stage (Clear → Cloudy → Mist → Snow → Rain → Thunder).
- Roster composition 40% current-weather / 40% challenge-weather / 20% random;
  deterministic on `(seed, weather, challenge_index)`. Team sizes 4/5/6/7/8/10.
- 6 authored bosses, 2 phases (phase 2 grants +1 active +1 passive), one
  weather-themed map effect each; boss affinity == node weather (including final boss).

### T22 — Meta Progression

- Augment (1-of-3, 4 qualities, one reroll); Supply (1-of-5 champion+item).
- Economy: **Amber** currency, `Cost(T) = T`, leveling by combining 3.
- Team board cap grows via the `Tempest` counter (XP analogue): start rank 1,
  `+2` Tempest per fight, raise rank `N` at `2N`; **Amber** completes a rank-up
  instantly at `1 Amber : 1 Tempest`, full remaining cost (no partial buys).
  Roster (owned) is distinct from board cap (deployable); `/recruit` seeds 3
  into the roster.

## Open Items / Deferred

SPEC D-section now lists 16 open decisions, grouped Route / Combat / Content /
Economy / UI. Largest undesigned gaps flagged:

- **D.8 Synergy traits** — `Champion.traits` reserved by V.8 but no synergy
  catalogue or bonuses exist.
- **D.9 Item system** — items referenced by Supply, Reward drops, and the prep
  inventory; no model, pool, or effects designed.
- **D.16 View/route drift** — SPEC's Flet route table is stale against
  `views_spec.md`; `views_spec.md` §11 itself is stale (7-node route, 4-value
  `NodeType`).

Both D.8 and D.9 likely warrant their own plan docs before T5 content.

## Verification

- No code; no test run. Verification is documentation consistency:
- Route node count (50), challenge count (6), and the `NodeType` extension are
  consistent across `SPEC.md`, `t4_city_route_plan.md`, and
  `t21_challenge_boss_plan.md`.
- Team-cap mechanic (`Tempest` / `Amber`) consistent across
  `t22_meta_progression_plan.md` §5, `SPEC.md` D.14, and B.4.
- Editing note: the T4 plan re-added its stage-1 challenge after an interim
  edit had removed it (challenge count 5 → 6); final state is 6 challenges,
  50 nodes.
