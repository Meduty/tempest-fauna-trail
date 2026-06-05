# T.33 Plan — Three-class stat scaling + tier/level speed nudge (+ speed-stat baseline parity & mage buff)

> **Status:** plan — ready for review. (§T row T.33 already added by `/spec`; this plan finalizes scope + numbers, which **revise** the just-added V.34/T.33 values — see §10.)
> **Depends:** T.18 (power scaling — done), T.32 (composer full-rework — done). Both built; this task edits the same `scaling.py` / `compose_stats` surfaces they own.
> **Resolves:** GitHub #36 (side-A equal-AS tie bias → SPEC B.14) and GitHub #39 (mana-regen not comparable to AS/MS — *baseline* mismatch: MR=10 vs AS=100/MS=90), folded in per user request as an adjacent fix.
> **Design source of truth:** GitHub issue #36 thread (final two comments: "three stat classes" + "task draft") and #39. `src/game/scaling.py` (T.18 power model), SPEC §V.33/§B.6 (threat/move_speed off the power budget).
> **What this plan adds beyond those:** the **+2%/tier** exponent; **all-int speeds** + an int `milli_AS` for sub-integer ordering; the **canonical side-independent total order** that fixes B.14 in the comparator (`load_order`, absorbing D.18) — *not* speed precision; the speed-stat baseline-parity model (MR & MS → 100, cost rescaled, capacitors deliberately *unequal*) + mage buff; the **speed axis 3→7** diversity (33b); and the test/re-baseline plan.
> **Status:** design locked & applied to SPEC (V.34 rewritten, V.35, D.18 resolved, D.19, T.33→T.33a/T.33b). Combat module was renamed mid-flight: `loop_new.py→engine.py`, `legacy.py→resolve.py` (refs updated). T.33a engine work in progress.

---

## 0. Substep split (T.33a → T.33b)

Split at the engine/content seam; both ship now, each test-gated.

- **T.33a — engine + #39 + tiebreak.** 3-class scaling (+2%/tier), int speeds + `milli_AS`, baseline parity (MR/MS→100, cost→300k, mage buff, boss costs ×10), `load_order` (seeded) + rename `speed_tiebreaker→formation_index`, canonical sort key. **Fully fixes B.14.** No role-system coupling. Files: `game/scaling.py`, `game/content.py`, `game/encounter.py`, `game/piece.py`, `game/loadout.py`, `game/combat/engine.py`, `game/combat/resolve.py`, `game/formation.py`, `game/bosses/data.py`, `game/abilities/bosses.py`, `tools/playtest/inspect.py`, tests.
- **T.33b — speed diversity (depends on 33a).** `_SPEED` 3→7 (+4 token names), roster reassignment, regen `t32_role_matrix.txt` 648→1512, update `test_role_intent.py`, amend V.32. Files: `game/content.py`, `docs/design/tasks/t32_role_matrix.txt`, `tests/game/test_role_intent.py`, roster defs.

"Done when": 33a — full suite re-baselined green + mirror/mixed-tier no longer side-A. 33b — 7 speed levels in use across roster, matrix 1512 injective, V.32 amended.

## 1. Scope

**In scope:**
- `scaling.py`: a 3-class scaling taxonomy (`PRIMARY` / `SECONDARY` / `FLAT`) driven off the **same** `power(T, L)` curve, with a gentle exponent for the middle class; `stat_multiplier(tier, level, exponent=PRIMARY_EXPONENT)`.
- Route every tier/level scale loop + `_assert_budget` through the tuples (`content.py`, `encounter.py`).
- Secondary stats (`attack_speed`/`move_speed`/`mana_regen`/`threat`) get the gentle curve, **stored int** (rounded). A dedicated int `milli_AS = round(exact×1000)` carries sub-integer speed for ordering (§3.5).
- **B.14 fixed by a fair canonical total order** (§3.6): new `Piece.load_order` (seeded, side-independent), rename overloaded `speed_tiebreaker → formation_index`, sort key `(-AS_int, -milli_AS, champion_id, load_order, kind)`. Absorbs D.18.
- **Speed axis 3→7** (§3.7, substep b): expand `_SPEED`, reassign roster, regen role matrix 648→1512, amend V.32.
- **#39 fold (speed-stat baseline parity + mage buff):** lift `mana_regen` baseline 10 → **100** and `move_speed` baseline 90 → **100** so all three speed stats read on a shared ~100 baseline alongside `attack_speed` (=100) — a player compares MR/MS/AS as power investments directly. Rescale `ability_cost` to hold cast cadence (×10 unit-rescale), then shave it for a deliberate **mage buff**: baseline `ability_cost` 36_000 → **300_000**. Boss costs ×10 (cadence-neutral). Capacitors stay *unequal* by design (a cast costs far more than an attack — that lives in the threshold, invisible to the player; comparability lives at the baseline, not the capacitor).
- Re-baseline all stat/sim/snapshot tests.

