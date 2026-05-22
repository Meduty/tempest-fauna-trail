# Enemy Roster — 60 PvE Designs

A complete first-pass roster of 60 enemies, organized by tier and weather affinity, designed to populate PvE waves and boss encounters.

## Distribution Framework

**Skew toward Clear (50% Clear, 10% each remaining weather).**

Rationale: enemies are predominantly human/industrial — soldiers, engineers, mages of the Empire — and humans are mechanically and thematically *less* coupled to weather than the spirit champions are. A "human soldier" doesn't gain or lose much from rain. Weather-aligned enemies are monsters, spirits, and elementals that share an affinity with one of the five non-Clear weather types.

**Bosses always have a weather affinity.** Each weather (including Clear) has exactly one Tier 10 boss. The final boss in New York uses the city's live weather as its affinity — the same rule as every other stage boss, just with higher stats and more complex mechanics. The other five T10 bosses are creature/spirit bosses tied to their elemental domain.

### Composition

| Weather | Count | Theme |
|---------|-------|-------|
| Clear | 30 (50%) | Humans: industrial, military, technological, imperial |
| Rain | 6 | Aquatic creatures, marsh-dwellers, river spirits |
| Snow | 6 | Frost beasts, ice elementals, glacial creatures |
| Cloudy | 6 | Mountain monsters, shadow-dwellers, stone beings |
| Mist | 6 | Wraiths, ghosts, ethereal predators |
| Thunder | 6 | Storm beasts, lightning elementals, electric predators |

### Tier distribution

| Tier | Clear | Per non-Clear weather | Total |
|------|-------|------------------------|-------|
| 1 | 5 | 0 | 5 |
| 2 | 4 | 0 | 4 |
| 3 | 3 | 1 each (5) | 8 |
| 4 | 3 | 1 each (5) | 8 |
| 5 | 3 | 1 each (5) | 8 |
| 6 | 4 | 0 | 4 |
| 7 | 2 | 1 each (5) | 7 |
| 8 | 3 | 0 | 3 |
| 9 | 2 | 1 each (5) | 7 |
| 10 | 1 (boss) | 1 each (5 bosses) | 6 |
| **Total** | **30** | **6 each** | **60** |

Lower tiers (T1–2) are pure-Clear because basic infantry/grunts are the canonical "early-game creep" feel. Weather creatures enter at T3 as the encounter difficulty ramps. T6 and T8 are pure-Clear "elite human" tiers — mid-late progression spikes that lean industrial. T10 is the boss tier, one per weather including Clear.

## Mechanical Notes — How Enemies Differ From Champions

Enemies share the **archetype system, stat block, ability framework, and damage formulas** with champions — they're built on identical construct. The differences are operational:

- **Not bought, spawned.** Enemies appear in pre-scripted PvE waves, not from a shop. No combination mechanic; no level-up via 3-of-a-kind. Encounter difficulty is set by which enemies and how many.
- **Tier ≠ rarity.** Tier here means raw power level / encounter difficulty, not shop rarity. A T7 enemy is roughly as strong as a T7 champion at level 1.
- **No items.** Enemies arrive with fixed stat blocks, no equipment slots. (Bosses may have an exception — see below.)
- **Bosses scale to player.** Recommended: Tier 10 boss stats scale with the player's current "stage" so they remain challenging across a long run. Optional encounter modifier — TBD.
- **Encounter composition.** Each PvE round is a curated mix from this roster. Encounter design is its own discipline (out of scope for this document) but this roster is the ingredient list.

## Master Matrix

