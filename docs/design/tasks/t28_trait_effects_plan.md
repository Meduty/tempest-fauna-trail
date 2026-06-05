# T.28 Plan — Synergy Trait Effects (a / b / c)

> **Status:** plan — ready for review. (§T.28a/b exist at 📋 Plan; this rewrite
> supersedes the v1 plan and **re-splits into a / b / c** per the v2.1 catalog.)
> **Depends:** T.5 (roster + tags — done), T.20 (effect/registry substrate — done),
> T.26 (loadout/combat unification — done). T.29 (emblems) and T.31 (Primordial
> unlock augments) **consume** this, not the reverse.
> **Resolves:** SPEC §D.8 (trait breakpoints) + the trait half of the content layer.
> **Design source of truth:** [`trait_catalog.md` v2.1](../content/trait_catalog.md)
> (the 24 traits, **breakpoint counts**, identities, reachability model, primitive
> list, and the a/b/c scope in its §9), `champion_roster.md` (per-champion
> assignment), `effect_systems_design.md` §7 (substrate) + §10.1 (application order).
> **What this plan adds beyond the catalog:** concrete stat values, the code touch
> points (verified against current code), the engine-primitive designs, and the
> SPEC deltas.

> **Verified against current code (2026-06-05, post T.32/T.33):**
> - `register_trait` + empty `TRAIT_REGISTRY` exist (`registries.py:30,77`);
>   factory signature is `() -> list[TraitBreakpoint]`.
> - `compile_loadout` returns **`(pieces, bus)`** (`loadout.py:263`); step 2 =
>   weather (`_apply_weather_to_piece`), then jumps to step 7 = passives — the
>   trait step slots into the reserved 3–6 gap. T.33a's `load_order` block (~:255)
>   is additive and unaffected.
> - `apply_bundle` (`loadout.py:31`) already applies `granted_traits`, `modifiers`,
>   `statuses`, `granted_abilities`, `hooks` — traits are just another bundle
>   source. `granted_traits` are appended to `target.traits` → emblems (T.29) count
>   if applied **before** `_resolve_traits`.
> - `Piece.base_stats` keys (author modifiers against these): `hp` (**not**
>   `max_hp`), `strength`, `intelligence`, `attack_speed`, `milli_AS`,
>   `move_speed`, `mana_regen`, `threat`, `armor`, `resistance`, `attack_range`,
>   `crit_chance`, `penetration`, `penetration_pct`. `Piece` also has `load_order`,
>   `crit_counter`, `ability_can_crit`, `is_enemy`, `level`, **`barriers`**.
> - **Barrier system already exists (V.28):** `Piece.barriers` + `ctx.grant_barrier
>   (target, amount, duration_ticks)`, consumed before HP, expiry-pruned. → shields,
>   Guardian/Warden barriers, and the second-wind **decaying shield** reuse it; no
>   new absorb machinery needed.
> - `CALLING_TAGS` (`content.py:198`) still carries the 4 dead tags
>   (`Bulwark/Drifter/Harbinger/Emissary`) and omits `Packmate` — drift confirmed.
> - `StatusGate` has 4 members (no `UNTARGETABLE`); `StatusInstance` =
>   `status_id/remaining_ticks/stacks/source_id/potency`.
> - All six Tier-10s are currently **Spirit** (`content.py:511-561`) and **not
>   acquirable** by the player (shop/supply/challenge all exclude T10) — Primordial
>   is dormant until T.31's unlock augments.

---

## 0. Substep split (T.28a → T.28b → T.28c)

Seam = **what it touches.** a = declarative only (`loadout`/`models`/`content`/
`traits`), no engine edits. b = combat-primitives batch 1. c = combat-primitives
batch 2 + apex effects. Each ships and tests independently; b depends on a, c on b.

### T.28a — Framework + declarative content + roster rebalance (Est M–L)
- §3.1 types (`TraitScope`/`TraitBreakpoint`) + `@register_trait`; `game/traits/`
  package (`kinships/affinities/callings/_packs`), imported in `loadout.py`.
- §3.2 `_resolve_traits` + bundle application in `compile_loadout` (unique-id
  count, scope, §10.1 order), **player team only**.
- §3.2a **apex + dynamic-threshold infra**: a `TraitBreakpoint.count` may be an int
  *or* a `DynamicThreshold` (callable of the team/board cap) for Packmate
  `@full-board`; resolved at loadout.
- §3.3 affinity-trait synthesis (derived from `affinity`, weather-independent).
- §3.5 `BattleResult.trait_activations` (surfaced from `compile_loadout`).
- §6 **vocabulary + roster rebalance**: drop 4 dead Callings, add Packmate;
  reassign the 6 Tier-10 kinships (one per kinship); spread Hunter T2–9; rebalance
  kinship pools (Beast 18→14, etc.); assign Packmate to ~8 T1–3 fillers (secondary).
