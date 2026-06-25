# T.23 Plan — Prep View (full economy) + team-positions wrapper

> **Status:** `T.23 🟡 WIP` (already flipped by `t10_mvp_run_loop_plan.md`). This
> doc is the **focused** T.23 plan; the MVP-slice doc covers it at slice-level
> (§3.3) — this one verifies every seam against current code and splits 23a/23b.
> **Supersedes:** [`t23_prep_formation_snapshot_plan.md`](./t23_prep_formation_snapshot_plan.md)
> (🔴 drift — cites the removed `game/combat.py` + `resolve_combat(team_positions=)`;
> the landed primitive is V.62 `build_combat(positions=)` + `CombatSession.positions`).
> **Depends (all built):** T.1 (models ✅), T.3 (combat ✅), T.10 (RunStart ✅),
> T.11 (Trail ✅), T.22 (economy/shop ✅), T.24 (enemy formation + deployment-zone
> definition ✅), T.29 (item engine ✅, gates 23b).
> **Resolves:** the Prep stub (`main.py:53 _push_prep_stub`); the last big unbuilt
> run-loop seam (Trail→Prep→Combat).
> **Design source-of-truth:** [`views_spec.md`](../systems/views_spec.md) §6 (Prep),
> SPEC §V.62 (positions primitive), §V.63 (run-loop computes no game logic),
> [`t24_enemy_formation_plan.md`](./t24_enemy_formation_plan.md):56-57 (deployment
> zones), [`docs/live/systems/ui.md`](../../live/systems/ui.md) (CombatSession seam).
> **What this plan adds beyond the MVP doc:** the verified-against-code seam list,
> the **corrected deployment zone** (`q < 3`, not the MVP doc's loose `q < 5`),
> the 23a/23b split (items deferred behind a new `game/` equip seam), and the exact
> `validate_team_positions` contract.

---

## 0. Substep split

Real seam = **pure-UI-over-existing-backend (23a)** vs **needs-a-new-`game/`-equip-primitive
(23b)**. Each ships + tests independently; 23b depends on 23a.

| Sub | Scope | New code | Ships |
|---|---|---|---|
| **23a** | Prep view: hex placement (drag / Auto-Place / Reset, zone `q < 3`), bench↔field, **shop** (buy/reroll/sell/supply), enemy preview, stat tooltips, Start-Combat → `CombatSession(positions=team_positions)`. Engine residue = **only** the team-only `validate_team_positions` wrapper. | `ui/views/prep.py`, `game/loadout.py::validate_team_positions` | Full pre-combat decision layer minus items |
| **23b** | Items: new **`game/` equip/unequip seam** (`inventory`↔`champion.items`, ≤3 cap, combine-on-equip) + Prep equip panel. | `game/inventory.py` (or `economy.py` addn), `ui/views/prep.py` (edit) | Item loadout in Prep |

Build order: **23a → 23b.** 23a is the run-loop-critical path (the loop closes
without items); 23b layers on top. (User pick: split, not all-in-one.)

---

## 1. Scope

**In (23a):** the full pre-combat decision UI over the *existing* economy/shop/combat
backends — placement, bench/field, shop, preview, tooltips, Start-Combat. The only
new `game/` code is the team-positions validator.
**In (23b):** the item equip seam + UI.

**Out (with why):**
- **No combat/economy/shop *rules*** — V.63/V.1: Prep mutates `Run` only through
  `game/economy.py` / `game/shop.py` and resolves only via the combat view's
  `resolve_combat`/`CombatReplay`. Prep computes no Amber/cost/level/encounter number.
- **No augment-pick UI** — `active_augments` stays seeded/empty for MVP (a separate
  T.31-UI task); the combat path already honors any present `RunModifiers`.
- **No new placement *engine* primitive** — V.62 `build_combat(positions=)` already
  overrides spawns for both sides + validates on-board / no-dup / known-id. 23a only
  adds the **team-only** zone + roster-id wrapper on top.
- **Items deferred to 23b** — no public equip seam exists yet; building it is real
  `game/` work, kept off the loop-critical path.

---

## 2. The gap today

| Piece | `file.py:line` | State |
|---|---|---|
| Positions primitive (both sides, validated, byte-identical when `None`) | `game/combat/resolve.py:80 build_combat(positions=)` | ✅ V.62 |
| CombatSession seam (carries `positions`/`run_mods`/`node_id`/`map_effect_id`) | `ui/combat_playback.py:133` | ✅ |
| Shared node encounter (preview == fought squad) | `game/encounter.py:902 node_encounter(seed, node, weather=None, dc=…) -> NodeEncounter(enemies, map_effect_id)` | ✅ (Trail already uses) |
| Shop ops | `game/shop.py` `buy_from_shop`/`reroll_shop`/`reroll_cost`/`generate_supply_offer`/`take_supply_champion`/`refresh_shop` | ✅ |
| Economy ops | `game/economy.py` `sell_champion`/`buy_champion`/`champion_cost`/`sell_value`/`level_from_copies`/`try_rank_up_with_amber` | ✅ |
| Run loadout state | `game/models.py:702 roster`/`703 bench`/`712 tempest_rank` (field cap)/`716 champion_copies`/`707 inventory` | ✅ |
| Default spawn packing (team → low-q cols) | `game/combat/engine.py:756 assign_spawns` (`position_q = i // BOARD_HEIGHT`) | ✅ |
| Deployment zone definition | `t24_enemy_formation_plan.md:56` player = cols 0–2; enemy = 7–9 | ✅ (doc) — **not a code constant yet** |
| Dev-harness reference producer | `ui/views/dev_harness.py:537 CombatSession(...)` | ✅ mirror this |
| Combat board geometry | `ui/views/combat.py:192 _cell_xy(q,r)` (view-private) | 🔶 needs extracting/reusing |
| Stat-inspect rows | `ui/views/combat.py:714 _stat_row` / `721 _build_inspect` (view-private) | 🔶 needs extracting/reusing |
| `validate_team_positions` | `game/loadout.py` | ❌ create (23a) |
| Item equip/unequip seam | — | ❌ create (23b) |
| Prep view | `main.py:53 _push_prep_stub` (placeholder) | ❌ create |

---

## 3. Architecture

`ui/` imports `game/` + `viz/` + `api/`, never the reverse (V.1). Prep is a
`page.views`-stack route handler. One `Run` holds all state. The dev_harness
(`dev_harness.py:537`) is the **reference producer** — Prep builds the **identical**
`CombatSession`; mirror it.

### 3.1 Placement → `team_positions` → `CombatSession.positions`
- Player drags/taps deployable champions onto allied-zone hex cells. State held in the
  view as `team_positions: dict[champion_id → (q, r)]`.
- **Deployable set** = the first `tempest_rank` champions of `roster` (field cap, V.22).
  Bench = the rest. Only deployable pieces get a board cell; bench pieces don't.
- **Auto-Place** = `positions=None` semantics (don't author cells; let `assign_spawns`
  pack) → byte-identical default formation (V.62). Practically: clear `team_positions`.
- **Reset** = clear `team_positions` (≡ Auto-Place).
- **Start Combat** = `CombatSession(team=deployable, enemies=enc.enemies, weather=node
  display-independent **node default** (V.66/V.2), run_mods=RunModifiers.from_run(run),
  node_id, map_effect_id=enc.map_effect_id, positions=team_positions or None)`. Pushes
  the combat view. Enemies/weather/map-effect come from **`encounter.node_encounter`**
  (the same dispatcher Trail's preview uses → preview == fought squad, V.2/V.63).

#### 3.1.1 `validate_team_positions` — the only 23a engine residue
Location: **`game/loadout.py`** (the content↔combat boundary; Flet-free, testable;
the MVP doc's D2). Signature (proposed):

```python
def validate_team_positions(
    team: list[Champion],
    positions: dict[str, tuple[int, int]],
    *, zone_max_q: int = ALLIED_ZONE_MAX_Q,  # exclusive: q < zone_max_q
) -> None:
    """Raise ValueError unless every key names a champion in `team`, every cell is in
    the allied deployment zone (0 <= q < zone_max_q, 0 <= r < BOARD_HEIGHT), and no two
    share a cell. A team-only superset of the V.62 engine guard (which checks on-board /
    no-dup / known-piece across BOTH sides) — adds the zone + roster-id (team-only) check
    the engine can't (it doesn't know which pieces are the player's)."""
```

- 23a calls it **before** building `CombatSession`; an invalid layout blocks Start-Combat
  with a clear message (never a silent drop, never an engine-level raise mid-sim).
- `ALLIED_ZONE_MAX_Q = 3` — a named constant (proposed home: `game/loadout.py` or
  re-exported from `game/formation.py` next to the enemy `COL_FRONT/MID/BACK`), matching
  `t24_enemy_formation_plan.md:56` (player cols 0–2). **Not** the MVP doc's `q < 5` (§6).
- The V.62 engine guard still runs underneath at `build_combat` — defense in depth.

### 3.2 Economy panel (shop + bench/field)
All mutations go through `game/`:
- Shop: `buy_from_shop(run, slot)` / `reroll_shop(run)` (cost via `reroll_cost`) /
  `sell_champion(run, champion_id)` / `take_supply_champion(run, champion_id)`.
- Field cap = `tempest_rank`; rank-up via `try_rank_up_with_amber(run)`.
- Merge feedback: `champion_copies` + `level_from_copies` (3-copy → level rule already in
  `economy.buy_champion`/`_materialize_champion`). Prep **displays** copy progress; the
  merge happens in the backend on buy.
- Bench↔field = reorder `roster` so the intended deployable set occupies the first
  `tempest_rank` slots (no new model field; the cap is positional). Verify against
  `models.py` whether a deploy flag exists or ordering is the contract (§7 Q-open).

### 3.3 Enemy preview + tooltips
- Preview from `node_encounter(run.seed, node)` (deterministic). Per enemy: name/type,
  role, **affinity clash** via `weather_effects.ring_relation` (predator/prey vs the
  team's affinities) — same helper Trail's focus panel uses.
- **Stat tooltips:** views_spec §6.4 wants raw (HP/STR/INT/AS/MS/MR/THR/Armor/RES) +
  derived rates. The combat view already renders these in `_build_inspect`/`_stat_row`
  (`combat.py:714-721`) — but they're **view-private**. Decision (§4): extract a shared
  stat-row builder (Flet, in `ui/components/`) reused by both combat-inspect and Prep,
  rather than duplicate. Ability text via the existing `render_for` (`ability_text`).

### 3.4 Board geometry reuse
`_cell_xy(q, r)` (`combat.py:192`) maps axial→pixel for the hex board. Prep needs the
same geometry. Decision (§4): extract `_cell_xy` + hex constants to a shared module
(`ui/components/` or `viz/`) so Prep and combat share one geometry source — no second
hand-rolled coordinate system (drift risk).

### 3.5 Cross-task seams / wrinkles
- **Weather:** Prep shows the node's live/tri-state weather (display, V.66) but Start-Combat
  passes the node **default** weather (deterministic, V.2) — combat never depends on the
  live feed. (Same decoupling Trail enforces.)
- **Boss nodes:** `node_encounter` returns `map_effect_id`; pass it through —
  the combat view already wires `attach_map_effect`.
- **run_mods deep-clone:** combat view clones `run_mods` (V.55); Prep just passes
  `RunModifiers.from_run(run)` by the dev-harness convention.
- **Back to Trail:** allowed; purchases already committed to `Run` (no Prep-local
  staging) — re-entering Prep shows the post-purchase state. (views_spec §6.5 "with
  confirmation" — MVP: no confirm, purchases are intended-permanent.)

---

## 4. Decisions

1. **Deployment zone = `q < 3`** (cols 0–2), per `t24_enemy_formation_plan.md:56` (the
   landed enemy-formation design that paired player 0–2 / enemy 7–9). **Corrects** the
   MVP doc's first-pass `q < 5`. Named constant `ALLIED_ZONE_MAX_Q = 3`. **Proposed.**
2. **`validate_team_positions` in `game/loadout.py`** — the team-shaping content↔combat
   seam; Flet-free + testable + reusable. **Proposed.**
3. **Items → 23b** behind a new `game/` equip seam (user pick). 23a ships without items.
   **Decided (user).**
4. **Extract shared stat-row builder + `_cell_xy` geometry** to `ui/components/` rather
   than duplicate combat-view internals in Prep (anti-drift). **Proposed.**
5. **Bench/field = positional** (first `tempest_rank` of `roster` deploy) unless a deploy
   flag already exists on the model — confirm in §7 Q1. **Proposed.**

---

## 5. Authored values
- `ALLIED_ZONE_MAX_Q = 3` (cols 0–2; 3×7 = 21 cells ≫ max 10 deployable). Tunable.
- No new economy/combat constants — 23a authors **layout + a validator**, not balance.
- 23b: item equip cap = **3** (already `Champion` invariant, `models.py:162`); no new number.

---

## 6. Content / roster audit + reconciliation

- **Deployment-zone drift (caught).** Two docs disagree: `t24_enemy_formation_plan.md:56`
  says player cols **0–2** (`q < 3`); `t10_mvp_run_loop_plan.md:206` proposed `q < 5`
  (loose "left half", first-pass, pre-verification). T.24 is the **landed** design that
  actually placed enemies at 7–9 to leave 0–2 for the player → it wins. **Reconcile:** use
  `q < 3`; note the MVP doc's `q < 5` superseded (§10). **V-guard:** the new V invariant
  (§10) pins the zone + names `validate_team_positions` as its sole enforcer, so the two
  numbers can't re-diverge.
- **Stale T.23 snapshot plan** (`t23_prep_formation_snapshot_plan.md`) cites removed
  `game/combat.py` + `resolve_combat(team_positions=)` → superseded by this doc (§10).
- No code-vocabulary drift (no new tags/registries/rosters — UI + one validator).

---

## 7. Open questions

**Resolved here (overridable):** zone `q < 3` (D1); validator in `loadout.py` (D2);
items → 23b (D3); extract shared stat-row + geometry (D4); positional bench/field (D5).

**Resolved by user (this round):**
- **Q1 — TFT-style bench/board (decided).** `roster` (board/field) + `bench` are separate
  lists; bench↔field = drag/drop a champion **between the two lists**, with board pieces
  carrying a `team_positions` cell. Field count ≤ `tempest_rank` (cap); bench holds the
  overflow + reserves. Re-verify the `bench` size cap + any field-cap helper in
  `economy.py`/`models.py` before building 3.2 (no new model field expected — the two
  lists *are* the bench/board split).
- **Q2 — partial team allowed (decided).** Start-Combat with **fewer than `tempest_rank`**
  placed is legal (≥1 piece); the engine handles any team size.
- **Q3 (23b) — auto-combine on double-equip (decided).** Equipping consumes the
  `inventory` entry (`_inv_remove`) and, when a champion holds two components that form a
  recipe (`recipes.combine`), **auto-combines** into the recipe item in `champion.items`.
  Pin exact ordering (equip-then-combine, ≤3 cap interaction) in the 23b sub-plan.

**Deferred:** augment-pick screen (T.31-UI); Prep visual polish; consumable/active-item
use mid-Prep (only equip in 23b).

---

## 8. Test plan

Logic is testable; views are not (CLAUDE.md "test logic only").

**23a — `tests/game/test_prep_positions.py`:**
- `validate_team_positions`: valid layout passes; **off-zone** (`q >= 3`) raises;
  **dup cell** raises; **unknown champion id** raises; **out-of-board r** raises; empty
  `positions` (Auto-Place) passes (≡ default).
- **V.62 regression:** a layout that passes the wrapper, fed as `CombatSession.positions`
  → `build_combat`, places pieces at exactly those cells at tick 1; `None` ⇒ default
  formation byte-identical (fixed seed, `workers=1` — V.2/V.14).
- **Producer-shape parity:** the `CombatSession` Prep would build for a node equals the
  dev-harness producer's shape for the same `(seed, node)` (same enemies via
  `node_encounter`, same fields populated).

**23b — `tests/game/test_inventory.py`:**
- equip moves `inventory[item]`→`champion.items`, decrements inventory, respects the ≤3
  cap (raises/blocks on the 4th), combines two components into the recipe item; unequip
  reverses; determinism preserved.

**Regression:** existing combat-view + encounter tests stay green (no signature change to
`node_encounter`/`build_combat`).

---

## 9. Acceptance criteria

**23a:**
1. Prep renders the hex board (shared `_cell_xy` geometry), team roster (board + bench),
   enemy preview (via `node_encounter`, role + affinity clash), and shop.
2. Placement: drag + Auto-Place + Reset within `q < 3`; one piece per cell; invalid
   placement gives clear feedback and **cannot** Start-Combat.
3. Shop buy/reroll/sell/supply + bench↔field all mutate `Run` **only** through
   `game/economy.py`/`game/shop.py` (Prep computes no number — V.63).
4. Stat tooltips show raw + derived stats (shared renderer).
5. Start-Combat builds a `CombatSession` **shape-identical** to `dev_harness.py:537` with
   `positions=team_positions` and pushes the combat view.
6. `validate_team_positions` tests green; V.62 byte-identical regression holds.

**23b:**
7. Equip/unequip moves items `inventory`↔`champion.items` with the ≤3 cap + combine,
   through a `game/` seam (no inline UI mutation of `champion.items`); tests green.

---

## 10. SPEC changes needed (for `/spec`)

- **§T.23 row** — refresh files-cell to landed reality + note the 23a/23b split:
  goal-cell already rewritten (post-V.62) by the MVP doc; append files
  `ui/views/prep.py`, `game/loadout.py` (`validate_team_positions` + `ALLIED_ZONE_MAX_Q`),
  `game/inventory.py` (23b), `tests/game/test_prep_positions.py`,
  `tests/game/test_inventory.py`. Status stays `🟡` until 23b lands, then `✅`.
- **New §V invariant (deployment zone):** *the player's Prep placement is confined to the
  allied deployment zone `0 ≤ q < ALLIED_ZONE_MAX_Q (=3)` and validated **team-only** by
  `game/loadout.py::validate_team_positions` (zone + roster-id) on top of the V.62 engine
  guard; the zone matches the T.24 enemy formation's player half (cols 0–2)*. Guards the
  `q<3`/`q<5` re-divergence + a view bypassing the validator.
- **§B backprop:** none (no runtime bug). Record the deployment-zone **doc drift**
  (`q<5` vs `q<3`) as a documentary reconciliation in this plan's §6, not a §B row.
- **§D:** Prep-loop gap → resolved on 23b land; augment-pick UI + Prep polish stay deferred.
- **Implementation Order:** `T.23 → T.15(reward)` already placed; split internally
  `T.23a → T.23b` (23b may trail T.15/T.13 since the loop closes without items).
- **Supersede note:** mark `t23_prep_formation_snapshot_plan.md` superseded by this doc.

---

## 11. LIVING docs to update (build must touch on landing)

- **`docs/live/systems/ui.md`** — add the Prep section (layout, placement→`team_positions`
  →`CombatSession` seam, shop/bench economy calls, shared stat-row + geometry helpers,
  the validator). 23b adds the item-equip note. Flip Prep status 🔶→✅ (23a), items in
  Prep ✅ (23b).
- **`docs/live/systems/items.md`** — on 23b, document the new equip/unequip seam +
  re-reconcile date.
- **`ARCHITECTURE.md`** — ensure the view-stack map shows Trail→Prep→Combat + which `game/`
  modules Prep calls.
- Journal entry on landing (Process notes + prompting-strategy section, CLAUDE.md mandate),
  incl. the deployment-zone drift catch.
