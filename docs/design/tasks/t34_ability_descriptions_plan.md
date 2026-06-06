# T.34 Plan — Ability description / tooltip system

> **Status:** plan — approved; `/spec` applied. Three new §T rows **T.34a/T.34b/T.34c** + invariants **V.38** (meta coverage / source-of-truth B) and **V.39** (`100 ticks = 1s` display convention) are in SPEC. Next: `/build §T.34a`.
> **Depends:** T.20 (ability framework — registries, `_eval_scaling`; done), T.30 (all 276 roster handlers exist + V.15 resolution guarantee; done), T.32/T.33 (stat axes + `compute_stat`; done). All deps built — no unbuilt gate.
> **Resolves:** net-new presentation layer. Touches no open §D row directly; adjacent to D.17 (UI polish) but independent.
> **Design source of truth:** no design-doc exists for this — it is presentation metadata over the kits frozen in `docs/design/content/ABILITY_CATALOG_CHAMPIONS.md` / `ABILITY_CATALOG_ENEMIES.md` and the live framework doc `docs/live/content/abilities.md` + `docs/live/systems/effects.md`. The handlers in `src/game/abilities/{champions,enemies,bosses}.py` are the behavioural ground truth this plan describes.
> **What this plan adds beyond those:** a structured `AbilityMeta` record per roster ability id (champions + enemies + bosses, 276 total), a pure renderer producing `RenderedAbility(name, text, formula, tags)` that resolves live numbers against either a base `Champion` (roster tooltips) or a live `Piece` (in-combat tooltips), a `Champion.stat()` adapter, and a CI drift-guard (every in-scope roster id has a meta; golden snapshot of rendered formulas).

---

## 0. Substep split (`T.34a → T.34b → T.34c`)

Real seam = the three `abilities/{champions,enemies,bosses}.py` files. Each ships + tests independently; `b`/`c` reuse every type/renderer/test-harness from `a`.

| Substep | Scope | Files | Done when |
|---|---|---|---|
| **T.34a** | Meta types + renderer + `Champion.stat()` adapter + **all 120 champion** metas; champion handlers refactored to read primary numbers from terms (source-of-truth B); §V drift-guard + golden snapshot for champions. | `game/ability_text.py` (new), `game/registries.py` (types), `game/models.py` (`Champion.stat`), `game/abilities/champions.py`, `tests/game/test_ability_text.py` (new) | All 120 champion ids render; champion sims byte-identical; guard + snapshot green. |
| **T.34b** | **All 120 enemy** metas + `Enemy.stat()`; enemy handlers refactored to read terms; drift-guard extended to enemy ids; snapshot extended. | `game/abilities/enemies.py`, `game/models.py`, `tests/game/test_ability_text.py` | All 240 champion+enemy ids render; full sims byte-identical; guard covers both rosters. |
| **T.34c** | **All 36 boss** metas (6 bosses × 6 id fields: `phase1_active`/`phase1_passive`/`phase1_phase_hook`/`phase2_active`/`phase2_passive`/`on_death_hook`); boss damage/heal handlers read terms; guard + snapshot extended to all **276** roster ids; boss tooltips render against the **compiled boss `Piece`** (no draft sheet → no `BossDef.stat()` needed). | `game/abilities/bosses.py`, `tests/game/test_ability_text.py` | All 276 ids render; boss + full sims byte-identical; guard covers all three rosters. |

`b` depends on `a`; `c` depends on `a` (types + renderer land in `a`).

## 1. Scope

**In scope (T.34a + b + c):**
- `AbilityMeta`, `ScalingTerm`, `Clause`, `RenderedAbility` dataclasses (pure, in `game/`).
- A `render(meta, source) -> RenderedAbility` function — `source` is anything exposing `.stat(name) -> float` (live `Piece` **or** base `Champion` via the new adapter).
- `ABILITY_META: dict[str, AbilityMeta]` parallel to `ABILITY_REGISTRY`/`PASSIVE_REGISTRY`, keyed by the same roster ability-id strings.
- One meta per **champion** (120 ids, T.34a), **enemy** (120 ids, T.34b), and **boss** (36 ids = 6 bosses × 6 fields, T.34c) roster ability/passive id → **276** total.
- Source-of-truth **B**: champion + enemy + boss handlers read their **primary** damage/heal constants from the term objects (no duplicated magic numbers for the headline number).
- `Champion.stat(name)` / `Enemy.stat(name)` adapters (plain field lookup, no modifiers) so roster-context numbers aren't zeroed. Bosses render against the compiled boss `Piece` (no draft sheet), so no `BossDef.stat()`.
- CI drift-guard (§V) + golden snapshot test of every rendered formula.