| Tier | Clear (Humans) | Rain | Snow | Cloudy | Mist | Thunder |
|------|---------|------|------|--------|------|---------|
| 1 | Recruit, Conscript, Militiaman, Bandage Carrier, Drummer Boy | — | — | — | — | — |
| 2 | Pikeman, Crossbowman, Field Medic, Sapper | — | — | — | — | — |
| 3 | Sergeant, Battle Cleric, Standard Bearer | Marsh Lurker (Tank-HP) | Frostbite Hound (ADC-STR Warrior) | Cave Crawler (Tank-STR) | Faded Wraith (APC-INT Assassin) | Spark Wolf (ADC-STR Warrior) |
| 4 | Heavy Knight, Steam Engineer, Royal Guard | Tidesinger (APC-INT Mage) | Yeti Brute (Tank-HP) | Stone Sentinel (Tank-ARM+RES) | Mist Hunter (ADC-INT Marksman) | Storm Hawk (ADC-INT Marksman) |
| 5 | Battlemage, Gunslinger, Captain | Brine Berserker (ADC-STR Warrior) | Avalanche Caller (APC-STR Mage) | Shadowmaw (APC-INT Assassin) | Pale Banshee (SUP-Debuff) | Volt Diviner (APC-INT Mage) |
| 6 | Steam Knight, Riflemaster, Inquisitor, Magus Blade | — | — | — | — | — |
| 7 | Lord Commander, Iron Maiden | Riverhulk (Hybrid-Tank/DMG) | Glacial Goliath (Tank-ARM+RES) | Mountain Reaver (Hybrid-APC/ADC) | Shrouded Killer (APC-STR Assassin) | Thunder Bull (Tank-STR) |
| 8 | Cannoneer, Spymaster, Hierarch | — | — | — | — | — |
| 9 | Arcanist, Archmage Imperator | Storm Maw (Hybrid-APC/ADC) | Frost Wyrm (Hybrid-INT/STR) | Granite Behemoth (Hybrid-Tank/DMG) | Spectral Lord (Hybrid-INT/STR) | Storm Drake (Hybrid-INT/STR) |
| 10 | **Iron Emperor** (Hybrid-Tank/DMG) | **Leviathan of the Deep** (Hybrid-Tank/DMG) | **Avalanche Lord** (Hybrid-INT/STR) | **The Obsidian Wraith** (Hybrid-APC/ADC) | **The Veiled Sovereign** (Hybrid-APC/ADC) | **The Living Storm** (Hybrid-INT/STR) |

## Detailed Roster

### Clear — Humans / Empire

The bulk of the roster. Industrial, militaristic, technological. Mix of conscripted infantry, professional soldiers, royal guards, imperial mages, and clergy. Themed around a fading-empire vibe: gunpowder coexists with magic, steam-tech alongside old religion.

**Tier 1 — Conscripted infantry** (cheap fillers for early waves)
- **Recruit** (*Tank-HP*) — fresh frontline trainee · *passive: gains 50 HP on round start; no active ability.*
- **Conscript** (*ADC-STR Warrior*) — basic melee infantry · *passive: every 4th auto does +50% STR damage.*
- **Militiaman** (*ADC-STR Marksman*) — basic crossbow infantry · *no special abilities; reliable auto-attacker.*
- **Bandage Carrier** (*SUP-Heal*) — field aid · *cast: heals lowest-HP ally for small fixed amount.*
- **Drummer Boy** (*SUP-Buff*) — battlefield rallier · *aura: nearby allies gain +5% AS.*

**Tier 2 — Specialized infantry**
- **Pikeman** (*Tank-ARM+RES*) — phalanx defender · *passive: takes 30% less damage from enemies 2+ hexes away.*
- **Crossbowman** (*ADC-STR Marksman*) — heavier ranged · *cast: armor-piercing bolt, ignores 50% target Armor.*
- **Field Medic** (*SUP-Heal*) — trained healer · *cast: heals target ally for INT-scaled amount; passive: heals self over time.*
- **Sapper** (*APC-STR Mage*) — explosives specialist · *cast: throws bomb in 1-hex AOE, STR-scaled damage.*

**Tier 3 — Trained military and clergy**
- **Sergeant** (*Hybrid-Tank/DMG*) — bruiser leader · *passive: gains +1 STR for each nearby ally; cast: short cleave.*
- **Battle Cleric** (*SUP-Heal*) — martial priest · *cast: AOE heal in 2-hex radius around self; also wears armor and autos.*
- **Standard Bearer** (*SUP-Buff*) — inspires line · *aura: allies in 3-hex radius gain +10% STR/INT.*

