# UI — main menu + combat view + dev harness (LIVING)

> **Status:** ✅ for the main menu (T.9), combat view core + dev harness (T.12a),
> **RunStart (T.10)**, **Trail (T.11)**, **Prep (T.23a/b — full economy + items)**,
> **Reward + result-out seam (T.15a)**, **Summary (T.13 — canvas damage chart)**,
> **routing + Continue (T.15b)**, **Prep items (T.23b)**. The **full menu→…→menu loop
> is live**: New Run → RunStart → Trail → Prep → Combat → Reward → Trail, terminal →
> **Summary** → menu; **Continue** loads the latest save into the Trail. **MVP run-loop
> slice complete.** FROZEN design:
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
    shows only on the `CURRENT` node → `_play_next(node)`: **locks the current node's
    weather** (`run.lock_node_weather`, T.39/V.73) before `on_play_next(node)`.
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
    **Display is tri-state by `node.weather_state` (T.39/V.73, was `CacheState`):**
    UNKNOWN → a `?` "weather pending" chip (map label `?`, favor `— pending`) — **never a
    concrete weather it hasn't fetched**; SUBSTITUTE → the city default weather **flagged
    `fallback`**; LIVE → the weather badge unflagged. **No API key** (or `WeatherClient`
    `ValueError`) ⇒ refresher skipped, so **every node stays UNKNOWN → `?`** until a key
    is configured. **Persistence (T.39/V.73):** `_weather_status` reads the **persisted
    `Run` `Node`** (not the ephemeral cache), and `_sync_cache_to_run()` (called each
    `_render`) write-throughs fetched cache values onto the `Run` via
    `run.set_node_live_weather` (no-op on locked nodes) — so weather **survives Trail
    re-open + Save&Exit** instead of resetting to `?` (fixes B.33). `node.weather` is now
    the **live-locked** game weather (no longer pinned to `default_weather`): combat Weather
    Favor + the CHALLENGE 30% live-weather slot read it; FIGHT squad theming stays on stage
    affinity (deterministic, V.2). The view is
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

## Prep (T.23a, layout/panels T.40) — `ui/views/prep.py`

The pre-combat decision layer (route `/prep`). Pure presentation over the finished
economy/combat backend (V.63/V.1): it mutates `Run` **only** through `game/economy.py`
/ `game/shop.py` (buy/reroll/sell/supply, `try_rank_up_with_amber`, `toggle_shop_freeze`)
and resolves combat **only** by building a `CombatSession` — it recomputes no
Amber/cost/level/encounter number.

- **TFT-style layout (T.40):** **shop on top** (full-width 5-slot rail), then three
  columns — **left rail** = combat-weather · traits · augments · item-bench · shop-odds
  panels; **center** = the hex board ("map") + bench below + the action row (Auto-Place /
  Reset / Start Combat); **right** = the champion sheet (inspect) + enemy preview. Each
  panel is a `_render()`-rebuilt holder.
- **Placement → `Run.team_positions` (persisted, V.76):** the player arranges the team on
  the hex board (Flet `Draggable` tokens + per-cell `DragTarget`, TFT-style bench↔board)
  within the **allied deployment zone** (columns `0..ALLIED_ZONE_MAX_Q-1` = 0–2, V.68).
  `run.roster` = the deployable field (capped at `tempest_rank`); `run.bench` = reserves.
  The view **binds `team_positions = run.team_positions`** and mutates it in place, so the
  formation **survives Prep→Combat→Prep + Save&Exit**. On entry it prunes stale ids + fills
  new champions (`_ensure_placed`); a first-ever entry with none falls back to default
  `assign_spawns` packing (V.62/V.2).
- **Auto-Place / Reset** = the default packing `champion i → (i // 7, i % 7)`, mirroring
  `engine.assign_spawns` so it's **byte-identical** to `positions=None` (V.62/V.2).
