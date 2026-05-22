# Champion Roster — 60 Animal & Spirit Pieces

The player's champions are the **uprising**: animals woken to purpose and nature
spirits risen out of the wounded earth, banding together against the industrial
colonizers who strip the living world bare (see `enemy_roster.md`). Every
champion is a *piece* — the exact same combat object as an enemy
(`Champion`/`Enemy` share a stat block, the ability framework, and all damage
math). Champions differ only in *operation*: they are drafted, bought, levelled
by collecting copies, and they carry **traits** for team synergies.

**Status:** first-pass roster — 60 designs across 10 tiers × 6 weather
affinities. Names, identity hooks, one-line ability *concepts*, and trait tags
only. No stat blocks, no mana costs, no ranges — those are downstream work
(`t18_power_scaling_plan.md` for stats, the ability framework for kits). Traits
are defined in `trait_catalog.md`; the effect substrate in
`effect_systems_design.md`.

## Distribution Framework

**Per weather (10 champions each):**
- 2 Tanks (from 4 subtypes)
- 2 APCs / burst (from 4 subtypes)
- 2 ADCs / sustain (from 4 subtypes)
- 2 SUPs (from 4 subtypes)
- 2 Hybrids (from 3 subtypes)

Every archetype subtype appears in 3–4 different weathers, so no single piece is
a must-pick regardless of the live weather. **Total: 60.**

## Archetype Identity

| Family | Identity | Default damage source |
|--------|----------|-----------------------|
| Tank | Frontline, absorbs damage | Mixed / utility |
| APC | Burst — high per-cast damage, slow cycle | INT (Mage) or STR (Mage/Assassin variants) |
| ADC | Sustain — steady auto-attack DPS | STR (default) or INT (on-hit variants) |
| SUP | Enables the team via heal / shield / buff / debuff | N/A |
| Hybrid | Cross-family identity (bruiser, spellblade, phase-piece) | Varies per subtype |

Every champion also carries **one Kinship** and **one or two Callings**
(`trait_catalog.md`). Kinship is what the creature *is*; Calling is how it
fights. Tier-10s additionally carry the **Primordial** Calling.

## Master Matrix

| Tier | Clear | Rain | Snow | Cloudy | Mist | Thunder |
|------|-------|------|------|--------|------|---------|
| 1 | Dawnwisp (SUP-Heal) | Springfrog (SUP-Heal) | Snowpelt Cub (Tank-HP) | Pebbleback Pangolin (Tank-HP) | Lostlight Wisp (SUP-Heal) | Sparkfly (SUP-Debuff) |
| 2 | Veldt Pronghorn (ADC-STR Warrior) | Reedbank Otter (ADC-STR Warrior) | Wintermoth (SUP-Buff) | Dusk Bat (SUP-Debuff) | Will-o-Fawn (APC-INT Mage) | Thunderhoof Colt (ADC-STR Warrior) |
| 3 | Ember Salamander (APC-INT Mage) | Torrent Heron (APC-STR Mage) | Permafrost Walrus (APC-STR Mage) | Boulderhide Skink (APC-STR Mage) | Phantom Lynx (APC-INT Assassin) | Voltscale Mamba (APC-STR Assassin) |
| 4 | Goldcrest Lark (SUP-Buff) | Grovekeeper Tapir (Hybrid-Tank/DMG) | Hoarfrost Owl (SUP-Shield) | Geode Beetle (SUP-Shield) | Hollow Elk (Tank-INT) | Coppercrest Stork (SUP-Shield) |
| 5 | Aegis Tortoise (Tank-ARM+RES) | Coral Colossus (Tank-HP) | Frostplate Tortoise (Tank-ARM+RES) | Duskstep Marten (ADC-INT Warrior) | Fogveil Moth (SUP-Debuff) | Thunderhide Bison (Tank-ARM+RES) |
| 6 | Sunmane Lion (Tank-STR) | Marsh Thrush (SUP-Buff) | Iceclaw Lynx (ADC-INT Warrior) | Granite Gorilla (Tank-INT) | Wraithorn Stag (Tank-STR) | Tempest Eel (APC-INT Mage) |
| 7 | Goldhide Rhino (Hybrid-Tank/DMG) | Mirewarden Toad (Tank-INT) | Glacierback Mammoth (Hybrid-Tank/DMG) | Eclipse Jaguar (Hybrid-INT/STR) | Marshghast Boar (Hybrid-Tank/DMG) | Voltmane Jackal (Hybrid-INT/STR) |
| 8 | Mirage Caracal (APC-INT Assassin) | Glade Heron (ADC-INT Marksman) | Frostfang Wolverine (APC-STR Assassin) | Nightglass Mantis (APC-INT Assassin) | Veilfang Wolf (ADC-INT Warrior) | Thunderclap Gorilla (Tank-STR) |
| 9 | Sunspear Falcon (ADC-STR Marksman) | Riptide Caiman (APC-STR Assassin) | Frostquill Porcupine (ADC-STR Marksman) | Cliffeyrie Eagle (ADC-STR Marksman) | Spectral Heron (ADC-INT Marksman) | Storm Eagle (ADC-INT Marksman) |
| 10 | Aurion, the First Dawn (Hybrid-INT/STR) | Nerei, the Floodmother (Hybrid-APC/ADC) | Borealis, the Pale Aurora (Hybrid-INT/STR) | Umbra, the Mountain's Shadow (Hybrid-APC/ADC) | Mournhollow, the Pale Stag (Hybrid-APC/ADC) | Aerion, the Skybreaker (Hybrid-APC/ADC) |

