"""Item presentation metadata (T.41a) — `ITEM_META`, the player-facing name +
blurb for every item id (V.78).

Transcribed from `docs/design/content/item_catalog.md` (FROZEN). The **stat line
is NOT stored here** — `describe.render_item` derives it from the item's
`EffectBundle` (V.78), so the blurb carries only the *effect/flavor prose* (the
leading stat phrase from the catalog concept is dropped, since the derived line
already shows it). One entry per `ITEM_REGISTRY` id: 8 components + 8
same-component + 28 cross-component + 6 emblems = **50**.
"""

from __future__ import annotations

from src.game.describe import ItemMeta

ITEM_META: dict[str, ItemMeta] = {
    # --- Base components (8, §1) — flavour blurb; stat is derived ---
    "fang":       ItemMeta("Fang", "A predator's tooth, still sharp."),
    "talon":      ItemMeta("Talon", "A raptor's claw — quick, light."),
    "heartseed":  ItemMeta("Heartseed", "A seed that remembers the whole forest."),
    "springtear": ItemMeta("Springtear", "A drop of the first spring, never dry."),
    "old_hide":   ItemMeta("Old Hide", "Thick weatherworn pelt."),
    "stoneplate": ItemMeta("Stoneplate", "A shard of mountain bedrock."),
    "wardpelt":   ItemMeta("Wardpelt", "Fur that turns aside spellfire."),
    "keen_claw":  ItemMeta("Keen Claw", "A claw honed to one perfect edge."),

    # --- Same-component recipes (8, §2.1) ---
    "apex_fang":        ItemMeta("Apex Fang", "Gains permanent bonus Strength on every takedown."),
    "tempest_talons":   ItemMeta("Tempest Talons", "Attack Speed keeps ramping for every auto landed this combat."),
    "worldroot_bloom":  ItemMeta("Worldroot Bloom", "A large flat Intelligence spike — the caster's payoff item."),
    "deepwell":         ItemMeta("Deepwell", "After its first cast, refunds a big share of mana on every cast."),
    "mammoth_hide":     ItemMeta("Mammoth Hide", "Regenerates steadily while the holder hasn't taken damage recently."),
    "bramble_carapace": ItemMeta("Bramble Carapace", "When hit in melee, deals splash magic damage and cuts the attacker's healing."),
    "mistward_shroud":  ItemMeta("Mistward Shroud", "The holder regenerates a share of max HP each round."),
    "perfect_predator": ItemMeta("Perfect Predator", "Critical hits deal extra damage."),

    # --- Cross-component recipes (28, §2.2) ---
    "huntress_talon":     ItemMeta("Huntress Talon", "Autos apply a stacking bleed that ticks over time."),
    "bloodthorn_briar":   ItemMeta("Bloodthorn Briar", "Heals for a share of all damage dealt — auto and ability."),
    "relentless_spear":   ItemMeta("Relentless Spear", "Every auto grants bonus mana, so an auto-attacker casts often."),
    "titanbone_charm":    ItemMeta("Titanbone Charm", "Stacks Strength as the holder attacks and is attacked, with a payoff at full stacks."),
    "beastheart_gauntlet": ItemMeta("Beastheart Gauntlet", "The first time the holder drops low, it gains a large shield."),
    "twinclaw_pact":      ItemMeta("Twinclaw Pact", "Alternates — one strike deals bonus damage, the next heals the holder."),
    "giantsbane":         ItemMeta("Giantsbane", "Bonus damage scaling with the target's maximum HP."),
    "wildfury_lash":      ItemMeta("Wildfury Lash", "Each auto stacks Attack Speed; at a threshold the next auto also triggers a cast."),
    "stormscale_quiver":  ItemMeta("Stormscale Quiver", "Every few autos discharge a chain of lightning to nearby enemies."),
    "quickpelt_harness":  ItemMeta("Quickpelt Harness", "The first time the holder is stunned, it cleanses and is briefly CC-immune."),
    "sundertalon":        ItemMeta("Sundertalon", "The holder's autos shred the target's Armor."),
    "splitwind_talons":   ItemMeta("Splitwind Talons", "Autos also strike a second nearby enemy at reduced damage."),
    "stalkerclaw":        ItemMeta("Stalkerclaw", "The clean auto-attack crit-carry stat stick."),
    "everbloom_staff":    ItemMeta("Everbloom Staff", "Intelligence climbs steadily for every tick the holder stays alive."),
    "witherbloom_censer": ItemMeta("Witherbloom Censer", "The holder's damage plants a burning rot that also cuts the target's healing."),
    "stoneward_idol":     ItemMeta("Stoneward Idol", "The durable backline-caster anchor."),
    "stormglass_totem":   ItemMeta("Stormglass Totem", "When a nearby enemy casts, the holder zaps it."),
    "spellfang_crown":    ItemMeta("Spellfang Crown", "Unlocks ability crit — the holder's abilities can now critically strike."),
    "sapwood_aegis":      ItemMeta("Sapwood Aegis", "Shields at combat start; when the shield breaks it releases a burst of ability power."),
    "wardens_dewstone":   ItemMeta("Warden's Dewstone", "A defensive support-caster anchor."),
    "seasonward_charm":   ItemMeta("Seasonward Charm", "Adapts — gains extra defense against whichever damage type recently hurt the holder most."),
    "dewclaw_fetish":     ItemMeta("Dewclaw Fetish", "A crit item for a cast-cycling carry."),
    "living_bulwark":     ItemMeta("Living Bulwark", "The plain, excellent frontline brick."),
    "spiritbark_hide":    ItemMeta("Spiritbark Hide", "The anti-magic frontline brick."),
    "gorehide_wrap":      ItemMeta("Gorehide Wrap", "Lets a fragile crit-carry survive the frontline."),
    "greatward_carapace": ItemMeta("Greatward Carapace", "Defenses scale with the number of enemies still alive."),
    "edge_of_stone":      ItemMeta("Edge of Stone", "A bruiser-carry hybrid."),
    "hexward_claw":       ItemMeta("Hexward Claw", "A crit item that survives magic burst."),

    # --- Emblems (6, §4) — grant a Kinship ---
    "beast_emblem":   ItemMeta("Beast Emblem", "Grants the Beast Kinship — the backbone synergy."),
    "skyborn_emblem": ItemMeta("Skyborn Emblem", "Grants the Skyborn Kinship — lets a grounded carry join a tempo board."),
    "scaled_emblem":  ItemMeta("Scaled Emblem", "Grants the Scaled Kinship — splashes weather-proofing onto a key piece."),
    "tidekin_emblem": ItemMeta("Tidekin Emblem", "Grants the Tidekin Kinship — bolts the heal-anchor synergy onto a non-aquatic core."),
    "swarm_emblem":   ItemMeta("Swarm Emblem", "Grants the Swarm Kinship — pads a wide board toward its breakpoint."),
    "spirit_emblem":  ItemMeta("Spirit Emblem", "Grants the Spirit Kinship — the ability-driven synergy."),
}
