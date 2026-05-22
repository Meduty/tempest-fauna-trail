# Champion Roster — 60 Skeleton Designs

A complete first-pass roster of 60 champions, distributed across 10 tiers and 6 weather types, with balanced archetype representation.

## Distribution Framework

**Per weather (10 champions each):**
- 2 Tanks (from 4 subtypes)
- 2 APCs (burst) (from 4 subtypes)
- 2 ADCs (sustain) (from 4 subtypes)
- 2 SUPs (from 4 subtypes)
- 2 Hybrids (from 3 subtypes)

**Subtype totals across all 60 champions:**
- Tank subtypes (HP, ARM+RES, INT, STR): 3 each = 12
- APC subtypes (INT Mage, STR Mage, INT Assassin, STR Assassin): 3 each = 12
- ADC subtypes (INT Marksman, STR Marksman, INT Warrior, STR Warrior): 3 each = 12
- SUP subtypes (Heal, Shield, Buff, Debuff): 3 each = 12
- Hybrid subtypes (Tank/DMG, INT/STR, APC/ADC): 4 each = 12

**Total: 60.** Every subtype appears in 3–4 different weathers, ensuring no piece is a "must-pick" regardless of weather state.

## Archetype Identity Reminder

| Family | Identity | Default damage source |
|--------|----------|-----------------------|
| Tank | Frontline, absorbs damage | Mixed/utility |
| APC | Burst — high per-cast damage, slow cycle | INT (Mage) or STR (Mage/Assassin variants) |
| ADC | Sustain — steady auto-attack DPS | STR (default) or INT (on-hit variants) |
| SUP | Enables team via heal/shield/buff/debuff | N/A |
| Hybrid | Cross-family identity (bruiser, spellblade, etc.) | Varies per subtype |

## Master Matrix

| Tier | Clear | Rain | Snow | Cloudy | Mist | Thunder |
|------|-------|------|------|--------|------|---------|
| 1 | Acolyte (SUP-Heal) | Tide Acolyte (SUP-Heal) | Frost Cub (Tank-HP) | Stone Acolyte (Tank-HP) | Lost Wisp (SUP-Heal) | Spark Caster (SUP-Debuff) |
| 2 | Squire (ADC-STR Warrior) | Rivulet Guardian (ADC-STR Warrior) | Snow Acolyte (SUP-Buff) | Shrouded One (SUP-Debuff) | Spectral Apprentice (APC-INT Mage) | Storm Berserker (ADC-STR Warrior) |
| 3 | Sun Priest (APC-INT Mage) | Tide Conjurer (APC-STR Mage) | Avalanche Caster (APC-STR Mage) | Storm Slinger (APC-STR Mage) | Phantom Blade (APC-INT Assassin) | Voltdancer (APC-STR Assassin) |
| 4 | Lightbringer (SUP-Buff) | Druid of the Grove (Hybrid-Tank/DMG) | Frostbinder (SUP-Shield) | Stoneform Guardian (SUP-Shield) | Hollow Warden (Tank-INT) | Stormcatcher (SUP-Shield) |
| 5 | Paladin (Tank-ARM+RES) | Coral Behemoth (Tank-HP) | Glacial Warden (Tank-ARM+RES) | Shadowstep Striker (ADC-INT Warrior) | Mistweaver (SUP-Debuff) | Storm Titan (Tank-ARM+RES) |
| 6 | Sunblade Warden (Tank-STR) | Wandering Singer (SUP-Buff) | Glaivedancer (ADC-INT Warrior) | Mountain Sage (Tank-INT) | Wraith Knight (Tank-STR) | Stormbringer (APC-INT Mage) |
| 7 | Solar Crusader (Hybrid-Tank/DMG) | Mire Warden (Tank-INT) | Avalanche Elemental (Hybrid-Tank/DMG) | Dusk Stalker (Hybrid-INT/STR) | Mireborn (Hybrid-Tank/DMG) | Voltkin (Hybrid-INT/STR) |
| 8 | Dawnstrider (APC-INT Assassin) | Glade Hunter (ADC-INT Marksman) | Frostfang (APC-STR Assassin) | Twilight Reaver (APC-INT Assassin) | Veil Hunter (ADC-INT Warrior) | Thunderclap (Tank-STR) |
| 9 | Helios Archer (ADC-STR Marksman) | Tide Reaver (APC-STR Assassin) | Icebow Sniper (ADC-STR Marksman) | Skyhunter (ADC-STR Marksman) | Wraithbow (ADC-INT Marksman) | Stormbow (ADC-INT Marksman) |
| 10 | Aurelius, Lord of Dawn (Hybrid-INT/STR) | Nereus, Tide Sovereign (Hybrid-APC/ADC) | Borealis, Frost Sovereign (Hybrid-INT/STR) | Umbra, Shadow Sovereign (Hybrid-APC/ADC) | Specterking, Pale Lord (Hybrid-APC/ADC) | Aerion, Storm Sovereign (Hybrid-APC/ADC) |

