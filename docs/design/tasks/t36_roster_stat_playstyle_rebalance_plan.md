# T.36 Plan — Roster stat/playstyle rebalance + Primordial diversification

> **Status:** ✅ **BUILD-READY (2026-06-15, rev 2)** — supersedes the
> 2026-06-15 first-pass draft. Decisions ratified with the user: full draft grid
> (22/22/16), split **T.36a** (Primordials) / **T.36b** (distribution), and a
> **self-documenting distribution guard test** (pins the target but is explicitly
> *not* a true invariant — see §8). Per-piece moves are now fully enumerated and
> delta-verified to land the target grid exactly. **Per-piece axis assignments
> remain tunable** (lore/kit fit) — the cell *counts* are the contract, the
> *which-piece* is the proposal.

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
| 11 | `champ_voltmane_jackal` | Beast · **Skirmisher**·Channeler | hybrid/hybrid | **hybrid/auto** | ✓ Skirmisher=auto |
| 12 | `champ_grovekeeper_tapir` | Tidekin · Bruiser·**Mender** | hybrid/hybrid | **hybrid/ability** | ✓ Mender=cast (caster-mender tank; was hybrid/auto — swapped with eclipse to preserve its auto-soul) |

**The 3 Calling tweaks** (minimal trait edits to fit the cells): `snowpelt_cub` gains
**Bruiser** (tanky brawler), `granite_gorilla` gains **Bruiser** (gorilla brawler),
`eclipse_jaguar` **restores Stalker** (it is in the roster doc, dropped from code — this
tweak doubles as a doc/code drift fix). All Beast pieces, all auto-Callings, lore-natural.
No other traits change.

**Stays `hybrid/hybrid` (target 4):** **Aurion** (king) + `champ_goldhide_rhino`, `champ_marshghast_boar`, `champ_glacierback_mammoth`.

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
