# T30 Plan — Ability & Passive Catalog Implementation

> **Status:** plan — ready for review.
> **Depends:** T.20 (framework — done), T.5 (roster — done), T.3/T.26 (engine — done).
> **Resolves:** SPEC §D.5 ("per-champion ability and passive *content* (kits) is still open") and the kit half of §D.2/§D.4 (boss kits).
> **Motivated by:** [`reviews/mega2_analysis_report.md`](../../../reviews/mega2_analysis_report.md) rectification — the mega2 sim ran with **zero designed abilities firing**; all per-piece/role/trait balance reads are invalid until kits exist.
> **Not a §T row yet** — needs a `/spec` invocation to add **T.30** to §T and update §D.5. Do not edit SPEC inline.

---

## 1. Scope

Implement the **ability + passive content** for all 120 roster pieces (60 champions, 60 enemies) plus the 6 bosses, against the existing T.20 framework. The framework (registry, `CombatContext` mutators, targeting helpers, status system, event bus) is complete and unchanged here — this task is **content + two bug fixes + a small set of missing engine primitives** that several kit concepts require.

**Primary outputs:**
- `src/game/abilities/` — one module per affinity (`sun.py`, `tide.py`, `frost.py`, `crag.py`, `haze.py`, `storm.py`) + `enemies.py` + `bosses.py` + shared `factories.py`/`simple.py`.
- Bug fix in registration ids (see §3).
- A small set of new engine primitives (see §6) in `combat/`, `status.py`, `loadout.py`.

**Source of truth for concepts:** [`champion_roster.md`](../content/champion_roster.md) and [`enemy_roster.md`](../content/enemy_roster.md) (one-line kit concepts), [`boss_roster.md`](../content/boss_roster.md) (boss kits), [`effect_systems_design.md`](../systems/effect_systems_design.md) (substrate), [`t20_ability_framework_plan.md`](t20_ability_framework_plan.md) (the API this binds to).

**Out of scope:** trait synergy effects (T.28), item effects (T.29), augments (T.22), new champions/enemies, stat re-tuning (separate, post-re-sim).

---

## 2. The two defects this fixes

### 2.1 Content unimplemented (the gap)
Per §D.5, only the T.20 *reference* abilities exist (~9 active + 7 passive). The roster wires all 120 pieces to `{id}.active` / `{id}.passive` (240 slots); **~16 of 240 have any handler.** The rest fall back to the generic cast.

