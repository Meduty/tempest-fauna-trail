# Trait Catalog — Synergy System

The trait system is a near-direct port of TFT's origin/class synergies, retuned
for a tick-based turn engine. Traits are the player's draft-puzzle layer: every
champion carries trait tags, and fielding enough tag-sharing champions unlocks
**breakpoint bonuses** that reward committed team-building.

**Status:** design — **v2.1 pass** (2026-06-05). Names, breakpoint *concepts*, and
**breakpoint counts** are set here; stat tuning + engine wiring happen in
T.28a/b/c and are sim-validated (T.25). Substrate:
`docs/design/systems/effect_systems_design.md` §7 (traits as `TraitBreakpoint`
lists of `EffectBundle` factories). `champion_roster.md` assigns each champion its
Kinship + Calling(s).

> **§0. v2.1 design decisions (this pass).**
> 1. **Apex = `min(carrier-pool, board-cap)`** for most traits — the top rung
>    means "own (nearly) all carriers and/or commit your whole board." No count
>    can exceed the board cap (each counted champ = one slot, dupes count once,
>    emblem = one substitute carrier), so the apex is a structural
>    "once-in-many-runs, emblem/Amber-assisted" chase. Lower rungs carry the
>    normal game.
> 2. **Many rungs, single-step-leaning, @1 entries.** TFT runs 4–5 breakpoints on
>    real traits and ~⅓ start at a single unit (Set 16: Longshot/Warden/Vanquisher
>    `2/3/4/5`, Darkin `1/2/3`, Yordle `2/4/6/8/10`). We mirror that: single-step
>    *runs* in the body + a jump to the apex chase. **Board cap == rank, starts at
>    1**, so @1 entries are needed for early-game synergy at all.
> 3. **Reachability fixed** — Packmate filled (go-wide, cheap T1–3 secondary);
>    Hunter spread across tiers; Callings (no emblem) apex at native pool.
> 4. **Tier-10 diversified** — one legendary per Kinship (§5). **T10 acquisition
>    is augment-gated**: three **paired** RUN-augments unlock the Primordials in
>    the late shop (T.31; T.28a ships the trait factories ready-but-dormant).
> 5. **Skyborn → Kiters** — the tile-collision idea is gone; Skyborn *kite*
>    (maintain attack-range distance from melee), with melee Skyborn gaining +1
>    Range so they can kite at all. Smart-behaviour guardrails in §7.
> 6. **Low-HP / sustain mechanics are diversified** — exactly **one** true revive
>    (Mender); the others are distinct (threshold decaying-shield "second wind",
>    tidal heal-over-time, low-HP enrage). They stack happily but aren't redundant
>    revive-walls (§4.1).
>
> Cap math + the engine primitives this implies are in §7; scope split (a/b/c) in
> §9; playstyles in §6.

---

## 1. Design rules

- **Three trait families.** Each champion contributes exactly **one Affinity**
  (weather element), exactly **one Kinship** (creature/spirit kind), and **one or
  two Callings** (how it fights). Tier-10 legendaries add **Primordial**.
- **Counting rule.** Breakpoints count **unique champion ids** (`effect_systems_
  design.md` §7.1); counted **at loadout** (pre-combat) from the fielded board.
  Mid-combat spawns/revives never raise a count.
- **Breakpoints — variable shape.** Each trait lists **2–5** thresholds; highest
  cleared applies. Lowest rung = cheap *splash* (often @1–@2); highest = *apex*
  chase (`min(pool, cap)`). Bodies favour **single steps** so a churning player
  always has a next payoff.
- **Emblems — Kinship only, worth one carrier.** Spirit Gem + component → Kinship
  emblem (`item_catalog.md` §4) = one substitute carrier, reaching a Kinship apex
  one native short. **Callings/Affinities have no emblems.**
- **Board cap is the ceiling.** Team size = Tempest rank (T.22), starts at **1**,
  ~8 free / **10** Amber. `@8` ≈ whole free board; `@10` ≈ all-in Amber board.
- **Determinism.** Every effect is RNG-free (cadence counters / geometry) per
  SPEC V.2/V.14.
- **Affinity traits are derived counts**, weather-independent.
- **Enemies** carry trait *tags* as opaque labels (quest-augment matching) but
  never light up breakpoints.

---

## 2. Kinships (origin traits)

Six Kinships, one emblem + one Tier-10 anchor each (§5). The **deep-commit axis**
— emblem-able, apex at pool−1; rewards picking a creature-family and sticking.

