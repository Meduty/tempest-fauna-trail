# T.30 — Ability & Passive Catalog

**Date:** 2026-05-30

## Why

T.20 built the ability/passive/status framework (event bus, registries,
`EffectBundle`, `Modifier`, status gates). T.21 designed boss kits and wired
phase hooks. But until T.30, only a handful of reference abilities existed —
the 120-piece roster and 6 bosses ran on the generic fallback formula, making
combat outcomes homogeneous. T.30 gives every piece a unique mechanical
identity: authored coefficients, distinct ability shapes (AoE, heal, burn,
summon, buff/debuff, aura), and boss phase transitions that change the fight
mid-combat.

## Key Decisions

1. **Round semantics (G8 amendment).** "Round" = 600 ticks by convention only.
   All periodic passives use `on_tick` hooks with a `last_fired` timestamp and
   `>= 600` guard. No `on_round_start` event was introduced.

2. **Aura modeling (Q4 amendment).** Signal Drummer, Standard Bearer, and
   similar radius buffers use **periodic re-scan** (`on_tick` every 300 ticks):
   scan radius, apply a short-duration `TIMED` modifier to in-range pieces.
   Pieces leaving the radius naturally lose the buff when the modifier expires.
   No persistent `WHILE_CONDITION` primitive needed.

3. **Summon scope (G6 amendment).** Umbra's shadow summon and Steam Engineer's
   turret spawn as real `Piece` objects with `summon=True`,
   `summon_owner_id`, and `summon_expires_tick`. The tick loop despawns expired
   summons by setting `alive=False` and `hp=0` (pieces remain in `ctx._pieces`
   but are treated as dead). This keeps summons first-class: they
   can be targeted, take damage, trigger events.

4. **Generic fallback fix.** The old formula `0.2*STR + 4.2*INT` was biased
   toward INT scalers. Replaced with `4.4 * max(STR, INT)` — neutral between
   physical and magical. All existing tests updated (84→88 damage).

5. **Registration ID re-key.** Old IDs used short names (`dawnwisp.active`);
   content.py generates IDs with `champ_` / `enemy_` prefixes. All handlers
   re-keyed to match, e.g. `champ_dawnwisp.active`.

6. **Shield / knockback / invulnerability approximation.** Without dedicated
   shield HP pools or displacement systems, these are modeled via temporary
   stat modifiers (large armor buffs for shield/invuln, stun for knockback).
   Sufficient for auto-resolve; a future task can add explicit shield pools.

7. **Boss kits (Q5 amendment).** All 6 bosses have full 2-phase kits:
   phase 1 active + passive, a phase hook at 50% HP that swaps the active slot
   and registers phase 2 passives, phase 2 active + passive, and an on-death
   cleanup hook. Phase hooks fire `PhaseEvent(new_phase=2)` on the event bus.

8. **Coefficients are authored.** Each ability has hand-tuned base damage /
   scaling strings (e.g. `"strength*1.8"`, `"intelligence*2.2"`). These
   approximately follow the design guidelines (~4.4× stat at tier 1) but are
   individually calibrated for role and ability shape.

## Deviations from Plan

- Plan §6 suggested a `shared_factories.py` module for common patterns (burn
  applicator, heal-over-time, etc.). Instead, patterns are inlined per-handler
  since the factory abstraction added indirection without meaningful DRY gains
  — most abilities differ in enough details to not benefit.

- Plan §11 mentioned a `test_coefficients.py` sanity-checking coefficient
  magnitude ranges. Deferred — the authored values are intentionally diverse
  and a blanket bounds-check would need too many exceptions to be useful.

- Plan §12 suggested updating the power simulation to validate T.30 balance.
  Deferred to a follow-up playtest session (the sim already works with the new
  abilities, just needs re-running).

## File Summary

| File | Change |
|------|--------|
| `src/game/abilities/champions.py` | Complete rewrite: 60 champion active+passive handlers |
| `src/game/abilities/enemies.py` | New: 60 enemy active+passive handlers |
| `src/game/abilities/bosses.py` | New: 6 boss full 2-phase kits |
| `src/game/abilities/__init__.py` | Import trigger for new modules |
| `src/game/piece.py` | Added `summon`, `summon_owner_id`, `summon_expires_tick` fields |
| `src/game/combat/loop_new.py` | Fixed generic fallback + summon expiry logic |
| `tests/game/test_ability_catalog.py` | 16 new tests (CI guard, smoke, scaling, boss, summon) |
| `tests/game/test_combat.py` | Updated fallback damage assertion |
| `tests/game/test_combat_log.py` | Updated fallback damage text |
| `SPEC.md` | §T.30 row, §V.15 invariant, §D.2/D.5 amendments |

