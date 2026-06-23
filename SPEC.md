# Tempest Fauna Trail — Implementation Spec

## G. Goal

Roguelike auto-chess strategy game inspired by TFT, under an animal-spirits-and-weather theme.
Players start with **1 chosen champion** and **10 Amber** (starting budget), then progress
through a fixed 50-node route of real-world cities across 6 continent stages. Live
OpenWeather data at each city shapes combat modifiers. Battles are tick-based and
auto-resolved — the player's decisions happen *between* fights.

**Core game loop (per node):**
1. **Trail** — view route progress, preview next node weather & enemies.
2. **Prep** — reposition pieces on the hex board, swap bench ↔ field, use items,
   browse the **champion shop** (buy / sell / reroll), spend Amber to level team-size.
3. **Combat** — auto-resolved; outcome grants Amber, items, and/or Tempest XP.

**Core player decisions:** team composition & synergy traits, item optimization,
weather-aware roster swaps, and board positioning.

**Run-start conditions:**
- Team-size cap: **3** at rank 1 (field 1 champion, bench holds 2 spares); grows with Tempest rank up to **10** at max rank (see D.14).
- Starting champion: player picks 1 from a seed-random offer of 3 (Tier 1–2).
- Starting shop: 5 Tier-1 champions (auto-populated; first reroll per node is free).
- Starting Amber: **10** (enough to buy 2 Tier-1 champions or 1 Tier-2 + save).

Built with Flet (Python). FH Technikum Wien project — 2 students, 8 weeks.

**Grading weight**: UI 4pt | Data Loading 2pt | Visualization 4pt | Structure 6pt | Documentation 4pt

## C. Context

| Constraint | Detail |
|---|---|
| Framework | Flet (Python), desktop app |
| API | OpenWeather free tier — 60 calls/min, current weather by city |
| Visualizations | Min 2 required: route map (Canvas) + run summary (BarChart) |
| Code structure | Modules: `api/`, `game/`, `ui/`, `viz/`. Classes + functions, no monolith |
| Documentation | README with setup, prompting strategy, flow chart |
| Deliverables | Proposal PDF, source ZIP, documentation PDF |

## I. Interfaces

### OpenWeather API
- `GET /data/2.5/weather?q={city}&appid={key}&units=metric`
- Response: `weather[0].id` → `WeatherState` via `WeatherState.from_openweather_id`
- Mapping (one `WeatherState` per OpenWeather main group):
  - `200-232` Thunderstorm → `THUNDER`
  - `300-321` Drizzle + `500-531` Rain → `RAIN`
  - `600-622` Snow → `SNOW`
  - `701-781` Atmosphere (mist/fog/haze/dust/smoke) → `MIST`
  - `800` Clear → `CLEAR`
  - `801-804` Clouds → `CLOUDY`
- Icon URL: `https://openweathermap.org/img/wn/{icon}@2x.png`

### Internal Data Flow
```
OpenWeather API → WeatherClient → cache.json
                                ↓
Route (staged nodes) → Node[weather] → Combat(team, enemies, weather) → BattleResult
                                                                    ↓
                                                              Run.battle_log → viz
```

### Flet Routes
| Route | View | Purpose |
|---|---|---|
| `/` | Main Menu | New game, continue, quit |
| `/trail` | Trail Map | Route progression, node preview, weather overlays |
| `/prep` | Prep Phase | Board placement, bench/field swap, shop, items |
| `/combat` | Battle | Auto-resolved combat with animated log |
| `/summary` | Run Summary | BarChart of damage per battle, win/loss |

## V. Invariants

