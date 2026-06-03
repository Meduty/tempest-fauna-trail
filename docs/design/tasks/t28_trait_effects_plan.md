# T28 Plan — Synergy Trait Effects

> **Status:** plan — ready for review. (T.28 is already a §T row at ❌ Not started; landing this doc flips it to 📋 Plan via `/spec`.)
> **Depends:** T.5 (roster + trait tags — done), T.20 (effect substrate / registries — done), T.26 (loadout/combat unification — done). Independent of T.22 — buildable now, in parallel.
> **Resolves:** SPEC §D.8 (trait breakpoints + bonuses) and the trait half of the content layer.
> **Design source of truth:** [`trait_catalog.md`](../content/trait_catalog.md) (the 24 traits + breakpoint *concepts*), [`champion_roster.md`](../content/champion_roster.md) (authoritative per-champion Kinship + Calling assignment), [`enemy_roster.md`](../content/enemy_roster.md) (enemy tags — no synergy), and [`effect_systems_design.md` §7](../systems/effect_systems_design.md) (substrate — `TraitScope`, `TraitBreakpoint`, `_resolve_traits`, emblem `granted_traits` ordering) + §10.1 (application order).
> **What this plan adds beyond those:** the **concrete breakpoint stat values** (catalog is concepts-only), the **new combat primitives** several breakpoints require, a **Calling-vocabulary reconciliation** (§6.1 — code drifted from the docs), and a **fidelity policy** for the deepest mechanics (§3.4 — MVP-simplifies the most engine-invasive breakpoints).

---

## 0. Two-substep split (T.28a → T.28b)

Per the §10 estimate flag, T.28 ships as two sequential substeps. The seam is **whether new combat-engine primitives are touched**: T.28a changes only `loadout.py` / `models.py` / `content.py` (low risk, no loop/status/targeting edits); T.28b adds the engine primitives and the hook-based breakpoints that use them. b depends on a.

### T.28a — Trait framework + declarative content (Est: M)
The whole system wired end-to-end with every breakpoint that is a **pure stat `Modifier` bundle**.
- §3.1 types (`TraitScope`/`TraitBreakpoint`), `@register_trait`, `game/traits/` package.
- §3.2 `_resolve_traits` + bundle application in `compile_loadout` (unique-id count, scope, §10.1 order).
- §3.3 affinity-trait synthesis.
- §3.5 `BattleResult.trait_activations` record (compile-time surfacing).
- §6.1 Calling-vocabulary reconciliation (drop 4 dead tags, add Packmate + carriers) + §6.2 roster audit.
- §10 invariants V.20 / V.21 + V-guard test.
- **Content:** all Affinity breakpoints (§5.1) + the stat-pack portions of Kinships/Callings (Mystic @2 INT, Bruiser @2/@4 HP/STR, Scaled @2 armor/res, Galvanized, Packmate stat packs, etc.).
- **Files:** `game/traits/`, `game/loadout.py`, `game/models.py`, `game/content.py`. **No** `status.py` / `loop_new.py` / `context.py` / `targeting.py` changes.
- **Done when:** counting/scope/determinism/vocab tests green; a stat-pack breakpoint measurably shifts a fixed-seed fight; no-trait regression intact.

### T.28b — Combat primitives + mechanic breakpoints (Est: M–L, depends T.28a)
- §3.4 Tier-A primitives: `Piece.shield_hp` absorb, `StatusGate.UNTARGETABLE`, `taunt`, deterministic `dodge`, `revive`-once, time-ramp, echo/double-cast, mana-denial aura — all deterministic (no RNG).
- §3.4 Tier-B proxies (Skyborn collision/tie, Stalker reposition).
- **Content:** every hook-based breakpoint (Beast ramp/lifesteal, Skyborn opener, Spirit untargetable/echo, Tidekin/Mender revive, Swarm spawn, Guardian/Warden shields, Stalker, Skirmisher dodge/ramp, Channeler free/double-cast, Trickster taunt/aura, Hunter empowered shot, Primordial second-wind).
- **Files:** `game/status.py`, `game/piece.py`, `game/combat/loop_new.py`, `game/combat/context.py`, `game/targeting.py`, `game/traits/` (hook factories).
- **Done when:** each primitive has a unit test; a breakpoint using each fires deterministically; `workers=1`/fixed-seed byte-identical.

