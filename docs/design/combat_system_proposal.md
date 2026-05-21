# Combat System Proposal

## 1. Terminology

**Piece** — anything that occupies a tile and acts in combat (covers both player champions and enemies). Chess-aware terminology, fitting for a hex-grid tactical game. Used throughout this document.

## 2. Time Architecture

- **1 tick** = 10ms = 1/100 second. The smallest unit of simulation time.
- **1 round** = 600 ticks = 6 seconds. A UI/balancing convention used for stat presentation and queue markers — the engine itself does not process "turns" or "rounds," it processes ticks and resolves actions whenever they fire.
- **Combat length**: variable, ends when one team has no living pieces. (Timeout fallback TBD.)

## 3. Map

- Hexagonal grid.
- Each piece occupies exactly one tile.
- No two pieces may share a tile.
- Pieces cannot move through occupied tiles — they must path around.
- Range and pathfinding use hex distance. Pathfinding is A* over the hex graph (or BFS for uniform terrain).

## 4. Piece Composition

A piece is defined by its **identity** (tier, level), its **stats** (numerical attributes), and its **abilities** (one active, one passive).

### 4.1 Identity

| Property | Range | Description |
|----------|-------|-------------|
| **Tier** | 1–10 | Intrinsic to the piece type — fixed at creation, never changes. Determines rarity in the shop (higher tier = rarer) and base stat power. A Tier 5 piece is always Tier 5. |
| **Level** | 1–3 | Instance state. Three copies of the same piece at the same level combine into one copy at the next level. Level-3 is the cap. Scales stats and ability potency. |

**Combination rule:** three level-1 copies of the same piece → one level-2 copy. Three level-2s of the same piece → one level-3. (Standard auto-chess "star" mechanic.)