- **Content:** every **stat-pack** breakpoint rung — all Affinity rungs + the stat
  portions of Kinship/Calling ladders (the non-mechanic rungs).
- **Files:** `game/traits/`, `game/loadout.py`, `game/models.py`, `game/content.py`.
  **No** `status.py`/`engine.py`/`context.py`/`targeting.py` changes.
- **Done when:** counting/scope/dynamic-threshold/affinity-synthesis/vocab/roster
  tests green; a stat-pack breakpoint measurably shifts a fixed-seed fight;
  no-trait regression intact; V-guard (every tag resolves; ≥1 Kinship + ≥1 Calling
  per champion) green.

### T.28b — Combat primitives batch 1 + their breakpoints (Est M)
- Primitives: **untargetable** (`StatusGate.UNTARGETABLE` + target filters),
  **taunt**, **deterministic dodge**, **revive-once** (Mender), **threshold
  decaying-shield / second-wind** (Primordial; reuses `grant_barrier`),
  **tidal HoT** (Tidekin; heal cadence), **time-ramp/enrage** (Beast/Skirmisher),
  **kiting movement** (Skyborn, §3.4), **backline target-priority** (Stalker @2).
  (Plain barriers already exist — Guardian/Warden reuse `grant_barrier`.)
- **Content:** the breakpoints that use the above.
- **Files:** `game/status.py`, `game/piece.py`, `game/combat/engine.py`,
  `game/combat/context.py`, `game/targeting.py`, `game/traits/`.
- **Done when:** each primitive has a unit test; a breakpoint using each fires
  deterministically; `workers=1`/fixed-seed byte-identical; kiting guardrails
  (plant-when-cornered/swarmed) tested.

### T.28c — Combat primitives batch 2 + apex effects (Est M)
- Primitives: **echo/double-cast**, **mana-denial aura**, **ability-splash**,
  **on-death spawns** (Swarm), **empowered-shot/pierce/cleave** (Hunter), **Scaled
  weather-as-buff**, **Primordial kit hooks**, **Packmate `@full-board`** effect.
- **Content:** every remaining (mechanic + apex) breakpoint.
- **Files:** `game/combat/engine.py`, `game/combat/context.py`, `game/abilities/`
  (hook idioms), `game/traits/`.
- **Done when:** all 24 traits fully wired; apex effects fire; full sim regression;
  a T.25 sweep flags no obvious degeneracy (cheat-death stack, caster stack).

---

## 1. Scope

**In scope (all substeps):** the synergy trait layer — 24 traits (6 Kinship, 6
Affinity, 12 Calling), breakpoint factories with authored values, resolution in
`compile_loadout`, the engine primitives the catalog lists, the activation record,
and the vocab/roster reconciliation. Backend only (UI fires later).

**Out of scope:** emblem **items** (T.29 — a only guarantees the
`granted_traits`-before-resolution order); **Primordial unlock augments** (T.31 —
the 3 paired RUN-augments); UI surfacing of traits (T.10/T.15); trait-scope
augments (T.31).

---

## 2. The gap today
| Piece | Where | State |
|---|---|---|
| `register_trait` + `TRAIT_REGISTRY` | `registries.py:30,77` | 🔶 decorator + empty dict |
| `TraitScope`/`TraitBreakpoint` + `DynamicThreshold` | — | ❌ |
| Trait roll-up in `compile_loadout` | `loadout.py` (gap between step 2 and 7) | ❌ |
| Affinity synthesis | — | ❌ |
| `BattleResult.trait_activations` | `models.py`, `recorder.py` | ❌ |
| Barrier/shield | `piece.py`/`context.py` (V.28) | ✅ reuse `grant_barrier` |
| untargetable / taunt / dodge / revive / second-wind / tidal-HoT / kiting / backline-target | `status.py`/`engine.py`/`context.py`/`targeting.py` | ❌ (T.28b) |
| echo / mana-aura / splash / spawns / empowered-shot / weather-as-buff / full-board | engine/abilities | ❌ (T.28c) |
| Calling vocabulary | `content.py:198` | 🔴 drifted (4 dead, Packmate missing) |
| Tier-10 kinship spread + Hunter spread + Packmate carriers | `content.py:511-561` + roster | 🔴 (all T10 Spirit; Hunter all T8+; Packmate 0) |

---

## 3. Architecture (key points; full per-trait content in the catalog)

### 3.1 Types — `game/traits/__init__.py`
```python
class TraitScope(Enum):
    PER_TRAIT_PIECE = "per_trait_piece"   # bundle → carriers only
    TEAM_WIDE       = "team_wide"         # bundle → all team pieces

@dataclass
class TraitBreakpoint:
    count: int | DynamicThreshold          # int, or callable(team, board_cap)->int
    scope: TraitScope
    bundle_factory: Callable[[Piece], EffectBundle]
```
`@register_trait("<id>")` → `() -> list[TraitBreakpoint]` (highest cleared wins).
Author all modifiers against the **real** `base_stats` keys (§verified note; `hp`
not `max_hp`; ability scaling = `intelligence`).

