# 2026-06-13 — T.29a item engine: components, 16-core cut, 3-slot equip, REWARD drops

Implements T.29a in full. Key deliverable: a `src/game/items/` package wiring 8
base components + 16 combined items into the existing T.20 effect substrate
(`ITEM_REGISTRY`, `EffectBundle`, `Modifier`, hook closures). `Champion.items`
(≤3 slot) applied at `compile_loadout` step 2.5. Seed-deterministic REWARD-node
drops via `generate_reward_loot`. 52 new unit tests, 1085 total passing.

## What changed

1. **`src/game/items/__init__.py`** — package entry; re-exports `BASE_COMPONENTS`,
   `SPIRIT_GEM`, `RECIPE_MAP`, `combine`; side-effect import of `combined.py`
   triggers all `@register_item` decorators.
2. **`src/game/items/base.py`** — `BASE_COMPONENTS: frozenset[str]` (8 IDs) +
   `SPIRIT_GEM` constant.
3. **`src/game/items/recipes.py`** — `RECIPE_MAP: dict[frozenset[str], str]` (36
   entries) + `combine(a, b) -> str | None`.
4. **`src/game/items/combined.py`** — `@register_item` factories for all 24 items
   (8 components + 16 combined). Hook closures use `owner: Piece` captured at
   factory-call time for per-instance state.
5. **`src/game/models.py`** — `Champion.items: list[str]` (default `[]`); validation
   (≤3, non-empty); `to_dict`/`from_dict` round-trip.
6. **`src/game/loadout.py`** — `piece_from_champion` copies `champion.items →
   piece.items`; `compile_loadout` step 2.5 applies item bundles after weather,
   before trait resolution.
7. **`src/game/encounter.py`** — `CH_REWARD: Final[int] = 8`; `RewardLoot` dataclass;
   `generate_reward_loot(run_seed, node_index) -> RewardLoot`.
8. **`tests/game/test_items.py`** — 52 tests covering all T.29a acceptance criteria.
9. **`SPEC.md`** — T.29a status updated from `📋 Plan` → `✅ Done`.
10. **`docs/live/systems/items.md`** — new LIVING doc (created).
11. **`docs/live/systems/encounter.md`** — added `generate_reward_loot` entry.

## Why (the part SPEC compresses out)

The T.29a plan was already complete when this session started, so the question was
purely *precision of execution* against the plan. The main design insight the plan
captures — and which must not be forgotten — is that **mana cannot be a stat
modifier**. Mana lives on `ActiveSlot.cost`/`ActiveSlot.current_mana`, not in
`Piece.base_stats`. Any item that changes mana cost must do so via an
`on_combat_start` hook that reaches into the piece's active slots. `deepwell` and
`springtear` both follow this pattern.

Item bundle application order is equally important: step 2.5 (after weather,
before trait resolution) ensures that any future emblem items granting `granted_traits`
(T.29b) will be visible to the trait counter at step 3. This ordering is now
invariant V.23 (all item application via `compile_loadout`).

`Lifetime.COMBAT` was chosen for all item modifiers because pieces are fully
rebuilt each combat from the `Champion` dataclass. Using `PERMANENT` would have
no observable difference mechanically but would be semantically misleading and
might cause issues if the same piece were ever reused across combats.

## Decisions

- **Same-component recipes as single-element frozensets**: `frozenset({"fang", "fang"})
  == frozenset({"fang"})`, so `RECIPE_MAP[frozenset({"fang"})] = "apex_fang"` works
  for both `combine("fang", "fang")` and direct key lookup. No special-case needed.
- **spirit_gem outbound recipes return None**: T.29b stub. All 8 spirit_gem entries
  in RECIPE_MAP exist as keys but point to `None`-returning branches in `combine()`.
  This avoids a KeyError in any forward reference.
- **Hook recursion guard via SourceTag.ITEM_PROC**: Items that emit bonus damage
  (`apex_fang`, `perfect_predator`, `bloodthorn_briar`, `wildfury_lash`) check
  `ev.tag == SourceTag.ITEM_PROC` to avoid re-triggering on their own bonus damage.
  Copied idiom from enemy ability hooks.
- **`ability_can_crit` in on_combat_start, not as a modifier**: `Piece.ability_can_crit`
  is a boolean flag, not a numeric stat. Setting it via an `on_combat_start` hook
  mirrors the exact pattern used by the `ability_crit()` trait mechanic
  (`traits/mechanics.py:268–273`).
