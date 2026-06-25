# 2026-06-25 — T.13: run-summary view (canvas damage chart)

## Overview

Built the run-end Summary screen: an outcome banner + a damage-per-battle bar
chart + final stats + Return-to-Menu. The chart is **hand-drawn on `flet.canvas`**
(not `ft.BarChart`) — see the reconciliation below. Mirrors the route-map's
pure-spec + canvas-builder shape (V.70).

## What landed

- **`viz/run_summary.py`** — `run_summary_specs(run) -> list[BarSpec]` (pure,
  Flet-free, deterministic): one bar per `run.battle_log` entry, `damage =
  sum(team_damage_dealt.values())`, `height_frac` max-normalized (empty/all-zero
  guarded), `won` from outcome. `build_run_summary(run)` draws `cv.Rect` bars
  (green win / red loss) + value/node labels + baseline on a `cv.Canvas`.
- **`ui/views/summary.py`** — `build_summary_view(page, run, *, on_menu)` (route
  `/summary`): banner + chart + stat chips (nodes cleared / battles / Amber / rank).
- **Tests** — `tests/viz/test_run_summary.py` (8: count/order/sum/normalize/zero-guard/
  outcome/determinism/types), `tests/ui/test_summary.py` (1: construct + menu). Suite **1428**.
- **Docs** — ui.md Summary section + V.70; SPEC T.13 ✅ + V.70; **CLAUDE.md "Charts"
  convention line corrected** (it still listed the removed native widgets).

## Process notes (AI collaboration)

- **The spec named an API the environment no longer has.** SPEC §T.13 + the MVP plan
  both mandated `ft.BarChart` ("graded viz, kept — no shortcut"). The plan's verify pass
  grepped the installed Flet (0.85.2) and found **no chart classes at all** — Flet ≥0.85
  moved `BarChart`/`LineChart`/`PieChart` to the optional `flet-charts` plugin. This is
  the CLAUDE.md "design docs lie — verify every primitive against code" rule biting at the
  *framework* level, not just our own primitives. Caught at plan time, not mid-build.
- **Surfaced the real fork instead of silently substituting.** Two honest options — add
  the `flet-charts` dep (restores the native widget but bumps flet 0.85.2→0.85.3 app-wide)
  vs draw on canvas (zero deps, matches the existing `route_map`). Asked the user; they
  chose canvas. Then **re-asked when they said they didn't understand** — rewrote the
  question in plain terms (what the chart is, why the widget's gone, the dep-vs-draw
  tradeoff) before proceeding. A confusing fork is worth re-framing, not pushing through.
- **Researched the canonical API before coding.** On the canvas decision, introspected the
  *installed* `flet.canvas` signatures (`cv.Rect(x,y,width,height,border_radius,paint)`,
  `cv.Text(x,y,value,style=ft.TextStyle,...)`, `ft.Paint(color,style=PaintingStyle.FILL)`)
  rather than trusting remembered Flet API — the pinned source is the ground truth.
- **Backprop judgment: drift, not bug.** The `ft.BarChart` citation was environment/API
  drift from a framework upgrade, reconciled by amending the row + adding V.70 (guards a
  future viz re-citing a removed widget). No §B — nothing regressed; the code was never
  written against the old API. Knowing when *not* to file §B keeps the bug ledger honest.
- **Fixed the screenshot harness lesson from T.15a.** Last task's deep-link screenshot was
  interrupted partly because the reused `shoot.py` hardcoded the prep port. This time the
  preview + screenshot scripts take matched ports — the visual gate rendered the chart
  cleanly (green wins, red loss bar, max-normalized heights, value/city labels).

## Prompting-strategy reflection

The plan→spec→build chain absorbed a framework-level surprise (a removed widget) without
derailing the build, because the *plan's* verify step is where I run code against the
environment — by the time `/build` ran, the canvas API was already confirmed and the only
open decision (dep vs draw) was the user's, asked up front. The re-ask moment is worth
noting: when a fork's first framing didn't land, the fix wasn't to decide for the user, it
was to strip the jargon and show the concrete tradeoff. Clear forks beat clever defaults.
The pattern holds: spend tokens verifying seams (now including the framework's own surface)
in planning, and the build stays mechanical.
