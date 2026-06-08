# T.28d Plan — Trait apexes + hexproof correctness + deferred-flavor fold-ins

> **Status:** plan — ready for review. (§T.28d **status flip** `📋 Plan → ~`, with a **rewritten goal line** — Primordial content moves out; a hexproof rename/fix moves in.)
> **Depends:** T.28c (done — riders batch 2 + `ctx` idioms). No unbuilt deps gate this; all touch points exist.
> **Resolves:** the last reachable slice of SPEC §T.28. Defers the two *dormant* Primordial pieces to T.31.
> **Design source of truth:**
> - [`docs/design/content/trait_catalog.md`](../content/trait_catalog.md) v2.1 — §"Primordial" (line 176), affinity apex intent, "deferred flavour" rungs.
> - [`docs/live/content/traits.md`](../../live/content/traits.md) — current trait taxonomy, cumulative-rung rule, T.28d pending list.
> - [`docs/design/tasks/t28_trait_effects_plan.md`](t28_trait_effects_plan.md) + [`t28d_handoff.md`](t28d_handoff.md) — prior slices, gotchas.
> - SPEC §V.21/§V.22/§V.37 (traits), §V.28 (barriers), §V.34 (stat-scaling/total-order), §V.2/§V.14 (determinism).
> **What this plan adds beyond those:** the 5 affinity-@10 rider mechanics + Sunlit premium-stat extension (catalog leaves these as concepts); the Scaled @5/@8 mechanics; the Spirit @8 three-part upgrade; **the hexproof bug fix + rename** (a drift/correctness finding, not in the catalog); authored first-pass numbers for all of the above; 4 new RNG-free mechanic builders.
> **Not yet applied to SPEC** — needs `/spec` to flip + rewrite the §T.28d row, add §V.40, §B.15, §D.20. §10 lists the exact deltas. Do not edit SPEC inline.

---

## 0. Substep split — none

T.28d is now small enough to ship as one unit (the Primordial subsystem work that justified a split has been removed — see §1). All changes are RNG-free and land together with one test pass. If the hexproof rename proves noisy in review it can be cherry-split, but it is planned as one task.

## 1. Scope

**In scope:**
1. **Hexproof rename + correctness fix** (`status.py`, `combat/engine.py`, `targeting.py`, `piece.py`, `traits/mechanics.py`, `traits/{callings,kinships}.py`, tests):
   - Rename status `untargetable` → `hexproof`; `StatusGate.UNTARGETABLE` → `StatusGate.HEXPROOF`; riders `untargetable_opener` → `hexproof_opener`, `untargetable_after_kill` → `hexproof_after_kill`.
   - **Bug fix:** the single-target acquisition helpers in `targeting.py` never filtered the gate (only the engine auto-attack path did), so *targeted* abilities hit hexproof pieces. Add the filter; AoE / untargeted effects still hit (MTG-hexproof semantics).
   - `Piece.pierces_hexproof` marker → carriers bypass the filter (the lone exception, wired to Spirit @8).
2. **Affinity @10 apex riders** (`traits/affinities.py`, `traits/mechanics.py`): 5 mechanical riders (Galvanized / Frostbound / Stormfed / Shrouded / Overcast) + **Sunlit stays stat-only** but its packs gain small premium-stat entries.
3. **Scaled @5 CC-immunity + @8 weather-as-buff** (`piece.py`, `combat/context.py`, `loadout.py`, `traits/kinships.py`): `Piece.cc_immune` marker + `apply_status` guard for hard-CC (gate-bearing) statuses; `Piece.weather_favored` marker + favorable-pack override in `_apply_weather_to_piece`, sequenced before weather application.
4. **Spirit @8 three-part upgrade** (`traits/kinships.py`, `traits/mechanics.py`, `combat/context.py`): reduced-potency echo via a transient `ctx._echo_potency` damage multiplier; `mana_regen` ability-haste (stat pack); `pierces_hexproof` flag (from item 1).
5. **Deferred-flavor fold-ins** (`traits/{kinships}.py`, `traits/mechanics.py`): Beast @4/@6 strength ramp (`time_ramp(stat="strength")`), Skyborn @3 kite-reward (`kite_reward`), Tidekin @3 heal-lowest-ally (`ally_tidal`).
6. **§B.15** (hexproof bug) + **§V.40** (hexproof targeting invariant) + tests.

