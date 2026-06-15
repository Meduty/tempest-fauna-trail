# T.36 Plan — Roster stat/playstyle rebalance + Primordial diversification

> **Status:** ⚠️ **FIRST-PASS DRAFT (2026-06-15)** — drafted from the STR/INT
> scaling-edge investigation (D.25) + the hybrid-stat matrix discussion. Numbers
> and per-piece assignments below are **proposals, not final**; this needs a
> review pass + `/spec` row before `/build`. Not build-ready.

## Goal

Re-shape the **champion stat × playstyle distribution** to a deliberate, even
target, and **break the "all 6 Primordials are identical hybrid/hybrid" mold** —
make each Kinship's T10 king a distinct apex archetype. No net-new pieces (keep
the 60-champ, 1-per-affinity-per-tier grid); this is a **re-axis + kit-rewrite**
pass.

## Why (learnings from the D.25 discussion)

1. **STR > INT as a coefficient because of the free auto tagalong.** The
   universal auto is `1.0·STR + 0.25·INT` (post-D.25), so STR pieces collect auto
   damage for free alongside abilities; INT does not. Measured: auto/STR beats its
   power budget, ability/INT lags. → kits must be axis-aware (see "kit patterns").
2. **The roster was lopsided + archetype-incomplete.** Pre-work: stat int 27 /
   str 21 / hybrid 12; **hybrid-stat was 100% playstyle=hybrid, locked to T4/7/10**;
   `auto/int` existed but was **mislabeled** (classify_role forced int⇒caster — B,
   fixed) — `glade_heron` + 8 carriers were really auto-int. The stat×playstyle
   matrix had empty/near-empty cells (hybrid/auto, hybrid/ability, str/ability).
3. **"All Primordials hybrid/hybrid" is bland** and floored hybrid/hybrid at 6,
   blocking a clean target. V.37 only requires *one T10 Primordial per Kinship* —
   **not** a hybrid axis (confirmed: no test pins it). Freeing their axes both
   improves their identity and unblocks the target grid.
4. **str/ability is the weakest quadrant** (STR-on-cast wastes the auto tagalong).
   If it's populated, those pieces must be **"ability empowers autos"** (Jax-W
   style), not raw STR nukes — else they're dead-weight.

## Target distribution (proposal)

Champion `stat × playstyle`, sums to 60, symmetric across str↔int:

```
          auto  ability  hybrid   TOT
str        12      6        4      22
int         6     12        4      22
hybrid      6      6        4      16
TOT        24     24       12      60
```

- **Flagships str/auto = int/ability = 12** (the two pure carries, equal).
- **Off cells uniform = 6** (str/ability, int/auto, hybrid/auto, hybrid/ability).
- **hybrid column even 4/4/4** — playstyle-hybrid halved (21→12); stat-hybrid
  row (16) > playstyle-hybrid col (12).
- Even stat marginals 22/22/16; even playstyle marginals 24/24/12.

**Current (HEAD) for reference:**
```
          auto  ability  hybrid
str         8      2        6
int         5     18        3
hybrid      3      3       12
```
Deltas (~big): int/ability 18→12, hybrid/hybrid 12→4, str/auto 8→12, str/ability
2→6, the hybrid-auto/ability cells 3→6, etc. **~20 pieces re-axised** = ~⅓ roster.

> **Open numbers to ratify:** flagship size (12 vs 11), whether str/ability really
> sits at 6 (weak quadrant — maybe 4), exact hybrid/hybrid (4 vs keep 6). The grid
> is a starting point, not gospel.

## Primordial diversification (6 kings → 6 archetypes)

V.37-legal (stays T10 + one-per-Kinship + Primordial trait; only stat/playstyle/
kit change). Proposal — one per cell-family so the kings showcase the matrix:

| King | Kinship | proposed axis | identity sketch |
|---|---|---|---|
| Aurion (Spirit/Clear) | Spirit | str/auto | radiant warlord-archer (auto carry king) |
| Nerei (Tidekin/Rain) | Tidekin | int/ability | floodmother archmage (cast queen) |
| Borealis (Swarm/Snow) | Swarm | hybrid/ability | aurora battlemage |
| Umbra (Scaled/Cloudy) | Scaled | hybrid/hybrid | shadow bruiser-king (keeps the dual mold) |
| Mournhollow (Beast/Mist) | Beast | hybrid/auto | pale-stag on-hit-INT bruiser |
| Aerion (Skyborn/Thunder) | Skyborn | str/ability | storm warcaster — **ability empowers autos** (str/ability done right) |

> Sketches only — each needs a kit redesign honoring V.47 (hybrid → both coeffs)
> and the axis-aware patterns. Authoring these 6 is the headline content work.

## Kit patterns (axis-aware, from the investigation + research)

- **str/auto** — STR autos; ability = utility/steroid (not a nuke).
- **int/ability** — big INT nuke (casts rare ⇒ per-cast must hit hard).
- **int/auto** — INT fuels autos: self-haste (AS scales INT) or on-hit INT proc;
  STR-less. (the glade_heron line — already built.)
- **hybrid/auto** — AS-per-INT *or* on-hit-INT bonus; STR makes autos land (Voli).
- **hybrid/ability** — both-coeff cast `STR·A + INT·B` (Jax Q / Varus W).
- **str/ability** — **ability empowers autos** (Jax-W: cast → next autos bonus),
  NOT a raw STR cast (weak quadrant guard).

## Execution shape (phased — each phase ships + tests green)

1. **Primordial diversification** (6 pieces) — self-contained, high-value slice;
   can ship first.
2. **Drain int/ability → targets** (~6 pieces) to hit the 12 cap.
3. **hybrid/hybrid → 4** (re-axis the non-Primordial triple-hybrids).
4. **Fill str/auto, str/ability, hybrid-auto/ability** to target.
5. Each phase: re-axis + kit rewrite (V.47) + snapshot regen + role-matrix regen +
   determinism re-baseline; **balance-sim** (`stat_edge`) after.

## Guards / invariants to hold

- **V.47** axis↔scaling: every stat=int/hybrid references INT (hybrid → both).
- **V.22**: ≥1 Kinship + ≥1 Calling per champ; T10 carries Primordial.
- **V.37**: still exactly one T10 Primordial per Kinship (axes now free).
- **±10% HP·DPS proxy** (`test_role_intent`) — re-axis shifts stat weights; verify.
- Determinism (V.2): re-baseline snapshots/sims; no RNG introduced.

## SPEC changes needed (for `/spec`, after review)

- **New §T row T.36** (roster stat/playstyle rebalance + Primordial diversification;
  depends T.32 role system, T.35b, D.25; Est L).
- **Amend V.37 note**: Primordials no longer share a hybrid axis — each is a
  distinct apex archetype (still T10 + one-per-Kinship + Primordial trait).
- **Resolve/extend D.25**: the INT-coeff tuning feeds the redesigned kits.
- Possibly a **§V for the target distribution** (stat×playstyle marginals) as a
  roster-shape guard, if we want it CI-enforced.

## Notes

- **No wasted optimising:** the D.25 INT-coeff tuning (auto 0.25, INT ability
  ×1.44+) is inherited by the redesigned kits — re-axis reuses the balanced coeffs.
- This plan is **first-pass**; per-piece target assignments (which 20 champs move
  where) are NOT yet enumerated — that's the next planning step before build.
