# Mega7 Simulation Analysis Report

## 0. Executive summary

Mega7 is the **deepest balance sweep to date** and the first to use the new pooled `ratings_combined.csv` artefact (every battle from every stage and weather in one flat table). It spans **nine team sizes (2v2–10v10) × six weathers**, 360 pieces (120 bases × 3 levels), with a combined median of **237 matches/piece** — ~20× the per-cell depth of mega6.

Five headline findings:

1. **Faction balance is sound.** Champion vs enemy win rate sits at 0.507 / 0.491 pooled and stays within ±0.02 at every team size. Every pathology below is *within* the roster, not a champion/enemy asymmetry.

2. **The mage deficit persists and is a small-format problem.** Mage is the weakest role pooled (win rate 0.458 vs non-mage 0.515; gap +0.057). The within-tier deficit is worst at 2v2 (0.079), shrinks through the mid sizes, and *inverts* at 7v7–8v8 (mages slightly ahead). Same shape as mega6, marginally worse at 2v2.

3. **Weather favor is modest and working correctly — ~+0.01, not the +0.18 a first pass suggested.** An earlier read of this dataset reported a dominant +0.18 own-vs-counter swing; that was a **metric artefact** (the `counter_weather_wr` column zero-fills weathers a piece never played — 37% of rows, including every `clear`-affinity piece — and averaging those zeros craters the counter mean). Recomputed from raw per-weather win rates, the own-weather edge is **+0.010 own-vs-counter** and **+0.008 own-vs-clear-baseline**, positive for *every* affinity (no snow/thunder inversion — that too was thin-slice noise). The favor system is applied and behaves as designed; the metric has been fixed (§6).

4. **T10 hybrid boss kits under-deliver vs their power budget — again.** Hybrid has the *highest* raw win rate (0.559) but the *most negative* pooled `wr_delta` (−0.030): Aurion (clear T10 L3, −0.245), Aerion (thunder T10 L3, −0.165), Storm Tyrant (−0.089). They win because they are high-power, but less than their power says they should. This recurs from mega6.

5. **Level premium is steep but roughly on-budget.** L3 pooled win rate 0.593 vs L1 0.424; L3 `wr_delta` −0.021 (slightly over-delivers). By design, not flagged.

One real watch-item: **timeouts climb to 44% at 10v10**, compressing role signal at the largest sizes.

## 1. Dataset and method

| Field | Value |
|---|---|
| Directory | `results/mega/mega7/` |
| Run date | 2026-06-03 |
| Engine state | current working tree: poison percentage-decay (V.25 `decay_fraction=0.2`), barrier system, Glade Heron rework, weather favor ±0.30 |
| Stages | 2v2, 3v3, 4v4, 5v5, 6v6, 7v7, 8v8, 9v9, 10v10 (no 1v1) |
| Per-stage rated rows | 19,200 |
| Combined pieces | 360 (120 bases × 3 levels) |
| Weathers | clear, cloudy, mist, rain, snow, thunder |
| max-ticks | 12,000 (engine default — sudden death engaged) |
| Baseline | mega6 (`cache_mega6.rds`; raw dir deleted) |

**The combined file is the canonical aggregate.** Per-(stage,weather) ratings still exist for slicing, but per-cell samples are thin (median 3–6 matches). `ratings_combined.csv` pools every battle — pair-game weighted — so its per-piece win rates and cross-weather metrics are the reliable read (median 237 matches). All §7–§8 outlier work uses it.

**`wr_delta` interpretation (carries from prior reports).** `expected_wr` is the deterministic power-threshold model: 1.0 if your team's ΣP exceeds the opponent's, 0.0 if less, 0.5 if equal, averaged over the actual opponent field. `wr_delta = win_rate − expected_wr`. Near 0 = on-budget; negative = kit under-delivers vs power; positive = over-delivers.

**Provenance caveat.** Mega7 was generated from the current uncommitted working tree. Kit-level reads for pieces touched this session (Glade Heron, poison users, Hierarch) are indicative; a clean post-commit re-run is advisable before acting on those specific rows.

## 2. Aggregate balance

