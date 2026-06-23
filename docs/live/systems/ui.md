# UI — combat view + dev harness (LIVING)

> **Status:** ✅ for the combat view core + dev harness (T.12a). The rest of the
> Flet UI (Menu/Trail/Prep/Summary, T.9–T.15/T.23) is unbuilt — this doc grows as
> those land. FROZEN design: [`views_spec.md`](../../design/systems/views_spec.md).
> Audited by `/check`.

The combat view is **pure presentation over the replay backend** (V.56): it
renders a fight only through `resolve_combat` + the forward `CombatReplay`
stepper + `inspect_at_tick` + the recorded `BattleResult` stream, and implements
**no** combat math. `ui/` imports `game/`, never the reverse (V.1).

## The seam — `CombatSession`

`ui/combat_playback.py` defines the one input bundle the combat view consumes
(plain game models, Flet-free):

```
CombatSession(team: list[Champion], enemies: list[Enemy], weather: WeatherState,
              run_mods=None, node_id="")
```

**Two producers, one session:** the dev harness builds it from selectors now; the
Prep/Trail `Start Combat` flow builds the **identical** object later → same view,
no change. The view owns resolution (takes inputs, not a pre-resolved result).

## `ui/combat_playback.py` — pure animation model (Flet-free, tested)

`build_playback(result) -> Playback` turns the recorded event stream into:

- **`Playback.steps: list[Step]`** — one `Step(tick, round, beats)` per
  event-bearing tick (`group_events_by_tick`); `beats` are the **animation cues**
  to play at that tick (attack/cast/heal/dot/death/spawn/despawn/move). `round =
  tick // ROUND_TICKS`.
- **`Playback.queue(cursor) -> list[QueueEntry]`** — the forward **action-queue
  projection**: upcoming `move`/`attack`/`cast` beats from the cursor's tick,
  spanning the current round + the next `QUEUE_LOOKAHEAD_ROUNDS` (= 2); each entry
  carries its `round` so the view draws round-split markers. Moves render smaller
  + movement-iconed; attacks/casts are the primary entries.

**This model carries NO resource numbers** (hp/mana/barrier) — a regression guard
test asserts it. Resource truth comes from the live stepper (V.57); the stream is
*incomplete* for it (registered-ability burst emits no `hp_after`, B.28).

## `ui/views/combat.py` — the Flet view

`build_combat_view(page, session, on_exit) -> ft.View`. On open it calls
`resolve_combat(session…)` once (→ `Playback`) and builds **one
`CombatReplay(session…)`**.

**Drive loop (the V.57 heart):** the view holds a `cursor` (`-1` = initial board
at tick 0; `0..N-1` = step index) and the forward stepper. Stepping forward calls
`replay.step_to(steps[cursor].tick)`; **backward / restart rebuilds a fresh
`CombatReplay`** (the stepper is forward-only) and re-drives to the target tick.
Every render reads **live `PieceView`s** off the stepper — HP/barrier/per-slot
mana/effective stats/`(q,r)` — so bars move correctly through ability bursts, not
just basic attacks.

Zones (views_spec §7.3):

- **Top — action queue:** `Playback.queue(cursor)` chips, round-split markers,
  slides forward as rounds complete.
- **Centre — hex board:** `flet.canvas` 10×7 (`BOARD_WIDTH`×`BOARD_HEIGHT`); each
  living piece a token (`cv.Circle` tinted `AFFINITY_COLORS[affinity]` + initials,
  ally/enemy outline) at its **stepped `(q,r)`**, with `meter_bar` HP (+ first-slot
  mana) overlaid beneath. Floating damage/heal numbers (red/green, crit = amber)
  drawn for the current step's beats. **Click-to-select** via transparent overlay
  containers per token (robust hit-test — no canvas gesture math).
- **Side — inspect (read-only):** selected piece → live stats (stepper), mana,
  statuses, equipped `champion.items`, `champion.traits`; a global sub-panel shows
  active augments (`session.run_mods.augments`) + cleared `result.trait_activations`.
  Floating numbers are **monospaced** (`FONT_MONO`), coloured **by damage type**
  (`_DMG_COLORS`: physical red, magical blue, true white, DOT purple; heal green),
  with crit marked by a trailing `!` + size bump (not colour), and **staggered per
  target** so multi-hit ticks stay legible.
- **Bottom controls:** **Next ▶** (default manual step), ◀ Prev, Autoplay toggle,
  ⏭ End (fast-forward), ↺ Restart, Exit.
- **Combat-end panel:** outcome / survivors / damage dealt-taken / **Continue**
  (→ `on_exit`).

**Playback driver:** manual step mutates the cursor + re-renders (no thread).
Autoplay is an opt-in `threading.Thread` advancing the cursor on a fixed interval
(`_AUTOPLAY_INTERVAL_S`, event-paced — **not** tick=second, V.56) + `page.update()`;
it never blocks the main thread and stops on view pop / toggle-off (the view's
on-pop handler, stashed on `view.data`, clears an `alive` flag). Displayed
durations → seconds via `TICKS_PER_SECOND` (V.39), never used for pacing.

## `ui/views/dev_harness.py` — launcher

`build_dev_harness_view(page, open_combat) -> ft.View`. GUI wrapper of the
`sim_node` inputs: run seed · stage · node index · DC · node type
(FIGHT/CHALLENGE/REWARD — **all combats**, REWARD = an easy fight) · weather
(default = node city's `default_weather`) · team (comma champion ids; blank →
`default_team(stage)`) · items (applied to each champion via `dataclasses.replace`
— never mutates the roster, clamped to 3, V.23) · augments (→ `RunModifiers`).
**Run** assembles a `CombatSession` and calls `open_combat`. Ids are validated
against `CHAMPION_ROSTER` / `ITEM_REGISTRY` / `AUGMENT_REGISTRY`; errors surface
inline.

## `src/main.py` dev entry

Behind `TEMPEST_DEV=1` (mirrors `TEMPEST_ADMIN`): a tiny harness↔combat
`page.views` stack (`_dev_ui`) ahead of the real routing (T.15). `open_combat`
pushes the combat view; Continue / `page.on_view_pop` pops it (firing the combat
view's on-pop to stop autoplay). Existing counter/admin entries untouched.

## Invariants this layer owns

- **V.1** — `ui/` imports `game/`, never the reverse; no `game/` logic added here.
- **V.56** — combat view is pure presentation over the replay backend; one
  `CombatSession`, swappable producers; event-paced playback, not tick=second.
- **V.57** — resource truth (HP/mana/stats/position) is the live `CombatReplay`
  stepper, **never** the event stream's partial `hp_after` (B.28). The stream is
  animation cues + action-queue projection only.
- **V.39** — `TICKS_PER_SECOND` renders durations as text only, never pacing.

## File map

| Concern | File |
|---|---|
| `CombatSession` + pure cue/queue model (`build_playback`) | `src/ui/combat_playback.py` |
| Combat view (canvas board, stepper drive loop, inspect, end panel) | `src/ui/views/combat.py` |
| Dev harness launcher → `CombatSession` | `src/ui/views/dev_harness.py` |
| Dev entry (`TEMPEST_DEV=1`) + harness↔combat nav | `src/main.py` |
| Design tokens / shared components (`meter_bar`, chips, …) | `src/ui/theme.py`, `src/ui/components/` |
