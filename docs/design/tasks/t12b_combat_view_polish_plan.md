# T.12b Plan — Combat view boss + polish

> **Status:** plan — ready for review. (The **§T.12b row already exists** (📋 Plan); this plan fills it in. Minor `/spec` goal-line refinement + one new §V for the boss single-entry promotion — see §10.)
> **Depends:** **T.12a** (combat view core — ✅ done), **T.37c** (`CombatReplay` stepper — ✅), **T.21** (bosses/map-effects — ✅). All met.
> **Resolves:** the polish half of SPEC §T.12 — boss support + the readability/animation layer surfaced in playtest (DOTs unreadable, no sudden-death cue, attacks/casts/moves not legible).
> **Design source of truth:** [`views_spec.md` §7](../systems/views_spec.md) (zones, telemetry, states), [`t12_combat_view_plan.md`](t12_combat_view_plan.md) (the core + §7.1 research backlog this plan executes), LIVING [`docs/live/systems/ui.md`](../../live/systems/ui.md) + [`combat.md`](../../live/systems/combat.md).
> **What this plan adds beyond those:** the concrete animation model (token tween, attack/cast arrows, tickwise DOT reveal incl. autoplay, sudden-death cue), the **boss single-entry promotion** (`resolve_boss_combat` + map-effect-aware `CombatReplay`/`inspect_at_tick` into `src/game/combat/`), and a board map-effect overlay.
>
> **⚠️ Headless-build caveat:** the view is built without a display — animations cannot be self-verified. Every visual deliverable below carries a **user visual-verification gate** (`TEMPEST_DEV=1 uv run flet run`). Logic (pure model, boss byte-identity) is test-gated as usual.

## 0. Substep split (`T.12b-A` readability/animation · `T.12b-B` boss)

Two independent seams; each ships + verifies on its own. **B does not depend on A.**

- **T.12b-A — Readability & animation (presentation-only, V.56/V.57).** Token movement tween, attack/cast target arrows, tickwise DOT reveal (fixed + autoplay-visible), sudden-death indicator, status-icon row, real-time-scaled autoplay pacing. Touches only `ui/` (+ a tiny pure `combat_playback` helper). No `game/` change → sims trivially byte-identical.
- **T.12b-B — Boss support.** Promote `resolve_boss_combat` `tools/`→`src/game/combat/resolve.py`; map-effect-aware `CombatReplay`/`inspect_at_tick`; board map-effect overlay; harness BOSS node type. Touches `game/combat/` (V.1 promotion, V.2 byte-identical) + `ui/`.

## 1. Scope

**In scope (A):** `ui/views/combat.py` (tween, arrows, sudden-death cue, status icons, autoplay pacing), `ui/combat_playback.py` (a pure `prev-position` lookup + sudden-death helper, tested), `tests/ui/test_combat_playback.py`. **Plus a small `game/` fix** (the real drip root cause, §3.A.3): `game/combat/recorder.py` + `game/combat/context.py` + `game/events.py` — emit a `dot` beat for **true-damage** DOT ticks (sudden death) so they're captured + drippable. Observer-only ⇒ byte-identical (V.2).

**In scope (B):** `game/combat/resolve.py` (+`resolve_boss_combat`), `game/combat/replay.py` (`CombatReplay`/`inspect_at_tick` take `map_effect_id`), `game/combat/__init__.py` (export), `ui/combat_playback.py` (`CombatSession.map_effect_id`), `ui/views/combat.py` (map-effect overlay), `ui/views/dev_harness.py` (BOSS type), `tools/playtest/_common.py` (delegate to the promoted fn), tests.

**Out of scope (why):**
- **Sprites / art** — tokens stay affinity-tinted circles + initials; art is a later content pass (deferred in T.12a §7).
- **Tick-by-tick admin mode** — the original row mentions it; defer unless trivial (the stepper already supports arbitrary `step_to`; a raw-tick scrubber is a small follow-up, flag in §7).
- **New combat math** — A is pure presentation; B moves boss wiring **verbatim** (V.2). No balance/mechanic change.

## 2. The gap today

