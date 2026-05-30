# Champion Ability Catalog — Full Implementation Details

**60 champions × 2 abilities each = 120 total abilities**

This document provides comprehensive descriptions and implementation details for every champion ability in the roster. Champions are organized by affinity (Clear, Rain, Snow, Cloudy, Mist, Thunder), then by tier (T1-T10).

## Legend

- **Active**: Cast ability with mana cost and cooldown
- **Passive**: Always-on effect that subscribes to combat events
- **Scaling notation**: `base=X, scaling="stat*coefficient"` → damage/heal = base + (stat × coefficient)
- **Status durations**: Listed in ticks (600 ticks ≈ "per round" by convention)
- **Hooks**: Event subscriptions like `on_attack_landed`, `on_damage_taken`, `on_tick`, `on_cast_complete`

---

## CLEAR Affinity (10 champions)

### Dawnwisp (T1, SUP-Heal)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Knit Wound** (`champ_dawnwisp.active`) | Active | Heals the lowest-HP ally with INT-scaled restoration | INT heal: base=40, scaling="intelligence*2.5". Targets `lowest_hp_ally` |
| **Lingering Light** (`champ_dawnwisp.passive`) | Passive | Grants bonus heal to heal target (simulates HoT) | Hook: `on_heal`. Adds intelligence*0.3 bonus heal. Includes recursion guard to prevent infinite loop |

### Veldt Pronghorn (T2, ADC-STR Warrior)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Lunging Charge** (`champ_veldt_pronghorn.active`) | Active | Single-target STR-scaled physical strike | STR damage: base=50, scaling="strength*1.8", damage_type="physical" |
| **Double Strike** (`champ_veldt_pronghorn.passive`) | Passive | Every 3rd auto-attack strikes twice | Hook: `on_attack_landed`. Tracks counter, on 3rd hit deals 50% bonus physical damage |

### Ember Salamander (T3, APC-INT Mage)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Kindling Light** (`champ_ember_salamander.active`) | Active | Line of fire that burns the ground | INT damage: base=60, scaling="intelligence*1.8". Applies burn status 300 ticks |
| **Scorch** (`champ_ember_salamander.passive`) | Passive | Bonus damage vs burning targets | Hook: `on_attack_landed`. If target has burn, adds intelligence*0.3 damage |

### Goldcrest Lark (T4, SUP-Buff)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **War Song** (`champ_goldcrest_lark.active`) | Active | Grants all allies damage and attack speed buff | Applies +20 STR and 1.2x AS multiplier to all allies for 600 ticks |
| **Harmony Aura** (`champ_goldcrest_lark.passive`) | Passive | Nearby allies gain intelligence boost | Combat-duration +10 intelligence modifier to all allies |

### Aegis Tortoise (T5, Tank-ARM+RES)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Shell Fortify** (`champ_aegis_tortoise.active`) | Active | Gains massive armor and resistance | Grants +30 armor and +30 resistance for 600 ticks |
| **Carapace** (`champ_aegis_tortoise.passive`) | Passive | Reduces damage from adjacent attackers | Hook: `on_damage_pre`. 20% reduction (0.8x multiplier) from attackers at distance ≤ 1 |

### Sunmane Lion (T6, Tank-STR)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Radiant Cleave** (`champ_sunmane_lion.active`) | Active | STR cleave that heals self for damage dealt | STR damage: base=80, scaling="strength*2.0", damage_type="physical". Heals self for 30% of damage dealt |
| **Regal Fury** (`champ_sunmane_lion.passive`) | Passive | Gains bonus STR when bloodied (<50% HP) | Hook: `on_damage_taken`. Once when hp_pct < 0.5, grants +25 STR for 600 ticks |

### Goldhide Rhino (T7, Tank-Heal)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Stampede** (`champ_goldhide_rhino.active`) | Active | Charge with self-heal | STR damage: base=60, scaling="strength*1.5", damage_type="physical". Heals self for 5% max_hp |
| **Thick Hide** (`champ_goldhide_rhino.passive`) | Passive | Heals on every auto-attack | Hook: `on_attack_landed`. Self-heals 3% max_hp per hit |

