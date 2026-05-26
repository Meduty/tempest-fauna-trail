# T24 Plan — Enemy Formation Policy (`src/game/formation.py`)

> **Status:** ✅ Implemented — amendments applied (§4.2 flanker repositioning, §5.6 per-boss authored position).
> **Depends:** T.19 (squads generated), T.1 (models), T.3 (combat engine board).
> **Consumed by:** T.3 combat init, T.21 boss placement, T.23 (player placement is
> separate — T24 is enemy-side only).

---

## 1. Scope

T24 replaces the current index-only enemy spawn packing (`_assign_spawns` in
`combat.py`) with a deterministic, role-aware formation planner. Enemy placement
should feel **tactically coherent**: tanks in front absorbing damage, bruisers
and warriors behind them, assassins flanking, marksmen and mages in the backline.

**Primary output:** `src/game/formation.py`
**Test output:** `tests/game/test_formation.py`

**Out of scope:**
- Adaptive counter-positioning against player comp (future AI work)
- Terrain/map-effect-aware placement (future map effect integration)
- Mid-fight reformation behavior
- Player team placement (T23 handles that)

---

## 2. Design Philosophy

### 2.1 Formations should feel intentional, not optimal

The goal is not a chess-engine-level AI that perfectly counters the player's
formation. The goal is an **enemy team that looks and fights like it was
arranged by a competent commander**:

- Tanks and bruisers form a shield wall
- Fragile damage dealers stay behind the wall
- Supports sit where they can reach allies
- Assassins may start at the flanks

This makes combat visually readable and tactically interesting. The player
can identify threats and plan around the enemy formation during prep.

### 2.2 Determinism

Enemy formation is a **pure function** of the enemy squad (roster + roles). No
RNG is used — given the same squad, the formation is identical every time. This
preserves the determinism invariant (V.2).

---

## 3. Board Layout

Current board: **10 columns × 7 rows** (axial hex grid).

Player deployment zone: columns 0–2 (left side).
Enemy deployment zone: columns 7–9 (right side).
No-man's-land: columns 3–6.

```
Player side (cols 0-2)     Gap (3-6)     Enemy side (cols 7-9)
[P] [P] [P]  [.] [.] [.] [.]  [E] [E] [E]
[P] [P] [P]  [.] [.] [.] [.]  [E] [E] [E]
[P] [P] [P]  [.] [.] [.] [.]  [E] [E] [E]
[P] [P] [P]  [.] [.] [.] [.]  [E] [E] [E]
[P] [P] [P]  [.] [.] [.] [.]  [E] [E] [E]
[P] [P] [P]  [.] [.] [.] [.]  [E] [E] [E]
[P] [P] [P]  [.] [.] [.] [.]  [E] [E] [E]
```

Enemy deployment: 3 columns × 7 rows = **21 max slots**. More than sufficient
for max squad size (~10–11).

---

## 4. Role Bucketing

### 4.1 Role classification from piece data

`CombatPieceState` is runtime combat data and does not carry archetype fields
like `range_` / `durability`. Role classification therefore reads those fields
from the originating `EnemyDef` in `content.py`, looked up by `piece_id`.
These are mapped to **placement roles**:

```python
class PlacementRole(Enum):
    FRONTLINE = "frontline"    # Tanks, bruisers — absorb damage
    MIDLINE   = "midline"      # Warriors, hybrid melee — deal and take
    FLANK     = "flank"        # Assassins — start at edges
    BACKLINE  = "backline"     # Mages, marksmen, supports — stay behind
```

**Classification rules:**

```python
def classify_role(enemy_def: EnemyDef) -> PlacementRole:
    # Use archetype tags from content.py
    durability = enemy_def.durability
    range_ = enemy_def.range_

    # Tanks go front
    if durability in ("tanky_hp", "tanky_arm"):
        return PlacementRole.FRONTLINE

    # Melee squishy = assassin flank
    if range_ == "melee" and durability == "squishy":
        return PlacementRole.FLANK

    # Melee standard = bruiser/warrior midline
    if range_ == "melee":
        return PlacementRole.MIDLINE

    # Ranged = backline (mages, marksmen, supports)
    return PlacementRole.BACKLINE
```

### 4.2 Archetype-to-role mapping

For reference, the archetype→role mapping for enemy types:

| Archetype (from `enemy_roster.md`) | Placement role |
|---|---|
| Tank-HP, Tank-STR, Tank-ARM+RES, Tank-INT | FRONTLINE |
| Hybrid-Tank/DMG | FRONTLINE |
| ADC-STR Warrior, Hybrid-INT/STR | MIDLINE |
| APC-INT Assassin, APC-STR Assassin | FLANK |
| APC-INT Mage, APC-STR Mage | BACKLINE |
| ADC-STR Marksman, ADC-INT Marksman | BACKLINE |
| SUP-Heal, SUP-Buff, SUP-Shield, SUP-Debuff | BACKLINE |
| Hybrid-APC/ADC | BACKLINE |

