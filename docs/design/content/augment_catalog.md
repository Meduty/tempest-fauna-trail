# Augment Catalog

Augments are a near-direct port of TFT's: at each `AUGMENT` node the player picks
**1 of 3** offered, run-long modifiers that bend a whole team's identity. The
system is intentionally game-changing — augments are where a run decides what it
*is*.

**Status:** first-pass design — ~50 augments across 4 qualities. Names, quality,
scope, and one-line effect *concepts* only — no stat values, no proc rates. The
substrate that runs all of this is `effect_systems_design.md` §9 (augments as
`PIECE` / `TEAM` / `RUN`-scoped handlers, plus quest trackers); offers and the
quality-weight curve are `t22_meta_progression_plan.md` §2.

## Design rules

- **4 qualities** — `Common · Rare · Epic · Prismatic`. Quality weights shift
  toward the higher tiers in later stages.
- **3 scopes** (`effect_systems_design.md` §9.1):
  `TEAM` (bundle to every champion) · `PIECE` (bundle to specific/filtered
  champions) · `RUN` (mutates `Run` state, no combat bundle). **Quest** augments
  are `RUN`-scope with a persistent tracker that pays out when its goal is met.
- **One reroll** per `AUGMENT` node re-rolls all 3 offers.
- **Lean.** These augments deliberately reach into systems unique to this game —
  the live weather, the predator/prey ring, the tick clock, the Tempest board
  cap, and the "rising up" run arc — so augments feel like *this* game, not a
  generic stat shop. Where an augment just grants stats, that is by design: the
  Common tier should be safe and legible.

---

## 1. Common augments

Safe, legible, low-variance — stat packs and small economy. Always a fine pick,
never a run-definer.

| Augment | Scope | Effect concept |
|---|---|---|
| **Thicker Hides** | Team | Allies gain Health. |
| **Sharpened Fangs** | Team | Allies gain Strength. |
| **Quick Wits** | Team | Allies gain Intelligence. |
| **Fleetfoot** | Team | Allies gain Move Speed — the team closes and repositions faster. |
| **Pack Instinct** | Team | Allies gain a small amount of every combat stat. |
| **Second Wind** | Team | Allies regenerate a trickle of Health each round. |
| **Opening Howl** | Team | Allies gain a burst of Attack Speed for the first round (600 ticks) only. |
| **Trail Rations** | Run | Your champions start each fight with partial mana for the rest of the run. |
| **Forage** | Run | Immediately gain two random base components. |
| **Amber Vein** | Run | Immediately gain a lump of Amber. |
| **Scout's Pay** | Run | Gain bonus Amber after each of the next several fights. |
| **Salvage Rights** | Run | Selling a champion recovers extra Amber for the rest of the run. |
| **Prospector** *(quest)* | Run | Bank a target amount of Amber at once → reward: a free component. |

---

## 2. Rare augments

Conditional and directional — weather payoffs, light trait support, the first
build-shaping picks.

| Augment | Scope | Effect concept |
|---|---|---|
| **Stormchaser's Pact** | Team | Allies whose affinity *hunts* the live node weather deal bonus damage (amplifies their Affinity Clash edge). |
| **Stubborn Roots** | Team | Allies that are *prey* to the live weather ignore the Weather Favor stat debuff. |
| **Slow Burn** | Team | Allies gain stacking power every few hundred ticks they stay alive — rewards surviving the opening. |
| **Adrenal Glands** | Team | Each champion's first cast of every combat is empowered. |
| **Glass Fang** | Team | Allies gain large Strength and Intelligence but lose some Health. |
| **First Blood** | Team | The first enemy your team kills each fight grants the whole team a short power surge. |
| **Kinship Crest** | Run | Choose a Kinship — your board counts as +1 toward it for the rest of the run. |
| **Calling Crest** | Run | Choose a Calling — your board counts as +1 toward it for the rest of the run. |
| **Sharpshooter** | Piece | Hunter champions gain Attack Range. |
| **Phalanx Drill** | Piece | Guardian champions raise their Threat and briefly taunt on cast. |
| **Component Stipend** | Run | Gain a chosen base component, plus one free augment reroll banked for later. |
| **Tempest Surge** | Run | Immediately gain a chunk of Tempest — the board cap climbs sooner. |
| **Stormbound Trail** *(quest)* | Run | Win a target number of fights in non-`CLEAR` weather → reward: a Kinship emblem. |

---

## 3. Epic augments

Strong, identity-defining — archetype power spikes and the system build-arounds.