## Detailed Roster by Weather

Each entry: **Name** (Tier T, *Archetype*) — identity hook · *ability concept*.

---

### Clear (Sun / Holy faction)

Themes: light, gold, divine, balance. Generic-feeling faction; strong baseline pieces with few exotic mechanics. Default counter to Cloudy and Mist.

- **Acolyte** (T1, *SUP-Heal*) — entry-level healer · *cast: heal lowest-HP ally for moderate INT-scaled health.*
- **Squire** (T2, *ADC-STR Warrior*) — cheap melee carry · *passive: every 3rd auto deals bonus STR damage.*
- **Sun Priest** (T3, *APC-INT Mage*) — light-burst mage · *cast: AOE holy damage in line, scales with INT.*
- **Lightbringer** (T4, *SUP-Buff*) — team STR/INT amplifier · *cast: aura giving allies +20% damage for 4s.*
- **Paladin** (T5, *Tank-ARM+RES*) — defensive frontline · *passive: reduces damage taken from adjacent attackers.*
- **Sunblade Warden** (T6, *Tank-STR*) — aggressive tank, frontline counter · *cast: short STR-scaling cleave, gain shield equal to damage dealt.*
- **Solar Crusader** (T7, *Hybrid-Tank/DMG*) — bruiser, sustains in fights · *passive: heals on auto-attack, scales with own HP.*
- **Dawnstrider** (T8, *APC-INT Assassin*) — burst assassin, holy damage · *cast: blink to lowest-HP enemy, INT-scaled execute.*
- **Helios Archer** (T9, *ADC-STR Marksman*) — fast-attacking sunbow · *passive: every auto applies a sun-mark, marked targets take +X% damage from autos.*
- **Aurelius, Lord of Dawn** (T10, *Hybrid-INT/STR*) — legendary; auto-attacks scale with both stats · *cast: blinding nova that disarms and deals hybrid damage; passive: gains 1 INT and 1 STR per second alive.*

---

### Rain (Water / Druid faction)

Themes: water, growth, healing, mobility. Mid-defense, high sustain. Strong against Thunder; counters Snow's slow-imposing kits via mobility.

- **Tide Acolyte** (T1, *SUP-Heal*) — basic water-priest healer · *cast: heal target ally over 3s (HoT).*
- **Rivulet Guardian** (T2, *ADC-STR Warrior*) — riverbank warrior · *passive: gains MS for 2s after attacking.*
- **Tide Conjurer** (T3, *APC-STR Mage*) — STR-scaling water mage; abilities summon water spears · *cast: throws three water spears in a cone, scales with STR (the water has weight).*
- **Druid of the Grove** (T4, *Hybrid-Tank/DMG*) — nature bruiser, regenerates · *passive: regenerates 2% HP/sec; cast: roots target in vines, deals STR-scaled damage over duration.*
- **Coral Behemoth** (T5, *Tank-HP*) — massive HP pool · *passive: gains 50 HP per second below 50% HP; cast: shell-up for 3s of damage immunity.*
- **Wandering Singer** (T6, *SUP-Buff*) — bard-style buffer · *cast: grants allies +30% MS and AS for 5s.*
- **Mire Warden** (T7, *Tank-INT*) — magic-damage tank, slow zone · *passive: creates a slowing aura around self; cast: pulls all enemies in range toward self.*
- **Glade Hunter** (T8, *ADC-INT Marksman*) — magical archer, on-hit poison · *passive: autos apply poison stacks scaling with INT.*
- **Tide Reaver** (T9, *APC-STR Assassin*) — water-blade burst assassin · *cast: dash through enemy, deal heavy STR damage; passive: refunds 30% mana on kill.*
- **Nereus, Tide Sovereign** (T10, *Hybrid-APC/ADC*) — legendary; alternates auto/cast roles · *passive: every cast empowers next 3 autos with INT scaling; cast: AOE tidal wave.*