---

## Detailed Roster by Weather

Each entry: **Name** (Tier T, *Archetype*) · [Kinship · Calling(s)] — identity
hook · *ability concept*. "Cast" = active ability; "passive" = always-on.

---

### Clear — The Sunwild

Sun-warmed plains, high open sky, dawn light. Big cats, hoofed runners, raptors,
and motes of first light. Clear is the **baseline** faction — strong, honest
pieces with few exotic mechanics, fitting `CLEAR`'s inert standing in both
weather systems (it neither counters nor is countered). Pairs well into any
team. *Weather: `CLEAR` sits outside the predator/prey ring — no node buff, no
node debuff, no affinity damage triangle.*

- **Dawnwisp** (T1, *SUP-Heal*) · [Spirit · Mender] — a mote of first light · *cast: knit a wound on the lowest-HP ally, INT-scaled heal.*
- **Veldt Pronghorn** (T2, *ADC-STR Warrior*) · [Beast · Skirmisher] — tireless plains runner · *passive: every 3rd auto strikes twice as the pronghorn wheels and gores.*
- **Ember Salamander** (T3, *APC-INT Mage*) · [Scaled · Mystic] — sun-basking firestarter · *cast: a line of kindling light, INT-scaled, that burns the ground for several ticks.*
- **Goldcrest Lark** (T4, *SUP-Buff*) · [Skyborn · Warden] — its dawn-song lifts the flock · *cast: a rallying song — allies gain damage and Attack Speed for one round (600 ticks).*
- **Aegis Tortoise** (T5, *Tank-ARM+RES*) · [Scaled · Guardian] — an ancient walking shield · *passive: reduces damage taken from every attacker adjacent to it.*
- **Sunmane Lion** (T6, *Tank-STR*) · [Beast · Bruiser] — the pride's roaring frontline · *cast: a STR-scaled cleave; the lion shields itself for a share of the damage it deals.*
- **Goldhide Rhino** (T7, *Hybrid-Tank/DMG*) · [Beast · Bruiser · Mender] — unstoppable once it builds momentum · *passive: heals on every auto, scaling with its own max HP; the longer it lives the harder it is to kill.*
- **Mirage Caracal** (T8, *APC-INT Assassin*) · [Beast · Stalker] — strikes from a shimmer of heat-haze · *cast: blink to the lowest-HP enemy, INT-scaled execute that hits harder the lower their HP.*
- **Sunspear Falcon** (T9, *ADC-STR Marksman*) · [Skyborn · Hunter] — a stooping dive of pure speed · *passive: every auto sets a sun-mark; marked targets take bonus auto damage.*
- **Aurion, the First Dawn** (T10, *Hybrid-INT/STR*) · [Spirit · Primordial · Channeler] — the great sun-lion spirit, the light the land was born under · *passive: gains a point of STR and a point of INT every tick alive — autos scale with both; cast: a blinding solar nova that disarms all enemies hit.*

