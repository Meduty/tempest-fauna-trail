"""Champion shop — stage-gated tier rolls + buy / sell / reroll (T.22).

Pure game logic — no Flet imports, no I/O (V.1). Shop offers are
seed-deterministic: ``(run_seed, visit_index, reroll_count)`` → the same 5 ids,
mirroring the T.19 encounter contract. Lives in the Prep view (SPEC §D.15); this
module is the headless economy substrate the UI will drive.

Tier availability is gated by stage (cheap high-tier units cannot be rushed —
T.18 §5). Tier-10 Primordials are boss-only and never appear in the shop, so the
buyable ceiling is T9 (SPEC §D.15's "Tier 1-10" read as "up to the buyable max").
The concrete stage→tier weight table is authored here and in the t22 plan doc.
"""
from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING, Final

from . import economy
from .content import CHAMPION_DEF_BY_ID
from .encounter import shop_seed, supply_seed
from .route import stage_of

if TYPE_CHECKING:
    from .models import Run

# ---------------------------------------------------------------------------
# Shop constants (SPEC §D.13 / §D.15)
# ---------------------------------------------------------------------------

SHOP_SLOTS: Final[int] = 5
REROLL_COST: Final[int] = 1  # Amber; first reroll each node is free
SUPPLY_SLOTS: Final[int] = 5  # SUPPLY node: pick 1-of-5 free champion offers

# ---------------------------------------------------------------------------
# Stage → tier weight table (SPEC §D.15)
# ---------------------------------------------------------------------------

# Relative draw weights per buyable tier (T1-9), gated by stage. Stage 1 sees
# T1-2 only; the band slides up and widens to T1-9 by stage 6 with higher-tier
# weight. Cross-checked against TFT shop-odds (rising windows, ~1% top-tier).
STAGE_TIER_WEIGHTS: Final[dict[int, dict[int, float]]] = {
    1: {1: 0.70, 2: 0.30},
    2: {1: 0.45, 2: 0.35, 3: 0.18, 4: 0.02},
    3: {1: 0.25, 2: 0.35, 3: 0.25, 4: 0.13, 5: 0.02},
    4: {1: 0.15, 2: 0.25, 3: 0.30, 4: 0.20, 5: 0.08, 6: 0.02},
    5: {1: 0.10, 2: 0.15, 3: 0.25, 4: 0.25, 5: 0.15, 6: 0.08, 7: 0.02},
    6: {1: 0.05, 2: 0.10, 3: 0.15, 4: 0.20, 5: 0.22, 6: 0.15, 7: 0.08, 8: 0.04, 9: 0.01},
}

# Buyable champion ids grouped by tier (T10 Primordials excluded), sorted for
# deterministic indexing.
CHAMPIONS_BY_TIER: Final[dict[int, tuple[str, ...]]] = {
    tier: tuple(sorted(d.id for d in CHAMPION_DEF_BY_ID.values() if d.tier == tier))
    for tier in range(1, 10)
}


def _assert_table() -> None:
    for stage_index, weights in STAGE_TIER_WEIGHTS.items():
        assert 1 <= stage_index <= 6, f"bad stage index {stage_index}"
        for tier in weights:
            assert CHAMPIONS_BY_TIER.get(tier), f"stage {stage_index}: no champions at tier {tier}"
        assert 10 not in weights, f"stage {stage_index}: T10 Primordials are not buyable"


_assert_table()


# ---------------------------------------------------------------------------
# Pure offer roll
# ---------------------------------------------------------------------------


def _roll_offers(rng: Random, stage_index: int, slots: int) -> list[str]:
    """Draw ``slots`` champion ids via stage-gated tier weights (consumes rng)."""
    if stage_index not in STAGE_TIER_WEIGHTS:
        raise ValueError(f"no shop tier weights for stage {stage_index}")
    weights = STAGE_TIER_WEIGHTS[stage_index]
    tiers = sorted(weights)
    tier_weights = [weights[t] for t in tiers]
    picks: list[str] = []
    for _ in range(slots):
        tier = rng.choices(tiers, weights=tier_weights, k=1)[0]
        picks.append(rng.choice(CHAMPIONS_BY_TIER[tier]))
    return picks


