# T.10–T.15 Plan — MVP Playable Run Loop (RunStart → Trail → Prep → Combat → Reward → Summary)

> **Status:** flips `T.10 📋→🟡`, `T.11 📋→🟡`, `T.13 📋→🟡`, `T.15 📋→🟡`,
> `T.23 📋→🟡` (build order ships them green substep-by-substep).
> **Depends:** T.8 (theme/components ✅), T.9 (menu ✅), T.12a/b/c (combat view ✅),
> T.22 (economy/shop ✅), T.14 (save ✅), T.4 (route ✅), T.5 (content ✅),
> T.7 (weather refresher ✅), T.19/T.21 (encounter/boss ✅), T.24 (enemy formation ✅).
> **All backend deps are built** — this slice is **UI + wiring only** over a finished engine.
> **Resolves:** §D loop-shell gap; surfaces-but-disabled New Run/Continue (T.9).
> **Design source-of-truth:** [`views_spec.md`](../systems/views_spec.md) §4–§7,
> SPEC §G "Core game loop", [`docs/live/systems/ui.md`](../../live/systems/ui.md)
> (combat-view seam), [`t22_meta_progression_plan.md`](./t22_meta_progression_plan.md),
> [`t23_prep_formation_snapshot_plan.md`](./t23_prep_formation_snapshot_plan.md) (**stale — see §6**).
> **What this plan adds beyond them:** the concrete view-by-view wiring against the
> *current* (post-V.62) API surface, the combat-result-out seam fix, the live-weather
> refresher lifecycle, the autosave/Continue path, and the substep ship order.

User guideline for this slice: **ship the whole loop without shortcuts, as fast as
possible.** Three scope forks resolved with user (all "no shortcuts"): live
OpenWeather refresher wired (not city-default); **full economy Prep** (placement +
shop + bench + items + tooltips); autosave + working Continue.

---

## 0. Substep split

Real seam = the per-node loop stages. Each substep ships + tests independently and
is committable green. Later letters depend on earlier.

| Sub | Scope | New files | Ships |
|---|---|---|---|
| **10a** | **RunStart** — `run_init.py` builds a `Run` (route, 1-of-3 champion pick, Amber 10, first shop, rank 1); New-Run menu wiring; lands on a stub Trail. | `game/run_init.py`, `ui/views/run_start.py` | New Run → playable Run object in memory |
| **11a** | **Trail** — Canvas node-line (all nodes/state/weather/selection/progression), node focus panel (weather favor + affinity clash + enemy preview), team summary, **live weather refresher** wired, Play-Next → Prep, Save&Exit, autosave. | `viz/route_map.py`, `ui/views/trail.py` | Trail view drives node selection + live weather |
| **23a** | **Prep (full economy)** — hex placement (drag/drop via V.62 `positions`), bench↔field, shop buy/sell/reroll/supply, items, enemy preview, stat tooltips, Auto-Place/Reset/Start-Combat → builds `CombatSession`. | `ui/views/prep.py` | Full pre-combat decision layer |
| **15a** | **Combat-result-out + Reward** — thread `BattleResult` out of the combat view; post-combat applies income/tempest, marks cleared, advances, autosaves; thin reward panel. | `ui/views/reward.py` (+ edit `ui/views/combat.py`) | Closed per-node loop |
| **13a** | **Summary** — run-end view: BarChart damage-per-battle + outcome, return to menu. | `viz/run_summary.py`, `ui/views/summary.py` | Run terminates cleanly (victory/defeat) |
| **15b** | **Routing + Continue** — `main.py` `page.views` stack wires menu↔run_start↔trail↔prep↔combat↔reward↔summary; autosave each node; Continue loads save into Trail; refresher lifecycle bound to Run. | `main.py` (edit) | Whole menu-to-menu loop incl. resume |

Build order: **10a → 11a → 23a → 15a → 13a → 15b.** (15a before 13a so the loop
closes before the terminal screen; 15b last to wire the assembled views.)

