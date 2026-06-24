# 2026-06-23 — T.12c-A footprint VFX · dev hex-harness · starting-position override (V.62)

## What changed

Three threads, one session (all on top of the merged T.12 combat view):

1. **T.12c phase A — per-ability-shape footprint VFX.** Targeting helpers
   (`enemies_in_radius`/`allies_in_radius`/`neighbors_of` → `circle`,
   `line_targets` → `line`) now record the geometry they already compute via
   `ctx.note_footprint` → `on_footprint` → recorder `Footprint`s on
   `BattleResult` — **observer-only, scoped to `current_cast_id`, byte-identical**
   (V.61). `cast_id` threaded onto the `cast`/`ability` beats so the view joins a
   footprint to its ability for **element colour** (`AbilityMeta.tags`). View
   draws an animated expand/fade circle (element-coloured) that pops the **same on
   manual Next and autoplay** then stays as a static residue. Status: T.12c
   `🔶 Partial` (phase B — buff/heal halos + control telegraphs — not built).

2. **Dev hex-map board builder** (`ui/views/dev_harness.py`). Replaced the
   text-field team picker with a TFT-style **hex map**: 10×7 offset grid split
   left=ally / right=enemy (+ centre divider = the "missing middle"); a bench
   (Champions ↔ enemy-mobs toggle, searchable) of `Draggable` tiles; drag a tile
   onto a **cell = that unit's starting position**; drag a placed token to move
   it; click → level (1-3) / remove panel; **presets** dropdown (4) + Clear. A
   champion dropped on the enemy half → `Enemy`; an enemy mob on the ally half →
   `Champion`; ids de-duped. Procedural mode kept as a second tab.

3. **Starting-position override (V.62).** `build_combat(…, positions)` applies a
   piece-id → `(q,r)` map **after `assign_spawns`** (both sides), validated
   (on-board, no shared cell), byte-identical when `None`. Threaded through
   `resolve_combat`/`resolve_boss_combat`/`CombatReplay` + `CombatSession.positions`;
   the view passes it. This is what makes the hex placement actually matter in
   combat.

## Why (the part SPEC compresses out)

The combat view shipped last session; the user wanted to *drive* it without the
unbuilt Prep/Trail shell — hence a real placement UI, framed explicitly as "a
preliminary version of the prep phase." The footprint work (T.12c-A) and the
harness are independent but landed together because the harness is how you
*see* the footprints (drag Aurion, watch the AoE circle).

The deep call of the session was **not inventing a parallel surface**: the
position override is the write-half of the planned **T.23** (Prep formation
snapshot). We kept the general both-sides primitive (V.62) the dev tool needs,
and re-scoped T.23 as the player-team-only validated wrapper *on top* of it,
rather than letting `positions` float un-spec'd.

## Decisions

- **Footprint = recorded targeting geometry, not authored** (V.61) — reuse the
  handler's own hit-determination; zero drift, zero content tax. (Carried from
  the T.12c plan.)
- **`cast_id` on beats** (user-directed) — precise footprint↔ability colour join
  even when two casts share a tick, over a cheaper per-step-cast heuristic.
- **Manual == autoplay VFX** (user-directed) — static truth painted immediately
  (race-safe), the "exciting" shape pop is a non-blocking cosmetic over it; a
  rapid Next just leaves the full shape. Avoids re-introducing the rapid-Next
  abort bug we fixed last session.
- **Drag-and-drop over click placement** — feasible because we de-blinded (below).
- **General `positions` (both sides) + V.62, not team-only `team_positions`** —
  the dev tool places enemies too; T.23 stays the team-only prep wrapper.

## Process notes (AI collaboration)   ← MANDATORY