**Out of scope (with why):**
- **Shared/test handlers** in `reference.py` (`smash`, `cone_aoe`, `static_buildup`, `phase_hook_test`, `heal_pulse`, `sunlit_vigor`) → only meta'd if a champion/enemy/boss def actually references that id (then it gets one shared meta, see §3). Pure test scaffolding ids get no meta and are excluded from the guard.
- **Flet UI wiring** (champion-card hover, combat tooltip widgets) → consumes `render()`; belongs to the UI task batch (T.8-T.15/T.23), not here. This task delivers the pure data + renderer only (V.1).
- **JSON export** of all metas → explicitly dropped by the user (contexts 1+2 only). The data is trivially serializable later if wanted.
- **i18n / localization** → English strings inline; no string-table layer.

## 2. The gap today

| Piece | Where (`file.py:line`) | State |
|---|---|---|
| Ability handlers (240 roster ids) | `abilities/champions.py`, `abilities/enemies.py` | ✅ exist (T.30), behaviour is ground truth |
| Numbers as literals in handlers | e.g. `champions.py:52` `_eval_scaling(40.0, "intelligence*2.5", actor)` | 🔶 trapped in code — no tooltip can read them |
| `_eval_scaling(base, scaling, actor)` | `registries.py:129` | ✅ reusable; guards `hasattr(actor,"stat")` → **0 contribution if source lacks `.stat()`** |
| `Piece.stat(name)` | `piece.py:87` → `compute_stat` (`effects.py:61`) | ✅ live-combat source works |
| `Champion.stat(name)` | `models.py` Champion (after `:93`) | ❌ **absent** — roster-context render would zero every scaling term |
| `AbilityMeta` / renderer | — | ❌ does not exist |
| Drift guard (id→meta) | `tests/game/test_ability_catalog.py` (V.15 id→handler guard exists) | 🔶 analogous guard exists for handlers; none for metas |
| Description text | `ABILITY_CATALOG_*.md` (frozen lore) | 🔶 prose lore exists but un-templated, no live numbers, not code-reachable |

## 3. Architecture

### 3.1 Data types (in `registries.py`, beside the registries they parallel)

Verified against real stat keys (`intelligence`/`strength`/`armor`/`resistance`/`attack_speed`/`move_speed`/`mana_regen`/`max_hp`/`attack_range`/`penetration`/`penetration_pct` — all `Champion`/`Piece` fields; `_STAT_ALIASES` in `registries.py:138` maps `int→intelligence` etc.):

```python
@dataclass(frozen=True)
class ScalingTerm:
    label: str           # "damage" | "heal" | "shield" | "bonus" ...
    base: float          # the literal the handler used (e.g. 40.0)
    scaling: str = ""    # _eval_scaling expr, e.g. "intelligence*2.5"
    note: str = ""       # optional ("per hit", "to each enemy in radius 2")
    def eval(self, source) -> float:        # reuses the engine's evaluator
        return _eval_scaling(self.base, self.scaling, source)

@dataclass(frozen=True)
class Clause:
    text: str            # conditional/static prose, e.g. "+50% vs targets below 30% HP"

@dataclass(frozen=True)
class AbilityMeta:
    name: str                          # "Blink Execute"
    kind: str                          # "active" | "passive"
    blurb: str                         # prose w/ {token} slots = ScalingTerm.labels
    terms: tuple[ScalingTerm, ...] = ()
    clauses: tuple[Clause, ...] = ()
    tags: tuple[str, ...] = ()         # ("heal",) / ("aoe","stun") — UI iconography

ABILITY_META: dict[str, AbilityMeta] = {}   # keyed by roster ability-id string
```

### 3.2 Renderer (new pure module `game/ability_text.py`)

```python
@dataclass(frozen=True)
class RenderedAbility:
    name: str
    text: str        # blurb with {tokens} replaced by rounded live numbers
    formula: str     # "267 = 80 + INT×2.2  (INT 85)" — separate field, multiline-joinable
    tags: tuple[str, ...]

def render(meta: AbilityMeta, source) -> RenderedAbility: ...
def render_for(ability_id: str, source) -> RenderedAbility | None:   # dict lookup + render
```