(Sections §1–§9 below are shared design context; each is tagged where a substep boundary matters.)

---

## 1. Scope

Implement the **synergy trait layer**: the draft-puzzle payoff where fielding enough tag-sharing champions unlocks breakpoint bonuses. Backend-only (no UI — fired later by Prep/Trail views). Three trait families, 24 traits total: **6 Kinships, 6 Affinities, 12 Callings**.

**In scope**
- `src/game/traits/` — `TraitScope`, `TraitBreakpoint` types; `@register_trait` factories for all 24 traits; authored breakpoint values (§5).
- `src/game/loadout.py` — trait roll-up step in `compile_loadout` (count unique champion ids → resolve highest cleared breakpoint → apply bundles), slotted per §10.1.
- Affinity-trait synthesis — derive the affinity trait tag from each piece's `affinity` field (catalog §3 / §1).
- `src/game/status.py` + loop/targeting — new primitives: `shield`, `untargetable`, `taunt`.
- `BattleResult` trait-activation events (recorder).
- Roster audit — confirm all 60 champions carry a complete Kinship + Calling(s) (+ Primordial on T10).
- Tests: `tests/game/test_traits.py`, additions to `tests/game/test_loadout.py`.

**Out of scope**
- Emblem **items** (Spirit Gem + component → Kinship) — T.29. This task only guarantees the `granted_traits`-before-resolution ordering so emblems slot in cleanly later.
- UI surfacing of active traits — T.10/T.15.
- Trait-scope augments (Crest/Crown/Built Different) — T.31 consumes trait counts.

---

## 2. The gap today

