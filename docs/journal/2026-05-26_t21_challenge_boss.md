# 2026-05-26 — T21: Challenge & Boss Encounters

## What was built

T21 adds two authored encounter types — champion-faction challenges and
multi-phase bosses — on top of the T19 seed-deterministic generator and the T20
ability/effect substrate.

### New modules

| Module | Purpose |
|---|---|
| `game/board.py` | `BoardState` + `CellModifier` — pure data layer for hex-cell modifiers |
| `game/map_effects.py` | 6 `MapEffect` subclasses; event-bus-driven, duck-typed ctx |
| `game/bosses/__init__.py` | Package entry point |
| `game/bosses/data.py` | 6 `BossDef` authored constants + `BossEncounterResult` |

### Extended modules

| Module | What changed |
|---|---|
| `game/encounter.py` | `generate_challenge()`, `generate_boss_encounter()`, `ChallengeReward`, `CHALLENGE_TEAM_SIZE` |
| `game/combat/context.py` | `board_state` property + `BoardState` plumbing |
| `game/combat/loop.py` | `_process_board_state()` — applies slow status from `board.slow_cells` each tick |
| `game/targeting.py` | `_filter_fog()` — respects `board_state.fog_range` |

### Tests

`tests/game/test_challenge_boss.py` — 63 tests covering:
- Challenge determinism, faction (champions only), team size, affinity distribution
- ChallengeReward fields (champion_offer, component_offer, themed_component, amber)
- Boss authored stats, fixed cast presence, variable adds within range/pool
- All map effects: BoardState mutations, on-tick behaviour, per-interval triggers

---

## Key design decisions

### Challenges use the champion faction

The original T21 plan had challenges drawing from a "spirit/corrupted" enemy
sub-pool. The user amended this before implementation: **challenges use the
Champion roster**. Players fight pieces they recognise as their own — same stat
profile, same affinities — converted to Enemy objects via
`_champion_def_to_enemy()`. Traits are dropped (trait synergies are a player-board
mechanic). The 50% stage affinity / 30% live weather / 20% random distribution
drives affinity selection; T10 Primordials are excluded.

This required adding `_CHAMPION_DEFS` to the public import surface of
`game/content.py`. The team size padding was later fixed to always produce exactly
`CHALLENGE_TEAM_SIZE[stage]` pieces (budget is a soft quality target, not a hard
count target).

### Auto-battle-aware map effects

Original plan had spawn rifts (Holloway) and a generic "collapsing arena" (Iron
Emperor). Both were revised because the game's auto-battle nature means players
can't react to tile effects in real time — the meaningful decision window is
**Prep placement**, not combat control.

Revised design principles (applied to all 6 effects):
1. Effect visible during Prep so players can reason about it
2. Effect influences piece behaviour deterministically (pathing, targeting)
3. Effect applies to both teams (no one-sided punishment that feels arbitrary)

Result:
- **Clear → Sunlit Tiles**: heal + damage buff for any piece on designated cells;
  placement matters, both sides benefit.
- **Cloudy → Defensive Ley Cells**: team-wide armor to whoever holds each cell;
  formation decisions matter; ownership transfers on step.
- **Thunder → Hazard Tiles (interval)**: changed per-tick damage → every 60 ticks
  (ticks are fine-grained; per-tick was invisible in practice).
- **Snow → Slow Tiles**: edges freeze inward each round; Phase 2 doubles the rate
  via `on_phase_change` hook; no cells disabled (no invisible-wall frustration).
- **Sudden death** remains as the timeout escalation; it's not part of Iron
  Emperor's mechanic.

### Architecture: BoardState outside `combat/`

Map effects need to write to cell modifiers; the combat engine needs to read them.
The isolation invariant (`combat/` must not be imported by content modules) would
create a circular import if `BoardState` lived under `combat/`.

Solution: `game/board.py` — imported by both `combat/context.py` and
`map_effects.py` with no circularity. Map effects receive `ctx` as a duck-typed
parameter from the event bus (never import `CombatContext`).

### Boss variable adds

All six bosses have a **fixed core cast** (always present, thematic identity) plus
a **variable add pool** (3–5 random picks per fight). This was a user amendment —
"I don't like fully authored boss fights; there should be some variation in Adds."
The Iron Emperor's pool mixes infantry and mid-tier elites, so each fight feels
slightly different at the edges while the core (2× Archmagus Imperator + 2×
Hierarch) stays recognisable.

### Living World deferred

The original T21 plan §6 proposed a "Living World" augment system. Deferred: the
system depends on weather map effects being designed first, and some of those
effects are difficult or impossible to make beneficial as an augment. Rationale
recorded in `t21_challenge_boss_plan.md` §6.

---

## What's still open

- **Ability kit content.** Boss and champion ability handler functions are stubs
  (registered ids only). Implementing them is the next major content task.
- **Map effect integration in encounter init.** `generate_boss_encounter()` returns
  a `map_effect_id`; the combat init layer (not yet built for boss fights) must
  call `build_map_effect()`, call `.register(bus)`, and pass the `BoardState` into
  `CombatContext`. The plumbing is ready; the wiring call site is the missing link.
- **`on_phase_change` event.** `SlowTilesEffect` subscribes to `on_phase_change`;
  the boss phase hook ability must fire this event when the boss crosses 50% HP.
  Currently stubbed.
- **T22 augments / T24 formation.** Next tasks on the dependency chain.