- **Shared geometry:** the hex pixel layout lives in `ui/components/board_geometry.py`
  (`cell_xy`, `COL_W`, `ROW_H`, `BOARD_W/H`), reused by the combat view — one coordinate
  source, no drift.
- **Shop top rail (T.40) + freeze (V.75):** horizontal 5-slot rail (`run.shop_offers`, cost
  via `champion_cost`, owned-copy `●N` badge from `run.champion_copies`). The shop
  **auto-rerolls on every Prep entry** (`refresh_shop(run)` at view build) — frozen slots
  persist. Each slot has a **freeze toggle** (❄/✛ → `toggle_shop_freeze`); a frozen slot
  shows a 2px accent border and is kept across rerolls **and** Prep phases. Clicking a slot
  (not the freeze/Buy buttons) inspects it.
- **Inspect panel (right):** tap-to-inspect works from **board, bench, or shop** — a shop
  slot sets `state["shop_sel"]` → a **read-only preview** from
  `content.build_champion_at_level(id, 1)` + Buy (`buy_from_shop` via the first matching
  slot); an owned token sets `state["selected"]` (mutually exclusive). Shows **name ·
  affinity · role `[role_code]` · L/T**, **trait chips** (`champ.traits`), a stat grid,
  **copy-combine progress** (`level_from_copies` / `LEVEL_COPY_THRESHOLDS` — 3→L2, 9→L3),
  and the **actives + passive** rendered live via `ability_text.render_for(id, champ)`
  (name + blurb + formula, against the `Champion`'s own `.stat()`, source-of-truth B/V.38).
  Equipped items unequip on click; the inventory **bench** lives in the left Items panel.
- **Left-rail panels (T.40):** **Augments** — `run.active_augments` names from
  `AUGMENT_REGISTRY` (blurb tooltips). **Traits** — `traits.preview_team_traits(placed,
  board_cap, bonus_counts=run.augment_state['trait_bonus'])` (pure tally, V.21/V.1) rendered
  via the shared `ui/components/trait_synergies.py::trait_synergies_panel` (used by Combat
  too). TFT-style: **active** synergies (≥1 rung cleared, `TraitPreview.active`) read
  prominently with a SUCCESS rail + lit rung-ladder pips (`TraitPreview.thresholds`); **dormant**
  ones (carried, below the first rung) are greyed under a "Dormant" divider. `bonus_counts`
  folds in augment Crest/Crown so the preview matches what combat clears. **Items**
  — the inventory component bench; clicking a chip equips onto the selected unit via the
  `game/inventory.py` seam (auto-combine on double-equip, V.2).
- **Rank-up affordance:** the top-bar resources row shows `Tempest {have}/{tempest_threshold(rank)}`
  and a **`Rank Up ({rank_up_cost_amber}⨀)`** button (disabled when unaffordable or at
  `MAX_RANK`, with a tooltip explaining 1 Amber = 1 Tempest). All numbers read from
  `game/economy.py` — the view computes none.
- **Combat-weather panel:** for `node.weather` (the live-locked combat weather — frozen at
  Prep-entry on the Trail, T.39/V.73), lists each non-CLEAR affinity ordered strongest-buff → strongest-debuff via
  `weather_effects.ring_relation`. Each affinity is a **mini-card** (tone-coloured left rail):
  header row = colour dot · name · tone-tinted favor badge (`_FAVOR_LABEL`) · "◀ you" when
  the team fields that affinity; below it the per-stat deltas from
  `weather_effects.combat_modifier(affinity, weather)` render as **discrete chips** (one per
  stat, so they size to content and never char-wrap in the narrow rail). CLEAR ⇒ "no affinity favored".
- **Shop tier-odds panel:** renders the current Tempest rank's tier distribution from
  `shop.RANK_TIER_WEIGHTS[run.tempest_rank]` (normalized to %), beside the **next rank's**
  for comparison. Odds are **rank-gated** (V.74) — ranking up both widens the team cap
  and lifts/widens the tier band, so the panel quantifies exactly what an Amber rank-rush
  buys. The note tells the player odds follow Tempest rank.
- **Items (T.23b):** all equip/unequip routes through the `game/inventory.py` seam (V.63,
  never inline) — the left **item bench** equips a component onto the selected unit; the
  inspect panel's equipped chips unequip on click. `equip_item` **auto-combines on
  double-equip** (incoming item + a held component that form a recipe → the combined item
  in one slot, `items.combine`), else fills a free slot (≤3); `unequip_item` returns the
  item whole. Deterministic (first held partner, V.2). Chips classify each item via
  `prep._item_kind` — **component** (raw, ◆, can still fuse) · **gem** (Spirit Gem, ✧) ·
  **combined** (✦, terminal, bordered) — with an explanatory tooltip, and Title-case the
  snake_case id (`_item_label`, stopgap until the authored item render-layer). Reward drops
  grant ids from `items.base.BASE_COMPONENTS` so two reward components always fuse (V.77).
- **Start-Combat:** `team = run.roster` placed pieces; `validate_team_positions(team,
  positions)` (`game/loadout.py`, V.68 — zone + roster-id, on top of the V.62 engine
  guard); builds `CombatSession(team, enemies, weather=node.weather, run_mods=
  RunModifiers.from_run(run), node_id, map_effect_id, positions=team_positions)` —
  shape-identical to the dev-harness producer — and hands it to the host. The
  reward/progression step (applying the `BattleResult`) is the host's job (T.15, V.64);
  Prep only produces the input. Combat weather = `node.weather` — the **live-locked** value
  frozen at Prep-entry (T.39/V.73); reproducible because the locked value is saved (replay
  reads the same; FIGHT squads stay on stage affinity, V.2).

The combat view is **pure presentation over the replay backend** (V.56): it
renders a fight only through `resolve_combat` + the forward `CombatReplay`
stepper + `inspect_at_tick` + the recorded `BattleResult` stream, and implements
**no** combat math. `ui/` imports `game/`, never the reverse (V.1).

## Reward (T.15a + T.38) — `ui/views/reward.py` + `economy.apply_node_result`

The post-fight panel (route `/reward`). The run-loop **producer** (`main.py::_finish_combat`)
is what closes a node — not the view:

1. `economy.apply_node_result(run, result) -> NodeResultSummary` — the single game-side
   reward orchestrator (V.69/V.70/V.71): appends `result` to `run.battle_log`, grants seeded
   income (win bonus on a win only, V.2) and — **on a win** — fight tempest (`grant_fight_tempest`,
   cascades rank-ups) + the node's **type auto-reward** (`generate_node_reward` → REWARD loot
   to `Run.inventory` / CHALLENGE amber+components+tempest; `champion_offer` surfaced *pending*,
   V.70) + `mark_current_node_cleared` + `advance_to_next_node` (→ `VICTORY` if last). A
   **non-win** decrements `Run.hearts` (Hearts model, V.71): a non-boss/non-final loss with
   `hearts > 0` survives (CLEARED + advance), while a **BOSS_FIGHT loss**, a **final-node loss**,
   or `hearts <= 0` sets `status = DEFEAT`. Unique payouts are win-only ⇒ a loss is reward-zeroed.
   Called **exactly once per fight**, never re-resolves.
