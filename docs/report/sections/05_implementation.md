# How the Project Was Built

Tempest Fauna Trail is a FH Technikum Wien project — two students, eight weeks —
graded on UI, data loading, visualization, code structure, and documentation. What
follows is how it was actually built: the **spec-driven method** that governed
every change, and the **implementation arc** that method produced, from data models
to a playable run loop.

## Spec-Driven Development

The organizing idea is that a single **contract** — [SPEC.md](../../SPEC.md) —
drives the work, and every other document has a defined and different relationship
to the truth. Nothing lands without passing through the contract.

### The document layers and the LIVING vs FROZEN rule

The rule that prevents documentation drift is the distinction between **LIVING** and
**FROZEN** docs:

| Layer | Doc | Role | Currency |
|---|---|---|---|
| Contract | `SPEC.md` | the full contract (§G/§C/§I/§V/§T/§B/§D) | LIVING |
| Map | `ARCHITECTURE.md` | where things live and how they interact | LIVING |
| Reference | `docs/live/**` | how each subsystem works *now* | LIVING |
| Record | `docs/design/**` | how a task was *planned/built* | FROZEN |
| History | `docs/journal/**` | *why*, chronologically | FROZEN |

**LIVING** docs describe how things work *now* and **must match the code** — drift
is treated as a bug, the same as a failing test. **FROZEN** docs are point-in-time
records that are *never* retro-edited; a frozen task plan is read as a dated
snapshot, not current truth. The recurring, expensive failure the project kept
paying down was reading a frozen plan as if it were live — so the discipline is:
when a change lands, reconcile the matching LIVING doc in the same commit, and leave
the frozen plan alone.

### The skill chain

The workflow is mechanized as a chain of skills, each with a single, bounded job:

- **`/plan`** — writes a `docs/design/tasks/tN_*_plan.md` before any build; runs a
  required-reading pass and verifies every primitive against the code; ends in the
  exact spec deltas needed. Writes only the plan doc.
- **`/spec`** — the **sole mutator** of SPEC.md. New rows, invariants, bug
  backprop. Keeping one mutator preserves the numbering and encoding discipline.
- **`/build`** — plan-then-execute against a §T task; flips task status; auto-runs
  backprop on a test failure.
- **`/check`** — a read-only drift audit: every backticked code reference in the
  LIVING docs must resolve, every invariant must hold, content counts must match.
  It reports; it never edits.

The seams held in practice: each stage's output is the next stage's contract, so a
mistake gets caught at the cheapest layer. When a build *falsified* a plan's claim
(for instance, a change that was assumed byte-identical turned out to shift tick
timing), the correction was routed back through `/spec` rather than buried — the
build is allowed to falsify the plan, and the contract is corrected in the open.

### Invariants as executable guardrails

The `§V` invariants are the backbone. They are not aspirational prose — most are
**CI-guarded**, and each new one is typically born from a bug via *backprop* (the
"what invariant would have caught this?" reflex from the previous chapter). A
sampling of the load-bearing ones:

- **V.1** — `game/` has zero Flet imports (pure logic).
- **V.2** — `resolve_combat` is a pure function: identical inputs yield
  byte-identical output. No RNG, no clock, no globals.
- **V.14 / V.19** — the simulation layer imports only pure game logic; all
  procedural generation derives from `(run_seed, node_index, channel)`.
- **V.3 / V.4** — the API key is never logged; all HTTP runs on a worker thread.
- Content and balance guards (id resolution, axis↔scaling coverage, weather-metric
  NaN handling) that turn "silently wrong content" into red tests.

## The implementation arc

Development proceeded **engine-first, UI-last** — a direct consequence of the purity
invariants. Because `game/` is Flet-free and I/O-free, the entire game is testable
and simulatable without a UI or a network, so the whole engine, content, and balance
layers could be built and validated through the playtest CLI and the power
simulation long before any view existed. The tasks (`§T`) fall into a few waves:

### Foundation (the deterministic core)

