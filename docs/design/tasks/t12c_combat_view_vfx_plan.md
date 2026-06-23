# T.12c Plan — Combat-view per-ability-shape VFX (recorded footprints)

> **Status:** plan — ready for review. **Not a §T row yet** — needs `/spec` to add **T.12c** (resolves deferred **§D.27**). §10 lists the deltas.
> **Depends:** **T.12b** (combat view + primitives — ✅), **T.20** (targeting helpers — ✅), **T.34** (`AbilityMeta` tags — ✅). All met.
> **Resolves:** SPEC **§D.27** — richer per-ability-shape VFX (flashy line/cone/circle, stick-fight-magic feel; sprites stay deferred).
> **Design source of truth:** SPEC §D.27; LIVING [`ui.md`](../../live/systems/ui.md) + [`combat.md`](../../live/systems/combat.md); [`t12b_combat_view_polish_plan.md`](t12b_combat_view_polish_plan.md). Invariants: **V.54** (event-stream completeness), **V.56/V.57** (presentation over replay), **V.38** (`AbilityMeta`), **V.1/V.2/V.14**.
> **What this plan adds:** the **how-does-the-view-know-the-shape** answer — **record the ability's actual targeting footprint** (the geometry the handler already computes) onto the event stream, and animate it. Zero shape-authoring, **zero drift** (it *is* the engine's targeting), reuses the existing hit-determination.
>
> **⚠️ Headless-build caveat:** animations can't be self-verified — every visual is a **user gate** (`TEMPEST_DEV=1 uv run flet run`). The footprint recording + classifier are unit-testable (incl. byte-identical sims).

## Why footprints (the design call)

