# Enemy Ability Catalog — Full Implementation Details

**60 enemies × 2 abilities each = 120 total abilities**

This document provides comprehensive descriptions and implementation details for every enemy ability in the roster. Enemies are organized by faction: Humans (T1-T10, 30 enemies), then Corrupted Wildlife by affinity (Rain/Snow/Cloudy/Mist/Thunder, 5 each = 30 enemies).

## Legend

- **Active**: Cast ability with mana cost and cooldown
- **Passive**: Always-on effect that subscribes to combat events
- **Scaling notation**: `base=X, scaling="stat*coefficient"` → damage/heal = base + (stat × coefficient)
- **Status durations**: Listed in ticks (600 ticks ≈ "per round" by convention)
- **Hooks**: Event subscriptions like `on_attack_landed`, `on_damage_taken`, `on_tick`, `on_cast_complete`

---

## HUMANS (30 enemies, T1-T10)

### Conscript (T1)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Heavy Strike** (`enemy_conscript.active`) | Active | Basic STR strike | STR damage: base=30, scaling="strength*1.5", damage_type="physical" |
| **Phalanx Training** (`enemy_conscript.passive`) | Passive | Every 4th auto heavier | Hook: `on_attack_landed`. Tracks counter. On 4th hit, adds strength*0.5 bonus physical damage |

### Levyman (T1)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Strike** (`enemy_levyman.active`) | Active | Basic STR strike | STR damage: base=25, scaling="strength*1.3", damage_type="physical" |
| **Grit** (`enemy_levyman.passive`) | Passive | Gains HP periodically | Hook: `on_tick` every 600 ticks. Increases max_hp by 25, heals 25 |

### Picket (T1)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Basic Attack** (`enemy_picket.active`) | Active | Minimal STR strike | STR damage: base=20, scaling="strength*1.2", damage_type="physical" |
| **(No passive)** (`enemy_picket.passive`) | Passive | No special ability | Empty EffectBundle |

### Stretcher-Hand (T1, Support)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Field Heal** (`enemy_stretcher_hand.active`) | Active | Small INT heal | INT heal: base=25, scaling="intelligence*1.5". Targets `lowest_hp_ally` |
| **(No passive)** (`enemy_stretcher_hand.passive`) | Passive | No special ability | Empty EffectBundle |

### Signal Drummer (T1, Support)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Drum Roll** (`enemy_signal_drummer.active`) | Active | Buffs all allies AS | Grants all allies +15 attack_speed for 600 ticks |
| **Marching Beat** (`enemy_signal_drummer.passive`) | Passive | Aura nearby allies gain AS | Hook: `on_tick` every 300 ticks. Grants allies in radius 2 +12 attack_speed for 350 ticks |

### Pikeman (T2)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Pike Thrust** (`enemy_pikeman.active`) | Active | STR physical strike | STR damage: base=35, scaling="strength*1.5", damage_type="physical" |
| **Polearm Stance** (`enemy_pikeman.passive`) | Passive | Reduced damage from ranged attackers | Hook: `on_damage_pre`. 25% reduction (0.75x) from attackers at distance >= 2 |

### Crossbow Levy (T2)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Armor-Piercing Bolt** (`enemy_crossbow_levy.active`) | Active | STR strike with penetration | STR damage: base=40, scaling="strength*1.8", damage_type="physical". Applies +15 penetration for 50 ticks |
| **Marksmanship** (`enemy_crossbow_levy.passive`) | Passive | Penetration boost | Combat-duration +5 penetration modifier |

### Field Medic (T2, Support)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Stabilize** (`enemy_field_medic.active`) | Active | INT heal ally | INT heal: base=30, scaling="intelligence*2.0". Targets `lowest_hp_ally` |
| **Regeneration** (`enemy_field_medic.passive`) | Passive | Self-regen periodic | Hook: `on_tick` every 300 ticks. Heals self 2% max_hp |

### Powder Sapper (T2)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Powder Charge** (`enemy_powder_sapper.active`) | Active | STR splash charge | STR damage: base=50, scaling="strength*1.8", damage_type="physical". Primary full, neighbors 40% |
| **(No passive)** (`enemy_powder_sapper.passive`) | Passive | No special ability | Empty EffectBundle |

