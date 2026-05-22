# Enemy Roster — 60 Pieces of the Reclamation

The enemy faction is **the Reclamation** — an industrial-colonial human power
that strips the living world for fuel, ore, and weather itself. Steam and
gunpowder married to stolen magic; survey-flags, extraction rigs, and company
soldiers. They are settlers in the worst sense: they arrive, they fence the
land, they drain it. Two kinds of piece fight under their banner:

1. **Humans** — the company itself: conscripts, riflemen, engineers, mages,
   officers. The bulk of the roster, `CLEAR`-affinity, weather-indifferent.
2. **Corrupted wildlife** — animals and elementals the Reclamation has poisoned,
   collared, machine-grafted, or driven mad, then loosed as living weapons.
   These are the weather-aligned enemies. They are *not* spirits in revolt —
   they are the uprising's kin, broken and turned. Freeing the world means
   fighting through them.

Every enemy is a **piece** — the identical combat object as a champion
(`Champion`/`Enemy` share a stat block, the ability framework, the damage math,
the crit rules). The differences are purely operational:

- **Spawned, not bought.** Enemies appear in scripted PvE waves. No shop, no
  3-copy levelling. Encounter difficulty is set by which enemies and how many.
- **Tier = power, not rarity.** A Tier-7 enemy is roughly as strong as a Tier-7
  champion at level 1.
- **No items, no traits.** Enemies arrive with fixed stat blocks. They carry no
  equipment slots and contribute no synergy breakpoints (traits are a
  player-board mechanic — `trait_catalog.md` §1). Enemy pieces may still carry
  opaque **tags** (`human`, `beast`, `corrupted`, `machine`, …) purely so quest
  augments can match them (`augment_catalog.md` §6).
- **Bosses** are authored set-pieces — see `boss_roster.md`.

**Status:** first-pass roster — names, identity hooks, one-line ability
*concepts* only. No stat tuning, no kit implementation.

## Distribution Framework

**Skew toward Clear (50% Clear, 10% each remaining weather).** The Reclamation
is mostly human, and humans are weather-indifferent — a company rifleman gains
nothing from rain. Weather-aligned slots go to the corrupted wildlife, which
shares an affinity with one of the five non-`CLEAR` weathers.

| Weather | Count | Theme |
|---------|-------|-------|
| Clear | 30 (50%) | Humans — industrial, military, technological |
| Rain | 6 | Corrupted marsh & river wildlife; blight-fouled water |
| Snow | 6 | Frost beasts grafted with cold-iron; broken glacier elementals |
| Cloudy | 6 | Collared cave & mountain creatures; quarried stone-things |
| Mist | 6 | Hollowed wildlife; spirits caged and drained |
| Thunder | 6 | Storm beasts wired into capture-rigs; loosed current |

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

T1–2 are pure human — basic infantry is the canonical early-game creep.
Corrupted wildlife enters at T3 as encounter difficulty ramps. T6 and T8 are
pure-human "elite company" tiers — the Reclamation's professional core. T10 is
the boss tier: six stage bosses, fully designed in `boss_roster.md`.

## Master Matrix