### Beast — *fur, blood, stubborn endurance* · pool 14 · **@2 / 3 / 4 / 6 / 8**
The backbone vertical; rewards the long fight (front-load's opposite).
- **@2** — HP + slow regen while alive.
- **@3** — small Strength.
- **@4** — Beasts build stacking Strength every few hundred ticks alive (slow-burn
  ramp; rewards surviving the opening).
- **@6** — the ramp doubles and Beasts heal for a share of damage dealt.
- **@8** *(apex — full board, emblem→7)* — lifesteal+ramp becomes a team aura; a
  Beast below 25% HP **enrages** once (burst of AS + Strength).

### Spirit — *breath, mana, the half-real* · pool 11 · **@2 / 3 / 5 / 8**
The caster vertical.
- **@2** — start with partial mana + Mana Regen.
- **@3** — abilities cost a little less.
- **@5** — untargetable for the opening ~150 ticks; every few casts a Spirit's
  next ability echoes (free, reduced potency).
- **@8** *(apex)* — the echo fires every cast; Spirit abilities pierce
  untargetable/blind gates; team gains an ability-haste pool.

### Skyborn — *wings, height, the kite* · pool 9 · **@1 / 2 / 3 / 5 / 8**
**Kiters** — the only pieces that out-maneuver melee (§7 logic).
- **@1** — Move Speed (a single bird splash).
- **@2** — **Kiting unlocks**: maintain attack-range distance from melee threats
  (smart retreat), and **melee Skyborn gain +1 Attack Range** so they can kite. +
  small Attack Speed.
- **@3** — bonus damage to enemies that currently can't reach them (kite reward).
- **@5** — +1 Attack Range (all Skyborn); melee chasers targeting a Skyborn are
  slowed.
- **@8** *(apex — emblem→7)* — Skyborn attack without losing tempo while
  repositioning (true hit-and-run); team gains Move Speed.

### Scaled — *cold blood, hard plates, weatherproof* · pool 9 · **@2 / 3 / 5 / 8**
The defensive, weather-agnostic core.
- **@2** — Armor + Resistance.
- **@3** — more Armor + Resistance.
- **@5** — immune to the Weather Favor debuff (still take Affinity Clash hits).
- **@8** *(apex — emblem→7)* — Scaled treat *every* node weather as a self-buff
  (strong-tier Weather Favor pack); shrug off the first hard CC each combat.

### Tidekin — *water, sustain, the slow tide* · pool 9 · **@2 / 3 / 5 / 8**
The heal anchor — **tidal regeneration, not death-cheating** (reworked off revive
for variety, §4.1).
- **@2** — Tidekin emit a small periodic heal to themselves.
- **@3** — the heal reaches the lowest-HP ally too.
- **@5** — Tidekin healing and healing they receive is amplified; the periodic
  heal becomes a rolling **team heal-over-time** (the rising tide).
- **@8** *(apex — emblem→7)* — the tide swells: a large scaling team HoT all
  combat; healing also grants a small overheal shield.

### Swarm — *numbers, and what's left behind* · pool 8 · **@3 / 4 / 5 / 6 / 8**
Go-wide — high entry, single-step body (every body matters), apex demands the
whole board.
- **@3** — a dying Swarm leaves a chitin-spawn (weak body; not counted).
- **@4** — Swarm gain small stats per *other* fielded Swarm.
- **@5** — that per-Swarm bonus grows; spawns are stronger.
- **@6** — spawns inherit a fraction of their parent's stats.
- **@8** *(apex — full board, emblem→7)* — spawns can spawn once, and each Swarm
  death briefly buffs the rest — the board never thins.

---

## 3. Affinities (element traits)

Six, one per weather, **10 carriers each**, no emblem, weather-independent counts.
Shape **@2 / 4 / 6 / 8 / 10** — even-step ladder (it's the "background" axis every
champion contributes to) with a **mono-affinity `@10` apex** (entire Amber board
one weather: the prismatic flex).

Naming: **Weather Favor** = node-weather buff/debuff; **Affinity Clash** =
affinity-vs-affinity multiplier. Ids: `trait.affinity.<name>@<2|4|6|8|10>`,
`bundle.affinity.<name>.<minor|moderate|major|greater|mono>`.

| Affinity | Source | @2–@8 (scaling pack) | @10 mono apex |
|---|---|---|---|
| **Sunlit** | Clear | all-around stats | + team on-kill stat snowball |
| **Overcast** | Cloudy | HP + Resistance | + team takes reduced burst damage |
| **Shrouded** | Mist | Move Speed + Threat (+brief untargetable opener from @6) | + longer team untargetable opener |
| **Stormfed** | Rain | Attack Speed + Mana Regen | + team ability-haste |
| **Frostbound** | Snow | Armor + Resistance | + attackers that hit the team are slowed |
| **Galvanized** | Thunder | Strength + Attack Speed | + crits chain a small arc to a neighbour |

---

## 4. Callings (class traits)

Twelve. The **flex / playstyle axis** — **no emblem**, apexes at native pool. Rung
counts/levels vary most here; @1 entries on supports/casters.

| Calling | Pool | Breakpoints | Fantasy & concepts (apex = top rung) |
|---|---|---|---|
| **Hunter** | 8 | **@2 / 4 / 6 / 8** | Ranged carries; spread across tiers. @2 bonus auto dmg · @4 empowered shot every few autos · @6 +Range & shots pierce · **@8** team auto-damage aura + empowered shots cleave. |
| **Mystic** | 8 | **@2 / 3 / 5 / 8** | Mages. @2 +INT · @3 more INT · @5 `ability_can_crit` + casts splash to a neighbour · **@8** casts splash twice + team ability power. |
| **Guardian** | 9 | **@2 / 3 / 4 / 6 / 8** | Frontline shields. @2 self-shield at start · @3/@4 bigger · @6 shield adjacent allies + refresh each round · **@8** shielded Guardians' neighbours take reduced damage (team bastion). |
| **Bruiser** | 8 | **@2 / 4 / 6 / 8** | STR frontline. @2 +HP · @4 +HP & +STR · @6 lifesteal on attacks · **@8** team-wide lifesteal + HP. |
| **Skirmisher** | 8 | **@2 / 3 / 4 / 5 / 8** | Mobile melee ("every hit"). @2 stacking AS on one target · @3/@4/@5 ramp grows + dodge a share of autos + Move Speed · **@8** the AS ramp never decays + extends to the team's melee. |
| **Stalker** | 7 | **@2 / 3 / 5 / 7** | Assassins. @2 **backline target-priority + Move Speed** (no teleport) · @3 more · @5 bonus dmg vs high-HP targets + mana on takedown · **@7** brief untargetable after a takedown. |
| **Channeler** | 7 | **@1 / 2 / 4 / 7** | Cast-spam. @1 +Mana Regen splash · @2 more · @4 every few casts the next ability is free · **@7** first cast each combat triggers twice + team ability-haste. |
| **Warden** | 6 | **@1 / 2 / 4 / 6** | Shield/buff supports. @1 cast shields the lowest-HP ally (splash) · @2/@4 bigger + buffs last longer · **@6** (own all 6) whole-team opening shield. |
| **Trickster** | 6 | **@2 / 3 / 4 / 6** | Debuff/disruption. @2 casts apply slow/wither · @3/@4 +Threat & taunt target on cast · **@6** (own all 6) enemies near a Trickster gain mana slower. |
| **Mender** | 6 | **@1 / 2 / 4 / 6** | Healers — owns the one true **revive** (§4.1). @1 healing amplified (splash) · @2 more · @4 overheal → shield · **@6** (own all 6) the first ally death each combat is **revived** once at low HP. |
| **Packmate** | 8 | **@2 / 3 / 4 / 6 / full-board** | Wide-board; **secondary Calling on cheap T1–3 fillers**. @2/@3/@4 team-wide stats scaling with *number* fielded · @6 large flat pack · **@full-board** *(dynamic apex — count == current Tempest cap)* every champion gets a large flat bonus. The anti-churn payoff. |
| **Primordial** | 6 | **@1 / 2 / 3** | The six Tier-10 legendaries (**augment-gated**, §5). @1 signature mechanic on · @2 big team pack + **second wind** (threshold decaying-shield, §4.1) · @3 *(aspirational)* the team's highest *other* trait counts one tier higher. |

### 4.1 Low-HP / sustain mechanics — diversified (one revive only)
Different traits do different things at the brink, so stacking is clever synergy
rather than redundant revive-walls:
- **Revive (death-save)** — **Mender @6** only. On an ally's first death each
  combat, restore it at low HP. The dramatic one.
- **Second wind (threshold decaying-shield)** — **Primordial @2**. On dropping
  below ~60% HP, gain a ~40%-max-HP shield that decays over ~12 s, once per
  combat. *Reusable primitive*; proactive, not a death-save — burst can still kill
  through it.
- **Tidal heal-over-time** — **Tidekin** (whole ladder). Rolling team regen; keeps
  the board topped up, never cheats death.
- **Enrage** — **Beast @8**. A low-HP Beast bursts AS+Strength once (offense, not a
  save).
- **Barriers** — **Guardian / Warden**. Proactive start/cast shields; unrelated to
  death triggers.

---

## 5. Trait-to-roster map (intended carriers)

Carrier counts **place** each apex (§7). Kinship sums to 60 (one per champion);
Callings sum ~87 (≈27 champions carry a 2nd Calling — Packmate especially, as a
secondary tag).

### Kinships (1 per champion · sums 60)
| Kinship | Pool | Tier-10 anchor | Notes |
|---|---|---|---|
| Beast | 14 | **Mournhollow** (Mist) | Backbone; spread across all weathers. Trimmed from v1's 18. |
| Spirit | 11 | **Aurion** (Clear) | Casters; no longer monopolises T10. |
| Skyborn | 9 | **Aerion** (Thunder) | **Kiters — lean ranged** (kiting needs reach; melee Skyborn rely on the @2 +1 range). |
| Scaled | 9 | **Umbra** (Cloudy) | Reptile/earthen defensive core. +2 from v1. |
| Tidekin | 9 | **Nerei** (Rain) | Heal anchor. +3 from v1. |
| Swarm | 8 | **Borealis** (Snow) | Insects + clustered light-motes. +3 from v1; ≥3 must be T1–3 for the @3 entry. |

### Callings (1–2 per champion · sums ~87)
| Calling | Pool | Notes |
|---|---|---|
| Guardian | 9 | Tank subtypes. |
| Hunter | 8 | Marksmen — **spread T2–T9** (v1 was all T8+). Pairs with Skyborn (ranged birds). |
| Mystic | 8 | Mage subtypes. |
| Bruiser | 8 | STR frontline + hybrids. |
| Skirmisher | 8 | Warrior subtypes. |
| Packmate | 8 | **Cheap T1–3 fillers, secondary Calling.** Spread their *primary* callings. |
| Stalker | 7 | Assassins. Trimmed from v1's 10. |
| Channeler | 7 | Cast-cycle casters. |
| Warden | 6 | Shield/buff supports. |
| Trickster | 6 | Debuff supports. |
| Mender | 6 | Heal supports. |
| Primordial | 6 | The six Tier-10s (one per Kinship). |

### Tier-10 acquisition (augment-gated)
Primordials are **not** in the normal shop. Three **paired** RUN-augments
(authored in T.31) each add **two** Primordials to the late-stage shop tier pool,
paired by Kinship theme. Picking one opens its pair; fielding ≥1 lights
Primordial @1 (@2/@3 stay aspirational — T10s cost 10 Amber + late shop-RNG).
Suggested pairs (overridable):
- **Verdant** — Mournhollow (Beast) + Nerei (Tidekin)
- **Tempest** — Aerion (Skyborn) + Aurion (Spirit)
- **Stoneveil** — Umbra (Scaled) + Borealis (Swarm)

---

## 6. Playstyle archetypes (what the diversity buys)

- **Flex / horizontal.** Splash cheap @1/@2 rungs of 3–4 traits. Reactive, strong
  early and when the draft is unkind. Every trait's lowest rung serves it.
- **Loyalist / one deep vertical.** Climb a 4–5-rung trait all run — a **Kinship**
  (emblem-able, apex at pool−1, Tier-10 anchor as capstone) or a marquee
  **Calling** (Hunter/Mystic) or **Packmate** or a **mono-Affinity** (@10).
- **Churn two-three.** Pair a **go-tall elite** cluster (Primordial via augment,
  the top of Hunter/Mystic) with a **go-wide cheap** cluster (Packmate
  `@full-board` / Swarm `@8`). The wide apexes are the **anti-churn counter** —
  they pay you for *not* selling your cheap board.

Intent: flex = safe default, loyalist = highest ceiling, churn-mix = expressive
middle. No path dominates — every apex presses against the same board cap.

---

## 7. Reachability model + new primitives (why the counts are what they are)

**Board cap over a run** (T.22, free +2 Tempest/fight; **cap == rank, starts 1**):
~1–2 at stage 1, ~3 by stage 1–2, ~4–5 by stage 3, ~6 by stage 4–5, ~7–8 by the
end; **9–10 only with Amber.** So @1–@2 must be start-able (carriers at **T1–T3**),
@4 ≈ stage 3, @6 = late board-dominating commit, **@7–@8 ≈ whole free board**, @10
≈ all-in Amber mono.

**Apex rule.** `apex = min(pool, cap)`; each counted champ = one slot, dupes count
once, emblem = one substitute carrier. Pool ≤ 8 (most Callings, Swarm) → apex ==
pool (no-emblem Callings are the hardest); pool > 8 (Beast, Spirit, Affinities) →
apex == cap; **Packmate** → apex == live board cap (dynamic).

**Kiting smart-behaviour logic (Skyborn).** Each movement phase a kiter checks the
**nearest enemy**:
- Nearest is **melee (range-1)** within trigger distance → step to restore
  attack-range distance while keeping *some* target attackable (retreat-kite).
- **Guardrails:** **plant when cornered** (no retreat tile increases distance);
  **plant when ≥2 enemies adjacent** (kiting futile); **only kite melee** (not
  ranged you can't out-range); **never kite with no attackable target**. Board-edge
  aware (lateral over corner). Deterministic geometry in the movement phase.
- **Melee Skyborn get +1 Range at @2** so they can kite at all (a range-1 kiter
  would retreat out of its own range).

**New combat primitives this design needs:**
- **Kite movement** (Skyborn) — above. The one Skyborn engine touch (T.28b).
- **Backline target-priority** (Stalker @2) — targeting hook, no teleport (T.28b).
- **Revive-once** (Mender) — death-path intercept, once/combat/piece (T.28b).
- **Threshold decaying-shield / "second wind"** (Primordial) — on HP crossing
  below X%, grant a Y%-max decaying shield over Z s, once/combat. Distinct from
  barrier (granted) and revive (death) (T.28b).
- **Tidal HoT** (Tidekin) — periodic team heal cadence (T.28b).
- **Barrier/shield, untargetable, taunt, deterministic dodge, time-ramp/enrage**
  (T.28b); **echo/double-cast, mana-denial aura, ability-splash, on-death spawns,
  empowered-shot/pierce/cleave, weather-as-buff** (T.28c).
- **Dynamic breakpoint** (Packmate `@full-board`) — a `TraitBreakpoint` whose
  threshold reads the live board cap at loadout (T.28a infra; effect in T.28c).

**Cheat-death stacking** is allowed and intentional (§4.1) — the mechanics are
varied (one revive + shield + HoT + enrage), so stacking is earned synergy, not an
unkillable wall. **The T.25 sim must still check for degeneracy** (no hard cap).

Magnitudes are first-pass; the `@7+`/`@10`/`@full-board` payoffs especially need a
T.25 sim sweep over leveled boards.

---

## 8. Open questions

- **Apex/second-wind magnitudes.** All `@7+` payoffs + the second-wind shield
  numbers are concepts; sim-tune after T.28b/c.
- **Cheat-death degeneracy.** Stacking is intentional — revisit only if the sim
  shows unkillable boards.
- **Kiting fidelity.** Retreat-step pathing is the one engine cost; if too invasive
  in T.28b, fall back to a Move-Speed + bonus-damage-to-unreachable proxy (keeps
  the kite *reward* without the retreat motion).
- **Two-Kinship hybrids.** Every champion has one Kinship; a few T7/T10 hybrids
  could carry two — deferred until single-Kinship draft proves thin.
- **Primordial @3.** Author as a flavour capstone, not balanced content.
- **Swarm legendary flavour.** Borealis-as-Swarm ("frozen light") is a deliberate
  stretch so every Kinship has a T10 anchor; overridable.
- **Emblem economy.** Six Kinship emblems; equal craftability vs boss-drop is a
  `D.12` / T.29 call.
- **Enemy tags.** Quest-augment matching vocabulary still unspecified
  (`augment_catalog.md` §6).

---

## 9. Build scope — T.28 splits into a / b / c

The system is large (~100 breakpoints + several engine primitives), so it ships in
three sequential substeps (each independently testable; b depends on a, c on b):

- **T.28a — framework + declarative content.** `TraitScope`/`TraitBreakpoint`
  types + `@register_trait`; `_resolve_traits` roll-up in `compile_loadout`
  (unique-id count, scope, §10.1 order, **apex/dynamic-threshold infra**);
  affinity-trait synthesis; **all stat-pack breakpoints** (Affinities + the stat
  portions of Kinships/Callings); Calling-vocabulary reconciliation (drop 4 dead
  tags, add Packmate + carriers); **roster rebalance** (kinship pools, T10 kinship
  anchors, Hunter spread); `BattleResult.trait_activations`. No engine-primitive
  changes.
- **T.28b — combat primitives, batch 1 + their breakpoints.** barrier/shield,
  untargetable, taunt, deterministic dodge, **revive-once**, **threshold
  decaying-shield (second wind)**, **tidal HoT**, time-ramp/enrage, **kiting
  movement**, backline target-priority.
- **T.28c — combat primitives, batch 2 + the rest.** echo/double-cast, mana-denial
  aura, ability-splash, Swarm on-death spawns, Hunter empowered-shot/pierce/cleave,
  Scaled weather-as-buff, Primordial kit hooks, the **apex effects**, and Packmate
  `@full-board`.
