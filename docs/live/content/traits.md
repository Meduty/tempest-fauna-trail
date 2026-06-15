# Traits — kinships, callings, breakpoints

> **Status: LIVING** — must match `src/game/traits/` + `content.py` trait vocab.
> Audited by `/check`. **Reconciled:** 2026-06-06 (T.28c).
>
> 🔶 **PARTIAL** — T.28a/b/c/d built the framework + stat packs + the full
> reachable combat surface. T.28b combat primitives (second-wind, tidal HoT,
> enrage, time-ramp, dodge, hexproof opener; kiting, backline, taunt, revive).
> **T.28c (done)** added the rider batch over existing `ctx`: Hunter
> bonus-auto/empowered/cleave/team-aura, Mystic `ability_can_crit`+splash, Guardian
> start+periodic shields, Bruiser lifesteal, Skirmisher @8 team ramp, Stalker
> hi-HP-bonus/mana-on-kill/hexproof-after-kill, Channeler free-cast/first-cast-twice,
> Warden cast-shield+team-opener, Trickster slow+taunt-on-cast+mana-aura, Mender
> heal-splash/overheal-shield, Spirit echo, Swarm on-death chitin spawn. **T.28d
> (done):** renamed `untargetable`→`hexproof` + fixed single-target acquisition to
> honor the gate (AoE still hits; `pierces_hexproof` bypass — V.40, B.15); 5
> affinity @10 riders (Galvanized crit-arc, Frostbound chill-attackers, Stormfed
> mana-haste [stat], Shrouded longer hexproof-opener, Overcast burst-reduction) +
> Sunlit premium-stat @10 pack; Scaled @5 hard-CC immunity + @8 favorable weather
> override; Spirit @8 reduced-potency echo (0.6×) + mana-haste + hexproof pierce;
> fold-ins Beast @4/@6 strength-ramp, Skyborn @3 kite-reward, Tidekin @3 ally-heal.
> **Deferred to T.31 (D.20):** 6 Primordial @1 signature mechanics (legendaries
> already carry full T.30 kits; signatures unreachable until the unlock augments)
> + Primordial @3 tier-up. Primordial @1 ships as its stat pack only. Design
> (frozen): [`docs/design/content/trait_catalog.md`](../../design/content/trait_catalog.md) v2.1.

## Where it lives
- `game/traits/types.py` — `TraitScope` (`PER_TRAIT_PIECE`/`TEAM_WIDE`),
  `TraitBreakpoint(count, scope, bundle_factory)`, `DynamicThreshold`
  (`callable(team, board_cap) -> int`).
- `game/traits/_packs.py` — `stat_pack_bundle` (mul/add `Modifier`s; an
  `attack_speed` mul moves tie-order on its own now that AS is a float, V.34 /
  T.29-pre — no `milli_AS` rider) + `define_trait` shorthand (registers a trait
  from `(count, scope, muls, adds)` rungs).
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
- **13 Callings** (`CALLING_TAGS`): Hunter, Guardian, Mystic, Warden, Stalker,
  Bruiser, Skirmisher, Channeler, Mender, Trickster, Packmate, Primordial,
  **Multicaster** (T.29d — quick-caster on multi-slot champs; @2/3/4 per-trait,
  `cast_momentum` stacks `attack_speed`+`mana_regen` per cast; ~6-carrier pool).

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

