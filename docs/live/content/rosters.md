# Rosters — champions, enemies, bosses

> **Status: LIVING** — source of truth is `src/game/content.py` + `bosses/data.py`. Audited by `/check` (counts + axis marginals).
> **Scope:** the live roster invariants, the `def → model` build, the six identity axes `compose_stats` turns into a stat block, and where the real data lives. **Reconciled:** 2026-07-01.
>
> Stat blocks, names, and lore live in code + the frozen catalogs
> (`docs/design/content/champion_roster.md`, `enemy_roster.md`, `boss_roster.md`).
> Here = the invariants, the axis vocabulary, and the build path.

## Counts (verified; `/check` re-checks against code)

- **60 champions** — `len(CHAMPION_ROSTER)`; tiers 1–10 × 6 affinities
  (`clear/cloudy/mist/rain/snow/thunder`), 10 per affinity
  (`_validate_rosters`, `content.py:715`).
- **60 enemies** — `len(ENEMY_ROSTER)`; 30 `CLEAR` + 6 for each of the other 5
  weathers (`content.py:720`).
- **6 bosses** — `len(BOSS_DEFS)` (`bosses/data.py`).

## Source of truth (code, not this doc)

- `content.py` — authored tuples `_CHAMPION_DEFS: tuple[ChampionDef, ...]` and
  `_ENEMY_DEFS: tuple[EnemyDef, ...]` are the design data. They're built into the
  runtime model dicts:
  - `CHAMPION_ROSTER: dict[str, Champion]`, `ENEMY_ROSTER: dict[str, Enemy]`,
    `ENEMY_DEF_BY_ID` / `CHAMPION_DEF_BY_ID: dict[str, <Def>]` (formation/encounter
    read the defs).
  - Accessors `get_champion(id)` / `get_enemy(id)`; level rebuilds
    `build_champion_at_level(id, level)` / `build_enemy_at_level(id, level)` for
    L1–L3 (`content.py:693`).
- `bosses/data.py` — `BOSS_DEFS: dict[int, BossDef]` (keyed by stage index 1–6; kit, map effect, spawn).

## Def → model build path

Each def is a **compact identity declaration** — six axis tokens plus content
metadata — and the runtime `Champion`/`Enemy` is *derived*, not hand-authored
(`_build_champion` / `_build_enemy`, `content.py:383`):

1. `compose_stats(stat, reach, durability, playstyle, speed, intent, tier)` →
   a full combat stat dict from the six axes at that tier (see next section).
2. `_assert_budget` — `stat_overrides` may drift the five PRIMARY stats by at most
   **±15%** of their base budget (`content.py:365`).
3. `_apply_stat_overrides` — flat per-stat nudges, applied **after** tier-scale,
   **before** level-scale; keys must be real stat keys (`ALL_STAT_KEYS`).
4. `level_scale_stats(base, tier, level)` — scaling curve (no-op at L1).
5. `role` / `role_code` derived via `classify_role` / `build_role_code`;
   `active_abilities` resolved (explicit `abilities=` list, or auto-discovery — see
   below); `passive_ability` = `"{id}.passive"`.

**Ability discovery (T.29d, V.49):** a def's `abilities=None` (the factory default)
auto-discovers every registered `{id}.active`, `{id}.active2`, … in sorted order
(`discover_abilities`, `content.py:19`). An explicit list overrides (named kits,
bosses, or `[]` for a deliberately ability-less stat-stick). Every resolved
`active`/`passive` id must exist in its registry (CI-guarded — see
[abilities.md](abilities.md)).

**Champion vs Enemy defs** share the whole stat/ability/damage framework and differ
only in operation and metadata:

| | `ChampionDef` | `EnemyDef` |
|---|---|---|
| id prefix | `champ_…` | `enemy_…` |
| tagging | `traits: list[str]` from `ALL_TRAIT_TAGS` (Kinship ∪ Calling), non-empty | `tags: frozenset[str]` from `ENEMY_TAGS` (`human/beast/corrupted/machine/spirit`) |
| operation | drafted / bought / levelled | spawned by encounter/formation |
| extra guard | tier-10 champions **must** carry `Primordial` (`content.py:661`) | — |

