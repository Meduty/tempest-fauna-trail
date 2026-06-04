# Mega Sim & Report Guideline

How to run a mega sweep and write its analysis report so the numbers mean
something. Distilled from the mega7 pass — every rule here exists because a
prior read got it wrong.

> **Scope**: covers `tools/simulation/mega.py` (the sweep) and the
> `NN_megaK*.R` + `build_megaK_pdf.py` report pipeline under `reviews/mega_sim/`.
> Engine is byte-deterministic (V.2/V.14) — same tree + same flags reproduce
> CSVs exactly. Every claim in a report must be reproducible from the saved
> flags.

---

## 1. The one rule that governs everything: sample depth

Per-cell depth decides whether a number is signal or noise. A `win_rate` from
`n` matches carries binomial sd ≈ `sqrt(p(1-p)/n)` — at `n=4`, that is ±0.25.
Most mega pathologies traced back to reading a thin cell as if it were solid.

- **`ratings_combined.csv` is the canonical aggregate.** It pools every battle
  (all stages + all weathers), pair-game weighted, to ~237 matches/piece. Use
  it for every per-piece outlier call.
- **Per-`(stage,weather)` cells are thin** (often 1–6 matches under a
  `--total-battles` budget split nine sizes × six weathers). Use them for
  *trends across sizes*, never for a single piece's headline number.
- **State your median matches/piece up front** (§1 of the report). It sets the
  noise floor for the whole document.
- **`n_matches < 20` → ignore the row.** Noise floor.
- When a finding sits near a decision threshold (±0.05), confirm with a
  `--seed` sweep before filing a content change. A single-run +0.20 can drop to
  +0.05 under a different seed.

## 2. Run conventions

```
# Sweep (current working tree). Pick --total-battles for hands-off budgeting.
python -m tools.simulation.mega --total-battles <N> --skip 1v1 \
    --workers <PHYSICAL_CORES> --out results/mega/megaK

# Analysis + tables + cache  →  reviews/mega_sim/tables/mK_*.csv, cache_megaK.rds
Rscript reviews/mega_sim/NN_megaK.R

# Figures  →  reviews/mega_sim/plots/mK_*.png
Rscript reviews/mega_sim/NN_megaK_plots.R

# PDF  →  reviews/mega_sim/megaK_analysis_report.pdf
python3 reviews/mega_sim/build_megaK_pdf.py
```

- `--workers` = **physical** core count, not logical (SMT hurts this workload).
- Record **engine provenance** in the report: which tree the sweep ran from
  (barrier system, poison decay model, any kit rework in flight). Kit reads are
  only indicative if the tree moved after the run.
- `--max-ticks` default keeps the shipped 12,000-tick timeout (sudden death
  engaged) — sims see what players see. Only raise it to separate "weak kit"
  from "stalls past the cap", and say which mode produced the numbers.

## 3. Metrics — what to compute and the traps

### `wr_delta = win_rate − expected_wr`
Tuning residual vs the deterministic power-budget model. Near 0 = on-budget;
negative = kit under-delivers vs raw power; positive = over-delivers. **A high
raw win rate is not a balance flag** — a T10 L3 piece is *supposed* to win a
lot. Read `wr_delta`, not `win_rate`, for "is this piece tuned right".

### `wd_z` — within-tier z-score of `wr_delta`
Standardize `wr_delta` within each tier cohort: `(x − mean) / sd` per tier.
`|z| ≳ 2` = a genuine per-tier outlier, controlled for the fact that residual
variance differs by tier position. Report it next to raw `wr_delta` so a reader
can tell a true tail event from a big-but-normal-for-its-tier number.

### Weather own/counter advantage — **never average the CSV columns**
`own_weather_wr` / `counter_weather_wr` **zero-fill weathers a piece never
played** (every clear-affinity piece has no counter; sampling misses the single
counter weather in ~37% of rows). Averaging those zeros fabricated a +0.18
own-vs-counter swing in an early mega7 read; the true value was +0.01.
**Recompute from raw per-weather `win_rate`**, NaN-skipping, match-weighted.
Keep the buggy-vs-correct comparison in the report as a standing caveat (§6
"METRIC ARTEFACT" block).

### Context-volatility (spread) — subtract the noise floor
"Odd" also means **inconsistent**: a pooled `wr_delta` near 0 hiding large
swings across formats/weathers. To measure it honestly:

1. Per piece, match-weighted `sd(wr_delta)` across its stage×weather cells.
2. Subtract the **expected binomial-noise sd**.
3. Rank by the **excess** (`wd_sd − noise_sd`), not raw sd.

