# Weather — Favor & Affinity Clash

> **Status: LIVING** — must match `src/game/weather_effects.py` + `loadout._apply_weather_to_piece`. Audited by `/check`.
> **Scope:** the two decoupled weather systems and the single place each is applied. **Reconciled:** 2026-06-05 @ refactor/combat-engine-single-source.

Six weather states (V.5): `CLEAR, CLOUDY, MIST, RAIN, SNOW, THUNDER`. Each piece
carries exactly one `affinity: WeatherState` (V.6). `CLEAR` sits outside the
predator/prey ring and is inert in both systems. The two systems are **never
summed**:

## 1. Weather Favor — `combat_modifier`

"Does the node weather suit my affinity?" A 5-tier stat buff/debuff
(`combat_modifier(affinity, weather) -> CombatModifier`) driven by the
directional predator/prey ring. Applied **once at combat init**, in exactly one
place: `loadout._apply_weather_to_piece` mutates the `Piece.base_stats`
(integer-scaled, `round(value × mult)`, `attack_range` clamped ≥ 1). There is no
other application path — the old `weather_effects.apply_weather` snapshot and
the `CombatPieceState` model it built were removed (one source of truth).

## 2. Affinity Clash — `damage_modifier`

"Do I beat this enemy?" A per-hit multiplier `damage_modifier(attacker_affinity,
defender_affinity)` applied on **every damage instance** inside the damage
pipeline (see [combat.md](combat.md#damage-pipeline)). It depends on the
defender, so it can't be pre-snapshotted — it's resolved per hit, not at init.

## Why decoupled

Favor asks about the *node*; Clash asks about the *opponent*. Keeping them
separate means weather tuning and matchup tuning don't entangle. Both read the
same predator/prey ring (`ring_relation`) but apply at different times to
different magnitudes (`combat_modifier` stat packs vs `damage_modifier`
multiplier).

## Also here

`shop_weight(affinity, weather)` — prep-shop pull weight by ring relation
(content economy, not combat).

## File map

| Concern | Symbol |
|---|---|
| Ring relation (predator/prey) | `weather_effects.ring_relation` |
| Weather Favor stat pack | `weather_effects.combat_modifier` → `CombatModifier` |
| Weather Favor application (only path) | `loadout._apply_weather_to_piece` |
| Affinity Clash per-hit multiplier | `weather_effects.damage_modifier` |
| Shop pull weight | `weather_effects.shop_weight` |