- V.1: `game/` has zero Flet imports — pure logic, no UI coupling
- V.2: Combat is pure function — `resolve_combat(team, enemies, weather) -> BattleResult`. Single public entry point; the new ability/passive/status framework is invoked through it, never alongside it. `resolve_combat` internally delegates to `compile_loadout → CombatContext → combat/engine.run → BattleResultRecorder.build_result`. Boss fights use the same delegation chain but attach `map_effect_id` via `attach_map_effect` before running the loop (T.26). `resolve_combat`/`resolve_boss_combat` also accept an optional `run_mods: RunModifiers` (active augment ids + a mutable `augment_state` for quest trackers); it stays pure and deterministic, and the `None` default leaves all non-augment callers — including every balance sim — byte-for-byte unchanged (T.31).
- V.3: API failure never crashes app — failed fetch leaves node `unknown` (never-succeeded) or `substitute` (holds `CITIES[city_id].default_weather`); refresher streams keep retrying, never escalate
- V.4: All HTTP calls run on `threading.Thread`, never main thread
- V.5: Weather state enum: exactly 6 values (Clear, Cloudy, Mist, Rain, Snow, Thunder), mapped 1:1 to OpenWeather id main groups
- V.6: Each piece (Champion, Enemy, runtime `Piece`) carries exactly one `affinity: WeatherState` field; it drives both weather systems (node-weather buff/debuff and the affinity damage triangle) — there is no separate weakness field
- V.8: `Champion.traits: list[str]` holds auto-chess synergy tags (Hunter, Mammal, Reptile, etc.). Distinct from `affinity`. Synergy tags are open-ended strings owned by content (T.5); engine treats them as opaque labels for grouping.
- V.7: Route is a staged path with multiple stages (one per continent, up to 6), with one or more nodes per stage and a final boss fight node in a famous city.
- V.9: Cache always populated post-init — every node ∈ {`unknown`, `live`, `substitute`}; engine never reads `None`
- V.10: Cache + refresher stateless re: game — refresher reads `Run.current_node` only for B-stream window, never writes game state
- V.11: Refresher tick = 1/min, fires 3 streams (A: full RR 50; B: RR window `[current+1 .. current+6]` count-clamped at trail end; C: uniform random 50), deduped per tick → ≤3 API calls/min; A alone bounds staleness ≤ 50 min
- V.12: Locked node weather = frozen snapshot in `Run`; cache may refresh same city, engine ignores cache for that node and reads `Run`
- V.13: Advance to `unknown` triggers one synchronous fetch + lock; on fetch fail, lock `substitute` with `CITIES[city_id].default_weather`
- V.14: `tools/simulation/` imports only from `src/game/` — no `ui/`, no `api/`. Matches the V.1 isolation rule extended to the sim layer; keeps `resolve_combat` as the only engine entry. (T.25)
- V.15: Every `ability_id` and `passive_id` referenced by `ChampionDef`, `EnemyDef`, or `BossDef` in content/roster data **must** resolve in `ABILITY_REGISTRY` or `PASSIVE_REGISTRY` respectively — enforced by CI guard test (`test_ability_catalog.py::test_all_*_resolve` and `test_all_boss_abilities_resolve`). BossDef coverage includes `phase1_active`, `phase1_passive`, `phase1_phase_hook`, `phase2_active`, `phase2_passive`, and `on_death_hook`. (T.30)
- V.16: Sim weather-affinity metrics (`own_weather_wr`, `counter_weather_wr`, `weather_sensitivity` on `PieceStats`) are **cross-weather** — derived only via `ratings.weather_metrics()` over per-piece win-rates pooled across **all** weathers, never from a single-weather `aggregate_stats` pass. A single weather yields `weather_sensitivity ≡ 0` by construction; `mega`/`runner` must pool weathers then inject before writing per-weather ratings CSVs. (T.25)
- V.17: Every id in `Run.active_augments` (and every quest-tracker id it implies) **must** resolve in `AUGMENT_REGISTRY` / `QUEST_TRACKER_REGISTRY` — enforced by CI guard test, mirroring V.15. (T.31)
- V.18: Augments are **run-long**: `TEAM`/`PIECE` augment effects are rebuilt fresh in `compile_loadout` each combat from `Run.active_augments`, never persisted as combat state; `RUN`-scope augments mutate `Run` exactly once at pick time. (T.31)
- V.19: Economy / shop / offer rolls are **seed-deterministic** — shop offers from `(run_seed, visit_index, reroll_count)` via `CH_SHOP`, SUPPLY from `(run_seed, node_index)` via `CH_SUPPLY`, Amber win-bonus from `(run_seed, node_index)` via `CH_ECONOMY`; same seed → same draws, mirroring the T.19 encounter contract (extends V.14-style determinism to the economy layer). (T.22)
- V.20: `Tempest` rank is **monotonic non-decreasing** — starts at 1, capped at 10, `rank == deployable board cap`. `Run.tempest` accumulates (+2/fight, +challenge bonus, or Amber rush) and cascades into rank-ups consuming the per-rank thresholds; overflow Tempest carries to the next rank, never decrements rank. (T.22)
- V.21: Trait breakpoints count **unique champion ids** (duplicate copies count once); trait effects enter combat **only** via `compile_loadout` (never alongside `resolve_combat`); `_resolve_traits` is a pure, RNG-free function of the team — replay-stable. (T.28)
- V.22: Every tag in `Champion.traits` **must** resolve in `TRAIT_REGISTRY`, and every champion carries ≥1 Kinship + ≥1 Calling (+ `Primordial` at T10) — CI-guarded, mirroring V.15. Enemies carry trait tags as opaque labels only and never light up breakpoints. (T.28)
- V.23: Items apply **only** via `compile_loadout` (combat-facing `EffectBundle` factories in `ITEM_REGISTRY`) or `RUN_ACTION_REGISTRY` (run-facing); ≤3 equipped items per piece; item procs are deterministic (cadence counters / one-shot flags, never RNG). (T.29)
- V.24: Special items (`RUN_ACTION_REGISTRY`) operate on `Run` state only and are **never** referenced from `game/combat/` — combat sees only their result (`effect_systems_design.md` §8.4). (T.29)
- V.25: Damage-over-time fires on a **per-status cadence**, not per engine tick — `StatusDef.dot_interval_ticks` (`100` ticks = 1s for **all** DOTs incl. `sudden_death`). [Was `sudden_death = 1` (per engine tick); changed to `100` in T.12a — per-tick sudden death killed faster than the ~600-tick action cadence, so a stalled fight got zero actions in the sudden-death window. At `100` it still escalates (+3 stacks/engine-tick from the loop, dmg `0.5×stacks`) but lands once/sec, leaving room for a few last actions before HARD_CAP (14000) forces resolution.] DOT damage **and** stack decay (`decay_stacks_per_dot`, renamed from `decay_stacks_per_tick`) apply only when the per-instance clock `StatusInstance.ticks_to_next_dot` reaches 0. That clock **free-runs**: re-applying a status refreshes duration/stacks but never resets the next-DOT timer (so poison-on-every-auto can't starve or delay ticks). A DOT pays its final tick on the same engine tick it expires (DOT runs **before** the expiry check); expiry itself stays tick-precise (`remaining_ticks` decremented every tick). Rationale: 1 action ≈ 600 ticks, so the old per-tick DOT was ~100× mis-scaled and spammed `on_damage_*` hooks. `dot_per_tick` magnitudes are now per-DOT-tick (≈ per-second): burn `40.0`, poison `18.0`/stack, sudden_death `0.5` (provisional, pending sim sweep). **Stack decay is percentage, not flat**: per DOT tick a decaying status sheds `max(1, trunc(stacks · StatusDef.decay_fraction))` when `decay_fraction > 0` (poison `0.2`), else the legacy flat `1`. Why: combat is a continuous tick auto-battler (V.29), so continuous auto-application + flat-1 decrement = **linear runaway** with no natural plateau. Percentage decay gives an **investment-scaling equilibrium** `stacks_eq ≈ apply_rate / decay_fraction` — a soft plateau that rises with AS / level / INT / poison sources but **never runs away and has NO hard cap** (hard stack caps deliberately rejected: they wall off the build instead of letting it come online; matches PoE/StS DOT philosophy over TFT's anti-stack refresh). (T.20, T.30)
- V.26: A status has **one** `StatusInstance` per `status_id` per piece — identity is `status_id` only, non-stacking across sources (Option 1 / TFT-style). Re-application merges into that single instance; `ctx.apply_status(..., potency=)` lets a caster override per-DOT-tick damage (`StatusInstance.potency`, `0` → fall back to `StatusDef.dot_per_tick`), and on merge the **strongest potency wins** and takes damage credit (`source_id`). Intensity that should *accumulate* across applications uses `StackBehaviour.STACK` (poison), never separate instances. (T.20, T.30)
- V.27: The combat `Piece` carries `level` (in-tier 1–3), copied from `Champion.level`/`Enemy.level` in `loadout.piece_from_*`, so level-scaling passives can read `owner.level`. The marker status `focus_fire` (no gates, no DOT) backs the `enemy_company_captain` **Focus Fire** passive: a captain hit marks the struck enemy **and raises its `threat`** (targeting priority — a TIMED modifier expiring with the mark) so the captain's allies focus it; an ally *other than* the captain hitting a marked target triggers bonus INT magic damage from the captain. Both the bonus and the threat bump scale with captain `level` — guarded against re-triggering on its own bonus hit. (T.30)
- V.28: **Barrier ≠ shield.** A *barrier* is a temporary damage-absorb pool (`Piece.barriers: list[BarrierSegment]`), consumed **before** HP inside `deal_damage` (`absorb_with_barrier` soaks `final` post-mitigation; remainder hits HP) and **never** counted toward `hp`/`max_hp`. Multi-segment, consumed **FIFO**; each segment has optional tick expiry (`expires_at_tick=None` → until consumed) pruned in `expire_modifiers` alongside TIMED modifiers. Granted only via `ctx.grant_barrier(target, amount, duration_ticks)` (`duration_ticks<=0` → no expiry; `amount<=0` or dead target → no-op). `on_damage_*` events still fire the **full** pre-barrier amount (DPS accounting unchanged). The word *"shield"* in content/ids (e.g. `enemy_hierarch.shield`) means an armor/resistance **buff**, a distinct mechanic — do not conflate. (barrier system)
- V.29: **Single combat tick engine.** `src/game/combat/engine.py` is the sole tick loop; `combat/loop.py` (pre-T.26 partial loop) was **deleted** after the T.26 unification (it was dead production code kept alive only by one test import). No parallel/duplicate engine may be reintroduced — a per-tick mechanic (e.g. barrier prune) must live in exactly one place. Tests import loop internals from `combat.engine`. (T.26, barrier system)
- V.30: **Sim weather metrics treat an absent weather as missing (NaN), never 0.** `weather_metrics` returns `NaN` for `own_weather_wr`/`counter_weather_wr` when the piece played **no games** in that weather — a genuine 0% (played, lost all) stays `0.0`; `clear` affinity has no counter weather (NEUTRAL ring), so its counter is always `NaN`. `report.py` writes an **empty CSV cell** for `NaN`; every cross-weather aggregate **must skip NA** (`mean(..., na.rm=TRUE)` / nm-weighted raw recompute), never average missing-as-0. Averaging missing-as-0 fabricated the mega7 `+0.18` own-vs-counter swing (true ≈ `+0.01`). Extends V.16. (T.25, B.12)
- V.31: Every `ChampionDef`/`EnemyDef`/`BossDef` carries a valid `intent ∈ {damage, hybrid, utility}` — the 6th archetype axis (alongside `stat`, `reach`, `durability`, `playstyle`, `speed`). CI-guarded, mirroring V.22/V.15. (T.32)
- V.32: `role` (coarse human title — exactly one of `tank`/`bruiser`/`support`/`mage`/`marksman`/`assassin`/`swashbuckler`/`spellblade`/`spellslinger`) and `role_code` (fine descriptor — the 6 axis tokens in fixed order `stat-reach-durability-playstyle-speed-intent`, with every `hybrid` token omitted, joined by `-`) are **pure deterministic functions of the 6 axes** — no RNG, no traits, no kit. **`spellslinger`** = `reach=="ranged" AND playstyle=="hybrid" AND intent=="damage"` (a ranged dealer that casts *and* autos — the ranged, playstyle-keyed analog of `spellblade`'s stat-keyed catch; branch evaluated before the final `mage`/`marksman` line, which only sees `playstyle=="ability"` as caster). (T.36b) `role_code` is a non-positional **tag-set** (consumed by membership/substring, never positional indexing — its length is dynamic); any programmatic consumer reads the first-class `role`/`intent` fields, never parses `role_code`. Omitting `hybrid` is lossless (an absent axis = `hybrid` by position), so `role_code` is injective over the **1512** axis combinations (T.33b widened the speed axis 3→7: `leaden`/`heavy`/`steady`/`hybrid`/`brisk`/`speedy`/`blinding`) and maps to exactly one `role`. Replaces the legacy flat `_ROLE_FROM_AXES[stat][reach]` map. (T.32, T.33b)
- V.33: Every combat stat is generated by `compose_stats` from the 6 axes — there is **no per-unit authored stat** except `stat_overrides` (which may target **any** stat key incl. premium `crit_chance`/`penetration`, is key-validated, and is applied **after tier-scale, before level-scale** so scalable overrides level-scale while non-scaled/premium ones stay flat). The intent stat-bias multiplier applies at **one fixed point** (after the axis + speed multipliers, before the tier `round()`) and must keep the HP·DPS power proxy `(dmg_mult · AS_mult) · sqrt(hp_mult · armor_mult · res_mult)` within **±10%** (re-flavour, not stealth buff); `threat`/`move_speed`/`crit_chance`/`penetration` are **off the power budget by design** (B.6) — the drift guard and `_assert_budget` ignore them. **T.35b re-tuned `_INTENT` (damage `1.08→1.14`, utility `0.94→0.87`) + `_DURABILITY` tanky STR/INT (`0.55→0.42`, B.20); the ±10% band is unchanged and still holds (proxy `1.075`/`0.947`).** (T.32, T.35b)
- V.34: **Three stat-scaling classes + fair total order.** `PRIMARY_SCALABLE_STATS` (`max_hp`/`strength`/`intelligence`/`armor`/`resistance`) scale on `sqrt(power)` (`PRIMARY_EXPONENT=0.5`, ≈ ×1.122/tier); `SECONDARY_SCALABLE_STATS` (`attack_speed`/`move_speed`/`mana_regen`/`threat`) scale on a **gentle** `SECONDARY_EXPONENT=0.0857` (≈ ×1.02/tier, ×1.428 T1L1→T10L3); only `attack_range` is `FLAT_STATS` (T.29c removes `ability_cost` — cast cost → per-ability `mana_cost`, V.48). Driven off the same `power(tier, level)` curve via `stat_multiplier(tier, level, exponent=PRIMARY_EXPONENT)`. **Stored quantities are int** except **`attack_speed` is float** (T.29-pre: cadence reads `int(attack_speed)`; sub-integer order via `round(attack_speed×1000)`); `move_speed`/`mana_regen`/`threat` stay int; only `crit_chance`/`penetration_pct` ratios are otherwise float; the four scale loops + `_assert_budget` route through the tuples (`SCALABLE_STATS` deprecated-aliases the primary tuple). `threat`/`move_speed` stay **off the HP·DPS power budget** (V.33, B.6). **B.14 is fixed in the comparator, not the stat:** `_event_sort_key` is the canonical side-independent total order **`(-round(attack_speed×1000), champion_id, load_order, kind)`** (T.29-pre: the quantized AS key **subsumes** the old coarse `-AS_int` level — it is monotonic in AS; **`milli_AS` removed** — sub-integer order now **derives** from the float `attack_speed`, so an `attack_speed` mul moves cadence **and** tie-order together, killing the desync where ability muls didn't ride the separate `milli_AS` field, B.18); `champion_id` breaks rare cross-champion exact ties; **`load_order`** is a deterministic side-independent permutation assigned in `compile_loadout` (from its `seed`, **never** team-block-then-enemy) — this removes the side-A bias for every tie incl. true mirrors. The legacy `speed_tiebreaker` is renamed **`formation_index`** (its surviving job is the enemy formation-position key, unrelated to tie order). Meters stay int. Pure fns of (tier, level)/seed, no per-tick RNG (V.2/V.14). (T.33a, B.14; amended T.29-pre, B.18; amended T.29c — `ability_cost` dropped from `FLAT_STATS`)
- V.35: **Speed-stat baseline parity.** `_BASE_STATS` `attack_speed` == `move_speed` == `mana_regen` == **`100`**, so a player compares the three speed stats as **equal-scale power investments** (resolves the #39 complaint that `mana_regen=10` was 10× off `attack_speed=100`/`move_speed=90` and unreadable). The per-meter **capacitor is deliberately unequal** — mana `ability_cost` (baseline `300_000`) ≫ action/movement `ENERGY_THRESHOLD=60_000` (a cast is worth ~5 autos) — and is **internal, non-player-facing**: comparability lives at the **baseline, not the threshold**. `ability_cost` is `FLAT` (per-kit deviations = intended longer/shorter casts); the three speed stats are `SECONDARY`-scaled (V.34). Baseline `ability_cost=300_000` (vs the cadence-neutral `360_000`) bakes a deliberate ~20% mage buff; `move_speed` 90→100 a ~11% (symmetric) movement buff. **Amended T.29c:** the `ability_cost` FLAT **stat is removed**; cast cost is now per-ability **`mana_cost`** (default `300_000`) authored on the ability def (`ABILITY_MANA`, V.48). The baseline-parity argument (the three speed stats =`100`) is unchanged; the mana capacitor value simply moves from the stat onto the ability `mana_cost`. (T.33, resolves #39; amended T.29c)
- V.36: **`game/save.py` is the sole file-I/O home for `Run` persistence.** The (de)serialization contract stays on the model dataclasses (`Run.to_dict`/`from_dict`); `save.py` is the disk layer over it, importing only `json`/`os`/`pathlib` — **no Flet** (extends V.1). `save_run(run, path)` writes **atomically**: temp `<path>.tmp` → `flush`+`fsync` → `os.replace` onto `path`, auto-creating parent dirs and removing the temp on any failure (readers never observe a partial file). `load_run(path)` **gates on `schema_version` before `Run.from_dict`**: `> CURRENT_SCHEMA_VERSION` → `UnsupportedSchemaError`; missing/non-int/`< 1` → `CorruptSaveError`; `from_dict`'s `ValueError`/`KeyError`/`TypeError` (validators + `_parse_enum` + missing required keys) are wrapped as `CorruptSaveError`; `FileNotFoundError` propagates **unwrapped** (callers branch on "no save yet"). Round-trip identity holds for current data (`load_run` of `save_run(x)` equals `x` at the `to_dict` level), and older payloads load via the `.get` back-compat defaults (B.4 `gold`→`amber`). `CURRENT_SCHEMA_VERSION` (=1) is the single source for the persisted version and the in-`load_run` migration hook point; bump only for a breaking change a `.get` default can't absorb. Errors: `SaveError` (base) → `CorruptSaveError`, `UnsupportedSchemaError`. (T.14)
- V.37: **Trait breakpoint shape + new-primitive determinism.** A trait's **apex** (top breakpoint) = **`min(carrier-pool, board-cap)`** — own (nearly) all carriers and/or commit the whole board. **Emblems are Kinship-only** (V.22, T.29) and act as **one substitute carrier**, so a Kinship apex is reachable at **`pool−1`** native; Callings/Affinities have no emblem (draft-only apex). A `TraitBreakpoint.count` may be an **int or a dynamic threshold** resolved **at loadout** against the live board cap — Packmate `@full-board` == current Tempest rank (V.20). All trait combat primitives are **RNG-free** (geometry / cadence counters, V.2/V.14, replay-stable): **kiting** (Skyborn — geometric retreat to attack-range distance from the nearest melee threat, with **plant-when-cornered / plant-when-≥2-adjacent / only-kite-melee / never-kite-without-target** guardrails; melee Skyborn gain **+1 `attack_range`** at the kiting-unlock rung so they can kite at all), **deterministic dodge** (every Nth incoming auto), **revive-once**, **second-wind threshold decaying-shield** (on HP crossing below a % → a decaying barrier via the V.28 pool, once/combat), **tidal HoT**, **time-ramp/enrage**. **Cheat-death effects stack with NO hard cap by design**, but are **diversified** so stacking is varied not redundant: exactly **one** true revive (**Mender**), the others distinct mechanics (second-wind shield = **Primordial**, tidal HoT = **Tidekin**, enrage = **Beast**). Exactly **one Tier-10 Primordial per Kinship** (the legendary anchor); Primordial **shop access is gated by 3 paired RUN-augments** (T.31), so the trait + T10 anchors ship **ready-but-dormant** in T.28a. **T.36a un-pins the 6 Primordials from the shared `hybrid/hybrid` mold — each T10 is now a distinct apex archetype (Aurion hybrid/hybrid, Nerei int/ability, Borealis hybrid/ability, Umbra str/auto, Mournhollow str/ability, Aerion hybrid/auto), still exactly one per Kinship + Primordial.** (T.28, extends V.20/V.21/V.22/V.28; diversified T.36a)
- V.38: **Every roster ability id has an `AbilityMeta`.** Every `active_ability`/`passive_ability` id referenced by a `ChampionDef`/`EnemyDef`, and every `BossDef` ability id (`phase1_active`, `phase1_passive`, `phase1_phase_hook`, `phase2_active`, `phase2_passive`, `on_death_hook` — the V.15 field-set), **must** resolve in `ABILITY_META` — CI-guarded (`test_all_{champion,enemy,boss}_abilities_have_meta`), mirroring V.15. `render(meta, source) -> RenderedAbility(name, text, formula, tags)` is **pure** (no Flet, no I/O — extends V.1) and reads numbers via `source.stat()`, so a base `Champion`/`Enemy` (roster sheet, via the `Champion.stat()`/`Enemy.stat()` field-lookup adapters) and a live `Piece` (combat, with modifiers; **bosses always via the compiled `Piece`**) render through **one** call. **Source-of-truth B:** headline damage/heal constants live **once** in `ScalingTerm`s the handler also reads — tooltip numbers **cannot drift** from combat numbers; `ScalingTerm.eval` delegates to `_eval_scaling` (`registries.py`), keeping `resolve_combat` **byte-identical** (V.2/V.14). A golden snapshot pins every rendered `formula`. **T.35a extends source-of-truth B to the whole closed `Magnitude` family (V.46) + clause-terms** — not only headline `ScalingTerm`s; every Tier-B scaler is now a rendered, drift-pinned `Magnitude`. (T.34, T.35a)
- V.39: **`100 ticks = 1 second` is the canonical display convention — ticks in code, seconds only at the user-faced boundary.** All game logic (`game/combat/`, statuses, cadence counters, durations, `expires_at_tick`, `current_tick`) operates in **ticks only**; **no mechanics module converts ticks↔seconds** (the conversion is never read back into the simulation, so determinism is untouched, V.2/V.14). The tick→second transform is **presentation-only**, applied at user-faced output: `ability_text.render` for ability blurb/clause durations and cadences, and `ui/` for any tick-valued surface. The single source is `TICKS_PER_SECOND = 100` defined in `game/ability_text.py` (the lowest pure user-faced formatter; consistent with the V.25 DOT cadence `default 100 ticks = 1s`); `ui/` imports it from there (never redefines, never the reverse dependency). A duration of `N` ticks displays as `N / 100` s. (T.34)
- V.40: **Hexproof targeting.** `StatusGate.HEXPROOF` (status `hexproof`, renamed from `untargetable`) excludes a piece from **single-target acquisition** — both the engine auto-attack target scan (`game/combat/engine.py`) **and every** single-target helper in `game/targeting.py` (`primary_target`/`lowest_hp_enemy`/`highest_ap_enemy`/`random_enemy`/`furthest_enemy`/`_closest_enemy`) — but **never** from AoE/untargeted effects (`enemies_in_radius`/`line_targets`/`neighbors_of`, or a cast iterating the full `ctx.enemies_of` list). A piece with `Piece.pierces_hexproof` ignores the exclusion (Spirit @8 — the lone bypass). The filter is a pure predicate (`target.is_gated(StatusGate.HEXPROOF) and not actor.pierces_hexproof`), RNG-free (V.2/V.14, replay-stable). (T.28d, B.15)
- V.41: **Cumulative trait rungs.** Trait resolution (`game/traits/__init__.py::_resolve_traits`) applies **only the single highest cleared `TraitBreakpoint`'s** bundle — **not a union** — and stat magnitudes are authored as the **total at that rung** (they replace, never stack). Therefore each rung **MUST re-include every mechanic rider a lower cleared rung grants**: a higher trait count never silently loses a lower count's mechanic. **Sole exception:** carrier-**movement** riders (`kiting`/`backline_seeker`) are omitted at a `TEAM_WIDE` apex — applying them team-wide would make every ally kite/seek (the documented apex movement-exception). Signature riders that must stay carrier-only at a TEAM apex are **`trait`-guarded** (`cc_immunity`/`pierce_hexproof`/`hexproof_opener` take a `trait=` arg, mirroring `on_death_spawn`), **not** dropped. CI-guarded by `tests/game/test_traits.py::test_trait_rungs_are_cumulative_for_mechanics` (probes each rung's mechanic fingerprint as a carrier; asserts monotonic non-decrease modulo the movement exception). (T.28d, B.16)
- V.42: **Weather Favor applies only as `source="weather:<state>"` modifiers.** Weather Favor is translated into `Modifier`s (`*_mult` → `("<stat>","mul",mult)`, `attack_range_delta` → `("attack_range","add",delta)`) carrying `source_id="weather:<state>"` and applied through `compile_loadout` via `apply_bundle` (the `weather_favored` T.28d override still builds from `WEATHER_BUFF_BASE[weather]` regardless of affinity). **The `base_stats` fold is deleted** — `loadout._apply_weather_to_piece` no longer mutates `piece.base_stats` in place, and **no engine path reads a weather base-snapshot**; weather is now a first-class attributable source (feeds `stat_breakdown`, V.45). `CLEAR` contributes no modifier (inert). Pure, RNG-free (V.2/V.14). (T.29-pre)
- V.43: **`compute_stat` is the single stat fold + resources are never `Modifier` targets.** Effective stats come **only** from `compute_stat = (base + Σadds) × Πmuls` with a `_STAT_FLOORS` clamp (`attack_range ≥ 1`, restoring the floor lost when weather left the clamped fold). **Resources — `hp`/`max_hp` and per-`ActiveSlot` mana — are NEVER `Modifier` targets**; every system that changes a max-resource (weather, traits `game/traits/__init__.py`, clones/turrets) **direct-sets + reconciles** from `stat()` after modifiers apply (`piece.max_hp = piece.hp = piece.stat("hp")`), because a resource carries a live current value the fold cannot express. Flow stats (str/int/attack_speed/move_speed/mana_regen/armor/resistance/crit/pen/threat/attack_range) flow through modifiers; resources reconcile. (T.29-pre)
- V.44: **Stat-scaling modifiers snapshot at apply — no self-feeding per-tick loop.** A `Modifier` holds a **static `value`** computed **once at apply time** off a defined base, not a live formula; `compute_stat` only sums frozen values. **No per-tick/per-event hook may apply a modifier whose value reads a stat that same modifier also feeds** (e.g. an HP-scaling-AP modifier and an AP-scaling-HP modifier re-applied each tick → unbounded feedback). Cross-stat scaling is allowed but evaluated once in the fixed `compile_loadout` step order (§10.1), keeping results deterministic (V.2/V.14) and bounded. (T.29-pre)
- V.45: **`Modifier.source_id` uses a fixed prefix vocab.** Every applied `Modifier` tags its origin as `<prefix>:<id>` with `prefix ∈ {item, augment, passive, trait, weather}`; the prep-view `stat_breakdown(piece)` (pure `game/`, no Flet — extends V.1) groups `piece.modifiers` by this prefix into per-source per-stat deltas (plus a `base` row from `piece.base_stats`) so the UI can show effective total + a hold-modifier breakdown. The vocab is the contract item (T.29a) / augment (T.31) factories author against. (T.29-pre)
- V.46: **Closed `Magnitude` family + no orphan handler stat-read.** Every numeric outlet an ability handler computes from a stat flows through a registered `Magnitude` — never free inline math. The family is **closed**, modeled on GAS's `EGameplayEffectMagnitudeCalculation`: `ScalingTerm` (linear `base + Σ source.stat·coeff`, the canonical kind), `PctResource` (`%-of-max_hp`, reads `.max_hp` **directly** to dodge the `Piece.stat("max_hp")==0` trap of `effects.py::compute_stat`, `of="self"|"target"`), `MaxOfTerm` (`base + max(source.stat(s)…)·coeff`), `SetByCaller` (`base + caller[key]·coeff`, runtime value the handler injects). All share one Protocol — `eval(source, target=None, caller=None) -> float` + `render_formula`/`render_inline` — **pure, RNG-free** (V.2/V.14), **self-describing** so `ability_text.render` is pure per-kind dispatch (no special-casing). **No `.stat()`/`.max_hp`/`.hp` read in an `ABILITY_REGISTRY`/`PASSIVE_REGISTRY` handler may go uncovered**: each is backed by a `Magnitude` on that ability's `AbilityMeta` (in `terms` or any `clauses[].terms`) or is on the explicit `_PROSE_ALLOWLIST` (id→reason: predicate gates, summon statlines, flat resource growth). CI-guarded (`test_no_orphan_stat_reads`), mirroring V.38. Extends source-of-truth B (V.38) to all kinds + clause-terms. (T.35a)
- V.47: **Axis↔scaling alignment.** Every `ChampionDef`/`EnemyDef` whose `stat="int"` **must** reference INT via a `Magnitude` on its active/passive `AbilityMeta`; `stat="hybrid"` references **both** STR and INT; `stat="str"` references STR. The universal auto-attack (`1.0·STR + 0.25·INT`, `combat/context.py`) counts for STR only, so a `str` unit is auto-satisfied while `int`/`hybrid` units earn their primary via the kit — stops the dead-stat drift (an INT-heavy statline whose kit never reads INT, #42 Finding B / B.20). CI-guarded (`TestAxisScalingAlignment`), mirrors V.22/V.38; depends on V.46 making every Tier-B scaler a visible `Magnitude`. **T.36a closes the guard gap (B.24): the original `test_int_and_hybrid_units_reference_int` checked INT only — it never verified a `hybrid` piece references STR; the guard now enforces `hybrid`→both STR+INT (+ a dead-STR-hybrid detector test).** (T.35b; guard completed T.36a)
- V.48: **Per-ability mana primitive + deterministic cast scheduling.** Each `ActiveSlot` carries per-slot **`mana_cost`/`max_mana`/`start_mana`/`priority`** (+ runtime `current_mana`). `mana_cost`'s base is authored **on the ability def** via an `ABILITY_MANA` registry (the replacement for the deprecated `ability_cost` stat — V.34/V.35 amended); **`mana_regen` is the only piece-level mana stat and the cast-rate knob** (the lone `Modifier`-able mana value). **`max_mana` = universal pool cap** — regen/start/`grant_mana` all clamp to it; **default `= 2× mana_cost`**; never auto-raised. Defaults: `mana_cost=300_000`, `max_mana=2×mana_cost`, `priority=1`, `start_mana=current_mana=0`. The pool fields are **resource state** — direct slot writes only, **never `Modifier` targets** (extends V.43); **no item/`Modifier` ever changes `mana_cost`** (mana items grant `mana_regen` via `Modifier` or `start_mana` via slot — kills negative-cost stacking). **Charge = deterministic weighted-rank cycle:** cycle length `sum(slot.priority)`, each slot occupies `priority` positions, **one** slot charged per tick with the full `mana_regen` (skip a slot already at `max_mana`) ⇒ total throughput = `mana_regen`/tick **regardless of slot count**. **Cast = at most one per action window;** among slots with `current_mana ≥ mana_cost` the **highest `priority`** casts (tie → lowest slot index). Single-slot, no-item combat is byte-identical to pre-T.29c (V.2). RNG-free cadence (V.2/V.14). (T.29c, amends V.34/V.35, extends V.43)
- V.49: **Multi-slot pieces + `Multicaster` Calling.** `Champion`/`Enemy` carry **`active_abilities: list[str]`** (`from_dict` reads the legacy single `active_ability` key; a one-element list ⇒ one `ActiveSlot` ⇒ byte-identical, V.2); `compile_loadout` builds **one `ActiveSlot` per entry**, each seeded from `ABILITY_MANA` (V.48). There is **no `active_ability` singular** — one list is the only ability concept (single/null/multi all just list lengths; an empty list = a deliberately ability-less stat-stick with no mana bar). **Abilities are discovered by convention, override by data** (`content.discover_abilities`): a roster def with `abilities=None` auto-attaches every registered **`{id}.active`, `{id}.active2`, …** (sorted) — registering a `.active2` handler is all it takes; an explicit `abilities=[...]` overrides for named kits (bosses) or `[]` for null. **Every multicaster's slots MUST have unique integer `priority`** (no two slots sharing the same priority) so abilities reach their cast threshold at **different** times — intermittent casting, never lockstep simul-cast; best case **both `priority` AND `mana_cost` are unique** per piece, and **mana costs SHOULD be coprime** in reduced form (i.e. `gcd(cost_a / 10k, cost_b / 10k) == 1`) so cast cadences never lock in step. Default authoring = **same cost, unique priorities** (primary `priority=2` dominant, secondary `1`); high-tier **Ultimate** secondaries instead diverge by cost (`2×` default) with `priority` ∝ cost so the ult stays castable ≥1×/fight at a high-tier mage's MR with no items. **Starting-mana items grant a slot-count-invariant TOTAL, split across slots by priority weight** (not per-slot — that would duplicate value on multi-slot pieces, the same bug the MR cycle avoids). New Calling **`Multicaster`** ∈ `CALLING_TAGS` (extends the V.22 vocab guard), breakpoints **2/3/4 per-trait** sized to its ~6-carrier pool (no team-wide apex — apex = `min(pool, cap)`, V.37). New mechanic **`cast_momentum`** (`on_cast_complete` → stacking `attack_speed` mul + small `mana_regen`, capped) is **RNG-free** (cadence per cast, extends V.37). Enemies may field extra slots but **never light up the `Multicaster` Calling** (V.22 — enemy tags are opaque). (T.29d, extends V.22/V.37, builds on V.48)
- V.50: **Every ability activation records exactly one `cast` event.** Both cast paths emit one `EVENT_CAST` into `BattleResult.events`: registered abilities via `BattleResultRecorder._on_cast` (subscribed to the `on_cast` the `ctx.cast_ability` fires), and the unregistered-ability fallback via the engine's direct `recorder.record_cast`. Neither path fires both (the fallback bypasses `cast_ability`/`on_cast`) ⇒ no double-count, no drop. Cast **damage/heal** is attributed separately (`_on_damage_dealt` / heal totals); the cast event marks the activation (amount may be 0). This keeps casters visible in the combat log, sim metrics, and `turns` count — a `pass` stub here silently zeroed all registered casts (B.22). (T.29c, fixes B.22)
- V.51: **Antiheal is the `grievous` status, honored in `ctx.heal`.** A `grievous`-afflicted piece receives healing scaled by `GRIEVOUS_HEAL_MULT` (0.5) — the single grievous-wounds primitive. `ctx.heal` is the **only** heal path and applies the reduction before the `max_hp` clamp, so every heal source (regen items, lifesteal, ability heals) respects it uniformly. Pure marker status (no gates/DOT); applied by Bramble Carapace (attacker), Witherbloom Censer (target), and available to abilities. RNG-free (V.2/V.14). (T.29a item rebalance, fixes B.23)
- V.53: **Every *applied* status must have an engine consumer — no dead soft-CC markers.** If a
  `StatusDef` is applied anywhere (`ctx.apply_status("<id>", …)`), the engine MUST *read* it through
  exactly one of: a `StatusGate` (stun/silence/disarm/root/frozen/hexproof — honored in meter/target/
  move gates), a DOT field (`dot_per_tick`: burn/poison/grief/sudden_death), `ctx.heal`'s `grievous`
  check, or a **named handler** that consumes it (`slow` → `_slow_factor` meter throttle; `taunt`/
  `focus_fire`/`charged`/`stone_charge`/`soul_charged`/`nerei_grudge` → verified engine/kit readers).
  A status **applied but never read** is a bug (B.25, e.g. `slow` pre-T.31). A status **defined but
  never applied** (`soaked`) is harmless dead-def, exempt. Specifically `slow` throttles action+movement
  meter gain by `max(0.40, 1−0.15·stacks)`, RNG-free (V.2/V.14). (T.31, fixes B.25)
- V.52: **Piece stat-stacking is in-combat only; cross-`Run` permastacking is augment-exclusive.** No champion/enemy kit grants stat stacks that persist across battles — holds **by construction** of V.2 (combat is pure; all `Piece` runtime state rebuilds per `resolve_combat` from the `ChampionDef`, so any in-combat ramp — Aurion *Ascendance* cast-stacks, `grief`/`nerei_grudge`, granite_gorilla *Stone Charge* — resets each fight). Only **augments** (T.31, `RUN` scope) may accumulate across a `Run`. Ability/passive blurbs MUST say "until end of battle", never "permanently" (a "permanent" wording mislabels an in-combat ramp). Blurb-wording guard. (T.36a)
- V.54: **Combat event-stream completeness — every visible-state-changing beat emits exactly one `BattleEvent`.** The animation-facing event taxonomy is `move`/`attack`/`cast`/`ability`/`death` **+ `heal`/`dot`/`status`(apply+expire)/`spawn`/`despawn`**; each beat has **one** producer path in `BattleResultRecorder` (no double-count, no silent drop). **`cast` vs `ability` are distinct beats: `cast` is the *activation* marker** (a piece casts — `amount=0`, one per `on_cast`, `_on_cast`), **`ability` is the resulting *damage*** (one per target hit, `_on_damage_dealt` when `tag == ABILITY`) — first a `cast`, then per-target `ability` beats. HP-changing beats (`attack`/`ability`/`heal`/`dot`) carry `hp_after`/`barrier_after` = the engine's post-event `target.hp`/barrier truth (read after `deal_damage` applies `to_hp`, `context.py:272-283`) — correct under V.28 barriers (full pre-barrier `amount` still fired for DPS accounting) + DOT + heals + `grievous`. **A `dot` beat fires for EVERY status-DOT tick regardless of `damage_type`** — `_on_damage_dealt` emits it when `tag == DOT` **or** `DamageEvent.is_dot` (set by `process_statuses` on both its DOT `deal_damage` calls, T.12b). This makes **`dot_true_damage` statuses (`sudden_death`, `SourceTag.TRUE`) visible** — they were silent (TRUE matched no beat branch), which is why sudden death instakilled with no animation; the combat view absorbs these into `pre_beats` (a drip *between* actions, never a standalone step). The `ability`/`attack` beat's `amount` is the **final post-mitigation** figure with `is_crit` + `damage_type` (`physical`/`magical`/`true`, carried on `DamageEvent`, `events.py`) — the single `ctx.deal_damage` chokepoint is the one producer (no separate ability handler, V.43-style single fold). With `ability` added, the stream is now HP-complete; the combat view still reads bars from the live stepper (V.57 — one source of truth, the beat's `amount`/`type` drives the floating *number*, not the bar). The `move` beat carries **structured `dest_q`/`dest_r` int fields** (not a parsed `note` string, T.37c). The **`status` (apply) beat fires once per *acquisition*, not per re-apply** (T.12a): the recorder tracks a `(piece_id, status_id)` active set (cleared on `status_expire`) and emits a beat only on the transition into a status the piece didn't already hold — stack-refreshes / re-applications emit no new beat (kills the sudden-death spam — re-applied every engine tick — and poison-restack spam; the view reads live stacks from the stepper, V.57, so the beat is just the acquisition cue). `expire_summon` fires a new `on_despawn` so summon removal is distinguishable from `death` (fade vs death-anim). Generalizes V.50 ("one cast = one event") to the whole stream. The recorder is **observer-only** — new subscriptions/events/fields never feed combat math, and **`turns` counts `attack`+`cast` only** (the new `ability` beats are excluded) ⇒ damage totals + `turns` unchanged ⇒ sims byte-identical (V.2/V.14); only `combat_log` golden snapshots re-baseline. (T.37a, fixes B.26/B.27; `ability` beat T.37 follow-up, closes B.28 cosmetic remainder)
- V.55: **Combat state for the view is recomputed by replay, never recorded as per-tick keyframes.** The engine exposes a **stepper** (the `engine.run` tick loop made drivable); `resolve_combat`/`resolve_boss_combat` are reimplemented on it **byte-identically** (single public entry preserved, V.2 — same loop body, no determinism re-baseline). Two read paths, both pure + UI-free (extends V.1), both byte-identical to the resolved fight (V.2): (1) **sequential playback** holds **one live `CombatReplay` instance** (`game/combat/replay.py`, T.37c) that advances the engine **forward** (`.advance()` one event-bearing tick / `.step_to(tick)`) and reads live `PieceView`s **as it goes** — O(total ticks) for a whole playthrough, the default Next/autoplay path; (2) **random access** `inspect_at_tick(team, enemies, weather, run_mods, tick) -> list[PieceView]` **re-runs from scratch** to `tick` (back-scrub / jump / click-at-arbitrary-tick only). Both run on a **deep clone** of `run_mods` (the mutable `augment_state` quest trackers ⇒ zero side effects on the caller) and return **read-only value structs** (hp/barriers/per-slot mana/effective stats via `piece.stat()` incl. STR/AS ramp/statuses/position) — this live state is **complete** (every HP change, incl. registered-ability burst the event stream omits, B.28). Raw `Piece` and Flet types **never escape `src/game/`** (V.1/V.14). Per-tick state is **never** persisted into `BattleResult` (would bloat T.14 saves + re-introduce stat-drift). (T.37b; forward stepper T.37c)
- V.56: **The combat view is pure presentation over the replay backend.** `ui/views/combat.py` renders a fight **only** through `resolve_combat` + the forward `CombatReplay` stepper + `inspect_at_tick` + the recorded `BattleResult` stream — it implements **no** combat math (extends V.1: `ui/` imports `game/`, never the reverse; `game/` never imports `ui/`). It is **interactive but read-only**, fed one **`CombatSession`** input bundle (`team`/`enemies`/`weather`/`run_mods`/`node_id`) built **identically** by the dev harness (now) and the Prep/Trail `Start Combat` flow (T.15/T.23, later) — one view, swappable producers. Playback is **event-paced** (default = manual event-step; autoplay is an opt-in mode), **not** tick=second real-time; `TICKS_PER_SECOND` (V.39) renders *durations as text* only, never playback timing. **Resource/state truth — HP, barrier, per-slot mana, effective stats (STR/AS ramp), board position — comes from the live replay (forward stepper for sequential playback, `inspect_at_tick` for random seek), NOT the event stream** (V.57). The recorded stream supplies **animation cues** (which beat to play this tick: attack/cast/heal/dot/status/death/spawn/despawn/move) **+ the action-queue projection** (future attack/cast/move beats, round = `ROUND_TICKS`) — never the resource numbers (incomplete for them, B.28). The boss path resolves through `src/game/combat/` (never `tools/`). (T.12)
- V.57: **The combat view's resource truth is the live replay, never the event stream's partial resource fields.** Per-tick HP/barrier/per-slot mana/effective stats (incl. STR/AS ramp)/position rendered by `ui/views/combat.py` + `ui/combat_playback.py` are read **only** from the live engine via the forward `CombatReplay` stepper (sequential) or `inspect_at_tick` (random access) — both deterministic replays of the resolved fight (V.55/V.2). The recorded `BattleResult` event stream is **animation cues + action-queue projection only**; its `hp_after`/`barrier_after`/`mana_after` fields are telemetry, **not** a reconstruction source — they are stamped on only *some* beat types (basic-attack/DOT/heal), not registered-ability burst (B.28). Rationale: one source of truth (the engine via replay) ⇒ bars cannot drift from the sim, and there is no second resource pipeline to keep complete. (T.12a, fixes B.28; refines V.54/V.55/V.56)
- V.58: **`damage_type` is a closed vocabulary — `physical` | `magical` | `true`.** `ctx.deal_damage`'s mitigation switch keys on it: `magical` → `resistance`, `physical` → `armor`, `true` → unmitigated (also reached via `tag == SourceTag.TRUE`). An **unknown string silently mitigated as physical** is forbidden — `deal_damage` **validates** `damage_type` against the frozen set and **raises** on anything else (fail-loud, V.2: a typo can never quietly flip mitigation again). Canonical constants `DMG_PHYSICAL`/`DMG_MAGICAL`/`DMG_TRUE` (`engine.py`); the only legal default is `magical`. (B.29)
- V.59: **The boss combat path resolves through `src/game/combat/resolve.py::resolve_boss_combat` — the single src-side boss entry.** It composes the same primitives as `resolve_combat` plus a map effect: `build_combat` → `attach_map_effect(map_effect_id, ctx, seed)` when set → `run` → `build_result`. It takes a **`map_effect_id: str`** (never a `bosses/`-content type, so `combat/` stays content-import-free — the package HARD RULE; `attach_map_effect` is a deferred `loadout` import) and is **byte-identical** to the former `tools/playtest/_common` version (V.2 — same primitives, order, default seed); `tools/` now **delegates** to it. `CombatReplay`/`inspect_at_tick` accept the same `map_effect_id` and replay the boss fight identically (V.55). The combat view reaches the boss path **only** via `src/game/combat/` — `ui/` never imports `tools/` (V.1). (T.12b)
- V.60: **Combat outcome is survivor-based, never forced by `timed_out`.** `CombatOutcome` follows the engine's survivor-based `winner` (`recorder.build_result`): **WIN** = team has ≥1 living piece and enemy none; **LOSS** = enemy survivors and no team; **DRAW** = **neither side has a survivor** — a true mutual wipe, reachable only when one `process_statuses`/sudden-death DOT pass kills the last of both sides in the same tick (action resolution checks `both_sides_alive()` after each action ⇒ a side that wipes first loses, so actions never draw). `timed_out` (incl. sudden-death resolution) is an **independent flag** on `BattleResult` and must **not** change the outcome — the prior override `if self._timed_out: outcome = DRAW` is **removed** (it relabeled real winners — e.g. a boss wipe where the enemy survives — as DRAW). Outcome maps from `winner` only, uniformly. Determinism note: timed-out fights with a survivor now resolve WIN/LOSS not DRAW (no committed sim golden — `results/` gitignored; symmetric mirror-stalemate tests stay DRAW via simultaneous DOT wipe). (T.12b)

## T. Tasks

**Status legend:** ✅ Done — ✔ implemented & tested | 🔶 Partial — incomplete implementation | 📋 Plan — documented design, not yet coded | ❌ Not started — no plan or code

| # | Task | Files (code paths are relative to `src/`; `docs/` and `tools/` paths are repo-root relative) | Depends | Est | Status |
|---|---|---|---|---|---|
| T.1 | Data models — Champion, Enemy, Node, Run, BattleResult, WeatherState + NodeType/NodeState + combat runtime state + JSON serialization helpers | `game/models.py`, `docs/design/tasks/t1_data_models_plan.md`, `docs/design/tasks/t1_model_contracts.md` | — | M | ✅ Done |
| T.2 | Weather effects — directional predator/prey ring; two decoupled systems (node-weather buff/debuff + affinity damage triangle), per-weather stat packs, shop weight, weather favor applied at combat init (`combat_modifier` via `loadout._apply_weather_to_piece`) | `game/weather_effects.py`, `docs/design/tasks/t2_weather_effects_plan.md` | T.1 | M | ✅ Done |
| T.3 | Combat engine — tick-based auto-resolve (10ms tick simulation), apply weather modifiers | `game/combat/` | T.1, T.2 | M | ✅ Done |
| T.4 | City route — ~50 cities (one per node) across 6 staged continents, coordinates, stage affinity, enemy pools | `game/route.py` | T.1 | M | ✅ Done |
| T.5 | Content — define champion roster (target: 1 per affinity × 10 tiers = ~60 champions; MVP cut OK) + ~5 enemy types with stats + synergy trait catalog | `game/content.py` | T.1 | M | ✅ Done |
| T.6 | OpenWeather client — fetch current weather, parse to WeatherState | `api/weather.py` | T.1 | S | ✅ Done |
| T.7 | Cache + refresher — stateless per-city cache (`unknown` / `live`+`fetched_at` / `substitute` holding city-default weather), 3-stream refresher (A full RR 50, B window `[current+1..+6]` count-clamped, C uniform random) ticks 1/min deduped → ≤3 calls/min, sync fetch on advance-to-`unknown` | `api/cache.py`, `api/refresher.py`, `docs/design/tasks/t7_cache_refresher_plan.md` | T.6 | M | ✅ Done |
| T.8 | Theme + shared components — colors, fonts, champion card, weather badge | `ui/theme.py`, `ui/components/` | — | S | ✅ Done |
| T.9 | Main menu view — new game, load game, quit | `ui/views/menu.py`, `main.py` | T.8 | S | 📋 Plan |
| T.10 | Run-start flow — initial champion pick (1-of-3 offer), first shop population, starting Amber/Tempest state init | `game/run_init.py`, `ui/views/trail.py` | T.5, T.8, T.22 | S | 📋 Plan |
| T.11 | Route map visualization — Canvas with city nodes + weather icons | `viz/route_map.py`, `ui/views/trail.py` | T.4, T.6, T.8 | L | 📋 Plan |
| T.37c | Resumable forward combat-replay stepper + move-coords hardening (combat-view prep, headless). Refactor `engine.run`'s `for tick` loop into a **single generator loop body** (`_step_combat`) driven two ways — `run()` **drains** it (byte-identical, V.29 one-loop preserved), `CombatReplay` **steps** it forward (`.step_to(tick)` + `.pieces()` live `PieceView`s) — O(total ticks) playback vs `inspect_at_tick`'s O(N²) per-step re-run (kept for random seek; reimplemented **on** `CombatReplay` ⇒ one read driver, no parallel path). **Drop** the half-built `stop_after_tick` kwarg. Live state complete incl. **registered-ability burst the stream omits** (B.28). Replace `move`+`spawn` `BattleEvent` `note=f"{q},{r}"` string with structured `dest_q`/`dest_r` int fields (recorder + `combat_log` + serialization round-trip, legacy → `-1`). Observer-only / read-only ⇒ sims byte-identical (V.2/V.14) | `game/combat/engine.py`, `game/combat/replay.py`, `game/models.py`, `game/combat/recorder.py`, `game/combat_log.py`, `tests/game/test_combat_replay.py`, `tests/game/test_combat.py`, `docs/design/tasks/t37c_forward_replay_stepper_plan.md` | T.37a, T.37b | M | ✅ Done |
| T.12a | Combat view core + dev harness — flet.canvas hex board (10×7), pieces at coords, **DEFAULT manual event-step** playback (+ optional autoplay/fast-fwd) driving the **forward `CombatReplay` stepper** (resource truth: live HP/mana/stat bars via the stepper, V.57; back-scrub via `inspect_at_tick`) with the T.37 stream as **animation cues + action queue**, per-event animations + floating damage/heal numbers + death/despawn; action-queue with 2-round projection + round markers (entries = moves + attacks/casts; moves smaller + movement-iconed); click-to-inspect (live stats via the replay + equipped items + traits; global active augments); combat-end panel; dev-harness launcher (FIGHT/CHALLENGE/REWARD all combats, REWARD = easy fight + team/weather/augments/items → `CombatSession`) + minimal `main.py` dev entry (`TEMPEST_DEV=1`); pure Flet-free `combat_playback` model (queue projection + cue derivation, tested) | `ui/views/combat.py`, `ui/views/dev_harness.py`, `ui/combat_playback.py`, `main.py`, `docs/live/systems/ui.md`, `tests/ui/test_combat_playback.py`, `docs/design/tasks/t12_combat_view_plan.md` | T.3, T.8, T.37a, T.37b, T.37c | L | ✅ Done |
| T.12b | Combat view boss + polish — **phase A (readability/animation, V.56/V.57):** token movement tween (glide, not pop), attack/cast **target arrows**, **tickwise DOT reveal** (manual+autoplay; incl. sudden-death **true-DOT now beat-emitting** via `is_dot`, V.54 — was silent ⇒ instakill), **sudden-death indicator** (header badge + queue divider), status-icon row, real-time-scaled autoplay pacing. **Phase B (boss):** promote `resolve_boss_combat` `tools/`→`src/game/combat/resolve.py` (takes `map_effect_id`, content-import-free, byte-identical V.2/V.59) + map-effect-aware `inspect_at_tick`/`CombatReplay` + map-effect board overlay + harness BOSS node. Sprites + tick-by-tick admin mode deferred | `ui/views/combat.py`, `ui/combat_playback.py`, `ui/views/dev_harness.py`, `game/combat/resolve.py`, `game/combat/replay.py`, `game/combat/recorder.py`, `game/combat/context.py`, `game/events.py`, `tools/playtest/_common.py`, `docs/design/tasks/t12b_combat_view_polish_plan.md`, `docs/live/systems/ui.md`, `tests/ui/test_combat_playback.py`, `tests/` | T.12a | M | ✅ Done |
| T.13 | Run summary visualization — BarChart of damage per battle | `viz/run_summary.py`, `ui/views/summary.py` | T.3, T.8 | M | 📋 Plan |
| T.14 | Save/load — JSON serialization of Run state | `game/save.py` | T.1 | S | ✅ Done |
| T.15 | Routing + app wiring — connect all views in main.py | `main.py` | T.9-T.13 | M | 📋 Plan |
| T.16 | Unit tests — combat, weather effects, API parsing | `tests/` | T.1, T.2, T.3, T.6, T.7 | M | ✅ Done |
| T.17 | Documentation — README, prompting strategy, flow chart | `README.md`, `docs/` | all | M | 🔶 Partial |
| T.18 | Power & scaling model — `P` formula, `√P` stat coupling, economy cost curve | `game/scaling.py`, `docs/design/tasks/t18_power_scaling_plan.md` | T.1 | S | ✅ Done |
| T.19 | Encounter generation — seed-deterministic squad/offer fill, enemy power clustering, node budgets | `game/encounter.py`, `docs/design/tasks/t19_encounter_generation_plan.md` | T.1, T.4, T.5, T.18 | M | ✅ Done |
| T.20 | Ability/passive/status framework — registry, typed event bus, status gates, boss phase hook | `game/abilities/`, `game/effects.py`, `game/events.py`, `game/status.py`, `game/registries.py`, `docs/design/tasks/t20_ability_framework_plan.md` | T.3 | L | ✅ Done |
| T.21 | Challenge & boss encounters — champion-faction challenges, 2-phase bosses, auto-battle-aware map effects | `game/encounter.py`, `game/board.py`, `game/map_effects.py`, `game/bosses/`, `docs/design/tasks/t21_challenge_boss_plan.md` | T.19, T.20 | M | ✅ Done |
| T.22 | Economy & shop — Amber income per node (+3 base, +1-3 win bonus, +interest 1/10 cap 5), shop refresh (5 slots, auto-refresh each node, manual reroll 1 Amber, first reroll per node free), buy `Cost(T)=T`, sell `floor(Cost/2)`, 3-copy leveling, SUPPLY 1-of-5 free recruit, team-size Tempest leveling (accelerating thresholds 2/4/6/10/14/18/24/30/36, free +2/fight, all-or-nothing Amber rush 1:1, max rank 10), stage-gated tier probabilities | `game/economy.py`, `game/shop.py`, `game/models.py`, `docs/design/tasks/t22_meta_progression_plan.md` | T.1, T.5, T.18 | L | ✅ Done |
| T.23 | Prep formation snapshot integration — lock player board placement in Prep, validate deployment constraints, pass explicit coordinates into combat init | `ui/views/prep.py`, `game/models.py`, `game/combat/`, `docs/design/tasks/t23_prep_formation_snapshot_plan.md` | T.1, T.3, T.15 | M | 📋 Plan |
| T.24 | Enemy formation policy — deterministic role-aware spawn planner (frontline forward, backline protected, size-aware packing) with safe fallback | `game/formation.py`, `game/combat/`, `docs/design/tasks/t24_enemy_formation_plan.md` | T.3, T.5, T.23 | M | ✅ Done |
| T.25 | Power simulation & balance benchmarking — deterministic matchup sweeps and empirical power ratings | `tools/simulation/`, `docs/design/tasks/t25_power_simulation_plan.md` | T.3, T.5 | M | ✅ Done |
| T.26 | Combat engine unification — `resolve_combat` delegates to the new loop via `BattleResultRecorder`; legacy tick loop retired; Weather Favor applied in `compile_loadout` | `game/combat/resolve.py`, `game/combat/engine.py`, `game/combat/recorder.py`, `game/loadout.py` | T.3, T.20 | M | ✅ Done |
| T.27 | Playtesting CLI — dev-facing tools for sim_fight / sim_node / sim_run / inspect / inspect_node, no Flet, pure consumers of `src/game/` | `tools/playtest/`, `docs/design/playtesting/` | T.3, T.5, T.19, T.21, T.26 | M | ✅ Done |
| T.28a | Synergy trait framework + declarative content + roster rebalance — `TraitScope`/`TraitBreakpoint` (+ `DynamicThreshold`) types + `@register_trait`; `_resolve_traits` team roll-up in `compile_loadout` (unique-id count, scope, §10.1 order, **apex=`min(pool,cap)`** + dynamic-threshold infra for Packmate `@full-board`); affinity-trait synthesis from `affinity`; `BattleResult.trait_activations`; **all declarative stat-pack breakpoint rungs** (Affinities + Kinship/Calling stat portions); Calling-vocab reconciliation (drop 4 dead T.5 tags, add `Packmate` + ~8 T1-3 carriers — B.9); **roster rebalance** (kinship pools Beast 18→14/Spirit 15→11/Scaled+Tidekin+Swarm up; **one Tier-10 Primordial per kinship**; Hunter spread T2-9) | `game/traits/`, `game/loadout.py`, `game/models.py`, `game/content.py`, `docs/design/tasks/t28_trait_effects_plan.md` | T.5, T.20, T.26 | L | ✅ Done |
| T.28b | Trait combat primitives batch 1 + breakpoints — `StatusGate.UNTARGETABLE`, `taunt`, deterministic dodge, **revive-once** (Mender), **threshold decaying-shield/second-wind** (Primordial — reuses V.28 barriers), **tidal HoT** (Tidekin), time-ramp/enrage (Beast/Skirmisher), **kiting movement** (Skyborn — geometric retreat to attack-range from nearest melee, plant-when-cornered/swarmed, melee Skyborn +1 range), **backline target-priority** (Stalker @2); all RNG-free | `game/status.py`, `game/piece.py`, `game/combat/engine.py`, `game/combat/context.py`, `game/targeting.py`, `game/traits/`, `docs/design/tasks/t28_trait_effects_plan.md` | T.28a | M | ✅ Done |
| T.28c | Trait mechanic + apex riders via **hook idioms over existing `ctx`** (RNG-free, no new engine subsystems) — Hunter bonus-auto/empowered-shot/cleave/team-aura; Mystic `ability_can_crit`+ability-splash; Guardian start+periodic shields; Bruiser attack-lifesteal (+team); Skirmisher @8 team AS-ramp; Stalker hi-HP-bonus/mana-on-kill/untargetable-after-takedown; Channeler free-cast/first-cast-twice (recast); Warden cast-shield-lowest/opening-team-shield; Trickster slow-on-cast/taunt-on-cast/mana-denial-aura; Mender heal-splash/overheal-shield; Spirit echo (cadence recast); Swarm on-death chitin spawn; Packmate `@full-board` (stat pack, T.28a) | `game/traits/`, `game/abilities/`, `docs/design/tasks/t28_trait_effects_plan.md` | T.28b | M | ✅ Done |
| T.28d | Trait apex riders + hexproof correctness + deferred-flavor fold-ins — **rename `untargetable`→`hexproof`** + **fix** single-target acquisition to honor the gate (AoE/untargeted still hits; `Piece.pierces_hexproof` bypass for Spirit @8) [B.15, V.40]; 5 **affinity @10** riders (Galvanized crit-arc, Frostbound chill-attackers, Stormfed mana-haste, Shrouded longer hexproof-opener, Overcast burst-reduction) + Sunlit premium-stat pack; **Scaled** @5 hard-CC immunity (`cc_immune` + `apply_status` guard) + @8 full favorable weather override (`weather_favored`, pre-weather marker pass); **Spirit @8** reduced-potency echo (`ctx._echo_potency`) + mana-haste + hexproof pierce; fold-ins Beast @4/@6 str-ramp, Skyborn @3 kite-reward, Tidekin @3 ally-heal; all RNG-free. **Primordial @1 signatures + @3 tier-up deferred to T.31 [D.20].** | `game/status.py`, `game/piece.py`, `game/targeting.py`, `game/combat/context.py`, `game/combat/engine.py`, `game/loadout.py`, `game/traits/`, `tests/game/test_hexproof.py`, `docs/design/tasks/t28d_trait_apex_hexproof_plan.md` | T.28c | M | ✅ Done |
| T.29-pre | Combat stat substrate (sequences FIRST in the T.29 block — see plan [Part B / §B.10](docs/design/tasks/t29_item_engine_plan.md)) — **Commit 1:** weather → `source="weather:<state>"` `Modifier`s (delete the `base_stats` fold in `loadout._apply_weather_to_piece`) [V.42] + HP/resource resync via the trait template + `attack_range` floor (`_STAT_FLOORS`) in `compute_stat` [V.43] + `(base+Σadds)×Πmuls` as the universal compose contract (weather scales item/augment adds) + standardized `Modifier.source_id` prefix vocab `item:`/`augment:`/`passive:`/`trait:`/`weather:` [V.45]; **Commit 2:** `attack_speed` int→float, **drop `milli_AS`** everywhere (cadence `int(AS)`, tiebreak `round(AS×1000)`; no save migration — `from_dict` reads the float) [amends V.34, B.18] + delete the trait `milli_AS` rider modifiers; **also** `stat_breakdown(piece)` pure helper [V.45] + V.44 anti-runaway guard; **one determinism re-baseline** — Commit 2 (AS float) shifts cadence timing by ≤1 tick (int-truncate vs old round); Commit 1 (weather modifiers) shifts weather-fight stat values (unrounded float mul compose); determinism preserved (V.2) | `game/loadout.py`, `game/weather_effects.py`, `game/effects.py`, `game/models.py`, `game/content.py`, `game/scaling.py`, `game/encounter.py`, `game/combat/engine.py`, `game/traits/_packs.py`, `game/traits/mechanics.py`, `tests/game/test_tiebreak.py`, `tests/game/test_scaling.py`, `tests/game/test_trait_mechanics.py`, `docs/design/tasks/t29_item_engine_plan.md` | T.2, T.20, T.28d, T.33a | L | ✅ Done |
| T.29a | Item engine — components + combined + 16 core cut — real component→stat mapping (mana per-`ActiveSlot`, not a stat), `RECIPE_MAP` (8×8 = 36) + `combine()` recipe branch, `Champion.items` (≤3 persistent) equip applied in `compile_loadout`, `@register_item` factories for 8 components + 16 core-cut items (modifier + hook, closure-per-combat), seed-deterministic REWARD-node drops | `game/items/`, `game/loadout.py`, `game/models.py`, `game/encounter.py`, `docs/design/tasks/t29_item_engine_plan.md` | T.1, T.20, T.22 | L | ✅ Done |
| T.29b | Items — remaining 20 combined + emblems + special — 20 combined-item factories, 6 emblems (`emblems.py`, `granted_traits`, counted via T.28a) + Spirit-Gem `combine()` branch (`base.KINSHIP_OF`), 5 special run-actions (`special.py`, `RUN_ACTION_REGISTRY` on `Run`; Spirit Gem = 6th, inline in `combine()`) + `register_run_action` + `decompose()`, Heartwood `heartwood:` equip-scaling (`loadout._heartwood_scale`, D.21 MVP ×1.5), interactive `sim_run --interactive` prep shell, Spellfang Crown `ability_can_crit` (already in T.29a) | `game/items/{combined,emblems,special,base,recipes}.py`, `game/registries.py`, `game/loadout.py`, `tools/playtest/sim_run.py`, `docs/design/tasks/t29_item_engine_plan.md` | T.29a, T.28a | M | ✅ Done |
| T.29c | Mana primitive (builds the resolved plan §3.1a — T.29a shipped the item engine **without** it) — rename `ActiveSlot.cost`→`mana_cost`, add per-slot `max_mana` (default `2×`)/`start_mana`, `ABILITY_MANA` cost-meta on the ability def (+ `@register_active` mana kwargs), **drop the `ability_cost` stat** (amends V.34/V.35) + migrate 6 boss costs + 2 `999_999` sentinels onto ability defs, **weighted-rank charge cycle** + **≤1 cast/window unified-`priority`** in the engine, **retrofit the 3 T.29a cost-reducing mana items** (`springtear`/`deepwell`/`everbloom_staff` + `wildfury_lash` clamp) to grant `mana_regen`/`start_mana` not cut `mana_cost` (V.48, fixes B.21); **fix the `_on_cast` recorder no-op so registered casts emit a `cast` event** (V.50, fixes B.22 — casters were invisible); one determinism re-baseline | `game/piece.py`, `game/models.py`, `game/loadout.py`, `game/registries.py`, `game/combat/engine.py`, `game/combat/recorder.py`, `game/combat_log.py`, `game/content.py`, `game/scaling.py`, `game/bosses/data.py`, `game/abilities/champions.py`, `game/abilities/enemies.py`, `game/items/combined.py`, `docs/design/tasks/t29_item_engine_plan.md` | T.29a, T.33a | M | ✅ Done |
| T.29d | Multi-slot pieces + Multicaster showcase — `Champion`/`Enemy` `active_ability`→`active_abilities: list[str]` (+ legacy `from_dict` read, per-entry `ActiveSlot` build); new **`Multicaster`** Calling (breakpoints 2/3/4) + **`cast_momentum`** mechanic + `"Multicaster"` in `CALLING_TAGS`; **9 showcase pieces** — 6 champs gain the trait + a `.active2` secondary, 3 enemy casters gain a 2nd slot; author/verify primaries + 9 secondaries. **Convention discovery** (`content.discover_abilities`: `abilities=None` ⇒ auto-attach `{id}.active*`; explicit list overrides for bosses/null); **no `active_ability` singular** (read sites use `active_abilities`); distinct slots per piece (cost OR unique priority — no simul-cast); **Ultimate** secondaries for tier ≥ 5 (`marsh_thrush`/`tempest_eel`: 600k cost, priority ∝ cost, ~2× output); start-mana items split priority-weighted (slot-count-invariant) | `game/models.py`, `game/loadout.py`, `game/content.py`, `game/registries.py`, `game/items/combined.py`, `game/traits/callings.py`, `game/traits/mechanics.py`, `game/abilities/champions.py`, `game/abilities/enemies.py`, `game/encounter.py`, `game/bosses/data.py`, `tools/export_roster.py`, `tools/simulation/matchup.py`, `docs/design/tasks/t29_item_engine_plan.md` | T.29c, T.28a | L | ✅ Done |
| T.30 | Ability & passive catalog — implement all 120 roster ability/passive handlers (60 champions + 60 enemies) plus 6 full 2-phase boss kits; fix registration IDs, fix generic-fallback bias, add summon lifecycle primitives, add CI guard test for ability-id resolution | `game/abilities/champions.py`, `game/abilities/enemies.py`, `game/abilities/bosses.py`, `game/piece.py`, `game/combat/engine.py`, `docs/design/tasks/t30_ability_catalog_plan.md` | T.5, T.20, T.21, T.26 | L | ✅ Done |
| T.31 | Augment system — `Augment`/`AugmentScope`/`AugmentQuality` model + `@register_augment`; all ~50 catalog augments (4 qualities × 3 scopes `TEAM`/`PIECE`/`RUN`, incl. quest trackers); deterministic 1-of-3 offers + one reroll + Prismatic gating + per-stage quality-weight curve; `Run.active_augments`/`augment_state` (+ serialization, id-validation); `compile_loadout` augment-bundle application (step 6) + quest-tracker wiring (step 9); `RunModifiers` combat seam (optional, `None`-default back-compat); `sim_run` augment resolution — `--augment-policy {first,random,highest-quality,none}` + `--interactive` manual run; **+3 paired RUN-augments unlocking the Tier-10 Primordials in the late shop** (kinship pairs — Verdant/Tempest/Stoneveil; trait factories ship in T.28a, V.37); **6 Primordial @1 signature mechanics + @3 aspirational tier-up** (authored here — reachable once the 3 paired unlock augments exist; @3 needs a trait re-resolve/fixpoint pass — D.20) | `game/augments.py`, `game/loadout.py`, `game/models.py`, `game/combat/resolve.py`, `game/traits/`, `tools/playtest/sim_run.py`, `docs/design/tasks/t31_augment_system_plan.md` | T.20, T.22, T.26, T.28d, T.29b | L | ✅ Done |
| T.32 | Role system revamp — add 6th axis `intent` (damage/hybrid/utility); composer full-rework (every stat generated incl. `threat`/`move_speed`, dead per-unit `threat`/`move_speed`/`ability_cost` Def fields removed, `ability_cost`→constant); axis renames (`primary_stat`→`stat`, `range_`→`reach`, durability/speed middles→`hybrid`); replace flat `_ROLE_FROM_AXES` with 8-role `classify_role` + deterministic `role_code` (hybrid-stripped tag-set); `stat_overrides` scope=all-stats + key-validated + ordering after-tier-before-level; intent stat-bias under ±10% HP·DPS drift guard | `game/content.py`, `game/models.py`, `game/encounter.py`, `game/formation.py`, `tools/simulation/matchup.py`, `tools/playtest/`, `ui/`, `docs/design/tasks/t32_role_intent_revamp_plan.md`, `docs/design/tasks/t32_role_matrix.txt` | T.5, T.18, T.19, T.24, T.25 | M | ✅ Done |
| T.33a | Stat-scaling 3-class + #39 baseline parity + **fair total order** (fixes B.14, resolves #39, absorbs D.18): `PRIMARY`/`SECONDARY`/`FLAT` tuples + `PRIMARY_EXPONENT=0.5`/`SECONDARY_EXPONENT=0.0857`, `stat_multiplier(...,exponent)`; route the 4 scale loops + `_assert_budget` through tuples; **all speeds int**; new int `milli_AS=round(exact×1000)` (threaded level+weather); baseline parity (V.35): `mana_regen` 10→100, `move_speed` 90→100, `ability_cost` 36k→300k (~20% mage buff), boss costs ×10; new `Piece.load_order` (seeded side-independent permutation), rename `speed_tiebreaker→formation_index`, sort key `(-AS_int, -milli_AS, champion_id, load_order, kind)`; re-baseline snapshots/sims/mega7 | `game/scaling.py`, `game/content.py`, `game/encounter.py`, `game/piece.py`, `game/loadout.py`, `game/combat/engine.py`, `game/formation.py`, `game/bosses/data.py`, `game/abilities/bosses.py`, `tools/playtest/inspect.py`, `tests/game/test_scaling.py`, `docs/design/tasks/t33_speed_scaling_plan.md` | T.18, T.32 | L | ✅ Done |
| T.33b | Speed-axis diversity 3→7 (rides T.33a): expand `_SPEED` to 7 levels (+4 token names, wider `attack_speed`/`move_speed`/`primary_stat`/`resistance` spread); reassign 120-piece roster across them; `classify_role` unaffected (ignores `speed`); regen `t32_role_matrix.txt` 648→**1512** combos + update `test_role_intent.py`; amend V.32 cardinality | `game/content.py`, `docs/design/tasks/t32_role_matrix.txt`, `tests/game/test_role_intent.py` | T.33a | M | ✅ Done |
| T.34a | Ability description/tooltip metadata — champions — `AbilityMeta(name/blurb/terms[ScalingTerm]/clauses[Clause]/tags)` parallel registry; pure `render(meta, source)`→`RenderedAbility(name,text,formula,tags)` serving base-`Champion` (roster) + live-`Piece` (combat) via structural `.stat()`; `Champion.stat()` base-sheet adapter; source-of-truth B (champion handlers read headline numbers from terms, byte-identical sims); CI coverage guard + golden formula snapshot | `game/ability_text.py`, `game/registries.py`, `game/models.py`, `game/abilities/champions.py`, `tests/game/test_ability_text.py`, `docs/design/tasks/t34_ability_descriptions_plan.md` | T.20, T.30, T.32 | M | ✅ Done |
| T.34b | Ability description/tooltip metadata — enemies — 120 enemy `AbilityMeta`s + `Enemy.stat()` parity; enemy handlers read terms (byte-identical sims); V.38 guard + snapshot extended to all 240 champ+enemy ids | `game/abilities/enemies.py`, `game/models.py`, `tests/game/test_ability_text.py` | T.34a | M | ✅ Done |
| T.34c | Ability description/tooltip metadata — bosses — 36 boss `AbilityMeta`s (6 bosses × `phase1`/`phase2` active+passive + `phase1_phase_hook` + `on_death_hook`); boss handlers read terms (byte-identical sims); rendered against compiled boss `Piece`; V.38 guard + snapshot extended to all 276 roster ids | `game/abilities/bosses.py`, `tests/game/test_ability_text.py` | T.34a | M | ✅ Done |
| T.35a | Ability scaling uniformity (#42 Finding A) — promote `ScalingTerm` into a **closed `Magnitude` family** (`ScalingTerm` linear + `PctResource` + `MaxOfTerm` + `SetByCaller`, GAS-modeled) behind one `eval(source,target,caller)` Protocol; `Clause.template`+`terms` (A1, prose pulls live numbers); `ability_text.render` → pure per-kind dispatch (delete `ScalingTerm`-only branch); **A2 AST orphan-stat-read guard** + `_PROSE_ALLOWLIST`; relocate every Tier-B inline scaler into a `Magnitude` (byte-identical sims, V.2/V.14); `SummonSpec` for summon statlines; snapshot regen (text-only) | `game/registries.py`, `game/ability_text.py`, `game/abilities/champions.py`, `game/abilities/enemies.py`, `game/abilities/bosses.py`, `tests/game/test_ability_text.py`, `docs/design/tasks/t35_ability_scaling_uniformity_plan.md` | T.34a, T.34b, T.34c | M | ✅ Done |
| T.35b | Dead-stat balance (#42 Finding B) — re-tune `_DURABILITY` tanky STR/INT `0.55→0.42` + `_INTENT` damage `1.08→1.14`/utility `0.94→0.87` (proxy-verified `1.075`/`0.947`, V.33/V.33-band held) so a primary-stat tank no longer rivals an assassin's primary (Coral STR `92→65` vs Marten INT `127→134`, B.20); per-role INT coeffs on ~13 dead-INT carriers authored as `Magnitude`s (via T.35a); **axis↔scaling guard** (V.47). **Deterministic re-baseline, NO sim sweep** (balance sim-unvalidated by choice); regen stat/formula snapshots | `game/content.py`, `game/abilities/champions.py`, `game/abilities/enemies.py`, `tests/game/test_role_intent.py`, `tests/game/test_content.py`, `tests/game/test_scaling.py`, `tests/game/test_ability_text.py`, `docs/design/tasks/t35_ability_scaling_uniformity_plan.md` | T.35a | M | ✅ Done |
| T.36a | Primordial diversification — re-axis + kit-rewrite the **6 T10 kings** off uniform `hybrid/hybrid` into 6 distinct apex archetypes, **Calling-honest** (cast-Callings→`ability`, auto-Callings→`auto`): **Aurion** keeps hybrid/hybrid (*Ascendance* cast-ramp max 8 stacks), **Nerei** int/ability (*Grudge of the Flood* — `nerei_grudge` marker + `on_damage_pre` amp), **Borealis** hybrid/ability (Blizzard INT 2.28→2.7, frozen +15%), **Umbra** str/auto (every-5th-auto `STR·1.5`, no INT), **Mournhollow** str/ability (*Haunting Mist* + `grief` DoT `STR·0.4`/tick, parity coeff), **Aerion** hybrid/auto (every-3rd-auto chain + `attack_speed` steroid); **extend the V.47 guard to enforce `hybrid`→both STR+INT** (was INT-only, B.24) + dead-STR-hybrid detector test; fix stale `0.2·INT` comment (`test_content.py:363`→`0.25`); new `grief` DoT StatusDef + `nerei_grudge` marker; all kits deterministic (V.2/V.14), existing primitives only | `game/content.py`, `game/abilities/champions.py`, `game/status.py`, `tests/game/test_content.py`, `tests/game/test_role_intent.py`, `docs/design/tasks/t36_roster_stat_playstyle_rebalance_plan.md` | T.32, T.35a, T.35b | M | ✅ Done |
| T.36b | Champion roster axis-distribution rebalance (unified solve — plan §13/§14) — **optimize axis marginals directly** (role is a pure fn of axes, V.32; stop fighting two grids). Curated champion assignment hits target marginals (stat 22/22/16, playstyle 24/24/12, reach 30/30, **durability 11/8/13/28** [fixes the hybrid-35/arm-3 skew], intent ~26/22/12) + **soft role floors** (all ≥4) → **emergent roles** (tank 11 / support 11 / mage 9 / swash 6 / bruiser 6 / marksman 5 / assassin 4 / spellblade 4 / spellslinger 4); ~37 axis edits, **~15 new kit rebuilds** (beyond T.36a kings + 3 flip kits) by role-batch (bruiser=Bruiser-calling intent→damage; assassin=Stalker squishy playstyle→ability; spellslinger=auto+cast Callings; spellblade=dual-stat); **caster identities protected** (Menders/Mystics stay ranged+ability); `marsh_thrush` utility-INT/damage-STR; **new role `Spellslinger`** (amends V.32); soft **axis-marginal/distribution guard** (not §V); Kinship left as-is (animal-locked); snapshot + role-matrix regen + `stat_edge` champ read | `game/content.py`, `game/abilities/champions.py`, `tests/game/test_content.py`, `docs/design/tasks/t32_role_matrix.txt`, `tests/game/test_role_intent.py`, `docs/design/tasks/t36_roster_stat_playstyle_rebalance_plan.md` | T.36a | L | ✅ Done |
| T.36c | Enemy roster axis-distribution rebalance (same method — plan §13/§14) — apply the unified solve to the 60 enemies, **curated by name/lore** (opaque tags, V.22; no D.25 parity contract). Same target marginals + role floors → **emergent roles** (tank 12 / support 11 / spellblade 6 / bruiser 6 / mage 6 / swash 6 / marksman 5 / assassin 4 / spellslinger 4); fixes the same `durability` skew; ~28 axis edits, **~16 kit rebuilds** (bruiser fills from brutes [berserker/hulk/behemoth], spellslinger from battlemage-types, caster-named protected); snapshot + role-matrix regen + `stat_edge` full read. **Combined sweep DONE [2026-06-17]** (`results/stat_edge_t36c.csv` n=8000 + iterate `results/stat_edge_t36d.csv` n=1500): **zero champs over the \|wr_delta\|>0.10 contract bar.** 5-champ tune (`champions.py`): mournhollow nuke STR `1.0→0.8` + grief `0.4→0.3`; veilfang_wolf bonus INT `0.55→0.45` + haste `0.64→0.42`; ember_salamander nuke STR `1.95→1.65` + magma `1.2→1.0`; aurion nova INT `2.86→3.25` (buff); will_o_fawn lure INT `2.45→2.8` + passive INT `8→12` (buff). Post-tune extremes (n=1500, noisy): ember `+0.088` / mournhollow `+0.083` / veilfang `+0.083` / aurion `−0.060` / will_o_fawn `−0.018` — all ≤0.10, **44/60 inside ±0.05**. assassin-survival + Bruiser/Stalker apex retunes validated in-band. ±0.05 stretch deferred to the full random-vs-random power sim (re-baselines all). | `game/content.py`, `game/abilities/enemies.py`, `game/abilities/champions.py`, `tests/game/test_content.py`, `tests/game/ability_formulas.snapshot.json`, `docs/design/tasks/t32_role_matrix.txt`, `tests/game/test_role_intent.py`, `docs/design/tasks/t36_roster_stat_playstyle_rebalance_plan.md` | T.36b | L | ✅ Done |
| T.37a | Combat replay backend — event-stream completion + initial-board snapshot (combat-view prep, headless). Subscribe the already-fired hooks the recorder drops (`on_heal`/`on_spawn`/`on_status_applied`/`on_status_expired`) + add a new `on_despawn` from `expire_summon` ⇒ `heal`/`dot`/`status`/`spawn`/`despawn` beats, **one event per beat** (generalizes V.50); add `hp_after`/`barrier_after` to HP-changing `BattleEvent`s (exact HP/barrier bars from the result alone — handles V.28 barriers + DOT + heals + `grievous`); capture `BattleResult.initial_pieces` (`PieceSnapshot`: post-`assign_spawns` `(q,r)` + `is_enemy`/`affinity`/`max_hp`/mana profile) in `recorder.__init__` (positions already final there, both resolve paths) + `board_width`/`board_height`; `combat_log` renders the new beats; serialization round-trips (legacy results → empty defaults). Recorder observer-only ⇒ sims byte-identical (V.2/V.14), only `combat_log` golden re-baselines | `game/combat/recorder.py`, `game/combat/context.py`, `game/combat/engine.py`, `game/models.py`, `game/combat_log.py`, `tests/game/test_combat.py`, `tests/game/test_combat_log.py`, `docs/design/tasks/t37_combat_replay_backend_plan.md` | T.3, T.20, T.26 | M | ✅ Done |
| T.37b | Steppable engine + deterministic inspect-at-tick API (combat-view prep, headless). Refactor `engine.run`'s `for tick` loop into a drivable **stepper**; reimplement `resolve_combat`/`resolve_boss_combat` on it **byte-identically** (single entry preserved, V.2 — same loop body, no re-baseline); new pure UI-free `inspect_at_tick(team, enemies, weather, run_mods, tick) -> list[PieceView]` re-running the engine to `tick` on a **deep clone** of `run_mods` (mutable `augment_state` ⇒ zero caller side effects), returning read-only value structs (hp/barriers/per-slot mana/effective stats via `piece.stat()` incl. STR/AS ramp/statuses/position); raw `Piece`/Flet never escape `src/game/` | `game/combat/engine.py`, `game/combat/resolve.py`, `game/combat/replay.py`, `game/combat/__init__.py`, `tests/game/test_combat.py`, `tests/game/test_combat_replay.py`, `docs/design/tasks/t37_combat_replay_backend_plan.md` | T.37a | M | ✅ Done |

**Size**: S = <1h, M = 1-3h, L = 3-6h

### T.1 Planning Notes

- T.1 now includes non-combat node typing (`fight`, `reward`, `augment`, `boss_fight`) so route and UI flows can share one node contract.
- T.1 now includes combat runtime model surfaces needed by the combat proposal.
- T.1 now includes JSON-friendly serialization contracts to reduce risk for T.14 save/load.
- Detailed T.1 execution plan: `docs/design/tasks/t1_data_models_plan.md`
- Detailed model schema contracts: `docs/design/tasks/t1_model_contracts.md`

### T.2 Planning Notes

- Directed predator/prey ring of 5 active weathers (`Mist → Cloudy → Rain → Snow → Thunder`) + `Clear` outside, inert in both systems. Each weather's primary prey is the previous ring member, secondary prey the one before that; predators are the inverse.
- **Two decoupled systems**, evaluated separately, never summed:
  - **Weather Favor — node weather**: buffs/debuffs each piece by its affinity vs the node weather. 5 tiers — strong/medium/weak buff (self / primary predator / secondary predator) at `+10/+6/+3%`, medium/weak debuff (primary/secondary prey) at `−6/−3%`. Self is the strict maximum; no strong debuff. Applied once at combat init.
  - **Affinity Clash — affinity damage triangle**: per-hit multiplier on every damage instance by attacker affinity vs defender affinity — `1.20/1.10/1.00/0.90/0.80` for primary predator / secondary predator / mirror or Clear / secondary prey / primary prey. Resolved per hit in the combat engine.
- `Mist` Weather Favor debuff is the only flat-integer effect: base `attack_range -1` (min 1), which scales/rounds to `-1` at medium tier and `0` at weak tier.
- Detailed T.2 plan: `docs/design/tasks/t2_weather_effects_plan.md`.

### T.4 Planning Notes

- Route locked: 6 continent stages, 50 linear nodes, one distinct city per node;
  each stage carries an authored affinity (one per `WeatherState`).
- Detailed T.4 plan: `docs/design/tasks/t4_city_route_plan.md`.

### T.7 Planning Notes

- Cache state per city: `unknown` (initial), `live` (fetched ok + `fetched_at` age), `substitute` (fetch failed, holds `CITIES[city_id].default_weather`). Substitutes retry every tick; success flips to `live`.
- 3 streams per 1-min tick, dedupe order A→B→C: A = full RR over 50; B = RR over `[current+1..+6]` (count-clamped at trail end, modbus-style base+count, no wrap, no pad); C = uniform random over 50 (no freshness re-roll). A alone ⇒ ≤ 50 min staleness everywhere.
- Run init: alloc cache as 50× `unknown`, fire tick #1 sync (fetches nodes 0, 1, + 1 random), then start. Node 0 locks from tick-1 result.
- Lock semantics: on advance, snapshot cache entry into `Run`. Cache keeps refreshing same city (harmless). Engine reads `Run` for locked nodes, cache for unlocked.
- Advance-to-`unknown` = single sync fetch + lock; on fail, lock substitute. Rare path: tick beats player advance speed.
- No backoff on repeated fetch fails; streams keep firing at 3/min.
- UI age warnings (subtle top-right indicator when any `substitute` present or any `live` aged > 2h, hover lists affected cities) deferred — see D.17.
- Detailed plan: `docs/design/tasks/t7_cache_refresher_plan.md`.

### T.18-T.31 Planning Notes (Systems Expansion)

- T.18 power scalar `P = 2 ** ((T-1)/3 + triplings(L))`, `triplings = {L1:0, L2:1, L3:3}`
  (retuned from the original `1.5 ** ((T-1)/2 + (L-1))` — commits 7c9eb14/6acbd5c —
  to a `cbrt(2)` per-tier step + tripling level mechanic), drives encounter budgets and
  piece stat generation; "three tiers == one tripling step in power".
- T.19 generates encounters deterministically from `Run.seed` via per-node
  sub-seeds; squads/offers are regenerated lazily, not stored.
- T.20 builds the ability/passive/status framework (resolves D.3-D.5); bosses
  are its first consumer.
- T.21 layers spirit challenges and 2-phase bosses on the T.19 generator.
- T.22 implements the full economy loop: Amber income (+3 base/node, +1-3 win
  bonus, +interest 1/10 cap 5), shop (5 slots, auto-refresh per node, reroll =
  1 Amber, first free), buy/sell (`Cost(T) = T` / `floor(Cost/2)`), 3-copy
  leveling, Tempest team-size leveling (accelerating thresholds, free +2/fight,
  all-or-nothing Amber rush, max rank 10), and stage-gated tier probabilities.
  Also covers supply node resolution (1-of-5 free recruit). (Augment node
  resolution + the augment pool moved to T.31; T.22 stays a dependency.)
- T.23 makes Prep placement authoritative: board coordinates from Prep become
  combat init input; combat no longer overwrites player layout when a valid
  placement snapshot is provided.
- T.24 introduces deterministic enemy formation heuristics by role and team
  size, replacing index-only right-side packing while preserving replay
  determinism.
- T.25 adds deterministic balance simulation and matchup benchmarking over the
  existing auto-resolve engine for data-driven tuning. Ships three modes:
  full 1v1 (C(N,2) pairs), full 2v2 Cartesian (opt-in, ~25M pairs), and
  random team sampling (`team-sample`, default; optional tier-stratification).
  Per-piece win attribution is binary (every piece on the winning team scores
  1 vs every piece on the losing team; draws split 0.5). Win-rate analysis
  uses the deterministic power-threshold model (higher power wins 100%,
  equal power scores 50%).
- T.26 unified the two combat engines that briefly coexisted: legacy
  `resolve_combat` (T.3) and `compile_loadout + CombatContext + loop.run`
  (T.20). Post-T.26 there is **one** entry point — see V.2 and
  `docs/design/playtesting/engine_split.md` for the historical note.
- T.27 ships the dev-facing playtest CLI suite (`tools/playtest/`) used to
  exercise the engine before the Flet UI exists; pure consumer of
  `src/game/`. See `docs/design/playtesting/plan.md`.
- T.28 (split **T.28a/T.28b/T.28c**) implements synergy trait breakpoint effects on
  the T.20 substrate per the **v2.1** trait design (`trait_catalog.md`): apex =
  `min(pool,cap)`, single-step-leaning ladders + @1 entries, diversified low-HP
  mechanics (one revive). **T.28a** = framework + declarative stat-pack content +
  apex/dynamic-threshold infra + affinity synthesis + the Calling-vocabulary
  reconciliation (B.9) + the roster rebalance (one Tier-10 per kinship, Hunter
  spread, kinship pools). **T.28b** = combat primitives batch 1
  (untargetable/taunt/dodge/revive/second-wind-shield/tidal-HoT/ramp/enrage +
  **kiting** + backline-targeting — deterministic, no RNG; reuses the V.28
  barrier pool). **T.28c** = primitives batch 2 (echo/aura/splash/spawns/
  empowered-shot/weather-as-buff/Primordial-kits) + the apex effects + Packmate
  `@full-board`. Skyborn reworked to **kiting** (the rejected collision/tie idea
  is gone); Stalker @2 to backline-targeting (no teleport). Affinity traits are
  derived from `affinity`. Plan: `docs/design/tasks/t28_trait_effects_plan.md`.
- T.29 (split **T.29a/T.29b**) implements the item engine: components + combined
  items + 3-slot equip + REWARD/boss drops + 16-item core cut (T.29a), then the
  remaining 20 combined + emblems + special run-actions with an interactive
  `sim_run` driver (T.29b). Components map to **real** engine stats with
  **flat-add magnitudes** (mana handled per-`ActiveSlot`, not as a base stat —
  see B.10); emblems gate on T.28a. Loot rolls off the new `CH_LOOT = 8` channel:
  REWARD table 45/20/15/15/5 (component/combined/Amber/champion/special) + boss
  3-pair pick (D.12). **Shop sells champions only — items never enter the shop.**
  Heartwood = generic stat-mult for MVP (D.21).
  Content `docs/design/content/item_catalog.md`; substrate
  `docs/design/systems/effect_systems_design.md` §8; plan
  `docs/design/tasks/t29_item_engine_plan.md`.
- T.30 implements the full ability & passive catalog for all 120 roster pieces
  and 6 bosses. Key design decisions: round = 600 ticks (G8, convention only,
  no round abstraction); summons are full Piece objects (G6); auras use periodic
  radius re-application (Q4); coefficients are fixed authored values; boss kits
  are full 2-phase with phase-transition map effects (Q5). Also fixes the
  generic fallback formula (`max(STR, INT)` instead of INT-biased) and re-keys
  all ability registration IDs to match content roster prefixes.
- T.31 implements the full augment system on the T.20 effect substrate
  (`effect_systems_design.md` §9): `Augment` model with `TEAM`/`PIECE`/`RUN`
  scopes, all ~50 augments from `augment_catalog.md` across 4 qualities, and
  quest augments as `RUN`-scope + persistent cross-combat trackers. Augments are
  run-long (V.18) — picked at `AUGMENT` nodes, re-applied every combat via
  `compile_loadout`, threaded in through the optional `RunModifiers` seam (V.2).
  Sequenced **after** T.22/T.28/T.29 because most augment content reaches into
  economy/trait/item systems those tasks build. The `sim_run` CLI walks a
  complete run (headless `--augment-policy` + rudimentary interactive mode),
  groundwork the eventual Flet view fires. Detailed plan:
  `docs/design/tasks/t31_augment_system_plan.md`.
- T.32 revamps the archetype/role system: adds a 6th axis `intent`
  (damage/hybrid/utility), reworks `compose_stats` to generate **every** stat
  from the axes (killing the dead per-unit `threat`/`move_speed`/`ability_cost`
  passthrough — authored 0× in the roster), and replaces the flat
  `_ROLE_FROM_AXES[stat][reach]` map with an 8-role `classify_role` + a
  deterministic `role_code` descriptor (V.31/V.32/V.33). Intent authored from the
  roster archetype tags; threat now composed (tanks pull, casters sneak) with no
  7th axis. The 648-combo classifier matrix is enumerated + validated in
  `docs/design/tasks/t32_role_matrix.txt`. Plan:
  `docs/design/tasks/t32_role_intent_revamp_plan.md`.
- Detailed plans: `docs/design/tasks/t18_power_scaling_plan.md` through
  `docs/design/tasks/t25_power_simulation_plan.md`;
  `docs/design/playtesting/plan.md` covers T.27;
  `docs/design/tasks/t30_ability_catalog_plan.md` covers T.30.

## B. Bugs / Backprop

- B.1 `NodeType` extended with `SUPPLY` and `CHALLENGE` for the T.4 route
  vocabulary; `docs/design/tasks/t1_model_contracts.md` must be synced.
- B.2 `Reward` node redefined as an easy fight with guaranteed loot — it carries
  both `enemy_pool_id` and `reward_table_id`, not a pure non-combat node.
- B.3 Planned model additions: `CombatPieceState.active_statuses` (T.20) and
  `Run.content_version` (T.19) for procedural-run save stability.
- B.5 Weather rework (T.2 revision): `CombatPieceState` gains an `affinity:
  WeatherState` field — the combat engine needs per-piece affinity at damage
  time for Affinity Clash (target-dependent, cannot be pre-snapshotted). The shipped
  `combat.py` damage step gains an Affinity Clash multiplier hook; `apply_modifier` is
  renamed `apply_weather`. Touches `models.py`, `to_dict`/`from_dict`,
  `combat.py`, `t1_model_contracts.md`, `test_models.py`, `test_combat.py`.
- B.4 Currency named **Amber**, the team-size XP counter named **Tempest**
  (`1 Amber : 1 Tempest`). The `Run.gold` model field should be renamed
  `Run.amber` — touches `models.py`, `to_dict`/`from_dict`, `test_models.py`,
  and `t1_model_contracts.md`.
  **RESOLVED [2026-06-03] (T.22):** `Run.gold` → `Run.amber` (`from_dict` reads
  the legacy `gold` key for back-compat); `Run` also gained `tempest`,
  `tempest_rank`, `champion_copies`, `shop_offers`, `shop_rerolls`
  (+ validation + serialization). See V.19/V.20.

- B.6 Combat gains a **penetration** stat pair — `penetration` (flat) and
  `penetration_pct` (`[0.0, 1.0]`) on `Champion`, `Enemy`, and
  `CombatPieceState`. The attacker's penetration erodes the target's
  Armor/Resistance before mitigation (percent first, then flat, clamped at 0);
  `true` damage is unaffected. Default `0` — a build-around stat, not a base
  archetype stat, not power-scaled (`T18`). Touches `models.py`, `combat.py`,
  `weather_effects.py` (`apply_weather` copy-through), `combat_system_proposal.md`
  §4.2/§4.4, `t1_model_contracts.md`, `t3_combat_engine_plan.md`,
  `test_models.py`, `test_combat.py`.

- B.7 Route reworked to **one city per node** — ~50 real cities across 6
  continent stages (was 6 hub cities, one per stage). A stage carries an
  authored **affinity** (`StageDef.affinity`, one per `WeatherState`) used by its
  boss and challenge; each node/city carries its own live weather. The stage-1
  boss fight moved to Vienna. Supersedes the "~6 cities" content budget. Touches
  `t4_city_route_plan.md`, `boss_roster.md`, `CLAUDE.md`, and (when built)
  `route.py`.

- B.8 [2026-06-03] Sim weather columns (`own_weather_wr`, `counter_weather_wr`,
  `weather_sensitivity`) were dead — computed inside `aggregate_stats`, which
  `mega`/`runner` call once **per single-weather** ratings file, so
  `weather_sensitivity = max−min` over one value ≡ always `0.0` and own/counter
  were sparse-zero. **Cause:** a cross-weather metric derived from single-weather
  input. **Fix → V.16:** extracted `ratings.weather_metrics()` (single source of
  truth); `mega`/`runner` now pool per-weather win-rates and inject before
  writing. Tests: `test_ratings.py` (own/counter/sensitivity + single-weather→0).
  Note: the report's "weather inert" verdict was a *separate* analysis error —
  the cross-weather sweep measures only Weather Favor, never Affinity Clash
  (target-dependent, weather-independent); both must be measured separately.

- B.9 [2026-06-03] Calling-vocabulary drift: `CALLING_TAGS` (`content.py`) carried
  4 dead tags (`Bulwark/Drifter/Harbinger/Emissary`) introduced in the T.5 content
  commit — 0 carriers, referenced nowhere else, never present in any design doc —
  and omitted `Packmate` (the catalog's 12th Calling). **Cause:** the T.5 ad-hoc
  calling set was never reconciled with the later `trait_catalog.md` /
  `champion_roster.md` 12-Calling design. **Fix (T.28a):** drop the 4 dead tags,
  add `Packmate` + ~8 T1-3 carriers; **V.22** prevents recurrence.

- B.10 [2026-06-03] Item-doc drift: `effect_systems_design.md` §8.1 budgets "15
  combined" and §8.2/§8.3 use placeholder component ids + stat keys that don't
  exist in the engine (`ability_power`, `attack_damage`, `mana_max`); `item_catalog.md`
  §6 cites a non-existent "§14" for the 3-slot rule. **Cause:** the §8 sketch
  predates the 8-component/36-item `item_catalog.md` and the engine's real stat
  vocabulary. **Fix (T.29):** map components to real `Piece.base_stats` keys (mana
  handled per-`ActiveSlot`), annotate §8.1 → 36, and make
  `t29_item_engine_plan.md` §3.3 the 3-slot authority.

- B.11 [2026-06-03] DOT decay was mis-scaled to the engine tick: `poison`
  `decay_stacks_per_tick` removed one stack **every 10ms tick** while
  `duration_ticks` (400–500) was sized for the action clock — so a 4-stack
  poison drained in 4 ticks (~40ms, ~15 dmg), its `duration_ticks` was dead
  code, and poison sat ~40× weaker than `burn` (600+) with nothing visible at
  the call site. Separately, `StatusDef.dot_per_tick` was static on the shared
  def, so no caster could scale a DOT (every burn identical T1↔T10). **Cause:**
  DOT cadence + decay written as if 1 tick ≈ 1 turn, but a tick is ~600× finer
  than an action; intensity hard-coded on the shared def. **Fix → V.25/V.26:**
  data-driven `dot_interval_ticks` (1s default, `sudden_death` = 1),
  free-running per-instance DOT clock, `decay_stacks_per_dot`, per-instance
  `potency` with strongest-wins merge; magnitudes retuned to per-second. Touches
  `status.py`, `piece.py`, `loadout.py`, `combat/context.py`,
  `combat/engine.py`, `combat/loop.py`, `effect_systems_design.md`.

- B.12 [2026-06-03] `weather_metrics` zero-filled `own_weather_wr` /
  `counter_weather_wr` when a piece had no games in that weather — and `clear`
  affinity has no counter weather at all (NEUTRAL ring), so ~37% of mega7 rows
  carried `counter_weather_wr == 0.0` as if a real 0% win rate. Unweighted
  column-averaging in the report then manufactured a `+0.18` own-vs-counter
  weather swing (true effect ≈ `+0.01`) plus a spurious snow/thunder
  "inversion" (thin-slice noise on the same metric). **Cause:** missing data
  conflated with `0.0` at the metric source. **Fix → V.30:** `weather_metrics`
  emits `NaN` for no-data (genuine `0.0` preserved), `report.py` writes an empty
  CSV cell, aggregators skip NA / recompute from raw per-weather win rates.
  Touches `tools/simulation/ratings.py`, `tools/simulation/report.py`,
  `tests/tools/simulation/test_ratings.py`, `reviews/mega_sim/11_mega7.R`,
  `reviews/mega7_analysis_report.md`.

- B.13 [2026-06-04] Axis-count drift: `t5_content_plan.md` documents "**4
  orthogonal axes**" but `content.py` ships **5** (`speed` was added after the
  T.5 plan, never back-propagated to the doc), and the legacy
  `_ROLE_FROM_AXES[primary_stat][range_]` derived `role` from **only 2 of the 5**
  axes — so durability/playstyle/speed never reached the role title and a
  damage-bruiser was indistinguishable from a peeling support. **Cause:** the
  composer grew axes the design doc + role map never tracked. **Fix → V.31/V.32/V.33
  (T.32):** add the 6th axis `intent`, reconcile docs+code to 6, replace the flat
  map with a 6-axis `classify_role`, and guard intent/axis presence + the
  pure-function role derivation so the count can't silently drift again. Touches
  `game/content.py`, `game/models.py`, `t5_content_plan.md`,
  `t32_role_intent_revamp_plan.md`.
- B.14 [2026-06-05] Side-A deterministic win on equal-AS ties. **Cause:**
  `resolve_combat` builds pieces team-block-then-enemy-block (`compile_loadout(team,
  enemies, …)`) and sets `piece.speed_tiebreaker = index` in that order
  (`resolve.py`); `_event_sort_key` orders same-tick actions by `(-AS, -AS,
  speed_tiebreaker, kind)` (`engine.py`). Speeds were **flat** across
  tiers/levels (`attack_speed`/`move_speed`/`mana_regen` excluded from every scale
  loop), so equal-AS ties were the **common** case → every team piece (indices
  `0..N-1`) outranks every enemy piece (`N..2N-1`) → team acts and kills first. A
  byte-identical mirror matchup is **100% side-A win**, not a draw — biasing every
  prior sim/report (mega7 etc.); `tools/simulation/weather_impact.py` needed
  `--both-sides` to cancel it (mirrors then read `0.000`/`50%`). **Fix → V.34
  (T.33a):** the bias lived in the *tiebreak*, not the speed — `_event_sort_key`
  becomes the canonical side-independent total order `(-AS_int, -milli_AS,
  champion_id, load_order, kind)`, where `load_order` is a seeded permutation
  (never team-block-then-enemy). Every tie — cross-power *and* true-mirror — now
  resolves fairly; **D.18 absorbed (no longer deferred).** Touches
  `game/combat/engine.py`, `game/combat/resolve.py`, `game/piece.py`,
  `game/loadout.py`, `game/scaling.py`, `game/content.py`, `game/encounter.py`.
- B.15 [2026-06-08] Hexproof (then `untargetable`) leaked through single-target
  abilities. **Cause:** T.28b added `StatusGate.UNTARGETABLE` + the engine
  auto-attack filter (`engine.py:99`), but the `game/targeting.py` single-target
  acquisition helpers (T.20, predating the gate) filtered only fog — so *targeted*
  casts (`primary_target`/`lowest_hp_enemy`/`highest_ap_enemy`/`random_enemy`/
  `furthest_enemy` → `_closest_enemy`) still picked untargetable pieces,
  contradicting the intended "can't be targeted" semantics. AoE was (correctly)
  unaffected. **Fix → V.40 (T.28d):** rename to `hexproof`; add the gate filter to
  the single-target helpers (AoE/untargeted unchanged — MTG-hexproof model);
  `Piece.pierces_hexproof` bypass (Spirit @8). **Guard:** V.40 +
  `tests/game/test_hexproof.py` (auto / single-target / AoE / pierce cases).
  Touches `game/status.py`, `game/targeting.py`, `game/piece.py`,
  `game/combat/engine.py`, `game/traits/`.
- B.16 [2026-06-08] Cumulative-rung mechanic drops across the trait ladders.
  **Cause:** `_resolve_traits` (`game/traits/__init__.py`) applies only the single
  highest cleared `TraitBreakpoint`'s bundle (stats authored as per-rung totals,
  replace-not-stack), so a mechanic rider persists only if **every** higher rung
  manually re-lists it. Four didn't — Skyborn `kiting` (armed only @2), Skyborn
  `kite_reward` (only @3, added in T.28d), Spirit `hexproof_opener` (dropped @8),
  Primordial `second_wind` (dropped @3) — silently lost at higher trait counts.
  Caught by the new V.41 guard during T.28d review. **Fix → V.41 (T.28d):**
  re-include each rider up its ladder — carrier-movement omitted only at a
  `TEAM_WIDE` apex; signature riders carrier-guarded via `trait=` rather than
  dropped. **Guard:** V.41 +
  `tests/game/test_traits.py::test_trait_rungs_are_cumulative_for_mechanics`.
  Touches `game/traits/{kinships,callings,mechanics}.py`.
- B.17 [2026-06-13] Boss map-effect (environmental) damage crashed `deal_damage`
  ([#40](https://github.com/Meduty/tempest-fauna-trail/issues/40)). **Cause:**
  hazard tiles / map effects deal attacker-less damage (`map_effects.py:258`
  `deal_damage(None, piece, …)`), but `context.deal_damage` dereferenced
  `attacker.affinity` (`:221`) and `attacker.ability_can_crit` (`:229`), and the
  recorder dereferenced `event.attacker.id` (`recorder.py:156`) — all unguarded,
  while sibling sites already handle `None` (`kill(killer=None)`,
  `recorder.py:162`). Latent: no test drove a boss fight through
  `resolve_boss_combat` with an active hazard map effect. Caught while adding a
  boss determinism harness for T.34. **Fix (T.34):** treat attacker-less damage
  as environmental — skip affinity clash + crit when `attacker is None`; count it
  as *taken* but attributed to no dealer. Behavior-preserving for all
  attacker-bearing paths (sims byte-identical). **Guard:**
  `tests/game/test_environmental_damage.py`. Touches `game/combat/context.py`,
  `game/combat/recorder.py`.
- B.18 [2026-06-13] `attack_speed` muls desynced cadence from tie-order. **Cause:**
  `attack_speed` (cadence) and `milli_AS` (the sub-integer sort field) were two
  separate stats; an ability `Modifier("attack_speed","mul",…)`
  (`champions.py:207`) moved cadence but **not** `milli_AS`, so the canonical
  `_event_sort_key` (V.34) ordered the piece by its **pre-buff** speed. Only
  weather (`loadout.py:198`) and traits (`traits/_packs.py:41`,
  `traits/mechanics.py:93,114`) manually rode `milli_AS` alongside the AS mul to
  stay synced; every other AS mul drifted. Deterministic but wrong ordering on
  same-tick ties. Caught while designing the T.29-pre stat substrate. **Fix → V.34
  (T.29-pre):** make `attack_speed` a **float** and **delete `milli_AS`** (and its
  weather/trait rider modifiers) — the tiebreak `round(attack_speed×1000)` derives
  from the **same** value cadence reads (`int(attack_speed)`), so any AS mul moves
  both together. **Deterministic re-baseline, NOT byte-identical:** the old int
  `attack_speed` (stored `round`-ed) and `milli_AS` were independent fields that
  could be mutually inconsistent; unifying them into one float makes cadence
  truncate (`int(float)`) where it used to round, shifting some fight timing by
  ≤1 tick (damage/structure unchanged) — verified even in clear weather. Same seed
  → identical output (V.2 holds); all combat snapshots re-baselined once. No save
  migration (no legacy saves; `from_dict` reads the float directly). Touches
  `game/models.py`, `game/content.py`, `game/scaling.py`, `game/encounter.py`,
  `game/loadout.py`, `game/combat/engine.py`, `game/traits/_packs.py`,
  `game/traits/mechanics.py`.
- B.19 [2026-06-14] Tier-B inline scalers invisible + free-prose drift
  ([#42](https://github.com/Meduty/tempest-fauna-trail/issues/42) Finding A). **Cause:**
  T.34 hoisted only **headline** damage/heal numbers into `ScalingTerm`s; every other
  stat-scaled outlet (armor/res buffs `enemies.py:1249-1250`, barriers, `max(STR,INT)`
  `enemies.py:966,2124`, %-of-max-HP heals, summon fractions) stayed **free inline math**
  described by a hand-written `Clause` — so `formula` under-reported scaling and the prose
  `"40%"` could silently diverge from the handler `*0.4`. A class of drift V.38 did not
  cover (headline-only). **Fix → V.46 (T.35a):** a **closed `Magnitude` family** (GAS-modeled)
  every handler reads; renderer dispatches per-kind; A2 AST guard (`test_no_orphan_stat_reads`)
  fails the build on any uncovered stat-read. Byte-identical (V.2/V.14). Touches
  `game/registries.py`, `game/ability_text.py`, `game/abilities/{champions,enemies,bosses}.py`.
- B.20 [2026-06-14] Primary-stat tanks rival assassins; dead INT
  ([#42](https://github.com/Meduty/tempest-fauna-trail/issues/42) Finding B). **Cause:**
  durability's STR/INT penalty was sized without accounting for the `stat`-axis bonus —
  `_PRIMARY_STAT["str"]=1.8 × _DURABILITY["tanky_hp"]["strength"]=0.55 ≈ 0.99 ≈` a bruiser's
  `1.0` (`content.py:34,77`), so a `stat="str"` tank kept ~full primary scaling (Coral Colossus
  STR `92` vs Duskstep Marten INT `127`, gap only `35` at T5). Separately, `stat="int"`/`hybrid`
  units carried INT-heavy statlines whose kits never read INT (dead stat), nothing tied the
  `stat` axis to the kit. **Fix → V.33 re-tune + V.47 (T.35b):** `_DURABILITY` tanky STR/INT
  `0.55→0.42` + `_INTENT` damage/utility widened (proxy band held, `1.075`/`0.947`) → Coral
  `65` / Marten `134` (gap `69`); per-role INT coeffs on ~13 dead carriers; axis↔scaling guard
  (`TestAxisScalingAlignment::test_int_and_hybrid_units_reference_int`). **Deterministic re-baseline; balance NOT sim-validated this
  pass** (by choice). Touches `game/content.py`, `game/abilities/{champions,enemies}.py`.
- B.21 [2026-06-14] T.29a mana items **reduced `mana_cost`** (negative-cost stacking).
  **Cause:** PR #41 (Copilot) authored `springtear`/`deepwell`/`everbloom_staff` against the
  **pre-§3.1a** mana model — `_apply_mana_to_slots(..., cost_mult<1.0)` did `slot.cost *= 0.9/0.8`
  (`items/combined.py:69`), the exact stacking exploit the reworked design forbids; `springtear`
  (the item V.48 cites as the canonical *pure-`mana_regen`* item) was a cost-cutter. **Cause root:**
  T.29a shipped before the §3.1a tensions resolved, so the items targeted a model that no longer
  exists. **Fix → V.48 (T.29c):** mana items grant `mana_regen` (Modifier) or `start_mana` (slot),
  **never** `mana_cost`; deleted the `cost_mult` path, reclamp grants to `max_mana`. Guard:
  `test_items.py` asserts `mana_cost` unchanged + a `mana_regen` modifier present. Touches
  `game/items/combined.py`.
- B.22 [2026-06-14] **Registered ability casts were invisible** — casters looked like a dead class.
  **Cause:** `BattleResultRecorder._on_cast` was a `pass` stub (`recorder.py:173`), so casts firing
  through `process_casts → ctx.cast_ability` (which fires `on_cast`) produced **no `cast` event**;
  only the unregistered-fallback path called `record_cast`. A 12 061-tick fight where Coral Colossus
  actually cast **5×** logged **0** casts → sims/metrics/turn-counts undercounted casts to zero,
  hiding a whole class. **Fix → V.50 (T.29c):** implement `_on_cast` to append one `cast` event
  (amount 0, note `ability_id`; damage attributed via `_on_damage_dealt`); `combat_log` renders a
  clean activation line. Guard: V.50 + `test_combat`/sim show casts. Touches `game/combat/recorder.py`,
  `game/combat_log.py`.
- B.23 [2026-06-15] **T.29a item procs mis-scaled / overtuned** (Copilot, PR #41) — evaluated
  against measured combat (autos ~5 s, casts 25–50 s, HP 600–1500, dmg 50–200). **Causes:**
  (a) `bramble_carapace` retaliate `INT×0.35` on an **armor item → tanks (INT≈6)** = ~2 dmg, and
  the catalog's "cut attacker healing" was dropped; (b) `witherbloom_censer` burn = flat `40`, 1.5 s
  (one tick, non-scaling), heal-cut dropped; (c) `mistward_shroud` `1.5%/s` self-regen ≈ out-healed
  auto DPS (near-unkillable); (d) `mammoth_hide` regen gated on "no damage 2 s" → erratic. **Pattern:**
  Copilot's **% stat mods were fine** (scale with tier); the misses were all **flat or wrong-stat
  procs** (same class as the flat 200 start-mana, T.29c). **Fix (T.29a rebalance):** bramble → flat 80
  thorns + `grievous`; witherbloom → burn 3 s + RES sunder + `grievous`; mistward → 1%/s self;
  mammoth → ungated 2%/2 s self+adjacent team aura. Added the `grievous` antiheal primitive (V.51),
  one soft-CC item (`splitwind_talons` Slow), two support effects (`living_bulwark` armor aura,
  `deepwell` ally shield). **Guard:** judge every item proc against the combat-scale baseline, and
  scale procs on a stat the holder actually has. Touches `game/items/combined.py`, `game/status.py`,
  `game/combat/context.py`. **Still open:** INT ability coeffs ≪ intended (casts should be big nukes,
  hybrids currently cast < auto) — a dedicated balance pass, see §D.
- B.24 [2026-06-16] **V.47 guard under-enforced — checked INT only, never verified `hybrid`→STR.**
  **Cause:** the T.35b guard `TestAxisScalingAlignment::test_int_and_hybrid_units_reference_int` used a
  single `_meta_references_int` predicate — it satisfied a `hybrid` piece on its INT reference alone and
  never checked STR, so a hybrid statline (1.0 STR weight) whose kit reads only INT had a **dead STR
  half** the guard couldn't see. Latent since T.35b; load-bearing once T.36 adds `hybrid/auto` +
  `hybrid/ability` pieces whose whole point is both-coeff scaling. **Fix → V.47 (T.36a):** extend the
  guard to require `stat="hybrid"` reference **both** STR and INT (`_meta_references_str` + hybrid
  branch) + a `test_guard_detects_a_dead_str_hybrid` detector mirroring the dead-INT test. Touches
  `tests/game/test_content.py`.
- B.25 [2026-06-22] **`slow` status was a no-op dead marker — soft CC did nothing.** **Cause:** the
  `slow` StatusDef (`status.py`) carries no gate and no DOT, and **no engine code read it** to throttle
  speed — yet it was applied by map slow-tiles (`engine.py:721`, `map_effects.py`), 5+ boss abilities
  (`abilities/bosses.py`), enemy abilities (`abilities/enemies.py`), Frostbound/chill traits
  (`traits/mechanics.py:511,671`), and frost items (`items/combined.py:547,560`). Every one silently
  did nothing. Surfaced building T.31 Living World's SNOW boon (the team debuff was inert). **Fix →
  V.53 (T.31):** the engine meter loop multiplies action+movement gain by `_slow_factor(piece)` =
  `max(0.40, 1 − 0.15·stacks)` (`engine.py`), applied to meter *gain* not `piece.stat(...)` so
  tiebreak/AS reads stay clean; RNG-free (V.2/V.14). Guard `test_combat.py::test_slow_factor_scales_with_stacks_and_floors`
  + `test_slow_changes_combat_outcome_end_to_end`. Touches `game/combat/engine.py`, `tests/game/test_combat.py`.
- B.26 [2026-06-22] **Summon despawn was invisible — `expire_summon` fired no event.** **Cause:** `ctx.expire_summon` (`context.py:485`, called from `engine.py:860`) ends a summon's life (drops `alive`, decrements the O(1) liveness count) **without** firing any bus event — asymmetric vs `spawn`'s `on_spawn`. A combat-view animator could never learn an expired summon (turret/echo) left the board, so it would render a dead piece forever. Surfaced auditing the recorder for combat-view readiness (T.37). **Fix → V.54 (T.37a):** `expire_summon` fires a new `on_despawn`; the recorder emits a `despawn` `BattleEvent` distinct from `death` (fade vs death-anim). Guard: V.54 + the stream-completeness test. Touches `game/combat/context.py`, `game/combat/engine.py`, `game/combat/recorder.py`.
- B.27 [2026-06-22] **HP-changing beats (DOT ticks, heals) were absent from the event stream → bars can't reconstruct.** **Cause:** `BattleResultRecorder` recorded only `attack`/`cast`/`death` as discrete `BattleEvent`s + tracked damage/heal **totals**; DOT-tick damage and `ctx.heal` changed `piece.hp` but emitted no event. Combined with V.28 barriers (`deal_damage` fires the **full pre-barrier** `amount` for DPS accounting while HP drops by the post-barrier `to_hp`, `context.py:272`), any HP-by-subtraction reconstruction in a view would **drift and over-count**. Surfaced in the combat-view readiness audit (T.37). **Fix → V.54 (T.37a):** emit `heal`/`dot` beats + stamp `hp_after`/`barrier_after` = engine truth on every HP-changing event, so HP/barrier bars reconstruct from `BattleResult` alone. Guard: V.54 + a barrier-case test asserting `amount ≠ HP-delta` but `hp_after` is exact. Touches `game/combat/recorder.py`, `tests/game/test_combat.py`.
- B.28 [2026-06-22] **Combat-view HP/mana bars would freeze through registered-ability damage, and the forward stepper the T.37b plan promised was never built.** **Cause (two drifts):** (a) **code** — `t37_combat_replay_backend_plan.md:89/97` specified *"the view holds one stepped instance and reads `PieceView`s as it advances"* (a resumable forward `step()`/generator), but `replay.py` shipped only `inspect_at_tick`, which **re-runs from `on_combat_start` every call** (`engine.run(stop_after_tick=N)` is not resumable, `engine.py:808`) ⇒ stepping a fight is O(N²) and there is no live-advance API; (b) **plan** — the later `t12_combat_view_plan.md` (§3.2:96, §3.6:133) abandoned the live-advance model and had bars **reconstruct from the recorded stream** (`hp_after`), "NO re-sim". That reconstruction is impossible: registered-ability burst damage emits no `hp_after` beat (`_on_cast` ⇒ `amount=0`/`hp_after=-1`, `recorder.py:279-288`; `_on_damage_dealt` emits only on `tag==dot`, `recorder.py:244`), so a stream-built HP bar holds stale through every ability hit until the next basic-attack/DOT/death/heal touches the piece. Two sources of truth for per-tick resources — the partial event-stream fields vs the authoritative live replay — and the view never needed the stream for numbers. Surfaced reviewing the T.12 plan for weak spots before build; user recalled the live-advance design and traced it to the T.37b plan doc. **Fix → V.55/V.56/V.57 (T.37c, T.12a):** build the resumable forward `CombatReplay` stepper the T.37b plan intended (`game/combat/replay.py`); the view drives it **forward** for Next/autoplay (O(total ticks), live state ⇒ every HP change correct incl. ability burst) and uses `inspect_at_tick` for back-scrub/random seek; the recorded stream is reframed as **animation cues + action-queue projection only** (V.57). V.54's "bars reconstruct from `BattleResult` alone" overclaim softened (`hp_after` = telemetry, not bar source). Also: the `move` beat's `note=f"{q},{r}"` string (`recorder.py:180`) hardened to structured `dest_q`/`dest_r` int fields (T.37c). Guard: V.57 + a test that a registered-ability-burst fight's stepper HP matches `inspect_at_tick` at every event tick (and ≠ a stream-`hp_after` reconstruction). Touches `game/combat/replay.py`, `game/combat/engine.py`, `game/models.py`, `game/combat/recorder.py`, `game/combat_log.py`, `ui/views/combat.py`, `ui/combat_playback.py`. **RESOLVED [2026-06-22] (T.37c):** built the forward `CombatReplay` stepper (single `_step_combat` generator, `run` drains / `CombatReplay` steps, V.29) + `inspect_at_tick` unified onto it; `move`/`spawn` beats carry structured `dest_q`/`dest_r`. Guard test `test_forward_stepper_hp_complete_through_ability_burst` confirms stream-only HP diverges from live. Sims byte-identical (1227 tests pass). The view-side reframe (stream = cues only) lands with T.12a. **Cosmetic remainder closed [2026-06-23] (T.37 follow-up):** `_on_damage_dealt` now emits an `ability` beat per ability hit (final post-mitigation `amount` + `damage_type` + `is_crit` + `hp_after`, `DamageEvent.damage_type` added) so ability-damage floating numbers render + the stream is HP-complete; bars still read the live stepper (V.57). `turns` excludes `ability` ⇒ sims byte-identical (V.54).
- B.29 [2026-06-23] **`damage_type="magic"` hits mitigated by armor, not resistance.** **Cause:** `deal_damage`'s mitigation switch is an exact match — `if damage_type == "magical": resistance else: armor` (`context.py:252`). Three enemy handlers passed the typo-variant `"magic"` (`abilities/enemies.py` — Warded Edge passive, Runed Thrust, Sigil Strike), which **no** code path matches, so they fell into the `else` (armor) branch — wrong mitigation, wrong balance, **silent** (no validation). Invisible until the new `ability` beat (T.37) surfaced `damage_type` on the event stream (`{"magic","magical","physical"}` seen). **Fix → V.58 (T.37 follow-up):** correct the 3 handlers `"magic"→"magical"`; `deal_damage` now **validates** `damage_type` against the closed `{physical, magical, true}` vocabulary and raises `ValueError` on anything else (recurrence-proof). Combat-math change ⇒ those enemies now mitigate via **resistance** ⇒ **determinism re-baseline** (sim sweeps + `ability_formulas`/`combat_log` goldens for any fight containing them). Touches `game/abilities/enemies.py`, `game/combat/context.py`, `tests/game/`.

## D. Systems Yet To Be Determined

Live backlog of big design decisions still open. Items now locked are recorded
in their T-task plan docs; what remains here is genuinely undecided.

### Route & Encounters

- D.1 Route branching: the linear 6-stage / 50-node chain is **locked** (T.4);
  whether optional branch/merge paths are added post-MVP is open.
- D.2 Boss content: authored per-boss kits (phase 1 + phase 2 abilities, on-death
  hooks) **designed in T.21** — `game/bosses/data.py`. Ability *implementation*
  (handler functions) **completed in T.30** — `game/abilities/bosses.py` contains
  full 2-phase kits for all 6 bosses with phase-transition hooks at 50% HP.
- D.3 Combat board-cell modifiers: **designed and implemented in T.21** —
  `game/board.py` (BoardState + CellModifier), `game/map_effects.py` (6 effect
  classes), `game/combat/loop.py` (_process_board_state), `game/targeting.py`
  (fog filter). Remaining: per-ability content that writes to board_state.

### Combat Systems

- D.5 Ability / passive / status framework: **designed in T.20**; per-champion
  ability and passive *content* (kits) **implemented in T.30** — all 120 roster
  pieces + 6 bosses now have authored handlers with fixed coefficients.
- D.6 Combat timeout policy: keep hard draw only or add sudden-death escalation.
- D.7 HP carryover: **LOCKED — full reset per fight.** Champions heal to full HP
  between nodes. Simplifies economy tuning and avoids snowball/frustration; the
  challenge comes from enemy scaling and weather variance, not attrition.
- D.18 Side-independent **residual** tiebreak. **RESOLVED [2026-06-05] (T.33a) →
  V.34:** folded into the canonical total order — the new `load_order` field is a
  deterministic side-independent permutation (not team-block-then-enemy), so even
  exact-build mirrors resolve fairly (winner = fn of identity+seed, not "player
  side"). No longer a separate residual concern.
- D.19 Speed-stat comparability (GitHub #39): `mana_regen` baseline `10` read as
  incomparable next to `attack_speed=100`/`move_speed=90`. **RESOLVED [2026-06-05]
  (T.33) → V.35:** all three speed-stat baselines lifted to `100`; per-meter
  capacitors deliberately unequal (mana `ability_cost=300_000` ≫ `ENERGY_THRESHOLD`)
  and non-player-facing — comparability lives at the baseline. Plan:
  `docs/design/tasks/t33_speed_scaling_plan.md`.
- D.23 Movement-event ordering by move-speed (the MS phase-split) — **deferred
  (T.29-pre).** Today `_event_sort_key` orders **all** triggered events (both
  movement and action) on `attack_speed`; `kind` is the last tiebreak (separating
  only a single piece's own move-before-act). So `move_speed` controls movement
  **frequency** (meter fill) but **never order**, and has no sub-integer field. A
  symmetric design — float `move_speed`, split resolution into a move-phase
  (ordered by `round(MS×1000)`) then an action-phase (ordered by `round(AS×1000)`),
  dropping the `kind` tiebreak — is cleaner but changes combat **semantics** (global
  reposition-then-act each tick → same-tick range/contest outcomes shift). Needs its
  own task + win-rate validation; **not** bundled into the T.29-pre representational
  refactor. (T.29-pre, B.9 of the plan)

### Content

- D.8 Synergy traits: V.8 reserves `Champion.traits` as auto-chess synergy tags.
  **Design complete (v2.1); implementation planned as T.28a/T.28b/T.28c**
  (`docs/design/tasks/t28_trait_effects_plan.md`) — breakpoint *concepts* in
  `docs/design/content/trait_catalog.md`, substrate in
  `docs/design/systems/effect_systems_design.md` §7, breakpoint **stat values
  authored in the plan (first pass)**. Open: breakpoint-value tuning, the Tier-B
  fidelity pass (Skyborn collision/tie + Stalker reposition ship as MVP proxies),
  and two-Kinship hybrids.
- D.9 Item system: **LOCKED — design in `docs/design/content/item_catalog.md`,
  implementation planned as T.29a/T.29b** (`docs/design/tasks/t29_item_engine_plan.md`).
  8 base components, 36 combined items via `RECIPE_MAP` (16-item core cut in
  T.29a, rest in T.29b), 6 emblems (Spirit Gem + component → Kinship; counted via
  T.28a), 6 special `RUN_ACTION_REGISTRY` items. 3 item slots per champion piece.
  **Magnitudes [resolved 2026-06-10]: flat add** (TFT-style — Fang +10 STR, Old Hide
  +100 HP, Keen Claw +0.15 crit, Springtear ±30_000 mana per-slot; items favour
  early/mid game by design). **Acquisition [resolved 2026-06-10]: REWARD/boss drops
  only — the shop sells champions ONLY, never items** (T.22 contract, do not
  extend); T.31 grant augments may award specials (emblems, Glimmerdust) as a bonus
  channel. **Heartwood [resolved 2026-06-10]: generic ×1.5 stat-mult for MVP** —
  authored per-item variants deferred (D.21). Open: flat-value tuning via sim.
- D.10 Champion / enemy archetypes: the ~6-8 role archetypes and their `P = 1`
  base stats, enemy power tags, and the spirit roster (T.5 / T.18). **Role-taxonomy
  half RESOLVED [2026-06-04] (T.32):** 6 archetype axes (`stat`/`reach`/`durability`/
  `playstyle`/`speed`/`intent`) compose all stats; an 8-role `classify_role` +
  `role_code` descriptor derive identity deterministically (V.31/V.32/V.33). **Durability/intent
  STR/INT re-tuned [2026-06-14] (T.35b, B.20)** — tanks no longer rival assassins on primary;
  dead-INT carriers gained per-role INT coeffs (V.47). **Caveat: the T.35b re-tune + coeffs are
  deterministic but NOT sim-validated this pass (by choice — "fix without sims").** Open: a
  `tools/simulation/` win-rate pass to refine the first-pass numbers; the **squishy-durability
  buff** (`1.25→1.35`) as a further offense lever (T.35b touched tanky + intent only); per-archetype
  `P=1` base-stat tuning + enemy power tags.
- D.11 Augment content: augment pool, 4 quality tiers, 3 scopes, and per-augment
  effects **owned by T.31** (substrate `effect_systems_design.md` §9, content
  `augment_catalog.md`, plan `t31_augment_system_plan.md`). Open tuning only: the
  per-stage quality-weight curve and a degenerate-combo (interaction-cap) audit.
- D.12 Drop tables: **RESOLVED [2026-06-10] (T.29a plan)** — T.22 never authored
  weights, so T.29a owns them. First-pass table (tunable): **45% component / 20%
  combined item / 15% Amber (+2) / 15% champion recruit (SUPPLY tier-pool logic) /
  5% special item** (falls back to component until T.29b ships). Seed-deterministic
  via new `CH_LOOT = 8` channel (`generate_reward_loot`, pure — returns
  `RewardLoot`, no `Run` mutation). **Boss defeat = 3-pair pick**: 3 pairs of 2
  drops rolled off the boss node's `CH_LOOT` seed (`generate_boss_loot`, len-3,
  deterministic); player picks one pair, headless sims take pair 0. Details:
  `docs/design/tasks/t29_item_engine_plan.md` §3.7.
- D.20 Primordial @1 signature mechanics + @3 tier-up **deferred to T.31**. The 6
  Tier-10 legendaries already carry full `.active`+`.passive` kits (T.30); the
  catalog's "@1 signature mechanic" (`trait_catalog.md:176`) is **un-authored**
  net-new design and **unreachable until T.31's 3 paired unlock augments** exist,
  so it cannot be tuned in T.28d. @3 ("team's highest *other* trait counts one tier
  higher") additionally needs a trait **re-resolve/fixpoint pass** in
  `compile_loadout` and is double-dormant (3 Primordials, all augment-gated; catalog
  flags it "aspirational … not balanced content"). Primordial @1 ships as its stat
  pack (`game/traits/callings.py`); T.31 authors the 6 signatures + @3 alongside the
  unlock augments. (Moved out of T.28d per the T.30-kit finding — see
  `docs/design/tasks/t28d_trait_apex_hexproof_plan.md` §1.)
- D.21 Authored Heartwood (radiant) item variants — **post-MVP**. MVP (T.29b)
  ships Glimmerdust as a **generic ×1.5 stat-mult** on the item's modifiers (proc
  untouched, one code path). Per-item authored Heartwood versions (boosted procs,
  bespoke stats) are future content; revisit after the base 36 prove out. (T.29)
- D.22 Bosses wearing items — **post-MVP**. Standard enemies carry no items;
  T.30 boss kits were authored + sim-tuned **without** items, so giving bosses
  1-2 authored items changes boss difficulty and needs a sim retune pass first.
  Boss *loot* (the D.12 3-pair pick) is separate and ships in T.29a. (T.29, T.30)
- D.23 Delist overpopulated existing Callings — **deferred from T.29d**. Adding
  `Multicaster` was kept purely additive; trimming over-used Callings is a separate
  vocab/V-guard reconciliation + breakpoint rebalance. Revisit when the Calling
  roster is next rebalanced. (T.29d)
- D.24 Expand multi-slot beyond the 9 showcase pieces — **post-MVP**. Once the
  V.48 rank cycle / one-cast gate prove out, more champs/enemies can gain 2nd (and
  3rd) abilities as content; sized as a content pass, not engine work. (T.29d)
- D.25 **RESOLVED [2026-06-15] — STR/INT *damage* parity reached; the residual is a SUPPORT-balance
  artifact, not a damage-coeff issue.** Levers: auto INT `0.2→0.25`; INT ability coeffs ×1.58 cumulative
  (global); **STR ability ×0.8**; then a final **damage-only** INT ×1.2 (only `ScalingTerm("damage",…)`
  intelligence coeffs — leaves heals/shields/haste/on-hit-burst untouched). **Key finding (intent slice):
  among `intent=damage` pieces the axes are at parity — str +0.029 / int −0.010 / hybrid −0.003** (n=4000,
  pre damage-only bump; the bump lifts the 4 lagging int-ability-*damage* casters that sat at −0.037). The
  alarming "int −0.021 by-stat" was **dragged down by the 14 INT *utility* pieces (−0.025)** crowding the
  int/ability cell (18 = 14 utility + 4 damage) — a **support-value** question (see D.26), which the
  damage lever can't and shouldn't touch. So INT-as-damage-coeff is fair (math: auto is `1·STR + 0.25·INT`
  → INT ability coeffs run ~3–5× STR's and stay fair); the headline deficit is support balance. (resolved
  via `tools/simulation/stat_edge.py`, intent-sliced) **CONSUMED [2026-06-16] by T.36** — the tuned
  coeff equilibrium (auto `1·STR+0.25·INT`; STR carriers ~7× INT auto DPS/pt; str/ability discount
  `coeff_str ≈ coeff_int − 0.667·autos_per_cast`) is now **spent** in the redesigned kits (T.36a/b);
  the lever work is closed. **Post-T.36 validation [2026-06-17] — reframe:** the residual STR-ability
  vs INT-ability `wr_delta` gap (`+0.035`, full n=8000 sweep) is **STR-ability OVER-budget** (free
  auto-tagalong: auto `1·STR+0.25·INT`), **not INT-ability under** — INT-ability (n13) sits AT budget
  (`≈0.000`); STR-ability (n7) sits `+0.034`. So the parity lever is trimming the STR-ability auto
  subsidy / per-champ STR-ability trims (done for mournhollow/ember in T.36c), **NOT** a further global
  INT bump (the orig D.25 framing). Confirms "lever work closed" — no global INT raise warranted. (T.36c)
- D.26 **INT utility/support pieces sit ~−0.025 wr_delta** (the 14 int/ability/utility champs — healers,
  shielders, debuffers). Surfaced while resolving D.25 (intent slice). **Not a damage-coeff issue** —
  it's whether support *value* (healing/shielding/CC) pays its power budget. `stat_edge` measures
  damage-budget conversion, so it can't judge this; needs a support-aware metric (e.g. ally-survival /
  damage-prevented vs power). Low priority — supports being slightly under their *raw-WR* budget is
  partly expected (their value is teamwide, not self-WR). Revisit with a survivability sim. (post D.25)
- D.25 (orig) **Cast-power balance pass — INT ability coeffs ≪ intended.** Design intent
  (2026-06-15): casts are rare (every 25–50 s) so each should be a **big INT nuke,
  INT coeff ≫ STR/autos**. Measured today: pure INT casters land ~3–7× their auto
  (mirage 6.6×, 302 dmg), but **hybrids cast *weaker* than they auto** (aurion 0.7×)
  and absolute cast values are low; ability `ScalingTerm` INT coeffs sit at ~1.8–2.5.
  Fix = a dedicated pass raising INT damage coeffs across the ~120 ability handlers
  (and re-checking auto's `0.2·INT`), **sim-validated** — too large + balance-sensitive
  to bundle into the item work. Interlocks with the value of mana items (springtear/
  deepwell/everbloom) which only pay off if casts hit hard. (post T.29c)
  **Evidence (`tools/simulation/stat_edge.py`, team sims 3v3, tier-stratified, n=4000
  clear):** grouping champions by stat×playstyle and reading `wr_delta` (win_rate −
  power-expected, tier-controlled). **INT under-performs its power budget in every
  playstyle; STR over-performs:** by stat **STR +0.024 / INT −0.034** (gap +0.058);
  matrix **auto STR +0.044 vs INT −0.029** (gap +0.073), **ability STR +0.053 vs INT
  −0.038** (gap +0.091). Same playstyle, swap STR→INT ≈ **7–9pp** win-rate drop —
  because the universal auto is `1.0·STR + 0.2·INT` (STR gets 5× the auto value). So
  **STR-as-coeff is strictly stronger than INT-as-coeff** (autos tag along free) → INT
  needs ~+0.06 wr_delta to reach parity. **First iteration APPLIED (2026-06-15, commit
  ceca46e):** (1) engine auto INT term `0.2·INT → 0.25·INT`; (2) all ability
  `intelligence*K` coeffs ×1.2 (per-term, not a global damage scale — STR coeffs/bases/
  hybrid expressions untouched). **Iter 2 (7f7f34d):** ability `strength*K` ×0.8 +
  `intelligence*K` ×1.2 again (cumulative INT ×1.44, STR ability ×0.8) — targets the
  ability-layer gap (post-iter1 ability STR +0.039 vs INT −0.036). Multisize (2-5v5,
  n=3000) post-iter1 read INT by-stat −0.030; iter-2 directional → −0.016 by-stat,
  ability marginal −0.014 (near par). **Still open:** confirm on a big multisize sweep;
  residual printed "ability gap" is the n=3 ability-STR sample (noisy), not a real
  deficit. The per-term coeffs are the tuning surface for any further nudge. Classification fix landed
  (2026-06-15): `classify_role` no longer forces INT⇒caster, and 9 INT auto-carriers
  were re-axised (`glade_heron` + 4 full-converts → auto, 3 → hybrid) so the auto-INT
  archetype is representable + measurable (currently ~−0.03 wr_delta). (post T.29c/T.29d)

### Economy & Meta

- D.13 Champion economy: **LOCKED — implemented in T.22.** Amber sources: +3
  base per node, +1-3 bonus on win (seed-deterministic), REWARD-node loot.
  Sinks: buy champion `Cost(T) = T` Amber, shop reroll = 1 Amber (first reroll
  each node is free), Tempest buy-up (`1 Amber : 1 Tempest`). Sell value:
  `floor(Cost / 2)` Amber per copy. Leveling: 3 copies → L2, 9 → L3
  (`Run.champion_copies`). **Interest [revised T.22]:** TFT-style +1 Amber per
  10 banked, cap +5 (computed on Amber held *before* node income) — supersedes
  the original "interest: none", added to deepen the save-vs-spend choice.
- D.14 Team-size cap: **LOCKED — implemented in T.22.** `Tempest` counter (the
  XP analogue) — start at rank `1` (field 1 + 2 bench = team-size 3), `+2`
  Tempest per fight (challenge clears +1 more). Rank-up thresholds are an
  **accelerating** curve (rank `N→N+1`): `1→2:2, 2→3:4, 3→4:6, 4→5:10, 5→6:14,
  6→7:18, 7→8:24, 8→9:30, 9→10:36`; reaching a threshold auto-ranks and overflow
  carries. Over ~38 combat nodes, free `+2`/fight tops out ~rank 7-8; ranks 9-10
  need the Amber rush (`1 Amber : 1 Tempest`, full remaining cost only,
  all-or-nothing). Max rank **10** (field cap == `tempest_rank`). [Was "max rank
  6"; corrected — shipped T.21 `CHALLENGE_TEAM_SIZE` stage-6 = 11 at design's
  `cap+1`/final`+2` implies cap ~10; code beat the spec.]
- D.15 Shop: **LOCKED — implemented in T.22.** Lives in the Prep view. 5 champion
  slots, auto-refreshed each node entry (free). Manual reroll costs 1 Amber; the
  first reroll each node is free (counter resets every node advance). Stage-gated
  tier probabilities: stage 1 sees Tier 1-2 only; stage 6 widens to Tier 1-9 with
  higher-tier weight. **Buyable ceiling is T9** — T10 Primordials stay boss-only,
  so "Tier 1-10" reads as "up to the buyable max T9". Probability table authored
  in `docs/design/tasks/t22_meta_progression_plan.md` and `shop.STAGE_TIER_WEIGHTS`.

### UI / Flow

- D.16 View/route drift: **RESOLVED.** Canonical routes are `/`, `/trail`,
  `/prep`, `/combat`, `/summary` — matching `views_spec.md`. The legacy
  `/recruit` and `/map` routes are retired; initial champion pick is handled
  inline during run-start (first Prep node). `views_spec.md` §11 node-type set
  updated to match `NodeType` enum (`fight`, `reward`, `augment`, `supply`,
  `challenge`, `boss_fight`). **T.12 note:** the `/combat` view ships first behind a
  dev harness (`TEMPEST_DEV=1`) ahead of T.15 routing — same view, later fed by the
  real Prep/Trail `Start Combat` producer (V.56). **T.12b note:** `/combat` also
  renders **boss** nodes (map-effect overlay), dev-launched via the harness BOSS
  type ahead of T.15.
- D.17 Cache health UX: warn indicator surface when any node is `substitute`
  or any `live` weather aged > 2h; hover shows affected cities; smart
  failsafe copy when many nodes degraded. Polish layer over T.7 cache states.

## Implementation Order

### Current Status & Next Steps

LIVING snapshot — refresh via `/spec` whenever a §T status flips. Last: 2026-06-10, post-T.28d merge (`84a4829`).

**Done (✅):** T.1-T.8, T.14, T.16, T.18-T.22, T.24-T.28d, T.30, T.32, T.33a/b — engine, weather, route+content, economy/shop, full trait chain, ability catalog, role/scaling revamps, save/load, playtest CLI. Backend headless-complete **except items + augments**. T.17 docs 🔶.

**WIP:** none — T.28d merged, tree clean. (Update this line when a task starts.)

**Next — backend chain, in order:**
1. ~~**T.29-pre** combat stat substrate — weather→`source:`-tagged modifiers (V.42), `compute_stat` single-fold + resource resync (V.43), anti-runaway snapshot (V.44), `source:` prefix vocab + `stat_breakdown` (V.45); `attack_speed`→float, drop `milli_AS` (amends V.34, B.18).~~ ✅ Done
2. ~~**T.29a** item engine core — components, 16-item cut, 3-slot equip, REWARD drops.~~ ✅ Done
3. ~~**T.29b** items rest — remaining 20 combined + 6 emblems + 6 special run-actions + interactive `sim_run` driver.~~ ✅ Done
4. ~~**T.29c** mana primitive — resolved §3.1a (`cost`→`mana_cost`, per-slot `max_mana`/`start_mana`, `ABILITY_MANA` on ability def, drop `ability_cost`, weighted-rank charge cycle + ≤1 cast/window; retrofit 3 T.29a cost-cut mana items to V.48).~~ ✅ Done
5. ~~**T.29d** multi-slot + Multicaster — `active_abilities: list` + convention discovery, `Multicaster` Calling + `cast_momentum`, 9 showcase pieces (6 champs + 3 enemies; T6 ults), distinct-slot rule, priority-weighted start-mana.~~ ✅ Done
6. **T.31** augments — ~50 catalog, `RunModifiers` seam, `sim_run` augment policies; carries 3 paired Primordial-unlock RUN-augments + Primordial @1 signatures + @3 tier-up (D.20).

**Then — UI phase:** T.9 → T.10 → T.15 → T.23 → **T.37a → T.37b → T.37c → T.12a → T.12b**; viz T.11/T.13; polish T.34a/b/c (ability tooltips) → **T.35a (Magnitude family) → T.35b (dead-stat balance)** + T.17.

**Independent now (post-T.34, no UI dep):** T.35a (#42 Finding A — Magnitude-family refactor, byte-identical) can run any time after T.34c; T.35b (#42 Finding B — balance re-tune) after T.35a. **T.36a (kings) → T.36b (champion roster rebalance) → T.36c (enemy roster rebalance)** run after T.35b — pure content/classification re-axis + kit rewrites; no UI/engine dep (new `Spellslinger` role + V.47-guard extension only). The unified axis-distribution solve (role derives from axes, V.32 — plan §13/§14) fixes the durability skew + populates all roles; combined ~66 axis edits / ~39 kit rebuilds across both rosters, split kings/champions/enemies so each ships green independently (enemies last — sims run champ-vs-enemy).

### Phase 1: Core Logic (Week 1-3)
T.1 → T.2 → T.3 → T.4 → T.18 → T.5 → T.19 → T.20 → T.21 → T.24 → T.26 → T.16 (game tests) → T.27 (playtest CLI)

### Phase 1b: Economy & Content Systems (Week 3-4) ← NEW critical path
T.22 (economy + shop) → T.28a → T.28b → T.28c → T.28d (traits) → T.29-pre (combat stat substrate: weather→modifiers, AS→float/drop milli_AS) → T.29a → T.29b (items) → T.29c (mana primitive: cost→mana_cost, drop ability_cost, charge cycle) → T.29d (multi-slot + Multicaster) → T.31 (augments)
T.32 (role/intent revamp) — slots after T.5; independent of the trait/item/augment chain (refactors content + classification only)
T.33a (3-class scaling + #39 baseline parity + fair total order) → T.33b (speed axis 3→7) — slot after T.32; touch the same scaling/composer code. T.33a fixes B.14 via the side-independent `load_order` total order (absorbs D.18). Re-baselines every stat/sim snapshot, so run before further sim-driven tuning.

### Phase 2: API + Data (Week 2-3)
T.6 → T.7 → T.16 (API tests)

### Phase 3: UI + Combat (Week 4-6)
T.8 → T.9 → T.10 → T.15 → T.23 → T.37a → T.37b → T.37c → T.12a → T.12b

### Phase 4: Visualizations (Week 6-7)
T.11 → T.13

### Phase 5: Polish + Docs (Week 7-8)
T.14 → T.17 → T.34a → T.34b → T.34c → T.35a (Magnitude family, #42 Finding A) → T.35b (dead-stat balance, #42 Finding B)

## Content Inspiration

### Weather States

Weather Favor stat packs per weather (the strong-tier `±10%` base; `combat_modifier`
scales the deviation by tier — see `docs/design/tasks/t2_weather_effects_plan.md`):

| State | OW IDs | Buff stats (self / predators) | Debuff stats (prey) |
|---|---|---|---|
| `CLEAR` | 800 | — (inert) | — (inert) |
| `CLOUDY` | 801-804 | `HP`, `RES` | `AS` |
| `MIST` | 701-781 | `MS`, `THR` | `attack_range -1` (min 1) |
| `SNOW` | 600-622 | `Armor`, `RES` | `MS` |
| `RAIN` | 300-321 + 500-531 | `AS`, `MR` | `STR` |
| `THUNDER` | 200-232 | `STR`, `AS` | `INT`, `MR` |

Directed predator/prey ring: `Mist → Cloudy → Rain → Snow → Thunder → Mist`.
Each weather preys on the previous ring members (primary = prev, secondary =
prev-prev). Weather Favor buffs self + predators, debuffs prey (§T.2 notes). Affinity Clash
multiplies every hit by the attacker-vs-defender ring relation. `Clear` is
outside the ring — inert in both systems. Full matrices in
`docs/design/tasks/t2_weather_effects_plan.md`.

> **Terminology**: `affinity` is the piece's single weather alignment (one of the 6 `WeatherState` values). `traits` are open-ended auto-chess synergy tags (e.g. `Hunter`, `Mammal`, `Reptile`, `Guardian`) — multiple per champion, used for team synergies. Do not confuse the two; weather logic only consumes `affinity`.

### Champions examples
| Name | Affinity | Synergy Traits | Role | Base ATK | Base HP |
|---|---|---|---|---|---|
| Blaze Fox | Clear | Mammal, Hunter | Attacker | 18 | 80 |
| Ember Salamander | Clear | Reptile, Mystic | Glass cannon | 22 | 60 |
| Drift Yak | Cloudy | Mammal, Guardian | Bruiser | 14 | 115 |
| Haze Owl | Mist | Bird, Mystic | Scout | 15 | 70 |
| Frost Wolf | Snow | Mammal, Hunter | Attacker | 17 | 85 |
| Tundra Bear | Snow | Mammal, Guardian | Bruiser | 15 | 110 |
| Tide Otter | Rain | Mammal, Mystic | Tank | 12 | 120 |
| Storm Eagle | Thunder | Bird, Hunter | Attacker | 16 | 75 |

T.5 expands this to a full roster of ~60 (1 champion per affinity × 10 tiers).

### Cities & route

The route is **6 continent stages, ~50 nodes, one distinct real city per node**
(`docs/design/tasks/t4_city_route_plan.md`). Each stage has an authored
**affinity** used by its boss/challenge encounters; each node/city carries its
own **live weather**. Boss cities, one per stage:

| Stage | Continent | Affinity | Boss city |
|---|---|---|---|
| 1 | Europe | Clear | Vienna |
| 2 | Africa | Mist | Cairo |
| 3 | Asia | Thunder | Tokyo |
| 4 | Oceania | Cloudy | Sydney |
| 5 | South America | Rain | Rio de Janeiro |
| 6 | North America | Snow | New York (grand boss) |

### Enemy Types examples
| Type | Base ATK | Base HP | Affinity |
|---|---|---|---|
| Frost Drone | 12 | 60 | Snow |
| Smog Bot | 14 | 70 | Cloudy |
| Heat Mech | 16 | 65 | Clear |
| Monsoon Walker | 13 | 80 | Rain |
| Storm Sentinel | 15 | 75 | Thunder |
