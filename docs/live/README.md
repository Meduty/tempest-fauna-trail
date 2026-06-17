# docs/live — the always-current docs

Everything under `docs/live/` is **LIVING**: it describes how a system or
content area *works right now* and **must match the code**. Drift here is a
bug, the same as a failing test — audited by the `/check` skill.

This is the mid-level layer the rest of the docs were missing:

| Layer | Doc | Role | Currency |
|---|---|---|---|
| Contract | `SPEC.md` | invariants (§V), tasks (§T), bugs (§B) | LIVING (`/spec`-gated) |
| Map | `ARCHITECTURE.md` | where things live + how they interact | LIVING |
| **Reference** | **`docs/live/**`** | **how each subsystem / content area works now** | **LIVING** |
| Record | `docs/design/**` | how we *planned/built* X (task plans, proposals) | FROZEN |
| History | `docs/journal/**` | why, chronologically | FROZEN |

**LIVING vs FROZEN is the rule that stops drift.** A reader (human or agent)
trusts a LIVING doc as current and a FROZEN doc as a dated snapshot. The bug we
keep paying down is reading a frozen task plan as if it were live. So:

- `docs/live/` is reconciled to code on every change that touches its subject.
- `docs/design/` is **never** retro-edited to match new code — it's the record
  of a decision at a moment. When a task lands, distil the durable "how it
  works" into the matching `docs/live/` doc; leave the plan frozen.

## Header convention

Every `docs/live/` doc starts with:

```
> **Status: LIVING** — must match `<code path(s)>`. Audited by `/check`.
> **Scope:** <one line>. **Reconciled:** <YYYY-MM-DD @ commit-ish>.
```

Every `docs/design/` and `docs/journal/` doc should carry (top):

```
> **Status: FROZEN (<task/date>)** — historical record; verify against code.
```

## How it stays honest

- **Convention** — the headers above declare intent; `docs/live/` = "trust me",
  `docs/design/` = "I was true once".
- **`/check`** — read-only audit. Extracts every backticked code reference in
  `docs/live/`/SPEC/ARCHITECTURE and verifies it resolves in the tree; checks
  §V invariants and content counts. Run it after touching a system, and before
  relying on a living doc. It reports; it never edits.
- **Discipline** — touching `src/game/combat/` ⇒ update `systems/combat.md` in
  the same change (like the mandatory journal entry for milestones).

Keep living docs **concise**: "how it works now + where it lives", not a
re-derivation of the code. Exhaustive design rationale belongs in the frozen
plan/journal; this layer is the durable, current summary.

## Index

Status: ✅ written & `/check`-clean · 🔶 stub (header + scope + anchors, prose TBD).

### Systems — `docs/live/systems/`
| Doc | Covers (code) | Status |
|---|---|---|
| [combat.md](systems/combat.md) | `game/combat/` (engine, context, recorder, resolve), `loadout.py`, `piece.py` | ✅ |
| [weather.md](systems/weather.md) | `game/weather_effects.py` + `loadout._apply_weather_to_piece` | ✅ |
| [formation.md](systems/formation.md) | `game/formation.py` | ✅ |
| [effects.md](systems/effects.md) | `effects.py`, `events.py`, `status.py`, `registries.py`, `piece.py`, `combat/context.py` | ✅ |
| [encounter.md](systems/encounter.md) | `game/encounter.py`, `bosses/data.py`, `map_effects.py`, `board.py` | ✅ |
| [scaling.md](systems/scaling.md) | `game/scaling.py`, `content.py` stat curves | ✅ |
| [weather_api.md](systems/weather_api.md) | `api/weather.py`, `api/cache.py`, `api/refresher.py` | ✅ |
| [save.md](systems/save.md) | `Run`/`BattleResult` serialization in `models.py` (+ planned save.py, T.14) | ✅ |
| [items.md](systems/items.md) | `game/items/`, `loadout.py` equip, `registries.py` (`ITEM_REGISTRY`/`RUN_ACTION_REGISTRY`) | ✅ |
| [kit_design_conventions.md](systems/kit_design_conventions.md) | `abilities/`, kit-authoring conventions (Calling-honest casts) | ✅ |

### Content — `docs/live/content/`
| Doc | Source of truth (code) | Status |
|---|---|---|
| [rosters.md](content/rosters.md) | `content.py` (champion/enemy rosters), `bosses/data.py` | ✅ |
| [abilities.md](content/abilities.md) | `abilities/`, `registries.py` (id resolution) | ✅ |
| [traits.md](content/traits.md) | `traits/`, `content.py` trait vocab | 🔶 |
| [augments.md](content/augments.md) | planned (T.31, augments.py) | 🔶 |
| [items.md](content/items.md) | pointer → `systems/items.md`, `game/items/` (T.29a-d) | ✅ |

Content living docs are **thin source-of-truth pointers**: stats/IDs/counts
live in code (and `/check` verifies the counts); lore and as-designed intent
stay in the frozen `docs/design/content/` catalogs. The living doc records the
invariants ("60 champions, 1 per affinity×tier"), the ID conventions, and where
the real data is — not a copy of it.
