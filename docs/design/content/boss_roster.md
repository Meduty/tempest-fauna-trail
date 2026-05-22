# Boss Roster — 6 Stage Bosses

Six bosses, one per stage, each the Tier-10 finale of a continent
(`t4_city_route_plan.md` §3.3). Every boss is a **Reclamation commander** — the
human leadership of the industrial faction (`enemy_roster.md`) — bonded to a
corrupted apex-creature it unleashes when wounded. That bond *is* the two-phase
structure: **Phase 1 is the commander and their war-machine; Phase 2 is the
broken beast set loose.**

**Status:** first-pass design. Identity, two-phase kit *concepts*, map effect,
on-death, and supporting cast only — no stat tuning, no kit implementation. The
2-phase mechanic, the phase hook, and the map-effect dependency are specified in
`t21_challenge_boss_plan.md` §3; the ability substrate in
`effect_systems_design.md` §6.6 (boss phase hook).

---

## 1. Shared boss rules

### 1.1 Fixed affinity per stage — design decision

Affinity is a **stage property**: each of the six stages has **one authored
affinity, fixed for the whole game** and known to the player from the start of
the run. A stage's boss takes that affinity — and so does the stage's challenge
encounter (`t21_challenge_boss_plan.md` §2). A boss's affinity drives **both
phases**; the phase-2 beast always shares the commander's element.

> **This supersedes the live-affinity rule in `t21_challenge_boss_plan.md` §3**,
> *and* replaces the separate challenge-weather table in T21 §2. One stage →
> one affinity, used by every authored encounter in the stage. T21 §2/§3 and
> `SPEC D.2` should be synced to this section.

**Stage affinities** — every `WeatherState` used exactly once:

| Stage | Continent | City | Affinity | Fit |
|---|---|---|---|---|
| 1 | Europe | Vienna | **Clear** | The on-ramp. `CLEAR` is inert in both weather systems, so stage 1 plays with weather muted — the player learns the base game before weather turns on at stage 2. |
| 2 | Africa | Cairo | **Mist** | Desert sandstorm and dust-haze (the OpenWeather *atmosphere* band — sand, dust, haze, smoke — maps to `MIST`). |
| 3 | Asia | Tokyo | **Thunder** | Japan's typhoon season — monsoon storms. |
| 4 | Oceania | Sydney | **Cloudy** | Coastal marine-layer overcast. The softest fit — forced once Africa takes `MIST` and North America takes `SNOW`. |
| 5 | South America | Rio | **Rain** | Amazon rainforest and monsoon (`SPEC` stage-5 theme: "Monsoon walkers"). |
| 6 | North America | New York | **Snow** | NYC's hard winters — and the finale as the machine's frozen, silent, dead world. |

**Why fixed, not live:**

- **Authored identity.** A boss is a hand-built set-piece — one kit, one beast,
  one arena — that the player learns and beats. Live affinity would re-roll the
  encounter's weather math every fight; fixed affinity lets each boss stay the
  thing it was designed to be.
- **Consistency.** Challenges already use a fixed affinity per stage; folding
  bosses into the *same* per-stage table gives one coherent rule for every
  authored encounter.
- **Theme.** The phase-2 beast always matches the boss's element — Crège's
  Leviathan is always Rain, Strand's Caged Storm always Thunder. A live-affinity
  rule produced absurdities (a "Leviathan" in Snow weather).
- **Variance.** Under a live-affinity rule a boss's affinity *equalled* the
  weather, so Weather Favor *always* gave it the strong self-buff — a permanent,
  varianceless tax. With fixed affinity the live weather sometimes buffs and
  **sometimes debuffs** the boss (§1.2) — a real swing the player can read and
  exploit.

Rejected alternatives: **six bosses per stage picked by weather** (36 bosses —
scope death, identity diluted across variants); **per-affinity kit variants of
one boss** (muddies a single learnable kit, six times the tuning).

### 1.2 The live weather still decides the fight — three layers

Stage affinity is fixed; the **live node weather** is the run's variable. They
interact in three layers, all readable in advance because the stage's affinity
is known from the start:

