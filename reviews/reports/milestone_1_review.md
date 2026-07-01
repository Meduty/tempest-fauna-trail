# Milestone 1 Review — Design Alignment Check

**Date:** 2026-05-30  
**Reviewer:** Design audit against stated game vision  
**Scope:** SPEC.md, views_spec.md, combat_system_proposal.md, content catalogs, code structure

---

## Stated Vision (Summary)

> A roguelike auto-chess game under a Spirit Island theme. Players start with a small budget and one champion, progress through reward-fight/normal-fight/other nodes, level up team size, gain items and currency, and build a strong team. Core decisions: item optimization, traits, team synergies, and weather effects. Before every fight: a prep phase with piece movement, item use, bench/field swaps, board placement, and a champion shop for acquiring or stacking champions.

---

## Verdict: Does SPEC.md Follow This Goal?

**Mostly yes, with meaningful gaps in three areas.**

The SPEC is a strong, detailed technical plan that correctly captures:
- ✅ Roguelike node-based progression (50 nodes, 6 stages, reward/fight/augment/boss types)
- ✅ Auto-chess combat (tick-based auto-resolve, no player micro during fights)
- ✅ Weather as a core differentiator (two decoupled weather systems, live API data)
- ✅ Champion stacking/leveling (3-copy merge, 10 tiers, 3 levels — standard TFT mechanic)
- ✅ Trait/synergy system (Kinship + Calling + Affinity breakpoints, well-designed catalog)
- ✅ Prep phase concept (placement, bench/board swap, enemy preview, shop panel)
- ✅ Economy (Amber currency, Tempest XP for team-size, tier-based cost)
- ✅ Item system (8-component combinatorics, 36 items, emblems, special items)

However, three areas are **underdeveloped or misaligned** relative to the stated vision:

---

## Area 1: The Shop & Economy Loop — Status: Undesigned (Critical Gap)

**The Problem:** The vision emphasizes the champion shop as a central mechanic — players "go through nodes to gain currency" and "have access to the champion shop where they can acquire new champions or stack existing ones." In TFT, the shop is the heartbeat of the game: refresh, buy, sell, level up. 

**What SPEC.md says:**
- D.15 explicitly states: *"Shop: lives in the Prep view; its inventory model, refresh rule, and stage availability gating are **open**"*
- D.13 says: *"shop reroll undecided"*
- T.22 (Meta progression — augment, supply, economy, team-size cap) is only 📋 Plan status
- The views_spec.md §6.4 mentions "Shop panel for purchasable pieces/upgrades" but defers all mechanics

**Impact:** Without a functioning shop economy, the game loop collapses. Players cannot make the "core decision" of team-building if they cannot acquire champions mid-run. This is the #1 gap between vision and plan.

**Recommendation:** T.22 must be elevated to a critical-path task. The shop needs at minimum:
- A refresh mechanism (automatic per node? manual reroll for Amber?)
- Stage-gated tier availability (higher tiers appear later)
- Buy/sell pricing (`Cost(T) = T` is mentioned but not implemented)
- Team-size-cap gating on how many pieces can be fielded

---

## Area 2: Starting Conditions & Early Game — Status: Implicit/Unclear

**The Problem:** The vision says "players start with some small starting budget of currency and one champion." The SPEC doesn't clearly define:
- What the player starts with (one champion? which one? random? chosen?)
- Starting Amber budget
- Initial team size cap
- Whether there's an initial draft/recruit phase or the player enters the first node with a preset

**What exists:**
- The `/recruit` route in the SPEC's Flet route table says "Pick ~3 champions from roster of 8" — this contradicts "start with one champion"
- The views_spec.md's flow is `Main Menu → Trail → Prep → Combat` with no explicit recruit/draft step
- D.16 acknowledges the route table is stale vs. views_spec.md

**Impact:** Medium. The game needs a clear "run initialization" step. The vision says one champion + small budget; the SPEC says recruit 3 from 8. These need reconciliation.

**Recommendation:** Decide and document:
- Start with 1 champion (chosen or random) + starting Amber for early shopping? (closer to vision)
- Or start with a mini-draft of 3? (closer to current SPEC `/recruit` route)
- Either way, make it explicit in a T-task or updated Section G.

---

## Area 3: Item System Integration — Status: Designed but Not Connected