- `source` is **structurally typed**: any object with `.stat(name) -> float`. Live `Piece` (combat) and base `Champion` (roster) both satisfy it after §3.3. This is the single mechanism that serves both UI contexts with one call — no context flag.
- `text`: each `{label}` token in `blurb` is replaced by `round(term.eval(source))`. Clauses are appended as separate sentences (UI may join with newlines / bullet them).
- `formula`: one line per term — `"{value} = {base} + {STAT}×{coeff} (STAT {statval})"`, pretty-printing the `scaling` string (split on `_eval_scaling`'s own `+`/`*` grammar, alias stats to UPPER short names via the existing `_STAT_ALIASES` inverse). Rounding identical to `text` so the two never disagree.
- **Durations/cadence → seconds (V.39):** `ability_text.py` defines the canonical `TICKS_PER_SECOND = 100`. Any tick value surfaced in a `blurb`/`Clause` (status duration, periodic cadence) is rendered as `ticks / 100` s — `root 200t → "2s"`, `every 600t → "every 6s"`. A `ticks_to_s(n)` helper formats it (trims trailing `.0`). Code/handlers stay in ticks; this is the sole conversion point. (`ui/` imports `TICKS_PER_SECOND` from here.)
- **No Flet, no I/O** → upholds V.1. Imports only `_eval_scaling`/types from `registries`.

### 3.3 `Champion.stat()` adapter (`models.py`)

`compute_stat` (`effects.py:61`) reads `Piece.base_stats` + modifier list — **not** available on `Champion`. So add a minimal field-lookup:

```python
def stat(self, stat_name: str) -> float:        # on Champion
    return float(getattr(self, stat_name, 0.0))
```

Returns the **base level-1 sheet** value (no combat modifiers) — exactly what a roster/draft tooltip should show. Matches `_eval_scaling`'s `actor.stat(...)` call site (`registries.py:163`). Unknown key → `0.0` (mirrors `_eval_scaling`'s silent-zero for typos). Apply the same to `Enemy` (T.34b) for enemy roster-context parity.

### 3.4 Source-of-truth B — handler refactor

Today: `amount = _eval_scaling(40.0, "intelligence*2.5", actor)`. After:

```python
DAWNWISP_HEAL = ScalingTerm("heal", 40.0, "intelligence*2.5")
# handler:
amount = DAWNWISP_HEAL.eval(actor)
# meta:
AbilityMeta(name="Knit Wound", kind="active",
    blurb="Heal the lowest-HP ally for {heal}.",
    terms=(DAWNWISP_HEAL,), tags=("heal",))
```

The term object is the **single** home of `40.0`/`"intelligence*2.5"`; handler and tooltip both read it → cannot drift. **Determinism guarantee:** `ScalingTerm.eval` calls the *same* `_eval_scaling` with the *same* base+string, so the float is bit-identical to today → sims stay byte-identical (regression-guarded, §8).

### 3.4.1 Fidelity policy — Tier-A vs Tier-B per ability

Not every magic number becomes a term. Two tiers:

- **Tier-A (term-driven):** the **headline** damage/heal/shield number(s) — every `_eval_scaling(...)` and direct `owner.stat(x)*k` damage/heal outlet. These move into `terms` and the handler reads them. ~70% of abilities are wholly this (deal/heal X [+ stat]).
- **Tier-B (descriptive `Clause`, handler keeps constant):** secondary/structural constants that don't fit a single number tooltip cleanly — conditional multipliers (Mirage `×1.5` execute <30%, Frostfang `×1.5` vs frozen/slow), self-heal shares (`dealt*0.3`), summon stat fractions (Umbra clone `0.4×`), status durations/stacks (root 200t, poison 2 stacks), AoE radius. These render as `Clause` prose ("Deals +50% to targets below 30% HP"). To still resist drift on the **damage-relevant** ones, hoist them to a **named module constant** the handler and clause format-string share (e.g. `CARACAL_EXECUTE_MULT = 1.5`); the clause text is built from it. Pure cosmetics (radius/duration) may stay inline — they're not numbers a balance pass tweaks for power.

This keeps B's no-drift promise on every **damage number** while not forcing a DSL onto irregular kits (summons, alternating-stat autos, mana-on-kill).

### 3.5 Shared-handler / shared-id metas

Most roster ids are unique-per-piece (`champ_x.active`, `enemy_y.passive`). Where several enemy defs reference one shared id (e.g. `register_active_simple("smash", ...)`), that id gets **one** `AbilityMeta`; `render()` resolves its numbers per-piece via `source`, so two different enemies sharing `smash` correctly show different damage. This is a feature of keying by ability-id, not piece-id. The guard (§6) keys off the **set of ids referenced by defs**, so shared ids are covered once.

