# Combat — engine & resolution

> **Status: LIVING** — must match `src/game/combat/`, `src/game/loadout.py`, `src/game/piece.py`. Audited by `/check`.
> **Scope:** how one battle resolves end-to-end: entry → compile → tick loop → result. **Reconciled:** 2026-06-05 @ refactor/combat-engine-single-source.
>
> Citations are by **symbol** (file + `function`), not line number, on purpose — lines drift, symbols don't. Design rationale lives in the frozen `docs/design/systems/combat_system_proposal.md` + `docs/journal/`.

## Entry point (the only one)

`resolve_combat(team, enemies, weather, *, node_id="") -> BattleResult` in
`combat/resolve.py` is the **single public combat entry** (V.2). It is pure and
deterministic: identical inputs → byte-identical `BattleResult`. It delegates the
setup to the shared `build_combat(...)` helper (the **one** wiring path) then
runs the loop:

```
ctx, recorder = build_combat(team, enemies, weather, run_mods, node_id, seed)  # resolve.py
#   = compile_loadout (pieces, bus) → assign_spawns → recorder.register → CombatContext
winner = run(ctx, recorder)                                                    # combat/engine.py
return recorder.build_result(winner)                                           # combat/recorder.py
```

`build_combat` is reused (no parallel setup, T.37b) by:
- **`resolve_boss_combat`** (`combat/resolve.py`, T.12b/V.59 — the **single src-side
  boss entry**; `tools/playtest/_common` delegates to it) — same `build_combat`, then
  `attach_map_effect(map_effect_id, ctx, seed)` before `run`. Takes a `map_effect_id:
  str` (never a `bosses/` content type ⇒ `combat/` stays content-import-free);
  byte-identical to the former `tools/` version (V.2). `CombatReplay`/`inspect_at_tick`
  accept the same `map_effect_id` to replay a boss fight; `CombatReplay.board_cells()`
  exposes the map-effect tiles as `(q,r,kind)` for the view overlay (V.1).
