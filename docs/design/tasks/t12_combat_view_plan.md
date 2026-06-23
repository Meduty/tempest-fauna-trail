# T12 Plan — Combat View (+ dev harness launcher)

> **Status:** plan — ready for review. (**Status flip + split**: the existing single §T.12 row becomes **T.12a / T.12b**; needs `/spec`. **Refreshed 2026-06-22** for the now-built **T.37c forward `CombatReplay` stepper** — §3.2/§3.3/§3.6/§8 rewritten: bars read the **live stepper**, the recorded stream is **animation cues + action-queue projection only**, per **B.28 + V.55/V.56/V.57**.)
> **Depends:** T.3 (combat engine — done), T.8 (theme + components — done), **T.37a/b (replay backend — done)**, **T.37c (forward `CombatReplay` stepper — ✅ done, commit `aef5d33`)**. The formal SPEC deps are all met. The *UI-shell* tasks that would normally precede it — **T.9 (menu), T.10 (run-start), T.15 (routing), T.23 (prep)** — are all **unbuilt (📋 Plan)**; rather than gate on them, T.12 ships behind a **dev harness launcher** (this plan) and is later fed by the real Prep/Trail flow with **zero view changes**.
> **Resolves:** the `/combat` view (SPEC §I route, views_spec §7); first real game UI view.
> **Design source of truth:** [`views_spec.md` §7](../systems/views_spec.md) (layout zones, telemetry 7.4, action queue 7.5, end 7.6, states 7.7) + §8 (view-model contracts), [`combat_system_proposal.md`](../systems/combat_system_proposal.md). LIVING: [`docs/live/systems/combat.md`](../../live/systems/combat.md) (replay/event-stream API).
> **What this plan adds beyond those:** the **interaction model** (default = manual event-step, TFT-feel read-only inspection), the **`CombatSession` contract** (one input bundle the harness builds now and the stage view builds later), the **pure `combat_playback` model** (Flet-free, testable — **animation-cue steps + 2-round action-queue projection** derived from the recorded event stream; **resource numbers come from the live `CombatReplay` stepper, not the stream**), the dev harness, and the standalone `main.py` dev entry.

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

- **T.12a — Combat view core + dev harness.** Hex board with pieces at coords; **manual event-step** playback (default) + optional fixed-interval autoplay + fast-forward, **driving the forward `CombatReplay` stepper** for live HP/mana/stat/position truth (V.57); per-event animations; floating damage/heal numbers; death/despawn; **action-queue with 2-round projection + round markers** (derived from the recorded stream); **click-to-inspect** (piece stats via the stepper / `inspect_at_tick`, equipped items, traits; global augments/traits); combat-end panel. Plus the **dev-harness launcher** (team / node-type / enemies / weather / augments / items → `CombatSession`) and a minimal `main.py` dev entry. **Node types: FIGHT, CHALLENGE, REWARD** — all are combats (REWARD = an easy fight); we build only the combat, not any post-combat/loot screen. **Done when:** `uv run flet run` (dev flag) → harness → a fight you step through action-by-action on the hex map (bars move correctly through ability bursts), inspecting pieces/items/augments/traits, with the action queue showing the next 2 rounds.
- **T.12b — Boss + polish.** Boss support (promote `resolve_boss_combat` `tools/`→`src/game/combat/resolve.py` + boss-aware `inspect_at_tick` + map-effect overlay); real-time-scaled autoplay pacing; status-icon detail row; keyboard shortcuts (`Enter`/`Esc`/→); tick-by-tick admin mode; sprite art (tokens are affinity-tinted circles + initials until then). **Done when:** boss nodes render with map effects and the polish layer is in.

## 1. Scope

**In scope (a):** `ui/views/combat.py` (the view), `ui/views/dev_harness.py` (launcher), `ui/combat_playback.py` (pure Flet-free model: **animation-cue steps + action-queue projection derived from the recorded stream** — testable; **no resource reconstruction**), `main.py` dev entry + minimal harness↔combat nav, `docs/live/systems/ui.md` (new LIVING doc), tests for the pure model.

