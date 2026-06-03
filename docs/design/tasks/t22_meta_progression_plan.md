# T22 Plan — Economy, Shop, Supply & Team Cap

## 1. Scope

T22 covers the non-combat **economy** systems: `SUPPLY` node resolution, the
Amber economy + champion cost/leveling curve, the Prep-view **champion shop**
(stage-gated tier rolls, buy/sell/reroll), and **Tempest** team-size cap growth.

Primary output: `src/game/economy.py`, `src/game/shop.py` (pure logic, no Flet,
no I/O — V.1). State lives on `Run` (`amber`, `tempest`, `tempest_rank`,
`champion_copies`, `shop_offers`, `shop_rerolls`).

Test output: `tests/game/test_meta_progression.py`

Depends: T1, T5, T18 (power/cost). Offer/shop/income rolls reuse the T19
sub-seed channels (`CH_SUPPLY`, `CH_SHOP`, `CH_ECONOMY`).

## 2. Augment System — MOVED TO T.31

> The `AUGMENT` node, augment pool, 4-quality weighting, and reroll-of-augments
> are **no longer part of T.22** — they are owned by **T.31** (Augment system).
> T.22 leaves `CH_AUGMENT` / `augment_seed()` in `encounter.py` untouched for
> T.31 to consume. See SPEC §D.11 and the t31 plan doc.

## 3. Supply System

- `SUPPLY` node: the player picks **1 of 5** champion offers. Offered champion
  tiers are scaled to the current stage via the same stage→tier weight table as
  the shop (§6). Deterministic via the `CH_SUPPLY` channel.
- Picks are **free recruits** (no Amber) — `shop.take_supply_champion(run, id)`
  adds a copy and auto-levels like a buy, without charging.
- **Item bundles deferred to T.29.** The MVP supply offer is champions only;
  the "champion + item combination" form arrives when items exist.

## 4. Economy

- Currency is **Amber** (`Run.amber`, renamed from `Run.gold` — SPEC B.4;
  `from_dict` still reads the legacy `gold` key). `Cost(T) = T` — linear
  acquisition cost (T18 §5).
- **Income per node** (`economy.node_income` / `apply_node_income`):
  `+3 base` + (`+1..3` win bonus, seed-deterministic via `CH_ECONOMY`) +
  **interest**. REWARD-node loot is separate (T.29 drop tables).
  **Grant policy (T.10 wiring):** base + interest are granted on **every node**
  visited (combat *and* non-combat — SUPPLY, future AUGMENT); the win bonus only
  on a combat win.
- **Interest (TFT-style):** `+1 Amber per 10 banked`, capped at `+5`
  (`min(5, amber // 10)`). Resolves the original §D.13 "interest: none" — added
  per the T.22 amendment to deepen the save-vs-spend decision. Interest is
  computed on the Amber held *before* the node's income is added.
- **Sinks:** buy champion `Cost(T) = T`; shop reroll = `1 Amber` (first reroll
  each node free); Tempest rush `1 Amber : 1 Tempest`. Sell value
  `floor(Cost × copies / 2)` (a single copy = `floor(T/2)`, the literal §D.13
  rule; a levelled unit refunds half of every copy fed in).
- Tier balance is enforced by **availability gating** (offer odds shift by
  stage — §6), not price. Cheap high-tier units cannot be rushed.
- **Leveling:** total base copies bought derive the level — **3 copies → L2,
  9 copies → L3** (`economy.level_from_copies`). `Run.champion_copies` tracks the
  count per id; the materialized `Champion` in the roster is rebuilt at the
  derived level (`build_champion_at_level`). Roster ids stay unique (one
  materialized unit per id), so copies live in the counter, not as duplicate
  roster entries. A maxed unit (9 copies / L3) is **no longer buyable or
  recruitable** — `buy_champion` / `take_supply_champion` refuse it so no Amber
  is wasted on copies past L3.

## 5. Team-Size Cap Progression — Tempest

- The deployable **board cap** == `Run.tempest_rank` (range **1–10**), driven by
  the **Tempest** counter (`Run.tempest`) — the run's XP analogue. Both are
  **monotonic non-decreasing**.
- **Start at rank 1.** Every **combat node** cleared grants **+2 Tempest** (free,
  `grant_fight_tempest`) — that is FIGHT, REWARD, CHALLENGE, and BOSS (REWARD
  nodes are weak-squad combats), **38 per run**. Non-combat nodes (SUPPLY,
  AUGMENT) grant no Tempest. Challenge clears add the
  `ChallengeReward.tempest_bonus` (`+1`) on top.
- Raising rank `N → N+1` consumes a **Tempest threshold**; reaching it auto-ranks
  and carries the overflow:

| Rank up | 1→2 | 2→3 | 3→4 | 4→5 | 5→6 | 6→7 | 7→8 | 8→9 | 9→10 |
|---|---|---|---|---|---|---|---|---|---|
| Tempest threshold | 2 | 4 | 6 | 10 | 14 | 18 | 24 | 30 | 36 |
| Cumulative to reach rank | 2 | 6 | 12 | 22 | 36 | 54 | 78 | 108 | 144 |

  This is an **accelerating** curve (steeper than the old flat `2N`). Over the
  ~38 combat nodes of a run, free `+2`/fight alone yields ~76 Tempest →
  **rank 7** (rank 8's 78 just out of reach); the six challenge `+1` bonuses tip
  it to **rank 8**. Ranks 9–10 require an **Amber rush**. The fast early ramp is
  preserved: rank 3 in 3 fights.
- **Amber rush** (`try_rank_up_with_amber`): spend Amber to complete the current
  rank-up immediately at `1 Amber : 1 Tempest`. **All-or-nothing** — only the
  full remaining `threshold − tempest` is offered (no partial buy), enabled only
  when affordable and below max rank.
- Challenge team sizes (T21 §2, `CHALLENGE_TEAM_SIZE` up to 11 at stage 6) sit at
  roughly `cap + 1` (final `+2`) so the optional fights outnumber the player —
  consistent with max rank 10 (this is why D.14's stale "max rank 6" was
  corrected to 10).
- Distinguish **roster** (owned champions, may exceed cap) from **board cap**
  (deployable in combat = `tempest_rank`).

## 6. Stage → Tier Probability Table (Shop & Supply)

Relative draw weights per **buyable** tier, gated by stage. Stage 1 sees T1–2
only; the band slides up and widens to T1–9 by stage 6 with higher-tier weight.
Cross-checked against TFT shop-odds (rising windows, ~1% top-tier). **T10
Primordials are boss-only and never offered** — the buyable ceiling is **T9**
(SPEC §D.15's "Tier 1–10" read as "up to the buyable max"). Authoritative copy
lives in `shop.STAGE_TIER_WEIGHTS`.

| Stage | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | .70 | .30 | — | — | — | — | — | — | — |
| 2 | .45 | .35 | .18 | .02 | — | — | — | — | — |
| 3 | .25 | .35 | .25 | .13 | .02 | — | — | — | — |
| 4 | .15 | .25 | .30 | .20 | .08 | .02 | — | — | — |
| 5 | .10 | .15 | .25 | .25 | .15 | .08 | .02 | — | — |
| 6 | .05 | .10 | .15 | .20 | .22 | .15 | .08 | .04 | .01 |

Each shop slot first rolls a tier by these weights, then a uniform champion of
that tier. Offers are seed-deterministic from `(run_seed, visit_index,
reroll_count)` via `CH_SHOP`; SUPPLY uses `(run_seed, node_index)` via
`CH_SUPPLY`. The shop auto-refreshes free on node entry (`refresh_shop`, resets
the reroll counter); buying consumes the slot (`buy_from_shop` → `None`).

## 7. Test Plan (→ `tests/game/test_meta_progression.py`)

- Economy: `champion_cost(T) == T`; sell value floors; interest banks
  (0/9→0, 10→1, 50→5, 60→5 cap); win bonus deterministic + in `[1,3]`.
- Leveling: 3 copies → L2, 9 → L3; buy materializes a single levelled roster
  unit; sell refunds and removes.
- Tempest: starts rank 1; monotonic non-decreasing; threshold cascade; free play
  tops at rank 7 (rank 8 with challenge bonuses); caps at rank 10.
- Amber rush: full-remaining only, blocked when unaffordable or at max rank;
  pays only the gap.
- Shop: deterministic rolls; stage-1 only T1–2; stage-6 reaches high tiers and
  never T10; reroll is deterministic + distinct, first free then 1 Amber;
  buy consumes the slot.
- Supply: deterministic offers, stage-scaled, free recruit.
- Back-compat: `from_dict` reads legacy `gold`.

## 8. Acceptance Criteria

1. SUPPLY / shop offers generate deterministically with a working reroll.
2. The cost curve, interest, and leveling rule are implemented.
3. Tempest team-cap progression (start 1, max 10) is implemented with the free
   `+2`/fight ramp and the all-or-nothing Amber rush.
4. `tests/game/test_meta_progression.py` passes; the full suite stays green.

## 9. Dependencies & Follow-ups

- Depends: T1, T5, T18; offer/shop/income rolls reuse T19 channels.
- **T.29 (items):** REWARD-node drop tables (Amber/item/champion weights) and the
  SUPPLY "champion + item" bundle form.
- **T.31 (augments):** the `AUGMENT` node + augment pool (excised from T.22);
  RUN-scope augments will hook into `Run.amber` / Tempest at pick time.
- **T.10 / T.15 (UI):** run-start state init (starting 10 Amber, rank 1) and the
  Prep-view shop UI driving these headless functions. **Contract:** any path that
  seeds a champion into the roster (incl. the run-start initial pick) must also
  set `Run.champion_copies[id] = 1`, or the first later buy of that champion
  under-counts its copies. `buy_champion` / `take_supply_champion` already do
  this; a bespoke run-start seeder must too.
- **T.14 (save/load):** now serializes the final `Run` shape (amber + Tempest +
  champion_copies + shop state).