| Piece | Where (`file.py:line`) | State |
|---|---|---|
| Tokens drawn as `cv.Circle` on the canvas (no per-shape animation) | `ui/views/combat.py` `_build_board` | 🔶 — canvas shapes can't tween; need overlay containers for `animate_offset` |
| `_drip_pre_beats` tickwise DOT reveal | `ui/views/combat.py` | 🔶 — works for `tag==DOT` (burn/poison) but **not sudden death** |
| **sudden-death (`dot_true_damage`) DOT → `SourceTag.TRUE`** → recorder emits **no beat** (only `tag==DOT`/`ABILITY` beat) | `status.py:200`, `combat/recorder.py:244`, `combat/engine.py:606` | 🔴 — **the real "drip not working"**: true-DOT produces no `dot` beat → no `pre_beats` → nothing to drip; HP collapses + units die "at once" with no animation |
| Autoplay = fixed `_AUTOPLAY_INTERVAL_S=0.75` | `ui/views/combat.py` | 🔶 — not tick-gap-scaled |
| No attack/cast target arrows | `ui/views/combat.py` | ❌ |
| No sudden-death cue (board or queue) | — | ❌ |
| Status icons only as text in inspect | `ui/views/combat.py` `_build_inspect` | 🔶 — no under-token row |
| `SUDDEN_DEATH_TICK_START = MAX_TICKS = 12000`, `ROUND_TICKS=600`, `TICKS_PER_SECOND=100` | `combat/engine.py:45`, `combat/recorder.py:46`, `ability_text.py:32` | ✅ (read) |
| `resolve_boss_combat` (build_combat + `attach_map_effect` + run) | `tools/playtest/_common.py:108` | 🔴 — in `tools/`; UI can't import (V.1) |
| `attach_map_effect(effect_id, ctx, seed)` | `loadout.py:173` | ✅ |
| `BossEncounterResult.all_enemies` / `.map_effect_id`; `generate_boss_encounter` | `bosses/data.py:135/132`, `encounter.py` | ✅ |
| `CombatReplay`/`inspect_at_tick` — no map-effect support | `combat/replay.py` | 🔴 — boss replay ignores hazards/sunlit/fog |
| Board cell state for overlay (`hazard_cells`, cell `kind` sunlit/hazard/ley/slow) | `board.py:34/84` | ✅ (exists; not yet exposed read-only by the stepper) |

## 3. Architecture

### 3.A Readability & animation (T.12b-A)

**3.A.1 Token movement tween.** Canvas `cv.Circle` cannot animate. Move the **token body to an overlay `ft.Container`** (circle via `border_radius`, affinity bg, initials text, ally/enemy border) positioned with `left`/`top` + `animate_position=ft.Animation(ms, ease)` (or `animate_offset`). On a step, the container is placed at the piece's **current** `(q,r)` pixel; because the same control id persists across renders, flet tweens the position change → glide. Canvas stays for **cells + arrows** behind. **Wrinkle:** flet diffs controls by list position/key — to tween rather than pop, the per-piece overlay must be **keyed by piece id** (`ft.Container(key=pid)`) and kept in stable order across renders, else flet rebuilds (pop). *Verify: tokens glide on a move step.*

**3.A.2 Attack/cast target arrows.** On a step, for each `attack`/`ability`/`cast` beat with a target, draw a `cv.Line` actor-centre→target-centre (color by damage type, arrowhead via a short second line or a `cv.Path`). Casts with no single target (AoE/self) → a ring on the actor instead. Lines live on the canvas (redrawn per render). *Verify: who-hits-whom legible.*

**3.A.3 Tickwise DOT reveal — redesign + the real root cause.** Keep `Step.pre_beats` (T.12a). **Root cause of "drip not working" (playtest, sudden death):** `dot_true_damage` statuses — `sudden_death` — call `ctx.deal_damage(..., SourceTag.TRUE)` (`engine.py:606`), and `recorder._on_damage_dealt` emits a `dot` beat **only** when `tag == SourceTag.DOT` (`recorder.py:244`). So **true-damage DOTs emit no beat** → no `pre_beats` → the drip has nothing to animate; the stepper's HP just collapses and 3 units die "at once." (Normal burn/poison, `tag==DOT`, *do* drip.)

**Fix (small `game/` change, observer-only):** thread an `is_dot` flag so the recorder emits a `dot` beat for **every** status-DOT tick regardless of `physical/magical/true`:
- `DamageEvent.is_dot: bool = False` (`events.py`); `process_statuses` sets `is_dot=True` on **both** its DOT `deal_damage` calls (true + magical, `engine.py:606/608`); `ctx.deal_damage(..., is_dot=…)` threads it onto the `dealt_event`.
- `recorder._on_damage_dealt`: emit the `dot` beat when `tag == DOT` **or** `event.is_dot` (covers sudden-death true-DOT). `turns` still excludes `dot` ⇒ **byte-identical** sims (V.2/V.14); only `combat_log` goldens re-baseline (new sudden-death dot lines). This **does not** make DOTs standalone steps — `combat_playback` absorbs them into the next action's `pre_beats` (T.12a), so they stay the drip ("between two actions"), per the user's "DOTs aren't queue entries" call.