2. node-boundary autosave via `save.save_run` (V.65) — `Run.hearts` round-trips (back-compat default 3).
3. `build_reward_view(page, run, summary, *, on_continue)` — pure presentation off the
   `NodeResultSummary` + live `Run`: outcome banner (incl. **"Held the Line"** for a survivable
   loss), Amber/tempest/rank, **Hearts** (♥, DANGER-tinted when ≤1), nodes cleared, a **Rewards**
   block (loot items + bonus Amber), and — for a pending CHALLENGE `champion_offer` — an
   interactive **Recruit / Skip** that mutates the run only via `economy.recruit_challenge_offer`
   (V.63 — the view chooses, `game/` mutates; recompute nothing). **Continue** → the producer's
   router (`main.py::_finish_combat`): a continuing run pops to the menu and pushes a **fresh
   Trail** at the new current node; a terminal run pushes the **Summary** view → menu (T.15b).

## Summary (T.13) — `viz/run_summary.py` + `ui/views/summary.py`

The run-end screen (route `/summary`). Mirrors the route-map's graded-viz shape
(V.72): a **pure data fn** + a **canvas builder** — no `ft.BarChart` (removed from
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
  Return-to-Menu. The producer (`main.py::_finish_combat`) routes a terminal run here
  (T.15b); the menu **Continue** loads the latest save → Trail.

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

Layout mirrors Prep (T.12d_a): header → divider → **action-queue strip** (where
Prep has the shop) → a **3-column body** — **left rail** (≈250: `weather_badge` +
the **shared trait-synergy panel** + active-augments line + the damage-type legend,
all static for the fight) · **centre** (hex board + the Prev/Next/Autoplay/End/
Restart/Exit controls) · **right** (≈320: the selected piece's infocard). The whole
body sits in a `Stack` under the `end_overlay`.

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
- **Right — infocard (read-only):** selected piece → the **shared `infocard_core`**
  (`src/ui/components/infocard.py`, T.12d_a/V.82) that **both** Prep and Combat render
  through: `infocard_header` (role glyph + affinity-coloured name + affinity/trait
  glyph cluster + subtitle), `infocard_stat_grid` (two-column glyph + label + value),
  `infocard_abilities` (name + **inline-iconed** blurb via `inline_effect_text` +
  formula, `render_for` against the stat source). Combat builds a `PieceInfo` from a
  live `PieceView` (`stat_src = _ViewStatSource(pv)` → blurbs track the live STR/AS
  ramp, V.38/V.57; `role`/`traits` off the `PieceView`, V.82) and wraps the core with
  its **combat-only extras** — current HP/barrier line, per-slot mana, status rows,
  read-only `render_item` item names; Prep builds the same `PieceInfo` from a
  `Champion` and wraps it with the copy-level line / interactive item chips. The team
  augments + synergy panel moved to the **left rail** (static for the fight). Hover a
  token for the same ability blurbs as a tooltip.
- **Floating numbers:** the step's `pre_beats` (interstitial DOTs) reveal by a
  **tick cutoff** (`state["reveal_tick"]`, set to the step tick on advance) — same-
  tick DOTs show together; the action `beats` reveal one at a time via the drip
  (below). Coloured by damage type (legend on screen); crit = `!` + size. (T.12b)
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
- **Sequential intra-tick reveal (T.12d_b, the one drip path):** the engine sorts +
  resolves a tick's actions one by one; the view mirrors that. A forward `Next` (and
  autoplay) re-seeds `reveal_n = 0`, then `_drip_action_beats` reveals beats `1..N` in
  recorded chronological order, **each given its animation window before the next**
  (`_BEAT_GAP_S` ≈ the `_TWEEN_MS` tween, scaled by the speed toggle) — so when
  **multiple pieces act on one tick** you read *A moves → B moves → A attacks → B casts*
  in order, not all at once. Each newly-revealed beat pops its footprint/halo/flash +
  floating number (`fp_phase`). `_advance_to` sets `reveal_n` to the full beat count for
  backward/seek (instant static truth). Interrupt-safe (`anim_token`): a rapid Next aborts
  the drip and the next advance shows everything. **Autoplay reuses this exact path**
  (no separate event-paced loop), so the stagger + every FX play under autoplay too.
- **Death linger (T.12d_b):** a piece dying *during* a tick gets a `death` beat in the
  step. `_death_markers(step, reveal_n, action_shown)` (pure, unit-tested) returns the
  ids dying this tick + which have had their death beat revealed: until revealed the
  piece reads as alive; once revealed it renders a **grayed body** (`_token(dead=True)`:
  desaturated disc + `✕`, dimmed) that **stays on the board through the rest of the
  tick's beats** so a later same-tick hit lands on a visible body, not an empty cell.
  Pieces that died on an **earlier** tick are skipped entirely (gone). Fixes the old
  "vanish then get attacked" flash.
- **Action queue (future-only + next highlight, T.12d_b):** `Playback.queue(cursor)`
  is **strictly upcoming** (`tick > now`) — the resolved tick's entries drop off the
  rail as the cursor lands on them. The entry(ies) at `Playback.next_action_tick`
  (the next step's tick — what one `Next` resolves) render **bigger + accent-bordered**
  ("next up", `animate_size`); fixed-width row with horizontal overflow so the layout
  never shifts. **Status pips** under each token (colour by status, stack count,
  remaining-time tooltip). **Sudden-death** (tick ≥ `SUDDEN_DEATH_TICK`): header badge +
  board border tint + a `DANGER` divider in the queue.
- **Autoplay = fixed cadence (T.12d_b, V.56):** `_autoplay_loop` advances one step,
  **awaits the same `_drip_action_beats`** (sequential beats + FX), then sleeps an
  inter-tick dwell `_TICK_GAP_S` before the next step — both gaps scaled by the
  **speed toggle** (`0.5×`/`1×`/`2×` → `_SPEED_FACTORS`, default `1×`). Wall-clock dwell
  over the deterministic replay, never feeding the sim (V.2/V.14). Replaces the old
  event-paced `_play_step` + the B.35 `_ACTION_DWELL_S` band-aid (both deleted —
  closes D.28 (1)+(2)). `anim_token`-interrupt-guarded (Next/Prev/Pause/exit aborts).
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
  **speed toggle** (`0.5×`/`1×`/`2×`), ⏭ End (fast-forward), ↺ Restart, Exit.
- **Combat-end panel (T.12d_b):** outcome banner + survivors + `rounds`/timed-out
  line + a **per-champion damage table** (one row per fielded champion — name, damage
  dealt, damage taken, from `BattleResult.team_damage_dealt`/`_taken`, sorted by dealt
  desc, dead marked `✕`, monospace) + **Continue** (→ `on_exit`).

**Playback driver:** a forward `Next` re-seeds `reveal_n = 0` then runs the async
`_drip_action_beats` (sequential beat reveal + FX); backward/seek re-renders the full
static truth instantly. Autoplay is opt-in, an **async loop** (`page.run_task(_autoplay_loop)`)
that advances one step, **awaits the same drip**, then sleeps the inter-tick gap — a
fixed real-time cadence scaled by the speed toggle (V.56; wall-clock over a
deterministic replay, never tick=second). It never blocks the main thread and stops
on view pop / toggle-off (the view's on-pop handler, stashed on `view.data`, clears an `alive`
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
  `CombatSession`, swappable producers; manual event-step default, **autoplay = fixed
  real-time cadence** (speed toggle) over the deterministic replay, not tick=second.
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
- **V.72** — graded viz (`route_map`, `run_summary`) is hand-drawn on `flet.canvas`
  (pure `*_specs` data fn + canvas builder, asserts data not pixels); no dependency on
  Flet's removed core chart widgets (`ft.BarChart`/`LineChart`/`PieChart`, ≥0.85).

## Iconography — `ui/components/iconography.py` + `ui/theme.py` maps

Shared glyph + tone helpers so every affinity / weather / trait / role / stat /
ability-effect state pairs **colour with a glyph** (colourblind-safe, reads at a
glance). Pure presentation; canonical token maps live in `theme.py`, behaviour in
`iconography.py`.

- **Token maps (`theme.py`):** `AFFINITY_ICONS` (== `WeatherState`, also used by
  `weather_badge`), `TRAIT_ICONS` (one per `TRAIT_REGISTRY` id; the six weather
  Callings reuse their affinity glyph) + `TRAIT_ICON_FALLBACK`, `ROLE_ICONS` +
  `ROLE_ICON_ASSETS` (swashbuckler → the sword asset), `STAT_ICONS`,
  `ABILITY_TAG_ICONS`, `TIER_BRONZE/SILVER/GOLD`, `SWORD_ICON_ASSET`
  (`icons/sword.svg` — physical damage + swashbuckler; Material has no blade).
- **Helpers (`iconography.py`):** `affinity_glyph`/`affinity_marker`, `favor_tone`
  + `clash_marker`/`clash_legend` (buff green ▲ / debuff red ▼ / neutral),
  `trait_glyph` (tier-coloured by rungs cleared, greyed when dormant), `role_glyph`
  (Image for asset roles, Icon otherwise), `stat_glyph`, `rich_tooltip` (dark card +
  tone border — Flet tooltips are single-style, so structure carries meaning via
  markers), and **`inline_effect_text`** — renders blurb prose with effect glyphs
  **inline** at the keyword (`"deal 120 physical damage ⚔ to the target"`), via a
  word-walk + two-word phrase map (`physical damage`, `move speed`, …) laid out in a
  wrapping Row.
- **Consumers:** Prep + Combat (both via the **shared `infocard_core`** —
  `infocard_header`/`infocard_stat_grid`/`infocard_abilities`, T.12d_a/V.82), Trail
  (enemy preview), `affinity_chip`, `weather_badge`, `trait_synergies_panel`.
- **Drift guards (tests):** every `TRAIT_REGISTRY` trait has a `TRAIT_ICONS` entry,
  every `WeatherState` an `AFFINITY_ICONS` entry, every roster role an icon in
  `ROLE_ICONS`/`ROLE_ICON_ASSETS`, the sword asset exists on disk, and **Prep and
  Combat both call the `infocard_*` core** (`TestInfocardSharedByBothViews`, V.82).
- **Shared infocard core (`src/ui/components/infocard.py`, T.12d_a/V.82):** a
  `PieceInfo` struct (built per-view from `Champion` / `PieceView`) feeds three pure
  builders — `infocard_header`, `infocard_stat_grid`, `infocard_abilities` — so the
  combat inspect and the Prep sheet render **identical** identity + stats + ability
  blurbs and cannot re-drift. `PieceView` now carries display-only `role` + `traits`
  (set in `compile_loadout` via `Piece.role`; never read by combat math). Each view
  wraps the core with its own extras (Prep: copy-level line / interactive items;
  Combat: live HP/barrier/mana/status / read-only item names).

## File map

| Concern | File |
|---|---|
| Shared iconography (glyph/tone helpers, inline effect text) | `src/ui/components/iconography.py`, `src/ui/theme.py` |
| Shared champion infocard core (Prep + Combat, V.82) | `src/ui/components/infocard.py` |
| `CombatSession` + pure cue/queue model (`build_playback`) | `src/ui/combat_playback.py` |
| Combat view (canvas board, stepper drive loop, inspect, end panel) | `src/ui/views/combat.py` |
| Prep view (placement + shop + bench + preview + tooltips, T.23a) | `src/ui/views/prep.py` |
| Reward view (post-fight panel, T.15a) | `src/ui/views/reward.py` |
| Reward orchestrator (`apply_node_result`, V.69) | `src/game/economy.py` |
| Run-summary view + canvas damage chart (T.13, V.72) | `src/ui/views/summary.py`, `src/viz/run_summary.py` |
| Shared hex-board pixel geometry (combat + Prep) | `src/ui/components/board_geometry.py` |
| Dev harness launcher → `CombatSession` | `src/ui/views/dev_harness.py` |
| Main menu (`/`, T.9) — New Run/Continue/Playfight/Quit | `src/ui/views/menu.py` |
| App shell — menu↔harness↔run-loop `page.views` nav | `src/main.py` |
| Design tokens / shared components (`meter_bar`, chips, …) | `src/ui/theme.py`, `src/ui/components/` |
