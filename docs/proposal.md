# Tempest Fauna Trail

**A weather-driven roguelike where animal champions battle across real-world cities, with live weather data shaping every fight.**

---

## Problem Statement

Turn-based strategy games rarely connect to the real world in a meaningful way. Players engage with static, pre-designed encounters that feel the same every session. There is no sense of the world outside the game influencing what happens inside it — a missed opportunity for dynamic, ever-changing gameplay.

**Tempest Fauna Trail** solves this by pulling live weather data from real cities and using it as the core combat mechanic. Every playthrough feels different because the real weather in London, Cairo, Tokyo, Sydney, Rio de Janeiro, and New York directly buffs, debuffs, and reshapes each battle.

## Target Users

- Casual strategy gamers who enjoy auto-battlers (Teamfight Tactics, Super Auto Pets) and roguelikes (Slay the Spire, Into the Breach)
- Players who appreciate short, replayable sessions (~15–25 minutes per run)
- Users interested in novel real-world data integrations in games

---

## Core Features

### 1. Live Weather Combat System
**What:** Real-time weather data from the OpenWeather API determines combat modifiers at each city node. A directed predator/prey weather ring (Mist → Cloudy → Rain → Snow → Thunder) creates a dynamic type-advantage system where champions with matching or predator affinities gain attack/defense bonuses, while prey affinities suffer debuffs.

**User Value:** No two runs play the same. A team built around Snow champions dominates when it's snowing in Tokyo but struggles if the weather shifts to Thunder — forcing players to adapt strategy to real-world conditions they cannot control.

### 2. Global Route Map with Staged Progression
**What:** A fixed route of 6 continent stages (Europe → Africa → Asia → Oceania → South America → North America) spanning ~50 nodes, visualized as an interactive canvas map. Each stage hub city displays its current real weather icon, and encounters scale in difficulty toward a powerful final boss in New York whose affinity matches the city's live weather — the same rule as every other boss, just harder.

**User Value:** Players experience a sense of world travel and escalating challenge. The visual map with live weather overlays makes the journey feel tangible and connected to the real world, while staged difficulty provides clear progression.

### 3. Champion Team Building & Synergy System
**What:** Players recruit a team of ~3 animal champions from a roster of 60+ (across 6 weather affinities and 10 power tiers). Each champion has a weather affinity plus open-ended synergy traits (Hunter, Mammal, Reptile, Guardian, etc.) that unlock team bonuses when combined. An augment and economy system (Amber currency, Tempest XP) allows upgrading and expanding the team mid-run.

**User Value:** Deep roster variety and trait synergies give meaningful draft decisions every run. Players can specialize around a weather type for focused power or diversify for resilience — with the real weather adding a layer of unpredictable risk/reward to every team composition choice.

### 4. Auto-Resolved Combat with Animated Battle Log
**What:** Combat is tick-based and auto-resolved — the player's strategic decisions happen during team building and preparation, while battles play out with animated HP bars, damage numbers, and a scrolling combat log showing ability triggers, weather effects, and status applications.

**User Value:** Removes execution pressure while keeping fights visually engaging. Players can watch their strategy succeed or fail in real-time, learn from the animated log, and adjust their approach for the next node.

---

## Technical Stack

| Component | Technology |
|-----------|-----------|
| Framework | Flet (Python) — cross-platform desktop app |
| API | OpenWeather free tier (current weather by city) |
| Visualizations | Flet Canvas (route map) + BarChart (run summary) |
| Architecture | Modular: `api/`, `game/`, `ui/`, `viz/` — pure game logic with no UI coupling |

---

## Team

2 students — FH Technikum Wien, 8-week development timeline.
