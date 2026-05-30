# T.30 — Ability & Passive Catalog

**Date:** 2026-05-30

## Why

T.20 built the ability/passive/status framework (event bus, registries,
`EffectBundle`, `Modifier`, status gates). T.21 designed boss kits and wired
phase hooks. But until T.30, only a handful of reference abilities existed —
the 120-piece roster and 6 bosses ran on the generic fallback formula, making
combat outcomes homogeneous. T.30 gives every piece a unique mechanical
identity: authored coefficients, distinct ability shapes (AoE, heal, burn,
summon, buff/debuff, aura), and boss phase transitions that change the fight
mid-combat.

## Key Decisions

1. **Round semantics (G8 amendment).** "Round" = 600 ticks by convention only.
   All periodic passives use `on_tick` hooks with a `last_fired` timestamp and
   `>= 600` guard. No `on_round_start` event was introduced.

2. **Aura modeling (Q4 amendment).** Signal Drummer, Standard Bearer, and
   similar radius buffers use **periodic re-scan** (`on_tick` every 300 ticks):
   scan radius, apply a short-duration `TIMED` modifier to in-range pieces.
   Pieces leaving the radius naturally lose the buff when the modifier expires.
   No persistent `WHILE_CONDITION` primitive needed.

3. **Summon scope (G6 amendment).** Umbra's shadow summon and Steam Engineer's
   turret spawn as real `Piece` objects with `summon=True`,
   `summon_owner_id`, and `summon_expires_tick`. The tick loop despawns expired
   summons by setting `alive=False` and `hp=0` (pieces remain in `ctx._pieces`
   but are treated as dead). This keeps summons first-class: they
   can be targeted, take damage, trigger events.

4. **Generic fallback fix.** The old formula `0.2*STR + 4.2*INT` was biased
   toward INT scalers. Replaced with `4.4 * max(STR, INT)` — neutral between
   physical and magical. All existing tests updated (84→88 damage).

5. **Registration ID re-key.** Old IDs used short names (`dawnwisp.active`);
   content.py generates IDs with `champ_` / `enemy_` prefixes. All handlers
   re-keyed to match, e.g. `champ_dawnwisp.active`.

6. **Shield / knockback / invulnerability approximation.** Without dedicated
   shield HP pools or displacement systems, these are modeled via temporary
   stat modifiers (large armor buffs for shield/invuln, stun for knockback).
   Sufficient for auto-resolve; a future task can add explicit shield pools.

7. **Boss kits (Q5 amendment).** All 6 bosses have full 2-phase kits:
   phase 1 active + passive, a phase hook at 50% HP that swaps the active slot
   and registers phase 2 passives, phase 2 active + passive, and an on-death
   cleanup hook. Phase hooks fire `PhaseEvent(new_phase=2)` on the event bus.

8. **Coefficients are authored.** Each ability has hand-tuned base damage /
   scaling strings (e.g. `"strength*1.8"`, `"intelligence*2.2"`). These
   approximately follow the design guidelines (~4.4× stat at tier 1) but are
   individually calibrated for role and ability shape.

## Deviations from Plan

- Plan §6 suggested a `shared_factories.py` module for common patterns (burn
  applicator, heal-over-time, etc.). Instead, patterns are inlined per-handler
  since the factory abstraction added indirection without meaningful DRY gains
  — most abilities differ in enough details to not benefit.

- Plan §11 mentioned a `test_coefficients.py` sanity-checking coefficient
  magnitude ranges. Deferred — the authored values are intentionally diverse
  and a blanket bounds-check would need too many exceptions to be useful.

- Plan §12 suggested updating the power simulation to validate T.30 balance.
  Deferred to a follow-up playtest session (the sim already works with the new
  abilities, just needs re-running).

## File Summary

