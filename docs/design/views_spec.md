# Tempest Fauna Trail - View Specification

## 1. Purpose

Define the four core game views and how the player moves between them:

1. Main Menu
2. Trail View
3. Prep View
4. Combat View

This spec aligns with:

- `SPEC.md` (fixed city route, weather-driven combat, Flet route stack)
- `docs/design/combat_system_proposal.md` (prep/combat UI expectations)

## 2. Core UX Flow

Primary loop:

`Main Menu -> Trail -> Prep -> Combat -> Trail -> ... -> End of Run`

View transitions:

- New game from Main Menu creates a new `Run` and opens Trail at node 1.
- Trail "Play Next Encounter" opens Prep for the current unresolved node.
- Prep "Start Combat" locks setup and opens Combat.
- Combat result resolves node and returns to Trail.
- If final node is cleared, show end-of-run outcome state (handled outside this doc).

## 3. Shared UI Rules

- Use one route handler per view and update via Flet `page.views` stack.
- Keep style tokens in `ui/theme.py`; avoid hardcoded colors and spacing.
- Show current node weather and forecasted node weather whenever available.
- Never block UI for weather fetch; show loading/fallback state.
- Default weather fallback remains `Clear` if API/cache fails.
- Desktop-first layout with mobile-safe wrapping/stacking.

## 4. Main Menu View

### 4.1 Goal

Entry point to start, continue, or exit game session.

### 4.2 Route

- `/`

### 4.3 Required Content

- Game title + subtitle (short fantasy/weather pitch).
- Primary actions:
	- `New Run`
	- `Continue` (enabled only if save exists)
	- `Quit`
- Optional secondary actions:
	- `Settings` (if implemented later)
	- `Credits`

### 4.4 Interactions

- `New Run`: initialize run state, roster seed, starting resources, route progress.
- `Continue`: load persisted run.
- `Quit`: close app.

### 4.5 States

- Continue disabled: no save file found.
- Continue enabled: valid save found.
- Error banner: save exists but failed to load.

## 5. Trail View

### 5.1 Goal

Show route progression, current position, future nodes, and high-level team readiness before entering next encounter.

### 5.2 Route

- `/trail` (or `/map` if route naming stays legacy; use one canonical route in implementation)

### 5.3 Required Content

- Route strip or map with all nodes in fixed order (6 + boss, per SPEC).
- For each node:
	- Node index (e.g., `3/7`)
	- City name
	- Stage type/icon (`normal`, `elite`, `boss`)
	- Weather icon/state
	- Resolution state (`cleared`, `current`, `upcoming`)
- Current node focus panel:
	- Enemy theme preview (high level)
	- Weather impact summary — how the node weather buffs/debuffs each affinity (System A); affinity matchup vs the previewed enemies (System B) where enemy affinities are known
	- Rewards preview (if known)
- Team summary panel:
	- Champions (portrait/name/role)
	- HP status (carry-over if persistent between battles)
	- Core resources (gold, consumables, bench slots if applicable)

### 5.4 Primary Actions

- `Play Next Encounter` (enabled only for unresolved current node)
- `Inspect Team`
- `Save and Exit`

### 5.5 Secondary Interactions

- Hover/select a future node to inspect weather and node type.
- Click current node to open detailed node card.

### 5.6 States

- Loading weather for one/more nodes.
- Partial weather data (mix of live + cached).
- All weather fallback (`Clear`) when API unavailable.
- Final node cleared state (transition to run-end summary flow).

## 6. Prep View

### 6.1 Goal

Pre-combat planning layer where player positions team, reviews enemies, and spends resources before locking the encounter.

### 6.2 Route

- `/prep`

### 6.3 Required Layout Zones

- Top bar: node info, weather state/icon, resource counts, back button.
- Center board: hex grid deployment map.
- Left (or collapsible) panel: player roster (board + bench).
- Right (or collapsible) panel: enemy preview + shop/items.
- Bottom action row: `Auto Place`, `Reset Placement`, `Start Combat`.

### 6.4 Required Features

#### Team Placement

- Drag/drop or tap-select placement onto valid allied deployment tiles.
- Enforce one piece per tile and legal deployment zone.
- Allow bench <-> board movement before combat lock.
- Visual feedback for selected piece, occupied tile, invalid placement.

#### Enemy Preview

- Show enemy piece list with at least:
	- Name/type
	- Estimated role/threat indicator
	- Affinity matchup hint — the System-B predator/prey relation of each enemy vs the player's affinities
- Show uncertainty marker if preview is intentionally incomplete.

