# T.36 Plan — Roster stat/playstyle rebalance + Primordial diversification

> **Status:** ✅ **BUILD-READY (2026-06-16, rev 5)** — **rev 5 = full roster-wide
> build, split 3 ways: T.36a (kings) / T.36b (champions) / T.36c (enemies)** — see
> **§14 (build structure)** + **§13 (the curated solve for both rosters).** Both
> rosters fit all 3 distros (axis marginals · roles all ≥4 · Calling/lore-honest)
> within ±1; combined ~66 axis edits / ~39 kit rebuilds (~30 new beyond kings+flips).
> rev 4 reframed to the **unified axis-distribution solve** (role derives from axes,
> V.32 — stop fighting two grids; fixes the `durability` skew). rev 3 locked the 6
> king kits + 3 flip kits + `Spellslinger` role; conventions in
> `docs/live/systems/kit_design_conventions.md`. **Read §13–§14 for the current plan;**
> §2–§12 are the rev 2/3 record (now-superseded ad-hoc grid/role tables).

- **Status:** two NEW §T rows — **T.36a** (`📋 Plan`) + **T.36b** (`📋 Plan`, depends T.36a).
- **Depends:** T.32 (role/intent axes, `classify_role`), T.33a/b (stat scaling), T.34a–c (`AbilityMeta`/`Magnitude`), T.35a (closed `Magnitude` family + V.46 orphan-stat guard), T.35b (V.47 axis↔scaling + INT coeffs). All built ✅ — no unbuilt gate.
- **Resolves:** D.25 (STR/INT coeff equilibrium — the redesigned kits *consume* the tuned coeffs; the lever work is done, T.36 spends it). Touches D.26 (INT-utility support value) only tangentially — left open.
- **Design source-of-truth:** the 2026-06-15 STR/INT scaling-edge journal (`docs/journal/2026-06-15_str_int_scaling_edge.md`) for the coeff equilibrium; this plan for the grid + per-piece moves.
- **What this plan adds beyond the draft:** the verified delta math (§2), the full 12-piece T.36b enumeration (§5), the V.47 hybrid-STR guard gap (§3/§6), and the self-documenting distribution-guard design (§8).

---

## 0. Substep split (real seam: apex content vs distribution)

- **T.36a — Primordial diversification.** Re-axis + kit-rewrite the **6 T10 kings** off the uniform `hybrid/hybrid` mold into 6 distinct apex archetypes. Self-contained, highest-identity-value, ships + tests first. Moves 5 of 12 `hybrid/hybrid` champs out (Umbra stays).
- **T.36b — Roster distribution re-axis.** Re-axis + kit-rewrite **12 non-king champs** to land the full target grid. Depends on T.36a (the king moves change the marginals T.36b finishes against — see §2 staged math).

Each substep: re-axis → kit rewrite (V.47) → snapshot regen → role-matrix regen → determinism re-baseline → `stat_edge` balance read. Both ship green independently.

## 1. Scope

**In:**
- Change `stat` / `playstyle` axis values on `ChampionDef`s (`content.py`).
- Rewrite the affected ability/passive kits so scaling honors the new axis (V.47) and the axis-aware kit patterns (§5).
- Add a **distribution guard test** (soft, self-documenting).
- Snapshot + role-matrix + sim re-baseline.

**Out (with why):**
- **No net-new/removed pieces** — the 60-champ, 1-per-affinity-×-10-tier grid is invariant (V.5/§T.5). Re-axis only.
- **No enemy/boss re-axis** — the STR/INT design lever is the champion roster (enemies are opaque-label trait carriers, V.22); enemy balance is out.
- **No new combat primitives** — kit rewrites reuse existing `Magnitude` kinds + hook idioms (T.35a). If a king kit *wants* a primitive that doesn't exist, descope that flourish, don't build engine.
- **No D.26 support-value fix** — needs a survivability sim, not a re-axis (stays deferred).
- **No grid-cardinality CI invariant** — the guard is a soft test, not §V (user decision).

## 2. The gap today — current matrix + the verified path to target

Live champion `stat × playstyle` (computed from `_CHAMPION_DEFS`, 60 champs):

```
        auto ability hybrid  TOT
str       8     2      6      16
int       5    18      3      26
hybrid    3     3     12      18
TOT      16    23     21      60
```

**Target (ratified draft grid):**

```
        auto ability hybrid  TOT
str      12     6      4      22
int       6    12      4      22
hybrid    6     6      4      16
TOT      24    24     12      60
```

**Per-cell delta (target − current):** str/auto +4, str/ability +4, str/hybrid −2, int/auto +1, int/ability −6, int/hybrid +1, hybrid/auto +3, hybrid/ability +3, hybrid/hybrid −8.

### Staged math (a then b) — verified to land exactly

**After T.36a** (5 kings leave `hybrid/hybrid`; **Aurion** stays):

```
        auto ability hybrid  TOT       king moves (CORRECTED — Calling-honest):
str       9     3      6      18       Umbra       h/h→str/auto      (Stalker=auto)
int       5    19      3      27       Nerei       h/h→int/ability   (Channeler=cast)
hybrid    4     4      7      15       Borealis    h/h→hybrid/ability (Mystic=cast)
                                       Mournhollow h/h→str/ability   (Channeler=cast)
                                       Aerion      h/h→hybrid/auto   (Hunter=auto)
                                       Aurion      stays h/h         (Channeler=cast)
```
*(Grid totals identical to the original draft — same cell multiset, only occupants swapped.)*

**T.36b** then re-axises **12 non-king champs** (deltas vs post-a): str/auto +3, str/ability +3, str/hybrid −2, int/auto +1, int/ability −7, int/hybrid +1, hybrid/auto +2, hybrid/ability +2, hybrid/hybrid −3 → **lands the target exactly** (proof in §5 table; sums balance: 7 int + 2 str + 3 hybrid sources = 6 str + 2 int + 4 hybrid fills = 12).

### Where each piece lives (touch points)

| Piece of work | `file.py` | state |
|---|---|---|
| `stat` / `playstyle` axis values | `game/content.py` `_champion_def(...)` calls (lines ~520–667) | ✅ exists — data edit |
| Champion ability/passive handlers | `game/abilities/champions.py` (`@register_active`/`@register_passive` + module-level `Magnitude`s, e.g. `EMBER_SALAMANDER_DMG = ScalingTerm("damage",60,"intelligence*3.93")` :155) | ✅ exists — rewrite per piece |
| INT/STR coeffs as `Magnitude`s | `game/registries.py` `ScalingTerm`/`PctResource`/`MaxOfTerm`/`SetByCaller` (:331/374/413/454) | ✅ closed family (T.35a) |
| V.47 axis↔scaling guard | `tests/game/test_content.py` `TestAxisScalingAlignment::test_int_and_hybrid_units_reference_int` (:359) | 🔶 **partial** — checks INT only, not hybrid-STR (§3) |
| Proxy band (±10% HP·DPS) | `tests/game/test_role_intent.py` (V.33) | ✅ exists — must stay green |
| Distribution guard | `tests/game/test_content.py` | ❌ **new** (§8) |
| Role matrix | `docs/design/tasks/t32_role_matrix.txt` + `tests/game/test_role_intent.py` | ✅ regen if any role changes |
| Formula/stat snapshots | `tests/game/ability_formulas.snapshot.json` + scaling snapshot | ✅ regen (text/number drift expected) |

## 3. Architecture

### Where axes plug in
`stat` and `playstyle` are plain fields on `ChampionDef`, consumed by `compose_stats` (the `_PRIMARY_STAT` map `str→{str:1.8,int:0.2}` etc., `content.py:34`) and by `classify_role`. Changing them is a **data edit**; the statline regenerates deterministically. No model change.

### Application order / re-baseline
Re-axis shifts: (1) generated statlines (primary-stat weights flip), (2) kit numbers (rewritten coeffs), (3) `classify_role` output for any piece whose role-determining axes move → role-matrix regen. All three are deterministic → **one re-baseline per substep** (snapshots + sims); **no RNG introduced** (V.2/V.14).

### Kit-rewrite fidelity (V.47 + the closed `Magnitude` family)
Every re-axised int/hybrid piece must reference its primary via a registered `Magnitude` on its `AbilityMeta` (T.35a closed it; orphan inline math fails the V.46 guard `test_no_orphan_stat_reads`). Re-axis = swap/retune the `Magnitude`'s `scaling` expr (`"intelligence*K"` ↔ `"strength*K"` ↔ `"strength*A + intelligence*B"`), not invent primitives.

