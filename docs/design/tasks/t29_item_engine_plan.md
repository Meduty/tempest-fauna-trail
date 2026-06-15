# T29 Plan — Item Engine

> **Status:** approved — T.29a/T.29b split in SPEC (📋 Plan). **`T.29-pre` ✅ Done (2026-06-13)** — combat stat substrate landed ([Part B](#part-b--t29-pre--combat-stat-substrate-prerequisite-sequences-first)); `T.29-pre → T.29a → T.29b`. ✅ **§3.1a mana primitive RESOLVED (2026-06-14)** — all four tensions decided: **T1 = Option A** (`mana_cost` base on the ability def; deprecate the V.35 `ability_cost` stat — amends V.35); **T2** = mechanical re-grep, not a fork; **T3 = weighted-rank charge cycle** (per-slot `priority` rank; one budget, one slot charged per tick, throughput slot-count-invariant); **T4 = one-cast-per-window (settled) + unified `priority`** (same rank picks the cast). **`max_mana` default raised to `2× mana_cost`** (overload headroom). ⚠️ **CORRECTION 2026-06-14:** T.29a **already shipped** (PR #41, commit `403e7e2`) as the **item engine only** — it did **not** build §3.1a (kept the old `ActiveSlot.cost`/`current_mana` model). So the resolved §3.1a mana primitive is its **own new row T.29c** (depends T.29a, done), and it must **retrofit 3 T.29a mana items that reduce `mana_cost`** (`springtear`/`deepwell`/`everbloom_staff` + `wildfury_lash` clamp — violate V.48). The §3.1b multi-slot + Multicaster work is row **T.29d** (depends T.29c + T.28a). Both 📋 Plan; **applied to SPEC 2026-06-14** (V.48/V.49, T.29c/T.29d rows, V.34/V.35 amends, D.23/D.24). Below, read "§3.1a → T.29c" and "§3.1b → T.29d".
> **Depends:** T.1 (models — done), T.20 (effect substrate / `ITEM_REGISTRY` / `register_item` — done), **T.22** (Amber economy, `Run` shop/inventory — done; drop-table weights **owned by T.29a** per §3.7 decision). **T.29b emblems additionally depend on T.28a** (trait counting consumes emblem `granted_traits`). **T.29b special-item CLI driver shares the `sim_run` interactive shell with T.31** — coordinate. **T.29-pre (substrate) depends only on already-built work (T.2 weather, T.20 effects, T.28d trait riders, T.33a sort-order) — it can build immediately and is a soft prerequisite to T.29a (fixes the `(base+adds)×muls` compose rule + `source:` prefix vocab that item factories author against).**
> **Resolves:** SPEC §D.9 (item system — components, recipes, emblems, special items, 3 slots) and the REWARD-drop half of §D.12.
> **Design source of truth:** [`item_catalog.md`](../content/item_catalog.md) (8 components, 36 combined, 6 emblems, 6 special, the §3 16-item core cut) + [`effect_systems_design.md` §8](../systems/effect_systems_design.md) (substrate: `BASE_COMPONENTS`, `RECIPE_MAP`, item factories, §8.4 run-actions, `combine()`) + §10.1 (application order).
> **What this plan adds beyond those:** the **real component→stat mapping** (the §8 sketch uses fake keys — **flat add chosen over mul**), a small **mana-stat primitive** (rename `ActiveSlot.cost`→`mana_cost` + split into `mana_cost`/`max_mana`/`start_mana` so items express mana **without ever touching `mana_cost`** — §3.1a), the **persistent equip model** (`Champion.items`), and a drift fix for the §8.1 "15 combined" / dangling "§14" references. **Drop-table weights (§D.12)**: T.29a owns a first-pass weight table (components, combined, Amber, champion recruit bucket) — flagged tunable; §3.7.

---

## 0. Substep split (T.29-pre → T.29a → T.29b)

The seam is **combat-facing vs meta/cross-task**. T.29a is self-contained (deps done after T.22); T.29b pulls in T.28 (emblems) and the prep-layer run-action driver. **T.29-pre (substrate, [Part B](#part-b--t29-pre--combat-stat-substrate-prerequisite-sequences-first)) is a stat-engine prerequisite that lands first** — it makes weather a normal `source:`-tagged modifier and turns `attack_speed` into a float (dropping `milli_AS`), so every later system (items, augments) composes through **one** `compute_stat` contract and is uniformly attributable in the prep view.

### T.29-pre — Combat stat substrate (Est: M–L, sequences FIRST) — see [Part B](#part-b--t29-pre--combat-stat-substrate-prerequisite-sequences-first)
- **Commit 1** weather → `source="weather:<state>"` modifiers (delete the `base_stats` fold); HP re-sync via the trait template; `attack_range` floor; standardized `source:` prefix vocab; the `(base+Σadds)×Πmuls` compose rule becomes the universal contract (weather scales item/augment adds).
- **Commit 2** `attack_speed` int→float; drop `milli_AS` everywhere; cadence `int(AS)`, tiebreak `round(AS*1000)`.
- **Also** `stat_breakdown(piece)` pure helper (groups `piece.modifiers` by `source:` prefix) for the T.34/T.23 prep-view breakdown — pure `game/`, no Flet.
- **One re-baseline, two separable commits** (commit 1 re-baselines weather numbers; commit 2 is ~byte-identical by exact migration).

### T.29a — Component + combined-item engine + 16 core items (Est: M–L)
- §3.1 component model + **real-stat mapping** + §3.1a mana-stat primitive (per-ability `mana_cost`/`max_mana`/`start_mana`/`priority`; `max_mana` = universal cap, default 2× cost; MR = cast-rate knob via weighted-rank charge cycle; ≤1 cast/window). ✅ **§3.1a all four tensions DECIDED 2026-06-14 (T1 cost-on-ability-def / T2 re-grep / T3 weighted-rank cycle / T4 one-cast+unified-priority) — build-ready (see §3.1a).**
- §3.2 `RECIPE_MAP` (full 8×8 = 36 keys) + `combine()` (recipes only; gem branch stubbed for b).
- §3.3 equip model: `Champion.items` (≤3, persistent) → threaded into `piece_from_champion`; `Piece.items` already exists ([piece.py:43](../../../src/game/piece.py#L43)); apply item bundles in `compile_loadout` (§10.1 step 5).
- §3.4 `@register_item` factories for the **16 core-cut items** (modifier + hook, closure-per-combat) + 8 raw components.
- §3.7 REWARD-node item drops + boss 3-pair loot (deterministic via `CH_LOOT`; T.29a authors the §D.12 weight table).
- **Files:** `game/items/` (`base.py`, `recipes.py`, `combined.py`), `game/loadout.py`, `game/models.py`, `game/encounter.py`, **`game/piece.py`** (`ActiveSlot.max_mana`/`start_mana`), **`game/combat/engine.py`** (3 mana sites), `game/effects.py` (`EffectBundle.slot_mana_start`), `game/combat/context.py` (`grant_mana`). **Done when:** equip ≤3 enforced, recipes resolve, a hook item (e.g. Splitwind Talons) procs deterministically in a fixed-seed fight, REWARD drop is seed-deterministic, **no-item fights byte-identical (§3.1a regression)**.

### T.29b — Remaining items + emblems + special items (Est: M–L, depends T.29a + T.28a)
- §3.4 the remaining **20 combined items**.
- §3.5 **6 emblems** — `granted_traits` ordering before trait resolution (the contract T.28a established); Spirit-Gem `combine()` branch.
- §3.6 **6 special items** — `register_run_action` registry + functions on `Run`, **+ interactive CLI driver** in `sim_run`.
- §3.4 Spellfang Crown's `ability_can_crit` unlock (reuse the T.28b flag-set idiom).
- **Files:** `game/items/combined.py`, `game/items/emblems.py`, `game/items/special.py`, `game/registries.py` (new run-action registry), `tools/playtest/sim_run.py`. **Done when:** emblem makes a non-native piece count toward a Kinship breakpoint; each run-action mutates `Run` correctly; `sim_run --interactive` can invoke them.

---

## 1. Scope

**In scope:** the full item system backend — 8 components, 36 combined items (16 in a, 20 in b), 6 emblems, 6 special run-actions, 3-slot equip, REWARD-drop integration, and the run-action CLI driver. Backend-first; UI fires it later (T.23 prep).

**Out of scope:** the prep-view item UI (T.23/T.15); any shop item sales — **the shop sells champions only, never items** (T.22 contract, §3.7); authored per-item Heartwood variants (MVP ships a generic stat-mult, §7); bosses wearing items (post-MVP §D, §7).

---

## 2. The gap today

| Piece | Where | State |
|---|---|---|
| `ITEM_REGISTRY` + `@register_item` | [registries.py:27,69](../../../src/game/registries.py#L27) | 🔶 empty dict + decorator, never populated |
| `Piece.items: list[str]` | [piece.py:43](../../../src/game/piece.py#L43) | ✅ combat-runtime field exists; loadout never reads it |
| `Run.inventory: dict[str,int]` | [models.py:580](../../../src/game/models.py#L580) | ✅ bench item counts exist + serialized |
| `Champion.items` (persistent equip) | [models.py](../../../src/game/models.py) | ❌ does not exist — pieces have no persistent equipped items |
| `RECIPE_MAP` / `combine()` / `BASE_COMPONENTS` | — | ❌ none in code (only sketched in §8) |
| `register_run_action` registry | — | ❌ none — special items have nowhere to live |
| Item bundle application in `compile_loadout` | [loadout.py:222](../../../src/game/loadout.py#L222) | ❌ step 5 (item bundles) + step 2 (item `granted_traits`) of §10.1 not implemented |
| REWARD item drops | [encounter.py](../../../src/game/encounter.py) | ❌ `generate_reward` yields enemies only; no loot roll |

`apply_bundle` ([loadout.py:40](../../../src/game/loadout.py#L40)) already applies `modifiers`/`hooks`/`granted_traits`/`statuses`/`granted_abilities` — combined items are just bundles, no new effect machinery. `SourceTag.ITEM_PROC` already exists for proc attribution.

---

## 3. Architecture

### 3.1 Components — real-stat mapping (the §8 sketch is fake)

[effect_systems_design.md §8.2](../systems/effect_systems_design.md) uses **placeholder component ids and stat keys** (`bow/tear/rod`, `ability_power`, `attack_damage`, `mana_max`, `magic_resist`) — explicitly TFT placeholders. Author against the real catalog components and real `Piece.base_stats` keys:

| Component | Catalog stat | Real engine handling |
|---|---|---|
| Fang | Strength | `Modifier("strength", "add", 10, …)` |
| Talon | Attack Speed | `Modifier("attack_speed", "add", 10, …)` |
| Heartseed | Intelligence | `Modifier("intelligence", "add", 10, …)` |
| Old Hide | Health | `Modifier("hp", "add", 100, …)` |
| Stoneplate | Armor | `Modifier("armor", "add", 5, …)` |
| Wardpelt | Resistance | `Modifier("resistance", "add", 5, …)` |
| Keen Claw | Crit Chance | `Modifier("crit_chance", "add", 0.15, …)` (0–1 float) |
| **Springtear** | **Mana regen** | `Modifier("mana_regen", "add", 40, …)` — a **real piece `base_stat`** (loadout.py:80, read engine.py:822). Clean Modifier, no slot mutation. (Reflavor catalog "Mana (start/cost)" → "Mana regen"; §6.) |

**Magnitude: flat add** (TFT-style). A +10 Fang is meaningful at T1 (~+20% STR) and weaker at T10 (~+2.5% STR) — that's intentional; items favour early/mid. Flag all values as first-pass; retune via sim. `crit_chance` and `mana_regen` already use flat by nature.

**Mana items never reduce `mana_cost`** (decision §4). The two — and only two — mana item effects are **(a) mana regen** (pure piece-stat Modifier, above) and **(b) starting mana** (per-slot `start_mana`, §3.1a). `mana_cost` stays a fixed per-ability/per-boss tuning knob; nothing equips against it. This removes the negative-cost stacking bug at the source.

### 3.1a Mana-stat primitive — `mana_cost` / `max_mana` / `start_mana` (per-ability slot)

> ✅ **RESOLVED 2026-06-14 — build-ready.** The mana model was reworked 2026-06-13
> (post-T.29-pre); all **four** tensions are now decided (see the per-tension blocks below,
> each headed **DECIDED**): **T1 Option A** (`mana_cost` on the ability def, deprecate the
> V.35 `ability_cost` stat), **T2** mechanical re-grep, **T3 weighted-rank charge cycle**,
> **T4 one-cast-per-window + unified `priority`**. **`max_mana` default = `2× mana_cost`.**
> Authoring a multi-ability kit = two numbers per slot (`mana_cost`, `priority`); cost is the
> **ability** knob, `mana_regen` the **piece** knob. Implement the engine sites below per the
> DECIDED rules (not the old full-MR-to-every-slot assumption).

**Settled model.** Four mana fields are **per-ability/per-slot** (they live on the
ability/`ActiveSlot`, alongside the existing `current_mana`); **`mana_regen` is the
one piece-level stat** and the **intended cast-rate knob** (the only `Modifier`-able
mana value — Springtear etc.). `max_mana` is the **single universal pool cap** —
every clamp (regen, start, on-event grants) is to `max_mana`. The old "regen guarded
at `mana_cost`" is **dropped**; the old 5×-default and the `max_mana = max(max_mana,
start_mana)` **auto-bump are dropped** — `max_mana` is a deliberate, authored,
**rarely-changed** cap.

| Field | Base authored on | Mutable by | Role |
|---|---|---|---|
| `mana_cost` | **ability def** (T1 Option A; deprecates V.35 `ability_cost`) | ability/augment (rare) | cast threshold + amount deducted per cast — **the ability cost knob** |
| `max_mana` | ability def | ability/augment (rare) | **universal pool cap** — everything clamps here; never auto-raised. **Default `= 2× mana_cost`** (overload headroom) |
| `start_mana` | ability def | ability/augment (rare) | combat-start fill (clamped to `max_mana`) |
| `priority` | ability def (per-slot rank, default `1`) | — | **unified rank** — drives both the T3 charge cycle **and** the T4 cast pick |
| `current_mana` | runtime | engine | per-slot pool |
| `mana_regen` | champ/enemy def (stat) | **`Modifier`s** (items/weather/traits) | fills the **rank-cycle-selected** slot's `current_mana` → `max_mana` each tick; **the piece-level cast-rate knob** |

- **Defaults for all fields — required even when a def specifies them.** Every field has a
  fallback default so a partial def still constructs: `mana_cost` default = the old baseline
  constant (`300_000`, the former V.35 `ability_cost` baseline — now the `mana_cost` default),
  `max_mana` **default = `2× mana_cost`** (overload headroom; abilities author higher/lower),
  `priority` default = `1`, `start_mana = 0`, `current_mana = 0`, `mana_regen` = champ/enemy
  base (V.35 `100`). Defs override; defaults always exist.
- **Engine sites — drop the MR guard + add the rank cycle + single-cast gate:**
  - **regen — weighted-rank charge cycle (T3 DECIDED):** maintain a per-piece deterministic
    cycle counter (cadence, V.2/V.14 — like `crit_counter`). Cycle length = `sum(slot.priority
    for slot in actives)`; each slot occupies `priority` positions. Each tick advances the
    counter and routes the **full** piece `mana_regen` to the **one** selected slot:
    `slot.current_mana = min(slot.max_mana, slot.current_mana + mr_val)` (was `min(slot.cost,
    …)`, engine.py:831). **`max_mana` is the clamp** (overload banks). **Skip rule:** if the
    cycle-selected slot is already at `max_mana`, advance to the next cycle position with a slot
    that has room (still deterministic). One slot charged per tick ⇒ total throughput =
    `mana_regen`/tick **regardless of slot count** (the T3 invariance constraint). Single-slot
    pieces: cycle len = that slot's `priority`, every tick charges it = full MR/tick = today.
  - **cast — one per window + unified priority (T4 DECIDED):** at most **one** cast per action
    window. Among slots with `current_mana >= mana_cost`, the **highest `priority`** casts
    (tie → lowest slot index, deterministic); `slot.current_mana -= slot.mana_cost` (was
    `= 0.0`, engine.py:486,663) so overflow carries. Other ready slots stay ready for later
    windows (no burst).
  - combat start (new) → `slot.current_mana = min(slot.max_mana, slot.start_mana)`.
  - ready check unchanged per-slot: `slot.current_mana >= slot.mana_cost` (engine.py:463,657)
    — selection among multiple ready is the unified-priority pick above.
  - **`ctx.spend_mana` removed (2026-06-15):** it set `current_mana = 0.0` (a dead method
    after the inline `-= mana_cost` cast paths, and its reset semantics now violate the
    overflow-carry rule). Cast deduction lives only at the two cast sites.
  - **Per-ability cost is fully supported** — `ABILITY_MANA[ability_id].mana_cost` is
    authored per ability (e.g. `register_active("...", mana_cost=120_000)` or boss
    registration), so two abilities (or two pieces) carry independent costs; only the
    *default* (`300_000`) is shared. Different cost ⇒ different fill time ⇒ different cast
    cadence (cheap = quick, heavy = slow), reinforced by the flat start-mana grant.
- **Resources, not modifiers (V.43).** `mana_cost`/`max_mana`/`start_mana`/`current_mana`
  are **slot resource state** — mutated by **explicit, rare** ability/augment effects via
  **direct slot writes**, never `Modifier`s (V.43 codifies this). Only `mana_regen` (flow
  stat) is `Modifier`-able. **Mana items grant `mana_regen` or `start_mana` — never reduce
  `mana_cost`** (kills the negative-cost stacking bug). ⚠️ **Retrofit (T.29c finding 2026-06-14):**
  T.29a shipped **3 mana items that violate this** via `combined.py:69 _apply_mana_to_slots(...,
  cost_mult<1.0)` → `slot.cost = round(slot.cost * cost_mult)`: **`springtear`** (`0.90` + 200 mana —
  the very item V.48 cites as the canonical *pure-`mana_regen`* item), **`deepwell`** (`0.80` + 400
  mana + on-cast cost refund `:206`), **`everbloom_staff`** (`0.90` + 200 mana). Also
  `wildfury_lash:350` sets `current_mana = cost` (should clamp to `max_mana`). T.29c rewrites these:
  grant `mana_regen` (`Modifier`) and/or `start_mana` (slot), delete the `cost_mult` path, reclamp
  current-mana writes to `max_mana`.
- **Regression / byte-identity (verify, don't assume).** With `max_mana = 2× mana_cost`,
  `start_mana = 0`, single-slot pieces (≈ the whole current roster): the cycle has one slot,
  so it charges every tick exactly like today; passive regen (baseline `100`/tick vs cost
  `300_000` → ~3000 ticks/cast) **never approaches `2× cost`**, so the raised cap is never hit
  by regen alone; a slot casts the tick it crosses `mana_cost`, leaving sub-`mana_regen`
  overflow, `-= mana_cost` ≡ old `= 0` within rounding → **expected byte-identical**. The 2×
  headroom only bites for `start_mana` items / on-event grants / multi-slot banking. **Gate
  (lesson from T.29-pre):** capture a pre-change baseline and diff — *prove* byte-identity
  empirically; the AS-float "~byte-identical" claim was wrong, and raising the cap to 2× is a
  behavioral change for any banking path, so do **not** trust this paragraph — verify.
- **Starting-mana items:** equip step does `slot.start_mana += S` (clamped: `start_mana`
  seeds `current_mana = min(max_mana, start_mana)` at combat start — **no `max_mana`
  auto-bump**; if `start_mana > max_mana` it is simply clamped). One slot-writing path,
  carried on the bundle via `slot_mana_start` (§3.4).
  - **Start-mana grant is a FLAT value, not a % of cost (decided 2026-06-15).** `S` is a
    flat number sized in the cost scale — **baseline ≈ 1/3 of default cost = `100_000`**
    (springtear `100_000`, deepwell `200_000` ≈ 2/3, everbloom `100_000`). **Why flat (not
    pct):** a flat head-start makes **cheaper abilities cast quicker and heavy abilities
    slower** (100k is 83% of a 120k spell but 21% of a 480k spell) — exactly the intended
    cost↔speed coupling; a %-of-cost grant would erase that signal. Implemented in
    `items/combined.py::_grant_start_mana(owner, amount)` (flat). 200 mana was a meaningless
    sip vs the 300_000 scale (the original T.29a value) — corrected here.
- **On-event mana gain** (T.29b) → `ctx.grant_mana(piece, amount)` clamped to `max_mana`.
  No mana-hook items in the 16-core cut → T.29a needs zero hook work here.
- **UI requirement (note for the UI tasks T.8–T.15, not combat):** render **one mana bar per
  ability slot**, and because `max_mana = 2× mana_cost` the bar now has headroom past the cast
  point — the bar **must mark the `mana_cost` cast threshold** (sub-cast tick) so overload vs
  ready-to-cast is legible. Record this requirement now so it isn't lost when the views ship.

**✅ Tension 1 — where `mana_cost`'s base lives — DECIDED: Option A (2026-06-14).** `mana_cost`'s
base is authored **on the ability def** (registry meta, the `loadout.py:59` `granted_abilities`
seam already supports a cost lookup). The champ/enemy **`ability_cost` FLAT stat is deprecated**
and **dropped from V.35** (`/spec` amend — see §10.2a). **Rationale:** cost is the *ability*
knob (how expensive THIS spell is); the *piece* knob is `mana_regen` (global cast rate). Mana
items never reduce `mana_cost` (already settled) → no cost-reduction piece knob exists → cost
belongs wholly on the ability. **Blast radius (small, verified 2026-06-14):** only **6 bosses**
deviate from baseline (`bosses/data.py` 380k–520k) + **2 `999_999` "can't-cast" sentinels**
(`champions.py:2029`, `enemies.py:621`); every other champ/enemy shares one baseline constant
(`content.py:322`) → becomes the `mana_cost` default. **Migration:** re-home those 8 values onto
their ability defs; delete `ability_cost` from the model/stat tuples/serialization. **Authoring
a 1.5×-cost kit** = two numbers per slot — e.g. `@register_ability("dire_bite", mana_cost=300_000,
priority=2)` + `@register_ability("dire_howl", mana_cost=450_000, priority=1)`: only `mana_cost`
differs (450k/300k = 1.5×), `max_mana` auto = 2× each, the shared `mana_regen` + rank cycle do
the rest. ⚠️ **Multi-active *champions* additionally need the `Champion` model to carry a list of
abilities** (today single `active_ability`/`ability_cost`, `models.py:116`); bosses already hold
multi-slot actives. That model change is a **separate** item (see §10.2c) from the mana primitive.

**✅ Tension 2 — rename scope + call-site sweep — DECIDED: mechanical, not a fork.** Just re-grep
before renaming `ActiveSlot.cost`→`mana_cost`. The plan's old line refs (engine.py:830/662/656,
loadout.py:99,138, reference.py:115) **shifted under T.29-pre** — re-grep every `slot.cost` /
`ActiveSlot(cost=` site at build time (current: engine.py:463,486,657,663,831; piece.py
`ActiveSlot`) before editing. Confirm bosses' multi-slot `ActiveSlot` construction carries the
new per-slot `max_mana`/`start_mana`/`priority` defaults.

**✅ Tension 3 — MR allocation across multiple slot-local pools — DECIDED: weighted-rank charge
cycle (2026-06-14).** Pools are per-slot, `mana_regen` is one piece stat. **Constraint held:**
*X `mana_regen` ≈ equal power whether a piece has one slot or many* (else slot count silently
multiplies MR value — Springtear/weather-MR/trait-MR buffs scale with slot count). **Decision:**
a deterministic **weighted round-robin** charge router (cadence counter, V.2/V.14). Cycle length
= `sum(slot.priority)`; each slot occupies `priority` positions in cycle order; **one** slot is
charged per tick with the **full** piece `mana_regen` (skip-to-next-with-room if the selected
slot is at `max_mana`). Example — 3 slots ranked 3/2/1 → cycle `[s3,s3,s3,s2,s2,s1]`. **Why this
over plain Option C:** one-slot-per-tick keeps total throughput = `mana_regen`/tick regardless of
slot count (the invariance), **and** the rank weighting fixes C's starvation — every slot gets a
`priority`-proportional share. Single-slot pieces: cycle = `[s]`, charges every tick = today
(byte-identity anchor). Default `priority = 1` ⇒ unweighted round-robin if unauthored.

**✅ Tension 4 — multi-ready cast semantics — DECIDED: one-cast-per-window + unified priority
(2026-06-14).** (a) **Hard rule (was already settled):** at most **one** cast per action window —
multiple slots may be ready, only the chosen one casts, the rest stay ready for later windows
(no burst). (b) **`priority` = unified** (T4 option 2): the **same** per-slot rank that drives
the T3 charge cycle also picks the casting slot — among ready slots, **highest `priority`** casts
(tie → lowest slot index, deterministic). Charge + cast stay coherent (one rank, one mental
model). Trade accepted: low-priority slots are subordinate (primary/secondary kit), not peers.

**Ratified MVP combo (2026-06-14):** **weighted-rank charge cycle (T3) + one-cast-per-window +
unified `priority` (T4) + `mana_cost` on the ability def (T1) + `max_mana` default 2× cost.**
MR value is stable across slot counts, no parallel throughput inflation, no same-window burst,
per-slot `max_mana`/`start_mana`/overload preserved, clean primary/secondary structure, MVP-sized.
**Consequence (authored intent):** a multi-active unit is **not** "several equal independent
casters charging in parallel" — it is a
**primary spell + one or more secondary/delayed/overflow spells**; multi-slot kits must be designed
around priority + cost spacing (maybe special secondary triggers later), not as N peer mana bars.
**Downside:** low-priority abilities may be subordinate/starved — judged acceptable for MVP over
duplicated MR (A) or vague parallel charging. **Why it matters for items:** unresolved mana
semantics become balance bugs once mana items ship — MR duplication makes Springtear over-strong on
multi-active; `start_mana` hitting all slots accelerates several spells per item; multi-ready
multi-cast explodes burst windows; implicit priority makes itemized multi-slot kits unreasonable.

### 3.1b Multi-slot pieces + Multicaster showcase (NEW row **T.29d**)

> ⚠️ **BUILT DIFFERENTLY THAN SKETCHED BELOW (2026-06-15) — code is truth.** The
> §3.1b sketch (a `secondary=` authoring kwarg; secondary `priority=1`,
> `mana_cost≈450_000` = 1.5×) was **superseded during build** by a cleaner design
> (V.49): (1) **no `active_ability` singular** — one `active_abilities: list`;
> (2) **convention discovery** — `discover_abilities` auto-attaches `{id}.active*`,
> `abilities=` overrides (no `secondary=` kwarg); (3) **distinct slots required**
> (cost OR unique priority — no simul-cast); default = same cost, unique priorities
> (primary `priority=2`); (4) **Ultimate** secondaries for tier ≥ 5 (600k cost,
> priority ∝ cost, ~2× output) instead of a flat 1.5×; (5) **start-mana split
> priority-weighted** (slot-count-invariant). See the 2026-06-15 journal + V.49.

> **Added 2026-06-14.** The §3.1a mana primitive makes multi-slot pieces cheap to enable
> (the engine is already multi-slot via bosses). This sub ships the small model change +
> a **new `Multicaster` Calling** + **9 showcase pieces** (6 champs, 3 enemies) carrying a
> 2nd authored ability, to actually exercise the per-slot pools / rank cycle / one-cast gate.
> **Seam:** carved out as its own row **T.29d** (depends **T.29c** mana primitive + T.28a trait
> counting). Enemies get a 2nd slot **mechanically**; the
> Multicaster Calling is **champion-side synergy only** (enemies use `human`/`corrupted`/…
> tags, not Callings).

**Model change (cheap).** `Champion.active_ability: str` → **`active_abilities: list[str]`**
(`Enemy` likewise, `models.py:235/253`); `from_dict` reads the legacy single `active_ability`
key for back-compat (no save migration). `ability_cost` is removed (T1 Option A) — per-slot
cost now comes from the ability cost-meta. `loadout.piece_from_champion`/`piece_from_enemy`
build **one `ActiveSlot` per entry**, each seeded with that ability's `mana_cost`/`max_mana`/
`start_mana`/`priority` from the cost-meta. Single-ability pieces (the other ~57 champs) keep a
one-element list → one slot → byte-identical (V.2). Validation: list non-empty, ids unique.

**Cost-meta home (T1 Option A wiring).** Add an **`ABILITY_MANA: dict[str, AbilityMana]`**
registry (parallel to `ABILITY_META`/`ABILITY_REGISTRY`) — `AbilityMana(mana_cost=300_000,
max_mana=2×cost, start_mana=0, priority=1)`, populated via optional kwargs on `@register_active`
(falls through to defaults for unregistered/partial ids — the `loadout.py:59` "cost from registry
meta if available" seam). This is where the 6 boss costs + 2 `999_999` sentinels re-home (T1
migration), and where the showcase secondaries author their `mana_cost`/`priority`.

**New Calling: `Multicaster` — quick-caster identity.** Reward casting *often* (what a 2-slot
piece does) with escalating cast speed. New mechanic **`cast_momentum`** (mirror `time_ramp`
`mechanics.py:100` but triggered on **`on_cast_complete`** instead of `on_tick`): each completed
cast adds one stack of `+per` `attack_speed` mul (COMBAT lifetime, capped at `cap` stacks),
plus a small `mana_regen` add so casting snowballs the next cast. **RNG-free** (per-cast cadence,
V.2/V.14). Breakpoints sized to the **~6-carrier pool** (no team-wide apex — V.37 apex =
`min(carrier-pool, board-cap)`):

| Rung | Scope | Stat pack | Mechanic |
|---|---|---|---|
| 2 | per-trait | `{attack_speed:0.06, mana_regen:0.10}` | `cast_momentum(per=0.04, cap=5)` |
| 3 | per-trait | `{mana_regen:0.10, attack_speed:0.06}` | `cast_momentum(per=0.05, cap=6)` |
| 4 | per-trait | `{mana_regen:0.14, attack_speed:0.08}` | `cast_momentum(per=0.06, cap=8)` |

Add `"Multicaster"` to `CALLING_TAGS` (`content.py:201`) — V-guard vocab must include it.

**9 showcase pieces.** Each champ keeps its existing `.active` as **primary** (`priority=2`,
`mana_cost=300_000`) and gains a **new `.active2` secondary** (`priority=1`, `mana_cost≈450_000`
= 1.5× — the cost-ratio worked example). Champs gain the `Multicaster` trait; enemies get the
2nd slot only. **Author/verify the primary is a real handler** (some roster `.active` ids no-op
today) **and author the secondary**:

| Piece | Weather/Affinity | +trait | Secondary `.active2` (sketch — /build refines) |
|---|---|---|---|
| `champ_ember_salamander` | CLEAR / Scaled·Mystic | Multicaster | **Magma Burst** — INT splash to enemies in radius |
| `champ_marsh_thrush` | RAIN / Skyborn·Warden·Mystic | Multicaster ⚠️4 traits | **Gale Note** — slow + minor dmg, furthest enemy |
| `champ_wintermoth` | SNOW / Swarm·Warden | Multicaster | **Frost Pollen** — chill/slow enemies in radius |
| `champ_geode_beetle` | CLOUDY / Swarm·Warden | Multicaster | **Crystal Lattice** — shield lowest-HP ally |
| `champ_will_o_fawn` | MIST / Spirit·Mystic | Multicaster | **Wisp Lure** — INT dmg + threat drop, primary target |
| `champ_tempest_eel` | THUNDER / Tidekin·Mystic | Multicaster | **Voltaic Lash** — chain lightning, 2 enemies |
| `enemy_battlemage` | CLEAR / human | — | **Arcane Nova** — AoE INT dmg |
| `enemy_arcanist` | CLEAR / human | — | **Mana Burn** — dmg + mana denial |
| `enemy_drowned_siren` | RAIN / corrupted·spirit | — | **Siren Wail** — AoE slow + DoT |

⚠️ `champ_marsh_thrush` would reach **4 traits** (Skyborn·Warden·Mystic·Multicaster) — no hard
cap exists in the model, but flag it; swap to a ≤2-trait RAIN caster (e.g. `champ_mirewarden_toad`)
at `/build` if 4 feels busy. **Determinism gate:** capture a pre/post sim baseline — the 57
untouched pieces must stay byte-identical; only the 9 showcase pieces' fights change.

**Out of scope (your discretion call):** *delisting overpopulated existing Callings* — declined
for this addition (separate vocab/V-guard/roster reconciliation + breakpoint rebalance; coupling
it here risks the showcase). Logged as optional follow-up **§D** (see §10).

### 3.2 `RECIPE_MAP` + `combine()`

```python
# game/items/recipes.py — full 8×8 matrix: 8 same-component + 28 cross = 36
RECIPE_MAP: dict[frozenset[str], str] = { frozenset({"fang","talon"}): "huntress_talon", … }

def combine(a: str, b: str) -> str | None:
    if a == SPIRIT_GEM and b in BASE_COMPONENTS: return f"{kinship_of(b)}_emblem"   # b: gem branch
    if b == SPIRIT_GEM and a in BASE_COMPONENTS: return …
    return RECIPE_MAP.get(frozenset({a, b}))
```

Same-component recipes use `frozenset({x})` (size-1) or a separate same-key map — `frozenset({"fang","fang"}) == frozenset({"fang"})`, so handle the diagonal explicitly. (a builds the recipe branch; b adds the gem branch.)

### 3.3 Equip model + 3-slot rule

- Add **`Champion.items: list[str]`** (persistent, ≤3) to the model + `to_dict`/`from_dict`. This is the Run-state equip; `Piece.items` stays the combat-runtime mirror.
- `piece_from_champion` ([loadout.py:67](../../../src/game/loadout.py#L67)) copies `champion.items` → `piece.items`.
- In `compile_loadout`, after pieces are built and **before passives** (so item stats are present; emblem `granted_traits` must land before trait resolution — §10.1 step 2 before step 3, which is T.28a), iterate each piece's items, look up the factory in `ITEM_REGISTRY`, `apply_bundle`. Raw components apply their pure-modifier bundle the same way.
- **3-slot enforcement** lives in the equip action (prep/shop layer) + a model validator on `Champion.items` (`len ≤ 3`). The item_catalog's "§14" reference is **dangling** (no §14 exists) — this plan is the authority; note the doc fix in §6.

### 3.4 Combined-item factories

Modifier-only items are trivial bundles. Hook items follow the §8.3 closure pattern (per-combat state, freshly created each combat):

```python
@register_item("splitwind_talons")           # Talon + Wardpelt — autos hit a 2nd nearby enemy
def splitwind_talons(owner):
    def on_landed(ctx, ev):
        if ev.attacker is not owner: return
        nearby = [e for e in ctx.enemies_of(owner) if hex_distance(...) <= 2 and e is not ev.target]
        if nearby: ctx.deal_damage(owner, nearby[0], ev.amount * 0.5, SourceTag.ITEM_PROC)
    return EffectBundle(
        modifiers=[Modifier("attack_speed","add",10,Lifetime.PERMANENT,"item:splitwind_talons"),
                   Modifier("resistance","add",5,Lifetime.PERMANENT,"item:splitwind_talons")],
        hooks=[Hook("on_attack_landed", on_landed, scope=HookScope.PER_HIT)])
```

- **Determinism:** "every few autos" / "first time low" use cadence counters / one-shot flags in the closure — never RNG (V.2/V.14). Same rule as T.28.
- **Spellfang Crown** (Heartseed+Keen Claw) sets `ability_can_crit` via an `on_combat_start` hook — identical idiom to Mystic @4 (T.28b). Shields (Beastheart Gauntlet, Sapwood Aegis) reuse the **`Piece.shield_hp` primitive from T.28b** — sequence T.29 hook-items needing shields after T.28b, or stub until then.
- **Starting-mana items** carry their start grant on a new `EffectBundle.slot_mana_start: int = 0` field (the bundle is otherwise modifiers/hooks). `compile_loadout`'s equip step reads it and applies `slot.start_mana += S` / `slot.max_mana = max(slot.max_mana, slot.start_mana)` to the piece's slot(s) — the one item path that writes a slot (§3.1a). No 16-core item uses it (it's reserved for the start-mana / overload combined items, mostly T.29b); the field + plumbing land in a so b items drop in clean.

### 3.5 Emblems (T.29b, depends T.28a)

Emblem = item whose bundle carries `granted_traits=["<Kinship>"]` + a small stat. `apply_bundle` already appends `granted_traits` to `piece.traits`; because emblems apply at §10.1 step 2 (before `_resolve_traits` at step 3, built in T.28a), the wearer counts toward that Kinship. One emblem per Kinship (Beast/Skyborn/Scaled/Tidekin/Swarm/Spirit). Crafted via `combine(Spirit_Gem, component)`.

### 3.6 Special items — run-actions + CLI driver (T.29b)

These never enter combat (§8.4) — separate registry, operate on `Run`:

```python
# game/registries.py
RUN_ACTION_REGISTRY: dict[str, Callable] = {}
def register_run_action(item_id): …                # mirrors register_item

# game/items/special.py
@register_run_action("reforger")        def reforger(run, target_item_idx): …
@register_run_action("unbinding_totem") def unbinding_totem(run, piece_id): …
@register_run_action("echo_acorn")      def echo_acorn(run, piece_id): …          # bench copy → T.22 levelling
@register_run_action("glimmerdust")     def glimmerdust(run, item_idx): …          # Heartwood upgrade (generic stat-mult, §7)
@register_run_action("reclaimers_cache")def reclaimers_cache(run, component_ids): …# components → Amber
# Spirit Gem handled inline by combine() (§3.2)
```

**CLI driver (your call):** extend `sim_run`'s interactive mode (the shell T.31 introduces) with a prep-layer special-item menu so a complete headless run can reforge/unbind/echo/salvage. Coordinate the interactive shell with T.31 so both layer cleanly (one prompt loop, pluggable actions). Headless auto-walk does not invoke special items (they're player decisions) — they appear only in `--interactive`.

### 3.7 REWARD drop integration

`generate_reward` ([encounter.py:473](../../../src/game/encounter.py#L473)) currently yields enemies only (REWARD = easy fight + guaranteed loot, B.2). Add a parallel `generate_reward_loot` function keyed on a new `CH_LOOT = 8` channel (channels 0–7 already taken; see top of `encounter.py`).

**Drop table (first-pass, tunable):** T.29a owns these weights per §D.12 decision; T.22 never defined them.

| Bucket | Weight | Result |
|---|---|---|
| Component | 45% | 1 random base component |
| Combined item | 20% | 1 random item from the core-16 (or full 36 once T.29b ships) |
| Amber bonus | 15% | +2 Amber credited to `Run.amber` |
| Champion recruit | 15% | 1 champion id (same tier-pool logic as SUPPLY; re-uses `shop._roll_offers`); player must accept/skip via UI (T.23/T.15) |
| Special item | 5% | 1 random special item (T.29b content; in T.29a this bucket falls back to a component so the weights stay stable across both substeps) |

**Acquisition channels (resolved):** the **shop sells champions only** — never items (T.22 contract, do not extend). Drops are the primary special-item source (the 5% bucket above). T.31 **grant augments** may additionally award specific specials (emblems via Spirit Gem, Glimmerdust) — coordinate with the T.31 augment catalog; that channel is a bonus, not the baseline.

Return type: a small dataclass `RewardLoot(type: str, item_id: str | None, champion_id: str | None, amber: int)`. The caller (UI/prep layer, T.23) acts on it; `generate_reward_loot` is pure — no `Run` mutation.

Seed: `derive_seed(run_seed, node_index, CH_LOOT)`.

**Boss loot (resolved):** on boss defeat, roll **three pairs of two drops each** from the same table (6 `RewardLoot` rolls off the boss node's `CH_LOOT` seed, consumed in order — fully deterministic); the player **picks one pair** (UI choice, T.23/T.15 surfaces it; headless sims take pair 0). New function `generate_boss_loot(run_seed, node_index) -> list[tuple[RewardLoot, RewardLoot]]` (len 3), pure like `generate_reward_loot`.

---

## 4. Decisions

- **3 item slots/piece** (catalog §6) — enforced in equip + `Champion.items` validator.
- **Raw components are equippable** (catalog §1) — occupy a slot, apply their pure-modifier bundle.
- **MVP = 16 core cut in T.29a** (catalog §3), remaining 20 in T.29b — your call.
- **Mana primitive (§3.1a) — ✅ DECIDED 2026-06-14, build-ready.** Per-ability slot fields `mana_cost`/`max_mana`/`start_mana`/`priority` (+ runtime `current_mana`); `mana_regen` is the lone piece stat and **the cast-rate knob**. **`max_mana` = the universal pool cap** (every clamp is to it); the old "regen guarded at `mana_cost`", the 5× default, and the `start_mana` auto-bump are **dropped**. Defaults: `mana_cost=300_000`, **`max_mana=2× mana_cost`**, `priority=1`, `start_mana/current_mana=0`. Mana items grant **`mana_regen` or `start_mana`, never reduce `mana_cost`** (kills negative-cost stacking). **Resolutions:** T1 = `mana_cost` base **on the ability def** (deprecate V.35 `ability_cost`); T2 = re-grep before rename (mechanical); T3 = **weighted-rank charge cycle** (cycle len `sum(priority)`, one slot/tick full MR, skip-if-full → throughput slot-count-invariant); T4 = **≤1 cast/window + unified `priority`** (highest-rank ready slot casts, tie→slot index). Multi-active = primary + secondary spells, not N peer bars.
- **Flat-add modifiers** for all component stats (§3.1) — TFT-style, items favour early/mid game; tunable.
- **Shop sells champions only** — items never enter the shop (T.22 contract; §3.7).
- **Boss loot = 3-pair pick** via `generate_boss_loot` (§3.7) — deterministic, player picks one pair.

## 5. Authored values (first pass — tunable)

**Components** (flat add, §3.1 decision): Fang +10 strength · Talon +10 attack_speed · Heartseed +10 intelligence · Old Hide +100 hp · Stoneplate +5 armor · Wardpelt +5 resistance · Keen Claw +0.15 crit_chance · **Springtear +40 mana_regen** (clean `Modifier`, no slot touch; §3.1).

Values are TFT-style flat — meaningful at low tiers (~15-20%), modest at T10 (~2-5%). Retune via sim after T.29a ships. **Starting-mana / overload items** (mostly T.29b) author a `slot_mana_start` value instead (§3.1a/§3.4); none in the 16-core cut.

**Combined items:** each carries both parent component stats (flat add, same amounts) plus the showcase mechanic. Per-item bonus authored inline in `game/items/combined.py`, flagged first-pass. Example: Splitwind Talons (Talon+Wardpelt) = +10 AS + +5 RES + splash proc.

## 6. Drift / doc reconciliation

- **§8.1 "15 combined"** vs catalog's **36** — the effect-doc table budgets a 6-component/15-item set; catalog §"Reconciliation" extends to 8 components/36. Annotate §8.1 to point at `item_catalog.md` as the authoritative count.
- **Dangling "§14"** — item_catalog §6 cites "effect_systems_design.md §14" for 3-slot enforcement; §14 doesn't exist. This plan (§3.3) is the authority; fix the catalog ref.
- **Fake stat keys / component ids** in §8.2/§8.3 — mapped to real engine stats in §3.1; note they're illustrative.
- **Springtear flavour** — `item_catalog.md` §1 lists Springtear as "Mana (start / cost)". Reflavor to **"Mana regen"** (the component now grants `mana_regen`, §3.1); starting-mana / cost are no longer a component effect (cost is never item-touched). Update the catalog row.

## 7. Open questions

**Resolved here:**
- Phasing → T.29a (engine + 16 core) / T.29b (rest + emblems + special).
- Special items → backend run-actions **+ interactive CLI driver** (§3.6).
- Mana handling → per-ability slot `mana_cost`/`max_mana`/`start_mana`/`priority` + piece-stat `mana_regen` (§3.1a); `max_mana` = universal cap (regen now fills to it, **guard dropped**), default `= 2× mana_cost`; MR = cast-rate knob. `mana_cost` base **on the ability def** (V.35 `ability_cost` deprecated). Mana items grant `mana_regen` **or** `start_mana`, **never reduce `mana_cost`**. ✅ **All four tensions DECIDED 2026-06-14:** T1 cost-on-ability-def; T2 re-grep (mechanical); **T3 weighted-rank charge cycle** (cycle len `sum(priority)`, one slot/tick full MR → slot-count-invariant throughput); **T4 ≤1 cast/window + unified `priority`** (highest-rank ready casts). Multi-active = primary + secondary spells, not N peer bars. (Reworked 2026-06-13 post-T.29-pre, tensions resolved 2026-06-14; supersedes the earlier 5×-default / guarded-regen model.)
- **Component modifier type → flat add** (TFT-style; §3.1, §5). `crit_chance` and mana already flat by nature.
- **Drop-table weights → T.29a owns** (§3.7): 45% component / 20% combined / 15% Amber / 15% champion recruit / 5% special. Flagged tunable.
- **Champion recruit drops** (§3.7): REWARD loot can yield a champion id; reuses SUPPLY tier-pool logic. Returns in `RewardLoot`; UI/prep layer acts on it.
- **Heartwood tier → pure stat-mult for MVP** (generic ×1.5 on the item's stat modifiers, proc untouched; one code path in T.29b). Authored per-item Heartwood variants noted as **post-MVP future work** — add a §D row.
- **Special-item acquisition → drops primary, shop never** (§3.7): shop sells champions only (T.22 contract — do not extend); specials come from the 5% REWARD bucket; T.31 grant augments may additionally award emblems/Glimmerdust as a bonus channel.
- **Boss loot → 3-pair pick** (§3.7): boss defeat rolls three pairs of two drops, player picks one pair; deterministic off `CH_LOOT`; `generate_boss_loot` in T.29a.

**Still open / deferred (post-MVP §D rows):**
- **Bosses wearing items** — deferred post-MVP; T.30 boss kits tuned without items, revisit with a sim retune pass once player items prove out.
- **Authored Heartwood variants** — MVP uses the generic stat-mult (above); per-item Heartwood content is future work.

## 8. Test plan

- **Recipes:** `combine()` resolves all 36 pairs (incl. same-component diagonal) + gem→emblem; unknown pair → `None`.
- **Equip:** ≤3 slots enforced; raw component applies its stat; `Champion.items` round-trips `to_dict`/`from_dict`; `piece_from_champion` mirrors into `Piece.items`.
- **Bundles:** modifier items shift stats; a hook item (Splitwind Talons, Stormscale Quiver) procs **deterministically** in a fixed-seed fight (no RNG); per-combat closure state resets each combat.
- **Mana primitive (§3.1a):** with `max_mana` default `= 2× mana_cost`, `start_mana==0`, and **single-slot** pieces (≈ whole current roster), no-item fights are **expected byte-identical** to today (one-slot cycle charges every tick like today; baseline regen `100`/tick never reaches `2× cost` = 600k → raised cap never hit by regen; pool crosses `mana_cost`, casts, `-= mana_cost` ≡ old `= 0` within rounding). ⚠️ **Verify empirically with a pre/post baseline diff — do not trust the claim** (T.29-pre lesson; 2× cap is a behavioral change for any banking/`start_mana`/multi-slot path). Springtear shifts `mana_regen` (piece stat) — no slot touch; **no item ever changes `mana_cost`**. A `start_mana` grant seeds `current_mana = min(max_mana, start_mana)` at combat start; regen fills to `max_mana` (guard dropped); `ctx.grant_mana` clamps to `max_mana`.
- **Emblems (b):** an emblem makes a non-native piece count toward a Kinship breakpoint (integration with T.28a `_resolve_traits`); ordering before resolution verified.
- **Special items (b):** each run-action mutates `Run` correctly (reforge swaps a component, unbind returns to bench decomposed, echo adds a copy, salvage credits Amber); `sim_run --interactive` invokes them.
- **REWARD drops:** seed-deterministic loot roll; same seed → same drop; bucket weights sum to 100; special bucket falls back to component while T.29b unshipped.
- **Boss loot:** `generate_boss_loot` returns exactly 3 pairs; same seed → same 3 pairs; pure (no `Run` mutation).
- **Determinism + regression:** no-item teams byte-identical to today; `workers=1`/fixed-seed identical.

## 9. Acceptance criteria

1. (a) Components + `RECIPE_MAP` (36) + `combine()` (recipe branch) + 3-slot equip + 16 core items applied via `compile_loadout`; REWARD drops + boss 3-pair loot seed-deterministic.
2. (a) `Champion.items` model + serialization + validator; `Piece.items` consumed in loadout.
3. (b) Remaining 20 combined items + 6 emblems (counting via T.28a) + gem `combine()` branch.
4. (b) `RUN_ACTION_REGISTRY` + 6 special-item functions + `sim_run --interactive` driver.
5. All item procs deterministic (no RNG); mana primitive (§3.1a) — `cost` renamed `mana_cost` (base now on the ability def, `ability_cost` stat removed), per-slot `mana_cost`/`max_mana`/`start_mana`/`priority` (`max_mana` **2× default**), `mana_regen` piece stat; charge = deterministic weighted-rank cycle (throughput slot-count-invariant); ≤1 cast/window, unified-`priority` cast pick; no item touches `mana_cost`; single-slot no-item fights byte-identical.
6. `tests/game/test_items.py` (+ loadout/encounter/CLI tests) pass; full suite green; no-item regression intact.

## 10. SPEC changes needed (for `/spec`)

1. **§T:** replace the T.29 row with **T.29a** (engine + 16 core items; depends T.1, T.20, T.22; Est M–L) and **T.29b** (remaining 20 + emblems + special items + CLI driver; depends T.29a, T.28a; Est M–L); both 📋 Plan; both cite `docs/design/tasks/t29_item_engine_plan.md`. Update Implementation-Order Phase 1b to `… → T.29a → T.29b → T.31`.
2. **New §V invariant:** items apply only via `compile_loadout` (combat-facing) or `RUN_ACTION_REGISTRY` (run-facing, never imported by `combat/`); ≤3 equipped items per piece; item procs deterministic (cadence/flags, no RNG). (T.29)
2a. **New §V invariant (mana) — ✅ FINALIZED (2026-06-14, all §3.1a tensions decided):** `ActiveSlot` carries per-slot `mana_cost`/`max_mana`/`start_mana`/`priority` (+ runtime `current_mana`); `mana_regen` is the only piece-level mana stat and the cast-rate knob. **`mana_cost`'s base is authored on the ability def** (T1 Option A; the V.35 `ability_cost` stat is deprecated — see §10.2a-bis). **`max_mana` is the universal pool cap** — regen, start, and `grant_mana` all clamp to it (no `mana_cost` regen-guard; no `start_mana` auto-bump). Defaults: `mana_cost = 300_000` (old `ability_cost` baseline), **`max_mana = 2× mana_cost`**, `priority = 1`, `start_mana`/`current_mana` `= 0`. The pool fields are **resource state** (direct slot writes only, never `Modifier`s — extends V.43); **no item/Modifier ever changes `mana_cost`** — mana items grant `mana_regen` (Modifier) or `start_mana` (slot). **Charge = deterministic weighted-rank cycle** (T3): cycle length `sum(slot.priority)`, one slot charged per tick with the full `mana_regen` (skip slots at `max_mana`) ⇒ total throughput = `mana_regen`/tick **regardless of slot count**; RNG-free cadence (V.2/V.14). **Cast = at most one per action window** (T4 hard rule); among ready slots the **highest `priority`** casts (tie → lowest slot index). Single-slot, no-item combat ⇒ byte-identical (V.2, verify empirically). ✅ **APPLIED to SPEC 2026-06-14 as V.48 (row T.29c — NOT T.29a, which already shipped).** (T.29c)
2a-bis. **§V.35 amend (T1 Option A):** **drop `ability_cost`** from the FLAT-stat set / `Champion`+`Enemy` stat fields / serialization; per-ability cast cost now lives as `mana_cost` on the ability def (default = the old `300_000` baseline). Migrate the 6 boss deviations (`bosses/data.py` 380k–520k) + 2 `999_999` "can't-cast" sentinels (`champions.py:2029`, `enemies.py:621`) onto their ability defs.
2b. **§T file-list (now the T.29c row):** `game/piece.py`, `game/combat/engine.py`, `game/combat/context.py`, `game/effects.py` (the §3.1a mana primitive) + `game/abilities/`, `game/bosses/data.py`, `game/content.py`, `game/scaling.py`, `game/items/combined.py` (the T1 cost re-home + `ability_cost` removal + item retrofit). ✅ Applied (T.29c row in SPEC).
2c. **NEW §T row — T.29d (multi-slot pieces + Multicaster showcase; §3.1b):** ✅ applied to SPEC. Depends **T.29c** (mana primitive + `ABILITY_MANA` cost-meta) + **T.28a** (trait counting); Est **M**; 📋 Plan; cites this plan. Scope: (i) `Champion`/`Enemy` `active_ability`→`active_abilities: list[str]` (+ `from_dict` legacy read, validation) and per-entry `ActiveSlot` build in `loadout`; (ii) `ABILITY_MANA` registry + `@register_active` mana kwargs; (iii) **new `Multicaster` Calling** (breakpoints 2/3/4, ~6-carrier pool, no team apex) + **new `cast_momentum` mechanic** (`on_cast_complete` stacking `attack_speed`, RNG-free); (iv) add `"Multicaster"` to `CALLING_TAGS`; (v) **9 showcase pieces** — 6 champs gain the trait + a `.active2` secondary, 3 enemies gain a 2nd slot; author/verify all primaries + 9 secondaries. Files: `game/models.py`, `game/loadout.py`, `game/content.py`, `game/registries.py`, `game/traits/callings.py`, `game/traits/mechanics.py`, `game/abilities/champions.py`, `game/abilities/enemies.py`, `docs/live/` trait + content docs, tests. **Implementation Order (applied): `… → T.29a → T.29b → T.29c → T.29d → T.31`.**
2d. **§V amends for T.29d (✅ applied as V.49):** (a) extend the §V trait-vocab/`CALLING_TAGS` guard to include `Multicaster`; (b) add a determinism clause — `cast_momentum` is RNG-free (per-cast cadence, V.2/V.14); (c) note multi-slot champs use `active_abilities: list` (the §3.1a mana invariant already covers per-slot pools + the rank cycle). Confirm no hard trait-count cap is asserted (marsh_thrush = 4 traits) or add one ≥4 if desired.
3. **New §V invariant:** special items (`RUN_ACTION_REGISTRY`) operate on `Run` only and are **never** referenced from `game/combat/` — combat sees only their result (§8.4). (T.29)
4. **§D.9:** mark item system implemented in T.29a/b; leave open only magnitude tuning.
5. **§D.12:** update to "REWARD loot drops fully integrated in T.29a — weights authored there (45% component / 20% combined / 15% Amber / 15% champion recruit / 5% special; first-pass, tunable); boss defeat = 3-pair pick via `generate_boss_loot`. T.22 never defined weights." Mark §D.12 resolved by T.29a. Shop stays champions-only (T.22 contract).
6. **New §B entry:** doc drift — `effect_systems_design.md` §8.1 "15 combined" and the dangling "§14" 3-slot ref; reconciled to `item_catalog.md` (36, 8-component matrix) and §3.3 of this plan.
7. **T.29 planning note** (T.18-T.31 block): item engine on the T.20 substrate; real-stat mapping (mana per-slot, flat-add magnitudes); emblems gate on T.28a; special items are run-actions with a `sim_run` interactive driver shared with T.31; Heartwood = generic stat-mult (MVP).
8. **New §D rows (post-MVP):** (i) authored per-item Heartwood variants (MVP ships the generic ×1.5 stat-mult); (ii) bosses wearing items (T.30 kits tuned without — needs sim retune pass if revisited); (iii) **delist overpopulated existing Callings** — deferred from T.29c (separate vocab/V-guard reconciliation + breakpoint rebalance; Multicaster shipped purely additive); revisit when the Calling roster is rebalanced; (iv) **expand multi-slot beyond the 9 showcase pieces** — once the rank cycle / one-cast gate prove out, more champs/enemies can gain 2nd abilities (and 3rd slots) as content.

> **Note:** the `T.29-pre` substrate (Part B) has its own `/spec` delta list — see [§B.10](#b10-spec-changes-needed-for-spec--t29-pre). It is sequenced **before** these item rows.

---

# Part B — T.29-pre — Combat Stat Substrate (prerequisite, sequences first)

> **Status:** NEW substep — needs a `/spec` row-add (`T.29-pre`, 📋 Plan) **before** T.29a in the T.29 block + Implementation Order.
> **Depends (all built):** T.2 (weather favor / `weather_effects.py` / `_apply_weather_to_piece` — done), T.20 (`Modifier`/`compute_stat`/`apply_bundle`/`EffectBundle` — done), T.28d (trait `milli_AS` riders + `weather_favored` marker — done), T.33a (V.34 sort order, `milli_AS`, baseline parity — done). No unbuilt deps → can build immediately.
> **Resolves:** the stat-attribution gap blocking the prep-view ability/stat breakdown (T.34/T.23): weather is currently a `base_stats` fold, unattributable like a modifier. Also kills the `milli_AS` desync (ability `attack_speed` muls don't ride `milli_AS`; only weather + traits manually keep the pair synced).
> **Design source of truth:** code — `loadout._apply_weather_to_piece` ([loadout.py:174-209](../../../src/game/loadout.py#L174)), `effects.compute_stat`/`Modifier` ([effects.py:47,61](../../../src/game/effects.py#L47)), `engine._event_sort_key` ([engine.py:525-540](../../../src/game/combat/engine.py#L525)), V.34/V.35 (SPEC). Verified against code 2026-06-13; design docs not relied on.

## B.1 Why (the driver)

The prep view wants **stat = effective total + a hold-modifier breakdown** (`100 base + 20 item:springtear + 12 weather:Rain + 10 augment:…`), with weather/items/augments/passives **all attributed uniformly**. T.34's `render(meta, source)` already renders any object exposing `.stat()`. The only blocker: **weather is baked into `base_stats`** (`_apply_weather_to_piece` mutates the dict in place, integer-rounded) so it cannot be attributed like a `Modifier` — items/augments/traits already carry a `source_id`, weather does not. Fix the substrate → the breakdown is a pure `source:`-prefix scan with **zero** special-casing.

Two architectural truths surfaced during design (both verified in code):
1. The real axis is **flow stat vs resource**, not weather-vs-modifier. Flow stats (str/int/AS/armor/res/crit/MS/MR/pen/range) flow through `Modifier`+`compute_stat`. Resources (`hp`/`max_hp`, and mana per-`ActiveSlot`) are **never** `Modifier`'d — every system that changes max HP (weather loadout.py:206-209, traits [traits/__init__.py:139-142](../../../src/game/traits/__init__.py#L139), clones/turrets) **direct-sets + reconciles**. So weather's HP buff keeps using that path; only its flow-stat changes become modifiers.
2. `milli_AS` exists only because `attack_speed` is conceptually int. With a float `attack_speed`, sub-integer order is **derived** (`round(AS*1000)`), the separate field disappears, and an `attack_speed` mul moves cadence **and** order together — no rider to keep in sync.

## B.2 The gap today

| Piece | Where | State |
|---|---|---|
| Weather folds into `base_stats` (rounded, in-place) | [loadout.py:174-209](../../../src/game/loadout.py#L174) | 🔴 unattributable — no `source_id`; blocks breakdown |
| `compute_stat` `(base+Σadds)×Πmuls`, no floor | [effects.py:61-90](../../../src/game/effects.py#L61) | ✅ the single fold; needs an `attack_range` floor when weather leaves the clamped path |
| `Modifier.source_id` | [effects.py:47](../../../src/game/effects.py#L47) | ✅ exists; **prefix vocab not standardized** (`item:`/`augment:`/`passive:`/`trait:`/`weather:`) |
| HP re-sync from `stat("hp")` after modifiers | [traits/__init__.py:139-142](../../../src/game/traits/__init__.py#L139) | ✅ template to reuse for weather + resources |
| `attack_speed: int` + `milli_AS: int` (×1000) | [models.py:104,122,237,253](../../../src/game/models.py#L104) | 🔴 to merge into one float `attack_speed` |
| `milli_AS` capture in compose (pre-round) | [content.py:328-332](../../../src/game/content.py#L325) | 🔴 `milli_AS = round(AS_float*1000)` then AS rounded — float AS makes this implicit |
| `milli_AS` scaled in level-scale | [scaling.py:130-134](../../../src/game/scaling.py#L130) | 🔴 remove (AS stays float through scaling) |
| `milli_AS` in sort key | [engine.py:525-540](../../../src/game/combat/engine.py#L525) | 🔴 `-int(stat("milli_AS"))` → `-round(stat("attack_speed")*1000)` |
| `milli_AS` trait rider modifiers | [traits/_packs.py:41](../../../src/game/traits/_packs.py#L41), [mechanics.py:93,114,583](../../../src/game/traits/mechanics.py#L93) | 🔴 delete — `attack_speed` mul alone now moves tie-order |
| `milli_AS` seeds / args | [loadout.py:78,117](../../../src/game/loadout.py#L78), [encounter.py:298,621](../../../src/game/encounter.py#L298) | 🔴 drop |
| `stat_breakdown(piece)` helper | — | ❌ new pure `game/` fn for the prep-view breakdown |

## B.3 Architecture

### B.3.1 Commit 1 — weather → modifiers

Replace `_apply_weather_to_piece`'s in-place `base_stats` mutation with a `CombatModifier → list[Modifier]` translation, applied via `apply_bundle` (reusing the existing path), then an HP re-sync. The `CombatModifier` ([weather_effects.py:87-103](../../../src/game/weather_effects.py#L87)) is a frozen pack of `*_mult` fields + `attack_range_delta`:

```python
# loadout.py — replaces the base_stats fold (lines 190-209)
def _weather_modifiers(mod: CombatModifier, state: WeatherState) -> list[Modifier]:
    src = f"weather:{state.value}"
    out: list[Modifier] = []
    for stat, mult in (("strength", mod.str_mult), ("intelligence", mod.int_mult),
                       ("attack_speed", mod.as_mult), ("move_speed", mod.ms_mult),
                       ("mana_regen", mod.mr_mult), ("hp", mod.hp_mult),
                       ("armor", mod.armor_mult), ("resistance", mod.res_mult),
                       ("threat", mod.thr_mult)):
        if mult != 1.0:
            out.append(Modifier(stat, "mul", mult, Lifetime.COMBAT, src))
    if mod.attack_range_delta:
        out.append(Modifier("attack_range", "add", float(mod.attack_range_delta), Lifetime.COMBAT, src))
    return out
```
- **Application point:** the existing `_apply_weather_to_piece` call site in `compile_loadout` (pre-trait-resolution, so the single trait HP re-sync at [traits/__init__.py:139](../../../src/game/traits/__init__.py#L139) folds weather+trait HP together). Keep an **own** HP re-sync in the weather step too (`piece.max_hp = piece.hp = piece.stat("hp")`) so weather-only / no-trait pieces still seed correctly — idempotent with the trait pass (both set full HP).
- **`weather_favored` (T.28d):** unchanged branch — favored pieces build from `WEATHER_BUFF_BASE[weather]` regardless of affinity ([loadout.py:185-188](../../../src/game/loadout.py#L185)); just feed it through `_weather_modifiers`.
- **`milli_AS` rider:** the old fold scaled `milli_AS` by `as_mult` (loadout.py:198) to keep order exact. With Commit 2's float AS the `attack_speed` mul **is** the order — no separate weather rider needed. (If Commit 1 lands before Commit 2, keep a transitional `Modifier("milli_AS","mul",as_mult,…)`; Commit 2 deletes it. Simpler: land both before re-baselining, see B.6.)

### B.3.2 `attack_range` floor (Commit 1)

`compute_stat` has no clamp; the old fold floored at 1 ([loadout.py:204](../../../src/game/loadout.py#L204) `max(1, …)`). With range as an `add` modifier (Mist `-1`), stacked debuffs could underflow. **Add a stat-floor map at the tail of `compute_stat`:**
```python
_STAT_FLOORS = {"attack_range": 1.0}
# return max(_STAT_FLOORS.get(stat, ...), (base + adds) * mul)  — floor only where defined
```
Minimal, generic, and correct: `attack_range` must never be < 1 regardless of source.

### B.3.3 Compose rule — the universal contract (RESOLVED)

`compute_stat` is `(base + Σadds) × Πmuls` ([effects.py:90](../../../src/game/effects.py#L90)). Once weather is a `mul` modifier and items are `add` modifiers, **weather scales the item/augment flat-adds too**: `(base + item_add) × weather_mul`. Worked: base STR 100 + Fang +10, Rain ×0.7 → `(110)×0.7 = 77` (vs the old fold's `round(70)+10 = 80`). **Intended** — items feel better in good weather, worse in bad; it is exactly how every existing ability/trait `mul` already composes (precedent: [champions.py:207](../../../src/game/abilities/champions.py#L207) `Modifier("attack_speed","mul",1.2)`). Op decides order (all adds before all muls), not acquisition order — the existing contract.

### B.3.4 Source-prefix vocab (Commit 1)

Standardize `Modifier.source_id` prefixes: **`item:` / `augment:` / `passive:` / `trait:` / `weather:`** (`<prefix>:<id>`). Weather adopts `weather:<state>`; item/augment factories (T.29a/T.31) author against it; the `stat_breakdown` helper groups on the prefix. Existing trait/ability `source_id`s are additive to standardize (low-risk; breakdown-only, not read by the engine).

### B.3.5 Commit 2 — `attack_speed` float, drop `milli_AS`

- **Models** ([models.py:104,120-133,237,252-264](../../../src/game/models.py#L104)): `attack_speed: int → float`; delete the `milli_AS` field + its `__post_init__` default + `_require_non_negative_int` validator + `to_dict`/`from_dict` keys. **Save migration** in `from_dict`: `attack_speed = payload.get("attack_speed_f") or (payload["milli_AS"] / 1000 if "milli_AS" in payload else float(payload["attack_speed"]))` — old saves carry int `attack_speed` + `milli_AS`; `milli_AS/1000` is the **exact** float (B.6).
- **Compose** ([content.py:328-332](../../../src/game/content.py#L328)): drop the `round` on `attack_speed` (keep float); delete the `milli_AS` line.
- **Scaling** ([scaling.py:130-134](../../../src/game/scaling.py#L130)): `attack_speed` stays float through the SECONDARY loop (don't round it); delete the `milli_AS` scale.
- **Sort key** ([engine.py:525-540](../../../src/game/combat/engine.py#L525)): replace `(-int(AS), -int(milli_AS), id, load_order, kind)` with **`(-round(stat("attack_speed")*1000), id, load_order, kind)`** — the quantized AS key is monotonic in AS, so it **subsumes** the old coarse `-int(AS)` (the two-level key was redundant). `round(...*1000)` kills float-noise tie flips + the cross-machine V.2 risk. Cadence unchanged: `int(stat("attack_speed"))` ([engine.py:820](../../../src/game/combat/engine.py#L820)).
- **Trait riders** ([_packs.py:41](../../../src/game/traits/_packs.py#L41), [mechanics.py:93,114,583](../../../src/game/traits/mechanics.py#L93)): delete every `Modifier("milli_AS",…)` and the `milli_AS` entry in the stat whitelist — the `attack_speed` mul now moves tie-order on its own.
- **Seeds / args** ([loadout.py:78,117](../../../src/game/loadout.py#L78), [encounter.py:298,621](../../../src/game/encounter.py#L298)): drop `milli_AS`.
- **Fractional AS is tiebreak-only** (not frequency) — `int(AS)` cadence means AS 50.9 and 50.1 attack identically; the fraction only orders same-tick collisions. Identical role to `milli_AS` today. **Float-energy frequency accumulation is OUT OF SCOPE** (a separate, bigger change).

### B.3.6 `stat_breakdown` helper (pure `game/`)

```python
# game/effects.py (or a new game/stat_breakdown.py) — pure, no Flet (V.1)
def stat_breakdown(piece) -> list[tuple[str, dict[str, float]]]:
    """Group piece.modifiers by source: prefix → per-stat delta, for the prep-view
    breakdown. 'base' row from piece.base_stats. Weather is a normal source now."""
```
Consumed later by T.34/T.23 (UI hold-modifier reveal); ships here as pure logic with its own unit test. `_apply_items` / `roster_source` / `projected_source` stay in **T.29a**; the UI stays in **T.23**.

## B.4 Decisions

- **`attack_speed` float; cadence `int(AS)`; tiebreak `round(AS*1000)`; `milli_AS` removed (derived, not stored).** Migration `AS_float = milli_AS/1000` is **exact** (B.6).
- **Sort key simplified to the single quantized AS key** — provably order-equivalent to the old two-level key, minus float noise.
- **`attack_range` floor via a `_STAT_FLOORS` map in `compute_stat`** — generic, replaces the lost `max(1,…)` clamp.
- **Weather = `mul`/`add` `Modifier`s tagged `weather:<state>`**, applied via `apply_bundle`; HP re-synced from `stat("hp")` (resources never modifier'd).
- **`(base+adds)×muls` is the universal compose contract** — weather scales item/augment adds (intended).
- **Resources (hp/mana) are direct-set + reconcile, never `Modifier` targets** — codified as a §V invariant.

## B.5 Authored values

None new — this is a substrate refactor. Weather magnitudes (`WEATHER_FAVOR_MAGNITUDE=0.3`, tier scalars) and AS baselines (V.35 `attack_speed=100`) are **unchanged**; only their representation changes (mul-modifier vs fold; float vs int+milli).

## B.6 Re-baseline (the determinism work)

- **Commit 2 (AS float) is ~byte-identical** by construction: cadence `int(142.43)=142` == old `int(round(142.43))=142`; tiebreak `round(142.43*1000)=142430` == old `milli_AS`. Verify with a snapshot diff — expect **zero or only rare tiebreak-rounding** deltas (from collapsing the trait `milli_AS` rider into the `attack_speed` mul). If a sim moves, it is one of those rare ties.
- **Commit 1 (weather) genuinely re-baselines:** `(base+adds)×mul` float compose replaces `round(base×mult)` fold → weather numbers shift (and now scale future item adds). Re-snapshot all sims; re-run `tools/simulation` + playtest baselines; re-verify **V.2** byte-identical *within the new baseline*, **V.14**, **V.34** (amended).
- **Keep the two commits separate** so any sim delta is attributable to the right change. Commit order: **2 first** (prove ~no-op), then **1** (own the weather re-baseline). This avoids the transitional `milli_AS` weather rider in B.3.1 — with Commit 2 already in, Commit 1 never touches `milli_AS`.

## B.7 Open questions

**Resolved here (overridable):**
- Weather→modifier vs delta-capture hybrid → **modifier** (uniform attribution, removes the special case; HP via the existing resync path makes it cheap).
- AS representation → **float field, drop `milli_AS`**; cadence int, tiebreak `round(×1000)`.
- Compose order / weather-scales-items → **yes**, the `(base+adds)×muls` contract.
- MS treatment → **leave as-is** (movement events still ordered by AS; `move_speed` keeps no sub-integer field). Deferred (B.9).

**Still open / deferred:**
- **MS phase-split** (B.9) — symmetric move-phase/act-phase ordering. Combat-semantics change; own task + sim validation.

## B.8 Test plan

- **Weather-as-modifier:** a piece in favorable weather has `piece.stat(s)` matching the old fold **within the new compose baseline**; the contributing `Modifier`s carry `source_id="weather:<state>"`; `CLEAR` adds none (inert).
- **HP resync:** weather HP buff reflects in `piece.max_hp`/`hp` (full at start); a no-trait, weather-buffed piece seeds correctly.
- **`attack_range` floor:** Mist `-1` on a range-1 piece clamps to 1; never < 1 under stacking.
- **Compose rule:** `(base+add)×mul` worked example pinned (STR 100 + Fang 10, Rain → 77).
- **AS float / migration:** `attack_speed=milli_AS/1000` round-trips an old save; cadence `int(AS)` and tiebreak `round(AS*1000)` reproduce pre-refactor values on a fixed fixture (the ~byte-identical claim).
- **Tiebreak:** rewrite [test_tiebreak.py](../../../tests/game/test_tiebreak.py) to float `attack_speed`, no `milli_AS`; assert the simplified key preserves V.34 side-independence (B.14) incl. true mirrors.
- **Trait riders removed:** [test_trait_mechanics.py](../../../tests/game/test_trait_mechanics.py) modifier counts drop the `milli_AS` entries (e.g. 3→2 stats per stack); an `attack_speed`-mul trait still reorders ties.
- **Determinism / regression (V.2/V.14):** `workers=1` + fixed seed byte-identical within the new baseline; Commit 2 alone diffed against pre-refactor snapshots (expect ~none).
- **`stat_breakdown`:** groups by `source:` prefix; base + per-source deltas sum to `piece.stat(...)`; weather appears as a normal source row.
- **Q6 anti-runaway guard:** a test that no engine hook re-applies a stat-scaling modifier reading a stat it also feeds (or a documented convention test on the item/augment factories).

## B.9 Deferred — MS phase-split (new §D)

Movement events are currently ordered by the mover's **attack_speed** (the `_event_sort_key` sorts *all* triggered entries — both kinds — on AS; `kind` is the last tiebreak, separating only a single piece's own move-before-act). `move_speed` controls movement **frequency** (meter fill), never **order**, and has no sub-integer field. A symmetric design — float `move_speed`, split resolution into a move-phase (ordered by `round(MS*1000)`) then an action-phase (ordered by `round(AS*1000)`), dropping the `kind` tiebreak — is **cleaner** but changes combat semantics (global reposition-then-act each tick → who's in range for same-tick actions shifts). **Deferred:** its own task + win-rate validation; not bundled into this representational refactor.

## B.10 SPEC changes needed (for `/spec` — T.29-pre)

1. **§T:** add row **`T.29-pre` — Combat stat substrate** (goal: weather→`source:`-tagged modifiers (delete `base_stats` fold) + HP/resource resync + `attack_range` floor + `(base+adds)×muls` universal compose + `source:` prefix vocab; `attack_speed` int→float, drop `milli_AS` (cadence `int(AS)`, tiebreak `round(AS*1000)`); `stat_breakdown` helper; one re-baseline). **Files:** `game/loadout.py`, `game/weather_effects.py`, `game/effects.py`, `game/models.py`, `game/content.py`, `game/scaling.py`, `game/encounter.py`, `game/combat/engine.py`, `game/traits/_packs.py`, `game/traits/mechanics.py`, `tests/game/test_tiebreak.py`, `tests/game/test_scaling.py`, `tests/game/test_trait_mechanics.py`, `docs/design/tasks/t29_item_engine_plan.md`. **Depends:** T.2, T.20, T.28d, T.33a. **Est:** M–L. **Status:** 📋 Plan.
2. **Amend §V.34:** `attack_speed` is now **float** (cadence via `int(attack_speed)`, sub-integer order via `round(attack_speed*1000)`); **`milli_AS` removed** (derived, not a stored field); sort key is **`(-round(AS*1000), champion_id, load_order, kind)`**. `move_speed`/`mana_regen`/`threat` stay int. B.14 side-independence + `load_order` unchanged. (T.29-pre)
3. **New §V (weather):** Weather Favor is applied **only** as `source="weather:<state>"` `Modifier`s through `compile_loadout` (no `base_stats` fold); the engine never reads a weather base-snapshot. Extends/relocates the T.2 application note. (T.29-pre)
4. **New §V (stat authority):** `compute_stat` is the single stat fold `(base+Σadds)×Πmuls` with a `_STAT_FLOORS` clamp (`attack_range ≥ 1`); **resources (`hp`/`max_hp`, per-`ActiveSlot` mana) are direct-set + reconciled from `stat()` after modifiers, never `Modifier` targets.** (T.29-pre)
5. **New §V (anti-runaway, Q6):** stat-scaling modifiers snapshot their value at apply time off a defined base; **no per-tick/per-event hook may apply a modifier whose value reads a stat that modifier also feeds** (prevents unbounded HP↔AP feedback). Modifiers are static values, not live formulas. (T.29-pre)
6. **New §V (source vocab):** `Modifier.source_id` uses the fixed prefix vocab `item:`/`augment:`/`passive:`/`trait:`/`weather:` (`<prefix>:<id>`); the prep-view `stat_breakdown` groups on it. (T.29-pre)
7. **New §B entry:** ability `attack_speed` muls did **not** ride `milli_AS` ([champions.py:207](../../../src/game/abilities/champions.py#L207)), desyncing tie-order from cadence (only weather + traits manually kept the pair synced, loadout.py:198 / _packs.py:41 / mechanics.py:93,114). **Fixed structurally** by the float `attack_speed` (tiebreak derives from the same value cadence reads). Recurrence guard = amended V.34. (T.29-pre)
8. **New §D row:** MS phase-split (B.9) — movement ordered by MS via a move-phase/act-phase split; combat-semantics change, deferred to its own task + sim validation.
9. **Implementation Order:** insert **`T.29-pre`** immediately before `T.29a` in the Phase-1b chain: `… → T.28d → T.29-pre → T.29a → T.29b → T.31`.
10. **LIVING docs to update on build (B.11):** `docs/live/systems/scaling.md`, `docs/live/systems/combat.md`, `docs/live/content/traits.md` (all reference `milli_AS` + the sort key) — flip their `milli_AS` prose to the float-AS model; add a weather-modifier note where the weather fold is described.

## B.11 LIVING docs to update (build step)

- [docs/live/systems/scaling.md](../../../docs/live/systems/scaling.md) — `milli_AS` storage + sort key (lines 22,32,37) → float `attack_speed`, derived order.
- [docs/live/systems/combat.md](../../../docs/live/systems/combat.md) — `_event_sort_key` description (lines 58-60) → simplified quantized key.
- [docs/live/content/traits.md](../../../docs/live/content/traits.md) — `milli_AS` rider note (line 32) → removed; `attack_speed` mul moves order directly.
- Weather application note wherever the `_apply_weather_to_piece` fold is described → modifier emission.