The combat entity built from either is the runtime `Piece`
(see [../systems/combat.md](../systems/combat.md)).

## `compose_stats` — the six identity axes (V.33)

`compose_stats` starts from `_BASE_STATS` and multiplies in each axis, then applies
the intent stat-bias, then tier-scales. This is the whole numeric identity of a
piece — no per-stat hand-authoring beyond the ±15% `stat_overrides`.

**Base stats** (`_BASE_STATS`, `content.py:27`): `max_hp 600`, `strength 50`,
`intelligence 50`, `armor 25`, `resistance 25`, `attack_speed 100`,
`mana_regen 100`, `move_speed 100`, `threat 60`, `attack_range 2`,
`crit_chance 0.0`, `penetration 0`, `penetration_pct 0.0`.

**Apply order** (`content.py:311`): primary-stat × reach × durability × playstyle
multipliers → reach sets a discrete `attack_range` → **speed** → **intent** bias
(one fixed point) → tier-scale.

| Axis | Values | What it does (`content.py`) |
|---|---|---|
| **stat** | `str` · `int` · `hybrid` | Splits STR/INT. `str` = 1.8 STR / 0.2 INT; `int` = 0.2 / 1.8; `hybrid` = 1.0 / 1.0 (`_PRIMARY_STAT:43`). |
| **reach** | `melee` · `ranged` | `melee`: +HP/armor/res/AS, `attack_range = 1`. `ranged`: −armor/res/HP/AS, `attack_range = 3`. The one **required positional** axis (no `hybrid` value) (`_REACH:49`). |
| **durability** | `squishy` · `hybrid` · `tanky_hp` · `tanky_arm` | Trades HP/armor/res against STR/INT and `threat`. Tanks read STR/INT at **0.42** so a primary-stat tank no longer rivals an assassin's primary (T.35b, B.20) (`_DURABILITY:66`). |
| **playstyle** | `auto` · `hybrid` · `ability` | `auto`: ×1.3 AS, ×0.6 mana_regen. `ability`: ×0.75 AS, ×1.5 mana_regen, ×0.85 threat (`_PLAYSTYLE:101`). |
| **speed** | 7 tiers (below) | Tempo/throughput trade: faster ⇒ ↑AS + ↑move_speed, ↓primary_stat (softer per-hit/cast) (`_SPEED:113`). |
| **intent** | `damage` · `utility` · `hybrid` | Power-**neutral** re-flavour (V.33): `damage` biases toward STR/INT/AS at the cost of HP/armor/res/threat; `utility` the reverse; `hybrid` is identity (`_INTENT:130`). |
| **tier** | `1..10` | Tier-scale: PRIMARY stats on `sqrt(power)`, SECONDARY on a gentle curve; `attack_speed` stays float (see [scaling](../systems/) / `scaling.py`). |

### Speed axis vocabulary (T.33b — 7 levels, slow → fast)

`_SPEED` (`content.py:113`). `hybrid` is the neutral centre (omitted from
`role_code`); `classify_role` ignores speed. Finer granularity ⇒ distinct pieces
rarely share an `attack_speed`.

| Speed | attack_speed | primary_stat | move_speed |
|---|---|---|---|
| `moloch` | ×0.70 | ×1.25 | ×0.70 |
| `leaden` | ×0.85 | ×1.12 | ×0.85 |
| `heavy` | ×0.92 | ×1.06 | ×0.92 |
| `hybrid` | ×1.00 | ×1.00 | ×1.00 |
| `light` | ×1.10 | ×0.95 | ×1.08 |
| `swift` | ×1.20 | ×0.90 | ×1.15 |
| `blazing` | ×1.35 | ×0.82 | ×1.25 |

> **Vocabulary note (LIVING):** these seven tokens
> (`moloch/leaden/heavy/hybrid/light/swift/blazing`) are the **current** speed
> vocabulary — the axis was renamed. Always verify against `content.py::_SPEED`;
> any other speed name predates the rename and is dead.

**Caster tempo special-case** (`content.py:325`): for `playstyle="ability"` the
speed's `attack_speed` deviation is **halved and applied to BOTH `attack_speed`
and `mana_regen`** — a faster caster acts and refills mana quicker (more, softer
casts), at half the swing since it lands on two stats. The `primary_stat` trade
applies to whichever of STR/INT the piece keys (`str`/`int`/`hybrid`).