**Out of scope:**
- **Float anything.** All stored quantities stay int (`milli_AS` is int too); only `crit_chance`/`penetration_pct` ratios are float. Meters keep `int()` (`engine.py:668-670`).
- **hp/damage/mana → int.** The engine currently runs those float (`piece.hp: float`, `deal_damage`); converting them to int is the *right* direction but a **separate engine task**, not T.33.
- **Deep mage/movement rebalance.** The MR lift carries a deliberate ~20% cast-frequency buff and the MS lift ~11% movement (D-3); tuning ability damage to match is a later sim-driven pass.

## 2. The gap today

| piece | where | state |
|---|---|---|
| `SCALABLE_STATS` 5-key tuple | `scaling.py:41` | 🔴 production-dead — only `tests/game/test_scaling.py` imports it; the live loops hardcode the same 5 keys inline |
| tier-scale loop (`compose_stats`) | `content.py:300-302` | hardcodes `("max_hp","strength","intelligence","armor","resistance")`, `round()`s them |
| `_assert_budget` scalable set | `content.py:306` | same 5-key tuple duplicated |
| level-scale loop (champion) | `content.py:337-339` | same tuple, `round()` |
| level-scale loop (`_instantiate_enemy`) | `encounter.py:285-287` | same tuple, `round()` |
| level-scale loop (`_champion_def_to_enemy`) | `encounter.py:611-613` | same tuple, `round()` |
| speeds (`attack_speed`/`move_speed`/`mana_regen`) + `threat` | — | ❌ **flat** — in no scale loop → equal-AS ties common → B.14 side-A bias |
| `_event_sort_key` | `engine.py:379-387` | today `(-AS, -AS, speed_tiebreaker, kind)` → **rewrite** to `(-AS_int, -milli_AS, champion_id, load_order, kind)` (§3.6) |
| `speed_tiebreaker = index` (the bias) | `resolve.py:36-37` | team-block-then-enemy → **replace** with seeded side-independent `load_order`; the field's formation job → renamed `formation_index` (`engine.py:541,545,548,579,589-590`; `formation.py`) |
| meter advance | `engine.py:668-670` | `int()`-truncates AS/MS/MR — **stays** (meters int) |
| speed-stat baselines | `_BASE_STATS` (`content.py:10`): `attack_speed=100`, `move_speed=90`, **`mana_regen=10`** | 🔴 **baseline mismatch** — #39: MR=10 reads as a tiny, incomparable number next to AS=100/MS=90 |
| mana capacitor | baseline `ability_cost = 36_000` (`content.py:127` `_ABILITY_COST`) | scales with MR baseline — must rescale ×10 to hold cadence when MR→100 |

## 3. Architecture

### 3.1 Three scaling classes (`scaling.py`)

```python
PRIMARY_SCALABLE_STATS   = ("max_hp", "strength", "intelligence", "armor", "resistance")
SECONDARY_SCALABLE_STATS = ("attack_speed", "move_speed", "mana_regen", "threat")
FLAT_STATS               = ("attack_range", "ability_cost")

PRIMARY_EXPONENT   = 0.5      # sqrt(power) — unchanged T.18 curve, ≈ +12.2%/tier
SECONDARY_EXPONENT = 0.0857   # ≈ +2%/tier — user-chosen, "noticeable" speed spread

def stat_multiplier(tier: int, level: int, exponent: float = PRIMARY_EXPONENT) -> float:
    return power(tier, level) ** exponent

# Deprecated alias — kept so nothing breaks; equals the primary tuple.
SCALABLE_STATS = PRIMARY_SCALABLE_STATS
```

`SECONDARY_EXPONENT = 0.0857` is derived, not guessed: `ln(1.02) / ln(2^(1/3)) = 0.08571` solves "+2% per tier" against the existing power curve. Resulting magnitudes (one model, two exponents):