| File | Change |
|------|--------|
| `src/game/abilities/champions.py` | Complete rewrite: 60 champion active+passive handlers |
| `src/game/abilities/enemies.py` | New: 60 enemy active+passive handlers |
| `src/game/abilities/bosses.py` | New: 6 boss full 2-phase kits |
| `src/game/abilities/__init__.py` | Import trigger for new modules |
| `src/game/piece.py` | Added `summon`, `summon_owner_id`, `summon_expires_tick` fields |
| `src/game/combat/loop_new.py` | Fixed generic fallback + summon expiry logic |
| `tests/game/test_ability_catalog.py` | 16 new tests (CI guard, smoke, scaling, boss, summon) |
| `tests/game/test_combat.py` | Updated fallback damage assertion |
| `tests/game/test_combat_log.py` | Updated fallback damage text |
| `SPEC.md` | §T.30 row, §V.15 invariant, §D.2/D.5 amendments |

## Follow-ups

- Re-run power simulation (`tools/simulation/`) to check balance with real kits
- Implement shield HP pool if playtesting shows armor-buff approximation is
  insufficient
- Board displacement system for knockback (currently modeled as stun)
- T.28 (synergy traits) and T.29 (items) will add multiplicative effects on
  top of these kits

## Full Implemented Ability Table (as of T.30)

### Champions (60)

