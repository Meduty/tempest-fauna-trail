# 2026-06-04 — T.32 role/intent revamp (implementation)

Built T.32 against the approved plan (`t32_role_intent_revamp_plan.md`) and the
already-committed invariants V.31/V.32/V.33. Adds a 6th archetype axis `intent`,
reworks `compose_stats` into a full composer, replaces the flat
`_ROLE_FROM_AXES[stat][reach]` map with `classify_role` + `build_role_code`, and
fixes `stat_overrides` scope/ordering. Status flipped 📋→✅. Suite 729→768 green.

## What changed

1. **6th axis `intent` (damage/hybrid/utility)** on `ChampionDef`/`EnemyDef`
   (`content.py`) + `BossDef` (`bosses/data.py`), authored from the roster
   archetype tags (`champion_roster.md`/`enemy_roster.md` master matrices:
   Tank-*/SUP-*→`utility`, APC-*/ADC-*→`damage`, Hybrid-*→`hybrid`). Champs
   24/24/12, enemies 24/19/17, bosses default `hybrid`.
2. **Full composer** (`content.py:compose_stats`) — now generates *every* stat
   incl. `threat` (durability/playstyle/intent weights) and `move_speed` (speed
   axis); `ability_cost`→module constant `_ABILITY_COST`; dead per-unit
   `move_speed`/`threat`/`ability_cost` Def fields deleted.
3. **8-role classifier + role_code** (`classify_role`/`build_role_code`) replace
   `_ROLE_FROM_AXES`. `Champion`/`Enemy` gain `intent`+`role_code` (defaulted,
   validated, round-tripped, back-compat read) in `models.py`.
4. **`stat_overrides`** scope=all-stats (key-validated against `ALL_STAT_KEYS`)
   + applied after-tier-before-level; premium overrides now forwarded to the
   model (`crit_chance`/`penetration`/`penetration_pct`).
5. **Consumers**: `encounter.py` (`_is_support`→intent; both Enemy builders),
   `formation.py` (`range_`→`reach`), `matchup.py`/`report.py` (emit
   role_code+intent), `_common.py`/`inspect.py` (INTENT column + `--intent`
   filter), `admin.py` (intent dropdown).
6. **Tests**: new `test_role_intent.py` (38 — classifier 8-role, 648-matrix vs
   `t32_role_matrix.txt`, injectivity, drift guard, V.31 roster/boss guard,
   composer, override scope/ordering); updated `test_content.py`/`test_formation.py`.
7. **Doc drift (B.13)**: `t5_content_plan.md` "4 orthogonal axes" annotated → 6.

## Why (the part SPEC compresses out)