**Out of scope (with why):**
- **6 Primordial @1 signature mechanics** → **T.31.** The catalog (line 176) defines @1 as a "signature mechanic," but the 6 are *un-authored* net-new design, and the 6 legendaries already carry full `.active`+`.passive` kits from T.30. They are unreachable + untunable until T.31's unlock augments exist. Primordial @1 ships as its existing stat pack (`callings.py:140`). (§D.20)
- **Primordial @3 aspirational tier-up** → **T.31 / §D.** Needs a trait re-resolve/fixpoint pass and is double-dormant (3 Primordials, all augment-gated). Catalog itself flags @3 "aspirational … not balanced content" (line 315). (§D.20)
- **Ability-haste as a new primitive** → never. No cooldown system exists (abilities gate on per-`ActiveSlot` mana). "Ability haste" = a `mana_regen` stat buff, folded into the relevant stat packs (Spirit @8, Stormfed @10). No engine work.

## 2. The gap today

| Piece | Where (`file.py:line`) | State |
|---|---|---|
| `untargetable` status + `StatusGate.UNTARGETABLE` | `status.py:34,132-136` | ✅ exists — to be **renamed** hexproof |
| Auto-attack hexproof filter | `combat/engine.py:99` (`p.is_gated(StatusGate.UNTARGETABLE)`) | ✅ correct (autos) |
| Single-target acquisition filter | `targeting.py:34-65,117-125,170-177` | 🔴 **drift/bug** — `primary_target`/`lowest_hp_enemy`/`highest_ap_enemy`/`random_enemy`/`furthest_enemy`/`_closest_enemy` filter only fog, **not** the gate → targeted casts hit hexproof pieces |
| `pierces_hexproof` / `cc_immune` markers | `piece.py:72-73` (`is_kiter`/`seeks_backline` precedent) | ❌ missing — add two bool fields |
| `Piece.is_gated(gate)` | `piece.py:128` | ✅ exists |
| Affinity @10 rungs | `traits/affinities.py:16-41` | 🔶 stat-only (no riders); built by the `_TWO` loop |
| Sunlit packs | `traits/affinities.py:16-23` | 🔶 7 stats, **no premium stats** (crit/pen/mana_regen) |
| Scaled @5/@8 | `traits/kinships.py:51-57` | 🔶 stat-only; comment still says "weather-immune/weather-as-buff = T.28c" (stale → T.28d) |
| Weather application | `loadout.py:174-181` (`_apply_weather_to_piece` → `combat_modifier(affinity, weather)`), called step 2 (`loadout.py:229-231`) | ✅ — needs a `weather_favored` branch + a pre-step-2 marker pass |
| Trait resolution | `loadout.py:233-237` step 3 (`resolve_and_apply_traits`) | ✅ — runs *after* weather (sequencing wrinkle for Scaled @8) |
| Spirit @8 echo | `traits/kinships.py:35` (`echo_cadence(3)`) | 🔶 full-potency; no haste/pierce |
| `_recast` / `echo_cadence` | `traits/mechanics.py:408-422,440-455` | ✅ — `ctx._in_recast` guard exists; add `ctx._echo_potency` |
| `deal_damage` | `combat/context.py:185-280` | ✅ — add one `raw *= ctx._echo_potency` line |
| `apply_status` | `combat/context.py:303-350` | ✅ — add `cc_immune` early-return for gate-bearing statuses |
| Beast @4/@6, Skyborn @3, Tidekin @3 | `traits/kinships.py:22-23,45,63` | 🔶 stat-only (deferred flavor) |
| `crit_arc` / `chill_attackers` / `burst_reduction` / `kite_reward` / `ally_tidal` builders | `traits/mechanics.py` | ❌ missing — 4-5 new RNG-free builders |

## 3. Architecture