> **⚠ DECISION NEEDED:** Whether `Hybrid-Tank/DMG` should be FRONTLINE (they
> are tanky enough to front) or MIDLINE (they want to deal damage). The roster
> tags them as hybrids that *hold the line while hitting* — that's FRONTLINE
> behavior. **Recommendation:** FRONTLINE — they fill the same battlefield
> role as tanks.

---

## 5. Formation Algorithm

### 5.1 Column assignment

Enemy columns are numbered 7 (front, closest to player), 8 (mid), 9 (back).

| Role | Assigned column |
|---|---|
| FRONTLINE | 7 (foremost enemy column) |
| MIDLINE | 8 |
| FLANK | 7 or 8 (top/bottom rows — edges of the formation) |
| BACKLINE | 9 (rearmost enemy column) |

### 5.2 Row assignment within columns

Within each column, pieces are placed **center-out** for compact formations:

```python
CENTER_ROW = BOARD_HEIGHT // 2  # row 3 on a 7-row board

def center_out_rows(count: int, board_height: int) -> list[int]:
    """Return 'count' row indices, center-out."""
    center = board_height // 2
    rows = [center]
    offset = 1
    while len(rows) < count:
        if center - offset >= 0:
            rows.append(center - offset)
        if len(rows) < count and center + offset < board_height:
            rows.append(center + offset)
        offset += 1
    return rows[:count]
```

### 5.3 Flank placement

Assassins/flankers use the **edge rows** (row 0 and row `BOARD_HEIGHT - 1`) of
the front or mid column, placing them at the periphery of the formation where
they can slip past the frontline:

```python
FLANK_ROWS = [0, BOARD_HEIGHT - 1]  # top and bottom edges

def place_flankers(flankers: list, occupied: set[tuple[int, int]]) -> dict[str, tuple[int, int]]:
    placements = {}
    for i, piece in enumerate(flankers):
        col = 7 if i % 2 == 0 else 8  # Alternate between front and mid columns
        row = FLANK_ROWS[i % 2]
        if (col, row) in occupied:
            # Spill to adjacent unoccupied cell
            row = _nearest_free_row(col, row, occupied)
        placements[piece.piece_id] = (col, row)
        occupied.add((col, row))
    return placements
```

### 5.4 Overflow handling

If a column is full (all 7 rows occupied), overflow pieces spill to the next
nearest column:
- FRONTLINE overflow → column 8
- BACKLINE overflow → column 8
- MIDLINE overflow → column 7 (prefer front) then 9

### 5.5 Full algorithm

```python
def plan_enemy_formation(
    enemies: list[CombatPieceState],
    enemy_defs_by_piece_id: dict[str, EnemyDef],
    *,
    board_width: int = BOARD_WIDTH,
    board_height: int = BOARD_HEIGHT,
) -> dict[str, tuple[int, int]]:
    """
    Deterministic role-aware enemy formation.
    Returns {piece_id: (col, row)} for each enemy.
    """
    # 1. Classify roles
    buckets: dict[PlacementRole, list] = {role: [] for role in PlacementRole}
    for enemy in sorted(enemies, key=lambda e: (e.piece_id,)):  # deterministic order
        enemy_def = enemy_defs_by_piece_id.get(enemy.piece_id)
        if enemy_def is None:
            raise ValueError(f"Missing EnemyDef for piece_id={enemy.piece_id!r}")
        role = classify_role(enemy_def)
        buckets[role].append(enemy)

    occupied: set[tuple[int, int]] = set()
    placements: dict[str, tuple[int, int]] = {}

    # 2. Place frontline (column 7, center-out)
    _place_band(
        buckets[PlacementRole.FRONTLINE],
        col=7,
        occupied=occupied,
        placements=placements,
        board_height=board_height,
    )

    # 3. Place flankers (edges of columns 7-8)
    _place_flankers(buckets[PlacementRole.FLANK], occupied, placements, board_height)

    # 4. Place midline (column 8, center-out)
    _place_band(
        buckets[PlacementRole.MIDLINE],
        col=8,
        occupied=occupied,
        placements=placements,
        board_height=board_height,
    )

    # 5. Place backline (column 9, center-out)
    _place_band(
        buckets[PlacementRole.BACKLINE],
        col=9,
        occupied=occupied,
        placements=placements,
        board_height=board_height,
    )

    return placements
```

### 5.6 Boss placement override

Boss pieces (T10) are placed at a **fixed position**: the center of the
backline (column 9, row 3). If that cell is occupied, the boss takes it and
displaces the occupant to the nearest free cell. This makes the boss visually
prominent and narratively correct — the commander stands behind their troops.

```python
BOSS_POSITION = (9, 3)  # center-back

def _place_boss(boss: CombatPieceState, occupied: set, placements: dict) -> None:
    # Displace any piece already at BOSS_POSITION
    for pid, pos in placements.items():
        if pos == BOSS_POSITION:
            new_pos = _nearest_free(BOSS_POSITION, occupied)
            placements[pid] = new_pos
            occupied.discard(BOSS_POSITION)
            occupied.add(new_pos)
            break
    placements[boss.piece_id] = BOSS_POSITION
    occupied.add(BOSS_POSITION)
```