### 2.2 Registration-id mismatch (the bug)
The ~16 existing handlers are registered under **short ids** (`@register_active("torrent_heron.active")`) while the roster references **prefixed ids** (`champ_torrent_heron.active`, from `content.py` `active_ability=f"{id}.active"`). **0 of 240 roster ability-ids resolve to a handler** (empirically verified). So even the implemented abilities never fire — every piece runs the generic fallback in [loop_new.py:334](../../../src/game/combat/loop_new.py#L334):
```python
raw = 0.2 * strength + 4.2 * intelligence   # INT coeff is 21× STR
```
This is why the str-primary casters (Powder Sapper et al.) read as "broken" — the fallback scales on INT, which they don't have.

---

## 3. Decision: canonical ability-id convention

**Register every handler under the full roster id `{piece_id}.active` / `{piece_id}.passive`.** i.e. `@register_active("champ_torrent_heron.active")`, `@register_active("enemy_powder_sapper.active")`.

Rationale: the roster id is the contract (`content.py` already emits it; combat looks it up verbatim). Zero engine change, zero `content.py` change. The fix is mechanical:
- Re-key the existing ~16 reference handlers to the prefixed form (or retire the ad-hoc ones that don't map to a roster piece — `smash`, `thunder_crash`, `heal_pulse`, `phase_hook_test` stay as test fixtures under their bare ids).
- Author all new handlers with the prefixed id.

**Add a CI guard** (test): every `champ_*`/`enemy_*` roster `active_ability`/`passive_ability` either resolves in the registry **or** is on an explicit `UNIMPLEMENTED` allowlist that shrinks to empty as T.30 lands. This makes the 2.2 class of bug impossible to reintroduce silently.

---

## 4. Decision: generic fallback fate

Keep the generic cast as a **safety net**, but fix its bias so partial rollout doesn't distort balance:
```python
# interim, until a piece has a real kit: scale on the piece's PRIMARY stat
raw = ABILITY_COEFF * max(strength, intelligence)
```
This de-biases unimplemented str pieces immediately (a P0 one-liner) and means the re-sim isn't polluted by the int-only fallback for any not-yet-authored piece. Once the allowlist (§3) is empty, the fallback only ever fires for genuinely ability-less pieces (e.g. Picket — "no special abilities").

---

## 5. Authoring conventions

1. **Flavour** (pick simplest that fits, per t20 §6.2): `register_active_simple` for "deal X to primary"; `factories.py` shapes for cone/line/splash/chain repeats; pure Python handler only for branching/conditional kits.
2. **Scaling.** `_eval_scaling(base, "<stat>*<coeff>", actor)`. Stat = the archetype's damage source (APC/ADC-STR → `strength`, -INT → `intelligence`, Hybrid → both). **Coefficients auto-scale across tiers** because stats already carry `√P` (scaling.py) — so a *fixed* coefficient is tier-correct; do not bake tier into the coefficient.
3. **Calibration target.** A single cast should be worth ≈ **3–5 auto-attacks** of the same piece at parity (burst APCs higher, sustain ADCs lower / passive-weighted). Tune `coeff` to that, then validate in re-sim. AOE coefficients per-target lower than single-target.
4. **Mana / cost.** Keep `ability_cost = 36_000` default unless the concept demands a faster/slower cycle; starting mana 0 (t20 open item #2). Burst pieces may get a lower cost; sustain/control higher.
5. **Targeting** only via `targeting.py` helpers; **randomness** only via `ctx.rng`; **iteration** over sorted keys (t20 §5.3). No board reach-ins.
6. **Determinism.** Same inputs → byte-equal `BattleResult` (t20 acceptance). Crit stays deterministic-cadence, off by default.
7. **One file per affinity**, mirroring `champion_roster.md` sections; enemies grouped in `enemies.py` by affinity block; bosses in `bosses.py`.

---

## 6. Engine primitive-gap audit (do BEFORE the kits that need them)

Many concepts resolve with existing mutators (`deal_damage`, `heal`, `apply_status`, `apply_modifier`, `teleport`, `spawn`, `gain_mana`, hooks). These primitives are **missing** and block a subset of kits:

| # | Missing primitive | Concept examples blocked | Proposed home |
|---|---|---|---|
| G1 | **Shield / absorb pool** (temp HP that soaks next N damage) | Hoarfrost Owl, Geode Beetle, Coppercrest Stork, Heavy Knight, Hierarch | `Piece.shield` + damage pipeline pre-step |
| G2 | **Untargetable / stealth** status (targeting helpers skip it) | Marshghast Boar, Spymaster, Hollowed Wisp, Quarry Crawler, Nightglass Mantis | `status.py` + `targeting.py` filter |
| G3 | **Invulnerability / damage-immunity** status | Coral Colossus, Glacier Goliath | `status.py` + damage pipeline gate |
| G4 | **Taunt** (force attacker target) | Company Guard | `status.py` + `ai.py` target override |
| G5 | **Knockback** helper (push K hexes + collision) | Thunderclap Gorilla, Cold-Iron Yeti, Glacierback Mammoth | `targeting.py`/`combat` movement helper |
| G6 | **Summon stat blocks + timed despawn** | Steam Engineer turret, Umbra clones, boss adds | `loadout.py` summon defs + lifetime on `Piece` |
| G7 | **Per-hit penetration arg** on `deal_damage` | Phantom Lynx, Crossbow Levy (armor ignore), Veilfang Wolf | extend `ctx.deal_damage(..., pen=, pen_pct=)` |
| G8 | **Round / round-start event** (or define "round" = N ticks) | "gains HP/STR each round" (Snowpelt Cub, Glacierback, Iron Maiden, Wintermoth, many) | `events.py` + loop emits `on_round_start` |
| G9 | **HoT / DoT helper** (confirm `burn` ticks damage; add generic timed tick-heal) | Springfrog, Lostlight Wisp, Grovekeeper, Blight Lurker | `status.py` (verify burn) + heal-tick status |

**Verify first:** does `status.py` `burn`/`slow`/`fear`/`frozen` actually *do* anything in the loop today, or are they inert flags? T.20 defined them; confirm the tick loop enforces gates + burn damage before relying on them.

Phasing: implement G1–G9 as a **primitive pre-pass**, each with its own test, before the kits that consume it. Kits needing only existing mutators (the majority) don't wait on this.

---

## 7. Champion catalog (60)

Columns: **scaling** (damage stat) · **needs** (primitive gap # or `—` if existing-API only) · **flavour** (S=simple, F=factory, H=handler, P=passive).

### Clear — The Sunwild
| Piece | T | Concept | Scaling | Needs | Flavour |
|---|---|---|---|---|---|
| Dawnwisp | 1 | heal lowest ally | INT | G9 | S/P |
| Veldt Pronghorn | 2 | every 3rd auto double-strikes | STR | — | P |
| Ember Salamander | 3 | line, burn ground | INT | G9(burn) | F+H |
| Goldcrest Lark | 4 | team STR+AS buff 1 round | — | — | H |
| Aegis Tortoise | 5 | reduce dmg from adjacent | — | — | P |
| Sunmane Lion | 6 | STR cleave, self-shield share | STR | G1 | H |
| Goldhide Rhino | 7 | heal-on-auto scaling maxHP | — | — | P |
| Mirage Caracal | 8 | blink execute (low-HP bonus) | INT | — | H |
| Sunspear Falcon | 9 | sun-mark, bonus auto dmg | STR | — | P |
| Aurion (T10) | 10 | +STR/+INT per tick; nova disarm | both | G8 | P+H |

### Rain — The Tidewild
| Piece | T | Concept | Scaling | Needs | Flavour |
|---|---|---|---|---|---|
| Springfrog | 1 | HoT on ally | INT | G9 | S/P |
| Reedbank Otter | 2 | MS after attack | STR | — | P |
| Torrent Heron | 3 | 3 water-spears cone | STR | — | F+H |
| Grovekeeper Tapir | 4 | regen + vine snare DoT | both | G9 | P+H |
| Coral Colossus | 5 | regen-on-low-HP; shell immunity | — | G3 | P+H |
| Marsh Thrush | 6 | team MS+AS buff | — | — | H |
| Mirewarden Toad | 7 | slow aura; tongue pull | — | G5 | P+H |
| Glade Heron | 8 | poison stacks on auto | INT | G9 | P |
| Riptide Caiman | 9 | death-roll dash; mana on kill | STR | — | H |
| Nerei (T10) | 10 | cast empowers next 3 autos; tidal wave | INT | — | P+H |

### Snow — The Frostwild
| Piece | T | Concept | Scaling | Needs | Flavour |
|---|---|---|---|---|---|
| Snowpelt Cub | 1 | +maxHP each round | — | G8 | P |
| Wintermoth | 2 | grant ally AS buff | — | — | S |
| Permafrost Walrus | 3 | ice-boulder splash | STR | — | F+H |
| Hoarfrost Owl | 4 | ally ice-shield → chill burst | INT | G1 | H |
| Frostplate Tortoise | 5 | stacking dmg-reduction on hit | — | — | P |
| Iceclaw Lynx | 6 | autos bonus INT + slow | INT | — | P |
| Glacierback Mammoth | 7 | +HP/+STR per round; knockback stomp | STR | G5,G8 | P+H |
| Frostfang Wolverine | 8 | leap burst; crit vs frozen/slowed | STR | — | P+H |
| Frostquill Porcupine | 9 | autos slow; bonus vs slowed | STR | — | P |
| Borealis (T10) | 10 | freeze nearest each round; blizzard | both | G8 | P+H |

### Cloudy — The Cragwild
| Piece | T | Concept | Scaling | Needs | Flavour |
|---|---|---|---|---|---|
| Pebbleback Pangolin | 1 | reduced dmg while not moved | — | — | P |
| Dusk Bat | 2 | blind one enemy (AS down) | — | — | S |
| Boulderhide Skink | 3 | boulder rolls a line | STR | — | F+H |
| Geode Beetle | 4 | ally shield blocks next big hit | — | G1 | H |
| Duskstep Marten | 5 | shadow-step behind every few autos | INT | — | P |
| Granite Gorilla | 6 | reflect dmg as INT | INT | — | P |
| Eclipse Jaguar | 7 | autos alternate STR/INT; twin strike | both | — | P+H |
| Nightglass Mantis | 8 | vanish → INT execute | INT | G2 | H |
| Cliffeyrie Eagle | 9 | first auto vastly amplified | STR | — | P |
| Umbra (T10) | 10 | every 5th auto free cast; shadow clones | INT | G6 | P+H |

### Mist — The Hazewild
| Piece | T | Concept | Scaling | Needs | Flavour |
|---|---|---|---|---|---|
| Lostlight Wisp | 1 | HoT wisp on ally | INT | G9 | S/P |
| Will-o-Fawn | 2 | conjure ally-auto double | INT | G6 | H |
| Phantom Lynx | 3 | phase hit, ignore RES | INT | G7 | H |
| Hollow Elk | 4 | convert incoming dmg → mana | — | — | P |
| Fogveil Moth | 5 | shroud enemy (autos may miss) | — | — | S |
| Wraithorn Stag | 6 | phase-move; spectral gore | STR | — | P+H |
| Marshghast Boar | 7 | <50% HP → untargetable + mana | — | G2 | P |
| Veilfang Wolf | 8 | autos bonus INT + RES shred | INT | — | P |
| Spectral Heron | 9 | line-shot autos (pierce) | INT | — | P |
| Mournhollow (T10) | 10 | every other action free auto; board fear | INT | — | P+H |

### Thunder — The Stormwild
| Piece | T | Concept | Scaling | Needs | Flavour |
|---|---|---|---|---|---|
| Sparkfly | 1 | brief stun one enemy | — | — | S |
| Thunderhoof Colt | 2 | stacking AS when auto'd | STR | — | P |
| Voltscale Mamba | 3 | dash, electric trail on tiles | STR | — | H |
| Coppercrest Stork | 4 | ally shield reflects share | — | G1 | H |
| Thunderhide Bison | 5 | absorb first magic hit/round | — | G8 | P |
| Tempest Eel | 6 | chain lightning (diminishing) | INT | — | F+H |
| Voltmane Jackal | 7 | STR+INT autos; discharge on higher | both | — | P+H |
| Thunderclap Gorilla | 8 | shockwave knockback + stun | STR | G5 | H |
| Storm Eagle | 9 | every 3rd auto forks 2 targets | INT | — | P |
| Aerion (T10) | 10 | full-mana autos→free casts; board storm | both | — | P+H |

---

## 8. Enemy catalog (60)

Humans (Clear) are mostly simple; corrupted wildlife mirror champion mechanics. Same column legend.

### Clear — Humans (30)
| Piece | T | Concept | Scaling | Needs | Flavour |
|---|---|---|---|---|---|
| Conscript | 1 | every 4th auto heavier | STR | — | P |
| Levyman | 1 | +HP at round start | — | G8 | P |
| Picket | 1 | plain auto-attacker (no ability) | STR | — | — |
| Stretcher-Hand | 1 | small fixed heal lowest ally | — | — | S |
| Signal Drummer | 1 | aura: nearby allies +AS | — | — | P(aura) |
| Pikeman | 2 | reduced dmg from ≥2-hex attackers | — | — | P |
| Crossbow Levy | 2 | armor-piercing bolt | STR | G7 | S |
| Field Medic | 2 | INT heal ally; self-regen | INT | G9 | S+P |
| Powder Sapper | 2 | STR splash charge | STR | — | F+H |
| Sergeant-at-Arms | 3 | +STR per nearby ally; cleave | STR | — | P+H |
| Field Chaplain | 3 | AOE heal around self | INT | — | H |
| Standard Bearer | 3 | aura: allies +STR/+INT | — | — | P(aura) |
| Heavy Knight | 4 | self-shield at round start | — | G1,G8 | P |
| Steam Engineer | 4 | deploy turret (timed) | INT | G6 | H |
| Company Guard | 4 | taunt attacker of ally | — | G4 | P |
| Battlemage | 5 | INT fireball splash | INT | — | F+H |
| Gunslinger | 5 | autos ricochet to 2nd | STR | — | P |
| Company Captain | 5 | mark target → takes +dmg | — | — | S |
| Steam Knight | 6 | every 3rd hit reflect STR | STR | — | P |
| Riflemaster | 6 | +range; first auto huge | STR | — | P |
| Inquisitor | 6 | bonus dmg vs casters | both | — | P |
| Hexblade Officer | 6 | autos bonus INT; empower autos | INT | — | P+H |
| Lord Commander | 7 | shockwave STR + stun | STR | — | H |
| Iron Maiden | 7 | +armor on hit; release AOE STR | STR | G8 | P+H |
| Cannoneer | 8 | autos splash | STR | — | P |
| Spymaster | 8 | stealth → INT execute | INT | G2 | H |
| Hierarch | 8 | shield whole enemy line | — | G1 | H |
| Arcanist | 9 | multi-bounce chain lightning | INT | — | F+H |
| Archmagus Imperator | 9 | STR/INT autos; both-scaling nuke | both | — | P+H |
| Grand Marshal (T10*) | 10 | *non-boss apex; auto-attacker* | STR | — | P |

### Corrupted wildlife (Rain/Snow/Cloudy/Mist/Thunder)
| Piece | T | Aff | Concept | Scaling | Needs | Flavour |
|---|---|---|---|---|---|---|
| Blight Lurker | 3 | Rain | regen when un-attacked | — | G8/G9 | P |
| Drowned Siren | 4 | Rain | AOE water → silence | INT | — | H |
| Brineblight Berserker | 5 | Rain | +AS as HP falls | STR | — | P |
| Dredge-Hulk | 7 | Rain | trail slowing puddles | — | — | P |
| Maw of the Drowned | 9 | Rain | cast empowers 3 autos; vortex pull | INT | G5 | P+H |
| Iron-Collared Hound | 3 | Snow | autos slow | STR | — | P |
| Cold-Iron Yeti | 4 | Snow | reduce auto dmg; knockback charge | STR | G5 | P+H |
| Avalanche Engine | 5 | Snow | ice-boulder line + slow | STR | — | F+H |
| Glacier Goliath | 7 | Snow | +ARM/+RES/round; ice invuln | — | G3,G8 | P+H |
| Riven Frost-Wyrm | 9 | Snow | freeze on auto; INT+STR cone | both | — | P+H |
| Quarry Crawler | 3 | Cloudy | stealth after taking dmg | STR | G2 | P |
| Slag Sentinel | 4 | Cloudy | CC-immune; root target | — | G4-ish | P+S |
| Shaftmaw | 5 | Cloudy | blink INT burst | INT | — | H |
| Reaver of the Reach | 7 | Cloudy | every 4th auto free cast; cleave | both | — | P+H |
| Quarried Behemoth | 9 | Cloudy | +STR per auto absorbed; ground-slam | STR | — | P+H |
| Hollowed Wisp | 3 | Mist | start invisible; phase hit | INT | G2 | P+H |
| Drained Stalker | 4 | Mist | line-pierce autos | INT | — | P |
| Caged Banshee | 5 | Mist | AOE fear | — | — | H |
| Shroud-Killer | 7 | Mist | backline dash execute; mana on kill | STR | — | H |
| Sundered Lord | 9 | Mist | STR/INT autos; AOE haunt | both | — | P+H |
| Capture-Rig Wolf | 3 | Thunder | AS burst at round start | STR | G8 | P |
| Stormhawk | 4 | Thunder | autos chain to 2nd | INT | — | P |
| Voltaic Diviner | 5 | Thunder | chain lightning | INT | — | F+H |
| Thunder Bull | 7 | Thunder | build static; discharge stun | STR | — | P+H |
| Caged Storm-Drake | 9 | Thunder | full-mana autos chain; dive AOE | both | — | P+H |

---

## 9. Bosses (6)

Boss kits (phase 1 + phase 2 + on-death/phase hooks + map effects) are designed in [`boss_roster.md`](../content/boss_roster.md) and wired via `attach_map_effect` (T.21). Implement in `bosses.py` **last** (P4) — they exercise the most primitives (G1–G6, phase hook, summons) and are best authored once those are proven on simpler pieces. Phase transition uses the existing `on_phase_change` event + `phase_hook_test` pattern (t20 §11).

---

## 10. Phasing & re-sim gates

| Phase | Work | Gate |
|---|---|---|
| **P0** | Fix registration ids (§3) + CI guard; fix generic fallback bias (§4); verify status primitives live (burn/slow/stun/fear) | existing tests green; the ~16 reference abilities now fire |
| **P1** | All kits needing only existing mutators (most of §7–8: damage/heal/buff/slow/stun/execute/AOE/chain/reflect/empower/aura) | per-piece tests; **re-run mega**, compare role/tier/trait deltas vs the no-kit baseline |
| **P2** | Engine primitives G1–G9 (each + test) | primitive tests green |
| **P3** | Kits gated on G1–G9 (shields, stealth, taunt, knockback, summons, pen, round-events) | per-piece tests; **re-run mega** |
| **P4** | Boss kits (`bosses.py`) | boss-fight tests via `resolve_boss_combat`; **re-run boss sims** |

**Re-sim is the acceptance signal**, not raw green tests: after P1 and P3, regenerate `results/mega*/` and diff the report findings. The §3–7 verdicts in the mega2 report only become trustworthy after P1.

---

## 11. Test plan

1. **Resolution:** every roster `active_ability`/`passive_ability` id resolves to a handler OR is on the shrinking `UNIMPLEMENTED` allowlist (§3 guard).
2. **Per-piece smoke:** each implemented ability, in a 1v1 against a dummy, produces the expected effect class (damage > 0 / heal / status applied / modifier present). Not exact-value (that's balance).
3. **Scaling correctness:** STR-scaling abilities scale with `strength`, INT with `intelligence` (regression against the 2.2 bug — assert a str-caster's cast tracks STR, not INT).
4. **Primitive tests:** G1–G9 each (shield absorbs then breaks; untargetable skipped by targeting; immunity gates damage; taunt redirects; knockback moves K hexes; summon spawns + despawns; pen reduces mitigation; round event fires every N ticks; HoT/DoT ticks).
5. **Determinism:** byte-equal `BattleResult` with full kits active (t20 acceptance #9 extended to content).
6. **Lints:** `combat/` imports no content; no `random.*` in `game/`; ability-id guard (§3).

---

## 12. Acceptance criteria

1. All 120 roster pieces + 6 bosses have implemented `active`/`passive` handlers (or an intentional no-ability marker, e.g. Picket), all registered under canonical ids; `UNIMPLEMENTED` allowlist empty.
2. The 2.2 registration bug is fixed and guarded by a test.
3. Primitives G1–G9 implemented + tested (or explicitly deferred with the dependent kits parked behind the allowlist).
4. STR-scaling kits scale on STR (the original defect cannot recur — covered by test #3).
5. `tests/game/test_abilities*.py` green; existing suite unaffected; determinism + lints pass.
6. Mega re-run completed after P1 and P3; report findings refreshed.

---

## 13. SPEC impact (for `/spec`)

- Add **§T.30** row: "Ability & passive catalog — implement all champion/enemy/boss kits against the T.20 framework; fix ability-id registration; add shield/stealth/immunity/taunt/knockback/summon/pen/round-event/HoT primitives" — files `game/abilities/`, `game/status.py`, `game/combat/`, deps T.20/T.5/T.26, size **L**.
- Amend **§D.5**: framework done *and* kit content implemented under T.30 (was "still open").
- Consider a new **§V invariant**: "every roster `active_ability`/`passive_ability` id resolves in the registry (or is on the explicit unimplemented allowlist)" — this is exactly the invariant whose absence let the 2.2 bug ship. Strong candidate for `/backprop`.

---

## 14. Open decisions

1. **"Round" semantics (G8).** Define a round as a fixed tick count and emit `on_round_start`, or reinterpret all "each round" passives as periodic ticks? Many pieces depend on this — decide before P2.
2. **Summon scope (G6).** Full summoned-piece stat blocks (per enemy_roster open Q "Summon stats") vs. a lightweight stat-derived add. Affects Steam Engineer, Umbra, bosses.
3. **Calibration pass ownership.** T.30 ships *functional, roughly-calibrated* kits; the precise coefficient tuning happens against the post-P1 re-sim — is that in T.30 or a follow-up balance task?
4. **Aura modeling.** Signal Drummer / Standard Bearer "aura" = periodic radius re-application vs. a persistent `WHILE_CONDITION` modifier (t20 deferred those). Pick one.
5. **Boss kit depth** — full 2-phase authoring in T.30, or land phase-1 here and phase-2 as a T.21 follow-up?
