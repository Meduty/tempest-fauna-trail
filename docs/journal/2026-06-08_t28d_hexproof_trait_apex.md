# 2026-06-08 — T.28d: hexproof correctness + trait apex riders + fold-ins

## What shipped
§T.28d, the last *reachable* slice of the T.28 trait line. Plan:
[`t28d_trait_apex_hexproof_plan.md`](../design/tasks/t28d_trait_apex_hexproof_plan.md).

- **Hexproof rename + bug fix (B.15 / V.40).** Renamed the `untargetable` status →
  `hexproof` (`StatusGate.UNTARGETABLE` → `HEXPROOF`; `untargetable_opener` →
  `hexproof_opener`; `untargetable_after_kill` → `hexproof_after_kill`). Fixed the
  real defect: the single-target acquisition helpers in `targeting.py` only ever
  filtered fog, never the gate — so *targeted* abilities hit untargetable pieces,
  while only the engine auto-attack scan (`_opponents`) honored it. Now both honor
  it; AoE / untargeted effects (which iterate `ctx.enemies_of` directly) still hit
  — MTG-hexproof semantics. `Piece.pierces_hexproof` is the lone bypass (Spirit @8).
- **5 affinity @10 riders + Sunlit premium pack.** Galvanized `crit_arc`, Frostbound
  `chill_attackers`, Overcast `burst_reduction`, Shrouded longer `hexproof_opener`,
  Stormfed mana-haste (stat). Sunlit stays stat-only but its @10 broadens to premium
  stats (`crit_chance`/`penetration_pct` flat adds + `mana_regen` mul), small by design.
- **Scaled** @5 hard-CC immunity (`cc_immune` marker + `apply_status` guard skipping
  any `BLOCKS_*`-gated status; slow/DoTs still land) + @8 full favorable weather
  override (`weather_favored` marker, set by the pre-step-2 `mark_weather_overrides`
  pass; `_apply_weather_to_piece` then uses `WEATHER_BUFF_BASE[weather]`).
- **Spirit @8** reduced-potency echo (`echo_cadence(3, potency=0.6)` via transient
  `ctx._echo_potency` read in `deal_damage`, damage-only) + `pierce_hexproof` + mana-haste.
- **Fold-ins:** Beast @4/@6/@8 strength `time_ramp`, Skyborn @3 `kite_reward`, Tidekin
  @3/@5/@8 `ally_tidal`.

Verify: **869 passed** (was 850; +19 in `test_hexproof.py`), trait sim byte-identical.

## Decisions + why (locked with the user before building)
- **Primordial @1 signatures + @3 deferred to T.31 (D.20).** This was the big one —
  see process notes. The 6 legendaries already carry full T.30 `.active`/`.passive`
  kits, and the "@1 signature mechanic" is un-authored, unreachable, untunable until
  the T.31 unlock augments exist. Building it now would have been speculative,
  unbalanced, dormant code. Primordial @1 ships as its existing stat pack.
- **Hexproof = MTG hexproof, not "can't be touched at all."** User explicitly steered
  this: untargeted/AoE spells hit; single-target spells + autos don't. That matched a
  latent bug (single-target helpers leaked), so the fix and the design intent
  coincided — backprop B.15 + invariant V.40.
- **CC-immunity = hard-CC only** (gate-bearing). Slow (no gate) and DoTs still land —
  keeps counterplay; cleanest as one `apply_status` early-return.
- **Echo potency is damage-only** via a one-line `ctx._echo_potency` multiplier — far
  cheaper than the "new ctx surface" the handoff feared, because `_recast` already
  brackets the recast with a call-stack flag.
- **Weather override sequencing:** a pre-pass marks Scaled @8 carriers *before* weather
  folds into `base_stats` (step 2), because trait bundles apply at step 3. Rejected
  undo-then-reapply (messy) and wholesale step reorder (entangles the HP re-sync).

## Process notes (AI collaboration)

### Conflicts / drift caught
- **SPEC ⟂ code drift, caught mid-plan (the save).** SPEC §T.28d still described
  "6 Primordial @1 signature kits" as buildable content. Verifying against code
  showed the 6 legendaries already had complete kits (T.30) and the signatures were
  never authored anywhere. Surfaced to the user *before* writing the plan; the whole
  Primordial subsystem moved to T.31 (D.20). This halved the task and removed all
  dormant/untunable code. Lesson reinforced: **grep the code before trusting a SPEC
  row's noun** — the row was written before T.30 existed.
- **Handoff overstated the cost of two items.** The T.28d handoff flagged
  reduced-potency echo as needing "a new ctx surface" and pierce-untargetable as
  needing engine work. Reading the code: echo needed *one line* (the `_in_recast`
  bracket already existed), and "pierce" was moot until I found the *actual* bug —
  single-target helpers never filtered the gate at all. The handoff's "VERIFY before
  building" note paid off; I verified and the work reshaped entirely.
- **Pre-existing latent issue noted, NOT fixed (scope discipline).** Skyborn `kiting`
  is armed only at exactly @2 (the @3/@5 PER rungs don't re-include it), so a
  ≥3-Skyborn board arguably loses `is_kiter` under the cumulative-rung rule. This is
  T.28b's, not T.28d's; I added `kite_reward` at @3 per the plan (it stands alone —
  rewards out-ranging, doesn't require `is_kiter`) and left the kiting question for a
  separate backprop. Did not silently "fix" it.

### Agent errors / wrong turns
- Wrote the `kite_reward` test feeding it an `AttackEvent` — which has no `.tag`
  field, so the hook would have `AttributeError`'d, not "guarded out" as my comment
  claimed. Caught by checking `events.py` before running; rewrote to use `DamageEvent`
  with `ITEM_PROC` (proves the no-recursion guard) + `BASIC_ATTACK`.
- First guessed the champion-roster export was `CHAMPIONS`; it's `CHAMPION_ROSTER`
  (a dict). Grepped instead of assuming.
- `Modifier`'s field is `stat` (not `stat_name`) — verified before the structural
  affinity-@10 test relied on `mod.stat`.

### Guardrails added
- **V.40** makes the hexproof single-target-vs-AoE split a checked invariant, with
  `test_hexproof.py` exercising all four cases (auto / single-target / AoE / pierce).
  The next agent can't silently regress the helpers back to fog-only filtering.

### Prompting-strategy reflection
The decision-by-decision `AskUserQuestion` walk (7 forks, one at a time, each grounded
in a fresh code read) was the high-leverage move. Two of the user's answers *changed
because I fed them a code fact mid-walk* — the hexproof "it already works?" turned into
a real bug fix once I showed the helpers don't filter the gate, and "build Primordial
kits now" reversed to "defer" once I showed the legendaries already had kits. Neither
would have surfaced from a plan-then-confirm flow; they came from interleaving
verification with the questions. The pattern that worked: **verify → state the fact →
re-pose the fork**, rather than asking abstractly. The cost is more turns up front, but
it prevented building a dormant subsystem nobody could tune. Keeping the plan doc as the
single artifact (with §10 = exact `/spec` deltas) again made the `/spec` and `/build`
steps mechanical — no re-litigation.

## Follow-ups
- **T.25 re-baseline** — every T.28d magnitude is first-pass (echo 0.6, burst cap 0.25,
  crit-arc 0.5, Sunlit premiums, ramp rates). Sweep the whole a/b/c/d rider surface at
  once now that the reachable trait combat is complete.
- **Skyborn kiting@2-only** — investigate whether `kiting` should re-include at @3/@5
  per the cumulative rule (potential backprop, pre-dates T.28d).
- **T.31** owns the 6 Primordial @1 signatures + @3 tier-up (D.20).