### 3.6 Cross-task seam

- **UI tasks (T.8-T.23):** import `game.ability_text.render_for(champion.active_ability, champion)` for roster cards and `render_for(piece.active_ability_id, piece)` in combat. Pure consumer; no engine change.
- **T.30 V.15 guard** already asserts id→handler. T.34's guard is the parallel id→meta; both live in `test_ability_catalog.py` / the new test, same shape.
- **No combat-engine change** — `engine.py` never imports `ability_text`. Handlers only swap literals for `term.eval()`; control flow unchanged.

## 4. Decisions that need stating

| # | Decision | Proposal | Rationale |
|---|---|---|---|
| D1 | Guard strictness | **Hard CI fail** if any in-scope roster id lacks a meta | Matches V.15/V.17/V.22 culture (resolution guarantees are hard guards, not warnings). |
| D2 | Guard coverage set | Every ability/passive id referenced by `_CHAMPION_DEFS` (a) + `_ENEMY_DEFS` (b) + every `BossDef` field `phase1_active`/`phase1_passive`/`phase1_phase_hook`/`phase2_active`/`phase2_passive`/`on_death_hook` (c). **Not** `reference.py` test ids. | Mirrors V.15's exact boss field-set; only describes shipped tooltipable content. |
| D3 | Passive numbers | Passives render the **same way** — terms for their headline number (reflect %, bonus-auto damage, periodic heal), clauses for cadence ("every 600 ticks", "every 3rd auto") | Passives need tooltips as much as actives; cadence is prose, not a stat number. |
| D4 | Tick→time in prose | **Render durations/cadence in seconds.** Canonical `TICKS_PER_SECOND = 100` (V.39) defined in `ability_text.py`; a duration of `N` ticks displays as `N/100` s (e.g. `root 200t → "for 2s"`, `every 600t → "every 6s"`). Code stays ticks-only; conversion is presentation-only. | User blessed `100 ticks = 1s` as the canonical convention (aligns with V.25 DOT cadence). Seconds are the player-readable unit; ticks never surface in tooltips. |
| D5 | Rounding | `round()` to int for displayed damage/heal; `formula` shows same rounded value | Tooltips show whole numbers; keep `text` and `formula` consistent. |
| D6 | `Champion.stat` returns base sheet (no modifiers) | yes | Roster context = pre-combat sheet; live buffs only exist on `Piece`. |

## 5. Authored values

No **new balance numbers** are introduced — every term reuses the constant already in the handler (source-of-truth B). The authored content is **prose**: `name`, `blurb`, `clauses`, `tags` per ability. Catalog (`ABILITY_CATALOG_*.md`) supplies lore names/flavour to adapt; numbers come from code, not the catalog (catalog numbers are frozen/illustrative and may drift — code wins). All prose is first-pass/tunable; the snapshot test pins the **rendered numbers**, not the wording, so copy edits don't churn the golden file (snapshot stores `formula` strings keyed by id; wording lives in `text` which the snapshot may exclude or store loosely — see §8).

## 6. Content / roster audit + reconciliation