### Sergeant-at-Arms (T3)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Cleave** (`enemy_sergeant_at_arms.active`) | Active | STR cleave damage | STR damage: base=50, scaling="strength*1.6", damage_type="physical". Primary full, neighbors 50% |
| **Rally Troops** (`enemy_sergeant_at_arms.passive`) | Passive | Gains STR per nearby ally | Hook: `on_tick` every 600 ticks. Grants +8 STR per ally in radius 2 for 600 ticks |

### Field Chaplain (T3, Support)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Group Heal** (`enemy_field_chaplain.active`) | Active | AOE heal around self | INT heal: base=30, scaling="intelligence*1.5". Heals all allies in radius 2 |
| **(No passive)** (`enemy_field_chaplain.passive`) | Passive | No special ability | Empty EffectBundle |

### Standard Bearer (T3, Support)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Raise Standard** (`enemy_standard_bearer.active`) | Active | Grants all allies STR buff | Grants all allies +12 strength for 600 ticks |
| **Banner Aura** (`enemy_standard_bearer.passive`) | Passive | Aura allies gain STR and INT | Hook: `on_tick` every 300 ticks. Grants allies in radius 2 +8 STR and +8 INT for 350 ticks |

### Heavy Knight (T4)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Heavy Strike** (`enemy_heavy_knight.active`) | Active | STR physical strike | STR damage: base=50, scaling="strength*1.6", damage_type="physical" |
| **Steel Plate** (`enemy_heavy_knight.passive`) | Passive | Self-shield periodically | Hook: `on_tick` every 600 ticks. Grants +40 armor for 400 ticks |

### Steam Engineer (T4, Summoner)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Deploy Turret** (`enemy_steam_engineer.active`) | Active | Summons a turret | Spawns turret `Piece` summon (25% HP, 50% INT, range 3, expires 1200 ticks) adjacent. Summon has `summon=True` flag |
| **(No passive)** (`enemy_steam_engineer.passive`) | Passive | No special ability | Empty EffectBundle |

### Company Guard (T4, Tank)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Shield Wall** (`enemy_company_guard.active`) | Active | Gains armor and threat | Grants +40 armor and +50 threat for 600 ticks |
| **Taunt** (`enemy_company_guard.passive`) | Passive | High threat modifier | Combat-duration +80 threat modifier |

### Battlemage (T5)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Fireball** (`enemy_battlemage.active`) | Active | INT splash damage | INT damage: base=70, scaling="intelligence*2.0". Primary full, neighbors 50% |
| **(No passive)** (`enemy_battlemage.passive`) | Passive | No special ability | Empty EffectBundle |

### Gunslinger (T5)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Quick Shot** (`enemy_gunslinger.active`) | Active | STR physical strike | STR damage: base=50, scaling="strength*1.8", damage_type="physical" |
| **Ricochet** (`enemy_gunslinger.passive`) | Passive | Autos ricochet to 2nd target | Hook: `on_attack_landed`. Hits 1 neighbor for strength*0.3 physical damage |

### Company Captain (T5)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Mark Target** (`enemy_company_captain.active`) | Active | Mark increases damage taken | Targets `lowest_hp_enemy`. Applies -15 armor and -15 resistance for 600 ticks |
| **(No passive)** (`enemy_company_captain.passive`) | Passive | No special ability | Empty EffectBundle |

### Steam Knight (T6)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Heavy Strike** (`enemy_steam_knight.active`) | Active | STR physical strike | STR damage: base=60, scaling="strength*1.8", damage_type="physical" |
| **Reactive Plating** (`enemy_steam_knight.passive`) | Passive | Every 3rd hit reflects STR damage | Tracks counter. On 3rd hit taken, reflects strength*0.4 physical damage |

### Riflemaster (T6)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Precision Shot** (`enemy_riflemaster.active`) | Active | High STR physical nuke | STR damage: base=70, scaling="strength*2.0", damage_type="physical" |
| **Long Range** (`enemy_riflemaster.passive`) | Passive | Increased range; first auto huge | Combat-duration +1 attack_range. First hit adds strength*1.2 physical damage |

### Inquisitor (T6)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Hex Strike** (`enemy_inquisitor.active`) | Active | Hybrid strike | Hybrid damage: base=55, scaling="strength*1.2+intelligence*1.2" |
| **Witch Hunter** (`enemy_inquisitor.passive`) | Passive | Bonus damage vs casters (high INT) | Hook: `on_attack_landed`. If target INT > STR, adds max(strength, intelligence)*0.3 damage |

