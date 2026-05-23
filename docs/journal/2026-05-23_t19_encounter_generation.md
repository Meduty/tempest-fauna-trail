# 2026-05-23 — T19 Encounter Generation

## Context

Implemented seed-deterministic encounter generation for FIGHT and REWARD nodes.
This is the core system that populates the 50-node route with enemy squads.

## Key Design Decisions (amended from original plan)

### Full Pool Access for FIGHT/REWARD
The original plan restricted FIGHT/REWARD nodes to `human`-tagged enemies only.
This was changed because it would result in players almost exclusively facing
CLEAR-affinity enemies (the human roster is 50% CLEAR), contradicting the
50/30/20 affinity theme weight system. Now all factions are available with
affinity theming providing the compositional variety.

### Soft Tier Gates
Tier gates are weighted, not hard. The power budget is the real balancing
factor — expensive enemies naturally limit variety at inappropriate stages.
T10 remains boss-exclusive as a hard rule.

### Template-Based Squad Packing
Replaced the weighted greedy algorithm with a template approach:
- Affinity slots (50% CLEAR / 30% stage / 20% any) guide composition
- Fuzzy role checks (DPS ≈ Tank+Warrior + 1 SUP) with reroll on failure
- Budget-aware level selection prevents single-enemy squads at high stages

### Full Level Roster (L1-L3)
All enemy levels are now used, weighted by stage. Early stages are pure L1,
late stages heavily favour L2-L3. The power budget naturally constrains this
since L2/L3 pieces cost proportionally more P.

### Difficulty Coefficient (DC)
Added a player-facing difficulty multiplier that scales `stage_base`. Default
DC=1.0, with DC×1.1 unlocked after each completed playthrough ("DC +N").
Stored on the Run model for persistence.

### Content Version
Added `content_version` field to Run model (alongside existing `schema_version`).
This allows save/load to detect when roster changes have invalidated seeded
generation. Mismatch handling UI deferred to T14.

## Champion Shop Touchpoints (Brainstorm for T22)

The shop system needs `CH_SHOP = 6` seed channel (defined in this task).
Key insight: shop randomness is seeded per visit_index, but the *pool* filter
depends on player progression state at visit time. This is acceptable — the
RNG sequence is reproducible, just filtered differently based on choices.

For full replay/spectate support, the choice history needs to be saved.
Implementation lives in T22.

## Implementation Notes

- `src/game/encounter.py`: ~480 lines, pure functions, zero Flet imports
- All randomness via `Random(derive_seed(...))` — local, never shared
- `_ENEMY_DEFS` from content.py used directly for pool access
- `_instantiate_enemy` handles level scaling by ratio-adjusting stats
- Squad budget + max size per stage provides the difficulty envelope
- `content_version` and `difficulty_coefficient` added to Run dataclass

## Test Coverage

33 new tests covering:
- Seed derivation (determinism, isolation, bit-width)
- Pool filtering (tier, faction, T10 exclusion)
- Squad generation (determinism, budget, dupes, min/max count)
- Fight/reward generation (stage scaling, DC effect)
- Level distribution (stage-appropriate levels)
- Seed helpers (augment, supply, shop channels)
- DC utilities (next_dc, dc_name)
