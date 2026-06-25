# T.38 — Node-type reward dispatch + Hearts (survivable loss)

> **Status:** NEW §T row (proposed `T.38`; alt id `T.15c` if kept in the routing/reward family).
> **Depends:** T.15a ✅ (reward step `apply_node_result`/V.69 — the seam we extend), T.22 ✅ (economy: `Run.amber`/`tempest`, `Run.inventory`, `grant_tempest`), T.29a ✅ (`generate_reward_loot`/`RewardLoot`), T.21/T.19 ✅ (`generate_challenge`/`ChallengeReward`, `stage_of`). All deps **built** — no unbuilt gate.
> **Resolves:** the orphaned node-type reward payloads (REWARD `RewardLoot`, CHALLENGE `ChallengeReward`) that today are generated and **discarded**; introduces the **Hearts** survivable-loss model (reverses V.69's instant-DEFEAT-on-loss).
> **Design source-of-truth:**
> - SPEC §V.69 (reward step — the branch we revise), §V.64 (result-out seam), §V.65 (autosave), §V.19/§V.2 (seed-determinism), §D.12 (REWARD drop table refine), §D.13 (Amber economy).
> - `src/game/encounter.py` — `generate_reward_loot` (:521), `generate_challenge`→`ChallengeReward` (:611/:778), `node_encounter` dispatch (:902, the discard site), `stage_of` (route.py:390).
> - `src/game/economy.py` — `apply_node_result` (:215), `NodeResultSummary` (:204).
> **What this plan adds beyond them:** a **reward-payload dispatcher** wired into the reward step (the missing "apply" half of generators that already exist), plus the **Hearts** field + loss-survival lifecycle + universal loss-zeroing of unique payouts.

---

## 0. Substep split

Split along a real seam — **content-application vs run-loss-model** — but they interlock (loss-zeroing needs the payouts to exist). User chose **one task together**; keep as one row with two internal phases, each independently testable:

- **Phase A — Reward dispatch:** `generate_node_reward(run_seed, node)` dispatcher in `encounter.py` (returns typed payload), **auto-rewards** (loot/amber/tempest) applied on **win** in `apply_node_result`. No Hearts yet (loss still DEFEAT).
- **Phase B — Hearts:** `Run.hearts` field + save round-trip; loss survives (−1 Heart, advance), `hearts<=0`→DEFEAT; **all unique payouts zero on any loss**; **boss loss → instant DEFEAT** (hard gate, O4).
- **Phase C — Interactive champion recruit:** CHALLENGE `champion_offer` is **not** auto-granted — surfaced in `NodeResultSummary` (pending), the reward view shows **Recruit / Skip**, Recruit calls `economy.recruit_challenge_offer(run, id)` (V.63 — view computes nothing).

Phases B/C depend on Phase A (loss-zeroing + recruit reference the payloads). Ship together; the test plan exercises each phase's acceptance criteria separately.

---

## 1. Scope

**In:**
- `generate_node_reward(run_seed, node) -> NodeReward | None` — type-dispatched reward payload (mirrors `node_encounter`).
- Apply **auto-payloads** to `Run` on win: REWARD loot → `inventory`; CHALLENGE amber + components → `inventory`, `tempest_bonus` → `grant_tempest`. `champion_offer` is **not** auto-applied — surfaced as a pending offer for the interactive recruit (D3).
- **Interactive champion recruit** (O1): `NodeResultSummary.champion_offer` surfaces the pending CHALLENGE offer; reward view shows **Recruit / Skip**; Recruit calls `economy.recruit_challenge_offer(run, id)` (materialize to bench, V.63 — view computes nothing).
- `Run.hearts: int` (default 3) + `to_dict`/`from_dict` round-trip + `__post_init__` range guard.
- Loss path: `hearts-=1`; if `>0` mark-cleared + advance (survive); if `<=0` → `DEFEAT`. **BOSS_FIGHT loss → instant `DEFEAT` regardless of Hearts** (hard gate, O4). **Final-node loss → `DEFEAT`** (O3).
- Loss zeroes **all** unique payouts; base income+interest still granted (no win-bonus).
- `NodeResultSummary` carries `hearts_remaining` + reward payload summary + pending `champion_offer` for the panel.
- Reward view shows Hearts + node-type rewards + Recruit/Skip.

**Out (with why):**
- **REWARD drop-table reweight (§D.12 45/20/15/15/5).** Current `generate_reward_loot` weights (60/25/15) ship as-is; reweight is its own balance pass.
- **SUPPLY/AUGMENT node payloads.** Those are non-combat offer nodes (shop/augment pick) handled by their own views; not fought, so no reward-step payload here.
- **NodeState.FAILED** distinct route-map state for lost nodes — MVP marks lost nodes `CLEARED` (resolved, O2). Adding a FAILED visual is deferred.
- **Hearts-as-resource economy** (buying Hearts, Heart-loss VFX). Just the int + lifecycle this row.

---

## 2. The gap today

| Piece | `file.py:line` | State |
|---|---|---|
| REWARD loot generator | `encounter.py:521` `generate_reward_loot` | ✅ built, ❌ never called in run loop |
| CHALLENGE reward payload | `encounter.py:778` `generate_challenge`→`ChallengeReward` | 🔴 generated then **discarded** (`squad, _reward = …`, `node_encounter` :925) |
| Reward dispatcher | — | ❌ none — `apply_node_result` is type-blind |
| `apply_node_result` | `economy.py:215` | 🔶 generic income+tempest only; no `node.node_type` branch |
| `Run.inventory` sink | `models.py:707` (`dict[str,int]`) | ✅ exists, unused by reward step |
| `Run.hearts` | — | ❌ no field |
| Loss = survivable | `economy.py:234-235` | 🔴 loss → instant `DEFEAT` (V.69) |
| Reward panel rewards/Hearts | `ui/views/reward.py` | 🔶 shows amber/tempest only |

---

## 3. Architecture

### 3a. Reward-payload dispatcher (Phase A)

Mirror `node_encounter` (encounter.py:902). New union + dispatcher **in encounter.py** (keeps reward derivation beside the generators it calls):

```python
@dataclass(frozen=True)
class NodeReward:
    """Applied-on-win payload for a fought node (None for non-reward types)."""
    item_ids: list[str] = field(default_factory=list)   # → Run.inventory
    amber: int = 0                                       # → Run.amber (beyond income)
    tempest_bonus: int = 0                               # → grant_tempest (beyond +2/fight)
    champion_offer: str | None = None                    # → bench (MVP, D3)

def generate_node_reward(run_seed: int, node: "Node") -> NodeReward | None:
    stage = stage_of(node.index)
    match node.node_type:
        case NodeType.REWARD:
            return NodeReward(item_ids=list(generate_reward_loot(run_seed, node.index).item_ids))
        case NodeType.CHALLENGE:
            _squad, r = generate_challenge(run_seed, node.index, stage, node.weather)
            return NodeReward(item_ids=[r.component_offer, r.themed_component],
                              amber=r.amber, tempest_bonus=r.tempest_bonus,
                              champion_offer=r.champion_offer or None)
        case _:
            return None   # FIGHT/BOSS_FIGHT/SUPPLY/AUGMENT → no unique payload
```

**Determinism wrinkle (V.2):** `generate_challenge` re-rolls the *squad* to derive `champion_offer` (offer = `rng.choice(squad)`). It must use **`node.weather`** (the node's `default_weather` — the same value game-logic uses for the fight per V.65, not live API weather) so the re-derivation is byte-identical to encounter time. Re-rolling the squad just to read the reward is wasteful but pure; acceptable for MVP (one extra deterministic roll at node boundary). Channels already isolate it (`CH_REWARD` / `CH_CHALLENGE`).

**Plug-in point:** `apply_node_result` (economy.py:215), **win branch only** (Phase A), after `grant_fight_tempest`:

```python
if won:
    grant_fight_tempest(run); tempest_gained = TEMPEST_PER_FIGHT
    reward = generate_node_reward(run.seed, node)          # node = run.current_node()
    pending_offer = None
    if reward:
        for iid in reward.item_ids: run.inventory[iid] = run.inventory.get(iid, 0) + 1
        run.amber += reward.amber
        if reward.tempest_bonus:
            grant_tempest(run, reward.tempest_bonus); tempest_gained += reward.tempest_bonus
        pending_offer = reward.champion_offer              # surfaced, NOT applied (D3/O1)
    run.mark_current_node_cleared(); run.advance_to_next_node()
```

`champion_offer` is **not** applied here — it is returned in `NodeResultSummary.champion_offer` as a *pending* choice. The reward view presents Recruit/Skip; **Recruit** calls a new game applier `economy.recruit_challenge_offer(run, champion_id) -> bool` (materialize at L1 to bench via `_materialize_champion`; no-op + False if already owned, mirrors `buy_champion`'s owned-guard). This keeps the choice in the view but the mutation in `game/` (V.63). The offer is *not* re-validated against re-derivation — the view passes back the exact id from the summary.

`apply_node_result` currently takes `(run, result)` and reads `node_index = run.current_node_index`. It needs the **`Node`** (for `node_type`/`weather`) — fetch via `run.current_node()` (models.py:782) before advancing. No signature change (still `(run, result)`); the producer seam (V.64) is untouched.

**Cross-task seam:** `node_encounter` (encounter.py:925) keeps discarding `_reward` — that's the *fight-build* path and must stay squad-only. The reward is owned by the new dispatcher at the *resolve* path. Two call sites, same seed ⇒ identical reward; document that they must not diverge (V-guard G2).

### 3b. Hearts (Phase B)

`Run.hearts: int = 3` (models.py, after `difficulty_coefficient`). `__post_init__`: `if self.hearts < 0: raise`. `to_dict`: `"hearts": self.hearts`. `from_dict`: `hearts=payload.get("hearts", 3)` (back-compat — pre-T.38 saves default to 3). `new_run`: relies on the field default (no explicit set needed, but pass `hearts=STARTING_HEARTS` for clarity).

**Loss path rewrite** (`apply_node_result` else-branch):

```python
else:  # LOSS or DRAW (V.60 — draw is non-win)
    run.hearts -= 1
    is_boss = node.node_type == NodeType.BOSS_FIGHT
    is_last = _is_last_node(run, node)                     # no node with index > node.index
    if run.hearts <= 0 or is_boss or is_last:
        run.status = RunStatus.DEFEAT          # terminal: hearts gone OR boss gate (O4) OR final node (O3)
    else:
        run.mark_current_node_cleared()        # resolved (CLEARED, not FAILED — O2)
        run.advance_to_next_node()             # survive → next node
```

**Boss loss = instant DEFEAT (O4):** BOSS_FIGHT is a hard stage gate — losing it ends the run regardless of Hearts (still decrements the Heart for display consistency, but the run is over). **Final-node loss = DEFEAT (O3):** never let `advance_to_next_node`'s "no next node ⇒ VICTORY" relabel a lost final fight as a win — guard with `_is_last_node` *before* advancing. Both bypass the survive branch.

**Loss-zeroing (universal):** the win-only placement of `generate_node_reward`/payload-apply means a loss **never** grants unique payouts — base income+interest already applied above via `apply_node_income(run, won=False, …)` (no win-bonus, economy.py:118). No extra code needed: zeroing is structural (payouts live in the win branch only). State that explicitly in the test (G1).

### 3c. NodeResultSummary + reward view

Extend `NodeResultSummary` (economy.py:204, frozen dataclass): add `hearts_remaining: int`, `item_ids: tuple[str, ...] = ()`, `bonus_amber: int = 0`, `champion_offer: str | None = None`. Reward view (`reward.py`) adds a Hearts stat-row (♥ count, DANGER tint when low) + a rewards block listing dropped items.

**Interactive recruit (Phase C):** when `summary.champion_offer` is set, the view renders a **Recruit / Skip** pair below the rewards. Recruit → `economy.recruit_challenge_offer(run, summary.champion_offer)` then re-render the panel (offer consumed, button row removed); Skip → just dismiss. Continue stays gated behind a resolved offer (or no offer). The view owns only the click→game-call wiring; the bench mutation is `game/` (V.63). On a terminal run (boss/final loss, or VICTORY) there is no pending offer to resolve.

---

## 4. Decisions

- **D1 — Hearts default = 3.** User pick ("Hearts", 3 lives). `STARTING_HEARTS: Final[int] = 3` in `run_init` (or economy). Tunable.
- **D2 — Loss advances (survivable), DEFEAT only at 0 Hearts.** Reverses V.69's instant-DEFEAT. Conscious reversal — the save-scum concern V.69 guarded **dissolves**: loss advances (no re-fight of the same node), so there is no re-prep to scum. Re-prep never happens on loss.
- **D3 — `champion_offer` → interactive Recruit/Skip (O1 resolved).** Not auto-granted. `apply_node_result` surfaces it as `NodeResultSummary.champion_offer` (pending); reward view shows Recruit/Skip; Recruit calls `economy.recruit_challenge_offer(run, id)` → materialize at L1 to `bench` if **not already owned** (`champion_copies` guard), else no-op + False (no Amber refund). The choice lives in the view, the mutation in `game/` (V.63).
- **D4 — Final-node loss → DEFEAT (O3 resolved).** A loss on the last node (no node with greater index) ends the run as **DEFEAT**, never VICTORY. Guard with `_is_last_node` **before** `advance_to_next_node` in the loss branch (else its "no next node ⇒ VICTORY" mislabels a lost final fight).
- **D5 — Boss loss → instant DEFEAT (O4 resolved).** BOSS_FIGHT is a **hard stage gate** — losing it ends the run **regardless of Hearts remaining**. The Heart still decrements (display consistency) but `status=DEFEAT` is forced. Non-boss losses remain survivable while Hearts > 0.

---

## 5. Authored values

| Const | Value | Where | Note |
|---|---|---|---|
| `STARTING_HEARTS` | `3` | `run_init.py` | tunable (D1) |
| REWARD loot weights | 60/25/15 | `encounter.py:534` (existing) | unchanged; §D.12 reweight deferred |
| CHALLENGE amber | `2 × stage_index` | `encounter.py` (existing) | unchanged |
| CHALLENGE tempest_bonus | `+1` | `encounter.py:626` (existing) | unchanged |

No new balance numbers — Phase A wires existing authored values; Phase B adds one int; Phase C reuses the existing `champion_offer` (no new value).

---

## 6. Content/roster audit + reconciliation

- **Drift caught (🔴):** `generate_challenge`'s `ChallengeReward` is **generated and discarded** at `node_encounter` (encounter.py:925) and **never applied** anywhere in the run loop. Git origin: T.21 authored the payload; T.15a's `apply_node_result` shipped type-blind (the wiring was implicitly deferred — `node_income` docstring even says "excludes REWARD loot drops", economy.py:119, and `RewardLoot` docstring says "Added to `Run.inventory` by the run-manager (T.22)" — a wiring that T.22 never delivered). This task closes both.
- **V-guard G2** (below) prevents the reward derivation in the fight-build path and the resolve path from silently diverging.
- No roster/tag drift in scope (no new content vocabulary).

---

## 7. Open questions

**Resolved (user-confirmed):**
- **O1** → **interactive Recruit/Skip** (D3) — reward view gains the offer interaction + `recruit_challenge_offer` applier.
- **O2** → lost node marked **`CLEARED`** (no FAILED state) for MVP.
- **O3** → final-node loss → **DEFEAT** (D4).
- **O4** → boss loss → **instant DEFEAT** regardless of Hearts (D5, hard gate).

**Deferred (§D):**
- REWARD drop-table reweight to §D.12 45/20/15/15/5 (incl. champion-recruit + special tiers).
- Interactive champion recruit UI; Heart-loss VFX / Heart economy.

---

## 8. Test plan

`tests/game/test_economy.py` (extend) + `tests/game/test_encounter.py` (dispatcher):

- **Dispatch (Phase A):**
  - `generate_node_reward` returns `NodeReward` with non-empty `item_ids` for a REWARD node; amber+components+offer for a CHALLENGE node; `None` for FIGHT/BOSS/SUPPLY/AUGMENT.
  - Win on a REWARD node → `inventory` count for the dropped id increments by exactly the loot list (byte-match `generate_reward_loot`).
  - Win on a CHALLENGE node → `amber` += `2×stage`, `tempest` gains the +1 bonus (rank cascade applied), both components land in `inventory`, `champion_offer` is **not** auto-added (stays pending in summary).
  - **Determinism (V.2):** same `(seed, node)` ⇒ identical `NodeReward` across repeated calls **and** identical to the reward `generate_challenge` would produce at encounter time (same `node.weather`). Fixed-seed assert.
- **Hearts (Phase B):**
  - New run → `hearts == 3`.
  - Loss with `hearts>1` on a **non-boss, non-final** node → `hearts-=1`, node CLEARED, advanced to next, `status==IN_PROGRESS`, **no** unique payout in `inventory`, income == base+interest (no win-bonus) — **G1 loss-zeroing**.
  - Loss bringing `hearts` to 0 → `status==DEFEAT`, no advance.
  - Three consecutive losses from full → DEFEAT on the third.
  - DRAW counts as loss (V.60) → costs a Heart.
  - **O3/D4:** loss on the final node with `hearts>1` → `DEFEAT` (not VICTORY), no advance.
  - **O4/D5:** loss on a BOSS_FIGHT with `hearts>1` → `DEFEAT` (Heart decremented but run terminal); a non-boss loss at the same Hearts survives.
- **Recruit (Phase C):**
  - `recruit_challenge_offer(run, id)` on an un-owned champion → materialized at L1 in `bench`, returns True; on an already-owned id → no-op, returns False, bench unchanged.
- **Save round-trip:** `Run.to_dict`→`from_dict` preserves `hearts`; a pre-T.38 payload (no `hearts` key) loads with `hearts==3` (back-compat).
- **Regression:** existing `apply_node_result` win-path tests (income/tempest/advance/VICTORY-on-last) stay green; `node_encounter` squad output **unchanged** (reward-discard path untouched).
- **V-guard G1/G2** asserted (see §10).

No new RNG cadence mechanic (Hearts is a plain counter); determinism rests on the existing seeded channels — assert byte-identical reward across repeated derivation.

---

## 9. Acceptance criteria

**Phase A (dispatch):**
1. `generate_node_reward(run.seed, node)` returns the correct typed payload per node_type; `None` for non-reward types.
2. A REWARD-node win deposits the exact `generate_reward_loot` items into `Run.inventory`.
3. A CHALLENGE-node win grants amber (`2×stage`), +1 tempest bonus, both components to inventory; `champion_offer` surfaced pending (not auto-applied).
4. Reward derivation is seed-deterministic and matches encounter-time (V.2).

**Phase B (Hearts):**
5. `Run.hearts` defaults to 3, range-guarded, round-trips through save (old saves → 3).
6. A non-boss, non-final loss with Hearts remaining decrements Hearts, marks node CLEARED, advances, keeps run IN_PROGRESS.
7. A loss at 1 Heart → DEFEAT; never advances.
8. Any loss grants **zero** unique payouts (only base income+interest).
9. Final-node loss → DEFEAT (O3); BOSS_FIGHT loss → DEFEAT regardless of Hearts (O4).

**Phase C (recruit) + panel:**
10. `recruit_challenge_offer` adds an un-owned champion to bench (True) / no-ops on owned (False).
11. Reward panel shows Hearts remaining + rewards + Recruit/Skip when an offer is pending; recomputes nothing (V.63).

---

## 10. SPEC changes needed (handoff payload — applied only on `/spec` OK)

**§T — new row:**
```
| T.38 | Node-type reward dispatch + Hearts — `encounter.generate_node_reward(run_seed, node) -> NodeReward|None` (type-dispatched: REWARD→`RewardLoot` items, CHALLENGE→amber+components+tempest_bonus+champion_offer; else None), auto-rewards applied **on win** in `economy.apply_node_result` (loot→`Run.inventory`, amber→`amber`, bonus→`grant_tempest`); CHALLENGE `champion_offer` surfaced **pending** → reward-view **Recruit/Skip** → `economy.recruit_challenge_offer`; **Hearts** survivable-loss — `Run.hearts:int=3` (save round-trip, back-compat default 3), non-boss/non-final loss `hearts-=1` + mark-cleared + advance while `>0`, `<=0`→`DEFEAT`; **boss loss → instant DEFEAT** (hard gate) + **final-node loss → DEFEAT**; **all unique payouts zero on any loss** (income=base+interest only); reward panel shows Hearts + rewards + Recruit/Skip | `game/economy.py`, `game/encounter.py`, `game/models.py`, `game/run_init.py`, `ui/views/reward.py`, `tests/game/test_economy.py`, `tests/game/test_encounter.py`, `docs/live/systems/encounter.md`, `docs/live/systems/ui.md`, `docs/design/tasks/t38_node_rewards_hearts_plan.md` | T.15a, T.22, T.29a, T.21 | M | 📋 Plan |
```

**§V — revise V.69** (loss branch): replace "else sets `status = DEFEAT` (a DRAW counts as non-win)" and the "Commit-on-start … abandon/re-prep is rejected" rationale's loss-finality with the **Hearts** model:
> …on a **win** marks CLEARED + advance (→VICTORY if last) **and applies the node's type auto-reward** (`generate_node_reward` → inventory/amber/tempest; CHALLENGE `champion_offer` surfaced *pending* for the view's Recruit/Skip → `recruit_challenge_offer`, not auto-applied); on a **non-win** (LOSS/DRAW, V.60) **decrements `Run.hearts`** — while `hearts>0` on a **non-boss, non-final** node it marks CLEARED + advances (survive), but a **BOSS_FIGHT loss** (hard stage gate) or a **final-node loss** sets `status=DEFEAT` **regardless of Hearts**, and otherwise **only `hearts<=0` sets `status=DEFEAT`**. **Unique payouts are granted on win only** ⇒ any loss yields base income+interest with **no win-bonus and no type reward** (structural zeroing). Commit-on-start still holds (every exit applies the result; no abandon) — but a non-boss loss is now *survivable*, not terminal, so re-prep never arises.

**§V — new invariants:**
- **V.70 (G2 — single reward source):** A fought node's type reward is derived **once**, on win, via `encounter.generate_node_reward(run.seed, node)` using `node.weather` (the node's `default_weather`, not live API weather) — byte-identical to the discarded encounter-time roll (`node_encounter`'s `_reward`). The fight-build path (`node_encounter`) stays squad-only; the resolve path owns the reward. Same `(seed, node)` ⇒ same payload (V.2/V.19). REWARD→items, CHALLENGE→amber+components+tempest+offer, all else→None.
- **V.71 (G1 — Hearts gate run-end on loss):** Run defeat is gated on `Run.hearts` depletion for ordinary nodes, not a single loss. `Run.hearts:int` (default 3, `>=0`, save-persisted, old saves default 3) decrements once per non-win; a non-boss, non-final loss with `hearts>0` survives (mark CLEARED + advance), and `status=DEFEAT` is set **iff** `hearts<=0` **or** the lost node is a **BOSS_FIGHT** (hard gate) **or** the **final** node (no greater index — never relabel as VICTORY). Hearts is a plain deterministic counter — no RNG (V.2 holds). Unique payouts are win-only ⇒ losses are structurally reward-zeroed. CHALLENGE `champion_offer` is applied only through `economy.recruit_challenge_offer` (player Recruit choice), never auto-granted (V.63 — view chooses, game mutates).

**§B:** backprop the discarded-`ChallengeReward` drift —
> B.x: `ChallengeReward`/`RewardLoot` were generated (T.21/T.29a) but **never applied** — `node_encounter` discarded `_reward`, `apply_node_result` was type-blind. Loot/challenge rewards silently did nothing. Caught planning T.38. Guard: V.70 (single reward source, applied at resolve).

**§D:** mark resolved — "REWARD/challenge reward application" now built (T.38); keep deferred: §D.12 drop-table reweight, interactive champion recruit UI, NodeState.FAILED, Heart VFX/economy.

**Implementation Order:** place T.38 after T.15a (done), independent of T.15b (terminal routing) — can build before or after T.15b; no ordering gate.

---

## 11. LIVING docs to update (on build landing)

- `docs/live/systems/encounter.md` — document `generate_node_reward` dispatcher + that `node_encounter` is squad-only (reward owned at resolve). Note REWARD/CHALLENGE payload application.
- `docs/live/systems/ui.md` — reward view now shows Hearts + node-type rewards.
- **No economy living doc exists** (`docs/live/systems/` has no `economy.md`) — the `apply_node_result` reward step's living-doc home is the SPEC §V.69/V.70/V.71 invariants. Consider a stub `economy.md` if the build wants a system page; otherwise the invariants are the auditable surface (`/check`).
- Flip none (no 🔶 stub becomes ✅ here beyond doc prose).

---

### Handoff — next moves
1. **`/spec`** — apply the §10 deltas: add the **T.38** row, revise **V.69**, add **V.70/V.71**, backprop the discarded-reward **§B** entry, update **§D**.
2. **`/build §T.38`** — execute (Phase A dispatch → Phase B Hearts), update the two living docs, run `/check`.

Confirm Open Qs **O1–O4** first (champion-offer UI scope, FAILED state, final-node loss, boss loss) — they change the §T row's surface.