**Design intent for 10 tiers.** The unusually wide tier range (vs. TFT's 5) exists specifically to support frequent team rotation. Combined with the weather-conditions system (defined separately) that gives players reasons to swap pieces between rounds, and shop probabilities that shift toward higher tiers as the player levels up, the goal is a steady flow of viable swap candidates rather than players locking into a single comp early. Mid-tier level-2 pieces (e.g., Tier 5 level-2) should be reasonably achievable at mid-to-high player levels; only top-tier level-3s (Tier 8–10) should feel like rare-moment achievements.

### 4.2 Stats

| Stat | Purpose | Player-facing display |
|------|---------|----------------------|
| HP | Health pool | `1000 / 1000` |
| STR | Auto-attack damage scaling | Raw stat |
| INT | Ability damage scaling | Raw stat |
| **Attack Speed (AS)** | Attack/cast frequency | Raw + `1.5 actions/round, acts every 4.0s` |
| **Move Speed (MS)** | Hex-step frequency | Raw + `2.0 hex-steps/round` |
| **Mana Regen (MR)** | Mana gained per tick (drives cast throughput) | `1.0 mana/sec (0.01 mana/tick), 0.20 casts/action (1 cast per 5 actions)` |
| **Threat (THR)** | Auto-attack targeting priority when multiple enemies are valid | Raw stat (primarily modified by abilities/status effects; not items) |
| Armor | Physical mitigation | Raw + `% damage reduction` |
| Resistance (RES) | Magical mitigation | Raw + `% damage reduction` |
| Attack Range | Auto-attack range in hexes | `Melee` / `Range 2` / etc. |

> ⚠ **Naming collision flag:** the natural abbreviation for both Mana Regen and Magic Resist is "MR." This proposal renames magic resist to **Resistance (RES)** to avoid the clash. Recommended short forms: **MR** for Mana Regen, **RES** for Resistance.

Attack Speed governs the action meter (attacks and casts). Move Speed governs an independent movement meter (hex stepping). The two are decoupled so that a high-AS "machine gun" carry doesn't also gain assassin-tier mobility, and a high-MS assassin doesn't auto-attack like a hyper-carry.

Base stat values are determined by the piece's tier. Level multiplies those base values. The exact tier→stat mapping and level multipliers are TBD (see §9.9).

### 4.3 Abilities

Each piece has exactly two abilities, both intrinsic to the piece type:

- **Active ability** — triggered when mana reaches `ability_cost`. Casting spends the full cost. Damage scales with INT (and a small STR component, see §4.4). Per-piece unique; defines the piece's combat role. This is the "cast" referenced throughout §7.
- **Passive ability** — always in effect. May be a stat modifier, an on-trigger effect (on-hit, on-cast, on-damage-taken, on-kill, etc.), or a constant aura affecting nearby pieces or the whole team. No mana cost; no action consumed.

Both abilities scale with the piece's level. Whether scaling is automatic (a global level multiplier on damage and effect magnitude) or hand-tuned per ability is TBD (see §9.9).

### 4.4 Damage Formulas

Standard scaling for damage output:

- **Auto-attack damage** = `1.0 × STR + 0.2 × INT`
- **Ability damage** = `0.2 × STR + 4.2 × INT` (default; per-ability overrides allowed)

The asymmetric scaling encodes the "STR for autoers, INT for casters" identity while keeping the overall stat-point price of STR and INT roughly equal *for the median caster archetype* (1 cast per 5 attacks). Derivation: per 5-auto + 1-cast cycle, 50 STR contributes `5(50) + 1(50×0.2) = 260` and 50 INT contributes `5(50×0.2) + 1(50×4.2) = 260` — equal.

This parity only holds for the *median* auto:cast ratio. A pure autoer (1 cast per 20 attacks) gets disproportionately more from STR; a pure caster (1 cast per 3 attacks) gets disproportionately more from INT. This is desirable — it gives stat investment its own archetype-dependent value.

**Per-piece ability scaling.** Slow heavy nukers may use higher Y (e.g., `0.2 × STR + 8.0 × INT` with a higher mana cost), fast spammy debuffers lower Y (`0.2 × STR + 2.0 × INT` with low mana cost). The number `Y − X = 4` is the "average mage" balance point and a useful default for new pieces.

**Damage type and mitigation.** STR-scaled damage routes through **Armor**, INT-scaled damage routes through **Resistance**. So a heavily-armored target effectively reduces the STR contribution of any damage instance, while a high-Resistance target reduces the INT contribution. This means the "STR ≈ INT in price" equivalence only holds against an average target — comp-aware itemization is a real decision lever.

## 5. Frequency Curves

Both Attack Speed and Move Speed use the same asymptotic-diminishing-returns shape, with different asymptotes reflecting their different design intents.

### 5.1 Attack Speed

Asymptote at the mechanistic cap (1 action per tick = 600 actions/round). The cap is technically reachable, but only with extreme investment — supporting the "machine gun carry" fantasy without producing literal infinity.

**Formula:**
```
attacks_per_round = 600 × AS / (AS + 59_900)
```

| AS | Attacks/round | Time/attack |
|------|---------------|-------------|
| 0 | 0.00 | ∞ |
| 50 | 0.50 | 12.0s |
| 100 | 1.00 *(baseline)* | 6.0s |
| 500 | 4.97 | 1.21s |
| 1000 | 9.85 | 0.61s |
| 5000 | 46.2 | 0.13s |
| 10000 | 85.8 | 0.07s |
| 60000 | 300 | 0.02s |
| ∞ | 600 *(asymptote)* | 0.01s (= 1 tick) |

In practice, stats above ~5000 are extreme-late-game territory and require synergy stacks, not raw items. The asymptote prevents any mathematical edge case from producing more than one attack per tick, regardless of how many buffs stack.

### 5.2 Move Speed

Asymptote at 6 hex-steps/round (= 1 hex per second). Movement is bounded much tighter than attacks because positional play breaks at high mobility — even a 6/round move stat lets a piece cross the map in a few seconds.

**Formula:**
```
hex_steps_per_round = 6 × MS / (MS + 500)
```

| MS | Hex-steps/round | Time/step |
|------|-----------------|-----------|
| 0 | 0.00 | ∞ |
| 50 | 0.55 | 11.0s |
| 100 | 1.00 *(baseline)* | 6.0s |
| 250 | 2.00 | 3.0s |
| 500 | 3.00 | 2.0s |
| 1000 | 4.00 | 1.5s |
| 2000 | 4.80 | 1.25s |
| ∞ | 6.00 *(asymptote)* | 1.0s |

### 5.3 Integer math implementation

Both meters use the same accumulator pattern:

```
threshold              = 60_000
effective_AS           = (600 × AS) / (AS + 59_900) × 100     // attacks/round × 100
effective_MS           = (600 × MS) / (MS + 500)              // hex-steps/round × 100

each tick:
    action_energy     += effective_AS
    movement_energy   += effective_MS
    mana               = min(ability_cost, mana + effective_MR_tick)
    if action_energy   >= threshold: trigger action,   action_energy -= threshold
    if movement_energy >= threshold: trigger move step, movement_energy -= threshold
```

Two meters per piece (plus mana) tick concurrently. They are mathematically equivalent to two parallel priority queues but easier to project for the UI queue (§8).

## 6. Mana Regen (Tick-Based, Linear)

MR is defined as **mana regenerated per simulation tick** behind the scenes.

- Internal simulation unit: `effective_MR_tick` (mana/tick)
- UI display unit: `mana_per_second = effective_MR_tick × 100` (because 1 tick = 0.01s)

There is **no diminishing-returns curve on MR itself**. MR scales linearly until a mechanistic utility cap: once a piece can cast on every action, extra MR is wasted due to mana clamping.

### 6.1 Derived cast throughput

```
ticks_per_action       = threshold / effective_AS
mana_gained_per_action = effective_MR_tick × ticks_per_action
casts_per_action       = min(1, mana_gained_per_action / ability_cost)
actions_per_cast       = 1 / casts_per_action    // if casts_per_action > 0
```

Equivalent cap expression:

```
MR_needed_for_1_cast_per_action = ability_cost / ticks_per_action
                               = ability_cost × effective_AS / threshold
```

When `effective_MR_tick >= MR_needed_for_1_cast_per_action`, the piece is at the cap (`casts_per_action = 1.0`), and any further MR has no combat value unless some other mechanic raises mana demand.

### 6.2 Design implication

MR utility is piece-contextual, not globally curved:

- Low action frequency pieces hit the 1-cast-per-action cap at lower MR.
- High action frequency pieces require higher MR to cap.
- Ability mana cost shifts the cap linearly (higher cost needs proportionally higher MR).

Player-facing display should therefore include both:

- `mana/sec` (converted from per-tick MR)
- `casts/action` at current stats (plus implied `1 cast per N actions` when below cap)

## 7. Action Resolution

Three meters per piece tick concurrently every simulation tick: **action**, **movement**, and **mana**. Each has its own trigger condition and resolution logic.

### Per-tick simulation step

```
for each living piece:
    action_energy   += effective_AS
    movement_energy += effective_MS
    mana             = min(ability_cost, mana + effective_MR_tick)

collect all (piece, meter) pairs where that piece's meter >= threshold
sort by (effective_AS of piece DESC, tiebreaker)
for each triggered meter in order:
    resolve(piece, meter)
    meter_energy -= threshold                     // preserve overflow
```

Mana isn't a triggered meter — it's a state that the action meter checks at resolution time. Only **action** and **movement** trigger events.

### Action meter resolution (cast or attack)

1. **Cast** — if `mana >= ability_cost` and a valid target exists (per the ability's targeting rules) → cast the ability, `mana -= ability_cost`.
2. **Auto-attack** — else if at least one enemy is within `attack_range` → attack the designated target (see static Threat targeting rule below).
3. **Idle** — else, the piece cannot act this trigger. Action energy is **clamped at threshold** (held, not wasted). The piece will attack the instant they get in range, rewarding high AS during repositioning rather than punishing it.

### Target selection (static Threat)

Each piece maintains exactly one designated `target` reference at a time (or `None` if no valid enemy exists).

- Auto-attacks always resolve against this designated target.
- Targeted abilities also use this designated target by default.
- Non-targeted abilities (self-buff, ground AOE, global effects, etc.) may use their own ability-specific rules.
- If the designated target becomes invalid (dead, untargetable, out of allowed ability constraints), the piece reselects a target immediately using the deterministic rules below.

When multiple valid enemies are in auto-attack range, choose the target deterministically:

1. Highest current `Threat (THR)`.
2. If tied: nearest by hex distance.
3. If tied: lower current HP%.
4. If tied: lower absolute HP.
5. If tied: lower unique piece ID (stable deterministic fallback).

Scope choice for now: Threat is a static combat stat (with temporary ability/status modifiers allowed), not a dynamic "recent damage" meter. This keeps implementation simple, supports taunt-style mechanics, and preserves deterministic replays.

Retarget policy:

1. Keep current designated target while it remains valid.
2. If invalid, acquire a new designated target from current in-range valid enemies using the deterministic order below.
3. If no in-range enemies are valid, designated target becomes `None` until one becomes valid.

### Movement meter resolution (hex step)

1. **In attack range** of at least one enemy → do not move. Stay in position. Movement energy clamps at threshold (carries over).
2. **Out of attack range** → step 1 hex toward the nearest enemy via shortest path (A* over the hex graph). If pathfinding fails (totally walled in), do not move; movement energy clamps.

This decouples positional play from action speed. A high-AS piece does not gain mobility from their attack stat; a high-MS piece does not auto-attack faster from their movement stat.

### Concurrency

The action and movement meters tick independently. A high-AS-low-MS piece (Jinx archetype) attacks rapidly once in range but closes slowly. A low-AS-high-MS piece (assassin archetype) closes fast but doesn't attack any harder. A piece can have both meters trigger on the same tick — they resolve in defined order (movement, then action, so the piece can step into range and then immediately attack on the same tick if both fire).

### Tie-breaking

When multiple meters trigger on the same tick:

1. Higher `effective_AS` goes first (faster pieces act first when timing collides).
2. Higher raw AS goes first.
3. Unique Speed Hardcode — deterministic fallback - each piece has a unique hardcode speed ID for ultimate tie breaking

## 8. UI

### Prep Phase

Show **raw stat + derived effect** for every stat with a curve, so players can both do stat math and understand combat impact:

> **Attack Speed (AS)**: 500
> *4.97 attacks/round, attack every 1.21s*

> **Move Speed (MS)**: 250
> *2.00 hex-steps/round, step every 3.0s*

> **Mana Regen (MR)**: 1.0 mana/sec
> *1.0 mana/sec, 0.20 casts/action (1 cast per 5 actions) at current AS and ability cost*

If a piece is capped, show it explicitly:

> *1.00 casts/action (capped), extra MR is wasted until action rate or mana cost changes*

On hover, preview deltas: `+50 AS: 4.97 → 5.46 attacks/round`.

### Combat View

- **No action meters visible.** Players do not see energy bars filling. The action queue conveys this information instead.
- **Mana bars visible** per piece. Fills 0 → `ability_cost`, then resets on cast.
- **HP bars visible** per piece.
- **Action Queue** strip at the top of the screen:
  - Displays the next ~12 seconds of predicted actions, in time order, left to right.
  - Vertical markers at 6-second boundaries (round dividers).
  - As time advances, completed actions slide out the left; new predictions slide in from the right.
  - Each entry shows the acting piece's portrait/icon.

**Queue computation** — for each living piece, project the action meter forward:
```
ticks_until_next_action = (threshold - action_energy) / effective_AS
```
…then project subsequent actions at `+threshold/effective_AS` intervals. Merge and sort across all pieces, render the leading 12 seconds. Cheap enough to recompute every frame.

The queue can optionally also project movement steps (using `effective_MS`) if you want to show them as separate entries, but for readability I'd recommend showing only action events in the queue — movement is a positional concern, not a turn-order one, and clogging the queue with steps makes it harder to read.

Queue does not need to predict cast-vs-auto — that's resolved live when the action fires. The queue just shows *who* acts *when*.

## 9. Open Questions and Gaps

### 9.3 Combat behaviors
- **What happens if an ability has no valid target?** Fall through to auto-attack, or hold action energy and wait for a valid target? Proposal §7 assumes fall-through.
- **Movement when pathfinding fails** (totally walled in): proposal says hold movement energy. Confirm — alternative is to step toward a partial path or skip entirely.
- **Idle policy when action triggers but can't act** — proposal recommends clamping action energy at threshold (option A). Confirm this is the desired behavior; option B (reset to 0, "waste" tempo) is the alternative.

### 9.4 Status effects
- **Stun**: skip the action entirely? Pause energy gain? Pause mana regen? (All three is most intuitive.)
- **Silence**: block cast specifically. Mana regen continues? (Probably yes — silence vs stun should feel different.)
- **Disarm**: block auto-attack. What does a disarmed piece do if mana is low — skip, or fall through to move?
- **Root**: block movement only. Caster/attacker still functions.

### 9.5 Combat lifecycle
- **Starting energy**: 0, or some champion-specific value (à la TFT starting mana)?
- **Starting mana**: same question — per-champion starting mana is a powerful design lever.
- **Death**: piece removed from board immediately, tile freed up. Confirm.
- **Mana on damage taken**: currently *not* in the design. TFT uses this. Worth a deliberate decision — keep mana purely regen-driven, or add a damage-taken bonus?
- **Win condition**: last team standing. Timeout fallback: Sudden Death - all pieces take increasing damage on every tick (could be weather dependent).

### 9.6 Implementation determinism
- **Tiebreaker on simultaneous actions** — need a deterministic rule. Random breaks replays and feels unfair.
- **Floating point**: avoid entirely. All curves should produce integer outputs after rounding.

### 9.7 UI details
- **Queue updates during combat** — does it re-predict every frame, or only when something changes? Probably every frame, cheaply.
- **Animation pause** — does the simulation pause briefly during action animations, or do animations play asynchronously while the sim continues? Auto-chess convention is "animations play while sim continues" (TFT does this).
- **Cast-vs-auto preview in queue** — show predicted action type, or stay agnostic? Agnostic is simpler; preview is more readable but requires predicting future mana state.

### 9.8 Ability mechanics not yet specified
- **Cast time**: instantaneous (resolution on the tick of the action) vs. delayed. Proposal assumes instantaneous.
- **Ability range**: separate stat from auto-attack range? Most likely yes — needs to be on the per-piece ability config.
- **Resource model**: mana-only, or do some abilities have additional resources (charges, cooldown-on-mana, ultimate meter)?
- **Passive trigger framework**: need a unified event system (on-hit, on-cast, on-damage-taken, on-kill, on-ally-cast, etc.) so passives can hook in cleanly. Worth designing the event taxonomy before the first passive is written.

### 9.9 Tier and Level system

Design intent confirmed: 10 tiers + upward-shifting shop probabilities + weather conditions (separate system) together encourage frequent team rotation. Shop distribution mirrors TFT's level-up odds, just stretched over more tiers. Open specifics:

- **Tier → base stat formula**: how does tier translate to base stat values? Per-tier hand-tuned table, or formula scaling (e.g., `HP = base × tier^k`)? With 10 tiers, the per-step ramp must be smaller than TFT's 5-tier ramp to keep the top end manageable. Hand-tuning gives more control per tier but doesn't scale; a formula plus per-tier overrides is probably the right hybrid.
- **Level multiplier**: typical auto-chess uses 1.5–1.8× stat multiplier per level. Pick a value, or per-stat values (e.g., 1.8× HP, 1.5× damage, 1.0× ranges and AS/MS/MR since those are already curved).
- **Level affecting mana cost**: assumed *no* (level-up should never feel like a penalty). Confirm.
- **Active/passive ability scaling with level**: automatic global multiplier on damage and effect magnitude, or hand-tuned per ability? Auto-multiplier is easier to balance globally; hand-tuning unlocks "level-3 unique effects" like TFT does for some champions.
- **Shop probability tables**: per-tier, per-player-level distribution numbers TBD. Must be designed alongside the economy and player-level pacing.
- **Top-tier level-3 achievability**: 3-copies-to-upgrade × 3-upgrades = 9 base copies for a level-3. For Tier 10 pieces appearing only at high player levels with low shop probability, achieving level-3 may be effectively impossible in a normal game. Options: accept that Tier 10 level-3 is a "once a month" highlight, cap top tiers at level-2, or design alternative upgrade paths (e.g., one-of-a-kind items that level up a single piece). Worth a deliberate call.
- **Rotation friction (economy concern, flagged here):** 10 tiers + weather aren't sufficient on their own to drive rotation. If swapping a piece means losing the gold invested in it, players won't swap regardless of how many tiers exist. The economy needs explicit rotation-friendly mechanisms (partial refund on sell, transferable items, etc.) — this lives outside the combat proposal but won't work without it.

---

## Summary

The system is: hex-grid tactical combat driven by a per-tick integer accumulator, with three parallel meters per piece (action → attacks/casts, movement → hex stepping, mana → casting gate). Attack Speed and Move Speed use asymptotic curves with mechanistically meaningful caps; Mana Regen is linear per tick and only capped in utility by the "1 cast per action" limit plus mana clamping at ability cost. Move Speed and Attack Speed are decoupled — a high-AS carry doesn't gain assassin mobility, and a high-MS assassin doesn't out-DPS a hyper-carry. Player UI hides the action and movement accumulators (queue communicates instead) and exposes the mana bar. Action chain is cast → attack → idle; movement chain is step if out of range, else hold. STR scales auto-attacks and physical damage (mitigated by Armor); INT scales abilities and magic damage (mitigated by Resistance), with formulas tuned so that 50 STR ≈ 50 INT in total damage for the median caster archetype.

The structural decisions are settled. The gaps in §9 are mostly tunable values and behavioral edge cases that need explicit calls before implementation.