### 3.2 Resolution in `compile_loadout` (player team only)
Insert after weather (step 2), before passives (step 7), per §10.1:
```python
team = [p for p in pieces if not p.is_enemy]
cleared = _resolve_traits(team, board_cap)   # {trait_id: TraitBreakpoint}
for trait_id, bp in cleared.items():
    targets = team if bp.scope is TEAM_WIDE else [p for p in team if trait_id in p.traits]
    for piece in targets:
        apply_bundle(piece, bp.bundle_factory(piece), bus)
```
- Count = **unique champion ids**; affinity tags injected synthetically in the
  count (not stamped on `Champion.traits`, so the V-guard ignores synthetic tags).
- Dynamic thresholds (Packmate `@full-board`) resolve `count(team, board_cap)`.
- `granted_traits` (emblems, T.29) are applied **before** this step → counted.
- Pure, RNG-free → replay-stable (new V).
- **Return change:** `compile_loadout` must also surface `cleared` (data-only) for
  the recorder — extend the return or attach to `bus`; keep additive/back-compat.

### 3.3 Affinity synthesis
At count time, add a derived tag per piece from `piece.affinity`
(`Clear→Sunlit`, …). Never reads node weather (V.6/V.8 clean).

### 3.4 Engine primitives (designs)
Determinism mandatory (cadence counters / geometry, never RNG — V.2/V.14):
- **Kiting (Skyborn, T.28b)** — in the movement phase, a kiter targets the tile
  restoring `attack_range` distance from the **nearest melee threat**. Guardrails:
  plant when cornered (no improving tile), plant when ≥2 adjacent, only kite
  range-1 threats, never kite without an attackable target, prefer lateral over
  corner. Melee Skyborn get **+1 `attack_range` at @2** so kiting is coherent.
- **Backline target-priority (Stalker @2, T.28b)** — targeting hook biasing the
  enemy backline; no spawn mutation.
- **Untargetable (T.28b)** — new `StatusGate.UNTARGETABLE`; filter in
  `_select_target`/`_opponents` + `targeting.py`.
- **Taunt (T.28b)** — status on the enemy, `source_id` = taunter; force-target in
  `_select_target`.
- **Dodge (T.28b)** — cadence counter; every Nth incoming basic deals 0.
- **Revive-once (Mender, T.28b)** — death-path intercept; restore at a fraction of
  `max_hp`; one flag per piece/combat.
