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
    SUPPLY = "supply"
    CHALLENGE = "challenge"
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


def _require_unit_float(value: float, field_name: str) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{field_name} must be in range [0.0, 1.0].")


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
    # attack_speed is a FLOAT (T.29-pre, amends V.34): cadence reads
    # int(attack_speed); sub-integer sort order derives from round(attack_speed×1000).
    # The old separate int `milli_AS` field is gone — the float is the single source.
    attack_speed: float
    move_speed: int
    mana_regen: int
    threat: int
    armor: int
    resistance: int
    attack_range: int
    passive_ability: str
    # Multi-slot abilities (T.29d, V.49): one ActiveSlot per id. A one-element
    # list is the common single-ability case (byte-identical, V.2). Empty = no
    # active. `active_ability` (below) is a back-compat read of the first entry.
    active_abilities: list[str] = field(default_factory=list)
    traits: list[str] = field(default_factory=list)
    intent: str = "hybrid"
    role_code: str = ""
    crit_chance: float = 0.0
    penetration: int = 0
    penetration_pct: float = 0.0
    # Persistent equipped items — up to 3 item IDs (V.23, T.29a).
    items: list[str] = field(default_factory=list)

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
        _require_unit_float(self.crit_chance, "Champion crit_chance")
        _require_non_negative_int(self.penetration, "Champion penetration")
        _require_unit_float(self.penetration_pct, "Champion penetration_pct")

        self.active_abilities = list(self.active_abilities)
        if any(not isinstance(a, str) or not a for a in self.active_abilities):
            raise ValueError("Champion active_abilities must be non-empty strings.")
        if len(set(self.active_abilities)) != len(self.active_abilities):
            raise ValueError("Champion active_abilities must be unique.")

        self.traits = list(self.traits)
        if any(not isinstance(t, str) or not t for t in self.traits):
            raise ValueError("Champion traits must be non-empty strings.")
        if len(set(self.traits)) != len(self.traits):
            raise ValueError("Champion traits must be unique.")
        if self.intent not in ("damage", "hybrid", "utility"):
            raise ValueError(
                f"Champion intent must be one of damage/hybrid/utility, got {self.intent!r}."
            )

        self.items = list(self.items)
        if len(self.items) > 3:
            raise ValueError(f"Champion may equip at most 3 items, got {len(self.items)}.")
        if any(not isinstance(i, str) or not i for i in self.items):
            raise ValueError("Champion item IDs must be non-empty strings.")

    def stat(self, stat_name: str) -> float:
        """Base level-1 sheet value for ability-text rendering (T.34, V.38).

        Structural ``.stat()`` parity with ``Piece`` so ``ability_text.render``
        resolves scaling terms in roster context (no combat modifiers).
        Unknown key -> ``0.0``, mirroring ``_eval_scaling``'s silent-zero.
        """
        return float(getattr(self, stat_name, 0.0))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "affinity": self.affinity.value,
            "traits": list(self.traits),
            "role": self.role,
            "role_code": self.role_code,
            "intent": self.intent,
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
            "active_abilities": list(self.active_abilities),
            "passive_ability": self.passive_ability,
            "crit_chance": self.crit_chance,
            "penetration": self.penetration,
            "penetration_pct": self.penetration_pct,
            "items": list(self.items),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Champion:
        return cls(
            id=payload["id"],
            name=payload["name"],
            affinity=_parse_enum(WeatherState, payload["affinity"], "affinity"),
            traits=list(payload.get("traits", [])),
            role=payload["role"],
            role_code=payload.get("role_code", ""),
            intent=payload.get("intent", "hybrid"),
            tier=payload["tier"],
            level=payload["level"],
            max_hp=payload["max_hp"],
            strength=payload["strength"],
            intelligence=payload["intelligence"],
            attack_speed=float(payload["attack_speed"]),
            move_speed=payload["move_speed"],
            mana_regen=payload["mana_regen"],
            threat=payload["threat"],
            armor=payload["armor"],
            resistance=payload["resistance"],
            attack_range=payload["attack_range"],
            active_abilities=payload.get("active_abilities") or ([payload["active_ability"]] if payload.get("active_ability") else []),
            passive_ability=payload["passive_ability"],
            crit_chance=payload.get("crit_chance", 0.0),
            penetration=payload.get("penetration", 0),
            penetration_pct=payload.get("penetration_pct", 0.0),
            items=list(payload.get("items", [])),
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
    # attack_speed is a FLOAT (T.29-pre, amends V.34) — see Champion.attack_speed.
    attack_speed: float
    move_speed: int
    mana_regen: int
    threat: int
    armor: int
    resistance: int
    attack_range: int
    passive_ability: str
    # Multi-slot abilities (T.29d, V.49). Enemies may field >1 slot but never
    # light up Callings (V.22). `active_ability` property = first entry.
    active_abilities: list[str] = field(default_factory=list)
    intent: str = "hybrid"
    role_code: str = ""
    crit_chance: float = 0.0
    penetration: int = 0
    penetration_pct: float = 0.0

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
        _require_unit_float(self.crit_chance, "Enemy crit_chance")
        _require_non_negative_int(self.penetration, "Enemy penetration")
        _require_unit_float(self.penetration_pct, "Enemy penetration_pct")
        self.active_abilities = list(self.active_abilities)
        if any(not isinstance(a, str) or not a for a in self.active_abilities):
            raise ValueError("Enemy active_abilities must be non-empty strings.")
        if len(set(self.active_abilities)) != len(self.active_abilities):
            raise ValueError("Enemy active_abilities must be unique.")
        if self.intent not in ("damage", "hybrid", "utility"):
            raise ValueError(
                f"Enemy intent must be one of damage/hybrid/utility, got {self.intent!r}."
            )

    def stat(self, stat_name: str) -> float:
        """Base sheet value for ability-text rendering (T.34, V.38).

        Mirror of ``Champion.stat`` — structural ``.stat()`` parity with
        ``Piece`` so enemy roster tooltips resolve scaling terms. Unknown key
        -> ``0.0``.
        """
        return float(getattr(self, stat_name, 0.0))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "affinity": self.affinity.value,
            "role": self.role,
            "role_code": self.role_code,
            "intent": self.intent,
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
            "active_abilities": list(self.active_abilities),
            "passive_ability": self.passive_ability,
            "crit_chance": self.crit_chance,
            "penetration": self.penetration,
            "penetration_pct": self.penetration_pct,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Enemy:
        return cls(
            id=payload["id"],
            name=payload["name"],
            affinity=_parse_enum(WeatherState, payload["affinity"], "affinity"),
            role=payload["role"],
            role_code=payload.get("role_code", ""),
            intent=payload.get("intent", "hybrid"),
            tier=payload["tier"],
            level=payload["level"],
            max_hp=payload["max_hp"],
            strength=payload["strength"],
            intelligence=payload["intelligence"],
            attack_speed=float(payload["attack_speed"]),
            move_speed=payload["move_speed"],
            mana_regen=payload["mana_regen"],
            threat=payload["threat"],
            armor=payload["armor"],
            resistance=payload["resistance"],
            attack_range=payload["attack_range"],
            active_abilities=payload.get("active_abilities") or ([payload["active_ability"]] if payload.get("active_ability") else []),
            passive_ability=payload["passive_ability"],
            crit_chance=payload.get("crit_chance", 0.0),
            penetration=payload.get("penetration", 0),
            penetration_pct=payload.get("penetration_pct", 0.0),
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
class BattleEvent:
    tick: int
    actor_id: str
    target_id: str | None
    event_type: str
    amount: int = 0
    note: str = ""
    is_crit: bool = False
    # Mana telemetry (T.36b). On a cast: slot_idx = which slot fired, mana_spent =
    # cost deducted, mana_after = that slot's current mana after the spend. -1/0
    # defaults mark a non-mana event. Feeds the mana-bar UI + cadence checks.
    slot_idx: int = -1
    mana_spent: int = 0
    mana_after: int = 0
    # Post-event resource truth (T.37a) — on an HP-changing beat (attack/cast/
    # heal/dot) these carry the target's `hp`/`barrier_total` *after* the beat
    # applied, read from the engine's own piece (V.28-correct: `amount` is the
    # full pre-barrier figure for DPS accounting, `hp_after` is the real HP).
    # `hp_after = -1` marks a non-HP beat (move/status/spawn/despawn). The combat
    # view reconstructs HP/barrier bars from these without re-summing damage.
    hp_after: int = -1
    barrier_after: int = 0
    # Structured board coords (T.37c) — on a `move`/`spawn` beat these carry the
    # destination/spawn `(q, r)`, replacing the fragile `note=f"{q},{r}"` string
    # parse (B.28). `-1` marks a non-positional beat. The combat view reads
    # piece positions from the live replay (V.57); these let any stream consumer
    # get robust coords without string-splitting.
    dest_q: int = -1
    dest_r: int = -1
    # Cast attribution (T.12c) — on a `cast` activation marker or an `ability`
    # damage beat, this is the engine's `cast_id` for that cast, so the combat
    # view can join a recorded targeting `Footprint` (which carries the same
    # cast_id) to its ability for element colour. `-1` marks a non-cast beat.
    cast_id: int = -1

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
            "is_crit": self.is_crit,
            "slot_idx": self.slot_idx,
            "mana_spent": self.mana_spent,
            "mana_after": self.mana_after,
            "hp_after": self.hp_after,
            "barrier_after": self.barrier_after,
            "dest_q": self.dest_q,
            "dest_r": self.dest_r,
            "cast_id": self.cast_id,
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
            is_crit=payload.get("is_crit", False),
            slot_idx=payload.get("slot_idx", -1),
            mana_spent=payload.get("mana_spent", 0),
            mana_after=payload.get("mana_after", 0),
            hp_after=payload.get("hp_after", -1),
            barrier_after=payload.get("barrier_after", 0),
            dest_q=payload.get("dest_q", -1),
            dest_r=payload.get("dest_r", -1),
            cast_id=payload.get("cast_id", -1),
        )


@dataclass(slots=True)
class ManaProfile:
    """A piece's mana shape at combat start (T.37a) — lets a view fill mana bars.

    `slots` is one `(mana_cost, max_mana, priority, start_mana)` tuple per
    `ActiveSlot`; `mana_regen` is the piece-level charge rate (V.48). Pieces with
    no active slots have `mana = None` on their snapshot (no mana bar).
    """
    mana_regen: int
    slots: list[tuple[int, int, int, int]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"mana_regen": self.mana_regen, "slots": [list(s) for s in self.slots]}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ManaProfile:
        return cls(
            mana_regen=payload["mana_regen"],
            slots=[tuple(s) for s in payload.get("slots", [])],
        )


@dataclass(slots=True)
class PieceSnapshot:
    """Identity + spawn-time board state of one combat piece (T.37a).

    Captured in `BattleResultRecorder` so a combat view can lay out the board
    without re-deriving formation. Start-of-combat pieces have `spawn_tick = 0`;
    mid-combat summons are appended with their spawn tick + spawn position (the
    `spawn`/`despawn` events drive their board entry/exit). `affinity`/`is_enemy`/
    `max_hp` are immutable identity; live HP/stats come from replay (T.37b).
    """
    id: str
    is_enemy: bool
    affinity: WeatherState
    q: int
    r: int
    max_hp: int
    mana: ManaProfile | None = None
    summon: bool = False
    spawn_tick: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "is_enemy": self.is_enemy,
            "affinity": self.affinity.value,
            "q": self.q,
            "r": self.r,
            "max_hp": self.max_hp,
            "mana": self.mana.to_dict() if self.mana is not None else None,
            "summon": self.summon,
            "spawn_tick": self.spawn_tick,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> PieceSnapshot:
        mana = payload.get("mana")
        return cls(
            id=payload["id"],
            is_enemy=payload["is_enemy"],
            affinity=_parse_enum(WeatherState, payload["affinity"], "affinity"),
            q=payload["q"],
            r=payload["r"],
            max_hp=payload["max_hp"],
            mana=ManaProfile.from_dict(mana) if mana is not None else None,
            summon=payload.get("summon", False),
            spawn_tick=payload.get("spawn_tick", 0),
        )


@dataclass(slots=True)
class Footprint:
    """A targeting helper's recorded geometry during a cast (T.12c, V.61).

    Observer-only telemetry for the combat view: `kind` is "circle" (radius AoE)
    or "line" (beam), `(center_q, center_r)` the origin, geometry is `radius`
    (circle) or `direction` + `length` (line). `tick`/`cast_id` join it to the
    cast's beats. Capture never affects combat math — the helper returns its
    target list unchanged and no subscriber exists on the sim path (byte-identical,
    V.2/V.14). Empty list for results from pre-T.12c saves.
    """
    tick: int
    cast_id: int
    kind: str
    center_q: int
    center_r: int
    radius: int = 0
    direction: tuple[int, int] = (0, 0)
    length: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "cast_id": self.cast_id,
            "kind": self.kind,
            "center_q": self.center_q,
            "center_r": self.center_r,
            "radius": self.radius,
            "direction": list(self.direction),
            "length": self.length,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Footprint:
        d = payload.get("direction", (0, 0))
        return cls(
            tick=payload["tick"],
            cast_id=payload["cast_id"],
            kind=payload["kind"],
            center_q=payload["center_q"],
            center_r=payload["center_r"],
            radius=payload.get("radius", 0),
            direction=tuple(d),
            length=payload.get("length", 0),
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
    # Weather- and passive-applied max HP per piece id, captured from the
    # engine's own pieces (the single source of truth). Consumed by the combat
    # log's HP trace; empty for results deserialized from pre-field saves.
    piece_max_hp: dict[str, int] = field(default_factory=dict)
    # Cleared player-team trait breakpoints (T.28a): (trait_id, unique-carrier
    # count, cleared threshold). Surfaced from compile_loadout; empty for
    # enemy-only or pre-field results.
    trait_activations: list[tuple[str, int, int]] = field(default_factory=list)
    # Combat-view board layout (T.37a): identity + spawn-time positions of every
    # piece (start pieces `spawn_tick=0`; summons appended at their spawn tick) +
    # the board dimensions, so a view renders the board without re-deriving
    # formation. Empty/0 for results deserialized from pre-T.37 saves.
    initial_pieces: list[PieceSnapshot] = field(default_factory=list)
    board_width: int = 0
    board_height: int = 0
    # Recorded per-cast targeting footprints (T.12c, V.61) — observer-only
    # geometry the combat view animates as per-ability shapes (circle/line).
    # Empty for results from pre-T.12c saves.
    footprints: list[Footprint] = field(default_factory=list)

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
            "piece_max_hp": dict(self.piece_max_hp),
            "trait_activations": [list(t) for t in self.trait_activations],
            "initial_pieces": [p.to_dict() for p in self.initial_pieces],
            "board_width": self.board_width,
            "board_height": self.board_height,
            "footprints": [f.to_dict() for f in self.footprints],
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
            piece_max_hp=dict(payload.get("piece_max_hp", {})),
            trait_activations=[
                (str(t[0]), int(t[1]), int(t[2]))
                for t in payload.get("trait_activations", [])
            ],
            initial_pieces=[
                PieceSnapshot.from_dict(raw)
                for raw in payload.get("initial_pieces", [])
            ],
            board_width=payload.get("board_width", 0),
            board_height=payload.get("board_height", 0),
            footprints=[
                Footprint.from_dict(raw)
                for raw in payload.get("footprints", [])
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
    amber: int = 0
    # Team-size cap progression (T.22). tempest_rank == deployable field cap.
    # tempest is progress toward the *next* rank-up; both monotonic non-decreasing.
    tempest: int = 0
    tempest_rank: int = 1
    # Champion shop economy (T.22). champion_copies maps a champion id to the
    # total base copies bought; the materialized level is derived (3 copies → L2,
    # 9 copies → L3). shop_offers holds the 5 current slots (None = bought/empty).
    champion_copies: dict[str, int] = field(default_factory=dict)
    shop_offers: list[str | None] = field(default_factory=list)
    shop_rerolls: int = 0
    # Augment system (T.31). active_augments holds picked augment ids in run order;
    # augment_state carries quest progress + RUN-scope flags (e.g. trait_bonus,
    # uprising_wins). Combat reads both via RunModifiers (V.18). Registry
    # resolution of every id is CI-guarded (V.17), not validated here (mirrors V.15).
    active_augments: list[str] = field(default_factory=list)
    augment_state: dict[str, Any] = field(default_factory=dict)
    content_version: str = "1.0.0"
    difficulty_coefficient: float = 1.0

    def __post_init__(self) -> None:
        if self.schema_version < 1:
            raise ValueError("schema_version must be >= 1.")
        if not self.route:
            raise ValueError("Run route must contain at least one node.")
        if self.amber < 0:
            raise ValueError("Run amber must be >= 0.")
        if self.tempest < 0:
            raise ValueError("Run tempest must be >= 0.")
        _require_range(self.tempest_rank, "Run tempest_rank", 1, 10)
        if self.shop_rerolls < 0:
            raise ValueError("Run shop_rerolls must be >= 0.")
        if any(copies < 1 for copies in self.champion_copies.values()):
            raise ValueError("Run champion_copies values must be >= 1.")

        # Augment shape validation only (T.31) — registry resolution is CI-guarded
        # (V.17), not here, to avoid an import cycle (mirrors V.15 for abilities).
        self.active_augments = list(self.active_augments)
        if any(not isinstance(a, str) or not a for a in self.active_augments):
            raise ValueError("Run active_augments must be non-empty strings.")
        if len(set(self.active_augments)) != len(self.active_augments):
            raise ValueError("Run active_augments must be unique.")
        if not isinstance(self.augment_state, dict):
            raise ValueError("Run augment_state must be a dict.")

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
            "amber": self.amber,
            "tempest": self.tempest,
            "tempest_rank": self.tempest_rank,
            "champion_copies": dict(self.champion_copies),
            "shop_offers": list(self.shop_offers),
            "shop_rerolls": self.shop_rerolls,
            "active_augments": list(self.active_augments),
            "augment_state": self.augment_state,
            "inventory": self.inventory,
            "current_node_index": self.current_node_index,
            "roster": [champion.to_dict() for champion in self.roster],
            "bench": [champion.to_dict() for champion in self.bench],
            "route": [node.to_dict() for node in self.route],
            "battle_log": [result.to_dict() for result in self.battle_log],
            "content_version": self.content_version,
            "difficulty_coefficient": self.difficulty_coefficient,
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
            # Accept the legacy "gold" key on read for back-compat (SPEC B.4).
            amber=payload.get("amber", payload.get("gold", 0)),
            tempest=payload.get("tempest", 0),
            tempest_rank=payload.get("tempest_rank", 1),
            champion_copies=dict(payload.get("champion_copies", {})),
            shop_offers=list(payload.get("shop_offers", [])),
            shop_rerolls=payload.get("shop_rerolls", 0),
            active_augments=list(payload.get("active_augments", [])),
            augment_state=dict(payload.get("augment_state", {})),
            content_version=payload.get("content_version", "1.0.0"),
            difficulty_coefficient=payload.get("difficulty_coefficient", 1.0),
        )