**In scope (b):** boss path, real-time autoplay pacing, status icons, keyboard, tick mode, sprites.

**Out of scope (why):**
- **Real routing / menu / trail / prep (T.9/T.10/T.15/T.23)** — the harness is the throwaway producer; the real flow lands in those tasks and reuses the **same** `CombatSession` + view unchanged.
- **Persisting node resolution to a `Run`** — the harness runs one-off scenarios; "Continue" returns to the harness (no `Run` yet). views_spec §7.6 "commit node resolution" is a Trail concern (T.15).
- **New game logic** — the view is **pure presentation** over `resolve_combat` + `CombatReplay` + `inspect_at_tick`; zero combat math (V.1/V.2/V.56 preserved).

## 2. The gap today

| Piece | Where (`file.py:line`) | State |
|---|---|---|
| Replay backend (event stream + `hp_after`/`barrier_after` + `initial_pieces` + board dims; `move`/`spawn` `dest_q`/`dest_r`) | `game/models.py`, `game/combat/recorder.py` | ✅ (T.37a, T.37c) |
| **Forward `CombatReplay` stepper** (`.step_to(tick)` → live `PieceView`s; the bar/board resource source, V.57) | `game/combat/replay.py` | ✅ (T.37c) |
| `inspect_at_tick` + `PieceView` (live stats/mana/statuses/pos at a tick; random seek / click) | `game/combat/replay.py` | ✅ (T.37b, on `CombatReplay` since T.37c) |
| `group_events_by_tick` (per-tick beat grouping → animation-cue steps) | `game/combat_log.py:19` | ✅ |
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

The view **owns resolution**: on open it calls `resolve_combat(session…) -> BattleResult` **once** (for the animation-cue stream + action-queue projection), and builds **one `CombatReplay(session…)`** that it drives **forward** for live resource state (HP/mana/stats/positions); `inspect_at_tick(session…, tick)` is used only for click-inspect at an arbitrary tick / backward scrub (V.55/V.57). It takes the *inputs* (not a pre-resolved result) because the stepper + inspect re-run from them. **Two producers, one session:** the dev harness builds it from selectors now; the future Prep/Trail `Start Combat` builds the identical object → same view, no change. (views_spec §8 `CombatStartViewModel`.)

### 3.2 Pure playback model (`ui/combat_playback.py`, Flet-free → testable)

No UI tests in this repo (CLAUDE.md) → the *cue + queue* logic is a pure function of `BattleResult`, rendered by the Flet view. **Critically: this model carries NO resource numbers** (hp/mana/barrier). Those come from the live `CombatReplay` stepper at render time (V.57) — the recorded stream is **incomplete** for them (registered-ability burst emits no `hp_after`, B.28). The model only answers *which tick to stop at, what to animate there, and what's coming up*:

```
build_playback(result) -> Playback
  Playback.steps: list[Step]                # one per event-bearing tick (group_events_by_tick)
    Step.tick, Step.round (tick // ROUND_TICKS), Step.beats: list[BattleEvent]
      # the ANIMATION CUES for this tick: attack/cast → nudge + number; heal → green;
      # dot → red tick; death → fade/✕; despawn → fade; move → (dest_q,dest_r) glide.
      # `amount`/`is_crit` drive the floating-number magnitude; NO hp/mana state here.
  Playback.queue(cursor) -> list[QueueEntry]  # upcoming move/attack/cast beats (kind flagged so
                                               # the view renders moves smaller + movement-iconed),
                                               # current + next 2 rounds, round split markers; slides
                                               # forward as the cursor crosses a round boundary.
```

