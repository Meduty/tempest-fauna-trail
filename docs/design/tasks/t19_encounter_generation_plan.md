# T19 Plan - Encounter Generation (`src/game/encounter.py`)

## 1. Scope

T19 fills route nodes with encounters that are a deterministic function of
`Run.seed`. It materializes the procedural encounter types — `REWARD` and
`FIGHT` enemy squads, `AUGMENT` and `SUPPLY` offers — and exposes the generic
squad-roll primitive that T21 reuses for challenges and bosses.

Primary output: `src/game/encounter.py`

Test output: `tests/game/test_encounter.py`

Out of scope: challenge/boss encounters (T21); reward/augment/supply payload
*content* (T5/T22); the power scalar itself (T18).

## 2. Determinism Model

- `Run.seed` (already on the model) is the single root of randomness.
- Per-node, per-channel **sub-seed**:

```python
ENEMIES, AUGMENT, SUPPLY, REROLL = 0, 1, 2, 3

def derive(run_seed: int, node_index: int, channel: int) -> int:
    return (run_seed * 2654435761 + node_index * 40503 + channel * 97) & 0xFFFFFFFF
```

- **Never** feed `hash("string")` into an RNG — `PYTHONHASHSEED` randomizes str
  hashing per process and silently drifts runs (T3 risk §8). Channels are ints.
- All generation is pure: `roll_*(seed, node_index, ...) -> Encounter`.

Sub-seeds isolate nodes and channels: node 5's squad is independent of node 4,
and a reroll at one node cannot shift another.

## 3. Enemy Power Clustering

Each enemy archetype (T5 content) carries:

| field | use |
|---|---|
| `faction` | `human` / `spirit` — node type selects |
| `affinity` | `WeatherState` — continent theming; drives weather Weather Favor/B at fight time |
| `role` | frontline / ranged / caster / swarm |
| `power` | `P` from T18 — the budget cost |

## 4. Node Budgets

Absolute difficulty curve, expressed in `P` units:

```
node_budget = stage_base[stage] * type_mult[node_type]
type_mult:  reward 0.5 | fight 1.0       (challenge / boss authored — T21)
stage_base: rising curve, stage 1 -> 6
```

Absolute (not player-relative) — a relative curve rubber-bands and is
exploitable by deliberate under-levelling.

`roll_squad(rng, faction, affinity_theme, budget, pool)` greedily fills enemies
(faction- and affinity-filtered) until `Σ power ≈ budget`.

## 5. Per-Node Generation

- **`REWARD`** — easy human squad (`0.5×` budget) + drop-table roll
  (item / champion / Amber). An easy fight with guaranteed loot.
- **`FIGHT`** — human squad (`1.0×` budget).
- **`AUGMENT`** — roll 3 offers from a quality-weighted pool (4 qualities;
  weights shift toward higher quality by stage). One reroll via the `REROLL`
  channel. Detail in T22.
- **`SUPPLY`** — roll 5 champion+item combos; champion tier scaled to stage.
  Detail in T22.

## 6. Persistence

Hybrid — small save file, run stable across logout:

- **Stored**: `seed`, node `state`s, player choices (per-node `rerolled` flag,
  picks taken).
- **Regenerated lazily**: enemy squads and offers — pure
  `f(seed, node_index, channel)`, recomputed on demand. Nothing extra to save.
- **`content_version`** guard: add alongside `Run.schema_version`. Content edits
  change generation output — on version mismatch, fall back / warn rather than
  silently rerolling an in-progress run.

No `Node` model change: nodes keep their pool ids (T4); the squad is
materialized on arrival, not stored on the node.

## 7. Test Plan

- Determinism: same `seed` → byte-equal squads/offers; two builds match.
- Sub-seed isolation: changing node 4's outcome does not shift node 5.
- Budget: `Σ enemy power ≤ node_budget` (within one archetype's cost).
- Reroll: the `REROLL` channel yields a different, still-deterministic offer.
- No `hash()` nondeterminism: generation is stable across processes with
  `PYTHONHASHSEED` varied.

## 8. Acceptance Criteria

1. `src/game/encounter.py` exists, pure, zero Flet imports.
2. Encounters are a deterministic function of `(seed, node_index, channel)`.
3. Squad budgets respected; reroll isolated.
4. The `content_version` guard is specified for save/load.
5. `tests/game/test_encounter.py` passes.

## 9. Dependencies & Open Items

- Depends: T1, T4 (route), T5 (enemy archetypes), T18 (power).
- Open: exact `stage_base` curve; drop-table content; whether `Run` gains
  `content_version` now or at T14 (save/load).
