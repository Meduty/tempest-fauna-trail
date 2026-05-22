# Item Catalog

The item system is a near-direct port of TFT's: **components** are the atoms,
two components **combine** into a finished item, **emblems** grant a Kinship, and
a handful of **special items** act on the run rather than on combat. Items are
acquired from `REWARD` drops, `SUPPLY` picks, and the prep shop, then equipped
onto champion pieces (3 slots per piece).

**Status:** first-pass design. Names and one-line effect *concepts* only — no
stat values, no proc rates, no kit implementation. The substrate that runs all
of this is `effect_systems_design.md` §8 (items as `EffectBundle` factories,
recipe map, special-item run-actions).

### Reconciliation with the effect-systems sketch

`effect_systems_design.md` §8.2 sketches **6** components and notes "15 combined
items" — that is exactly `C(6,2) = 15`, the distinct pairs of a 6-component set,
and its item *names* there (`rapidfire_cannon`, `guinsoo`, `archangels`) are
explicitly TFT placeholders. This catalog **extends that sketch to 8
components**, adding an **Armor** and a **Crit** component so item itemization
covers every combat stat the engine actually has (`combat_system_proposal.md`
§4.2). Eight components yield a `C(8,2) = 28` cross-pair matrix plus 8
same-component recipes — **36 combined items**. Shipping a smaller MVP subset is
fine; §3 marks a suggested core cut.

---

## 1. Base components (8)

The atoms — primal relics shed by the living world. A component can be equipped
raw (it just grants its stat) or combined. Each grants one combat stat.

| Component | Grants | Flavour |
|---|---|---|
| **Fang** | Strength | A predator's tooth, still sharp. |
| **Talon** | Attack Speed | A raptor's claw — quick, light. |
| **Heartseed** | Intelligence | A seed that remembers the whole forest. |
| **Springtear** | Mana (start / cost) | A drop of the first spring, never dry. |
| **Old Hide** | Health | Thick weatherworn pelt. |
| **Stoneplate** | Armor | A shard of mountain bedrock. |
| **Wardpelt** | Resistance | Fur that turns aside spellfire. |
| **Keen Claw** | Crit Chance | A claw honed to one perfect edge. |

---

## 2. Combined items (36)

Two components → one finished item (`effect_systems_design.md` §8.3, the
`RECIPE_MAP`). The full recipe matrix follows. Each cell is the item; the
diagonal is the same-component recipes.

### 2.1 Same-component recipes (8 — the "signature" items)

| Recipe | Item | Concept |
|---|---|---|
| Fang + Fang | **Apex Fang** | Strength; gains permanent bonus Strength on every takedown. |
| Talon + Talon | **Tempest Talons** | Attack Speed; AS keeps ramping for every auto landed this combat. |
| Heartseed + Heartseed | **Worldroot Bloom** | A large flat Intelligence spike — the caster's payoff item. |
| Springtear + Springtear | **Deepwell** | After its first cast, the holder refunds a big share of mana on every cast. |
| Old Hide + Old Hide | **Mammoth Hide** | Huge Health; regenerates steadily while the holder has not taken damage recently. |
| Stoneplate + Stoneplate | **Bramble Carapace** | Armor; when hit in melee, deals splash magic damage and cuts the attacker's healing. |
| Wardpelt + Wardpelt | **Mistward Shroud** | Resistance; the holder regenerates a share of max HP each round. |
| Keen Claw + Keen Claw | **Perfect Predator** | Crit Chance, and critical hits deal extra damage. |

### 2.2 Cross-component recipes (28)

| Recipe | Item | Concept |
|---|---|---|
| Fang + Talon | **Huntress Talon** | STR + AS; autos apply a stacking bleed that ticks over time. |
| Fang + Heartseed | **Bloodthorn Briar** | STR + INT; the holder heals for a share of all damage it deals (auto *and* ability). |
| Fang + Springtear | **Relentless Spear** | STR + mana; every auto grants bonus mana, so an auto-attacker casts often. |
| Fang + Old Hide | **Titanbone Charm** | STR + HP; stacks STR as the holder attacks and is attacked, with a defensive payoff at full stacks. |
| Fang + Stoneplate | **Beastheart Gauntlet** | STR + Armor; the first time the holder drops low, it gains a large shield. |
| Fang + Wardpelt | **Twinclaw Pact** | STR + RES; the holder alternates — one strike deals bonus damage, the next heals it. |
| Fang + Keen Claw | **Giantsbane** | STR + Crit; bonus damage scaling with the target's maximum HP. |
| Talon + Heartseed | **Wildfury Lash** | AS + INT; each auto stacks Attack Speed, and at a threshold the next auto also triggers a cast. |
| Talon + Springtear | **Stormscale Quiver** | AS + mana; every few autos discharge a chain of lightning to nearby enemies. |
| Talon + Old Hide | **Quickpelt Harness** | AS + HP; the first time the holder is stunned, it cleanses and is briefly CC-immune. |
| Talon + Stoneplate | **Sundertalon** | AS + Armor; the holder's autos shred the target's Armor. |
| Talon + Wardpelt | **Splitwind Talons** | AS + RES; the holder's autos also strike a second nearby enemy at reduced damage. |
| Talon + Keen Claw | **Stalkerclaw** | AS + Crit; the clean auto-attack crit-carry stat stick. |
| Heartseed + Springtear | **Everbloom Staff** | INT + mana; the holder's Intelligence climbs steadily for every tick it stays alive. |
| Heartseed + Old Hide | **Witherbloom Censer** | INT + HP; the holder's damage plants a burning rot that also cuts the target's healing. |
| Heartseed + Stoneplate | **Stoneward Idol** | INT + Armor; the durable backline-caster anchor. |
| Heartseed + Wardpelt | **Stormglass Totem** | INT + RES; when a nearby enemy casts, the holder zaps it. |
| Heartseed + Keen Claw | **Spellfang Crown** | INT + Crit; **unlocks `ability_can_crit`** — the holder's abilities can now critically strike. |
| Springtear + Old Hide | **Sapwood Aegis** | mana + HP; shields the holder at combat start; when the shield breaks it releases a burst of ability power. |
| Springtear + Stoneplate | **Warden's Dewstone** | mana + Armor; a defensive support-caster anchor. |
| Springtear + Wardpelt | **Seasonward Charm** | mana + RES; adapts — gains extra defense against whichever damage type recently hurt the holder most. |
| Springtear + Keen Claw | **Dewclaw Fetish** | mana + Crit; a crit item for a cast-cycling carry. |
| Old Hide + Stoneplate | **Living Bulwark** | HP + Armor; the plain, excellent frontline brick. |
| Old Hide + Wardpelt | **Spiritbark Hide** | HP + RES; the anti-magic frontline brick. |
| Old Hide + Keen Claw | **Gorehide Wrap** | HP + Crit; lets a fragile crit-carry survive the frontline. |
| Stoneplate + Wardpelt | **Greatward Carapace** | Armor + RES; the holder's defenses scale with the number of enemies still alive. |
| Stoneplate + Keen Claw | **Edge of Stone** | Armor + Crit; a bruiser-carry hybrid. |
| Wardpelt + Keen Claw | **Hexward Claw** | RES + Crit; a crit item that survives magic burst. |