### Mirage Caracal (T8, APC-INT Assassin)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Blink Strike** (`champ_mirage_caracal.active`) | Active | Execute with bonus damage vs low-HP targets | INT damage: base=80, scaling="intelligence*2.2". 1.5x multiplier vs targets <30% HP. Targets `lowest_hp_enemy` |
| **Shimmer** (`champ_mirage_caracal.passive`) | Passive | Next auto after cast deals bonus INT damage | Hook: `on_cast_complete` sets empowered flag. Hook: `on_attack_landed` adds intelligence*0.5 once, then clears flag |

### Sunspear Falcon (T9, ADC-STR Marksman)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Diving Strike** (`champ_sunspear_falcon.active`) | Active | Single-target STR physical nuke | STR damage: base=70, scaling="strength*2.0", damage_type="physical" |
| **Mark Prey** (`champ_sunspear_falcon.passive`) | Passive | Marks target on first auto; bonus damage on subsequent autos | Hook: `on_attack_landed`. Tracks marked targets by ID. Unmarked targets get marked. Marked targets take strength*0.35 bonus physical damage |

### Aurion, the First Dawn (T10, Primordial)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Dawn Nova** (`champ_aurion.active`) | Active | AOE nova that disarms enemies | Hybrid damage: base=100, scaling="strength*1.5+intelligence*1.5". AOE radius 2, applies disarm 200 ticks |
| **Perpetual Sunrise** (`champ_aurion.passive`) | Passive | Gains STR and INT periodically | Hook: `on_tick` every 600 ticks. Grants +15 STR and +15 INT (combat duration, stacks) |

---

## RAIN Affinity (10 champions)

### Springfrog (T1, SUP-Heal)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Healing Rain** (`champ_springfrog.active`) | Active | INT-scaled heal on lowest-HP ally | INT heal: base=30, scaling="intelligence*2.0". Targets `lowest_hp_ally` |
| **Mist Blessing** (`champ_springfrog.passive`) | Passive | Periodic heal tick to lowest ally | Hook: `on_tick` every 200 ticks. Heals intelligence*0.4 to `lowest_hp_ally` |

### Reedbank Otter (T2, ADC-STR Skirmisher)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Slippery Strike** (`champ_reedbank_otter.active`) | Active | Strike with attack speed boost | STR damage: base=40, scaling="strength*1.6", damage_type="physical". Grants +20 attack_speed for 400 ticks |
| **Evasive** (`champ_reedbank_otter.passive`) | Passive | Gains move speed after attacking | Hook: `on_attack_landed`. Grants +20 move_speed for 300 ticks |

### Torrent Heron (T3, APC-STR Mage)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Water Spears** (`champ_torrent_heron.active`) | Active | Three water-spears in a cone | STR damage: base=50, scaling="strength*1.6", damage_type="physical". Primary target full damage, 2 neighbors 60% each |
| **River's Blessing** (`champ_torrent_heron.passive`) | Passive | Water affinity bonus STR | Combat-duration +8 strength modifier |

### Grovekeeper Tapir (T4, Hybrid Bruiser-Mender)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Vine Snare** (`champ_grovekeeper_tapir.active`) | Active | Hybrid damage with root and poison DoT | Hybrid damage: base=40, scaling="strength*1.0+intelligence*1.0". Applies root 200 ticks and poison 400 ticks (2 stacks) |
| **Regeneration** (`champ_grovekeeper_tapir.passive`) | Passive | Periodic self-healing | Hook: `on_tick` every 300 ticks. Heals self 2% max_hp |

### Coral Colossus (T5, Tank-Guardian)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Shell Immunity** (`champ_coral_colossus.active`) | Active | Massive defense buff | Grants +200 armor and +200 resistance for 300 ticks |
| **Coral Regen** (`champ_coral_colossus.passive`) | Passive | Regen when below 40% HP | Hook: `on_tick` every 200 ticks. If hp_pct < 0.4, heals 4% max_hp |

### Marsh Thrush (T6, SUP-Buff)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Flock Call** (`champ_marsh_thrush.active`) | Active | Team move speed and attack speed buff | Grants all allies +15 move_speed and +15 attack_speed for 600 ticks |
| **Fleet Wings** (`champ_marsh_thrush.passive`) | Passive | Movement speed boost | Combat-duration +10 move_speed modifier |

