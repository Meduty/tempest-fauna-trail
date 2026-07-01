# Tempest Fauna Trail

Weather-driven roguelike where animal champions battle across real-world cities. Live OpenWeather data shapes every fight — a Snow-affinity team dominates in snowy Tokyo but folds when the city turns Thunder.

Built with [Flet](https://flet.dev) (Python), cross-platform desktop + web. Designed to be developed collaboratively with AI coding agents — see [CLAUDE.md](CLAUDE.md) and [SPEC.md](SPEC.md).

## Status

**Playable end to end — the full menu → trail → prep → combat → reward → summary loop runs over the finished engine. Every functional task in [SPEC.md §T](SPEC.md) is complete; the only open row is T.17 (this documentation) plus ongoing polish.**

- ✅ **Done** — data models, tick combat engine (ability/passive/status framework, bosses, map effects), weather effects, 50-city route, champion/enemy/boss rosters + ability catalog, power scaling, encounter generation, economy & shop, item/augment/trait systems, Prep equip seam, OpenWeather client + cache + 3-stream refresher, theme/components, Flet views (menu, run-start, trail, prep, combat, augment, supply, reward, summary, settings), route-map + run-summary + affinity-clash Canvas visualizations, save/load, playtest CLI, power-simulation tooling.
- 📋 **Open** — T.17 documentation (partial) + ongoing polish. See [SPEC.md §T](SPEC.md) for per-task status.

For how the systems fit together and where to find them, read **[ARCHITECTURE.md](ARCHITECTURE.md)**.

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

### Weather API key (optional, but recommended)

The Trail shows live weather per city — and that live weather **shapes combat**: each
node's weather is frozen when you enter Prep, then drives Weather Favor for the whole
fight (V.73). Without a key the game still plays on each city's deterministic default
weather, so runs stay reproducible either way — weather is locked *before* the fight
resolves, so live-feed timing never breaks determinism (V.2). Configure the key
**either** way:

1. **`.env` file** (preferred for local dev) — `cp .env.example .env`, then edit the
   one line:

   ```env
   OPENWEATHER_API_KEY=your_actual_key_here
   ```

   No quotes, no spaces around `=`. `.env` is git-ignored; the app/tests load it via
   `python-dotenv`.

2. **Environment variable** (CI / shells / one-off):

   ```bash
   export OPENWEATHER_API_KEY=your_actual_key_here
   uv run flet run
   ```

3. **In-app Settings menu** (no terminal needed) — launch the app, open
   **Settings** from the main menu, paste your key, **Save**. It persists to a local
   config file (`~/<user-data>/tempest-fauna-trail/config.json`) and the Trail picks
   it up next time you open it. An `OPENWEATHER_API_KEY` env var, if set, overrides it.

**Without a key the game still runs** — the weather refresher simply never starts, so
every Trail node shows a `?` **"weather pending"** marker (the app **never** invents
fake weather it hasn't fetched). Add a key to see live weather and the affinity
favor/clash it drives. The key is read from the environment and **never logged** (V.3).

### Run

```bash
uv run flet run               # desktop
uv run flet run --web         # browser
```

> **Note:** `uv run flet run` launches the real game (menu → trail → … → summary).
> For headless engine work — no UI — the **playtest CLI** drives the full engine
> straight from the terminal:
>
> ```bash
> uv run python -m tools.playtest.sim_fight --help     # resolve one fight
> uv run python -m tools.playtest.sim_run --help        # simulate a full run
> ```

### Tests

```bash
uv run pytest                            # all tests
uv run pytest -m "not integration"       # unit only (no network)
uv run pytest -m integration             # live API tests (needs OPENWEATHER_API_KEY)
```

## Project Map

| Path | Purpose |
|---|---|
| [SPEC.md](SPEC.md) | Canonical spec — goals, invariants, tasks, bugs. **Source of truth.** |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System map — how the engine/content/weather/economy systems work and where each lives in the code |
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

Source-available under the **PolyForm Noncommercial License 1.0.0** — free to
use, modify, and share for any **noncommercial** purpose. **Commercial use
requires a separate license** from the authors. See [LICENSE](LICENSE) and
[COMMERCIAL.md](COMMERCIAL.md).
