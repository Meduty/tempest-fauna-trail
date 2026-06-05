# 2026-06-06 — T.28b: trait combat primitives (engine cluster)

## What shipped

T.28b is **done** (✅). The hook-based half (second-wind, tidal HoT, enrage,
time-ramp, dodge, untargetable opener + `StatusGate.UNTARGETABLE`) landed in a
prior session (commit `67e1087`). This session completed the **engine-behaviour
cluster** — the four primitives that needed real movement/targeting/death edits:

- **Kiting** (Skyborn @2) — `Piece.is_kiter` set by an `on_combat_start` hook;
  melee carriers (base range ≤1) also gain +1 `attack_range` (conditional, so it
  never doubles with Skyborn @5's flat +1). Engine `_kite_step` runs in the
  movement phase: retreat one hex from a **single** adjacent melee threat to a
  tile that strictly increases distance from it while keeping ≥1 enemy
  attackable. Guardrails (all from the catalog §7): plant when ≥2 melee adjacent,
  plant when cornered (no improving tile), never kite without an attackable
  target (advance instead), only kite range-1 threats. Tie-break: max distance,
  then most-enemies-still-attackable (lateral over corner), then hex-direction
  order.
- **Backline target-priority** (Stalker @2) — `Piece.seeks_backline`; the engine
  paths toward the deepest enemy column (`_backline_subset`, max `position_q`)
  and `_select_target` prefers it. Falls back to the full enemy set when the
  backline is unreachable. No teleport.
- **Taunt** — a gate-free `taunt` StatusDef whose `source_id` is the taunter.
  `_taunt_target` forces the taunter as both attack target (overriding the
  "keep current target" shortcut) and movement goal. Capability only this task;
  Trickster's taunt-on-cast wiring is T.28c.
- **Revive** (Mender @6) — `ctx.revive(target, hp_frac)` reverses the death path
  (restore liveness + O(1) count, clear stale barriers, hp = 0.3·max_hp). An
  `on_death` hook fires it for the **first ally death each combat**, deduped
  across all carriers via a flag on `ctx`. The one true revive (V.37).

12 new tests (`test_trait_mechanics.py`, 20 total). Full suite **733 passed,
101 skipped**. Two identical sims are byte-identical (V.2/V.14).

## Key decisions / why

- **Flags over trait-id special-casing.** The engine stays content-agnostic: it
  reads `is_kiter`/`seeks_backline`/`taunt` status, never "if Skyborn". Traits
  *arm* the behaviour via `on_combat_start` hooks (same idiom as
  `untargetable_opener`). Keeps the engine free of the trait vocabulary.
- **Movement goal, not just target.** Backline/taunt only matter if the piece
  *approaches* the right enemy. So the `in_range`/hold decision and BFS goal use
  the biased subset (`goal_enemies`), not the full enemy list — otherwise a
  Stalker just attacks whatever frontliner is adjacent and never seeks. Fallback
  to the full set prevents a stuck seeker.
- **Revive dedup via `ctx` flag, not `ONCE_PER_COMBAT` scope.** The bus dedup
  ledger keys `ONCE_PER_COMBAT` on `hook_id`, which is per-subscribed-hook — a
  TEAM_WIDE apply subscribes one hook *per carrier*, so that scope would give one
  revive *per Mender*, not one total. A shared `ctx._mender_revive_used` flag is
  the only correct "once across all carriers". `ctx` is fresh per combat so it
  self-resets.
- **Conditional melee +1 range read at `on_combat_start`.** Stat-pack modifiers
  (incl. Skyborn @5's flat +1) are applied at loadout, *before* combat start, so
  `owner.stat("attack_range")` already reflects @5 when the kiting hook checks
  `≤1`. That's why @2+@5 melee Skyborn don't stack to +2 — the check sees range 2
  and skips. Verified by `test_kiting_no_double_range_for_already_ranged`.
- **Catalog said +1 range at @2, code had it at @5.** Catalog Skyborn: @2 melee
  +1 (kiting coherence) **and** @5 flat +1 (all). Both are real and distinct;
  kept @5's stat-pack add and added the @2 conditional via the kiting hook.

## Process notes (AI collaboration)

- **Doc drift caught (CLAUDE.md vs catalog):** the prior-session summary said
  "@5 adds attack_range +1" as the *only* range bump, implying @2 had none. The
  catalog actually specifies range bumps at **both** @2 (melee) and @5 (all).
  Reading the frozen catalog block directly (not trusting the summary) caught it
  — exactly the "design docs lie, verify against source" rule, applied to a
  context summary rather than a design doc. Lesson: a compaction summary is a
  lossy secondary source; reconcile it against the frozen catalog before coding.
- **Bus-scope trap:** my first instinct for "revive once" was
  `HookScope.ONCE_PER_COMBAT`. Reading `effects.py:_should_dedup` showed the key
  is `(combat, hook_id)` — per hook, not per team. Caught before writing it;
  would have shipped a silent "one revive per Mender" bug (a stacking cheat-death
  the design explicitly forbids). Reading the dedup implementation, not its name,
  was what saved it.
- **No backprop needed** — no test failed; the careful pre-reads (engine, bus,
  loadout apply path) front-loaded the bug-finding into design.

### Prompting-strategy reflection

This slice was deliberately deferred to a *fresh context* ("do kiting/taunt/
backline/revive next session") precisely because it was the invasive engine work
— the earlier session stopped at a clean checkpoint rather than push tired
context through delicate movement code. That paid off: the whole cluster landed
in one pass, no failed verification, because the session opened with a full
re-read of the four touch-point files (`engine.py`, `context.py`, `targeting.py`,
`piece.py`) and the effect substrate *before* any edit. The pattern that keeps
working on this project: **read the substrate's implementation (not its
docstring) for anything with shared/dedup/cached state** — the `max_hp` cache
(T.28a) and the `ONCE_PER_COMBAT` ledger (here) were both invisible-until-read
traps. Splitting T.28b's hook-half from its engine-half along the
"needs-engine-edits" seam was the right cut: the hook half was mechanical, the
engine half needed care, and isolating them kept each verification crisp.

## Follow-ups

- **T.28c** — echo/double-cast, mana-denial aura, ability-splash, Swarm on-death
  spawns, Hunter empowered-shot/pierce/cleave, Scaled weather-as-buff, Primordial
  kit hooks, Packmate `@full-board`, apex effects. Trickster taunt-on-cast wires
  to the taunt capability built here.
- **Sim re-baseline** — traits now change combat (Skyborn kite, Stalker seek,
  Mender revive); the T.25 power sim should be re-swept once T.28c lands.
- **Magnitudes** (revive 0.3, second-wind 0.4/1200t, etc.) are first-pass —
  deferred to the sim sweep per the catalog "still open" list.
