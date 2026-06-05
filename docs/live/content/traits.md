# Traits — kinships, callings, breakpoints

> **Status: LIVING** — must match `src/game/traits/` + `content.py` trait vocab.
> Audited by `/check`. **Reconciled:** 2026-06-05 (T.28a).
>
> 🔶 **PARTIAL** — T.28a built the **framework + declarative stat-pack** half;
> **T.28b (done)** added the combat primitives — hook riders **second-wind
> decaying-shield** (Primordial @2), **tidal HoT** (Tidekin @5/@8), **enrage**
> (Beast @8), **time-ramp** (Skirmisher @2), **dodge** (Skirmisher @4),
> **untargetable** opener (Spirit @5) — plus the engine-behaviour arms:
> **kiting** (Skyborn @2 — movement retreat + melee +1 range), **backline
> target-priority** (Stalker @2 — movement + target bias), **taunt** (status
> honored in target/movement; Trickster casts apply it in T.28c), and the one
> true **revive** (Mender @6 — `ctx.revive` death-path reversal). T.28c (pending):
> echo/aura/splash/spawns/empowered-shot/weather-as-buff/apex effects. Design
> (frozen): [`docs/design/content/trait_catalog.md`](../../design/content/trait_catalog.md) v2.1.

## Where it lives
- `game/traits/types.py` — `TraitScope` (`PER_TRAIT_PIECE`/`TEAM_WIDE`),
  `TraitBreakpoint(count, scope, bundle_factory)`, `DynamicThreshold`
  (`callable(team, board_cap) -> int`).
- `game/traits/_packs.py` — `stat_pack_bundle` (mul/add `Modifier`s; an
  `attack_speed` mul rides `milli_AS` for tie-order, V.34) + `define_trait`
  shorthand (registers a trait from `(count, scope, muls, adds)` rungs).
- `game/traits/{affinities,kinships,callings}.py` — the 24 trait factories
  (declarative stat-pack rungs). Imported by `traits/__init__`, which registers
  them into `TRAIT_REGISTRY` as a side effect.
- `game/traits/__init__.py` — `affinity_trait` (affinity → derived tag),
  `_resolve_traits`, `resolve_and_apply_traits`.
- `game/registries.py` — `TRAIT_REGISTRY` + `@register_trait`.
- `content.py` — `KINSHIP_TAGS` (6) / `CALLING_TAGS` (12) / `ALL_TRAIT_TAGS`;
  `Champion.traits`.

## The 24 traits
- **6 Kinships** (`KINSHIP_TAGS`): Beast, Spirit, Skyborn, Scaled, Tidekin, Swarm.
- **6 Affinities** (derived from `affinity`, never stored): Sunlit/Overcast/
  Shrouded/Stormfed/Frostbound/Galvanized = Clear/Cloudy/Mist/Rain/Snow/Thunder.
- **12 Callings** (`CALLING_TAGS`): Hunter, Guardian, Mystic, Warden, Stalker,
  Bruiser, Skirmisher, Channeler, Mender, Trickster, Packmate, Primordial.

## Resolution (in `compile_loadout`, step 3)
1. After weather (step 2), before passives (step 7).
2. `_resolve_traits(team, board_cap)` counts **unique champion ids** per tag
   (V.21), incl. each piece's **derived affinity tag**; finds the highest cleared
   rung (dynamic thresholds resolved against `board_cap == len(team)`).
3. Applies each cleared rung's bundle to its targets (`PER_TRAIT_PIECE` →
   carriers; `TEAM_WIDE` → whole team). **Player team only — enemies never light
   up** (V.22).
4. **HP re-sync:** the engine reads `piece.max_hp`/`hp` as cached fields, so after
   applying `hp`-mul modifiers the function recomputes `max_hp = hp =
   piece.stat("hp")` (pieces start each combat at full HP).
5. Returns `trait_activations: [(trait_id, count, threshold), …]` (sorted),
   surfaced through `compile_loadout`'s 3-tuple return → `BattleResult`.

Pure + RNG-free → replay-stable (V.21). Counting is at loadout; mid-combat
spawns/revives never raise a count.