- **Resource state is NOT in `Playback`.** The view holds a `CombatReplay`, calls `replay.step_to(step.tick)` for the cursor's step, and reads live `PieceView`s — HP/barrier/per-slot mana/effective stats/`(q,r)` — straight off them (complete + exact, incl. ability burst). Floating *numbers* on a hit come from the beat's `amount`; the *bar* it lands on comes from the stepped `PieceView.hp` (V.57). One forward drive over the fight ⇒ O(total ticks).
- **Board positions** also come from the stepped `PieceView` (`q`,`r`, `alive`, summon spawn/despawn reflected live); the `move` beat is just the glide *cue* (its `dest_q`/`dest_r` give the animation target, T.37c).
- **Action queue** is pure derivation over the stream: the fight is fully resolved, so future `attack`/`cast`/`move` beats are known — group by round (`ROUND_TICKS`), expose current + 2 future rounds with markers. (This *is* stream-only — it's structure, not resource numbers.)
- The model is pure, deterministic, unit-tested without Flet; the **resource fidelity** is already guaranteed + tested by T.37c (`CombatReplay` == `inspect_at_tick`), so this layer needs no HP assertions.

### 3.3 The Flet view (`ui/views/combat.py`)

`build_combat_view(page, session, on_exit)`. Zones (views_spec §7.3):
- **Top — action queue:** horizontal timeline of upcoming actors (portrait/initial + affinity tint), **2 full rounds projected**, **round split markers**, scrolls/appends as rounds complete (from `Playback.queue(cursor)`). Entries are **moves + attacks/casts**: attacks/casts are the primary (larger) entries, **moves are smaller + carry a movement icon**.
- **Center — hex board:** `flet.canvas` (CLAUDE.md hex convention), 10×7 (`BOARD_WIDTH`×`BOARD_HEIGHT`); per living piece a token (`cv.Circle` tinted `AFFINITY_COLORS[affinity]` + initial) at its **stepped `PieceView.(q,r)`**, with `meter_bar` HP (+ mana) read from the **stepped `PieceView.hp`/`barrier_total`/per-slot `mana`** beneath; cells behind, tokens on top. **Clickable** (manual hit-test → select piece).
- **Per-event animation:** on each step, the step's *beats* are the cues — attack/cast → token nudge + red number (`beat.amount`) on target; heal → green; dot → red tick; death → fade/✕; despawn → fade (distinct); move → glide to `(dest_q,dest_r)`. The **bars then snap to the stepped `PieceView`** (resource truth, V.57) — *not* to a stream-reconstructed frame.
- **Side panel — inspect (read-only):** selected piece → live stats from the stepper at the cursor tick (or `inspect_at_tick` for an off-cursor scrub), incl. STR/AS ramp; **equipped items** (`champion.items`), **traits** (`champion.traits` + cleared `result.trait_activations`); a global sub-panel shows **active augments** (`session.run_mods.augments`). Combat-log feed beneath.
- **Bottom controls:** **Next ▶ (default, manual step)**, Prev ◀, Autoplay toggle, Fast-forward, restart.
- **Combat-end panel (§7.6):** outcome / survivors / damage dealt-taken / `Continue` (→ `on_exit`).

**Playback driver:** the view holds the cursor (an index into `Playback.steps`) **and one `CombatReplay`**. Forward step (Next/autoplay): `cursor += 1`, `replay.step_to(steps[cursor].tick)`, render cues + read live `PieceView`s, `page.update()`. **Backward (Prev) / restart:** `CombatReplay` is forward-only — rebuild a fresh `CombatReplay` from the session (cheap; O(target tick)) **or** fall back to `inspect_at_tick(target)` for the bars (decision §4.8). Autoplay uses a `threading.Thread` advancing the cursor on a fixed interval + `page.update()` — never blocks main; stopped on view exit / toggle-off (no touching disposed controls). Displayed durations → seconds via `TICKS_PER_SECOND` (V.39); playback pacing is event-paced, never tick=second (V.56).

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
- **V.2/V.55** — view calls `resolve_combat` + the `CombatReplay` stepper + `inspect_at_tick` (all pure, deterministic); never re-implements combat. Same session → same fight.
- **V.56/V.57** — **resource truth (HP/mana/stats/position) comes from the live replay, NOT the event stream.** The recorded stream supplies animation cues + the action-queue projection only; its `hp_after`/`mana_after` are telemetry, not the bar source (incomplete for ability burst, B.28). Playback is event-paced, not tick=second.
- **V.39** — ticks in the model; seconds only at rendered duration text — **not** playback timing.

## 4. Decisions
- **§4.1 Default = manual event-step; autoplay is opt-in, event-paced (not tick=second).** Matches the TFT "you're playing" feel. *Firm (user-set).*
- **§4.2 View takes `CombatSession` (inputs), resolves internally.** Needed for `inspect_at_tick`; keeps harness/stage producers symmetric. *Firm (V.55).*
- **§4.3 Pure Flet-free `combat_playback` = animation cues + queue projection ONLY (no resource numbers).** Resource truth (HP/mana/stats/pos) is read live off the `CombatReplay` stepper at render time (V.57); the model never reconstructs HP from the stream (incomplete, B.28). The test surface; thin Flet renderer. *Firm (V.56/V.57, T.37c).*
- **§4.4 Action queue + inspect (items/augments/traits) are CORE (T.12a), not polish.** Per the interaction model. *Firm (user-set).*
- **§4.5 All node types (FIGHT/CHALLENGE/REWARD) → combat; REWARD = an easy fight.** Post-combat/loot grant is out of scope (combat only). *Overridable.*
- **§4.6 Boss in T.12b** (needs the `tools/`→`src/` promotion + boss-aware inspect). *Overridable.*
- **§4.7 Dev entry `TEMPEST_DEV=1`, minimal nav — not T.15.** *Overridable.*
- **§4.8 Backward step / restart = rebuild a fresh `CombatReplay` from the session (forward-only stepper) and drive to the target tick; bars read it (or `inspect_at_tick` for a one-off scrub).** Rebuild is O(target tick) on short fights — cheap; no keyframe cache needed (matches T.37c §4.3 deferral). Forward Next/autoplay reuses the one held stepper. *Proposal, overridable.*

## 5. Authored values
No game numbers (presentation only). Reuse `ui/theme.py`. Autoplay interval first-pass `≈ 600–900 ms`/event (tunable); fast-forward = no delay. Action queue window = current + **2** rounds (`ROUND_TICKS=600`).

## 6. Content / roster audit + reconciliation
None (no rosters/tags touched). Doc-drift: no `docs/live/systems/ui.md` exists yet (flet-ui.md expects one as the UI solidifies) — T.12a creates it. views_spec stays FROZEN.

## 7. Open questions
**Resolved here (overridable):** §4.3 (`combat_playback` = cues + queue, no resource numbers — bars from the stepper), §4.5 (reward = easy fight, combat only), §4.6 (boss in b), §4.7 (dev entry), §4.8 (backward/restart = rebuild a fresh `CombatReplay`). Board = `flet.canvas` hex.
**Still open / deferred:** action-queue projection granularity (which beats count as "actions" — proposal: `attack`/`cast` are queue entries; `move`/`dot`/`status` are not — refine in build); mana display via stepper per-slot `PieceView.mana` (live, exact — no linear fill needed now the stepper is the source); real-time-scaled autoplay pacing (T.12b); sprite art; keyboard shortcuts (T.12b).

### 7.1 Design research findings (TFT + JRPG + Flet) — 2026-06-23

Web research into TFT board UX, turn-based JRPG combat presentation, and Flet
game-dev patterns. Sources: [TFT UI case study (Z. Roberson)](https://zacharyrobes.com/teamfight-tactics-ui-design),
[TFT UI tools (esports.gg)](https://esports.gg/guides/teamfight-tactics/tft-tip-tuesday-how-to-utilize-the-ui-tools/),
[Damage Numbers in RPGs (Shweep)](https://shweep.medium.com/damage-numbers-in-rpgs-1f0e3b1bc23a),
[JRPG combat system (S. Hargain)](https://medium.com/@seanhargain055/building-a-jrpg-combat-system-without-losing-the-thread-3c6a1ee543d4),
[Flet Canvas docs](https://flet.dev/docs/controls/canvas/),
[Flet Animations docs](https://flet.dev/docs/guides/python/animations/).

**Cheap legibility fixes — ✅ DONE in T.12a (`combat.py` floating-number loop):**
- ✅ **Monospaced floating numbers** — `theme.FONT_MONO` on the damage/heal `TextStyle`.
- ✅ **Floating numbers coloured by damage type** (`_DMG_COLORS` keyed on the beat's damage-type `note`): physical = `DANGER` red, magical = `ACCENT` blue, true = `TEXT_PRIMARY` white, DOT = `DOT_DAMAGE` purple, heal = `SUCCESS` green. Crit marked with a trailing `!` + size bump (research: secondary element, not colour) so the type colour stays readable.
- ✅ **Stagger overlapping numbers** — per-target `hit_count` offsets each number up + right by index so multi-hit ticks stay legible.

**T.12b polish backlog (research-sourced):**
- **Float-up + bounce motion** for numbers — swap canvas `cv.Text` for an overlay `ft.Text` with `animate_offset` (implicit anim, no thread); "numbers float upward with bounce" is the standard juice. Flet has no canvas anim → manual timing or implicit-animated overlay controls.
- **Hit reaction** — token nudge / flash on damage ("without damage reactions, hits feel like a wet noodle"). Skipped in `a`.
- **Two-tier inspect** — hover = light highlight + name tooltip; click = full panel (TFT pattern). `a` is click-only.
- **Dedicated trait/synergy strip** + **live damage mini-tracker** — TFT splits info across panels (trait tracker left, damage/scoreboard right) to cut board clutter; ours buries traits in the inspect global panel and shows damage only on the end panel.
- **HP bars do double duty** — embed tier/rarity pip on the bar (TFT bars carry star level); pairs with the sprite pass.
- **Canvas static-layer flatten** — the 70-dot cell grid is static; `canvas.capture()` it once instead of redrawing each render (micro-opt; current full-rebuild is fine for a low-frequency turn-based stepper, not a 60fps loop).
- **Phase state-machine** for menu→prep→combat→summary routing (T.15) — standard game-loop pattern; our update(stepper)/render split already conforms.

## 8. Test plan
UI not unit-tested (CLAUDE.md) → target the **pure `combat_playback`** model (cues + queue) + the **view↔stepper wiring contract**:
- `build_playback(result)`: one step per event-bearing tick; steps cover every `BattleEvent`; `Step.round == tick // ROUND_TICKS`; each step's beats are the tick's cues in resolved order (no resource fields on the model).
- **Action queue:** `queue(cursor)` returns current + ≤2 future rounds, round-split markers correct; window slides + appends as the cursor crosses a `ROUND_TICKS` boundary; entries are the chosen action beats in resolved order.
- **Resource truth is the stepper, not the model:** assert `Playback`/`Step` exposes **no** hp/mana/barrier fields (regression guard against re-introducing stream reconstruction, B.28). Resource fidelity itself is already covered by T.37c (`CombatReplay` == `inspect_at_tick`) — not re-tested here.
- **Stepper wiring (pure, no Flet):** a tiny helper that, given a `BattleResult` + a `CombatReplay`, walks the steps and reads `replay.step_to(step.tick).pieces()` — assert it reaches the final survivors (sanity that the view's drive loop is correct without a display).
- Spawn/despawn: summon's step appears at its spawn tick; the stepped board shows it alive then gone after despawn (not a lingering corpse).
- Determinism: same `CombatSession` → identical `Playback` (pure; no view-layer RNG).
- No Flet import in `combat_playback` (import it in a test with no display).
- (T.12b) `resolve_boss_combat` promoted to src is byte-identical to the `tools/` version (sims unchanged).

## 9. Acceptance criteria
**T.12a**
1. `uv run flet run` (dev flag) → harness; node-type (FIGHT/CHALLENGE/REWARD, all combats) + team + enemies + weather + augments + items selectable; "Run" opens the combat view (REWARD = easy fight).
2. Hex board shows pieces at their **stepped** coords; **Next** steps the fight one action at a time (default), each event animates and **bars/positions/statuses snap to the live `CombatReplay` `PieceView`** — HP drops correctly through registered-ability bursts (B.28), not just basic attacks; autoplay + fast-forward also work.
3. **Action queue** (top) projects the next **2 full rounds** with round split markers, appending as rounds complete.
4. **Click-to-inspect** a piece shows live stats (from the stepper / `inspect_at_tick`, incl. STR ramp) + equipped items + traits; a global panel shows active augments + cleared traits. Read-only.
5. Combat-end panel (outcome/survivors/damage); `Continue` → harness.
6. `combat_playback` is pure, Flet-free, tested, and carries **no resource numbers** (cues + queue only, V.57); `game/` has zero `ui/` imports (V.1); displayed durations are seconds (V.39).
7. `docs/live/systems/ui.md` created; `/check` passes.

**T.12b**
8. Boss nodes render with map effects; `resolve_boss_combat` lives in `src/game/combat/resolve.py` (UI imports src, not `tools/`); sims byte-identical; boss-aware `inspect_at_tick`.
9. Real-time-scaled autoplay pacing, status-icon row, keyboard shortcuts, tick-by-tick admin mode.

## 10. SPEC changes needed (for `/spec`)

This is a **refresh** — the T.12a/T.12b rows + V.56/V.57 are **already in SPEC** (added when T.12 was split + during the B.28 backprop). Remaining deltas are small:

**§T — amend the `T.12a` row:**
- **Depends:** `T.3, T.8, T.37` → **`T.3, T.8, T.37a, T.37b, T.37c`** (T.37c is the forward stepper the bars now require; ✅ done).
- **Goal-line wording:** swap "over the T.37 stream … live HP/mana bars" for "**driving the forward `CombatReplay` stepper** for live HP/mana/stat/position bars (V.57); the recorded stream supplies **animation cues + 2-round action-queue projection**". `combat_playback` described as "**cues + queue projection** (no resource reconstruction)".
- Status stays `📋 Plan`. (T.12b row unchanged.)

**§V — none new.** V.56 + V.57 (already in SPEC) cover "view resource truth = live replay, stream = cues + queue". This plan just conforms to them.

**§B — none.** B.28 already records the drift + is RESOLVED by T.37c.

**§D:** D.16 (routes) — note `/combat` now has a real view, dev-launched ahead of T.15 (unchanged from prior plan).

**Implementation Order:** `… T.37a → T.37b → T.37c → T.12a → T.12b` (already reflects T.37c). The harness substitutes for the unbuilt shell (T.9/T.10/T.15/T.23); those tasks later swap their `Start Combat` producer onto the same `CombatSession`.

## 11. LIVING docs to update
- **Create `docs/live/systems/ui.md`** (first UI LIVING doc): `CombatSession` contract, `combat_playback` model (**cues + queue, no resource numbers**), combat-view zones + interaction model (manual step default, inspection), **the view↔`CombatReplay` drive loop (bars from the live stepper, V.57)**, dev harness, `main.py` dev entry. `/check` must pass.
- Append to [`docs/live/systems/combat.md`](../../live/systems/combat.md): one-line pointer that the combat view consumes the `CombatReplay` stepper + event-stream API (no logic added). *(The Replay section already documents the stepper as of T.37c.)*
- `ARCHITECTURE.md` §11 (UI layer): add the combat view + harness + `CombatSession` seam. FROZEN docs (`views_spec.md`) untouched.
