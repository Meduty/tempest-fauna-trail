# T.36 Plan — Roster stat/playstyle rebalance + Primordial diversification

> **Status:** ✅ **BUILD-READY (2026-06-15, rev 2)** — supersedes the
> 2026-06-15 first-pass draft. Decisions ratified with the user: full draft grid
> (22/22/16), split **T.36a** (Primordials) / **T.36b** (distribution), and a
> **self-documenting distribution guard test** (pins the target but is explicitly
> *not* a true invariant — see §8). Per-piece moves are now fully enumerated and
> delta-verified to land the target grid exactly. **Per-piece axis assignments
> remain tunable** (lore/kit fit) — the cell *counts* are the contract, the
> *which-piece* is the proposal.

- **Status:** two NEW §T rows — **T.36a** (`📋 Plan`) + **T.36b** (`📋 Plan`, depends T.36a).
- **Depends:** T.32 (role/intent axes, `classify_role`), T.33a/b (stat scaling), T.34a–c (`AbilityMeta`/`Magnitude`), T.35a (closed `Magnitude` family + V.46 orphan-stat guard), T.35b (V.47 axis↔scaling + INT coeffs). All built ✅ — no unbuilt gate.
- **Resolves:** D.25 (STR/INT coeff equilibrium — the redesigned kits *consume* the tuned coeffs; the lever work is done, T.36 spends it). Touches D.26 (INT-utility support value) only tangentially — left open.
- **Design source-of-truth:** the 2026-06-15 STR/INT scaling-edge journal (`docs/journal/2026-06-15_str_int_scaling_edge.md`) for the coeff equilibrium; this plan for the grid + per-piece moves.
- **What this plan adds beyond the draft:** the verified delta math (§2), the full 12-piece T.36b enumeration (§5), the V.47 hybrid-STR guard gap (§3/§6), and the self-documenting distribution-guard design (§8).

---

## 0. Substep split (real seam: apex content vs distribution)

- **T.36a — Primordial diversification.** Re-axis + kit-rewrite the **6 T10 kings** off the uniform `hybrid/hybrid` mold into 6 distinct apex archetypes. Self-contained, highest-identity-value, ships + tests first. Moves 5 of 12 `hybrid/hybrid` champs out (Umbra stays).
- **T.36b — Roster distribution re-axis.** Re-axis + kit-rewrite **12 non-king champs** to land the full target grid. Depends on T.36a (the king moves change the marginals T.36b finishes against — see §2 staged math).

Each substep: re-axis → kit rewrite (V.47) → snapshot regen → role-matrix regen → determinism re-baseline → `stat_edge` balance read. Both ship green independently.

## 1. Scope

**In:**
- Change `stat` / `playstyle` axis values on `ChampionDef`s (`content.py`).
- Rewrite the affected ability/passive kits so scaling honors the new axis (V.47) and the axis-aware kit patterns (§5).
- Add a **distribution guard test** (soft, self-documenting).
- Snapshot + role-matrix + sim re-baseline.

**Out (with why):**
- **No net-new/removed pieces** — the 60-champ, 1-per-affinity-×-10-tier grid is invariant (V.5/§T.5). Re-axis only.
- **No enemy/boss re-axis** — the STR/INT design lever is the champion roster (enemies are opaque-label trait carriers, V.22); enemy balance is out.
- **No new combat primitives** — kit rewrites reuse existing `Magnitude` kinds + hook idioms (T.35a). If a king kit *wants* a primitive that doesn't exist, descope that flourish, don't build engine.
- **No D.26 support-value fix** — needs a survivability sim, not a re-axis (stays deferred).
- **No grid-cardinality CI invariant** — the guard is a soft test, not §V (user decision).

## 2. The gap today — current matrix + the verified path to target

Live champion `stat × playstyle` (computed from `_CHAMPION_DEFS`, 60 champs):

```
        auto ability hybrid  TOT
str       8     2      6      16
int       5    18      3      26
hybrid    3     3     12      18
TOT      16    23     21      60
```

**Target (ratified draft grid):**

```
        auto ability hybrid  TOT
str      12     6      4      22
int       6    12      4      22
hybrid    6     6      4      16
TOT      24    24     12      60
```