| stage | champion | enemy | sd(win_rate) | timeout |
|---|---|---|---|---|
| 2v2 | 0.500 | 0.505 | 0.268 | 0.151 |
| 3v3 | 0.505 | 0.492 | 0.244 | 0.189 |
| 4v4 | 0.501 | 0.491 | 0.256 | 0.212 |
| 5v5 | 0.489 | 0.493 | 0.235 | 0.279 |
| 6v6 | 0.502 | 0.503 | 0.245 | 0.285 |
| 7v7 | 0.508 | 0.475 | 0.232 | 0.370 |
| 8v8 | 0.519 | 0.486 | 0.222 | 0.399 |
| 9v9 | 0.513 | 0.489 | 0.209 | 0.418 |
| 10v10 | 0.504 | 0.485 | 0.210 | 0.442 |

Champion/enemy parity holds across all formats. Win-rate spread declines only modestly with team size (0.27 → 0.21), much less than mega6's collapse (0.23 → 0.09). The cause is **per-stage sampling depth**, not a real effect: mega7's per-(piece, stage) samples are thin (median 3–6 matches — the `--total-battles` budget spread across nine sizes × six weathers), so each per-piece win rate carries large binomial noise that inflates sd at every size. mega6 reached 50–222 matches/piece at its top sizes, so its sd genuinely collapsed. Read mega7's *pooled* (combined) win rates for per-piece signal; treat per-stage sd as noise-dominated.

**Timeouts are a rising concern**: 15% at 2v2 → 44% at 10v10. Every timeout is a draw, pulling win rates toward 0.50 and compressing differences at the top sizes.

![win\_rate spread and timeout vs team size](plots/m7_02_variance_timeout_vs_size.png)

## 3. Role balance

### 3.1 Win rate by team size

![Role win\_rate by size (heatmap)](plots/m7_04_role_wr_heatmap.png)

Pooled (combined) role win rates:

| role | win_rate |
|---|---|
| mage | 0.458 |
| warrior | 0.486 |
| assassin | 0.496 |
| marksman | 0.515 |
| bruiser | 0.546 |
| hybrid | 0.559 |

Mage is the floor at every size except 9v9. Hybrid and bruiser are the ceiling — the same two outliers flagged in mega6.

### 3.2 Tuning residuals (wr_delta)

Pooled (combined) role `wr_delta`:

| role | wr_delta |
|---|---|
| hybrid | −0.030 |
| mage | −0.018 |
| assassin | −0.001 |
| bruiser | +0.008 |
| warrior | +0.024 |
| marksman | +0.029 |

The story splits from raw win rate. **Hybrid is the most *under-budget* role** despite the highest raw win rate — its members are high-power T10 bosses that win on stats but under-deliver on kit. **Marksman and warrior over-deliver** (+0.025–0.029): they punch above their power budget. Mage is under on both raw and budget.

![Role tuning residuals by team size](plots/m7_01_role_wrdelta_vs_size.png)

## 4. Mage deficit

| stage | mage | nonmage | within_tier_def | cor(tier,wr) |
|---|---|---|---|---|
| 2v2 | 0.398 | 0.542 | 0.079 | 0.383 |
| 3v3 | 0.444 | 0.519 | 0.011 | 0.290 |
| 4v4 | 0.434 | 0.519 | 0.019 | 0.322 |
| 5v5 | 0.432 | 0.514 | 0.045 | 0.255 |
| 6v6 | 0.454 | 0.521 | 0.034 | 0.154 |
| 7v7 | 0.453 | 0.506 | −0.016 | 0.265 |
| 8v8 | 0.480 | 0.511 | −0.013 | 0.204 |
| 9v9 | 0.499 | 0.502 | −0.004 | 0.223 |
| 10v10 | 0.452 | 0.510 | 0.023 | 0.223 |

The within-tier deficit is sharply concentrated at **2v2 (0.079)** and is gone or inverted by 7v7–8v8. Mages scale *into* relevance with team size — they need allies to survive long enough to ramp. Versus mega6 at matched sizes the picture is mixed: 2v2 slightly worse (+0.013), but 3v3/7v7/8v8 notably better (−0.036 to −0.038).

![Mage deficit by team size: mega6 vs mega7](plots/m7_03_mage_deficit_by_size.png)

The worst individual mages (pooled `wr_delta`) are **Hierarch** (clear T8 L3, −0.221), **Hoarfrost Owl** (snow T4 L3, −0.184), **Standard Bearer** (clear T3 L2, −0.179), **Fogveil Moth** (mist T5 L3, −0.170), **Drowned Siren** (rain T4 L1, −0.165). Note Hierarch — it received the on-death barrier this session, which does nothing for its own survival; it remains the single most under-tuned mage. **Glade Heron L3 is on-budget (+0.022)** despite a 0.903 raw win rate (T8 L3 is *expected* to win that much) — the rework landed in the right place.

