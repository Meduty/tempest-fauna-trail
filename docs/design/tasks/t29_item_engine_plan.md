# T29 Plan — Item Engine

> **Status:** approved — T.29a/T.29b already split in SPEC (📋 Plan). **NEW prerequisite substep `T.29-pre` added below ([Part B](#part-b--t29-pre--combat-stat-substrate-prerequisite-sequences-first)) — sequences FIRST in the T.29 block (`T.29-pre → T.29a → T.29b`).** Ready for `/build T.29a` once T.29-pre lands.
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
- §3.1 component model + **real-stat mapping** + §3.1a mana-stat primitive (rename `cost`→`mana_cost`; add `ActiveSlot.max_mana`/`start_mana`; 3 engine sites; regression-safe).
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

### 3.1a Mana-stat primitive — rename `cost`→`mana_cost`, split into `mana_cost` / `max_mana` / `start_mana`

**Rename** the existing `ActiveSlot.cost` field → **`mana_cost`** (clearer + namespaced; touch every reference — piece.py, loadout.py:99,138, engine.py:463,656, bosses.py ×6, reference.py:115, tests). `mana_cost` today conflates **threshold** (mana needed to cast) and **cap** (regen clamps to it, engine.py:830) with **no starting value**. Split it so mana items have somewhere to land without touching `mana_cost`, and so a pool can *overload* (bank past one cast):

- **`ActiveSlot`** gains two fields (all mana state stays per-slot — only `mana_regen` is a piece stat): `max_mana: int = 0` (overload cap; `__post_init__`: `if max_mana <= 0: max_mana = mana_cost * 5` — **default 5× mana_cost**, so external sources can bank up to ~5 casts out of the box) and `start_mana: int = 0` (combat-start seed). `mana_cost` (renamed), `current_mana`, `priority` unchanged in role.
- **Engine (3 sites, all per-slot):**
  - **regen tops up to `mana_cost` only** (never overloads): `if slot.current_mana < slot.mana_cost: slot.current_mana = min(slot.mana_cost, slot.current_mana + mr_val)` (was the unconditional `min(slot.cost, …)`, engine.py:830). The `< mana_cost` guard is a no-op unless already overloaded — passive regen gives you exactly your next cast, never banks. **Only start_mana / on-event gain overload** (matches the design intent: overload is item-granted, not free from waiting).
  - cast → `slot.current_mana -= slot.mana_cost` (was `= 0.0`, engine.py:662) so externally-added overflow carries = overload.
  - combat start (new) → `slot.current_mana = min(slot.max_mana, slot.start_mana)` per slot.
- **Regression-safe (V.2, no re-baseline) — independent of the 5× default:** because regen is guarded at `mana_cost`, a no-item pool reaches **exactly** `mana_cost` then casts (`-= mana_cost` ≡ old `= 0`); it never overshoots, so the `max_mana` value is irrelevant without items. `start_mana == 0` → no start seed. ⇒ **byte-identical** to today. Bosses need **no rewrite** beyond the field rename (still `ActiveSlot(mana_cost=…)`; `max_mana` auto-defaults to 5× `mana_cost`, unused without items; `start_mana` 0); the `phase_hook_test` multi-slot fixture is untouched (per-slot model preserved).
- **Starting-mana items:** equip step adds `slot.start_mana += S` (and `slot.max_mana = max(slot.max_mana, slot.start_mana)` only if a grant exceeds the 5× default). Seeds `current_mana` at combat start → instant first cast + bankable overflow. Additive + clamped → **bug-free** (unlike cost-reduction). This is the one item path that writes a slot; carried on the bundle via a new `slot_mana_start` field (§3.4) applied in `compile_loadout`'s equip step.
- **On-event mana gain** (T.29b Deepwell/Relentless Spear) → hook calling a new `ctx.grant_mana(piece, amount)` helper, clamped to `max_mana` (the 5× cap) → banks past cost = overload. Event-driven, stays a hook; **no mana-hook items in the 16-core cut**, so T.29a needs zero hook work here.

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
- **Mana primitive: rename `cost`→`mana_cost`, split `mana_cost`/`max_mana`/`start_mana`** (§3.1a) — all mana state stays per-slot except `mana_regen` (piece stat); `max_mana` defaults 5× `mana_cost`; regression-safe (regen guarded at `mana_cost`). Mana items grant **either `mana_regen` or `start_mana`, never reduce `mana_cost`** — `mana_cost` is a fixed per-ability knob; kills the negative-cost stacking bug.
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
- Mana handling → **rename `cost`→`mana_cost`, split `mana_cost`/`max_mana`/`start_mana`** (§3.1a); all per-slot except `mana_regen` (piece stat); `max_mana` defaults 5× `mana_cost`. Mana items grant `mana_regen` **or** `start_mana`, **never reduce `mana_cost`** — kills the negative-cost stacking bug; enables starting mana + overload (bank past `mana_cost` up to `max_mana`, regen guarded so overload is item-only).
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
- **Mana primitive (§3.1a):** field renamed `cost`→`mana_cost`; `max_mana` defaults 5× `mana_cost`, `start_mana==0`, regen guarded at `mana_cost` → no-item fights **byte-identical** to today (pool tops at `mana_cost`, `-= mana_cost` ≡ old `= 0`). Springtear shifts `mana_regen` (a piece stat) — no slot touch, **no item ever changes `mana_cost`**. A `start_mana` grant seeds `current_mana` at combat start and overloads past `mana_cost` up to `max_mana`; `ctx.grant_mana` clamps to `max_mana`.
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
5. All item procs deterministic (no RNG); mana primitive (§3.1a) — `cost` renamed `mana_cost`, split `mana_cost`/`max_mana`/`start_mana` per-slot (`max_mana` 5× default), `mana_regen` piece stat; no item touches `mana_cost`; no-item fights byte-identical.
6. `tests/game/test_items.py` (+ loadout/encounter/CLI tests) pass; full suite green; no-item regression intact.

## 10. SPEC changes needed (for `/spec`)

1. **§T:** replace the T.29 row with **T.29a** (engine + 16 core items; depends T.1, T.20, T.22; Est M–L) and **T.29b** (remaining 20 + emblems + special items + CLI driver; depends T.29a, T.28a; Est M–L); both 📋 Plan; both cite `docs/design/tasks/t29_item_engine_plan.md`. Update Implementation-Order Phase 1b to `… → T.29a → T.29b → T.31`.
2. **New §V invariant:** items apply only via `compile_loadout` (combat-facing) or `RUN_ACTION_REGISTRY` (run-facing, never imported by `combat/`); ≤3 equipped items per piece; item procs deterministic (cadence/flags, no RNG). (T.29)
2a. **New §V invariant (mana):** `ActiveSlot` carries `mana_cost`/`max_mana`/`start_mana` (renamed from `cost`; `max_mana` defaults to **5× `mana_cost`**, `start_mana` to 0); `mana_regen` is the only piece-level mana stat. **No item ever modifies `mana_cost`** — mana items grant `mana_regen` (Modifier) or `start_mana` (slot, additive+clamped) only. Regen is guarded at `mana_cost` (only `start_mana`/`grant_mana` overload up to `max_mana`), keeping no-item combat byte-identical (V.2). (T.29a)
2b. **§T file-list:** add `game/piece.py`, `game/combat/engine.py`, `game/combat/context.py`, `game/effects.py` to the T.29a row (the §3.1a mana primitive).
3. **New §V invariant:** special items (`RUN_ACTION_REGISTRY`) operate on `Run` only and are **never** referenced from `game/combat/` — combat sees only their result (§8.4). (T.29)
4. **§D.9:** mark item system implemented in T.29a/b; leave open only magnitude tuning.
5. **§D.12:** update to "REWARD loot drops fully integrated in T.29a — weights authored there (45% component / 20% combined / 15% Amber / 15% champion recruit / 5% special; first-pass, tunable); boss defeat = 3-pair pick via `generate_boss_loot`. T.22 never defined weights." Mark §D.12 resolved by T.29a. Shop stays champions-only (T.22 contract).
6. **New §B entry:** doc drift — `effect_systems_design.md` §8.1 "15 combined" and the dangling "§14" 3-slot ref; reconciled to `item_catalog.md` (36, 8-component matrix) and §3.3 of this plan.
7. **T.29 planning note** (T.18-T.31 block): item engine on the T.20 substrate; real-stat mapping (mana per-slot, flat-add magnitudes); emblems gate on T.28a; special items are run-actions with a `sim_run` interactive driver shared with T.31; Heartwood = generic stat-mult (MVP).
8. **New §D rows (post-MVP):** (i) authored per-item Heartwood variants (MVP ships the generic ×1.5 stat-mult); (ii) bosses wearing items (T.30 kits tuned without — needs sim retune pass if revisited).

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