**Per-cell delta (target − current):** str/auto +4, str/ability +4, str/hybrid −2, int/auto +1, int/ability −6, int/hybrid +1, hybrid/auto +3, hybrid/ability +3, hybrid/hybrid −8.

### Staged math (a then b) — verified to land exactly

**After T.36a** (5 kings leave `hybrid/hybrid`; Umbra stays):

```
        auto ability hybrid  TOT       king moves:
str       9     3      6      18       Aurion  h/h→str/auto
int       5    19      3      27       Nerei   h/h→int/ability
hybrid    4     4      7      15       Borealis h/h→hybrid/ability
                                       Mournhollow h/h→hybrid/auto
                                       Aerion  h/h→str/ability
                                       Umbra   stays h/h
```

**T.36b** then re-axises **12 non-king champs** (deltas vs post-a): str/auto +3, str/ability +3, str/hybrid −2, int/auto +1, int/ability −7, int/hybrid +1, hybrid/auto +2, hybrid/ability +2, hybrid/hybrid −3 → **lands the target exactly** (proof in §5 table; sums balance: 7 int + 2 str + 3 hybrid sources = 6 str + 2 int + 4 hybrid fills = 12).

### Where each piece lives (touch points)

| Piece of work | `file.py` | state |
|---|---|---|
| `stat` / `playstyle` axis values | `game/content.py` `_champion_def(...)` calls (lines ~520–667) | ✅ exists — data edit |
| Champion ability/passive handlers | `game/abilities/champions.py` (`@register_active`/`@register_passive` + module-level `Magnitude`s, e.g. `EMBER_SALAMANDER_DMG = ScalingTerm("damage",60,"intelligence*3.93")` :155) | ✅ exists — rewrite per piece |
| INT/STR coeffs as `Magnitude`s | `game/registries.py` `ScalingTerm`/`PctResource`/`MaxOfTerm`/`SetByCaller` (:331/374/413/454) | ✅ closed family (T.35a) |
| V.47 axis↔scaling guard | `tests/game/test_content.py` `TestAxisScalingAlignment::test_int_and_hybrid_units_reference_int` (:359) | 🔶 **partial** — checks INT only, not hybrid-STR (§3) |
| Proxy band (±10% HP·DPS) | `tests/game/test_role_intent.py` (V.33) | ✅ exists — must stay green |
| Distribution guard | `tests/game/test_content.py` | ❌ **new** (§8) |
| Role matrix | `docs/design/tasks/t32_role_matrix.txt` + `tests/game/test_role_intent.py` | ✅ regen if any role changes |
| Formula/stat snapshots | `tests/game/ability_formulas.snapshot.json` + scaling snapshot | ✅ regen (text/number drift expected) |

## 3. Architecture

### Where axes plug in
`stat` and `playstyle` are plain fields on `ChampionDef`, consumed by `compose_stats` (the `_PRIMARY_STAT` map `str→{str:1.8,int:0.2}` etc., `content.py:34`) and by `classify_role`. Changing them is a **data edit**; the statline regenerates deterministically. No model change.

### Application order / re-baseline
Re-axis shifts: (1) generated statlines (primary-stat weights flip), (2) kit numbers (rewritten coeffs), (3) `classify_role` output for any piece whose role-determining axes move → role-matrix regen. All three are deterministic → **one re-baseline per substep** (snapshots + sims); **no RNG introduced** (V.2/V.14).

### Kit-rewrite fidelity (V.47 + the closed `Magnitude` family)
Every re-axised int/hybrid piece must reference its primary via a registered `Magnitude` on its `AbilityMeta` (T.35a closed it; orphan inline math fails the V.46 guard `test_no_orphan_stat_reads`). Re-axis = swap/retune the `Magnitude`'s `scaling` expr (`"intelligence*K"` ↔ `"strength*K"` ↔ `"strength*A + intelligence*B"`), not invent primitives.

