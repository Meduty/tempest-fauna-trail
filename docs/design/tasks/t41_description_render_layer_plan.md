# T.41 Plan — Shared description render-layer (traits · items · augments)

> **Status:** plan — ready for review. **New §T row** (T.41, split T.41a/T.41b) — not yet in SPEC §T.
> **Depends:** PR #56 (`polish/prep-ux-traits-items`) — provides `ui/components/trait_synergies.py::trait_synergies_panel`, `TraitPreview.thresholds`/`active`, and `prep._item_kind`/`_item_label` (the stopgap this task replaces). **Unmerged at plan time** — gates the UI-consumer half (the panels that render the blurbs). The pure render core + metas can be built before merge; wiring lands after.
> **Resolves:** the deferred "B" follow-up from the 2026-06-26 polish session (`docs/journal/2026-06-26_prep_ux_polish.md`); memory `render-layer-followup`.

**Design source-of-truth (FROZEN — transcribe, verify against code):**
- `docs/design/content/item_catalog.md` — every item's **Name** + one-line description (components + 36 combined + emblems + special).
- `docs/design/content/trait_catalog.md` (v2.1) — every trait's per-breakpoint **concept** descriptions (`@2 — HP + slow regen`, …) + flavor.
- `docs/design/content/augment_catalog.md` — augment names + blurbs (**already in code**, see §2).
- **Pattern to mirror:** `src/game/ability_text.py` (`render`/`render_for` → `RenderedAbility`) + `registries.py::AbilityMeta` (`registries.py:502`).

**What this plan adds beyond the catalogs:** the catalogs hold the *words*; this task builds the **structured code metadata + one pure render path** that surfaces them in-game, with the stat lines **auto-derived from the live numbers** (not re-typed) so text can't drift from balance.

---

## 0. Substep split (T.41a → T.41b)

Real seam: **static items (simplest, self-contained)** vs **per-breakpoint traits (the big transcription)**. Each ships + tests independently.

- **T.41a — render core + items.** Shared `RenderedEntry` + a pure `describe` module (stat-line derivation helper), `ITEM_META`, and the Prep item-chip consumer. Items are champion-independent and already half-described (docstrings), so this proves the path end-to-end on the smaller surface.
- **T.41b — traits.** `TRAIT_META` (name/blurb + per-breakpoint text), capture of each rung's `muls`/`adds` for the auto-derived stat line, and the `trait_synergies_panel` tooltip consumer (Prep + Combat). Depends on T.41a's render core.
- **Augments:** **no new substep.** They already carry `name`+`blurb` (`Augment`, `registries`/`augments.py`). T.41a adds only a thin adapter so the augments panel can render through the same `RenderedEntry` shape if desired (overridable — see §7).

## 1. Scope

**In scope:**
- T.41a: `src/game/describe.py` (new — `RenderedEntry`, `stat_line`, `render_item`), `src/game/items/meta.py` (new — `ITEM_META`), wire `ui/views/prep.py::_item_chip`, tests.
- T.41b: extend `src/game/traits/_packs.py::define_trait` to capture meta + raw muls/adds; `src/game/traits/meta.py` or inline `TRAIT_META`; `src/game/trait_text.py` (or `describe.render_trait`); wire `ui/components/trait_synergies.py` tooltips; tests.

**Out of scope (why):**
- **Refactoring `ability_text.py`** to share `RenderedEntry` — the ability system works and is caster-scaled (needs live `Magnitude` terms); folding it in risks churn for no user gain. T.41 mirrors its *shape*, doesn't merge it. (Possible later cleanup, §7.)
- **Live-number term rendering for items/traits** — they're champion-independent (fixed %); static text + auto-derived stat line suffices (operator decision). No `Magnitude` machinery here.
- **A full item/trait "codex" view** — this task feeds the *existing* tooltips/chips, not a new screen.
- **Augment re-authoring** — already done.

## 2. The gap today

