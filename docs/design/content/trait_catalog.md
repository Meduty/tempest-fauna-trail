# Trait Catalog — Synergy System

The trait system is a near-direct port of TFT's origin/class synergies, retuned
for a tick-based turn engine. Traits are the player's draft-puzzle layer: every
champion carries trait tags, and fielding enough tag-sharing champions unlocks
**breakpoint bonuses** that reward committed team-building.

**Status:** first-pass design. Names and breakpoint *concepts* only — no stat
tuning, no engine wiring. The substrate that runs all of this is
`docs/design/systems/effect_systems_design.md` §7 (traits as `TraitBreakpoint`
lists of `EffectBundle` factories). See also `champion_roster.md`, which assigns
every champion its Kinship + Calling(s).

---

## 1. Design rules

- **Two trait families.** Every champion has exactly **one Kinship** (what kind
  of creature/spirit it is) and **one or two Callings** (how it fights).
  Tier-10 legendaries carry the **Primordial** Calling on top of their normal
  Calling.
- **Counting rule.** Breakpoints count **unique champion ids**, not copies —
  two copies of the same champion count once (TFT convention,
  `effect_systems_design.md` §7.1).
- **Breakpoints.** Each trait lists 2–4 thresholds. The highest cleared
  threshold is the only one that applies (it supersedes lower ones).
- **Emblems.** The six Kinships are emblem-able: a **Spirit Gem** + an item
  component crafts that Kinship's emblem, letting any champion count toward it
  (`item_catalog.md` §4, `effect_systems_design.md` §7.3). Callings have no
  emblems.
