# Effects — hooks, abilities, passives, statuses

> **Status: LIVING** — must match `src/game/effects.py`, `events.py`, `status.py`, `registries.py`, `abilities/`, `piece.py`. Audited by `/check`.
> **Scope:** the T.20 effect substrate — EventBus/Hook, Modifier/EffectBundle, StatusInstance/gates, ability & passive registries, and how content plugs in via `CombatContext`. **Reconciled:** 2026-06-05.
>
> 🔶 **STUB** — anchors only; prose TBD. Design rationale (frozen): `docs/design/systems/effect_systems_design.md`, `passive_system_proposal.md`.

## Where it lives
- `effects.py` — `EventBus`, `Hook`/`HookScope`, `Modifier`, `EffectBundle`, `compute_stat`.
- `events.py` — typed event payloads (DamageEvent, AttackEvent, DeathEvent, …).
- `status.py` — `StatusInstance`, `StatusDef`, `StatusGate` (BLOCKS_* / UNTARGETABLE).
- `registries.py` — `ABILITY_REGISTRY`, `PASSIVE_REGISTRY` (+ `@register_*`).
- `abilities/` — champion/enemy/boss handlers (registered by decorator import).
- `piece.py` — per-piece modifiers/statuses/barriers/`crit_counter`.

## Key invariants
- Determinism (V.2/V.14): cadence counters, never RNG.
- combat/ never imports content modules at module scope (see `combat/resolve.py`).