| Piece | `file.py:line` | State |
|---|---|---|
| Ability render (pattern) | `ability_text.py:56,83`; `registries.py:502` (`AbilityMeta`), `:544` (`ABILITY_META`) | ✅ the model |
| Augment name/blurb | `augments.py:73-82` (`Augment.name`/`.blurb`), `:106` (`register_augment`) | ✅ exists; panel renders it (`prep.py::_build_augments`) |
| Item registry | `registries.py:150` (`register_item`), `:27` (`ITEM_REGISTRY`, 50 ids) | 🔶 factory-only — **no name/blurb**; each factory has a **docstring** (`items/combined.py` `"""Fang — +12% Strength."""`) |
| `ITEM_META` | — | ❌ does not exist |
| Item-chip text | `prep.py::_item_label` (Title-case stopgap), `_item_kind` (PR #56) | 🔶 stopgap — `witherbloom_censer` → "Witherbloom Censer", no blurb |
| Trait registry | `registries.py:158` (`register_trait`), `:35` (`TRAIT_REGISTRY`, 25 ids); `traits/_packs.py:52` (`define_trait`) | 🔶 breakpoint factory-only — **no name/blurb/per-rung text**; rung `muls`/`adds` consumed into a closure (`_packs.py:70`) and discarded |
| `TRAIT_META` | — | ❌ does not exist |
| Trait tooltip | `trait_synergies.py` (numeric ladder only, PR #56) | 🔶 numbers, no effect text |
| Shared `RenderedEntry` | — | ❌ — `RenderedAbility` (`ability_text.py:36`) is the same shape but ability-bound |

## 3. Architecture

### 3.1 Shared render core — `src/game/describe.py` (T.41a, pure, V.1)
- `@dataclass(frozen=True) RenderedEntry(name: str, text: str, stat_line: str = "", tags: tuple[str,...] = ())` — mirrors `RenderedAbility(name,text,formula,tags)` (`ability_text.py:36`) but `stat_line` replaces `formula` (no caster source). One shape consumed by all UI panels.
- `stat_line(muls: dict[str,float], adds: dict[str,float]) -> str` — "+8% STR, +8% AS" from the same `{stat: pct}` dicts traits/items already hold. Reuse the canonical short-label map (`registries.py:222` `_STAT_ALIASES`/`_short`, or the prep `_MOD_FIELDS` order — pick one, §4) so labels match the rest of the UI. Pure, deterministic, no RNG.

### 3.2 Items — `ITEM_META` + `render_item` (T.41a)
- `src/game/items/meta.py`: `ITEM_META: dict[str, ItemMeta]` where `ItemMeta(name: str, blurb: str)`. **Transcribed from `item_catalog.md`** (50 entries). Name = catalog name (`Fang`, `Apex Fang`, `Huntress Talon`); blurb = catalog description column.
- `describe.render_item(item_id, *, derive_stats=True) -> RenderedEntry | None`: look up `ITEM_META`; for the stat line, **introspect the registered factory's `EffectBundle`** — call `ITEM_REGISTRY[id](_NullOwner)` and read `modifiers` (`mod.stat`, `mod.op`, `mod.value`) → "+12% STR". Components (flat mul bundles) derive cleanly; combined items with hooks fall back to the authored blurb for the mechanic part. **Wrinkle:** a few combined factories apply context hooks (`items/combined.py:170+` `apex_fang`) — the bundle still carries the headline mul, so the stat line derives; the hook prose comes from `blurb`. No factory has side effects on a null owner (verify in build — they only build modifiers).
- **Consumer:** `prep.py::_item_chip` — replace `_item_label(item_id)` with `render_item(id).name`; chip tooltip gains the blurb + derived stat line (alongside the PR #56 kind line). Keep `_item_kind` (PR #56) — orthogonal.

### 3.3 Traits — `TRAIT_META` + `render_trait` (T.41b)
- Extend `define_trait` (`_packs.py:52`) to **also** capture per-trait `name`/`blurb` and **per-rung `text`** + retain the raw `muls`/`adds` (today bound into `_factory` and lost). Two clean options (§4): (a) widen the rung tuple to carry an optional description, or (b) a parallel `TRAIT_META` authored dict keyed by `(trait_id)` with a list of `BreakpointMeta(count, text)`. **Proposal: (a)+capture** — keep description co-located with the rung that owns it (maintainability), and store `muls`/`adds` on a `TraitBreakpoint`-parallel meta for the derived stat line.
- `TraitMeta(name: str, blurb: str, rungs: tuple[BreakpointMeta, ...])`, `BreakpointMeta(count: int|str, text: str, muls: dict, adds: dict)`. `count` mirrors the breakpoint (`int` or `"full"` for dynamic, `_packs.py:66`).
- `describe.render_trait(trait_id) -> RenderedTraitDoc` (name/blurb + per-rung `RenderedEntry`): each rung's `text` = authored prose; `stat_line` = `stat_line(muls, adds)` auto-derived. Mechanic riders (kiting/echo/…) stay as authored prose (no introspectable name — confirmed PR #56: `HookBuilder` is an opaque closure).
- **Consumer:** `trait_synergies.py::trait_synergies_panel` — the per-trait tooltip gains the trait blurb + the **cleared rung's** effect text + derived stat line; dormant rungs can list the next rung's text ("@4: …"). Used by Prep + Combat (one component, both views).

### 3.4 Determinism + purity
All of `describe`/`*_META` is pure data + pure functions in `game/` (V.1: no Flet; V.2: no RNG, no I/O). Zero combat impact — presentation only. Factory introspection for stat lines uses a null/stub owner and reads modifiers; it must not mutate combat state (verify the called factories are side-effect-free on build, §8).

## 4. Decisions

- **`RenderedEntry` is new, not a refactor of `RenderedAbility`.** Same shape, different module; avoids touching the working caster-scaled ability path. (Overridable → §7.)
- **Stat-line label source = the canonical `registries._short`/`_STAT_ALIASES` map** (`registries.py:222`), so item/trait/ability stat labels read identically. (Alternative: prep `_MOD_FIELDS` — but that's UI-local; prefer the game-layer canonical.)
- **Trait meta co-located in `define_trait`** (widen the rung), not a detached dict — the description lives with the numbers it describes, so a balance edit and its prose move together (drift-resistant, maintainable — the operator's stated value).
- **Stat line auto-derived, prose authored.** The % numbers are never re-typed; only mechanic/flavor prose is transcribed from the catalog.
- **Catalog is FROZEN source; code META becomes LIVING truth.** Transcribe once; thereafter `*_META` is the source of truth and the catalog stays a dated snapshot (standard LIVING/FROZEN rule). A V-guard (below) keeps META complete; balance retunes edit META, not the catalog.

## 5. Authored values

No new numbers — all stat magnitudes already exist (item bundles, trait `muls`/`adds`). The only authored content is **transcribed prose**: 50 item name+blurb pairs (`item_catalog.md`) and 25 trait name+blurb + ~80–100 per-breakpoint descriptions (`trait_catalog.md`). Counts to verify at build: `len(ITEM_REGISTRY)==50`, `len(TRAIT_REGISTRY)==25`, breakpoint count per trait matches `factory()` length.

## 6. Content / roster audit + reconciliation

- **Item id ↔ catalog name drift.** `item_catalog.md` names must map 1:1 onto `ITEM_REGISTRY` ids (`fang`→"Fang", `apex_fang`→"Apex Fang", `huntress_talon`→"Huntress Talon"). Build step: diff catalog rows against `ITEM_REGISTRY` keys; any id without a catalog row (or vice-versa) is reconciled in-task. Guard: V-A (below).
- **Trait breakpoint count drift.** `trait_catalog.md` lists each trait's rung counts (`@2/3/4/6/8`); these must match `factory()` breakpoint counts in code. Diff during transcription; guard: V-B asserts every `TRAIT_REGISTRY` trait has a `TRAIT_META` rung per actual breakpoint.
- **Emblem/special items** (`emblem_beast`, `spirit_gem`, run-action specials) — confirm they have catalog entries; if the catalog omits a code id, author a minimal blurb in-task and note it (catalog stays frozen).

## 7. Open questions

**Resolved here (proposals, overridable):**
- New `RenderedEntry` rather than generalizing `RenderedAbility` (§4). If you'd rather one shape across all four, T.41a can lift `RenderedAbility`→`RenderedEntry` and alias — more churn, flagged.
- Augments get only a thin adapter (`render_augment(id)` wrapping the existing `Augment.name/.blurb` into `RenderedEntry`); no re-authoring. Skippable if the augments panel stays as-is.
- Co-locate trait meta in `define_trait` (vs detached dict).

**Still open / deferred:**
- Whether a future cleanup unifies `ability_text` onto `RenderedEntry` (out of scope here).
- A dedicated item/trait codex screen (not this task).

## 8. Test plan

- **Completeness (V-guards):** `set(ITEM_REGISTRY) == set(ITEM_META)` (T.41a); every `TRAIT_REGISTRY` id has `TRAIT_META` with one rung-meta per actual breakpoint count (T.41b).
- **Counts:** `len(ITEM_META)==50`, trait rung-meta counts match `factory()`.
- **Stat-line derivation:** `stat_line({"strength":0.08,"attack_speed":0.08}, {})=="+8% STR, +8% AS"`; item `render_item("fang").stat_line=="+12% STR"` (introspected from the bundle = matches the modifier exactly → can't drift).
- **Purity/determinism (V.1/V.2):** `render_item`/`render_trait` are pure — same output twice; no Flet import in `describe`/`*_meta` (grep guard); factory introspection mutates nothing (assert combat unaffected — a sim snapshot stays byte-identical, `workers=1`).
- **Regression:** full suite green; the PR #56 panels still build (import smoke test for prep/combat/trait_synergies).
- **No live-number claim:** assert item/trait stat lines are champion-independent (same text regardless of any source).

## 9. Acceptance criteria

**T.41a:**
1. `src/game/describe.py` exports `RenderedEntry` + `stat_line` + `render_item`; pure, Flet-free.
2. `ITEM_META` covers all 50 `ITEM_REGISTRY` ids (V-A test passes); names/blurbs transcribed from `item_catalog.md`.
3. Prep item chips show the catalog **name** (not the Title-case stopgap) + a tooltip with blurb + derived stat line; `_item_kind` markers (PR #56) retained.
4. Full suite green; new tests cover completeness + derivation + purity.

**T.41b:**
5. `define_trait` captures name/blurb + per-rung text + raw muls/adds; `TRAIT_META` covers all 25 traits (V-B test passes).
6. `render_trait` returns name/blurb + per-breakpoint effect text + auto-derived stat line.
7. `trait_synergies_panel` tooltips (Prep **and** Combat) show the cleared rung's effect text; numbers match `preview_team_traits`.
8. Full suite green; determinism snapshot byte-identical.

## 10. SPEC changes needed (for `/spec`)

- **§T rows:**
  - `T.41a | Description render core + item metadata — `describe.py` (`RenderedEntry`, `stat_line`, `render_item`) + `items/meta.py` (`ITEM_META`, 50 from item_catalog) + Prep item-chip wiring; `docs/design/tasks/t41_description_render_layer_plan.md` | Depends T.29a, T.40 (PR #56) | M | 📋 Plan`
  - `T.41b | Trait description metadata — `define_trait` meta capture + `TRAIT_META` (25 traits, per-breakpoint text from trait_catalog) + `render_trait` + `trait_synergies_panel` tooltip wiring; same plan doc | Depends T.41a, T.28 | M | 📋 Plan`
- **New §V invariants:**
  - **V-A (T.41a):** every `ITEM_REGISTRY` id has an `ITEM_META(name, blurb)` entry — no item renders as a bare id. Stat line is **introspected from the item's `EffectBundle`** (never re-typed), so it can't drift from the modifier. Guard test: `set(ITEM_REGISTRY)==set(ITEM_META)`.
  - **V-B (T.41b):** every `TRAIT_REGISTRY` trait has `TRAIT_META` with one breakpoint description per actual `factory()` breakpoint; the stat line derives from the rung's `muls`/`adds` (same source the bundle uses). Guards trait-text ↔ breakpoint-count drift.
  - **V-C (both):** the description layer is **pure presentation** — `game/describe.py` + `*_meta` have zero Flet imports and no RNG/I/O (extends V.1/V.2); rendering a description never mutates combat state.
- **§B:** none (no bug — net-new layer).
- **§D:** if a "unify ability_text onto the shared render shape" item is wanted, add it as a deferred §D note; otherwise none.
- **Implementation Order:** after T.40; T.41a before T.41b.

## 11. LIVING docs to update (on build/landing)

- `docs/live/content/items.md` — add the `ITEM_META`/`render_item` description path (where item names/blurbs now live).
- `docs/live/content/traits.md` — add `TRAIT_META`/`render_trait` + the per-breakpoint description model.
- `docs/live/systems/ui.md` — update the Prep item-chip + trait-tooltip lines (PR #56 entries) to cite the rendered name/blurb instead of the `_item_label` stopgap / numeric-only tooltip.
- New `docs/live/systems/` note (or extend an existing one) for the shared `describe.py` render core; flip any 🔶 once true.