- **De-blinding mid-session.** The agent had been treating "headless build, user
  is the visual oracle" as a hard constraint and pre-emptively recommended the
  *lower-fidelity* option (click placement) to dodge blind drag-drop risk. The
  user pushed: *"if the issue is developing blind can you change that?"* — and it
  could: `flet run -w` + Playwright (`chromium --use-gl=swiftshader`, CanvasKit
  renders fine) → the agent now screenshots its own work. **Lesson: don't bake a
  constraint into the recommendation before checking if the constraint is real.**
  This flipped the whole interaction model (true DnD, self-verified).
- **Planned-task collision caught by the user, not the agent.** The agent shipped
  a `positions` param on the pure combat entry without checking SPEC §T — the
  user's *"the engine should already be prepared for inloading starting
  positions, investigate deeper"* surfaced **T.23** (a `📋 Plan` row whose plan
  doc specs a `team_positions` contract). The agent had built a parallel surface
  to a planned task + drifted **V.56** (whose `CombatSession` field list was
  already stale re `map_effect_id` from T.12b). Reconciled via `/spec` (V.62 +
  V.56 amend + T.23 annotation). **Lesson: before adding a param to a §V/§I
  surface, grep §T/§D for the reserved home.** A pre-edit "does the spec already
  own this?" check would have caught it.
- **Flet 0.85 API drift.** `ft.Dropdown` uses `on_select` (Material-3 menu), not
  `on_change`; `DragTargetEvent` exposes `.src`/`.src_id`, not a `.data` shortcut.
  Both caught only because the agent could now *see* the red error overlay in a
  screenshot — would have been invisible headless.
- **Background-server hygiene.** `pkill -f "flet run -w"` repeatedly missed the
  uvicorn child holding the port → stale server kept serving old code, masking
  fixes (the `on_change` error "persisted" after the fix). Had to kill by the
  listening pid (`ss -ltnp`) and bump ports. **Lesson: when a web-served edit
  "didn't take", suspect a zombie on the port before doubting the code.**

### Prompting-strategy reflection   ← MANDATORY

The session's signal: **the user repeatedly traded a few clarifying questions for
big course-corrections.** Three times a short user message redirected hours of
work (de-blind; "it's a hex map not columns"; "investigate, T.23 exists"). The
agent's `AskUserQuestion` forks (cast_id precision, animation scope, placement
UX, bench roster, override-scope, spec-process) were the right shape — but the
*best* moments came when the agent **verified a premise before asking** (probing
for a browser, grepping §T) rather than asking from assumption. The evolving
strategy: **ask after a cheap investigation, not instead of one** — and treat
"the user gently says investigate deeper" as a near-certain sign there's an
existing spec/code home to align to, not a green-field build.

## Files

- `src/game/targeting.py`, `src/game/combat/context.py` (`note_footprint`),
  `src/game/events.py` (`FootprintEvent`), `src/game/combat/recorder.py`
  (`_on_footprint`, `cast_id` on beats), `src/game/models.py` (`Footprint`,
  `BattleEvent.cast_id`, `BattleResult.footprints`)
- `src/game/combat/resolve.py` (`build_combat(positions=…)` + validation),
  `src/game/combat/replay.py` (`CombatReplay(positions=…)`)
- `src/ui/combat_playback.py` (`Step.footprints`, `CombatSession.positions`),
  `src/ui/views/combat.py` (footprint VFX + pop), `src/ui/views/dev_harness.py`
  (hex builder + presets)
- `tests/game/test_combat.py`, `tests/ui/test_combat_playback.py` (+8 tests)
- `SPEC.md` (V.62, V.56 amend, T.23 annot), `docs/live/systems/combat.md`,
  `docs/live/systems/ui.md`

## Follow-ups

- **T.12c phase B** — buff/heal ally halos + control telegraphs + status-apply
  flash via `AbilityMeta` intent tags.
- **T.23** — the Prep-side `team_positions` wrapper (player-team-only,
  deployment-zone + roster-id validation) over the V.62 primitive.
- **`playwright`** is venv-only — promote to a dev dependency if the
  screenshot verify-loop should be reproducible for the next agent.
