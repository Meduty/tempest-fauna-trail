"""Trait presentation metadata (T.41b) — `TRAIT_META`, the player-facing name +
blurb + per-breakpoint effect text for every trait (V.79).

Transcribed from `docs/design/content/trait_catalog.md` (FROZEN), reconciled to
the **code's actual breakpoint counts** (the source of truth — a few drifted from
the catalog during T.28b/c balance: Bruiser apex is @10 not @8, Stalker apex is
@8 not @7). Each trait's `rungs` keys **must** match its `factory()` breakpoint
counts exactly (V.79 guard). Stat lines are NOT stored here — `describe.render_trait`
derives them from `_packs.TRAIT_STAT_PACKS` so they can't drift from the bundle.

25 traits: 6 Kinships + 6 Affinities + 13 Callings (incl. Multicaster, T.29d).
"""

from __future__ import annotations

from src.game.describe import TraitMeta

# Affinity rungs share the scaling-pack shape (@2/4/6/8 grow the same stats; the
# stat line carries the numbers) + a per-affinity @10 mono apex rider.
_AFF_BODY: dict[object, str] = {
    2: "Minor stat pack.",
    4: "Moderate stat pack.",
    6: "Major stat pack.",
    8: "Greater stat pack.",
}


def _affinity(name: str, blurb: str, apex: str) -> TraitMeta:
    return TraitMeta(name, blurb, {**_AFF_BODY, 10: apex})


