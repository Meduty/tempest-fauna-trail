# UI — main menu + combat view + dev harness (LIVING)

> **Status:** ✅ for the main menu (T.9), combat view core + dev harness (T.12a).
> The rest of the Flet UI (Trail/Prep/Summary, T.10–T.15/T.23) is unbuilt — this
> doc grows as those land. New Run/Continue are surfaced-but-disabled in the menu
> until the Trail run shell exists. FROZEN design:
> [`views_spec.md`](../../design/systems/views_spec.md). Audited by `/check`.

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

- **`Playback.steps: list[Step]`** — one `Step(tick, round, beats, pre_beats,
  footprints)` per **action moment**. DOT-only ticks are **absorbed**: a step's
  `beats` are the action cues at `tick` (attack/cast/ability/heal/death/spawn/
  despawn/move), and `pre_beats` are the DOTs that ticked *between* the previous
  action step and this one. **`footprints`** (T.12c) are the cast's recorded
  targeting geometry at that tick (`BattleResult.footprints` joined by tick) — the
  per-ability-shape VFX; geometry only, no resource numbers. So Next goes action→action (no DOT-only steps), and the view drips
  `pre_beats` chronologically before showing the action ("what bled in between").
  `round = tick // ROUND_TICKS`.
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
  ally/enemy outline) at its **stepped `(q,r)`**, with `meter_bar` HP + a custom
  **mana bar (`_mana_bar`)** overlaid beneath. The mana bar draws a **cast-threshold
  tick at each `k×mana_cost`** (since `max_mana` = 2×cost, V.48, the fill alone
  doesn't show readiness) and a **ready highlight** once `current ≥ cost`. Floating
  damage/heal numbers are coloured **by damage type** (phys red / magic blue / true
  white / dot purple / heal green; crit = trailing `!` + size bump, not colour) and
  render as overlay controls on top of the tokens. **Click-to-select** via the token
  overlay (robust hit-test — no canvas gesture math).
- **Side — inspect (read-only):** selected piece → live stats (stepper), mana,
  statuses, **ability descriptions** (`render_for` against a `PieceView` stat-shim
  → name + live blurb + formula, for team *and* enemy pieces), equipped
  `champion.items`, `champion.traits`; a global sub-panel shows active augments
  (`session.run_mods.augments`) + cleared `result.trait_activations`. Hover a token
  for the same ability blurbs as a tooltip.
- **Floating numbers:** the step's `pre_beats` (interstitial DOTs) reveal by a
  **tick cutoff** (`state["reveal_tick"]`) — same-tick DOTs pop together, paced
  **real-time** (`playback_delay_s`, 1 game-s ≈ 1 real-s) via `_play_step`/
  `page.run_task`; then the action `beats` show. Coloured by damage type (legend on
  screen); crit = `!` + size. (T.12b)
- **Token tween (T.12b):** tokens are **keyed overlay `Container`s** (`tok-{id}`,
  HP/mana/status pips `hp-`/`mp-`/`st-{id}`) with `animate_position` → they **glide**
  between cells; canvas keeps cells + slash/arrows + numbers. On an action the
  attacker **lunges** toward its target (offset, tweened). **Melee** basic attacks
  draw a red **swoosh** (`_swoosh`, `cv.Arc` crescent facing the attacker);
  **ranged/ability/cast** draw a directional **arrow** (`_arrow`, colour by damage
  type); AoE/self casts → a ring on the caster.
- **Per-ability-shape VFX (T.12c, V.61):** a cast's recorded targeting
  **footprint** (`step.footprints`, joined to the `cast` beat by `cast_id`) draws
  in the ability's **element colour** (`_element_color` from `AbilityMeta.tags`:
  magic→accent, physical→danger, true→white). A `circle` (radius AoE) is an
  **animated overlay** (`_footprint_circle`, keyed `fp-{cast_id}-{i}`) — translucent
  fill + ring that **pops** (expand + fade-in via `state["fp_phase"]` 0→1 with
  `animate_scale`/`animate_opacity`) then stays as the **static residue**. A `line`
  (beam) draws on the canvas (`_footprint_line`; no roster ability uses
  `line_targets` yet — kept correct).
- **Ability-intent recolour (T.12c-B):** the cast's intent (`classify_intent` in
  `combat_playback.py`, from `AbilityMeta.tags`: heal → summon → damage-element →
  buff) recolours the footprint shape — an ally-directed **heal/buff** renders as a
  **green halo** (`SUCCESS`) instead of an element colour, and a **control** ability
  adds a **`WARNING` telegraph ring** just outside the AoE (keyed
  `fp-tel-{cast_id}-{i}`). (Sprites/projectiles still deferred, D.27.)