- **Second-wind / threshold decaying-shield (Primordial, T.28b)** — on HP crossing
  below X%, `grant_barrier(self, 0.4*max_hp, ~1200 ticks)`; one flag/combat. Reuses
  V.28 barriers (decay = the barrier's tick expiry).
- **Tidal HoT (Tidekin, T.28b)** — per-cadence team `ctx.heal` tick.
- **Time-ramp / enrage (Beast/Skirmisher, T.28b)** — `on_tick` stacking `mul`
  modifier to a cap; enrage = one-shot low-HP burst.
- **Echo/double-cast, mana-aura, splash, spawns, empowered-shot, weather-as-buff,
  full-board (T.28c)** — hook idioms reusing `abilities/` patterns +
  `ctx.deal_damage`/`heal`/`spawn`.

### 3.5 Activation record
`BattleResult.trait_activations: list[tuple[str, int, int]]` (trait id, count,
breakpoint), surfaced from `compile_loadout` → `recorder.build_result`; + `to_dict`
/`from_dict` (save.py round-trips it for free). Optionally record the *next*
breakpoint + gap for future UI legibility.

---

## 4. Authored values — see catalog §2–§4 for the ladders
Stat bonuses are **percentages** (`mul` modifiers, scale across tiers); convention
minor ≈ +8% / moderate ≈ +15% / major ≈ +24% per named stat; `source_id` pattern
`trait:<id>@<n>`. Single-step body rungs are smaller increments of the same stat.
All numbers first-pass → **T.25 sim retune** (esp. apex / second-wind / dynamic).

---

## 5. Roster rebalance (T.28a content) — targets in catalog §5
- **Kinship pools** Beast 14 / Spirit 11 / Skyborn 9 / Scaled 9 / Tidekin 9 /
  Swarm 8 (=60). One **T10 anchor per kinship**: Mournhollow→Beast, Aurion→Spirit,
  Aerion→Skyborn, Umbra→Scaled, Nerei→Tidekin, Borealis→Swarm. (Kit unchanged —
  only the kinship tag moves; kinship ≠ playstyle.)
- **Callings:** add Packmate (8, T1–3 **secondary**), spread Hunter T2–9, trim
  Stalker 10→7; sums ~87. Constraints: Skyborn lean ranged; Swarm ≥3 in T1–3;
  kinships spread across affinities; Packmate primaries spread.
- **Drop** the 4 dead Calling tags from `CALLING_TAGS` + `ALL_TRAIT_TAGS`.

---

## 6. Open questions
**Resolved (overridable):** apex=`min(pool,cap)`; single-step ladders; @1 entries
on supports/casters/kiters; cheat-death stacks but diversified (one revive); T10
via 3 paired augments (T.31); Skyborn=kiting; Stalker @2 no-teleport.
**Still open / deferred:** apex+second-wind magnitudes (sim); kiting fidelity
fallback (proxy if pathing too invasive); two-Kinship hybrids; Primordial @3 as
flavour; Borealis-as-Swarm flavour; emblem economy (T.29/D.12); enemy quest tags.

---

## 7. Test plan
- **Counting/scope:** unique ids; copies count once; highest breakpoint wins;
  PER_TRAIT_PIECE hits carriers only; TEAM_WIDE hits all; enemies never light up.
- **Dynamic threshold:** Packmate `@full-board` resolves to live board cap.
- **Affinity synthesis:** N same-affinity champions light the affinity trait
  without touching node weather.
- **`granted_traits` ordering:** a piece given a tag pre-resolution is counted
  (simulated emblem).
- **Primitives (b/c):** untargetable excluded from selection; taunt forces target;
  dodge every Nth; revive once; second-wind grants a decaying barrier at the HP
  threshold once; tidal HoT ticks on cadence; **kiting** retreats vs melee, **plants
  when cornered/swarmed**, no-ops for melee w/o the @2 range; backline-priority
  picks the back row.
- **Determinism:** all cadence/geometry RNG-free; `workers=1`/fixed-seed
  byte-identical; trait resolution byte-identical for a fixed team.
- **Regression:** no-trait teams unchanged.
- **Effect:** a met breakpoint measurably shifts a fixed-seed fight.
- **V-guard:** `CALLING_TAGS` == the 12 catalog Callings; every tag resolves in
  `TRAIT_REGISTRY`; every champion ≥1 Kinship + ≥1 Calling (+ Primordial at T10);
  Packmate ≥ its carriers; one T10 per kinship.

---

## 8. Acceptance criteria (per substep)
**a:** types + `@register_trait` for all 24 traits' **declarative rungs**; resolution
in `compile_loadout` (count/scope/dynamic, player-only, §10.1 order); affinity
synthesis; `BattleResult.trait_activations`; vocab + roster rebalance done;
V-guard + counting/scope/affinity/dynamic tests green; no-trait regression intact.
**b:** batch-1 primitives implemented + honored in loop/targeting/`deal_damage`;
their breakpoints fire deterministically; kiting guardrails tested; byte-identical.
**c:** batch-2 primitives + all apex effects; 24 traits fully wired; full sim
regression; T.25 sweep shows no obvious degeneracy.

---

## 9. SPEC changes needed (for `/spec`)
1. **§T:** replace T.28a/T.28b rows with **T.28a / T.28b / T.28c** (descriptions
   per §0; a Est M–L, b M, c M; b dep a, c dep b); cite this plan. Update
   Implementation-Order chain `… → T.28a → T.28b → T.28c → …`.
2. **V.21/V.22** stand (unique-id count + RNG-free; tag-resolution + ≥1 Kinship/
   Calling). Extend V.22 note: exactly one Tier-10 per kinship.
3. **New invariant (apex/dynamic + determinism of new primitives):** trait apex =
   `min(pool, board-cap)`; a `TraitBreakpoint.count` may be a dynamic threshold
   resolved at loadout; kiting/dodge/second-wind/revive/tidal-HoT are deterministic
   (geometry/cadence, never RNG); cheat-death effects stack (no hard cap) by design.
4. **§B:** Calling-vocab drift (4 dead T.5 tags + missing Packmate) — cause +
   fix in T.28a; V.22 prevents recurrence.
5. **§D.8:** trait effects implemented in T.28a/b/c; leave open value-tuning,
   kiting-fidelity fallback, two-Kinship hybrids.
6. **T.29 note:** emblems rely on the `granted_traits`-before-resolution order
   (§3.2). **T.31 note:** +3 paired RUN-augments unlock Primordials in shop.

---

## 10. LIVING docs to update
- `docs/live/content/traits.md` — flip 🔶 toward ✅ as each substep lands (a: vocab
  + counting + stat packs; b/c: primitives). Cite real `traits/` symbols.
- `ARCHITECTURE.md` — add `game/traits/` to the system map on a.
- FROZEN (`trait_catalog.md`, this plan) left as-is once landed.
