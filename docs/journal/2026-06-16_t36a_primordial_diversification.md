# 2026-06-16 — T.36a: Primordial diversification (the 6 kings)

Re-axised and kit-rewrote the six T10 Primordial kings off uniform `hybrid/hybrid`
into six distinct apex archetypes, extended the V.47 axis↔scaling guard to close
B.24, and ran a three-pass `stat_edge` balance loop to land a runaway Borealis.
First build step of T.36 (the roster axis-distribution rebalance). Branch
`feature/t36a-primordials` off the plan branch.

## What changed

1. **5 king axis edits** (`content.py`) — Aurion stays `hybrid/hybrid`; Nerei
   `int/ability`; Borealis `hybrid/ability`; Umbra `str/auto`; Mournhollow
   `str/ability`; Aerion `hybrid/auto`. Resulting roles (pure `classify_role`):
   Aurion/Aerion spellblade, Nerei/Borealis/Mournhollow mage, Umbra marksman.
2. **6 king kit rewrites** (`abilities/champions.py`):
   - **Aurion** *Ascendance* — was a per-tick uncapped ramp; now cast-driven,
     +15 STR/+15 INT per cast, hard cap 8 stacks (kit conventions #6: bound the ramp).
   - **Nerei** *Grudge of the Flood* — replaced the empower-next-3-autos passive
     with a debuff marker: anyone who damages Nerei is branded (`nerei_grudge`,
     6s, +1, cap 5), and her damage vs a brand-bearer is amplified +6%/stack via
     `on_damage_pre`.
   - **Borealis** — Blizzard kept STR 0.96 + INT 2.28, added +15%-vs-frozen amp;
     **freeze cadence widened 6s→10s** (the balance fix, see below).
   - **Umbra** — stripped INT entirely: strike `STR·1.5` (was INT·2.38), clones
     fold the old 0.64·INT fraction into STR (0.32→0.64·STR, INT→0).
   - **Mournhollow** *Haunting Mist* — active `INT·3.42`→`80+STR·1.0` ×0.6 AoE +
     fear + new `grief` DoT (`STR·0.4`/1s tick, 4s, BURN convention).
   - **Aerion** — replaced the mana-gate passive + Board Storm nuke with
     *Overcharge* (every 3rd auto arcs `INT·1.4` to ≤2 nearest, deterministic) +
     *Skybreaker* (self +35% attack_speed for 4s, no nuke).
3. **2 new statuses** (`status.py`) — `grief` (potency-driven DoT, REFRESH, no
   gate) and `nerei_grudge` (STACK marker, no gate/DOT).
4. **V.47 guard B.24** (`tests/game/test_content.py`) — added `_meta_references_str`,
   a `test_hybrid_ability_units_reference_str` enforcing `hybrid`→STR via a
   Magnitude *unless* the piece has live autos (playstyle auto/hybrid), plus a
   dead-STR negative control. Fixed the stale `0.2·INT`→`0.25·INT` comment.
5. **3 blurb-vs-code drift fixes** — Aurion disarm 2s→4s, Borealis freeze 2s→4s,
   Nerei charged 3s→6s. The code always did 4s/6s; these were shipped tooltip bugs.
6. Regenerated `ability_formulas.snapshot.json`; verified `t32_role_matrix.txt`
   byte-identical (classify_role unchanged — Spellslinger lands in T.36b).

## Why (the part SPEC compresses out)

The kings were six identical `hybrid/hybrid` stat blocks with bespoke kits — no
archetypal identity. T.36a gives each a distinct axis fingerprint that the pure
`classify_role` reads into a real role, then rewrites the kit to fit that role
honestly (cast-Callings → ability, auto-Callings → auto).

The interesting part was **balance discovery**. The `stat_edge` sweep (tier-
controlled team sims) showed the *stat axes* land balanced (str/int/hybrid all
within ±0.01 wr_delta — the core D.25 "free-auto subsidy" concern is held), but
the per-king coeffs were spread: Borealis +0.151 (roster #1 overperformer),
Mournhollow +0.089, Nerei +0.074 over; Aurion −0.069, Aerion −0.057 under
(those two by design — I removed power, capping Aurion's ramp and swapping
Aerion's nuke for a steroid).

Borealis is the lesson. The first trim — reverting the INT bump 2.7→2.28, a ~12%
Blizzard cut — moved it only +0.151→+0.141. **The damage coefficient was never
the driver; the freeze was.** A 4s freeze every 6s is ~67% disable-uptime on a
target (`BLOCKS_ACTION` + `BLOCKS_MOVEMENT`) — it removes an enemy piece for most
of the fight, a tempo swing that dwarfs any damage number. Widening the cadence
6s→10s (uptime ~67%→~40%) dropped Borealis to +0.063 in one shot. CC tempo, not
DPS, was the budget. (Per the user's call, the milder ±0.07 king spread is left
for a later tuning pass — only the +0.15 outlier was unacceptable.)

## Decisions

- **Aerion's STR satisfaction is a guard *rule*, not an allowlist.** Aerion is
  `hybrid/auto`; the B.24 guard wants hybrid→both STR+INT via Magnitudes, but its
  STR comes through the universal auto (it's an auto-attacker). Rather than
  bolt a synthetic STR Magnitude onto the kit or one-off allowlist it, the guard
  treats live autos (playstyle auto/hybrid) as STR-satisfying — the same reason
  `str` units are auto-satisfied. So only `hybrid`+`ability` must reference STR by
  Magnitude. Verified all four pre-existing such pieces already do.
- **Umbra clones fold INT→STR** rather than just dropping INT — relocate the soul,
  don't nerf it (kit conventions #3); clone power stays ≈ constant.
- **`grief` lives only in Mournhollow's clause `terms`, not the meta `terms`** —
  listing it in both rendered the DoT line twice in the snapshot. The clause keeps
  it V.46-visible and fills `{grief}`.

## Process notes (AI collaboration)

- **Conflict — plan §10 vs reality.** The plan said "update `rosters.md` /
  `abilities.md` per substep," but those LIVING docs are deliberately *thin
  pointers* (counts + def→model build path + id-resolution). They don't enumerate
  per-piece axes, kits, or marginals — so nothing drifted and there was nothing to
  edit. The plan author (me, prior session) assumed those docs track distribution;
  they don't. **The target marginals/role-distro have no auditable living home** —
  recorded as a project memory; the T.36b distribution-guard test must become that
  home. `effects.md` (StatusGate table, event list) didn't drift either: grief and
  grudge are gateless, and `on_damage_pre`/`on_damage_taken` were already listed.
- **Agent error — I offered the wrong balance lever first.** For Borealis I
  presented "revert INT only" as a co-equal knob in the consult menu. The sweep
  proved it near-useless (−0.01). I had *diagnosed* the freeze self-combo in prose
  but mis-weighted the options — a plausible-but-weak knob shouldn't sit beside the
  dominant one. Cost a full 18-minute sweep to learn what the mechanic already
  said. Lesson: when consulting on a balance knob, lead with the mechanically
  dominant lever (here: CC uptime), and label weak knobs as weak.
- **Guardrail added — V.47 B.24.** The original guard checked INT only and never
  verified a `hybrid` piece reads STR. The extension (hybrid→both, with the
  live-auto exception) + a dead-STR negative control closes the gap that let a
  hybrid statline carry a dead STR half.
- **Drift caught — 3 shipped tooltip bugs** (Aurion/Borealis/Nerei durations);
  the user OK'd folding the fixes in since I was already in those kits.
- **Odd find — orphan T.29 doc WIP.** `git status` surfaced six `docs/live/` +
  `ARCHITECTURE.md` edits I never made (T.29a-d registry counts, items, Multicaster
  trait), carried in uncommitted from the branch point. Confirmed zero T.36 content
  and excluded them from this commit rather than sweep them in.

### Prompting-strategy reflection

The two standing instructions this session — "consult before changing a kit" and
"let me know if you find something odd, we'll discuss" — produced a much tighter
loop than a fire-and-forget "build T.36a" would have. They turned me into a
pause-at-the-seams collaborator: I stopped at the genuine forks (Aerion STR rule,
Umbra clones, every balance knob) and surfaced failures (the INT lever flopping,
the orphan docs, the plan-§10 mismatch) instead of pressing on or silently
papering over them. The high-leverage shape was *"verify the primitive, then bring
me the decision with a recommendation and the trade-off"* — it kept design
authority with the user while offloading the legwork.

The expensive part was the balance loop: three 18-minute `stat_edge` sweeps to
converge one champion. Two were avoidable — the freeze was diagnosable from the
mechanic (67% CC uptime) before spending a sweep on the INT knob. Next time:
reason the dominant lever out first, sweep once to confirm, rather than sweep to
discover. The other durable lesson is preferring a *principled rule* over a
special-case: "live autos satisfy STR" generalizes and self-documents, where an
Aerion allowlist would have been a landmine for the next auto-hybrid king.

## Files

- `src/game/content.py` — 5 king axis edits.
- `src/game/abilities/champions.py` — 6 king kit rewrites + 3 blurb fixes.
- `src/game/status.py` — `grief`, `nerei_grudge` StatusDefs.
- `tests/game/test_content.py` — V.47 B.24 guard (`_meta_references_str`,
  hybrid→STR test, dead-STR control), `0.2`→`0.25` comment.
- `tests/game/ability_formulas.snapshot.json` — regenerated.
- SPEC deltas (already applied in the prior planning session): §T.36a row, V.32
  (+spellslinger, T.36b), V.37 (kings un-pinned), V.47 (hybrid→both), B.24, V.52,
  D.25 consumed.

## Follow-ups

- **King spread tuning pass** (deferred by choice): Mournhollow +0.089 / Nerei
  +0.074 mildly over; Aurion −0.069 / Aerion −0.057 mildly under. None outliers.
- **T.36b** must create the distribution-guard test as the living home for the
  target marginals (no `docs/live/` doc tracks them).
- The six orphan T.29 `docs/live/`/`ARCHITECTURE.md` edits sitting uncommitted in
  the working tree need their own commit (not T.36a's).
- `stat_edge` STR-ability vs INT-ability gap +0.054 is small and Mournhollow-driven
  (n=3 cell); revisit when T.36b/c repopulate the str-ability cell.