### Cumulative rungs (load-bearing) — V.41
Resolution applies **only the highest cleared rung's bundle** (one
`TraitBreakpoint`, not a union). Stat magnitudes are authored as the **total at
that rung** (they replace, not stack); mechanic riders persist **only if each
higher rung re-lists them**. **V.41** guards this: `test_trait_rungs_are_cumulative_for_mechanics`
asserts every mechanic fingerprint at rung N reappears at rungs > N — sole
exception, carrier-movement (kiting/backline) at a `TEAM_WIDE` apex. So each rung
**re-includes every mechanic it should still grant** — e.g. Skirmisher carries `time_ramp` on @2/@3/@4/@5/@8 and
`dodge` on @4/@5/@8. Forgetting to re-include silently drops a lower mechanic at
the higher count. **Apex exception:** carrier-*movement* mechanics (kiting,
backline) are NOT re-applied at a TEAM apex — applying them team-wide would make
every ally kite/seek; apex trades the few-carrier identity for a team buff.
Caster/role-gated riders (echo, splash, lifesteal, shields, on-death spawn) ARE
team-safe (no-op for the wrong role) and stay; the Swarm on-death spawn is
explicitly `trait="Swarm"`-guarded so a TEAM apply only spawns for Swarm pieces.

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
- `hexproof_opener` (Spirit @5, Shrouded @10) — `on_combat_start` applies `hexproof`.

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

`StatusGate.HEXPROOF` (status `hexproof`, renamed from `untargetable` in T.28d)
excludes a piece from **single-target acquisition** — the engine `_opponents`
auto-attack scan **and** every single-target helper in `targeting.py`
(`primary_target`/`lowest_hp_enemy`/`highest_ap_enemy`/`random_enemy`/
`furthest_enemy`/`_closest_enemy`). AoE/untargeted effects (`enemies_in_radius`,
`line_targets`, a cast iterating `ctx.enemies_of`) **still hit** — MTG-hexproof.
A piece with `Piece.pierces_hexproof` (Spirit @8) ignores the exclusion. The piece
still acts. (V.40, B.15)

## Mechanic + apex riders (T.28c) — `game/traits/mechanics.py`
All hook idioms over the existing `ctx` mutators (no new engine subsystems).
Secondary/proc damage uses `SourceTag.ITEM_PROC` — the existing "follow-up hit"
tag that does NOT re-fire `on_attack_landed`/`on_ability_damage`, so no recursion.
Recast/heal-splash guard re-entry with `ctx._in_recast` / `ctx._in_heal_splash`.
- Hunter: `bonus_auto_damage` + `empowered_shot` (cadence) + `cleave`
  (`on_attack_landed`); @8 TEAM aura.
- Mystic: `ability_crit` (flips `Piece.ability_can_crit`) + `ability_splash`
  (`on_ability_damage` → adjacent enemies).
- Guardian/Warden: `start_shield` (`on_combat_start`), `periodic_shield`
  (`on_tick` self + adjacent allies), `cast_shield_lowest` (`on_cast`).
- Bruiser/Beast: `attack_lifesteal` (`on_damage_dealt`, basic only).
- Stalker: `high_hp_bonus` (`on_damage_dealt` vs >60%-HP target), `mana_on_kill` +
  `hexproof_after_kill` (`on_kill`).
- Channeler/Spirit: `free_cast` (refund every Nth), `recast_first`, `echo_cadence`
  (re-run via `ctx.cast_ability`, `_in_recast`-guarded).
- Trickster: `slow_on_cast`, `taunt_on_cast` (reuses the T.28b taunt status),
  `mana_denial_aura` (`on_tick` drains adjacent enemy slot mana).
- Mender: `heal_splash` (`on_heal` → lowest-HP other ally), `overheal_shield`
  (heal to a near-full ally banked as a barrier).
- Swarm: `on_death_spawn` — a dying Swarm leaves a stat-fraction chitin via the
  existing summon pattern (`Piece`+summon flags+`ctx.spawn`); `trait`-guarded.
- Packmate `@full-board`: the flat stat pack IS the apex payoff (no rider).
- Multicaster (T.29d): `cast_momentum` (`on_cast_complete` → each cast stacks
  `+per` `attack_speed` mul + `+mr_per` `mana_regen` mul, capped) — the
  quick-caster snowball for multi-slot champs.

Cast-triggered riders only fire for **registered** abilities (the unregistered
fast-path in `_resolve_action` deals damage without firing `on_cast`).