### Mirewarden Toad (T7, Tank-Guardian)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Tongue Pull** (`champ_mirewarden_toad.active`) | Active | Pull furthest enemy with slow and root | INT damage: base=50, scaling="intelligence*1.5". Targets `furthest_enemy`. Applies slow 300 ticks (2 stacks) and root 150 ticks |
| **Swamp Aura** (`champ_mirewarden_toad.passive`) | Passive | Slow aura | Hook: `on_tick` every 300 ticks. Applies slow to enemies in radius 2 (350 ticks, 1 stack) |

### Glade Heron (T8, ADC-INT Hunter)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Toxic Volley** (`champ_glade_heron.active`) | Active | INT strike with heavy poison | INT damage: base=60, scaling="intelligence*1.8". Applies poison 500 ticks (3 stacks) |
| **Venom Tip** (`champ_glade_heron.passive`) | Passive | Autos apply poison stacks | Hook: `on_attack_landed`. Applies poison 400 ticks (1 stack) |

### Riptide Caiman (T9, ADC-STR Stalker)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Death-Roll** (`champ_riptide_caiman.active`) | Active | Massive STR dash to lowest-HP enemy | STR damage: base=100, scaling="strength*2.5", damage_type="physical". Targets `lowest_hp_enemy` |
| **Predator** (`champ_riptide_caiman.passive`) | Passive | Mana refund on kill | Hook: `on_kill`. Grants 40% of ability cost as mana |

### Nerei, the Floodmother (T10, Primordial)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Tidal Wave** (`champ_nerei.active`) | Active | Massive AOE with charged self-buff | INT damage: base=90, scaling="intelligence*2.0". AOE radius 3, 70% damage each. Applies charged 300 ticks to self |
| **Surge** (`champ_nerei.passive`) | Passive | Next 3 autos after cast deal bonus INT | Hook: `on_cast_complete` grants 3 empowered autos. Each adds intelligence*0.6 damage, counter decrements |

---

## SNOW Affinity (10 champions)

### Snowpelt Cub (T1, Tank-Guardian)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Frostbite Nip** (`champ_snowpelt_cub.active`) | Active | Small STR strike with slow | STR damage: base=25, scaling="strength*1.2", damage_type="physical". Applies slow 200 ticks (1 stack) |
| **Growing Up** (`champ_snowpelt_cub.passive`) | Passive | Gains max HP periodically | Hook: `on_tick` every 600 ticks. Increases max_hp by 30, heals 30 |

### Wintermoth (T2, SUP-Buff)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Frost Dust** (`champ_wintermoth.active`) | Active | Grant ally AS buff and small heal | Targets `lowest_hp_ally`. Grants +25 attack_speed for 600 ticks. INT heal: base=20, scaling="intelligence*1.0" |
| **Cold Shroud** (`champ_wintermoth.passive`) | Passive | Resistance boost | Combat-duration +8 resistance modifier |

### Permafrost Walrus (T3, APC-STR Mage)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Ice Boulder** (`champ_permafrost_walrus.active`) | Active | STR projectile with splash | STR damage: base=70, scaling="strength*1.8", damage_type="physical". Primary full, neighbors 40% |
| **Frozen Fortitude** (`champ_permafrost_walrus.passive`) | Passive | Strength boost | Combat-duration +8 strength modifier |

### Hoarfrost Owl (T4, SUP-Shield)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Ice Shield** (`champ_hoarfrost_owl.active`) | Active | Grants ally armor shield and heal | Targets `lowest_hp_ally`. Grants +60 armor for 400 ticks. INT heal: base=30, scaling="intelligence*1.5" |
| **Frostborn** (`champ_hoarfrost_owl.passive`) | Passive | Intelligence boost | Combat-duration +8 intelligence modifier |

