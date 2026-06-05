---
paths:
  - "src/game/**/*.py"
---

# Game Logic Rules

> **Before editing:** complete the required reading in [CLAUDE.md](../../CLAUDE.md) → "Required reading before any task work" — SPEC.md (§V invariants), ARCHITECTURE.md (the combat/weather/content/economy system you're touching), **the LIVING doc for that system ([docs/live/](../../docs/live/README.md))** — current truth, trust it over the frozen plan — the task plan doc, the touched design docs, and the touched code. Verify every primitive/stat against the code — design docs lie.
>
> **After editing:** update the matching `docs/live/` doc in the same change (real code taxonomy, not generic prose; flip its 🔶→✅ if you made it true), then run `/check`. A stale living doc is a bug.

- Combat resolution is a pure function — no side effects, no I/O
- Models use dataclasses with type hints
- Weather effects are dict lookups, not class hierarchies
- RNG seeded explicitly when needed for reproducibility
- No Flet imports in game/ — zero UI coupling
- All public functions have type hints