**View fixes (presentation):** (a) the drip also runs under **autoplay**; (b) each revealed DOT gets a brief **on-token flash**; (c) the status row (3.A.5) shows the bleeding status. The reveal order/count stay pure-model truth (`pre_beats`, tested). *Verify: sudden death now ticks visibly (units bleed down over a few reveals) instead of dying instantly; burn/poison drip too.*

**3.A.4 Sudden-death indicator.** Pure helper `is_sudden_death(tick) -> bool` (`tick >= SUDDEN_DEATH_TICK_START`) in `combat_playback` (tested). View: once the cursor tick crosses it, show a persistent **banner/badge** ("⚠ Sudden Death") in the header + tint the board border; the action queue marks the boundary (a red "Sudden Death" divider, like the round-split marker). *Verify: badge + queue marker appear at tick 12000.*

**3.A.5 Status-icon row.** Under each token, a compact row of status pips (one per `PieceView.statuses` entry: short glyph/initial + stack count, tooltip = `status_id · x{stacks} · {remaining}s`). Read live from the stepper (V.57). *Verify: burn/poison/stun show under the token with remaining time.*

**3.A.6 Real-time-scaled autoplay pacing.** Pace by the **inter-action tick gap**: between step N and N+1, delay `≈ clamp((tick[N+1]-tick[N]) / TICKS_PER_SECOND × SPEED, min, max)` (V.39 — ticks→seconds for *pacing feel* only, still event-paced, not a tick=second sim clock; V.56). `SPEED`/`min`/`max` authored (§5). Pure helper `autoplay_delay_s(prev_tick, tick)` in `combat_playback` (tested). *Verify: bursts of fast actions feel fast; long gaps don't stall forever (clamped).*

### 3.B Boss support (T.12b-B)

**3.B.1 Promote `resolve_boss_combat` → `src/game/combat/resolve.py`.** Move the body **verbatim** (build_combat → `attach_map_effect` if id → `run_combat` → `build_result`). **Keep `combat/` content-import-free** (the package HARD RULE): the promoted fn takes a **`map_effect_id: str`** (+ `enemies`), **not** a `BossEncounterResult` (that lives in `bosses/data.py`) — `attach_map_effect` is already a deferred `loadout` import. Signature:
```
resolve_boss_combat(team, enemies, weather, *, map_effect_id="", run_seed=42, node_id="", run_mods=None) -> BattleResult
```
`tools/playtest/_common.resolve_boss_combat` becomes a thin shim: `from src.game.combat.resolve import resolve_boss_combat as _r; return _r(team, enc.all_enemies, weather, map_effect_id=enc.map_effect_id, ...)`. **Byte-identical** — same primitives, same order, same default seed (V.2). Guard: a test asserts the promoted fn == the old `tools/` result on a fixed boss seed; sim sweep unaffected (no sim uses bosses on the hot path).

**3.B.2 Map-effect-aware `CombatReplay`/`inspect_at_tick`.** Add `map_effect_id: str = ""` to both. In `CombatReplay.__init__`: after `build_combat(..., with_recorder=False)` and **before** creating the `_step_combat` generator, `attach_map_effect(map_effect_id, ctx, seed)` when set — so the boss replay reproduces hazard/sunlit/fog exactly (the map effect mutates `ctx`/board each tick inside the loop). `inspect_at_tick` passes it through. *Determinism:* same inputs+effect → byte-identical to `resolve_boss_combat`'s fight (V.55/V.2).

**3.B.3 `CombatSession.map_effect_id` + board overlay.** Add the field (T.12a left it as a TODO). The view, when `session.map_effect_id`, builds the `CombatReplay` with it. **Overlay:** expose board cell state read-only from the stepper — `CombatReplay.board_cells() -> list[tuple[int,int,str]]` ((q,r,kind) from `ctx` board: `hazard_cells` + sunlit/ley/slow modifiers, `board.py:34/84`) — never leaking the raw board (V.1). The view tints those cells on the canvas (kind→color). *Verify: a boss node shows its hazard/sunlit/fog tiles + boss at its `spawn_position`.*

**3.B.4 Harness BOSS node type.** Dev harness adds **BOSS** to the node-type dropdown → `generate_boss_encounter(seed, node_index, stage)` → `CombatSession(team, enc.all_enemies, weather, map_effect_id=enc.map_effect_id, node_id=…)`. (`sim_node.py:133` is the headless reference.)