1. **Boss vs. weather (Weather Favor).** The live weather resolves
   `combat_modifier(boss.affinity, weather)`:
   - weather **==** boss affinity → boss takes the **strong self-buff** (home turf);
   - weather is **hunted by** the boss affinity → boss takes a medium/weak buff;
   - weather **hunts** the boss affinity → boss is **debuffed** — the **lucky
     strike window**, a fight to rush;
   - weather is `CLEAR` → boss is inert from weather (neutral).
   A `Clear`-affinity boss (Holloway, stage 1) is inert in *every* weather and
   carries a flat compensating stat bump instead — the deliberate weather-neutral
   tutorial boss.

2. **The player's prep fork.** Knowing the stage affinity, the player chooses
   what to build:
   - **Weather-fit** — champions whose affinity suits the *live node weather*,
     for their own Weather Favor self-buff; or
   - **Type-advantage** — champions whose affinity **hunts the boss's fixed
     affinity**, landing Affinity Clash `1.10×` on the boss every hit *and* taking
     only `0.90×` back from it.
   These often pull apart: the predator of the boss may itself be prey to the
   live weather. That tension is the boss-prep minigame.

3. **Luck.** When the live weather already debuffs the boss (layer 1), the
   player can skip the mind-games and just bring power.

### 1.3 Two phases

At **50% HP** the boss enters Phase 2 — it gains **+1 active and +1 passive**
ability (the unleashed-beast kit). The transition fires once, deterministically,
via the phase hook (`effect_systems_design.md` §6.6).

### 1.4 One map effect — fixed per stage affinity

Each boss has **one authored arena**, fixed by its stage affinity — not
re-rolled by live weather. The effect each affinity contributes is the T21
table; each boss is locked to its own:

| Boss (affinity) | Map effect | Authored as |
|---|---|---|
| Holloway (Clear) | **Spawn rifts** — cells periodically open and spawn adds | Furnace scrap-vents coughing up scrap-imp adds |
| Vance (Mist) | **Fog** — pieces beyond short range are untargetable | The dust-storm her extraction raised — blowing sand |
| Strand (Thunder) | **Hazard tiles** — cells deal per-tick damage to occupants | Live capture-grid cells — the marquee hazard fight |
| Vossberg (Cloudy) | **Ley cells** — contested tiles buff whoever holds them | Smouldering scorched ground — thermals to fight over |
| Crège (Rain) | **Flood lanes** — a board column floods impassable, shifts per round | The dredge-wake tearing the board open |
| Iron Emperor (Snow) | **Collapsing arena** — edge rows disable over the fight | The World-Engine freezing the board solid, edges inward |

Map effects require board-cell modifier support — a combat-engine extension that
is not yet built (`SPEC D.3`).

### 1.5 Supporting cast & scaling

A boss never fights alone — it arrives with a curated squad drawn from lower
tiers of `enemy_roster.md`, so the player juggles boss mechanics while clearing
trash. Recommended: boss stats scale with the player's current stage so the
encounter stays sharp across a long run (`enemy_roster.md` open question).

---

## 2. Stage 1 — Europe / Vienna · Foundry-Lord Holloway

*The first wall. A smoke-blackened industrialist who fences the green country and feeds
them to the furnaces.* Affinity: **Clear** — the weather-neutral tutorial boss.
Stage 1 plays with the weather systems muted, so the player meets a clean,
honest fight before weather turns on at stage 2; Holloway is inert in both
weather systems and carries a flat compensating stat bump instead. There is no
lucky-weather window and no type-advantage line against him — he is a pure
out-fight-him check, and his all-iron Furnace-Walker does not care what the sky
does. Tags: `human, machine` → Phase 2 `corrupted, machine`.

- **Identity.** Holloway fights from inside a piloted **Furnace-Walker**, a
  squat ironclad that vents scalding steam. Slow, armored, relentless.
- **Phase 1 — active: *Pressure Vent*** — a ring of steam around the Walker,
  STR-scaled AOE damage and a brief slow to everything adjacent.
- **Phase 1 — passive: *Stoke the Fires*** — the Walker gains Armor and
  Resistance every round it survives; the longer the fight, the harder it gets.
- **Phase 2 — the Slag unleashed.** At 50% HP the Walker's core ruptures and a
  **Quarried Colossus** — a furnace-fed stone-beast chained inside the chassis —
  tears free, wearing the wreck as armor.
  - **+active: *Magma Heave*** — hurls a gout of molten slag in a line, leaving
    burning tiles that deal damage over several ticks.
  - **+passive: *Cinder Husk*** — reflects a share of every hit it takes back as
    burn damage.
