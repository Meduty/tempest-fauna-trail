# T.13 Plan — Run-summary view (canvas damage-per-battle chart)

> **Status:** `T.13 🟡 WIP` (flipped by `t10_mvp_run_loop_plan.md`). Focused plan;
> the MVP-slice doc covers it at slice level (§3.5). **Key reconciliation:** the
> SPEC + MVP doc mandate **`ft.BarChart`**, but **Flet 0.85 removed the chart
> widgets from core** (`ft.BarChart`/`LineChart`/`PieChart` are gone; they live in
> the optional `flet-charts` plugin). Per the user, the summary chart is **hand-drawn
> on `flet.canvas`** (the same graded-viz path the route-map already uses) — no new
> dependency, no flet version bump. The T.13 row's `ft.BarChart` is amended to
> "canvas bar chart" (§10).
> **Depends (state):** T.3 (`BattleResult` ✅), T.8 (theme/components ✅). **Gates:**
> **T.15b** (terminal → Summary routing) needs this view to exist.
> **Resolves:** the run-end screen gap; the second graded visualization of the MVP slice.
> **Design source-of-truth:** SPEC §G "Core game loop", §V.2 (determinism),
> [`views_spec.md`](../systems/views_spec.md) §8 (Summary),
> [`t10_mvp_run_loop_plan.md`](./t10_mvp_run_loop_plan.md) §3.5, and the **landed
> `viz/route_map.py`** (the canonical pure-spec + canvas-builder pattern to mirror).
> **What this plan adds beyond the MVP doc:** the canvas-vs-`ft.BarChart`
> reconciliation, the verified Flet-0.85 canvas API, and the pure-spec/test shape.

---

## 0. Substep split

None — single M task (one pure builder + one view + one test), mirroring
`viz/route_map.py` + `ui/views/trail.py`'s split-within-a-file shape.

---

## 1. Scope

**In:** `viz/run_summary.py` (pure `run_summary_specs(run)` + canvas
`build_run_summary(run)`), `ui/views/summary.py` (the run-end view: outcome banner
+ chart + final stats + return-to-menu), `tests/viz/test_run_summary.py`.

**Out (with why):**
- **No routing to Summary** — terminal (victory/defeat) → Summary is **T.15b** (the
  view is built + verified here via deep-link; wired there).
- **No new combat/economy data** — reads `run.battle_log` (`BattleResult`) + `run`
  fields that already exist; computes nothing new (V.63/V.1).
- **No `ft.BarChart` / `flet-charts` dependency** — canvas-drawn (user decision, §4 D1).
- **No per-piece breakdown / interactive chart** — one bar per battle, MVP (deferred).

---

## 2. The gap today

| Piece | `file.py:line` | State |
|---|---|---|
| Per-battle damage | `BattleResult.team_damage_dealt: dict[str,int]` / `team_damage_taken` (`models.py:606-607`) | ✅ |
| Battle log | `Run.battle_log: list[BattleResult]` (`models.py:706`) | ✅ |
| Run-end status | `Run.status` ∈ `RunStatus.{VICTORY,DEFEAT}` (`models.py:48`); per-battle `result.outcome` (`CombatOutcome`) | ✅ |
| Final stats | `run.amber`, `run.tempest_rank`, nodes cleared (`route` state count) | ✅ |
| Canvas viz pattern | `viz/route_map.py` (pure `route_node_specs` + `build_route_map`, `cv.Circle/Line/Text` + overlay) | ✅ mirror |
| Canvas primitives (Flet 0.85, verified) | `cv.Rect(x,y,width,height,border_radius,paint)`, `cv.Text(x,y,value,style=ft.TextStyle,alignment)`, `cv.Line`, `cv.Canvas(shapes,width,height)`, `ft.Paint(color,style=ft.PaintingStyle.FILL/STROKE,stroke_width)` | ✅ |
| `ft.BarChart` | — | 🔴 **removed in Flet 0.85** (SPEC/MVP-doc cite it; reconcile → canvas) |
| `viz/run_summary.py`, `ui/views/summary.py` | `viz/__init__.py` only | ❌ create |

---

## 3. Architecture

`ui/`→`game/`/`viz/`, never the reverse (V.1). Mirror `viz/route_map.py`: a **pure
data** function (test-asserts structure, not pixels) + a **canvas builder** that turns
specs into `cv.*` shapes.