### 3.1 Hexproof rename + targeting fix
- **Semantics (the invariant, §V.40):** a `hexproof` piece is excluded from **single-target acquisition** (the `targeting.py` single-target helpers **and** the engine auto-attack acquisition at `engine.py:99`) but **not** from AoE / untargeted effects (`enemies_in_radius`, `line_targets`, `neighbors_of`, and the full `ctx.enemies_of` list a cast iterates). A piece with `pierces_hexproof` ignores the exclusion.
- **Why AoE still hits:** `cast_ability` (`context.py:412`) hands the handler `list(self.enemies_of(actor))` (the full living-enemy list). AoE abilities iterate it directly — they must keep hitting hexproof pieces. Only the *single-target selectors* gate. This is exactly MTG hexproof: "can't be the **target** of an opponent's spell; AoE/sweepers still catch it."
- **Plug-in point:** add a private `_targetable(actor, e, ctx)` predicate in `targeting.py` and apply it inside the six single-target helpers (`primary_target`, `lowest_hp_enemy`, `highest_ap_enemy`, `random_enemy`, `furthest_enemy`, `_closest_enemy`). Predicate: `not e.is_gated(StatusGate.HEXPROOF) or actor.pierces_hexproof`. Keep `_filter_fog` as-is and compose.
  - `targeting.py` currently has no `status` import — add `from src.game.status import StatusGate` (no game→ui/api coupling; V.1 safe).
- **Rename mechanics:** pure find/replace across `status.py` (id + enum + `UNTARGETABLE` module constant), `engine.py:99` + comments (`engine.py:90-92`), `traits/mechanics.py` (`untargetable_opener`→`hexproof_opener`, `untargetable_after_kill`→`hexproof_after_kill`, their `apply_status(..., "untargetable")` calls), `traits/kinships.py:34`, `traits/callings.py:82`, `docs/live/content/traits.md` (lines 93,113,129), and all tests referencing the old id. The status **string id** `"untargetable"` → `"hexproof"` (no serialized saves yet — T.14 unbuilt — so no migration).
- **`pierces_hexproof` marker:** set on Spirit @8 carriers via a tiny `on_combat_start` rider (or directly in the trait apply); cleared by default. Same lifecycle pattern as `is_kiter`.