| step | primary (×) | **secondary (×)** | AS/MS/MR 100 → | threat 60 → |
|---|---|---|---|---|
| per tier | 1.122 | **1.020** | — | — |
| L1→L2 | 1.414 | **1.061** | — | — |
| L2→L3 | 2.000 | **1.195** | — | — |
| T5L1 | — | **1.082** | 108.2 | 64.9 |
| T10L1 | — | **1.195** | 119.5 | 71.7 |
| T10L3 | — | **1.428** | 142.8 | 85.7 |

(AS, MS, and MR now share base 100 → scale identically; threat base 60.)

### 3.2 Route the scale loops through the tuples

All four loops + `_assert_budget` stop hardcoding the 5-key tuple. Each iterates **primary at `PRIMARY_EXPONENT`** (with `round()`, unchanged) and **secondary at `SECONDARY_EXPONENT`** (no `round()`). Sketch for the `compose_stats` tier step (`content.py:300-302`):

```python
sp = stat_multiplier(tier, 1, PRIMARY_EXPONENT)
ss = stat_multiplier(tier, 1, SECONDARY_EXPONENT)
for k in PRIMARY_SCALABLE_STATS:
    stats[k] = round(stats[k] * sp)          # primary: rounded int, as today
for k in SECONDARY_SCALABLE_STATS:
    stats[k] = stats[k] * ss                 # secondary: FLOAT, never round()
```

Same shape at the two `content.py` / two `encounter.py` level-scale steps (use the `sm(T,L)/sm(T,1)` ratio at each exponent). `FLAT_STATS` are never multiplied.

### 3.3 Ordering: all stats int; B.14 fixed by a fair total order

**Every stored quantity is int** (hp/damage/mana/speeds/costs/energy) — only `crit_chance`/`penetration_pct` (ratios) are float (user principle; avoids display artifacts like a piece reading `0` HP at `0.4`). Speeds are int; the sub-integer precision needed for *ordering* lives in a dedicated `milli_AS` int field (§3.5), not in the speed value.

B.14 is **not** fixed by making speeds collide-free — it's fixed by replacing the **biased final tiebreak** (input index, team-block-then-enemy) with a fair, side-independent **canonical total order** (§3.6). Meters stay int (`int()` at `engine.py:668-670`); cadence scales ~2%/tier off the int speed. Determinism (V.2/V.14) holds — all combat-loop math is integer.

### 3.4 #39 — speed-stat baseline parity (+ mage buff)