---

### Snow (Ice / Frost faction)

Themes: cold, mountain, defense, slows. Tanky and controlling. Counters Rain via freezing; weak to Thunder's burst.

- **Frost Cub** (T1, *Tank-HP*) — sturdy starter tank · *passive: gains 10% HP at start of round.*
- **Snow Acolyte** (T2, *SUP-Buff*) — basic frost-themed buffer · *cast: grants ally +AS for 4s.*
- **Avalanche Caster** (T3, *APC-STR Mage*) — STR-scaling ice mage; throws frozen boulders · *cast: hurls heavy ice projectile, STR-scaling impact damage in small AOE.*
- **Frostbinder** (T4, *SUP-Shield*) — encases allies in ice shells · *cast: shield target ally; shield breaks deal AOE slow.*
- **Glacial Warden** (T5, *Tank-ARM+RES*) — heavy ice armor · *passive: each hit taken reduces incoming damage by 1% (stacking up to 30%).*
- **Glaivedancer** (T6, *ADC-INT Warrior*) — INT-scaling spinning melee · *passive: autos deal +INT magic damage and slow target briefly.*
- **Avalanche Elemental** (T7, *Hybrid-Tank/DMG*) — bruiser frost giant · *passive: grows in size as fight progresses, gaining HP and STR; cast: AOE knockback.*
- **Frostfang** (T8, *APC-STR Assassin*) — ice-dagger burst killer · *cast: leap behind target, deal massive STR damage; passive: critical strikes against frozen targets.*
- **Icebow Sniper** (T9, *ADC-STR Marksman*) — long-range frost archer · *passive: autos slow target; deals bonus damage to slowed enemies.*
- **Borealis, Frost Sovereign** (T10, *Hybrid-INT/STR*) — legendary; ice queen with mixed scaling · *passive: aura freezes nearest enemy briefly every 3s; cast: blizzard AOE scaling with INT+STR.*

---

### Cloudy (Shadow / Stone faction)

Themes: shadow, mountain, mystery, deception. Strong against APC backline (assassins reach them); weak to ADC sustain.

- **Stone Acolyte** (T1, *Tank-HP*) — basic mountain tank · *passive: rooted in place; reduces damage taken while stationary.*
- **Shrouded One** (T2, *SUP-Debuff*) — obscures enemy targeting · *cast: reduces target enemy's AS by 40% for 3s.*
- **Storm Slinger** (T3, *APC-STR Mage*) — STR-scaling stone-thrower · *cast: hurls boulder dealing STR damage in line.*
- **Stoneform Guardian** (T4, *SUP-Shield*) — turns allies temporarily invulnerable · *cast: grants target ally a stone-skin shield blocking the next big attack.*
- **Shadowstep Striker** (T5, *ADC-INT Warrior*) — INT melee with mobility · *passive: autos cause a small shadow-step, repositioning behind target on every Nth hit.*
- **Mountain Sage** (T6, *Tank-INT*) — magic-damage tank · *passive: returns 20% damage taken as INT magic damage to attacker.*
- **Dusk Stalker** (T7, *Hybrid-INT/STR*) — blade-mage hybrid · *passive: alternates auto-attacks between STR and INT scaling; cast: dual-element burst.*
- **Twilight Reaver** (T8, *APC-INT Assassin*) — shadow burst-killer · *cast: brief stealth, then INT-scaled execute on lowest-HP enemy.*
- **Skyhunter** (T9, *ADC-STR Marksman*) — high-perch silent archer · *passive: first attack each combat deals 300% STR damage.*
- **Umbra, Shadow Sovereign** (T10, *Hybrid-APC/ADC*) — legendary; transforms mid-fight · *passive: every 5th auto becomes an empowered cast; cast: shadow clones that auto-attack.*

---

### Mist (Ghost / Ethereal faction)