def roll_shop(
    run_seed: int,
    visit_index: int,
    stage_index: int,
    *,
    slots: int = SHOP_SLOTS,
    reroll_count: int = 0,
) -> list[str | None]:
    """Roll ``slots`` champion offers for a stage, seed-deterministically.

    Each slot first draws a tier by the stage weight table, then a uniform
    champion of that tier. Same ``(run_seed, visit_index, reroll_count)`` → same
    offers.
    """
    rng = Random(shop_seed(run_seed, visit_index, reroll_count))
    return list(_roll_offers(rng, stage_index, slots))


# ---------------------------------------------------------------------------
# SUPPLY node resolution (SPEC §D.15 / t22 plan §3)
# ---------------------------------------------------------------------------


def generate_supply_offer(
    run_seed: int,
    node_index: int,
    stage_index: int,
    *,
    slots: int = SUPPLY_SLOTS,
) -> list[str]:
    """Generate the SUPPLY node's free champion offers, tier-scaled to stage.

    Deterministic via the T.19 ``CH_SUPPLY`` channel. Item bundles are deferred
    to T.29 — this returns champion ids only for now.
    """
    rng = Random(supply_seed(run_seed, node_index))
    return _roll_offers(rng, stage_index, slots)


def take_supply_champion(run: "Run", champion_id: str) -> bool:
    """Recruit a SUPPLY-offered champion for free (no Amber cost).

    Adds a copy (auto-levelling like a buy) without charging. Returns ``False``
    for unknown ids, tier-10 Primordials (boss-only), or an already-maxed unit.
    """
    champ_def = CHAMPION_DEF_BY_ID.get(champion_id)
    if champ_def is None or champ_def.tier == 10:
        return False
    if run.champion_copies.get(champion_id, 0) >= economy.MAX_COPIES:
        return False
    copies = run.champion_copies.get(champion_id, 0) + 1
    run.champion_copies[champion_id] = copies
    economy._materialize_champion(run, champion_id, economy.level_from_copies(copies))
    return True


# ---------------------------------------------------------------------------
# Run-stateful helpers (mutate the passed Run, no I/O)
# ---------------------------------------------------------------------------


def _stage_index(run: "Run", stage_index: int | None) -> int:
    if stage_index is not None:
        return stage_index
    return stage_of(run.current_node_index).index


def refresh_shop(run: "Run", stage_index: int | None = None) -> None:
    """Auto-refresh the shop on node/Prep entry (free); resets the reroll counter."""
    stage = _stage_index(run, stage_index)
    run.shop_offers = roll_shop(run.seed, run.current_node_index, stage)
    run.shop_rerolls = 0


def reroll_cost(shop_rerolls: int) -> int:
    """Amber cost of the next manual reroll (the first each node is free)."""
    return 0 if shop_rerolls == 0 else REROLL_COST


def reroll_shop(run: "Run", stage_index: int | None = None) -> bool:
    """Manually reroll the offers. First reroll each node is free, then 1 Amber.

    Returns ``False`` (no-op) if the reroll is unaffordable.
    """
    cost = reroll_cost(run.shop_rerolls)
    if cost > run.amber:
        return False
    run.amber -= cost
    run.shop_rerolls += 1
    stage = _stage_index(run, stage_index)
    run.shop_offers = roll_shop(
        run.seed, run.current_node_index, stage, reroll_count=run.shop_rerolls
    )
    return True


def buy_from_shop(run: "Run", slot: int) -> bool:
    """Buy the champion in ``slot``; on success the slot is consumed (set None).

    Returns ``False`` (no-op) for an out-of-range / empty slot or a failed buy
    (unaffordable / not buyable).
    """
    if not 0 <= slot < len(run.shop_offers):
        return False
    champion_id = run.shop_offers[slot]
    if champion_id is None:
        return False
    if economy.buy_champion(run, champion_id):
        run.shop_offers[slot] = None
        return True
    return False
