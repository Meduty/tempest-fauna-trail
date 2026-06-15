# 2026-06-15 — T.29b: remaining items, emblems, special run-actions

## What shipped

The second half of the item system, on top of T.29a/T.29c:

- **20 remaining combined items** (`combined.py` T.29b block) — completes the 36.
  Hook items reuse the established closure/cadence/`secs()` patterns; magnitudes
  judged against the measured combat scale (autos ~5 s, HP 600–1500, dmg 50–200).
- **6 emblems** (`emblems.py`) — `granted_traits=["<Kinship>"]` + 8% flavour stat,
  applied at §10.1 step 2.5 before `_resolve_traits` so the wearer counts toward
  the Kinship breakpoint. Crafted via the new **Spirit-Gem `combine()` branch**
  (`base.KINSHIP_OF`: 6 mapped components; wardpelt/keen_claw → None).
- **5 special run-actions** (`special.py`, `RUN_ACTION_REGISTRY`, V.24) — reforger,
  unbinding_totem, echo_acorn, glimmerdust, reclaimers_cache — operate on `Run`
  only, never imported by `game/combat/`. Spirit Gem is the 6th special, handled
  inline by `combine()` (crafting). Plus `decompose()` (any item → base components).
- **Heartwood** (Glimmerdust): `heartwood:<id>` items scaled at equip by
  `loadout._heartwood_scale` (mul/add modifiers ×1.5, procs untouched — D.21 MVP).
- **`sim_run --interactive`** — a prep shell (combine/equip/reforge/unbind/echo/
  glimmer/salvage) over a real `Run` before the route walk.

SPEC: T.29b ✅ (V.23/V.24 already covered it). Suite 1153 passed (+19 T.29b tests).

## Process notes (AI collaboration)

- **The plan saved a wrong assumption.** Plan §3.2 said the gem branch + recipe
  map were T.29b work; the code already had the full 36-key `RECIPE_MAP` (built in
  T.29a) with only the gem branch stubbed. Reading the code first (not trusting the
  frozen plan) meant T.29b was "add factories + gem branch + emblems + specials",
  not "build recipes." The CLAUDE.md "verify against code" rule paid off again.
- **Catalog said "6 special items" but only 5 are run-actions.** Spirit Gem is a
  *crafting* special, not a `Run`-mutation — it lives in `combine()`, not
  `RUN_ACTION_REGISTRY`. Easy to mis-author as a 6th no-op run-action; the catalog
  wording (§5 lists Spirit Gem among "special items") invites it. Resolved by
  treating "special" as a UI/loot category, not an implementation registry.
- **Magnitude discipline carried over from the B.23 audit.** Every new hook item's
  number was written against the combat-scale baseline from the last session
  (thorns 80, giantsbane 4% maxHP, stormscale 0.6×primary) rather than guessed —
  the "flat 200 mana / 2-dmg thorns" failure class is fresh, so I costed each proc
  in autos/HP terms as I wrote it.
- **Test-harness friction, twice:** `apply_status`/equip hooks fire with `ctx=None`
  in unit tests, and `Run.__post_init__` requires exactly one CURRENT node. Both
  are existing invariants; guarding `ctx is None` in ally-targeting items and
  copying the `_run` route-setup helper fixed it. Worth remembering these are the
  two standard stubs when unit-testing combat/run code in this repo.

### Prompting-strategy reflection

This was a large, mechanical content drop (20 + 6 + 5 factories). The efficient
shape was: read the catalog + plan once for intent, verify the substrate against
code, then batch-write all factories in one append and let the suite + a few
targeted smoke scripts (combine/emblem/run-action) catch errors — rather than
authoring one item at a time. The earlier sessions' combat-scale data and the
`secs()`/closure idioms meant near-zero design re-litigation per item. Bulk
content benefits from front-loading the conventions, then writing wide.
