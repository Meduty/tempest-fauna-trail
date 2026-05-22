# Journal - 2026-05-22 (T3 Combat Engine)

## Scope and User Intent

Session goal: implement T3 (combat engine) against `docs/design/t3_combat_engine_plan.md`. Plan was already written and locked in a prior session. No design iteration this session — pure implementation against the plan document.

## Chronological Protocol

1. Read `docs/design/t3_combat_engine_plan.md`, `SPEC.md`, `src/game/models.py`, and `src/game/weather_effects.py` to establish the full input/output contract and all pre-existing structures.
2. Confirmed all T1 + T2 outputs available: `Champion`, `Enemy`, `CombatPieceState`, `BattleEvent`, `BattleResult`, `CombatOutcome`, `WeatherState`, and `apply_modifier`. Test suite green at 34/34 before touching anything.
3. Implemented `src/game/combat.py`:
   - Module-level constants: `TICK_MS=10`, `ROUND_TICKS=600`, `ENERGY_THRESHOLD=60_000`, `MAX_TICKS=7_200`, `BOARD_WIDTH=10`, `BOARD_HEIGHT=7`.
   - Effective stat helpers: `effective_as`, `effective_ms`, `effective_mr_tick` — integer-only, returns the raw stat, structured as functions for future status-effect gates.
   - `hex_distance` (axial cube formula) + `_on_board` bounds check.
   - `_assign_spawns`: team to left columns (low q), enemies to right (high q), stable by input index, rows round-robin within BOARD_HEIGHT.
   - `_select_target`: deterministic priority — `(-threat, distance, hp_pct, hp, piece_id)` with `min` giving total order.
   - `_next_step_toward`: multi-source BFS outward from all goal cells (free on-board cells within attack_range of a living enemy), then step into the free neighbour of start with minimum distance-to-goal. Fixed `HEX_DIRECTIONS` order breaks ties.
   - `_mitigated_damage` + `_apply_hit`: bounded reduction `stat/(stat+100)`, typed damage (physical/magical/true), clamp to ≥1, records attack/cast + death `BattleEvent`, updates both aggregate dicts.
   - `_resolve_movement`: in-range → hold; else BFS step; no path → hold. Overflow carries on step; clamps to threshold on hold.
   - `_resolve_action`: cast (mana full, any living enemy) → auto (enemy in attack_range) → idle-hold. Mana reset to 0 after cast. Overflow carries on real action; clamps on idle.
   - `_event_sort_key`: primary sort `(-effective_as, -attack_speed, speed_tiebreaker)`, secondary `movement < action` for same piece.
   - `resolve_combat`: snapshots team + enemies through `apply_modifier`; assigns `speed_tiebreaker` by input index; runs tick loop; builds `BattleResult`.
4. Wrote `tests/game/test_combat.py` (18 tests covering all plan §6 groups):
   - 6.1 Determinism: same inputs → byte-equal `to_dict()`.
   - 6.2 Outcomes: WIN at tick 1, LOSS when team dies, DRAW timeout with `turns=0`, `timed_out=True`, `duration_ticks=MAX_TICKS`.
   - 6.3 Meters: overflow-carry test (attack_speed=25000 → attack ticks [3,5], not [3,6]); movement-hold-in-range (attack_range=12, no move events); idle-hold produces no actions.
   - 6.4 Targeting: threat > distance (high-threat far enemy targeted first); full tie chain to piece_id unit-tested via `_select_target` directly; dead target triggers retarget to second enemy.
   - 6.5 Pathing: `_next_step_toward` unit tests — piece at (0,0), blocker at (1,0), routes via (0,1); both on-board neighbours blocked returns None.
   - 6.6 Weather: THUNDER-affinity champion's first-hit damage under `WeatherState.THUNDER` (STR ×1.10) exceeds the same under `WeatherState.CLEAR`.
   - 6.7 Integrity: `turns` == len(attack+cast events); `rounds` == ceil(duration/600); sum of `damage_dealt` == sum of `damage_taken`; survivors and the dead are disjoint.
   - Additional: cast path produces magical damage events and resets mana; effective stat helpers are integer identities; board constants correct.
5. `python -m pytest tests/ -q` → 52 passed (34 prior + 18 new).

## Repo Changes Summary

