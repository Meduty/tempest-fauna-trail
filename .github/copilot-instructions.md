# Copilot Instructions — Tempest Fauna Trail

Flet (Python) roguelike auto-battler: animal champions travel real-world cities;
live OpenWeather data shapes tick-based, auto-resolved combat.

These instructions mirror [CLAUDE.md](../CLAUDE.md). When they disagree, **CLAUDE.md
and SPEC.md win** — keep this file aligned with them, don't fork the rules.

## Canonical documents (sources of truth)

**LIVING vs FROZEN** — LIVING docs (SPEC, ARCHITECTURE, `docs/live/`) describe how
things work **now** and must match code; drift is a bug, audited by `/check`.
FROZEN docs (`docs/design/`, `docs/journal/`) are dated records — never retro-edited
to match new code. Read a frozen task plan as a snapshot, not current truth.

| Doc | Role | Currency |
|---|---|---|
| [SPEC.md](../SPEC.md) | **The contract** — §G goal, §C context, §I interfaces, §V invariants, §T tasks, §B bugs, §D deferred. Wins on any conflict. Mutated **only** via the `/spec` workflow. | LIVING |
| [ARCHITECTURE.md](../ARCHITECTURE.md) | **The system map** — how every system works + interacts, and where each lives. Start here to navigate. | LIVING |
| [docs/live/](../docs/live/README.md) | **Per-system / per-content references** — "how this subsystem works now". The mid layer between ARCHITECTURE and code. Audited by `/check`. | LIVING |
| [CLAUDE.md](../CLAUDE.md) | Agent onboarding — structure, conventions, workflow. | LIVING |
| [docs/design/](../docs/design/), [docs/journal/](../docs/journal/) | Per-task plans, design proposals, rosters (as-designed), dev journal. | FROZEN |

## Required reading before any task work (MANDATORY)

Before writing or editing **any** code for a task, read, in order:

1. **SPEC.md** — the relevant §T row(s), every applicable §V invariant, nearby §B history.
2. **ARCHITECTURE.md** — the system you're touching, how it interacts, where it lives.
3. **The LIVING doc for the area** — `docs/live/systems/<sys>.md` or
   `docs/live/content/<x>.md`. This is current truth; trust it over the frozen plan.
   (If it's a 🔶 stub, fall through to the design doc + code.)
4. **The task plan doc** — `docs/design/tasks/tN_*_plan.md` (write one first if absent).
   **FROZEN** — a snapshot, not current truth.
5. **Every design doc the task touches** — `docs/design/{systems,content}/*.md` in scope.
   **FROZEN** — verify against code.
6. **Every piece of code the change touches** — read the modules + integration touch
   points, don't trust their names. Cite touch points as `file.py:line`.

Design-doc examples are illustrative and **sometimes cite stats/primitives that don't
exist** — verify every primitive/stat/function against the code before relying on it.

## Non-negotiable invariants (see SPEC §V for the full list)

- `src/game/` is **pure** — zero Flet imports, zero I/O (V.1). `tools/simulation/`
  imports only `src/game/` (V.14).
- Combat is a **pure, deterministic** function: `resolve_combat(team, enemies, weather)
  -> BattleResult`, byte-identical for identical inputs (V.2). Single entry point.
- **Determinism is mandatory.** Any "chance"/"every few" mechanic uses a deterministic
  cadence counter, never RNG. All procedural generation derives from
  `(run_seed, node_index, channel)`.
- All HTTP runs on a worker `threading.Thread`; API failure never crashes (V.3, V.4).
- Never log the OpenWeather API key.
- Every content id (ability/passive/trait/augment) must resolve in its registry —
  CI-guarded (V.15, V.17, V.22).

## Conventions

- Python ≥ 3.10. Dataclasses with type hints; weather effects are dict lookups, not
  class hierarchies. Match existing module conventions and import boundaries.
- Tests alongside code (`tests/` mirrors `src/`); mock the API with `unittest.mock`;
  live API tests marked `@pytest.mark.integration`. Run `uv run pytest`.
- Path-scoped rules live in [.claude/rules/](../.claude/rules/) (`api.md`,
  `game-logic.md`, `flet-ui.md`).

## After a non-trivial change

- Update SPEC.md via `/spec` (§T status, new §V, §B for bugs caught).
- **Update the matching `docs/live/` doc in the same change** (it's LIVING — a stale
  one is a bug), using the code's own taxonomy (real file/symbol names, not generic
  prose). Then run **`/check`** to confirm no LIVING-doc drift (every cited path/symbol
  resolves; §V invariants + content counts hold). `/check` writes nothing.
- Leave `docs/design/` FROZEN — don't retro-edit it; distil durable "how it works" into
  the living doc instead.
- Append a journal entry from [docs/templates/journal_entry.md](../docs/templates/journal_entry.md),
  including its **mandatory "Process notes (AI collaboration)" + prompting-strategy
  reflection** sections — this repo is a vibe-coding case study; record where agent,
  spec, docs, and code disagreed, not just the code's "why".
