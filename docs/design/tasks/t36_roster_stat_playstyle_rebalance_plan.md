# T.36 Plan — Roster axis-distribution rebalance + Primordial diversification

> **Status:** ✅ **BUILD-READY (2026-06-16, rev 7).** Full roster-wide rebalance, derived from a
> **unified axis-distribution solve** (role is a pure function of the axes, V.32 — so we optimize
> the axis *marginals* + soft role floors directly, and the role distribution falls out; one
> target, not two competing grids). Split for build into **T.36a (6 kings) → T.36b (champions) →
> T.36c (enemies)**. Both rosters fit all three target distributions (axis marginals · role distro
> all ≥4 · Calling/lore-honest) within ±2. Combined ~65 axis edits / ~40 kit rebuilds (~31 new
> beyond the kings+flips). Kit-authoring conventions live in
> [docs/live/systems/kit_design_conventions.md](../../live/systems/kit_design_conventions.md).
>
> *(Rewritten clean at rev 6 — earlier revs' ad-hoc grid/role targets are superseded & removed,
> git history holds them. **rev 7** applied matrix improvements: dawnwisp kept support (was
> support-mage), enemy `maw`/`flood` kept ranged (were melee-curated), light enemy stat×playstyle
> cross-variety. **A "force tanky_arm 8 + reach 30/30" lever was tried and reverted** — it
> melee-ized the ranged marksmen (falcon/heron) and dropped marksman below floor; the ±2 reach/
> durability drift is the gentler, identity-preserving outcome.)*

- **New §T rows:** T.36a (kings) · T.36b (champions) · T.36c (enemies). All depend on the built
  T.32/T.33/T.34/T.35 chain — no unbuilt gate.
- **Resolves:** D.25 (STR/INT coeff equilibrium — the redesigned kits *consume* the tuned coeffs).
  D.26 (INT-support value) untouched, stays deferred.

---

## 1. Goal & the reframe

**Goal:** the roster's identity axes were assigned ad-hoc; rebalance them to a principled
distribution so every archetype is represented and the stat/playstyle/role spreads are healthy.

**The reframe (why one solve, not two grids):** `role = classify_role(stat, reach, durability,
playstyle, intent)` is a pure deterministic function of 5 axes (V.32). Earlier revs chased a
stat×playstyle *cell grid* AND a separate role target — two grids fighting each other. Instead we
**optimize the per-axis marginals + soft role floors in one objective**; the role distribution is
*derived*, not targeted.

**Two structural findings that drove it:**
1. **Role-volume in axis-space is unequal** (of 216 combos: tank 33% · support 17% · bruiser 14% ·
   swash 9% · mage/marksman/assassin/spellslinger 6% · spellblade 4%). So even *perfectly balanced
   axes* give a **frontline-weighted, assassin-rare** roster — and that's correct, it matches
   gameplay (field several frontliners, 1-2 assassins). We stop targeting equal roles; only floor
   the off-roles so none is empty.
2. **The real ad-hoc artifact was `durability`** — wildly skewed (hybrid 35/60, tanky_arm 3). A
   role-first approach never surfaces this; the axis view does. Fixing it is the core of T.36b/c.

**Scope:** axis-value edits on `ChampionDef`/`EnemyDef` (`content.py`) + kit rewrites so scaling
honors the new axis (V.47) + new `Spellslinger` role + guard/snapshot/role-matrix regen. No new
pieces (60+60 invariant, V.5). No new combat primitives (reuse the T.35a `Magnitude` family).

## 2. Target axis marginals (design — ratified)

| axis | champion target | enemy target |
|---|---|---|
| **stat** | str 22 · int 22 · hybrid 16 (D.25 parity) | str 22 · int 22 · hybrid 16 |
| **playstyle** | auto 24 · ability 24 · hybrid 12 | auto 22 · ability 22 · hybrid 16 |
| **reach** | melee 30 · ranged 30 | melee 30 · ranged 30 |
| **durability** | tanky_hp 11 · tanky_arm 8 · squishy 13 · hybrid 28 | same |
| **intent** | damage ~26 · utility ~22 · hybrid 12 | same |