### Frostplate Tortoise (T5, Tank)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Ice Slam** (`champ_frostplate_tortoise.active`) | Active | STR slam with root | STR damage: base=60, scaling="strength*1.6", damage_type="physical". Applies root 200 ticks |
| **Permafrost Armor** (`champ_frostplate_tortoise.passive`) | Passive | Stacking armor on each hit taken | Hook: `on_damage_pre`. Grants +5 armor for 600 ticks per hit (stacks) |

### Iceclaw Lynx (T6, ADC-INT Warrior)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Frost Pounce** (`champ_iceclaw_lynx.active`) | Active | INT burst with freeze | INT damage: base=80, scaling="intelligence*2.0". Applies frozen 150 ticks |
| **Icy Touch** (`champ_iceclaw_lynx.passive`) | Passive | Autos deal bonus INT and slow | Hook: `on_attack_landed`. Adds intelligence*0.4 damage, applies slow 100 ticks (1 stack) |

### Glacierback Mammoth (T7, Tank-Bruiser)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Knockback Stomp** (`champ_glacierback_mammoth.active`) | Active | STR AOE with stun (simulates knockback) | STR damage: base=80, scaling="strength*2.0", damage_type="physical". AOE radius 1, applies stun 100 ticks |
| **Ancient Growth** (`champ_glacierback_mammoth.passive`) | Passive | Gains HP and STR periodically | Hook: `on_tick` every 600 ticks. Increases max_hp by 40, heals 40, grants +10 STR (combat duration, stacks) |

### Frostfang Wolverine (T8, ADC-STR Stalker)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Savage Leap** (`champ_frostfang_wolverine.active`) | Active | STR burst with crit bonus vs frozen/slowed | STR damage: base=90, scaling="strength*2.2", damage_type="physical", crit=true. 1.5x multiplier vs frozen/slowed targets |
| **Pack Hunter** (`champ_frostfang_wolverine.passive`) | Passive | Gains AS after each kill | Hook: `on_kill`. Grants +20 attack_speed (combat duration, stacks) |

### Frostquill Porcupine (T9, ADC-STR Hunter)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Quill Volley** (`champ_frostquill_porcupine.active`) | Active | Multi-target STR strike with slow | STR damage: base=70, scaling="strength*1.8", damage_type="physical". Primary full + slow 300 ticks (2 stacks). 2 neighbors 50% + slow 300 ticks (1 stack) |
| **Barbed Quills** (`champ_frostquill_porcupine.passive`) | Passive | Autos slow; bonus damage vs slowed | Hook: `on_attack_landed`. Applies slow 150 ticks (1 stack). If target has slow, adds strength*0.25 bonus physical damage |

### Borealis, the Pale Aurora (T10, Primordial)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Blizzard** (`champ_borealis.active`) | Active | Massive hybrid AOE with slow | Hybrid damage: base=80, scaling="strength*1.2+intelligence*1.2". AOE radius 3, applies slow 300 ticks (2 stacks) |
| **Eternal Winter** (`champ_borealis.passive`) | Passive | Periodically freezes nearest enemy | Hook: `on_tick` every 600 ticks. Applies frozen 200 ticks to closest enemy |

---

## CLOUDY Affinity (10 champions)

### Pebbleback Pangolin (T1, Tank)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Curl Up** (`champ_pebbleback_pangolin.active`) | Active | Gains armor | Grants +25 armor for 400 ticks |
| **Armored Shell** (`champ_pebbleback_pangolin.passive`) | Passive | Reduced damage while stationary | Combat-duration +15 armor modifier |

### Dusk Bat (T2, Trickster)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Screech** (`champ_dusk_bat.active`) | Active | Blinds enemy, reducing AS | Applies -30 attack_speed for 400 ticks |
| **Night Flight** (`champ_dusk_bat.passive`) | Passive | Movement speed boost | Combat-duration +10 move_speed modifier |

### Boulderhide Skink (T3, APC-STR Mage)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Boulder Line** (`champ_boulderhide_skink.active`) | Active | STR line damage | STR damage: base=60, scaling="strength*1.8", damage_type="physical". Primary full, 1 neighbor 50% |
| **Rocky Skin** (`champ_boulderhide_skink.passive`) | Passive | Armor boost | Combat-duration +5 armor modifier |

