# T.42 — Augment & Supply node UI + non-fight run-loop dispatch

> **Status:** NEW rows — needs `/spec` to add **T.42a** + **T.42b** to §T (and the
> invariants/§D updates in §10). Split along a real seam (see §0).
> **Depends:** T.31 (augment backend ✅), T.22 (SUPPLY backend ✅), T.15a/T.38
> (run-loop + `apply_node_result` orchestrator ✅), T.11 (Trail dispatch ✅),
> T.23a/T.40 (Prep view + panels the augment view mirrors ✅), T.41 (`describe`/
> name+blurb render ✅). **All deps are built** — this is pure wiring over a
> finished backend.
> **Resolves:** §D.29(1) "augment-pick UI — no augment-selection screen; owner: a
> future T.31-UI task". Also closes the parallel SUPPLY-node dead-path (same gap,
> undocumented in §D — added as §B backprop, see §6/§10).
> **Design source-of-truth:** SPEC §T.31 / §T.22 rows; `effect_systems_design.md`
> §9 (augment model); `docs/live/systems/ui.md` (view taxonomy — Trail §32, Prep
> §93, Reward §202); `docs/design/tasks/t31_augment_system_plan.md`;
> `augment_catalog.md`. **What this plan adds beyond them:** the offer→pick→apply
> UI + the *non-fight node resolution seam* the run loop never grew (every node
> today routes to fight-prep), plus a small backend extension letting the offer
> support **N rerolls** (awarded/banked), not just one.

---

## 0. Substep split

Real seam: **augment view + the shared non-fight-node dispatch/resolution
machinery** vs **supply view (a second thin producer on the same seam)**.

