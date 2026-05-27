# 2026-05-27 — Playtest CLI findings

First end-to-end playtest pass after T.27. Fixed two engine bugs (DOT
attribution + sudden-death timeout); the rest is content / design notes
deferred for later passes. Findings below are surfaced by the new
`tools/playtest/` CLI.

## Fixed this session

### DOT attribution
DOT ticks in `loop_new.process_statuses` (and `loop.process_statuses`) passed
the victim as both attacker and target into `ctx.deal_damage`. Effects:

- Death log emitted `X is defeated by X` whenever DOT delivered the killing
  blow — including every sudden-death timeout, since sudden-death is a DOT
  status routed through the same path.
- `damage_dealt` totals inflated for the victim by the amount of DOT it took
  from someone else's status (e.g. observed `enemy_steam_engineer 3044` in a
  fight where Steam Engineer only had 159 INT).
- on-kill triggers fired against the wrong piece — the actual ability/passive
  applier got no kill credit.

`StatusInstance.source_id` already existed; `apply_status` already accepted
it. Fix:

- DOT processing looks up the applier piece by `source_id`; falls back to
  victim when source_id is empty (sudden-death + board slow-tiles use empty
  source — engine-applied, no caster).
- All ability callsites that apply DOT / control statuses now pass
  `source_id=actor.id` / `source_id=owner.id`. (`burn` from
  `ember_salamander.active`, `slow` from the marksman passive, `charged` from
  `static_buildup`.)
- Combat log now suppresses the ` by X` suffix when the recorded killer is
  the same as the victim — keeps engine-applied deaths readable.

### Sudden-death timeout
`MAX_TICKS=7_200` (12 rounds) was the dominant terminal state for any
multi-piece fight. Bumped to `12_000` (20 rounds). `sudden_death.dot_per_tick`
dropped from 5.0 to 0.5; combined with the new longer timeout this gives
sudden death room to escalate gradually instead of nuking everything in the
first second past the cap. Three files updated in lockstep:
`combat/loop_new.py`, `combat/loop.py`, `combat/legacy.py` (re-export).

### Verification
- 563/563 tests pass.
- Previous draw fights resolve as wins/losses now.
- Default T1L1 team on seed 42 / stage-affinity: was drawing at node 4 →
  now clears 6 nodes and **loses** at node 7. Real signal.
- T8/T9/T10 rain team on stage-1 boss: was drawing → now **loses** properly
  to the boss + 9 adds.

## Remaining findings — not fixed

### Content tuning

1. **Coral Colossus (T5 warrior) loses 1v1 to Conscript (T1 warrior)** in
   matched weather. Power scaling predicts 2.25× advantage; Colossus has AS 94
   vs Conscript AS 143, low STR-to-effective ratio, so Conscript out-DPSes
   130/cycle vs 68/cycle. Likely the warrior STR/AS curve is mistuned for
   tier 5.

2. **Weather impact is thin.** Damage triangle is ±10%
   ([weather_effects.py:167](../../src/game/weather_effects.py#L167)) and stat
   favor adjusts a couple stats by ~3-10% (mostly AS / one of STR/INT). In
   `sim_fight` a rain-affinity mage saw only ~3% damage delta between rain
   and thunder weather. Either widen the triangle or land favor on HP/damage
   so weather actually changes outcomes.

3. **T1 enemy roster is clear-only.** `inspect --kind enemy --tier 1` returns
   5 enemies, all clear-affinity. Rain enemies start at T3. Encounter gen on
   stage 1 can never weather-match. Decide: add T1 enemies for the other five
   affinities, or accept that the first stage is mono-clear by design.

4. **Stage-1 boss generates 9 adds + boss vs 3 champions.** Authored by design
   (`BossDef.fixed_cast` / `variable_cast` bypass `STAGE_MAX_SQUAD=4`). Even
   T10 team can't reach the boss — observed 68 dmg into Holloway over a full
   12-round fight. Either lower add count for early bosses, raise team cap
   for boss nodes (Tempest, planned T.22), or give the boss a focus-me
   mechanic.

5. **Iron Emperor adds mismatch affinity.** Final boss is snow-affinity in a
   snow city under snow weather; the 7 supporting cast are clear-affinity
   imperial troops. Probably narrative-driven (he commands the empire) but
   means the boss gets zero affinity synergy from his squad.

6. **T10 champions are stat-identical** across all six affinities (HP 1527 /
   STR 141 / INT 141 / AR 57 / RES 57 / AS 90 / MS 90). Differentiation lives
   entirely in abilities/passives. Worth flagging when ability content is
   reviewed — otherwise all six play identically at endgame.

### Naming / UX

7. **Node-type "reward" includes combat.** Stage 1 nodes 1 & 2 are typed
   `reward` and resolve as fights-with-reward (distinct from `fight`). The
   name reads like a no-combat reward; consider renaming to
   `fight_with_reward` or `easy_fight` so `sim_run` CSV columns are
   self-explanatory.

8. **`inspect --show-favor` only surfaces the stat-favor block.** Doesn't
   show the damage-triangle multiplier (the bigger effect). Add a triangle
   column or a separate `--show-triangle` flag.

### Process

9. **All five playtest CLIs run cleanly**, error paths reject unknown id /
   invalid weather / empty team. Determinism is solid (md5 of stdout
   identical on repeat runs, including boss encounters). The plan's P1-P4
   delivered exactly what was promised — no follow-up work on the CLI itself
   needed before the admin Flet view (Layer 2).

## Next

- Layer 2: scuffed admin Flet view (`/admin` route, env-flagged) reusing
  the Layer-1 CLI primitives. Started this session — see
  [docs/design/playtesting/plan.md §5.2](../design/playtesting/plan.md).
