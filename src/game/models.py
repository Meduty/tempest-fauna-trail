from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar


class WeatherState(str, Enum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    MIST = "mist"
    RAIN = "rain"
    SNOW = "snow"
    THUNDER = "thunder"

    @classmethod
    def from_openweather_id(cls, weather_id: int) -> "WeatherState":
        if 200 <= weather_id < 300:
            return cls.THUNDER
        if 300 <= weather_id < 400 or 500 <= weather_id < 600:
            return cls.RAIN
        if 600 <= weather_id < 700:
            return cls.SNOW
        if 700 <= weather_id < 800:
            return cls.MIST
        if weather_id == 800:
            return cls.CLEAR
        if 800 < weather_id < 900:
            return cls.CLOUDY
        raise ValueError(f"Unknown OpenWeather id: {weather_id}")


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


EnumT = TypeVar("EnumT", bound=Enum)


def _parse_enum(enum_cls: type[EnumT], value: str, field_name: str) -> EnumT:
    try:
        return enum_cls(value)
    except ValueError as exc:
        valid_values = ", ".join(member.value for member in enum_cls)
        raise ValueError(
            f"Invalid {field_name!r}: {value!r}. Expected one of: {valid_values}."
        ) from exc


def _require_positive_int(value: int, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be > 0.")


def _require_non_negative_int(value: int, field_name: str) -> None:
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0.")


def _require_range(value: int, field_name: str, min_value: int, max_value: int) -> None:
    if not min_value <= value <= max_value:
        raise ValueError(f"{field_name} must be in range [{min_value}, {max_value}].")


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

    def __post_init__(self) -> None:
        _require_range(self.tier, "Champion tier", 1, 10)
        _require_range(self.level, "Champion level", 1, 3)
        _require_positive_int(self.max_hp, "Champion max_hp")
        _require_non_negative_int(self.strength, "Champion strength")
        _require_non_negative_int(self.intelligence, "Champion intelligence")
        _require_non_negative_int(self.attack_speed, "Champion attack_speed")
        _require_non_negative_int(self.move_speed, "Champion move_speed")
        _require_non_negative_int(self.mana_regen, "Champion mana_regen")
        _require_non_negative_int(self.threat, "Champion threat")
        _require_non_negative_int(self.armor, "Champion armor")
        _require_non_negative_int(self.resistance, "Champion resistance")
        _require_positive_int(self.attack_range, "Champion attack_range")
        _require_positive_int(self.ability_cost, "Champion ability_cost")

        self.traits = list(self.traits)
        if any(not isinstance(t, str) or not t for t in self.traits):
            raise ValueError("Champion traits must be non-empty strings.")
        if len(set(self.traits)) != len(self.traits):
            raise ValueError("Champion traits must be unique.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "affinity": self.affinity.value,
            "traits": list(self.traits),
            "role": self.role,
            "tier": self.tier,
            "level": self.level,
            "max_hp": self.max_hp,
            "strength": self.strength,
            "intelligence": self.intelligence,
            "attack_speed": self.attack_speed,
            "move_speed": self.move_speed,
            "mana_regen": self.mana_regen,
            "threat": self.threat,
            "armor": self.armor,
            "resistance": self.resistance,
            "attack_range": self.attack_range,
            "active_ability": self.active_ability,
            "passive_ability": self.passive_ability,
            "ability_cost": self.ability_cost,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Champion:
        return cls(
            id=payload["id"],
            name=payload["name"],
            affinity=_parse_enum(WeatherState, payload["affinity"], "affinity"),
            traits=list(payload.get("traits", [])),
            role=payload["role"],
            tier=payload["tier"],
            level=payload["level"],
            max_hp=payload["max_hp"],
            strength=payload["strength"],
            intelligence=payload["intelligence"],
            attack_speed=payload["attack_speed"],
            move_speed=payload["move_speed"],
            mana_regen=payload["mana_regen"],
            threat=payload["threat"],
            armor=payload["armor"],
            resistance=payload["resistance"],
            attack_range=payload["attack_range"],
            active_ability=payload["active_ability"],
            passive_ability=payload["passive_ability"],
            ability_cost=payload["ability_cost"],
        )


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

    def __post_init__(self) -> None:
        _require_range(self.tier, "Enemy tier", 1, 10)
        _require_range(self.level, "Enemy level", 1, 3)
        _require_positive_int(self.max_hp, "Enemy max_hp")
        _require_non_negative_int(self.strength, "Enemy strength")
        _require_non_negative_int(self.intelligence, "Enemy intelligence")
        _require_non_negative_int(self.attack_speed, "Enemy attack_speed")
        _require_non_negative_int(self.move_speed, "Enemy move_speed")
        _require_non_negative_int(self.mana_regen, "Enemy mana_regen")
        _require_non_negative_int(self.threat, "Enemy threat")
        _require_non_negative_int(self.armor, "Enemy armor")
        _require_non_negative_int(self.resistance, "Enemy resistance")
        _require_positive_int(self.attack_range, "Enemy attack_range")
        _require_positive_int(self.ability_cost, "Enemy ability_cost")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "affinity": self.affinity.value,
            "role": self.role,
            "tier": self.tier,
            "level": self.level,
            "max_hp": self.max_hp,
            "strength": self.strength,
            "intelligence": self.intelligence,
            "attack_speed": self.attack_speed,
            "move_speed": self.move_speed,
            "mana_regen": self.mana_regen,
            "threat": self.threat,
            "armor": self.armor,
            "resistance": self.resistance,
            "attack_range": self.attack_range,
            "active_ability": self.active_ability,
            "passive_ability": self.passive_ability,
            "ability_cost": self.ability_cost,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Enemy:
        return cls(
            id=payload["id"],
            name=payload["name"],
            affinity=_parse_enum(WeatherState, payload["affinity"], "affinity"),
            role=payload["role"],
            tier=payload["tier"],
            level=payload["level"],
            max_hp=payload["max_hp"],
            strength=payload["strength"],
            intelligence=payload["intelligence"],
            attack_speed=payload["attack_speed"],
            move_speed=payload["move_speed"],
            mana_regen=payload["mana_regen"],
            threat=payload["threat"],
            armor=payload["armor"],
            resistance=payload["resistance"],
            attack_range=payload["attack_range"],
            active_ability=payload["active_ability"],
            passive_ability=payload["passive_ability"],
            ability_cost=payload["ability_cost"],
        )


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

    def __post_init__(self) -> None:
        if self.index < 1:
            raise ValueError("Node index must be >= 1.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "index": self.index,
            "city": self.city,
            "weather": self.weather.value,
            "node_type": self.node_type.value,
            "state": self.state.value,
            "enemy_pool_id": self.enemy_pool_id,
            "reward_table_id": self.reward_table_id,
            "augment_pool_id": self.augment_pool_id,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Node:
        return cls(
            id=payload["id"],
            index=payload["index"],
            city=payload["city"],
            weather=_parse_enum(WeatherState, payload["weather"], "weather"),
            node_type=_parse_enum(NodeType, payload["node_type"], "node_type"),
            state=_parse_enum(NodeState, payload["state"], "state"),
            enemy_pool_id=payload.get("enemy_pool_id"),
            reward_table_id=payload.get("reward_table_id"),
            augment_pool_id=payload.get("augment_pool_id"),
        )


@dataclass(slots=True)
class CombatPieceState:
    piece_id: str
    is_enemy: bool
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
    alive: bool = True

    def __post_init__(self) -> None:
        _require_range(self.tier, "CombatPieceState tier", 1, 10)
        _require_range(self.level, "CombatPieceState level", 1, 3)
        _require_positive_int(self.max_hp, "CombatPieceState max_hp")
        _require_non_negative_int(self.hp, "CombatPieceState hp")
        _require_non_negative_int(self.strength, "CombatPieceState strength")
        _require_non_negative_int(self.intelligence, "CombatPieceState intelligence")
        _require_non_negative_int(self.attack_speed, "CombatPieceState attack_speed")
        _require_non_negative_int(self.move_speed, "CombatPieceState move_speed")
        _require_non_negative_int(self.mana_regen, "CombatPieceState mana_regen")
        _require_non_negative_int(self.threat, "CombatPieceState threat")
        _require_non_negative_int(self.armor, "CombatPieceState armor")
        _require_non_negative_int(self.resistance, "CombatPieceState resistance")
        _require_positive_int(self.attack_range, "CombatPieceState attack_range")
        _require_positive_int(self.ability_cost, "CombatPieceState ability_cost")
        _require_non_negative_int(self.mana, "CombatPieceState mana")
        _require_non_negative_int(self.action_energy, "CombatPieceState action_energy")
        _require_non_negative_int(self.movement_energy, "CombatPieceState movement_energy")
        _require_non_negative_int(
            self.speed_tiebreaker, "CombatPieceState speed_tiebreaker"
        )

        if self.hp > self.max_hp:
            self.hp = self.max_hp
        if self.mana > self.ability_cost:
            self.mana = self.ability_cost
        if self.hp == 0:
            self.alive = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "piece_id": self.piece_id,
            "is_enemy": self.is_enemy,
            "tier": self.tier,
            "level": self.level,
            "max_hp": self.max_hp,
            "hp": self.hp,
            "strength": self.strength,
            "intelligence": self.intelligence,
            "attack_speed": self.attack_speed,
            "move_speed": self.move_speed,
            "mana_regen": self.mana_regen,
            "threat": self.threat,
            "armor": self.armor,
            "resistance": self.resistance,
            "attack_range": self.attack_range,
            "ability_cost": self.ability_cost,
            "mana": self.mana,
            "action_energy": self.action_energy,
            "movement_energy": self.movement_energy,
            "position_q": self.position_q,
            "position_r": self.position_r,
            "target_piece_id": self.target_piece_id,
            "speed_tiebreaker": self.speed_tiebreaker,
            "alive": self.alive,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CombatPieceState:
        return cls(
            piece_id=payload["piece_id"],
            is_enemy=payload["is_enemy"],
            tier=payload["tier"],
            level=payload["level"],
            max_hp=payload["max_hp"],
            hp=payload["hp"],
            strength=payload["strength"],
            intelligence=payload["intelligence"],
            attack_speed=payload["attack_speed"],
            move_speed=payload["move_speed"],
            mana_regen=payload["mana_regen"],
            threat=payload["threat"],
            armor=payload["armor"],
            resistance=payload["resistance"],
            attack_range=payload["attack_range"],
            ability_cost=payload["ability_cost"],
            mana=payload.get("mana", 0),
            action_energy=payload.get("action_energy", 0),
            movement_energy=payload.get("movement_energy", 0),
            position_q=payload.get("position_q", 0),
            position_r=payload.get("position_r", 0),
            target_piece_id=payload.get("target_piece_id"),
            speed_tiebreaker=payload.get("speed_tiebreaker", 0),
            alive=payload.get("alive", True),
        )


@dataclass(slots=True)
class BattleEvent:
    tick: int
    actor_id: str
    target_id: str | None
    event_type: str
    amount: int = 0
    note: str = ""

    def __post_init__(self) -> None:
        if self.tick < 0:
            raise ValueError("BattleEvent tick must be >= 0.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "actor_id": self.actor_id,
            "target_id": self.target_id,
            "event_type": self.event_type,
            "amount": self.amount,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BattleEvent:
        return cls(
            tick=payload["tick"],
            actor_id=payload["actor_id"],
            target_id=payload.get("target_id"),
            event_type=payload["event_type"],
            amount=payload.get("amount", 0),
            note=payload.get("note", ""),
        )


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

    def __post_init__(self) -> None:
        if self.rounds < 0 or self.turns < 0 or self.duration_ticks < 0:
            raise ValueError(
                "BattleResult rounds, turns, and duration_ticks must be >= 0."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "weather": self.weather.value,
            "outcome": self.outcome.value,
            "rounds": self.rounds,
            "turns": self.turns,
            "duration_ticks": self.duration_ticks,
            "team_damage_dealt": self.team_damage_dealt,
            "team_damage_taken": self.team_damage_taken,
            "surviving_team_ids": self.surviving_team_ids,
            "surviving_enemy_ids": self.surviving_enemy_ids,
            "timed_out": self.timed_out,
            "events": [event.to_dict() for event in self.events],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BattleResult:
        return cls(
            node_id=payload["node_id"],
            weather=_parse_enum(WeatherState, payload["weather"], "weather"),
            outcome=_parse_enum(CombatOutcome, payload["outcome"], "outcome"),
            rounds=payload["rounds"],
            turns=payload["turns"],
            duration_ticks=payload.get("duration_ticks", 0),
            team_damage_dealt=dict(payload["team_damage_dealt"]),
            team_damage_taken=dict(payload["team_damage_taken"]),
            surviving_team_ids=list(payload["surviving_team_ids"]),
            surviving_enemy_ids=list(payload["surviving_enemy_ids"]),
            timed_out=payload.get("timed_out", False),
            events=[
                BattleEvent.from_dict(raw_event)
                for raw_event in payload.get("events", [])
            ],
        )


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

    def __post_init__(self) -> None:
        if self.schema_version < 1:
            raise ValueError("schema_version must be >= 1.")
        if not self.route:
            raise ValueError("Run route must contain at least one node.")
        if self.gold < 0:
            raise ValueError("Run gold must be >= 0.")

        roster_ids = [champion.id for champion in self.roster]
        if len(roster_ids) != len(set(roster_ids)):
            raise ValueError("Run roster champion ids must be unique.")

        bench_ids = [champion.id for champion in self.bench]
        if len(bench_ids) != len(set(bench_ids)):
            raise ValueError("Run bench champion ids must be unique.")

        route_indexes = {node.index for node in self.route}
        if len(route_indexes) != len(self.route):
            raise ValueError("Run route node indexes must be unique.")

        if self.status == RunStatus.IN_PROGRESS:
            if self.current_node_index not in route_indexes:
                raise ValueError(
                    "Run current_node_index must point to a valid route node index "
                    "while run is in progress."
                )

            current_nodes = [node for node in self.route if node.state == NodeState.CURRENT]
            if len(current_nodes) != 1:
                raise ValueError(
                    "Run in progress must have exactly one node with CURRENT state."
                )
            if current_nodes[0].index != self.current_node_index:
                raise ValueError(
                    "Run current_node_index must match the CURRENT route node index."
                )

    def current_node(self) -> Node | None:
        if self.status != RunStatus.IN_PROGRESS:
            return None

        for node in self.route:
            if node.index == self.current_node_index:
                return node
        return None

    def mark_current_node_cleared(self) -> None:
        node = self.current_node()
        if node is None:
            raise ValueError("No current node to clear.")
        if node.state == NodeState.CLEARED:
            return
        node.state = NodeState.CLEARED

    def advance_to_next_node(self) -> None:
        node = self.current_node()
        if node is None:
            raise ValueError("Cannot advance; there is no current node.")
        if node.state != NodeState.CLEARED:
            raise ValueError("Current node must be CLEARED before advancing.")

        next_node = None
        for candidate in self.route:
            if candidate.index > node.index and (
                next_node is None or candidate.index < next_node.index
            ):
                next_node = candidate

        if next_node is None:
            self.status = RunStatus.VICTORY
            return

        if next_node.state == NodeState.CLEARED:
            raise ValueError("Cannot advance into a node that is already CLEARED.")
        if next_node.state == NodeState.CURRENT:
            self.current_node_index = next_node.index
            return

        next_node.state = NodeState.CURRENT
        self.current_node_index = next_node.index

    def is_complete(self) -> bool:
        return self.status in {RunStatus.VICTORY, RunStatus.DEFEAT}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "seed": self.seed,
            "status": self.status.value,
            "gold": self.gold,
            "inventory": self.inventory,
            "current_node_index": self.current_node_index,
            "roster": [champion.to_dict() for champion in self.roster],
            "bench": [champion.to_dict() for champion in self.bench],
            "route": [node.to_dict() for node in self.route],
            "battle_log": [result.to_dict() for result in self.battle_log],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Run:
        return cls(
            run_id=payload["run_id"],
            schema_version=payload["schema_version"],
            seed=payload["seed"],
            status=_parse_enum(RunStatus, payload["status"], "status"),
            roster=[
                Champion.from_dict(raw_champion)
                for raw_champion in payload.get("roster", [])
            ],
            bench=[Champion.from_dict(raw_champion) for raw_champion in payload.get("bench", [])],
            route=[Node.from_dict(raw_node) for raw_node in payload["route"]],
            current_node_index=payload["current_node_index"],
            battle_log=[
                BattleResult.from_dict(raw_result)
                for raw_result in payload.get("battle_log", [])
            ],
            inventory=dict(payload.get("inventory", {})),
            gold=payload.get("gold", 0),
        )