#### Economy and Loadout

- Item inventory and usable consumables.
- Shop panel for purchasable pieces/upgrades (if active in this phase).
- Gold cost and affordability indicators.
- Buy/sell/merge feedback for level-up combinations (3 -> 1 upgrade rule if implemented now).

#### Stat Readability

Per combat proposal, each piece tooltip/card should show:

- Raw stat values (HP, STR, INT, AS, MS, MR, THR, Armor, RES)
- Derived rates for AS/MS/MR when selected or hovered
- Clear capped-state messaging for MR when applicable

### 6.5 Primary Actions

- `Start Combat`:
	- Validates minimum team requirements.
	- Locks formation/economy changes.
	- Creates combat snapshot and routes to Combat view.
- `Back to Trail`:
	- Allowed only if no irreversible purchases/actions were committed, or with confirmation.

### 6.6 States

- Invalid board state (not enough deployed units, illegal tile occupancy).
- Insufficient gold for selected purchase.
- API/weather stale warning (non-blocking).

## 7. Combat View

### 7.1 Goal

Present readable live/auto-resolved battle with enough tactical telemetry to understand why outcomes happen.

### 7.2 Route

- `/combat`

### 7.3 Required Layout Zones

- Top: action queue timeline (next ~12 seconds projection).
- Center: hex battlefield with piece sprites and combat effects.
- Side panel: selected unit details + combat log feed.
- Bottom controls: speed, pause (optional), skip/fast-resolve (optional).

### 7.4 Required Combat Telemetry

- Piece HP bars visible.
- Piece mana bars visible (fill to ability cost, reset on cast).
- No action-energy bars shown (per proposal).
- Visual cast/attack events and damage/heal numbers.
- Defeat indicators and removal from board.

### 7.5 Action Queue Requirements

- Show projected actor order based on action meter timing.
- Left-to-right chronological ordering.
- Round markers every 6 seconds.
- Continuous scrolling as events resolve.
- Queue entries show acting piece icon/portrait.

### 7.6 Combat End

- Detect victory/defeat when one team has no living pieces.
- Show compact result panel:
	- Outcome
	- Survivors
	- Key stats (damage dealt/taken summary)
- `Continue` returns to Trail and commits node resolution.

### 7.7 States

- Live simulation mode.
- Fast-forward mode.
- Post-combat result mode (interaction locked except continue/details).

## 8. Data Contracts (View-Level)

Each view should receive a minimal, explicit view model from controller/app state.

- Main Menu:
	- `has_save: bool`
	- `last_run_meta: optional`
- Trail:
	- `route_nodes: list[NodeViewModel]`
	- `current_node_index: int`
	- `team_summary: TeamSummaryViewModel`
	- `resources: ResourceViewModel`
- Prep:
	- `board_state: BoardViewModel`
	- `bench_state: BenchViewModel`
	- `enemy_preview: EnemyPreviewViewModel`
	- `shop_state: ShopViewModel`
	- `weather_context: WeatherViewModel`
- Combat:
	- `combat_snapshot: CombatStartViewModel`
	- `live_combat_state: CombatRuntimeViewModel`
	- `action_queue_projection: list[QueueEventViewModel]`

Exact typing/naming can evolve, but this separation should be preserved.

## 9. Non-Functional Requirements

- View transitions should feel immediate (<200ms perceived delay).
- Combat rendering should remain readable at normal speed and 2x speed.
- Controls must remain usable at 1280x720 and scale down for smaller laptop widths.
- Keyboard fallback for key actions (`Enter` start/continue, `Esc` back where safe).

## 10. MVP Scope Cut (If Needed)

If timeline pressure occurs, keep this order:

1. Main Menu basic actions
2. Trail with node progression + Play Next Encounter
3. Prep with placement + Start Combat (no shop)
4. Combat with HP/mana + log + win/loss
5. Add queue projection, then shop/economy depth

This preserves core game loop while allowing iterative depth.

## 11. Node Design Specification

### 11.1 Node Types (Principal)

Route nodes are explicitly typed and drive both gameplay and UI behavior.

- `fight`: standard combat encounter
- `reward`: non-combat loot/economy node
- `augment`: non-combat power-choice node
- `boss_fight`: major combat encounter with stronger rewards and run-gate behavior

All node cards in Trail must expose these fields at minimum:

- `node_id`
- `node_index`
- `node_type`
- `city_name`
- `weather_state`
- `state` (`upcoming`, `current`, `cleared`)

### 11.2 Route Composition Rules

For current fixed-route scope (7 total nodes), recommended composition:

- 1 `boss_fight` as final node (index 7)
- 3-4 `fight` nodes
- 1-2 `reward` nodes
- 1 `augment` node

Example sequence:

1. `fight`
2. `reward`
3. `fight`
4. `augment`
5. `fight`
6. `reward` or `fight`
7. `boss_fight`

Composition can be adjusted later, but `boss_fight` remains final and unique.

### 11.3 Per-Node UX and Flow

#### Fight Node

- Trail CTA: `Play Encounter`
- Transition: `Trail -> Prep -> Combat -> Trail`
- Prep enabled features: placement, enemy preview, item usage, optional shop
- Success result: mark node cleared, grant base fight rewards
- Failure result: run defeat handling (or retry policy if added later)

#### Reward Node

- Trail CTA: `Claim Reward`
- Transition: `Trail -> Reward Resolve (modal or dedicated panel) -> Trail`
- No Prep/Combat stage
- Reward choices should be 1-of-N (recommended 3 options), examples:
	- Gold bundle
	- Consumable item
	- Temporary buff for next fight
	- Unit heal/restore action
- On claim, node resolves immediately and cannot be revisited

#### Augment Node

- Trail CTA: `Choose Augment`
- Transition: `Trail -> Augment Resolve (modal or dedicated panel) -> Trail`
- No Prep/Combat stage
- Present 2-3 augment choices with clear tradeoffs
- Augments should be run-persistent unless explicitly labeled temporary
- Each augment card should show:
	- Name
	- Effect text
	- Scope (`team`, `economy`, `weather`, `combat timing`)
	- Rarity tier (if applicable)
- On selection, persist augment to run state and resolve node

#### Boss Fight Node

- Trail CTA: `Face Boss`
- Transition: `Trail -> Prep -> Combat -> Trail/Run End`
- Uses boss-specific enemy composition and encounter modifiers
- Prep may include extra warning banner with boss mechanics/weather pressure
- Victory: resolves run as complete and grants final rewards/summary access
- Defeat: resolves run as failed

### 11.4 Node Visual Language (Trail)

Each node type must be recognizable at a glance by icon + frame shape + color family.

- `fight`: crossed-claw/sword icon, standard frame
- `reward`: chest/coin icon, bright frame
- `augment`: star/glyph icon, arcane frame
- `boss_fight`: crown/skull icon, heavy frame + larger size

Weather badge overlays node icon (top-right) and remains visible for all types.

Recommended status overlays:

- Cleared: checkmark + muted opacity
- Current: pulsing ring
- Upcoming: neutral tone

### 11.5 Reward Budget and Scaling

Node type controls baseline economy output.

- `fight`:
	- Moderate gold
	- Chance-based item/material
- `reward`:
	- Highest immediate economy burst per node
	- No combat risk
- `augment`:
	- Low immediate economy
	- High long-term power value
- `boss_fight`:
	- Highest total payout
	- Unlocks run-completion summary rewards

Scaling guideline by progression:

- Nodes 1-2: low-medium value, onboarding-focused
- Nodes 3-5: medium-high value, build-defining
- Node 7 boss: peak value

### 11.6 Integration With Existing Views

- Trail is the primary node interaction surface.
- Prep is entered only for combat-class nodes (`fight`, `boss_fight`).
- Combat is entered only for combat-class nodes.
- Reward/Augment resolve in a non-combat flow from Trail and return directly to Trail.

This implies Trail action button labeling is node-type dependent.

### 11.7 Suggested Data Model Additions

To support the above cleanly, add/extend these model concepts:

- `NodeType` enum:
	- `FIGHT`
	- `REWARD`
	- `AUGMENT`
	- `BOSS_FIGHT`
- `NodeState` enum:
	- `UPCOMING`
	- `CURRENT`
	- `CLEARED`
- `Node` fields:
	- `type: NodeType`
	- `city: str`
	- `weather: WeatherState`
	- `reward_table_id: str | None`
	- `augment_pool_id: str | None`
	- `enemy_pool_id: str | None`

Resolution handler split:

- `resolve_combat_node(...)`
- `resolve_reward_node(...)`
- `resolve_augment_node(...)`

### 11.8 MVP Node Scope

For first playable version:

1. Implement `fight` and `boss_fight` fully with current Prep/Combat flow.
2. Implement `reward` as simple 1-of-3 economy choice.
3. Implement `augment` with a small static pool of 6-8 augments.
4. Defer rarity tiers, reroll mechanics, and advanced augment synergies.

This keeps node variety meaningful while staying realistic for milestone delivery.
