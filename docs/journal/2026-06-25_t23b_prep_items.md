# 2026-06-25 — T.23b: Prep items (equip seam) + a concurrency lesson

## Overview

Added the item layer to Prep: a `game/inventory.py` equip seam + an equip panel
in the Prep inspect view. This is the last piece of the MVP run-loop slice (the
loop was already playable without items).

## What landed

- **`game/inventory.py`** — `equip_item(run, champion, item_id)` /
  `unequip_item(...)`. Moves items between `Run.inventory` and `Champion.items`.
  **Auto-combines on double-equip:** if the champion holds a component that pairs
  with the incoming item into a recipe (`items.combine`), the two fuse into the
  combined item in one slot (works even at the 3-item cap); else a free slot (≤3).
  Combine partner is the **first** held item that pairs — deterministic (V.2).
- **`ui/views/prep.py`** — the inspect panel grew an Items section: equipped chips
  unequip on click; inventory chips equip onto the selected champion. All mutation
  routes through `game/inventory.py` (V.63 — no inline `champion.items` edits).
- **Tests** — `tests/game/test_inventory.py` (8: free-slot equip, not-in-inv no-op,
  ≤3 cap, auto-combine, combine-at-full, first-partner determinism, unequip round-trip).
- **Docs** — items.md equip-seam section; ui.md Prep items; SPEC T.23b ✅.

## Process notes (AI collaboration)

- **`git add -A` fought concurrent work — the real lesson of the day.** T.38 (node
  rewards + Hearts) was being built **in the same worktree** in parallel. My earlier
  `git add -A` on the T.13/T.15b commits swept T.38's then-uncommitted SPEC.md edits into
  *my* commits — and because both tasks had independently grabbed `V.70` from `/spec`
  (T.13 = canvas-viz, T.38 = node-reward), HEAD ended up with a **duplicate V.70** (a
  monotonic-numbering violation). Fix: switched to **targeted `git add`** of only my files,
  and renumbered the lower-blast-radius invariant — my canvas-viz `V.70 → V.72` (T.38's
  V.70/V.71 are referenced across economy/reward/models/encounter/tests, far more surface)
  — across SPEC + ui.md + CLAUDE.md + the viz/summary docstrings. Standing rule now: **in a
  shared worktree, never `git add -A`; stage your own paths explicitly.**
- **Shared commit, by request.** Rather than keep disentangling, the user chose to bundle
  T.23b + T.38 into one shared commit on a shared branch and PR the whole slice to main at
  once. Correct call given they're interleaved in the same files (SPEC, economy, reward).
- **Coexistence verified, not assumed.** Ran the full suite after the renumber — 1455 green
  (my 8 inventory tests + T.38's reward/Hearts tests together), confirming the two streams
  compose. T.38 had even adapted my `test_run_loop.py` first-loss test to their Hearts
  model, so the integration was mutual.
- **Mutable Champion, cap enforced by the seam.** `Champion` is `@dataclass(slots=True)`
  (not frozen), so `equip_item` mutates `items` in place — but the ≤3 cap is only checked
  in `__post_init__`, never on mutation, so the seam enforces it itself. Verified the
  decorator before relying on in-place mutation rather than `dataclasses.replace`.

## Prompting-strategy reflection

The day's lesson wasn't about a feature — it was about **tooling discipline under
concurrency**. `git add -A` is a convenient default that silently becomes destructive the
moment another agent/human shares the worktree. The cost showed up one layer removed (a
duplicate invariant in committed history), which is exactly the kind of damage that's
invisible at commit time and expensive later. The fix was cheap *because* SDD makes the
spec the single source of truth: the collision was a grep away, and renumbering was
mechanical. Takeaway for driving agents in shared trees: constrain the blast radius of
every write — explicit `git add <paths>`, never `-A` — and let the spec's numbering
discipline surface collisions early.