- **`CombatReplay` / `inspect_at_tick`** (`combat/replay.py`) — `build_combat(...,
  with_recorder=False)`, then steps the `_step_combat` generator to read live
  state (see [Replay](#replay)).

## The pieces

- **`compile_loadout`** (`loadout.py`) — builds runtime `Piece`s from
  `Champion`/`Enemy` models, **uniquifies duplicate piece ids** (B.65 — the 2nd+
  occurrence of a def id gets a deterministic `#n` suffix, e.g. `wolf`,
  `wolf#1`, `wolf#2`; done in assembly order *before* any hook closes over the
  piece, so the fight is object-identity-based and unaffected while the recorded
  stream / per-id tallies / view control keys stay collision-free), applies
  **Weather Favor** to `base_stats` (see [weather.md](weather.md) — the single
  application path), applies item/trait/augment bundles, subscribes passive
  `Hook`s to a fresh `EventBus`, wires boss phase/death hooks, then seeds
  per-slot start mana. Returns `(pieces, bus)`.
- **`Piece`** (`piece.py`) — the live combat entity (the *only* combat model;
  there is no separate snapshot type). Carries `base_stats`, modifiers,
  statuses, ability slots, position, meters, `crit_counter`. Effective stats via
  `piece.stat(name)` = `compute_stat` over base + modifiers.
- **`CombatContext`** (`combat/context.py`) — the mutator API: the *only* way
  content touches the world (deal_damage, apply_status, cast_ability, …). Holds
  the board state and `hex_distance`.
- **`engine.run`** (`combat/engine.py`) — the tick loop (below). The **sole**
  tick engine (V.29); there is no second `run`.
- **`BattleResultRecorder`** (`combat/recorder.py`) — subscribes to bus events
  and reconstructs `BattleResult` (outcome, survivors, damage, event stream,
  `piece_max_hp`, plus the `initial_pieces` board snapshot + board dims, T.37a).
  Observer-only: it never feeds combat math, so sims stay byte-identical (V.54).

## Tick model

Time = **10 ms ticks** (`TICK_MS`); 1 round = 600 ticks (`ROUND_TICKS`, a
presentation unit only). Each living piece accrues three meters per tick from
its int stats: `action_energy += attack_speed`, `movement_energy += move_speed`,
and mana via the **weighted-rank charge cycle** (T.29c, V.48): one slot is
charged the full `mana_regen` per tick, cycle length `sum(slot.priority)`, each
slot occupying `priority` positions (skip slots at `max_mana`) → mana throughput
= `mana_regen`/tick regardless of slot count. A meter fires at `ENERGY_THRESHOLD`
(60 000) and **carries overflow** (it subtracts the threshold, not resets) so
cadence is exact. Mana is per-slot: `mana_cost`/`max_mana` (default `2×cost`)/
`start_mana`/`priority` are authored on the ability def (`ABILITY_MANA`), not a
piece stat; a cast deducts `-= mana_cost` so overflow banks toward the next.

**Multi-slot pieces (T.29d, V.49):** a piece carries `active_abilities: list[str]`
— one `ActiveSlot` per id (single/null/multi are just list lengths; empty = a
stat-stick with no mana bar). Roster ids are **discovered by convention**
(`content.discover_abilities`: `{id}.active`, `{id}.active2`, … sorted) unless a
def sets `abilities=` explicitly (bosses' named kits, or `[]`). A multicaster's
slots must differ in cost **or** priority (no lockstep simul-cast); the default is
same cost + unique priorities (primary dominant), with high-tier **Ultimate**
secondaries diverging by cost (2×) + priority ∝ cost.

**Status durations** are authored with `secs(x)` (seconds → ticks, fractions OK,
e.g. `secs(3.5)`) — `SECS` (=100) for raw tick intervals. The stored value is
always real ticks (no hidden runtime scaling; tick↔time stays honest). CC/DoT
durations were re-tuned ~2× (1.5–3 s → ~3–6 s) so effects don't expire between
the slow ~5 s action cadence (`60000/attack_speed`).

- **Ordering** — within a tick, triggered meters resolve in the canonical
  side-independent total order `_event_sort_key = (-round(attack_speed×1000),
  champion_id, load_order, kind)` (V.34, T.29-pre): faster attack-speed first
  (the quantized float key carries both whole + sub-integer speed in one term —
  no separate `milli_AS`), then identity, then the seeded `load_order` (never
  team-then-enemy → no side-A bias, B.14), then movement before action. Cadence
  reads `int(attack_speed)`. No RNG in the loop; `load_order` is a one-time
  seeded permutation (V.2/V.14). **Soft-CC:** `slow` stacks throttle action +
  movement meter *gain* by `_slow_factor` = `max(0.40, 1 − 0.15·stacks)` (V.53,
  B.25) — not a gate, not the `stat`.
- **Movement** — `_resolve_movement`: hold at threshold if in range or no
  enemies; else one BFS step toward the nearest in-range cell
  (`_next_step_toward`), carrying overflow; hold if no path. Gated by
  `BLOCKS_MOVEMENT` statuses.
- **Action** — `_resolve_action`: cast an *unregistered* ability if mana full
  (fallback path), else auto-attack if an enemy is in range
  (`ctx.trigger_basic_attack`), else idle-hold. Registered abilities cast
  separately via `process_casts` → `ctx.cast_ability` — **at most one cast per
  window** (V.48 T4): among ready slots the highest `priority` casts (tie →
  lowest slot index), the rest stay ready for later windows. Gated by
  `BLOCKS_ACTION`/`BLOCKS_ATTACK`/`BLOCKS_CAST`.
- **Per-tick upkeep** — `_process_board_state` (slow tiles), `process_statuses`
  (DOT + decay on each status's cadence, then expiry), `expire_modifiers`,
  summon despawn.
- **Termination** — ends when one side has no living piece. **Sudden death**:
  at `SUDDEN_DEATH_TICK_START` (= `MAX_TICKS`, 12 000) the loop applies a
  stacking DOT (+3 stacks/engine-tick) that **damages once per second**
  (`dot_interval_ticks=100`, like every DOT — V.25), so it escalates but still
  leaves room for a few last actions; `HARD_CAP_TICKS` (= MAX_TICKS + 2 000) is
  the absolute ceiling. **Outcome is survivor-based (V.60):** WIN = team
  survivors & no enemy, LOSS = enemy survivors & no team, DRAW = **no survivors
  either side** (a true mutual wipe — only via a simultaneous DOT/sudden-death
  pass). `timed_out` is an **independent flag**, not an outcome — a sudden-death
  fight with a survivor is a real WIN/LOSS.

## Damage pipeline

`_apply_hit` / `ctx.deal_damage` order:

```
raw = str_coeff·STR + int_coeff·INT
raw ×= damage_modifier(attacker.affinity, target.affinity)   # Affinity Clash, weather.md
if crit:  raw ×= CRIT_MULTIPLIER (1.5)                        # deterministic cadence
mitigated = raw × (1 − mit/(mit+100)) after penetration       # _mitigated_damage
final = max(1, round(mitigated))                              # true damage skips mitigation
```

- Coeffs (`combat/engine.py`): auto = `AUTO_STR_COEFF` 1.0 / `AUTO_INT_COEFF` 0.2;
  ability fallback = `ABILITY_STR_COEFF` 0.2 / `ABILITY_INT_COEFF` 4.2.
- **Crit is not random** — `crit_counter` on the `Piece` increments per eligible
  hit and crits every `round(1/crit_chance)`-th, then resets. Shared autos/casts.
- **Mitigation** — `magical`→resistance, `physical`→armor, `true`→unmitigated;
  `_effective_mitigation` applies `penetration_pct` then flat `penetration`,
  clamped ≥ 0. `damage_type` is a **closed vocabulary** `{physical, magical, true}`
  that `deal_damage` **validates** (raises on anything else, V.58) — a typo can't
  silently fall into the armor branch (B.29).

## Result

`BattleResultRecorder.build_result` emits `BattleResult` with: outcome
(WIN/LOSS/DRAW), `rounds`/`turns`/`duration_ticks`, `team_damage_dealt`/`_taken`,
survivor id lists, `events` (full tick-ordered `BattleEvent` stream),
`piece_max_hp` (`{id: int(max_hp)}` captured from the engine's pieces), and the
combat-view layout (`initial_pieces`: per-piece `PieceSnapshot` identity +
spawn-time position + mana profile, with `spawn_tick=0` for starters and the
spawn tick for mid-combat summons; `board_width`/`board_height`).

**Beat taxonomy (V.54, T.37a; `ability` T.37 follow-up).** Every visible-state-
changing beat emits exactly one `BattleEvent` from a single producer path:
`move`/`attack`/`cast`/`ability`/`death` plus `heal`/`dot`/`status`(applied)/
`status_expire`/`spawn`/`despawn`. **`cast` vs `ability` are distinct:** `cast` is
the *activation* marker (`amount=0`, "a piece casts", `_on_cast`); `ability` is
the resulting *damage* (one per target hit, `_on_damage_dealt` when
`tag == ABILITY`) — first a `cast`, then per-target `ability` beats. Beats that
actually change HP carry `hp_after`/`barrier_after` = the engine's post-event
truth (read after `deal_damage` applies, V.28-correct: the `amount` is the full
pre-barrier figure for DPS accounting): on `attack`/`ability`/`dot`/`heal`. The
`ability`/`attack` `amount` is the **final post-mitigation** figure with `is_crit`
+ `damage_type` (`physical`/`magical`/`true`, on `DamageEvent`) — the single
`ctx.deal_damage` chokepoint is the one producer (no separate ability handler).
With `ability` added the stream is HP-complete; the view still reads bars from the
live stepper (V.57) — the beat's `amount`/`type` drives the floating *number*, not
the bar. `turns` counts `attack`+`cast` only (`ability` excluded) ⇒ byte-identical.
The **`status` (apply) beat fires once per *acquisition*** — the recorder tracks a
`(piece_id, status_id)` active set (cleared on `status_expire`) and skips re-applies/
refreshes (V.54), so sudden-death (re-applied every tick) + poison-restacks don't
spam the stream (live stacks come from the stepper anyway, V.57). `expire_summon`
fires `on_despawn` (distinct from `death`). The recorder is observer-only ⇒ sims
byte-identical; only `combat_log` golden text re-baselines. `record_attack` (a
dead parallel path) was removed — `_on_attack_landed` is the sole attack producer.

**Targeting footprints (T.12c, V.61) — observer-only shape telemetry.** Alongside
beats, the recorder collects a `footprints: list[Footprint]` for the combat view's
per-ability-shape VFX. The targeting helpers record the geometry they already
compute: `enemies_in_radius`/`allies_in_radius`/`neighbors_of` → a `circle`
(center + radius), `line_targets` → a `line` (origin + direction + length), via
`ctx.note_footprint(kind, q, r, …)` → `on_footprint` → `_on_footprint`. Capture
fires **only while a cast is in flight** (`note_footprint` gates on
`_current_cast_id`), so idle/AI/passive target queries don't record. It is
**observer-only**: the helper returns its target list unchanged and, on the sim /
`CombatReplay` path (no recorder subscribed), the bus fire no-ops ⇒ **byte-identical**
(V.2/V.14, extends V.54). The `cast` + `ability` beats now carry the engine's
`cast_id` so the view joins a footprint to its ability for element colour.

<a id="rendering"></a>
## Rendering

`combat_log.py` turns a `BattleResult` into text purely from the result (it does
**not** recompute anything): the HP trace prefers each event's `hp_after`
(barrier/DOT/heal-correct, T.37a) and falls back to `piece_max_hp` + damage
subtraction for legacy events. Used by the playtest CLIs and golden-snapshot
tests.

<a id="replay"></a>
## Replay / forward stepper / inspect-at-tick (T.37b, T.37c)

Continuous combat state for a view is **recomputed, not recorded** (V.55). The
engine loop is the **single** `_step_combat` generator (`combat/engine.py`, V.29),
driven two ways — no parallel loop:

- **`run(ctx, recorder=None)`** *drains* it to completion (the resolve path) —
  byte-identical to the pre-T.37c monolithic loop (V.2/V.14).
- **`CombatReplay(team, enemies, weather, *, run_mods=None)`** *steps* it
  **forward** (`.step_to(tick)`, `.pieces() -> list[PieceView]`, `.tick`,
  `.winner`) for sequential playback — drives one instance once, O(total ticks).
  Forward-only; `step_to` to an earlier tick raises.

The generator yields once per fully-processed tick (`yield 0` = after
`on_combat_start`; `yield N` = after ticks 1..N), so a stepping consumer pauses
mid-fight **before** the post-loop finalize (`end_combat`/`on_combat_end` never
mutate the inspected state).

`inspect_at_tick(team, enemies, weather, *, run_mods=None, tick) -> list[PieceView]`
is a random/backward-access wrapper (re-run from 0) **over `CombatReplay`** — one
driver, two shapes. Each reads hp, barriers, per-slot mana, **effective stats**
via `piece.stat()` (STR/AS ramp included), statuses, position into frozen
read-only `PieceView`/`SlotView`/`StatusView` structs. `run_mods` is **cloned**
(deep-copy of mutable `augment_state`) so replay never mutates the caller. Raw
`Piece`/Flet never escape `src/game/` (V.1). No per-tick state is stored in
`BattleResult` (avoids T.14 save bloat + stat-drift).

**This live state is the combat view's resource-truth source (V.56/V.57), NOT
the recorded event stream** — even though the stream is now HP-complete (the
`ability` beat closed the B.28 gap), the view keeps **one** source of truth (the
stepper) so bars can't drift from a dual pipeline; the stream's `amount`/`type`
drives the floating *number*, the stepper drives the *bar*. The stream is
**animation cues + action-queue projection** only. `move`/
`spawn` beats carry structured `dest_q`/`dest_r` int coords (T.37c), not a parsed
`note` string.

## Invariants this system owns

- **V.2** — combat is a pure, seeded function; the ability/passive/status
  framework is invoked *through* `resolve_combat`, never alongside it.
- **V.29** — exactly one tick loop (`combat/engine.py`); no parallel engine.
- **V.14** — determinism: every "chance" mechanic uses a cadence counter
  (`crit_counter`), never RNG.
- **V.54** — event-stream completeness: every visible-state-changing beat emits
  exactly one `BattleEvent` (T.37a).
- **V.55** — view state is recomputed by replay, never recorded as per-tick
  keyframes; the forward `CombatReplay` stepper + `inspect_at_tick` are pure +
  clone `run_mods` (T.37b, forward stepper T.37c).
- **V.56/V.57** — the combat view's resource truth (hp/mana/stats/position) is the
  live replay, **never** the event stream's partial `hp_after` fields (incomplete
  for ability burst, B.28); the stream is animation cues + queue projection (T.12).
- **V.58** — `damage_type` is a closed vocabulary `{physical, magical, true}`;
  `deal_damage` validates + raises on anything else so a typo can't be mis-mitigated
  as physical (B.29).
- **V.61** — targeting footprints are observer-only telemetry for the combat view:
  helpers record geometry via `ctx.note_footprint` → `on_footprint` only while a
  cast is in flight; the recorder stamps `footprint` records on `BattleResult`;
  capture never changes targeting results or damage ⇒ byte-identical (T.12c).

## File map

| Concern | File |
|---|---|
| Public entry + shared `build_combat` wiring | `combat/resolve.py` |
| Single tick loop (`_step_combat` generator) + `run` drain, pathing, damage, spawns, constants | `combat/engine.py` |
| Forward stepper `CombatReplay` + `inspect_at_tick` (recompute state at a tick) | `combat/replay.py` |
| Mutator API (the only way to touch the world) | `combat/context.py` |
| Event → `BattleResult` (incl. footprint telemetry) | `combat/recorder.py` |
| Targeting helpers + footprint capture | `targeting.py` (`ctx.note_footprint` in `combat/context.py`) |
| Model → `Piece` compile + weather + passives | `loadout.py` |
| Runtime piece | `piece.py` |
| Boss wiring (map effect) | `tools/playtest/_common.py::resolve_boss_combat` |