---

## 1. Scope

**In:** the full per-node loop UI + the run lifecycle wiring; live weather in Trail;
full economy Prep; autosave + Continue; both graded visualizations (route Canvas,
summary BarChart).

**Out (with why):**
- **No new combat/engine math** — V.56/V.1: `ui/` renders `game/`, never computes. All
  resolution stays in `resolve_combat`/`CombatReplay`.
- **No new economy/shop/augment rules** — T.22/T.31 backend is complete; we call it.
- **No augment-pick UI** (`active_augments` stays as seeded/empty for MVP) — augment
  *selection* screens are a separate T.31-UI task; the combat path already honors
  `RunModifiers` if present. *(Flag: confirm in §7.)*
- **Combat-view polish** (autoplay rework §D.28) — untouched; the loop uses the view as-is.
- **Visual polish** — Trail/Prep ship minimal-but-complete per user (functional first).

---

## 2. The gap today

| Piece | `file.py:line` | State |
|---|---|---|
| Run model (loop state + `current_node`/`mark_current_node_cleared`/`advance_to_next_node`) | `game/models.py:697-820` | ✅ ready |
| Route builder | `game/route.py:338 build_route()` | ✅ |
| Encounter gen | `game/encounter.py` + `tools/playtest/_common.py` `generate_fight/reward/challenge`, `generate_boss_encounter` | ✅ (used by dev_harness) |
| Economy | `game/economy.py` `apply_node_income`/`grant_fight_tempest`/`try_rank_up_with_amber`/`buy_champion`/`sell_champion` | ✅ |
| Shop | `game/shop.py` `refresh_shop`/`reroll_shop`/`buy_from_shop`/`generate_supply_offer`/`take_supply_champion` | ✅ |
| Save/load | `game/save.py` (T.14, atomic, schema-gated) | ✅ |
| Weather cache + refresher | `api/cache.py` `WeatherCache`, `api/refresher.py` (3-stream tick) | ✅ but **unwired to UI** |
| Combat seam | `ui/combat_playback.py` `CombatSession(... positions, run_mods, node_id, map_effect_id)` | ✅ |
| Combat view | `ui/views/combat.py:254 build_combat_view(page, session, on_exit)` | ✅ but `on_exit()` **drops the result** |
| Menu | `ui/views/menu.py:44 build_menu_view(... on_new_run, on_continue, save_exists)` | ✅ but New Run/Continue → `_noop` (`main.py`) |
| Dev-harness reference wiring | `ui/views/dev_harness.py:480-538` | ✅ canonical `CombatSession` build to mirror |
| `run_init.py` | — | ❌ create (10a) |
| Trail / Prep / Reward / Summary views | — | ❌ create |
| `viz/route_map.py`, `viz/run_summary.py` | `viz/__init__.py` only | ❌ create |
| T.23 plan doc | `docs/design/tasks/t23_prep_formation_snapshot_plan.md` | 🔴 **drift** (pre-V.62 API) |

---

## 3. Architecture

`ui/` imports `game/` + `viz/` + `api/`, never the reverse (V.1). Views are
`page.views`-stack route handlers (CLAUDE.md Flet conventions). One `Run` holds all
state. The dev_harness (`dev_harness.py:480-538`) is the **reference producer** — the
real Trail→Prep flow builds the **identical** `CombatSession`; mirror it.

### 3.1 RunStart (10a) — `game/run_init.py` + `ui/views/run_start.py`
- `run_init.new_run(seed) -> Run`: `build_route()`; set node 1 `CURRENT`; `amber=10`,
  `tempest_rank=1`, `status=IN_PROGRESS`; offer = seed-deterministic 3 champions
  (Tier 1–2) via the **encounter seed helper** (`encounter.derive_seed`) — **no RNG
  outside seeded `Random`** (V.2). Player pick appends to `roster`. First shop =
  `shop.refresh_shop(run)` (auto-populates 5 slots).