### 3.2 Affinity @10 riders (`traits/affinities.py` restructure)
- **Wrinkle:** the `_TWO` loop (`affinities.py:33-41`) builds all five 2-stat affinities identically, so a *per-affinity* @10 rider can't ride the shared loop. Restructure: keep @2–@8 in the loop (or a shared rung-builder), then **append a per-affinity @10 rung** carrying that affinity's rider. Scope stays `PER_TRAIT_PIECE` — at @10 the board is 10 mono-affinity uniques, so PER == TEAM in practice; no scope change needed (avoids the TEAM-apex movement-mechanic caveat entirely; these riders are all damage/defensive, team-safe regardless).
- **Riders (all `traits/mechanics.py` hook idioms, RNG-free):**
  - **Galvanized** `crit_arc(frac)` — `on_damage_dealt`, `event.is_crit` → arc `frac`·hit to one neighbour of the target (`neighbors_of`, deterministic pick by `id`). Tag `SourceTag.ITEM_PROC` (no re-fire recursion, per the T.28c rule).
  - **Frostbound** `chill_attackers(slow_dur)` — `on_damage_taken` (carrier is target) → `apply_status(attacker, "slow", slow_dur)`. Re-entry-safe (slow has no gate; applies to attacker, not self).
  - **Stormfed** — `mana_regen` stat bump in the @10 pack (ability-haste). **No builder** (declarative).
  - **Shrouded** — reuse `hexproof_opener(duration=<longer>)` (the renamed opener) at @10. Longer team opener.
  - **Overcast** `burst_reduction(cap_frac)` — `on_damage_pre` reducing hook: clamp a single hit to `cap_frac·max_hp` (anti-burst). Reducing hook returns `min(value, cap_frac*target.max_hp)`.
  - **Sunlit** — **no rider.** Extend its stat pack to include premium stats (`crit_chance`, `penetration`, `mana_regen`) at small values; magnitudes deliberately low (full-Clear's no-weakness identity is already strong — see §5).

### 3.3 Scaled @5 CC-immunity + @8 weather-as-buff
- **CC-immunity (@5):** add `Piece.cc_immune: bool`. In `apply_status` (`context.py:303`), after the `STATUS_DEFS` lookup, **early-return** when `target.cc_immune and status_def has any of `{BLOCKS_ACTION, BLOCKS_CAST, BLOCKS_ATTACK, BLOCKS_MOVEMENT}``. This blocks stun/frozen/fear/silence/disarm/root; **leaves** `slow` (no gate — soft CC), DoTs (`burn`/`poison`), `soaked`, `taunt`, `hexproof`, `charged`, `focus_fire` landing. Set `cc_immune` on Scaled @5+ carriers (an `on_combat_start` rider or set at apply). **Cumulative:** @8 must re-include the CC-immunity (it currently has no rider; add the marker-set to both @5 and @8).
- **Weather-as-buff (@8):** add `Piece.weather_favored: bool`. In `_apply_weather_to_piece` (`loadout.py:174`): if `piece.weather_favored`, use the favorable pack at SELF tier for the node weather regardless of affinity — i.e. `modifier = WEATHER_BUFF_BASE[weather]` (the strong-tier buff; `CLEAR` → `IDENTITY`, unchanged) instead of `combat_modifier(piece.affinity, weather)`.
  - **Sequencing wrinkle (the load-bearing bit):** weather is applied **step 2** (`loadout.py:229`), trait resolution **step 3** (`loadout.py:233`). So `weather_favored` must be set **before** step 2. Add a small pre-pass `mark_weather_overrides(team, board_cap)` (in `traits/__init__.py`) called immediately before step 2: it runs `_resolve_traits` (already pure/RNG-free), and for any team that cleared **Scaled @8** sets `weather_favored=True` on each Scaled carrier. Step 3 then applies the Scaled @8 *stat* bundle normally (the weather override already happened). The extra `_resolve_traits` call is loadout-time only (negligible) and deterministic.
  - **Alternative considered + rejected:** undo-then-reapply weather inside the trait bundle (messy — must reverse the already-applied debuff modifier); or reorder steps 2/3 wholesale (entangles the HP re-sync that reads post-weather `stat("hp")`). The marker pre-pass is the least-invasive correct option.

### 3.4 Spirit @8 reduced-potency echo
- `_recast` (`mechanics.py:408`) already brackets the recast with `ctx._in_recast = True/False`. Extend it to accept an optional `potency: float = 1.0`; set `ctx._echo_potency = potency` for the duration of the recast, restore to `1.0` after (try/finally, mirroring the `_in_recast` reset).
- `echo_cadence` gains a `potency` param threaded into `_recast`. Spirit @5 keeps `echo_cadence(4)` (full potency, unchanged); Spirit @8 → `echo_cadence(3, potency=0.6)`.
- `deal_damage` (`context.py:204`, right after `raw = amount`): `raw *= getattr(ctx, "_echo_potency", 1.0)`. Damage-only by design — heals/shields in the echoed ability stay full (acceptable; broader potency was explicitly out of scope).
- **Determinism:** `_echo_potency` is a deterministic flag toggled on the call stack (like `_in_recast`); no RNG. Sims stay byte-identical except where the @8 echo's damage now differs — that is the intended behaviour change, covered by updated snapshots.
- **Hexproof pierce:** Spirit @8 also sets `pierces_hexproof` on carriers (from §3.1). Spirit @5/@8 already apply `hexproof_opener`; the pierce lets a Spirit caster's *targeted* ability still pick a hexproof enemy.

### 3.5 New mechanic builders + fidelity policy
All are **Tier-A full** (no MVP proxy), RNG-free hook idioms over existing `ctx` mutators, following the T.28c idiom set:
- `crit_arc(frac=0.5)` → `on_damage_dealt` (`HookScope.PER_HIT`), guarded `event.is_crit` + `event.attacker is owner`.
- `chill_attackers(duration=200)` → `on_damage_taken`, `event.target is owner`, `apply_status(attacker, "slow", duration)`.
- `burst_reduction(cap_frac=0.25)` → `on_damage_pre` reducing, returns `min(value, cap_frac*owner.max_hp)`.
- `kite_reward(frac=0.15)` → `on_damage_dealt`, bonus `ITEM_PROC` damage when `target.stat("attack_range") < hex_distance(owner,target)` (the target can't reach back).
- `ally_tidal(interval=200, heal_frac=0.02)` → `on_tick` cadence heal of the **lowest-HP ally** (`lowest_hp_ally`) — Tidekin @3. (Distinct from `tidal_hot`, which heals the carrier.)

All cadence/threshold based; no `ctx.rng` use. Each gets a determinism test (§8).

## 4. Decisions that need stating

| # | Decision | Choice + rationale |
|---|---|---|
| D1 | Primordial @1 signatures | **Defer to T.31.** Premise changed: legendaries already have full T.30 kits; the 6 signatures are un-authored + untunable until reachable. @1 ships as its stat pack. (User-confirmed after the T.30 finding.) |
| D2 | Echo potency | **Reduced via transient `ctx._echo_potency`** (damage-only, first-pass `0.6`). Minimal new surface (1 line in `deal_damage` + try/finally in `_recast`). |
| D3 | Affinity @10 scope | **5 mechanical riders + Sunlit stat-only** (premium-stat extension). Sunlit kept deliberately weak (no-weakness identity already strong). |
| D4 | Hexproof model | **MTG-hexproof:** single-target acquisition (helpers + engine auto) excludes hexproof; AoE/untargeted still hits; `pierces_hexproof` is the lone bypass. This is a **bug fix** (§B.15) + a rename, gated by a new invariant (§V.40). |
| D5 | CC-immunity scope | **Hard-CC only** — block the four `BLOCKS_*`-gated statuses; `slow`/DoTs still land. Keeps counterplay. |
| D6 | Weather override strength | **Full favorable override** (Scaled @8 always gets the strong buff pack), via a pre-step-2 `weather_favored` marker pass. |
| D7 | Affinity @10 trait scope | **Keep `PER_TRAIT_PIECE`** (not TEAM) — at @10 the board is mono-affinity so PER==TEAM; avoids the TEAM-apex movement caveat; riders are team-safe anyway. |
| D8 | Fold-ins | **All three** (Beast @4/@6 ramp, Skyborn @3 kite-reward, Tidekin @3 ally-heal) — cheap idioms; completes the trait surface for the single T.25 re-baseline. |

## 5. Authored values (first-pass, tunable — flag in code)

**Affinity @10 riders:**
- Galvanized `crit_arc(frac=0.5)` — half the crit splashes to one neighbour.
- Frostbound `chill_attackers(duration=200)` — 2s slow on whoever hits a Frostbound carrier.
- Stormfed @10 pack — add `mana_regen: 0.30` (on top of the existing `attack_speed`/`mana_regen` 0.27 two-stat) → ability-haste.
- Shrouded `hexproof_opener(duration=300)` at @10 (vs Spirit's default 150) — longer opener.
- Overcast `burst_reduction(cap_frac=0.25)` — no single hit exceeds 25% max-HP.
- **Sunlit premium extension** (small, on the @10 rung; magnitudes low by design): `crit_chance: 0.04`, `penetration: 0.04`, `mana_regen: 0.06` *added alongside* the existing 7-stat 0.16 pack. (Optionally seed tiny premium amounts on @6/@8 too — flagged tunable; default: @10 only to keep it an apex flourish.)

**Scaled:** @5 sets `cc_immune` (hard-CC); @8 sets `weather_favored` + re-includes `cc_immune`. No new numbers (markers, not stats).

**Spirit @8:** `echo_cadence(3, potency=0.6)`; `mana_regen` already in the @8 pack (`0.15`) — bump to `0.20` for the haste identity (tunable). Sets `pierces_hexproof`.

**Fold-ins:**
- Beast @4 `time_ramp(stat="strength", per=0.02, cap=8)`, @6 `time_ramp(stat="strength", per=0.03, cap=8)` (re-include enrage at @8 — already present).
- Skyborn @3 `kite_reward(frac=0.15)`.
- Tidekin @3 `ally_tidal(interval=200, heal_frac=0.015)` (lighter than the carrier `tidal_hot` 0.02; @5/@8 keep `tidal_hot` — decide whether to also carry `ally_tidal` upward: default **yes at @5/@8** so the ally-reach persists per the cumulative rule).

> **All magnitudes are first-pass.** They join the T.25 re-baseline (handoff "After T.28d") that sweeps the entire a/b/c/d rider surface at once.

## 6. Content / roster audit + reconciliation

- **Hexproof drift (B.15, fix here):** `targeting.py` single-target helpers never filtered `StatusGate.UNTARGETABLE` — only `engine.py:99` (autos) did. Git origin: T.28b added the gate + the engine auto filter (`engine.py:99`) but the targeting helpers (T.20) predate it and were never updated, so targeted abilities silently pierced. Caught during T.28d planning. Guarded by §V.40 + regression tests.
- **Stale comments:** `kinships.py:50` ("weather-immune/weather-as-buff = T.28c") and `kinships.py:29` ("potency-cut/pierce/haste = T.28d") — reconcile to reflect what T.28d actually builds. `traits/affinities.py:4-5` docstring ("@10 mono rider … T.28c") → T.28d.
- **Living doc:** `docs/live/content/traits.md` T.28d-pending block (lines 15-19) is now wrong in two ways — (a) Primordial @1/@3 are deferred, (b) hexproof rename. Update on landing (§11). The "deferred flavour … ship stat-only" note (lines 18-19) flips: those three rungs now carry riders.
- **No roster/vocabulary count change** — no trait tags added/removed; `KINSHIP_TAGS`/`CALLING_TAGS`/affinity set untouched. V.22 holds.

## 7. Open questions

**Resolved here (proposals, overridable):**
- Sunlit premium stats on @10 only (not the whole ladder) — keeps it an apex flourish. (§5)
- Affinity @10 stays `PER_TRAIT_PIECE`. (D7)
- `ally_tidal` carried at Tidekin @5/@8 in addition to `tidal_hot` (cumulative ally-reach). (§5)
- Echo `potency=0.6`, Overcast `cap_frac=0.25`, crit_arc `0.5` — all first-pass for T.25.

**Still open / deferred:**
- 6 Primordial @1 signature mechanics — **un-authored**, deferred to T.31 (design them when reachable). (§D.20)
- Primordial @3 tier-up — deferred, needs re-resolve pass. (§D.20)
- Whether hexproof should also block **friendly** single-target (e.g. ally-targeted buffs) — out of scope; current single-target *ally* helper (`lowest_hp_ally`) is unaffected (hexproof is an enemy-evasion tool; no content targets it). Note for T.30 if single-target friendly grows.

## 8. Test plan

- **Hexproof rename:** grep guard — no `"untargetable"` / `UNTARGETABLE` left in `src/` (test or CI assert); existing Stalker @7 / Spirit opener tests pass under the new id.
- **Hexproof semantics (the §V.40 guard), new `tests/game/test_hexproof.py`:**
  1. auto-attack acquisition skips a hexproof enemy (existing behaviour, re-asserted).
  2. each single-target helper (`primary_target`/`lowest_hp_enemy`/`highest_ap_enemy`/`random_enemy`/`furthest_enemy`) returns `None`/skips when the only/closest enemy is hexproof.
  3. an **AoE** path (`enemies_in_radius`, and a cast that iterates `enemies_of`) **still hits** a hexproof enemy.
  4. a `pierces_hexproof` actor's single-target helper **does** pick the hexproof enemy.
- **CC-immunity:** `apply_status(scaled_carrier, "stun"/"root"/"silence"/"disarm"/"frozen"/"fear")` is a no-op; `"slow"`/`"burn"`/`"poison"` still apply.
- **Weather override:** a Scaled-@8 board in an **unfavorable** node weather gets the favorable buff pack (compare a flagged vs unflagged piece's post-loadout stats); `CLEAR` stays identity.
- **Echo potency:** an @8 Spirit echo deals `0.6×` the first cast's damage; @5 echo unchanged (full); `ctx._echo_potency` is `1.0` outside a recast.
- **New builders determinism:** each of `crit_arc`/`chill_attackers`/`burst_reduction`/`kite_reward`/`ally_tidal` — fixed-seed `sim_fight` with `workers=1` is **byte-identical** across two runs (V.2/V.14); none reference `ctx.rng`.
- **Affinity @10:** a 10-mono board lights `@10` and applies the rider (count==10, threshold==10); the rider fires (e.g. Galvanized crit splashes a neighbour).
- **Regression / snapshot:** re-baseline the trait-heavy sim snapshots that change *only* where the @8 echo potency or new riders bite; confirm no unrelated drift. Full `uv run pytest` green (target: prior 768 + new cases).

## 9. Acceptance criteria

1. `untargetable`→`hexproof` rename complete; no old id in `src/`; all prior untargetable tests pass renamed.
2. Single-target abilities **cannot** target a hexproof enemy; AoE **can**; `pierces_hexproof` bypasses — all four cases tested (§8.2).
3. Affinity @10 riders live for Galvanized/Frostbound/Stormfed/Shrouded/Overcast; Sunlit @10 carries the premium-stat extension; all RNG-free.
4. Scaled @5 blocks hard-CC only (slow/DoTs land); Scaled @8 grants the favorable weather pack regardless of affinity and re-includes CC-immunity.
5. Spirit @8 echoes at cadence 3, `0.6×` damage, with `mana_regen` haste and `pierces_hexproof`; Spirit @5 unchanged.
6. Beast @4/@6 strength ramp, Skyborn @3 kite-reward, Tidekin @3 ally-heal all fire.
7. Primordial @1 = stat pack only; **no** signature-mechanic or @3 code lands (deferred §D.20).
8. `uv run pytest` green; fixed-seed sims byte-identical except the intended @8-echo / rider deltas (§V.2/§V.14). §V.40 guard passes.
9. `docs/live/content/traits.md` updated to match (Primordial deferral + hexproof + fold-in rungs no longer "stat-only"); `/check` clean.

## 10. SPEC changes needed (for `/spec`)

**§T row — flip + rewrite §T.28d** (`📋 Plan → ~`, then `✅` on landing):
> `| T.28d | Trait apex riders + hexproof correctness + deferred-flavor fold-ins — **rename `untargetable`→`hexproof`** + **fix** single-target acquisition to honor the gate (AoE still hits; `Piece.pierces_hexproof` bypass for Spirit @8) [B.15]; 5 **affinity @10** riders (Galvanized crit-arc, Frostbound chill-attackers, Stormfed mana-haste, Shrouded longer hexproof-opener, Overcast burst-reduction) + Sunlit premium-stat pack; **Scaled** @5 hard-CC immunity (`cc_immune`) + @8 full favorable weather override (`weather_favored`, pre-weather marker pass); **Spirit @8** reduced-potency echo (`ctx._echo_potency`) + mana-haste + pierce; fold-ins Beast @4/@6 str-ramp, Skyborn @3 kite-reward, Tidekin @3 ally-heal; all RNG-free. **Primordial @1 signatures + @3 deferred to T.31 [D.20].** | `game/status.py`, `game/piece.py`, `game/targeting.py`, `game/combat/context.py`, `game/loadout.py`, `game/weather_effects.py`, `game/traits/`, `docs/design/tasks/t28d_trait_apex_hexproof_plan.md` | T.28c | M | ~ |`
> (Files-cell now points to **this** plan doc, not `t28_trait_effects_plan.md`. Est lowered **M-L → M** — Primordial subsystem removed.)

**New §V.40** (guards the B.15 recurrence):
> `- V.40: **Hexproof targeting.** `StatusGate.HEXPROOF` (status `hexproof`, formerly `untargetable`) excludes a piece from **single-target acquisition** — both the engine auto-attack target scan (`combat/engine.py`) and **every** single-target helper in `targeting.py` (`primary_target`/`lowest_hp_enemy`/`highest_ap_enemy`/`random_enemy`/`furthest_enemy`/`_closest_enemy`) — but **never** from AoE/untargeted effects (`enemies_in_radius`/`line_targets`/`neighbors_of`, or a cast iterating `ctx.enemies_of`). A piece with `Piece.pierces_hexproof` ignores the exclusion (Spirit @8 — the lone bypass). Filtering is a pure predicate (`is_gated(HEXPROOF) and not actor.pierces_hexproof`), RNG-free (V.2/V.14). (T.28d, B.15)`

**New §B.15:**
> `- B.15 [2026-06-08] Hexproof (then `untargetable`) leaked through single-target abilities. **Cause:** T.28b added `StatusGate.UNTARGETABLE` + the engine auto-attack filter (`engine.py:99`) but the `targeting.py` single-target acquisition helpers (T.20, predating the gate) filtered only fog — so *targeted* casts (`primary_target` et al.) still picked untargetable pieces, contradicting the intended "can't be targeted" semantics. **Fix (T.28d):** rename to `hexproof`; add the gate filter to the single-target helpers (AoE/untargeted unaffected — MTG-hexproof model); `pierces_hexproof` bypass. **Guard:** V.40 + `tests/game/test_hexproof.py` (auto / single-target / AoE / pierce cases).`

**§D.20 (new — Primordial deferral):**
> `- D.20 Primordial @1 signature mechanics + @3 tier-up deferred to **T.31**. The 6 Tier-10 legendaries already carry full `.active`+`.passive` kits (T.30); the catalog's "@1 signature mechanic" (trait_catalog.md:176) is un-authored net-new design and **unreachable until T.31's 3 paired unlock augments** exist, so it cannot be tuned in T.28d. @3 ("highest other trait counts one tier higher") additionally needs a trait re-resolve/fixpoint pass and is double-dormant. Primordial @1 ships as its stat pack (`callings.py`); T.31 authors the signatures + @3 alongside the unlock augments. (was T.28d scope; moved per the T.30-kit finding)`

**§T.31 row — append to its goal** (Primordial content lands there):
> add `…; **6 Primordial @1 signature mechanics + @3 aspirational tier-up** (authored here — reachable once the 3 paired unlock augments exist; @3 needs a trait re-resolve pass) …` and add `T.28d` to its depends if not already implied.

**Implementation Order:** unchanged — `… → T.28c → T.28d → T.29a → …`. T.28d no longer gates on anything new.

## 11. LIVING docs to update (on build/landing)

- **`docs/live/content/traits.md`** — (a) flip the T.28d-pending block (lines 15-19): Primordial @1/@3 → "deferred to T.31 (§D.20)"; the three "deferred flavour … stat-only" rungs (Beast @4/@6, Skyborn @3, Tidekin @3) now carry riders; (b) rename every `untargetable`→`hexproof` mention (lines 93,113,129) + document the single-target-vs-AoE rule + `pierces_hexproof`; (c) add the affinity @10 riders + Scaled @5/@8 + Spirit @8 upgrade to the rider sections; (d) reconcile the stale `kinships.py`/`affinities.py` "T.28c" comments referenced there. Bump the "Reconciled" date; the 🔶 PARTIAL banner stays only if Primordial @1/@3 are tracked as the remaining (now T.31) slice — otherwise note T.28 trait *combat surface* is complete pending T.31's Primordial signatures.
- **`ARCHITECTURE.md`** — check the targeting/status lines for hexproof rename drift; reconcile if the auto/AoE distinction is described. (Build-skill ARCHITECTURE drift step.)
- No `docs/design/` (FROZEN) edits.

---

### Next moves (in order)
1. **`/spec`** — apply the §10 deltas (flip+rewrite §T.28d, add §V.40, §B.15, §D.20, amend §T.31).
2. **`/build §T.28d`** — execute this plan.
