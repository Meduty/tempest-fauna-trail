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

| Path | Purpose |
|---|---|
| [SPEC.md](SPEC.md) | Canonical spec — §G goal, §C context, §I interfaces, §V invariants, §T tasks, §B bugs, §D deferred. All design decisions land here. |
| [docs/proposal.md](docs/proposal.md) | Pitch / problem framing / target users. |
| [docs/design/tasks/](docs/design/tasks/) | Per-task plan docs (`tN_*_plan.md`). Detailed designs for §T rows. |
| [docs/design/content/](docs/design/content/) | Champion / enemy / boss / augment / item / trait rosters. |
| [docs/design/systems/](docs/design/systems/) | Combat, passive, effect, view system designs. |
| [docs/design/playtesting/](docs/design/playtesting/) | Dev playtest CLI design (T.27) + historical engine-split note. |
| [docs/journal/](docs/journal/) | Chronological dev log — context, decisions, "why". Append after milestones. |
| [.claude/rules/](.claude/rules/) | Path-scoped guardrails for AI edits (`api.md`, `game-logic.md`, `flet-ui.md`). |

## AI Workflow

- **Spec changes**: invoke `/spec` (sole mutator of SPEC.md). Bug report → `/spec bug: <desc>` triggers §B backprop with optional new §V invariant.
- **Implementation**: invoke `/build` for plan-then-execute against §T tasks. Auto-runs `/backprop` on test failure.
- **Drift audit**: invoke `/check` for read-only SPEC-vs-code report.
- **Journal**: append `docs/journal/<date>_<topic>.md` after non-trivial milestones — captures the "why" that SPEC.md compresses out.

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
│   │   ├── legacy.py       #   resolve_combat shim → loop_new + recorder
│   │   ├── loop_new.py     #   unified tick loop (meters, pathing, casts)
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
└── playtest/               # Dev CLI: sim_fight, sim_node, sim_run, inspect, inspect_node (T.27)
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
| `tools/simulation/` | T.25 | Matchup sweeps + Bradley-Terry power ratings |

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
- Combat is pure function: `resolve_combat(team, enemies, weather) -> BattleResult` (V.2). Single entry point — internally delegates to `compile_loadout → CombatContext → combat/loop_new.run → BattleResultRecorder.build_result` (T.26). Boss fights add `attach_map_effect` before the loop runs; see [tools/playtest/_common.py](tools/playtest/_common.py) `resolve_boss_combat` for the canonical wiring.
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