### Hexblade Officer (T6)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Enchanted Strike** (`enemy_hexblade_officer.active`) | Active | INT strike that empowers autos | INT damage: base=60, scaling="intelligence*1.8". Grants +20 INT for 600 ticks |
| **Mana Blade** (`enemy_hexblade_officer.passive`) | Passive | Autos bonus INT | Hook: `on_attack_landed`. Adds intelligence*0.25 damage |

### Lord Commander (T7)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Shockwave** (`enemy_lord_commander.active`) | Active | STR AOE with stun | STR damage: base=80, scaling="strength*2.0", damage_type="physical". AOE radius 2, applies stun 150 ticks |
| **Commanding Presence** (`enemy_lord_commander.passive`) | Passive | Strength boost | Combat-duration +15 strength modifier |

### Iron Maiden (T7, Tank)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Heavy Strike** (`enemy_iron_maiden.active`) | Active | STR physical strike | STR damage: base=60, scaling="strength*1.8", damage_type="physical" |
| **Retribution** (`enemy_iron_maiden.passive`) | Passive | Gains armor on hit; periodic AOE release | Hook: `on_damage_taken` grants +3 armor for 600 ticks per hit (tracks stacks). Hook: `on_tick` every 600 ticks releases AOE STR damage (strength*0.5 + stacks*5) radius 2 |

### Cannoneer (T8)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Cannon Shot** (`enemy_cannoneer.active`) | Active | Massive STR splash | STR damage: base=80, scaling="strength*2.2", damage_type="physical". Primary full, neighbors 40% |
| **Artillery** (`enemy_cannoneer.passive`) | Passive | Autos splash | Hook: `on_attack_landed`. Hits all neighbors for strength*0.2 physical damage |

### Spymaster (T8, Assassin)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Assassinate** (`enemy_spymaster.active`) | Active | Stealth INT execute | INT damage: base=100, scaling="intelligence*2.5". 1.6x vs targets <30% HP. Targets `lowest_hp_enemy` |
| **First Strike** (`enemy_spymaster.passive`) | Passive | Massive first hit | First hit adds intelligence*1.0 damage |

### Hierarch (T8, Support)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Divine Shield** (`enemy_hierarch.active`) | Active | Shield whole enemy line | Grants all allies +40 armor and +20 resistance for 500 ticks |
| **(No passive)** (`enemy_hierarch.passive`) | Passive | No special ability | Empty EffectBundle |

### Arcanist (T9)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Chain Lightning** (`enemy_arcanist.active`) | Active | Multi-bounce chain lightning | INT damage: base=90, scaling="intelligence*2.2". Chains to 3 neighbors at 60%, 45%, 30% |
| **(No passive)** (`enemy_arcanist.passive`) | Passive | No special ability | Empty EffectBundle |

### Archmagus Imperator (T9)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Hybrid Nuke** (`enemy_archmagus_imperator.active`) | Active | Massive hybrid strike | Hybrid damage: base=80, scaling="strength*1.5+intelligence*1.5" |
| **Battlemage** (`enemy_archmagus_imperator.passive`) | Passive | Autos alternate STR and INT | Tracks counter. Even hits add intelligence*0.35 (magical). Odd hits add strength*0.3 (physical) |

### Grand Marshal (T10)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Overwhelming Strike** (`enemy_grand_marshal.active`) | Active | Massive STR nuke | STR damage: base=90, scaling="strength*2.5", damage_type="physical" |
| **Veteran** (`enemy_grand_marshal.passive`) | Passive | Ramping STR periodically | Hook: `on_tick` every 600 ticks. Grants +20 STR (combat duration, stacks) |

---

## CORRUPTED WILDLIFE — RAIN (5 enemies)

### Blight Lurker (T3)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Basic Strike** (`enemy_blight_lurker.active`) | Active | STR physical strike | STR damage: base=40, scaling="strength*1.5", damage_type="physical" |
| **Regeneration** (`enemy_blight_lurker.passive`) | Passive | Regen when un-attacked | Tracks last_hit_tick. Hook: `on_tick` every 200 ticks. If 300 ticks since last hit, heals 3% max_hp |

