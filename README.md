# Tempest Fauna Trail

Weather-driven roguelike where animal champions battle across real-world cities. Live OpenWeather data shapes every fight — a Snow-affinity team dominates in snowy Tokyo but folds when the city turns Thunder.

Built with [Flet](https://flet.dev) (Python), cross-platform desktop + web. Designed to be developed collaboratively with AI coding agents — see [CLAUDE.md](CLAUDE.md) and [SPEC.md](SPEC.md).

## Status

Early development. Engine + content layers (data models, combat, weather effects, route, content roster, scaling, OpenWeather client) are landing first. UI / cache-refresher / encounter generator are planned per [SPEC.md §T](SPEC.md).

## Quickstart

### Requirements

- Python ≥ 3.10
- OpenWeather API key (free tier — [openweathermap.org/api](https://openweathermap.org/api))

### Setup

```bash
git clone <repo>
cd tempest-fauna-trail
uv sync                       # or: pip install -e . && pip install -r requirements.txt
cp .env.example .env
# edit .env, set OPENWEATHER_API_KEY=<your-key>
```

### Run

```bash
uv run flet run               # desktop
uv run flet run --web         # browser
```

### Tests

```bash
pytest tests/                          # all tests
pytest tests/ -m "not integration"     # unit only (no network)
pytest tests/ -m integration           # live API tests (needs OPENWEATHER_API_KEY)
```

## Project Map

| Path | Purpose |
|---|---|
| [SPEC.md](SPEC.md) | Canonical spec — goals, invariants, tasks, bugs. **Source of truth.** |
| [CLAUDE.md](CLAUDE.md) | AI agent onboarding — project structure, conventions, workflow |
| [docs/proposal.md](docs/proposal.md) | Pitch + design framing |
| [docs/design/tasks/](docs/design/tasks/) | Per-task plan docs (`tN_*_plan.md`) |
| [docs/design/content/](docs/design/content/) | Champion / enemy / boss / augment / item / trait rosters |
| [docs/design/systems/](docs/design/systems/) | Combat, passive, effect, view system designs |
| [docs/journal/](docs/journal/) | Chronological dev log |
| [src/](src/) | Implementation |
| [tests/](tests/) | Unit + integration tests |

## AI-Driven Development

This repo is set up for collaboration with AI coding agents (Claude Code etc.):

- **Source of truth** lives in [SPEC.md](SPEC.md) — caveman-encoded sections §G/§C/§I/§V (invariants), §T (tasks), §B (bugs), §D (deferred).
- **Skills** wrap key workflows:
  - `/spec` — sole mutator of SPEC.md (new spec, amend, distill from code, bug backprop)
  - `/build` — plan-then-execute against §T tasks; auto-runs backprop on test failure
  - `/check` — read-only drift audit, SPEC vs code
- **Per-path guardrails** in [.claude/rules/](.claude/rules/) bound AI edits by scope (`api.md`, `game-logic.md`, `flet-ui.md`).
- **Journal** in [docs/journal/](docs/journal/) captures the "why" that SPEC compresses out — append after non-trivial milestones.

## Build (Flet packaging)

```bash
flet build apk -v             # Android
flet build ipa -v             # iOS
flet build macos -v
flet build linux -v
flet build windows -v
flet build web -v
```

See [Flet build docs](https://flet.dev/docs/publish/) for signing + distribution details.

## License

TBD.
