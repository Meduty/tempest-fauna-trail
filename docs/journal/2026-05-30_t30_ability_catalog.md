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
   summons (removal from `ctx.pieces`). This keeps summons first-class: they
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