### ⚠️ V.47 guard gap (must fix in T.36)
SPEC §V.47 states `hybrid` units reference **both** STR and INT, but the guard `test_int_and_hybrid_units_reference_int` only checks `_meta_references_int` — it **never verifies a hybrid piece references STR**. T.36 *adds* `hybrid/auto` + `hybrid/ability` pieces whose whole point is both-coeff scaling, so this gap is now load-bearing. **Fix in T.36a:** extend the guard so `stat="hybrid"` must reference **both** STR and INT (add `_meta_references_str` + the hybrid branch). Backprop as a §B note (guard under-enforced V.47 since T.35b).

### Coefficient equilibrium (from D.25 — the authoring rule)
Universal auto is `1.0·STR + 0.25·INT`, so a STR carrier gets ~7× INT's auto DPS per primary point. DPS-parity **INT ability-*damage* coeff ≈ 3.7** at baseline (`mana_cost` 300k, ability mults). Scaling rule for authored kits:
`INT coeff ≈ 3.7 × (mana_cost / 300000) × (100 / mana_regen_base)` — ultimate at 2× cost ⇒ ~2× coeff; auto-int/hybrid pieces need *less* (autos carry). STR ability coeffs ≈ 0.8× their pre-D.25 values. Authored INT damage coeffs currently sit ~3.5–4.3 — reuse, don't re-derive.

## 4. Decisions

- **Grid = full draft (22/22/16).** Flagships `str/auto = int/ability = 12`; off-cells 6; `hybrid/hybrid = 4`. (User-ratified.)
- **Split T.36a / T.36b** along the apex-vs-distribution seam. (User-ratified.)
- **Distribution guard = soft self-documenting test, not §V.** On failure the test message tells operators to *re-evaluate whether the new distribution is desirable*, not blindly restore counts. (User-ratified — see §8 for the exact comment.)
- **str/ability is the weak quadrant** (STR-on-cast wastes the auto tagalong). Every piece landing there uses the **"ability empowers autos"** pattern (Jax-W: cast buffs next autos), never a raw STR nuke. Enforced by review, not test.
- **Umbra keeps `hybrid/hybrid`** as the deliberate "dual mold survives" king; the other 5 kings diversify.
- **Per-piece assignment is a proposal.** Cell counts are the contract; lore/kit fit may reshuffle *which* piece fills a cell during build — as long as the matrix lands and V.47 holds.

## 5. Authored values

### T.36a — the 6 kings (axis + kit sketch, all V.47-legal: T10 + one-per-Kinship + Primordial)

| King | Kinship | new axis | kit identity (sketch — tunable) |
|---|---|---|---|
| Aurion | Spirit | **str/auto** | radiant warlord-archer; autos carry, ability = team steroid/utility (not a nuke) |
| Nerei | Tidekin | **int/ability** | floodmother archmage; rare big-INT nuke (`coeff ≈ 3.7+`, "ultimate" feel) |
| Borealis | Swarm | **hybrid/ability** | aurora battlemage; both-coeff cast `STR·A + INT·B` |
| Umbra | Scaled | **hybrid/hybrid** (kept) | shadow bruiser-king; dual mold preserved |
| Mournhollow | Beast | **hybrid/auto** | pale-stag; STR autos + on-hit-INT proc (autos land, INT bonus) |
| Aerion | Skyborn | **str/ability** | storm warcaster; **ability empowers autos** (str/ability done right) |

### T.36b — the 12 non-king re-axis moves (delta-verified to land target)

