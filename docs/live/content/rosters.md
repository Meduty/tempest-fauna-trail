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

## Stat-axis balance (T.35b, #42 Finding B / B.20)

The `stat` axis × `durability` jointly set a unit's primary. T.35b re-tuned two
axis tables in `content.py` so a primary-stat **tank no longer rivals an
assassin's primary** (was: `1.8·str-axis × 0.55·tanky ≈ 0.99 ≈` a bruiser):

- `_DURABILITY` tanky_hp / tanky_arm `strength`/`intelligence` **`0.55 → 0.42`**.
- `_INTENT` damage `strength`/`intelligence` **`1.08 → 1.14`**, utility **`0.94 → 0.87`**
  (defensive stats compensate so the V.33 HP·DPS proxy stays in `[0.90,1.10]`:
  damage `1.075`, utility `0.947`). Example: Coral Colossus STR `92→65`,
  Duskstep Marten INT `127→134`.

**Dead-INT carriers fixed:** every `int`/`hybrid` unit now reads INT in its kit —
per-role INT coefficients added to ~14 carriers' ability outlets (authored as
`Magnitude`s, T.35a). Enforced by **§V.47** (`test_axis_scaling_alignment`):
`stat="int"` must reference INT via a meta `Magnitude`, `hybrid` references both,
`str` is auto-satisfied by the auto-attack. `enemy_steam_engineer` is allowlisted
(its INT sizes the turret `SummonSpec`, not a meta outlet).

## Axis-distribution rebalance (T.36)

The roster axes were rebalanced to principled marginals (a unified solve — role is
a pure fn of axes, V.32, so the marginals + soft role floors are the target and the
role distribution is derived). Live counts (recompute from `_CHAMPION_DEFS` /
`_ENEMY_DEFS`; ±2 of target is in-band):

| axis | champions | enemies |
|---|---|---|
| **stat** | str 22 · int 22 · hybrid 16 | str 22 · int 22 · hybrid 16 |
| **playstyle** | auto 24 · ability 24 · hybrid 12 | auto 22 · ability 22 · hybrid 16 |
| **reach** | melee 28 · ranged 32 | melee 30 · ranged 30 |
| **durability** | thp 11 · tarm 6 · squishy 13 · hybrid 30 | thp 11 · tarm 7 · squishy 13 · hybrid 29 |
| **intent** | damage 28 · utility 20 · hybrid 12 | damage 29 · utility 19 · hybrid 12 |

**Emergent enemy roles** (T.36c — curated by name/lore, opaque tags V.22): tank 12 ·
support 11 · spellblade 6 · bruiser 6 · mage 6 · swashbuckler 6 · marksman 5 ·
assassin 4 · spellslinger 4. New `Spellslinger` role (V.32, T.36b). All roles ≥4.
Re-axised kits honor V.46/V.47 (every int/hybrid enemy reads its primary stat;
hybrid ability-users read both). Combined champ-vs-enemy **sim balance-validation is
deferred** (a follow-up `stat_edge` sweep, as with T.36b).

## Invariants

- Counts above hold (per the §T content budget); `/check` recomputes them.
- Every `active_ability`/`passive_ability` id on a def resolves in its registry
  — see [abilities.md](abilities.md) (CI-guarded).
- §V.47 axis↔scaling: `int`/`hybrid` units reference INT in their kit (no dead INT).

## File map

| Concern | Symbol |
|---|---|
| Champion design data → models | `content.py` (`_CHAMPION_DEFS`, `ChampionDef`, `CHAMPION_ROSTER`, `get_champion`) |
| Enemy design data → models | `content.py` (`_ENEMY_DEFS`, `EnemyDef`, `ENEMY_ROSTER`, `ENEMY_DEF_BY_ID`, `get_enemy`) |
| Role derivation | `content.py` (`classify_role`, `build_role_code`, `CALLING_TAGS`) |
| Bosses | `bosses/data.py` (`BossDef`, `BOSS_DEFS`) |
