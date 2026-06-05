# T31 Plan — Augment System

> **Status:** plan — ready for review.
> **Depends:** T.20 (effect substrate — done), T.26 (loadout/combat unification — done), **T.22** (Amber/Tempest economy + Run state + node-resolution flow), **T.28** (Kinship/Calling traits), **T.29** (items/components/emblems). The trait/item/economy augment *content* cannot function before those land — this is **one task sequenced after T.22 + T.28 + T.29**.
> **Resolves:** SPEC §D.11 (augment pool, 4 quality tiers, per-augment effects) and the augment half of T.22 (which is hereby narrowed to economy/shop/supply/team-cap).
> **Design source of truth:** [`augment_catalog.md`](../content/augment_catalog.md) (the ~50 augments), [`effect_systems_design.md` §9](../systems/effect_systems_design.md) (the substrate — `Augment`, `AugmentScope`, registry, quest trackers, application order), [`t22_meta_progression_plan.md` §2](t22_meta_progression_plan.md) (offer/reroll/quality-weight framing).
> **Not a §T row yet** — needs a `/spec` invocation to add **T.31** to §T, amend V.2, add invariants, and update §D.11 + the T.22 row. Do not edit SPEC inline. §10 lists the exact spec deltas.

---

## 1. Scope

Implement the **complete augment system, backend-first** — engine, offers, run-state, combat integration, all ~50 catalog augments across 4 qualities and 3 scopes, plus the CLI playthrough driver that exercises them. The UI is out of scope by design: the backend is built so a later Flet view (T.10/T.15) only has to *call* it. The dev CLI (`sim_run`) is the reference consumer and must support a **complete run** — including augment nodes — headlessly and via a rudimentary interactive prompt.

**In scope**
- `src/game/augments.py` — `Augment`, `AugmentScope`, `@register_augment`, `@register_quest_tracker`, the ~50 handlers, the per-stage quality-weight curve, offer generation, pick/reroll/apply logic.
- `Run` model additions (`active_augments`, `augment_state`) + serialization.
- Combat integration seam — thread active augments into `compile_loadout` (V.2 amendment).
- Quest-tracker wiring in `loadout.py` (§9.3 of the effect spec).
- `sim_run` augment node resolution: `--augment-policy` + interactive manual mode.
- Tests: `tests/game/test_augments.py`, additions to `tests/game/test_loadout.py`, `tests/tools/test_playtest_smoke.py`.

**Out of scope**
- Flet UI (augment-offer view) — fired by the backend later, T.10/T.15.
- The supply node (1-of-5 champ+item) — stays in T.22.
- New trait/item/champion *content* — consumed here, authored in T.28/T.29/T.5.

---

## 2. The gap today (current scaffolding)

What exists is plumbing for the *node*, not the *system*:

| Piece | Where | State |
|---|---|---|
| `NodeType.AUGMENT` | [models.py:36](../../../src/game/models.py#L36) | ✅ enum |
| `Node.augment_pool_id` (+ serialize) | [models.py:306](../../../src/game/models.py#L306) | ✅ field, defaults `None`; set to `"augment_basic"` for augment nodes |
| Route placement + `_encounter_ids` | [route.py:209,322](../../../src/game/route.py#L322) | ✅ augment nodes seeded; hands back `"augment_basic"` |
| `augment_seed(run_seed, node_index, rerolled)` | [encounter.py:488](../../../src/game/encounter.py#L488) | ✅ defined, **zero callers** |
| `AUGMENT_REGISTRY` | [registries.py:33](../../../src/game/registries.py#L33) | 🔶 empty dict, never written/read |
| `EffectBundle` substrate (modifiers/hooks/statuses/granted_*) | [effects.py](../../../src/game/effects.py) | ✅ shared with items/traits/passives — augments reuse verbatim |

**Missing = the whole system:** no `Augment` model, no scope handlers, no `@register_augment`, `"augment_basic"` is a dangling string with no pool definition, `augment_seed` feeds no generator, `sim_run` literally skips augment nodes ([sim_run.py:133](../../../tools/playtest/sim_run.py#L133)), and `Run` has nowhere to hold an active augment.

---

## 3. Architecture

### 3.1 Data model (`src/game/augments.py`)

Ported directly from [`effect_systems_design.md` §9.1](../systems/effect_systems_design.md):

```python
class AugmentScope(Enum):
    PIECE = "piece"   # bundle applied to filtered pieces
    TEAM  = "team"    # bundle applied team-wide
    RUN   = "run"     # mutates Run state, no combat bundle

class AugmentQuality(Enum):
    COMMON = "common"; RARE = "rare"; EPIC = "epic"; PRISMATIC = "prismatic"

@dataclass(frozen=True)
class Augment:
    id: str
    name: str
    scope: AugmentScope
    quality: AugmentQuality
    handler: Callable                          # signature varies by scope (below)
    piece_filter: Callable[[Piece], bool] | None = None   # PIECE only
    quest_tracker: str | None = None                      # quest augments
```

Handler signatures (the contract `compile_loadout` / node-resolution dispatch on):

| Scope | Signature | Effect |
|---|---|---|
| `TEAM` | `(team: list[Piece]) -> EffectBundle` | bundle applied to every team piece |
| `PIECE` | `(piece: Piece) -> EffectBundle` | bundle applied to each piece passing `piece_filter` |
| `RUN` | `(run: Run) -> None` | mutates `Run` directly at **pick time**, no combat bundle |

`@register_augment(id, name, scope, quality, ...)` populates the existing `AUGMENT_REGISTRY`. Importing the augments package triggers registration, mirroring `@register_active`/`@register_passive`. The `game/__init__` content-import path must include it so the registry is populated before any lookup (same pattern as abilities).

### 3.2 Run state additions ([models.py](../../../src/game/models.py))

```python
active_augments: list[str]        = field(default_factory=list)   # picked augment ids, run order
augment_state:   dict[str, Any]   = field(default_factory=dict)   # quest progress + RUN-scope flags
```

- `to_dict`/`from_dict` round-trip both (B.3-style save stability; needed for T.14).
- `__post_init__` validates every id in `active_augments` resolves in `AUGMENT_REGISTRY` (V-invariant, §10) — analogous to V.15 for abilities.
- Reroll bookkeeping is **per-node ephemeral** (the offer is regenerated, not stored — matches T.19); the "first reroll free, then 1 Amber" rule is enforced at resolution time using `Node` + a per-node reroll counter, paralleling D.15's shop reroll.

### 3.3 Offer generation + reroll + node resolution

```python
def generate_augment_offer(run_seed, node_index, stage, *, rerolled=False) -> list[Augment]:
    rng = SeededRng(augment_seed(run_seed, node_index, rerolled))   # existing fn
    weights = quality_weights_for_stage(stage.index)                # §5 curve
    # roll 3 distinct augments: pick quality by weight, then an unpicked augment
    # of that quality from AUGMENT_REGISTRY; exclude run.active_augments and dups.
```

- **1-of-3**, deterministic from `augment_seed` (already channel-split for `rerolled` via `CH_AUGMENT`/`CH_REROLL`).
- **One reroll/node** re-rolls all 3 via the `rerolled=True` sub-seed; first reroll free, subsequent (none in MVP — only one allowed) gated by Amber.
- Exclusions: already-active augments, and within an offer no duplicate ids.
- **Prismatic gating** (catalog §6 open q): Prismatic excluded from stage 1 offers; eligible stage ≥ 2. (Proposed; tuning.)

`apply_augment(run, augment)` at node resolution:
- `RUN` scope → call `handler(run)` immediately (mutates Amber/items/Tempest/`augment_state`), append id to `active_augments`.
- `TEAM`/`PIECE` scope → append id to `active_augments`; the bundle is built fresh **each combat** in `compile_loadout` (run-long ⇒ re-applied, never persisted as combat state).
- Quest augment → its `RUN` handler seeds `augment_state[id]`; the tracker is wired per-combat (§3.5).

### 3.4 Combat integration seam (amends V.2)

V.2 locks `resolve_combat(team, enemies, weather) -> BattleResult`. Run-long TEAM/PIECE augments must apply inside `compile_loadout`, and quest trackers must mutate persistent state during combat. **Proposed seam — a single optional param:**

```python
@dataclass
class RunModifiers:
    augments: list[str] = field(default_factory=list)
    augment_state: dict[str, Any] = field(default_factory=dict)   # mutable: quest trackers write here

def resolve_combat(team, enemies, weather, *, node_id=None, run_mods: RunModifiers | None = None) -> BattleResult: ...
```

- **Default `None`** ⇒ current callers and all balance sims (`mega`, `matchup`, `sim_fight`) are byte-for-byte unchanged — they never visit augment nodes (your note), so they pass nothing.
- `resolve_boss_combat` ([tools/playtest/_common.py](../../../tools/playtest/_common.py)) gains the same param and forwards it.
- `compile_loadout` consumes `run_mods.augments`: builds TEAM/PIECE bundles from the registry and applies them at the documented slot, and wires quest trackers against `run_mods.augment_state`.
- Determinism preserved: bundles are a pure function of `(augment ids, team)`; quest-state mutation is the one documented side-channel and is itself deterministic given inputs.

**Application order** — slots already reserved in [`effect_systems_design.md` §10.1](../systems/effect_systems_design.md): step 6 = augment bundles (**PIECE-filtered first, then TEAM**), step 9 = wire quest trackers. This task fills steps 6 + 9; later application overrides earlier, so augments sit after traits/items (intentional — augments are the loudest layer).

### 3.5 Quest tracker plumbing + event vocabulary

Quest trackers are **Run-level subscribers**, not combat hooks — they survive across combats accumulating progress ([§9.3](../systems/effect_systems_design.md)). `compile_loadout` wires each active quest augment's tracker into the bus as low-priority hooks on its declared events, closing over `run_mods.augment_state`.

The catalog §6 leaves the event vocabulary open. Pinning it for the 4 MVP quests:

| Quest augment | Events | Goal / payout (needs) |
|---|---|---|
| **Prospector** | (Run-level, checked at node resolution on Amber change) | bank target Amber → free component (T.29) |
| **Stormbound Trail** | `on_combat_end` + node weather ≠ CLEAR | win N non-CLEAR fights → Kinship emblem (T.28/T.29) |
| **Bloodless Victory** | `on_combat_end` + zero team deaths that fight | win N deathless → special item (T.29) |
| **The Long Hunt** | `on_kill` + victim carries a `boss_phase2` tag | kill all 6 phase-2 beasts → Prismatic payout |

→ requires a `boss_phase2` (and per-boss) victim tag from the boss kits (T.30 bosses exist; tag surface is a small addition). `QUEST_TRACKER_EVENTS: dict[str, list[str]]` declares the subscription set per tracker.

---

## 4. Content — the ~50 augments

All ~50 from [`augment_catalog.md`](../content/augment_catalog.md) are authored. Grouped by what they touch, with scope + hard dependency (this is why T.31 sequences after T.22/T.28/T.29):

| Group | Scope(s) | Count | Hard dep | Impl pattern |
|---|---|---|---|---|
| **Stat packs** (Thicker Hides, Sharpened Fangs, Glass Fang…) | TEAM | ~6 | none | `EffectBundle(modifiers=[Modifier(...)])` |
| **Weather** (Stormchaser's Pact, Apex Predators, Eye of the Storm, One With the Sky, Heart of the Storm…) | TEAM | ~7 | none | hooks on `on_damage_pre`/`on_combat_start`, read `ctx.weather` + `damage_modifier`/affinity ring |
| **Tick / time** (Slow Burn, Opening Howl, Adrenal Glands, Overclock, The Uprising) | TEAM | ~5 | none (Uprising reads `run.battle_log`) | `on_tick`/`on_cast` hooks; timed `Modifier`s |
| **Archetype / role** (Sharpshooter, Phalanx Drill, Ambush, Pack Tactics, Twin Fang, Threefold Bloom) | PIECE | ~6 | **T.28** (Calling tags for filters) | PIECE bundle + `piece_filter=lambda p: "<calling>" in p.traits` |
| **Trait** (Kinship/Calling Crest & Crown, Worldroot Crown, Built Different, Emblem of the Wild) | RUN / PIECE | ~6 | **T.28** (+ T.29 for emblems) | RUN: bump trait count in run/loadout; PIECE: conditional on active breakpoint |
| **Economy / meta** (Forage, Amber Vein, Scout's Pay, Salvage Rights, Trail Rations, Component Stipend, Tempest Surge, Tempest Ascendant) | RUN | ~8 | **T.22** (Amber/Tempest) + **T.29** (components) | `handler(run)` mutates `run.amber`/Tempest/inventory at pick time |
| **Quest** (Prospector, Stormbound Trail, Bloodless Victory, The Long Hunt) | RUN + tracker | 4 | T.22/T.28/T.29 + boss tags | §3.5 |
| **Defensive/utility prismatics** (Sanctuary, Hexproof Pack, Living Tide, Endless Swarm, Living World, Apex Instinct, Primordial Bond) | TEAM / PIECE | ~7 | mixed (Living World needs T.21 map flip; Primordial Bond needs T.28 Primordial) | revive/CC-immunity/lifesteal hooks; summon on death (T.30 summon primitives) |

Reference implementations to mirror live in [§9.2](../systems/effect_systems_design.md) (one per flavour) and the existing ability handlers in [champions.py](../../../src/game/abilities/champions.py) (hook idioms, `enemies_in_radius`, `_eval_scaling`).

---

## 5. Quality-weight curve

Per-stage offer weights (Common : Rare : Epic : Prismatic). Proposed starting point — **tuning job**, flagged in §7 and D.11:

| Stage | Common | Rare | Epic | Prismatic |
|---|---|---|---|---|
| 1 | 70 | 25 | 5 | 0 |
| 2 | 50 | 30 | 17 | 3 |
| 3 | 35 | 33 | 25 | 7 |
| 4 | 22 | 33 | 33 | 12 |
| 5 | 12 | 30 | 40 | 18 |
| 6 | 5 | 25 | 45 | 25 |

`quality_weights_for_stage(stage_index) -> dict[AugmentQuality, int]`. Monotone shift toward higher quality; Prismatic 0 at stage 1 (gating, §3.3).

---

## 6. CLI driver (`sim_run`)

Replace the skip at [sim_run.py:133](../../../tools/playtest/sim_run.py#L133) with real augment resolution. `sim_run` becomes a **complete run** — the reference backend consumer, no Flet.

**Headless (default).** `--augment-policy {first,random,highest-quality,none}` (default `highest-quality`), deterministic from `augment_seed`:
- `first` — always offer slot 0.
- `random` — seeded uniform over the 3.
- `highest-quality` — pick the highest-quality offer (ties → seeded).
- `none` — decline (skip), preserves today's behaviour for A/B runs.

A walked run threads picks into a `RunModifiers` and passes it to every subsequent `resolve_combat`/`resolve_boss_combat`. RUN-scope picks mutate the walker's `Run`. CSV gains an `augment_picked` column on augment-node rows.

**Interactive manual run.** `--interactive` (or a thin `sim_run play` mode): at each AUGMENT node, print the 3 offers (name · quality · scope · one-line effect) and prompt the player to pick `1/2/3`, `r` to reroll once, or `s` to skip. Should feel like a complete run with rudimentary CLI UI — groundwork the eventual Flet view mirrors. Extensible later to other decision nodes (shop, supply) but those are T.22.

---

## 7. Open questions

**Resolved here (proposals, overridable):**
- **Prismatic availability** (catalog §6) → gated to stage ≥ 2 (§3.3).
- **Quest event vocabulary** (catalog §6) → pinned in §3.5; needs a `boss_phase2` victim tag.
- **Combat seam shape** → `RunModifiers` optional param (§3.4), accepted.

**Still open / tuning:**
- **Quality-weight curve** (§5, D.11) — numbers are a balance pass, validate with `sim_run` over many seeds once content exists.
- **Interaction caps** (catalog §6) — degenerate stacks (Apex Instinct + Mystic@4 + Spellfang all touch crit). Needs a combo audit pass before tuning; not a blocker for shipping the engine.
- **Hero/piece-specific augments** — out of this pass per catalog §6.
- **Reroll count** — MVP = one reroll/node (first free). More rerolls = Amber, deferred.

---

## 8. Test plan

- **Offers deterministic:** `generate_augment_offer(seed, n)` stable across runs; `rerolled=True` yields a different deterministic set; offers contain no dups and exclude active augments.
- **Quality curve:** weights shift monotonically by stage; Prismatic weight 0 at stage 1; over many seeds the empirical quality mix tracks the curve.
- **Scope dispatch:** TEAM bundle hits every team piece; PIECE bundle hits only `piece_filter` matches; RUN handler mutates `Run` and leaves combat untouched.
- **Combat integration:** `resolve_combat` with `run_mods=None` is byte-identical to today (regression guard); a TEAM stat augment measurably shifts a fixed-seed fight; PIECE augment affects only filtered pieces.
- **Quest tracker:** progress accumulates across multiple `resolve_combat` calls sharing one `augment_state`; payout fires once at threshold; `ONCE_PER_COMBAT` dedup holds.
- **Run round-trip:** `active_augments` + `augment_state` survive `to_dict`/`from_dict`; invalid augment id raises in `__post_init__`.
- **CLI:** `sim_run --augment-policy …` resolves augment nodes (smoke); `none` reproduces the skip baseline; interactive mode parses `1/2/3/r/s`.
- **V-guard:** every `Augment.id` in `active_augments` resolves in `AUGMENT_REGISTRY` (CI test, mirrors V.15).

---

## 9. Acceptance criteria

1. `Augment`/`AugmentScope`/`AugmentQuality` model + `@register_augment` + populated `AUGMENT_REGISTRY` with all ~50 catalog augments.
2. Deterministic 1-of-3 offer generation + one reroll + Prismatic gating + per-stage quality curve.
3. `Run` holds `active_augments` + `augment_state` with serialization and id-validation.
4. TEAM/PIECE augments apply through `compile_loadout`; RUN augments mutate `Run` at pick time; quest trackers wired and accumulate across combats — all via the `RunModifiers` seam, with `None` fully back-compat.
5. `sim_run` resolves augment nodes headlessly (`--augment-policy`) and interactively (`--interactive`); balance sims unchanged.
6. `tests/game/test_augments.py` + integration/CLI tests pass; full suite green.

---

## 10. SPEC changes needed (for `/spec`)

1. **§T:** add **T.31** — "Augment system — `Augment`/`AugmentScope`/`AugmentQuality` model, `@register_augment`, all ~50 catalog augments (4 qualities × 3 scopes incl. quest trackers), deterministic 1-of-3 offers + reroll + per-stage quality curve, `Run.active_augments`/`augment_state`, `compile_loadout` application + quest-tracker wiring, `RunModifiers` combat seam, `sim_run` policy + interactive resolution" | files `game/augments.py`, `game/loadout.py`, `game/models.py`, `game/combat/resolve.py`, `tools/playtest/sim_run.py`, `docs/design/tasks/t31_augment_system_plan.md` | Depends T.20, T.22, T.26, T.28, T.29 | L | 📋 Plan.
2. **§T T.22 row:** narrow scope — drop "Also covers augment/supply node resolution and augment pool" → augment ownership moves to T.31; T.22 keeps economy/shop/supply/team-cap. (T.22 stays a dependency of T.31.)
3. **V.2 amendment:** note the optional `run_mods: RunModifiers` param on `resolve_combat`/`resolve_boss_combat` — still pure/deterministic; `None` default ⇒ no behavioural change for non-augment callers.
4. **New invariant (≈V.17):** every id in `Run.active_augments` (and every quest-tracker id) **must** resolve in `AUGMENT_REGISTRY` / `QUEST_TRACKER_REGISTRY` — CI-guarded, mirroring V.15.
5. **New invariant (≈V.18):** augments are **run-long** — TEAM/PIECE augment effects are rebuilt fresh in `compile_loadout` each combat from `active_augments`, never persisted as combat state; RUN augments mutate `Run` exactly once at pick time. (Encodes the re-apply contract.)
6. **§D.11:** mark augment content + substrate as **implemented in T.31**; leave only the quality-weight curve + interaction-cap audit as open tuning.
7. **Implementation Order:** Phase 1b becomes `T.22 → T.28 → T.29 → T.31`.
