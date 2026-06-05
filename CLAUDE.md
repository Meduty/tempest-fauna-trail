# Tempest Fauna Trail

Flet (Python) roguelike — animal champions travel real-world cities, live OpenWeather data shapes combat.

> **Source of truth**: [SPEC.md](SPEC.md). This file is the AI-agent collaboration shortcut — quick orientation + conventions. When CLAUDE.md and SPEC.md disagree, SPEC.md wins.

## Quick Reference

- **Run**: `uv run flet run` (desktop) or `uv run flet run --web`
- **Tests**: `uv run pytest` (add `-m integration` for live API)
- **Playtest CLI** (no UI required): `uv run python -m tools.playtest.sim_fight --help` — see [docs/design/playtesting/plan.md](docs/design/playtesting/plan.md). Scripts: `sim_fight`, `sim_node`, `sim_run`, `inspect`, `inspect_node`.
- **Python**: 3.10+
- **Deps**: see [pyproject.toml](pyproject.toml) (canonical) — runtime: `flet`, `requests`; dev: `python-dotenv`, flet CLI/desktop/web
- **API key**: `cp .env.example .env`, set `OPENWEATHER_API_KEY`

## Documentation Map

**LIVING vs FROZEN** — the rule that prevents doc drift. **LIVING** docs (SPEC,
ARCHITECTURE, `docs/live/`) describe how things work *now* and **must match
code** — audited by `/check`. **FROZEN** docs (`docs/design/`, `docs/journal/`)
are point-in-time records; they are *never* retro-edited to match new code. Read
a frozen task plan as a dated snapshot, not current truth — verify against code.
See [docs/live/README.md](docs/live/README.md).

| Path | Purpose | Currency |
|---|---|---|
| [SPEC.md](SPEC.md) | Canonical spec — §G goal, §C context, §I interfaces, §V invariants, §T tasks, §B bugs, §D deferred. All design decisions land here. | LIVING (`/spec`) |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System map — how all systems work + interact, and where each lives. The "find your way around" guide. | LIVING |
| [docs/live/](docs/live/README.md) | Per-system / per-content references — "how this subsystem works now". The mid-level layer between ARCHITECTURE and code. | LIVING (`/check`) |
| [docs/proposal.md](docs/proposal.md) | Pitch / problem framing / target users. | FROZEN |
| [docs/design/tasks/](docs/design/tasks/) | Per-task plan docs (`tN_*_plan.md`). How we *planned/built* a §T row. | FROZEN |
| [docs/design/content/](docs/design/content/) | Champion / enemy / boss / augment / item / trait rosters (as-designed lore + intent). | FROZEN |
| [docs/design/systems/](docs/design/systems/) | Combat, passive, effect, view system *proposals* (original design rationale). | FROZEN |
| [docs/design/playtesting/](docs/design/playtesting/) | Dev playtest CLI design (T.27) + historical engine-split note. | FROZEN |
| [docs/journal/](docs/journal/) | Chronological dev log — context, decisions, "why". Append after milestones. | FROZEN |
| [.claude/rules/](.claude/rules/) | Path-scoped guardrails for AI edits (`api.md`, `game-logic.md`, `flet-ui.md`). | LIVING |

## AI Workflow

### Required reading before any task work (MANDATORY)

Before writing or editing **any** code for a task, an agent **must** read, in order:

1. **[SPEC.md](SPEC.md)** — the relevant §T row(s), every §V invariant that could apply, and any §B bug history near the area. SPEC is the contract; it wins on conflict.
2. **[ARCHITECTURE.md](ARCHITECTURE.md)** — the system map: how the touched system works, how it interacts with others, and where it lives. Start here to find your way around.
3. **The LIVING system/content doc** — `docs/live/systems/<sys>.md` or `docs/live/content/<x>.md` for the touched area. This is the current truth; trust it over the frozen plan. (If it's a 🔶 stub, fall through to the design doc + code.)
4. **The task plan doc** — `docs/design/tasks/tN_*_plan.md` for the task (write one first if absent — see "Planning a §T task" below). **FROZEN** — a dated snapshot, not current truth.
5. **Every design doc the task touches** — the `docs/design/{systems,content}/*.md` files for the systems/rosters in scope (the plan doc lists them). **FROZEN** — verify against code.
6. **Every piece of code the change touches** — read the actual modules and their integration touch points before editing, not just their names. Cite touch points as `file.py:line`.

**When a change lands, update the matching `docs/live/` doc in the same commit** (like the mandatory journal entry) and run `/check` — a stale living doc is a bug.

This is not optional context — it is the groundwork. Design docs contain illustrative-but-wrong examples (see the planning rules), so **verify every primitive/stat/function against the code** before relying on it. The same checklist is enforced in [docs/templates/task_implementation_prompt.md](docs/templates/task_implementation_prompt.md), [docs/templates/task_plan.md](docs/templates/task_plan.md), the `.claude/rules/*` path guardrails, and [.github/copilot-instructions.md](.github/copilot-instructions.md).

- **Spec changes**: invoke `/spec` (sole mutator of SPEC.md). Bug report → `/spec bug: <desc>` triggers §B backprop with optional new §V invariant.
- **Implementation**: invoke `/build` for plan-then-execute against §T tasks. Auto-runs `/backprop` on test failure.
- **Drift audit**: invoke `/check` (repo skill, [.claude/skills/check](.claude/skills/check/SKILL.md)) for a read-only report of LIVING docs (SPEC, ARCHITECTURE, `docs/live/`) vs code — every cited path/symbol must resolve; §V invariants and content counts must hold. Writes nothing.
- **Journal**: append `docs/journal/<date>_<topic>.md` after non-trivial milestones — captures the "why" that SPEC.md compresses out. Use [docs/templates/journal_entry.md](docs/templates/journal_entry.md). **Every entry MUST carry a "Process notes (AI collaboration)" section** documenting conflicts/misalignments (CLAUDE.md vs SPEC vs design-docs vs code), agent errors and wrong turns, guardrails added, and drift caught — plus a **prompting-strategy reflection** on what prompt shapes worked and how your approach to driving the agent is evolving across the project. This repo is a vibe-coding case study; that signal is invisible in the diff and must be written down, not just the code's "why".

### Planning a §T task (before any `/build`)

Write `docs/design/tasks/tN_*_plan.md` from [docs/templates/task_plan.md](docs/templates/task_plan.md). Prompts for an *approved* plan use [docs/templates/task_implementation_prompt.md](docs/templates/task_implementation_prompt.md). Hard-won rules (a planning miss here costs a whole build):

- **Verify, don't trust the design docs.** `effect_systems_design.md` examples use **illustrative stat keys that don't exist** (`ability_power`→`intelligence`, `attack_damage`, `mana_max`; mana is per-`ActiveSlot`, not a `Piece` stat). Before citing a primitive/stat/function, grep it — confirm it exists and the real key/signature. Cite touch points as `file.py:line`.
- **Run a content↔design drift check.** Code rosters drift from `*_catalog.md` / `*_roster.md` (e.g. `CALLING_TAGS` carried 4 dead T.5 tags + omitted `Packmate`). Diff the code's vocabulary against the design docs; reconcile in the task; add a V-guard so it can't recur.
- **Determinism is non-negotiable (V.2/V.14).** Any "chance"/"every few" mechanic uses a deterministic cadence counter (like `crit_counter`), never RNG — sims must stay byte-identical.
- **Ask open questions *before* writing the plan, not after.** Use `AskUserQuestion` for genuine design forks (scope, vocab reconciliation, mechanic fidelity). Investigate origins (git history) before asking the user to decide.
- **Split large tasks** into `Tn_a`/`Tn_b` along a real seam (e.g. declarative-content vs engine-primitives) so each substep ships and tests independently.
- Plan ends with a **"SPEC changes needed"** section enumerating the `/spec` deltas (rows, invariants, §B, §D, order) — applied only on user OK.

## Project Structure

### Implemented

```
src/
├── main.py                 # Flet entry point (placeholder shell)
├── api/
│   ├── weather.py          # OpenWeather client (T.6)
│   ├── cache.py            # Stateless per-city cache (T.7)
│   └── refresher.py        # 3-stream tick refresher (T.7)
├── game/
│   ├── models.py           # Champion, Enemy, Node, Run, BattleResult (T.1)
│   ├── combat/             # Unified tick-based engine (T.3 + T.20 + T.26)
│   │   ├── __init__.py     #   re-exports resolve_combat, CombatContext, run
│   │   ├── resolve.py      #   resolve_combat public entry → engine + recorder
│   │   ├── engine.py       #   unified tick loop (meters, pathing, casts)
│   │   ├── context.py      #   CombatContext mutator API (T.20)
│   │   └── recorder.py     #   BattleResultRecorder (T.26)
│   ├── combat_log.py       # Render BattleResult → text lines
│   ├── content.py          # Champion / enemy rosters (T.5)
│   ├── scaling.py          # Power scaling P = 1.5^((T-1)/2 + (L-1)) (T.18)
│   ├── route.py            # 50-city route, 6 stages (T.4)
│   ├── weather_effects.py  # Stat packs + affinity damage triangle (T.2)
│   ├── encounter.py        # Seed-deterministic encounter gen (T.19, T.21)
│   ├── abilities/          # Ability + passive content (T.20, T.21)
│   ├── bosses/             # Authored boss kits (T.21)
│   ├── effects.py          # EventBus, EffectBundle, Modifier (T.20)
│   ├── events.py           # Typed combat event payloads (T.20)
│   ├── status.py           # Status defs + gates (T.20)
│   ├── registries.py       # ABILITY_REGISTRY + PASSIVE_REGISTRY (T.20)
│   ├── piece.py            # Piece runtime state (T.20)
│   ├── board.py            # Board cell modifier state (T.21)
│   ├── map_effects.py      # Boss map effects (T.21)
│   ├── targeting.py        # Targeting helpers (T.20)
│   ├── formation.py        # Role-aware enemy formation (T.24)
│   ├── loadout.py          # compile_loadout (content ↔ combat boundary)
│   └── rng.py              # Seeded RNG helper
├── ui/                     # Theme tokens + reusable Flet components (T.8)
│   ├── theme.py            # Design tokens (colors, typography, spacing, animation)
│   ├── components/         # Shared components (champion_card, weather_badge, meter_bar, chips)
│   └── views/
└── viz/                    # Stub (__init__.py only)
tools/
├── playtest/               # Dev CLI: sim_fight, sim_node, sim_run, inspect, inspect_node (T.27)
└── simulation/             # Power sim — matchup sweeps + deterministic win-rate analysis (T.25)
tests/                      # Mirrors src/ + tools/ structure
docs/                       # Design + journal (see Documentation Map)
```

### Planned per SPEC §T (not yet built)

| Module | Task | Description |
|---|---|---|
| `game/augments.py`, `game/economy.py` | T.22 | Augments, Amber economy, Tempest team-size cap |
| `game/save.py` | T.14 | JSON save/load of `Run` |
| `ui/theme.py`, `ui/components/`, `ui/views/` | T.8-T.13, T.15, T.23 | Flet views + shared components |
| `viz/route_map.py`, `viz/run_summary.py` | T.11, T.13 | Canvas route map, BarChart summary |

## Flet Conventions

- **Routing**: `page.views` stack model. Exact route names open — see SPEC §D.16 for stale-vs-`views_spec.md` mismatch.
- Each route handler clears `page.views`, rebuilds stack, calls `page.update()`. `page.on_view_pop` for back nav.
- Style constants in `ui/theme.py` — no hardcoded colors/fonts in views
- All API/HTTP on `threading.Thread` — never block main thread (V.4)
- `page.update()` once after batch control mutations — not per-control
- Avoid `page.clean()` — replace `page.views` list instead
- **Charts**: `ft.BarChart`, `ft.LineChart`, `ft.PieChart` native
- **Canvas**: `flet.canvas` for route map — `cv.Circle`, `cv.Line`, `cv.Text`. Draw connections behind, nodes on top. Manual hit-testing.
- **Animations**: `animate_opacity`, `animate_offset` on controls; `ft.AnimatedSwitcher` for combat log
- **Images**: OpenWeather icons via `ft.Image(src="https://openweathermap.org/img/wn/{icon}@2x.png")`

## Game State (per §V)

- Single `Run` holds all game state (current node, roster, battle log)
- `game/` has zero Flet imports — pure logic (V.1)
- Combat is pure function: `resolve_combat(team, enemies, weather) -> BattleResult` (V.2). Single entry point — internally delegates to `compile_loadout → CombatContext → combat/engine.run → BattleResultRecorder.build_result` (T.26). Boss fights add `attach_map_effect` before the loop runs; see [tools/playtest/_common.py](tools/playtest/_common.py) `resolve_boss_combat` for the canonical wiring.
- Weather effects = lookup dicts, no class hierarchies (V.5: 6 states; V.6: single `affinity` field per piece)
- No I/O in game logic — API/file access stays in `api/` layer

## API Integration (T.6 + T.7)

- OpenWeather free tier, fetched by lat/lon (T.6, [src/api/weather.py](src/api/weather.py))
- API key via env var `OPENWEATHER_API_KEY` — never log (V.3)
- **Cache + refresher (T.7)**: stateless per-city cache with 3 states (`unknown`/`live`+`fetched_at`/`substitute`). Refresher ticks 1/min, fires 3 deduped streams (A=full RR 50, B=window `[current+1..+6]`, C=uniform random) → ≤3 API calls/min. On fetch fail: city-default weather flagged `substitute`. Sync fetch on advance-to-`unknown`. See SPEC §V.9-V.13.
- All HTTP on worker thread (V.4)

## Testing

- Unit tests for game logic (combat, weather effects, scaling, content, route, models)
- Mock API responses with `unittest.mock.patch`
- Live API tests marked `@pytest.mark.integration` — auto-skipped when `OPENWEATHER_API_KEY` absent
- No UI tests — test logic only

## Content Budget (per §T / §D)

- ~50 cities, one per node, 6 continent stages (T.4)
- ~60 champions = 1 per affinity × 10 tiers (MVP cut OK) (T.5)
- ~60 enemies (T.5)
- 6 weather states: Clear, Cloudy, Mist, Rain, Snow, Thunder (V.5)
