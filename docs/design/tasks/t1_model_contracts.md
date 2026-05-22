# T1 Model Contracts

This document reflects the current implementation in `src/game/models.py`.

## 1. Enums

```python
class WeatherState(str, Enum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    MIST = "mist"
    RAIN = "rain"
    SNOW = "snow"
    THUNDER = "thunder"

class NodeType(str, Enum):
    FIGHT = "fight"
    REWARD = "reward"
    AUGMENT = "augment"
    BOSS_FIGHT = "boss_fight"

class NodeState(str, Enum):
    UPCOMING = "upcoming"
    CURRENT = "current"
    CLEARED = "cleared"

class RunStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    VICTORY = "victory"
    DEFEAT = "defeat"

class CombatOutcome(str, Enum):
    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"
```

### 1.1 OpenWeather Mapping Helper

`WeatherState` also exposes:

```python
@classmethod
def from_openweather_id(weather_id: int) -> WeatherState
```

Mapping:

- `200-299 -> THUNDER`
- `300-399` and `500-599 -> RAIN`
- `600-699 -> SNOW`
- `700-799 -> MIST`
- `800 -> CLEAR`
- `801-899 -> CLOUDY`
- otherwise raises `ValueError`

## 2. Dataclasses

### 2.1 Champion

```python
@dataclass(slots=True)
class Champion:
    id: str
    name: str
    affinity: WeatherState
    role: str
    tier: int
    level: int
    max_hp: int
    strength: int
    intelligence: int
    attack_speed: int
    move_speed: int
    mana_regen: int
    threat: int
    armor: int
    resistance: int
    attack_range: int
    active_ability: str
    passive_ability: str
    ability_cost: int
    traits: list[str] = field(default_factory=list)
    crit_chance: float = 0.0
    penetration: int = 0
    penetration_pct: float = 0.0
```

Validation:

- `tier` in `[1, 10]`
- `level` in `[1, 3]`
- `max_hp > 0`
- `strength`, `intelligence`, `attack_speed`, `move_speed`, `mana_regen`, `threat`, `armor`, `resistance >= 0`
- `attack_range > 0`
- `ability_cost > 0`
- `crit_chance`, `penetration_pct` in `[0.0, 1.0]`
- `penetration >= 0`
- `traits` must be non-empty unique strings

### 2.2 Enemy

```python
@dataclass(slots=True)
class Enemy:
    id: str
    name: str
    affinity: WeatherState
    role: str
    tier: int
    level: int
    max_hp: int
    strength: int
    intelligence: int
    attack_speed: int
    move_speed: int
    mana_regen: int
    threat: int
    armor: int
    resistance: int
    attack_range: int
    active_ability: str
    passive_ability: str
    ability_cost: int
    crit_chance: float = 0.0
    penetration: int = 0
    penetration_pct: float = 0.0
```

Validation:

- `tier` in `[1, 10]`
- `level` in `[1, 3]`
- `max_hp > 0`
- `strength`, `intelligence`, `attack_speed`, `move_speed`, `mana_regen`, `threat`, `armor`, `resistance >= 0`
- `attack_range > 0`
- `ability_cost > 0`
- `crit_chance`, `penetration_pct` in `[0.0, 1.0]`
- `penetration >= 0`

### 2.3 Node

```python
@dataclass(slots=True)
class Node:
    id: str
    index: int
    city: str
    weather: WeatherState
    node_type: NodeType = NodeType.FIGHT
    state: NodeState = NodeState.UPCOMING
    enemy_pool_id: str | None = None
    reward_table_id: str | None = None
    augment_pool_id: str | None = None
```

Validation:

- `index >= 1`

### 2.4 CombatPieceState

```python
@dataclass(slots=True)
class CombatPieceState:
    piece_id: str
    is_enemy: bool
    affinity: WeatherState
    tier: int
    level: int
    max_hp: int
    hp: int
    strength: int
    intelligence: int
    attack_speed: int
    move_speed: int
    mana_regen: int
    threat: int
    armor: int
    resistance: int
    attack_range: int
    ability_cost: int
    mana: int = 0
    action_energy: int = 0
    movement_energy: int = 0
    position_q: int = 0
    position_r: int = 0
    target_piece_id: str | None = None
    speed_tiebreaker: int = 0
    crit_chance: float = 0.0
    ability_can_crit: bool = False
    crit_counter: int = 0
    penetration: int = 0
    penetration_pct: float = 0.0
    alive: bool = True
```

