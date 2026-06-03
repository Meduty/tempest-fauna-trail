# T.22 — Economy, Shop & Team-Size Cap (Tempest)

**Date:** 2026-06-03

## Why

The combat engine (T.3/T.20/T.26/T.30), encounters (T.19/T.21), and power curve
(T.18) were all in place, but a run had no *meta loop*: no currency, no shop, no
way to grow the team. T.22 makes the between-fight decisions real — earn Amber,
buy/level champions from a stage-gated shop, and spend Tempest to widen the
board. This is the spine the UI (T.10/T.15) and later content (items T.29,
augments T.31) hang off of. Scope here is **headless, pure logic** — state on
`Run`, functions in `game/economy.py` + `game/shop.py`, zero Flet (V.1).

## Key Decisions

1. **`gold` → `amber` (SPEC B.4).** Renamed the `Run` field; `from_dict` still
   accepts the legacy `gold` key so old saves load. `1 Amber : 1 Tempest`.

2. **Tempest model shape.** Two new `Run` fields: `tempest` (progress toward the
   next rank) + `tempest_rank` (== deployable board cap). Both monotonic
   non-decreasing. `grant_fight_tempest` adds +2 then cascades rank-ups,
   carrying overflow. Chose a counter+rank pair (not a single cumulative XP int)
   so the "remaining to next rank" the Amber rush needs is a cheap subtraction.

3. **Accelerating Tempest curve (was flat 2N).** User flagged the old `2N` curve
   as "too cheap" (free play nearly maxed the board). New thresholds
   `{2,4,6,10,14,18,24,30,36}` → cumulative 144 to rank 10. Over ~38 combat
   nodes, free +2/fight ≈ 76 Tempest = **rank 7**; the six challenge `+1` bonuses
   tip it to **rank 8**; 9–10 need an Amber rush. Early ramp preserved (rank 3 in
   3 fights). Cross-checked against TFT's accelerating XP-to-level shape.

4. **Max rank 10, not 6 (D.14 corrected).** SPEC §D.14 had max rank 6, but the
   already-shipped T.21 `CHALLENGE_TEAM_SIZE` tops out at 11 (stage 6), and the
   design says challenge = `cap + 1` (final `+2`) → implies cap ~9–10. Code beat
   the spec; backpropped D.14 6→10 via /spec.

5. **Interest added (overrides D.13 "none").** TFT-style `+1 per 10 banked, cap
   +5`. D.13 originally said "interest: none (keeps runs short)"; the amendment
   reverses that to deepen the save-vs-spend choice. Computed on Amber held
   *before* the node's income is granted.

6. **Leveling via a copy counter, not duplicate roster entries.** `Run` roster
   ids must stay unique, so 3-copies-→-level can't be three roster rows. Added
   `Run.champion_copies` (id → total base copies); level is *derived*
   (3 → L2, 9 → L3) and the single roster `Champion` is rebuilt at that level via
   `build_champion_at_level`. Sell refunds `floor(tier × copies / 2)`.

7. **Stage→tier table authored here (D.15 pointer resolved).** `STAGE_TIER_WEIGHTS`
   in `shop.py` (mirrored in the plan doc): stage 1 → T1–2 only; stage 6 → T1–9,
   higher-tier-weighted. Each slot rolls a tier then a uniform champion of that
   tier. Deterministic from `(run_seed, visit_index, reroll_count)` via `CH_SHOP`;
   added `CH_ECONOMY=7` for the income win-bonus and a `SHOP_REROLL_STRIDE` fold
   so successive rerolls are distinct yet reproducible.

## Deviations from Plan

- **Augments excised.** Plan §2 (augment node/pool/quality/reroll) and its
  §6/§7 augment lines now belong to **T.31**. `CH_AUGMENT` / `augment_seed()`
  left untouched in `encounter.py` for T.31. Plan doc §2 rewritten as a pointer.
- **Shop tops at T9, not T10.** T10 Primordials are boss-only (enforced in
  `content.py`, `encounter.py`); offering them in the shop would break that
  invariant. Read SPEC §D.15's "Tier 1–10" as "up to the buyable max" (T9).
  Documented in both the module and the plan.
- **SUPPLY is champions-only for now.** Plan §3 wants "champion + item"
  bundles; items don't exist yet → SUPPLY offers champions (free recruit,
  `take_supply_champion`); item bundles deferred to T.29.
- **No `sim_run` wiring.** The auto-walk uses a fixed `--team` with no recruit
  loop, so SUPPLY/shop don't fall out cleanly there (they're Prep-view
  interactions). Left the `sim_run` SUPPLY-skip as-is, per the amendment's
  "optional, only if clean".

## Verification

`uv run pytest tests/` → **700 passed** (48 new in `test_meta_progression.py`,
covering the §6 plan: cost curve, leveling, interest banks, deterministic win
bonus + shop + reroll, Tempest monotonicity/cascade/cap/pacing, all-or-nothing
rush, SUPPLY, and `gold`→`amber` back-compat).

## Follow-ups

- **T.29 (items):** REWARD drop tables + the SUPPLY champion+item bundle form.
- **T.31 (augments):** the AUGMENT node + pool; RUN-scope augments hook into
  `Run.amber` / Tempest at pick time.
- **T.10 / T.15:** run-start init (10 Amber, rank 1, first shop populate) and the
  Prep-view shop UI driving these headless functions.
- **T.14 (save/load):** the `Run` shape is now final for serialization (amber,
  tempest, tempest_rank, champion_copies, shop_offers, shop_rerolls).