**The real complaint (#39):** the player can't compare speed stats *as numbers*. `_BASE_STATS` ships `attack_speed=100`, `move_speed=90`, **`mana_regen=10`** — MR is 10× off, so a sheet reading "MR 12" next to "AS 110" gives no intuition for which is the better investment. The *capacitor* (ticks-to-fill) is internal plumbing the player never sees; comparability must live at the **stat baseline**, not the capacitor threshold.

**Fix:** lift the two odd-baseline speed stats to 100 so all three share one scale, and rescale cost to keep cadence sane.

- `_BASE_STATS["move_speed"]`: `90` → **`100`** — joins AS/MR at baseline 100. Side effect: ~11% faster movement for everyone (symmetric, no side-bias). Flagged (D-3).
- `_BASE_STATS["mana_regen"]`: `10` → **`100`** (×10). Now MR 150 vs AS 150 read as equal-magnitude investments, exactly the #39 ask.
- `_ABILITY_COST` / `DEFAULT_ABILITY_COST`: `36_000` → **`300_000`**. The ×10 MR lift demands a ×10 cost lift (`→360_000`) just to hold the old `3600`-tick cadence; we instead use `300_000` (cadence `300000/100 = 3000` ticks) for a deliberate **~20% mage buff** (mages undertuned). `ability_cost` stays `FLAT` (a capacitor threshold, not a power stat).
- Authored boss costs (`bosses/data.py` default `48_000` + per-boss `38_000`–`52_000`; fallbacks in `abilities/bosses.py`) rescaled **×10** (cadence-neutral — bosses don't get the mage buff): `48_000→480_000`, `38_000–52_000 → 380_000–520_000`.
- **No change** to abilities that reference `cost` as a *fraction* (`champions.py:629` `cost*0.4`, `enemies.py:1649` `cost*0.8`, etc.) — scale-invariant, auto-adjust.
- `999_999` "never-cast" sentinels (`enemies.py:384`, `champions.py:1253`) left as-is (effectively infinite).

Result: AS/MS/MR all baseline 100 → directly comparable as stat values. The mana capacitor (`300_000`) stays far larger than the action/move capacitor (`60_000`) — that's *intended*, encoding "a cast is worth ~5 autos" — but it's invisible; the player just reads three speed numbers on one scale. MR is `SECONDARY`-scaled (base 100 → scales identically to AS), so higher-tier mages cast a hair faster — consistent "stronger = faster". Both baselines are clean ints.

### 3.5 `milli_AS` — sub-integer speed, stored int

Speeds are int, but the action sort wants finer resolution so the *genuinely* faster of two same-int-AS pieces acts first (rather than falling straight to identity). An empirical sweep (120 defs × L1-3 = 360 instances) measured **different-power pairs sharing the same int AS**: **317** at int, **0** once sub-integer precision is kept. (Base AS is hyper-quantized — only **12 distinct values** across 120 defs — so scaling collapses many distinct (base,tier,level) combos onto the same int.)

**Decision (user-confirmed): store the precision as a dedicated int field, not as a float speed.**
- `Piece` (and the stat dict) carries **`milli_AS = round(exact_scaled_AS × 1000)`** — an int. Closest different-power gap is `0.043`, so ×1000 separates all 317 with 43× margin.
- Computed in `compose_stats` from the pre-round exact float, then **threaded through the level + weather multipliers alongside `attack_speed`** (so it stays exact post-weather). `attack_speed` itself = `round(exact)` for meter + display.
- The sort uses `-milli_AS` (§3.6). `attack_speed` (int) feeds the meter and the display unchanged.

This keeps **all stored speeds int** (no model-field float surgery, no `_apply_weather_to_piece` round removal, no float serialization) — `milli_AS` is just one more int stat riding the same scaling path. The 582 same-power pairs (true mirrors) have identical `milli_AS` by construction → resolved one tier down by `load_order` (§3.6), not by precision.

### 3.6 Canonical total order — the real B.14 fix (absorbs D.18)

The bias was never the speeds — it was the **final tiebreak**: `speed_tiebreaker = input index`, assigned team-block (`0..N-1`) then enemy-block (`resolve.py:36-37`), so *any* tie handed the whole team priority. Replace it with a fair, side-independent **total order**:

```python
# _event_sort_key  →
key = (-AS_int, -milli_AS, champion_id, load_order, kind)
```
| tier | purpose | side-independent? |
|---|---|---|
| `-AS_int` | coarse speed — faster acts first | ✓ |
| `-milli_AS` | fine speed — true order for the 317 same-int pairs | ✓ |
| `champion_id` | identity — rare exact-`milli` ties between *different* champs | ✓ (by id, not side) |
| `load_order` | same-champion copies / true mirrors | ✓ (seeded, not positional) |
| `kind` | a piece's own movement (0) vs action (1) | n/a |

- **`load_order`** — new `Piece` field, a deterministic side-independent permutation assigned in `compile_loadout` from its `seed` (currently 42). Unique per instance, never team-then-enemy. This is what makes true mirrors fair (winner depends on identity+seed, not on "player side") and **absorbs D.18** — no longer deferred.
- **Rename the overloaded `speed_tiebreaker` → `formation_index`** (`piece.py`, `combat/engine.py` `assign_spawns`, `game/formation.py`): its *surviving* job is the enemy formation-position key (`plan_enemy_formation`), which is unrelated to tie order. Splitting the two ends the "first-on-board = fastest" confusion.
- True-mirror honesty: a perfectly symmetric mirror has no unbiased deterministic winner (sequential combat → someone strikes first → determinism fixes who). `load_order` makes that "who" a function of identity+seed, so aggregate win-rate is unbiased even though a given mirror always resolves the same way.

### 3.7 Speed axis 3 → 7 (T.33b — diversity)

`_SPEED` (`content.py:97`) has 3 levels (`speedy 1.2 / hybrid 1.0 / heavy 0.85`). Expand to **7** so distinct pieces rarely share an AS and `speed` becomes a richer build lever (fix-the-model, not patch-the-symptom). Role **titles** are unaffected — `classify_role` ignores `speed` (verified). But `build_role_code` includes the speed token, so this:
- adds **4 new token names** (e.g. `crawling / slow / steady(=hybrid) / brisk / swift / fleet / blinding` — final names TBD in 33b),
- **reassigns the 120-piece roster** across the 7 levels (else no diversity gain),
- **regenerates the role matrix** `t32_role_matrix.txt` (648 → **1512** combos) and updates `test_role_intent.py` (the `648` assertions),
- **amends V.32** (injective over 648 → 1512).
Each `_SPEED` entry also sets `resistance`/`primary_stat`/`move_speed` tradeoffs (faster ⇒ less primary stat), spanning a wider range than today's 0.85–1.2 (e.g. ~0.7–1.4 AS) for real spread.
**Alternatives rejected (for the precision/ordering question):** *float speed values* (B') — rejected because the engine's float hp/damage/mana is itself a wart the user wants int, so adding more float is backwards, and the weather step re-rounds it anyway; *×100 fixed-point* — 0 ties but forces 6-million-magic thresholds + a `/100` display layer for no payoff (cross-platform determinism is moot while hp/damage stay float); *explicit `power()` sort term* — works but the user preferred the meaningful `milli_AS` (true speed) over an arbitrary power rank. **Chosen:** int speeds + int `milli_AS` + the side-independent total order (§3.6).

## 4. Decisions (stated, overridable)

- **D-1 Exponent = +2%/tier (`0.0857`).** User-chosen for a *noticeable* spread (×1.43 over the full T1L1→T10L3 range) vs the original ×1.20 at +1%/tier.
- **D-2 All stored quantities int; B.14 fixed in the comparator, not the stat.** Speeds int; `milli_AS` int carries ordering precision; the fair canonical total order (§3.6) removes the side bias. Float (B') was rejected: the engine's float hp/damage/mana is itself a wart the user wants int, so adding float speeds goes the wrong way; and the bias lived in the tiebreak, not the speed value. Only `crit_chance`/`penetration_pct` stay float (ratios). User-confirmed.
- **D-3 #39 baseline parity + mage/movement buffs.** Comparability lives at the **stat baseline**, not the capacitor (the player never sees ticks): lift MR `10→100` and MS `90→100` so all three speed stats sit at base 100. Cost rescales ×10 to hold cadence, then trimmed to `300_000` for a deliberate **~20% mage buff** (`3000` vs `3600` ticks). MS→100 carries a **~11% movement buff** (symmetric). Capacitors stay deliberately unequal (a cast ≫ an attack). User-chosen.
- **D-4 threat included in SECONDARY**, flagged: higher pieces pull slightly more aggro as they tier/level up. Still **off the HP·DPS power budget** (V.33/B.6) — the drift guard and `_assert_budget` ignore it; this is ordering/aggro flavour, not power.

## 5. Authored values (first-pass, tunable)

| constant | old | new | rationale |
|---|---|---|---|
| `SECONDARY_EXPONENT` | — | `0.0857` | +2%/tier |
| `_BASE_STATS["mana_regen"]` | `10` | `100` | baseline parity with AS/MS (#39); ×10 |
| `_BASE_STATS["move_speed"]` | `90` | `100` | baseline parity; ~11% movement buff (symmetric) |
| `_ABILITY_COST` | `36_000` | `300_000` | ×10 to hold cadence, then trimmed → ~20% mage buff (cadence 3000) |
| `DEFAULT_ABILITY_COST` | `36_000` | `300_000` | same |
| boss `ability_cost` (data.py default) | `48_000` | `480_000` | ×10, cadence-neutral (no mage buff for bosses) |
| boss per-kit costs | `38_000`–`52_000` | `380_000`–`520_000` | ×10, cadence-neutral |

## 6. Content / drift audit + reconciliation

- **Dead-tuple cleanup.** `SCALABLE_STATS` (`scaling.py:41`) is production-dead (4 inline duplicates). This task makes the three tuples the single source of truth; `SCALABLE_STATS` becomes a documented deprecated alias of `PRIMARY_SCALABLE_STATS`. Kills the 4-way duplication.
- **`scale_stat` helper** (`scaling.py:90`) is test-only (production uses `stat_multiplier` directly). Leave it; optionally add an `exponent` param for parity. No production impact.
- **V-guard.** New V.34 asserts the three-class taxonomy + monotonic-speed; new V.35 asserts speed-stat **baseline parity** (AS/MS/MR `_BASE_STATS` all == 100, so they're comparable as stat values). Guards stop the speeds silently reverting to flat (B.14) or a speed baseline drifting off 100 again (#39).

## 7. Open questions

**Resolved here (proposals, overridable):**
- Exponent magnitude → **+2%/tier** (D-1, user).
- Speed precision → **all-int speeds + int `milli_AS`**; B.14 fixed by the side-independent total order (D-2, user).
- #39 fold → **baseline parity**: MR `10→100`, MS `90→100`; cost `36_000→300_000` (×10 + ~20% mage buff); boss costs ×10 cadence-neutral (D-3, user).
- threat scaling → **included, flagged** (D-4).

**Still open / deferred:**
- Side-independent **residual** tiebreak for exact same-T/L mirrors → **D.18**, separate task (perturbs same-tick ordering on its own, needs its own re-baseline).
- Whether the ~20% mage buff + ~11% movement buff want a follow-up ability-damage re-tune → defer to a sim-driven balance pass once the engine re-baseline lands.

## 8. Test plan

- **Unit (scaling):** `stat_multiplier(T,L,PRIMARY_EXPONENT)` unchanged vs old `stat_multiplier`; `stat_multiplier(2,1,SECONDARY_EXPONENT) ≈ 1.020`; `(10,3) ≈ 1.428`. Monotonic in T and L for both exponents.
- **Unit (compose):** secondary stats `round()`-ed to int post-compose; `compose_stats(...,tier=2)["attack_speed"] >= tier=1`; `milli_AS == round(exact×1000)` and rides level+weather; `FLAT_STATS` identical across tiers.
- **Tie-fix (the point, 33a):** `_event_sort_key` is `(-AS_int, -milli_AS, champion_id, load_order, kind)`; a `resolve_combat` **mirror is no longer 100% side-A** (load_order decides, not input index); a mixed-tier matchup resolves the higher-power piece first. Roster-sweep regression: **0 different-power pairs share `milli_AS`** (§3.5).
- **load_order / formation_index:** `load_order` is a side-independent permutation (no team-block-first); swapping team↔enemy lists does not flip a mirror's winner systematically; `formation_index` still drives enemy spawn positions (formation unchanged).
- **#39 baseline parity:** `_BASE_STATS` `attack_speed == move_speed == mana_regen == 100`; baseline cast cadence ≈ `3000` ticks (~20% mage buff vs old 3600); move cadence `600` (~11% buff).
- **Determinism (V.2/V.14):** fixed seed + `workers=1` byte-identical; all combat-loop math integer.
- **Re-baseline:** stat snapshots, `tools/simulation`, mega7; `weather_impact.py` mirror diagonal ~50% **without** `--both-sides`.
- **V-guard:** `SECONDARY_SCALABLE_STATS` disjoint from `PRIMARY`/`FLAT`; every `_BASE_STATS` key classified once.
- **33b:** `_SPEED` has 7 keys; role matrix has 1512 injective combos; `classify_role` unchanged by speed; roster uses ≥5 of the 7 levels.

## 9. Acceptance criteria

**T.33a:**
1. `scaling.py` exposes the 3 tuples, `PRIMARY_EXPONENT=0.5`, `SECONDARY_EXPONENT=0.0857`, `stat_multiplier(tier, level, exponent=...)`; `SCALABLE_STATS` deprecated-aliases the primary tuple.
2. All scale loops + `_assert_budget` iterate the tuples; primary + secondary `round()`-ed to int; `milli_AS` carried as int.
3. `_event_sort_key == (-AS_int, -milli_AS, champion_id, load_order, kind)`; `load_order` side-independent; `speed_tiebreaker` renamed `formation_index` (formation intact).
4. Mirror & mixed-tier matchups no longer deterministically side-A.
5. `_BASE_STATS` AS==MS==MR==100; cadence ≈3000 (mage buff), move ≈600.
6. Determinism byte-identical; full suite re-baselined green.

**T.33b:**
7. `_SPEED` 7 levels; roster reassigned; `t32_role_matrix.txt` 1512 combos injective; `test_role_intent` updated; V.32 amended.

## 10. SPEC changes

**Already applied [2026-06-05]:** V.34 (exponent 0.0857), V.35 (baseline parity), T.33 row, D.19 (#39 resolved).

**Needs `/spec` (this locked design supersedes the float framing):**
- **Revise V.34** — speeds are **int** (not float); B.14 fixed by the canonical total order `(-AS_int, -milli_AS, champion_id, load_order, kind)` + side-independent `load_order`, **not** by float precision; `milli_AS` int field carries sub-integer ordering; meters int. Drop the "secondary float, never round()" clause.
- **Resolve D.18** — RESOLVED (T.33a) → folded into V.34's `load_order`; no longer deferred.
- **Amend V.32** (T.33b) — `role_code` injective over **1512** axis combinations (speed axis 3→7).
- **Split T.33 row → T.33a / T.33b**; files per §0. `game/models.py` only if speed fields need touching (they stay int → likely just `milli_AS`/`load_order` on `Piece`, not the Defs).
- New §B? No — B.14 already logged; its fix now points to V.34 (total order) instead of float.