## Follow-ups

- Re-run power simulation (`tools/simulation/`) to check balance with real kits
- Implement shield HP pool if playtesting shows armor-buff approximation is
  insufficient
- Board displacement system for knockback (currently modeled as stun)
- T.28 (synergy traits) and T.29 (items) will add multiplicative effects on
  top of these kits

## Full Implemented Ability Catalog (as of T.30)

This section documents all 246 implemented abilities (120 champion abilities, 120 enemy abilities, 6 boss death hooks) with descriptions and implementation details.

**Legend:**
- **Active**: Cast ability with mana cost
- **Passive**: Always-on effect via event hooks
- **Scaling**: Damage/heal formula (e.g., `base=40, scaling=intelligence*2.5`)
- **Hooks**: Event subscriptions (e.g., `on_attack_landed`, `on_tick`, `on_damage_taken`)
- **Periodic**: Fires every N ticks (600 ticks ≈ "per round", 300 ticks ≈ "twice per round")

### Champions (60 champions × 2 = 120 abilities)

Organized by affinity (Clear, Rain, Snow, Cloudy, Mist, Thunder), then by tier.

See **[ABILITY_CATALOG_CHAMPIONS.md](./ABILITY_CATALOG_CHAMPIONS.md)** for the full 60-champion table with descriptions and implementation details.

**Summary by archetype:**
- **Healers (SUP-Heal)**: Dawnwisp, Springfrog, Lostlight Wisp — INT-scaled heals, periodic HoT
- **Buffers (SUP-Buff)**: Goldcrest Lark, Marsh Thrush, Geode Beetle — team AS/MS/armor boosts
- **Tanks**: Aegis Tortoise, Coral Colossus, Frostplate Tortoise — damage reduction, armor stacking
- **Assassins**: Mirage Caracal, Duskstep Marten, Nightglass Mantis — execute bonuses vs low-HP, blink/stealth
- **Marksmen/Hunters**: Sunspear Falcon, Glade Heron, Cliffeyrie Eagle — empowered autos, marking
- **Mages (APC-INT)**: Ember Salamander, Tempest Eel, Phantom Lynx — AOE, chain lightning, penetration
- **Warriors/Bruisers (ADC-STR)**: Veldt Pronghorn, Sunmane Lion, Thunderclap Gorilla — physical scaling, cleaves
- **Primordials (T10)**: Aurion, Nerei, Borealis, Umbra, Mournhollow, Aerion — ramping stats, board-wide effects, summons

### Enemies (60 enemies × 2 = 120 abilities)

Organized by faction: Humans (30), Corrupted Wildlife Rain/Snow/Cloudy/Mist/Thunder (5 each = 30).

See **[ABILITY_CATALOG_ENEMIES.md](./ABILITY_CATALOG_ENEMIES.md)** for the full 60-enemy table with descriptions and implementation details.

**Summary by faction:**
- **Humans T1-T10**: Military units (Conscripts → Grand Marshal), support (Field Medic, Chaplain), specialists (Gunslinger, Spymaster, Arcanist). Include aura buffers (Signal Drummer, Standard Bearer), summons (Steam Engineer), armor-stacking (Iron Maiden).
- **Corrupted Wildlife**: Regen (Blight Lurker), AOE control (Drowned Siren), AS ramping (Capture-Rig Wolf), slowing auras (Dredge-Hulk), execute + mana refund (Shroud-Killer), periodic stat/armor stacking (T10 Tyrants/Wardens/Lords).

### Bosses (6 bosses × 6 abilities each = 36 abilities)

Each boss has a full 2-phase kit: phase 1 active/passive, phase hook (50% HP trigger), phase 2 active/passive, death hook.