`affinity` is copied from the source `Champion`/`Enemy` by
`weather_effects.apply_weather`; the combat engine reads it per hit for the
Affinity Clash affinity damage triangle (T.2 rework, SPEC B.5).

Validation:

- `tier` in `[1, 10]`
- `level` in `[1, 3]`
- `max_hp > 0`
- `hp >= 0`
- `strength`, `intelligence`, `attack_speed`, `move_speed`, `mana_regen`, `threat`, `armor`, `resistance >= 0`
- `attack_range > 0`
- `ability_cost > 0`
- `mana >= 0`, `action_energy >= 0`, `movement_energy >= 0`, `speed_tiebreaker >= 0`
- `crit_chance`, `penetration_pct` in `[0.0, 1.0]`
- `penetration >= 0`

Normalization in `__post_init__`:

- `hp` is clamped to `max_hp`
- `mana` is clamped to `ability_cost`
- if `hp == 0`, then `alive = False`

### 2.5 BattleEvent

```python
@dataclass(slots=True)
class BattleEvent:
    tick: int
    actor_id: str
    target_id: str | None
    event_type: str
    amount: int = 0
    note: str = ""
    is_crit: bool = False
```

Validation:

- `tick >= 0`

### 2.6 BattleResult

```python
@dataclass(slots=True)
class BattleResult:
    node_id: str
    weather: WeatherState
    outcome: CombatOutcome
    rounds: int
    turns: int
    duration_ticks: int
    team_damage_dealt: dict[str, int]
    team_damage_taken: dict[str, int]
    surviving_team_ids: list[str]
    surviving_enemy_ids: list[str]
    timed_out: bool = False
    events: list[BattleEvent] = field(default_factory=list)
```

Validation:

- `rounds >= 0`
- `turns >= 0`
- `duration_ticks >= 0`

### 2.7 Run

```python
@dataclass(slots=True)
class Run:
    run_id: str
    schema_version: int
    seed: int
    status: RunStatus
    roster: list[Champion]
    bench: list[Champion]
    route: list[Node]
    current_node_index: int
    battle_log: list[BattleResult] = field(default_factory=list)
    inventory: dict[str, int] = field(default_factory=dict)
    gold: int = 0
```

Validation:

- `schema_version >= 1`
- `route` is non-empty
- `gold >= 0`
- champion ids in `roster` are unique
- champion ids in `bench` are unique
- route node indexes are unique
- when `status == IN_PROGRESS`:
  - `current_node_index` must exist in route indexes
  - exactly one node is `CURRENT`
  - that node index must match `current_node_index`

Helpers:

- `current_node() -> Node | None`
- `mark_current_node_cleared() -> None`
- `advance_to_next_node() -> None`
- `is_complete() -> bool`

## 3. Serialization Contract

All models expose `to_dict()` / `from_dict()`. Enum values are stored as their string values and parsed via strict validation.

### 3.1 Run Payload Example

```json
{
  "schema_version": 1,
  "run_id": "run_20260521_001",
  "seed": 42,
  "status": "in_progress",
  "gold": 10,
  "inventory": {"potion_small": 2},
  "current_node_index": 1,
  "roster": [
    {
      "id": "champ_blaze_fox",
      "name": "Blaze Fox",
      "affinity": "clear",
      "traits": ["Mammal", "Hunter"],
      "role": "attacker",
      "tier": 3,
      "level": 1,
      "max_hp": 80,
      "strength": 18,
      "intelligence": 10,
      "attack_speed": 100,
      "move_speed": 100,
      "mana_regen": 5,
      "threat": 20,
      "armor": 8,
      "resistance": 6,
      "attack_range": 1,
      "active_ability": "Solar Pounce",
      "passive_ability": "Kindled Claws",
      "ability_cost": 100
    }
  ],
  "bench": [],
  "route": [
    {
      "id": "node_01",
      "index": 1,
      "city": "Reykjavik",
      "weather": "snow",
      "node_type": "fight",
      "state": "current",
      "enemy_pool_id": "pool_frost",
      "reward_table_id": null,
      "augment_pool_id": null
    }
  ],
  "battle_log": []
}
```

### 3.2 Strict Enum Parsing

Unknown enum values must raise a clear parse error in `from_dict()`.

## 4. Notes for T3

The model surface now includes combat-proposal-aligned runtime fields for:

- independent action/movement energy meters
- mana gating by `ability_cost`
- deterministic tie-breaking via `speed_tiebreaker`
- target tracking via `target_piece_id`
- hex positioning via `position_q` and `position_r`
- tick-level combat duration via `duration_ticks`
