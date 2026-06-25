# UI — main menu + combat view + dev harness (LIVING)

> **Status:** ✅ for the main menu (T.9), combat view core + dev harness (T.12a),
> **RunStart (T.10)**, **Trail (T.11)**, **Prep (T.23a — full economy, no items)**,
> **Reward + result-out seam (T.15a)**, **Summary (T.13 — canvas damage chart)**. Still
> unbuilt: terminal/Continue routing (T.15b), Prep items (T.23b). **New Run is live**
> (→ RunStart → champion pick → **Trail** → **Prep** → **Combat** → **Reward** → Trail);
> the Summary view exists but terminal→Summary + Continue land in T.15b. FROZEN design:
> [`views_spec.md`](../../design/systems/views_spec.md). Audited by `/check`.

## RunStart (T.10) — `game/run_init.py` + `ui/views/run_start.py`

The run-start flow is **logic in `game/run_init.py` (Flet-free, V.1/V.63), view in
`ui/views/run_start.py` (pure presentation)**:

- `run_init.champion_offer(seed) -> list[str]` — the **seed-deterministic** 1-of-3
  (`OFFER_SIZE`) Tier 1–2 (`OFFER_TIERS`) champion offer, via
  `encounter.derive_seed(seed, 0, _OFFER_CHANNEL=701)` over a sorted pool (V.2 —
  same seed ⇒ same ids, no `hash()`/wall-clock).
- `run_init.new_run(seed, chosen_champion_id) -> Run` — builds the in-progress `Run`
  per SPEC §G run-start conditions: `build_route()` + node 1 `CURRENT`,
  `STARTING_AMBER=10`, `tempest_rank=STARTING_RANK=1`, the chosen champion granted at
  level 1 through `economy._materialize_champion` (champion_copies + roster in sync),
  and the first shop via `shop.refresh_shop` (V.63 — economy/shop own the numbers;
  the view computes nothing). Rejects an un-offered id.
- `build_run_start_view(page, *, seed, on_pick, on_back) -> ft.View` (route
  `/run-start`) renders the offer as `champion_card`s; a click emits `on_pick(cid)`.
  The host (`main.py` `_start_new_run`) draws a fresh `secrets` seed, calls
  `new_run`, and pushes the next screen (`main._push_trail` → the Trail view).

## Trail (T.11) — `viz/route_map.py` + `ui/views/trail.py`

The between-fights hub. **Pure presentation (V.1/V.63)** — reads `Run` state and
calls into `game/` for every number; computes none itself.

- **`viz/route_map.py`** (graded Canvas viz, two layers like `combat_playback`):
  - `route_node_specs(run, weather_for, selected_index=None) -> list[RouteNodeSpec]`
    — **pure, Flet-free, test-asserted** (`tests/viz/test_route_map.py`): one spec per
    `run.route` node in index order, each carrying index/city/weather/state/`is_boss`/
    `is_selected`/`(x, y)`/state-tint colour. `weather_for(node)` supplies the *displayed*
    weather; selection defaults to `run.current_node_index`.
  - `build_route_map(run, weather_for, on_select, selected_index=None) -> ft.Control`
    — draws the specs with `flet.canvas` (`cv.Line` lane behind, `cv.Circle` nodes on
    top, index + 4-char weather label, boss = `DANGER` ring, focus = `TEXT_PRIMARY`
    ring) inside a horizontally-scrolling `ft.Stack`; transparent overlay `ft.Container`
    buttons per node hit-test → `on_select(node_index)` (no gesture math, per CLAUDE.md).