**Soft role floors (in-objective, not §V):** every role ≥4; bruiser ≥6, marksman ≥5, mage ≥6,
swash ≥6, support/tank ≥8; caps tank ≤12, support ≤11. Stat-parity `|str−int|≈0` (champions; D.25).

## 3. Result matrices (the solve output — both rosters fit the bill)

Solved by minimal-change local search over the axis assignment, with the **6 kings + 3 flip kits
fully pinned** (their kits are designed) and **caster identities protected** (Menders/Mystics held
ranged + ability + non-tanky, so the solver can't turn healers into auto-attackers or tanks).

### Champions (cost 12 — within ±2 of every marginal)

```
GRID  stat × playstyle      ROLE distro (derived)        AXIS marginals
        auto abil hybr       tank        11               stat   str22 int22 hyb16
str      11    7    4        support     11               play   auto24 abil24 hyb12
int       6   13    3        mage         9               reach  melee28 ranged32
hybrid    7    4    5        swashbuckler 6               durab  thp11 tarm6 squ13 hyb30
                             bruiser      6               intent dmg28 util20 hyb12
TOTAL    24   24   12        marksman     5
                             assassin     4
                             spellblade   4
                             spellslinger 4   = 60
```

### Enemies (cost 6)

```
GRID  stat × playstyle      ROLE distro (derived)        AXIS marginals
        auto abil hybr       tank        12               stat   str22 int22 hyb16
str      16    3    3        support     11               play   auto22 abil22 hyb16
int       4   15    3        spellblade   6               reach  melee30 ranged30
hybrid    2    4   10        bruiser      6               durab  thp11 tarm7 squ13 hyb29
                             mage         6               intent dmg29 util19 hyb12
TOTAL    22   22   16        swashbuckler 6
                             marksman     5
                             assassin     4
                             spellslinger 4   = 60
```

> **Note on the grid interior:** the *cell* counts (e.g. str/ability=7) are emergent — only the
> row/column **marginals** are the contract. Cells are no longer a target (that was the old
> two-grids mistake). Minor marginal drift (champ tanky_arm 6 vs 8, intent 28/20/12 vs 26/22/12) is
> within the soft band and accepted.

## 4. Full champion move list (37 movers — reference solve)

The off-role fills + kings/flips are identity-locked; donor picks marked **⚠** are awkward and get
final identity-curation at build (the matrices are the contract, not the exact donor axes).

| piece | → role | axis edits |
|---|---|---|
| dawnwisp | support | stat int→str (Mender stays support — intent kept utility) |
| veldt_pronghorn | tank | durability hybrid→tanky_arm; intent damage→utility |
| ember_salamander | mage | stat int→str; intent damage→hybrid |
| goldcrest_lark | mage | stat int→hybrid; intent utility→hybrid |
| aegis_tortoise | tank | playstyle hybrid→auto |
| **sunmane_lion** | **bruiser** | durability hybrid→tanky_hp; intent utility→damage |
| goldhide_rhino | tank | playstyle hybrid→auto; durability tanky_hp→tanky_arm |
| **mirage_caracal** | **assassin** | playstyle hybrid→ability |
| sunspear_falcon | marksman | durability hybrid→squishy; intent damage→hybrid |
| reedbank_otter | swashbuckler | intent damage→hybrid |
| torrent_heron | mage | intent damage→hybrid |
| grovekeeper_tapir | tank | playstyle hybrid→auto; durability tanky_hp→tanky_arm |
| coral_colossus | tank | playstyle hybrid→auto |
| mirewarden_toad | tank | playstyle ability→auto |
| glade_heron | marksman | intent damage→hybrid |
| **riptide_caiman** | **assassin** | playstyle auto→ability |
| **nerei*** | mage | stat hybrid→int; playstyle hybrid→ability; intent hybrid→damage |
| **glacierback_mammoth** | **bruiser** | intent hybrid→damage |
| **borealis*** | mage | playstyle hybrid→ability; intent hybrid→damage |
| **dusk_bat*** | support | stat int→str; playstyle ability→auto |
| **granite_gorilla*** | tank | stat int→str; playstyle ability→auto |
| **eclipse_jaguar** | spellblade | playstyle hybrid→auto |
| **nightglass_mantis** | **assassin** | playstyle hybrid→ability |
| **cliffeyrie_eagle** | **spellslinger** | playstyle ability→hybrid |
| **umbra*** | marksman | stat hybrid→str; playstyle hybrid→auto; intent hybrid→damage |
| **phantom_lynx*** | swashbuckler | playstyle ability→auto |
| **wraithorn_stag** | **bruiser** | durability hybrid→tanky_hp; intent utility→damage |
| **marshghast_boar** | **bruiser** | intent hybrid→damage |
| **mournhollow*** | mage | stat hybrid→str; playstyle hybrid→ability; intent hybrid→damage |
| **thunderhoof_colt** | spellblade | intent damage→hybrid |
| **voltscale_mamba** | **assassin** | playstyle auto→ability |
| **thunderhide_bison** | **bruiser** | intent utility→damage |
| **tempest_eel** | **spellslinger** | playstyle ability→hybrid |
| **voltmane_jackal** | **spellslinger** | intent hybrid→damage |
| **thunderclap_gorilla** | **bruiser** | durability hybrid→tanky_hp; intent utility→damage |
| **storm_eagle** | **spellslinger** | playstyle auto→hybrid |
| **aerion*** | spellblade | playstyle hybrid→auto |

`*` = king or flip kit (designed, see §6). **bold role** = an off-role fill (bruiser/assassin/
spellblade/spellslinger). **24 of these move stat/playstyle → kit rebuild.** marsh_thrush:
utility-INT / damage-STR (Galecrash `INT·6.55`→discounted `STR`), V.47-hybrid; axes unchanged.

## 5. Full enemy move list (28 movers — reference solve)

Enemies carry opaque tags not Callings (V.22), so curated by **name/lore**. ⚠ = awkward, build-curate.

| piece | → role | axis edits |
|---|---|---|
| conscript | swashbuckler | stat str→int; durability hybrid→squishy |
| levyman | tank | stat str→int; playstyle hybrid→auto |
| picket | swashbuckler | reach ranged→melee; durability hybrid→squishy |
| pikeman | tank | playstyle hybrid→auto |
| crossbow_levy | marksman | durability hybrid→squishy |
| powder_sapper | support | intent damage→utility |
| **sergeant_at_arms** | **bruiser** | intent hybrid→damage |
| heavy_knight | tank | playstyle hybrid→auto |
| company_guard | tank | stat hybrid→int; playstyle hybrid→auto; intent hybrid→utility |
| **battlemage** | **spellslinger** | playstyle ability→hybrid |
| steam_knight | tank | durability hybrid→tanky_arm |
| inquisitor | tank | playstyle hybrid→auto; reach ranged→melee; durability hybrid→tanky_arm ⚠ |
| lord_commander | tank | durability hybrid→tanky_arm |
| iron_maiden | tank | playstyle hybrid→ability |
| archmagus_imperator | mage | playstyle hybrid→ability |
| **blight_lurker** | **bruiser** | intent utility→damage |
| **brineblight_berserker** | **bruiser** | durability hybrid→tanky_hp |
| **dredge_hulk** | **bruiser** | intent hybrid→damage |
| maw_of_the_drowned | tank | playstyle hybrid→ability; durability hybrid→tanky_arm (kept **ranged** — fixed) |
| flood_tyrant | mage | playstyle hybrid→ability (kept **ranged** — fixed, was melee assassin) |
| **cold_iron_yeti** | **bruiser** | intent utility→damage |
| glacier_goliath | tank | playstyle hybrid→ability |
| riven_frost_wyrm | spellblade | reach ranged→melee ⚠ |
| **reaver_of_the_reach** | **spellslinger** | playstyle ability→hybrid; intent hybrid→damage |
| **quarried_behemoth** | **bruiser** | intent hybrid→damage |
| **drained_stalker** | **spellslinger** | playstyle ability→hybrid |
| **stormhawk** | **spellslinger** | playstyle ability→hybrid |
| voltaic_diviner | marksman | playstyle ability→auto; durability squishy→hybrid (lever-3 int-auto variety) |

Assassins kept as-is (hollowed_wisp, shaftmaw, hexblade_officer, spymaster = 4). **16 move
stat/playstyle → kit rebuild.** Residual ⚠ (inquisitor→melee tank, riven_frost_wyrm→melee
spellblade) — enemies are opaque-tag (V.22) so looser, but re-curate at build if the lore jars.

## 6. T.36a — the 6 Primordial king kits (locked)

All Calling-honest (cast-Calling→ability, auto-Calling→auto), deterministic (V.2/V.14), existing
primitives only. Roles (from §3 solve): Aurion spellblade · Nerei/Borealis/Mournhollow mage ·
Umbra marksman · Aerion spellblade.

| King | Kinship·Calling → axis | kit |
|---|---|---|
| **Aurion** | Spirit·Channeler → hybrid/hybrid | *Ascendance* passive: each cast → +15 STR & +15 INT, **max 8 stacks** (cast-driven; fixes the old +1/tick 600% bug). *Solar Nova*: `100 + STR·1.2 + INT·2.86` AoE magic r2, disarm 4s |
| **Nerei** | Tidekin·Channeler → int/ability | *Grudge of the Flood* passive: `on_damage_taken` → attacker gains `nerei_grudge` (marker, 6s, +1 stack, refresh); `on_damage_pre` → Nerei dmg vs grudged ×`(1 + 0.06·stacks)`, **cap 5**. *Tidal Wave*: `90 + INT·3.8` ×0.7 r3, charged 6s |
| **Borealis** | Swarm·Mystic → hybrid/ability | *Blizzard*: `80 + STR·0.96 + INT·2.7` board; **frozen targets take +15%** Blizzard dmg; freeze aura |
| **Umbra** | Scaled·Stalker → str/auto | *Hungering Shadow* passive: every 5th auto → `STR·1.5` strike. *Shadow Split*: STR-scaling auto-clones. **No INT** |
| **Mournhollow** | Beast·Channeler → str/ability | *Echoing Dead* passive: every 2nd cast → free `STR·1.0` auto. *Haunting Mist*: `80 + STR·1.0` ×0.6 r3 AoE + fear 4s + **grief** DoT (`STR·0.4`/DOT-tick, `dot_interval_ticks=100`, 4s — BURN convention) |
| **Aerion** | Skyborn·Hunter → hybrid/auto | *Overcharge* passive: every 3rd auto chains `INT·1.4` to ≤2. *Skybreaker*: 4s +~35% `attack_speed` steroid, no nuke |

New statuses: `grief` (DoT, REFLECT-style REFRESH, no gate), `nerei_grudge` (marker, no gate/DOT).

## 7. T.36b/c — the 3 champion flip kits + the off-role batch rules

**Flip kits (champion caster→auto, designed):**
- `dusk_bat` str/auto · support: *Blinding Flurry* (each auto shreds target `attack_speed`); *Dusk
  Swarm* AoE blind r1-2 + minimal STR. (Hunter that isn't a dealer — intent=utility holds support.)
- `phantom_lynx` int/auto · swashbuckler: *Phantom Claw* (flat pen `INT·0.12` sized vs max-res 359;
  each auto +`INT·0.8` magic; on `soul_charged` → `INT·1.8` **TRUE** + heal 35% of it); *Soul Reap*
  (Yorick-style — empowers the next auto).
- `granite_gorilla` str/auto + Bruiser · tank: *Stone Charge* (bank `STR·0.08`/blow, **cap STR·1.5**,
  autos discharge 50%); *Ground Slam* `STR·1.2` + stun + dump.

**Off-role batch rules (each batch = one identity rule from the conventions doc):**
- **bruiser** — melee STR brawler; ability modest; (mostly Bruiser-calling pieces, intent→damage).
- **assassin** — Stalker squishy; the active resolves through the autos (playstyle→ability burst);
  sustain scoped to the burst (conventions #10).
- **spellslinger** — ranged hybrid-playstyle; cast primary + on-hit/auto tail (battlemage); the
  ranged analog of spellblade.
- **spellblade** — dual-stat both-coeff (`STR·A + INT·B`), V.47-hybrid.
- **str/ability** (mournhollow, mirewarden, hollow_elk…) — ability is the main value, STR coeff
  **discounted** vs the INT baseline (free-auto subsidy; conventions #4). Even support casters with
  live STR autos get the discount.

## 8. Build structure — what needs doing

Split along the cleanest seam (kings / champions / enemies — separate files, each ships green +
tests independently, each one deterministic re-baseline). **Order: T.36a → T.36b → T.36c** (enemies
last — sims run champ-vs-enemy, so stabilize champions first).

| task | scope | est |
|---|---|---|
| **T.36a** | 5 king axis edits + 6 king kit rebuilds; new `grief`/`nerei_grudge` StatusDefs; **extend V.47 guard** (hybrid→both STR+INT) + dead-STR-hybrid test (B.24); fix stale `0.2` comment | M |
| **T.36b** | ~37 champion axis edits + **~15 new kit rebuilds** (beyond kings+flips, by §7 batch); protect casters; marsh utility-INT/damage-STR; new **`Spellslinger`** role (amends V.32); soft axis-marginal/distribution guard; 2 honesty fixes (torrent→mage, coral→Guardian-tank) | L |
| **T.36c** | ~28 enemy axis edits + **~16 kit rebuilds** (`abilities/enemies.py`, §7 batch + the ⚠ re-curation); same marginals + floors | L |

**Per-task acceptance:** target marginals hit (±2); all roles ≥4; V.33 ±10% HP·DPS band holds;
V.46 (no orphan stat reads) + V.47 (axis↔scaling incl. hybrid→both) green; role-matrix
(`t32_role_matrix.txt`) regenerated; snapshots regenerated; `stat_edge` STR/INT gap not widened;
one deterministic re-baseline (no RNG, V.2/V.14). **The §4/§5 per-piece axes are the reference
solve** — build may swap occupants within the marginal/floor constraints + the conventions-doc
identity rules (esp. the ⚠ donor picks).

**Kinship is intentionally left as-is** (Beast 14 / Swarm 8): Kinship is animal-locked (mammals
can't become insects) and tied to the affinity×tier grid + trait synergies (V.37 one-Primordial-
per-Kinship, emblems V.22), so a gentle rebalance doesn't exist — out of scope for an axis pass.

## 9. SPEC changes (applied via `/spec`)

- **§T.36a / §T.36b / §T.36c** rows (📋 Plan; b depends a, c depends b).
- **V.32** — add `spellslinger` role (`ranged` + playstyle-`hybrid` + `damage`; branch before
  mage/marksman). **V.37** — Primordials un-pinned from shared hybrid/hybrid (6 distinct archetypes).
- **V.47** — guard enforces `hybrid`→both STR+INT (was INT-only); **B.24** backprop (guard gap since
  T.35b). **V.52** — piece stat-stacking is in-combat only; cross-`Run` permastacking is
  augment-exclusive (holds by V.2; blurbs say "until end of battle").
- **D.25** marked consumed by T.36; **Implementation Order** T.36a→b→c after T.35b.
- Soft **axis-marginal/distribution guard** = self-documenting test, **not** a §V (re-evaluate the
  target on intentional change, don't blindly revert).

## 10. LIVING docs to update (in the landing commits)

- `docs/live/content/rosters.md` — the new axis marginals + role distro per substep.
- `docs/live/content/abilities.md` — rewritten kits for re-axised pieces.
- `docs/live/systems/kit_design_conventions.md` — already current (the authoring rules).
- Run `/check` after each substep — a stale living doc is a bug.
