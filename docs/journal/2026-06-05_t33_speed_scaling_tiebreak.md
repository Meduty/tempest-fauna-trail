# 2026-06-05 — T.33: speed scaling, baseline parity, and the B.14 tie-break

Landed T.33a (`4fb416b`) + T.33b (`907fc70`): three-class stat scaling, speed-stat
baseline parity (#39), a 7-level speed axis, and — the headline — the real fix for
**B.14** (side-A deterministic win on equal-attack-speed ties). Touches V.34 (new),
V.35 (new), V.32 (cardinality 648→1512), B.14 (fix clause), D.18 (resolved/absorbed),
D.19 (#39 resolved). 680 tests pass.

## What changed

1. **Three scaling classes** (`scaling.py`) — `PRIMARY`/`SECONDARY`/`FLAT` tuples off
   one `power(T,L)` curve at two exponents (`0.5` / `0.0857` ≈ +2%/tier). New
   `level_scale_stats()` is the single source of truth, killing four duplicated
   scale loops in `content.py`/`encounter.py`.
2. **Speed-stat baseline parity (#39)** — `mana_regen` 10→100, `move_speed` 90→100 so
   AS/MS/MR read on one scale; `ability_cost` 36k→300k (a deliberate ~20% mage buff),
   boss costs ×10.
3. **`milli_AS`** — an int field carrying sub-integer attack-speed (`round(exact×1000)`),
   threaded through compose → level → weather, used only for ordering.
4. **The B.14 fix** (`engine.py`, `loadout.py`, `piece.py`) — `_event_sort_key` is now
   the canonical side-independent total order `(-AS_int, -milli_AS, champion_id,
   load_order, kind)`. `load_order` is a seeded permutation assigned in
   `compile_loadout`. The overloaded `speed_tiebreaker` was renamed `formation_index`.
5. **Speed axis 3→7** (`content.py`) — leaden/heavy/steady/hybrid/brisk/speedy/blinding;
   `tools/gen_role_matrix.py` regenerates the 1512-combo matrix; 10 champions reassigned
   so all 7 levels are used.

## Why (the part SPEC compresses out)

**The bug was never in the speed value — it was in the tiebreak.** We spent most of
the session chasing the wrong layer. The chain went: int speeds collide → make them
float → no, ×1000 fixed-point → no, store milli in a breaker field → and only then
the reframe: *the side-A bias lives in `speed_tiebreaker = input_index` (team block
before enemy block), so any tie hands the team priority.* The fix is to make the
**final tiebreak** side-independent (`load_order` = seeded permutation), after which
ties are fair **regardless of how often they happen** — so the whole float/int/×100
precision debate became almost moot for *correctness*. `milli_AS` survived only as a
*quality* refinement (break same-int-AS cross-power pairs by true speed instead of
arbitrarily), not as the fix.

**Why all-int, not float.** The user's principle: stored quantities are int (hp,
damage, mana, speeds) so the UI never shows `0` HP at `0.4`. The engine *already* runs
hp/damage/mana as float — that's a wart to remove later, not a pattern to extend. So
adding float speeds went the wrong way. `milli_AS` keeps the ordering precision in a
dedicated int field; the genuine float (`power**exp`) is a transient at stat-build.

**Why a true mirror still has a "winner".** Sequential combat means someone strikes
first; determinism means it's always the same someone; symmetry means the only thing
distinguishing two identical pieces is their side. So no unbiased deterministic draw
exists. `load_order` makes the winner a function of identity+seed, *not* "player
side" — aggregate win-rate is unbiased even though a given mirror always resolves the
same way. That honesty is in V.34 and the plan.

## Decisions

- **Fix the comparator, not the stat.** Side-independent `load_order` replaces the
  input-index tiebreak; absorbs the previously-deferred D.18.
- **`milli_AS` as a separate int field**, not float speeds and not ×100 fixed-point
  (which would force 6-million-magic thresholds + a `/100` display layer for a
  determinism win the float-based engine can't realise anyway).
- **Mage buff is deliberate** (cost 300k not the cadence-neutral 360k) — ~20% faster
  casts; flagged, not stealth.
- **Speed axis expansion is its own substep (33b)** — it touches the T.32 role-code
  taxonomy (1512 combos, V.32) and roster, so it rides *after* the engine fix, which
  is correctness-complete on its own.

## Process notes (AI collaboration)

- **Conflicts / misalignments.** The combat module was renamed mid-session
  (`loop_new.py→engine.py`, `legacy.py→resolve.py`) by a separate commit while the
  T.33 plan + SPEC still cited the old names. Caught on the "review the plan before
  continuing" checkpoint — re-pinned every `file.py:line` in the plan, SPEC B.14, and
  the memory file. Lesson: a rename is a cross-cutting drift event; grep the docs, not
  just the code.
- **Agent errors.** (a) First precision proposal was *float speeds*, reversed twice
  after the user pushed back ("are ints superior?" / "speeds are the only place float
  helps") — the agent over-indexed on "engine is already float" without questioning
  whether that float-ness was itself desirable. (b) The agent initially treated B.14
  as a *speed-precision* problem for many turns before recognising the bias was in the
  tiebreak field — a classic root-cause miss. (c) `milli_AS` shipped **desynced under
  weather** in the first batch (weather scaled `attack_speed` but not `milli_AS`);
  caught only by the explicit self-review step before continuing.
- **Guardrails added.** `tests/game/test_tiebreak.py` — asserts the tie breaks by
  `load_order` not side, that `milli_AS` overrides identity, that `load_order` is a
  side-mixed deterministic permutation, and that `milli_AS` tracks AS through weather
  (the regression for error (c)). `test_scaling.py` V-guards: the three classes are
  disjoint and cover `_BASE_STATS`.
- **Drift caught.** Vestigial `_BASE_STATS["ability_cost"] = 36_000` (dead — `compose`
  overwrites it) updated to 300_000. The `scaling.md` living-doc stub (explicitly
  "fill once T.33a lands") was filled; `combat.md`'s tie-break description was stale.

### Prompting-strategy reflection

The high-leverage move this session was the **user's insistence on review checkpoints
between batches** ("review the plan before continuing", "review the changes so far")
— both caught real defects (the rename drift; the milli-weather desync) that the
green test suite did *not*. Tests passing is not "done"; an explicit adversarial
self-review pass is a separate, load-bearing step.

The low-leverage pattern was the agent's eagerness to **commit to an implementation
before the design was settled** — it started editing `content.py` (float secondary
stats) while the precision question was still open, then had to revert framing
repeatedly. The user's "brainstorm with me / don't fire yet" steering was corrective:
for a decision with this many forks (float vs int vs fixed-point vs sort-term vs
axis-diversity), the right shape is *exhaust the design space in conversation, lock
it in the plan + SPEC, then batch the code*. The plan doc churned a lot precisely
because we were designing in it live — acceptable, but the lesson is to mark a plan
"locked" explicitly before build, and treat pre-lock plan text as scratch.

Evolving habit: **reframe before optimising.** Several turns of float/fixed-point
math evaporated the moment we asked "where does the bias actually live?". Asking the
root-cause question earlier would have saved them — a prompt like "before choosing a
representation, where in the code is the unfairness introduced?" is higher-leverage
than "how do we make speeds unique?".

## Files

- `src/game/scaling.py` — 3 class tuples, exponents, `stat_multiplier(...,exponent)`,
  `level_scale_stats`.
- `src/game/content.py` — `_BASE_STATS` (MR/MS→100, cost 300k), `_SPEED` 7 levels,
  `compose_stats` (+`milli_AS`), `_assert_budget` via tuple, 10 roster speed reassigns.
- `src/game/encounter.py` — both builders via `level_scale_stats` + `milli_AS`.
- `src/game/models.py` — `milli_AS: int` on Champion/Enemy (+validate/serialize).
- `src/game/piece.py` — `load_order`; `speed_tiebreaker`→`formation_index`.
- `src/game/loadout.py` — seeded `load_order` + `formation_index` in `compile_loadout`,
  `milli_AS` in base_stats + weather, `DEFAULT_ABILITY_COST`→300k.
- `src/game/combat/engine.py` — `_event_sort_key` total order.
- `src/game/combat/resolve.py`, `tools/playtest/_common.py` — removed redundant index loops.
- `src/game/formation.py` — rename. `src/game/bosses/data.py`, `abilities/bosses.py` — costs ×10.
- `tools/gen_role_matrix.py` (new), `docs/design/tasks/t32_role_matrix.txt` (1512).
- Tests: `test_tiebreak.py` (new), `test_scaling.py`, `test_content.py`, `test_role_intent.py`.
- Docs: `SPEC.md` (V.34/V.35/V.32/B.14/D.18/D.19/T.33a/b), `docs/live/systems/scaling.md`
  (filled), `combat.md` (tie-break), `t33_speed_scaling_plan.md`.

## Follow-ups

- **Sim validation** (skipped): confirm `weather_impact.py` mirror diagonal reads ~50%
  without `--both-sides`, and that the mage/movement buffs land where intended.
- **hp/damage/mana → int** — the engine's float quantities are a separate cleanup task
  (the int-everywhere direction this session articulated).
- **Full thematic speed re-spread** — only 10 champions reassigned to demonstrate the 7
  levels; a roster-wide pass + tuning is deferred.
- **Boss-cost rounding** — ×10 was mechanical; per-boss cast cadence not re-tuned.
