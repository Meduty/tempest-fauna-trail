# Handoff — next agent

> Transient. Update or delete as you pick work up. Last updated **2026-06-23**.
> Authoritative state is always SPEC.md + the LIVING docs; this is just a fast
> "where we left off + what's next".

## State at handoff

Branch context: work from this session was committed on a feature branch (see
`git log`); `main` tip before it was `256bb8d`. **All tests green: 1255 passed,
101 skipped.** `/check` ran clean on touched invariants (V.1/V.56/V.61/V.62,
60/60 content).

### Landed this session
- **T.12c phase A** — per-ability footprint VFX (V.61). Targeting helpers record
  geometry → `BattleResult.footprints`; view animates element-coloured circles.
  SPEC status **`🔶 Partial`**.
- **Dev hex-map board builder** (`src/ui/views/dev_harness.py`) — TFT-style
  placement (drag bench → hex cell; left=ally/right=enemy; level/move/remove;
  presets; Champions↔enemy-mobs toggle). Procedural mode kept.
- **Starting-position override (V.62)** — `build_combat(…, positions)` over
  `assign_spawns`; `CombatSession.positions`. The general engine primitive; T.23
  is its prep-side wrapper.

## Pick-up candidates (no priority order)

1. **T.12c phase B** — buff/heal **ally halos** + control **telegraphs** +
   status-apply flash, classified from `AbilityMeta.tags`. Plan:
   `docs/design/tasks/t12c_combat_view_vfx_plan.md` §T.12c-B. Flip T.12c
   `🔶 → ✅` when done.
2. **T.23 (Prep formation snapshot)** — build the Prep-side `team_positions`
   wrapper (player-team-only; deployment-zone + roster-id validation) **over the
   V.62 primitive**. Plan: `docs/design/tasks/t23_prep_formation_snapshot_plan.md`
   (note: its contract is team-only `team_positions`; V.62 is the general both-
   sides engine layer it sits on). Needs T.15 routing.
3. **UI shell tasks** still `📋 Plan`: T.9/T.10/T.11/T.13/T.15. The combat view
   (T.12) + dev harness already build the `CombatSession` the Prep/Trail flow
   will reuse verbatim (V.56) — so wiring is "produce the same `CombatSession`".

## Visual verification (IMPORTANT — you are NOT blind)

The Flet UI can be self-verified without the user:
```bash
# 1. serve (pick a fresh port; kill zombies by listening pid, not pkill -f)
BROWSER=true TEMPEST_DEV=1 uv run flet run -w -p 8590 --host 127.0.0.1 src &
# 2. screenshot via Playwright (installed in the venv, NOT pyproject)
uv run python - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(args=["--use-gl=swiftshader","--enable-webgl","--ignore-gpu-blocklist"])
    pg=b.new_page(viewport={"width":1500,"height":1000})
    pg.goto("http://127.0.0.1:8590",wait_until="networkidle",timeout=60000)
    pg.wait_for_timeout(8000)          # CanvasKit needs time to paint
    pg.screenshot(path="/tmp/shot.png"); b.close()
PY
# then Read /tmp/shot.png
```
- Flet web = **one canvas, no DOM** → drive clicks/drags by **pixel coords**
  (`page.mouse.move/down/up`), not selectors. Errors show as a red overlay in the
  screenshot — that's how API drift gets caught.
- **Gotcha:** `flet run -w` leaves a uvicorn child on the port that `pkill -f
  "flet run -w"` misses → stale server serves old code. Kill by `ss -ltnp` pid +
  bump the port if an edit "didn't take".
- Flet 0.85 API notes: `ft.Dropdown` → `on_select` (not `on_change`);
  `DragTargetEvent` → `e.src.data` (resolved Draggable), not `e.data`.

## Loose ends
- **Nothing pushed/PR'd** unless you see it in `git log`/`gh pr` — check.
- **`playwright`** is venv-only; promote to a dev dependency in `pyproject.toml`
  if the verify-loop should be reproducible.
- Scratchpad screenshots/scripts (drag/run/preset/shot.py) are in the session
  scratchpad dir — not committed, regenerate as needed.