| # | piece | kin / T | from | → to | rationale (tunable) |
|---|---|---|---|---|---|
| 1 | `champ_snowpelt_cub` | Beast 1 | str/hybrid | **str/auto** | young beast, pure striker |
| 2 | `champ_granite_gorilla` | Beast 6 | int/ability | **str/auto** | brawler; INT was dead weight |
| 3 | `champ_mirewarden_toad` | Tidekin 7 | int/ability | **str/auto** | gulp-bruiser tank |
| 4 | `champ_pebbleback_pangolin` | Scaled 1 | str/hybrid | **str/ability** | roll-up buffs next autos (weak-quadrant pattern) |
| 5 | `champ_hollow_elk` | Spirit 4 | int/ability | **str/ability** | charge empowers autos |
| 6 | `champ_dusk_bat` | Swarm 2 | int/ability | **str/ability** | dive empowers autos (lore stretch — flag) |
| 7 | `champ_phantom_lynx` | Spirit 3 | int/ability | **int/auto** | INT-fed assassin autos (glade_heron pattern) |
| 8 | `champ_tempest_eel` | Tidekin 6 | int/ability | **int/hybrid** | zaps (auto) + casts; both INT |
| 9 | `champ_marsh_thrush` | Skyborn 6 | int/ability | **hybrid/ability** | both-coeff support-caster |
| 10 | `champ_grovekeeper_tapir` | Tidekin 4 | hybrid/hybrid | **hybrid/ability** | both-coeff cast, drops the triple-hybrid |
| 11 | `champ_voltmane_jackal` | Beast 7 | hybrid/hybrid | **hybrid/auto** | lightning brawler, on-hit INT |
| 12 | `champ_eclipse_jaguar` | Beast 7 | hybrid/hybrid | **hybrid/auto** | ambush striker, STR autos + INT bonus |

**Stays `hybrid/hybrid` (target 4):** Umbra (king) + `champ_goldhide_rhino`, `champ_marshghast_boar`, `champ_glacierback_mammoth`.

**Verification (post-a → moves → target):** str/auto 9+3=**12**; str/ability 3+3=**6**; str/hybrid 6−2=**4**; int/auto 5+1=**6**; int/ability 19−7=**12**; int/hybrid 3+1=**4**; hybrid/auto 4+2=**6**; hybrid/ability 4+2=**6**; hybrid/hybrid 7−3=**4**. ✅ exact.

### Coeff guidance per landing cell
- **str/auto, hybrid/auto** — autos carry; ability coeffs modest (utility/steroid). hybrid/auto: STR base + on-hit-INT `Magnitude` (both referenced → V.47).
- **str/ability** — "empowers autos": ability grants a decaying auto-buff `Magnitude` (STR-scaled), not a nuke.
- **int/ability** — big INT nuke, `coeff ≈ 3.7 × (cost/300k)`.
- **int/auto** — INT fuels autos (AS-per-INT or on-hit-INT); no STR.
- **hybrid/ability** — `strength*A + intelligence*B` cast (both referenced).

## 6. Content / roster audit + reconciliation

1. **Stale `0.2·INT` in a test comment** — `tests/game/test_content.py:363` comment reads `(1.0 STR + 0.2 INT)`; code is `0.25` (D.25, `context.py:409`). Origin: written at T.35b before the D.25 0.25 bump landed in the same arc. **Fix:** correct the comment in T.36a. (Doc nit, not behavior.)
2. **V.47 guard under-enforces hybrid-STR** (§3) — guard checks INT only; SPEC says hybrid references both. Origin: T.35b guard authored for the dead-INT case only. **Fix + §B backprop** in T.36a; add `test_guard_detects_a_dead_str_hybrid` mirroring the existing dead-INT detector test.
3. **No drift in the axis vocab** — `stat ∈ {str,int,hybrid}`, `playstyle ∈ {auto,ability,hybrid}` confirmed against `_PRIMARY_STAT` + `classify_role`; no dead tokens.

## 7. Open questions