- **The legacy role bug was invisible in the diff.** `_ROLE_FROM_AXES[stat][reach]`
  read 2 of 5 axes, so a damage-bruiser and a peeling support were the *same
  role string*. Role wasn't wrong-looking — it was under-determined. The fix is
  a classifier that's a pure function of all 6 axes, with `role_code` as the
  lossless fine descriptor (hybrid-stripped, so it's injective over 648 combos).
- **`threat` was the one never-composed stat** — flat 60 for every piece because
  no axis touched it and `d.threat` was authored 0× (dead default). Composing it
  (tanks pull, casters sneak, utility holds aggro) gave threat diversity without
  a 7th "taunt axis" — the rejected alternative.
- **Intent is a re-flavour, not a buff.** The ±10% HP·DPS drift guard exists so
  `damage`/`utility` shift the *shape* of a power budget (bursty-fragile vs
  durable-enabling) without moving the total. `threat`/`move_speed`/premium sit
  off-budget by design (B.6), so the threat-bias is free.

## Decisions

- **Role ≠ archetype label.** Sunmane Lion is a "Tank-STR" in the roster but has
  `hybrid` (standard) durability, so `classify_role` returns `support`, not
  `tank`. Intended: role is `f(axes)`; the archetype label only seeds `intent`.
  A future agent will be tempted to "fix" this — it's not a bug.
- **Bosses carry `intent` but keep `role="boss"`.** They're authored set-pieces
  outside the 648-combo classifier; `intent="hybrid"` satisfies V.31 as metadata.
- **`ability_cost` demotion preserves deviation.** Demoted to a constant, but
  per-champ cost deviation survives via `stat_overrides={"ability_cost": Δ}` —
  the same audited, key-validated path as every other stat (answered a mid-build
  user question; no code change needed).

## Process notes (AI collaboration)

- **Two mid-stream user pivots, both adopted.** (1) *"Why the ability_cost
  demotion? some champs could deviate"* — surfaced that I'd under-explained: the
  capability isn't lost, it moves to `stat_overrides`. No code change, but the
  question was correct to ask and worth a clear answer. (2) *"all stats default
  hybrid, deviate via kwarg (like speed), except reach"* — a genuine ergonomics
  improvement. I'd first written the def tuples in full-positional 6-axis form
  (`"int","ranged","hybrid","ability","utility"`); the pivot made them named-
  kwarg, deviations-only (`stat="int", playstyle="ability", intent="utility"`),
  which is reorder-safe and self-documenting. Cost: a second 120-line rewrite of
  both rosters — but it produces *identical* `ChampionDef` objects, so it was a
  pure call-site refactor with zero test impact.
- **Conflict caught — test invariant outdated by the feature.** `test_content.py::
  test_flat_stats_same_across_tiers` grouped champs by 5 axes and asserted equal
  `attack_speed`. T.32 makes `attack_speed` also scale with `intent`, so two
  same-5-axis champs with different intent legitimately differ. The test was
  *correctly* failing; fix was to group by all 6 axes, not to weaken the assert.
  This is the good kind of red — a guard noticing a real semantic shift.
- **Guardrails added.** `test_role_intent.py` asserts the full 648-combo matrix
  against the committed fixture (so the classifier can't silently drift),
  role_code injectivity, the V.31 roster/boss intent guard, and the intent drift
  band — the invariant-as-agent-guardrail pattern from B.13.
- **Drift reconciled.** `t5_content_plan.md` still claimed "4 orthogonal axes"
  (B.13); annotated to 6 with the rename history rather than rewriting the
  historical T.5 doc.
- **No determinism regression (V.2).** Composer shifts every piece's
  threat/move_speed and damage/utility stats, so combat outcomes moved — but
  same-seed runs stay byte-identical, and there were no committed golden combat
  baselines to regenerate (the sim emits fresh CSVs).

### Prompting-strategy reflection

The high-leverage move this session was **front-loading the entire read set
before any edit** — SPEC §V/§T/§B, the plan doc, the matrix fixture, all five
roster docs, and every consumer (`grep` for `_ROLE_FROM_AXES`/`primary_stat`
call sites) — so the 120-line roster rewrite and the consumer fan-out were
mechanical, not exploratory. Because the plan + invariants were already
committed, "build t32" was effectively an *execution* prompt, not a design one;
the cheapest path was to treat the plan as ground truth and verify each
primitive against code (the `intent` authoring came straight from the roster
master matrices, not guessed).

What's evolving: the user is now comfortable **interrupting mid-build with design
pivots** (the kwarg-default change landed after I'd already written the positional
form). The lesson is to keep edits *cheap to redo* — because the def tuples were a
single `Edit` block each, the second rewrite cost two tool calls, not a day. When
a refactor produces *identical objects*, doing it eagerly on request is low-risk;
I leaned into that rather than deferring. The under-leverage risk I'm watching:
batching too much into one turn — this was a 6-file change verified only at the
end. It held (one expected red, fixed), but a tighter loop (run `content.py`
import after the composer rework, before the roster rewrite) would have caught a
structural error sooner if one had existed.

## Files

- `src/game/content.py`, `src/game/models.py`, `src/game/encounter.py`,
  `src/game/formation.py`, `src/game/bosses/data.py`
- `tools/simulation/matchup.py`, `tools/simulation/report.py`,
  `tools/playtest/_common.py`, `tools/playtest/inspect.py`, `src/ui/views/admin.py`
- `tests/game/test_role_intent.py` (new), `tests/game/test_content.py`,
  `tests/game/test_formation.py`
- `SPEC.md` (T.32 status), `docs/design/tasks/t5_content_plan.md` (B.13)