![Mage wr\_delta per piece (combined)](plots/m7_08_mage_wrdelta.png)

## 5. Level effects

| level | win_rate | wr_delta | timeout |
|---|---|---|---|
| 1 | 0.424 | +0.019 | 0.279 |
| 2 | 0.480 | +0.004 | 0.277 |
| 3 | 0.593 | −0.021 | 0.304 |

The level premium is steep (L1→L3 = +0.17 raw) but `wr_delta` stays small: L1 slightly under-delivers, L3 slightly over. Mixed-level teams will be L3-dominated, which is by design. No action needed.

![Win rate and tuning residual by champion level](plots/m7_05_level_effect.png)

## 6. Weather effects

**Headline correction.** A first pass on this dataset reported a dominant **+0.18** own-vs-counter weather advantage. That number was wrong — a metric artefact, not a balance fact. This section uses the corrected computation (raw per-weather win rates); the favor effect is real but **modest (~+0.01)**.

**The bug.** The `counter_weather_wr` column defaults to **0.0 when a piece has no games in its counter weather**. That conflates "no data" with "0% win rate". It fires constantly: a piece's counter weather is one specific weather of six, and every `clear`-affinity piece has *no* counter weather at all (NEUTRAL on the ring). Result — `counter_weather_wr == 0.0` in **37.1%** of rows. Averaging those zeros in collapses the mean counter and manufactures a fake gap:

| computation | own | counter | own − counter |
|---|---|---|---|
| buggy column-average (zeros in) | 0.505 | 0.332 | +0.173 |
| **correct (raw per-weather win rate)** | **0.509** | **0.499** | **+0.010** |

Fixed in code: [`weather_metrics`](../tools/simulation/ratings.py) now emits `NaN` (not `0.0`) for a weather the piece never played, and the CSV writer leaves the cell empty so aggregators skip it. This report recomputes from raw per-weather win rates and is unaffected.

**Corrected own-weather advantage by size** (own = win rate in own affinity weather; clear = no-favor baseline; counter = weather that preys on you):

| stage | clear (base) | own | counter | own − counter | own − clear |
|---|---|---|---|---|---|
| 2v2 | 0.500 | 0.515 | 0.498 | +0.017 | +0.015 |
| 4v4 | 0.500 | 0.505 | 0.498 | +0.007 | +0.005 |
| 6v6 | 0.500 | 0.507 | 0.495 | +0.012 | +0.007 |
| 8v8 | 0.500 | 0.508 | 0.499 | +0.009 | +0.008 |
| 10v10 | 0.500 | 0.506 | 0.503 | +0.003 | +0.006 |

**Corrected per-affinity** (raw, pooled all stages):

| affinity | clear | own | counter | own − clear | own − counter |
|---|---|---|---|---|---|
| mist | 0.512 | 0.513 | 0.498 | +0.002 | +0.016 |
| cloudy | 0.506 | 0.530 | 0.494 | +0.025 | +0.037 |
| rain | 0.515 | 0.530 | 0.515 | +0.016 | +0.016 |
| snow | 0.509 | 0.516 | 0.495 | +0.007 | +0.022 |
| thunder | 0.491 | 0.511 | 0.496 | +0.020 | +0.015 |

Every affinity gains in its own weather and loses (or is flat) in its counter weather — **the favor system works as designed, and the earlier snow/thunder "inversion" was thin-slice noise**, not a real effect. The magnitude is small (single-digit win-rate points), so weather favor is a flavour-and-edge system, *not* a dominant axis — it does not overshadow kit or role. Whether ±0.30 favor magnitude should produce a *larger* effect than this is a separate design question, but it is not overpowered.

![Weather: corrected own-advantage by size and per-affinity edge](plots/m7_06_weather_effects.png)

## 7. Timeouts

| role | 2v2 | 5v5 | 8v8 | 10v10 |
|---|---|---|---|---|
| assassin | 0.131 | 0.312 | 0.352 | 0.483 |
| bruiser | 0.320 | 0.378 | 0.508 | 0.398 |
| hybrid | 0.120 | 0.289 | 0.350 | 0.405 |
| mage | 0.160 | 0.248 | 0.406 | 0.448 |
| marksman | 0.078 | 0.257 | 0.379 | 0.404 |
| warrior | 0.145 | 0.271 | 0.412 | 0.469 |