| Tier | Clear (Humans) | Rain | Snow | Cloudy | Mist | Thunder |
|------|---------|------|------|--------|------|---------|
| 1 | Conscript, Levyman, Picket, Stretcher-Hand, Signal Drummer | — | — | — | — | — |
| 2 | Pikeman, Crossbow Levy, Field Medic, Powder Sapper | — | — | — | — | — |
| 3 | Sergeant-at-Arms, Field Chaplain, Standard Bearer | Blight Lurker (Tank-HP) | Iron-Collared Hound (ADC-STR Warrior) | Quarry Crawler (Tank-STR) | Hollowed Wisp (APC-INT Assassin) | Capture-Rig Wolf (ADC-STR Warrior) |
| 4 | Heavy Knight, Steam Engineer, Company Guard | Drowned Siren (APC-INT Mage) | Cold-Iron Yeti (Tank-HP) | Slag Sentinel (Tank-ARM+RES) | Drained Stalker (ADC-INT Marksman) | Stormhawk (ADC-INT Marksman) |
| 5 | Battlemage, Gunslinger, Company Captain | Brineblight Berserker (ADC-STR Warrior) | Avalanche Engine (APC-STR Mage) | Shaftmaw (APC-INT Assassin) | Caged Banshee (SUP-Debuff) | Voltaic Diviner (APC-INT Mage) |
| 6 | Steam Knight, Riflemaster, Inquisitor, Hexblade Officer | — | — | — | — | — |
| 7 | Lord Commander, Iron Maiden | Dredge-Hulk (Hybrid-Tank/DMG) | Glacier Goliath (Tank-ARM+RES) | Reaver of the Reach (Hybrid-APC/ADC) | Shroud-Killer (APC-STR Assassin) | Thunder Bull (Tank-STR) |
| 8 | Cannoneer, Spymaster, Hierarch | — | — | — | — | — |
| 9 | Arcanist, Archmagus Imperator | Maw of the Drowned (Hybrid-APC/ADC) | Riven Frost-Wyrm (Hybrid-INT/STR) | Quarried Behemoth (Hybrid-Tank/DMG) | Sundered Lord (Hybrid-INT/STR) | Caged Storm-Drake (Hybrid-INT/STR) |
| 10 | **Stage bosses — see `boss_roster.md`** | | | | | |

The six Tier-10 bosses (one per stage) are authored separately in
`boss_roster.md`. Each is a Reclamation commander bonded to a corrupted
apex-creature for its second phase.

---

## Detailed Roster

### Clear — The Reclamation (Humans)

The bulk of the roster. Industrial, militarized, extractive — a company army:
conscripted infantry, professional soldiers, steam-engineers, contracted mages,
and a hard old company faith that blesses the draining of the land. Gunpowder
beside magic, rig-iron beside scripture.

**Tier 1 — Conscripted infantry** (cheap early-wave fillers)
- **Conscript** (*ADC-STR Warrior*) · tags `human` — pressed-in melee infantry · *passive: every 4th auto lands a heavier blow.*
- **Levyman** (*Tank-HP*) · tags `human` — a fresh body for the front rank · *passive: gains a chunk of HP at round start; no active.*
- **Picket** (*ADC-STR Marksman*) · tags `human` — basic crossbow line · *reliable auto-attacker; no special abilities.*
- **Stretcher-Hand** (*SUP-Heal*) · tags `human` — company field aid · *cast: heals the lowest-HP ally for a small fixed amount.*
- **Signal Drummer** (*SUP-Buff*) · tags `human` — beats the advance · *aura: nearby allies gain a little Attack Speed.*

**Tier 2 — Specialized infantry**
- **Pikeman** (*Tank-ARM+RES*) · tags `human` — braced phalanx wall · *passive: takes reduced damage from attackers two or more hexes away.*
- **Crossbow Levy** (*ADC-STR Marksman*) · tags `human` — heavier ranged line · *cast: an armor-piercing bolt that ignores much of the target's Armor.*
- **Field Medic** (*SUP-Heal*) · tags `human` — trained company healer · *cast: an INT-scaled heal on one ally; passive: slowly heals itself.*
- **Powder Sapper** (*APC-STR Mage*) · tags `human` — demolition contractor · *cast: lobs a charge for STR-scaled splash damage.*

**Tier 3 — Trained soldiery and company faith**
- **Sergeant-at-Arms** (*Hybrid-Tank/DMG*) · tags `human` — a bruiser who holds the line · *passive: gains STR for each nearby ally; cast: a short cleave.*
- **Field Chaplain** (*SUP-Heal*) · tags `human` — armored, armed, and preaching · *cast: an AOE heal around itself; also wears armor and auto-attacks.*
- **Standard Bearer** (*SUP-Buff*) · tags `human` — carries the company colours · *aura: allies in range gain STR and INT.*