### Ability mana cost

Ability cost is **uniform** — no longer a per-unit def field. It is a constant
(`DEFAULT_MANA_COST = 300_000`, `registries.py:48`) authored per-ability on the
`ActiveSlot` (V.35/V.48), not a `Piece` stat.

## Role taxonomy

A piece's `role`/`role_code` are **derived**, not authored. `classify_role(...)`
maps the six axes to one of **9 coarse role titles** (`ROLE_TITLES`,
`content.py:161`): `tank`, `bruiser`, `support`, `mage`, `marksman`, `assassin`,
`swashbuckler`, `spellblade`, `spellslinger`. `build_role_code(...)` joins the six
axis tokens in fixed order, omitting every `hybrid`, into the fine descriptor
(a non-positional tag-set, V.32; never empty because `reach` is never `hybrid`).
`Spellslinger` (ranged, playstyle-hybrid, damage) is the newest role (T.36b).
See SPEC §V.31–V.33 and the T.32 role/intent system.

`CALLING_TAGS` is the frozen Calling trait-tag vocabulary `Champion.traits` draws
from, alongside the 6 `KINSHIP_TAGS` (see [traits.md](traits.md)).

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
`_ENEMY_DEFS`; ±2 of target is in-band — **verified 2026-07-01**):

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
hybrid ability-users read both). Combined champ-vs-enemy **sim balance-validation
DONE** [2026-06-17] (`tools/simulation/stat_edge.py`, team sims 2–5v5 × all weathers,
`results/stat_edge_t36c.csv` n=8000 + iterate `_t36d.csv` n=1500): **zero champs over
the `|wr_delta|>0.10` contract bar** after a 5-champ tune (mournhollow/veilfang_wolf/
ember_salamander trimmed; aurion/will_o_fawn buffed — `champions.py`). 44/60 inside
±0.05; the ±0.05 stretch on 3 stubborn over-performers (ember/mournhollow/veilfang
~+0.085, within n=1500 noise) is deferred to the full random-vs-random power sim.
**D.25 reframe:** the residual STR-ability edge (+0.035) is STR-ability *over*-budget
(free auto-tagalong `1·STR+0.25·INT`), not INT-ability under — no further global INT
bump warranted.

## Invariants

- Counts + per-affinity splits above hold (`_validate_rosters`, `content.py:711`);
  `/check` recomputes them.
- Every `active_ability`/`passive_ability` id on a def resolves in its registry
  — see [abilities.md](abilities.md) (CI-guarded).
- Champion traits ⊆ `ALL_TRAIT_TAGS`, non-empty; enemy tags ⊆ `ENEMY_TAGS`,
  non-empty (build-time asserts).
- Tier-10 champions carry `Primordial`.
- `stat_overrides` drift ≤ ±15% of PRIMARY budget (`_assert_budget`).
- §V.47 axis↔scaling: `int`/`hybrid` units reference INT in their kit (no dead INT).

## File map

| Concern | Symbol |
|---|---|
| Champion design data → models | `content.py` (`_CHAMPION_DEFS`, `ChampionDef`, `_champion_def`, `CHAMPION_ROSTER`, `get_champion`) |
| Enemy design data → models | `content.py` (`_ENEMY_DEFS`, `EnemyDef`, `_enemy_def`, `ENEMY_ROSTER`, `ENEMY_DEF_BY_ID`, `get_enemy`) |
| Axis → stat block | `content.py` (`compose_stats`, `_BASE_STATS`, `_PRIMARY_STAT`, `_REACH`, `_DURABILITY`, `_PLAYSTYLE`, `_SPEED`, `_INTENT`) |
| Role derivation | `content.py` (`classify_role`, `build_role_code`, `ROLE_TITLES`, `CALLING_TAGS`, `KINSHIP_TAGS`) |
| Ability discovery | `content.py` (`discover_abilities`) |
| Tier / level scaling | `scaling.py` (`compose_stats` calls `stat_multiplier` / `level_scale_stats`) |
| Bosses | `bosses/data.py` (`BossDef`, `BOSS_DEFS`) |