### 3.C Invariant posture
- **V.1** — `ui/` imports `game/` only; the boss path now resolves through `src/game/combat/` (no `tools/` import from UI). `combat/` stays content-import-free (map effect via `str` id + deferred `loadout`).
- **V.2/V.55** — `resolve_boss_combat` moves verbatim (byte-identical); `CombatReplay` with a map effect replays the same fight; A adds no game logic.
- **V.56/V.57** — all visuals are presentation over the stepper; tween/arrows/icons/sudden-death read live state + the recorded stream's *cues*, never resource truth or combat math.
- **V.39** — autoplay pacing uses ticks→seconds for *feel* only; not a real-time sim clock.

## 4. Decisions
- **§4.1 Tokens → overlay containers (keyed by piece id) for tweening; canvas keeps cells + arrows.** Canvas has no per-shape animation; `animate_position` on a keyed container glides. *Proposal, firm (only way to tween in flet).*
- **§4.2 Boss promoted fn takes `map_effect_id: str`, not `BossEncounterResult`.** Keeps `combat/` free of `bosses/` content imports (package HARD RULE). *Firm.*
- **§4.3 Map-effect-aware replay via `attach_map_effect` before the generator.** Mirrors `resolve_boss_combat`'s order exactly → byte-identical. *Firm (V.2).*
- **§4.4 Autoplay pacing = clamped tick-gap × speed.** Event-paced feel without a real-time clock (V.56/V.39). *Proposal, overridable (numbers §5).*
- **§4.5 DOT reveal stays manual-drip + now autoplay-drip + token flash + status row.** Don't turn DOT ticks into queue entries (user-firm: too fine-grained). *Firm (user-set).*
- **§4.6 Split A (presentation) / B (boss); B independent.** Each verifies alone; A is zero-risk to sims. *Proposal, overridable.*

## 5. Authored values (presentation only; tunable)
- Token tween: `~250 ms` ease-out per move step.
- Arrow: stroke `~2.5px`, color = damage-type (`_DMG_COLORS`); AoE/self → ring radius `_TOKEN_R+6`.
- DOT reveal delay: keep `_DOT_REVEAL_DELAY_S ≈ 0.30 s`; token flash `~200 ms`.
- Autoplay pacing: `delay = clamp(gap_s × 0.5, 0.25 s, 1.5 s)` where `gap_s = (tick−prev_tick)/100`.
- Sudden-death: header badge + board border `DANGER`; queue divider `DANGER`.
No game numbers.

## 6. Content / roster audit + reconciliation
None — no rosters/tags/abilities touched. Map-effect ids (`sunlit_tiles`/`fog`/`hazard_tiles`) read from `bosses/data.py` (authored, T.21); board `kind` vocab (`sunlit`/`hazard`/`ley`/`slow`, `board.py:34`) drives overlay colors — no new vocab.

## 7. Open questions
**Resolved here (overridable):** §4.1 (overlay tokens), §4.2 (`map_effect_id` str), §4.4 (pacing formula), §4.6 (A/B split). Arrowhead = short twin lines (simplest in `cv`).
**Still open / deferred:** tick-by-tick admin scrubber (defer — stepper supports it, small follow-up); sprite art (deferred); whether autoplay should *also* token-flash each DOT or just reveal (refine in build with the user watching).

## 8. Test plan
Pure model + boss byte-identity are test-gated; **animations are user visual-verification gates** (no UI tests, CLAUDE.md).
- **A (pure helpers in `combat_playback`):** `is_sudden_death(tick)` boundary at `SUDDEN_DEATH_TICK_START`; `autoplay_delay_s(prev,tick)` clamps to `[min,max]` + scales with gap; a `prev_positions(steps)`/lookup helper if the tween needs precomputed prior coords — deterministic, Flet-free, no resource fields (B.28 guard still holds).
- **B (boss byte-identity, V.2):** `resolve_boss_combat` (promoted `src`) produces a `BattleResult` **byte-equal** to the pre-move `tools/` version on a fixed `(boss, seed, weather)`; `tools/_common.resolve_boss_combat` shim returns the same. `CombatReplay(map_effect_id=…)` HP at event ticks == `resolve_boss_combat` truth (hazard/sunlit/fog applied). `board_cells()` returns only value tuples (no raw board escapes, V.1). Full sim sweep unchanged (`workers=1` byte-identical).
- **Regression:** existing `combat_log`/replay/playback goldens unchanged by A; B re-baselines none (boss promotion is verbatim).
- **Visual gates (user):** tokens glide (not pop) on moves; attack/cast arrows point actor→target; DOTs tick visibly between actions (manual + autoplay); sudden-death badge + queue marker at tick 12000; status pips under tokens; boss node shows map-effect tiles + boss placement.