**Tier 4 — Mid-tier specialists**
- **Heavy Knight** (*Tank-HP*) — full plate armor · *passive: shields self for 200 HP at round start.*
- **Steam Engineer** (*APC-INT Mage*) — tech-based caster · *cast: deploys a steam-vent turret (stationary minion) that autos for 3s.*
- **Royal Guard** (*Hybrid-Tank/DMG*) — elite bodyguard · *passive: when an ally within 2 hexes is attacked, taunts attacker for 1s.*

**Tier 5 — Mid-tier elites**
- **Battlemage** (*APC-INT Mage*) — imperial arcanist · *cast: fireball, INT-scaled AOE damage.*
- **Gunslinger** (*ADC-STR Marksman*) — dual pistols · *passive: autos chain to a second nearby enemy at 50% damage.*
- **Captain** (*SUP-Buff*) — commander · *cast: orders nearby allies to focus-fire a single target (target takes +30% damage for 4s).*

**Tier 6 — High-tier specialists** (pure-Clear tier)
- **Steam Knight** (*Tank-STR*) — mechanized armor · *passive: every 3rd attack against this piece is reflected as STR damage.*
- **Riflemaster** (*ADC-STR Marksman*) — long-range marksman · *passive: +1 attack range; first auto each combat deals 400% STR damage.*
- **Inquisitor** (*Hybrid-INT/STR*) — magic-and-blade hunter · *passive: autos deal +50% damage to enemies who have cast an ability this round.*
- **Magus Blade** (*ADC-INT Warrior*) — enchanted-sword wielder · *passive: autos deal +75% INT as magic damage; cast: empowers next 3 autos.*

**Tier 7 — Elite officers**
- **Lord Commander** (*Tank-STR*) — aggressive frontline lord · *cast: AOE knockback around self, STR-scaled damage and brief stun.*
- **Iron Maiden** (*Hybrid-Tank/DMG*) — peerless knight · *passive: gains armor every time hit (stacking); cast: full-restore armor and deal AOE STR damage.*

**Tier 8 — Elite operatives** (pure-Clear tier)
- **Cannoneer** (*ADC-STR Marksman*) — heavy artillery · *passive: autos deal damage in a 1-hex AOE around the target.*
- **Spymaster** (*APC-INT Assassin*) — shadow agent · *cast: stealth for 2s, then INT-scaled execute on target.*
- **Hierarch** (*SUP-Shield*) — high priest of the order · *cast: shields all allies for 4s.*

**Tier 9 — Imperial elite**
- **Arcanist** (*APC-INT Mage*) — high-magic specialist · *cast: chain lightning that bounces 5 times, INT-scaled damage.*
- **Archmage Imperator** (*Hybrid-INT/STR*) — peak of human magic · *passive: alternates between STR/INT scaling on autos; cast: massive AOE detonation scaling with both stats.*

**Tier 10 — The Empire's apex**
- **The Iron Emperor** (*Hybrid-Tank/DMG, BOSS*) — final human boss · *passive: gains 5% damage and 5% damage reduction per active ally on the board; cast: thunderous shockwave from the throne, AOE knockback and stun; on death: summons two Royal Guards.*

### Rain — Aquatic Creatures and River Spirits

Themes: water, depth, decay, ambush from below. Sustain-focused; many heal-over-time effects and slow attacks.

- **Marsh Lurker** (T3, *Tank-HP*) — bloated swamp beast · *passive: regenerates 3% HP/sec when not attacked for 2s.*
- **Tidesinger** (T4, *APC-INT Mage*) — singing siren-mage · *cast: AOE water-spell that briefly silences enemies hit.*
- **Brine Berserker** (T5, *ADC-STR Warrior*) — frenzied amphibian warrior · *passive: gains +10% AS when below 50% HP (stacking up to 30%).*
- **Riverhulk** (T7, *Hybrid-Tank/DMG*) — massive aquatic bruiser · *passive: drips water, leaving slowing puddles where they stand.*
- **Storm Maw** (T9, *Hybrid-APC/ADC*) — maw-of-the-deep apex predator · *passive: every cast empowers next 3 autos with INT scaling; cast: vortex pulling all nearby enemies in.*
- **Leviathan of the Deep** (T10, *Hybrid-Tank/DMG, BOSS*) — colossal sea-beast · *passive: drowning aura — all enemies within 3 hexes take 1% max HP per second as magic damage; cast: tidal slam that knocks all enemies back and floods the board (next 5s, all enemy MS reduced 50%).*