**Noise estimate trap**: estimate the binomial variance from the piece's
**pooled** win-rate, `sqrt(pbar*(1-pbar) * mean(1/n_cell))` — NOT per-cell
`mean(wr*(1-wr)/n)`. A per-cell estimate collapses to 0 on single-match cells
(p = 0 or 1), understates noise, and fakes excess spread exactly for the
thinnest-sample pieces.

> mega7 result after this correction: only **8 of 360 pieces** showed any
> excess spread, all tiny (≤0.056) and thin-sample. Lesson: at typical
> `--total-battles` depth, across-context spread is **almost entirely sampling
> noise**. Do not file "inconsistent kit" findings unless excess clears the
> floor *and* survives a depth bump. To actually probe spread, raise
> `--total-battles` ~5–10× so per-cell depth lifts above the noise floor.

## 4. Report structure (megaK_analysis_report.md)

Sections that have earned their place:

0. **Executive summary** — ≤5 headline findings, each one sentence of claim +
   the number. Add a "watch-item" line for anything noisy (e.g. timeout climb).
1. **Dataset and method** — stages, weathers, piece count, **median
   matches/piece** (the noise floor), engine provenance, `wr_delta` definition.
2. **Aggregate balance** — champion vs enemy parity; variance/timeout vs size.
3. **Role balance** — win_rate heatmap + `wr_delta` by size.
4–6. Role/level/weather deep-dives as the data warrants.
7. **Timeouts** — they bias `wr_delta` down on stalemate-prone pieces; flag
   `timeout_rate > 0.1` rows as unreliable.
8. **Outliers** — see §5 below.
9. **Recommendations** — name pieces + the specific lever.
10. **Reproducibility** — the exact four commands + flags.

## 5. Presenting outliers — the part most reports get thin

Cover **three** distinct senses of "outlier", not just one list:

1. **Absolute magnitude** — largest `|wr_delta|`. Two tables (most under-tuned,
   most over-tuned), ≥13 rows each, **with the `wd_z` column** so a reader sees
   per-tier oddness. Save the full 30-row union to
   `tables/mK_abs_outliers.csv`.
2. **Distribution shape** — answer "how odd are these *as a set*" before naming
   anyone:
   - **Boxplots** of `wr_delta` by role and by tier (skew, IQR, whisker tails).
   - **Histogram + density vs a normal reference**, plus a **normal Q-Q**.
   - State the verdict in words: near-normal vs heavy-tailed; which roles skew
     which way; whether high tiers are systematically noisier (if not, that
     justifies the within-tier z-score).
3. **Context-volatility** — the excess-spread ranking from §3, as a lollipop
   plot + table, with the explicit "N of M pieces clear the noise floor"
   headline. If almost none do, **say so** — that is the finding, and it steers
   readers to the absolute list instead of chasing phantom inconsistency.

Always keep the `win_rate` vs `wr_delta` scatter (role-colored, labeled tails)
as the at-a-glance map.

## 6. Plotting conventions (base R, `NN_megaK_plots.R`)

- Base R graphics only; write `plots/mK_*.png` at `res=120`.
- Reuse the shared `ROLE_COLS` / `WX_COLS` palettes for cross-figure
  consistency.
- Reference lines: `abline(h=0)` for `wr_delta`, `abline(h=.5)`/`v=.5` for
  `win_rate`. A residual plot without its zero line is unreadable.
- Lollipop (segments + points) beats bars for sorted per-piece rankings.
- Label only the tail in scatters (e.g. `wr_delta` outside ±0.17 or `win_rate`
  outside [0.27, 0.85]) — labeling all 360 is noise.

## 7. Reproducibility & artefacts

- Every table the report cites must be a saved `tables/mK_*.csv`.
- Cache the analysis objects to `cache_megaK.rds` so the plots script never
  re-derives — plots read the cache, not the raw CSVs.
- The `.aux` / `.out` / `.log` xelatex by-products are build artefacts; only the
  `.md`, `.tex`, `.pdf`, plots, and tables are the deliverable.
- PDF build compiles **in** `reviews/mega_sim/` so `plots/*.png` relative paths
  resolve. Run `build_megaK_pdf.py` from repo root; it `cd`s itself.

---

### Checklist before publishing a mega report

- [ ] Median matches/piece stated; thin-cell caveat in §1.
- [ ] All per-piece headline numbers come from `ratings_combined.csv`.
- [ ] Weather own/counter recomputed from raw, NOT column-averaged.
- [ ] Outliers cover magnitude + distribution shape + context-volatility.
- [ ] Spread metric subtracts pooled-p binomial noise; "N of M clear floor"
      stated.
- [ ] `wd_z` shown alongside raw `wr_delta` in outlier tables.
- [ ] Engine provenance recorded; reproducibility commands exact.
- [ ] Findings near ±0.05 cross-checked with a `--seed` sweep.