---

### Rain — The Tidewild

Rivers, rainforest canopy, flooded marsh. Otters, herons, frogs, and slow river
spirits. Rain is **sustain incarnate** — heals over time, regeneration, heavy
slow attacks. *Weather: Rain hunts Cloudy and Mist; it is hunted by Snow and
Thunder (storm-water grounds itself, frost stills the river).* 

- **Springfrog** (T1, *SUP-Heal*) · [Tidekin · Mender] — a small bright river-frog · *cast: a healing rain on one ally, restoring health over several ticks.*
- **Reedbank Otter** (T2, *ADC-STR Warrior*) · [Tidekin · Skirmisher] — never still in the shallows · *passive: gains Move Speed for a short window after every attack.*
- **Torrent Heron** (T3, *APC-STR Mage*) · [Skyborn · Mystic] — hurls spears of weighted water · *cast: three water-spears in a cone; the water has heft, so the damage scales with STR.*
- **Grovekeeper Tapir** (T4, *Hybrid-Tank/DMG*) · [Beast · Bruiser · Mender] — a mossy-backed warden of the grove · *passive: regenerates HP every few ticks; cast: a snare of living vines, STR-scaled damage over its duration.*
- **Coral Colossus** (T5, *Tank-HP*) · [Tidekin · Guardian · Mender] — a reef given legs · *passive: the lower its HP, the faster it regenerates; cast: pull into its shell — brief damage immunity.*
- **Marsh Thrush** (T6, *SUP-Buff*) · [Skyborn · Warden] — a wandering songbird of the wetlands · *cast: a travelling song — allies gain Move Speed and Attack Speed for several ticks.*
- **Mirewarden Toad** (T7, *Tank-INT*) · [Tidekin · Guardian] — a vast bog-toad, half-sunk and patient · *passive: a slowing mire aura around it; cast: a sweep of its tongue drags all nearby enemies toward it.*
- **Glade Heron** (T8, *ADC-INT Marksman*) · [Skyborn · Hunter · Trickster] — a long-billed venom-hunter · *passive: autos plant poison stacks that tick for INT-scaled damage.*
- **Riptide Caiman** (T9, *APC-STR Assassin*) · [Scaled · Stalker] — death from below the waterline · *cast: a dashing death-roll through an enemy, heavy STR damage; passive: refunds mana on a takedown.*
- **Nerei, the Floodmother** (T10, *Hybrid-APC/ADC*) · [Spirit · Primordial · Channeler] — the great river-serpent spirit, the flood that remembers · *passive: every cast empowers her next 3 autos with INT scaling; cast: a board-spanning tidal wave.*

---

### Snow — The Frostwild

Tundra, glacier, the silent winter peaks. Bears, lynx, mammoths, owls — thick
hide and slow patience. Snow is **durable and controlling**: armor, slows, the
long grind. *Weather: Snow hunts Rain and Cloudy; it is hunted by Thunder and
Mist (lightning shatters ice, fog smothers the white).*