### Drowned Siren (T4)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Siren Song** (`enemy_drowned_siren.active`) | Active | AOE water with silence | INT damage: base=50, scaling="intelligence*1.8". AOE radius 2, applies silence 200 ticks |
| **(No passive)** (`enemy_drowned_siren.passive`) | Passive | No special ability | Empty EffectBundle |

### Brineblight Berserker (T5)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Berserk Strike** (`enemy_brineblight_berserker.active`) | Active | High STR strike | STR damage: base=60, scaling="strength*2.0", damage_type="physical" |
| **Blood Fury** (`enemy_brineblight_berserker.passive`) | Passive | Gains AS as HP falls | Hook: `on_damage_taken`. If hp_pct < 0.5, grants +15 attack_speed for 300 ticks |

### Dredge-Hulk (T7)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Sludge Strike** (`enemy_dredge_hulk.active`) | Active | Hybrid damage with slow | Hybrid damage: base=60, scaling="strength*1.5+intelligence*1.0", damage_type="physical". Applies slow 400 ticks (2 stacks) |
| **Slowing Trail** (`enemy_dredge_hulk.passive`) | Passive | Trail slowing puddles (aura) | Hook: `on_tick` every 300 ticks. Applies slow to enemies in radius 2 (350 ticks, 1 stack) |

### Maw of the Drowned (T9)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Vortex Pull** (`enemy_maw_of_the_drowned.active`) | Active | AOE with root | INT damage: base=80, scaling="intelligence*2.0". AOE radius 3, 60% damage. Applies root 200 ticks |
| **Deep Hunger** (`enemy_maw_of_the_drowned.passive`) | Passive | Empowered autos after cast (3 charges) | Hook: `on_cast_complete` grants 3 empowered autos. Each adds intelligence*0.5 damage |

### Flood Tyrant (T10)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Tsunami** (`enemy_flood_tyrant.active`) | Active | Massive AOE | INT damage: base=90, scaling="intelligence*2.2". AOE radius 3, 60% damage |
| **Rising Waters** (`enemy_flood_tyrant.passive`) | Passive | Ramping INT periodically | Hook: `on_tick` every 600 ticks. Grants +15 INT (combat duration, stacks) |

---

## CORRUPTED WILDLIFE — SNOW (5 enemies)

### Iron-Collared Hound (T3)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Bite** (`enemy_iron_collared_hound.active`) | Active | STR bite with slow | STR damage: base=40, scaling="strength*1.6", damage_type="physical". Applies slow 250 ticks (2 stacks) |
| **Chilling Fangs** (`enemy_iron_collared_hound.passive`) | Passive | Autos slow | Hook: `on_attack_landed`. Applies slow 150 ticks (1 stack) |

### Cold-Iron Yeti (T4)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Charge** (`enemy_cold_iron_yeti.active`) | Active | Knockback charge with stun | STR damage: base=60, scaling="strength*1.8", damage_type="physical". Applies stun 150 ticks |
| **Frost Armor** (`enemy_cold_iron_yeti.passive`) | Passive | Reduces all incoming damage | Hook: `on_damage_pre`. 15% reduction (0.85x multiplier) |

### Avalanche Engine (T5)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Ice Boulder** (`enemy_avalanche_engine.active`) | Active | STR line with slow | STR damage: base=65, scaling="strength*1.8", damage_type="physical". Primary slow 300 ticks (2 stacks). 1 neighbor 50% damage + slow 200 ticks (1 stack) |
| **(No passive)** (`enemy_avalanche_engine.passive`) | Passive | No special ability | Empty EffectBundle |

### Glacier Goliath (T7)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Ice Invulnerability** (`enemy_glacier_goliath.active`) | Active | Massive defense buff | Grants +100 armor and +100 resistance for 300 ticks |
| **Permafrost** (`enemy_glacier_goliath.passive`) | Passive | Gains ARM and RES periodically | Hook: `on_tick` every 600 ticks. Grants +15 armor and +15 resistance (combat duration, stacks) |

### Riven Frost-Wyrm (T9)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Breath** (`enemy_riven_frost_wyrm.active`) | Active | Hybrid cone breath | Hybrid damage: base=80, scaling="strength*1.3+intelligence*1.3". Primary full, neighbors 50% |
| **Freezing Touch** (`enemy_riven_frost_wyrm.passive`) | Passive | Freeze on auto (every 4th) | Tracks counter. On 4th auto, applies frozen 150 ticks |