`T.1` data models → `T.2` the two decoupled weather systems (Weather Favor +
Affinity Clash) → `T.3` the tick-based combat engine → `T.4` the 50-city / 6-stage
route → `T.5` the champion/enemy rosters → `T.6`/`T.7` the OpenWeather client, cache,
and 3-stream refresher → `T.18` the power/scaling formula. This wave established the
determinism doctrine that everything downstream relies on.

### Framework and tooling

`T.19` seed-deterministic encounter generation → `T.20` the ability / passive /
status framework (typed event bus, hooks, modifiers, registries) — the declarative
substrate all content plugs into → `T.21` challenge and 2-phase boss encounters with
map effects → `T.24` role-aware enemy formation → `T.26` unification of combat onto a
single tick loop (the old parallel engine was deleted). Alongside, `T.25` the power
simulation (matchup sweeps, win-rate/power metrics) and `T.27` the playtest CLI gave
the project its two ways to **drive the game headlessly** — the tools that made
engine-first development trustworthy.

### Content deepening and balance

The largest wave, and the one where the spec-driven method earned the most. Traits
were built in a deliberate split — `T.28a` (framework + declarative stat packs) →
`T.28b` (engine primitives) → `T.28c` (mechanic/apex riders via hook idioms) →
`T.28d` (hexproof correctness + fold-ins). Items followed the same shape:
`T.29-pre` reworked the combat **stat substrate** (weather-as-modifiers,
`attack_speed` to float), then `T.29a`–`T.29d` delivered the item engine, the full
catalog, the **mana primitive**, and multi-slot pieces. `T.30` implemented all 120
roster ability handlers plus 6 boss kits; `T.31` the augment system; `T.32` the
role/intent axis rework; `T.33a` the scaling classes and a fair total order
(`T.33b` the speed-axis diversity spread 3→7); `T.34a–c` the per-roster ability
metadata and `T.35a` the ability-description/tooltip layer (`T.35b` a dead-stat
balance pass); and `T.36a–c` the roster axis-distribution rebalance, closed with
power sweeps. Much of this wave's value was in **design conversation and balance
analysis** rather than code — for example, the INT-ability damage coefficient was
tuned empirically *and* cross-checked against a closed-form DPS-parity equilibrium
(≈ 3.7), so the balance pass ended with math and simulation agreeing, and produced a
reusable coefficient rule for future kits.

### The player-facing UI (built last, over the finished engine)

With a complete engine, the view layer was built last: `T.8` theme/components →
`T.9` menu → `T.10` run-start → `T.11` Trail view + Canvas route map → `T.12a–d` the
combat view (a forward replay stepper, animations, boss support, autoplay) →
`T.13` the Canvas run-summary chart → `T.14` save/load → `T.15a/b` the reward step
and full routing → `T.23a/b` the Prep view (economy, shop, board placement, item
equip) → `T.37a–c` the replay backend that combat playback rides on → `T.38`
node-type rewards and survivable "Hearts" → `T.39` persistent live node weather →
`T.40` the Prep UX overhaul → `T.41a/b` the description render layer → `T.42a/b`
the augment- and supply-node UIs plus the non-fight run-loop dispatch (and the
`viz/affinity_clash_heatmap` Canvas). With T.42 the menu→…→summary loop is complete
end to end. This wave depended on a hard constraint — the agent cannot see rendered output — which shaped
the collaboration lessons of the previous chapter (visual gating, self-screenshotting,
web-vs-desktop threading traps).

## Determinism as the spine

If one property holds the whole project together, it is **determinism**. Because
`resolve_combat` is pure and all generation is seeded, the same seed yields the same
route, squads, shop, economy, and byte-identical combat — which is exactly what makes
the simulation layer a trustworthy balance oracle and the combat replay possible
(state for a view is *recomputed* from the seed, not recorded). Every engine or
content change was argued for byte-identity or an explicit, sanctioned
**re-baseline**, and the distinction between "byte-identical" and "deterministic but
re-baselined" was tracked carefully in the spec. This is the invariant that lets a
two-person, eight-week, agent-built project stay coherent: the contract says what
must hold, the invariants make it checkable, and the seed makes it reproducible.
