# Tempest Fauna Trail

Flet (Python) roguelike — animal champions travel real-world cities, live OpenWeather data shapes combat.

## Quick Reference

- **Run**: `flet run src/main.py` or `python -m src.main`
- **Tests**: `pytest tests/`
- **Python**: 3.10+
- **Dependencies**: `flet>=0.84.0`, `requests>=2.31.0`

## Project Structure

```
src/
├── main.py                 # Entry point, Flet app setup, routing
├── api/
│   ├── weather.py          # OpenWeather API client
│   └── cache.py            # Local JSON cache (1h TTL)
├── game/
│   ├── models.py           # Champion, Enemy, Node, Run dataclasses
│   ├── combat.py           # Auto-resolved turn-by-turn combat
│   ├── weather_effects.py  # Weather state → combat modifier mapping
│   └── route.py            # Fixed city route definition
├── ui/
│   ├── views/              # One view per screen (menu, map, combat, summary)
│   ├── components/         # Reusable widgets (champion card, weather badge)
│   └── theme.py            # Colors, fonts, spacing constants
├── viz/
│   ├── route_map.py        # City route with weather icons (Canvas)
│   └── run_summary.py      # Damage chart per battle (BarChart)
assets/                     # Icons, images
docs/                       # Flow charts, documentation PDFs
tests/                      # pytest, mirrors src/ structure
```

## Flet Conventions

- **Routing**: `page.views` stack model. `page.go("/route")` triggers `page.on_route_change`.
  Each route handler clears `page.views`, rebuilds stack, calls `page.update()`.
  `page.on_view_pop` handles back navigation.
- Route format: `/`, `/map`, `/combat`, `/summary`
- Style constants in `ui/theme.py` — no hardcoded colors/fonts in views
- All API calls on `threading.Thread` — never block main thread
- Call `page.update()` once after batch control mutations — not per-control
- Avoid `page.clean()` — replace `page.views` list instead
- **Charts**: `ft.BarChart` (damage per battle), `ft.LineChart`, `ft.PieChart` available natively
- **Canvas**: `flet.canvas` for route map — `cv.Circle`, `cv.Line`, `cv.Text` etc.
  Draw connections first (behind), nodes on top. Manual hit-testing for clicks.
- **Animations**: implicit via `animate_opacity`, `animate_offset` on controls.
  `ft.AnimatedSwitcher` for combat log message transitions.
- **Images**: OpenWeather icons via `ft.Image(src="https://openweathermap.org/img/wn/{icon}@2x.png")`

## Game State

- Single `Run` object holds all game state (current node, roster, battle log)
- Combat is pure function: `resolve_combat(team, enemies, weather) -> BattleResult`
- Weather effects are lookup dicts, not inheritance hierarchies
- No I/O in game logic — API/file access stays in `api/` layer

## API Integration

- OpenWeather free tier: current weather by city name
- API key via env var `OPENWEATHER_API_KEY`
- Cache responses locally (JSON, 1h TTL)
- On failure: use cached data or default to Clear weather
- Never log API key

## Testing

- Unit tests for game logic (combat resolution, weather effects)
- Mock API responses with `unittest.mock.patch`
- No UI tests — test logic only

## Content Budget

~50 cities (one per node), ~60 champions, ~60 enemies, 6 weather states (Clear, Cloudy, Mist, Rain, Snow, Thunder)