---

## 3. Suggested MVP core cut

If the build needs a smaller starting set, ship these **16** first — full stat
coverage, every archetype served, the showcase mechanics present:

> Apex Fang · Tempest Talons · Worldroot Bloom · Deepwell · Mammoth Hide ·
> Bramble Carapace · Mistward Shroud · Perfect Predator · Bloodthorn Briar ·
> Wildfury Lash · Everbloom Staff · Witherbloom Censer · Stormglass Totem ·
> Spellfang Crown · Living Bulwark · Splitwind Talons.

The remaining 20 are pure content extension — no new systems, just more
`RECIPE_MAP` entries and factories.

---

## 4. Emblems (6)

An emblem makes its wearer count toward a **Kinship** they do not natively have
(`trait_catalog.md` §1, `effect_systems_design.md` §7.3). One emblem per
Kinship. Each is crafted by combining a **Spirit Gem** (§5) with one base
component; the component chosen also flavours the small stat the emblem grants.

| Emblem | Grants Kinship | Note |
|---|---|---|
| **Beast Emblem** | Beast | The most common emblem — Beast is the backbone Kinship. |
| **Skyborn Emblem** | Skyborn | Lets a grounded carry join a tempo board. |
| **Scaled Emblem** | Scaled | Splashes the weather-proofing trait onto a key piece. |
| **Tidekin Emblem** | Tidekin | Bolts the heal-anchor synergy onto a non-aquatic core. |
| **Swarm Emblem** | Swarm | Pads a wide board toward its hard-to-reach breakpoint. |
| **Spirit Emblem** | Spirit | Brings a champion into the ability-driven Spirit synergy. |

---

## 5. Special items (6)

Special items never enter combat — they have **no `EffectBundle`** and act on
`Run` state from the map/prep layer (`effect_systems_design.md` §8.4,
run-actions). Combat only ever sees their *result*.

| Item | Acts on | Concept |
|---|---|---|
| **Wildwood Reforging Stone** | a combined item | Swap one of the item's two components for a random different one, then recombine. |
| **Unbinding Totem** | a champion | Strip every item off the piece and return them to the bench, decomposed to base components. |
| **Echo Acorn** | a champion | Add a fresh copy of the chosen champion to the bench (feeds levelling — `t22_meta_progression_plan.md` §4). |
| **Spirit Gem** | a component | The emblem-maker — combine with any base component to craft that emblem's Kinship (§4). |
| **Glimmerdust** | a combined item | Upgrade a finished item into a stronger **Heartwood** version (the catalog's "radiant" tier). |
| **Reclaimer's Cache** | the bench | Salvage spare base components into Amber — an economy valve for dead components. |

---

## 6. Open questions

- **Item slots.** Adopt TFT's 3 slots per piece; enforced in
  `loadout.compile_loadout` (`effect_systems_design.md` §14).
- **Component drop economy.** How components vs. finished items vs. emblems
  weight in `REWARD` drop tables (`SPEC D.12`).
- **Heartwood / radiant tier.** Whether Glimmerdust upgrades are full content
  (36 upgraded variants) or a small curated set.
- **Same-component recipes vs. the §8.1 table.** The effect doc's §8.1 table
  budgets "15 combined" — that table should be updated to "36 (8-component
  matrix)" or annotated to point here as the authoritative content count.
- **Special-item acquisition.** Whether special items are shop-only, drop-only,
  or augment-granted (`augment_catalog.md` §5 grant augments).
- **Enemy items.** Standard wave enemies carry no items; whether bosses are an
  exception is open (`enemy_roster.md`, `boss_roster.md` §1).