- Added: `src/game/combat.py`
- Added: `tests/game/test_combat.py`
- Added: `src/game/combat_log.py` (combat log continuation, see below)
- Added: `tests/game/test_combat_log.py` (combat log continuation, see below)
- No changes to `SPEC.md`, models, or weather effects.

## Key Technical Outcomes

- Engine is pure: `apply_modifier` snapshots weather once; loop mutates only `CombatPieceState` copies; `Champion`/`Enemy` inputs are never touched.
- Determinism: no randomness anywhere. Collections sorted before selection; `HEX_DIRECTIONS` fixed; `speed_tiebreaker` unique per piece → total sort order.
- Tick loop structure: meter update → collect triggers → sort → resolve each event sequentially; dead-skip guard on every event; break inner+outer on combat end.
- Meter semantics: overflow carries on real actions/steps (`energy -= THRESHOLD`); idle/hold clamps to exactly `THRESHOLD` so piece re-evaluates each tick without accumulation.
- Pathing: multi-source BFS from goal cells (free cells within attack_range of any living enemy) outward over free tiles; pick min-dist free neighbour of start. Fully deterministic, O(board_size) per step.
- BFS goals defined as "within attack_range", not just adjacent — correct for ranged pieces; movement-hold trigger uses the same check.
- Cast targeting ignores range per plan §3.3 (plan distinguishes "valid target exists" for cast vs "in attack_range" for auto). Noted in module docstring.
- `team_damage_dealt` / `team_damage_taken` keyed by all piece ids (both sides) initialised to 0 — consistent, deterministic, T13-friendly.
- `turns` counts resolved action events (attack + cast) only; `rounds = ceil(duration_ticks / ROUND_TICKS)` via integer arithmetic.
- `EVENT_DEATH` actor = victim, target = killer — makes "who died" the subject; consistent with T12 animation expectations.

## Continuation - Combat Log Layer

User follow-up after T3 landed: "build a step by step execution of the simulation with a combat log" — usable both by the game (T12 combat view) and for testing.

Note: the T3 engine already emits the step-by-step record as the tick-ordered `BattleEvent` stream inside `BattleResult`. What was missing was a readable rendering layer. Built as a separate pure module rather than touching the engine or the T1 `BattleEvent` model.

1. Implemented `src/game/combat_log.py`:
   - `group_events_by_tick(result)` → `[(tick, [events])]` — contiguous per-tick grouping. The T12 UI walks this for tick-paced animation.
   - `format_combat_log(result, *, team=None, enemies=None)` → `list[str]` — ordered log lines. Header (node / weather / rosters) → per-tick blocks (move / attack / cast / death) → footer (outcome, duration·rounds·turns, survivors, damage dealt).
   - `render_combat_log(...)` → joined `str` for golden-snapshot tests.
   - Optional `team` / `enemies` args enable a running `(target: before -> after)` HP trace. HP is reconstructed inside the formatter by replaying event `amount`s against `apply_modifier` max-HP — no engine change, no new `BattleEvent` field. Omitting the rosters degrades to damage-numbers-only.
2. Wrote `tests/game/test_combat_log.py` (7 tests): tick-grouping contiguity + ordering, header/footer/attack-line content, running HP trace, no-roster degrade, stalemate empty-log path, cast + move line rendering, determinism.
3. `python -m pytest tests/ -q` → 59 passed (52 + 7).

### Combat Log Decisions

- HP trace reconstructed in the formatter, not stored on `BattleEvent` — keeps the T1 model contract untouched. Reconstruction is exact: a piece's HP = max_hp − Σ(event amounts targeting it so far).
- `EVENT_MOVE` / `EVENT_ATTACK` / `EVENT_CAST` / `EVENT_DEATH` constants imported from `combat.py` — single source of truth. `combat_log` imports `combat` one-directionally; no cycle.
- Module is pure, no Flet imports — V.1 holds. Output is a deterministic function of the `BattleResult`.

## Deferred (plan §4b)

- Status effects (stun/silence/disarm/root): `active_statuses` + hook gates at meter/action/movement/damage. Not started.
- Ability/passive framework: `AbilityRegistry`, typed event bus, per-piece active/passive handlers. Not started.
- These are formally deferred in SPEC.md §D.3–D.5.

## Verification

- Test command: `python -m pytest tests/ -q`
- Final observed status: 59 passed, 0 failed.