- Pure-logic offer generation lives in `run_init.py` (Flet-free, testable); the view is
  presentation only.

### 3.2 Trail (11a) — `viz/route_map.py` + `ui/views/trail.py`
- **`viz/route_map.py`** (graded Canvas viz): `build_route_map(run, weather_lookup,
  on_select) -> ft.Control`. `flet.canvas`: nodes as `cv.Circle` along a horizontal
  line (`cv.Line` behind), state-tinted (cleared/current/upcoming), weather icon/label
  per node, boss node marked. Minimal visual, **functionally complete** (all nodes,
  weather, state, selection). Manual hit-test via transparent overlay buttons (per
  CLAUDE.md canvas convention — no gesture math).
- **Live weather:** Trail owns a `WeatherCache(city_ids)` + `Refresher` (T.7) started on
  open, stopped on exit. Reads are non-blocking; missing → `CacheState.UNKNOWN` shows the
  city `default_weather` placeholder (views_spec §5.6 fallback = Clear). **All HTTP on the
  refresher's worker thread** (V.4) — never block the main thread; `page.update()` on the
  refresher callback when an entry flips LIVE.
- **Node focus panel:** weather-favor (affinity stat pack for node weather) + affinity-clash
  (predator/prey vs previewed enemies) via `weather_effects.py`; enemy preview from the
  node's deterministic encounter (`generate_*` by `(seed, node_index, stage)`).
- **Team summary:** roster portraits/role/HP; Amber/tempest-rank/bench counts.
- Actions: **Play Next Encounter** (current unresolved only) → Prep; **Save & Exit** →
  autosave + back to menu.

### 3.3 Prep (23a) — `ui/views/prep.py` (full economy)
- Layout per views_spec §6.3: top bar (node/weather/Amber/back); center hex board
  (`flet.canvas` 10×7, reuse combat board geometry helpers); left roster+bench; right
  enemy-preview + shop; bottom Auto-Place / Reset / Start-Combat.
- **Placement:** drag/drop (or tap-select) onto **allied deployment zone** cells; one piece
  per cell. Produces `team_positions: dict[champion_id → (q,r)]` → fed to
  `CombatSession.positions` (V.62). **Auto-Place** = default formation (positions=None
  semantics, byte-identical). Validation = the V.62 engine path (on-board, no-dup); the
  **deployment-zone + roster-id** team-only checks are the T.23 wrapper (§3.3.1).
- **Economy:** shop panel calls `buy_from_shop`/`reroll_shop`/`sell_champion`/
  `take_supply_champion`; bench↔field swaps mutate `roster`/`bench`; team-size cap =
  `tempest_rank` (field cap); rank-up via `try_rank_up_with_amber`. Affordability +
  3-copy-merge feedback from `champion_copies`/`level_from_copies`. **All mutations go
  through `game/economy.py`/`game/shop.py`** — Prep computes nothing.
- **Stat tooltips:** reuse the combat-view inspect renderer (`render_for`) for raw + derived
  stats.
- **Start Combat:** builds `CombatSession(team, enemies, weather, run_mods=
  RunModifiers.from_run(run), node_id, map_effect_id, positions=team_positions)` —
  **identical shape to `dev_harness.py:537`** — and pushes the combat view.

#### 3.3.1 T.23 team-positions wrapper (the only T.23 *engine-side* remainder)
V.62 already overrides spawns for both sides. T.23's residue = a **team-only validated
wrapper**: validate every key ∈ current `team` roster ids + every cell ∈ the allied
deployment zone, before handing to `build_combat`. Location decision in §4.

### 3.4 Combat-result-out + Reward (15a) — edit `ui/views/combat.py`, new `ui/views/reward.py`
- **Seam fix (§4):** combat view currently `on_exit()` drops the `BattleResult`
  (`combat.py:806-830`). The loop needs it (won? + per-piece damage for the summary
  BarChart). Thread it out: `on_exit(result: BattleResult)`. Dev_harness passes a
  result-ignoring lambda (back-compat).
