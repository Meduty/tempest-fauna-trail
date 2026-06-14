# 2026-06-14 — T.35 ability-scaling uniformity + dead-stat balance (#42), run as a parallel two-agent experiment

Resolves GitHub #42 (both findings). **T.35a** (`adf3e09`) — closed `Magnitude`
family + A2 orphan-stat-read guard (V.46), byte-identical refactor. **T.35b**
(`bd99983`) — durability/intent re-tune + per-role INT coeffs on dead-INT
carriers + axis↔scaling guard (V.47, B.20). Plus `0c81e8f` (handoff close) and
`4278e1a` (ARCHITECTURE drift sync, caught by a `/check --all` sweep). Notable
process-wise: T.35a and T.35b were built **concurrently by two agents in the same
working tree**, coordinated through a live handoff doc.

## What changed

1. **`ScalingTerm` → closed `Magnitude` family** (`registries.py`, T.35a/`adf3e09`).
   Four GAS-modeled kinds behind one Protocol (`eval(source,target,caller)` +
   `render_formula`/`render_inline`): `ScalingTerm` (linear), `PctResource`
   (%-of-max_hp, reads `.max_hp` directly), `MaxOfTerm` (`max(STR,INT)`),
   `SetByCaller` (runtime stacks). `Clause` gained `template`+`terms` (A1).
   `ability_text.render` became pure per-kind dispatch — the `ScalingTerm`-only
   branch deleted.
2. **A2 orphan-stat-read guard** (`test_ability_text.py::test_no_orphan_stat_reads`,
   V.46). AST-walks every handler; any `.stat()`/`.max_hp` read not backed by a
   `Magnitude` (or on `_PROSE_ALLOWLIST`) fails the build.
3. **Durability/intent re-tune** (`content.py`, T.35b/`bd99983`). `_DURABILITY`
   tanky STR/INT `0.55→0.42`; `_INTENT` damage `1.08→1.14` / utility `0.94→0.87`
   with defensive compensation. Proxy held at `1.075`/`0.947` (V.33 band).
4. **Per-role INT coeffs on 14 dead-INT carriers** (`abilities/champions.py`,
   `abilities/enemies.py`). 8 group-1 flat supports + 6 hybrid tanks; each authored
   as a `Magnitude` so the A2 guard covers it and the tooltip renders it.
5. **Axis↔scaling guard** (`test_content.py::TestAxisScalingAlignment`, V.47/B.20):
   an `int`/`hybrid` unit must read INT via a meta `Magnitude`.
6. **ARCHITECTURE sync** (`4278e1a`): §3.3 registries (TRAIT/ITEM populated, not
   empty) + Magnitude presentation layer; §5 traits/items planned→done.

## Why (the part SPEC compresses out)

**The issue framed Finding A as "B-tier scalers can't be `ScalingTerm`." That
framing was wrong, and chasing it would have produced the wrong design.** The real
defect wasn't that the math was special — it was that handlers did *free inline
arithmetic outside any introspectable object*. Both symptoms (empty `formula`,
prose that drifts from handler math) follow from that one root. The owner pushed
exactly here ("why can't ALL scalers be one class?"), which forced the right
question: not "one class" but **one closed polymorphic set**. Unreal's GAS had
already solved this exact problem — `EGameplayEffectMagnitudeCalculation` is a
tagged union of 4 magnitude kinds, not a single shape. Our Cat-0…Cat-5 audit
mapped 1:1 onto it. Borrowing the proven taxonomy beat inventing one.