**Tier 4 — Mid-tier specialists**
- **Heavy Knight** (*Tank-HP*) · tags `human` — full company plate · *passive: shields itself at round start.*
- **Steam Engineer** (*APC-INT Mage*) · tags `human, machine` — deploys field machinery · *cast: builds a stationary steam-vent turret that auto-attacks for a time.*
- **Company Guard** (*Hybrid-Tank/DMG*) · tags `human` — elite bodyguard detail · *passive: when a nearby ally is attacked, taunts the attacker briefly.*

**Tier 5 — Mid-tier elites**
- **Battlemage** (*APC-INT Mage*) · tags `human` — a contracted arcanist · *cast: an INT-scaled fireball with splash.*
- **Gunslinger** (*ADC-STR Marksman*) · tags `human` — twin company revolvers · *passive: autos ricochet to a second nearby enemy at reduced damage.*
- **Company Captain** (*SUP-Buff*) · tags `human` — a field officer · *cast: marks a target for focus-fire — it takes increased damage for a window.*

**Tier 6 — Professional core** (pure-Clear tier)
- **Steam Knight** (*Tank-STR*) · tags `human, machine` — a piloted ironclad walker · *passive: every 3rd hit it takes is reflected as STR damage.*
- **Riflemaster** (*ADC-STR Marksman*) · tags `human` — a master marksman · *passive: extra attack range; its first auto each combat hits enormously hard.*
- **Inquisitor** (*Hybrid-INT/STR*) · tags `human` — hunts spellcasters for the company faith · *passive: deals bonus damage to any enemy that has cast an ability this round.*
- **Hexblade Officer** (*ADC-INT Warrior*) · tags `human` — a stolen-magic blade · *passive: autos deal bonus INT-magic damage; cast: empowers its next several autos.*

**Tier 7 — Senior officers**
- **Lord Commander** (*Tank-STR*) · tags `human` — leads from the front rank · *cast: a shockwave around itself — STR-scaled damage and a brief stun.*
- **Iron Maiden** (*Hybrid-Tank/DMG*) · tags `human, machine` — a peerless company knight · *passive: gains Armor every time it is hit; cast: restores all that Armor at once and deals AOE STR damage.*

**Tier 8 — Elite operatives** (pure-Clear tier)
- **Cannoneer** (*ADC-STR Marksman*) · tags `human, machine` — wheeled heavy artillery · *passive: autos detonate in a small splash around the target.*
- **Spymaster** (*APC-INT Assassin*) · tags `human` — the company's shadow-hand · *cast: a stealth window, then an INT-scaled execute.*
- **Hierarch** (*SUP-Shield*) · tags `human` — high voice of the company faith · *cast: shields the whole enemy line for a time.*

**Tier 9 — The Reclamation's apex**
- **Arcanist** (*APC-INT Mage*) · tags `human` — a high-magic specialist · *cast: chain lightning that bounces several times, INT-scaled.*
- **Archmagus Imperator** (*Hybrid-INT/STR*) · tags `human` — the summit of company magic · *passive: alternates STR/INT scaling on autos; cast: a vast detonation scaling with both stats.*

### Rain — Corrupted Marsh & River Wildlife

Animals and water-spirits the Reclamation has fouled with run-off, bound with
dredge-iron, and loosed downstream. Sustain-heavy, slow, and waterlogged.