- **Snowpelt Cub** (T1, *Tank-HP*) · [Beast · Guardian] — a stubborn bear cub that will not fall · *passive: gains a chunk of max HP at the start of each round.*
- **Wintermoth** (T2, *SUP-Buff*) · [Swarm · Warden] — pale wings that beat warmth into allies · *cast: grants one ally a lasting Attack-Speed buff.*
- **Permafrost Walrus** (T3, *APC-STR Mage*) · [Tidekin · Mystic] — heaves slabs of pack-ice · *cast: hurls a compacted ice-boulder, STR-scaled impact damage in a small splash.*
- **Hoarfrost Owl** (T4, *SUP-Shield*) · [Skyborn · Warden] — sheathes the flock in ice · *cast: an ice-shell shield on an ally; when the shell breaks it bursts into a slowing chill.*
- **Frostplate Tortoise** (T5, *Tank-ARM+RES*) · [Scaled · Guardian] — armor of layered glacier · *passive: each hit it takes stacks a small, lasting damage-reduction (up to a cap).*
- **Iceclaw Lynx** (T6, *ADC-INT Warrior*) · [Beast · Skirmisher · Trickster] — a blur of cold claws · *passive: autos deal bonus INT-magic damage and briefly slow the target.*
- **Glacierback Mammoth** (T7, *Hybrid-Tank/DMG*) · [Beast · Bruiser] — it grows colder and vaster as the fight drags · *passive: gains HP and STR every round it survives; cast: a ground-quaking stomp that knocks enemies back.*
- **Frostfang Wolverine** (T8, *APC-STR Assassin*) · [Beast · Stalker] — small, rabid, lethal · *cast: a leap behind the target, massive STR burst; passive: its strikes critically hit any target afflicted by a freeze or slow.*
- **Frostquill Porcupine** (T9, *ADC-STR Marksman*) · [Beast · Hunter · Trickster] — fires a hail of ice quills · *passive: autos slow the target and deal bonus damage to already-slowed enemies.*
- **Borealis, the Pale Aurora** (T10, *Hybrid-INT/STR*) · [Spirit · Primordial · Mystic] — the great winter spirit, the hush before the white · *passive: an aura briefly freezes the nearest enemy every round; cast: a blizzard across the board scaling with INT and STR.*

---

### Cloudy — The Cragwild

Sheer mountains, cave-dark, twilight, and old stone. Bats, pangolins, mountain
apes, cliff eagles, and stone-patient creatures. Cloudy plays **deceptive and
defensive** — shadow, ambush, things hard to see and hard to move. *Weather:
Cloudy hunts Mist and Thunder; it is hunted by Rain and Snow.*

- **Pebbleback Pangolin** (T1, *Tank-HP*) · [Scaled · Guardian] — curls into an unbreakable ball · *passive: while it has not moved this round, it takes heavily reduced damage.*
- **Dusk Bat** (T2, *SUP-Debuff*) · [Beast · Trickster] — a flurry of wings in the enemy's eyes · *cast: blinds one enemy — sharply reduced Attack Speed for several ticks.*
- **Boulderhide Skink** (T3, *APC-STR Mage*) · [Scaled · Mystic] — a heavy cliff-lizard that throws the cliff · *cast: rolls a boulder down a line, STR-scaled damage to everything it crosses.*
- **Geode Beetle** (T4, *SUP-Shield*) · [Swarm · Warden] — its crystal shell can be lent out · *cast: a stone-skin shield on an ally that blocks the next large hit outright.*
- **Duskstep Marten** (T5, *ADC-INT Warrior*) · [Beast · Skirmisher · Stalker] — never where the blade expects · *passive: every few autos it shadow-steps behind its target before striking.*
- **Granite Gorilla** (T6, *Tank-INT*) · [Beast · Guardian] — answers every blow with the mountain's weight · *passive: returns a share of damage taken to the attacker as INT-magic damage.*
- **Eclipse Jaguar** (T7, *Hybrid-INT/STR*) · [Beast · Stalker · Channeler] — light and shadow in one body · *passive: alternates auto-attacks between STR and INT scaling; cast: a twinned strike that lands both at once.*
- **Nightglass Mantis** (T8, *APC-INT Assassin*) · [Swarm · Stalker] — a sliver of darkness with blades · *cast: vanish for a brief window, then an INT-scaled execute on the lowest-HP enemy.*
- **Cliffeyrie Eagle** (T9, *ADC-STR Marksman*) · [Skyborn · Hunter] — watches, unseen, from the high crag · *passive: its first auto each combat strikes for vastly amplified STR damage.*
- **Umbra, the Mountain's Shadow** (T10, *Hybrid-APC/ADC*) · [Spirit · Primordial · Stalker] — the great shadow the peaks cast at dusk, given hunger · *passive: every 5th auto becomes an empowered free cast; cast: splits off shadow-clones that auto-attack for a time.*

---

### Mist — The Hazewild

Fog-drowned forest, will-o'-wisps, the half-real. Ghost-stags, pale wolves,
moths, and drifting spirits — Mist is the most spirit-heavy faction by far.
Mist **ignores positioning**: it phases, it bypasses the frontline, it strikes
the backline directly. *Weather: Mist hunts Thunder and Snow; it is hunted by
Cloudy and Rain.*

