# 2026-06-06 — T.28c: trait mechanic + apex riders (hook batch)

## What shipped

T.28c is **done** (✅). It wires the bulk of the remaining trait mechanic/apex
riders as deterministic **hook idioms over the existing `ctx` mutators** — no new
engine subsystems. ~20 builders in `game/traits/mechanics.py`, attached to the
relevant rungs in `kinships.py` / `callings.py`.

Covered: Hunter (bonus-auto/empowered-shot/cleave/team-aura), Mystic
(`ability_can_crit`+splash), Guardian (start+periodic shields), Bruiser
(attack-lifesteal +team), Skirmisher @8 (team ramp+dodge), Stalker
(hi-HP-bonus/mana-on-kill/untargetable-after-kill), Channeler
(free-cast/first-cast-twice), Warden (cast-shield-lowest/team-opener), Trickster
(slow-on-cast/taunt-on-cast/mana-denial-aura), Mender (heal-splash/overheal-shield),
Spirit (echo), Swarm (on-death chitin spawn), Packmate (`@full-board` = its stat
pack). 16 new tests (`test_trait_riders.py`); suite **749 passed / 101 skipped**;
trait-heavy sim byte-identical.

## Scope split (why T.28c shrank, T.28d born)

The original T.28c row claimed "M" but listed effects needing whole new
subsystems (echo potency-reduction, pierce-untargetable gate, ability-haste pool,
CC-immunity, weather-as-buff override, 6 bespoke Primordial kits, 6 affinity apex
riders). Per the user's "pragmatic batch + split" call, `/spec amend` narrowed
T.28c to the hook-idiom batch and created **T.28d** for the subsystem-heavy +
currently-dormant remainder (Primordials are augment-gated, unreachable until
T.31 — no reason to build their kits before they can be fielded).

## Key decisions / why

- **No new subsystems (user directive: no parallel systems).** Every rider is a
  `Hook` over `deal_damage`/`heal`/`grant_barrier`/`apply_status`/`gain_mana`/
  `cast_ability`/`spawn`. Chitin reuses the existing **summon pattern** (`Piece`
  + summon flags + `ctx.spawn`) that bosses/champions already use — not a new
  spawn path. Echo reuses `ctx.cast_ability`. Taunt-on-cast reuses the T.28b
  taunt status. The engine was not touched at all.
- **`SourceTag.ITEM_PROC` for all secondary damage.** It's the existing tag for
  follow-up hits that must not re-fire `on_attack_landed`/`on_ability_damage` —
  so bonus-auto/empowered/cleave/splash/high-HP-bonus can't recurse. No new
  `SourceTag.TRAIT` (would have rippled through the recorder/log for no gain).
- **Cumulative rungs.** The big correctness rule: resolution applies only the
  **single highest cleared rung's** bundle, so every rung must re-include the
  mechanics it should still grant. This also surfaced a **latent T.28b bug** —
  Skirmisher's `time_ramp` was only on @2 and `dodge` only on @4, so a 4+-Skirmisher
  board silently *lost* the ramp (the @4 rung replaced @2). Fixed by carrying
  `time_ramp` on @2/3/4/5/8 and `dodge` on @4/5/8. (No §B entry: caught and fixed
  inside the same trait-wiring pass before it ever shipped a test; noted here.)
- **Apex scope exception.** Carrier-*movement* mechanics (kiting, backline) are
  NOT re-applied at a TEAM apex — team-wide they'd make everyone kite/seek. Apex
  trades the few-carrier identity for a team buff. Caster/role-gated riders (echo,
  splash, lifesteal, shields, on-death spawn) are team-safe (no-op for the wrong
  role); the Swarm spawn is `trait="Swarm"`-guarded so a TEAM apply only spawns
  for Swarm pieces.
- **Cast riders only fire for registered abilities.** The unregistered fast-path
  in `_resolve_action` deals damage without firing `on_cast`/`on_cast_complete`.
  Acceptable — T.30 registered all 120 roster abilities, so carriers have real
  casts. Documented in the living doc.
- **Deliberately deferred flavor (not in any task):** Beast @4/@6 ramp, Skyborn
  @3 kite-reward, Tidekin @3 ally-heal. They weren't in the agreed T.28c list and
  aren't subsystem-heavy enough for T.28d; those rungs ship stat-only. Recorded in
  the living doc so it's a known gap, not silent drift.

## Process notes (AI collaboration)

- **Asked before building.** T.28c's true size was obvious on first read (it
  needed subsystems the "M" estimate hid). Rather than guess, I surfaced the fork
  with `AskUserQuestion` (pragmatic-split vs full-faithful). The split kept this
  pass shippable and testable; full-faithful would have been a multi-session slog
  against the 733-test suite. Lesson reinforced: when a task row and its real
  scope disagree, escalate the *scope*, don't quietly half-build.
- **User mid-flight steer — "no parallel systems."** Arrived while I was writing
  builders; it matched the chosen approach (hooks over existing ctx) and I called
  it out explicitly (ITEM_PROC reuse, summon-pattern reuse, no engine edits)
  rather than inventing a trait-damage tag or a bespoke spawn path. The steer
  mostly confirmed direction but tightened the chitin design (reuse summon, don't
  add a template module).
- **Latent-bug catch came from the framework, not a test.** Re-deriving "only the
  highest rung applies" (from `_resolve_traits`) is what exposed the Skirmisher
  ramp-drop — reading the resolution code, not running combat, found it. Same
  pattern as the T.28b `ONCE_PER_COMBAT` trap: the bug lived in shared-state
  semantics that only a read of the substrate reveals.
- **No backprop needed** — no test failed; the cumulative-rung issue was fixed in
  the same edit that introduced the wiring.

### Prompting-strategy reflection

The decisive move this turn was the `AskUserQuestion` *before* any edit. Three
sessions of trait work (a/b/c) have settled into a rhythm: read the substrate →
size the real task → if it exceeds its row, split via `/spec` and ask → build the
bounded slice → prove determinism. The `/spec` split is doing real work as a
scope-control valve: T.28 has now legitimately become a/b/c/d, each shipping
green, instead of one ballooning "traits" task that's perpetually 80% done. The
other durable lesson: write the *deferred* list down (in SPEC as T.28d, in the
living doc as "deferred flavor") — an explicit gap is a plan; an implicit one is
drift that `/check` will later flag as a lie.

## Follow-ups

- **T.28d** — 6 Primordial @1 kits (dormant), 6 affinity @10 apex riders, Scaled
  @5 CC-immunity + @8 weather-as-buff, Spirit @8 echo-potency/pierce/haste,
  Primordial @3. Plus the deferred flavor (Beast ramp, Skyborn kite-reward,
  Tidekin ally-heal) if folded in.
- **T.25 sim re-baseline** — all rider magnitudes (lifesteal 0.12, splash 0.4,
  shields, empowered mults, echo cadence) are first-pass; sweep once T.28d lands.
- Trickster taunt-on-cast now exercises the T.28b taunt engine path in real play
  — watch it in the sim re-baseline.