- **Beat-driven intent FX (T.12c-B):** observer-only overlays read from the
  recorded `heal`/`status` beats (no sim-path change, V.2/V.14) so single-target
  casts — which produce no footprint — still read intent:
  - **Ally halo** — a green (`SUCCESS`) ring on each **healed target** (`heal` beat
    → `target_id`'s cell, keyed `heal-halo-{target_id}`); covers single-target heals
    the footprint recolour can't reach.
  - **Status-apply flash** — a coloured disc on a piece the moment a status lands
    (`status` beat → `actor_id`'s cell, colour `_STATUS_COLORS[note]` else
    `WARNING`, keyed `stflash-{actor_id}-{note}`); the arrow loop otherwise skips
    `status` beats.
  Both share the footprint **pop phase** (`fp_phase`); on manual `Next` the
  per-beat drip (`_drip_action_beats`) re-seeds the grow as each heal/status beat is
  revealed, so halo/flash animate like footprint shapes.
- **Manual step = instant** full reveal of the static truth (action + arrows +
  numbers + dots) so the DOTs+truth show, then the tick's **action beats reveal one
  at a time** in recorded chronological order (intra-tick stagger): `_advance_to`
  sets `reveal_n` to the step's full beat count (static truth for backward/seek), and
  a forward `Next` re-seeds `reveal_n = 0` and `_drip_action_beats` reveals beats
  `1..N` `_BEAT_STAGGER_S` apart — so when **multiple pieces act on one tick** you read
  move→attack→… in order instead of all at once. Each newly-revealed beat pops its
  footprint/halo/flash (`fp_phase`). Interrupt-safe (`anim_token`): a rapid Next
  aborts the drip and the next advance shows everything. The **real-time DOT drip
  stays autoplay-only**. ⚠ **Known-rough (D.28):** the stagger is **manual-`Next`
  only** and feels clunky; **autoplay does not stagger** — it shows the tick's beats
  together and is flagged for a **full rework** (pacing/illegibility).
- **Action queue active highlight:** the entry(ies) at the current step's tick
  ("resolving now") render **bigger + accent-bordered** (`animate_size`); fixed-width
  row with horizontal overflow so the layout never shifts.
  **Status pips** under each token (colour by status, stack count, remaining-time
  tooltip). **Sudden-death** (tick ≥ `SUDDEN_DEATH_TICK`): header badge + board
  border tint + a `DANGER` divider in the queue.
- **Autoplay = real-time (T.12b):** `_autoplay_loop` advances one step then
  `_play_step` drips DOTs + action paced by the tick gap (1s ≈ 1s, clamped).
- **Boss (T.12b):** `CombatSession.map_effect_id` → the view resolves via
  `resolve_boss_combat` + builds `CombatReplay(map_effect_id=…)`; the board tints
  map-effect tiles (`_CELL_COLORS` over `replay.board_cells()`). Dev harness adds a
  **BOSS** node type (`generate_boss_encounter` → `enc.all_enemies` + `map_effect_id`).
- **Keyboard:** →/↵ Next · ← Prev · Space autoplay · F end · R restart · Esc exit
  (`page.on_keyboard_event`, cleared on view pop).
  Floating numbers are **monospaced** (`FONT_MONO`), coloured **by damage type**
  (`_DMG_COLORS`: physical red, magical blue, true white, DOT purple; heal green),
  with crit marked by a trailing `!` + size bump (not colour), and **staggered per
  target** so multi-hit ticks stay legible. Ability damage shows via the `ability`
  beat (V.54), basic hits via `attack`, bleeds via `dot`, heals via `heal`.
- **Bottom controls:** **Next ▶** (default manual step), ◀ Prev, Autoplay toggle,
  ⏭ End (fast-forward), ↺ Restart, Exit.
- **Combat-end panel:** outcome / survivors / damage dealt-taken / **Continue**
  (→ `on_exit`).

**Playback driver:** manual step mutates the cursor + re-renders **instantly**
(full reveal — action + numbers + DOTs at once; no async drip to out-race a rapid
Next). Autoplay is opt-in, an **async loop** scheduled with `page.run_task(_autoplay_loop)`
that advances one step then `_play_step` drips the interstitial DOTs + action paced
by the tick gap (`playback_delay_s`, 1s ≈ 1s real, clamped; event-paced not
tick=second, V.56). It never blocks the main thread and stops on view pop /
toggle-off (the view's on-pop handler, stashed on `view.data`, clears an `alive`
flag). Displayed durations → seconds via `TICKS_PER_SECOND` (V.39).

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

## `ui/views/menu.py` — main menu (T.9, route `/`)

`build_menu_view(page, *, on_new_run, on_continue, on_playfight, on_quit,
save_exists=False) -> ft.View`. The app entry point (views_spec §4): title +
pitch + four entries. **New Run** / **Continue** are surfaced but **disabled**
(the Trail/Prep run shell, T.10/T.11, isn't built — Continue's hint reflects
`save_exists`); **Playfight ▶** opens the combat dev harness; **Quit** closes the
app. Pure presentation — emits intent through the `on_*` callbacks; the host owns
the view stack. Buttons keyed by their `content` label (Flet 0.84).

## `src/main.py` app shell

`_game_ui` is the default shell (no env gate): a `page.views` stack rooted at the
menu (`/`). **Playfight** pushes the dev harness (`_push_playfight`) whose
`open_combat` pushes the combat view; `_pop` / `page.on_view_pop` unwind the
stack (firing the combat view's on-pop to stop autoplay). `TEMPEST_DEV=1` is a
**legacy shortcut** that lands directly in Playfight; `TEMPEST_ADMIN=1` still
opens the admin panel. Quit → `page.window.destroy()`.

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
| Main menu (`/`, T.9) — New Run/Continue/Playfight/Quit | `src/ui/views/menu.py` |
| App shell — menu↔harness↔combat `page.views` nav | `src/main.py` |
| Design tokens / shared components (`meter_bar`, chips, …) | `src/ui/theme.py`, `src/ui/components/` |
