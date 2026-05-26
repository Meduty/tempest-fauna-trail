# Engine Split — Playtest Implications

The codebase ships **two combat entry points**. Every playtest tool must choose
one. This is the most important reality-check finding from designing the
playtest surface.

## The split

### Legacy: `resolve_combat(team, enemies, weather, *, node_id) -> BattleResult`

- File: `src/game/combat/legacy.py`
- Public re-export: `src.game.combat.resolve_combat`
- Self-contained tick loop (no `CombatContext`, no event bus).
- Applies **Weather Favor** stat packs via `apply_weather()` at init.
- Applies **Affinity Clash** damage triangle via `damage_modifier()` per hit.
- Emits a complete `BattleEvent` stream stored in `BattleResult.events`.
- Consumed by `combat_log.format_combat_log(result, team, enemies)` for the
  existing human-readable log.
- **Does not invoke abilities, passives, statuses, board cells, or map effects.**

### New: `compile_loadout` + `CombatContext` + `combat/loop.run`

- Files: `src/game/loadout.py`, `src/game/combat/context.py`,
  `src/game/combat/loop.py`.
- Built for T.20 (ability/passive/status framework) and T.21 (challenges,
  bosses, map effects).
- Mutator API on `CombatContext`; content interacts only via this surface.
- `combat/loop.run(ctx)` returns just `"team" | "enemy" | "draw"` — no
  `BattleResult`, **no events list**.
- Applies **Affinity Clash** via `ctx.deal_damage` → `damage_modifier`.
- **Does not apply Weather Favor stat packs** (`apply_weather` is never called
  in the loadout build path). Treat this as a known gap, not a playtest bug.

## What this means for playtest tools

| Goal | Engine | Why |
|---|---|---|
| Show a battle as text log with HP trace | Legacy | `BattleResult.events` + `combat_log` already exist |
| Balance sweep on stat baselines | Legacy | Deterministic, fast, weather Favor included |
| Exercise abilities / passives / statuses | New | Legacy ignores them entirely |
| Boss fights with map effects | New | Requires `attach_map_effect(effect_id, ctx, seed)` |
| Challenge encounters (champion-as-enemy) | Either | Pure stat / weather check works on legacy |

## DebugRecorder — bridging the gap

For the new engine to produce a renderable trace, the playtest layer must add
a thin subscriber:

```python
# tools/playtest/debug_recorder.py
class DebugRecorder:
    """Subscribes to CombatContext.bus, records tick-ordered events."""
    def __init__(self, bus, ctx):
        self.events: list[tuple[int, str, dict]] = []  # (tick, name, payload)
        for hook_name in (
            "on_attack_landed", "on_damage_dealt", "on_cast",
            "on_cast_complete", "on_death", "on_status_applied",
            "on_status_expired", "on_heal", "on_spawn",
        ):
            bus.subscribe(Hook(hook=hook_name, fn=self._record, ...))
        self._ctx = ctx

    def _record(self, ev, **kw):
        self.events.append((self._ctx.current_tick, ev.__class__.__name__, ev))

    def render(self) -> list[str]:
        # Mirror format_combat_log shape so output is interchangeable.
        ...
```

This keeps `src/game/` Flet-free (V.1) and untouched — the recorder lives in
`tools/playtest/`, hooks into the existing bus API, and produces text using the
same grouping/format conventions as `combat_log.py`.

## When the split should close

Eventually the legacy engine should either be deleted or rebuilt on top of
`CombatContext`. That is **not in scope for playtesting**. Playtest tools
work with what exists today and surface the split so users can pick the right
tool for the right question.
