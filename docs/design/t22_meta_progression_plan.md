# T22 Plan - Meta Progression: Augment, Supply, Economy, Team Cap

## 1. Scope

T22 covers the non-combat progression systems: `AUGMENT` and `SUPPLY` node
choices, the Amber economy and champion cost curve, and team-size cap growth.

Primary output: `src/game/augments.py`, `src/game/economy.py`

Test output: `tests/game/test_meta_progression.py`

Depends: T1, T18 (power/cost). Offer rolls reuse the T19 sub-seed channels.

## 2. Augment System

- `AUGMENT` node: the player picks **1 of 3** team-wide / game-changing
  augmentations.
- **4 qualities** (e.g. `Common / Rare / Epic / Prismatic`); quality weights
  shift toward higher quality in later stages.
- **One reroll** per node — re-rolls the 3 offers via the `REROLL` sub-seed
  channel (T19). The `rerolled` flag is stored per node.
- MVP: a small placeholder augment pool; real augment content is later work.

## 3. Supply System

- `SUPPLY` node: the player picks **1 of 5** champion + item combinations.
- The offered champion tier is scaled to the current stage (T18 power band).
- MVP: a placeholder item set.

## 4. Economy

- The currency is **Amber**. `Cost(T) = T` — linear acquisition cost in Amber.
  Amber drops from `REWARD` nodes. (The `Run.gold` model field is renamed
  `Run.amber` — SPEC B.4.)
- Champion acquisition routes: `SUPPLY` picks, `REWARD` drops, and the **shop**
  in the Prep view (`views_spec.md` §6.3-§6.4 — purchasable pieces/upgrades,
  Amber cost, buy/sell/merge feedback). Shop inventory model and refresh open.
- Tier balance is enforced by **availability gating** (offer odds shift by
  stage), not price (per the T18 §5 analysis). Cheap high-tier units cannot be
  rushed.
- **Leveling**: collect 3 copies of the same champion → `+1 level`. The Amber
  inefficiency of leveling is intended (board-slot compression).

## 5. Team-Size Cap Progression — Tempest

- The deployable **board cap** grows over the run (TFT model: cap `==` rank,
  range 1-10), driven by the **Tempest** counter — the game's XP analogue.
- **Start at Tempest rank 1.** Every fight cleared grants **+2 Tempest** (free).
- Raising the rank from `N` to `N+1` costs `2N` Tempest:

| Rank up | 1→2 | 2→3 | 3→4 | 4→5 | 5→6 | 6→7 | 7→8 | 8→9 | 9→10 |
|---|---|---|---|---|---|---|---|---|---|
| Tempest threshold | 2 | 4 | 6 | 8 | 10 | 12 | 14 | 16 | 18 |

  At `+2`/fight that is `N` fights per rank-up — the first two rank-ups take 1
  and 2 fights, a fast early ramp to rank 3. Reaching a threshold raises the
  rank automatically; overflow Tempest carries to the next rank.

- **Amber rush option.** The player may spend **Amber** to **complete the
  current rank-up immediately**, at **1 Amber per missing Tempest point**:

  ```
  cost = remaining_tempest        # 1 Amber : 1 Tempest
  ```

  The cost shrinks as free Tempest accumulates. It is **all-or-nothing** — only
  the full remaining cost is offered; no partial / incremental purchase and no
  half-fill option. The Prep view shows a single `Rank Up — <cost> Amber`
  action, enabled only when affordable.

- Over ~38 fights the free `+2`/fight alone reaches roughly rank 9; Amber
  rushes close the gap to 10 and let the player spike the board earlier.
- Challenge team sizes (T21 §2) sit at `cap + 1` (final challenge `+2`) so the
  optional fights outnumber the player.
- Distinguish **roster** (owned champions, may exceed cap) from **board cap**
  (deployable in combat) — `/recruit` seeds 3 champions into the roster; the
  player deploys 1 at first.

## 6. Test Plan

- Augment: 3 deterministic offers; reroll yields a different deterministic set;
  quality weights shift by stage.
- Supply: 5 deterministic champion+item offers; champion tier matches stage.
- Economy: `Cost(T) == T`; leveling consumes 3 copies.
- Team cap: monotonically non-decreasing; reaches the target by the final stage.

## 7. Acceptance Criteria

1. Augment / supply offers generate deterministically with a working reroll.
2. The cost curve and leveling rule are implemented.
3. Team-cap progression is implemented and reconciled with `/recruit`.
4. `tests/game/test_meta_progression.py` passes.

## 8. Dependencies & Open Items

- Depends: T1, T18; offer rolls reuse T19 channels.
- Open: augment / item / champion-pool content; the Prep-view shop inventory
  model, refresh, and stage availability gating; augment quality names and the
  weight curve.