- **Blight Lurker** (T3, *Tank-HP*) · tags `corrupted, beast` — a swamp beast swollen with poisoned silt · *passive: regenerates HP whenever it has not been attacked for a short time.*
- **Drowned Siren** (T4, *APC-INT Mage*) · tags `corrupted, spirit` — a river-spirit drained to a thin wail · *cast: an AOE water-spell that briefly silences enemies hit.*
- **Brineblight Berserker** (T5, *ADC-STR Warrior*) · tags `corrupted, beast` — a frenzied amphibian, mad with rot · *passive: gains stacking Attack Speed as its HP falls.*
- **Dredge-Hulk** (T7, *Hybrid-Tank/DMG*) · tags `corrupted, beast, machine` — a great river-beast grafted to a dredging rig · *passive: trails toxic run-off, leaving slowing puddles where it stands.*
- **Maw of the Drowned** (T9, *Hybrid-APC/ADC*) · tags `corrupted, beast` — a deep-river apex hunter, eyes gone milk-white · *passive: every cast empowers its next 3 autos with INT scaling; cast: a vortex that drags nearby enemies in.*

### Snow — Frost Beasts in Cold-Iron

Tundra wildlife grafted with cold-iron and broken glacier elementals harnessed
as siege-engines. Durable, slow, control-heavy.

- **Iron-Collared Hound** (T3, *ADC-STR Warrior*) · tags `corrupted, beast` — a pack wolf leashed to the company · *passive: its autos slow the target for a short time.*
- **Cold-Iron Yeti** (T4, *Tank-HP*) · tags `corrupted, beast, machine` — a tundra brute plated in scavenged iron · *passive: heavily reduced damage from auto-attacks; cast: a charge that knocks back the nearest enemy.*
- **Avalanche Engine** (T5, *APC-STR Mage*) · tags `corrupted, machine` — a captured ice-elemental fed through a launcher · *cast: hurls a compacted ice-boulder in a line — STR-scaled damage and a slow.*
- **Glacier Goliath** (T7, *Tank-ARM+RES*) · tags `corrupted, machine` — a walking glacier fitted with company armor-plate · *passive: gains Armor and Resistance each round; cast: encases itself in ice, briefly invulnerable.*
- **Riven Frost-Wyrm** (T9, *Hybrid-INT/STR*) · tags `corrupted, beast` — an ice-serpent split and re-stitched with rig-iron · *passive: briefly freezes targets it auto-attacks; cast: an ice-breath cone scaling with INT and STR.*

### Cloudy — Collared Cave & Mountain Creatures

Cliff-dwellers and stone-things dragged from quarries and mineshafts, collared
and set loose. Slow tanks and ambush killers.

- **Quarry Crawler** (T3, *Tank-STR*) · tags `corrupted, beast` — an armored cave-stalker, mine-blinded · *passive: gains brief stealth after taking damage.*
- **Slag Sentinel** (T4, *Tank-ARM+RES*) · tags `corrupted, machine` — animated furnace-slag in a rough humanoid shape · *passive: immune to crowd control; cast: roots a target in cooling slag.*
- **Shaftmaw** (T5, *APC-INT Assassin*) · tags `corrupted, beast` — a shadow-predator bred in the deep shafts · *cast: blinks behind the target for an INT-scaled burst.*
- **Reaver of the Reach** (T7, *Hybrid-APC/ADC*) · tags `corrupted, beast` — a peak-dwelling hunter, half its mind gone to the collar · *passive: every 4th auto becomes a free cast at reduced scaling; cast: a cleaving slash.*
- **Quarried Behemoth** (T9, *Hybrid-Tank/DMG*) · tags `corrupted, machine` — a mountain hewn into a moving siege-form · *passive: each auto it absorbs raises its own STR; cast: a ground-slam AOE.*

### Mist — Hollowed Wildlife & Caged Spirits

Forest wildlife hollowed out and spirits caged in draining-iron — the cruelest
corner of the roster. They phase, they bypass the frontline, they strike straight
for the backline.

