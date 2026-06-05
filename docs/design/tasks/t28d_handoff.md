# T.28d — handoff note (next session)

> Working note, not the frozen plan. Written 2026-06-06 after T.28a/b/c shipped.
> Start with the **Required reading** in CLAUDE.md, then this. SPEC row T.28d +
> `docs/live/content/traits.md` are the live contract; trust them over this note
> if they ever diverge.

## State at handoff
- **T.28a/b/c = ✅ Done.** Framework + stat packs + (almost all) mechanic riders.
- Suite: **749 passed / 101 skipped**. Trait-heavy sim byte-identical.
- Commits: `5a33157` (a) · `67e1087`+`b738b4b` (b) · `6a16053` (c).
- Working tree clean.

## T.28d scope (the remaining slice)
Subsystem-heavy + currently-**dormant** trait effects — the ones that need new
engine/ctx capability or are bespoke-per-legendary. Per SPEC row T.28d:

1. **6 Primordial @1 signature kits.** One bespoke effect per Tier-10 legendary
   (aurion/nerei/borealis/umbra/mournhollow/aerion). **DORMANT**: Primordials are
   augment-gated (T.31, the 3 paired unlock augments) and have **no acquisition
   path** in play yet — so these are unreachable until T.31. Low urgency; consider
   doing T.31 first, or build the kits behind tests only.
2. **6 affinity @10 apex riders** (`game/traits/affinities.py`, currently stat-only
   at @10): Galvanized crit-arc-to-neighbour, Frostbound slow-attackers-of-team,
   Stormfed team ability-haste, Shrouded longer team untargetable opener, Overcast
   team burst-damage reduction, Sunlit (pick one — all-rounder). @10 needs 10
   same-affinity uniques (all-in Amber board) — rare but reachable.
3. **Scaled** @5 CC-immunity + @8 weather-as-buff override
   (`game/weather_effects.py`). CC-immunity = a guard so `ctx.apply_status` skips
   gate-bearing statuses for Scaled carriers (needs a clean hook point — see Risks).
   Weather-as-buff = treat node weather as the favorable pack regardless of the
   piece's `affinity` (interacts with weather already folded into `base_stats`).
4. **Spirit @8** echo-potency-reduction + pierce-untargetable-gate + ability-haste
   pool. Today Spirit @8 just re-uses `echo_cadence(3)` (full potency). T.28d:
   reduced-potency echo (needs a damage-mult context the pipeline doesn't have),
   let Spirit casts target `UNTARGETABLE` pieces (a per-cast targeting bypass),
   and a team ability-haste pool.
5. **Primordial @3** aspirational "team's highest *other* trait counts one tier
   higher" — re-resolve interaction; aspirational, can defer again.

### Also fold in if cheap (deferred *flavor*, currently stat-only)
Not in any task row, documented in `traits.md` as deferred:
- Beast @4/@6 strength ramp (use existing `m.time_ramp(stat="strength")`).
- Skyborn @3 kite-reward (bonus dmg to enemies that can't reach the carrier —
  `on_damage_dealt`, target.attack_range < distance).
- Tidekin @3 heal also reaches lowest-HP ally.
These are pure hook idioms (cheap); good warm-up before the subsystem work.

## Load-bearing gotchas (learned in a/b/c — DO NOT relearn the hard way)
- **Cumulative rungs.** Resolution applies **only the highest cleared rung's**
  bundle (`traits/__init__._resolve_traits`). Every rung must re-include the
  mechanics it should still grant. When you touch affinity @10 / Scaled @8 / Spirit
  @8, re-include the lower riders. (This is how the latent Skirmisher ramp-drop
  got fixed in c.)
- **Apex TEAM scope.** A TEAM_WIDE rung applies its bundle to every ally. Safe for
  caster/role-gated riders (no-op for wrong role); UNSAFE for carrier-movement
  (kiting/backline) and for anything that shouldn't hit non-carriers — guard with
  `if "<Trait>" not in owner.traits: return` (see `on_death_spawn`).
- **`SourceTag.ITEM_PROC`** for secondary/proc damage — it does NOT re-fire
  `on_attack_landed`/`on_ability_damage`, so no recursion. Don't add a new tag.
- **Re-entry guards on ctx** (`_in_recast`, `_in_heal_splash`) for any hook that
  triggers the same event it listens to. Echo proven bounded to exactly +1.
- **Cast riders only fire for REGISTERED abilities** (the unregistered fast-path
  in `_resolve_action` skips `on_cast`). Fine post-T.30.
- **Mid-iteration spawn is safe** (append to `pieces`, same as shadow clones), but
  fires `on_spawn` — mind any future `on_spawn` listeners.
- **Stats read via `piece.stat()` EXCEPT `max_hp`/`hp`** (cached). An `hp`-mul
  needs the HP re-sync (already done in `resolve_and_apply_traits`).

## New capability T.28d likely needs (none exist yet)
- **Reduced-potency cast** — a damage multiplier the recast can pass through.
  `ctx.cast_ability` has no potency arg; abilities compute their own damage. Either
  add an optional `potency`/`damage_mult` carried on ctx during a recast, or accept
  full-potency echo and cut scope. Discuss before building (new ctx surface).
- **Pierce-untargetable** — Spirit casts ignoring `StatusGate.UNTARGETABLE`. Today
  `ctx.enemies_of` (used by `cast_ability` target resolution) does NOT filter
  untargetable (only the engine's `_opponents` does), so casts may *already* hit
  untargetable. VERIFY before building — the gate may only need engine-side, not
  cast-side, work.
- **CC-immunity** — cleanest as a guard inside `ctx.apply_status` (skip if target
  has a Scaled-immunity marker for gate-bearing statuses). New marker flag on Piece
  like `is_kiter`/`seeks_backline`.
- **Ability-haste pool / weather-as-buff** — touch `weather_effects.py` / stat
  application; design first.

## Open decisions to raise with user before building T.28d
- Do Primordial kits NOW (dormant, test-only) or after T.31 unlock? (Recommend
  after T.31, or stub + test.)
- Reduced-potency echo: add ctx potency surface, or keep full-potency and drop that
  bullet? (Affects whether T.28d needs a new ctx arg.)
- Affinity @10 riders: build all 6 or just the reachable/impactful ones?

## After T.28d
- **T.25 sim re-baseline** — ALL rider magnitudes (a/b/c) are first-pass
  (lifesteal 0.12, splash 0.4, second-wind 0.4/1200t, revive 0.3, shields,
  empowered mults, echo cadence, chitin stat-frac). Sweep once T.28d lands so the
  whole trait surface is tuned together, not piecemeal.