> **⚠ DECISION NEEDED:** Whether the boss should always be center-back, or
> whether brawler-type bosses (Holloway, Vossberg) should start in the
> **frontline** (column 7). Their kits are melee-forward — a backline start
> wastes their opening ticks walking forward.
> **Recommendation:** per-boss authored position. Melee bosses (Holloway,
> Vossberg) start at (7, 3). Ranged/caster bosses (Vance, Strand, Crège) start
> at (9, 3). The Iron Emperor is TBD. Store this as a `spawn_position` field
> on the boss data.

---

## 6. Visual Examples

### 6.1 Small squad (3 enemies — stage 1)

```
col 7    col 8    col 9
  .        .        .       row 0
  .        .        .       row 1
  .        .        .       row 2
 [Tank]    .      [Mage]    row 3 (center)
  .        .        .       row 4
  .      [Warrior]  .       row 5
  .        .        .       row 6
```

### 6.2 Medium squad (6 enemies — stage 3)

```
col 7    col 8    col 9
  .        .        .       row 0
 [Tank]    .      [Mark]    row 1
  .      [Warr]    .        row 2
 [Tank]    .      [Mage]    row 3 (center)
  .      [Warr]    .        row 4
  .        .      [Supp]    row 5
  .        .        .       row 6
```

### 6.3 Large squad (9 enemies — stage 6)

```
col 7    col 8    col 9
 [Assn]    .        .       row 0 (flank)
 [Tank]  [Warr]  [Mark]     row 1
  .      [Warr]  [Mage]     row 2
 [Tank]    .     [Supp]     row 3 (center)
  .      [Warr]  [Mark]     row 4
  .        .        .       row 5
 [Assn]    .        .       row 6 (flank)
```

---

## 7. Integration with Combat Init

### 7.1 Current flow (T3)

```python
def _assign_spawns(pieces):
    # Index-based packing — no role awareness
    for piece in pieces:
        if piece.is_enemy:
            piece.position_q = BOARD_WIDTH - 1 - (enemy_index // BOARD_HEIGHT)
            piece.position_r = enemy_index % BOARD_HEIGHT
```

### 7.2 New flow (T24)

```python
def _assign_spawns(pieces, team_positions=None):
    # Player team: T23 snapshot or fallback
    if team_positions:
        for piece in pieces:
            if not piece.is_enemy and piece.piece_id in team_positions:
                piece.position_q, piece.position_r = team_positions[piece.piece_id]
    else:
        _assign_player_fallback(pieces)

    # Enemy team: T24 formation planner
    enemies = [p for p in pieces if p.is_enemy]
    formation = plan_enemy_formation(enemies)
    for piece in enemies:
        piece.position_q, piece.position_r = formation[piece.piece_id]
```

The existing `speed_tiebreaker` assignment remains unchanged — it's determined
after placement.

---

## 8. Test Plan

See T.16 for full test details. Summary:

1. **Determinism:** identical squad → identical formation. No RNG.
2. **Role correctness:** frontline average column < backline average column
   (frontline is closer to the player).
3. **Center-out packing:** pieces in the same column cluster around the center
   row.
4. **Flank placement:** assassins are at edge rows.
5. **Boss placement:** boss is at authored position; displaces any occupant.
6. **Size scaling:** 1, 2, 3, 5, 8, 11 enemy squads all produce valid layouts.
7. **No duplicates:** no two pieces share a cell.
8. **No off-board:** all coordinates within `[0, board_width) × [0, board_height)`.
9. **Overflow:** column overflow spills correctly to adjacent columns.
10. **Fallback:** if planner fails catastrophically, existing index packing is
    used (never crash).
11. **Integration:** combat with formation planner produces valid `BattleResult`.

---

## 9. Acceptance Criteria

1. `src/game/formation.py` exists, pure, zero Flet imports.
2. Enemy placement is role-aware and deterministic.
3. Formations are valid for all tested squad sizes (1–11).
4. Boss placement uses authored position.
5. Fallback path remains safe and deterministic.
6. Combat tests pass with new formation planner integrated.
7. `tests/game/test_formation.py` passes.

---

## 10. Open Items Summary

| # | Question | Recommendation | Impact if deferred |
|---|---|---|---|
| 1 | Hybrid-Tank/DMG: FRONTLINE or MIDLINE? | FRONTLINE | Low — cosmetic |
| 2 | Boss position: fixed center-back or per-boss authored? | Per-boss authored | Medium — affects melee boss feel |
| 3 | Adaptive counter-positioning against player comp | Defer to post-MVP | Zero for MVP |
| 4 | Map-effect-aware placement (avoid hazard tiles) | Defer — T21 map effects land later | Zero for MVP |
| 5 | Support sub-positioning (near allies they buff) | Center-out is sufficient for MVP | Low — supports are effective anywhere |
| 6 | Multiple frontline/backline columns for large squads | Overflow handles it | Low — cosmetic |
