# T12 Plan — Combat View (+ dev harness launcher)

> **Status:** plan — ready for review. (**Status flip + split**: the existing single §T.12 row becomes **T.12a / T.12b**; needs `/spec`.)
> **Depends:** T.3 (combat engine — done), T.8 (theme + components — done), **T.37 (replay backend — done)**. The formal SPEC deps are all met. The *UI-shell* tasks that would normally precede it — **T.9 (menu), T.10 (run-start), T.15 (routing), T.23 (prep)** — are all **unbuilt (📋 Plan)**; rather than gate on them, T.12 ships behind a **dev harness launcher** (this plan) and is later fed by the real Prep/Trail flow with **zero view changes**.
> **Resolves:** the `/combat` view (SPEC §I route, views_spec §7); first real game UI view.
> **Design source of truth:** [`views_spec.md` §7](../systems/views_spec.md) (layout zones, telemetry 7.4, action queue 7.5, end 7.6, states 7.7) + §8 (view-model contracts), [`combat_system_proposal.md`](../systems/combat_system_proposal.md). LIVING: [`docs/live/systems/combat.md`](../../live/systems/combat.md) (replay/event-stream API).
> **What this plan adds beyond those:** the **interaction model** (default = manual event-step, TFT-feel read-only inspection), the **`CombatSession` contract** (one input bundle the harness builds now and the stage view builds later), the **pure `combat_playback` model** (Flet-free, testable — frames + 2-round action-queue projection), the dev harness, and the standalone `main.py` dev entry.

---

## Interaction model (the spine — read first)

**Reference: TFT.** The game is, mechanically, a **turn-based hex-gridded TFT** — so TFT is the explicit UX/visual reference for this view: a hex board of unit tokens with HP/mana bars, hover/click to inspect a unit's stats + items + traits, a synergy/trait readout, floating combat numbers. The one deliberate divergence: TFT auto-battles in real time; **ours is turn-based** — the player advances the resolved fight **event-by-event** (each event = one advanceable "turn"), which is what makes it inspectable.

The combat view is **interactive but read-only** — it should *feel like playing* (TFT-style), not like watching a video:

- **Default mode = manual event-step.** The player presses **Next** to advance the sim to the next action; each event plays a small animation and all meters/positions/statuses update to that event's state. Nothing auto-advances unless the player turns on autoplay.
- **Autoplay = optional secondary mode.** A toggle paces events automatically (a comfortable per-event interval; *optionally* scaled by the inter-event tick gap for a roughly real-time feel — T.12b). The animation is **event-paced, not tick=second real-time**; ticks↔seconds (V.39) is only used to render *durations as text* (status remaining, cadences) in inspect panels — never to drive playback timing.
- **Hex map is the main surface** — pieces at their board coords; the whole experience centres on it.
- **Inspection** — click any piece to read its live stats, equipped items, and traits; a global panel shows the team's active augments + cleared traits. Read-only.
- **Action queue (top)** — projects the **next 2 full rounds** of upcoming actions; entries are **moves + attacks/casts** (moves rendered **smaller + clearly movement-iconed**, attacks/casts the primary larger entries); a **round split marker** divides rounds; when a round completes, the next round is appended so 2 rounds are always visible ahead.

## 0. Substep split (`T.12a → T.12b`)

Real seam: **the playable, inspectable fight (core)** vs **boss + presentation polish**.

- **T.12a — Combat view core + dev harness.** Hex board with pieces at coords; **manual event-step** playback (default) + optional fixed-interval autoplay + fast-forward; per-event animations; live HP/mana bars; floating damage/heal numbers; death/despawn; **action-queue with 2-round projection + round markers**; **click-to-inspect** (piece stats via `inspect_at_tick`, equipped items, traits; global augments/traits); combat-end panel. Plus the **dev-harness launcher** (team / node-type / enemies / weather / augments / items → `CombatSession`) and a minimal `main.py` dev entry. **Node types: FIGHT, CHALLENGE, REWARD** — all are combats (REWARD = an easy fight); we build only the combat, not any post-combat/loot screen. **Done when:** `uv run flet run` (dev flag) → harness → a fight you step through action-by-action on the hex map, inspecting pieces/items/augments/traits, with the action queue showing the next 2 rounds.
- **T.12b — Boss + polish.** Boss support (promote `resolve_boss_combat` `tools/`→`src/game/combat/resolve.py` + boss-aware `inspect_at_tick` + map-effect overlay); real-time-scaled autoplay pacing; status-icon detail row; keyboard shortcuts (`Enter`/`Esc`/→); tick-by-tick admin mode; sprite art (tokens are affinity-tinted circles + initials until then). **Done when:** boss nodes render with map effects and the polish layer is in.