- **Affinity is not a trait.** A champion's `affinity` (its `WeatherState`)
  drives the weather systems and is *separate* from traits (SPEC V.6, V.8).
  Traits never read weather; weather never reads traits. A handful of traits
  *thematically* echo weather (e.g. Scaled's storm-hardening) but resolve purely
  off trait membership.
- **Enemies and traits.** Enemies are the same kind of piece as champions and
  run on the same combat substrate, but traits are a **player-board mechanic** —
  enemy squads do not light up breakpoints. Enemy pieces may still carry trait
  *tags* as opaque labels so quest augments can match them (e.g. "kill 10
  Beasts"); they grant no synergy bonus. See `enemy_roster.md`.

---

## 2. Kinships (origin traits)

Six Kinships, one emblem each. A Kinship answers *"what rose up out of the
land?"* — the six broad forms the awakened wild takes.

### Beast — *fur, blood, and stubborn endurance*
Land mammals: the backbone of the uprising. Beast rewards the long fight.
- **@2** — Beasts gain bonus HP and slowly regenerate while alive.
- **@4** — Beasts also build stacking Strength every few hundred ticks they
  stay alive (a slow-burn ramp; rewards surviving the opening rounds).
- **@6** — the ramp doubles and Beasts heal for a share of the damage they deal.

### Skyborn — *wings, height, and the first move*
Birds and winged creatures. Skyborn rewards tempo and reach.
- **@2** — Skyborn gain Attack Speed and ignore piece collision while moving
  (they fly over the board; movement still costs the same energy).
- **@4** — Skyborn also gain Attack Range and act first in same-tick ties.
- **@6** — the first round of combat, Skyborn attacks cannot be answered: they
  gain a large burst of Attack Speed for the opening 600 ticks.

### Scaled — *cold blood, hard plates, weatherproof*
Reptiles. Scaled rewards a defensive, weather-agnostic core.
- **@2** — Scaled gain Armor and Resistance.
- **@4** — Scaled are **immune to the weather System-A debuff** — being the
  weather's prey no longer lowers their stats (they still take System-B hit
  multipliers).
- **@6** — Scaled additionally treat *every* node weather as a self-buff,
  gaining the strong-tier System-A stat pack regardless of affinity.

### Tidekin — *water, sustain, and the slow tide*
Aquatic creatures and amphibians. Tidekin rewards a healing-anchored team.
- **@2** — Tidekin heal a small amount every few hundred ticks.
- **@3** — Tidekin healing and all healing they receive is amplified.
- **@5** — once per combat, when a Tidekin would drop to 0 HP it instead surges
  back to a fraction of max HP (a single "undertow" save).

### Swarm — *numbers, and what's left behind*
Insects and small clustered creatures. Swarm rewards going wide and dying ugly.
- **@3** — when a Swarm champion dies it leaves a hazard or a chitin-spawn on
  its tile (an on-death effect; the substrate's `on_death` hook).
- **@5** — Swarm champions gain stats for every *other* Swarm champion on the
  board, and the on-death spawn grows stronger.
- **@7** — the on-death spawns can themselves spawn once; a fielded Swarm board
  never really thins out.

### Spirit — *breath, mana, and the half-real*
Elemental and ethereal nature spirits — the non-corporeal half of the uprising.
Spirit rewards an ability-driven team.
- **@2** — Spirits start combat with partial mana and gain Mana Regen.
- **@4** — Spirits are **untargetable for the opening ~150 ticks** of combat
  (they fade in) and their abilities cost less.
- **@6** — every few casts, a Spirit's next ability is empowered (a free
  echo-cast at reduced potency).

---

## 3. Callings (class traits)

Twelve Callings. A Calling answers *"what does it do in the fight?"* They cut
across Kinships and across the archetype taxonomy in `champion_roster.md` —
deliberately, so a synergy board never collapses into one archetype.

| Calling | Fantasy | Breakpoint shape (concept) |
|---|---|---|
| **Hunter** | Ranged carries — talon, quill, and patient aim. | @2 bonus auto-attack damage · @4 every few autos fires an empowered shot · @6 Hunters gain Attack Range and their empowered shots pierce. |
| **Guardian** | Frontline that shields the line behind it. | @2 Guardians shield themselves at combat start · @4 the shield extends to adjacent allies and refreshes each round · @6 while a Guardian's shield holds, adjacent allies take reduced damage. |
| **Mystic** | Mages — ability damage and arcane scaling. | @2 bonus Intelligence · @4 more Intelligence and **abilities may critically strike** (sets the `ability_can_crit` flag) · @6 Mystic casts also splash reduced damage to a neighbour. |
| **Warden** | Shield/buff supports who enable a team. | @2 a Warden's cast also grants a small shield to the lowest-HP ally · @4 Warden buffs and shields last longer · @6 at combat start the whole team gains a shield. |
| **Stalker** | Assassins — reach the backline, end one piece. | @2 Stalkers begin combat repositioned next to the enemy backline · @4 bonus damage to targets above a high HP threshold and mana refunded on takedown · @6 Stalkers gain a brief untargetable window after a takedown. |
| **Bruiser** | STR frontline that trades blows and lives. | @2 bonus HP · @4 bonus HP and Strength · @6 Bruisers heal for a share of the damage their attacks deal. |
| **Skirmisher** | Mobile melee — strike, reposition, strike. | @2 Skirmishers gain Attack Speed as they keep attacking one target · @4 they gain Move Speed and dodge a share of incoming autos · @6 the Attack-Speed ramp no longer decays and applies to the whole team's melee. |
| **Channeler** | Cast-spam engines — mana in, spells out. | @2 bonus Mana Regen · @4 every few casts the next ability is free · @6 a Channeler's first cast each combat triggers twice. |
| **Mender** | Healers — keep the board standing. | @2 healing done is amplified · @4 overhealing converts to a shield · @6 the first time each ally would die, a Mender's presence revives it once at low HP. |
| **Trickster** | Debuff and disruption — bend the enemy's tempo. | @2 Trickster casts apply a lingering debuff (slow / wither) · @4 Tricksters raise their own Threat and taunt their target briefly on cast · @6 enemies near a Trickster gain mana more slowly. |
| **Packmate** | Wide-board synergy — the many over the few. | @2 small team-wide stats · @4 the bonus scales with the *number of champions* you field · @6 a full board grants every champion a large flat bonus. |
| **Primordial** | The six Tier-10 legendaries — set-defining anchors. | @1 the Primordial's signature mechanic is active · @2 the team gains a large stat pack and Primordials gain a second wind once per combat · @3 (all-three, aspirational) the team's highest other trait counts as one tier higher. |

---

## 4. Trait-to-roster map (intended carriers)

Approximate carrier counts so breakpoints are reachable. Final assignment lives
in `champion_roster.md`; this is the budget it is balanced against.

| Trait | Family | Target carriers | Notes |
|---|---|---|---|
| Beast | Kinship | ~15 | The default land animal; spread across all weathers. |
| Spirit | Kinship | ~13 | Mist-heavy; every Tier-10 is a Spirit. |
| Skyborn | Kinship | ~9 | Birds; tempo-leaning weathers. |
| Tidekin | Kinship | ~8 | Rain-heavy; the heal anchor. |
| Scaled | Kinship | ~8 | Reptiles; the defensive core. |
| Swarm | Kinship | ~7 | Insects; cheap, wide, expendable. |
| Hunter | Calling | ~9 | All Marksman subtypes. |
| Mystic | Calling | ~9 | All Mage subtypes. |
| Guardian | Calling | ~9 | All Tank subtypes. |
| Bruiser | Calling | ~8 | STR frontline + Tank/DMG hybrids. |
| Skirmisher | Calling | ~8 | Warrior subtypes. |
| Stalker | Calling | ~7 | Assassin subtypes. |
| Warden | Calling | ~7 | Shield/Buff supports. |
| Channeler | Calling | ~7 | Cast-cycle hybrids + casters. |
| Trickster | Calling | ~6 | Debuff supports. |
| Mender | Calling | ~6 | Heal supports. |
| Packmate | Calling | ~8 | Low-tier fillers (T1–3). |
| Primordial | Calling | 6 | Exactly one per weather (the Tier-10s). |

---

## 5. Open questions

- **Breakpoint values vs. set size.** With a ~3-champion starting board and a
  board cap that climbs to 10 (T22 Tempest), @6 traits only matter very late.
  Confirm whether some traits should breakpoint at 2/3/4 instead of 2/4/6.
- **Two-Kinship hybrids.** Tier-10s and a few Tier-7 hybrids could carry two
  Kinships (TFT does this). Currently every champion has exactly one; revisit if
  draft flexibility feels thin.
- **Emblem scarcity.** Six Kinship emblems exist; whether all six are equally
  craftable or some are challenge/boss drops is an economy call (`D.12`).
- **Primordial @3.** Fielding three Tier-10s is extremely rare — confirm the @3
  bonus is worth authoring, or cap Primordial at @2.
- **Enemy tags.** The exact tag vocabulary enemies carry for quest-augment
  matching is unspecified — see `augment_catalog.md` §6 (quest augments).
