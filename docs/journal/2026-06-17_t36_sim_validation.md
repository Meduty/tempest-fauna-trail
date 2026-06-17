# 2026-06-17 — T.36 sim-validation: closing the roster rebalance

The deferred combined `stat_edge` sweep (T.36b/c gate) finished. Read it, tuned 5
champions, re-swept, and flipped T.36a/b/c → ✅ Done. Touches §T (T.36b/c status),
§D.25 (post-validation reframe), `docs/live/content/rosters.md`. No new §V/§B.

## What changed

1. **Read the full n=8000 sweep** (`results/stat_edge_t36c.csv`, team sims 2–5v5 ×
   all 6 weathers, 1.59M champ-game samples). Headline: the T.29/D.25 stat lever
   landed at aggregate (by-stat str +0.006 / int +0.004 / hybrid −0.006), but the
   STR-ability cross-cell sits +0.034 over budget while INT-ability sits at ~0.000.
2. **5-champ coefficient tune** (`game/abilities/champions.py`): trimmed the three
   over-budget outliers — mournhollow (nuke STR 1.0→0.8, grief 0.4→0.3),
   veilfang_wolf (bonus INT 0.55→0.45, haste 0.64→0.42), ember_salamander (nuke STR
   1.95→1.65, magma 1.2→1.0); buffed the two under — aurion (nova INT 2.86→3.25),
   will_o_fawn (lure INT 2.45→2.8, passive INT 8→12). Snapshot regenerated
   (`tests/game/ability_formulas.snapshot.json`); diff touches only these 5.
3. **Iterate re-sweep** (`results/stat_edge_t36d.csv`, n=1500): zero champs over the
   `|wr_delta|>0.10` contract bar; all 5 moved the right direction; 44/60 inside
   ±0.05.
4. **§D.25 reframe** + `docs/live/content/rosters.md` validation note + T.36a/b/c
   status flips to Done.

## Why (the part SPEC compresses out)

The original D.25 framing was "INT ability coeffs are too low — raise them." The
full sweep falsifies the *direction* even though parity was reached: INT-ability
(n13, the big reliable bucket) sits exactly at budget. The gap is entirely
**STR-ability over-budget** — a STR ability-user gets the universal auto
(`1·STR + 0.25·INT`, 4× STR edge) as a *free tagalong* on top of its ability damage.
So the correct lever is trimming the STR-ability auto subsidy (or per-champ STR
trims), never a further global INT bump. Raising INT again would over-pay the
already-fair INT casters. This is why the tune trimmed mournhollow/ember (STR
ability) rather than touching the INT side.

We accepted the ±0.05 stretch miss on three stragglers (ember +0.088, mournhollow
+0.083, veilfang +0.083) deliberately: at n=1500 the per-champ noise is ±0.02–0.04
(untuned champs swung that much between the two runs), so chasing sub-0.05 there is
chasing noise, and the trims needed (~2–3×) would start eating champion identity.
The full random-vs-random power sim queued next is the higher-fidelity arbiter and
re-baselines everything — over-tuning stat_edge now produces signal that sim
supersedes.

## Decisions

- **Bar = the SPEC contract (`|wr_delta|>0.10`), not the ±0.05 stretch.** Met fully
  (zero over). ±0.05 deferred to the general sim.
- **Kings held to the same bar** (user call): mournhollow + aurion got no apex
  exemption; both now well under 0.10.
- **Damage-coeff trims move wr_delta weakly** — ember's −15%/−17% nuke cut moved
  wr_delta only −0.011. Recorded so future balance passes size trims realistically.
- **No new §V.** The tune is a numeric nudge, not a new structural rule; V.47
  (axis↔scaling) already guards the thing that could break, and it held.

## Process notes (AI collaboration)

- **Drift caught:** `docs/live/content/rosters.md` still read "sim balance-validation
  is deferred" and SPEC T.36b/c carried `~ Built; sim-validation deferred`. Both were
  stale the moment the sweep finished; reconciled in this same change (living-doc +
  spec in lockstep, per CLAUDE.md).
- **Misalignment (spec vs reality):** D.25 was marked RESOLVED/CONSUMED with "lever
  work closed," yet the validation surfaced a live +0.035 residual. Rather than
  re-open D.25, appended a dated reframe — the residual is real but is *not* the
  lever D.25 named, so "closed" stands with a clarifying note. Avoided renumbering /
  re-opening a resolved item for a finding that refines rather than contradicts it.
- **Agent error avoided:** first instinct on a "+0.035 INT-ability gap" is to raise
  INT coeffs (the literal D.25 prescription). The intent-slice in the data showed
  INT-ability at budget — so the fix was the opposite (trim STR-ability). Reading the
  cross-cell *before* acting prevented a wrong global bump.
- **Guardrail relied on:** the formula snapshot (`ability_formulas.snapshot.json`)
  caught exactly the 5 touched kits and nothing else — a cheap proof that the tune
  had no collateral. V.47's CI guard confirmed the trims kept every stat reference
  non-zero.

### Prompting-strategy reflection

High-leverage this round: the user front-loaded the decision forks (tune scope +
king policy) via a structured question *before* any edit, so the build step was
pure execution with zero mid-flight ambiguity. That "resolve the design forks, then
let the agent run" shape is becoming the dominant pattern on this project and it
keeps paying off — the agent does the investigation + proposes concrete numbers, the
human picks the policy, the agent executes.

Also high-leverage: insisting on reading the sweep *deeply* (cross-cell, not just
by-stat) before proposing tunes. The shallow read ("INT-ability gap → raise INT")
would have been wrong; the deep read flipped the prescription. Worth generalizing:
for balance work, always slice one level finer than the headline metric before
prescribing a fix.

Low-leverage / watch-out: the first tune undershot ±0.05 because I sized trims by
gut, not by a measured wr_delta-per-coeff sensitivity. Next balance pass should
estimate the sensitivity from one probe edit before committing to magnitudes —
would save an iterate cycle. The n=1500 re-sweep was the right call for a *direction*
check but too noisy for a *precision* check; matching sweep-n to the question
(direction vs precision) is the lesson.

## Files

- `src/game/abilities/champions.py` — 5-champ coefficient tune
- `tests/game/ability_formulas.snapshot.json` — regenerated (5 kits)
- `SPEC.md` — T.36a/b/c status → Done; T.36c sweep note; D.25 reframe
- `docs/live/content/rosters.md` — validation-done note + D.25 reframe
- `results/stat_edge_t36c.csv` / `_t36d.csv` — sweep outputs (n=8000 / n=1500)