- **`ui/views/trail.py`** `build_trail_view(page, run, *, on_play_next, on_save_exit)
  -> ft.View` (route `/trail`):
  - **Node focus panel** — selected node's city/type/weather (`weather_badge`),
    team-wide Weather Favor (`weather_effects.ring_relation` tally ↑/·/↓), and the
    deterministic **enemy preview** via `encounter.node_encounter(run.seed, node,
    weather=…)` (boss `map_effect_id` surfaced). The **Play Next Encounter** button
    shows only on the `CURRENT` node → `on_play_next(node)`.
  - **Team summary** — Amber / Tempest rank / bench counts + roster rows
    (affinity dot, name, `L{level} {role}`, HP).
  - **Live weather (V.66/V.4)** — the view **owns** a T.7 `WeatherCache(ROUTE_CITY_IDS)`
    + `WeatherRefresher`, started on open. **On open a kickstart worker thread fetches
    the *current* node immediately** (then runs one seed tick for neighbours) so the
    Trail shows live weather at once instead of waiting a full ~60s tick — the rest
    fill at ≤3 nodes/pulse (V.11). The refresher's optional `on_tick=…` callback
    repaints **each pulse** while the player sits on the Trail. **Repaints from these
    worker threads marshal onto the Flet event loop via `page.run_task`** (`_schedule_render`
    → `asyncio.run_coroutine_threadsafe`, the same pattern combat-view autoplay uses) —
    a bare `page.update()` from a `threading.Timer` thread is unreliable on desktop.
    A **no-key banner** ("Add one in Settings") shows when no key resolves.
    **Display is tri-state by `CacheState` (V.66):** UNKNOWN → a `?` "weather pending"
    chip (map label `?`, favor `— pending`) — **never a concrete weather it hasn't
    fetched**; SUBSTITUTE → the city default weather **flagged `fallback`**; LIVE → the
    weather badge unflagged. **No API key** (or `WeatherClient` `ValueError`) ⇒ refresher
    skipped, so **every node stays UNKNOWN → `?`** until a key is configured. The enemy
    preview/favor-generation still derive from the node's `default_weather`
    deterministically (V.2) — *display* weather ≠ *game-logic* weather. The view is
    **lifecycle-bounded**: `view.data` is
    the refresher-stop handler that `main._pop` fires before popping, and **Save & Exit**
    stops it explicitly then autosaves via `save.save_run` (V.65/V.36) → menu.
- **Shared seam:** `encounter.node_encounter(run_seed, node, weather=None, dc) ->
  NodeEncounter(enemies, map_effect_id)` is the **one deterministic dispatcher** (V.2)
  the Trail preview uses now and the Prep `Start Combat` flow reuses (T.23a) — so the
  previewed squad is byte-identical to the fought squad. `route.city_id_for_node(index)`
  / `route.ROUTE_CITY_IDS` back the `Node` (which holds only the city *name*) with the
  city id the weather cache keys on.
- **Wiring (`main.py`):** New Run → RunStart → `_push_trail`; Play Next →
  `_push_prep` (the full Prep view, T.23a); Save & Exit → autosave + `_pop` to menu.

## Prep (T.23a) — `ui/views/prep.py`

The pre-combat decision layer (route `/prep`). Pure presentation over the finished
economy/combat backend (V.63/V.1): it mutates `Run` **only** through `game/economy.py`
/ `game/shop.py` (buy/reroll/sell/supply, `try_rank_up_with_amber`) and resolves combat
**only** by building a `CombatSession` — it recomputes no Amber/cost/level/encounter
number.

- **Placement → `team_positions`:** the player arranges the team on the hex board (Flet
  `Draggable` tokens + per-cell `DragTarget`, TFT-style bench↔board) within the **allied
  deployment zone** (columns `0..ALLIED_ZONE_MAX_Q-1` = 0–2, V.68). `run.roster` = the
  deployable field (capped at `tempest_rank`); `run.bench` = reserves; dragging moves a
  champion between the two lists. Each placed champion gets a `team_positions[id] = (q,r)`.
- **Auto-Place / Reset** = the default packing `champion i → (i // 7, i % 7)`, mirroring
  `engine.assign_spawns` so it's **byte-identical** to `positions=None` (V.62/V.2).
- **Shared geometry:** the hex pixel layout lives in `ui/components/board_geometry.py`
  (`cell_xy`, `COL_W`, `ROW_H`, `BOARD_W/H`), reused by the combat view — one coordinate
  source, no drift.
