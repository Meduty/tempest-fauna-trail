# 2026-06-15 — T.29d: multi-slot pieces, ability discovery, Multicaster

## What shipped

The last T.29 row — multi-slot pieces on the T.29c mana primitive:

- **One unified ability concept.** `Champion`/`Enemy` carry `active_abilities:
  list[str]` — single/null/multi are just list lengths; an empty list = a
  deliberately ability-less stat-stick (no mana bar). The old singular
  `active_ability` is **gone** (read sites use the list).
- **Convention discovery, data override.** `content.discover_abilities(id)`
  auto-attaches every registered `{id}.active`, `{id}.active2`, … (sorted).
  Roster defs author *nothing* — registering a `.active2` handler is enough.
  `abilities=[...]` overrides for named kits (bosses) or `[]` for null.
- **Distinct-slot rule (V.49).** A multicaster's slots must differ in `mana_cost`
  **or** `priority` (no two identical) so they reach threshold at different times
  → intermittent casting, never lockstep simul-cast. Default = same cost + unique
  priorities (primary `priority=2` dominant, secondary `1`).
- **Ultimate secondaries** for tier ≥ 5 (`marsh_thrush`, `tempest_eel`): `600k`
  cost (2× default) + `priority` ∝ cost, ~2× output — fires ≥1×/fight at a
  high-tier mage's MR with no items (sim-verified: 59s fight → 1 ult).
- **`Multicaster` Calling** (@2/3/4) + **`cast_momentum`** mechanic
  (`on_cast_complete` → stacking AS+MR, capped). 6 champs carry it; 3 enemy
  casters get a 2nd slot mechanically (no Calling — V.22).
- **Priority-weighted start-mana** — items grant a slot-count-invariant *total*
  split by priority, not per-slot (which duplicated value on multi-slot pieces).

SPEC V.49 amended; T.29d ✅. Suite 1174 passed (+12 T.29d tests, +1 snapshot regen).

## Process notes (AI collaboration)

- **The user caught a hack mid-build and forced a better architecture.** I'd
  built multi-slot with a `secondary=` authoring kwarg + an `active_ability`
  back-compat property. The user: *"this seems more like a hack… one logic that
  handles single/null/multi."* They were right — the runtime was already unified
  (engine iterates `piece.actives` with zero primary/secondary branching); the
  hack was the **authoring layer**. They then pushed further: *"why store entries
  at all? can't we lookup smartly?"* → convention discovery. The final design
  (discover-by-default, `abilities=` override) is materially cleaner than my
  plan's `secondary=` and *removes* authoring. **Lesson: when the user smells a
  hack, stop and re-derive the seam — don't defend the in-flight approach.** I
  researched the pattern (GAS / data-driven RPG: abilities as a uniform list,
  data separated from logic) which confirmed their instinct over my plan.
- **Cost vs priority churned three times, each a real correction:**
  1. I set secondaries to 1.5× cost (450k) → user: *"normal cost, MR is the scale,
     not cost."* Reverted to default cost.
  2. User then: *"for higher-tier multicasters, design secondaries as Ultimates —
     high cost, high output."* So cost-divergence is the *exception* (ults), not
     the default.
  3. User: *"all multicasters need diverging cost OR unique priorities — default
     is same cost, unique prios."* I'd left 7 of 9 with identical (cost, prio) on
     both slots. The rationale they gave — *"no simul-cast, an intermittent feel
     is desirable"* — is the actual design principle; unique priorities stagger
     the charge cycle. Fixed all 9.
- **Surface-math before trusting a feature.** User asked me to *calculate whether
  the ults even hit*. Equal priority → 64s to charge (most fights end first).
  The fix (priority ∝ cost) makes the 600k ult and 300k primary reach threshold
  together (~48s) — the piece fires its whole kit once per ~48s, like a single
  900k unit. Then sim-confirmed (59s fight lands the ult). **Doing the napkin
  math first caught a dead feature before it shipped.**
- **The user surfaced a second invariance bug I'd reintroduced.** *"How does
  starting mana work with multi-slot?"* — `_grant_start_mana` applied the flat
  amount to *every* slot → a 2-slot piece got 2× value from one item. That's the
  exact slot-count-duplication the MR charge-cycle (V.48 T3) was built to avoid,
  and which the user had flagged for MR earlier. Fixed to a priority-weighted
  invariant total. **The same balance principle (slot-count invariance) has to
  hold for *every* per-slot resource path — MR, start-mana, future grants.**

### Prompting-strategy reflection

The strongest signal this session was the user repeatedly choosing the
*architecture* fork over the *expedient* one, and being right each time. My
plan-doc design (`secondary=` kwarg, 1.5× cost) was "fine" but the user's
instincts (uniform list, discovery, unique-priority, invariant start-mana)
produced a cleaner system. When mid-build, I defaulted to defending the planned
shape; the better move was to treat each push-back as a design review and
re-derive. Also: the model rename rippled to ~10 test files — converting via sed
worked but mis-fired once (turned an `EnemyDef` `active_ability=""` into a model
kwarg `active_abilities=[]`); blanket regex edits across model-vs-def
construction need a per-type pass, not one sweep.
