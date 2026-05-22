# T18 Plan - Power & Scaling Model (`src/game/scaling.py`)

## 1. Scope

T18 defines the single power scalar `P` that the rest of the game budgets and
scales against: encounter difficulty (T19), piece stat generation (T5), level
and tier mechanics, and economy cost (T22).

Primary output: `src/game/scaling.py`

Test output: `tests/game/test_scaling.py`

Out of scope: champion archetype base stats (T5), encounter budgets (T19),
economy/shop implementation (T22).

## 2. Power Formula

```
P(T, L) = 1.5 ** E       where   E = (T - 1) / 2 + (L - 1)
```

- `T` = tier, integer `[1, 10]`. `L` = level, integer `[1, 3]`.
- Per tier: `×√1.5 ≈ ×1.2247`. Per level: `×1.5`.
- Consequence: **two tier steps == one level step** (both add `1` to `E`):
  `P(T+2, L) == P(T, L+1)`.

| T \ L | L1 | L2 | L3 |
|---|---|---|---|
| 1 | 1.00 | 1.50 | 2.25 |
| 5 | 2.25 | 3.38 | 5.06 |
| 10 | 6.20 | 9.30 | 13.95 |

Spread `T1L1 → T10L3` ≈ **14×**.

## 3. Stat Coupling

`P` is an abstract scalar; it becomes real by driving piece stats.

A piece's combat value ≈ `HP × DPS` (Lanchester). For `Σ P` to be a fair
encounter budget, combat value must be linear in `P`, so each factor scales
with `√P`:

```
stat_multiplier(T, L) = sqrt(P) = 1.5 ** (E / 2)
```

- **Scaled by `√P`** (combat magnitude): `max_hp`, `strength`, `intelligence`,
  `armor`, `resistance`.
- **Flat — never scaled** (role identity / tempo): `attack_speed`, `move_speed`,
  `mana_regen`, `attack_range`, `threat`.

DPS growth rides `strength` / `intelligence` only — scaling `attack_speed` too
would double-count and snowball.

## 4. Archetype-Driven Roster

T5 authors a small set of **role archetypes** (≈6-8: one per affinity, plus
role variants) with base stats defined at `P = 1` (`T1, L1`). The concrete
60-champion roster (`6 affinity × 10 tier`) is **derived**, not hand-tuned:

```
concrete_stat = round(archetype_base_stat * stat_multiplier(T, L))
```

Level-up (`L → L+1`) multiplies `P` by `1.5`, so every scaled stat grows
`×√1.5 ≈ ×1.225`.

## 5. Economy Cost (analysis — implemented in T22)

Acquisition cost `Cost(T) = T` (linear). Power is exponential in `T`, so
Amber-efficiency `P / Cost` is **U-shaped**:

| T1 | T3 | T5 | T8 | T10 |
|---|---|---|---|---|
| 1.00 | 0.50 | 0.45 | 0.52 | 0.62 |

- Low tiers overpriced (worst single step: `T1→T2`, cost `×2` / power `×1.22`).
- Mid tiers fairest. High tiers underpriced.
- **Resolution: gate tier availability by progression** (offer odds shift by
  stage), not price — keeps `Cost = T` simple; cheap high-tier units cannot be
  rushed early. Detailed in T22.
- Leveling (combine 3) halves Amber-efficiency per level — **intended**: you
  level for board-slot compression, not Amber value.

## 6. Public Surface

```python
TIER_STEP  = 1.5 ** 0.5      # per-tier power multiplier
LEVEL_STEP = 1.5             # per-level power multiplier

def power(tier: int, level: int) -> float
def stat_multiplier(tier: int, level: int) -> float       # sqrt(power)
def scale_stat(base: int, tier: int, level: int) -> int   # round(base * mult)
```

Pure, integer-out for `scale_stat`, no Flet imports (V.1).

## 7. Test Plan

- `power(1, 1) == 1.0`; monotonically increasing in both `T` and `L`.
- `power(3, 1) == power(1, 2)` and `power(T+2, L) == power(T, L+1)` — the
  "two tiers = one level" identity.
- `power(10, 3)` ≈ `13.95`; spread ≈ 14×.
- `scale_stat` returns `int`, monotonic, `scale_stat(base, 1, 1) == base`.
- Determinism: pure, same inputs → same outputs.

## 8. Acceptance Criteria

1. `src/game/scaling.py` exists, pure, zero Flet imports, fully type-hinted.
2. Formula and the tier/level identity hold exactly.
3. `scale_stat` is integer-valued and monotonic.
4. `tests/game/test_scaling.py` passes; existing tests unaffected.

## 9. Dependencies & Open Items

- Depends: T1 (no model change required).
- Open: archetype base stats (T5); economy tuning (T22); whether high-tier
  archetypes get distinct kits versus pure stat scaling (T20/T21).