### ⚠️ V.47 guard gap (must fix in T.36)
SPEC §V.47 states `hybrid` units reference **both** STR and INT, but the guard `test_int_and_hybrid_units_reference_int` only checks `_meta_references_int` — it **never verifies a hybrid piece references STR**. T.36 *adds* `hybrid/auto` + `hybrid/ability` pieces whose whole point is both-coeff scaling, so this gap is now load-bearing. **Fix in T.36a:** extend the guard so `stat="hybrid"` must reference **both** STR and INT (add `_meta_references_str` + the hybrid branch). Backprop as a §B note (guard under-enforced V.47 since T.35b).

### Coefficient equilibrium (from D.25 — the authoring rule)
Universal auto is `1.0·STR + 0.25·INT`, so a STR carrier gets ~7× INT's auto DPS per primary point. DPS-parity **INT ability-*damage* coeff ≈ 3.7** at baseline (`mana_cost` 300k, ability mults). Scaling rule for authored kits:
`INT coeff ≈ 3.7 × (mana_cost / 300000) × (100 / mana_regen_base)` — ultimate at 2× cost ⇒ ~2× coeff; auto-int/hybrid pieces need *less* (autos carry). STR ability coeffs ≈ 0.8× their pre-D.25 values. Authored INT damage coeffs currently sit ~3.5–4.3 — reuse, don't re-derive.

## 4. Decisions

- **Grid = full draft (22/22/16).** Flagships `str/auto = int/ability = 12`; off-cells 6; `hybrid/hybrid = 4`. (User-ratified.)
- **Split T.36a / T.36b** along the apex-vs-distribution seam. (User-ratified.)
- **Distribution guard = soft self-documenting test, not §V.** On failure the test message tells operators to *re-evaluate whether the new distribution is desirable*, not blindly restore counts. (User-ratified — see §8 for the exact comment.)
- **str/ability** (revised guideline — supersedes the old "empowers autos" rule): the **ability is the main value source** (hits hard / big effect); the STR ability-coeff is tuned **lower** than the INT baseline because the free auto-attack tagalong already pays STR. *Not* the "cast buffs next autos" steroid pattern. Enforced by review, not test.
- **Aurion keeps `hybrid/hybrid`** (Channeler — keeps a cast in a mixed kit) as the deliberate "dual mold survives" king; the other 5 kings diversify. *(Corrected: the earlier draft kept Umbra here, but Umbra is a Stalker = auto-Calling, so it belongs in `str/auto`.)*
- **Per-piece assignment is a proposal.** Cell counts are the contract; lore/kit fit may reshuffle *which* piece fills a cell during build — as long as the matrix lands and V.47 holds.

## 5. Authored values

### T.36a — the 6 kings (CORRECTED: Calling-honest, live-brainstorm locks)

> **Supersedes the earlier draft.** The earlier table put 3 kings' *playstyle* against
> their *Calling*: Aurion + Mournhollow are **Channelers** (cast → ability/hybrid) yet
> were dumped in `auto` cells; Aerion is a **Hunter** (auto) yet sat in `str/ability`.
> Rule (from the kit-rework guideline): **the Calling fixes the playstyle; the stat
> stays flexible.** Cast-Callings (Channeler/Mystic/Multicaster/Warden/Mender) → ability;
> auto-Callings (Hunter/Skirmisher/Stalker/Bruiser) → auto. **Grid is unchanged** — the
> corrected list fills the *same cell multiset*; only the king↔cell occupant swapped
> (Aurion↔Umbra, Mournhollow↔Aerion).

| King | Kinship · Calling | from | → to | Calling fit | locked kit (live) |
|---|---|---|---|---|---|
| Aurion | Spirit · **Channeler** | hybrid/hybrid | **hybrid/hybrid** (kept) | cast → hybrid ✓ (keeps a cast) | *Ascendance* passive: each cast → +15 STR/+15 INT, **max 8 stacks** (cast-driven; fixes the old +1/tick 600% bug). *Solar Nova*: `100 + STR·1.2 + INT·2.86` AoE magic r2, disarm 4s — coeffs held |
| Nerei | Tidekin · **Channeler** | hybrid/hybrid | **int/ability** | cast → ability ✓ | *Grudge of the Flood* passive (replaces Tideturn): `on_damage_taken` → attacker gains `nerei_grudge` (marker, 6s, +1 stack, refresh); `on_damage_pre` → Nerei outgoing vs grudged ×`(1 + 0.06·stacks)`, **cap 5 (+30%)**. *Tidal Wave*: `90 + INT·3.8` ×0.7 r3, charged 6s — coeff held |
| Borealis | Swarm · **Mystic** | hybrid/hybrid | **hybrid/ability** | cast → ability ✓ | *Blizzard*: `80 + STR·0.96 + INT·2.7` board (INT nudged 2.28→2.7, Mystic lean); **frozen targets take +15% Blizzard dmg** (light freeze-coupling); freeze aura kept |
| Umbra | Scaled · **Stalker** | hybrid/hybrid | **str/auto** | auto → auto ✓ | *Hungering Shadow* passive: every 5th auto → empowered `STR·1.5` strike (was INT·2.38). *Shadow Split*: STR-scaling auto-clones (steroid). **No INT** (str-stat) |
| Mournhollow | Beast · **Channeler** | hybrid/hybrid | **str/ability** | cast → ability ✓ | *Echoing Dead* passive **kept** (every 2nd cast → free auto on primary — now `STR·1.0`, the auto tagalong). *Haunting Mist* (was Board Fear): `80 + STR·1.0` ×0.6 r3 AoE + fear 4s + **grief** DoT — `potency = GRIEF_DOT.eval(actor) = STR·0.4` **per DOT tick** (`dot_interval_ticks=100` = 1s, like BURN), 4s → **4 ticks** total ≈ `STR·1.6` spread (NOT per engine tick; trimmed 0.6→0.4 — DPS-fit ran hot at 0.6, see §5 fit table). **STR coeff in D.25 parity band ~1.1–1.4** — fear + DoT carry; old 2.7 was ~2× over parity. New `grief` StatusDef (REFRESH, DoT, no gate — matches BURN convention) + `GRIEF_DOT` ScalingTerm on AbilityMeta (V.46) |
| Aerion | Skyborn · **Hunter** | hybrid/hybrid | **hybrid/auto** | auto → auto ✓ | *Overcharge* passive (rework — drop the near-full-mana gate): **every 3rd auto** (deterministic cadence counter, `crit_counter`-style, V.2) arcs chain-lightning to ≤2 nearby enemies for `INT·1.4` each. *Skybreaker* active (was Board Storm — rework to steroid, NOT nuke): 4s self-buff +~35% `attack_speed` + autos chain to adjacent; low/no direct coeff — **autos carry**. Both stats referenced (STR autos + INT chain) → V.47. *Build-confirm: timed-self-Modifier path (Modifier+Lifetime) on `attack_speed`.* |

**Note on the str/ability guideline (supersedes §4 "empowers autos"):** per the revised
kit-rework rule, a `str/ability` piece makes the **ability the main value source**
(hits hard / big effect), with the STR ability-coeff tuned **lower** than the INT
baseline because the free auto-attack tagalong already pays STR. It is *not* the old
"cast buffs next autos" steroid pattern. Mournhollow's *Board Fear* (board-wide CC +
discounted STR burst) + the free-auto passive is the canonical shape.

**Resulting grid after T.36a — UNCHANGED** (same per-cell king deltas as the original
draft; see staged math below): each of the 5 leaver kings adds +1 to its target cell,
Aurion (not Umbra) is the one that stays in `hybrid/hybrid`.

### T.36b — the 12 non-king re-axis moves (CORRECTED: Calling-honest reshuffle)