- **`milli_AS` paired with `attack_speed`**: V.34 requires that any modifier to
  `attack_speed` also modifies `milli_AS`. All AS items apply two modifiers.

## Process notes (AI collaboration)

- **Conflict: design-doc examples vs real engine API.** The plan document warned
  explicitly that design-doc examples cite stat keys that don't exist. This warning
  paid off: `CombatOutcome.TEAM_WIN` and `BattleResult.winner` (used in first-draft
  test assertions) don't exist — the real values are `CombatOutcome.WIN` /
  `.LOSS` / `.DRAW` and `BattleResult.outcome` / `.duration_ticks`. The plan's
  "verify against code" instruction was well-placed; the agent still needed two
  correction rounds on the test assertions before they matched the real API.

- **Agent error — `_CHAMPION_DEFS` type assumption.** The agent assumed
  `_CHAMPION_DEFS` was a dict and called `.values()` on it. It's a tuple.
  Similarly, `ROUTE` was assumed to be a top-level export from `route.py`; the
  real export is `STAGES`. Both errors appeared in the test harness, not the
  production code — a good reminder to read rather than infer module exports.

- **Agent error — `BattleResult` field names.** As noted above: `winner` and
  `total_ticks` were hallucinated from plausible conventions. The real fields are
  `outcome` and `duration_ticks`. Caught in the first test run and fixed.

- **Guardrail added: test for BattleResult API.** `TestCompileLoadoutItems` now
  asserts against the real `CombatOutcome` enum values and `duration_ticks` field,
  serving as a living regression guard if those are ever renamed.

- **Drift caught: encounter.md missing generate_reward_loot.** The living doc
  for `encounter.py` listed `generate_reward` but not the new
  `generate_reward_loot`. Updated in this session.

- **No design forks required.** The T.29a plan was detailed enough that no new
  design decisions were needed during implementation — every ambiguity (mana,
  ordering, lifetime, spirit_gem stubs) was pre-resolved in the plan doc. This is
  the ideal state for a build session.

### Prompting-strategy reflection

This session followed the "read everything first, then build" discipline from
CLAUDE.md and it worked well — the plan doc had pre-resolved all ambiguities. The
remaining errors (field name hallucinations, module-export assumptions) were pure
agent knowledge-boundary failures not solvable by better prompting; they required
actual code reads. The best mitigation is exactly what CLAUDE.md mandates: read
the actual module before writing tests for it. The agent did this for production
code but skimmed models.py for test setup — a mistake.

One pattern that added friction: the agent batched too many conceptual changes
into a single edit pass on `combined.py`. Reviewing 24 item factories in one
large edit made it harder to catch subtle bugs (e.g., `wildfury_lash` constructing
`_as_mod` twice). Smaller passes per factory family would have been easier to audit.

The "verify every primitive/stat/function against the code before relying on it"
guardrail in CLAUDE.md should be extended to explicitly cover *test assertion
targets* (enum values, dataclass field names) as a distinct check, not just
production-code primitives. It's easy to skip this step when writing tests because
they "obviously" match the interface you just implemented.

## Files

**Created:**
- `src/game/items/__init__.py`
- `src/game/items/base.py`
- `src/game/items/recipes.py`
- `src/game/items/combined.py`
- `tests/game/test_items.py`
- `docs/live/systems/items.md`

**Modified:**
- `src/game/models.py` — `Champion.items` field
- `src/game/loadout.py` — step 2.5 item bundle application + `piece_from_champion`
- `src/game/encounter.py` — `CH_REWARD`, `RewardLoot`, `generate_reward_loot`
- `SPEC.md` — T.29a status → ✅ Done; implementation-order note struck through
- `docs/live/systems/encounter.md` — `generate_reward_loot` entry

## Follow-ups

- T.29b: remaining 20 combined items, 6 emblems (`granted_traits`), 6 special
  run-actions (`RUN_ACTION_REGISTRY`), Spirit-Gem `combine()` branch, interactive
  `sim_run` driver.
- `wildfury_lash` factory creates `_as_mod` twice for the same delta — technically
  correct (two Modifier objects with identical values) but wasteful. Could be
  refactored to call `_as_mod` once and expand the result inline, but not a
  correctness issue.
- When T.29b lands: verify `spellfang_crown` and `mistward_shroud` interact
  correctly with the hexproof targeting guard (V.40) — `mistward_shroud` sets
  `piece.hexproof = True` which is the same flag that `hexproof` trait uses.
