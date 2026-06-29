# T.12d Plan — Combat-view rework (shared infocard · queue-next · cadence autoplay · end summary)

> **Status:** plan — ready for review. **New §T row** (T.12d) — needs `/spec` to add it; §10 lists the deltas. Do not edit SPEC inline.
> **Depends:** T.12c (combat VFX, ✅), T.12a/b (combat core + replay, ✅), T.23a (Prep view + shared board geometry, ✅), T.28a (`trait_synergies_panel`, ✅), T.41a (`game/describe.py` `render_item`, ✅) + T.41b (`render_trait`, ✅), UI-iconography (PR #58 — `iconography.py`, ✅). All deps built; nothing gates.
> **Resolves:** SPEC §D.28 (1) autoplay rework, (2) intra-tick reveal feel — folded into the cadence model; plus the combat-infocard parity gap noted in `docs/live/systems/ui.md`.
> **Design source of truth:**
> - SPEC §V.56 (combat view = pure presentation; **playback model — amended here**), §V.57 (resource truth = live replay), §V.39 (ticks↔seconds display-only), §V.54 (event stream taxonomy), §V.1 (`game/` Flet-free).
> - SPEC §D.28 (deferred combat-view polish — the "treat autoplay as a rewrite" directive + the manual-only intra-tick stagger).
> - Code: `src/ui/views/combat.py` (the view), `src/ui/views/prep.py` (the infocard + 3-column layout to mirror), `src/ui/combat_playback.py` (queue projection + steps), `src/game/combat/replay.py` (`PieceView`), `src/ui/components/iconography.py` (`inline_effect_text`, `role_glyph`, `trait_glyph`, `affinity_marker`), `src/game/describe.py` (`render_item`).
> **What this plan adds beyond those:** a **shared infocard core** (one identity-header + stat-grid + ability-blurb builder both Prep and Combat feed), `role`/`traits` surfaced on `PieceView`, a **fixed-cadence autoplay** (speed toggle, each tick = one Next-step so the existing reveal animation plays), a **future-only action queue** (hide resolved, highlight next), and a **per-champion end-summary overlay**.

---

## 0. Substep split — T.12d_a → T.12d_b

Split along a real seam: **static read surface** (a) vs **playback behaviour** (b). Each ships + tests independently; b builds on a but does not require it (the two touch different code regions of `combat.py`).

| Substep | Scope | Touches | Done when |
|---|---|---|---|
| **T.12d_a** — shared infocard + layout | Extract `infocard_core`; surface `role`+`traits` on `PieceView`; rebuild combat's inspect panel + the Prep-style 3-column layout (action-queue strip on top where Prep has the shop). | `ui/components/infocard.py` (new), `game/combat/replay.py`, `game/piece.py`, `game/loadout.py`, `ui/views/combat.py`, `ui/views/prep.py`, tests | Combat inspect renders role-glyph + trait glyphs + inline-iconed ability blurbs identical to Prep; both views call one core builder; layout mirrors Prep. |
| **T.12d_b** — autoplay + queue + end summary | Cadence autoplay (speed toggle, each tick = `_step(1)`); queue shows strictly-upcoming, highlights the **next** step; per-champion end-summary overlay. | `ui/views/combat.py`, `ui/combat_playback.py`, tests | Autoplay steps every 0.5 s at 1× reusing the Next animation; speed toggle 0.5×/1×/2×; queue hides resolved entries + flags the next; end overlay shows the per-champion damage table. |

**§V impact:** T.12d_a is additive/display (a light §V note that `PieceView.role`/`traits` are display-only identity, extending V.57). T.12d_b **amends V.56** (playback model: autoplay = fixed real-time cadence, not event-paced). Both land their own `/spec` deltas (§10).

---

## 1. Scope

**In scope**
- A reusable `infocard_core(info) -> list[ft.Control]` (identity header with role/affinity/trait glyphs + two-column stat grid + ability blurbs via `inline_effect_text`), consumed by Prep and Combat. Each view keeps its own extras (Prep: items/sell/level-line/shop-preview Buy; Combat: live current-HP/barrier, status rows, per-slot mana).
- `PieceView.role` + `PieceView.traits` (display-only identity), via a new `Piece.role` set in `compile_loadout`.
- Combat layout mirrors Prep: top bar → **action-queue strip** (where Prep has the shop) → 3-column body (left: weather/synergies/legend · center: board + controls · right: shared infocard).
- Autoplay rework: a fixed-cadence stepper that fires one `_step(1)` per tick (reusing the existing Next reveal animation), with a 0.5×/1×/2× speed toggle (1× = 0.5 s/step). Replaces `_autoplay_loop`/`_play_step` event-paced real-time pacing.
- Action queue: project **strictly upcoming** actions (drop anything at/before the resolved cursor tick) and visually flag the **next** step's action(s).
- End-of-fight overlay: per-champion damage-dealt/taken table + outcome + survivors + rounds/timed-out.

**Out of scope (why)**
- Sprite art for tokens (still affinity circle + initials) — D.27/D.28, art task.
- Per-tick timeline scheduler that interleaves move→cast→attack with independent dwell (the "ideal" D.28 (1) endgame) — the cadence-stepper reusing the proven Next animation is the pragmatic rewrite; a full scheduler is a later T.12e if still wanted.
- Any combat-math change — view stays pure presentation (V.56/V.57); the engine, recorder, and `resolve_combat` are untouched.
- New ability/trait/item authored text — consumes the existing `describe.py` / `ability_text.render_for` render-layer as-is.

---

## 2. The gap today

| Piece | Where (`file.py:line`) | State |
|---|---|---|
| Combat inspect panel built inline, separate from Prep | `ui/views/combat.py:735-826` (`_build_inspect`) | 🔴 drift — duplicates Prep's header/stat/ability render with a thinner result (plain `Text` abilities, no role/trait glyphs, no inline effect icons) |
| Prep infocard pieces | `ui/views/prep.py:836-936` (`_piece_icon_cluster`/`_champ_header`/`_stat_grid`/`_ability_block`) | ✅ rich (role glyph, trait glyphs, `inline_effect_text`) — the target to share |
| `PieceView` identity | `game/combat/replay.py:56-72` | 🔶 has `affinity`, no `role`/`traits` |
| `Piece` runtime | `game/piece.py:65` | 🔶 has `traits`, **no `role`** |
| Action queue projection | `ui/combat_playback.py:212-223` (`Playback.queue`) | 🔶 includes `tick >= now` (the current/just-resolved tick stays on the rail) |
| Queue chip "active" = resolving-now | `ui/views/combat.py:678-721` | 🔶 highlights the *current* tick; user wants the **next** highlighted, resolved hidden |
| Autoplay | `ui/views/combat.py:950-988` (`_autoplay_loop`/`_play_step`) + `combat_playback.py:107-118` (`playback_delay_s`) | 🔴 event-paced real-time; D.28 (1) flags "needs a full rework" — FX flash sub-frame, first step eats the 2.5 s clamp, no intra-tick stagger in autoplay |
| End panel | `ui/views/combat.py:829-854` (`_build_end_panel`) | 🔶 totals only; user wants a per-champion table |

---

## 3. Architecture

### 3.1 Shared infocard core (`ui/components/infocard.py`, new)

The two infocards are **not identical** — Prep shows a static sheet + economy controls; Combat shows live current HP/mana/statuses. The shareable seam is the **identity + stats + abilities core**; each view wraps it with its own extras.

**Input — a normalized struct** (so the core never imports `Champion`/`PieceView` directly):

```python
@dataclass(frozen=True, slots=True)
class PieceInfo:
    name: str
    affinity: WeatherState
    role: str
    traits: tuple[str, ...]
    # stat grid rows: (label, formatted_value) in display order
    primary_stats: tuple[tuple[str, str], ...]
    premium_stats: tuple[tuple[str, str], ...]
    # abilities: (section, ids) — rendered via ability_text.render_for against `stat_src`
    actives: tuple[str, ...]
    passive: str
    stat_src: Any          # exposes .stat(name) for render_for (Champion or _ViewStatSource)
    subtitle: str          # "affinity · role [code] · L/T" (Prep) or "affinity · enemy/ally · summon" (Combat)
```

**Core builder** (pure presentation; lives in `ui/`, V.1):

```python
def infocard_header(info) -> ft.Control       # role_glyph + name + affinity/trait cluster + subtitle
def infocard_stat_grid(info) -> ft.Control    # two columns of stat_glyph + label + value
def infocard_abilities(info) -> list[ft.Control]  # name + inline_effect_text(blurb) + formula
```

- Header reuses the existing helpers verbatim: `role_glyph` (`iconography.py:139`), `affinity_marker`, `trait_glyph` (the `_piece_icon_cluster` cluster, `prep.py:836`).
- Abilities reuse `render_for` (`game/ability_text.py`) + `inline_effect_text` (`iconography.py:218`) — this is exactly Prep's `_ability_block` (`prep.py:912-936`), lifted.
- Stat grid reuses `stat_glyph` (`iconography.py:157`) — exactly Prep's `_stat_row` (`prep.py:779`).

**Prep adapter** (`prep.py`): build `PieceInfo` from a `Champion` (role/traits/stats straight off the model; `stat_src = champ`, V.38). Replaces `_champ_header`/`_stat_grid`/`_ability_block` bodies with calls into the core; keeps `_traits_chips`, `_level_line`, `_item_chip`, Sell, shop-preview Buy as Prep-only wrappers around the core.

**Combat adapter** (`combat.py`): build `PieceInfo` from a `PieceView`. `name` from `name_by_id`; `role`/`traits` from `PieceView` (3.2); stats formatted from `pv.stats` (the existing `_fmt`/`primary`/`premium` lists, `combat.py:759-774`); abilities from `abilities_by_id`; `stat_src = _ViewStatSource(pv)` (`combat.py:248`). Combat keeps its live extras (current `HP/max_hp`, `barrier_total`, status rows, per-slot mana, the global Team/augments/synergies block) wrapping the core.

> **Wrinkle — items:** Prep shows equipped items with equip/unequip (economy). Combat currently lists item ids as plain text (`combat.py:799-802`). Keep items **view-specific** (not in the core): Combat renders them read-only via `render_item` chips (no click), Prep keeps the interactive `_item_chip`. The core is identity+stats+abilities only.

### 3.2 `PieceView.role` + `PieceView.traits`

- Add `role: str = ""` to `Piece` (`game/piece.py`); set it in `compile_loadout` at both build sites — champion path `loadout.py:158` (`role=champion.role`) and enemy path `loadout.py:194` (`role=enemy.role`). Pure data, never read by combat math (display-only; V.1 holds — no Flet).
- Surface on `PieceView` (`replay.py:56-72`): `role=piece.role`, `traits=tuple(piece.traits)`. `Piece.traits` already exists (`piece.py:65`) — champions carry base + emblem-granted traits (`loadout.py:133-135`), enemies empty. Combat's identity glyphs thus show the **fielded** trait set (incl. emblems) — a superset of Prep's base sheet, which is correct for an in-combat readout and still drift-safe (both go through `trait_glyph`).
- `_STAT_KEYS` unchanged; the two new fields are identity, not stats.

### 3.3 Cadence autoplay (T.12d_b)

Replace the event-paced `_autoplay_loop` + `_play_step` with a **fixed-cadence** loop that reuses the manual Next path:

```python
_AUTOPLAY_BASE_S = 0.5          # 1× cadence: one step every 0.5 s
_SPEED_FACTORS = {"0.5×": 2.0, "1×": 1.0, "2×": 0.5}  # multiplies the 0.5 s base

async def _autoplay_loop():
    while state["alive"] and state["playing"]:
        if state["cursor"] >= _last_cursor():
            state["playing"] = False; _sync_autoplay_btn(); _render(); break
        _step(1)                                  # the SAME Next path: advance + drip animation
        await asyncio.sleep(_AUTOPLAY_BASE_S * _SPEED_FACTORS[state["speed"]])
```

- Each tick = one `_step(1)` → reuses `_advance_to` + `_drip_action_beats` (`combat.py:899-936`), so the **intra-tick stagger animation now plays in autoplay too** — fixing D.28 (2) (stagger was manual-only) for free, because autoplay no longer takes a separate FX-skipping path.
- The `await sleep` is the dwell between steps; `_drip_action_beats` runs its own short beat-stagger inside the step. At 1× a multi-beat step may need > 0.5 s to finish its drip — guard by awaiting the drip task before sleeping (capture the `page.run_task` handle, or have `_step` expose the drip coroutine for autoplay to await), so a step never overlaps the next. Build detail: `_step` returns the drip task; autoplay `await`s it, then sleeps the cadence gap.
- `playback_delay_s` / `PLAYBACK_SPEED` / `PLAYBACK_MAX_DELAY_S` / `pre_beat_ticks` in `combat_playback.py` become dead for autoplay; keep `playback_delay_s` only if `_drip_action_beats`/DOT reveal still uses it, else remove (drift check in §6).
- **Determinism untouched (V.2/V.14):** cadence is wall-clock dwell over a deterministic replay; it changes *when* frames paint, never the sim. No RNG.
- Speed toggle = a 3-segment control writing `state["speed"]`; `state` already exists (`combat.py:319`). Adding `"speed": "1×"`.

### 3.4 Future-only queue + next highlight (T.12d_b)

- `Playback.queue(cursor)` (`combat_playback.py:212`): change `e.tick >= now` → `e.tick > now` so the **resolved** tick's entries drop off the rail as the cursor lands on them. (At `cursor = -1`/tick 0, `now = 0` → all real actions are `tick > 0`, so the opening rail is full.)
- "Next" = the entries of the **next step** (`playback.steps[cursor+1]`), i.e. the lowest upcoming action tick. The chip builder (`combat.py:678`) flags `active` when `e.tick == next_action_tick` instead of `== now`. Rename the visual intent from "resolving now" to "next up" (border + size bump on the next step's chips).
- `QUEUE_LOOKAHEAD_ROUNDS` (=2) and the round/sudden-death dividers (`combat.py:702-725`) are unchanged.

### 3.5 End-summary overlay (T.12d_b)

Extend `_build_end_panel` (`combat.py:829`). `BattleResult` already carries everything (verified `models.py:631-660`): `outcome`, `rounds`, `timed_out`, `surviving_team_ids`/`surviving_enemy_ids`, and **per-piece** `team_damage_dealt`/`team_damage_taken` (`dict[str,int]`).

- Banner: Victory/Defeat/Draw (existing colour logic).
- Line: `Survivors {n_team}/{n_enemy} · {rounds} rounds (· timed out)`.
- Per-champion table: one row per `c in session.team` — `name_by_id[c.id]` · `team_damage_dealt.get(c.id,0)` · `team_damage_taken.get(c.id,0)`. Sort by dealt desc. Monospace columns, `FONT_MONO`.
- Continue button → `on_exit(result)` (unchanged, V.64).
- Overlay stays `visible=False` until end (the existing hit-testing guard, `combat.py:349-355`, is load-bearing — keep it).

### 3.6 Layout mirror (T.12d_a)

Reshape `combat.py`'s assembly (`combat.py:1029-1050`) to mirror Prep (`prep.py:1094-1126`):

```
root → Column[ header,
               Divider,
               queue_strip,                 # where Prep has shop_holder
               Row[ left_col, center_col, right_col ] ]   (+ end_overlay in the Stack)
```

- `left_col` (≈250): weather badge (combat `session.weather`) + the team `trait_synergies_panel` (moved out of the right inspect) + the damage-type legend.
- `center_col` (expand): `board_container` + `controls_row` (Prev/Next/Autoplay+speed/End/Restart/Exit).
- `right_col` (≈320): the shared infocard (`_build_inspect` → core + combat extras).
- The queue strip keeps the fixed-width horizontal-scroll `queue_row` (`combat.py:339`) so it never reflows the board.
- `end_overlay` stays in a `Stack` over the body (`combat.py:1048`).

---

## 4. Decisions (proposals — overridable)

1. **`PieceView` gets role/traits via `Piece.role`** (not an in-view source-model lookup). Rationale: `PieceView` is *the* combat identity struct the view already trusts; a one-field `Piece.role` is cheaper than threading `enemy_by_id`/`champ_by_id` role/trait lookups through the adapter, and it gives summons/mid-fight spawns a role for free. The field is display-only (no engine read). *Alt considered:* assemble role/traits in-view from `session.team`/`enemies` — avoids touching `Piece`, but breaks for summons and re-introduces an id-lookup the struct exists to remove.
2. **Autoplay reuses the Next path, not a new scheduler.** The user's "press one forward every 0.5 s … might make the animation work" is exactly this: the manual Next animation is proven; autoplay just fires it on a clock. A full move→cast→attack timeline scheduler (D.28 (1) ideal) is deferred to a possible T.12e.
3. **Speed toggle 0.5×/1×/2×, default 1× = 0.5 s/step.** Per the chosen option. `state["speed"]`.
4. **Items stay view-specific, out of the shared core.** Combat shows read-only `render_item` chips; Prep keeps interactive equip/unequip. Core = identity+stats+abilities only (the genuinely-identical surface).
5. **Queue "next" = next *step*'s tick** (all beats sharing the lowest upcoming action tick highlight together), matching how a single Next press resolves one step.

---

## 5. Authored values
None — no new game numbers. UI constants only: `_AUTOPLAY_BASE_S = 0.5`, `_SPEED_FACTORS = {0.5×:2.0, 1×:1.0, 2×:0.5}` (first-pass, tunable).

---

## 6. Content / drift audit + reconciliation
- **`combat_playback` dead code:** after the cadence rework, audit `playback_delay_s`, `PLAYBACK_SPEED`, `PLAYBACK_MAX_DELAY_S`, `pre_beat_ticks`, `is_sudden_death` for live consumers (`grep`). Remove what only fed `_play_step`; keep what the DOT pre-beat drip still uses. A leftover unused pacing fn is drift — delete it in the same change.
- **`_build_inspect` duplication:** the whole point — combat's inline header/stat/ability render is deleted in favour of the core. Confirm no other caller depends on the removed private builders.
- **V-guard:** a test asserts Prep and Combat infocards go through the **same** `infocard_core` (import-level: both call `infocard_header`/`infocard_stat_grid`/`infocard_abilities`) so they can't re-drift. Plus a `PieceView.role`/`traits` round-trip test (champion role set, enemy role set, traits surfaced).

---

## 7. Open questions
**Resolved here (overridable):**
- Shared-core seam, autoplay-reuses-Next, speed toggle, items-out-of-core, queue-next-semantics, end-summary richness — all per §4 + the user's answers (shared core builder · per-champion table · speed toggle default 0.5 s).
- `Piece.role` added (vs in-view lookup) — §4 (1).

**Still open / deferred:**
- Full timeline/scheduler autoplay (independent per-piece dwell) — possible T.12e; not now.
- Sprite art (D.27/D.28).
- Whether the left-column synergies panel should collapse on narrow widths — defer to feel-test.

---

## 8. Test plan
- **`tests/ui/test_combat_playback.py`** — `queue()` excludes the resolved tick (`tick > now`); the opening rail (cursor −1) still lists all actions; the "next step tick" helper returns the lowest upcoming action tick.
- **`tests/game/test_replay.py`** (or combat) — `PieceView.role`/`traits` surface: a champion piece carries its `role` + base traits; an enemy piece carries its `role` + empty traits; a summon carries a role. `Piece.role` set by `compile_loadout`.
- **`tests/ui/test_components.py`** — `infocard_core` builders: `infocard_header` emits a `role_glyph` + affinity + trait glyphs for a sample `PieceInfo`; `infocard_abilities` routes blurbs through `inline_effect_text` (an effect keyword yields an icon run). Drift guard: Prep and Combat both import/call the core (no private re-implementation).
- **Determinism (V.2/V.14):** the cadence autoplay is wall-clock only — assert no `combat_playback`/replay output changes; existing engine sim tests stay byte-identical (autoplay is not in the sim path, so this is a no-op guard + a code-review check that no RNG/seed entered the view).
- **Regression:** full `pytest` green; combat-log golden snapshots untouched (no recorder change).

## 9. Acceptance criteria
**T.12d_a**
1. Combat inspect panel renders role glyph + affinity + trait glyphs + two-column stat grid + ability blurbs with inline effect icons — visually matching Prep.
2. Prep and Combat both build their infocard via `infocard_core` (one builder; no duplicated header/stat/ability code).
3. `PieceView` exposes `role` + `traits`; `Piece.role` set in `compile_loadout` (champion + enemy).
4. Combat layout: top bar → action-queue strip → 3-column body (weather/synergies/legend · board+controls · infocard). `pytest` green.

**T.12d_b**
5. Autoplay advances one step per cadence tick reusing the Next reveal animation (FX play); 0.5×/1×/2× toggle, 1× = 0.5 s/step; a step never overlaps the next (drip awaited).
6. Action queue shows only strictly-upcoming actions (resolved entries drop off) and highlights the next step's action(s).
7. Fight-over overlay shows outcome + survivors + rounds/timed-out + a per-champion damage-dealt/taken table; Continue fires `on_exit(result)`.
8. `pytest` green; sims byte-identical; `combat_playback` dead pacing code removed.

---

## 10. SPEC changes needed (the `/spec` payload — apply on user OK only)

**New §T rows**
- `T.12d_a | . | Combat-view shared infocard + layout — extract infocard_core (identity header + stat grid + inline-iconed ability blurbs) shared by Prep + Combat; surface role/traits on PieceView (Piece.role via compile_loadout); combat layout mirrors Prep (action-queue strip on top, 3-column body) | ui/components/infocard.py, game/combat/replay.py, game/piece.py, game/loadout.py, ui/views/combat.py, ui/views/prep.py, docs/live/systems/ui.md, tests/ui/test_components.py, tests/game/test_replay.py, docs/design/tasks/t12d_combat_view_rework_plan.md | T.12c, T.23a, T.41 | M | .`
- `T.12d_b | . | Combat-view autoplay + queue + end summary — fixed-cadence autoplay (speed toggle 0.5×/1×/2×, each tick = one Next-step, reuses reveal animation); action queue future-only + next-highlight; per-champion end-summary overlay | ui/views/combat.py, ui/combat_playback.py, docs/live/systems/ui.md, tests/ui/test_combat_playback.py | T.12d_a | M | .`

**§V amendments**
- **Amend V.56** — soften "Playback is event-paced … not tick=second real-time" to: *manual event-step is the default; **autoplay is a fixed real-time cadence** (one Step per tick at a user-set speed, reusing the Next reveal animation) — wall-clock dwell over the deterministic replay, never feeding the sim (V.2/V.14). `TICKS_PER_SECOND` (V.39) stays display-only.* (Reason: the event-paced real-time loop was illegible — D.28 (1).)
- **New V.82 (next free — verify)** — *`PieceView.role`/`PieceView.traits` are display-only identity surfaced from `Piece` (role set in `compile_loadout`, traits = fielded set incl. emblems); never read by combat math. The combat and Prep infocards render through one shared `ui/components/infocard.py` core (identity header + stat grid + ability blurbs) — neither view re-implements it. Extends V.56/V.57/V.1; guarded by `tests/ui/test_components.py` + `tests/game/test_replay.py`.*

**§B**
- None (no bug — this is the planned D.28 polish). If the autoplay-overlap (drip vs cadence) surfaces a real defect during build, `/spec bug:` it then.

**§D**
- **D.28** → mark (1) autoplay + (2) intra-tick stagger **RESOLVED [date] (T.12d)**; leave (3) sprite art / full scheduler deferred (note the timeline-scheduler ideal as a possible T.12e).

**Implementation Order** — place T.12d_a then T.12d_b after T.12c in the combat-view chain.

**§11 LIVING docs to update on build**
- `docs/live/systems/ui.md` — replace the combat-infocard-gap note with the shared-`infocard_core` taxonomy; document the cadence autoplay + future-only queue + end-summary; flip any 🔶.

---

## Handoff
1. `/spec` to apply the §10 deltas (add T.12d_a/_b rows, amend V.56, add V.82, update D.28).
2. `/build §T.12d_a` then `/build §T.12d_b`.

---

## Build addendum — T.12d_b (2026-06-29), two operator-requested folds

Built T.12d_b with two requirements folded in beyond §3.3/§3.4 (operator playtest
of the T.12d_a build):

1. **Sequential, animation-gated intra-tick reveal (refines §3.3).** Rather than the
   autoplay cadence merely *reusing* the Next reveal, the **single** `_drip_action_beats`
   path (manual + autoplay) now reveals a tick's beats **one at a time in recorded
   order, each given its animation window before the next** — the engine resolves a
   tick's actions sequentially, so the view plays them the same way (*A moves → B moves
   → A attacks → B casts*). Constants: `_BEAT_GAP_S = 0.18` (intra-tick), `_TICK_GAP_S =
   0.40` (inter-tick dwell), `_TWEEN_MS = 180` (was 250, so the glide finishes inside the
   beat gap); both gaps scaled by `_SPEED_FACTORS` (the §3.3 speed toggle). The old
   event-paced `_play_step` + the B.35 `_ACTION_DWELL_S` band-aid are **deleted** — one
   reveal path now, closing D.28 (1)+(2) together.
2. **Death linger (new — not in original §3.x).** On a piece's death beat the token
   turns into a **grayed body** (`_token(dead=True)`) and **stays on the board through
   the rest of that tick's beats**, removed only when the cursor leaves the tick — so a
   later same-tick hit lands on a visible body instead of an empty cell (the old
   immediate-vanish let FX paint on nothing). Decision rule extracted to the pure,
   unit-tested `_death_markers(step, reveal_n, action_shown)`.

**Queue:** `Playback.queue` → `tick > now` (strictly upcoming) + `next_action_tick`;
chips highlight the **next** step ("next up"), not the resolved tick. **End panel:**
per-champion damage table (dealt/taken, sorted, dead marked `✕`) + rounds line.
**Determinism:** all wall-clock/render only — sims byte-identical (1533 tests pass).
No §B (planned polish; the death-vanish was a known cosmetic gap, not a regression).
`combat_playback` dead pacing (`playback_delay_s`/`PLAYBACK_SPEED`/`PLAYBACK_MAX_DELAY_S`)
removed; `pre_beat_ticks` kept (still groups interstitial DOTs).
