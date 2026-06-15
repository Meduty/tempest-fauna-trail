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

## Result (3v3, clear, n≈200 — direction; rerun larger for stable magnitudes)

```
stat × playstyle  [wr_delta]
              str       int
auto        +0.107    −0.099     ← same playstyle, swap stat → ~20pp gap
ability     −0.083    −0.014
hybrid      +0.034    +0.083
```

**auto/STR beats its budget by +0.107; auto/INT under-performs by −0.099** — a
~20-point swing explained entirely by the auto formula. STR-as-coeff is strictly
stronger than INT-as-coeff: autos tag along for free on STR, not on INT. Direct
evidence that **INT ability (and on-hit/auto-INT) coeffs must be raised** to reach
parity — logged as **§D.25**.

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