- **Shop / preview / tooltips:** shop slots (`run.shop_offers`, cost via `champion_cost`),
  deterministic enemy preview (`node_encounter`, with affinity-clash hints via
  `ring_relation`), and a tap-to-inspect stat panel (raw sheet read off the `Champion`).
- **Start-Combat:** `team = run.roster` placed pieces; `validate_team_positions(team,
  positions)` (`game/loadout.py`, V.68 — zone + roster-id, on top of the V.62 engine
  guard); builds `CombatSession(team, enemies, weather=node.weather, run_mods=
  RunModifiers.from_run(run), node_id, map_effect_id, positions=team_positions)` —
  shape-identical to the dev-harness producer — and hands it to the host. The
  reward/progression step (applying the `BattleResult`) is the host's job (T.15, V.64);
  Prep only produces the input. Combat weather = the node default (deterministic, V.2),
  decoupled from the displayed live weather (V.66).

The combat view is **pure presentation over the replay backend** (V.56): it
renders a fight only through `resolve_combat` + the forward `CombatReplay`
stepper + `inspect_at_tick` + the recorded `BattleResult` stream, and implements
**no** combat math. `ui/` imports `game/`, never the reverse (V.1).

## Reward (T.15a) — `ui/views/reward.py` + `economy.apply_node_result`

The post-fight panel (route `/reward`). The run-loop **producer** (`main.py::_finish_combat`)
is what closes a node — not the view:

1. `economy.apply_node_result(run, result) -> NodeResultSummary` — the single game-side
   reward orchestrator (V.69): appends `result` to `run.battle_log`, grants seeded income
   (win bonus on a win only, V.2) and — **on a win** — fight tempest (`grant_fight_tempest`,
   cascades rank-ups) + `mark_current_node_cleared` + `advance_to_next_node` (→ `VICTORY`
   if last); a non-win (LOSS/DRAW) sets `status = DEFEAT`. Called **exactly once per fight**,
   never re-resolves.
2. node-boundary autosave via `save.save_run` (V.65).
3. `build_reward_view(page, run, summary, *, on_continue)` — pure presentation off the
   `NodeResultSummary` + live `Run` (outcome banner, Amber/tempest/rank, nodes cleared).
   **Continue** → the producer's router: a continuing run pops the stack to the menu and
   pushes a **fresh Trail** at the new current node; a terminal run stays on the menu
   (T.15a interim → Summary in T.15b).

## Summary (T.13) — `viz/run_summary.py` + `ui/views/summary.py`

The run-end screen (route `/summary`). Mirrors the route-map's graded-viz shape
(V.70): a **pure data fn** + a **canvas builder** — no `ft.BarChart` (removed from
Flet core ≥0.85).

- `viz/run_summary.py::run_summary_specs(run) -> list[BarSpec]` — one `BarSpec(index,
  label, damage, height_frac, won)` per battle in `run.battle_log`, in fight order.
  `damage = sum(result.team_damage_dealt.values())`; `height_frac` max-normalized
  across the log (peak bar = 1.0; empty/all-zero ⇒ 0.0, guarded); `won` from
  `result.outcome`. Deterministic + Flet-free (V.2) — tests assert this data, not pixels.
- `build_run_summary(run) -> ft.Control` — draws the bars as `cv.Rect` (green win /
  red loss), value + node labels (`cv.Text`), a baseline (`cv.Line`) on a `cv.Canvas`;
  empty log ⇒ a "No battles fought" text.
- `ui/views/summary.py::build_summary_view(page, run, *, on_menu)` — outcome banner
  (Victory/Defeat) + the chart + stat chips (nodes cleared / battles / Amber / rank) +
  Return-to-Menu. Terminal→Summary routing is wired by the producer in T.15b.

## The seam — `CombatSession`

`ui/combat_playback.py` defines the one input bundle the combat view consumes
(plain game models, Flet-free):

```
CombatSession(team: list[Champion], enemies: list[Enemy], weather: WeatherState,
              run_mods=None, node_id="")
```

**Two producers, one session:** the dev harness builds it from selectors; the Prep
`Start Combat` flow (T.23a) builds the **identical** object → same view. The view owns
resolution (takes inputs, not a pre-resolved result).

