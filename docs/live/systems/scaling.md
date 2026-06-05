# Stat scaling

> **Status: LIVING** — must match `src/game/scaling.py` + `content.py` stat curves. Audited by `/check`.
> **Scope:** the power curve P(tier,level) and how champion/enemy stats scale across tiers. **Reconciled:** 2026-06-05.
>
> 🔶 **STUB** — anchors only; prose TBD. ⚠️ **T.33 in flight** (3-class scaling + baseline parity) is actively reshaping this — fill once T.33a lands so the doc isn't born stale. Design: `docs/design/tasks/t18_*`, `t33_speed_scaling_plan.md`.

## Where it lives
- `scaling.py` — power curve + `stat_multiplier`.
- `content.py` — base stat blocks + per-tier scaling application.
