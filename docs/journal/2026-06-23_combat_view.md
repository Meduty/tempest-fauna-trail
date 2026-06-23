# 2026-06-23 — Combat view: stepper, view, boss, and the backprop cascade

Branch `feat/t12-combat-view`. One long session that took the combat UI from a
plan to a working, steppable, boss-capable view — and, characteristically,
surfaced four engine/recorder issues along the way.

## What shipped

- **T.37c — resumable forward replay stepper.** Refactored `engine.run`'s
  monolithic tick loop into a single `_step_combat` **generator** driven two ways
  (V.29 — one loop body): `run()` drains it (byte-identical resolve), `CombatReplay`
  steps it **forward** (`.step_to`/`.pieces()`), `inspect_at_tick` re-runs on it.
  Killed the O(N²) re-sim-per-tick the T.12 plan would have needed. Move/spawn
  beats hardened to structured `dest_q`/`dest_r`.
- **T.12a — combat view core + dev harness.** `flet.canvas` hex board, live
  HP/mana/stat bars off the stepper, action queue, click/hover inspect with live
  ability text, dev harness (`TEMPEST_DEV=1`), pure Flet-free `combat_playback`.
- **T.12b — boss + animation/readability.** `resolve_boss_combat` promoted to
  `src/game/combat/` (V.59); map-effect overlay; token **tween**, attack
  **swoosh**/**arrow**, heal **beam**, **lunge**, real-time **DOT drip**,
  **sudden-death** indicator, status pips, active-queue highlight, mana
  cast-threshold ticks, damage-type colours + legend.

## The backprop cascade (the real story)

The view never changed combat math, but **building presentation over the engine
exposed latent engine/recorder bugs** the headless sims never noticed:

- **B.28** — the recorder's event stream was an *incomplete* resource source
  (registered-ability burst emits no `hp_after`). Caught in **plan review**, before
  a line of view code — which is why the view reads bars from the live stepper
  (V.55/56/57), not the stream. Later the cosmetic remainder (ability-damage
  numbers) closed by adding an `ability` beat (V.54).
- **B.29** — three enemy abilities passed `damage_type="magic"`; the mitigation
  switch only matched `"magical"`, so they were silently mitigated by **armor not
  resistance**. Invisible for the whole project until the new `ability` beat put
  `damage_type` on the stream. Fixed + V.58 (closed `damage_type` vocabulary,
  `deal_damage` validates).
- **Sudden death** — `dot_true_damage` (sudden_death) dealt `SourceTag.TRUE`,
  which the recorder never beat → the view couldn't show it → "3 units die at
  once." Fixed with an `is_dot` flag (V.54) so true-DOTs emit `dot` beats; also
  slowed sudden death to once/sec + de-spammed the per-tick status re-apply.
- **V.60 — outcome is survivor-based.** The recorder forced `DRAW` on any
  `timed_out`, relabeling real winners (a boss sudden-death wipe) as draws.
  Removed the override; outcome follows the engine's survivor-based `winner`; a
  true DRAW is only a simultaneous DOT wipe (reachable, the mirror-stalemate
  tests prove it). `timed_out` is now an independent flag.

## Process notes (AI collaboration)

- **Plan review paid for itself.** The "review the plan for weak spots" prompt
  caught B.28 (HP-bar would freeze through ability bursts) *before* implementation
  — the single highest-leverage moment of the session. The agent's first instinct
  (stream-reconstruction) was wrong; the user's "can't we read the live sim?" redirect
  produced the correct, simpler design (V.55 stepper).
- **Plan-vs-code drift, twice.** The T.37b plan *promised* a forward stepper
  ("hold one stepped instance and advance"), but only `inspect_at_tick` (re-sim)
  shipped; the later T.12 plan then *reverted* to stream-reconstruction. The user
  remembered the original design — the agent had to reconcile a frozen plan doc, a
  newer plan doc, and code that matched neither. Lesson reinforced: frozen plans
  are dated snapshots; verify against code (CLAUDE.md), and the journal/why-trail
  matters.
- **Headless UI building is the sharpest constraint.** The agent cannot see Flet
  output; every visual bug — the click-eating `expand`-in-`Stack` overlay, the
  `expand`-in-`wrap` legend balloon, numbers hidden behind tokens (canvas under
  overlays), heal lines pointing at enemies, attacks invisible on rapid Next —
  was found by the **user's screenshots**, not by the agent. Mitigation that
  worked: build the view with a **fake `Page`** to catch import/attr/exceptions
  (proved several "bugs" were layout, not crashes), and lean on the pure
  `combat_playback` model + boss byte-identity for the parts that *are* testable.
- **Two flet traps logged:** `expand=True` inside a `Stack` overlay eats pointer
  events even when its content is `visible=False`; `expand` inside a `wrap=True`
  Row balloons. Both cost a round-trip.
- **"Attacks broken" was an interaction-timing bug, not a draw bug.** The
  `is_dot` change made most steps carry `pre_beats`, so the async real-time drip
  gated the action behind a multi-second wait that rapid Next aborted. Fix:
  manual Next = instant reveal; the drip is autoplay-only. A reminder that adding
  data (beats) silently changed an unrelated interaction path.
- **Determinism discipline held throughout.** Every recorder/engine change was
  argued byte-identical (observer-only; `turns` excludes new beat types) and the
  full suite stayed green (1208 → 1247) with no sim re-baseline.

## Prompting-strategy reflection

- The most valuable prompts were **"review X for weak spots"** and **terse
  redirections** ("can't we read the live sim?", "no true draw exists… on no
  survivors"). The user steered *design* at decision forks and let the agent run
  the mechanical build — exactly the split SDD wants.
- **Screenshots as the test oracle** for UI: the agent should treat each as a
  bug report and, before re-building blind, reproduce via the fake-Page harness +
  reason from the control tree. "Builds headless" is necessary but never
  sufficient for UI; say so and gate on the user.
- **Spec-first for every semantics change**, even mid-build (the `is_dot`,
  `damage_type` validation, and DRAW changes each got a `/spec` amend before the
  edit) kept the invariants honest and the journal-able "why" recorded as it
  happened rather than reconstructed.
- Emerging pattern: when a presentation layer "just displays" an existing system,
  budget for it to **surface that system's latent bugs** — the display is the
  first consumer that actually looks at every field.

## Deferred

D.18 — richer per-ability-shape VFX (AoE area marking, buffs circling targets,
cones/lines, cast glow/projectile, sprites) → future T.12c. Plan: `t12b_combat_view_polish_plan.md`.