## 9. Acceptance criteria
**T.12b-A**
1. Tokens **glide** between cells on move steps (keyed overlay + `animate_position`), not teleport.
2. Attack/ability/cast steps draw a **target arrow** (or AoE/self ring); colored by damage type.
3. **Tickwise DOTs** reveal in order with a per-tick flash, on **manual Next and autoplay**; not queue entries. **Sudden-death DOTs now emit beats** (`is_dot`) ⇒ they drip-tick visibly instead of instakilling — units bleed down over reveals; sims byte-identical (V.2).
4. **Sudden-death** badge (header + board border) and a queue divider appear once tick ≥ `SUDDEN_DEATH_TICK_START`.
5. **Status pips** under each token (live, with remaining time); pure helpers tested.
6. **Autoplay** paces by clamped tick-gap (V.39 feel, V.56 event-paced).
7. `game/` unchanged by A; `combat_playback` helpers Flet-free + tested; `/check` passes.

**T.12b-B**
8. `resolve_boss_combat` lives in `src/game/combat/resolve.py` (takes `map_effect_id`); `tools/` shim delegates; **byte-identical** on fixed boss seeds; sims unchanged (V.2).
9. `CombatReplay`/`inspect_at_tick` accept `map_effect_id` and reproduce the boss fight (hazard/sunlit/fog) exactly (V.55).
10. Harness **BOSS** node type → `CombatSession.map_effect_id`; the board renders **map-effect tiles** + the boss at its `spawn_position`; raw `Piece`/board never escape `src/game/` (V.1).
11. LIVING docs updated; `/check` passes.

## 10. SPEC changes needed (for `/spec`)

**§T — amend the existing `T.12b` row** (no new row):
- **Goal-line:** keep "boss support (promote `resolve_boss_combat` `tools/`→`src/game/combat/resolve.py` + map-effect-aware `inspect_at_tick`/`CombatReplay` + map-effect board overlay + harness BOSS node)"; expand "polish" → "token movement tween, attack/cast **target arrows**, **tickwise DOT reveal** (manual+autoplay), **sudden-death indicator**, status-icon row, real-time-scaled autoplay pacing".
- **Files:** add `docs/design/tasks/t12b_combat_view_polish_plan.md`, `tests/ui/test_combat_playback.py`, `docs/live/systems/ui.md`. Status stays `📋 Plan`.
- Optional: note the **A/B build phases** under §T Planning Notes.

**§V — amend V.54 (true-damage DOT now emits a beat):**
- Add: HP-changing beats now include **every status-DOT tick regardless of `damage_type`** — `_on_damage_dealt` emits a `dot` beat when `tag == DOT` **or** `DamageEvent.is_dot` (set by `process_statuses`), so **`dot_true_damage` statuses (`sudden_death`) become visible** (they were silent — `SourceTag.TRUE` produced no beat). Still observer-only; `turns` excludes `dot` ⇒ byte-identical (V.2). The combat view absorbs these into `pre_beats` (a drip "between actions"), never a standalone step.

**§V — one new invariant (boss single-entry promotion):**
- **V.x:** *The boss combat path resolves through `src/game/combat/resolve.py::resolve_boss_combat`* — the **single src-side** boss entry (build_combat → `attach_map_effect(map_effect_id)` → run → result). It takes a **`map_effect_id: str`** (never a `bosses/`-content type, so `combat/` stays content-import-free, V.1) and is **byte-identical** to the former `tools/playtest/_common` version (V.2); `tools/` now delegates to it. `CombatReplay`/`inspect_at_tick` accept the same `map_effect_id` and replay the boss fight identically (V.55). The combat view reaches it **only** via `src/game/combat/` (V.1 — UI never imports `tools/`). (T.12b)

**§B:** none (no bug; if the promotion surfaces a drift, backprop then).

**§D:** D.16 — `/combat` now also renders boss nodes (dev-launched ahead of T.15).

**Implementation Order:** unchanged (`… T.37c → T.12a → T.12b`); build **T.12b-A then T.12b-B** (independent; A is lower-risk).

## 11. LIVING docs to update
- **`docs/live/systems/ui.md`** — animation layer (token tween, arrows, tickwise DOT reveal + autoplay, sudden-death cue, status pips, autoplay pacing); `CombatSession.map_effect_id` + boss path + map-effect overlay.
- **`docs/live/systems/combat.md`** — `resolve_boss_combat` now in `combat/resolve.py` (the boss single-entry); `CombatReplay`/`inspect_at_tick` `map_effect_id`; `board_cells()` read accessor. Update the file-map + the boss/`build_combat` reuse note.
- **`ARCHITECTURE.md`** §3.1/§11 — boss path src-side; combat view boss render. FROZEN docs (`views_spec.md`) untouched.