## Apex riders + arms (T.28d) — `game/traits/mechanics.py`
All RNG-free. Affinity `@10` rungs (PER scope — at @10 the board is mono-affinity):
- Galvanized: `crit_arc` (`on_damage_dealt` + `is_crit` → arc to a neighbour, ITEM_PROC).
- Frostbound: `chill_attackers` (`on_damage_taken` → slow the attacker).
- Overcast: `burst_reduction` (reducing `on_damage_pre`, cap a hit at 25% max-HP).
- Shrouded: `hexproof_opener(300)` (longer team opener).
- Stormfed: mana-haste = a fatter `mana_regen` stat in the @10 pack (no hook).
- Sunlit: **stat-only** @10 — broadened to premium stats (`crit_chance`/`penetration_pct`
  flat adds + `mana_regen` mul), deliberately small.

Kinship arms + fold-ins:
- Scaled: `cc_immunity` (@5/@8 — sets `Piece.cc_immune`; `ctx.apply_status` skips
  hard-CC, i.e. any `BLOCKS_*`-gated status; slow/DoTs still land). **Signature →
  carrier-guarded at the @8 TEAM rung** (`cc_immunity(trait="Scaled")`) so the
  team-wide armor/res pack still blankets the squad but CC-immunity stays a Scaled
  perk. @8 also marks `Piece.weather_favored` via the **pre-weather pass**
  `mark_weather_overrides` (loadout step 2-pre, carrier-guarded) →
  `_apply_weather_to_piece` uses `WEATHER_BUFF_BASE[weather]` regardless of affinity.
- Spirit @8 (TEAM): `echo_cadence(3, potency=0.6)` goes team-wide (caster-gated, the
  apex buff) — reduced-potency echo via transient `ctx._echo_potency`, read in
  `deal_damage` (damage-only). The `hexproof_opener` (re-included, cumulative) +
  `pierce_hexproof` are **Spirit signatures → carrier-guarded** (`trait="Spirit"`).
  `mana_regen` haste (stat) is team-wide.
- Beast @4/@6/@8: `time_ramp(stat="strength")` (re-included up the ladder with enrage @8).
- Skyborn: `kiting` re-included on the @3/@5 PER rungs (cumulative — was dropped past
  @2, **B.16**); **not** re-applied at the @8 TEAM apex (movement exception). `kite_reward`
  (`on_damage_dealt`, bonus vs a target whose `attack_range` < gap) on @3/@5/@8 (team-wide
  damage buff at the apex).
- Tidekin @3/@5/@8: `ally_tidal` (cadence-heal the lowest-HP ally; distinct from the
  carrier `tidal_hot` at @5/@8).

**Carrier-scope principle (T.28d):** at a `TEAM_WIDE` apex, stat packs + event/role-gated
riders (echo, lifesteal, shields, ramp, splash, sustain) apply team-wide — that IS the
apex trade. **Signature/identity effects** (CC-immunity, hexproof opener/pierce) and
**carrier-movement** (kiting/backline) stay carrier-only — trait-guarded
(`cc_immunity(trait=…)`, `pierce_hexproof(trait=…)`, `hexproof_opener(trait=…)`) or
omitted from the apex, mirroring the `on_death_spawn` `trait`-guard.

**Deferred to T.31 (D.20):** Primordial @1 signature mechanics + @3 tier-up.

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
  V.37 (apex/dynamic-threshold + primitive determinism), **V.40 (hexproof targeting
  — single-target acquisition excludes `HEXPROOF`; AoE still hits; `pierces_hexproof`
  bypass; B.15)**, **V.41 (cumulative rungs — a higher rung re-includes every lower
  rung's mechanic; sole exception carrier-movement at a TEAM apex; B.16)**. Guarded
  by `tests/game/test_traits.py` + `tests/game/test_hexproof.py` + `content.py` self-asserts.
