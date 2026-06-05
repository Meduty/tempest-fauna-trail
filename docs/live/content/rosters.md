# Rosters — champions, enemies, bosses

> **Status: LIVING** — source of truth is `src/game/content.py` + `bosses/data.py`. Audited by `/check` (counts).
> **Scope:** the live roster invariants and where the real data lives. **Reconciled:** 2026-06-05.
>
> 🔶 **STUB** — invariants + pointers; lore/intent stay in the frozen `docs/design/content/champion_roster.md`, `enemy_roster.md`, `boss_roster.md`.

## Source of truth (code, not this doc)
- `content.py` — `CHAMPION_ROSTER`, `ENEMY_ROSTER`, `ENEMY_DEF_BY_ID`.
- `bosses/data.py` — `BOSS_DEFS`.

## Invariants (`/check` verifies counts vs SPEC §V / §T budget)
- ~60 champions (1 per affinity × 10 tiers), ~60 enemies, 6 bosses.