### Geode Beetle (T4, SUP-Shield)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Crystal Shield** (`champ_geode_beetle.active`) | Active | Grants ally massive shield | Targets `lowest_hp_ally`. Grants +80 armor and +40 resistance for 400 ticks |
| **Mineral Armor** (`champ_geode_beetle.passive`) | Passive | Armor boost | Combat-duration +10 armor modifier |

### Duskstep Marten (T5, INT Assassin)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Shadow Strike** (`champ_duskstep_marten.active`) | Active | INT burst on lowest-HP | INT damage: base=70, scaling="intelligence*2.0". Targets `lowest_hp_enemy` |
| **Shadowstep** (`champ_duskstep_marten.passive`) | Passive | Every 4th auto teleport bonus | Tracks counter. On 4th auto, adds intelligence*0.6 damage |

### Granite Gorilla (T6, Tank-INT)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Ground Slam** (`champ_granite_gorilla.active`) | Active | INT AOE with stun | INT damage: base=70, scaling="intelligence*1.8". AOE radius 1, applies stun 100 ticks |
| **Stone Skin** (`champ_granite_gorilla.passive`) | Passive | Returns damage as INT-magic | Hook: `on_damage_taken`. Reflects 15% damage as magical |

### Eclipse Jaguar (T7, Hybrid Stalker)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Twin Strike** (`champ_eclipse_jaguar.active`) | Active | Hybrid strike with both damage types | STR portion: base=50, scaling="strength*1.5", damage_type="physical". INT portion: base=50, scaling="intelligence*1.5", damage_type="magical" |
| **Dual Nature** (`champ_eclipse_jaguar.passive`) | Passive | Autos alternate STR and INT damage | Tracks counter. Even hits add intelligence*0.4 (magical). Odd hits add strength*0.3 (physical) |

### Nightglass Mantis (T8, INT Assassin)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Vanish Execute** (`champ_nightglass_mantis.active`) | Active | Execute with massive bonus vs low-HP | INT damage: base=100, scaling="intelligence*2.5". 1.6x multiplier vs targets <30% HP. Targets `lowest_hp_enemy` |
| **Stealth** (`champ_nightglass_mantis.passive`) | Passive | First hit amplified after combat start or cast | Hook: `on_attack_landed`. First hit (or after cast) adds intelligence*0.8 damage. Hook: `on_cast_complete` resets |

### Cliffeyrie Eagle (T9, ADC-STR Hunter)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Diving Talon** (`champ_cliffeyrie_eagle.active`) | Active | High STR physical nuke | STR damage: base=80, scaling="strength*2.2", damage_type="physical" |
| **Apex Predator** (`champ_cliffeyrie_eagle.passive`) | Passive | First auto vastly amplified | First hit adds strength*1.5 bonus physical damage (once per combat) |

### Umbra, the Mountain's Shadow (T10, Primordial)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Shadow Clones** (`champ_umbra.active`) | Active | Summons 2 shadow clones | Spawns 2 `Piece` summons (30% HP, 40% STR/INT, expires 1200 ticks) adjacent to caster. Summons have `summon=True` flag |
| **Penumbra** (`champ_umbra.passive`) | Passive | Every 5th auto triggers free cast damage | Tracks counter. On 5th auto, adds intelligence*1.5 damage |

---

## MIST Affinity (10 champions)

### Lostlight Wisp (T1, SUP-Heal)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Wisp Heal** (`champ_lostlight_wisp.active`) | Active | INT heal on ally | INT heal: base=35, scaling="intelligence*2.0". Targets `lowest_hp_ally` |
| **Healing Glow** (`champ_lostlight_wisp.passive`) | Passive | Periodic heal to lowest ally | Hook: `on_tick` every 200 ticks. Heals intelligence*0.3 to `lowest_hp_ally` |

### Will-o-Fawn (T2, INT Mystic)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Will Blessing** (`champ_will_o_fawn.active`) | Active | Grants ally attack speed buff | Targets `lowest_hp_ally` (excluding self). Grants +40 attack_speed for 300 ticks |
| **Ethereal** (`champ_will_o_fawn.passive`) | Passive | Intelligence boost | Combat-duration +8 intelligence modifier |

