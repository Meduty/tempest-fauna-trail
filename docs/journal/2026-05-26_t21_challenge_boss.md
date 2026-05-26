# 2026-05-26 — T21: Challenge & Boss Encounters

## Context

T21 builds on the encounter generation (T19) and ability framework (T20) to add
the game's two authored encounter types: **Challenges** and **Boss Fights**.
This completes the encounter vocabulary — the route now has all node types fully
backed by generation logic.

## Key Decisions

### Challenges draw from Champions faction (§2.3 amendment)

The original plan had challenges using "spirit" enemies. The user amended this:
challenges now draw from the **Champions roster**. This is the unique hook —
the player fights pieces they know as their own. The composition follows a
50/30/20 split: 50% stage affinity, 30% live weather affinity, 20% random.

### Challenge rewards (§2.5 amendment)

Reward for clearing a challenge: one champion *from the challenge team itself*
(as a recruit), plus a random component and a themed component. This makes
challenges feel like "win to draft" opportunities.

### Map effects system decoupled from bosses (§4.5 amendment)

Map effects (`src/game/map_effects.py`) are authored as a generic system with a
`MapEffect` base class, a `BoardState` container, and concrete per-affinity
implementations. Currently used only by bosses, but the interface is clean
enough for future augment/passive use without scope explosion.

### Auto-battle-aware map effects (§4.2 amendment)

Since players don't control pieces during combat, map effects focus on:
- **Visibility during planning** — players see effects before combat begins
- **Influencing pathing/targeting** — effects create positional incentives
- **Deterministic intervals** — damage on hazard tiles every 60 ticks (not
  every tick), preventing overwhelming tick-damage from dominating outcomes

Reworked effects:
- **Clear (Holloway)**: spawn rifts every 2 rounds (not every round), spawning
  weak adds at visible positions
- **Thunder (Strand)**: hazard tiles deal damage every 60 ticks (not per-tick),
  shift positions each round for dynamic pathing
- **Snow (Iron Emperor)**: collapsing arena shrinks from edges — the thematic
  "sudden death at timeout" comes from the arena itself, not an artificial timer

### Iron Emperor finale (§3.3 amendment)

Authored as the final boss with supporting cast variation. Not fully authored
in a rigid way — adds are drawn from a variation pool so each encounter feels
slightly different. His kit reflects lessons from all prior bosses (grows like
Holloway, focuses like Vance, has windows like Strand, pressures like Vossberg,
controls like Crège) without going overboard on mechanics.

### Boss on-death hooks (§5 note)

Kept lightweight since fights end when all enemies die. Most are narrative beats
(Vance's team heal, Crège's slow removal) rather than combat-altering mechanics.
Holloway and Strand have short AOE detonations that matter only if adds survive.

### Living World deferred (§6)

Deferred entirely per user direction — some map effects cannot easily be made
beneficial, and weather-reactive map effects add complexity without clear payoff.

## Files Changed

| File | Purpose |
|---|---|
| `src/game/map_effects.py` | Map effects system — BoardState, MapEffect base, 6 concrete effects |
| `src/game/bosses.py` | Boss definitions, phase hooks, on-death hooks, data registry |
| `src/game/encounter.py` | Added `generate_challenge`, `generate_boss`, `ChallengeReward` |
| `tests/game/test_challenge_boss.py` | 36 tests covering all new functionality |
| `SPEC.md` | T21 marked done, D.2/D.3 updated, T21 description revised |

## Architecture Notes

- `MapEffect` is stateless in schema, stateful at runtime (setup → round → tick).
  This mirrors how the `EffectBundle` pattern works: authored as data, applied
  as live hooks.
- Boss phase hooks use the existing `ONCE_PER_COMBAT` dedup on `on_damage_taken`
  — identical pattern to the example in `effect_systems_design.md` §6.6.
- Challenge generation reuses `_tier_weight`, `_pick_level`, and `power()` from
  the T19 encounter module — no new scaling math.
- The `_champion_as_enemy()` helper produces Enemy instances from ChampionDefs,
  preserving stat computation through the same `compose_stats` pipeline.

## Open Items

- Boss ability *handlers* (the actual `@register_active` functions) are not yet
  implemented. They require combat-system content work beyond T21's scope.
- Map effects are not yet integrated into the combat tick loop (`loop.py`). The
  system is ready; `process_occupants()` and `on_round()` need to be called from
  the appropriate places in `run()`.
- Supporting cast level scaling (whether adds scale with stage or stay L1) is
  a tuning question for T25 power simulation.