**Result-out (T.15a, V.64):** `build_combat_view(..., on_exit: Callable[[BattleResult],
None])` hands the resolved `BattleResult` back on **every** exit (end-panel Continue /
control-bar Exit / Escape — all carry the same up-front-resolved result; **commit-on-start**,
V.69). The **producer** applies progression; the dev harness ignores the arg
(`lambda _result: _pop(page)`).

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
on_settings=None, save_exists=False) -> ft.View`. The app entry point
(views_spec §4): title + pitch + entries. **New Run** is live (→ RunStart →
Trail); **Continue** stays disabled until load-into-Trail (T.15, hint reflects
`save_exists`); **Playfight ▶** opens the combat dev harness; **Settings**
(rendered when `on_settings` is wired) opens the API-key view; **Quit** closes the
app. Pure presentation — emits intent through the `on_*` callbacks; the host owns
the view stack. Buttons keyed by their `content` label (Flet 0.84).

## `ui/views/settings.py` — Settings (API key, route `/settings`)

`build_settings_view(page, *, on_back) -> ft.View`. Lets a player set the
OpenWeather API key **in-app** (no `.env`/shell needed). Pure presentation over
**`src/app_config.py`** (Flet-free file I/O): a masked, reveal-able key field +
**Save** → `app_config.save_api_key` (atomic temp→`os.replace`), status line
(saved / cleared / none), and the config-file path. The key is **never displayed
in full or logged** (V.3). Persistence lives in `~/<user-data>/tempest-fauna-trail/
config.json` (sibling of `saves/`), kept **separate from `game/save.py`** (V.36 =
*Run* persistence only). `app_config.resolve_api_key()` reads **env var → config
file → None** (env wins). The Trail calls it on open: a key starts the refresher,
none ⇒ every node stays `?` (V.66). Changing the key takes effect the next time the
Trail opens (Settings is reached from the menu, so no Trail is live to re-init).

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
- **V.63** — the run-loop UI computes no game logic (Prep mutates `Run` only
  through `game/economy.py`/`game/shop.py`, resolves only via the combat view).
- **V.68** — Prep placement is confined to the allied zone (cols 0–2) + validated
  team-only by `game/loadout.py::validate_team_positions` atop the V.62 guard.
- **V.69** — the run-loop applies a fought node's outcome only through
  `economy.apply_node_result(run, result)` (once per fight, never re-resolving);
  combat exits via `on_exit(result)` (commit-on-start). Extends V.64.
- **V.70** — graded viz (`route_map`, `run_summary`) is hand-drawn on `flet.canvas`
  (pure `*_specs` data fn + canvas builder, asserts data not pixels); no dependency on
  Flet's removed core chart widgets (`ft.BarChart`/`LineChart`/`PieChart`, ≥0.85).

## File map

| Concern | File |
|---|---|
| `CombatSession` + pure cue/queue model (`build_playback`) | `src/ui/combat_playback.py` |
| Combat view (canvas board, stepper drive loop, inspect, end panel) | `src/ui/views/combat.py` |
| Prep view (placement + shop + bench + preview + tooltips, T.23a) | `src/ui/views/prep.py` |
| Reward view (post-fight panel, T.15a) | `src/ui/views/reward.py` |
| Reward orchestrator (`apply_node_result`, V.69) | `src/game/economy.py` |
| Run-summary view + canvas damage chart (T.13, V.70) | `src/ui/views/summary.py`, `src/viz/run_summary.py` |
| Shared hex-board pixel geometry (combat + Prep) | `src/ui/components/board_geometry.py` |
| Dev harness launcher → `CombatSession` | `src/ui/views/dev_harness.py` |
| Main menu (`/`, T.9) — New Run/Continue/Playfight/Quit | `src/ui/views/menu.py` |
| App shell — menu↔harness↔run-loop `page.views` nav | `src/main.py` |
| Design tokens / shared components (`meter_bar`, chips, …) | `src/ui/theme.py`, `src/ui/components/` |
