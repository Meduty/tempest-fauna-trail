# 2026-06-03 — DOT cadence rework + per-instance potency + Focus Fire

## What changed

Two combat-system changes landed together, plus one content passive that
exposed the gaps.

1. **Focus Fire** (`enemy_company_captain.passive`) — captain hit marks the
   struck enemy with a new `focus_fire` marker status **and raises the target's
   `threat`** (a TIMED modifier expiring with the mark) so the captain's allies
   focus it — `_select_target` sorts on `-threat` first, so the mark literally
   redirects targeting. An ally *other than* the captain hitting a marked target
   then deals bonus INT magic damage from the captain. Bonus + threat both scale
   with captain `level`. Recursion-guarded via an `in_bonus` flag.
2. **`Piece.level`** — the combat `Piece` now carries `level` (1–3), copied from
   `Champion.level`/`Enemy.level` in `loadout.piece_from_*`. Previously level
   lived only on the source model and never reached combat, so level-scaling
   passives had nothing to read.
3. **DOT cadence rework** — DOT now fires on a per-status interval, not every
   engine tick; per-instance `potency` lets casters scale a DOT; status identity
   pinned to `status_id` (Option 1 / TFT-style).

## Why (the part SPEC compresses out)

Building Focus Fire surfaced that the status substrate had two latent problems,
both rooted in the same false assumption: **tick ≈ turn**. It isn't.

- 1 action ≈ **600 ticks** (`ENERGY_THRESHOLD 60_000` / AS 100). A tick is 10ms;
  an action is ~6s. DOT was processed **every tick**.
- So `burn` at `dot_per_tick=2.0` was really **200 dmg/s** — and `poison`'s
  `decay_stacks_per_tick` removed a stack **every 10ms**, draining a 4-stack
  poison in 4 ticks (~40ms, ~15 dmg total). Its `duration_ticks=400-500` was
  **dead code**, and poison sat ~40× weaker than burn with nothing visible at the
  call site. (Backpropped as SPEC B.11.)
- `dot_per_tick` was static on the shared `StatusDef`, so no caster could scale a
  DOT — every burn identical T1↔T10. Focus Fire wanted INT/level scaling and had
  to push it into the passive instead of the status.

## Decisions

- **Cadence is data, not a constant.** `StatusDef.dot_interval_ticks` (default
  100t = 1s). `sudden_death` overrides to `1` (per-tick) — it's a TRUE-damage
  timeout failsafe that *wants* a smooth per-tick ramp, and per-tick + per-tick
  stack-accrual stay coherent. The "exception" is just a field value, no
  `if status_id == ...` hack. sudden_death ends up byte-for-byte unchanged.
- **Option A ordering** — DOT pays its final tick on the same engine tick it
  expires (DOT runs before the expiry check). Avoids an off-by-one where a
  200t burn would only tick once.
- **Free-running DOT clock** — `StatusInstance.ticks_to_next_dot` is seeded once
  and never reset on reapply. A reapply refreshes duration/stacks but can't push
  back the next tick. Without this, poison-on-every-auto (faster than the 100t
  interval) would shove the trigger forward forever and deal 0.
- **Single instance, strongest-wins** — identity = `status_id` only. Two burns
  from two pieces merge into one; the higher `potency` wins and takes damage
  credit. Chose this over per-`(status_id, source_id)` instances: same-DoT
  overlap is rare in a roguelike, and single-instance avoids instance explosion
  + keeps CC identity (you don't want 5 independent stun timers). Poison still
  ramps via `StackBehaviour.STACK`. (TFT burn is the reference: %HP, non-stacking,
  strongest applies — we kept the non-stacking identity, went flat+`potency`
  instead of %HP so the caster's INT matters.)
- **Granularity stays 1s.** Considered 0.5s / 0.1s. Finer re-introduces the
  proc-spam (DOT fires `on_damage_*` → reflect/stack procs), the `max(1.0)`
  per-tick floor leak (≥1/tick through infinite resistance), and re-shrinks
  poison decay. The per-status field is the escape hatch if a future "rapid
  bleed" wants 50t.

## Retune (provisional — pending sim sweep)

| status | old (per engine tick) | new (per DOT tick ≈ /s) |
|---|---|---|
| burn | 2.0 | 40.0 |
| poison | 1.5 / stack | 18.0 / stack |
| sudden_death | 0.5 (unchanged) | 0.5, interval 1 |

Scan confirmed **no live sub-100t DOT** before the change (all burn ≥200, poison
≥400), so nothing silently dropped to 0.

## Files

`status.py`, `piece.py`, `loadout.py`, `combat/context.py`, `combat/loop_new.py`,
`combat/loop.py` (legacy, kept in sync — still imported by `test_abilities.py`),
`abilities/enemies.py`. Docs: SPEC V.25-V.27 + B.11, `effect_systems_design.md`
(§5 apply_status sig, §10.2 pseudo fix, decision #11), `t20_ability_framework_plan.md`.

## Follow-ups

- Run a `tools/simulation` sweep to finalize 40/18 (and whether burn/poison want
  different `dot_interval_ticks`).
- The `max(1.0)` damage floor in `deal_damage` now leaks ≥1/s per DOT instead of
  ≥100/s — much tamer, but DOT may eventually want to skip the floor entirely.
- `potency` can express %max-HP DOTs later (`potency = target.max_hp * pct` at
  apply, or a `dot_pct_max_hp` flag) if an anti-tank burn is wanted.