## 1. Scope

**In scope (a):** `ui/views/combat.py` (the view), `ui/views/dev_harness.py` (launcher), `ui/combat_playback.py` (pure Flet-free model: per-event frames + action-queue projection — testable), `main.py` dev entry + minimal harness↔combat nav, `docs/live/systems/ui.md` (new LIVING doc), tests for the pure model.

**In scope (b):** boss path, real-time autoplay pacing, status icons, keyboard, tick mode, sprites.

**Out of scope (why):**
- **Real routing / menu / trail / prep (T.9/T.10/T.15/T.23)** — the harness is the throwaway producer; the real flow lands in those tasks and reuses the **same** `CombatSession` + view unchanged.
- **Persisting node resolution to a `Run`** — the harness runs one-off scenarios; "Continue" returns to the harness (no `Run` yet). views_spec §7.6 "commit node resolution" is a Trail concern (T.15).
- **New game logic** — the view is **pure presentation** over `resolve_combat` + `inspect_at_tick`; zero combat math (V.1/V.2 preserved).

## 2. The gap today

| Piece | Where (`file.py:line`) | State |
|---|---|---|
| Replay backend (event stream + `hp_after`/`barrier_after` + `initial_pieces` + board dims) | `game/models.py`, `game/combat/recorder.py` | ✅ (T.37a) |
| `inspect_at_tick` + `PieceView` (live stats/mana/statuses/pos at a tick) | `game/combat/replay.py` | ✅ (T.37b) |
| `group_events_by_tick` (per-tick beat grouping) | `game/combat_log.py:19` | ✅ |
| `ROUND_TICKS = 600` (round length for queue markers) | `game/combat/recorder.py` | ✅ |
| `resolve_combat(team, enemies, weather, *, node_id, run_mods)` | `game/combat/resolve.py:19` | ✅ |
| Non-boss encounter gen `generate_fight`, `generate_challenge`, reward `generate_reward_loot` | `game/encounter.py:454/778/521` | ✅ |
| `default_team`, roster lookups, `STAGES`/`stage_of`, `AUGMENT_REGISTRY`/`ITEM_REGISTRY` | `tools/playtest/_common.py`, `game/content.py`, `game/route.py`, `game/registries.py:27/38` | ✅ |
| Champion carries `items`/`traits`; `BattleResult.trait_activations` | `game/models.py` | ✅ |
| `meter_bar`, `champion_card`, `weather_badge`, chips; theme (`AFFINITY_COLORS`, `ANIM_COMBAT_TICK`) | `ui/components/`, `ui/theme.py` | ✅ (T.8) |
| `TICKS_PER_SECOND=100` (ticks→sec for displayed durations) | `game/ability_text.py:32` | ✅ (V.39) |
| Combat view / dev harness / pure playback model | `ui/views/combat.py`, `ui/views/dev_harness.py`, `ui/combat_playback.py` | ❌ |
| App shell / routing | `main.py` (placeholder counter + admin) | 🔴 stub |
| `resolve_boss_combat` reachable from UI | `tools/playtest/_common.py:108` (UI can't import `tools/`) | 🔴 (T.12b promotes to src) |
| LIVING UI doc | `docs/live/systems/ui.md` | ❌ |

## 3. Architecture

### 3.1 The reusable seam — `CombatSession`

One input bundle (plain game models — Flet-free), the view's only input:

```
@dataclass(frozen=True)
class CombatSession:
    team: list[Champion]          # carry their items + traits
    enemies: list[Enemy]
    weather: WeatherState
    run_mods: RunModifiers | None = None   # active augments
    node_id: str = ""
    # (T.12b) map_effect_id for boss fights
```

The view **owns resolution**: on open it calls `resolve_combat(session…) -> BattleResult`, and `inspect_at_tick(session…, tick)` for inspection. It takes the *inputs* (not a pre-resolved result) because `inspect_at_tick` re-runs from them (V.55). **Two producers, one session:** the dev harness builds it from selectors now; the future Prep/Trail `Start Combat` builds the identical object → same view, no change. (views_spec §8 `CombatStartViewModel`.)

### 3.2 Pure playback model (`ui/combat_playback.py`, Flet-free → testable)

No UI tests in this repo (CLAUDE.md) → the animation *logic* is a pure function of `BattleResult`, rendered by the Flet view:

```
build_playback(result) -> Playback
  Playback.steps: list[Step]                # one per event-bearing tick (group_events_by_tick)
    Step.tick, Step.round (tick // ROUND_TICKS), Step.beats: list[BattleEvent]
    Step.board: dict[id -> PieceFrame(q, r, hp, max_hp, barrier, alive)]
      # initial_pieces + walk events: hp_after/barrier_after (V.54), move positions,
      # spawn/despawn — reads recorded truth, NO re-sim.
  Playback.queue(cursor) -> list[QueueEntry]  # upcoming move/attack/cast beats (kind flagged so
                                               # the view renders moves smaller + movement-iconed),
                                               # current + next 2 rounds, round split markers; slides
                                               # forward as the cursor crosses a round boundary.
```

- **Bars** read `PieceFrame.hp/barrier` (exact, from `hp_after`). Mana in T.12a from cast-event `mana_after` + linear fill between (exact mana available on demand via `inspect_at_tick`).
- **Action queue** is pure derivation: the fight is fully resolved, so future `attack`/`cast`/`move` beats are known — group them by round (`ROUND_TICKS`), expose current + 2 future rounds with markers.
- Pure, deterministic, unit-tested without Flet.

### 3.3 The Flet view (`ui/views/combat.py`)

`build_combat_view(page, session, on_exit)`. Zones (views_spec §7.3):
- **Top — action queue:** horizontal timeline of upcoming actors (portrait/initial + affinity tint), **2 full rounds projected**, **round split markers**, scrolls/appends as rounds complete (from `Playback.queue(cursor)`). Entries are **moves + attacks/casts**: attacks/casts are the primary (larger) entries, **moves are smaller + carry a movement icon**.
- **Center — hex board:** `flet.canvas` (CLAUDE.md hex convention), 10×7 (`BOARD_WIDTH`×`BOARD_HEIGHT`); per living piece a token (`cv.Circle` tinted `AFFINITY_COLORS[affinity]` + initial) at its `(q,r)`, with `meter_bar` HP (+ mana) beneath; cells behind, tokens on top. **Clickable** (manual hit-test → select piece).
- **Per-event animation:** on each step, attack/cast → token nudge + red number on target; heal → green; dot → red tick; death → fade/✕; despawn → fade (distinct, V.54); meters update to the step's frame.
- **Side panel — inspect (read-only):** selected piece → live stats (`inspect_at_tick` at cursor tick, incl. STR/AS ramp), **equipped items** (`champion.items`), **traits** (`champion.traits` + cleared `result.trait_activations`); a global sub-panel shows **active augments** (`session.run_mods.augments`). Combat-log feed beneath.
- **Bottom controls:** **Next ▶ (default, manual step)**, Prev ◀, Autoplay toggle, Fast-forward, restart.
- **Combat-end panel (§7.6):** outcome / survivors / damage dealt-taken / `Continue` (→ `on_exit`).

**Playback driver:** manual step mutates a cursor int + re-renders (no thread). Autoplay uses a `threading.Thread` that advances the cursor on a fixed interval and calls `page.update()` — never blocks main; stopped on view exit / toggle-off (no touching disposed controls). Displayed durations → seconds via `TICKS_PER_SECOND` (V.39).

### 3.4 Dev harness (`ui/views/dev_harness.py`)

GUI wrapper of the `sim_node` inputs (`tools/playtest/sim_node.py` is the headless reference):
- **Node type** — FIGHT / CHALLENGE / REWARD selector + stage + `node_index` + `dc`. **All three are combats** (we build only the combat, not any post-combat/loot screen):
  - FIGHT → `generate_fight(run_seed, node_index, stage, dc)`.
  - REWARD → **an easy fight** (a `generate_fight`-equivalent at the reward node-type budget / lower `dc`); the loot grant is post-combat → out of scope.
  - CHALLENGE → `generate_challenge(...)`.
  - All → enemy squad → combat view.
- **Team** — multiselect from `CHAMPION_ROSTER` (or `default_team(stage)`), tier/level; optional **items** per champion (`ITEM_REGISTRY` ids).
- **Weather** — `WeatherState` picker (default = stage/city default).
- **Augments** — multiselect from `AUGMENT_REGISTRY` → `RunModifiers`.
- **Run** → assemble `CombatSession` → open combat view (all three node types).

### 3.5 App shell (`main.py`)

Minimal, **not** T.15: dev entry behind `TEMPEST_DEV=1` (mirrors `TEMPEST_ADMIN`) → harness; tiny `page.views` push/pop harness↔combat. Existing counter/admin entries untouched.

### 3.6 Invariant posture
- **V.1** — `ui/` imports `game/`, never the reverse; no `game/` logic added. Boss wrinkle (`resolve_boss_combat` in `tools/`) fixed in T.12b by promoting to `src/game/combat/resolve.py`.
- **V.2/V.55** — view calls `resolve_combat`/`inspect_at_tick` (pure, deterministic); never re-implements combat. Same session → same fight.
- **V.39** — ticks in the model; seconds only at rendered duration text — **not** playback timing.
- **V.54** — bars/beats read the recorded stream (`hp_after`/`barrier_after`), never a re-sim.

## 4. Decisions
- **§4.1 Default = manual event-step; autoplay is opt-in, event-paced (not tick=second).** Matches the TFT "you're playing" feel. *Firm (user-set).*
- **§4.2 View takes `CombatSession` (inputs), resolves internally.** Needed for `inspect_at_tick`; keeps harness/stage producers symmetric. *Firm (V.55).*
- **§4.3 Pure Flet-free `combat_playback` (frames + queue projection).** The test surface; thin Flet renderer. *Firm.*
- **§4.4 Action queue + inspect (items/augments/traits) are CORE (T.12a), not polish.** Per the interaction model. *Firm (user-set).*
- **§4.5 All node types (FIGHT/CHALLENGE/REWARD) → combat; REWARD = an easy fight.** Post-combat/loot grant is out of scope (combat only). *Overridable.*
- **§4.6 Boss in T.12b** (needs the `tools/`→`src/` promotion + boss-aware inspect). *Overridable.*
- **§4.7 Dev entry `TEMPEST_DEV=1`, minimal nav — not T.15.** *Overridable.*

## 5. Authored values
No game numbers (presentation only). Reuse `ui/theme.py`. Autoplay interval first-pass `≈ 600–900 ms`/event (tunable); fast-forward = no delay. Action queue window = current + **2** rounds (`ROUND_TICKS=600`).

## 6. Content / roster audit + reconciliation
None (no rosters/tags touched). Doc-drift: no `docs/live/systems/ui.md` exists yet (flet-ui.md expects one as the UI solidifies) — T.12a creates it. views_spec stays FROZEN.

## 7. Open questions
**Resolved here (overridable):** §4.5 (reward = easy fight, combat only), §4.6 (boss in b), §4.7 (dev entry). Board = `flet.canvas` hex.
**Still open / deferred:** action-queue projection granularity (which beats count as "actions" — proposal: `attack`/`cast` are queue entries; `move`/`dot`/`status` are not — refine in build); real-time-scaled autoplay pacing (T.12b); sprite art; keyboard shortcuts (T.12b).

## 8. Test plan
UI not unit-tested (CLAUDE.md) → target the **pure `combat_playback`** model:
- `build_playback(result)`: one step per event-bearing tick; steps cover every `BattleEvent`; `Step.round == tick // ROUND_TICKS`.
- **Board fidelity:** each `PieceFrame.hp` equals engine truth — cross-check vs `inspect_at_tick(...).hp` at that step's tick on a sample fight, **incl. a barrier case** (frame hp ≠ Σdamage, V.54).
- **Action queue:** `queue(cursor)` returns current + ≤2 future rounds, round-split markers correct; window slides + appends as the cursor crosses a `ROUND_TICKS` boundary; entries are the chosen action beats in resolved order.
- Spawn/despawn: summon appears at spawn step, gone after despawn (not a lingering corpse).
- Determinism: same `CombatSession` → identical `Playback` (pure; no view-layer RNG).
- No Flet import in `combat_playback` (import it in a test with no display).
- (T.12b) `resolve_boss_combat` promoted to src is byte-identical to the `tools/` version (sims unchanged).

## 9. Acceptance criteria
**T.12a**
1. `uv run flet run` (dev flag) → harness; node-type (FIGHT/CHALLENGE/REWARD, all combats) + team + enemies + weather + augments + items selectable; "Run" opens the combat view (REWARD = easy fight).
2. Hex board shows pieces at their coords; **Next** steps the fight one action at a time (default), each event animates and updates all meters/positions/statuses; autoplay + fast-forward also work.
3. **Action queue** (top) projects the next **2 full rounds** with round split markers, appending as rounds complete.
4. **Click-to-inspect** a piece shows live stats (`inspect_at_tick`, incl. STR ramp) + equipped items + traits; a global panel shows active augments + cleared traits. Read-only.
5. Combat-end panel (outcome/survivors/damage); `Continue` → harness.
6. `combat_playback` is pure, Flet-free, tested; `game/` has zero `ui/` imports (V.1); displayed durations are seconds (V.39).
7. `docs/live/systems/ui.md` created; `/check` passes.

**T.12b**
8. Boss nodes render with map effects; `resolve_boss_combat` lives in `src/game/combat/resolve.py` (UI imports src, not `tools/`); sims byte-identical; boss-aware `inspect_at_tick`.
9. Real-time-scaled autoplay pacing, status-icon row, keyboard shortcuts, tick-by-tick admin mode.

## 10. SPEC changes needed (for `/spec`)

**§T — replace T.12 with two rows:**
- `T.12a | Combat view core + dev harness — flet.canvas hex board (10×7), pieces at coords, DEFAULT manual event-step playback (+ optional autoplay/fast-fwd) over the T.37 stream, per-event animations + live HP/mana bars + floating damage/heal numbers + death/despawn; action-queue with 2-round projection + round markers (entries = moves + attacks/casts; moves smaller + movement-iconed); click-to-inspect (live stats via inspect_at_tick + equipped items + traits; global active augments); combat-end panel; dev-harness launcher (FIGHT/CHALLENGE/REWARD all combats, REWARD = easy fight + team/weather/augments/items → CombatSession) + minimal main.py dev entry; pure Flet-free combat_playback model (frames + queue projection, tested) | ui/views/combat.py, ui/views/dev_harness.py, ui/combat_playback.py, main.py, docs/live/systems/ui.md, tests/ui/test_combat_playback.py, docs/design/tasks/t12_combat_view_plan.md | T.3, T.8, T.37 | L | 📋 Plan`
- `T.12b | Combat view boss + polish — boss support (promote resolve_boss_combat tools→src/game/combat/resolve.py + boss-aware inspect_at_tick + map-effect overlay), real-time-scaled autoplay pacing, status-icon row, keyboard shortcuts, tick-by-tick admin mode, sprites | ui/views/combat.py, ui/combat_playback.py, game/combat/resolve.py, game/combat/replay.py, tools/playtest/_common.py, tests/ | T.12a | M | 📋 Plan`

**§V — new invariant:**
- **V.x (combat view is pure presentation over the replay backend):** `ui/views/combat.py` renders a fight **only** through `resolve_combat` + `inspect_at_tick` + the recorded `BattleResult` stream — **no** combat math (extends V.1: `ui/`→`game/` only, never the reverse). It is **interactive but read-only** and is fed one **`CombatSession`** bundle, built identically by the dev harness (now) and Prep/Trail (later) — one view, swappable producers. Playback is **event-paced** (default manual step), **not** tick=second real-time; `TICKS_PER_SECOND` (V.39) renders *durations as text* only. Board/bars/queue read the recorded stream (`hp_after`/`barrier_after`/move beats, round = `ROUND_TICKS`), not a re-sim; the boss path resolves through `src/game/combat/` (never `tools/`). (T.12)

**§D:** D.16 (routes) — note `/combat` now has a real view, dev-launched ahead of T.15.

**Implementation Order:** `… T.37a → T.37b → T.12a → T.12b` (no longer waits on T.9/T.10/T.15/T.23 — the harness substitutes for the shell; those tasks later swap their `Start Combat` producer onto the same `CombatSession`).

## 11. LIVING docs to update
- **Create `docs/live/systems/ui.md`** (first UI LIVING doc): `CombatSession` contract, `combat_playback` model (frames + queue), combat-view zones + interaction model (manual step default, inspection), dev harness, `main.py` dev entry. `/check` must pass.
- Append to [`docs/live/systems/combat.md`](../../live/systems/combat.md): one-line pointer that the combat view consumes the replay/event-stream API (no logic added).
- `ARCHITECTURE.md` §11 (UI layer): add the combat view + harness + `CombatSession` seam. FROZEN docs (`views_spec.md`) untouched.