Themes: stealth, ethereal, fog, vision. Anti-positioning; bypasses frontlines. Weak to AOE that ignores stealth.

- **Lost Wisp** (T1, *SUP-Heal*) — ghostly healer · *cast: places a healing wisp on lowest-HP ally; wisp heals over time.*
- **Spectral Apprentice** (T2, *APC-INT Mage*) — illusion mage · *cast: spawns a temporary illusion that mimics target ally's auto-attacks.*
- **Phantom Blade** (T3, *APC-INT Assassin*) — ghost burst-killer · *cast: phases through target, dealing INT damage and ignoring 50% Resistance.*
- **Hollow Warden** (T4, *Tank-INT*) — spirit-form tank · *passive: 20% of incoming damage is converted to mana.*
- **Mistweaver** (T5, *SUP-Debuff*) — blinds enemies · *cast: targets enemy now has 50% miss chance for 3s (autos can miss).*
- **Wraith Knight** (T6, *Tank-STR*) — aggressive ghost frontline · *passive: phases through pieces while moving (ignores collision for movement); cast: STR-scaled spectral cleave.*
- **Mireborn** (T7, *Hybrid-Tank/DMG*) — swamp-bound bruiser · *passive: at <50% HP, gains stealth for 2s and refunds 50% mana.*
- **Veil Hunter** (T8, *ADC-INT Warrior*) — on-hit ghost melee · *passive: autos deal +75% INT as magic damage and reduce target's RES.*
- **Wraithbow** (T9, *ADC-INT Marksman*) — ethereal archer · *passive: arrows pass through pieces, hitting all in line (line-AOE auto-attacks).*
- **Specterking, Pale Lord** (T10, *Hybrid-APC/ADC*) — legendary; alternates phases · *passive: every other action is a free auto-attack at INT scaling; cast: AOE haunt that fears enemies.*

---

### Thunder (Lightning / Storm faction)

Themes: speed, burst, chain effects, electricity. High-tempo, high-risk. Strong against Snow; weak to Rain (water grounds lightning).

- **Spark Caster** (T1, *SUP-Debuff*) — basic shock debuff · *cast: applies a brief stun to target enemy.*
- **Storm Berserker** (T2, *ADC-STR Warrior*) — fast-attacking berserker · *passive: gains +5% AS every time auto-attacked (stacking, decays out of combat).*
- **Voltdancer** (T3, *APC-STR Assassin*) — physical lightning-assassin · *cast: dashes through target leaving a STR-scaled electric trail.*
- **Stormcatcher** (T4, *SUP-Shield*) — lightning-rod shield support · *cast: grants ally a shield that redirects 30% incoming damage as lightning to attacker.*
- **Storm Titan** (T5, *Tank-ARM+RES*) — lightning-resistant heavy tank · *passive: chain-resistance — first instance of magic damage each round is reduced 80%.*
- **Stormbringer** (T6, *APC-INT Mage*) — classic lightning mage · *cast: chain lightning hitting up to 4 enemies, INT scaling.*
- **Voltkin** (T7, *Hybrid-INT/STR*) — hybrid lightning warrior-mage · *passive: STR and INT contribute equally to autos (replaces default formula); cast: discharge based on highest stat.*
- **Thunderclap** (T8, *Tank-STR*) — aggressive electric frontline · *cast: shockwave knocking nearby enemies back, STR-scaled stun.*
- **Stormbow** (T9, *ADC-INT Marksman*) — chain-lightning archer · *passive: every 3rd auto chains to 2 additional targets, INT-scaled chain damage.*
- **Aerion, Storm Sovereign** (T10, *Hybrid-APC/ADC*) — legendary; speed + burst hybrid · *passive: at 100 mana, next 5 autos become free casts at reduced scaling; cast: ultimate AOE storm.*

---

## Tier Philosophy

The tier-by-tier feel, intended as guidance for designing kit complexity:

| Tier | Role | Kit complexity |
|------|------|----------------|
| 1–2 | Entry-level pieces; cheap fillers for early rounds | Single simple ability, minimal passive |
| 3–4 | Foundational archetypes; recognizable identities | Active + simple passive |
| 5–6 | Mid-game power pieces; comp anchors | More complex passives, conditional triggers |
| 7–8 | High-impact pieces with distinctive mechanics | Multi-step abilities, transformative passives |
| 9 | Premium carries; build-around pieces | Specialized kits, requires synergy |
| 10 | Legendary pieces; unique mechanics not seen elsewhere | Game-defining; one per weather |

