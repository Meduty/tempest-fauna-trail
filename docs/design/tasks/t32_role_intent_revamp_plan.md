# T.32 Plan — Role system revamp: intent axis + role / role_code model

> **Status:** plan — ready for review. New §T row (T.32); needs `/spec` to add it.
> **Depends:** T.5 (content roster — done), T.18 (scaling — done), T.24 (formation — done), T.19 (encounter — done), T.25 (sim — done). All built; this is a refactor + content pass over existing systems.
> **Resolves:** GitHub issue #37 ("Role system revamp: add intent axis + primary/secondary role model"); SPEC §D.10 (archetype/role taxonomy).
> **Design source of truth:** `docs/design/content/champion_roster.md` (archetype tags = intent source), `docs/design/content/enemy_roster.md`, `docs/design/content/trait_catalog.md` (Calling semantics), `docs/design/tasks/t5_content_plan.md` (axis composer), `docs/design/tasks/t18_power_scaling_plan.md` (P / √P), `src/game/content.py` (composer + `_ROLE_FROM_AXES`).
> **What this plan adds beyond those:** a 6th axis (`intent`); a full composer rework (every stat generated, dead per-unit override fields removed, override ordering fixed); an 8-role classifier replacing the flat `_ROLE_FROM_AXES` 6-value map; a deterministic `role_code` descriptor; an enumerated 648-combo validation matrix (`t32_role_matrix.txt`).
> **Not a §T row yet** — needs `/spec` to add the row + invariants; §10 lists the deltas. Do not edit SPEC inline.

---

## 1. Scope

**In scope:**
- `src/game/content.py` — add `intent` axis; rework `compose_stats` to full-compose every stat; remove dead `threat`/`move_speed`/`ability_cost` Def fields + their `_build_*` passthrough; new `classify_role` + `build_role_code`; replace `_ROLE_FROM_AXES`; fix `stat_overrides` ordering + scope.
- `src/game/models.py` — `Champion`/`Enemy` gain `intent` + `role_code`; `role` reused for the coarse title; `to_dict`/`from_dict` (+ back-compat read).
- `src/game/encounter.py` — switch `_is_support`/`_is_tanky`/`_is_dps` to `intent`/`role`; update the two `_ROLE_FROM_AXES` call sites.
- `src/game/formation.py` — `classify_role` (placement) kept axes-based; align with new vocab where it reads `durability`/`range_`→`reach`.
- `tools/simulation/matchup.py`, `tools/playtest/inspect.py`, `tools/playtest/_common.py`, `src/ui/views/admin.py`, `src/ui/components/champion_card.py` — emit/display/filter `role` + `role_code` + `intent`.
- Content: author `intent` on all ~60 champions + ~60 enemies + 6 bosses, derived from roster archetype tags.
- Tests + the generated matrix fixture.

**Out of scope:**
- Buff-vs-debuff "controller" role (no axis encodes it → folded into `support`; the distinction stays in trait/kit data, not the role taxonomy).
- A 7th "taunt-vs-sneak" axis (rejected — threat is composed across `durability`/`intent`/`playstyle` instead; keeps the axis count at 6).
- Re-tuning the intent stat-bias magnitudes beyond the conservative first pass (balance work, follow-up).

## 2. The gap today