Bruisers stall hardest at small/mid sizes (high survivability, low burst), consistent with mega6. At the largest sizes nearly half of all battles time out — the 12,000-tick cap is too tight for 10v10 to resolve organically. Large-format role reads should be treated cautiously because of this.

## 8. Outliers and tuning priorities

![Piece outliers: win\_rate vs wr\_delta (combined)](plots/m7_07_outlier_scatter.png)

**Most under-tuned (pooled `wr_delta`):**

| name | affinity | role | tier | level | win_rate | wr_delta |
|---|---|---|---|---|---|---|
| Cliffeyrie Eagle | cloudy | marksman | 9 | 3 | 0.664 | −0.305 |
| Aurion, the First Dawn | clear | hybrid | 10 | 3 | 0.755 | −0.245 |
| Riven Frost-Wyrm | snow | hybrid | 9 | 1 | 0.331 | −0.236 |
| Hierarch | clear | mage | 8 | 3 | 0.682 | −0.221 |
| Cold-Iron Yeti | snow | warrior | 4 | 2 | 0.342 | −0.206 |
| Hoarfrost Owl | snow | mage | 4 | 3 | 0.518 | −0.184 |
| Spymaster | clear | assassin | 8 | 3 | 0.630 | −0.182 |

**Most over-tuned:**

| name | affinity | role | tier | level | win_rate | wr_delta |
|---|---|---|---|---|---|---|
| Lostlight Wisp | mist | mage | 1 | 1 | 0.508 | +0.270 |
| Flood Tyrant | rain | hybrid | 10 | 2 | 0.628 | +0.217 |
| Aegis Tortoise | clear | warrior | 5 | 3 | 0.557 | +0.210 |
| Thunder Bull | thunder | warrior | 7 | 2 | 0.548 | +0.197 |
| Frostfang Wolverine | snow | warrior | 8 | 1 | 0.481 | +0.180 |

The under-tuned list is dominated by **high-tier hybrids/mages that win on raw power but miss their budget** (Aurion, Hierarch) and **snow pieces** (Riven Frost-Wyrm, Cold-Iron Yeti, Hoarfrost Owl) — reinforcing the snow-affinity anomaly from §6. The over-tuned list is led by a T1 mage (Lostlight Wisp) and the rain/thunder hybrid Tyrants.

## 9. Recommendations

- **Mage early-game power (priority).** Target the 2v2 within-tier deficit specifically — it vanishes at scale, so the fix is early survivability/damage, not late-game. Worst offenders: Hierarch, Hoarfrost Owl, Standard Bearer, Fogveil Moth, Drowned Siren.
- **T10 hybrid boss kits (Aurion, Aerion, Storm Tyrant) under-deliver vs budget** — recurring since mega6. Their kits need a pass; they should top the chart, not merely win on raw power.
- **Hierarch.** Most under-tuned mage; the new on-death barrier helps allies, not itself. Needs a personal-survivability or damage buff.
- **Weather favor: no action needed.** Corrected analysis (§6) shows it working as designed at a modest ~+0.01 edge. If a *stronger* competitive weather effect is wanted, the ±0.30 magnitude could be revisited — but it is not a balance problem. The metric bug that overstated it has been fixed in `weather_metrics`.
- **Validated this session:** Glade Heron L3 is on-budget (+0.022); the poison percentage-decay model produced no runaway poison outliers in team play.

## 10. Reproducibility

```
# 1. Run the sweep (current working tree)
python -m tools.simulation.mega --total-battles <N> --skip 1v1 \
    --workers 16 --out results/mega/mega7

# 2. Analysis + tables + cache
Rscript reviews/mega_sim/11_mega7.R

# 3. Figures
Rscript reviews/mega_sim/12_mega7_plots.R

# 4. This PDF
python3 reviews/mega_sim/build_mega7_pdf.py
```

Tables written to `reviews/mega_sim/tables/m7_*.csv`; cache to `cache_mega7.rds`; figures to `reviews/mega_sim/plots/m7_*.png`. The engine is byte-deterministic — same tree + same flags reproduce the CSVs exactly.
