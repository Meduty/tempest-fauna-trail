# 2026-06-15 — STR vs INT scaling edge (auto tagalong) + role-classifier fix

## Question

Is STR stronger than INT as an ability coefficient? The universal auto-attack is
`1.0*STR + 0.2*INT` (`combat/context.py`): STR gets **5×** the auto value. So a
piece that scales its kit on STR collects auto damage **for free** alongside its
ability damage, while an INT piece's autos are near-dead. If ability INT-coeffs
are sized like STR-coeffs, STR pieces should systematically out-perform — and
INT coeffs should be *higher* to compensate.

## Tool

`tools/simulation/stat_edge.py` — **team** sims (tier-stratified random KvK; NOT
1v1, which rewards self-sufficient duelists and confounds the signal). Groups
champions by roster axis (`stat` × `playstyle`) and reports **`wr_delta` =
win_rate − power-expected win_rate** (tier-controlled: positive = beats its power
budget). tqdm progress; `--csv` per-champion dump.

## Result (3v3, clear, n=4000 — stable)

```
stat × playstyle  [wr_delta | n]
              str            int
auto        +0.044 (n12)   −0.029 (n5)    gap +0.073
ability     +0.053 (n3)    −0.038 (n19)   gap +0.091
hybrid      −0.028 (n6)    −0.017 (n3)
by stat:    STR +0.024     INT −0.034     gap +0.058
```

**INT under-performs its power budget in every playstyle row (−0.017 to −0.038);
STR over-performs (+0.024).** Same playstyle, swap STR→INT ≈ **7–9pp** win-rate
drop — explained by the auto formula (STR 5× the auto value). STR-as-coeff is
strictly stronger: autos tag along free on STR, not INT. INT needs ~+0.06 wr_delta
to reach parity → **§D.25** (lever 1: raise engine auto `0.2·INT`→~0.35 global;
lever 2: +20–30% INT ability coeffs; sim-validate iteratively).

