# T29 Plan — Item Engine

> **Status:** approved — T.29a/T.29b already split in SPEC (📋 Plan). Ready for `/build T.29a`.
> **Depends:** T.1 (models — done), T.20 (effect substrate / `ITEM_REGISTRY` / `register_item` — done), **T.22** (Amber economy, `Run` shop/inventory — done; drop-table weights **owned by T.29a** per §3.7 decision). **T.29b emblems additionally depend on T.28a** (trait counting consumes emblem `granted_traits`). **T.29b special-item CLI driver shares the `sim_run` interactive shell with T.31** — coordinate.
> **Resolves:** SPEC §D.9 (item system — components, recipes, emblems, special items, 3 slots) and the REWARD-drop half of §D.12.
> **Design source of truth:** [`item_catalog.md`](../content/item_catalog.md) (8 components, 36 combined, 6 emblems, 6 special, the §3 16-item core cut) + [`effect_systems_design.md` §8](../systems/effect_systems_design.md) (substrate: `BASE_COMPONENTS`, `RECIPE_MAP`, item factories, §8.4 run-actions, `combine()`) + §10.1 (application order).
> **What this plan adds beyond those:** the **real component→stat mapping** (the §8 sketch uses fake keys — **flat add chosen over mul**), the **mana-per-slot handling** (mana is not a `Piece` stat), the **persistent equip model** (`Champion.items`), and a drift fix for the §8.1 "15 combined" / dangling "§14" references. **Drop-table weights (§D.12)**: T.29a owns a first-pass weight table (components, combined, Amber, champion recruit bucket) — flagged tunable; §3.7.

---

## 0. Two-substep split (T.29a → T.29b)

The seam is **combat-facing vs meta/cross-task**. T.29a is self-contained (deps done after T.22); T.29b pulls in T.28 (emblems) and the prep-layer run-action driver.