### 3.1 Pure specs — `viz/run_summary.py::run_summary_specs(run) -> list[BarSpec]`
```python
@dataclass(frozen=True, slots=True)
class BarSpec:
    index: int          # battle ordinal (0-based)
    label: str          # short node label (from BattleResult.node_id)
    damage: int         # sum(result.team_damage_dealt.values())
    height_frac: float  # damage / max_damage  (0..1; max-damage bar = 1.0)
    won: bool           # result.outcome == CombatOutcome.WIN
```
- One spec per `result` in `run.battle_log`, in order.
- `damage = sum(result.team_damage_dealt.values())` (team **dealt** — matches SPEC
  "damage-per-battle"; `taken` left for a future toggle).
- `height_frac` normalized to the max damage across the log (empty / all-zero log ⇒
  `height_frac = 0.0`, guarded — no divide-by-zero).
- `label` derived from `node_id` (e.g. trailing city/segment); pure string slice.
- **Deterministic + pure** — same `run` ⇒ same specs (V.2); no Flet import in the
  spec function (only the builder imports `flet`).

### 3.2 Canvas builder — `build_run_summary(run) -> ft.Control`
- `specs = run_summary_specs(run)`; layout constants (margins, bar width/gap, plot
  height) module-level like `route_map`'s.
- Per spec: `cv.Rect(x, baseline - bar_h, bar_w, bar_h, border_radius=2, paint=
  ft.Paint(color=SUCCESS if won else DANGER, style=ft.PaintingStyle.FILL))` where
  `bar_h = spec.height_frac * PLOT_H`; a value label (`cv.Text`) above + the node
  label below; a baseline `cv.Line`. Wrap in `cv.Canvas(shapes, width, height)`.
- Empty log ⇒ a single "No battles fought" `ft.Text` (no canvas).
- Pure presentation — reads specs only, no recompute (V.63).

### 3.3 View — `ui/views/summary.py::build_summary_view(page, run, *, on_menu) -> ft.View`
- Route `/summary`. Outcome banner (`VICTORY`→SUCCESS "Victory", `DEFEAT`→DANGER
  "Defeat"), the canvas chart, a stat row (nodes cleared `N/len(route)`, final Amber,
  rank, battles fought), and a **Return to Menu** button → `on_menu()`.
- Mirrors `ui/views/reward.py` / `run_start.py` shape (centered card, theme tokens).

### 3.4 Cross-task seams
- **T.15b** wires `summary.status` terminal → `build_summary_view(..., on_menu=
  _pop_to_root)`; this task ships the view + a deep-link visual check only.
- **Determinism:** the chart is a pure function of `run.battle_log`; a Continue-after-
  load run reproduces the identical chart (V.2).

---

## 4. Decisions

1. **Canvas-drawn chart, not `ft.BarChart`/`flet-charts`** (user decision). *Rationale:*
   Flet 0.85 removed core charts; the repo already commits to `flet.canvas` for graded
   viz (`route_map`); zero new deps / no version bump. **Decided (user).**
2. **Metric = team damage *dealt* per battle** (`sum(team_damage_dealt.values())`).
   *Rationale:* matches SPEC "damage-per-battle"; `taken` deferred to a toggle. **Proposed.**
3. **Bar colour = outcome** (win→`SUCCESS`, loss→`DANGER`) so a defeat's last bar reads
   red. **Proposed.**
4. **Normalize to max-damage bar = full height**; empty/all-zero ⇒ flat (guarded).
   **Proposed.**

---

## 5. Authored values
- Layout constants (plot height, bar width/gap, margins) — first-pass, tunable; no
  game-balance numbers (this task authors a viz, not balance).

---

## 6. Content / roster audit + reconciliation