- **Lostlight Wisp** (T1, *SUP-Heal*) · [Spirit · Mender] — a flicker that tends the fallen · *cast: sets a healing wisp on the lowest-HP ally that mends them over several ticks.*
- **Will-o-Fawn** (T2, *APC-INT Mage*) · [Spirit · Mystic] — a fawn of cold marsh-fire · *cast: conjures a fleeting double of an ally that mirrors their auto-attacks.*
- **Phantom Lynx** (T3, *APC-INT Assassin*) · [Spirit · Stalker] — a ghost-cat that walks through walls of flesh · *cast: phases through the target for INT damage, ignoring a large share of their Resistance.*
- **Hollow Elk** (T4, *Tank-INT*) · [Spirit · Guardian · Channeler] — a hollow-eyed spirit-stag, more breath than body · *passive: converts a share of all incoming damage into mana.*
- **Fogveil Moth** (T5, *SUP-Debuff*) · [Swarm · Trickster] — beats blinding fog from its wings · *cast: shrouds one enemy so its auto-attacks may simply miss for several ticks.*
- **Wraithorn Stag** (T6, *Tank-STR*) · [Spirit · Bruiser] — antlers of grave-light, a frontline that cannot be walled out · *passive: phases through pieces while moving (ignores collision); cast: a STR-scaled spectral gore.*
- **Marshghast Boar** (T7, *Hybrid-Tank/DMG*) · [Spirit · Bruiser · Stalker] — a swamp-ghost that vanishes when cornered · *passive: on dropping below half HP, turns briefly untargetable and refunds a chunk of mana.*
- **Veilfang Wolf** (T8, *ADC-INT Warrior*) · [Spirit · Skirmisher] — its bite leaves the soul thin · *passive: autos deal bonus INT-magic damage and shred the target's Resistance.*
- **Spectral Heron** (T9, *ADC-INT Marksman*) · [Spirit · Hunter] — looses arrows that pass clean through the living · *passive: autos are line-shots, striking every enemy behind the first.*
- **Mournhollow, the Pale Stag** (T10, *Hybrid-APC/ADC*) · [Spirit · Primordial · Channeler] — the great mist-stag, the grief the forest never set down · *passive: every other action is a free auto-attack at INT scaling; cast: a board-wide haunt that fears all enemies.*

---

### Thunder — The Stormwild

Open storm-skies and the fast hot savanna beneath them. Cheetah-quick beasts,
storm-birds, electric eels, things that move before the eye does. Thunder is
**high-tempo, high-risk** — burst, chains, speed, glass. *Weather: Thunder hunts
Snow and Rain; it is hunted by Mist and Cloudy.*

- **Sparkfly** (T1, *SUP-Debuff*) · [Swarm · Trickster] — a single bright jolt · *cast: a brief stun on one enemy.*
- **Thunderhoof Colt** (T2, *ADC-STR Warrior*) · [Beast · Skirmisher] — a young storm-horse, all nerve · *passive: gains a stacking burst of Attack Speed each time it is auto-attacked.*
- **Voltscale Mamba** (T3, *APC-STR Assassin*) · [Scaled · Stalker] — a strike like a closed circuit · *cast: a dash through the target leaving a STR-scaled electric trail across the tiles it crossed.*
- **Coppercrest Stork** (T4, *SUP-Shield*) · [Skyborn · Warden] — draws the lightning so allies need not · *cast: shields an ally; the shield redirects a share of incoming damage back to the attacker as lightning.*
- **Thunderhide Bison** (T5, *Tank-ARM+RES*) · [Beast · Guardian] — storm-grounded, heavy, immovable · *passive: the first instance of magic damage it takes each round is almost entirely absorbed.*
- **Tempest Eel** (T6, *APC-INT Mage*) · [Tidekin · Mystic] — the classic arc of chain-lightning · *cast: a bolt that leaps between several enemies, INT-scaled, weaker with each jump.*
- **Voltmane Jackal** (T7, *Hybrid-INT/STR*) · [Beast · Skirmisher · Channeler] — a warrior wired to the storm · *passive: STR and INT contribute equally to its autos; cast: a discharge that scales off whichever stat is higher.*
- **Thunderclap Gorilla** (T8, *Tank-STR*) · [Beast · Bruiser] — drums the ground into a shockwave · *cast: a STR-scaled shockwave that knocks back and briefly stuns nearby enemies.*
- **Storm Eagle** (T9, *ADC-INT Marksman*) · [Skyborn · Hunter · Channeler] — its talons trail living current · *passive: every 3rd auto forks to two extra targets for INT-scaled chain damage.*
- **Aerion, the Skybreaker** (T10, *Hybrid-APC/ADC*) · [Spirit · Primordial · Hunter] — the great storm-spirit, the first thunder that ever rolled · *passive: at full mana its next several autos become free casts at reduced scaling; cast: a sky-splitting storm over the whole board.*

