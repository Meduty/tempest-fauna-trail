# Handoff — next agent

> Transient. Update or delete as you pick work up. Last updated **2026-06-24 (EOD)**.
> Authoritative state is always SPEC.md + the LIVING docs; this is just a fast
> "where we left off + what's next".

## State at EOD (2026-06-24)

`main` is the single source of truth and is **green: 1363 passed**. Lint clean,
`/check` clean on touched invariants (V.56/V.61/V.62). Today consolidated two
machines' divergent work and finished the combat-view intent VFX.

### Landed today (all on `main`)
- **Reconciliation (PR #51, squash `53d1b31`)** — two parallel T.12c builds were
  reconciled: the **more robust remote build won the base** (footprint VFX with
  per-cast `cast_id` join + `fp_phase` pop animation, the **drag-drop hex board
  builder**, and **V.62** starting-position override), and the local build's
  **intent layer** was ported on top (`classify_intent` → heal/buff green halo +
  control telegraph ring). **T.9** (main menu + Playfight) was folded in. The
  local-VFX line was discarded. All stale branches pruned (remote+local → only
  `main`).
- **T.12c-B — beat-driven intent VFX (T.12c now ✅).** Observer-only overlays read
  from recorded `heal`/`status` beats so single-target casts (no footprint) still
  read intent: **ally halo** on heal targets (`heal-halo-{target_id}`) +
  **status-apply flash** on the afflicted piece (`stflash-{actor_id}-{note}`).
  `game/` untouched → byte-identical sims (V.2/V.14). Visually gated headless
  (halo + flash render, no error overlay).
- **Intra-tick stagger (manual `Next` only)** — `reveal_n` + `_drip_action_beats`
  (`_BEAT_STAGGER_S`) reveal a tick's beats in recorded chronological order, so
  multiple pieces acting on one tick read move→attack→… instead of all at once.

## ⚠ Known-rough / shipped unpolished (SPEC §D.28)

The combat view is **intentionally shipped unpolished** to hit the full-suite MVP
deadline — polish pass is post-MVP. Carried on purpose:
- **Autoplay needs a full REWORK, not a patch** (top combat-view pickup). Pacing is
  weak/illegible: action FX flash sub-frame on single-beat ticks, the first step
  eats the clamped 2.5 s delay, and a tick's beats show together. Autoplay was
  reverted to its pre-stagger control flow today (no worse than what shipped in
  #51). Likely wants a real timeline/scheduler with dwell + interleaved beats.
  Suggest a **T.12d / T.12-polish** task.
- The **manual stagger feels clunky** (delay tuning + interrupt feel) and does
  **not** apply to autoplay.
- Sprite art + general shape/number/lunge timing polish still deferred (D.27).

## Pick-up candidates (no priority order)
1. **Autoplay rework** (T.12d) — see §D.28. Highest-value combat-view polish.
2. **T.23 (Prep formation snapshot)** — Prep-side player-team `team_positions`
   wrapper (deployment-zone + roster-id validation) **over the V.62 primitive**.
   Plan: `docs/design/tasks/t23_prep_formation_snapshot_plan.md`. Needs T.15.
3. **UI shell tasks** still `📋 Plan`: T.10/T.11/T.13/T.15 (T.9 menu done). The
   combat view + dev harness already build the `CombatSession` the Prep/Trail flow
   reuses verbatim (V.56) — wiring is "produce the same `CombatSession`".

## Multi-machine hygiene (today's lesson)
Two machines built T.12c in parallel off an unsynced `main` → a painful manual
reconcile. **Always branch + push before leaving a machine; pull `origin/main`
before starting.** The other machine still needs to sync:
`git fetch origin && git status` (confirm clean) `&& git checkout main && git reset --hard origin/main`.

## Visual verification (you are NOT blind)
Self-verify Flet VFX headlessly. Two paths:
- **Quick / live app:** `BROWSER=true TEMPEST_DEV=1 uv run flet run -w -p 8590 --host 127.0.0.1 src &`
  then Playwright screenshot (below). Lands in the Playfight harness.
- **Targeted (a specific fight + step):** a **standalone gate app** is more reliable
  than driving the harness — build a `CombatSession` and call `build_combat_view`
  directly, serve `ft.app(main, view=ft.AppView.WEB_BROWSER, port=…)`, then drive.
  (Working scripts were in the session scratchpad — regenerate; not committed.)

```bash
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
- Flet web = **one canvas, no DOM** → drive by **pixel coords / keyboard**, not
  selectors. A red overlay in the shot = API drift (that's how you catch it).
- **Keyboard nav** in the combat view: `→`/`Enter` Next · `←` Prev · `Space`
  autoplay · `F` end · `R` restart · `Esc` exit. **Click the board first to focus**,
  and pace presses (~120 ms) — rapid keypresses get dropped (and rapid `Next` is
  interrupt-safe by design, so it fast-seeks). Pre-compute the target step index
  (resolve + `build_playback`, scan `step.beats` kinds) — the opening steps are
  positioning **moves**, damage numbers don't appear until pieces engage.
- **Gotcha:** `flet run -w` leaves a uvicorn child; kill by `ss -ltnp` pid, bump the
  port if an edit "didn't take". Flet 0.85: `ft.Dropdown` → `on_select`;
  `DragTargetEvent` → `e.src.data`.

## Loose ends
- **`playwright`** is venv-only; promote to a `pyproject.toml` dev dep if the
  verify-loop should be reproducible.
- Scratchpad gate/driver scripts are not committed — regenerate as needed.