### Frost Sovereign (T10)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Blizzard** (`enemy_frost_sovereign.active`) | Active | Massive hybrid AOE with freeze | Hybrid damage: base=90, scaling="strength*1.2+intelligence*1.5". AOE radius 3, 60% damage. Applies frozen 150 ticks |
| **Eternal Winter** (`enemy_frost_sovereign.passive`) | Passive | Ramping INT periodically | Hook: `on_tick` every 600 ticks. Grants +15 INT (combat duration, stacks) |

---

## CORRUPTED WILDLIFE — CLOUDY (5 enemies)

### Quarry Crawler (T3)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Basic Strike** (`enemy_quarry_crawler.active`) | Active | STR physical strike | STR damage: base=40, scaling="strength*1.6", damage_type="physical" |
| **Carapace** (`enemy_quarry_crawler.passive`) | Passive | Gains armor after taking damage | Hook: `on_damage_taken`. Grants +8 armor for 400 ticks per hit |

### Slag Sentinel (T4)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Strike with Root** (`enemy_slag_sentinel.active`) | Active | STR strike with root | STR damage: base=45, scaling="strength*1.5", damage_type="physical". Applies root 250 ticks |
| **Heavy Armor** (`enemy_slag_sentinel.passive`) | Passive | CC-immune (high defenses) | Combat-duration +30 resistance and +20 armor modifiers |

### Shaftmaw (T5)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Blink Burst** (`enemy_shaftmaw.active`) | Active | INT burst on lowest-HP | INT damage: base=70, scaling="intelligence*2.0". Targets `lowest_hp_enemy` |
| **(No passive)** (`enemy_shaftmaw.passive`) | Passive | No special ability | Empty EffectBundle |

### Reaver of the Reach (T7)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Hybrid Cleave** (`enemy_reaver_of_the_reach.active`) | Active | Hybrid cleave | Hybrid damage: base=70, scaling="strength*1.5+intelligence*1.0", damage_type="physical" |
| **Cleave Proc** (`enemy_reaver_of_the_reach.passive`) | Passive | Every 4th auto free cleave | Tracks counter. On 4th auto, hits 1 neighbor for max(strength, intelligence)*0.6 physical damage |

### Quarried Behemoth (T9)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Ground Slam** (`enemy_quarried_behemoth.active`) | Active | STR AOE with stun | STR damage: base=80, scaling="strength*2.2", damage_type="physical". AOE radius 2, applies stun 100 ticks |
| **Enrage** (`enemy_quarried_behemoth.passive`) | Passive | Gains STR per hit absorbed | Hook: `on_damage_taken`. Grants +5 STR (combat duration, stacks) |

### Stone Warden (T10)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Massive Slam** (`enemy_stone_warden.active`) | Active | Massive STR AOE | STR damage: base=80, scaling="strength*2.0", damage_type="physical". AOE radius 2 |
| **Stone Form** (`enemy_stone_warden.passive`) | Passive | Ramping armor periodically | Hook: `on_tick` every 600 ticks. Grants +20 armor (combat duration, stacks) |

---

## CORRUPTED WILDLIFE — MIST (5 enemies)

### Hollowed Wisp (T3)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Phase Strike** (`enemy_hollowed_wisp.active`) | Active | INT strike | INT damage: base=50, scaling="intelligence*1.8" |
| **Intangible** (`enemy_hollowed_wisp.passive`) | Passive | Phase hit bonus | First hit adds intelligence*0.8 damage |

### Drained Stalker (T4)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Phase Strike** (`enemy_drained_stalker.active`) | Active | INT strike | INT damage: base=50, scaling="intelligence*1.8" |
| **Pierce** (`enemy_drained_stalker.passive`) | Passive | Line-pierce autos | Hook: `on_attack_landed`. Hits 1 neighbor for intelligence*0.25 damage |

### Caged Banshee (T5)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Wail** (`enemy_caged_banshee.active`) | Active | AOE fear | AOE radius 3, applies fear 200 ticks. Small INT damage: base=30, scaling="intelligence*1.0" |
| **(No passive)** (`enemy_caged_banshee.passive`) | Passive | No special ability | Empty EffectBundle |

