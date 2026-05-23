# Tempest Fauna Trail

Flet (Python) roguelike — animal champions travel real-world cities, live OpenWeather data shapes combat.

> **Source of truth**: [SPEC.md](SPEC.md). This file is the AI-agent collaboration shortcut — quick orientation + conventions. When CLAUDE.md and SPEC.md disagree, SPEC.md wins.

## Quick Reference

- **Run**: `uv run flet run` (desktop) or `uv run flet run --web`
- **Tests**: `pytest tests/` (add `-m integration` for live API)
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
│   └── weather.py          # OpenWeather client (T.6)
├── game/
│   ├── models.py           # Champion, Enemy, Node, Run dataclasses (T.1)
│   ├── combat.py           # Tick-based auto-resolve combat (T.3)
│   ├── combat_log.py       # Structured combat event log
│   ├── content.py          # Champion / enemy rosters (T.5)
│   ├── scaling.py          # Power scaling P = 1.5^((T-1)/2 + (L-1)) (T.18)
│   ├── route.py            # 50-city route, 6 stages (T.4)
│   └── weather_effects.py  # Stat packs + affinity damage triangle (T.2)
├── ui/                     # Stub (__init__.py only)
└── viz/                    # Stub (__init__.py only)
tests/                      # Mirrors src/ structure
docs/                       # Design + journal (see Documentation Map)
```

### Planned per SPEC §T (not yet built)

| Module | Task | Description |
|---|---|---|
| `api/cache.py`, `api/refresher.py` | T.7 | Stateless per-city cache + 3-stream tick refresher |
| `game/encounter.py` | T.19, T.21 | Seed-deterministic encounter gen, bosses, challenges |
| `game/abilities.py` | T.20 | Ability / passive / status framework |
| `game/augments.py`, `game/economy.py` | T.22 | Augments, Amber economy, Tempest team-size cap |
| `game/formation.py` | T.24 | Enemy formation policy |
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
- Combat is pure function: `resolve_combat(team, enemies, weather) -> BattleResult` (V.2)
- Weather effects = lookup dicts, no class hierarchies (V.5: 6 states; V.6: single `affinity` field per piece)
- No I/O in game logic — API/file access stays in `api/` layer

## API Integration (T.6 + T.7)

- OpenWeather free tier, fetched by lat/lon (T.6, [src/api/weather.py](src/api/weather.py))
- API key via env var `OPENWEATHER_API_KEY` — never log (V.3)
- **Cache + refresher (T.7, planned)**: stateless per-city cache with 3 states (`unknown`/`live`+`fetched_at`/`substitute`). Refresher ticks 1/min, fires 3 deduped streams (A=full RR 50, B=window `[current+1..+6]`, C=uniform random) → ≤3 API calls/min. On fetch fail: city-default weather flagged `substitute`. Sync fetch on advance-to-`unknown`. See SPEC §V.9-V.13.
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