### T.29a — Component + combined-item engine + 16 core items (Est: M–L)
- §3.1 component model + **real-stat mapping** + mana-per-slot handling.
- §3.2 `RECIPE_MAP` (full 8×8 = 36 keys) + `combine()` (recipes only; gem branch stubbed for b).
- §3.3 equip model: `Champion.items` (≤3, persistent) → threaded into `piece_from_champion`; `Piece.items` already exists ([piece.py:43](../../../src/game/piece.py#L43)); apply item bundles in `compile_loadout` (§10.1 step 5).
- §3.4 `@register_item` factories for the **16 core-cut items** (modifier + hook, closure-per-combat) + 8 raw components.
- §3.7 REWARD-node item drops + boss 3-pair loot (deterministic via `CH_LOOT`; T.29a authors the §D.12 weight table).
- **Files:** `game/items/` (`base.py`, `recipes.py`, `combined.py`), `game/loadout.py`, `game/models.py`, `game/encounter.py`. **Done when:** equip ≤3 enforced, recipes resolve, a hook item (e.g. Splitwind Talons) procs deterministically in a fixed-seed fight, REWARD drop is seed-deterministic.

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
| **Springtear** | **Mana (start/cost)** | **NOT a `Piece` stat** — mana lives on `ActiveSlot.cost` / `current_mana` ([piece.py:22-23](../../../src/game/piece.py#L22)). Handle in a dedicated equip step: grant `+30_000` starting `current_mana` and reduce `slot.cost` by `30_000`. Do **not** emit a base-stats `Modifier`. |

**Magnitude: flat add** (TFT-style). A +10 Fang is meaningful at T1 (~+20% STR) and weaker at T10 (~+2.5% STR) — that's intentional; items favour early/mid. Flag all values as first-pass; retune via sim. `crit_chance` and mana already use flat by nature.

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
- **Mana via slot, not stat** (§3.1) — Springtear-class items handled in the equip step.
- **Flat-add modifiers** for all component stats (§3.1) — TFT-style, items favour early/mid game; tunable.
- **Shop sells champions only** — items never enter the shop (T.22 contract; §3.7).
- **Boss loot = 3-pair pick** via `generate_boss_loot` (§3.7) — deterministic, player picks one pair.

## 5. Authored values (first pass — tunable)

**Components** (flat add, §3.1 decision): Fang +10 strength · Talon +10 attack_speed · Heartseed +10 intelligence · Old Hide +100 hp · Stoneplate +5 armor · Wardpelt +5 resistance · Keen Claw +0.15 crit_chance · Springtear +30_000 current_mana (start) + −30_000 slot.cost.

Values are TFT-style flat — meaningful at low tiers (~15-20%), modest at T10 (~2-5%). Retune via sim after T.29a ships.

**Combined items:** each carries both parent component stats (flat add, same amounts) plus the showcase mechanic. Per-item bonus authored inline in `game/items/combined.py`, flagged first-pass. Example: Splitwind Talons (Talon+Wardpelt) = +10 AS + +5 RES + splash proc.

## 6. Drift / doc reconciliation

- **§8.1 "15 combined"** vs catalog's **36** — the effect-doc table budgets a 6-component/15-item set; catalog §"Reconciliation" extends to 8 components/36. Annotate §8.1 to point at `item_catalog.md` as the authoritative count.
- **Dangling "§14"** — item_catalog §6 cites "effect_systems_design.md §14" for 3-slot enforcement; §14 doesn't exist. This plan (§3.3) is the authority; fix the catalog ref.
- **Fake stat keys / component ids** in §8.2/§8.3 — mapped to real engine stats in §3.1; note they're illustrative.

## 7. Open questions

**Resolved here:**
- Phasing → T.29a (engine + 16 core) / T.29b (rest + emblems + special).
- Special items → backend run-actions **+ interactive CLI driver** (§3.6).
- Mana handling → slot-level, not a stat (§3.1).
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
- **Mana items:** Springtear/Deepwell/Relentless Spear affect `current_mana`/`slot.cost`, not base_stats.
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
5. All item procs deterministic (no RNG); mana handled at slot level.
6. `tests/game/test_items.py` (+ loadout/encounter/CLI tests) pass; full suite green; no-item regression intact.

## 10. SPEC changes needed (for `/spec`)

1. **§T:** replace the T.29 row with **T.29a** (engine + 16 core items; depends T.1, T.20, T.22; Est M–L) and **T.29b** (remaining 20 + emblems + special items + CLI driver; depends T.29a, T.28a; Est M–L); both 📋 Plan; both cite `docs/design/tasks/t29_item_engine_plan.md`. Update Implementation-Order Phase 1b to `… → T.29a → T.29b → T.31`.
2. **New §V invariant:** items apply only via `compile_loadout` (combat-facing) or `RUN_ACTION_REGISTRY` (run-facing, never imported by `combat/`); ≤3 equipped items per piece; item procs deterministic (cadence/flags, no RNG). (T.29)
3. **New §V invariant:** special items (`RUN_ACTION_REGISTRY`) operate on `Run` only and are **never** referenced from `game/combat/` — combat sees only their result (§8.4). (T.29)
4. **§D.9:** mark item system implemented in T.29a/b; leave open only magnitude tuning.
5. **§D.12:** update to "REWARD loot drops fully integrated in T.29a — weights authored there (45% component / 20% combined / 15% Amber / 15% champion recruit / 5% special; first-pass, tunable); boss defeat = 3-pair pick via `generate_boss_loot`. T.22 never defined weights." Mark §D.12 resolved by T.29a. Shop stays champions-only (T.22 contract).
6. **New §B entry:** doc drift — `effect_systems_design.md` §8.1 "15 combined" and the dangling "§14" 3-slot ref; reconciled to `item_catalog.md` (36, 8-component matrix) and §3.3 of this plan.
7. **T.29 planning note** (T.18-T.31 block): item engine on the T.20 substrate; real-stat mapping (mana per-slot, flat-add magnitudes); emblems gate on T.28a; special items are run-actions with a `sim_run` interactive driver shared with T.31; Heartwood = generic stat-mult (MVP).
8. **New §D rows (post-MVP):** (i) authored per-item Heartwood variants (MVP ships the generic ×1.5 stat-mult); (ii) bosses wearing items (T.30 kits tuned without — needs sim retune pass if revisited).
