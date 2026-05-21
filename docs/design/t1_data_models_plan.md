# T1 Plan - Core Data Models (`src/game/models.py`)

## 1. Scope

This plan expands T1 to support current project decisions:

- Include node types beyond combat (`fight`, `reward`, `augment`, `boss_fight`).
- Include model structures required by the combat design proposal (piece/runtime combat state).
- Make models JSON-serialization ready now for future save/load work (T14).

Primary output of T1 is still one module:

- `src/game/models.py`

## 2. Deliverables

T1 will deliver the following model groups.

### 2.1 Enums

- `WeatherState`: `CLEAR`, `RAIN`, `STORM`, `HEAT`, `COLD`
- `NodeType`: `FIGHT`, `REWARD`, `AUGMENT`, `BOSS_FIGHT`
- `NodeState`: `UPCOMING`, `CURRENT`, `CLEARED`
- `RunStatus`: `IN_PROGRESS`, `VICTORY`, `DEFEAT`
- `CombatOutcome`: `WIN`, `LOSS`, `DRAW` (draw reserved for timeout/future rule)

### 2.2 Static Content Models

- `Champion`
- `Enemy`
- `Node`

These represent configuration/state that exists before combat simulation starts.

### 2.3 Runtime Combat Models

- `CombatPieceState`
- `BattleEvent`
- `BattleResult`

These represent what the combat engine (T3) consumes/produces.

### 2.4 Run-Level Models

- `Run`

Holds route progression, roster state, and battle history.

### 2.5 Serialization Utilities

- `to_dict()` and `from_dict()` per top-level model (`Node`, `Run`, `BattleResult` at minimum).
- Enum serialization as stable strings.
- Version stamp in run payload for migration safety.

## 3. Data Model Contract Summary

Detailed field-level contract is in:

- `docs/design/t1_model_contracts.md`

## 4. File-Level Work Breakdown

### Step 1: Enum Foundation

- Implement all enums listed in 2.1.
- Ensure enum values are lowercase wire-format strings (JSON-stable).

### Step 2: Static Models

- Implement `Champion`, `Enemy`, `Node` dataclasses.
- Add validation in `__post_init__` for key invariants (non-negative stats, valid ranges).

### Step 3: Runtime Combat Models

- Implement `CombatPieceState` as simulation carrier for tick/action data.
- Implement `BattleEvent` minimal event record for logs and summary charts.
- Implement `BattleResult` as pure combat output aggregate.

### Step 4: Run Model

- Implement `Run` with progression fields and history collections.
- Include helpers for current node access and completion checks.

### Step 5: Serialization

- Add deterministic `to_dict()`/`from_dict()` for all persisted models.
- Include `schema_version` at run root.

### Step 6: Unit Tests (T1 Slice)

Create `tests/game/test_models.py` with coverage for:

- Enum serialization/deserialization.
- Node/run invariants.
- Round-trip JSON model conversion.
- Basic helper methods (`current_node`, `is_complete`, etc.).

## 5. Acceptance Criteria

T1 is complete when all are true:

1. `src/game/models.py` defines all T1 models and enums from this plan.
2. Models can be serialized to JSON-safe dicts and loaded back without loss of semantic state.
3. Route node model supports non-combat nodes (`reward`, `augment`) while preserving fixed 7-node route invariant.
4. Combat runtime model surface is sufficient for T3 to implement tick/action simulation without redesigning core model shapes.
5. Tests exist and pass for model invariants and serialization round-trips.

## 6. Risks and Mitigations

- Risk: Over-modeling T1 may slow early delivery.
  - Mitigation: Keep runtime models minimal and focused on fields directly required by combat proposal.

- Risk: Future save format changes break old runs.
  - Mitigation: Add `schema_version` now and isolate parsing in `from_dict()`.

- Risk: Node feature scope drift between views and game logic.
  - Mitigation: Keep `NodeType` and `NodeState` centralized in `models.py` and used by both game and UI layers.

## 7. Out of Scope

- No combat calculations or turn resolution logic (T3).
- No weather modifier logic (T2).
- No file IO persistence implementation (T14).
- No UI rendering logic.