| Piece ID | Name | Active Ability ID | Passive Ability ID |
|---|---|---|---|
| `champ_aegis_tortoise` | Aegis Tortoise | `champ_aegis_tortoise.active` | `champ_aegis_tortoise.passive` |
| `champ_aerion` | Aerion, the Skybreaker | `champ_aerion.active` | `champ_aerion.passive` |
| `champ_aurion` | Aurion, the First Dawn | `champ_aurion.active` | `champ_aurion.passive` |
| `champ_borealis` | Borealis, the Pale Aurora | `champ_borealis.active` | `champ_borealis.passive` |
| `champ_boulderhide_skink` | Boulderhide Skink | `champ_boulderhide_skink.active` | `champ_boulderhide_skink.passive` |
| `champ_cliffeyrie_eagle` | Cliffeyrie Eagle | `champ_cliffeyrie_eagle.active` | `champ_cliffeyrie_eagle.passive` |
| `champ_coppercrest_stork` | Coppercrest Stork | `champ_coppercrest_stork.active` | `champ_coppercrest_stork.passive` |
| `champ_coral_colossus` | Coral Colossus | `champ_coral_colossus.active` | `champ_coral_colossus.passive` |
| `champ_dawnwisp` | Dawnwisp | `champ_dawnwisp.active` | `champ_dawnwisp.passive` |
| `champ_dusk_bat` | Dusk Bat | `champ_dusk_bat.active` | `champ_dusk_bat.passive` |
| `champ_duskstep_marten` | Duskstep Marten | `champ_duskstep_marten.active` | `champ_duskstep_marten.passive` |
| `champ_eclipse_jaguar` | Eclipse Jaguar | `champ_eclipse_jaguar.active` | `champ_eclipse_jaguar.passive` |
| `champ_ember_salamander` | Ember Salamander | `champ_ember_salamander.active` | `champ_ember_salamander.passive` |
| `champ_fogveil_moth` | Fogveil Moth | `champ_fogveil_moth.active` | `champ_fogveil_moth.passive` |
| `champ_frostfang_wolverine` | Frostfang Wolverine | `champ_frostfang_wolverine.active` | `champ_frostfang_wolverine.passive` |
| `champ_frostplate_tortoise` | Frostplate Tortoise | `champ_frostplate_tortoise.active` | `champ_frostplate_tortoise.passive` |
| `champ_frostquill_porcupine` | Frostquill Porcupine | `champ_frostquill_porcupine.active` | `champ_frostquill_porcupine.passive` |
| `champ_geode_beetle` | Geode Beetle | `champ_geode_beetle.active` | `champ_geode_beetle.passive` |
| `champ_glacierback_mammoth` | Glacierback Mammoth | `champ_glacierback_mammoth.active` | `champ_glacierback_mammoth.passive` |
| `champ_glade_heron` | Glade Heron | `champ_glade_heron.active` | `champ_glade_heron.passive` |
| `champ_goldcrest_lark` | Goldcrest Lark | `champ_goldcrest_lark.active` | `champ_goldcrest_lark.passive` |
| `champ_goldhide_rhino` | Goldhide Rhino | `champ_goldhide_rhino.active` | `champ_goldhide_rhino.passive` |
| `champ_granite_gorilla` | Granite Gorilla | `champ_granite_gorilla.active` | `champ_granite_gorilla.passive` |
| `champ_grovekeeper_tapir` | Grovekeeper Tapir | `champ_grovekeeper_tapir.active` | `champ_grovekeeper_tapir.passive` |
| `champ_hoarfrost_owl` | Hoarfrost Owl | `champ_hoarfrost_owl.active` | `champ_hoarfrost_owl.passive` |
| `champ_hollow_elk` | Hollow Elk | `champ_hollow_elk.active` | `champ_hollow_elk.passive` |
| `champ_iceclaw_lynx` | Iceclaw Lynx | `champ_iceclaw_lynx.active` | `champ_iceclaw_lynx.passive` |
| `champ_lostlight_wisp` | Lostlight Wisp | `champ_lostlight_wisp.active` | `champ_lostlight_wisp.passive` |
| `champ_marsh_thrush` | Marsh Thrush | `champ_marsh_thrush.active` | `champ_marsh_thrush.passive` |
| `champ_marshghast_boar` | Marshghast Boar | `champ_marshghast_boar.active` | `champ_marshghast_boar.passive` |
| `champ_mirage_caracal` | Mirage Caracal | `champ_mirage_caracal.active` | `champ_mirage_caracal.passive` |
| `champ_mirewarden_toad` | Mirewarden Toad | `champ_mirewarden_toad.active` | `champ_mirewarden_toad.passive` |
| `champ_mournhollow` | Mournhollow, the Pale Stag | `champ_mournhollow.active` | `champ_mournhollow.passive` |
| `champ_nerei` | Nerei, the Floodmother | `champ_nerei.active` | `champ_nerei.passive` |
| `champ_nightglass_mantis` | Nightglass Mantis | `champ_nightglass_mantis.active` | `champ_nightglass_mantis.passive` |
| `champ_pebbleback_pangolin` | Pebbleback Pangolin | `champ_pebbleback_pangolin.active` | `champ_pebbleback_pangolin.passive` |
| `champ_permafrost_walrus` | Permafrost Walrus | `champ_permafrost_walrus.active` | `champ_permafrost_walrus.passive` |
| `champ_phantom_lynx` | Phantom Lynx | `champ_phantom_lynx.active` | `champ_phantom_lynx.passive` |
| `champ_reedbank_otter` | Reedbank Otter | `champ_reedbank_otter.active` | `champ_reedbank_otter.passive` |
| `champ_riptide_caiman` | Riptide Caiman | `champ_riptide_caiman.active` | `champ_riptide_caiman.passive` |
| `champ_snowpelt_cub` | Snowpelt Cub | `champ_snowpelt_cub.active` | `champ_snowpelt_cub.passive` |
| `champ_sparkfly` | Sparkfly | `champ_sparkfly.active` | `champ_sparkfly.passive` |
| `champ_spectral_heron` | Spectral Heron | `champ_spectral_heron.active` | `champ_spectral_heron.passive` |
| `champ_springfrog` | Springfrog | `champ_springfrog.active` | `champ_springfrog.passive` |
| `champ_storm_eagle` | Storm Eagle | `champ_storm_eagle.active` | `champ_storm_eagle.passive` |
| `champ_sunmane_lion` | Sunmane Lion | `champ_sunmane_lion.active` | `champ_sunmane_lion.passive` |
| `champ_sunspear_falcon` | Sunspear Falcon | `champ_sunspear_falcon.active` | `champ_sunspear_falcon.passive` |
| `champ_tempest_eel` | Tempest Eel | `champ_tempest_eel.active` | `champ_tempest_eel.passive` |
| `champ_thunderclap_gorilla` | Thunderclap Gorilla | `champ_thunderclap_gorilla.active` | `champ_thunderclap_gorilla.passive` |
| `champ_thunderhide_bison` | Thunderhide Bison | `champ_thunderhide_bison.active` | `champ_thunderhide_bison.passive` |
| `champ_thunderhoof_colt` | Thunderhoof Colt | `champ_thunderhoof_colt.active` | `champ_thunderhoof_colt.passive` |
| `champ_torrent_heron` | Torrent Heron | `champ_torrent_heron.active` | `champ_torrent_heron.passive` |
| `champ_umbra` | Umbra, the Mountain's Shadow | `champ_umbra.active` | `champ_umbra.passive` |
| `champ_veilfang_wolf` | Veilfang Wolf | `champ_veilfang_wolf.active` | `champ_veilfang_wolf.passive` |
| `champ_veldt_pronghorn` | Veldt Pronghorn | `champ_veldt_pronghorn.active` | `champ_veldt_pronghorn.passive` |
| `champ_voltmane_jackal` | Voltmane Jackal | `champ_voltmane_jackal.active` | `champ_voltmane_jackal.passive` |
| `champ_voltscale_mamba` | Voltscale Mamba | `champ_voltscale_mamba.active` | `champ_voltscale_mamba.passive` |
| `champ_will_o_fawn` | Will-o-Fawn | `champ_will_o_fawn.active` | `champ_will_o_fawn.passive` |
| `champ_wintermoth` | Wintermoth | `champ_wintermoth.active` | `champ_wintermoth.passive` |
| `champ_wraithorn_stag` | Wraithorn Stag | `champ_wraithorn_stag.active` | `champ_wraithorn_stag.passive` |

