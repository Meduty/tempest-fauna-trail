# 2026-06-17 — T.36b: champion roster re-axis + the multicaster cast-mechanic dig

The champion half of the T.36 roster rebalance. Re-axised the 60-champion roster
onto the target distribution, added the **Spellslinger** role, rebuilt the kits the
moves demanded, and — mid-batch — uncovered and fixed a dead-secondary cast bug
that grew into a mana-telemetry feature + a coprime-cost retune. Branch
`feature/t36b-champion-reaxis` (commits `54da1f5..3de7696`), stacked on T.36a.

## What changed

1. **Spellslinger role (V.32)** — `classify_role` gains a `ranged ∧ playstyle-hybrid
   ∧ damage` branch before mage/marksman. ROLE_TITLES 8→9; role matrix regenerated
   (1512 combos, 42 spellslinger). Pure-function foundation, no piece moved yet.
2. **The 3 flip kits** (caster→auto): dusk_bat str/auto support (Blinding Flurry
   AS-shred — the `slow` status is cosmetic so a real `attack_speed` Modifier is
   used), phantom_lynx int/auto swashbuckler (Phantom Claw flat-pen + on-hit, Soul
   Reap empower-next-auto via the new `soul_charged` marker), granite_gorilla str/auto
   tank (Stone Charge capacitor — `stone_charge` stacking status banks STR, autos
   discharge half, Ground Slam dumps the bank).
3. **Off-role batch fills** — bruiser ×6, assassin ×4, spellslinger ×4. The
   discovery: **these were mis-LABELED, not mis-built** — every bruiser already had
   a brawler kit, every assassin a burst-dive kit. Almost all were pure axis edits.