| Piece | Where | State |
|---|---|---|
| `@register_trait` + `TRAIT_REGISTRY` | [registries.py:30,77](../../../src/game/registries.py#L77) | 🔶 decorator + empty dict, never populated |
| `TraitScope` / `TraitBreakpoint` types | — | ❌ sketched in §7, not coded |
| Champion trait tags (Kinship + Calling) | [content.py](../../../src/game/content.py) | ✅ assigned (e.g. `["Beast", "Skirmisher"]`); needs completeness audit |
| Trait roll-up in `compile_loadout` | [loadout.py:222](../../../src/game/loadout.py#L222) | ❌ jumps from weather (step 2) straight to passives (step 7) — no trait step |
| `shield` / `untargetable` / `taunt` + deeper primitives | [status.py](../../../src/game/status.py), [piece.py](../../../src/game/piece.py) | ❌ none exist; `StatusGate` has only 4 members (`BLOCKS_ACTION/CAST/ATTACK/MOVEMENT`); `StatusInstance` has no value field (`status_id, remaining_ticks, stacks, source_id` only) |
| Trait activation record on `BattleResult` | [recorder.py:44](../../../src/game/combat/recorder.py#L44), [models.py:512](../../../src/game/models.py#L512) | ❌ `BattleResult` has no trait field; recorder is built from `pieces` + bus hooks (see §3.5 wrinkle) |
| Calling-tag vocabulary | [content.py:101-118](../../../src/game/content.py#L101-L118) | 🔴 **drifted** — `CALLING_TAGS` carries 4 dead tags + omits `Packmate` (see §6.1) |

`apply_bundle` ([loadout.py:40](../../../src/game/loadout.py#L40)) already handles `granted_traits`, `modifiers`, `statuses`, `granted_abilities`, `hooks` — traits are just another bundle source, no new effect machinery. `ALL_TRAIT_TAGS` ([content.py:120](../../../src/game/content.py#L120)) already exists for the §10 V-guard (it excludes affinity-derived tags by design — good).

---

## 3. Architecture

### 3.1 Types (`src/game/traits/__init__.py` + per-family modules)

Port [§7.1](../systems/effect_systems_design.md) verbatim:

```python
class TraitScope(Enum):
    PER_TRAIT_PIECE = "per_trait_piece"   # bundle → only pieces carrying the trait
    TEAM_WIDE       = "team_wide"         # bundle → all team pieces

@dataclass
class TraitBreakpoint:
    count: int                                       # min unique champions carrying the trait
    scope: TraitScope
    bundle_factory: Callable[[Piece], EffectBundle]  # called per target piece
```

`@register_trait("<id>")` returns `list[TraitBreakpoint]` (highest cleared wins). Package layout: `traits/kinships.py`, `traits/affinities.py`, `traits/callings.py`, plus `traits/_packs.py` for shared stat-pack `EffectBundle` factories. Import the package in `loadout.py` (like `import abilities`) so decorators register.

> **Stat-key note:** the §7 example uses an illustrative `"ability_power"` stat that does **not** exist in the engine. Author all modifiers against the real `Piece.base_stats` keys: `hp, strength, intelligence, attack_speed, move_speed, mana_regen, threat, armor, resistance, attack_range, crit_chance, penetration, penetration_pct`. Ability scaling lives on `intelligence`.

### 3.2 Resolution in `compile_loadout`

Insert a trait step after pieces are built (and after weather, current step 2) and **before** passives (current step 7), matching §10.1 steps 3-4:

```python
# 3. Resolve trait breakpoints (player team only — enemies never light up, catalog §1)
cleared = _resolve_traits([p for p in pieces if not p.is_enemy])
# 4. Apply trait bundles
for trait, bp in cleared.items():
    targets = team_pieces if bp.scope == TEAM_WIDE else [p for p in team_pieces if trait in p.traits]
    for piece in targets:
        apply_bundle(piece, bp.bundle_factory(piece), bus)
```

- **Counting = unique champion ids** ([§7.2](../systems/effect_systems_design.md)); two copies of one champion count once.
- **Emblem / `granted_traits` ordering (for T.29):** §10.1 says item `granted_traits` apply at step 2, *before* trait counting at step 3. `apply_bundle` already appends `granted_traits` to `target.traits`, so when T.29 lands, applying item bundles before `_resolve_traits` is sufficient — document this ordering as a hard contract so emblems count.
- Determinism: pure function of the team's `(id, traits)` — no RNG, replay-stable. → new invariant (§10).

### 3.3 Affinity-trait synthesis

Affinity traits (Sunlit … Galvanized) are **derived from `piece.affinity`**, not stored tags (catalog §1, §3; keeps V.6/V.8 clean — affinity stays one field). At resolution, inject a synthetic trait tag per piece: `affinity_trait(piece.affinity)` → `"Sunlit"` etc., counted alongside native tags. Never reads live node weather. Implementation: extend the counting loop to add the affinity-derived tag, or stamp it onto `piece.traits` at piece-build time (prefer the counting-loop approach so `Champion.traits` stays authored-only and the V-guard in §10 doesn't trip on synthetic tags).

### 3.4 New combat primitives + fidelity policy

Several breakpoints need mechanics that don't exist yet. **Determinism is mandatory** (V.2 / V.14 — combat is replay-identical, sims byte-identical): every "chance"-flavoured effect uses a **deterministic cadence counter** like the existing `crit_counter` ([piece.py:57](../../../src/game/piece.py#L57)), **never RNG**. "Dodge 15% of autos" = dodge every Nth incoming auto (N = round(1/0.15)); "every few autos/casts" = a per-piece counter. Same idiom as crit in [combat/loop_new.py:212](../../../src/game/combat/loop_new.py#L212).

**Per your steer, MVP-simplify the most engine-invasive breakpoints** (flag for a later fidelity pass) and build the rest at full fidelity:

**Tier A — build full (generic primitives, content-agnostic, like T.30 summons):**

| Primitive | Needed by | Mechanism |
|---|---|---|
| **`shield`** — absorb pool, depletes before HP | Guardian, Warden, Mender, Bruiser-adjacent | **`Piece.shield_hp: float` field** (+ optional `shield_expires_tick`), NOT a `StatusInstance` (it has no value field). Absorb in `deal_damage` ([context.py:244](../../../src/game/combat/context.py#L244)) before subtracting HP; apply via an `on_combat_start`/`on_cast` hook in the factory. |
| **`untargetable`** — excluded from target selection | Spirit @4, Shrouded @4/@6, Stalker @6 | new `StatusGate.UNTARGETABLE`; filter in `_opponents`/`_select_target` ([loop_new.py:86,91](../../../src/game/combat/loop_new.py#L86)) + [targeting.py](../../../src/game/targeting.py). Piece can still act. |
| **`taunt`** — forces an enemy to target the taunter | Trickster @4 | `taunt` status on the *enemy*, `source_id` = taunter; in `_select_target`, if the acting piece has an active taunt, force-target its `source_id` (if alive + in range). |
| **deterministic `dodge`** | Skirmisher @4 | cadence counter on `Piece`; in `deal_damage`/`_apply_hit`, every Nth incoming `BASIC_ATTACK` deals 0. |
| **`revive`-once** | Tidekin @5, Mender @6 | guard flag in `augment_state`-style per-combat dict on the piece; intercept in the kill path ([context.py:262](../../../src/game/combat/context.py#L262)) — restore to a fraction of `max_hp`, fire once. Reuse for T.31 Sanctuary augment later. |
| **time-ramp stats** | Beast @4/@6, Skirmisher @2 | `on_tick` hook adds a stacking `mul` `Modifier` every K ticks up to a cap. |
| **echo / double-cast** | Spirit @6, Channeler @6 | `on_cast`/cast-counter hook that re-invokes the handler at reduced potency / for free. |
| **mana-denial aura** | Trickster @6 | `on_tick` hook reducing nearby enemies' mana gain (radius check via `hex_distance`). |

**Tier B — MVP-simplify now, full-fidelity later (flagged):**

| Breakpoint | Designed | MVP proxy |
|---|---|---|
| Skyborn @2 "ignore piece collision while moving" | skip `occupied` cells in `_next_step_toward` ([loop_new.py:111](../../../src/game/combat/loop_new.py#L111)) | grant Move Speed instead (same "closes faster" intent); leave collision untouched |
| Skyborn @4 "act first in same-tick ties" | inject into `_event_sort_key` ([loop_new.py:378](../../../src/game/combat/loop_new.py#L378)) — `speed_tiebreaker` isn't a stat | fold into the @4 Attack-Speed bonus (higher AS already sorts earlier) |
| Stalker @2 "start repositioned to enemy backline" | mutate spawn position pre-loop (interacts with `assign_spawns` [loop_new.py:517](../../../src/game/combat/loop_new.py#L517)) | grant a large opening Move-Speed burst so Stalkers reach the backline fast |

> `ability_can_crit` (Mystic @4) already exists as a `Piece` flag. `EffectBundle` has no "set bool" channel, so set it via a tiny `on_combat_start` hook in the breakpoint factory (`lambda ctx, ev: setattr(owner, "ability_can_crit", True)`).

### 3.5 BattleResult activation record

Record which traits were active at which breakpoint, for the run summary / debugging. Add `trait_activations: list[tuple[str, int, int]]` (trait id, count, breakpoint) to `BattleResult` ([models.py:512](../../../src/game/models.py#L512), + `to_dict`/`from_dict`).

**Wrinkle:** trait activations are known at **compile time** (`_resolve_traits`), not via combat events — but the recorder ([recorder.py:44](../../../src/game/combat/recorder.py#L44)) is built from `pieces` and only listens to bus hooks. So the cleared-traits dict must be **surfaced out of `compile_loadout`** (cleanest: change its return to also yield `cleared`, or stash it on the returned `bus`/a small loadout-result object) and threaded into `recorder.build_result`. This touches the `compile_loadout` → `resolve_combat` → recorder wiring ([combat/legacy.py](../../../src/game/combat/legacy.py)) — keep the change additive and back-compat. Data-only; no combat behaviour.

---

## 4. Threshold decision (catalog §6 open q)

The catalog flags that with a 3-champion start climbing to a 10-cap (T.22 Tempest), `@6` breakpoints only matter very late. **Proposed:**

- **Kinships:** keep `@2 / @4 / @6` (reachable mid-late; emblems help).
- **Affinities:** keep `@2 / @4 / @6` (10 carriers each — mono-affinity is a deliberate late commitment).
- **Callings:** keep authored thresholds as in catalog §4 (most `@2/@4/@6`; Tidekin/Swarm/Primordial use their listed odd thresholds `@3/@5/@7`, `@1/@2/@3`).
- Leave the "compress some to 2/3/4" idea as a **post-sim tuning lever** — validate with a `sim_run` / matchup sweep over leveled boards once values exist, then retune. Don't pre-optimize.

---

## 5. Authored breakpoint values (first pass — tunable)

Values are **first-pass tuning**, recorded here as the source until a sim pass retunes them. **Stat bonuses are percentages (`mul` modifiers)** so they scale across T1–T10 — flat adds would be trivial at high tier and oppressive at low. Convention: minor ≈ **+8%**, moderate ≈ **+15%**, major ≈ **+24%** per named stat. `source_id` pattern `trait:<id>@<n>`.

### 5.1 Affinities (stat packs, `PER_TRAIT_PIECE`)

| Trait | @2 minor | @4 moderate | @6 major | Extra |
|---|---|---|---|---|
| Sunlit | +8% all combat stats | +15% all | +24% all | — |
| Overcast | +8% hp,resistance | +15% | +24% | — |
| Shrouded | +8% move_speed,threat | +15% + `untargetable` 80t opener | +24% + `untargetable` 150t opener | ethereal rider |
| Stormfed | +8% attack_speed,mana_regen | +15% | +24% | — |
| Frostbound | +8% armor,resistance | +15% | +24% | — |
| Galvanized | +8% strength,attack_speed | +15% | +24% | — |

"all combat stats" = strength, intelligence, attack_speed, move_speed, armor, resistance, hp (not crit/pen).

### 5.2 Kinships (`PER_TRAIT_PIECE` unless noted)

| Trait | @2 | @4 | @6 |
|---|---|---|---|
| **Beast** | +12% hp + regen 0.5%/100t | + slow-burn: +2% strength/200t alive (cap +20%) | ramp doubles (+4%/200t) + 15% lifesteal on damage dealt |
| **Skyborn** | +10% attack_speed + ignore-collision (movement flag) | + +1 attack_range + win same-tick ties (speed_tiebreaker boost) | + opening 600t: +40% attack_speed |
| **Scaled** | +12% armor,resistance | + immune to Weather Favor debuff (skip negative `combat_modifier`) | + treat every node weather as strong-tier self-buff |
| **Tidekin** | heal 0.4% max_hp/200t | (@3) +25% healing done & received | (@5, `TEAM_WIDE`) once/combat undertow: revive at 30% max_hp |
| **Swarm** | (@3) on-death chitin spawn (summon primitive, T.30) | (@5) +4% all stats per other living Swarm + bigger spawn | (@7) spawns can themselves spawn once |
| **Spirit** | start +30% mana + +20% mana_regen | + `untargetable` 150t opener + −20% ability cost | + every 3 casts: free echo-cast at 50% potency |

### 5.3 Callings

| Trait | @2 | @4 | @6 |
|---|---|---|---|
| **Hunter** | +12% auto damage (on_attack_landed bonus) | + every 4 autos an empowered shot (1.6×) | + +1 attack_range, empowered shots pierce |
| **Guardian** | `shield` = 15% max_hp at start | + shield → adjacent allies, refresh/round (600t) | + while shielded, adjacent allies −12% damage taken |
| **Mystic** | +12% intelligence | + +12% intelligence & set `ability_can_crit` | + ability hits splash 40% to one neighbour |
| **Warden** | on-cast: shield lowest-HP ally 10% their max_hp | + Warden shields/buffs last +50% duration | + at start, whole team gains 8% max_hp shield (`TEAM_WIDE`) |
| **Stalker** | start repositioned to enemy backline | + +25% damage vs targets >70% HP, mana refund on kill | + `untargetable` 120t after a takedown |
| **Bruiser** | +12% hp | + +15% hp & +12% strength | + 15% lifesteal on auto damage |
| **Skirmisher** | stacking +3% attack_speed per hit on same target (cap +24%) | + +12% move_speed & dodge 15% of autos | + (`TEAM_WIDE` melee) ramp no longer decays |
| **Channeler** | +20% mana_regen | + every 4 casts the next ability is free | + first cast each combat triggers twice |
| **Mender** | +25% healing done | + overheal → shield | + (`TEAM_WIDE`) first ally death/combat → revive at 25% max_hp |
| **Trickster** | on-cast: apply slow/wither debuff | + +threat & `taunt` target 100t on cast | + enemies near a Trickster gain mana 30% slower |
| **Packmate** | (`TEAM_WIDE`) +5% all stats | + bonus scales: +1.5% per champion fielded | + full board (== cap): +18% flat all stats |
| **Primordial** | (@1) signature mechanic active (per-champ, T.30 kit) | (@2, `TEAM_WIDE`) large +18% stat pack + Primordial second-wind once/combat | (@3) highest other trait counts as one tier higher |

(Mechanics tagged "hook" — Hunter empowered shot, Channeler double-cast, echo-casts, lifesteal, on-death spawns — reuse existing ability-handler idioms in [champions.py](../../../src/game/abilities/champions.py): `on_attack_landed`/`on_cast`/`on_death`/`on_damage_dealt` hooks + `ctx.deal_damage`/`ctx.heal`/`ctx.spawn`.)

---

## 6. Roster audit + vocabulary reconciliation

### 6.1 Calling-vocabulary drift (must fix first)

Git-confirmed: `CALLING_TAGS` ([content.py:101-118](../../../src/game/content.py#L101-L118)) carries **4 dead tags** — `Bulwark, Drifter, Harbinger, Emissary` — introduced in the original T.5 commit (6936634), assigned to **no champion**, referenced nowhere else, and **never present in any design doc in any commit**. `Packmate` (catalog's 12th Calling, ~8 intended T1–3 carriers) is **absent** from `CALLING_TAGS` and has 0 carriers. The two design docs agree on 12; the code is vestigial T.5 scaffolding.

**Resolution — catalog canonical (the 12):**
- Remove `Bulwark, Drifter, Harbinger, Emissary` from `CALLING_TAGS` (and `ALL_TRAIT_TAGS`).
- Add `Packmate`; **assign ~8 T1–3 filler champions** to it per catalog §5 (small, reversible roster edit, part of T.28). *(Overridable: cut Packmate instead for an 11-Calling set — but that drops the wide-board archetype; default is assign.)*
- End state: 12 Callings, each with carriers **and** a `@register_trait` factory — satisfies the §10 V-guard (no tag without breakpoints, no breakpoint set without carriers).

### 6.2 Roster completeness

- Affinity traits: **auto-derived** (§3.3) — no content edits; all 60 covered by construction (10 per affinity).
- Kinship + Calling: already assigned in [content.py](../../../src/game/content.py) (authoritative design: [champion_roster.md](../content/champion_roster.md)). Audit all 60 `_champion_def` rows carry exactly one Kinship + one or two Callings; T10s additionally carry `Primordial`. Fill gaps (incl. the new Packmate carriers); add a test asserting every champion has ≥1 Kinship + ≥1 Calling and every tag resolves in `TRAIT_REGISTRY`.
- Enemies carry no synergy (catalog §1) — `piece_from_enemy` already sets `traits=[]`; leave as-is. (Enemy quest-match tags are T.31's concern.)

---

## 7. Open questions

**Resolved here (proposals, overridable):**
- Threshold scheme → keep catalog thresholds; compression is a post-sim lever (§4).
- Affinity-trait counting → synthetic derived tag in the resolution loop (§3.3).
- `ability_can_crit` / shields / untargetable / taunt → `on_combat_start` hook + new status primitives (§3.4).

**Resolved by investigation:**
- **Calling-vocab drift** → catalog canonical; drop 4 dead T.5 tags, add Packmate + carriers (§6.1).
- **Fidelity** → Tier-A breakpoints full, Tier-B (Skyborn collision/tie, Stalker reposition) MVP-simplified to proxies, flagged (§3.4).

**Still open / deferred:**
- **Packmate carriers** — which ~8 T1–3 champions get the tag (§6.1). Default: pick from existing low-tier fillers; trivial to adjust.
- **Tier-B fidelity pass** — restore Skyborn collision-ignore / same-tick-tie + Stalker start-reposition to full fidelity post-MVP (needs movement/spawn/sort-key engine touches).
- **Breakpoint values** (§5) — first pass; retune after a leveled-board sim sweep.
- **Two-Kinship hybrids** (catalog §6) — every champion has one Kinship for now; revisit if draft feels thin.
- **Primordial @3** (catalog §6) — author it but gate behind the "3 Tier-10s" rarity; cheap to cut if unused.
- **Emblem scarcity / drop economy** — T.29 + D.12.

---

## 8. Test plan

- **Counting:** unique champion ids; two copies of one champion count once; highest cleared breakpoint wins, lower suppressed.
- **Scope:** `PER_TRAIT_PIECE` bundle hits only carriers; `TEAM_WIDE` hits all team pieces; enemies never gain trait bundles.
- **Affinity synthesis:** N same-affinity champions light the affinity trait at the right breakpoint without touching node weather.
- **`granted_traits` ordering:** a piece given a trait via `granted_traits` is counted by `_resolve_traits` (simulate an emblem bundle pre-resolution).
- **Primitives:** `shield` absorbs then HP and depletes; `untargetable` excluded from `_select_target`/`_opponents`; `taunt` forces target; `revive` fires once; each expires correctly.
- **Determinism of cadence mechanics:** dodge / "every Nth auto" / "every few casts" fire on the fixed Nth occurrence with **no RNG** — same seed and `workers=1` byte-identical (V.2/V.14).
- **Vocabulary guard:** `CALLING_TAGS` == the 12 catalog Callings (4 dead tags gone, Packmate present); every champion tag resolves in `TRAIT_REGISTRY`; Packmate has ≥ its intended carriers.
- **Determinism:** trait resolution byte-identical across runs for a fixed team; full-suite combat regression (no-trait teams unchanged).
- **Effect:** a fixed-seed fight where a met breakpoint measurably shifts the outcome vs the same team below the breakpoint.
- **V-guard:** every tag in every `Champion.traits` resolves in `TRAIT_REGISTRY`; every champion has ≥1 Kinship + ≥1 Calling.

---

## 9. Acceptance criteria

1. `TraitScope`/`TraitBreakpoint` types + `@register_trait` factories for all 24 traits with authored values (§5), populating `TRAIT_REGISTRY`.
2. `compile_loadout` resolves + applies trait bundles (unique-id count, highest breakpoint, correct scope), player-team only, slotted per §10.1.
3. Affinity traits derived from `affinity`, weather-independent.
4. Tier-A primitives (shield, untargetable, taunt, deterministic dodge, revive, time-ramp, echo, mana-aura) implemented and honored in loop/targeting/`deal_damage`; Tier-B breakpoints shipped as the §3.4 proxies, flagged for a later fidelity pass.
5. `BattleResult` carries the trait-activation record (surfaced from `compile_loadout`).
6. Calling vocabulary reconciled (§6.1 — 4 dead tags removed, Packmate added + carriers); roster audit complete; V-guard test green.
7. All cadence mechanics deterministic (no RNG); `workers=1` / fixed-seed byte-identical.
8. `tests/game/test_traits.py` + loadout/combat tests pass; full suite green; no-trait regression intact.

---

## 10. SPEC changes needed (for `/spec`)

1. **§T:** replace the single T.28 row with **two rows — T.28a** (framework + declarative content, Est M) and **T.28b** (combat primitives + mechanic breakpoints, depends T.28a, Est M–L); both 📋 Plan; both cite `docs/design/tasks/t28_trait_effects_plan.md` (§0 defines the split). Update the Implementation-Order Phase 1b chain to `… → T.28a → T.28b → …`.
2. **New invariant (≈V.20):** trait breakpoints count **unique champion ids**; trait effects enter combat **only** via `compile_loadout` (never alongside `resolve_combat`); resolution is a pure, RNG-free function of the team — replay-stable. (T.28)
3. **New invariant (≈V.21):** every tag in `Champion.traits` **must** resolve in `TRAIT_REGISTRY`, and every champion carries ≥1 Kinship + ≥1 Calling (+ `Primordial` at T10) — CI-guarded, mirroring V.15. Enemies carry no synergy. (T.28)
4. **§D.8:** mark trait effects as implemented in T.28; leave open only breakpoint-value tuning, the Tier-B fidelity pass (§3.4), and the two-Kinship-hybrid question.
5. **New §B entry:** calling-vocabulary drift — `CALLING_TAGS` carried 4 dead T.5 tags (`Bulwark/Drifter/Harbinger/Emissary`, 0 carriers, never in design docs) and omitted `Packmate`. Cause: T.5 ad-hoc calling set never reconciled with the later `trait_catalog.md`/`champion_roster.md` 12-Calling design. Fix in T.28 (§6.1); **V.21** prevents recurrence (every tag must resolve in `TRAIT_REGISTRY`).
6. **T.28 planning note** (in the T.18-T.31 notes block): implements the synergy layer on the T.20 substrate; adds shield/untargetable/taunt/dodge/revive/ramp/echo primitives (deterministic cadence, no RNG — V.2); affinity traits derived from `affinity`; Tier-B mechanics (Skyborn collision/tie, Stalker reposition) MVP-simplified, flagged; values are a first pass pending a sim retune.
7. **T.29 row note:** emblem items (T.29) rely on the `granted_traits`-before-resolution ordering this task establishes (§3.2).
8. **Estimate:** split into T.28a (M) + T.28b (M–L) per §0 — supersedes the original single `L` row.