(An early n≈200 smoke read auto/INT at −0.099 — noise; n=4000 settles it at −0.029.
Lesson: don't quote magnitudes off a 200-battle run.)

## Two findings that fell out

1. **`classify_role` int⇒caster bug (fixed).** `caster = playstyle=="ability" OR
   stat=="int"` forced every INT piece to "caster" → an INT auto-attacker was
   structurally unclassifiable (always mage/assassin, never marksman/swashbuckler).
   The auto/INT cell was **empty** in the roster not because the archetype is
   impossible, but because the classifier couldn't represent it and nobody statted
   one. Dropped the `stat=="int"` force.

2. **`glade_heron` was mislabeled** `playstyle=ability` — its whole kit funnels INT
   into autos (self-haste active + INT poison-burst on auto), yet it was handed a
   caster statline (low AS / high MR) fighting its own kit. Re-axised to `auto`
   (→ marksman, `int-ranged-auto`, AS↑ MR↓). An audit found **8 more** INT champs
   routing INT through autos via on-hit-INT passives but statted as pure casters;
   reworked them (4 full → auto self-buff actives, 3 → hybrid with reduced-damage
   utility actives) so the archetype is **present + measurable** in content. They
   currently sit ~−0.10 wr_delta — which *is* the finding: auto-INT is weak until
   D.25 raises INT's conversion.

## Process notes (AI collaboration)

- **The user redirected the method three times, each correctly.** I first proposed
  a synthetic controlled-dummy harness → user: "just run normal sims, compare
  win-rates across roles." I built 1v1 → user: "1v1 biases toward duelist
  high-performers" (true: tanky bruisers win 1v1, backline casters lose). Switched
  to tier-stratified team sims. The metric also moved from raw win_rate to
  `wr_delta` to control for tier. Each redirect made the analysis more valid.
- **The user knew the content better than my heuristics.** When the matrix showed
  auto/INT empty, I concluded the archetype didn't exist. User: "not true, there's
  an auto-int heron that stacks poison on autos." My `inspect.getsource` heuristic
  had **missed `glade_heron`** because its INT scaling lived in a module-level
  `ScalingTerm` (not in the function body text). Lesson: detect via the registered
  `Magnitude`/META + hook subscriptions, not source-text grep.
- **The empty cell was the finding, not a dead end.** "auto/INT is empty" looked
  like a data gap; it was actually the hypothesis (nobody builds auto-INT because
  INT doesn't pay through autos) *plus* a classifier bug hiding the one that exists.
  Surfacing it led to the real fix.
- **tqdm parity matters.** First sweep "looked frozen" — `run_tournament` has no
  progress bar (mega wraps its own). Added one; the user caught the omission.

### Prompting-strategy reflection

Analysis tasks: don't over-engineer the apparatus up front. The user's "just use
normal sims" beat my synthetic-harness instinct, and the right experiment design
(team not 1v1, wr_delta not win_rate, content-present-not-synthetic) emerged from
their domain corrections, not from my first plan. Build the cheapest tool that can
show the signal, then let the domain expert sharpen the controls.

## Outcome — D.25 resolved (3 iterations)

| stat (by-marginal wr_delta) | pre-tune | final (n=4000) |
|---|---|---|
| str | +0.024 | **+0.000** |
| int | −0.034 | **−0.018** |
| hybrid | ~0 | **−0.002** |

Levers applied: auto INT term `0.2→0.25`; INT ability coeffs ×1.58 cumulative
(iters 1.2 · 1.2 · 1.1); STR ability coeffs ×0.8. str + hybrid land dead-on
parity; int within noise.

**The real cause — intent slice (user's "isolate damage" instinct cracked it).**
The int/ability cell (n=18) is **14 utility + 4 damage**. Slicing by intent:
*among `intent=damage` pieces* the axes are already at parity — **str +0.029 /
int −0.010 / hybrid −0.003**. The scary "int −0.021 by-stat" was **the 14 INT
utility/support pieces (−0.025)** dragging the average, NOT damage casters. Every
damage-coeff bump "bounced off" because it reached only 4 of 18 pieces in that
cell. So:
- **INT-as-damage-coeff is fair** (a focused damage-only ×1.2 lifts the 4
  int-ability-damage casters that sat at −0.037; the rest of int-damage was −0.010).
- The residual is **support-value balance** (D.26) — a different axis stat_edge
  can't measure (it scores damage-budget conversion, not healing/CC value).

**Lesson:** when a targeted lever bounces off a cell, the cell is probably
*mixed* — slice by another dimension (here `intent`) before concluding the lever
is wrong or exhausted. My first read ("cadence/rarity") was a guess; the intent
slice was the evidence. A composite metric (cell averaging damage + utility
pieces) hid two unrelated problems.

## Analytical equilibrium — the INT ability damage coeff ≈ 3.7

Cross-checked the empirical tuning against pure math. For DPS parity between a
STR/auto carrier and an INT/ability carrier at equal primary stat P (each ≈0 in
its off-stat), tick=10ms, ENERGY_THRESHOLD=60000, auto = `1.0·STR + 0.25·INT`,
playstyle mults (auto AS×1.3; ability AS×0.75, mana_regen×1.5), mana_cost=300k:

```
STR/auto DPS per P  = 1.00 × (1.3·100/60000)×100 = 0.2167   (full auto)
INT/auto DPS per P  = 0.25 × (0.75·100/60000)×100 = 0.0313  (the 0.25 tagalong)
casts/sec           = (1.5·100)×100 / 300000      = 0.0500  (~1 cast / 20s)

0.2167 = 0.0313 + coeff × 0.0500   →   coeff ≈ 3.71   (3.75 at flat baseline)
```

Interpretation: autos give STR 0.217 DPS/point but INT only 0.031, so the INT
caster must recover **0.185/point through rare casts** → at ~0.05 casts/s each
cast needs a **~3.7 INT coeff**.

**The blind sim-tuning converged on it.** Post-tune INT damage coeffs cluster
3.0–4.2, centered ≈3.7 (ember 3.42, tempest active 3.80, phantom 4.19; ult 5.70
at 2× cost — higher cost ⇒ higher coeff, correct). Empirical == analytical →
D.25 is balanced both ways, not just "sim says ok."

**Reusable rule (for T.36 kit redesign + new mages):**
`equilibrium INT coeff ≈ 3.7 × (cost / 300000) × (100 / mana_regen_base)` — i.e.
**scale the coeff with cast cost** (an ultimate at 2× cost wants ~2× coeff) and
**inversely with cast rate**. Auto-int / hybrid pieces need less (autos carry).

A final **+15% INT push on all ability-playstyle pieces** (collision-safe, 23
terms) lifts the whole int/ability cell — both the 4 damage casters and the 14
INT utility pieces (their heals/shields scale on INT too), partly addressing the
D.26 support drag. Centers INT damage coeffs just above 3.7 — within the "casts
are big nukes" design intent.