4. **Multicaster cast-mechanic workstream** (the session's rabbit hole — see Why):
   mana telemetry on the combat log (CastEvent→BattleEvent slot/cost/mana), coprime
   secondary-cost retune un-starving the 4 lower multicasters, tempest_eel converted
   to the 4th spellslinger (kept its ult), a strict unique-slot-priority guard.
5. **Batch 5 + stat-swaps** — 12 tank/marksman/spellblade axis fills + 3 stat-swap
   kit rebuilds (dawnwisp/ember int→str, goldcrest int→hybrid). Roster landed
   **every target exactly**: roles 11·11·9·6·6·5·4·4·4, stat 22/22/16, play 24/24/12.
6. **Flag resolutions** — marsh kept pure-INT (conventions exemplar re-pointed to
   dawnwisp); 4 assassins got distinct scoped survival (untargetable / barrier /
   lifesteal / hit-and-run); Bruiser/Stalker apexes retuned 8→10 / 7→8 to match the
   pools the +Calling tweaks grew (V.37 apex = min(pool, cap)).
7. **Two sweep-driven tunes** — ember_salamander trimmed (+0.149 over) and will_o_fawn
   buffed (−0.097 under).

## Why (the part SPEC compresses out)

**The roster was mis-labeled, not mis-built.** The single biggest time-saver: before
each off-role batch I checked the existing kits, and bruisers/assassins already
*were* brawlers/divers — only their `intent`/`playstyle` axis lied about it. So most
of T.36b is axis edits, not kit rewrites. The conventions doc predicted this ("an
off-reading role on re-axis is a signal"), and it held.

**The multicaster dig.** tempest_eel was the awkward 4th spellslinger (a double
cast-Calling Mystic/Multicaster). Investigating its cadence, the mana telemetry I
added to *instrument* the question immediately showed the real bug: the lower-tier
multicaster **secondaries never fired**. Root cause: `_charge_mana` routes regen by
priority weight (V.48), so a same-cost lower-priority secondary charges at ~1/3 rate
and needs ~6200 ticks to reach threshold — longer than most fights. The fix had to
respect the user's hard constraint (don't touch priority or MR allocation — the only
knob is ability cost/power): make secondaries **cheaper** (fire in fight-length) with
**coprime** cost ratios to the primary (cadences never lock in step), and weaker to
stay budget-neutral. This was pure number theory in service of game-feel.

**Balance is a loop, not a guess.** The assassin-survival decision was deliberately
deferred to the running sweep — which then confirmed 3 of 4 sat under budget, turning
"should they have sustain?" from opinion into data. Same sweep caught my own ember
overshoot (+0.149, the int→str swap compounding with cheaper costs and an un-starved
secondary). Tuned, re-sweeping. The re-sweep did **not** finish before EOD — so the
ember/will_o_fawn tunes, the assassin survival magnitudes, and the breakpoint retune
are all **sim-unvalidated** as of this entry (see Follow-ups).

## Decisions

- **Spellslinger landed as a pure function first**, committed alone — zero kit risk,
  and no piece becomes one until a later axis edit lands it. Foundations before fills.
- **granite's capacitor uses a stacking status, not a closure** — so the active can
  read/dump the bank the passive builds without any engine/model change (the user's
  stacks idea solved the cross-function-state problem cleanly).
- **Assassin survival is varied, not 4× lifesteal** (user steer) — evasion/mitigation/
  sustain/escape, each thematic and scoped to the commit move (conventions #10).
- **marsh stays INT** — the plan's "utility-INT/damage-STR, axes unchanged, V.47-hybrid"
  was self-contradictory; keeping it INT and fixing the doc was cleaner than forcing a
  marginal-breaking hybrid swap. Distribution was already exact without it.
- **No new §V for the distribution target** — it lives in the plan + the role counts;
  the soft guard is the test. (The marginals still have no living-doc home — known gap.)

## Process notes (AI collaboration)

- **Bug found by instrumentation, not by grep** (reinforces a prior memory). The "0
  casts" smell was real this time, but the *recorder* could have been lying again
  (B.21). Wrapping `cast_ability` to count + adding mana to the event stream proved
  the secondary genuinely never fired, and the mana telemetry then doubled as the UI
  feature. Instrument the path; don't trust or grep a zero.
- **User constraints redirected the fix.** My first instinct for the dead secondary
  was "fix the charge split / priorities." The user vetoed touching priority or MR
  ("the knob is cost/power") — which forced the coprime-cost solution, a better fix
  (no engine change, self-documenting via the test). The strict-priority-uniqueness
  guard was also a user ask, kept as a forward guardrail.
- **Decide-and-flag worked well at batch scale.** Per-batch checkpoints + flagging
  judgment calls (granite active-dump dropped-then-restored, the assassin lifesteal
  held, the trait adds) let the user catch and redirect three things I'd have
  otherwise committed silently: the survival-variety steer, keeping marsh INT, and
  retuning the breakpoints rather than reverting the trait adds.
- **My own overshoot, caught by the gate.** ember +0.149 was a self-inflicted stack
  of buffs (int→str coeff + cheaper cost + un-starved secondary). The sweep caught it
  exactly like Borealis in T.36a. Moderate trim + re-sweep, not a big swing (will_o_fawn
  is the cautionary tale — its ×0.5 nerf overshot the other way).
- **Trait adds have a synergy cost.** Adding auto-Callings for Calling-honesty grew
  the Bruiser/Stalker pools, which silently shifts their apex semantics (V.37
  apex=min(pool,cap)). Easy to miss; the user flagged trait changes up front, which is
  why it surfaced.

### Prompting-strategy reflection

The standing "consult before kit/trait changes, flag anything odd" instruction turned
a 60-piece mechanical re-axis into a genuinely collaborative loop — and it paid off
most on the *unplanned* branch (the multicaster bug). I didn't predict that flag; I
found it because instrumenting one piece's cadence was cheap, and the user's follow-up
nudges ("the secondary never fired is suspicious", "vary the costs to coprime") shaped
a feature-sized detour mid-task. The lesson reinforced across T.36a→b: **lead the user
the mechanically-dominant lever, not a menu of equals** — I wasted a sweep in T.36a
offering "revert INT" for Borealis; this time I correctly read the charge-rate as the
driver and brought the cost knob. Per-batch commits also kept the diff legible across
~16 commits, so each decision is independently reviewable — worth the slight overhead.

## Files

- `src/game/content.py` — ~37 champion axis edits + 3 Calling tweaks.
- `src/game/abilities/champions.py` — flip/assassin/stat-swap/tempest kit rebuilds,
  survival adds, multicaster cost retune, ember/will_o_fawn tunes.
- `src/game/status.py` — `soul_charged`, `stone_charge` (+ T.36a `grief`, `nerei_grudge`).
- `src/game/events.py`, `models.py`, `combat/context.py`, `combat/recorder.py`,
  `combat/engine.py`, `combat_log.py` — mana telemetry plumbing.
- `src/game/traits/callings.py` — Bruiser/Stalker apex retune.
- `tests/game/` — role/multislot/hexproof test updates + the unique-priority guard.
- `docs/live/systems/kit_design_conventions.md` — exemplar re-pointed to dawnwisp.
- `tests/game/ability_formulas.snapshot.json`, `docs/design/tasks/t32_role_matrix.txt`
  — regenerated.

## Follow-ups

- **SIM BALANCING STILL DUE (carry into T.36c).** The T.36b re-sweep did not finish
  before EOD. Unvalidated by sim: the ember_salamander trim + will_o_fawn buff (tuned
  blind to confirm they landed in-band), the 4 assassin survival magnitudes, and the
  Bruiser/Stalker apex retune. Re-run `python -m tools.simulation.stat_edge
  --team-sizes 3 --n 4000 --weather all` and tune any |wr_delta| > ~0.10 outlier.
  Known going in: mournhollow +0.089 (T.36a-deferred), aegis_tortoise reads low
  (utility tank). **Fold this validation into T.36c's acceptance** — enemies are
  re-axised against champions anyway, so one combined sweep validates both.
- **marsh_thrush** flavor refinement (utility-INT/damage-STR) intentionally dropped.
- **T.36c** (enemy roster re-axis) is the remaining T.36 substep.
- The distribution target still has no auditable living-doc home (the soft guard test
  is its only home; write it in T.36c if not already).