**Tier 10 are all hybrids by design** — they're the most complex pieces and hybrid archetypes inherently require more bespoke kit design. Each Tier 10 should feel like a "set-defining" piece that comps can be built around.

## Balance and Distribution Notes

### Subtype frequency verification

| Subtype | Count | Weathers |
|---------|-------|----------|
| Tank-HP | 3 | Rain, Snow, Cloudy |
| Tank-ARM+RES | 3 | Clear, Snow, Thunder |
| Tank-INT | 3 | Rain, Cloudy, Mist |
| Tank-STR | 3 | Clear, Mist, Thunder |
| APC-INT Mage | 3 | Clear, Mist, Thunder |
| APC-STR Mage | 3 | Rain, Snow, Cloudy |
| APC-INT Assassin | 3 | Clear, Cloudy, Mist |
| APC-STR Assassin | 3 | Rain, Snow, Thunder |
| ADC-INT Marksman | 3 | Rain, Mist, Thunder |
| ADC-STR Marksman | 3 | Clear, Snow, Cloudy |
| ADC-INT Warrior | 3 | Snow, Cloudy, Mist |
| ADC-STR Warrior | 3 | Clear, Rain, Thunder |
| SUP-Heal | 3 | Clear, Rain, Mist |
| SUP-Shield | 3 | Snow, Cloudy, Thunder |
| SUP-Buff | 3 | Clear, Rain, Snow |
| SUP-Debuff | 3 | Cloudy, Mist, Thunder |
| Hybrid-Tank/DMG | 4 | Clear, Rain, Snow, Mist |
| Hybrid-INT/STR | 4 | Clear, Snow, Cloudy, Thunder |
| Hybrid-APC/ADC | 4 | Rain, Cloudy, Mist, Thunder |

### Weather counters (proposed)

These define how the weather-rotation system encourages team swaps:

- **Clear → counters Mist & Cloudy** (light reveals what shadow hides)
- **Rain → counters Thunder** (water grounds lightning)
- **Snow → counters Rain** (freezes water-based kits)
- **Cloudy → counters Clear** (shadow over sun)
- **Mist → counters Snow** (fog disrupts visibility advantage)
- **Thunder → counters Snow & Mist** (lightning pierces both)

This is a soft suggestion; the actual weather effect mechanics live in a separate proposal.

### Open gaps and follow-ups

- **Critical strikes.** All champions ship with `crit_chance = 0.0` by default — no
  piece starts with innate crit probability. Active abilities also cannot crit unless
  an augment or passive sets the `ability_can_crit` flag at runtime. Crit is intentionally
  a build-around mechanic, not a universal scaling path. Example: Frostfang's passive
  (*critical strikes against frozen targets*) is implemented as a passive listener that
  sets `ability_can_crit = True` while the target has the frozen status — not as a base
  stat. Any champion whose kit concept mentions crits should be treated similarly.
- **Naming.** All names are placeholders. Cohesive renaming pass needed once worldbuilding crystallizes.
- **Kit details.** Identity hooks and one-line ability concepts only — full kit design (mana cost, scaling, ranges, targeting) per piece is a follow-up.
- **Stat blocks.** Base stats per tier × per archetype not yet defined. See §9.9 of the combat proposal.
- **Trait/synergy system.** Pieces will likely also have non-weather traits (e.g., "Mage" trait giving bonus INT to all Mage subtypes regardless of weather). Untouched here.
- **Tier 10 mechanics.** Each legendary needs a hand-tuned signature mechanic; the descriptions above are deliberately suggestive rather than locked.
- **STR Mages and INT Warriors** are the rarest archetypes. Verify in playtesting whether the 3-per-subtype-distribution gives them enough representation, or if some cells should be re-archetyped.
- **Visual/thematic cohesion.** Pieces within a weather should feel like a faction. Some current names lean elemental (Frost Cub, Storm Titan); others lean role-titular (Acolyte, Squire). A second-pass naming sweep should commit to one convention per weather.