### Enemies (60)

| Piece ID | Name | Active Ability ID | Passive Ability ID |
|---|---|---|---|
| `enemy_arcanist` | Arcanist | `enemy_arcanist.active` | `enemy_arcanist.passive` |
| `enemy_archmagus_imperator` | Archmagus Imperator | `enemy_archmagus_imperator.active` | `enemy_archmagus_imperator.passive` |
| `enemy_avalanche_engine` | Avalanche Engine | `enemy_avalanche_engine.active` | `enemy_avalanche_engine.passive` |
| `enemy_battlemage` | Battlemage | `enemy_battlemage.active` | `enemy_battlemage.passive` |
| `enemy_blight_lurker` | Blight Lurker | `enemy_blight_lurker.active` | `enemy_blight_lurker.passive` |
| `enemy_brineblight_berserker` | Brineblight Berserker | `enemy_brineblight_berserker.active` | `enemy_brineblight_berserker.passive` |
| `enemy_caged_banshee` | Caged Banshee | `enemy_caged_banshee.active` | `enemy_caged_banshee.passive` |
| `enemy_caged_storm_drake` | Caged Storm-Drake | `enemy_caged_storm_drake.active` | `enemy_caged_storm_drake.passive` |
| `enemy_cannoneer` | Cannoneer | `enemy_cannoneer.active` | `enemy_cannoneer.passive` |
| `enemy_capture_rig_wolf` | Capture-Rig Wolf | `enemy_capture_rig_wolf.active` | `enemy_capture_rig_wolf.passive` |
| `enemy_cold_iron_yeti` | Cold-Iron Yeti | `enemy_cold_iron_yeti.active` | `enemy_cold_iron_yeti.passive` |
| `enemy_company_captain` | Company Captain | `enemy_company_captain.active` | `enemy_company_captain.passive` |
| `enemy_company_guard` | Company Guard | `enemy_company_guard.active` | `enemy_company_guard.passive` |
| `enemy_conscript` | Conscript | `enemy_conscript.active` | `enemy_conscript.passive` |
| `enemy_crossbow_levy` | Crossbow Levy | `enemy_crossbow_levy.active` | `enemy_crossbow_levy.passive` |
| `enemy_drained_stalker` | Drained Stalker | `enemy_drained_stalker.active` | `enemy_drained_stalker.passive` |
| `enemy_dredge_hulk` | Dredge-Hulk | `enemy_dredge_hulk.active` | `enemy_dredge_hulk.passive` |
| `enemy_drowned_siren` | Drowned Siren | `enemy_drowned_siren.active` | `enemy_drowned_siren.passive` |
| `enemy_field_chaplain` | Field Chaplain | `enemy_field_chaplain.active` | `enemy_field_chaplain.passive` |
| `enemy_field_medic` | Field Medic | `enemy_field_medic.active` | `enemy_field_medic.passive` |
| `enemy_flood_tyrant` | Flood Tyrant | `enemy_flood_tyrant.active` | `enemy_flood_tyrant.passive` |
| `enemy_frost_sovereign` | Frost Sovereign | `enemy_frost_sovereign.active` | `enemy_frost_sovereign.passive` |
| `enemy_glacier_goliath` | Glacier Goliath | `enemy_glacier_goliath.active` | `enemy_glacier_goliath.passive` |
| `enemy_grand_marshal` | Grand Marshal | `enemy_grand_marshal.active` | `enemy_grand_marshal.passive` |
| `enemy_gunslinger` | Gunslinger | `enemy_gunslinger.active` | `enemy_gunslinger.passive` |
| `enemy_heavy_knight` | Heavy Knight | `enemy_heavy_knight.active` | `enemy_heavy_knight.passive` |
| `enemy_hexblade_officer` | Hexblade Officer | `enemy_hexblade_officer.active` | `enemy_hexblade_officer.passive` |
| `enemy_hierarch` | Hierarch | `enemy_hierarch.active` | `enemy_hierarch.passive` |
| `enemy_hollowed_wisp` | Hollowed Wisp | `enemy_hollowed_wisp.active` | `enemy_hollowed_wisp.passive` |
| `enemy_inquisitor` | Inquisitor | `enemy_inquisitor.active` | `enemy_inquisitor.passive` |
| `enemy_iron_collared_hound` | Iron-Collared Hound | `enemy_iron_collared_hound.active` | `enemy_iron_collared_hound.passive` |
| `enemy_iron_maiden` | Iron Maiden | `enemy_iron_maiden.active` | `enemy_iron_maiden.passive` |
| `enemy_levyman` | Levyman | `enemy_levyman.active` | `enemy_levyman.passive` |
| `enemy_lord_commander` | Lord Commander | `enemy_lord_commander.active` | `enemy_lord_commander.passive` |
| `enemy_maw_of_the_drowned` | Maw of the Drowned | `enemy_maw_of_the_drowned.active` | `enemy_maw_of_the_drowned.passive` |
| `enemy_picket` | Picket | `enemy_picket.active` | `enemy_picket.passive` |
| `enemy_pikeman` | Pikeman | `enemy_pikeman.active` | `enemy_pikeman.passive` |
| `enemy_powder_sapper` | Powder Sapper | `enemy_powder_sapper.active` | `enemy_powder_sapper.passive` |
| `enemy_quarried_behemoth` | Quarried Behemoth | `enemy_quarried_behemoth.active` | `enemy_quarried_behemoth.passive` |
| `enemy_quarry_crawler` | Quarry Crawler | `enemy_quarry_crawler.active` | `enemy_quarry_crawler.passive` |
| `enemy_reaver_of_the_reach` | Reaver of the Reach | `enemy_reaver_of_the_reach.active` | `enemy_reaver_of_the_reach.passive` |
| `enemy_riflemaster` | Riflemaster | `enemy_riflemaster.active` | `enemy_riflemaster.passive` |
| `enemy_riven_frost_wyrm` | Riven Frost-Wyrm | `enemy_riven_frost_wyrm.active` | `enemy_riven_frost_wyrm.passive` |
| `enemy_sergeant_at_arms` | Sergeant-at-Arms | `enemy_sergeant_at_arms.active` | `enemy_sergeant_at_arms.passive` |
| `enemy_shaftmaw` | Shaftmaw | `enemy_shaftmaw.active` | `enemy_shaftmaw.passive` |
| `enemy_shroud_killer` | Shroud-Killer | `enemy_shroud_killer.active` | `enemy_shroud_killer.passive` |
| `enemy_signal_drummer` | Signal Drummer | `enemy_signal_drummer.active` | `enemy_signal_drummer.passive` |
| `enemy_slag_sentinel` | Slag Sentinel | `enemy_slag_sentinel.active` | `enemy_slag_sentinel.passive` |
| `enemy_spymaster` | Spymaster | `enemy_spymaster.active` | `enemy_spymaster.passive` |
| `enemy_standard_bearer` | Standard Bearer | `enemy_standard_bearer.active` | `enemy_standard_bearer.passive` |
| `enemy_steam_engineer` | Steam Engineer | `enemy_steam_engineer.active` | `enemy_steam_engineer.passive` |
| `enemy_steam_knight` | Steam Knight | `enemy_steam_knight.active` | `enemy_steam_knight.passive` |
| `enemy_stone_warden` | Stone Warden | `enemy_stone_warden.active` | `enemy_stone_warden.passive` |
| `enemy_storm_tyrant` | Storm Tyrant | `enemy_storm_tyrant.active` | `enemy_storm_tyrant.passive` |
| `enemy_stormhawk` | Stormhawk | `enemy_stormhawk.active` | `enemy_stormhawk.passive` |
| `enemy_stretcher_hand` | Stretcher-Hand | `enemy_stretcher_hand.active` | `enemy_stretcher_hand.passive` |
| `enemy_sundered_lord` | Sundered Lord | `enemy_sundered_lord.active` | `enemy_sundered_lord.passive` |
| `enemy_thunder_bull` | Thunder Bull | `enemy_thunder_bull.active` | `enemy_thunder_bull.passive` |
| `enemy_veil_lord` | Veil Lord | `enemy_veil_lord.active` | `enemy_veil_lord.passive` |
| `enemy_voltaic_diviner` | Voltaic Diviner | `enemy_voltaic_diviner.active` | `enemy_voltaic_diviner.passive` |