## Breakpoint shapes (apex = `min(pool, cap)`, V.37)
Ladders are single-step-leaning with `@1` entries on supports/casters/kiters; see
the catalog for per-trait rungs. **T.28a implements the stat-pack portion of every
rung**; mechanic riders layer onto the same trait ids in b/c. Packmate's apex is a
**dynamic `@full-board`** threshold (== fielded board size).

## Combat primitives (T.28b) — `game/traits/mechanics.py` + engine
All deterministic (cadence counters / HP thresholds / geometry, never RNG —
V.2/V.14/V.37). A rung's optional 5th tuple element is a list of builders
`(owner, source_id) -> list[Hook]` appended to its bundle (`_packs.define_trait`).

**Hook riders** (ride the event bus, no engine edits):
- `second_wind` (Primordial @2) — `on_damage_taken`; first drop below 60% HP →
  `grant_barrier(0.4·max_hp, 1200t)` once. Reuses V.28 barriers (decay = expiry).
- `tidal_hot` (Tidekin @5/@8) — `on_tick` cadence `ctx.heal` of the carrier.
- `enrage` (Beast @8) — `on_damage_taken`; one-shot AS+STR burst below 25% HP.
- `time_ramp` (Skirmisher @2) — `on_tick` stacking AS `mul` to a cap.
- `dodge` (Skirmisher @4) — `on_damage_pre` reducing; every Nth basic → 0
  (engine floors final to 1, so a near-total mitigation).
- `untargetable_opener` (Spirit @5) — `on_combat_start` applies `untargetable`.

**Engine-behaviour arms** (set a flag/status the engine reads):
- `kiting` (Skyborn @2) — `on_combat_start` sets `Piece.is_kiter`; melee (base
  range ≤1) also get +1 `attack_range` (no double vs @5's flat +1). Engine
  `_kite_step` (movement): retreat one hex from a **single** adjacent melee
  threat that strictly increases distance while keeping ≥1 enemy attackable;
  plant when swarmed (≥2 melee), cornered, or no target.
- `backline_seeker` (Stalker @2) — sets `Piece.seeks_backline`; engine paths to
  the deepest enemy column (`_backline_subset`) and `_select_target` prefers it.
  No teleport.
- `revive_first_ally` (Mender @6, TEAM_WIDE) — `on_death`; the first ally death
  each combat → `ctx.revive(victim, 0.3)`. Once-per-combat shared across all
  carriers via a flag on `ctx`. The one true revive (V.37); mid-combat revives
  never raise a trait count.
- **taunt** — `StatusGate`-free `taunt` StatusDef; `StatusInstance.source_id` =
  taunter. Engine `_taunt_target` forces the taunter as target (overrides
  current/backline) and as the movement goal. Capability only in T.28b — wired
  to Trickster casts in T.28c.

`StatusGate.UNTARGETABLE` excludes a piece from `_opponents` (target selection);
the piece still acts.

## Roster (post-T.28a rebalance, B.9)
- Kinship pools (sum 60): Beast 14, Spirit 11, Skyborn 9, Scaled 9, Tidekin 9,
  Swarm 8. One **Tier-10 anchor per kinship**: Mournhollow→Beast, Aurion→Spirit,
  Aerion→Skyborn, Umbra→Scaled, Nerei→Tidekin, Borealis→Swarm.
- Calling pools (sum ~87): Guardian 9; Hunter/Mystic/Bruiser/Skirmisher/Packmate
  8; Stalker/Channeler 7; Warden/Trickster/Mender/Primordial 6.
- `CALLING_TAGS` dropped the 4 dead T.5 tags (Bulwark/Drifter/Harbinger/Emissary)
  and added **Packmate** (8 cheap T1–3 secondary carriers). Hunter spread toward
  lower tiers (e.g. Dusk Bat T2). Primordial shop access is augment-gated (T.31);
  trait factories ship ready-but-dormant.

## Invariants
- V.21 (unique-id count, RNG-free, replay-stable), V.22 (every `Champion.traits`
  tag resolves in `TRAIT_REGISTRY`; ≥1 Kinship + ≥1 Calling; Primordial at T10),
  V.37 (apex/dynamic-threshold + primitive determinism). Guarded by
  `tests/game/test_traits.py` + `content.py` self-asserts.