**Resolved here (overridable):**
- Per-piece assignments in §5 (esp. #6 `dusk_bat`→str/ability is the biggest lore stretch — swap candidate: `coppercrest_stork`).
- Umbra is the kept-hybrid king (vs e.g. Borealis).

**Still open / deferred:**
- D.26 INT-utility support value (needs survivability sim) — not touched.
- Whether to later promote the distribution guard to a hard §V once the roster shape is proven stable (revisit post-T.36b sims).

## 8. Test plan

- **Distribution guard (new, soft).** `tests/game/test_content.py::test_stat_playstyle_distribution` asserts the live matrix equals the target grid. **Self-documenting failure message** (per user):
  > "Roster stat×playstyle distribution changed. This is a *target*, not an invariant — if you intentionally re-axised pieces, re-evaluate whether the new matrix + marginals are still desirable (even str/int parity, populated cells, weak str/ability kept small) and update the target here. Do NOT blindly revert."
- **V.47 (extended).** `test_int_and_hybrid_units_reference_int` stays green; **add** hybrid-STR enforcement + `test_guard_detects_a_dead_str_hybrid`.
- **V.46.** `test_no_orphan_stat_reads` stays green (every rewritten coeff is a `Magnitude`).
- **Proxy band (V.33).** `test_role_intent.py` ±10% HP·DPS holds after re-axis.
- **Role matrix.** Regen `t32_role_matrix.txt`; update `test_role_intent.py` if any role changes.
- **Determinism (V.2/V.14).** Fixed-seed + `workers=1` sims byte-identical *after* the one intended re-baseline per substep; no cadence/RNG mechanic added.
- **Snapshots.** Regen `ability_formulas.snapshot.json` + scaling snapshot (number/text drift expected, reviewed).
- **Balance read (non-gating).** `tools/simulation/stat_edge.py` after each substep — STR/INT `wr_delta` gap should not *widen*; record in journal.

## 9. Acceptance criteria

**T.36a:**
1. All 6 kings carry their §5 axis; 5 leave `hybrid/hybrid` (Umbra stays); matrix matches the post-a table.
2. Each king kit references its primary via `Magnitude`(s); hybrids reference **both** STR and INT.
3. V.47 guard **extended** (hybrid-STR) + new dead-STR-hybrid detector test; both green. Stale `0.2` comment fixed.
4. Snapshots/role-matrix regen; full suite green; sims byte-identical post-rebaseline.

**T.36b:**
1. The 12 §5 moves applied; live matrix equals the **target grid exactly** (verified by the new distribution guard).
2. Every re-axised int/hybrid piece passes V.47; str/ability pieces use "empowers autos" (review).
3. Proxy band, V.46, determinism, snapshots all green.
4. `stat_edge` STR/INT gap does not widen vs pre-T.36 baseline (recorded, non-gating).

## 10. SPEC changes needed (apply via `/spec` after approval)

- **New §T.36a** — *Primordial diversification — re-axis + kit-rewrite the 6 T10 kings into 6 distinct apex archetypes (Aurion str/auto, Nerei int/ability, Borealis hybrid/ability, Umbra keeps hybrid/hybrid, Mournhollow hybrid/auto, Aerion str/ability); extend the V.47 guard to enforce hybrid→both STR+INT; fix stale 0.2 test comment.* Files: `game/content.py`, `game/abilities/champions.py`, `tests/game/test_content.py`, `tests/game/test_role_intent.py`, snapshots. Depends: T.32, T.35a, T.35b. Est: M. Status: 📋 Plan.
- **New §T.36b** — *Roster distribution re-axis — re-axis + kit-rewrite 12 non-king champs to land the 22/22/16 target grid; add the self-documenting distribution guard test.* Files: `game/content.py`, `game/abilities/champions.py`, `tests/game/test_content.py`, `docs/design/tasks/t32_role_matrix.txt`, `tests/game/test_role_intent.py`, snapshots. Depends: T.36a. Est: L. Status: 📋 Plan.
- **Amend V.37** — append: Primordials are no longer pinned to a shared `hybrid` axis; each T10 is a distinct apex archetype (still exactly one per Kinship + Primordial trait). (T.36a)
- **Amend V.47** — note the guard now enforces `hybrid`→**both** STR+INT (was INT-only); cite `TestAxisScalingAlignment` covering str-hybrid + int-hybrid. (T.36a)
- **§B backprop** — new entry: "V.47 guard under-enforced — checked INT only, never verified hybrid pieces reference STR (since T.35b); T.36a closes it." Optionally cite the stale `0.2` comment.
- **§D.25** — mark consumed/closed by T.36 (the tuned coeffs are now spent in the redesigned kits); D.26 stays open.
- **Implementation Order** — place T.36a then T.36b after T.35b.

## 11. LIVING docs to update (in the landing commits)

- `docs/live/content/rosters.md` — new stat×playstyle distribution + the 6 king archetypes (per substep).
- `docs/live/content/abilities.md` — rewritten kits for the re-axised pieces.
- Run `/check` after each substep — stale living doc is a bug.