### Snow — Frost Beasts and Ice Elementals

Themes: cold, slows, durability, ambush from blizzard. Hard-to-damage, control-heavy.

- **Frostbite Hound** (T3, *ADC-STR Warrior*) — pack-hunting wolf · *passive: autos slow target by 20% for 2s.*
- **Yeti Brute** (T4, *Tank-HP*) — massive cold-resistant brute · *passive: takes 50% reduced damage from auto-attacks; cast: charge that knocks back nearest enemy.*
- **Avalanche Caller** (T5, *APC-STR Mage*) — STR-scaling ice-summoner · *cast: hurls a boulder of compacted ice in a line, STR-scaled damage and slow.*
- **Glacial Goliath** (T7, *Tank-ARM+RES*) — walking glacier · *passive: gains 10 ARM and 10 RES per round; cast: encases self in ice (invulnerable for 2s).*
- **Frost Wyrm** (T9, *Hybrid-INT/STR*) — flying ice serpent · *passive: aura freezes targets it auto-attacks (briefly rooted); cast: ice-breath cone scaling with INT and STR.*
- **Avalanche Lord** (T10, *Hybrid-INT/STR, BOSS*) — embodiment of the frozen mountain · *passive: at start of combat, summons three ice statues (immobile minions with high HP); cast: ICE AGE — freezes all enemies for 2s and deals INT+STR damage; on death: leaves a permanent slowing field where they stood.*

### Cloudy — Mountain Monsters and Stone-Dwellers

Themes: stone, ambush, hard-to-see, deceptive. Mix of slow tanks and burst assassins.

- **Cave Crawler** (T3, *Tank-STR*) — armored cave-stalker · *passive: gains stealth for 1s after taking damage.*
- **Stone Sentinel** (T4, *Tank-ARM+RES*) — animated boulder · *passive: immune to crowd control; cast: roots target for 2s.*
- **Shadowmaw** (T5, *APC-INT Assassin*) — shadow predator · *cast: blinks behind target, dealing INT-scaled burst.*
- **Mountain Reaver** (T7, *Hybrid-APC/ADC*) — peak-dwelling apex hunter · *passive: every 4th auto becomes a free cast at reduced scaling; cast: cleaving slash.*
- **Granite Behemoth** (T9, *Hybrid-Tank/DMG*) — massive stone-form bruiser · *passive: each auto received increases own STR by 1 (stacking); cast: ground-slam AOE.*
- **The Obsidian Wraith** (T10, *Hybrid-APC/ADC, BOSS*) — sentient mountain shadow · *passive: shrouded — first 3 seconds of combat, untargetable; cast: shadow clones that auto for 4s, scaling with INT; on death: shatters into three smaller stone elementals (continued combat).*

### Mist — Wraiths and Ethereal Predators

Themes: stealth, phasing, ignoring positional defenses. Anti-frontline, hits backline directly.

- **Faded Wraith** (T3, *APC-INT Assassin*) — barely-visible ghost · *passive: starts combat invisible until first attack; cast: phases through target, dealing INT damage.*
- **Mist Hunter** (T4, *ADC-INT Marksman*) — spirit archer · *passive: autos pass through pieces in line (line AOE).*
- **Pale Banshee** (T5, *SUP-Debuff*) — wailing spirit · *cast: AOE wail that fears enemies (3-hex radius) for 2s.*
- **Shrouded Killer** (T7, *APC-STR Assassin*) — invisible blade-master · *cast: dash to backline target, dealing STR-scaled execute; refunds mana on kill.*
- **Spectral Lord** (T9, *Hybrid-INT/STR*) — high noble of the dead · *passive: alternates auto scaling between STR (physical) and INT (magic); cast: AOE haunt.*
- **The Veiled Sovereign** (T10, *Hybrid-APC/ADC, BOSS*) — undying king of mist · *passive: cannot be auto-attacked while above 50% HP (only abilities damage); cast: spawns 4 wraith copies that auto-attack the player's backline; on death: explodes into a permanent damage aura for the remaining round.*

