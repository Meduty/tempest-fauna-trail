# Tempest Fauna Trail

A small roguelike where animal champions travel a fixed route of real-world cities, and the live weather at each stop shapes the battle.

## Problem Statement

Strategy roguelikes rely entirely on procedural randomness, which eventually feels repetitive. **Tempest Fauna Trail** replaces part of that randomness with real-world data: each city node pulls live weather from the OpenWeather API and applies clear, readable modifiers to the upcoming battle. The result is a short, replayable strategy game whose variance comes from the actual planet.

## Core Features

1. **Fixed-route world tour** -- ~6 city nodes visited in order, each with a single battle. Completing the route wins the run.
2. **Live weather modifiers (OpenWeather API)** -- On entering each city, the game queries OpenWeather and maps the result to one of 5 weather states (Clear, Rain, Storm, Heat, Cold). Each state applies visible combat modifiers.
3. **Team building with weather affinities (auto-resolved combat)** -- Players recruit from ~8 animal/spirit champions, each with one weather affinity. Matching the city's weather grants a bonus; mismatched units lose effectiveness. Combat is auto-resolved turn-by-turn.

## Visualizations

- **Route map view** -- The fixed city route with a weather icon on each upcoming node.
- **Run summary screen** -- A chart of damage dealt/taken per battle and win/loss outcome.

## Tech Stack

- **Language:** Python 3.10+
- **UI Framework:** Flet
- **API:** OpenWeather API (free tier)
- **Data Storage:** Local JSON for save data

## Project Structure

```
src/
  api/          # OpenWeather API client, data models
  game/         # Core entities (Champion, Enemy, Node, Run), combat rules
  ui/           # Flet views and navigation
  viz/          # Chart and map visualization components
assets/         # Static assets (icons, data files)
docs/           # Documentation, flow charts
tests/          # Unit tests
```

## Setup & Run

```bash
# Clone the repo
git clone https://github.com/Meduty/tempest-fauna-trail.git
cd tempest-fauna-trail

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Set your OpenWeather API key
export OPENWEATHER_API_KEY="your-key-here"

# Run the app
python -m src.main
```

## Team

- **Partner A** -- UI & user flow
- **Partner B** -- Data fetching & visualization logic

## Division of Work

| Feature | Responsible |
|---------|-------------|
| Flet UI / navigation | Partner A |
| OpenWeather API integration | Partner B |
| Game logic / combat | TBD |
| Visualizations (map + charts) | Partner B |
| Documentation & flow charts | Both |

## Prompting Strategy

*(To be filled in during development)*

## Flow Chart

*(To be added in `docs/`)*