### Phantom Lynx (T3, APC-INT Assassin)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Phase Through** (`champ_phantom_lynx.active`) | Active | INT nuke with penetration | INT damage: base=90, scaling="intelligence*2.2". Grants +0.3 penetration_pct for 200 ticks. Targets `lowest_hp_enemy` |
| **Intangible** (`champ_phantom_lynx.passive`) | Passive | Penetration boost | Combat-duration +0.15 penetration_pct modifier |

### Hollow Elk (T4, Tank-Channeler)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Spirit Drain** (`champ_hollow_elk.active`) | Active | INT damage with self-heal | INT damage: base=60, scaling="intelligence*1.8". Heals self for 30% of damage dealt |
| **Void Absorption** (`champ_hollow_elk.passive`) | Passive | Converts incoming damage to mana | Hook: `on_damage_taken`. Grants 10% of damage as mana |

### Fogveil Moth (T5, Trickster)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Shroud** (`champ_fogveil_moth.active`) | Active | Reduces enemy AS with small INT damage | INT damage: base=30, scaling="intelligence*1.2". Applies -35 attack_speed for 500 ticks |
| **Mist Cloak** (`champ_fogveil_moth.passive`) | Passive | Resistance boost | Combat-duration +10 resistance modifier |

### Wraithorn Stag (T6, STR Bruiser)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Spectral Gore** (`champ_wraithorn_stag.active`) | Active | High STR physical burst | STR damage: base=80, scaling="strength*2.2", damage_type="physical" |
| **Ghostwalk** (`champ_wraithorn_stag.passive`) | Passive | Gains move speed after attacking | Hook: `on_attack_landed`. Grants +25 move_speed for 300 ticks |

### Marshghast Boar (T7, Hybrid Bruiser)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Ghost Charge** (`champ_marshghast_boar.active`) | Active | Hybrid physical charge | Hybrid damage: base=60, scaling="strength*1.2+intelligence*1.2", damage_type="physical" |
| **Last Stand** (`champ_marshghast_boar.passive`) | Passive | Below 50% HP gains defenses and mana | Hook: `on_damage_taken`. Once when hp_pct < 0.5: grants +60 resistance, +40 armor (combat duration), 50% ability cost mana |

### Veilfang Wolf (T8, INT Skirmisher)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Fang Rush** (`champ_veilfang_wolf.active`) | Active | INT physical damage | INT damage: base=80, scaling="intelligence*2.2" |
| **Veil Rend** (`champ_veilfang_wolf.passive`) | Passive | Autos deal bonus INT and shred resistance | Hook: `on_attack_landed`. Adds intelligence*0.35 damage. Applies -8 resistance for 400 ticks |

### Spectral Heron (T9, INT Hunter)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Spectral Beam** (`champ_spectral_heron.active`) | Active | INT line damage | INT damage: base=80, scaling="intelligence*2.0". Primary full, neighbors 60% |
| **Pierce** (`champ_spectral_heron.passive`) | Passive | Autos pierce (hit target + 1 behind) | Hook: `on_attack_landed`. Hits 1 neighbor for intelligence*0.3 damage |

### Mournhollow, the Pale Stag (T10, Primordial)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Haunt** (`champ_mournhollow.active`) | Active | Board fear AOE | INT damage: base=80, scaling="intelligence*1.8". AOE radius 3, 60% damage. Applies fear 200 ticks |
| **Spirit Form** (`champ_mournhollow.passive`) | Passive | Every other cast triggers free auto | Tracks counter. On even casts, triggers basic attack (1.0x multiplier) |

---

## THUNDER Affinity (10 champions)

### Sparkfly (T1, Trickster)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Shock** (`champ_sparkfly.active`) | Active | Brief stun one enemy | INT damage: base=20, scaling="intelligence*1.0". Applies stun 150 ticks |
| **Zippy** (`champ_sparkfly.passive`) | Passive | Movement speed boost | Combat-duration +10 move_speed modifier |