### Thunder — Storm Beasts and Lightning Elementals

Themes: speed, chain damage, high-burst, fragile. Glass cannons.

- **Spark Wolf** (T3, *ADC-STR Warrior*) — lightning-charged wolf · *passive: gains 100% AS for 2s on round start.*
- **Storm Hawk** (T4, *ADC-INT Marksman*) — sky-diving raptor · *passive: autos chain to a second target at 50% damage with INT scaling.*
- **Volt Diviner** (T5, *APC-INT Mage*) — lightning shaman · *cast: chain lightning hitting up to 3 enemies, INT-scaled.*
- **Thunder Bull** (T7, *Tank-STR*) — electric charger · *passive: every step taken builds static; cast: discharge stuns nearby enemies and deals STR damage.*
- **Storm Drake** (T9, *Hybrid-INT/STR*) — winged lightning-wyrm · *passive: at full mana, autos discharge chain lightning at INT scaling; cast: dive-bomb dealing massive STR damage in AOE.*
- **The Living Storm** (T10, *Hybrid-INT/STR, BOSS*) — pure elemental storm given form · *passive: phases mid-combat — alternates between "cloud form" (untargetable, can't act) and "storm form" (devastating chain lightning autos); cast: thunderstorm AOE; on death: lightning strike that revives self at 30% HP, then phases out for good after 5 more seconds.*

## Tier Philosophy for Enemies

| Tier | Encounter role |
|------|----------------|
| 1–2 | Early creep waves; numerous, cheap, designed to be cleared in one round |
| 3–5 | Mid-game waves; introduce weather variety; encounter mix of human and creature |
| 6–8 | Late-game elite waves; small numbers, high difficulty per piece |
| 9 | Mini-bosses or pre-boss elite gauntlets |
| 10 | Stage bosses; one major encounter per "act" of the game; signature mechanics |

**Boss encounter design.** Each T10 boss is intended to anchor a stage encounter. The boss appears with a supporting cast drawn from lower tiers of their weather (e.g., the Iron Emperor appears with 2× T8 humans and 4× T1–3 conscripts). This gives the boss thematic context and lets the player engage the boss mechanics while still managing trash.

## Open Questions and Gaps

- **Encounter pacing.** How many PvE rounds per "act," and what's the difficulty curve? Out of scope for the roster itself, but the roster needs to support the curve.
- **Boss scaling.** Static T10 stats, or scale with player stage/level? Recommended: scale, so the same boss can appear at different points in a run.
- **Loot drops.** Do specific enemies drop specific items? If so, which? Especially relevant for bosses — a boss kill should feel rewarding.
- **Trash variety.** 30 humans and 6 weather creatures per faction may not be enough variety across a full game run. Consider tier-appropriate palette swaps (e.g., a "Veteran Recruit" reskin that's stat-identical to Recruit) for visual variety without bloating the design roster.
- **Encounter-specific behavior.** Do certain enemies trigger special encounter mechanics (e.g., "the Iron Emperor's throne room is a different map layout")? Currently treated as a single combat board; richer encounter design is a future consideration.
- **Summon scaling.** Several bosses (Obsidian Wraith, Veiled Sovereign, Avalanche Lord) summon minions. Summon stats and behaviors need their own design pass — should match the trash from this roster, or be unique encounter-specific units?
- **Difficulty modes.** If the game has multiple difficulty tiers (Normal/Hard/Insane), how do enemies scale across them? Stat multiplier on the same roster, or different roster compositions? Out of scope here.

## Summary

60 enemies skewed 50% Clear (humans/industrial) with 10% each across the five non-Clear weathers (monsters/spirits). Mechanically identical to champions — same archetype taxonomy, same combat math, same ability framework — differing only in operational role (spawned in PvE waves, no shop, no combination). Tier 10 holds six bosses, one per weather. The final boss in New York takes its affinity from the city's live weather at fight time — the same weather-dependent rule as every other boss, just with significantly higher power. The other five T10 bosses are the apex monster/spirit of each elemental faction. The full roster gives the encounter designer 60 ingredients to mix and match into PvE rounds, with thematic cohesion provided by weather grouping and tier appropriate for difficulty scaling.