- **Coverage audit (build step):** enumerate `{d.active_ability, d.passive_ability for d in _CHAMPION_DEFS}` → 120 ids (T.34a); `_ENEMY_DEFS` → 120 ids (T.34b); the 6 id fields over every `BossDef` → 36 ids (T.34c). Assert each has an `ABILITY_META` entry. Any handler whose numbers were missed shows up as a missing/empty-term meta in review.
- **Drift origin note:** the latent drift this prevents = exactly the failure source-of-truth A would have (tooltip number ≠ handler number after a rebalance). B + the snapshot guard make it structurally impossible for the headline number and a `git blame`-able test for the rest.
- **V-guard added:** new invariant (V.38, §10) — every champion/enemy/boss roster ability id resolves in `ABILITY_META`, mirroring V.15 (incl. V.15's full BossDef field-set). CI tests `test_all_{champion,enemy,boss}_abilities_have_meta`.
- No vocabulary/tag drift in scope (tags here are new UI-iconography labels owned by this task, not the trait/role vocab).

## 7. Open questions

**Resolved here (proposals, overridable):**
- **`100 ticks = 1s` canonical (V.39):** durations/cadence render in **seconds** (`TICKS_PER_SECOND = 100` in `ability_text.py`); code stays ticks-only, conversion is presentation-only. User-blessed convention.
- Bosses **folded in** as T.34c (user request) — guard + snapshot extend to all 276 roster ids. Boss tooltips render against the compiled boss `Piece` (combat-only context; bosses have no draft sheet), so no `BossDef.stat()` adapter.
- Boss `phase_hook` / `on_death_hook` ids (HP-trigger / death-trigger passives, some via `register_bundle`) get metas too — blurb + clauses describing the trigger, `terms` only where they emit a damage/heal number. Coverage is per V.15's boss field-set, not "only damaging abilities".
- Tier-B damage-relevant constants hoisted to named module constants; pure radius/duration may stay inline (D + §3.4.1).
- `Enemy.stat()` adapter added in T.34b alongside enemy metas (parity with `Champion.stat()` in a).

**Still open / deferred:**
- Whether `text` should embed clauses inline or the UI lays them out — leaving `RenderedAbility` to expose `text` (blurb+numbers) and clauses already folded in as sentences; a future `clauses: tuple[str,...]` field on `RenderedAbility` can split them if the UI wants bullets. Deferred (additive).

## 8. Test plan

`tests/game/test_ability_text.py` (new):

1. **Coverage / V-guard (counting):** `test_all_champion_abilities_have_meta` — every id in `{active_ability,passive_ability}` over `_CHAMPION_DEFS` is in `ABILITY_META` (T.34a); `..._enemy_...` (T.34b); `..._boss_...` over all 6 `BossDef` id fields (T.34c). Hard fail on any miss. (Mirrors `test_ability_catalog.py` V.15 tests, incl. its boss coverage.)
2. **Render smoke:** for every in-scope id, `render_for(id, base_piece)` returns non-empty `name`, `text` has no leftover `{token}`, `formula` parses, no exception. Run against both a `Champion` and a compiled `Piece` to exercise both source types.
3. **Number correctness:** for a sampled set (≥1 per scaling shape: flat-only, single-stat, two-stat `str*k+int*k`), assert `RenderedAbility` number == `_eval_scaling(base, scaling, source)` rounded — i.e. tooltip == what the handler would compute.
4. **Source-of-truth B / determinism (regression):** full sim parity — run the existing champion/enemy sim or a fixed-seed `resolve_combat` battery **before vs after** the handler refactor and assert **byte-identical** `BattleResult` (fixed seed, `workers=1`). This is the load-bearing guard that swapping literals→`term.eval()` changed nothing. (No new RNG introduced — renderer is pure, no cadence mechanic, so nothing new to prove RNG-free; the determinism risk is purely the refactor, covered here.)
5. **Golden snapshot:** `ability_formulas.snapshot` — `{id: formula_string}` for all in-scope ids (276 at c) rendered against base sheet (champions/enemies) or compiled boss `Piece` (bosses). Pins the headline numbers so a future rebalance that touches a handler but forgets the term (impossible under B, but belt-and-suspenders for Tier-B clause constants) fails loudly. Regenerate via a documented `--update` flag.
6. **Champion.stat adapter:** `Champion.stat("intelligence") == champion.intelligence`; unknown key → `0.0`; a scaling term against a `Champion` yields non-zero stat contribution (the bug §2 flags).
7. **Tick→seconds (V.39):** `TICKS_PER_SECOND == 100`; `ticks_to_s(200) == "2"`/`"2s"` and `ticks_to_s(600) == "6"`; a rendered blurb/clause with a duration shows seconds, never a raw tick count; assert no `game/combat|status|piece|engine` module references `TICKS_PER_SECOND` (mechanics stay ticks-only).

## 9. Acceptance criteria

**T.34a:**
1. `ScalingTerm`/`Clause`/`AbilityMeta`/`RenderedAbility` + `ABILITY_META` + `render`/`render_for` exist; `ability_text.py` has zero Flet/api imports.
2. `Champion.stat()` returns the base field; scaling terms resolve non-zero against a `Champion`.
3. All **120 champion** roster ids have an `AbilityMeta`; coverage guard green.
4. Champion handlers read their headline numbers from terms; champion sim battery **byte-identical** pre/post.
5. `render_for(id, source)` works for both `Champion` and `Piece`; golden snapshot committed.

**T.34b:**
6. All **120 enemy** roster ids have an `AbilityMeta`; guard extended; enemy + full-roster sims byte-identical.
7. `Enemy.stat()` parity adapter present.
8. Snapshot covers all 240 champ+enemy ids; `/check` passes.

**T.34c:**
9. All **36 boss** roster ids (6 bosses × 6 fields) have an `AbilityMeta`; guard covers all three rosters (276 ids).
10. Boss damage/heal handlers read terms; boss + full sims byte-identical; boss metas render against compiled boss `Piece`.
11. Snapshot covers all 276 ids; `/check` passes; `docs/live/content/abilities.md` updated (§11).

## 10. SPEC changes needed (for `/spec`)

- **§T rows (add three):**
  - `| T.34a | Ability description/tooltip metadata — champions — AbilityMeta(name/blurb/terms[ScalingTerm]/clauses[Clause]/tags) parallel registry; pure render(meta, source)→RenderedAbility(name,text,formula,tags) serving base-Champion (roster) + live-Piece (combat) via structural .stat(); Champion.stat() base-sheet adapter; source-of-truth B (champion handlers read headline numbers from terms, byte-identical sims); CI coverage guard + golden formula snapshot | game/ability_text.py, game/registries.py, game/models.py, game/abilities/champions.py, tests/game/test_ability_text.py, docs/design/tasks/t34_ability_descriptions_plan.md | T.20, T.30, T.32 | M | 📋 Plan |`
  - `| T.34b | Ability description/tooltip metadata — enemies — 120 enemy AbilityMetas + Enemy.stat() parity; enemy handlers read terms (byte-identical sims); V.38 guard + snapshot extended to all 240 champ+enemy ids | game/abilities/enemies.py, game/models.py, tests/game/test_ability_text.py | T.34a | M | 📋 Plan |`
  - `| T.34c | Ability description/tooltip metadata — bosses — 36 boss AbilityMetas (6 bosses × phase1/2 active+passive + phase_hook + on_death_hook); boss handlers read terms (byte-identical sims); rendered against compiled boss Piece; V.38 guard + snapshot extended to all 276 roster ids | game/abilities/bosses.py, tests/game/test_ability_text.py | T.34a | M | 📋 Plan |`
- **New §V invariants:**
  - `V.39: \`100 ticks = 1 second\` canonical display convention — ticks in code, seconds only at the user-faced boundary. \`TICKS_PER_SECOND = 100\` in \`game/ability_text.py\` is the single source; mechanics never convert; \`ability_text.render\` + \`ui/\` apply it. (T.34)` — full wording in §3.2/D4.
  - `V.38: Every \`active_ability\`/\`passive_ability\` id referenced by a \`ChampionDef\`/\`EnemyDef\`, and every \`BossDef\` ability id (\`phase1_active\`, \`phase1_passive\`, \`phase1_phase_hook\`, \`phase2_active\`, \`phase2_passive\`, \`on_death_hook\` — the V.15 field-set), resolves in \`ABILITY_META\` — CI-guarded (\`test_all_{champion,enemy,boss}_abilities_have_meta\`), mirroring V.15. \`render(meta, source)\` is pure (no Flet/I-O, extends V.1) and reads numbers via \`source.stat()\` so a base \`Champion\`/\`Enemy\` (roster sheet) and a live \`Piece\` (combat, with modifiers; bosses always via the compiled Piece) render through one call. Headline damage/heal constants live **once** in \`ScalingTerm\`s the handler also reads (source-of-truth B) → tooltip numbers cannot drift from combat numbers; \`ScalingTerm.eval\` delegates to \`_eval_scaling\`, keeping \`resolve_combat\` byte-identical. (T.34)`
- **§B backprop:** none — no bug caught while planning (the `Champion.stat` gap is a forward-looking design constraint, not a shipped defect).
- **§D updates:** none required; optionally note under UI/Flow that ability tooltips now have a pure data source (`game.ability_text.render_for`).
- **Implementation Order:** append T.34a, T.34b, T.34c to Phase 5 (Polish + Docs) — presentation layer over shipped systems.

## 11. LIVING docs to update

- `docs/live/content/abilities.md` — add a section "Ability descriptions (T.34)": the `ABILITY_META` parallel registry, `render(meta, source)` contract, the two source contexts, the V.38 guarantee, and the V.39 `TICKS_PER_SECOND = 100` display convention (ticks-in-code / seconds-at-boundary). Update the Counts block to note meta coverage (120 champ in a; 240 in b; 276 incl. bosses in c). No 🔶→✅ flip (doc already ✅); keep `/check` green.
- No new `docs/live/systems/` doc — renderer is small and content-facing; it lives under the abilities content doc.