- **Map effect — spawn rifts.** The Furnace-Walker's scrap-vents periodically
  open and cough up scrap-imp adds into the fight.
- **On death.** The Walker's boiler bursts — a final delayed AOE detonation
  centered on the wreck a few ticks after death. Stand clear.
- **Supporting cast.** 2× Heavy Knight, 2× Steam Engineer, 4× Conscript.
- **Feel.** A patient endurance check, and the player's first boss — weather off
  the table, the lesson is simply that bosses *grow*: kill it before *Stoke the
  Fires* makes it unkillable.

---

## 3. Stage 2 — Africa / Cairo · Solar Overseer Vance

*She drank the desert dry. Vance ran the great mirror-fields until the land had
nothing left to give — and now it is only dust, and the dust never settles.*
Affinity: **Mist** — not fog but the permanent sandstorm her extraction raised.
Tags: `human` → Phase 2 `corrupted, beast`.

- **Identity.** Vance commands from a **Heliostat Carriage** — a mobile array of
  focusing mirrors. She does not brawl; she *aims*, picking targets out of the
  blowing dust.
- **Phase 1 — active: *Focusing Lens*** — a slow-tracking beam that locks the
  highest-Threat enemy and burns it for escalating INT-scaled damage the longer
  the lock holds.
- **Phase 1 — passive: *Glare*** — the dust she stirs fouls vision; enemies that
  stay at long range from the Carriage have their accuracy spoiled (a chance for
  autos to miss). Vance punishes the backline for hanging back.
- **Phase 2 — the Husk of the Sun-Lion.** At 50% HP, Vance opens the array's
  reliquary and looses the **Sun-Husk** — a great savanna lion drained to a
  hollow, light-leaking shell, staggering through the haze, kept alive only to
  be a weapon.
  - **+active: *Sunflare Pounce*** — a blink onto the lowest-HP enemy and a
    light-burst execute that scales with how low their HP already is.
  - **+passive: *Drought Aura*** — enemies near the Sun-Husk regenerate mana
    more slowly and heal for less.
- **Map effect — fog.** The dust-storm — pieces beyond a short range are
  untargetable, which bites hardest against Vance's own long-range beam: close
  the gap or fight half-blind.
- **On death.** The Sun-Husk collapses into a fading mote of light that briefly
  *heals* the player's team — a held breath of the lion freed at last.
- **Supporting cast.** 2× Battlemage, 1× Company Captain, 4× Picket.
- **Feel.** A positioning puzzle in low visibility — break line-of-aim, deny the
  lock, and reach the Sun-Husk before it executes your carry.

---

## 4. Stage 3 — Asia / Tokyo · Grid-Director Strand

*The man who put the sky on a meter. Strand's towers harvest the storm itself.*
Affinity: **Thunder**. Tags: `human, machine` → Phase 2 `corrupted, spirit`.

- **Identity.** Strand fights wired into a **Capture-Grid Throne**, drawing
  power from the city's lightning-rigs. Fast, fragile, overwhelming.
- **Phase 1 — active: *Arc Cascade*** — chain lightning that leaps across the
  enemy line, INT-scaled, weaker per jump but jumping to *every* valid target.
- **Phase 1 — passive: *Overcharged*** — every few hundred ticks Strand
  discharges, gaining a burst of Attack Speed; his tempo climbs in waves.
- **Phase 2 — the Caged Storm.** At 50% HP the grid fails and the **Caged
  Storm** — a storm-elemental spirit bled for years into the rigs — bursts its
  cage and folds Strand into its body.
  - **+active: *Thunderhead*** — a storm parks over the board and strikes random
    tiles with delayed lightning; telegraphed bolts the player can step out of.
  - **+passive: *Stormform*** — the boss cycles between a **discharged** state
    (vulnerable, normal) and a **charged** state (briefly untargetable, building
    power). Damage windows are real but narrow.
- **Map effect — hazard tiles.** Live capture-grid cells deal per-tick damage to
  whatever stands on them — the game's marquee version of the hazard fight.
- **On death.** A final uncontrolled lightning strike hits the boss's own tile,
  damaging anything adjacent — the storm's last, free swing.