### Thunderhoof Colt (T2, ADC-STR Skirmisher)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Thunder Charge** (`champ_thunderhoof_colt.active`) | Active | STR physical strike | STR damage: base=45, scaling="strength*1.6", damage_type="physical" |
| **Reactive** (`champ_thunderhoof_colt.passive`) | Passive | Stacking AS when attacked | Hook: `on_damage_taken`. Grants +8 attack_speed for 600 ticks per hit (stacks) |

### Voltscale Mamba (T3, ADC-STR Stalker)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Electric Dash** (`champ_voltscale_mamba.active`) | Active | STR dash with burn | STR damage: base=55, scaling="strength*1.8", damage_type="physical". Applies burn 200 ticks |
| **Lightning Fast** (`champ_voltscale_mamba.passive`) | Passive | Movement speed boost | Combat-duration +15 move_speed modifier |

### Coppercrest Stork (T4, SUP-Shield)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Copper Shield** (`champ_coppercrest_stork.active`) | Active | Ally shield (armor buff) | Targets `lowest_hp_ally`. Grants +50 armor for 400 ticks |
| **Static Guard** (`champ_coppercrest_stork.passive`) | Passive | Resistance boost | Combat-duration +10 resistance modifier |

### Thunderhide Bison (T5, Tank)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Thunder Stomp** (`champ_thunderhide_bison.active`) | Active | STR AOE with stun | STR damage: base=60, scaling="strength*1.8", damage_type="physical". Applies stun 120 ticks |
| **Magnetic Hide** (`champ_thunderhide_bison.passive`) | Passive | Periodic magic absorption (resistance buff) | Hook: `on_tick` every 600 ticks. Grants +50 resistance for 200 ticks |

### Tempest Eel (T6, APC-INT Mage)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Chain Lightning** (`champ_tempest_eel.active`) | Active | Chain lightning jumps to nearby | INT damage: base=100, scaling="intelligence*2.0". Chains to 2 neighbors at 60% and 40% |
| **Stormborn** (`champ_tempest_eel.passive`) | Passive | Intelligence boost | Combat-duration +10 intelligence modifier |

### Voltmane Jackal (T7, Hybrid Skirmisher)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Static Discharge** (`champ_voltmane_jackal.active`) | Active | Hybrid burst with charged status | Hybrid damage: base=60, scaling="strength*1.2+intelligence*1.2". Applies charged 300 ticks |
| **Alternating Current** (`champ_voltmane_jackal.passive`) | Passive | Every 3rd auto discharges bonus damage | Tracks counter. On 3rd auto, adds max(strength, intelligence)*0.5 damage |

### Thunderclap Gorilla (T8, STR Bruiser)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Shockwave** (`champ_thunderclap_gorilla.active`) | Active | STR AOE knockback with stun | STR damage: base=90, scaling="strength*2.2", damage_type="physical". AOE radius 2, applies stun 150 ticks |
| **Thunderous** (`champ_thunderclap_gorilla.passive`) | Passive | Strength boost | Combat-duration +15 strength modifier |

### Storm Eagle (T9, INT Hunter)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Lightning Dive** (`champ_storm_eagle.active`) | Active | INT physical nuke | INT damage: base=80, scaling="intelligence*2.0" |
| **Fork Lightning** (`champ_storm_eagle.passive`) | Passive | Every 3rd auto forks to 2 targets | Tracks counter. On 3rd auto, hits up to 2 neighbors for intelligence*0.4 each |

### Aerion, the Skybreaker (T10, Primordial)

| Ability | Type | Description | Implementation |
|---|---|---|---|
| **Storm** (`champ_aerion.active`) | Active | Massive board AOE with charged status | Hybrid damage: base=100, scaling="strength*1.3+intelligence*1.3". AOE radius 4, 60% damage. Applies charged 200 ticks |
| **Overcharge** (`champ_aerion.passive`) | Passive | When mana full, autos trigger bonus damage | Hook: `on_attack_landed`. If mana >= 90% of ability cost, adds intelligence*0.8 damage |

---

**Total: 120 champion abilities documented**

See also: [ABILITY_CATALOG_ENEMIES.md](./ABILITY_CATALOG_ENEMIES.md) for enemy abilities and [../journal/2026-05-30_t30_ability_catalog.md](../../journal/2026-05-30_t30_ability_catalog.md) for boss kits and implementation context.