| Augment | Scope | Effect concept |
|---|---|---|
| **Apex Predators** | Team | The team's Affinity Clash predator damage multipliers are amplified — you hit your prey markedly harder. |
| **Eye of the Storm** | Team | At combat start the node weather's Weather Favor buff is applied as the affinity that suits the *most* of your team. |
| **Doldrums Blessing** | Team | While the node weather is `CLEAR` (inert), the whole team gains a large stat pack — turns dead weather into an upside. |
| **Built Different** | Piece | Champions with no *active* Kinship or Calling breakpoint gain large stats — rewards a no-synergy board. |
| **Living Tide** | Team | Allies heal for a share of all damage they deal. |
| **Overclock** | Team | Allies' action and movement meters fill faster for the opening rounds, then normalize. |
| **Hexproof Pack** | Team | The first crowd-control effect on each champion each combat is ignored. |
| **Ambush** | Piece | Stalker champions begin combat repositioned into the enemy backline. |
| **Twin Fang** | Piece | A chosen champion gains a second active slot running a copy of its ability — its own mana flurry (`effect_systems_design.md` §6.5). |
| **Pack Tactics** | Team | Champions adjacent to an ally deal bonus damage — rewards tight formation. |
| **Kinship Crown** | Run | Choose a Kinship — your board counts as +2 toward it (that Kinship only). |
| **Emblem of the Wild** | Run | Gain a Spirit Gem and a chosen component — a free emblem path (`item_catalog.md` §4). |
| **Bloodless Victory** *(quest)* | Run | Win a target number of fights with no champion deaths → reward: a special item. |

---

## 4. Prismatic augments

Game-warping, run-defining. A Prismatic augment should be the thing a player
remembers about the run.

| Augment | Scope | Effect concept |
|---|---|---|
| **The Uprising** | Team | The team gains a power pack that *grows* with every fight already won this run — a run-long ramp, the "rising up" payoff. |
| **One With the Sky** | Team | Every champion's affinity is treated as the live node weather each fight — you are never prey, never debuffed by weather. |
| **Heart of the Storm** | Team | At the start of each round the live weather shifts one step along the predator/prey ring in your favour. |
| **Apex Instinct** | Team | Abilities can critically strike team-wide (`ability_can_crit`), and critical damage is amplified. |
| **Endless Swarm** | Team | When any champion dies it leaves a fighting echo of itself on its tile (board-wide on-death spawn). |
| **Worldroot Crown** | Run | Your board counts as +1 toward *every* Kinship — one breakpoint of all six. |
| **Sanctuary** | Team | The first champion that would die each fight is instead revived once at low Health. |
| **Living World** | Team | The boss map effect benefits your team instead of harming it — ley cells, spawn rifts, and hazard tiles flip to your side. |
| **Primordial Bond** | Piece | Your Tier-10 Primordial gains its `@2` Primordial breakpoint for free and a once-per-combat second wind. |
| **Threefold Bloom** | Piece | Your three highest-Tier champions each gain a free slot's worth of stats. |
| **Tempest Ascendant** | Run | Immediately raise the board cap by two ranks (`t22_meta_progression_plan.md` §5). |
| **The Long Hunt** *(quest)* | Run | Land the killing blow on each of the six stage bosses' phase-2 beasts → reward: a Prismatic-tier payout. |

---

## 5. Augment categories (cross-cutting)

The same ~50 augments, grouped by what system they lean on — a designer's view
for balancing offer pools.

- **Stat packs** — Thicker Hides, Sharpened Fangs, Quick Wits, Fleetfoot, Pack
  Instinct, Glass Fang. *Legible filler; weight heavy at Common.*
- **Weather** — Stormchaser's Pact, Stubborn Roots, Apex Predators, Eye of the
  Storm, Doldrums Blessing, One With the Sky, Heart of the Storm. *The
  game's signature lever — every quality has one.*
- **Tick / time** — Slow Burn, Opening Howl, Adrenal Glands, Overclock, The
  Uprising. *Reward surviving, or spiking, across the tick clock.*
- **Trait** — Kinship Crest, Calling Crest, Kinship Crown, Worldroot Crown,
  Built Different, Emblem of the Wild. *Bend the synergy puzzle.*
- **Archetype** — Sharpshooter, Phalanx Drill, Ambush, Pack Tactics, Twin Fang,
  Primordial Bond, Threefold Bloom. *Power-spike a way of fighting.*
- **Economy / meta** — Forage, Amber Vein, Scout's Pay, Salvage Rights, Trail
  Rations, Component Stipend, Tempest Surge, Tempest Ascendant. *`RUN`-scope;
  feed the Amber/Tempest economy (`t22_meta_progression_plan.md`).*
- **Quest** — Prospector, Stormbound Trail, Bloodless Victory, The Long Hunt.
  *`RUN`-scope with a persistent tracker (`effect_systems_design.md` §9.3).*

---

## 6. Open questions

- **Quest-tracker event vocabulary.** Each quest augment names events its
  tracker subscribes to (`on_combat_end`, `on_kill`, …) and any enemy/boss tags
  it matches (`enemy_roster.md` tags, `boss_roster.md` phase-2 beasts). The exact
  tag set is unspecified — pin it down with the quest content.
- **Hero / piece-specific augments.** TFT has champion-specific "hero augments."
  Out of this pass — revisit once the roster's signature champions are locked.
- **Quality-weight curve.** The per-stage Common→Prismatic offer weights are a
  tuning job (`t22_meta_progression_plan.md` §2, `D.11`).
- **Augment count per quality.** ~13/13/13/12 here; TFT ships far more. This is
  the MVP pool — extension is pure content, no new systems.
- **Interaction caps.** Some augments stack dangerously (Apex Instinct + Spellfang
  Crown + Mystic @4 all touch crit). A pass for degenerate combos is needed
  before tuning.
- **Prismatic availability.** Whether Prismatic augments can appear at the
  stage-1 `AUGMENT` node or are gated to later stages.