TRAIT_META: dict[str, TraitMeta] = {
    # --- Kinships (§2) ---
    "Beast": TraitMeta("Beast", "Fur, blood, stubborn endurance — the long fight.", {
        2: "HP + slow regen while alive.",
        3: "Small Strength.",
        4: "Build stacking Strength while alive (slow-burn ramp).",
        6: "The ramp doubles; Beasts heal for a share of damage dealt.",
        8: "Apex: lifesteal + ramp become a team aura; a Beast below 25% HP enrages once (burst AS + STR).",
    }),
    "Spirit": TraitMeta("Spirit", "Breath, mana, the half-real — the caster line.", {
        2: "Start with partial mana + Mana Regen.",
        3: "Abilities cost a little less.",
        5: "Untargetable for the opening; every few casts a Spirit's next ability echoes (free, reduced).",
        8: "Apex: the echo fires every cast; abilities pierce untargetable/blind; team ability-haste.",
    }),
    "Skyborn": TraitMeta("Skyborn", "Wings, height, the kite — out-maneuver melee.", {
        1: "Move Speed.",
        2: "Kiting unlocks: keep attack-range distance from melee; melee Skyborn gain +1 Range. + Attack Speed.",
        3: "Bonus damage to enemies that currently can't reach them.",
        5: "+1 Attack Range (all Skyborn); melee chasers targeting a Skyborn are slowed.",
        8: "Apex: attack without losing tempo while repositioning; team Move Speed.",
    }),
    "Scaled": TraitMeta("Scaled", "Cold blood, hard plates, weatherproof.", {
        2: "Armor + Resistance.",
        3: "More Armor + Resistance.",
        5: "Immune to the Weather Favor debuff (still take Affinity Clash hits).",
        8: "Apex: treat every node weather as a self-buff; shrug off the first hard CC each combat.",
    }),
    "Tidekin": TraitMeta("Tidekin", "Water, sustain, the slow tide — the heal anchor.", {
        2: "A small periodic self-heal.",
        3: "The heal reaches the lowest-HP ally too.",
        5: "Healing amplified; the heal becomes a rolling team heal-over-time.",
        8: "Apex: a large scaling team HoT all combat; healing also grants a small overheal shield.",
    }),
    "Swarm": TraitMeta("Swarm", "Numbers, and what's left behind — go wide.", {
        3: "A dying Swarm leaves a chitin-spawn (a weak, uncounted body).",
        4: "Small stats per other fielded Swarm.",
        5: "That per-Swarm bonus grows; spawns are stronger.",
        6: "Spawns inherit a fraction of their parent's stats.",
        8: "Apex: spawns can spawn once; each Swarm death briefly buffs the rest.",
    }),

    # --- Affinities (§3) — derived weather counts, weather-independent ---
    "Sunlit": _affinity("Sunlit", "Clear-weather champions — a little of everything.",
                        "Mono apex: the team gains a stat on every kill (snowball)."),
    "Overcast": _affinity("Overcast", "Cloudy-weather champions — endurance and resilience.",
                          "Mono apex: the team takes reduced burst damage."),
    "Shrouded": _affinity("Shrouded", "Mist-weather champions — speed and the veil.",
                          "Mono apex: a longer team untargetable opener."),
    "Stormfed": _affinity("Stormfed", "Rain-weather champions — tempo and mana.",
                          "Mono apex: team ability-haste."),
    "Frostbound": _affinity("Frostbound", "Snow-weather champions — armor and cold.",
                            "Mono apex: attackers that hit the team are slowed."),
    "Galvanized": _affinity("Galvanized", "Thunder-weather champions — power and speed.",
                            "Mono apex: crits chain a small arc to a neighbour."),

    # --- Callings (§4) — counts follow the code (factory()) ---
    "Hunter": TraitMeta("Hunter", "Ranged carries.", {
        2: "Bonus auto-attack damage.",
        4: "Empowered shot every few autos.",
        6: "+Attack Range; shots pierce.",
        8: "Apex: team auto-damage aura; empowered shots cleave.",
    }),
    "Mystic": TraitMeta("Mystic", "Mages.", {
        2: "+Intelligence.",
        3: "More Intelligence.",
        5: "Abilities can crit; casts splash to a neighbour.",
        8: "Apex: casts splash twice; team ability power.",
    }),
    "Guardian": TraitMeta("Guardian", "Frontline shields.", {
        2: "Self-shield at combat start.",
        3: "Bigger start shield.",
        4: "Bigger start shield.",
        6: "Shield adjacent allies + refresh each round.",
        8: "Apex: shielded Guardians' neighbours take reduced damage (team bastion).",
    }),
    "Bruiser": TraitMeta("Bruiser", "Strength frontline.", {
        2: "+HP.",
        4: "+HP & +Strength.",
        6: "Lifesteal on attacks.",
        10: "Apex: team-wide lifesteal + HP.",
    }),
    "Skirmisher": TraitMeta("Skirmisher", "Mobile melee — every hit ramps.", {
        2: "Stacking Attack Speed on one target.",
        3: "The ramp grows.",
        4: "Ramp grows + dodge a share of autos.",
        5: "+Move Speed; the ramp grows further.",
        8: "Apex: the AS ramp never decays + extends to the team's melee.",
    }),
    "Stalker": TraitMeta("Stalker", "Assassins.", {
        2: "Backline target-priority + Move Speed (no teleport).",
        3: "Stronger backline pressure.",
        5: "Bonus damage vs high-HP targets; mana on takedown.",
        8: "Apex: brief untargetable after a takedown.",
    }),
    "Channeler": TraitMeta("Channeler", "Cast-spam casters.", {
        1: "+Mana Regen (splash).",
        2: "More Mana Regen.",
        4: "Every few casts the next ability is free.",
        7: "Apex: the first cast each combat triggers twice; team ability-haste.",
    }),
    "Warden": TraitMeta("Warden", "Shield / buff supports.", {
        1: "Cast shields the lowest-HP ally (splash).",
        2: "Bigger shields; buffs last longer.",
        4: "Bigger shields still.",
        6: "Apex (own all 6): a whole-team opening shield.",
    }),
    "Trickster": TraitMeta("Trickster", "Debuff / disruption.", {
        2: "Casts apply slow / wither.",
        3: "+Threat; taunt the target on cast.",
        4: "Stronger disruption.",
        6: "Apex (own all 6): enemies near a Trickster gain mana slower.",
    }),
    "Mender": TraitMeta("Mender", "Healers — owns the one true revive.", {
        1: "Healing amplified (splash).",
        2: "More healing.",
        4: "Overheal converts to a shield.",
        6: "Apex (own all 6): the first ally death each combat is revived once at low HP.",
    }),
    "Packmate": TraitMeta("Packmate", "Wide-board filler — a cheap secondary Calling.", {
        2: "Team-wide stats scaling with the number fielded.",
        3: "More per fielded Packmate.",
        4: "More still.",
        6: "A large flat pack.",
        "full": "Dynamic apex (full board): every champion gets a large flat bonus.",
    }),
    "Primordial": TraitMeta("Primordial", "The six Tier-10 legendaries (augment-gated).", {
        1: "Signature mechanic active.",
        2: "Big team pack + second wind (a threshold decaying shield).",
        3: "Aspirational: the team's highest other trait counts one tier higher.",
    }),
    "Multicaster": TraitMeta("Multicaster", "Cast-cycle casters — every cast ramps.", {
        2: "Each cast ramps Attack Speed + Mana Regen (capped).",
        3: "The ramp grows.",
        4: "Higher ramp + cap.",
    }),
}