- **Hollowed Wisp** (T3, *APC-INT Assassin*) · tags `corrupted, spirit` — a wisp drained almost to nothing · *passive: starts combat invisible until its first attack; cast: phases through the target for INT damage.*
- **Drained Stalker** (T4, *ADC-INT Marksman*) · tags `corrupted, beast` — a forest hunter, its outline gone thin and grey · *passive: its autos pass through pieces in a line.*
- **Caged Banshee** (T5, *SUP-Debuff*) · tags `corrupted, spirit` — a wailing spirit in a draining-cage · *cast: an AOE wail that fears nearby enemies.*
- **Shroud-Killer** (T7, *APC-STR Assassin*) · tags `corrupted, spirit` — a hollowed predator-spirit set to one purpose · *cast: a dash to a backline target for a STR-scaled execute; refunds mana on a takedown.*
- **Sundered Lord** (T9, *Hybrid-INT/STR*) · tags `corrupted, spirit` — a once-great forest spirit, cracked down the middle · *passive: alternates auto scaling between STR and INT; cast: an AOE haunt.*

### Thunder — Storm Beasts on Capture-Rigs

Storm-wildlife and loose current wired into the Reclamation's lightning-capture
rigs — drained for power and discharged at the enemy. Fast, fragile, brutal.

- **Capture-Rig Wolf** (T3, *ADC-STR Warrior*) · tags `corrupted, beast, machine` — a storm-wolf chained to a charge-coil · *passive: a burst of Attack Speed at round start.*
- **Stormhawk** (T4, *ADC-INT Marksman*) · tags `corrupted, beast` — a raptor with capture-wire still trailing from its talons · *passive: autos chain to a second target at reduced INT-scaled damage.*
- **Voltaic Diviner** (T5, *APC-INT Mage*) · tags `corrupted, spirit` — a storm-spirit bled into a conducting array · *cast: chain lightning across several enemies, INT-scaled.*
- **Thunder Bull** (T7, *Tank-STR*) · tags `corrupted, beast, machine` — a charging beast wired as a living battery · *passive: builds static with every step it takes; cast: discharges to stun nearby enemies for STR damage.*
- **Caged Storm-Drake** (T9, *Hybrid-INT/STR*) · tags `corrupted, beast` — a winged storm-wyrm shackled to a capture-rig · *passive: at full mana, its autos discharge chain lightning at INT scaling; cast: a dive-bomb for heavy STR AOE.*

## Tier Philosophy for Enemies

| Tier | Encounter role |
|------|----------------|
| 1–2 | Early creep waves — numerous, cheap, cleared in one round |
| 3–5 | Mid-game waves — introduce weather variety; mixed human + corrupted |
| 6–8 | Late-game elite waves — small numbers, high difficulty per piece |
| 9 | Pre-boss elite gauntlets / mini-bosses |
| 10 | Stage bosses — one per stage; signature 2-phase encounters (`boss_roster.md`) |

**Encounter composition** is its own discipline (`t19_encounter_generation_plan.md`)
— this roster is the ingredient list. Each PvE round is a curated, power-budgeted
mix. T9 corrupted apexes (Maw of the Drowned, Riven Frost-Wyrm, …) double as
pre-boss elites and as a boss's supporting cast.

## Open Questions & Gaps

- **Boss reconciliation.** The T10 row points to `boss_roster.md`. The earlier
  draft listed five free-standing creature-bosses (Leviathan, Avalanche Lord,
  …) — those apex-creature concepts are now folded into the bosses' **phase 2**
  (the corrupted beast a Reclamation commander unleashes when wounded).
- **Palette swaps.** 30 humans + 30 corrupted beasts may want tier-appropriate
  reskins (a stat-identical "Veteran Conscript") for visual variety without
  bloating the design roster.
- **Summon stats.** Steam Engineer's turret, boss adds, and similar summoned
  pieces need their own light stat pass.
- **Boss scaling.** Whether T10 stats scale to the player's stage — recommended
  yes, so a boss stays a threat across a long run.
- **Loot.** Whether specific enemies drop specific items, especially bosses
  (`D.12` drop tables).