### Shroud-Killer (T7)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Backline Execute** (`enemy_shroud_killer.active`) | Active | Dash execute | STR damage: base=90, scaling="strength*2.5", damage_type="physical". 1.5x vs targets <30% HP. Targets `lowest_hp_enemy` |
| **Assassin** (`enemy_shroud_killer.passive`) | Passive | Mana on kill | Hook: `on_kill`. Grants 50% of ability cost as mana |

### Sundered Lord (T9)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Haunt** (`enemy_sundered_lord.active`) | Active | AOE haunt with fear | Hybrid damage: base=70, scaling="strength*1.2+intelligence*1.2". AOE radius 3, 60% damage. Applies fear 150 ticks |
| **Spectral** (`enemy_sundered_lord.passive`) | Passive | Autos alternate with INT bonus | Tracks counter. Even hits add intelligence*0.3 damage |

### Veil Lord (T10)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Massive AOE** (`enemy_veil_lord.active`) | Active | Massive INT AOE | INT damage: base=80, scaling="intelligence*2.0". AOE radius 3, 60% damage |
| **Veil Power** (`enemy_veil_lord.passive`) | Passive | Ramping INT periodically | Hook: `on_tick` every 600 ticks. Grants +15 INT (combat duration, stacks) |

---

## CORRUPTED WILDLIFE — THUNDER (5 enemies)

### Capture-Rig Wolf (T3)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Basic Strike** (`enemy_capture_rig_wolf.active`) | Active | STR physical strike | STR damage: base=45, scaling="strength*1.6", damage_type="physical" |
| **Overclocked** (`enemy_capture_rig_wolf.passive`) | Passive | AS burst periodically | Hook: `on_tick` every 600 ticks. Grants +30 attack_speed for 300 ticks |

### Stormhawk (T4)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Lightning Strike** (`enemy_stormhawk.active`) | Active | INT strike | INT damage: base=50, scaling="intelligence*1.8" |
| **Chain Autos** (`enemy_stormhawk.passive`) | Passive | Autos chain to 2nd | Hook: `on_attack_landed`. Hits 1 neighbor for intelligence*0.3 damage |

### Voltaic Diviner (T5)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Chain Lightning** (`enemy_voltaic_diviner.active`) | Active | Chain lightning | INT damage: base=65, scaling="intelligence*2.0". Chains to 2 neighbors at 50% and 35% |
| **(No passive)** (`enemy_voltaic_diviner.passive`) | Passive | No special ability | Empty EffectBundle |

### Thunder Bull (T7)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Discharge** (`enemy_thunder_bull.active`) | Active | STR burst with stun | STR damage: base=70, scaling="strength*2.0", damage_type="physical". Applies stun 180 ticks |
| **Static Build** (`enemy_thunder_bull.passive`) | Passive | Tracks stacks (unused in combat) | Tracks counter of autos landed |

### Caged Storm-Drake (T9)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Dive** (`enemy_caged_storm_drake.active`) | Active | Hybrid AOE with stun | Hybrid damage: base=80, scaling="strength*1.3+intelligence*1.3". AOE radius 2, applies stun 100 ticks |
| **Overcharge** (`enemy_caged_storm_drake.passive`) | Passive | Mana-full autos chain | Hook: `on_attack_landed`. If mana >= 80% of cost, hits 1 neighbor for intelligence*0.4 damage |

### Storm Tyrant (T10)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Massive Hybrid AOE** (`enemy_storm_tyrant.active`) | Active | Massive hybrid AOE | Hybrid damage: base=90, scaling="strength*1.3+intelligence*1.3". AOE radius 3, 60% damage |
| **Storm Surge** (`enemy_storm_tyrant.passive`) | Passive | Ramping STR and INT periodically | Hook: `on_tick` every 600 ticks. Grants +12 STR and +12 INT (combat duration, stacks) |

---

**Total: 120 enemy abilities documented**

See also: [ABILITY_CATALOG_CHAMPIONS.md](./ABILITY_CATALOG_CHAMPIONS.md) for champion abilities and [../journal/2026-05-30_t30_ability_catalog.md](../../journal/2026-05-30_t30_ability_catalog.md) for boss kits and implementation context.