| Piece | Where | State |
|---|---|---|
| 5 axes (`primary_stat`,`range_`,`durability`,`playstyle`,`speed`) | `content.py:126-162` | ✅ (t5 doc says "4" — `speed` added later; doc stale) |
| `intent` axis | — | ❌ missing |
| `role` derivation | `content.py:93-97` `_ROLE_FROM_AXES[stat][reach]` flat 6-value map | 🔴 ignores durability/playstyle/speed/intent → can't tell a damage-bruiser from a peeling support |
| `role_code` descriptor | — | ❌ missing |
| `threat` composition | `content.py` — in `_BASE_STATS` (60) but **no axis touches it**, then overwritten by `d.threat` in `_build_*` (`:264`,`:305`) | 🔴 the one stat never composed; `d.threat` authored **0×** in roster (dead default) |
| `move_speed` / `ability_cost` | `_build_*` read `d.move_speed`/`d.ability_cost` | 🔴 authored **0×** in roster — dead default passthrough (always 90 / 36000) |
| `stat_overrides` | `_apply_stat_overrides` (`:229`) adds to **all** base keys; `_assert_budget` (`:218`) checks only 5 scalable; applied **after** level-scale (flat-last) | 🔶 capability is all-stats (docs' "only scalable" is a *budget* claim, not capability); ordering makes scalable overrides a vanishing relative bonus at high level |

`d.*` audit (roster call sites in `content.py`): `speed=` 28 uses (real axis), `stat_overrides=` 1 use (Glade Heron `resistance:40`), `threat=`/`move_speed=`/`ability_cost=` **0** uses.

## 3. Architecture

### 3.1 The 6 axes (final)

| # | Axis (code) | Values | Identity meaning |
|---|---|---|---|
| 1 | `stat` *(rename `primary_stat`)* | `str` / `int` / `hybrid` | primary damage stat |
| 2 | `reach` *(rename `range_`)* | `melee` / `ranged` | reach (underscore was only dodging the `range` builtin) |
| 3 | `durability` | `squishy` / `hybrid` / `tanky_hp` / `tanky_arm` | frame (`standard`→`hybrid`, matching the other axes' middle) |
| 4 | `playstyle` | `auto` / `hybrid` / `ability` | auto-attack vs cast reliance |
| 5 | `speed` | `speedy` / `hybrid` / `heavy` | tempo (`neutral`→`hybrid`) |
| 6 | **`intent`** *(new)* | `damage` / `hybrid` / `utility` | combat purpose — deal damage vs enable team |

`intent` is genuinely orthogonal: a `tanky_hp` piece can be a damage-bruiser **or** a peeling support — axes 1–5 cannot separate them. (Axis renames `primary_stat`→`stat`, `range_`→`reach` are cosmetic clarity; value renames `standard`→`hybrid`, `neutral`→`hybrid` unify the "middle = hybrid" convention. `hybrid` deliberately recurs across 4 axes; `role_code` strips it for readability — §3.4.)

### 3.2 `intent` is authored from the roster (no guessing)

Every champion already carries an archetype tag in `champion_roster.md`. Direct map:

| Roster archetype | `intent` |
|---|---|
| `Tank-*` (HP/ARM+RES/STR/INT) | `utility` |
| `APC-*`, `ADC-*` | `damage` |
| `SUP-*` (Heal/Buff/Shield/Debuff) | `utility` |
| `Hybrid-*` (Tank/DMG, INT/STR, APC/ADC) | `hybrid` |

Enemies: same shape from `enemy_roster.md` (tanky frame → `utility`/`hybrid`, dps → `damage`). Bosses: authored per kit. **CI guard** asserts every Def carries a valid `intent` (mirrors V.22).

### 3.3 Composer rework — `compose_stats` does a full compose

**Current pipeline** (`content.py`): `compose_stats` (multiplies named keys through `_PRIMARY_STAT`/`_RANGE`/`_DURABILITY`/`_PLAYSTYLE`, sets `attack_range` discretely, applies `_SPEED`, tier-scales **only** `max_hp/strength/intelligence/armor/resistance` via `√P(T,1)`) → `_assert_budget` → `_build_*` level-scales those same 5 by `√P(T,L)/√P(T,1)`, then **overwrites** `threat`/`move_speed`/`ability_cost` from the Def and adds `stat_overrides` flat-last.

**Reworked pipeline:**
1. `compose_stats(stat, reach, durability, playstyle, speed, intent, tier)` generates **every** stat from the axes — including `threat` (new weights below), `move_speed` (from `speed` axis), `mana_regen`, `attack_speed`. `ability_cost` becomes a module constant (`_ABILITY_COST = 36_000`), not a Def field (uniform; no axis varies it yet).
2. Tier-scale the 5 power stats by `√P(T,1)` (unchanged set — `threat`/`move_speed`/`mana_regen`/`attack_speed`/premium are **not** tier-scaled, as today).
3. **Intent multiplier** (§5) applied at one fixed point: after the axis loops + speed, **before** the tier `round()`.
4. **`stat_overrides`** applied **after tier-scale, before level-scale** (§3.5) — fixes the flat-last ordering.
5. `_build_*` level-scales the 5 power stats. `threat`/`move_speed`/`ability_cost` now read from the composed stats dict — the `d.threat`/`d.move_speed`/`d.ability_cost` passthrough is **deleted**.

**`threat` axis weights** (new — diversifies what was a uniform 60):
- `durability`: `tanky_hp`/`tanky_arm` **↑threat** (tanks pull aggro), `squishy` **↓threat**.
- `intent`: `utility` **↑threat**, `damage` **↓threat**, `hybrid` neutral.
- `playstyle`: `ability` slight **↓threat** (casters want to be ignored).

`move_speed` from `speed` axis: `speedy` ↑, `heavy` ↓, `hybrid` baseline 90.

### 3.4 Role classifier + `role_code` (pure function of the 6 axes)

8 roles, each = one distinct axis region. Replaces `_ROLE_FROM_AXES`.

| Role | Represents | Defined by |
|---|---|---|
| `tank` | frontline absorber | tanky frame, intent ≠ damage |
| `bruiser` | durable frontline that also deals damage | tanky frame, intent `damage` |
| `support` | team enabler (heal/buff/debuff) | intent `utility`, non-tanky |
| `mage` | ranged ability/INT burst | ranged + caster |
| `marksman` | ranged auto-attack DPS | ranged + auto |
| `assassin` | melee ability/INT burst diver | melee + caster |
| `swashbuckler` | melee auto-attack DPS | melee + auto |
| `spellblade` | all-hybrid generalist (no lane pinned) | `stat==hybrid AND intent==hybrid AND not caster`, non-tanky |

```python
def classify_role(stat, reach, durability, playstyle, speed, intent) -> str:
    tanky  = durability in ("tanky_hp", "tanky_arm")
    caster = (playstyle == "ability") or (stat == "int")
    if tanky:
        return "bruiser" if intent == "damage" else "tank"
    if intent == "utility":
        return "support"
    if stat == "hybrid" and intent == "hybrid" and not caster:
        return "spellblade"
    if reach == "melee":
        return "assassin" if caster else "swashbuckler"
    return "mage" if caster else "marksman"
```
- `tank↔bruiser`: split by **intent**. `tank↔support`: split by **frame**. `mage↔marksman` / `assassin↔swashbuckler`: split by **caster** (`caster = playstyle==ability OR stat==int`). `mage↔assassin` / `marksman↔swashbuckler`: split by **reach**.
- `speed` and the `tanky_hp`↔`tanky_arm` subtype do **not** change the title (stat flavour only) — they live in `role_code`.

**`role_code`** = the 6 axis tokens in fixed order `stat-reach-durability-playstyle-speed-intent`, **omitting every `hybrid` token**, joined by `-`:
```python
def build_role_code(stat, reach, durability, playstyle, speed, intent) -> str:
    toks = [stat, reach, durability, playstyle, speed, intent]
    return "-".join(t for t in toks if t != "hybrid")
```
e.g. `str-melee-tanky_hp-auto-heavy-damage`; `int-ranged-hybrid-ability-hybrid-utility` → `int-ranged-ability-utility`. `reach` is never `hybrid`, so `role_code` is never empty. Omitting `hybrid` is **lossless** (an absent axis = `hybrid` by position) → `role_code` is **injective** over the 648 combos, so it trivially maps to exactly one role.

**Consumption contract (V — §10):** `role_code` is a **deterministic ordered tag-set**, consumed by **membership/substring** (`"utility" in code`), **never positional** (dynamic length). Programmatic consumers read the first-class fields `role` and `intent`; nobody parses `intent` out of `role_code`. → omission is safe for any future mission/quest/filter system; none consume `role_code` today.

### 3.5 `stat_overrides` — scope + ordering

- **Scope = all stats, incl. premium.** Mechanically already true (`_apply_stat_overrides` adds to every base key, and `crit_chance`/`penetration`/`penetration_pct` are in `_BASE_STATS`). Make it explicit: **validate every override key** against the known stat set (typo = error, V.15 philosophy).
- **Ordering = after tier-scale, before level-scale** (your call). So a scalable override **level-scales** (proportionally stable across L1→L3); a non-scaled/premium override (pen/crit/threat) stays **flat** (the level step only multiplies the 5 power stats, so it never touches them either way). Worked examples on a T5 piece:
  - `+10 STR` (scalable): old = `base·√P(T5,L) + 10` (flat, vanishes relatively at L3); new = `(base·√P(T5,1) + 10)·levelscale` → the +10 grows with level, a constant proportion.
  - `+10 pen` (non-scaled, build-around per B.6): **identical both ways** — `10` at every tier/level; pen is in neither scale loop.
- **Budget guard** (`_assert_budget`) compares override deltas against the **tier-scaled-L1 baseline** (the new application point); guard covers only **power-contributing** stats — **threat, move_speed, crit, penetration are exempt** (off the P budget by design — B.6).

### 3.6 Intent stat-bias is NOT a free power buff — the drift guard

"Power" `P` (scaling.py) is the combat-value budget ≈ `HP × DPS`. Only these feed it: HP side `max_hp/armor/resistance`; DPS side `strength/intelligence/attack_speed`. **`threat`/`move_speed`/`mana_regen`/`attack_range`/`crit`/`penetration` are NOT power stats** — so the intent threat-bias (§3.3) cannot break a power budget; it's free. The drift guard only watches the intent multiplier's net effect on the HP·DPS proxy:

**Guard (option a) — unit-tested per intent:** (`dmg_mult` = the damage-stat multiplier — identical for `strength`/`intelligence` under a given intent)
```
(dmg_mult · AS_mult) · sqrt(hp_mult · armor_mult · res_mult)  ∈  [0.90, 1.10]
```
So `damage`/`utility` **re-flavour** a piece (bursty-fragile / durable-enabling) at ~equal total power, not a stealth buff. (Stat changes during tuning are expected — the guard isn't "don't change stats"; it's "intent must not silently move total power.")

## 4. Decisions stated

1. **No `controller` role** — role is a pure function of the 6 axes; buff-vs-debuff isn't an axis (it's kit/trait behaviour, e.g. Trickster=debuff). Utility → `support`.
2. **No 7th axis** — threat diversity comes from composing across `durability`/`intent`/`playstyle`; axis count stays 6.
3. **`role` reused** for the coarse title (not `primary_role`); **`role_code`** for the fine descriptor (not `secondary_role_signature`) — "primary/secondary" wrongly implies importance; `role` = coarse title, `role_code` = fine encoding.
4. **`ability_cost`** → module constant (uniform; demote from Def field); revisit if a future axis needs to vary it.

## 5. Authored values (intent multiplier — conservative first pass, tunable)

| Stat | `damage` | `utility` | `hybrid` |
|---|---|---|---|
| `strength`/`intelligence` | ×1.08 | ×0.94 | — |
| `attack_speed` | ×1.05 | ×0.96 | — |
| `max_hp` | ×0.96 | ×1.08 | — |
| `armor`/`resistance` | ×0.97 | ×1.05 | — |
| `mana_regen` | ×0.97 | ×1.08 | — |
| `threat` | ×0.92 | ×1.10 | — |

(utility also biases armor/res, per decision.) These satisfy the §3.6 guard: damage `(1.08·1.05)·√(0.96·0.97·0.97) ≈ 1.08` ✓; utility `(0.94·0.96)·√(1.08·1.05·1.05) ≈ 0.98` ✓. Threat sits outside the guard. `hybrid` = identity (no drift, no test churn for hybrid-intent pieces). All first-pass; balance via the T.25 sim sweep.

## 6. Content / roster audit + reconciliation

- **Drift caught:** `t5_content_plan.md` says "4 orthogonal axes" but code has 5 (`speed` added post-t5). Reconcile docs to 6 (this task). → §B entry.
- **Intent authoring:** all 60 champs + 60 enemies + 6 bosses get `intent` from roster archetype tags (§3.2). Diff code vocabulary against `champion_roster.md`/`enemy_roster.md` archetype column; reconcile.
- **V-guard:** every Def carries valid `intent`; `role`/`role_code` are pure deterministic axis functions — CI-tested (mirrors V.22).

## 7. Open questions

**Resolved here (proposals confirmed by user in planning):** 6-axis taxonomy + renames; 8-role set incl. `spellblade`; `role_code` strips `hybrid`, tag-set semantics; threat composed (no 7th axis); override scope=all-stats + ordering after-tier-before-level; drift guard option (a); no `controller`.

**Still open / deferred:**
- Intent-multiplier magnitude tuning (first pass shipped; sim-sweep follow-up).
- Whether `formation.classify_role` (placement) should become `intent`-aware vs stay frame/reach-based (kept as-is for now — placement ≠ identity).
- Whether the recurring `hybrid` token in non-`role_code` surfaces (e.g. admin filters) needs disambiguation UI.

## 8. Test plan

- **Classifier:** `classify_role` unit table — all 8 roles reachable; spot-check the splits; **full 648-combo enumeration** asserted against `t32_role_matrix.txt` (regenerated, diffed). Assert every `role_code` maps to ≤1 role (injectivity).
- **role_code:** `hybrid`-omission cases; never empty; tag-membership lookups.
- **Composer:** `threat`/`move_speed` now vary by axis (not constant); `ability_cost` constant; dead Def fields removed (construct without them).
- **Intent bias:** drift guard `[0.90,1.10]` asserted for `damage`/`utility`; `hybrid` byte-identical to pre-change (no drift).
- **stat_overrides:** all-stat incl. crit/pen; key validation rejects typos; ordering — `+10 STR` level-scales, `+10 pen` flat across L1/L3.
- **Determinism (V.2/V.14):** fixed seed + `workers=1` → byte-identical `BattleResult`; sim baseline regenerated (expected, since damage/utility pieces shift) and re-committed.
- **Regression:** `encounter` composition still satisfies its fuzzy template after switching to `intent`; `matchup.py`/`inspect`/`admin` emit/filter the new fields.

## 9. Acceptance criteria

1. `ChampionDef`/`EnemyDef`/`BossDef` carry valid `intent ∈ {damage,hybrid,utility}`; CI-guarded.
2. `compose_stats` full-composes every stat; `threat`/`move_speed`/`ability_cost` no longer authored per-unit; `d.*` passthrough removed.
3. `Champion`/`Enemy` export `role` (coarse, 8-role classifier), `role_code` (fine, hybrid-stripped), `intent`; serialized round-trip + back-compat read.
4. `classify_role` + `build_role_code` are pure deterministic functions of the 6 axes; the 648-combo matrix validates (0 role_codes → >1 role).
5. `stat_overrides` apply to all stats incl. premium, with key validation, after-tier-before-level ordering; budget guard on power stats only.
6. Intent stat-bias passes the `[0.90,1.10]` drift guard; `hybrid`-intent pieces byte-identical to pre-change.
7. `encounter`/`formation`/sim/inspect/admin/UI consume the new fields; full suite green; sim baseline regenerated.

## 10. SPEC changes needed (for `/spec`)

- **§T:** add row **T.32** — "Role system revamp — `intent` 6th axis + composer full-rework + 8-role `classify_role`/`role_code` + `stat_overrides` scope/ordering fix" — files `game/content.py`, `game/models.py`, `game/encounter.py`, `game/formation.py`, `tools/simulation/matchup.py`, `tools/playtest/*`, `ui/*`, `docs/design/tasks/t32_*` — Depends T.5,T.18,T.19,T.24,T.25 — Est M — Status 📋 Plan.
- **§V new invariants:**
  - **V.31** — Every `ChampionDef`/`EnemyDef`/`BossDef` carries a valid `intent ∈ {damage,hybrid,utility}`; CI-guarded (mirrors V.22).
  - **V.32** — `role` (coarse, 8 titles) and `role_code` (fine, `hybrid`-stripped) are **pure deterministic functions of the 6 axes** — no RNG, no traits, no kit. `role_code` is a non-positional tag-set; programmatic consumers read `role`/`intent`, never parse `role_code`.
  - **V.33** — Every stat is generated by `compose_stats` from the 6 axes (no per-unit authored stat except `stat_overrides`); the intent multiplier applies at one fixed point and keeps the HP·DPS power proxy within ±10% (`threat`/`move_speed`/premium are off-budget by design).
- **§B backprop:** entry — `t5_content_plan.md` "4 orthogonal axes" drifted from code's 5; T.32 reconciles to 6 + adds the V.31/V.33 guards so axis count can't silently drift again.
- **§D:** mark D.10 (role archetypes) resolved by T.32 for the taxonomy half.
- **Implementation Order:** insert T.32 in Phase 1b after T.5 (content), independent of the trait/item/augment chain (it only refactors content + classification).