- **Reward step:** on combat end → `run.battle_log.append(result)`;
  `economy.apply_node_income(run, won, node_index)` (+3 base / win bonus / interest);
  `economy.grant_fight_tempest(run)`; `run.mark_current_node_cleared()`. Thin reward panel
  shows outcome + Amber gained + tempest progress + Continue. On a **loss** → run
  `status=DEFEAT` → Summary. On win → `run.advance_to_next_node()` (→ `VICTORY` if last
  node) then autosave → Trail (or Summary if terminal).

### 3.5 Summary (13a) — `viz/run_summary.py` + `ui/views/summary.py`
- **`viz/run_summary.py`** (graded BarChart viz): `build_run_summary(run) -> ft.Control`
  using `ft.BarChart` — **damage per battle** from `run.battle_log` (`BattleResult` damage
  totals). Outcome banner (Victory/Defeat), nodes cleared, final Amber/rank. Return-to-menu.

### 3.6 Routing + Continue (15b) — edit `main.py`
- Replace `_noop` New Run → `run_start` flow; Continue → `save.load_run` → Trail.
- `page.views` stack: menu → run_start → trail ⇄ prep → combat → reward → (trail | summary)
  → menu. `on_view_pop` unwinds; stop combat autoplay + Trail refresher on pop (extend the
  existing `_pop` autoplay-stop).
- **Autosave** each node boundary (after reward advance, on Save&Exit) via
  `save.save_run` (atomic, V.36). `save_exists` already plumbed to light Continue.

### 3.7 Cross-task seams / wrinkles
- **`run_mods` for the real flow:** pass `RunModifiers.from_run(run)`
  (`augments.py:158`) so combat sees live augments + shares `augment_state` by ref (V.18);
  the combat view runs on a **deep clone** of run_mods (V.55) so no side effects leak.
- **Determinism:** node encounters + champion offer + shop derive from `run.seed`
  (+ node/channel) via seeded `Random` — re-resolving a node is byte-identical (V.2), so
  Continue-after-load reproduces the same fight.
- **Boss nodes:** `CombatSession.map_effect_id` carries the boss board effect; the combat
  view already wires `attach_map_effect`. Trail/Prep just set it from `generate_boss_encounter`.

---

## 4. Decisions

1. **Combat-result seam:** change `on_exit()` → `on_exit(result: BattleResult)` rather than
   re-resolving in the loop. *Rationale:* the view already holds the resolved result;
   re-resolving wastes a full sim. Dev_harness adapts with a 1-arg lambda. **Proposed.**
