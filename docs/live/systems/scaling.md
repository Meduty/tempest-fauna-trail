# Stat scaling

> **Status: LIVING** — must match `src/game/scaling.py` + `content.py` stat curves. Audited by `/check`.
> **Scope:** the power curve P(tier,level), the three stat-scaling classes, baseline parity, and the combat tie-break. **Reconciled:** 2026-07-01 (T.33a/b).

## Power curve
- `power(tier, level) = 2 ** ((tier-1)/3 + triplings[level])`, `triplings = {1:0, 2:1, 3:3}` (T.18). `tier ∈ [1,10]`, `level ∈ [1,3]` — out of range raises `ValueError`.
- Level-ups are a **tripling** mechanic (mirrors TFT 3-to-1): 3 copies → L2 (1 tripling), 9 → L3 (3 triplings). Accelerating: L1→L2 is `√2` in stats, L2→L3 is `×2`. `LEVEL_UP_MOD = 2.0`, `TIER_UP_MOD = 2**(1/3) ≈ 1.26` (three tier-ups = one tripling of power); `LEVEL_STEP`/`TIER_STEP` are back-compat aliases.
- `stat_multiplier(tier, level, exponent=PRIMARY_EXPONENT) = power(tier, level) ** exponent`. At the default `0.5` this is `sqrt(power)`, so HP·DPS ∝ P and encounter budgets stay **linear** in P.
- `scale_stat(base, tier, level) -> int` — one-shot `round(base * stat_multiplier(...))` for a single primary value (used where a full dict isn't in play).

## Three scaling classes (T.33, V.34)
Every base stat is in exactly one class; both curves ride the same `power` curve at a different exponent:

| class | stats | exponent | per-tier | T1L1→T10L3 |
|---|---|---|---|---|
| `PRIMARY_SCALABLE_STATS` | `max_hp` `strength` `intelligence` `armor` `resistance` | `PRIMARY_EXPONENT=0.5` (`sqrt(power)`) | ≈ ×1.122 | ×8 |
| `SECONDARY_SCALABLE_STATS` | `attack_speed` `move_speed` `mana_regen` `threat` | `SECONDARY_EXPONENT=0.0857` | ≈ ×1.02 | ×1.428 |
| `FLAT_STATS` | `attack_range` | — | — | — |

`crit_chance`/`penetration`/`penetration_pct` are ratios, off the scaling model. `SCALABLE_STATS` is a deprecated alias of the primary tuple. `level_scale_stats(stats, tier, level)` applies both curves in place — the single source of truth for the four builders (`content._build_champion`/`_build_enemy`, `encounter._instantiate_enemy`/`_champion_def_to_enemy`). `threat`/`move_speed` stay **off** the HP·DPS power budget (V.33, B.6).

## Quantities: int except attack_speed
Stored quantities (hp, damage, mana, `move_speed`/`mana_regen`/`threat`, costs, energy meters) are **int**; the ratio stats **and `attack_speed`** are float. `attack_speed` is a float (T.29-pre, amends V.34): cadence reads `int(attack_speed)`, and the sub-integer precision for same-tick ordering derives from the **same** value via `round(attack_speed × 1000)` — there is no separate `milli_AS` field. Because weather now applies as `mul` modifiers (not a base fold), `attack_speed` stays float through level **and** combat.

## Speed-stat baseline parity (#39, V.35)
`_BASE_STATS` `attack_speed == move_speed == mana_regen == 100` so the three speed stats compare directly as power investments. The per-meter capacitor is deliberately unequal and non-player-facing: mana `mana_cost` baseline `300_000` ≫ action/move `ENERGY_THRESHOLD = 60_000` (a cast ≈ 5 autos). `mana_cost` 300_000 (vs cadence-neutral 360_000) is a deliberate ~20% mage buff; `move_speed` 90→100 a ~11% movement buff. **T.29c (V.48):** cast cost is no longer a per-piece `ability_cost` FLAT stat — it is authored **per-ability** on the ability def (`ABILITY_MANA`, default `300_000`); bosses register their own (380k–520k). `max_mana` defaults to `2×mana_cost` (overload headroom).

## Speed axis — 7 levels (T.33b)
`_SPEED` (content.py): `moloch` / `leaden` / `heavy` / `hybrid` / `light` / `swift` / `blazing`, slow→fast. Faster ⇒ ↑`move_speed`, ↓`primary_stat` (softer per-hit/cast), and a tempo gain that **routes by playstyle**: auto/hybrid pieces get the full `attack_speed` mult; `ability` casters get **half** the AS deviation applied to *both* `attack_speed` and `mana_regen` (more, softer casts) — speed no longer touches `resistance`. Roughly power-neutral (cadence up, per-hit down). `hybrid` is the neutral centre (omitted from `role_code`). Widening 3→7 took the role-code space to 1512 combos (V.32); `classify_role` ignores speed, so role *titles* are unaffected. The full 60-champion + 60-enemy roster is assigned across the 7 levels by theme + within-tier AS spread (54/60 champions distinct-AS within their tier).

## Combat tie-break (V.34, fixes B.14)
Same-tick action order is the canonical side-independent total order in `_event_sort_key` (`combat/engine.py`):
`(-round(attack_speed × 1000), champion_id, load_order, kind)` — the quantized AS key (T.29-pre) is monotonic in the float `attack_speed`, so it subsumes the old coarse `-AS_int` level and the separate `milli_AS` field in one term.
- `load_order` — a seeded, side-independent permutation assigned in `compile_loadout` (never team-block-then-enemy), so equal-AS ties never systematically favour the player team (the old B.14 bug). Renamed from the overloaded `speed_tiebreaker`; the formation-position key is now `formation_index`.

## Where it lives
- `scaling.py` — power curve, the three class tuples + exponents, `stat_multiplier`, `level_scale_stats`, `scale_stat`.
- `content.py` — base stat blocks, axis multipliers, `compose_stats` (`attack_speed` kept float). Cast cost is authored per-ability via `ABILITY_MANA` / `DEFAULT_MANA_COST` in `registries.py` (the former `_ABILITY_COST` baseline).
- `combat/engine.py` — `_event_sort_key`. `loadout.py` — `load_order`/`formation_index` assignment, weather application.
- `tools/gen_role_matrix.py` — regenerates `docs/design/tasks/t32_role_matrix.txt`.