### Bosses (6, two-phase)

| Boss ID | Name | Phase 1 Active | Phase 1 Passive | Phase Hook | Phase 2 Active | Phase 2 Passive | On-Death Hook |
|---|---|---|---|---|---|---|---|
| `boss_holloway` | Foundry-Lord Holloway | `holloway.pressure_vent` | `holloway.stoke_the_fires` | `holloway.phase_hook` | `holloway.magma_heave` | `holloway.cinder_husk` | `holloway.boiler_burst` |
| `boss_vance` | Solar Overseer Vance | `vance.focusing_lens` | `vance.glare` | `vance.phase_hook` | `vance.sunflare_pounce` | `vance.drought_aura` | `vance.sun_husk_collapse` |
| `boss_strand` | Grid-Director Strand | `strand.arc_cascade` | `strand.overcharged` | `strand.phase_hook` | `strand.thunderhead` | `strand.stormform` | `strand.lightning_strike` |
| `boss_vossberg` | Clearance-Marshal Vossberg | `vossberg.scorched_advance` | `vossberg.no_quarter` | `vossberg.phase_hook` | `vossberg.wildfire_leap` | `vossberg.feeding_frenzy` | `vossberg.fire_gutters_out` |
| `boss_crege` | Dredge-Admiral Crège | `crege.harpoon_winch` | `crege.dredged_depths` | `crege.phase_hook` | `crege.maelstrom_jaws` | `crege.drowning_tide` | `crege.silt_drains` |
| `boss_iron_emperor` | The Iron Emperor | `iron_emperor.decree_of_iron` | `iron_emperor.tribute` | `iron_emperor.phase_hook` | `iron_emperor.reclamation` | `iron_emperor.the_wound_spreads` | `iron_emperor.world_engine_dark` |