| Boss | Affinity | Phase 1 Active | Phase 1 Passive | Phase Hook (50% HP) | Phase 2 Active | Phase 2 Passive | Death Hook |
|---|---|---|---|---|---|---|---|
| **Foundry-Lord Holloway** | Clear | **Pressure Vent**: STR cone (base 100, scaling strength\*2.5) + burn 400 ticks | **Stoke the Fires**: Gains +8 STR per ally every 600 ticks | Burns all enemies 200 ticks, swaps active, registers phase 2 passive | **Magma Heave**: STR AOE radius 3 (base 140, scaling strength\*3.0) 70% damage + burn 500 ticks | **Cinder Husk**: +30 armor; reflects 10% damage as physical | **Boiler Burst**: 80 true damage AOE to all enemies |
| **Solar Overseer Vance** | Mist | **Focusing Lens**: High INT nuke (base 120, scaling intelligence\*2.8) furthest enemy | **Glare**: Periodic aura -15 AS to enemies radius 3 every 300 ticks | Silences all enemies 200 ticks, swaps active, registers phase 2 passive | **Sunflare Pounce**: INT burst (base 150, scaling intelligence\*3.0) lowest-HP + fear 250 ticks | **Drought Aura**: Periodic -5 mana_regen to enemies radius 4 every 300 ticks | **Sun Husk Collapse**: 60 true damage + burn 300 ticks AOE |
| **Grid-Director Strand** | Thunder | **Arc Cascade**: Chain lightning (base 110, scaling intelligence\*2.5) chains to 3 (60%, 50%, 40%) | **Overcharged**: Gains +12 INT per cast (stacking) | Stuns all enemies 150 ticks, swaps active, registers phase 2 passive | **Thunderhead**: Massive AOE radius 4 (base 130, scaling intelligence\*3.0) 60% + charged 300 ticks | **Stormform**: Bonus intelligence\*0.4 damage to charged targets | **Lightning Strike**: 100 true damage + stun 100 ticks AOE |
| **Clearance-Marshal Vossberg** | Cloudy | **Scorched Advance**: STR charge (base 130, scaling strength\*2.8) + burn 300 ticks, neighbors 40% | **No Quarter**: Every 3rd attack grants +10 STR (stacking) | Grants +40 STR, swaps active, registers phase 2 passive | **Wildfire Leap**: STR AOE radius 2 (base 160, scaling strength\*3.2) 80% + burn 400 ticks | **Feeding Frenzy**: Heals 10% max_hp on kill | **Fire Gutters Out**: Allies lose -20 STR on boss death |
| **Dredge-Admiral Crège** | Rain | **Harpoon Winch**: Hybrid pull (base 100, scaling strength\*2.0+intelligence\*1.0) furthest enemy + root 250 ticks, teleport 1 hex toward boss | **Dredged Depths**: Periodic slow aura radius 3 every 300 ticks | Roots all enemies 200 ticks, swaps active, registers phase 2 passive | **Maelstrom Jaws**: Hybrid AOE radius 3 (base 120, scaling strength\*2.5+intelligence\*1.5) 70% + slow 400 ticks | **Drowning Tide**: Periodic 5 DoT damage to all enemies every 200 ticks | **Silt Drains**: Removes slow status + heals 50 to all enemies |
| **The Iron Emperor** | Snow | **Decree of Iron**: Hybrid mark (base 100, scaling strength\*1.5+intelligence\*1.5) lowest-HP -25 armor/-25 resistance 600 ticks | **Tribute**: Gains +6 STR/INT per ally every 600 ticks | Grants +50 STR/INT, freezes all enemies 200 ticks, swaps active, registers phase 2 passive | **Reclamation**: Channel finisher AOE radius 4 (base 150, scaling strength\*2.0+intelligence\*2.0) 50% + slow 400 ticks | **The Wound Spreads**: Periodic intensifying DoT (3\*intensity) + slow every 300 ticks | **World Engine Dark**: Strips all timed modifiers from allies, heals 100 to all enemies |

**Boss implementation notes:**
- Phase hooks fire `PhaseEvent(new_phase=2)` on the event bus
- Phase transitions swap the active slot via `owner.actives = [ActiveSlot(...)]`
- Phase 2 passives are registered mid-combat via `ctx.register_bundle(owner, bundle)`
- Boss map effects (burn/silence/stun all enemies) fire during phase hook before phase 2 begins
- Death hooks fire `on_death` event; Crège/Iron Emperor have ally-healing/cleansing effects

---

## Detailed Ability Tables

Due to the large size (240+ abilities), the full ability-by-ability tables are in separate files:

- **[docs/design/content/ABILITY_CATALOG_CHAMPIONS.md](../design/content/ABILITY_CATALOG_CHAMPIONS.md)** — 60 champions, organized by affinity (Clear, Rain, Snow, Cloudy, Mist, Thunder) with descriptions and implementation details
- **[docs/design/content/ABILITY_CATALOG_ENEMIES.md](../design/content/ABILITY_CATALOG_ENEMIES.md)** — 60 enemies, organized by faction (Humans T1-T10, Corrupted Wildlife by affinity)
