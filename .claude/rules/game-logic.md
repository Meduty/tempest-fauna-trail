---
paths:
  - "src/game/**/*.py"
---

# Game Logic Rules

- Combat resolution is a pure function — no side effects, no I/O
- Models use dataclasses with type hints
- Weather effects are dict lookups, not class hierarchies
- RNG seeded explicitly when needed for reproducibility
- No Flet imports in game/ — zero UI coupling
- All public functions have type hints
