# Stat scaling

> **Status: LIVING** — must match `src/game/scaling.py` + `content.py` stat curves. Audited by `/check`.
> **Scope:** the power curve P(tier,level), the three stat-scaling classes, baseline parity, and the combat tie-break. **Reconciled:** 2026-06-05 (T.33a/b).

## Power curve
- `power(tier, level) = 2 ** ((tier-1)/3 + triplings[level])`, `triplings = {1:0, 2:1, 3:3}` (T.18).
- `stat_multiplier(tier, level, exponent=PRIMARY_EXPONENT) = power(tier, level) ** exponent`.

## Three scaling classes (T.33, V.34)
Every base stat is in exactly one class; both curves ride the same `power` curve at a different exponent:

| class | stats | exponent | per-tier | T1L1→T10L3 |
|---|---|---|---|---|
| `PRIMARY_SCALABLE_STATS` | `max_hp` `strength` `intelligence` `armor` `resistance` | `PRIMARY_EXPONENT=0.5` (`sqrt(power)`) | ≈ ×1.122 | ×8 |
| `SECONDARY_SCALABLE_STATS` | `attack_speed` `move_speed` `mana_regen` `threat` | `SECONDARY_EXPONENT=0.0857` | ≈ ×1.02 | ×1.428 |
| `FLAT_STATS` | `attack_range` `ability_cost` | — | — | — |

`crit_chance`/`penetration`/`penetration_pct` are ratios, off the scaling model. `SCALABLE_STATS` is a deprecated alias of the primary tuple. `level_scale_stats(stats, tier, level)` applies both curves in place — the single source of truth for the four builders (`content._build_champion`/`_build_enemy`, `encounter._instantiate_enemy`/`_champion_def_to_enemy`). `threat`/`move_speed` stay **off** the HP·DPS power budget (V.33, B.6).

## All quantities are int
Stored quantities (hp, damage, mana, speeds, costs, energy meters) are **int**; only the ratio stats are float. Speeds round to int; the sub-integer attack-speed precision needed for ordering lives in a dedicated int field `milli_AS = round(exact_scaled_AS × 1000)`, threaded through level + weather alongside `attack_speed`.

## Speed-stat baseline parity (#39, V.35)
`_BASE_STATS` `attack_speed == move_speed == mana_regen == 100` so the three speed stats compare directly as power investments. The per-meter capacitor is deliberately unequal and non-player-facing: mana `ability_cost` baseline `300_000` ≫ action/move `ENERGY_THRESHOLD = 60_000` (a cast ≈ 5 autos). `ability_cost` 300_000 (vs cadence-neutral 360_000) is a deliberate ~20% mage buff; `move_speed` 90→100 a ~11% movement buff. Boss costs ×10.

## Speed axis — 7 levels (T.33b)
`_SPEED` (content.py): `leaden` / `heavy` / `steady` / `hybrid` / `brisk` / `speedy` / `blinding`, slow→fast. Faster ⇒ ↑`move_speed`, ↓`primary_stat` (softer per-hit/cast), and a tempo gain that **routes by playstyle**: auto/hybrid pieces get the full `attack_speed` mult; `ability` casters get **half** the AS deviation applied to *both* `attack_speed` and `mana_regen` (more, softer casts) — speed no longer touches `resistance`. Roughly power-neutral (cadence up, per-hit down). `hybrid` is the neutral centre (omitted from `role_code`). Widening 3→7 took the role-code space to 1512 combos (V.32); `classify_role` ignores speed, so role *titles* are unaffected. The full 60-champion + 60-enemy roster is assigned across the 7 levels by theme + within-tier AS spread (54/60 champions distinct-AS within their tier).

## Combat tie-break (V.34, fixes B.14)
Same-tick action order is the canonical side-independent total order in `_event_sort_key` (`combat/engine.py`):
`(-AS_int, -milli_AS, champion_id, load_order, kind)`.
- `load_order` — a seeded, side-independent permutation assigned in `compile_loadout` (never team-block-then-enemy), so equal-AS ties never systematically favour the player team (the old B.14 bug). Renamed from the overloaded `speed_tiebreaker`; the formation-position key is now `formation_index`.

## Where it lives
- `scaling.py` — power curve, the three class tuples + exponents, `stat_multiplier`, `level_scale_stats`.
- `content.py` — base stat blocks, axis multipliers, `compose_stats` (incl. `milli_AS`), `_ABILITY_COST`.
- `combat/engine.py` — `_event_sort_key`. `loadout.py` — `load_order`/`formation_index` assignment, weather application.
- `tools/gen_role_matrix.py` — regenerates `docs/design/tasks/t32_role_matrix.txt`.
