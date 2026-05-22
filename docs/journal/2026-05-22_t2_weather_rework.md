# Journal - 2026-05-22 (T2 Weather System Rework)

## Scope and User Intent

User proposed a rework of the T2 weather system and asked for a review focused
on preparation-for-a-fight and teambuilding UX. The session converged the
design, rewrote every affected design document, then implemented the code.
Started from: T2/T3 already implemented (symmetric "Variant B" pentagon).

## Chronological Protocol

1. **Review.** Read the shipped `t2_weather_effects_plan.md`, `weather_effects.py`,
   `models.py`. Reviewed the proposal: a directed predator/prey ring with node
   weather buffing self+predators / debuffing prey, plus a per-hit damage
   triangle. Flagged a wart — "W is second-best at its own node" — which was
   **my own error**: I had summed the two systems into one ranking.

2. **Decoupling correction.** User: the two systems are decoupled, never summed.
   System A (node weather) is enemy-independent; System B (damage triangle) is
   weather-independent. Self is the strict System-A maximum. Re-derived the
   model on that basis.

3. **Magnitude tuning.** User flagged the predator/prey exchange as too swingy
   at `1.2/0.8` (1.5× exchange). Settled System B at `1.10/1.05/1.00/0.95/0.90`
   (primary exchange ~1.22×). System A locked to strong/medium/weak buff +
   medium/weak debuff.

4. **Plan rewrite.** Rewrote `t2_weather_effects_plan.md` end to end.

5. **Doc sweep.** User: "rewrite all design documents first, then code."
   Grepped for every weather reference; updated 8 further docs. Journals left
   untouched (historical record).

6. **Code.** Implemented in order: `models.py` → `weather_effects.py` →
   `combat.py` → `combat_log.py` → tests. `pytest tests/` — 61 passed.

## Repo Changes Summary

- Rewrote: `docs/design/tasks/t2_weather_effects_plan.md` (full),
  `src/game/weather_effects.py` (full), `tests/game/test_weather_effects.py`
  (full, 28 tests).
- Modified docs: `SPEC.md` (V.6, T.2 row + notes, B.5 backprop, weather table),
  `t3_combat_engine_plan.md`, `t1_model_contracts.md`,
  `t20_ability_framework_plan.md`, `t21_challenge_boss_plan.md`,
  `t19_encounter_generation_plan.md`, `combat_system_proposal.md`,
  `views_spec.md`.
- Modified code: `src/game/models.py` (`CombatPieceState += affinity`),
  `src/game/combat.py` (System-B damage hook, `apply_weather` rename),
  `src/game/combat_log.py` (`apply_weather` rename).
- Modified tests: `test_combat.py` (`_state` gains `affinity`, new System-B
  test), `test_models.py` (`CombatPieceState` ctor gains `affinity`).
- Added: this journal.

## Key Design Decisions

### The ring

- Directed predator/prey ring: `Mist → Cloudy → Rain → Snow → Thunder → Mist`
  (reordered from the old `Cloudy → Mist → Snow → Rain → Thunder`). Each weather
  preys on the previous (primary) and prev-prev (secondary); predators are the
  inverse. `Clear` sits outside — inert in both systems.

### Two decoupled systems

- **System A — node weather.** Buffs/debuffs each piece by affinity vs node
  weather. 5 tiers: strong/medium/weak buff (self / primary predator /
  secondary predator) `+10/+6/+3%`; medium/weak debuff (primary/secondary prey)
  `−6/−3%`. Self is the strict maximum; no strong debuff (weather is net-kind).
  Applied once at combat init.
- **System B — affinity damage triangle.** Per-hit multiplier on every damage
  instance by attacker vs defender affinity: `1.10/1.05/1.00/0.95/0.90`.
  Resolved per hit in the combat engine — depends on the defender, cannot be
  pre-snapshotted.
- The systems are **never summed**. System A asks "does the weather suit me?";
  System B asks "do I beat this enemy?". They are evaluated separately.

### Implementation

- `combat_modifier` scales a per-weather `±10%` base by the tier scalar
  (`1.0/0.6/0.3`). `Mist`'s flat `attack_range −1` survives the medium tier and
  rounds away at the weak tier.
- `CombatPieceState` gained an `affinity` field (SPEC B.5) so the engine can
  resolve System B per hit. `apply_modifier` renamed `apply_weather`.

## Open Items / Deferred

- T20: ability damage must route through the engine's shared damage path so
  System B applies to spell damage (noted in the T20 plan).
- `views_spec.md` weather panels updated only minimally — the doc is still
  flagged stale for the broader D.16 sync.
- Magnitude tuning is locked but unplaytested — no balance pass yet.

## Verification

- `pytest tests/` — **61 passed**. Per file: `test_weather_effects` 28,
  `test_combat` 19, `test_models` 7, `test_combat_log` 7.
- System-B behavior checked end to end: RAIN enemy (armor 0), raw auto 50 →
  SNOW predator hits `55` (×1.10), CLOUDY prey hits `45` (×0.90).
- `CLEAR`-affinity pieces verified inert in both systems — existing combat and
  combat-log golden tests unchanged.
- Doc-consistency grep clean: no `pentagon` / `Variant B` / `apply_modifier` /
  `DEBUFFED_AFFINITIES` left outside intentional supersede/rename notes.

## Reflection

- The one substantive mistake was summing the two systems into a single
  "best affinity at this node" score during the review — which produced a
  phantom design wart. The fix was conceptual, not numeric: the systems answer
  different questions and must be reasoned about independently.