---

## Tier Philosophy

| Tier | Role | Kit complexity |
|------|------|----------------|
| 1–2 | Entry pieces; cheap early-round fillers | One simple ability, minimal passive |
| 3–4 | Foundational archetypes; recognizable identities | Active + simple passive |
| 5–6 | Mid-game power; comp anchors | Conditional passives, escalating effects |
| 7–8 | High-impact pieces; distinctive mechanics | Multi-step abilities, transformative passives |
| 9 | Premium carries; build-around pieces | Specialized kits that want synergy |
| 10 | Legendary Primordials; unique mechanics | Set-defining; one per weather |

All six **Tier-10s are Hybrids** and all carry the **Primordial** Calling
(`trait_catalog.md` §3). They are the great nature spirits — the oldest,
largest expressions of the uprising — and each should anchor a comp built
around it.

## Weather Counter Reference

Champions live and die by the live weather. The predator/prey ring
(`weather_effects.py`: `MIST → CLOUDY → RAIN → SNOW → THUNDER → MIST`) decides
who is buffed and who is prey. Field a champion whose affinity *hunts* the
node weather and it takes the medium System-A buff **and** lands System-B hits
at up to `1.10×`.

| Affinity | Hunts (good vs.) | Hunted by (bad vs.) |
|---|---|---|
| Mist | Thunder, Snow | Cloudy, Rain |
| Cloudy | Mist, Thunder | Rain, Snow |
| Rain | Cloudy, Mist | Snow, Thunder |
| Snow | Rain, Cloudy | Thunder, Mist |
| Thunder | Snow, Rain | Mist, Cloudy |
| Clear | — (inert) | — (inert) |

> This corrects the earlier draft's counter table, which predated the
> implemented ring in `weather_effects.py`. `CLEAR` is outside the ring: a
> `CLEAR` champion is never buffed or debuffed by node weather and never gains
> or suffers an affinity damage multiplier — its identity comes from its kit and
> traits, not from weather (see `t20_ability_framework_plan.md` §9.1).

## Critical Strikes

All champions ship with `crit_chance = 0.0` and abilities that cannot crit.
Crit is a **build-around**, not a baseline — it is unlocked only by traits
(Mystic @4 sets `ability_can_crit`), augments, items (`item_catalog.md`), or a
champion's own passive. Frostfang Wolverine is the roster's reference case: its
"critically hit frozen/slowed targets" passive flips `ability_can_crit` while
the target is afflicted, rather than carrying a base crit stat.

## Open Gaps & Follow-ups

- **Trait distribution is first-pass.** Kinship counts run ~Beast 18 / Spirit 15
  / Skyborn 9 / Scaled 7 / Tidekin 6 / Swarm 5; Calling counts are balanced by
  giving sustain/disruption champions a second Calling. Verify against the
  `trait_catalog.md` §4 budget once breakpoints are tuned.
- **Stat blocks.** Per-tier × per-archetype base stats are unbuilt — `P = 1`
  archetype bases scaled by `t18_power_scaling_plan.md`.
- **Kit details.** Identity hooks and one-line concepts only; mana cost,
  scaling coefficients, ranges, and targeting are a per-piece follow-up against
  the ability framework.
- **Tier-10 signature mechanics.** Each Primordial needs a hand-tuned signature;
  the concepts above are suggestive, not locked.
- **STR Mages and INT Warriors** remain the rarest archetypes — confirm in
  playtest that 3 carriers each is enough representation.
