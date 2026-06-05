# Rosters — champions, enemies, bosses

> **Status: LIVING** — source of truth is `src/game/content.py` + `bosses/data.py`. Audited by `/check` (counts).
> **Scope:** the live roster invariants, the def→model build, and where the real data lives. **Reconciled:** 2026-06-05.
>
> This is a **thin pointer**: stat blocks, names, and lore live in code + the frozen catalogs (`docs/design/content/champion_roster.md`, `enemy_roster.md`, `boss_roster.md`). Here = the invariants and the build path.

## Counts (verified; `/check` re-checks against code)

- **60 champions** — `len(CHAMPION_ROSTER)`; tiers 1–10 × 6 affinities
  (`clear/cloudy/mist/rain/snow/thunder`).
- **60 enemies** — `len(ENEMY_ROSTER)`.
- **6 bosses** — `len(BOSS_DEFS)`.

## Source of truth (code, not this doc)

- `content.py` — authored tuples `_CHAMPION_DEFS: tuple[ChampionDef, ...]` and
  `_ENEMY_DEFS: tuple[EnemyDef, ...]` are the design data. They're built into the
  runtime model dicts:
  - `CHAMPION_ROSTER: dict[str, Champion]`, `ENEMY_ROSTER: dict[str, Enemy]`,
    `ENEMY_DEF_BY_ID: dict[str, EnemyDef]` (formation/encounter read the defs).
  - Accessors `get_champion(id)` / `get_enemy(id)`.
- `bosses/data.py` — `BOSS_DEFS: dict[str, BossDef]` (kit, map effect, spawn).

## Role taxonomy

A piece's `role`/`role_code` are **derived**, not authored: `classify_role(...)`
maps the design axes to a role title and `build_role_code(...)` to the role code
(see SPEC §V.31–V.33, the T.32 role/intent system). `CALLING_TAGS` is the
frozen trait-tag vocabulary `Champion.traits` draws from (see [traits.md](traits.md)).

`Champion` and `Enemy` share the same stat block + ability framework + damage
math — they differ only in operation (champions are drafted/bought/levelled,
carry traits). The combat entity built from either is the runtime `Piece`
(see [../systems/combat.md](../systems/combat.md)).

## Invariants

- Counts above hold (per the §T content budget); `/check` recomputes them.
- Every `active_ability`/`passive_ability` id on a def resolves in its registry
  — see [abilities.md](abilities.md) (CI-guarded).

## File map

| Concern | Symbol |
|---|---|
| Champion design data → models | `content.py` (`_CHAMPION_DEFS`, `ChampionDef`, `CHAMPION_ROSTER`, `get_champion`) |
| Enemy design data → models | `content.py` (`_ENEMY_DEFS`, `EnemyDef`, `ENEMY_ROSTER`, `ENEMY_DEF_BY_ID`, `get_enemy`) |
| Role derivation | `content.py` (`classify_role`, `build_role_code`, `CALLING_TAGS`) |
| Bosses | `bosses/data.py` (`BossDef`, `BOSS_DEFS`) |