- **Supporting cast.** 2× Arcanist, 1× Riflemaster, 3× Capture-Rig Wolf.
- **Feel.** A tempo race. Punish the discharged windows; survive the charged
  ones. The first boss that *hides* from you.

---

## 5. Stage 4 — Oceania / Sydney · Clearance-Marshal Vossberg

*He calls it making room. The bush burns where Vossberg's columns pass, and the
smoke has turned the sky to a low brown ceiling that never lifts.* Affinity:
**Cloudy** — the permanent ash-overcast of a burning continent. Tags:
`human, machine` → Phase 2 `corrupted, beast`.

- **Identity.** Vossberg leads a **Burn-Column** — a flame-rig escort. He is a
  blunt, aggressive frontline brawler who wants to be in your face.
- **Phase 1 — active: *Scorched Advance*** — Vossberg charges the farthest enemy,
  STR-scaled impact and a knockback, leaving a trail of burning tiles behind the
  charge path.
- **Phase 1 — passive: *No Quarter*** — Vossberg deals escalating bonus damage to
  any enemy below half HP; he closes out wounded pieces fast.
- **Phase 2 — the Pyre-Maw.** At 50% HP the Burn-Column's containment fails and
  the **Pyre-Maw** — a great marsupial predator driven feral by fire and pain —
  drags Vossberg onto its back and goes berserk.
  - **+active: *Wildfire Leap*** — a long leap onto the backline, AOE burn on
    landing, and the landing tiles stay alight.
  - **+passive: *Feeding Frenzy*** — every takedown (boss *or* its adds) grants
    the Pyre-Maw stacking Attack Speed for the rest of the fight.
- **Map effect — ley cells.** Smouldering scorched ground: contested hot-spot
  tiles that buff whoever holds them — a positional layer in a fight that
  otherwise just wants to brawl.
- **On death.** The Pyre-Maw's fire gutters out; the burning tiles it left snuff
  in a wave, and the brown ceiling thins — a small mercy for the survivors.
- **Supporting cast.** 1× Lord Commander, 2× Gunslinger, 4× Conscript.
- **Feel.** A pressure fight. Vossberg never stops moving forward; the player who
  turtles loses the board to fire — and the ley cells punish ceding ground.

---

## 6. Stage 5 — South America / Rio · Dredge-Admiral Crège

*She strangles rivers for a living. Crège's dredge-fleet has eaten a delta.*
Affinity: **Rain**. Tags: `human, machine` → Phase 2 `corrupted, beast`.

- **Identity.** Crège fights from the deck of a **Dredge-Barque**, a hull
  bristling with harpoon-rigs and chain-winches. She fights at range and reels
  the player in.
- **Phase 1 — active: *Harpoon Winch*** — fires a chain into the lowest-HP enemy
  and *drags it* across the board to the front rank, STR-scaled damage on the
  pull. Isolates the player's carry.
- **Phase 1 — passive: *Dredged Depths*** — the Barque leaves slowing silt in a
  spreading pool beneath itself; the longer the fight, the wider the bog.
- **Phase 2 — the Leviathan.** At 50% HP the winch-chains snap and the
  **Leviathan of the Deep** — a colossal river-beast the fleet has kept chained
  to its keel for years — rises and takes the Barque under.
  - **+active: *Maelstrom Jaws*** — a board-wide vortex that pulls every enemy
    toward the Leviathan, then a crushing bite on whatever is closest.
  - **+passive: *Drowning Tide*** — every enemy within a few hexes of the
    Leviathan takes a small share of their max HP as damage every tick.
- **Map effect — flood lanes.** The dredge-wake: a board column floods
  impassable and shifts each round, constantly reshaping the lanes the player
  must hold.
- **On death.** The Leviathan sinks and the dredged silt drains away — the board
  clears of slow as the river is, briefly, free.
- **Supporting cast.** 1× Iron Maiden, 2× Cannoneer, 3× Blight Lurker.
- **Feel.** A control fight against forced movement. The player must hold
  formation while the boss spends both phases tearing that formation apart.

---

## 7. Stage 6 — North America / New York · The Iron Emperor