> **Supersedes the earlier draft**, which inherited the same Calling-incoherence as the
> kings (dusk_bat is a **Hunter** = auto, yet was pointed at an ability cell; eclipse_jaguar
> is a **Channeler** = cast, yet pointed at an auto cell; Guardians shoved into raw auto).
> Reshuffled to honor Calling→playstyle while **preserving the destination cell multiset**
> (3×str/auto, 3×str/ability, 1×int/auto, 1×int/hybrid, 2×hybrid/ability, 2×hybrid/auto) →
> grid still lands exactly. The roster's re-axis pool is cast-Calling-skewed vs the
> auto-heavy target, so **2 irreducible auto-slot misfits** are paid with a **minimal
> Calling tweak** (a Beast-natural auto-Calling added) rather than a playstyle that fights
> the kit. (User-ratified approach.)

| # | piece | Kinship · Calling | from | → to | Calling fit |
|---|---|---|---|---|---|
| 1 | `champ_snowpelt_cub` | Beast · Guardian·Packmate | str/hybrid | **str/auto** | **tweak +Bruiser** (tanky frontline brawler — Bruiser fits the tank role better than Skirmisher's mobile-damage pull) |
| 2 | `champ_granite_gorilla` | Beast · Guardian | int/ability | **str/auto** | **tweak +Bruiser** (gorilla brawler — natural auto) |
| 3 | `champ_dusk_bat` | Swarm · Trickster·**Hunter** | int/ability | **str/auto** | ✓ Hunter=auto (was the ✗✗ Hunter-in-ability) |
| 4 | `champ_pebbleback_pangolin` | Scaled · **Guardian**·Packmate | str/hybrid | **str/ability** | ✓ Guardian→ability (tank casts) |
| 5 | `champ_mirewarden_toad` | Tidekin · **Guardian** | int/ability | **str/ability** | ✓ Guardian→ability (mire-caster; was str/auto) |
| 6 | `champ_hollow_elk` | Spirit · Guardian·**Channeler** | int/ability | **str/ability** | ✓ Channeler+Guardian=cast |
| 7 | `champ_phantom_lynx` | Spirit · **Stalker**·Packmate | int/ability | **int/auto** | ✓ Stalker=auto (INT-fed assassin autos) |
| 8 | `champ_tempest_eel` | Tidekin · Mystic·**Multicaster** | int/ability | **int/hybrid** | ~ soft (caster; hybrid-playstyle still casts) |
| 9 | `champ_marsh_thrush` | Skyborn · Warden·Mystic·Multicaster | int/ability | **hybrid/ability** | ✓ all-cast → ability |
| 10 | `champ_eclipse_jaguar` | Beast · **Stalker**·Channeler | hybrid/hybrid | **hybrid/auto** | ✓ **tweak: restore Stalker** (in the roster doc, dropped from code) — kit-soul is alternating STR/INT autos → role `spellblade`; Channeler justifies the twin-cast active |
| 11 | `champ_voltmane_jackal` | Beast · **Skirmisher**·**Channeler** | hybrid/hybrid | **hybrid/hybrid + intent=damage** → **Spellslinger** | ✓✓ Skirmisher(auto)+Channeler(cast) = hybrid-playstyle honors both (see Spellslinger tweaks) |
| 12 | `champ_grovekeeper_tapir` | Tidekin · Bruiser·**Mender** | hybrid/hybrid | **hybrid/ability** | ✓ Mender=cast (caster-mender tank; was hybrid/auto — swapped with eclipse to preserve its auto-soul) |

**The 3 Calling tweaks** (minimal trait edits to fit the cells): `snowpelt_cub` gains
**Bruiser** (tanky brawler), `granite_gorilla` gains **Bruiser** (gorilla brawler),
`eclipse_jaguar` **restores Stalker** (it is in the roster doc, dropped from code — this
tweak doubles as a doc/code drift fix). All Beast pieces, all auto-Callings, lore-natural.
No other traits change.

**Occupies `hybrid/hybrid` (target 4):** **Aurion** (king) + `champ_voltmane_jackal` + `champ_torrent_heron` + `champ_marshghast_boar`. *(Spellslinger tweaks moved `goldhide_rhino`→hybrid/ability and `glacierback_mammoth`→hybrid/auto out; voltmane + torrent in — grid-neutral. See "Spellslinger population" below.)*

**Verification — destination cell multiset is identical to the earlier draft** (only WHICH
piece fills each cell changed; eclipse_jaguar takes hybrid/**auto** to keep its alternating-
auto soul and grovekeeper takes hybrid/**ability** for its Mender cast — the two just swap
hybrid cells), so the per-cell deltas are unchanged: str/auto 9+3=**12**;
str/ability 3+3=**6**; str/hybrid 6−2=**4**; int/auto 5+1=**6**; int/ability 19−7=**12**;
int/hybrid 3+1=**4**; hybrid/auto 4+2=**6**; hybrid/ability 4+2=**6**; hybrid/hybrid 7−3=**4**. ✅ exact.

**Stat marginal check:** str ×6 (#1-6), int ×2 (#7-8), hybrid ×4 (#9-12) — matches the required 6/2/4 fills.

### T.36b flip kits — the 3 caster→auto reworks (LOCKED, live brainstorm)

These three flip *playstyle* ability→auto — a real identity reshape (the autos must
carry, the caster kit gets demoted), same problem class as the auto-kings. The other
9 are coeff-only or template-driven (see per-cell guidance). **Each holds intent → role
identity is preserved** (the recurring lesson: flex stat+playstyle, hold intent).

| Piece | → axis · role | Locked kit |
|---|---|---|
| `champ_dusk_bat` | str/auto · **utility** → role `support` (unchanged) | *Blinding Flurry* passive (was +move_speed): each auto shreds target `attack_speed` (flat/stacking — the harrying flurry); STR autos chip + deliver the shred. *Dusk Swarm* active (was single-target blind): AoE blind/AS-shred r1-2 + **minimal** STR strike (low coeff — it's a support; autos+debuff are the value). **Don't erase the debuff — relocate it onto the autos.** A Hunter that isn't a dealer (intent=utility holds the support role). |
| `champ_phantom_lynx` | int/auto · damage → role `swashbuckler` | *Phantom Claw* passive (was flat pen%): flat **`penetration = INT·0.12`** (the shred, INT-scaled — sized vs max-res 359 so it never zeroes the midfield; old INT·0.3 did); each auto +`INT·0.8` **magic** on-hit (the carry, split phys/magic vs base auto). On `soul_charged`: that auto instead adds `INT·1.8` **TRUE** + **heals self 35%** of it (soul reap). *Soul Reap* active (Yorick-Q style): lunge + apply self `soul_charged` — no direct damage; the payoff lands **on the next auto**. INT does quadruple duty (proc / pen / true-strike / reap-heal); the *active resolves through an auto* = the cleanest int/auto in the roster. Sustain is **scoped to its own burst** (squishy diver survives the commit; no free omni-lifesteal). |
| `champ_granite_gorilla` | str/auto + **Bruiser** tweak · utility → role `tank` (unchanged) | *Stone Charge* passive (replaces instant % reflect): damage taken **banks** `charge += STR·0.08` **per blow** (flat-per-blow, ignore magnitude), **hard cap `charge ≤ STR·1.5`**; autos discharge `charge·0.5` each as bonus physical on the gorilla's *own* target; depletes. *Ground Slam* active: `70 + STR·1.2` AoE r1 + stun 2s + **dumps remaining charge** AoE. **Avoids the asymmetric-reflect death-trap** (no instant %-of-incoming reflect → squishies don't suicide poking it) AND **makes autos the point** (str/auto honored — discharge flows through autos). STR keyed to the gorilla's *own* stat (not enemy damage), cap kills the hidden `k·N` hit-count multiplier → linear STR scaling, no stealth gem. |

### T.36b batch sketch — the other 9 (coeff retune + faults caught by the skeptical pass)

Verified each role-code holds (`build_role_code`/`classify_role`) and scanned every coeff
against the conventions doc. Findings:

| piece | →cell · role | coeff action | note |
|---|---|---|---|
| `snowpelt_cub` | str/auto · tank | keep `STR·0.96` active | fine — modest cub slam; +Bruiser tweak |
| `pebbleback_pangolin` | str/ability · tank | (no damage coeff) | pure-utility roll/shield tank; add token STR scaling if needed |
| `mirewarden_toad` | str/ability · tank | **`INT·3.29` → `STR·~1.0`** | 🔴 naive swap = 2-3× over parity; it's a utility tank — ability is CC/peel, damage minimal |
| `hollow_elk` | str/ability · tank | **`INT·3.93` → `STR·~1.2`** | 🔴 same landmine (conventions #4); restat low |
| `grovekeeper_tapir` | hybrid/ability · tank | keep `STR·0.8+INT·1.9` | already both-coeff modest cast; V.47-hybrid ✓ |
| `voltmane_jackal` | hybrid/auto · spellblade | **demote `INT·2.28`** | 🟡 ability-nuke lean; hybrid/auto wants autos to carry → push INT onto on-hit, modest active |
| `eclipse_jaguar` | hybrid/auto · spellblade | keep passive `STR·0.24/INT·0.64`; trim twin-cast `INT·2.38` | 🟢 alternating-auto passive *is* the carry; minor trim |
| `marsh_thrush` | hybrid/ability · support | utility=INT (Trill/Wings), **damage=STR**: Galecrash `INT·6.55 → STR·~4-5` (discounted) | ✅ resolved — see below |
| `tempest_eel` | int/hybrid · **Spellslinger** (new role) | keep `INT·4.37` chain primary, add INT auto-zaps | ✅ resolved — new role, see below |

**The recurring landmine:** every `int/ability → str/ability` move with an existing INT nuke
(`mirewarden`, `hollow_elk`) must drop the coeff hard on the stat swap — naive `INT·K →
STR·K` is the Mournhollow fault repeated. These are *utility tanks*, so the ability is
CC/peel and the damage coeff should be `~STR·1.0`, well under even the str/ability parity band.

**Two decisions — RESOLVED (user-ratified):**

1. **`tempest_eel` → new role `Spellslinger`.** The role taxonomy had a hole: a **ranged +
   playstyle-`hybrid` damage dealer** (casts *and* autos) is neither a pure `mage`
   (ability-only) nor a true `marksman` (auto ADC) — `classify_role` collapsed it into
   marksman because `caster = (playstyle == "ability")` lumps hybrid-playstyle with auto
   (`content.py:184,193`). This is the **ranged analog of the melee-side gap**, but keyed on
   *playstyle*-hybrid (≠ `spellblade`, which is *stat*-hybrid + intent-hybrid). **Add
   `Spellslinger`** = `reach==ranged AND playstyle=="hybrid" AND intent==damage` (checked
   before the final mage/marksman line). tempest_eel keeps its chain-lightning cast as primary
   value + gains INT-fed auto-zaps (the hybrid playstyle) → lands `Spellslinger` honestly.
   *Taxonomy change: `ROLE_TITLES`, `classify_role`, V.32, regen `t32_role_matrix.txt` + role
   tests.*
2. **`marsh_thrush` → `hybrid/ability`, utility=INT / damage=STR.** Clean per-ability stat
   split: the support magnitudes stay INT (*Quickening Trill* buff INT·0.25, *Restless Wings*
   MS INT·0.17), and the **damage** ult *Galecrash* swaps `INT·6.55 → STR·~4-5` (the gale's
   physical force = STR, the support cleverness = INT). Satisfies V.47-hybrid honestly (both
   stats do real work, neither token). **STR coeff is *discounted*** — even though marsh is a
   caster (low attack_speed), its STR-stat autos still out-chip every INT support **for free**
   (measured +5.5/s L1 → +18.5/s L3 vs an INT peer), so Galecrash comes *down* to keep marsh at
   support budget, not up to match the old INT·6.55 (which sat on the higher 1.8 INT weight).
   Sim-verify at build.

### Role-dependency impact (adding `Spellslinger` + the T.36 role changes)

Audited every consumer of the content `role`/`role_code` (V.32). **No game-logic system
branches on the role value** — it's computed + stored + displayed, never used for selection
or balance:

| consumer | reads content `role`? | impact |
|---|---|---|
| `content.py`/`encounter.py`/`models.py` | computes + stores on pieces | additive (new string only) |
| `formation.py` (enemy placement) | **No** — own `classify_role`→`PlacementRole` (durability+reach) | **unaffected** |
| `bosses/data.py` | hardcodes `role="boss"` | unaffected |
| `tools/gen_role_matrix.py` + `t32_role_matrix.txt` | enumerates combos→role | **regen** (in scope) |
| `tests/game/test_role_intent.py` | asserts the matrix | **update** (in scope) |
| `report.py` / `inspect.py --role` / `ui/` | display + substring filter | safe |

**Two parallel role taxonomies, both pure axis-functions, deliberately decoupled:**
- **content `role`** (V.32) — 9-role *identity* label (all 6 axes) → display / role-matrix / sim.
- **formation `PlacementRole`** (`formation.py:69`) — 4-bucket *tactical placement*
  (`durability`+`reach` only): tanky→FRONTLINE, melee+squishy→FLANK, melee→MIDLINE,
  ranged→BACKLINE. Consumed by `plan_enemy_formation` (enemy squad only).

So a `Spellslinger` (ranged) places BACKLINE like any mage/marksman — **no formation change.**
And T.36 changes stat/playstyle/intent but **not durability/reach**, so **every enemy's
PlacementRole is unchanged.** The identity taxonomy can grow (new roles, re-axis) without ever
perturbing placement. Net: Spellslinger + all T.36 role shifts are **display + matrix-regen
only, zero game-logic risk.**

**Spellslinger population (2 grid-neutral tweaks — applied).** Adding the role surfaced 2
pieces that are *more* Calling-honest as spellslingers; both swaps preserve every cell count:
- **`voltmane_jackal`** hybrid/auto → **hybrid/hybrid + intent=damage** (Spellslinger). It is
  Beast·**Skirmisher·Channeler** — Skirmisher(auto)+Channeler(cast) *are* hybrid-playstyle;
  the old hybrid/auto **ignored its Channeler**. Paired swap: **`glacierback_mammoth`**
  hybrid/hybrid → **hybrid/auto** (Beast·Bruiser → Bruiser=auto, honest). *(voltmane intent
  hybrid→damage: V.33 ±10% re-check at build; it already has a damage kit `STR·0.96+INT·2.28`.)*
- **`torrent_heron`** hybrid/ability → **hybrid/hybrid** (Spellslinger — Tidekin·Mystic,
  ranged, already intent=damage; mild Mystic→hybrid dilution). Paired swap: **`goldhide_rhino`**
  hybrid/hybrid → **hybrid/ability** (Scaled·Bruiser·**Mender** → Mender=cast, caster-tank).

Net: **`Spellslinger` = 3 occupants** (tempest_eel, voltmane_jackal, torrent_heron). Both
swaps are grid-neutral (cell counts unchanged) and improve/keep Calling honesty. **Updated
`hybrid/hybrid` (target 4):** Aurion (king) + voltmane_jackal + torrent_heron + `champ_marshghast_boar`
(rhino → hybrid/ability, mammoth → hybrid/auto).

**Role-distribution side-effect (flagged, not fixed):** post-T.36 the **champion** roster has
**0 bruiser** (all tanks are intent=utility) and **0 assassin** (phantom_lynx, the lone melee
caster-dealer, flipped int/ability→int/auto = swashbuckler). Enemies still field both (4
assassin), so encounters aren't missing the archetypes, but the champion roster lost two
identities — revisit if we want a champion assassin/bruiser back.

### Coeff guidance per landing cell
- **str/auto, hybrid/auto** — autos carry; ability coeffs modest (utility/steroid). hybrid/auto: STR base + on-hit-INT `Magnitude` (both referenced → V.47).
- **str/ability** (revised — ability is the *main value*, NOT "empowers autos"). The ability hits hard / carries a big effect, but the STR damage-coeff is tuned **well below** the INT baseline because the live STR auto-attack tagalong already pays out. **Parity formula** (vs the INT coeff it replaces): `coeff_str ≈ coeff_int − 0.667·(autos_per_cast)` — autos are `1.85·base` for a str-stat piece vs `0.65·base` for int-stat (`1.0·STR+0.25·INT`, primary weights 1.8/0.2). A ranged caster (~3 autos/cast) lands `coeff_str ≈ 1.1–1.7`; an AoE+CC ability sits at the low end (the CC is the payoff). *Worked example: Mournhollow's old `INT·3.42` AoE → `STR·~1.0–1.4`, not the naive 2.7.* The T.36b `str/ability` rows (#4–6) inherit this — drop their "empowers autos" rationale on build.
- **int/ability** — big INT nuke, `coeff ≈ 3.7 × (cost/300k)`.
- **int/auto** — INT fuels autos (AS-per-INT or on-hit-INT); no STR.
- **hybrid/ability** — `strength*A + intelligence*B` cast (both referenced).

### DPS / HP·DPS fit (T.36a kings — analytic, pre-build)

> **Terminology:** "power" in this codebase is the abstract scalar `scaling.power(T,L)
> = 1.5^((T-1)/2 + (L-1))` (T.18) — *not* used here. The metric below is **HP·DPS** (the
> V.33 worth proxy = effective-fight value), a different quantity. Kept distinct on purpose.

Composed each king's **new** axis statline via `compose_stats(...)` (T10), applied the
locked coeffs + the real cadence (`autos/sec = attack_speed/600`, `casts/sec =
mana_regen·100/300000`, `ENERGY_THRESHOLD=60000`, `DEFAULT_MANA_COST=300000`). Single-
target, mid-fight proxy (Aurion at mid-ramp +60/+60):

| King | axis | autoDPS | abilDPS | TOT(1t) | HP | HP·DPS |
|---|---|---|---|---|---|---|
| Aurion | hybrid/hybrid | 31 | 38 | 69 | 1527 | 105k |
| Nerei | int/ability | 15 | 48 | 63 | 1420 | 89k |
| Borealis | hybrid/ability | 25 | 36 | 61 | 1527 | 93k |
| Umbra | str/auto | 71 | proc 21 | 91 | 1420 | 129k |
| Mournhollow | str/ability | 42 | 53+grief | 104→~90 | 1420 | 147k→~127k (grief 0.6→0.4) |
| Aerion | hybrid/auto | 51 | chain 38 | 89 | 1420 | 126k |

**Reading (validated against the auto-vs-caster literature — autos are "free" sustained
DPS, casters pay it back in burst/AoE/utility):** two healthy clusters — auto-carries
(Umbra/Aerion ~127k) sustain higher single-target; ability-casters (Nerei/Borealis/Aurion
~90–105k single-target) trade for AoE ×2–4 + hard CC (freeze/disarm/fear) → comparable in
teamfights. Single-target proxy *understates* the casters (no AoE multiply, no CC value)
and the carries (uncounted Umbra clones, Aerion +35% AS burst). **Mournhollow ran hot at
grief `0.6` (147k) — trimmed to `0.4` (~127k).** All else in-band. *Non-gating; the real
gate is the engine's V.33 ±10% HP·DPS proxy + `stat_edge.py` sims at build.*

## 6. Content / roster audit + reconciliation

1. **Stale `0.2·INT` in a test comment** — `tests/game/test_content.py:363` comment reads `(1.0 STR + 0.2 INT)`; code is `0.25` (D.25, `context.py:409`). Origin: written at T.35b before the D.25 0.25 bump landed in the same arc. **Fix:** correct the comment in T.36a. (Doc nit, not behavior.)
2. **V.47 guard under-enforces hybrid-STR** (§3) — guard checks INT only; SPEC says hybrid references both. Origin: T.35b guard authored for the dead-INT case only. **Fix + §B backprop** in T.36a; add `test_guard_detects_a_dead_str_hybrid` mirroring the existing dead-INT detector test.
3. **No drift in the axis vocab** — `stat ∈ {str,int,hybrid}`, `playstyle ∈ {auto,ability,hybrid}` confirmed against `_PRIMARY_STAT` + `classify_role`; no dead tokens.
4. **"Permanent" blurbs mislabel in-combat ramps** — `champions.py:559` (Aurion old passive — auto-replaced by *Ascendance*) and `:1146` (`+30 max HP` ramp) say "permanently", but combat is a pure function (V.2) so all piece runtime state resets per `resolve_combat`; nothing persists across battles. **Invariant already holds by construction:** no champion/enemy piece grants cross-combat stat stacking — only augments may permastack across a `Run`. **Fix:** reword the two blurbs to "until end of battle" (`:1146`; `:559` dies with the rework); add candidate **§V** "piece stat stacking is in-combat only; cross-`Run` permastacking is augment-exclusive" + a blurb-wording guard. (User-noted.)

## 7. Open questions

**Resolved here (overridable):**
- Per-piece assignments in §5 — the Calling-honest reshuffle (T.36b table) + the 3 caster→auto flip kits + the 2 role decisions (`Spellslinger` for tempest_eel, utility-INT/damage-STR for marsh_thrush) are all locked via live brainstorm.
- **Aurion** is the kept-hybrid king (Channeler — keeps a cast in a mixed kit). *(Corrected from the earlier draft, which kept Umbra; Umbra is a Stalker = auto-Calling → `str/auto`.)*

**Still open / deferred:**
- D.26 INT-utility support value (needs survivability sim) — not touched.
- Whether to later promote the distribution guard to a hard §V once the roster shape is proven stable (revisit post-T.36b sims).

## 8. Test plan

- **Distribution guard (new, soft).** `tests/game/test_content.py::test_stat_playstyle_distribution` asserts the live matrix equals the target grid. **Self-documenting failure message** (per user):
  > "Roster stat×playstyle distribution changed. This is a *target*, not an invariant — if you intentionally re-axised pieces, re-evaluate whether the new matrix + marginals are still desirable (even str/int parity, populated cells, weak str/ability kept small) and update the target here. Do NOT blindly revert."
- **V.47 (extended).** `test_int_and_hybrid_units_reference_int` stays green; **add** hybrid-STR enforcement + `test_guard_detects_a_dead_str_hybrid`.
- **V.46.** `test_no_orphan_stat_reads` stays green (every rewritten coeff is a `Magnitude`).
- **Proxy band (V.33).** `test_role_intent.py` ±10% HP·DPS holds after re-axis.
- **Role matrix.** Regen `t32_role_matrix.txt`; update `test_role_intent.py` if any role changes.
- **Determinism (V.2/V.14).** Fixed-seed + `workers=1` sims byte-identical *after* the one intended re-baseline per substep; no cadence/RNG mechanic added.
- **Snapshots.** Regen `ability_formulas.snapshot.json` + scaling snapshot (number/text drift expected, reviewed).
- **Balance read (non-gating).** `tools/simulation/stat_edge.py` after each substep — STR/INT `wr_delta` gap should not *widen*; record in journal.

## 9. Acceptance criteria

**T.36a:**
1. All 6 kings carry their §5 axis; 5 leave `hybrid/hybrid` (Aurion stays); matrix matches the post-a table.
2. Each king kit references its primary via `Magnitude`(s); hybrids reference **both** STR and INT.
3. V.47 guard **extended** (hybrid-STR) + new dead-STR-hybrid detector test; both green. Stale `0.2` comment fixed.
4. Snapshots/role-matrix regen; full suite green; sims byte-identical post-rebaseline.

**T.36b:**
1. The 12 §5 moves applied; live matrix equals the **target grid exactly** (verified by the new distribution guard). Every move's playstyle honors its Calling; the 3 Calling tweaks (`snowpelt_cub`+Bruiser, `granite_gorilla`+Bruiser, `eclipse_jaguar` restore Stalker) are the only trait edits, and the overall auto/cast Calling balance does not degrade.
2. Every re-axised int/hybrid piece passes V.47; str/ability pieces follow the revised guideline — **ability is the main value, STR coeff below the INT baseline** (parity formula §5), not "empowers autos" (review).
3. Proxy band, V.46, determinism, snapshots all green.
4. `stat_edge` STR/INT gap does not widen vs pre-T.36 baseline (recorded, non-gating).

## 10. SPEC changes needed (apply via `/spec` after approval)

- **New §T.36a** — *Primordial diversification — re-axis + kit-rewrite the 6 T10 kings into 6 distinct apex archetypes (Calling-honest: Aurion keeps hybrid/hybrid, Nerei int/ability, Borealis hybrid/ability, Umbra str/auto, Mournhollow str/ability, Aerion hybrid/auto); extend the V.47 guard to enforce hybrid→both STR+INT; fix stale 0.2 test comment.* Files: `game/content.py`, `game/abilities/champions.py`, `tests/game/test_content.py`, `tests/game/test_role_intent.py`, snapshots. Depends: T.32, T.35a, T.35b. Est: M. Status: 📋 Plan.
- **New §T.36b** — *Roster distribution re-axis — Calling-honest re-axis + kit-rewrite of 12 non-king champs to land the 22/22/16 target grid; add 3 minimal Calling tweaks (`snowpelt_cub`+Bruiser, `granite_gorilla`+Bruiser, `eclipse_jaguar` restore Stalker [doc/code drift fix]) so the cast-skewed pool fills the auto-heavy cells without playstyle-vs-Calling misfits; add the new `Spellslinger` role (below); add the self-documenting distribution guard test.* Files: `game/content.py`, `game/abilities/champions.py`, `tests/game/test_content.py`, `docs/design/tasks/t32_role_matrix.txt`, `tests/game/test_role_intent.py`, snapshots. Depends: T.36a. Est: L. Status: 📋 Plan.
- **New role `Spellslinger` + amend V.32** — add `Spellslinger` to `ROLE_TITLES` and a branch in `classify_role`: `reach==ranged AND playstyle=="hybrid" AND intent=="damage"` (checked before the final mage/marksman line). Fills the ranged playstyle-hybrid hole (the ranged analog of `spellblade`'s stat-hybrid catch). Regen `t32_role_matrix.txt` + role tests. (T.36b — `tempest_eel` is the first occupant.)
- **Amend V.37** — append: Primordials are no longer pinned to a shared `hybrid` axis; each T10 is a distinct apex archetype (still exactly one per Kinship + Primordial trait). (T.36a)
- **Amend V.47** — note the guard now enforces `hybrid`→**both** STR+INT (was INT-only); cite `TestAxisScalingAlignment` covering str-hybrid + int-hybrid. (T.36a)
- **§B backprop** — new entry: "V.47 guard under-enforced — checked INT only, never verified hybrid pieces reference STR (since T.35b); T.36a closes it." Optionally cite the stale `0.2` comment.
- **New §V (candidate)** — *piece stat stacking is in-combat only; cross-`Run` permastacking is augment-exclusive.* Holds today by V.2 pure-combat construction (runtime state rebuilds per `resolve_combat`); lock it + reword the two "permanent" blurbs (`champions.py:559`/`:1146`) to "until end of battle". Add a blurb-wording guard. (User-noted; see §6.4.)
- **§D.25** — mark consumed/closed by T.36 (the tuned coeffs are now spent in the redesigned kits); D.26 stays open.
- **Implementation Order** — place T.36a then T.36b after T.35b.

## 11. LIVING docs to update (in the landing commits)

- `docs/live/content/rosters.md` — new stat×playstyle distribution + the 6 king archetypes (per substep).
- `docs/live/content/abilities.md` — rewritten kits for the re-axised pieces.
- Run `/check` after each substep — stale living doc is a bug.

## 12. T.36c — role + trait distribution reconciliation (settled target + method)

T.36a/b lock the **stat×playstyle grid** but leave the **role distribution** lopsided
(over: support/tank/swashbuckler; empty: assassin/bruiser; thin: spellblade/spellslinger).
T.36c gently reconciles **three distributions at once** — role · stat-playstyle (fixed) ·
traits (the free variable, fit last) — so every role, including the off-roles, is populated
for champions (and enemies). **Gentle, not strict:** soft targets, prefer identity-fitting
single-lever moves.

### Role-reachability ceiling (the structural finding)

The **grid-neutral ceiling** = how many pieces can *ever* reach a role via intent/durability
flips alone (grid untouched). It exposes that the caster-heavy grid (int/ability=12) **couples
to roles** — martial roles are body-starved:

| role | baseline (champ) | grid-neutral ceiling | note |
|---|---|---|---|
| bruiser | 0 | 56 | trivially fillable (any melee → tanky+damage) |
| **assassin** | 0 | **5** | hard cap — only 5 melee-ability bodies, **all tanky→squishy (identity-breaks)**; no clean body |
| **spellslinger** | 3 | **4** | the 4th body is **Aurion** (locked king) → +1 needs a grid touch |
| spellblade | 3 | 10 | room |
| marksman | 6 | 10 | room |
| mage | 8 | 19 | room |

### Settled target role distribution (soft — user-ratified)

| role | champ target | enemy target | baseline (champ / enemy) |
|---|---|---|---|
| tank | 8 | 9 | 13 / 13 |
| support | 10 | 9 | 15 / 12 |
| swashbuckler | 8 | 7 | 12 / 6 |
| mage | 8 | 9 | 8 / 10 |
| marksman | 7 | 7 | 6 / 5 |
| bruiser | 6 | 6 | 0 / 0 |
| **assassin** | **2** | 5 | 0 / 4 |
| spellblade | 7 | 4 | 3 / 10 |
| **spellslinger** | **4** | 4 | 3 / 0 |
| **total** | **60** | **60** | 60 / 60 |

**Two ceiling-driven decisions (user-ratified):**
- **assassin = 2** (not 3) — no clean assassin body exists (all 5 are Guardian/Channeler
  tank→squishy conversions = identity-break + Calling re-fit). Gentle floor; freed slot → spellblade 7.
- **spellslinger = 4** (not 3) — accept **one deliberate grid touch** (a ranged hybrid-ability
  support → hybrid-playstyle + damage = the 4th body), since the only grid-neutral 4th is the
  locked king Aurion. ±1 hybrid-row drift on the **soft** distribution guard (not §V) — acceptable.

Floors: every role ≥2 (all off-roles live); the support/tank/swash hoard broken (15/13/12 → 10/8/8).

### The dependency chain (the order of operations)

**grid (fixed) → set reach/durability/intent to hit the role target → fit Callings to the
resulting playstyle → gentle Kinship rebalance → rebuild kits to the new identity.**

Role = `f(stat, reach, durability, playstyle, intent)`. The grid pins stat×playstyle, so the
**grid-neutral levers are `intent` and `durability`** (and `reach`, more core). Traits are
fit *after* (a Calling is chosen to match the final playstyle, Calling→playstyle).

### Achievability + the assassin problem

Grid-neutral single-lever refits are **abundant** for bruiser/spellblade/spellslinger/marksman
(an `intent` or `durability` flip on an over-pop donor, identity-fitting):
- **bruiser** (need +4) — `tank → bruiser` (intent→damage) on Bruiser-calling tanks:
  `glacierback_mammoth`, `marshghast_boar` (done), `thunderhide_bison`, + 1 (e.g. `thunderclap_gorilla`).
- **spellblade** (+2) — `swashbuckler → spellblade` (intent damage→hybrid) on hybrid-stat strikers.
- **spellslinger** (+1) — covered by the T.36b tweaks (3 already); +1 from a ranged hybrid-play support.
- **marksman** (+1) — a ranged auto/hybrid support → damage.

**`assassin` is the structural hard case.** Assassin = `melee + ability + non-tanky + damage`,
but **every melee+ability champion is a *tank*** (Guardian/Bruiser) — there are **no natural
squishy-melee-casters**. So the only grid-neutral assassins come from either:
- **(a)** jarring `tank → squishy assassin` conversions (durability+intent flip on a caster-tank
  — a big identity break, *not* gentle), or
- **(b)** paired **swash↔mage playstyle swaps** within a stat row (a melee striker gains the
  cast → assassin; a ranged mage drops to auto → marksman) — grid-neutral but **2 kit reworks
  per assassin**, and pushes marksman up (so pair with the marksman target).

→ Decision pending: **assassin floor** (4 via swaps, or lower to 2-3 to stay gentle). The best
swap donors are the assassin-*flavoured* melee strikers already squishy (Stalker/Trickster):
`nightglass_mantis`, `voltscale_mamba`, `mirage_caracal`, `duskstep_marten`, `phantom_lynx`
(was an assassin pre-T.36) — each swapped against a ranged mage that can carry autos.

### Trait reconciliation (fit last)

- **Callings** follow the final playstyle (Calling→playstyle); AUTO≈CAST balance preserved
  (now 34/33). A role refit that changes playstyle gets its Calling re-fit.
- **Kinship** gentle-rebalance toward ~10 each (Beast 14 over; Swarm 8 under) — only where it
  doesn't fight a piece's locked identity.

### Enemies (parallel pass)

Same method; **enemies are freer** (no stat×playstyle grid contract; tags opaque per V.22).
Fill enemy `bruiser` (0→6) from aggressive tanky melee (`heavy_knight`, `sergeant_at_arms`,
`dredge_hulk`, `quarried_behemoth`, brutes — intent→damage; keep defensive walls
`glacier_goliath`/`slag_sentinel`/`stone_warden` as tank); fill `spellslinger`/`assassin`
likewise. Trim over-pop tank/support/spellblade.

### Scope

New **T.36c** (depends T.36b). Re-axis = intent/durability (+ a few reach/playstyle swaps),
trait re-fit, kit rebuilds for moved pieces, snapshot + role-matrix regen, distribution-guard
update. Est L. **Open:** the assassin floor (swap-cost vs gentleness) — settle before picking.

## 13. Unified axis-distribution solve — SUPERSEDES the §5 T.36b table + §12 T.36c

**Reframe (user-driven):** we were fighting *two* grids — the stat×playstyle contract AND a
role-distribution target. But **role is a pure function of the axes** (V.32), so optimize the
**axis distribution** directly and role falls out for free. One objective, not two.

### The structural findings (why this is the right frame)

1. **Role-volume is unequal** in axis-space (of 216 stat·play·reach·dur·intent combos): tank
   33% · support 17% · bruiser 14% · swash 9% · mage/marksman/assassin/spellslinger 6% ·
   spellblade 4%. → even *perfectly balanced axes* yield a **frontline-weighted, assassin-rare**
   roster. **That is correct, not a flaw** — it matches gameplay (field several frontliners,
   1-2 assassins). So we **stop targeting equal roles**; accept the natural shape, only enforce
   soft floors so no off-role is empty.
2. **Marginals alone are insufficient** — a min-change solve hitting every marginal still left
   assassin=1, because the *degenerate correlations* persisted (all melee+ability pieces were
   tanky → the squishy-melee-caster corner stayed empty). **The joint matters** → the solve must
   carry role floors as constraints in the *same* objective.
3. **The real ad-hoc artifact = `durability`**, wildly skewed (hybrid **35**/60, tanky_arm **3**)
   — a glut of middling-durability pieces, almost no armor-tanks. No role-first approach surfaces
   this; the axis view does. *This is the "which archetypes are over/under-represented" answer.*

### Target axis marginals (design — user-ratified)

| axis | target |
|---|---|
| stat | str 22 · int 22 · hybrid 16 (D.25 parity held) |
| playstyle | auto 24 · ability 24 · hybrid 12 |
| reach | melee 30 · ranged 30 (even frontline capacity) |
| **durability** | tanky_hp 11 · **tanky_arm 8** · squishy 13 · hybrid 28 (fixes the skew) |
| intent | damage ~26 · utility ~22 · hybrid 12 (slight dealer lean; solve drifts to ~29/19/12 to meet floors — soft) |

Role floors (soft, in-objective): assassin/spellblade/spellslinger ≥4, bruiser ≥6, marksman ≥5,
mage ≥6, swash ≥6, support/tank ≥8; caps tank ≤12, support ≤11. Stat-parity `|str−int| ≤ ~0`.

### Solve result (kings + 3 flip kits PINNED, other 51 free)

Greedy min-change over single-axis flips, multi-restart. **Cost 6, 20 non-king changes.**
**Emergent role distro:** tank 12 · support 11 · swash 7 · mage 7 · bruiser 6 · marksman 5 ·
assassin 4 · spellblade 4 · spellslinger 4 = 60. All marginals hit; all roles ≥4; frontline-weighted.

### Starting change-list (20 — to be IDENTITY-CURATED, not gospel)

The solver minimized *count*, not identity, so some picks are jarring (e.g. `ember_salamander`
fire-mage → melee/str). The solve **proves feasibility + fixes the marginals/roles**; the
per-piece pass swaps *which* piece fills each cell for identity fit (as we did for the kings),
**holding the marginals**. The 20 movers it found (durability/intent/reach/playstyle/stat flips):
`dawnwisp, veldt_pronghorn, ember_salamander, goldcrest_lark, aegis_tortoise, sunmane_lion,
goldhide_rhino, mirage_caracal, sunspear_falcon, springfrog, reedbank_otter, torrent_heron,
grovekeeper_tapir, coral_colossus, snowpelt_cub, permafrost_walrus, frostplate_tortoise,
iceclaw_lynx, duskstep_marten, nightglass_mantis`.

### Workflow (one task now)

1. **Settle target marginals** (above) — done.
2. **Solve** for emergent roles + feasibility — done (cost 6, 20 changes).
3. **Identity-curate** the per-piece assignment (swap occupants for lore/kit fit; hold marginals).
4. **Fit traits** — Callings→playstyle honest (Calling fixes playstyle); gentle Kinship rebalance
   (Beast 14→~10); the trait is the free variable.
5. **Rebuild kits** for every moved piece (one at a time, king-style) to its new identity.
6. Snapshot + role-matrix regen; distribution guard becomes an **axis-marginal** guard (soft);
   `stat_edge` read; V.33/V.47 hold.

**Restructure:** the §5 T.36b 12-piece table + the §12 T.36c role-reconciliation are **superseded**
by this single solve. New task shape: **T.36a** (6 kings — unchanged) → **T.36b** (unified roster
axis-distribution solve: the ~20-change curated re-axis + trait-fit + kit rebuilds). T.36c folded in.

### Enemy parallel solve (same method, 60 enemies)

Enemies carry the **same durability skew** (hybrid 36/60, tanky_arm 3) — the ad-hoc artifact
is roster-wide. Enemies are freer (no D.25 stat-parity contract; tags opaque, V.22), so the
solve targets the same marginals + role floors, min-change, no pins (bosses are separate in
`game/bosses/`, not in the 60).

**Result: cost 8, 21 changes.** Marginals all hit (stat 22/22/16, playstyle 22/22/16, reach
30/30, durability 11/8/13/28, intent ~30/18/12). **Emergent enemy roles:** tank 12 · support 11
· spellblade 6 · bruiser 6 · swash 6 · mage 6 · marksman 5 · assassin 4 · spellslinger 4 = 60 —
every role ≥4, **bruiser 0→6 and spellslinger 0→4 filled**, spellblade 10→6 / mage 10→6 / tank
13→12 trimmed. Same **identity-curation** caveat as champions (raw solver output picks by count
— e.g. `field_medic` ranged→melee, `conscript` str→int are jarring; curate the occupants for
identity while holding the marginals). The 21 raw movers:
`conscript, levyman, picket, stretcher_hand, signal_drummer, pikeman, crossbow_levy,
field_medic, powder_sapper, sergeant_at_arms, heavy_knight, steam_engineer, company_guard,
inquisitor, iron_maiden, archmagus_imperator, blight_lurker, maw_of_the_drowned, flood_tyrant,
drained_stalker, stormhawk`.

**Both rosters now have a proven target** (champ ~20 + enemy 21 curated re-axes). Next: identity-
curate occupants (champ + enemy), fit traits, rebuild kits — then build.

### Curated champion assignment (identity-fit, all 3 distros checked) — LOCKED draft

Curated the off-role occupants by **existing Calling/lore** (not the solver's count-min picks),
then ran a marginal-cleanup with **caster identities protected** (Menders/Mystics held
ranged+ability so the solver couldn't shove healers to auto/melee). **Cost 2 — fits the bill:**

- **Axis marginals:** stat 22/22/16 ✓ · playstyle 24/24/12 ✓ · reach 30/30 ✓ · durability
  11/8/13/28 ✓ · intent 27/21/12 (±1). Durability skew **fixed** (was hybrid 35 / arm 3).
- **Roles (emergent):** tank 12 · support 11 · bruiser 7 · mage 7 · swash 6 · marksman 5 ·
  assassin 4 · spellblade 4 · spellslinger 4 = 60 — every role ≥4, frontline-weighted.
- **Calling-honesty:** clean but for 2 minor donor artifacts — `torrent_heron` (Mystic) and
  `coral_colossus` (Mender) got pushed to auto; final fix = make torrent the spellslinger it
  wants (Mystic ranged), accept coral as a Guardian-tank (Guardian dominant).
- **Kinship:** unchanged by re-axis → **Beast still 14** (over). Gentle rebalance to ~10 is a
  separate tag-swap lever (swap a Kinship on ~3-4 Beast pieces where lore allows) — pending.

**Off-role fills (all lore/Calling-honest):**
- **bruiser** (Bruiser-calling, intent→damage): sunmane_lion, glacierback_mammoth, marshghast_boar,
  thunderclap_gorilla, thunderhide_bison, wraithorn_stag (+1 donor)
- **assassin** (Stalker squishy, playstyle→ability = the ambusher's burst): mirage_caracal,
  nightglass_mantis, voltscale_mamba, riptide_caiman
- **spellslinger** (auto+cast Callings): storm_eagle (Hunter·Channeler), voltmane_jackal,
  tempest_eel, cliffeyrie_eagle
- **spellblade** (dual-stat strikers): aurion*, eclipse_jaguar (Stalker·Channeler), aerion*, thunderhoof_colt

**Scope:** 36 axis-changes; 24 move stat/playstyle (kit rebuilds) — **9 are the designed
kings+flips → ~15 genuinely new kit rebuilds**; the other 12 are intent/durability relabels
(no kit-scaling change). Note: this is a **roster-wide rebalance**, not the original 18-piece
edit — the cost of fixing the durability skew + populating every role lore-honestly.

**Remaining before build:** (1) the 2 honesty fixes (torrent/coral); (2) Beast Kinship
rebalance; (3) the enemy curation (same pass on the 21 enemy movers); (4) per-piece kit rebuilds.

### Curated ENEMY assignment + honesty/Kinship resolution

**(1) Champion honesty fixes:** `torrent_heron` → protected as a ranged mage (Mystic, not
auto); `coral_colossus` → accepted as a Guardian-tank (Guardian dominant over its Mender,
frontline auto is fine). Both resolved.

**(2) Kinship rebalance — NOT done (reasoned).** Kinship is **animal-locked**: every Beast
piece is a mammal (lion/mammoth/gorilla/bison/colt…); none can become Swarm (insects) or any
other Kinship without re-theming the animal, and a swap also breaks the affinity×tier content
grid + trait synergies (V.37 one-Primordial-per-Kinship, emblems V.22). So a *gentle* Kinship
rebalance doesn't exist — Beast 14 / Swarm 8 (range 8-14, all ≥8) is the natural animal-determined
spread. Forcing it = content re-theme, out of scope for an axis rebalance.

**(3) Enemy curation (cost 2 — fits the bill).** Enemies carry opaque tags not Callings (V.22),
so curated by **name/lore**: protect caster-named enemies (medics/chaplains/magi/diviners stay
ranged+ability), fill bruiser from aggressive brutes, spellslinger from battlemage-types.
- **Axis marginals:** stat 22/22/16 ✓ · playstyle 22/22/16 ✓ · reach 30/30 ✓ · durability
  11/8/13/28 ✓ (skew fixed) · intent 27/21/12 (±1).
- **Roles:** tank 12 · support 11 · spellblade 6 · bruiser 6 · mage 6 · swash 6 · marksman 5 ·
  assassin 4 · spellslinger 4 = 60 — all ≥4.
- **bruiser fills:** blight_lurker, brineblight_berserker (berserker!), dredge_hulk,
  quarried_behemoth, cold_iron_yeti, sergeant_at_arms. **spellslinger fills:** `battlemage`
  (literal), reaver_of_the_reach, stormhawk, drained_stalker. **assassins kept:** hollowed_wisp,
  shaftmaw, hexblade_officer, spymaster.
- **Scope:** 30 enemy changes, 15 kit rebuilds.

### Combined T.36b scope (both rosters)

| | axis changes | kit rebuilds (stat/play) |
|---|---|---|
| champions | 36 | 24 (9 = designed kings+flips → ~15 new) |
| enemies | 30 | 15 |
| **total** | **66** | **~39** (~30 new) |

This is a **roster-wide rebalance** — far beyond the original 18-piece T.36 — the cost of
deriving the whole roster from a principled axis distribution + fixing the durability skew +
populating every role lore-honestly. Both rosters now fit all 3 distros within ±1, lore-honest.
**Remaining = the per-piece kit rebuilds** (the build itself) + snapshot/role-matrix regen.

## 14. Build structure — the 3-task split + what needs doing

Full roster-wide build (user-confirmed). Split along the cleanest seam — **kings / champions
/ enemies** — separate files, each ships green + tests independently, each is one deterministic
re-baseline.

### T.36a — Primordial kings (6) · Est M

The 6 designed king kits (plan §5 "T.36a CORRECTED" table). Self-contained, highest-identity.
- **Axis edits:** the 5 king stat/playstyle moves (Aurion stays h/h) in `content.py`.
- **Kit rebuilds (6):** Aurion *Ascendance*, Nerei *Grudge of the Flood* (+`nerei_grudge` status),
  Borealis *Blizzard* (frozen +15%), Umbra *Hungering Shadow*, Mournhollow *Haunting Mist*
  (+`grief` DoT status), Aerion *Overcharge*/*Skybreaker*.
- **Guards:** extend V.47 (hybrid→both STR+INT) + dead-STR-hybrid test (B.24); fix stale `0.2`
  comment; new `grief`/`nerei_grudge` StatusDefs.
- **Regen:** snapshots + role-matrix; `stat_edge` read. **Ships:** kings rebuilt, suite green.

### T.36b — Champion roster rebalance (~36 axis edits, ~15 new kit rebuilds) · Est L

Apply the curated champion assignment (§13) — hits the target marginals + role floors. The 9
kings+flips are already designed (T.36a + flip kits); this is the **other ~15 kit rebuilds**,
organized by **role-batch** (each batch shares one identity rule from
`docs/live/systems/kit_design_conventions.md`):

| batch | pieces (reference — finalize at build) | rule |
|---|---|---|
| **bruiser** (6) | sunmane_lion, glacierback_mammoth, marshghast_boar, thunderclap_gorilla, thunderhide_bison, wraithorn_stag | Bruiser-calling; intent→damage (+dur→tanky); melee STR brawler, ability = modest |
| **assassin** (4) | mirage_caracal, nightglass_mantis, voltscale_mamba, riptide_caiman | Stalker squishy; playstyle→ability = the ambush burst; scoped sustain (conventions #10) |
| **spellslinger** (4) | storm_eagle, voltmane_jackal, tempest_eel, cliffeyrie_eagle | ranged hybrid-play; cast primary + on-hit/auto tail (battlemage) |
| **spellblade** (4) | aurion*, eclipse_jaguar, aerion*, thunderhoof_colt | dual-stat both-coeff (V.47-hybrid) |
| **relabels** (~12) | intent/durability/reach-only movers | NO kit-scaling change — statline + role relabel only |

- **Protect casters** (Menders/Mystics stay ranged+ability — don't let the data edit push
  healers to auto/melee). **marsh_thrush** utility-INT/damage-STR. **2 honesty fixes**
  (torrent→mage, coral→Guardian-tank).
- **New `Spellslinger` role** (amends V.32) + soft **axis-marginal/distribution guard** (not §V).
- **Regen** snapshots + role-matrix; `stat_edge` champ read. **Ships:** champ roster fits all 3
  distros (±1), V.33/V.46/V.47 green, enemies untouched.

### T.36c — Enemy roster rebalance (~30 axis edits, ~15 kit rebuilds) · Est L

Same method on the 60 enemies (§13 enemy curation) — curated by **name/lore** (opaque tags,
V.22; no D.25 parity). Bruiser fills from brutes (berserker/hulk/behemoth), spellslinger from
battlemage-types, caster-named protected. Hits the same marginals + floors.
- **Kit rebuilds (~15)** in `abilities/enemies.py` (same role-batch rules). **Regen** snapshots
  + role-matrix; `stat_edge` full read. **Ships:** enemy roster fits; full suite green.

### Order, determinism, acceptance

**Order:** T.36a → T.36b → T.36c (enemies last — sims run champ-vs-enemy, so stabilize champs
first). Each = **one re-baseline** (snapshots/sims byte-identical after the intended shift; no
RNG, V.2/V.14). **Per-task acceptance:** target marginals hit (±1); all roles ≥4; V.33 ±10%
HP·DPS band holds; V.46 (no orphan stat reads) + V.47 (axis↔scaling, incl. hybrid→both) green;
role-matrix regenerated; `stat_edge` STR/INT gap not widened. **Per-piece axes are the §13
reference solve** — build may swap occupants within the marginal/floor constraints + the
conventions-doc identity rules (the solve is a feasibility proof + target, not frozen).