**Hit determination is imperative + inline** in each handler — `enemies_in_radius(t.q, t.r, 2, actor, ctx)`, `line_targets(actor, dir, len, ctx)` — radius/length are **literal args**, no stored targeting spec (`resolve_targets`'s selector path serves only the generic single-target default). So:
- **Pure beat-derivation can't draw intended beams** — beats are *cells hit*; a line catching one enemy looks single-target, cone≈line, no empty-cell footprint. Not Lux-ult-capable.
- **Authoring shape per ability** (~285) is a drift-prone content tax.
- **Reuse the handler's own targeting (chosen, user-directed):** the helpers already compute the exact geometry. Instrument them to **record the footprint** (kind + center + radius/length + cells) when a cast is in flight; the recorder stamps it on the stream; the view animates it. Single source of truth, no authoring, no drift, byte-identical (observer-only).

## 0. Substep split (`T.12c-A` footprint + flashy shapes · `T.12c-B` telegraphs + intent polish)

- **T.12c-A — footprint capture + animated shape VFX.** Instrument targeting helpers → `on_footprint` → recorder `footprint` records on the stream. View reads the step's footprints and draws + **animates (expand/fade)** the **circle** (radius AoE) / **line** (beam) in the ability's **element colour** (`AbilityMeta` tags). Single-target keeps swoosh/arrow. Pure footprint capture is byte-identical (V.2/V.14).
- **T.12c-B — intent + telegraphs.** Buff/heal → **ally halo/beam** (not a damage shape) via tags + heal/status beats; control tags → **target telegraph** + status-pip flash; per-element cast glyph; cone refinement only if a cone targeting helper is added (currently cones = radius AoE → circle).

## 1. Scope
**In scope (A):** `game/targeting.py` (helpers note their footprint during a cast), `game/combat/context.py` (`note_footprint` → `on_footprint`), `game/events.py` (`FootprintEvent`), `game/combat/recorder.py` (`_on_footprint` → `footprint` records) + `game/models.py` (footprint on `BattleResult`/beat), `ui/combat_playback.py` (expose footprints per step; pure), `ui/views/combat.py` (animated draw), tests.
**In scope (B):** intent classification from `AbilityMeta.tags` (buff/heal/control) + halos/telegraphs/status-flash in the view.
**Out of scope (why):**
- **Sprites / token art** — affinity circles + initials (D.27 keeps deferred).
- **Cone as a distinct shape** — no cone helper exists; cones resolve via radius → recorded as circle. A real cone helper is a separate (small) targeting addition if wanted.
- **Changing targeting results / damage** — footprint capture is **observer-only**; helpers return the same targets.

## 2. The gap today

| Piece | Where (`file.py:line`) | State |
|---|---|---|
| Flat VFX primitives (swoosh/arrow/beam/ring/lunge) | `ui/views/combat.py` | ✅ T.12b — single-target shaped |
| Targeting helpers w/ literal geometry | `targeting.py:114` `enemies_in_radius(center,radius)`, `:124` `allies_in_radius`, `:102` `neighbors_of`, `:145` `line_targets(actor,dir,length)` | ✅ — the footprint *source*; **not recorded** |
| Cast-scope hook | `context.py:110` `_current_cast_id` / `:135` `current_cast_id` | ✅ — scopes footprint capture to a cast |
| Event/recorder pattern (`on_*` → beat) | `context.py` bus + `recorder.py` subscriptions | ✅ — mirror for `on_footprint` |
| `AbilityMeta.tags` (element/intent: `magic`/`physical`/`true`, `aoe`/`buff`/`heal`/`defense`/control) | `registries.py:518` | ✅ — element colour + B's intent |
| Footprint on the stream | `models.py` `BattleResult`/`BattleEvent` | ❌ |
| No cone helper | `targeting.py` | 🔴 — cones = radius AoE (circle) |

## 3. Architecture

### 3.1 Footprint capture (game/, observer-only)
- **`targeting.py`** — `enemies_in_radius`/`allies_in_radius`/`neighbors_of` call `ctx.note_footprint("circle", center_q, center_r, radius=R)`; `line_targets` calls `ctx.note_footprint("line", actor.q, actor.r, direction=dir, length=L)`. They still return their target list unchanged. (`neighbors_of` = circle radius 1.)
- **`context.py`** — `note_footprint(kind, q, r, **geo)`: **only fires when `self._current_cast_id is not None`** (ties it to a cast; idle/AI/passive target queries don't record). Fires `on_footprint` with a `FootprintEvent` carrying `cast_id`, `kind`, center, geo. No subscriber (sims/CombatReplay) ⇒ a bus fire that no-ops ⇒ **byte-identical** (V.2/V.14); the helper's return is untouched.
- **`recorder.py`** — `_on_footprint` appends a `footprint` record (tick, cast_id, kind, center_q/r, radius|length|direction). Stored on `BattleResult` (a `footprints: list[Footprint]` field, serialized; legacy → empty) so the view reads it like the beat stream. **One producer, observer-only** (extends V.54).

### 3.2 View — animated shapes (`combat.py`, T.12c-A)
- Per step, gather the footprints at the step's tick (joined to the action by `cast_id`/tick). For each:
  - **circle** → an **expanding ring + low-opacity fill** at `(center_q,center_r)` scaled to `radius` cells, element-coloured.
  - **line** → a **beam** from the caster along `direction` for `length` cells (Lux-ult-style), element-coloured, thickening then fading.
- **Animated expand/fade (user-set):** a short async sequence (like `_play_step`'s drip) grows the shape's radius/opacity over ~0.3s then fades — drawn as overlay shapes (so they animate) or canvas redrawn per frame. Manual step shows the peak frame; autoplay plays the full expand/fade. Element colour from `AbilityMeta[ability_id].tags` (cast beat `note=ability_id`).
- Single-target (no footprint) → keep swoosh/arrow + lunge (T.12b).

### 3.3 Intent VFX (T.12c-B) — `AbilityMeta.tags`
`classify_intent(ability_id) -> heal|buff|damage|summon (+control flag)` (pure). Buff/heal → **ally halo** (green/accent ring on the targets from `heal`/`status` beats; pure-modifier buffs → caster glow). Control tags → **telegraph** on the struck target + status-pip flash on the `status` beat. No damage arrow for positive intents.

### 3.4 Invariant posture
- **V.2/V.14** — footprint capture is observer-only (no-op without a subscriber; targeting returns unchanged) ⇒ sims byte-identical.
- **V.54** — `footprint` joins the recorded stream as a single-producer record.
- **V.56/V.57** — view draws from the recorded footprints + `AbilityMeta` + live stepper; zero combat math.
- **V.1** — `ui/` reads `BattleResult.footprints` + `ABILITY_META`; raw `Piece`/`ctx` never escape.

## 4. Decisions
- **§4.1 Shape = recorded targeting footprint (reuse the handler), not authored, not beat-derived.** The helper already computes it; record what it used. Zero drift/authoring; exact geometry. *Firm (user-directed).*
- **§4.2 Capture scoped to `current_cast_id` + observer-only via `on_footprint`.** Idle/AI target queries don't record; no subscriber ⇒ byte-identical sims. *Firm (V.2).*
- **§4.3 Shapes: circle (radius) + line (dir/length).** The only geometries the helpers express; cone = radius AoE → circle (a real cone helper is a separate add). *Proposal, overridable.*
- **§4.4 Animated expand/fade** (async, like the drip); manual = peak frame, autoplay = full. *Firm (user-set).*
- **§4.5 Element colour from `AbilityMeta.tags`; intent (buff/heal/control) in B.** *Proposal.*
- **§4.6 Split A (footprint+shapes) / B (intent+telegraphs).** A is the flashy win + the backend lift; B is tag-driven polish. *Proposal, overridable.*

## 5. Authored values (presentation; tunable)
Expand/fade ~0.3s; circle fill opacity ~0.22 → 0 over the fade; beam stroke ~3→1px; element colours reuse `_DMG_COLORS`. No game numbers.

## 6. Content / roster audit + reconciliation
No handler/roster logic changed (helpers only *also* record). **Footprint-vs-reality guard:** a test asserts the recorded footprint's cells ⊇ the actual hit targets for a sample radius + line ability (the footprint must contain everyone who got hit) — catches a mis-recorded geometry. Tag-element mapping reuses the existing vocab (no new tags).

## 7. Open questions
**Resolved here (overridable):** §4.1–§4.6. Shape via recorded footprint; circle+line; animate expand/fade; intent in B.
**Still open / deferred:** a real **cone** targeting helper (if cones should render as cones, not circles) — small targeting add, propose only if playtest wants it; per-element distinct *glyphs* (vs just colour); sprite art (D.27).

## 8. Test plan
- **Byte-identical (V.2/V.14):** footprint capture adds no subscriber on the sim path ⇒ full sweep + `resolve_combat` golden unchanged (`workers=1`). A test: same fight with/without the recorder yields identical `winner`/survivors/`turns`.
- **Footprint correctness:** a radius ability records a `circle` with the right center+radius whose cells ⊇ the hit targets; a line ability records a `line` with dir+length (§6 guard).
- **`combat_playback` (pure):** footprints exposed per step join the right cast/tick; Flet-free; no resource fields (B.28 guard); `classify_intent` (B) tag→intent mapping + tag-coverage guard.
- **Serialization:** `BattleResult.footprints` round-trips; legacy results → empty.
- **Visual gates (user):** Ember Magma Burst / Aurion Solar Nova → expanding element-coloured **circle** over the radius; a line/beam ability → animated **beam**; buffs/heals → ally **halo/beam** not enemy arrows (B); control → telegraph (B).

## 9. Acceptance criteria
**T.12c-A**
1. Targeting helpers record their footprint during a cast (`on_footprint` → `BattleResult.footprints`); **observer-only, sims byte-identical**.
2. The view draws + **animates (expand/fade)** circle (radius) + line (beam) footprints, element-coloured; single-target keeps swoosh/arrow.
3. Footprint correctness + serialization tests pass; `combat_playback` Flet-free + tested; `/check` passes.
**T.12c-B**
4. Buffs/heals render as **ally halos/beams** (no damage arrow); control abilities show a **telegraph** + status flash; intent classifier + tag-coverage guard pass.

## 10. SPEC changes needed (for `/spec`)
**§T — add a new row** (after T.12b):
- `T.12c | Combat-view per-ability-shape VFX — record the ability's targeting footprint (reuse the handler's hit-determination: enemies_in_radius/allies_in_radius/neighbors_of → circle, line_targets → line) via ctx.note_footprint → on_footprint → recorder footprint records on BattleResult (observer-only, scoped to current_cast_id, sims byte-identical V.2/V.54); view draws + animates (expand/fade) circle/line in the ability's element colour (AbilityMeta tags), single-target keeps swoosh/arrow; (phase B) buff/heal ally halos + control telegraphs + status flash via AbilityMeta intent tags. Built headless → user visual gates | game/targeting.py, game/combat/context.py, game/events.py, game/combat/recorder.py, game/models.py, ui/combat_playback.py, ui/views/combat.py, tests/game/test_combat.py, tests/ui/test_combat_playback.py, docs/design/tasks/t12c_combat_view_vfx_plan.md, docs/live/systems/ui.md | T.12b, T.20, T.34 | M | 📋 Plan`
**§V — one new invariant:**
- **V.x (targeting footprints are observer-only telemetry):** targeting helpers record their geometry via `ctx.note_footprint` → `on_footprint` **only when a cast is in flight** (`current_cast_id` set); the recorder stamps `footprint` records on `BattleResult` for the combat view. Capture **never changes targeting results or damage** (helpers return unchanged; no subscriber on the sim path ⇒ byte-identical, V.2/V.14). The view reads footprints + `AbilityMeta` to draw shapes — no combat math (V.56/V.57). (T.12c)
**§D:** mark **D.27 RESOLVED (T.12c)** (sprites remain a separate deferred line).
**Implementation Order:** append `… T.12b → T.12c` (UI polish; non-blocking for the shell).

## 11. LIVING docs to update
- **`combat.md`** — `note_footprint`/`on_footprint` + `footprint` records on `BattleResult` (observer-only); add to the beat-taxonomy/recorder section.
- **`ui.md`** — footprint-driven shape VFX (circle/line expand-fade, element colour), intent halos/telegraphs (B). Replace the flat-primitive description.
- `ARCHITECTURE.md` §3.1 — footprint capture on the targeting/recorder seam. FROZEN docs untouched.