*The architect of all of it. The Iron Emperor founded the Reclamation, and the
Reclamation is the wound.* The grand finale (`SPEC V.7`). Affinity: **Snow** —
not a blizzard but the end-state of the machine: a world drained to iron-cold
silence, the heat-death of nature. Tags: `human, machine` → Phase 2
`corrupted, machine, spirit`.

- **Climax tension.** The fight plays under **live New York weather**. Because
  the stage affinity is fixed at Snow, the live sky decides whether the Emperor
  arrives **strong-buffed** (NYC in Snow, Rain, or Cloudy), **debuffed** and
  vulnerable (NYC in Thunder or Mist), or **untouched** (NYC in Clear) — and the
  player cannot pre-scout the real sky. The run's last decision is a gamble on a
  city's weather forecast: bring weather-fit, bring Thunder/Mist predators to
  hunt the Snow Emperor, or bring raw power and hope for a lucky window.
- **Phase 1 — the World-Engine Throne.** The Emperor fights from the heart of
  the central machine — the engine every other rig feeds.
  - **active: *Decree of Iron*** — targets the player's highest-Threat piece and
    marks it; while marked it takes heavily increased damage from the Emperor
    and his adds. Focus-fire, made into an ability.
  - **passive: *Tribute*** — the Emperor gains damage and damage-reduction for
    each living ally on the board. Phase 1 *wants* its supporting cast alive.
- **Phase 2 — the Engine's Heart.** At 50% HP the Emperor merges with the
  World-Engine itself, drawing every corrupted element the Reclamation ever
  caged — slag, storm, tide, drought — into one amalgam crowned with his throne.
  - **+active: *Reclamation*** — channels for a stretch of ticks, then a
    board-wide detonation; the channel can be raced but not interrupted. The
    signature "beat the timer" finale moment.
  - **+passive: *The Wound Spreads*** — in phase 2 the collapsing arena
    accelerates: the board freezes inward faster, the dead world closing on the
    player as the Emperor's HP falls.
- **Map effect — collapsing arena.** The World-Engine freezes the board solid
  from the edges inward; edge rows disable over the fight, and *The Wound
  Spreads* speeds the collapse in phase 2.
- **On death.** The World-Engine goes dark. The corrupted elements it held —
  every caged storm and drowned tide — come apart and *settle*, no longer bound.
  The run's victory state. A closing beat: a freed corrupted-creature or two may
  linger on the board, no longer hostile.
- **Supporting cast.** 2× Archmagus Imperator, 2× Hierarch, 4× T1–3 Conscripts —
  thematic context per `enemy_roster.md` (a boss appears with elites + trash).
- **Feel.** Every lesson at once: he grows like Holloway, focus-fires like
  Vance, hides his windows like Strand, pressures like Vossberg, controls the
  board like Crège — and then the floor itself becomes the threat.

---

## 8. Open questions

- **T21 / SPEC sync.** `t21_challenge_boss_plan.md` carries two stale rules: §3's
  "affinity == live node weather" + live-weather map-effect table, and §2's
  separate challenge-weather table (`1=Clear, 2=Cloudy, 3=Mist, 4=Snow, 5=Rain,
  6=Thunder`). Both should be replaced by the single §1.1 stage-affinity table
  here. Note this **moves stage 6 from Thunder to Snow** — T21 §2's "stage 6 is
  always Thunder, the marquee fight" note is dropped. `SPEC D.2` should be synced
  too.
- **Oceania = Cloudy.** The softest affinity fit (§1.1). Alternative considered:
  swap to NYC = Cloudy / Sydney = Snow — rejected because Sydney itself is not
  snowy and a Snow finale in NYC is the stronger image.
- **Map effects need a combat extension.** Board-cell modifiers are an unbuilt
  combat mechanic (`SPEC D.3`). Boss content blocks on it.
- **Channel interaction.** The Iron Emperor's *Reclamation* channel needs a rule
  for what (if anything) can interrupt it — stun? silence? nothing?
- **Boss affinity visibility.** The route map / prep UI must surface each stage's
  fixed affinity well in advance, since the whole prep fork (§1.2) depends on the
  player knowing it.
- **Supporting-cast scaling.** Whether the boss squad scales with stage like the
  boss does, or stays fixed-tier.
- **Difficulty modes.** If the game ships Normal/Hard tiers, do bosses gain a
  third phase, extra adds, or just a stat multiplier?
