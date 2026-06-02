# Underpowered Pieces & Weather System Balance Report

*Based on mega3/mega4 simulation data (2026-06-02). Companion to [`mega_sim/mega3_analysis_report.md`](mega_sim/mega3_analysis_report.md).*

---

## 0. Context

The mega3/mega4 simulation (294,840 battles, 120 pieces, 6 weathers, abilities firing) identifies **mage as the one broken role** (0.33 win rate, −0.20 within-tier deficit vs non-mages) and **hybrid as mildly under-delivering** (corrected `wr_delta` = −0.082). This report covers:

1. Individual stat blocks and kit descriptions for each confirmed underpowered piece
2. Suggested active/passive powerups per piece
3. Alternative `stat_overrides` modifications (the engine's per-piece post-generation tuning lever, capped at ±15% budget — see `src/game/content.py:218–226`)
4. Weather system coverage in the simulation

---

## 1. Weather System Coverage in Simulation

The engine implements **two decoupled weather systems** (`src/game/weather_effects.py`):

| System | Name | Mechanism | Sim Coverage |
|--------|------|-----------|--------------|
| **A** | **Weather Favor** | Node weather applies multiplicative stat buffs/debuffs at combat init based on piece affinity vs active weather (±10% strong tier, scaled down for medium/weak) | ✅ Fully measured in mega2/3/4 — own-weather advantage = **+0.011 win rate** (nearly inert) |
| **B** | **Affinity Clash** | Per-hit damage multiplier based on attacker affinity vs defender affinity (1.20× primary predator → 0.80× primary prey) | ⚠️ **Implicitly included** (the combat engine resolves it every hit via `damage_modifier()`), but **not independently measured or isolated** in the simulation reports |

### Verdict on Weather

Both systems fire during simulation battles, but the combined effect is negligible (+0.011 win rate for own-weather). The mega3 report §8 notes outcomes are "weather-invariant to 4 decimals" for top/bottom pieces. The simulation **does not separately report System B (Affinity Clash) impact** — it is entangled with System A in the aggregate weather metric. A dedicated A/B isolation sweep (disable one system at a time) is needed to attribute the ±1pp between the two.

**Root cause of weakness:** System A's buff magnitude (±10% at strong tier, ±6%/±3% at medium/weak) is too small relative to the power-ratio cliff. System B's ±20% damage mult is more impactful per-hit but since the same affinity matchup applies symmetrically across all hits, it shifts DPS linearly without creating the variance needed to soften the deterministic cliff.

---

## 2. Underpowered Pieces — Stat Blocks & Recommendations

### Priority ranking (by corrected `wr_delta` deficit)

| # | Piece | Tier | Role | Affinity | Faction | `wr_delta` (corrected) |
|---|-------|------|------|----------|---------|------------------------|
| 1 | Hierarch | 8 | mage | clear | enemy | **−0.379** |
| 2 | Marsh Thrush | 6 | mage | rain | champion | **−0.264** |
| 3 | Company Captain | 5 | mage | clear | enemy | **−0.209** |
| 4 | Storm Eagle | 9 | mage | thunder | champion | **−0.158** |
| 5 | Glade Heron | 8 | mage | rain | champion | **−0.128** |
| 6 | Arcanist | 9 | mage | clear | enemy | **−0.111** |

*Will-o-Fawn (T2 mist mage, 0.05 win rate) was originally flagged but mega4's corrected model shows `wr_delta` ≈ −0.07 — on-target for its T2 power. It is low because it is low-tier, not because it is mis-tuned. Included below for completeness but is NOT a priority buff target.*

---

### 2.1 Hierarch (T8, Enemy, Clear Mage) — `wr_delta = −0.379`

**The single most under-tuned piece in the roster.**

#### Stat Block

| Stat | Value | Notes |
|------|-------|-------|
| HP | 1,212 | standard durability × ranged × T8 scaling |
| Strength | 22 | INT-primary (0.2× base) |
| Intelligence | 202 | INT-primary (1.8× base) |
| Armor | 45 | ranged (0.8×) |
| Resistance | 45 | ranged (0.8×) |
| Attack Speed | 68 | ability playstyle (0.75×) |
| Mana Regen | 15 | ability playstyle (1.5×) |
| Move Speed | 90 | — |
| Attack Range | 3 | ranged |
| Ability Cost | 36,000 | standard |
| Power | 5.040 | — |

#### Current Kit

- **Active — Divine Shield:** Grants all allies +40 armor and +20 resistance for 500 ticks. *Pure support, zero damage contribution.*
- **Passive:** Empty (`EffectBundle()`). *No passive at all.*

#### Diagnosis

A T8 mage with zero personal damage output from abilities and no passive. Its only contribution is team buffing, but the stat block is offensive (INT-primary, low HP/armor) so it dies before meaningfully buffing. Massive design mismatch between stat profile and kit purpose.

#### Suggested Powerups

**Active rework — "Smite & Shield":** Deal INT damage (base=70, scaling=intelligence×1.8) to primary target, THEN grant all allies +25 armor and +15 resistance for 400 ticks. Combines damage with support utility.

**Passive — "Holy Fervor":** On each cast, Hierarch gains +15% attack speed for 600 ticks (stacking up to 3×). Gives sustained DPS between casts.

**Alternative passive — "Consecration Aura":** Every 400 ticks, enemies within radius 2 take intelligence×0.3 magic damage. Provides passive pressure even while support-buffing.

#### Stat Override Suggestion

```python
stat_overrides={"max_hp": +120, "intelligence": +20, "resistance": +15, "strength": -10, "armor": -10}
# Budget drift: (120+20+15-10-10) / (1212+22+202+45+45) ≈ +8.9% — within ±15% cap
```

Rationale: More HP and resistance to survive as a ranged support, plus extra INT to boost ability scaling.

---

### 2.2 Marsh Thrush (T6, Champion, Rain Mage) — `wr_delta = −0.264`

#### Stat Block

| Stat | Value | Notes |
|------|-------|-------|
| HP | 962 | standard × ranged × T6 |
| Strength | 18 | INT-primary |
| Intelligence | 160 | INT-primary |
| Armor | 36 | ranged (0.8×) |
| Resistance | 36 | ranged (0.8×) |
| Attack Speed | 68 | ability playstyle |
| Mana Regen | 15 | ability playstyle |
| Move Speed | 90 | — |
| Attack Range | 3 | ranged |
| Ability Cost | 36,000 | standard |
| Power | 3.175 | — |

#### Current Kit

- **Active — Flock Call:** Grants all allies +15 move_speed and +15 attack_speed for 600 ticks. *Zero damage.*
- **Passive — Fleet Wings:** +10 move_speed (combat duration). *Pure mobility, no combat value.*

#### Diagnosis

Full support kit on a mage stat profile. The buffs it provides (+15 AS) are marginal. Its 0.75× attack speed means its auto-attacks are weak, and it has no personal damage at all. It buff-bots while the enemy kills it.

#### Suggested Powerups

**Active rework — "Gale Song":** Deal INT damage (base=50, scaling=intelligence×1.5) to all enemies in radius 2 (AOE), THEN grant all allies +15 attack_speed for 400 ticks. Combines AOE damage with the existing support identity.

**Passive rework — "Tailwind":** When Marsh Thrush casts, the next 2 auto-attacks of each buffed ally deal +20% bonus damage. Converts the support theme into tangible DPS amplification.

**Alternative passive — "Wind Shear":** Every 3rd auto-attack launches a wind projectile dealing intelligence×0.5 magic damage to the target + 1 neighbor. Gives personal DPS contribution.

#### Stat Override Suggestion

```python
stat_overrides={"intelligence": +20, "max_hp": +80, "armor": -8, "strength": -5}
# Budget drift: (20+80-8-5) / (962+18+160+36+36) ≈ +7.2% — within cap
```

Rationale: Higher INT makes its (new) damage + buff scaling meaningful; extra HP for survivability.

---

### 2.3 Company Captain (T5, Enemy, Clear Mage) — `wr_delta = −0.209`

#### Stat Block

| Stat | Value | Notes |
|------|-------|-------|
| HP | 857 | standard × ranged × T5 |
| Strength | 16 | INT-primary |
| Intelligence | 143 | INT-primary |
| Armor | 32 | ranged (0.8×) |
| Resistance | 32 | ranged (0.8×) |
| Attack Speed | 68 | ability playstyle |
| Mana Regen | 15 | ability playstyle |
| Move Speed | 90 | — |
| Attack Range | 3 | ranged |
| Ability Cost | 36,000 | standard |
| Power | 2.520 | — |

#### Current Kit

- **Active — Mark Target:** Applies −15 armor and −15 resistance debuff on lowest-HP enemy for 600 ticks. *Zero damage, pure debuff.*
- **Passive:** Empty (`EffectBundle()`). *No passive.*

#### Diagnosis

Same pattern as Hierarch: utility-only kit on an offensive stat profile, with no passive. The debuff is useful in theory but a single-target −15 armor/res on an already-low-HP target is negligible compared to just dealing direct damage.

#### Suggested Powerups

**Active rework — "Barrage Order":** Deal INT damage (base=45, scaling=intelligence×1.5) to primary target AND apply −20 armor, −20 resistance for 500 ticks. Keeps the debuff identity but adds a damage component.

**Passive — "Command Presence":** When Company Captain autos a debuffed enemy, deal bonus intelligence×0.4 magic damage. Synergizes with own active.

**Alternative passive — "Volley Command":** Every 4th auto-attack, all allied enemies within radius 2 perform a bonus attack (deals 30% of their normal auto damage to the Captain's target). Creates a "commander" fantasy.

#### Stat Override Suggestion

```python
stat_overrides={"intelligence": +15, "max_hp": +60, "armor": -5, "resistance": -5}
# Budget drift: (15+60-5-5) / (857+16+143+32+32) ≈ +6.0%
```

---

### 2.4 Storm Eagle (T9, Champion, Thunder Mage) — `wr_delta = −0.158`

#### Stat Block

| Stat | Value | Notes |
|------|-------|-------|
| HP | 1,361 | standard × ranged × T9 × speedy resistance |
| Strength | 25 | INT-primary × speedy (0.9×) |
| Intelligence | 204 | INT-primary × speedy (0.9× of 1.8) |
| Armor | 50 | ranged (0.8×) |
| Resistance | 60 | speedy applies 1.2× to resistance (ability playstyle) |
| Attack Speed | 68 | ability playstyle (speed doesn't modify AS for ability) |
| Mana Regen | 15 | ability playstyle |
| Move Speed | 90 | — |
| Attack Range | 3 | ranged |
| Ability Cost | 36,000 | standard |
| Power | 6.350 | — |

#### Current Kit

- **Active — Lightning Dive:** INT damage (base=80, scaling=intelligence×2.0) to primary target. *Single-target only, no AOE/chain.*
- **Passive — Fork Lightning:** Every 3rd auto-attack hits up to 2 neighbors for intelligence×0.4 each. *Conditional, requires autos to proc.*

#### Diagnosis

A T9 caster with a single-target active that hits for ~488 damage (80 + 204×2.0) — respectable but compared to similarly-tiered STR pieces dealing 500+ with cleave/multi-hit AND having better base AS, it under-delivers. The passive procs only every 3rd auto, and with 68 AS (slow autos), it fires rarely. The "speedy" archetype reduces primary stat by 10%, costing INT without gaining the AS benefit (ability playstyle overrides speed's AS modifier).

#### Suggested Powerups

**Active buff — "Chain Lightning":** Increase to INT damage (base=90, scaling=intelligence×2.2), add chain: primary full damage → 2 neighbors at 50% each. Makes it a true AOE threat matching T9 expectations.

**Passive buff — "Storm Surge":** Reduce trigger from every 3rd to every 2nd auto-attack, increase bounce damage to intelligence×0.5, and add: when passive triggers during own-weather (thunder), chain hits +1 additional target. Adds weather-sensitivity the system lacks.

**Alternative passive — "Overcharge":** Each auto-attack grants a stacking +3% ability damage buff (combat duration, max 10 stacks). After casting, stacks reset. Creates a "charge up → big burst" rhythm.

#### Stat Override Suggestion

```python
stat_overrides={"intelligence": +25, "max_hp": -60, "armor": -10}
# Budget drift: (25-60-10) / (1361+25+204+50+60) ≈ −2.6% (acceptable, net nerf to budget)
```

Rationale: Trade bulk for more burst — a glass-cannon rebalance that leans into the "speedy" identity.

---

### 2.5 Glade Heron (T8, Champion, Rain Mage) — `wr_delta = −0.128`

#### Stat Block

| Stat | Value | Notes |
|------|-------|-------|
| HP | 1,212 | standard × ranged × T8 |
| Strength | 22 | INT-primary |
| Intelligence | 202 | INT-primary |
| Armor | 45 | ranged (0.8×) |
| Resistance | 45 | ranged (0.8×) |
| Attack Speed | 68 | ability playstyle |
| Mana Regen | 15 | ability playstyle |
| Move Speed | 90 | — |
| Attack Range | 3 | ranged |
| Ability Cost | 36,000 | standard |
| Power | 5.040 | — |

#### Current Kit

- **Active — Toxic Volley:** INT damage (base=60, scaling=intelligence×1.8) + applies poison 500 ticks (3 stacks). *Single-target, DoT-reliant.*
- **Passive — Venom Tip:** Autos apply poison 400 ticks (1 stack). *Gradual chip.*

#### Diagnosis

A T8 mage with a DoT-focused kit. The problem: poison ticks are slow DPS that doesn't kill fast enough in a deterministic engine. The auto-applied poison (1 stack per hit at 68 AS) builds too slowly. The active deals ~424 direct + slow DoT — insufficient burst for a T8. The kit has synergy (poison stacking) but the *rate* of poison application and the *payoff* per stack are both too low.

#### Suggested Powerups

**Active buff — "Plague Volley":** Increase to base=80, scaling=intelligence×2.0. Add: if target already has 3+ poison stacks, deal 50% bonus damage (execute condition for DoT stacking payoff). Makes the active-passive synergy explosive.

**Passive buff — "Venomous Assault":** Every auto applies poison (1 stack) AND if target has 4+ stacks of poison, auto-attacks deal bonus intelligence×0.5 magic damage. Creates a ramping DPS engine.

**Alternative passive — "Toxic Miasma":** Every 300 ticks, enemies with poison within radius 3 take intelligence×0.3 bonus magic damage per stack they carry. Area denial + burst payoff for poison accumulation.

#### Stat Override Suggestion

```python
stat_overrides={"intelligence": +20, "attack_speed": +8, "max_hp": -50, "armor": -10}
# Budget drift: (20-50-10) / (1212+22+202+45+45) ≈ −2.6%
# Note: attack_speed is not a scalable stat so overrides there don't count in the budget calc
```

Rationale: More INT and faster autos accelerate poison stack rate, which is the kit's core mechanic.

---

### 2.6 Arcanist (T9, Enemy, Clear Mage) — `wr_delta = −0.111`

#### Stat Block

| Stat | Value | Notes |
|------|-------|-------|
| HP | 884 | squishy (0.65×) × ranged × T9 |
| Strength | 31 | squishy (1.25×) × INT-primary (0.2×) |
| Intelligence | 283 | squishy (1.25×) × INT-primary (1.8×) |
| Armor | 33 | squishy (0.65×) × ranged (0.8×) |
| Resistance | 33 | squishy (0.65×) × ranged (0.8×) |
| Attack Speed | 68 | ability playstyle |
| Mana Regen | 15 | ability playstyle |
| Move Speed | 90 | — |
| Attack Range | 3 | ranged |
| Ability Cost | 36,000 | standard |
| Power | 6.350 | — |

#### Current Kit

- **Active — Chain Lightning:** INT damage (base=90, scaling=intelligence×2.2) to primary; chains to 3 neighbors at 60%, 45%, 30%. *Good AOE design.*
- **Passive:** Empty (`EffectBundle()`). *No passive.*

#### Diagnosis

Unlike the others, the Arcanist has a strong active concept (multi-target chain with good scaling: 90 + 283×2.2 = ~713 primary damage). The issue is: **no passive** and extreme squishiness (884 HP, 33 armor/res at T9). It dies before casting enough times. A T9 piece with this investment in offense needs either survival tools or faster mana cycling.

#### Suggested Powerups

**Passive — "Arcane Capacitor":** On each auto-attack, gain +5 mana_regen for 400 ticks (stacks up to 4×). Accelerates mana generation so the powerful active fires more often before dying.

**Alternative passive — "Phase Shift":** When Arcanist drops below 50% HP, gain +100 resistance and +20 move_speed for 400 ticks (one-time trigger). Survival insurance to guarantee at least one more cast.

**Alternative passive — "Overloaded Aura":** Arcanist autos deal intelligence×0.2 magic damage to the target's neighbors (mini chain on autos). Provides passive AOE pressure between casts.

#### Stat Override Suggestion

```python
stat_overrides={"max_hp": +100, "resistance": +15, "intelligence": -15}
# Budget drift: (100+15-15) / (884+31+283+33+33) ≈ +7.9%
```

Rationale: Trade a small amount of INT (the active is already strong at 283 INT) for survival. At 984 HP with 48 resistance, it lives long enough to chain-lightning twice.

---

### 2.7 Will-o-Fawn (T2, Champion, Mist Mage) — `wr_delta = −0.07` (on-target)

*Included for completeness — this piece is NOT a priority buff target. Its low 0.05 win rate is its low T2 power, not a tuning failure.*

#### Stat Block

| Stat | Value | Notes |
|------|-------|-------|
| HP | 394 | squishy (0.65×) × ranged × T2 × speedy(res) |
| Strength | 14 | squishy × INT-primary × speedy (0.9×) |
| Intelligence | 114 | squishy × INT-primary × speedy (0.9× of 1.8) |
| Armor | 15 | squishy × ranged |
| Resistance | 18 | squishy × ranged × speedy (1.2×) |
| Attack Speed | 68 | ability playstyle (speed doesn't modify AS for ability) |
| Mana Regen | 15 | ability playstyle |
| Move Speed | 90 | — |
| Attack Range | 3 | ranged |
| Ability Cost | 36,000 | standard |
| Power | 1.260 | — |

#### Current Kit

- **Active — Will Blessing:** Grants an ally +40 attack_speed for 300 ticks. *Pure support, zero personal output.*
- **Passive — Ethereal:** +8 intelligence (combat duration). *Tiny flat buff.*

#### Diagnosis

A T2 support mage — the kit is fine for its role (enabler) but it is fundamentally a support on a squishy frame that does nothing solo. Since `wr_delta` is on-target, no urgent tuning needed. If addressed later (for feel):

#### Minor Tweaks (Low Priority)

**Passive enhancement:** Change to "+8 INT + on each cast, Will-o-Fawn's next auto deals intelligence×0.4 magic damage." Gives a micro-payoff for casting without changing the support identity.

---

## 3. Systemic Mage Fixes (Role-Wide)

Beyond individual piece tuning, the mage role has a **structural deficit** (§5 of mega3 report: "no burst, no bulk"). Proposed role-wide levers:

| Lever | Current | Proposed | Effect |
|-------|---------|----------|--------|
| Ability playstyle AS multiplier | 0.75× | 0.80× | +7% auto DPS for all casters |
| Ability playstyle mana regen | 1.5× | 1.7× | ~13% faster casts — more burst windows |
| Ranged HP multiplier | 0.9× | 0.95× | ~6% more survival for all ranged mages |
| INT-primary stat weight | 1.8× | 1.9× | ~6% more INT → more ability damage |

These would shift as `stat_overrides` alternatives if per-piece tuning is preferred over systemic changes. A role-wide axis adjustment (e.g. `_PLAYSTYLE["ability"]["mana_regen"] = 1.7`) would apply to all 20+ mages simultaneously and requires a re-sim to validate.

---

## 4. `stat_overrides` Engine Reference

The engine supports per-piece stat modifications after axis composition via the `stat_overrides` field:

```python
# In src/game/content.py — ChampionDef / EnemyDef
stat_overrides: dict[str, int] = field(default_factory=dict)
```

Applied in `_apply_stat_overrides(base, overrides)` which adds the override value to the composed base stat. Budget integrity is enforced by `_assert_budget()` — the sum of overrides across scalable stats (`max_hp`, `strength`, `intelligence`, `armor`, `resistance`) must stay within ±15% of the total base budget.

**This is the intended tuning lever** — each piece can deviate from its archetype template without violating the power curve. All suggestions above stay within the ±15% envelope.

---

## 5. Summary of Recommendations

| Priority | Action | Pieces Affected |
|----------|--------|-----------------|
| **P0** | Add damage component to support-only mage actives | Hierarch, Marsh Thrush, Company Captain |
| **P0** | Add passives to pieces with empty `EffectBundle()` | Hierarch, Company Captain, Arcanist |
| **P1** | Buff single-target active damage/add AOE for high-tier casters | Storm Eagle, Glade Heron |
| **P1** | Apply `stat_overrides` for survival on squishy T9 | Arcanist |
| **P2** | Consider role-wide mana_regen / AS buff | All mages |
| **P2** | Weather audit: isolate System A (Favor) vs System B (Clash) impact | All pieces |
| **P3** | Strengthen weather coefficients (System A: ±10% → ±18%; System B: ±20% → ±30%) | Systemic |

---

## 6. Next Steps

1. Implement kit changes for P0 pieces (Hierarch, Marsh Thrush, Company Captain)
2. Re-run mega simulation (`tools/simulation/mega.py`) with kit fixes
3. Run dedicated weather isolation sweep (System A only / System B only / both) to attribute weather impact
4. Validate `wr_delta → 0` for buffed pieces before proceeding to P1/P2