**The Problem:** The vision emphasizes "optimising item use" as a core decision. The item_catalog.md is impressively detailed (8 components, 36 combined items, emblems, special items), but:
- D.9 states: *"no item model, pool, or effects exist — **undesigned**"* (referring to the engine substrate)
- No T-task covers item implementation — it's not in the task table at all
- Item acquisition (drops from REWARD nodes, shop purchases) has no implementation plan
- Item equip/unequip UI in the Prep phase is spec'd in views_spec.md §6.4 but has no backing task

**Impact:** High. Items are one of the three stated core decisions (items, traits, synergies). The content design exists, the systems substrate is sketched in effect_systems_design.md §8, but there's no implementation task to bridge the two.

**Recommendation:** Add a dedicated T-task for the item system engine (model, equip logic, effect resolution, recipe map, drop tables). This should land before or alongside T.22 (economy) and T.28 (traits).

---

## Secondary Observations

### What's Working Well

1. **Combat system is solid.** The tick-based engine with abilities, passives, statuses, formation, and weather is fully implemented and tested. This is the strongest pillar.
2. **Content depth is impressive.** 60+ champions, trait catalog, item catalog, boss roster — all designed before implementation. This is good planning.
3. **Weather integration is unique and complete.** The dual weather system (Weather Favor + Affinity Clash) is implemented, tested, and well-documented. It genuinely differentiates the game.
4. **Playtesting infrastructure exists.** The CLI tools (T.27) and power simulation (T.25) show investment in balance — rare for a student project.
5. **Code architecture is clean.** V.1 (no Flet in game/) is enforced; the game engine is testable and portable.

### Minor Concerns

| Issue | Severity | Note |
|-------|----------|------|
| D.16 route drift (SPEC says `/recruit`, `/map`, `/summary`; views_spec says `/trail`, `/prep`) | Low | Acknowledged in SPEC; just needs a sync pass |
| No explicit "game over / run loss" flow documented | Low | Boss defeat = run failed, but what about regular fight losses? |
| "Spirit Island theme" from vision is not present | Low | The theming is "animal spirits + weather" not Spirit Island specifically; this is fine and probably intentional |
| HP carryover (D.7) still undecided | Medium | This significantly affects difficulty and economy tuning |
| 50-node route may be too long for "15-25 minute" sessions | Medium | Proposal says 15-25 min; 50 nodes with prep phases could take 45-60 min unless most are auto-skippable |

---

## Should the Plan Be Reevaluated?

**Yes, in a targeted way.** The SPEC is a good plan overall — it does not need a rewrite. But the implementation order should be adjusted:

### Recommended Priority Shift

1. **Promote T.22 (Economy/Shop) to Phase 1 critical path.** Without economy, there is no game loop. It currently sits at 📋 Plan with no dependencies resolved.
2. **Add a new T-task for Item Engine.** Content is designed; implementation is not tracked.
3. **Define run-start conditions explicitly.** One paragraph in SPEC Section G or a mini-task.
4. **Resolve D.7 (HP carryover) before UI work.** It affects the Trail view's team panel and the entire difficulty curve.
5. **Consider session length.** If 50 nodes is intentional, fast-forward mechanics or shorter prep phases for non-boss nodes should be designed.

### Current Phase Status (honest assessment)

| Phase | Status | Blocker |
|-------|--------|---------|
| Phase 1: Core Logic | ~90% complete | T.28 (traits) not started |
| Phase 2: API + Data | ✅ Complete | — |
| Phase 3: UI + Combat | Not started | T.22 (economy) blocks meaningful Prep |
| Phase 4: Visualizations | Not started | Depends on Phase 3 |
| Phase 5: Polish + Docs | Not started | Depends on all above |

---

## Summary

The SPEC.md is a **good plan** that correctly captures the auto-chess roguelike vision in most respects. Its strongest asset is the fully-implemented combat engine with weather, abilities, and balance tooling. Its main weakness is that the **player-facing decision systems** (shop, items, economy) — the things that make it feel like TFT rather than just an auto-battler — are designed in content docs but have no implementation path in the task table. 

The game engine can fight battles beautifully. What it can't do yet is let the player *build a team across a run*, which is the actual game.

**Action items for the next milestone:**
1. Implement T.22 (economy + shop)
2. Add and implement an Item Engine task
3. Codify run-start conditions
4. Decide HP carryover (D.7)
5. Begin Phase 3 UI work with economy backing it