**Finding B's diagnosis hinged on reading the *right* two numbers.** The owner
challenged my first stat comparison (Coral STR 92 vs Marten INT 127, "your gaps
seem much wider"). He was right — I'd compared *the same stat across mismatched
builds*; the honest metric is *each unit's own primary*. That correction exposed
the actual structural bug: `1.8 (str axis) × 0.55 (tanky) ≈ 0.99 ≈` a bruiser's
`1.0`, so a primary-stat tank kept near-carry primary scaling. The durability
penalty had never accounted for the axis bonus it was supposed to offset.

## Decisions

- **Kept the name `ScalingTerm`** for the linear kind rather than renaming to
  `LinearTerm` — 276 metas reference it; keeping it made the diff a pure *addition*
  of 3 siblings, minimizing byte-identical risk.
- **`PctResource` reads `.max_hp` directly, not via `.stat()`** — because
  `Piece.stat("max_hp")` is `0` in combat (it's a Piece attribute, not a
  `base_stats` key). A naïve `ScalingTerm("heal","max_hp*0.05")` would render a real
  number but heal 0 — the worst drift direction. This trap is why the family needed
  a distinct resource kind.
- **A2 guard is coarse + allowlist, not precise dataflow.** AST can't cheaply prove
  "this read is the predicate vs the outlet," so any uncovered read is either a
  `Magnitude` or an explicit allowlist line with a reason. A false positive costs
  one line; a false negative was the original bug. Bias toward loud.
- **Re-tune touched tanky + intent only; squishy left as a deferred lever.** Smaller
  blast radius; the squishy `1.25→1.35` offense buff stays available if a later sim
  pass wants it.
- **No sim sweep this pass (user's call).** Balance ships deterministic but
  sim-unvalidated; the win-rate refinement is an explicit follow-up.

## Process notes (AI collaboration)

- **Conflict — the handoff doc contradicted itself.** The shared a↔b coordination
  doc marked `content.py` as "🟢 FREE — start re-tune NOW" in its file table, but
  its own snapshot/baseline protocol said the re-tune must wait until T.35a commits
  (the re-tune moves every sim hash → corrupts A's byte-identical gate + text-only
  snapshot diff). As the lower-prio (B) worker I followed the **stricter** reading
  and held all writes, flagging the contradiction for A. A confirmed: baseline
  protocol wins. Lesson: "no edit-collision" ≠ "safe to write" — a file can be
  collision-free yet *baseline*-blocked because its effect pollutes a shared gate.
- **Agent error (mine, B) — over-counted the group-2 dependency.** I initially
  listed all 5 hybrid tanks as "A-rewritten, must re-read post-commit." A's reply
  corrected it: only `goldhide_rhino` + `iron_maiden` were restructured; the other
  three A never touched. Re-reading A's actual orphan-guard output beat trusting my
  plan's assumption.
- **Diagnosis error (mine) — wrong stat comparison.** See "Why" above: I compared
  STR-vs-STR across a str-assassin and a hybrid-tank, inflating the apparent gap.
  The owner's "that doesn't match inspect" caught it; the corrected metric (each
  unit's own primary) became the core of B.20.
- **Framing error in the source issue, caught at plan time** — "B-tier can't be a
  ScalingTerm" would have led to bolting prose-scraping onto the renderer
  (re-introducing the very drift V.38 prevents). Researching GAS first reframed it
  into the closed-family design.
- **Guardrails added:** V.46 (A2 orphan-stat-read — converts "silently omitted
  scaler" into a red test) and V.47 (axis↔scaling — converts "dead INT" into a red
  test). **V.47 immediately earned its keep:** it flagged 2 dead-INT units beyond
  the issue's hand-listed sample — `enemy_sergeant_at_arms` (genuinely dead, fixed)
  and `enemy_steam_engineer` (INT lives in a turret `SummonSpec`, not dead →
  allowlisted with reason). A hand-audit would have missed both.
- **Drift caught by `/check --all`:** ARCHITECTURE §3.3 still called TRAIT/ITEM
  registries "empty scaffolds" (they're 24/24 since T.28/T.29a) and §5 listed
  traits/items as "planned." Pre-existing, unrelated to T.35, fixed in `4278e1a`.
  Also found **SPEC V.2 overstates a `run_mods`/`RunModifiers` seam that doesn't
  exist in code** (T.31 unbuilt) — left for `/spec` to fix, not hand-edited
  (sole-mutator discipline). Interestingly ARCHITECTURE L82 describes the same seam
  *correctly* as "not yet in code" — so the two living docs disagreed, and the
  honest one was ARCHITECTURE.
- **Determinism verified independently.** A's byte-identical proof tool
  (`tools/_t35_digest.py`) was scratch and never committed, so I rebuilt an
  independent combat-digest over a fixed fight battery and confirmed the chain:
  pre-T.35 `dd54c9b…` == post-T.35a `dd54c9b…` (A byte-identical ✓) ≠ post-T.35b
  `677f774…` (B deterministic re-tune ✓). Gap: nothing in committed CI pins combat
  hashes — see Follow-ups.

### Prompting-strategy reflection

The high-leverage move this round was **"research the proven pattern before
designing."** Pulling the GAS magnitude taxonomy turned a vague "make it uniform"
into a concrete closed set with a 1:1 mapping to our audited residue — far better
than reasoning from first principles. Worth repeating: when a problem smells
solved-elsewhere (ability systems, ECS, effect stacks), fetch the reference impl
first.

The other lesson was about **parallel agents on a shared tree.** Two agents + a
markdown handoff doc *worked* — zero merge conflicts, both halves landed — but only
because the seam was real (A = representation/byte-identical, B = balance/re-baseline)
and the *baseline ownership* was made explicit. The near-miss was treating
"file ownership" as the coordination primitive when the actual shared resource was
the **test baseline** (snapshot + sim hashes), which no single file owns. Next time
I'd put the baseline/gate ownership at the *top* of the handoff doc, above the file
table — the file table is necessary but not sufficient. Also: the lower-prio agent
defaulting to the stricter interpretation of any ambiguity, and writing nothing to
the tree until the dependency committed, was the right risk posture and cost almost
nothing (all prep was off-tree in `/tmp`).

Lower-leverage: my first `AskUserQuestion` batches were too eager — the owner twice
chose "let me clarify first." The pattern that emerged: for genuine design forks,
*lead with the investigation and a recommendation*, ask only the residual decision.
The owner consistently wanted the reasoning surfaced, not a menu.

## Files

- `src/game/registries.py` — `Magnitude` Protocol + `ScalingTerm`/`PctResource`/
  `MaxOfTerm`/`SetByCaller`, `Clause.template`/`terms`, `SummonSpec` (T.35a, A).
- `src/game/ability_text.py` — per-kind render dispatch (T.35a, A).
- `src/game/abilities/{champions,enemies,bosses}.py` — Tier-B scalers → Magnitudes
  (T.35a, A); 14 dead-INT INT coeffs (T.35b, B).
- `src/game/content.py` — `_DURABILITY`/`_INTENT` re-tune (T.35b, B).
- `tests/game/test_ability_text.py` — A2 guard + snapshot (T.35a, A).
- `tests/game/test_content.py` — V.47 axis↔scaling guard (T.35b, B).
- `tests/game/ability_formulas.snapshot.json` — regenerated twice (A text-only, B re-tune).
- `ARCHITECTURE.md` — §3.3/§5 registry + presentation-layer sync (`4278e1a`).
- `docs/live/content/{abilities,rosters}.md` — Magnitude family / dead-stat notes.
- SPEC: §T T.35a/T.35b ✅; §V.46, §V.47; V.38/V.33 extended; §B.19, §B.20.

## Follow-ups

- **Commit a combat-determinism guard.** Nothing in CI pins combat output hashes;
  the snapshot only pins rendered tooltip text. A fixed-battery digest test would
  stop a future refactor silently moving combat. (Recommended to the user.)
- **SPEC V.2 drift** — the `run_mods`/`RunModifiers` clause describes unbuilt T.31
  code. Fix via `/spec` when T.31 lands (or annotate as forward-declared now).
- **Sim-validate the T.35b balance.** First-pass re-tune + INT coeffs shipped
  without a `tools/simulation/` win-rate sweep (user's choice); refine the numbers
  when a sweep runs.
- `docs/design/tasks/t29_item_engine_plan.md` shows uncommitted churn from another
  worker — not part of T.35; left untouched.