| Substep | Ships | Independent? |
|---|---|---|
| **T.42a** | `reroll_count` backend extension + `augments.reroll_augment_offer` + `economy.resolve_nonfight_node` (the shared seam) + `ui/views/augment.py` + `main.py` AUGMENT dispatch. SUPPLY stays routed to fight-prep (pre-existing bug, unchanged — interim, like T.10's `_push_trail_stub`). | Yes — augment nodes fully playable; sims unchanged. |
| **T.42b** | `ui/views/supply.py` (1-of-5 free recruit) + flip `main.py` SUPPLY branch onto the T.42a seam. Backend (`generate_supply_offer`/`take_supply_champion`) already ✅. | Yes — depends only on T.42a's `resolve_nonfight_node`. |

`b` depends on `a` (reuses `resolve_nonfight_node` + the dispatch skeleton).

---

## 1. Scope

**In (T.42a):**
- Extend `augment_seed` + `generate_augment_offer` from a **binary** `rerolled:
  bool` to `reroll_count: int` (backward-compatible mapping — see §3.1). Backend
  becomes capable of >1 reroll for banked/awarded rerolls.
- `augments.reroll_augment_offer(run, node_index, stage_index) -> list[Augment] |
  None` — a game/ helper owning reroll bookkeeping (1 base free + `augment_state`
  banked, consumes one, returns the new offer or `None` when exhausted). Keeps the
  view Flet-free of game logic (V.63).
- `economy.resolve_nonfight_node(run) -> NodeResultSummary` — the single game/
  orchestrator for AUGMENT/SUPPLY: `mark_current_node_cleared` +
  `advance_to_next_node`, no income/tempest/Hearts (mirrors the sim). Parallels
  `apply_node_result` (V.69) for non-combat nodes.
- `ui/views/augment.py` — 1-of-3 offer cards (name/quality/scope/blurb via T.41
  `describe`), Reroll (shows remaining), Pick → `apply_augment` +
  `resolve_nonfight_node` + `save_run` → Trail.
- `main.py`: branch `on_play_next` on `node.node_type` — AUGMENT → new augment
  producer; fight-types unchanged → `_push_prep`.

**In (T.42b):** `ui/views/supply.py` (1-of-5 free recruit → `take_supply_champion`
+ `resolve_nonfight_node`); `main.py` SUPPLY branch.

**Out (why):**
- Multi-reroll *balance* (Amber cost, per-node reroll caps) — **out**: user chose
  "single free reroll normally"; backend gains *capability* only, tuning deferred
  to §D.
- Non-fight-node Amber income — **out**: the sim grants none on augment nodes;
  matching it avoids a balance + determinism decision here (flag in §7).
- New augment/supply *content* — **out**: rosters ship complete (T.31/T.22).
- Visual polish beyond functional cards — **out** (D.29(2) "functional first").

---

## 2. The gap today

| Piece | `file.py:line` | State |
|---|---|---|
| Augment offer/apply backend | `game/augments.py:1020` `generate_augment_offer`, `:1066` `apply_augment` | ✅ built, tested |
| Combat honors augments | `game/augments.py:1086` `apply_run_augments` via `RunModifiers` | ✅ |
| Canonical offer→pick→apply flow | `tools/playtest/sim_run.py:278` `_resolve_augment_node` | ✅ (CLI only) |
| SUPPLY backend | `game/shop.py:120` `generate_supply_offer`, `:136` `take_supply_champion` | ✅ built, tested |
| **In-game augment-pick view** | `ui/views/` — absent | ❌ **missing** |
| **In-game supply view** | `ui/views/` — absent | ❌ **missing** |
| **Node-type dispatch** | `main.py:135` `on_play_next=lambda node: _push_prep(...)` | 🔴 **drift** — routes *every* node, incl. AUGMENT/SUPPLY, to fight-prep |
| **Non-fight node resolution** | — no orchestrator; only `economy.apply_node_result` (fight-only, `:224`) | ❌ **missing** |
| Any UI caller of the offer API | `grep generate_augment_offer src/ui` → 0 hits | ❌ |
| Reads `active_augments` | `ui/views/prep.py:614-617` (display only) | ✅ but always empty (nothing fills it) |
| Reroll seed | `game/encounter.py:557` `augment_seed(..., rerolled: bool)` — binary channel `CH_AUGMENT`/`CH_REROLL` | 🔶 single-reroll only |
| Trail marks non-fight | `ui/views/trail.py:60` `_NO_FIGHT={AUGMENT,SUPPLY}` → "No fight here", but still calls `on_play_next` | 🔶 knows, doesn't dispatch |

Net: `Run.active_augments` never populated in-game → every TEAM/PIECE augment
effect silently no-ops (`apply_run_augments` early-returns on empty). Confirmed
against SPEC §D.29(1).

---

## 3. Architecture

### 3.1 Reroll-count seed extension (backend, verified against code)

Current (`encounter.py:557`):
```python
def augment_seed(run_seed, node_index, rerolled: bool = False) -> int:
    channel = CH_REROLL if rerolled else CH_AUGMENT   # CH_AUGMENT=1, CH_REROLL=3
    return derive_seed(run_seed, node_index, channel)
```
The two channels are the *only* two draws — structurally binary. Precedent for N:
`shop_seed` (`:569`) folds `reroll_count` into the node arg via `SHOP_REROLL_STRIDE`.

**Proposed** (`reroll_count: int = 0`, back-compat-preserving so **no
determinism re-baseline**):
```python
AUGMENT_REROLL_STRIDE: Final[int] = 1000
def augment_seed(run_seed, node_index, reroll_count: int = 0) -> int:
    if reroll_count == 0:
        return derive_seed(run_seed, node_index, CH_AUGMENT)          # == legacy False
    if reroll_count == 1:
        return derive_seed(run_seed, node_index, CH_REROLL)           # == legacy True (byte-identical)
    return derive_seed(run_seed, node_index * AUGMENT_REROLL_STRIDE + reroll_count, CH_REROLL)  # ≥2 new
```
- `reroll_count ∈ {0,1}` reproduce the exact legacy sub-seeds → existing augment
  sim tests stay byte-identical (V.2/V.14). Only newly-reachable `≥2` draws are net-new.
- `generate_augment_offer(..., rerolled: bool)` → `reroll_count: int = 0`. Migrate
  the one caller `sim_run.py:318` (`rerolled=True` → `reroll_count=1`) + the
  `_prompt_augment` loop (track an int, not a bool).
- **Note:** `supply_seed` (`:563`) also uses `CH_REROLL` but SUPPLY has no reroll
  in scope — leave `supply_seed` untouched (no collision: augment uses node_index,
  strided space is augment-only and SUPPLY never rerolls).

### 3.2 Reroll bookkeeping (game/, keeps view pure — V.63)

`augment_state` already carries `banked_rerolls` (set by the RARE augment at
`augments.py:433`). New helper:
```python
def reroll_augment_offer(run, node_index, stage_index) -> tuple[list[Augment], int] | None:
    """Consume one reroll (base free, then banked); return (new_offer, rerolls_left) or None."""
```
- Base free reroll = 1 per node visit; banked = `run.augment_state.get("banked_rerolls",0)`.
- The view tracks the current `reroll_count` (starts 0); each reroll calls this,
  which increments an in-view counter, decrements `banked_rerolls` once the free
  one is spent, and returns `generate_augment_offer(run.seed, node_index,
  stage_index, reroll_count=N, exclude=tuple(run.active_augments))`.
- Returns `None` when no reroll available → view disables the button.
- **RNG-free selection** (deterministic seed only) — V.2/V.14 hold.

### 3.3 Non-fight node resolution seam (game/)

`economy.resolve_nonfight_node(run) -> NodeResultSummary` mirrors
`apply_node_result` (`:224`) shape but for non-combat nodes:
- `run.mark_current_node_cleared()` + `run.advance_to_next_node()` (both exist,
  `models.py:837/845`).
- No `battle_log` append, no income, no tempest, no Hearts (no combat occurred).
- Returns a `NodeResultSummary` (reuse the dataclass; fields default/zero) so the
  producer has a uniform "what happened" struct + `terminal` flag (a non-fight
  node is never last, but keep the field for symmetry).
- **V.63 compliance:** the view mutates `Run` only through `apply_augment` /
  `take_supply_champion` (the pick) + `resolve_nonfight_node` (the advance) —
  never inline.

### 3.4 Augment view (`ui/views/augment.py`, T.42a)

Shape mirrors `reward.py` (`:46` `build_reward_view` signature style):
```python
def build_augment_view(page, run, node, *, on_done: Callable[[], None]) -> ft.View
```
- Derive `node_index = node.index`, `stage_index = route.stage_of(node.index).index`.
- Initial `offer = generate_augment_offer(run.seed, node_index, stage_index,
  exclude=tuple(run.active_augments))`.
- Render 3 cards: name + quality chip (color via `ui/iconography.py`/theme quality
  map) + scope tag + blurb (T.41 `describe`, V.78-80). Pick button per card.
- Reroll button (label `Reroll (N left)`), disabled when `reroll_augment_offer`
  returns `None`. Skip button (mirrors CLI `_prompt_augment` skip → apply nothing).
- On Pick: `apply_augment(run, chosen)` → `resolve_nonfight_node(run)` →
  `save_run` (V.65 node-boundary autosave) → `on_done()` (producer routes to Trail).
- On Skip: `resolve_nonfight_node` + save + `on_done()` (no augment applied).

### 3.5 Supply view (`ui/views/supply.py`, T.42b)

Same skeleton, 1-of-5 free recruit:
- `offer_ids = generate_supply_offer(run.seed, node.index, run.tempest_rank)`
  (`shop.py:120`; rank-gated per V.74).
- Render champion cards (reuse `ui/components/champion_card` + `describe`); Take →
  `take_supply_champion(run, id)` (`shop.py:136`) → `resolve_nonfight_node` + save
  → Trail. Skip allowed.

### 3.6 main.py dispatch

Replace the blanket `on_play_next=lambda node: _push_prep(page, run, node)`
(`main.py:135`) with a type branch:
```python
def _play_node(node):
    if node.node_type == NodeType.AUGMENT:   _push_augment(page, run, node)
    elif node.node_type == NodeType.SUPPLY:  _push_supply(page, run, node)   # T.42b; T.42a: falls through to _push_prep w/ TODO
    else:                                    _push_prep(page, run, node)
```
- `_push_augment` builds `build_augment_view(..., on_done=lambda: <pop + fresh Trail>)`,
  mirroring `_finish_combat._continue`'s Trail re-push.
- **Trail wrinkle:** `trail._play_next` (`trail.py:369`) locks node weather before
  dispatch — a harmless no-op for non-fight nodes (no combat reads it). Leave as is;
  note in the build.

### Cross-task seams
- **V.69 (fight orchestrator)** — untouched; `resolve_nonfight_node` is its
  non-combat sibling, not a replacement.
- **V.65 (node-boundary autosave)** — the augment/supply pick is an *interactive*
  mutation like the CHALLENGE Recruit (B.32), so the producer saves **after** the
  pick, not before — same discipline that fixed B.32.
- **RunModifiers seam** — once `active_augments` is populated, Prep→Combat already
  threads it (`CombatSession.run_mods`), so effects light up with zero combat-side
  change. Verified: `apply_run_augments` reads `run_mods.augments`.

---

## 4. Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | `reroll_count: int` with `{0,1}` = legacy channels, `≥2` strided | Back-compat → **zero determinism re-baseline**; satisfies "backend capable of more rerolls". |
| D2 | Reroll bookkeeping in game/ (`reroll_augment_offer`), not the view | V.63 — view computes no game logic; testable headless. |
| D3 | 1 base free reroll + `augment_state["banked_rerolls"]` | Matches user intent (single free normally, more when awarded); the banked key already exists (`augments.py:433`) but was dead — this makes it live. |
| D4 | Non-fight nodes grant **no** income/tempest | Mirrors `sim_run` (no `apply_node_income` on augment nodes); avoids an unspecified balance+determinism call. Flagged §7. |
| D5 | Skip allowed on both views | Mirrors CLI `_prompt_augment` skip; lets a player decline a PIECE augment with no valid target. |
| D6 | New view files, not folded into Prep/Reward | Distinct node semantics (pick, not fight-prep / post-fight); clean producer swap. |

---

## 5. Authored values

Minimal — content already authored. Only new constant:
- `AUGMENT_REROLL_STRIDE = 1000` (mirrors `SHOP_REROLL_STRIDE`; large enough that
  `node_index * STRIDE + reroll_count` never collides across nodes for realistic
  reroll counts). First-pass, not tunable-sensitive (determinism spacing only).

---

## 6. Content/roster audit + reconciliation

- **No roster drift** — augment/supply pools ship complete (T.31/T.22); this task
  adds no content. `AUGMENT_REGISTRY` id-validation already guarded (V.17).
- **Drift caught → §B backprop:** `main.py:135` routed **every** node type to
  fight-prep, so AUGMENT/SUPPLY nodes were unreachable-as-designed — augment nodes
  silently gave nothing, exactly the class of "authored-but-never-applied" defect
  as B.31 (orphaned node rewards). Propose a new **§B** entry documenting it, with
  a **§V guard** (§10) that non-fight nodes must resolve through
  `resolve_nonfight_node` so a future dispatch refactor can't re-orphan them.

---

## 7. Open questions

**Resolved-here (overridable):**
- **RQ1** Non-fight nodes give no Amber (D4). Override → add base income+interest
  via a seeded `apply_node_income`-style call, but that needs a determinism channel
  decision.
- **RQ2** Skip allowed (D5). Override → force-pick (TFT-style) if you'd rather
  augments be mandatory.
- **RQ3** Reroll is free (base) + banked only — no Amber cost (user's call).

**Still open / deferred (→ §D):**
- **OQ1** Multi-reroll *economy* (Amber cost, per-node caps, UI for buying
  rerolls) — backend now capable; balance deferred.
- **OQ2** Augment/supply view *visual polish* (icons, animations) — functional-first.

---

## 8. Test plan

**T.42a:**
1. `augment_seed` back-compat: `augment_seed(s,n,0)==<legacy False>` and
   `augment_seed(s,n,1)==<legacy True>` byte-identical (pin literal values);
   `reroll_count≥2` distinct from both and from each other. **Fixed-seed,
   `workers=1`.**
2. `generate_augment_offer(reroll_count=k)` deterministic + distinct per `k`;
   `exclude` honored; Prismatic still stage≥2 gated.
3. `reroll_augment_offer`: 1 free reroll from a fresh node; `banked_rerolls=2` →
   3 total; returns `None` when exhausted; decrements `banked_rerolls` only after
   the free one; **RNG-free** (same run/node → same sequence).
4. `resolve_nonfight_node`: current node → CLEARED, `current_node_index` advances,
   no `battle_log`/income/tempest mutation; idempotent guard (already-cleared).
5. Regression: full augment sim (`sim_run --augment-policy`) byte-identical to
   pre-change (the migrated `reroll_count=1` path).
6. **Existing suite green** (1524+ tests), ruff clean.

**T.42b:**
7. `resolve_nonfight_node` reused (no second orchestrator).
8. Supply offer determinism unchanged (rank-gated, V.74) — no new seed path.

UI: no Flet render tests (repo policy — logic only); the view producers are
covered via the game/ seam functions above.

---

## 9. Acceptance criteria

**T.42a**
1. Playing an AUGMENT node opens an offer screen; picking appends to
   `Run.active_augments` and the augment's effect is live in the next combat
   (verify a TEAM augment changes a stat via `stat_breakdown`).
2. Reroll works once free; a banked reroll grants a second; button disables when
   exhausted; every offer deterministic for a fixed seed.
3. After pick/skip the node is CLEARED, the run advances, and an autosave captures
   it (Continue resumes past the node with the augment retained).
4. Non-augment nodes route exactly as before (no fight-flow regression).
5. All augment sims byte-identical; suite green; ruff clean.

**T.42b**
6. Playing a SUPPLY node opens a 1-of-5 free-recruit screen; Take adds the
   champion (auto-level) at no Amber; resolves + advances + saves.
7. Reuses `resolve_nonfight_node` (no duplicate orchestrator).

---

## 10. SPEC changes needed (apply via `/spec` on OK only)

**New §T rows:**
- **T.42a** | Augment node UI + non-fight run-loop seam — `augment_seed`/
  `generate_augment_offer` `reroll_count:int` extension (back-compat {0,1}=legacy,
  ≥2 strided, no re-baseline) + `augments.reroll_augment_offer` (base-free +
  banked) + `economy.resolve_nonfight_node` + `ui/views/augment.py` + `main.py`
  node-type dispatch (AUGMENT); resolves D.29(1). Files: `game/encounter.py`,
  `game/augments.py`, `game/economy.py`, `ui/views/augment.py`, `main.py`,
  `tools/playtest/sim_run.py`, `tests/game/test_augments.py`,
  `tests/game/test_economy.py`, `docs/live/systems/ui.md`. Depends: T.31, T.22,
  T.15a, T.38, T.11, T.40, T.41. Est: **M**. Status: 📋 Plan.
- **T.42b** | Supply node UI on the non-fight seam — `ui/views/supply.py`
  (1-of-5 free recruit via `take_supply_champion`) + `main.py` SUPPLY branch;
  reuses `resolve_nonfight_node`. Files: `ui/views/supply.py`, `main.py`,
  `tests/game/test_economy.py`, `docs/live/systems/ui.md`. Depends: T.42a, T.22.
  Est: **S**. Status: 📋 Plan.

**New §V invariants:**
- **V.NEW-1 (extends V.63):** Non-fight nodes (AUGMENT/SUPPLY) resolve through the
  single game/ orchestrator `economy.resolve_nonfight_node(run)` (mark-cleared +
  advance, no income/tempest/Hearts), and the node's pick mutates `Run` **only**
  through `apply_augment` / `take_supply_champion` — the view computes no game
  logic. Guards the drift that left both node types dead (blanket fight-prep
  dispatch, no orchestrator).
- **V.NEW-2 (amends V.19):** The augment offer + reroll are seed-deterministic via
  `augment_seed(run_seed, node_index, reroll_count)` — `reroll_count ∈ {0,1}`
  reproduce the legacy `CH_AUGMENT`/`CH_REROLL` draws byte-identically, `≥2` fold
  into a strided sub-seed; reroll availability = 1 base free + `augment_state`
  banked/awarded, all RNG-free. Guards determinism as banked rerolls become live.

**New §B entry:**
- **B.NEW [2026-07-01]** Augment (and SUPPLY) nodes were unreachable-as-designed —
  `main.py` routed every node type to fight-prep (`_push_prep`), no non-fight
  orchestrator existed, and no UI ever called `generate_augment_offer` /
  `generate_supply_offer`, so `Run.active_augments` stayed empty and every
  TEAM/PIECE augment silently no-op'd (`apply_run_augments` early-return). Same
  class as B.31 (authored-but-never-applied). **Fix → V.NEW-1** (single non-fight
  orchestrator + type dispatch, T.42).

**§D updates:**
- **D.29(1)** — mark **RESOLVED (T.42a)**.
- Add **D.NEW** — multi-reroll *economy* (Amber cost / per-node caps / buy-reroll
  UI): backend gains N-reroll capability in T.42a, tuning deferred (OQ1).

**Implementation Order:** append `T.42a → T.42b` after the current UI phase tail
(post-T.41), in the run-loop/UI track.

---

## 11. LIVING docs to update (in the build commit)

- `docs/live/systems/ui.md` — new **Augment (T.42a)** + **Supply (T.42b)** view
  sections (mirror the Reward §202 entry shape); update the §476 `main.py app
  shell` dispatch description + the §544 file map; note the non-fight seam.
- No `docs/live/systems/encounter.md` change needed (seed extension is
  back-compat; note the `reroll_count` param if that doc enumerates the seed
  helpers — verify at build).
- Run `/check` after landing each substep.