2. **T.23 team-positions wrapper location:** put the validated team-only wrapper
   (`validate_team_positions(team, positions, zone)`) in **`game/loadout.py`** (the existing
   content↔combat boundary) — keeps Flet-free, testable, reusable by Prep + tests. *(Alt:
   `game/combat/resolve.py`; loadout is the better home — it's the team-shaping seam.)*
   **Proposed.**
3. **Live-weather lifecycle owner:** Trail owns the `Refresher`; it is **started on Trail
   open, stopped on pop/Save&Exit**, and the cache instance lives on the run-shell (so it
   survives Trail↔Prep↔Combat without refetch). *(Alt: app-shell-owned for whole run; defer
   — Trail-owned is simpler for MVP and weather only surfaces in Trail/Prep.)* **Proposed.**
4. **Deployment zone:** allied zone = left half of the board (`q < BOARD_WIDTH // 2`),
   matching `assign_spawns` left-pack default. **Proposed** (confirm in §7).
5. **Augment picks:** no augment-selection UI this slice; `active_augments` stays empty
   unless seeded. Combat honors any present. **Proposed** (confirm §7).

---

## 5. Authored values
- Starting Amber **10**, starting rank **1**, champion offer **3** (Tier 1–2), first shop
  **5** slots — all per SPEC §G "Run-start conditions" (already encoded in economy/shop;
  no new numbers).
- Deployment zone = left half (`q < 5` on the 10-wide board) — tunable, first-pass.
- No new combat/economy constants. (This slice authors **layout**, not balance.)

---

## 6. Content / roster audit + reconciliation

- **T.23 plan doc is drifted (🔴).** `t23_prep_formation_snapshot_plan.md` cites
  `game/combat.py` (now the `game/combat/` package) and
  `resolve_combat(team_positions=...)` — but the landed primitive is **V.62
  `build_combat(positions=)` + `CombatSession.positions`** (both sides, validated,
  byte-identical when `None`). **Reconcile:** this plan supersedes it; T.23's *remaining*
  scope is only the §3.3.1 team-only wrapper + the Prep UI. **V-guard:** no new invariant
  needed (V.62 already guards the engine path); the fix is documentary — mark the old plan
  superseded in §10.
- No code-vocabulary drift in scope (no new tags/registries/rosters — pure UI).

---

## 7. Open questions

**Resolved here (overridable):**
- Combat-result via callback arg (D1); wrapper in `loadout.py` (D2); Trail-owned refresher
  (D3); left-half deployment zone (D4); no augment-pick UI (D5).

**Still open / confirm before/early in build:**
- **Q1 (D4):** deployment zone = strict left-half, or a narrower back-2-columns zone for
  tactical clarity? (First-pass left-half; cheap to tune.)
- **Q2 (D5):** is empty-augments acceptable for the MVP loop, or seed a default starter
  augment so the augment path is exercised end-to-end? (Lean empty; combat path is already
  covered by sims.)
- **Q3:** Continue granularity — autosave **every node** only, or also on every Prep
  purchase? (Lean per-node; purchases are re-derivable mid-Prep and per-node keeps saves
  cheap.)

**Deferred:** augment-pick screen (T.31-UI), combat-view autoplay rework (§D.28),
Trail/Prep visual polish, route-map richness beyond the node-line.

---

## 8. Test plan

Logic is testable; views are not (CLAUDE.md "test logic only"). Targets:
- **`run_init`** (`tests/game/test_run_init.py`): `new_run(seed)` deterministic — same seed
  ⇒ same offer + route + first shop; Amber 10 / rank 1 / node-1-CURRENT invariants;
  fixed-seed byte-identical (V.2).
- **T.23 wrapper** (`tests/game/test_loadout.py` or `tests/game/test_prep_positions.py`):
  valid team_positions preserved at tick 1; off-zone / dup-cell / unknown-id / missing-id
  rejected with clear errors; `None` ⇒ default formation byte-identical (V.62 regression).
- **`viz/route_map`** + **`viz/run_summary`** (`tests/viz/`): pure builders return the
  expected node/bar **data** for a fixture Run (assert structure/counts, not pixels).
- **Loop wiring** (`tests/game/` integration-style, Flet-free where possible): a scripted
  run — new_run → resolve node → apply_node_income → advance — reaches VICTORY/DEFEAT and
  round-trips through `save_run`/`load_run` (V.36) identically.
- **Determinism guard:** new_run + node encounter under fixed seed, `workers=1`,
  byte-identical across two runs (V.2/V.14).
- **Combat-seam regression:** dev_harness still opens combat with the new `on_exit(result)`
  signature (1-arg lambda) — existing combat-view tests stay green.

---

## 9. Acceptance criteria

**10a:** New Run builds a valid in-progress `Run` (route, picked champion, Amber 10, first
shop, rank 1) deterministically; menu New Run reaches a Trail stub. Tests green.
**11a:** Trail renders all route nodes (state/weather/selection) on Canvas; live weather
populates without blocking the main thread (V.4); node focus + team summary correct;
Play-Next opens Prep for the current node; Save&Exit autosaves.
**23a:** Prep allows full placement (drag + Auto-Place + Reset) within the deployment zone,
bench↔field, and shop buy/sell/reroll/supply through the economy backend; Start Combat
builds a `CombatSession` identical in shape to the dev-harness producer with
`positions=team_positions`; invalid placement cannot start (clear error).
**15a:** Combat end threads `BattleResult` to the loop; income/tempest applied, node marked
cleared + advanced, autosaved; reward panel shows outcome; loss → Summary.
**13a:** Run-end Summary shows a `BarChart` of damage-per-battle + outcome; returns to menu.
**15b:** Full menu→…→menu loop runs; Continue loads a saved run into Trail and resumes;
refresher started/stopped with Trail; all tests green.

---

## 10. SPEC changes needed (for `/spec`)

- **§T rows — flip status + refresh files-cell to landed reality:**
  - **T.10** → `🟡 WIP`/`✅` on land. Files: `game/run_init.py`, `ui/views/run_start.py`,
    `tests/game/test_run_init.py`, `docs/live/systems/ui.md`.
  - **T.11** → status flip. Files: `viz/route_map.py`, `ui/views/trail.py`,
    `tests/viz/test_route_map.py`. Note: live weather via T.7 refresher.
  - **T.13** → status flip. Files: `viz/run_summary.py`, `ui/views/summary.py`,
    `tests/viz/test_run_summary.py`.
  - **T.15** → status flip. Files: `main.py` (routing + autosave + Continue).
  - **T.23** → status flip; **rewrite goal-cell** to: "Prep-side full economy view +
    team-only `team_positions` validated wrapper (deployment-zone + roster-id) over the
    landed V.62 `positions` primitive." Files: `ui/views/prep.py`, `game/loadout.py`,
    `tests/game/test_prep_positions.py`.
- **New §V invariants:**
  - **V.NN (loop-shell):** the run loop never computes combat/economy/weather — `ui/`
    views mutate `Run` only through `game/economy.py`/`game/shop.py`/`game/run_init.py`
    and resolve only through `resolve_combat`/`CombatReplay` (extends V.1/V.56). Guards
    re-introducing logic into views.
  - **V.NN (combat-result seam):** the combat view surfaces its `BattleResult` to the
    producer via the exit callback; the producer (not the view) applies node income +
    progression. Guards double-resolve / view-owns-economy drift.
  - **V.NN (autosave atomicity):** every node-boundary autosave goes through
    `save.save_run` (atomic, V.36) — no ad-hoc serialization in views.
  - **V.NN (refresher lifecycle):** the Trail-owned `Refresher` is started on open and
    **stopped on pop/exit** (no leaked worker threads); all weather HTTP stays off the main
    thread (re-asserts V.4 at the UI seam).
- **§B backprop:** none (no bug found); record the T.23-plan-doc drift as a documentary
  reconciliation only.
- **§D:** mark the loop-shell gap resolved; note augment-pick UI + Trail/Prep polish still
  deferred (§D.27/§D.28 unaffected).
- **Implementation Order:** insert `T.10 → T.11 → T.23 → T.15(reward) → T.13 → T.15(wire)`
  into the UI-phase chain (replacing the placeholder `T.10 → T.15 → T.23`).
- **Supersede note:** mark `t23_prep_formation_snapshot_plan.md` superseded by this doc
  (§6 drift).

---

## 11. LIVING docs to update (build must touch on landing)

- **`docs/live/systems/ui.md`** — grow from "menu + combat view" to the full loop: add
  RunStart / Trail / Prep / Reward / Summary sections, the `Run`-lifecycle + autosave/
  Continue path, the refresher lifecycle, and the `CombatSession` producer note (dev-harness
  *and* Prep). Flip the doc's status header (🔶/partial → ✅ for T.10/11/13/15/23).
- **`ARCHITECTURE.md`** — add the view-stack/run-loop map (page.views flow + which `game/`
  modules each view calls) if not already covered.
- **New `docs/live/systems/` entry not required** — UI doc covers it; route-map/summary viz
  are thin builders documented inline in ui.md.
- Journal entry on landing (build step) with the Process-notes + prompting-strategy section
  (CLAUDE.md mandate), incl. the T.23-plan-drift catch.