- **`ft.BarChart` API drift (caught).** SPEC §T.13 + `t10_mvp_run_loop_plan.md` §3.5
  cite `ft.BarChart`; **Flet 0.85.2 removed `BarChart`/`LineChart`/`PieChart` from core**
  (verified: absent from `dir(flet)` + the package; they now live in the optional
  `flet-charts` plugin). Origin: the spec/plan were written against an older Flet (the
  CLAUDE.md "Charts" convention line still lists the three native widgets). **Reconcile:**
  render on `flet.canvas` (matches `route_map`); amend the T.13 row `ft.BarChart` →
  "canvas bar chart"; **fix the stale CLAUDE.md "Charts" convention line** in the build.
  **V-guard:** propose a §V (graded viz is hand-drawn on `flet.canvas`, no dependency on
  Flet's removed/optional chart widgets) so a future task can't re-cite `ft.BarChart`.

---

## 7. Open questions

**Resolved here (overridable):** damage-dealt metric (D2); outcome colour (D3);
max-normalize + empty guard (D4). **Decided with user:** canvas-drawn (D1).

**Still open / confirm during build:**
- **Q1:** `label` source — `BattleResult.node_id` is like `n3-Lisbon`; show the city
  tail, the index, or both? (Lean: short node tail; cheap to tune.)
- **Q2:** also overlay damage *taken* (second bar / line)? (Lean: no — dealt only for
  MVP; a toggle is post-MVP.)

**Deferred:** per-piece damage breakdown, interactive/hover chart, taken-vs-dealt toggle.

---

## 8. Test plan

`tests/viz/test_run_summary.py` (pure data, not pixels — mirrors `test_route_map.py`):
- **One spec per battle, in order:** `len(specs) == len(run.battle_log)`; `index`
  ascending.
- **Damage value:** `spec.damage == sum(result.team_damage_dealt.values())` for a fixture
  run with known `battle_log`.
- **Normalization:** the max-damage spec has `height_frac == 1.0`; others `< 1.0`;
  all in `[0,1]`.
- **Outcome colour flag:** `spec.won` tracks `result.outcome == CombatOutcome.WIN`.
- **Empty log guard:** `run_summary_specs(run_with_empty_log) == []` and
  `build_run_summary` returns a non-crashing control.
- **Determinism (V.2):** same `run` ⇒ identical specs across two calls.
- **View smoke (optional, `tests/ui/test_summary.py`):** `build_summary_view`
  constructs + Return-to-Menu fires `on_menu` (mirrors `test_reward.py`).

---

## 9. Acceptance criteria

1. `run_summary_specs(run)` returns one `BarSpec` per battle (ordered), `damage` =
   per-battle team damage dealt, `height_frac` max-normalized + empty-guarded, `won`
   tracking outcome; deterministic; tested.
2. `build_run_summary(run)` renders a `flet.canvas` bar chart (one coloured bar per
   battle + labels + baseline) and an empty-log fallback; no pixel assertions.
3. `build_summary_view(page, run, on_menu)` shows the outcome banner + chart + final
   stats (nodes cleared / Amber / rank / battles) + Return-to-Menu; route `/summary`.
4. Deep-link visual check renders without error (a DEFEAT and a VICTORY run).
5. Tests green; full suite green; CLAUDE.md "Charts" line corrected.

---

## 10. SPEC changes needed (for `/spec`)

- **§T row T.13** — amend `**`ft.BarChart`** of` → `**canvas bar chart** (`flet.canvas`,
  Flet 0.85 removed core charts) of`; refresh files-cell:
  `viz/run_summary.py`, `ui/views/summary.py`, `tests/viz/test_run_summary.py`,
  `docs/live/systems/ui.md`, `docs/design/tasks/t13_run_summary_plan.md`. Status `🟡`→`✅`
  on land.
- **New §V invariant (graded-viz medium):** *the run-loop's graded visualizations
  (`viz/route_map.py` route-map, `viz/run_summary.py` damage chart) are hand-drawn on
  `flet.canvas` (pure `*_specs` data fn + canvas builder, test-asserts data not pixels);
  they take **no** dependency on Flet's chart widgets (`ft.BarChart`/`LineChart`/
  `PieChart` — removed from core in Flet ≥0.85, optional `flet-charts` only).* Guards a
  future task re-citing a removed widget.
- **§B backprop:** none — the `ft.BarChart` citation is environment/API drift from a
  Flet upgrade, reconciled here (not a code regression). Recorded in §6.
- **§D:** none.
- **Implementation Order:** unchanged — `T.15a → T.13 → T.15b` (this is the `T.13` step).

---

## 11. LIVING docs to update (build must touch on landing)

- **`docs/live/systems/ui.md`** — add the Summary section (route `/summary`, the
  `run_summary_specs` + canvas builder seam, the outcome/stats panel) + flip Summary
  status; note the canvas-chart decision next to the route-map viz.
- **`CLAUDE.md`** — fix the stale **"Charts: `ft.BarChart`, `ft.LineChart`, `ft.PieChart`
  native"** convention line (Flet 0.85 removed them) → "graded viz hand-drawn on
  `flet.canvas`; native charts are the optional `flet-charts` plugin (not used)".
- Journal entry on landing (Process notes + prompting-strategy section, CLAUDE.md mandate).
