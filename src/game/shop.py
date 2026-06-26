"""Champion shop — rank-gated tier rolls + buy / sell / reroll (T.22).

Pure game logic — no Flet imports, no I/O (V.1). Shop offers are
seed-deterministic: ``(run_seed, visit_index, reroll_count)`` → the same 5 ids,
mirroring the T.19 encounter contract. Lives in the Prep view (SPEC §D.15); this
module is the headless economy substrate the UI will drive.

Tier availability is gated by **Tempest rank** (V.20, `run.tempest_rank` 1-10) —
TFT-accurate: higher rank widens + lifts the tier band (your level drives your
odds, not the map position). A fast Amber rank-rush *can* reach high tiers early.
Tier-10 Primordials are boss-only and never appear in the shop, so the buyable
ceiling is T9 (SPEC §D.15's "Tier 1-10" read as "up to the buyable max"). The
concrete rank→tier weight table is authored here and in the t22 plan doc.
"""
from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING, Final

from . import economy
from .content import CHAMPION_DEF_BY_ID
from .encounter import shop_seed, supply_seed

if TYPE_CHECKING:
    from .models import Run

# ---------------------------------------------------------------------------
# Shop constants (SPEC §D.13 / §D.15)
# ---------------------------------------------------------------------------

SHOP_SLOTS: Final[int] = 5
REROLL_COST: Final[int] = 1  # Amber; first reroll each node is free
SUPPLY_SLOTS: Final[int] = 5  # SUPPLY node: pick 1-of-5 free champion offers

# ---------------------------------------------------------------------------
# Tempest rank → tier weight table (SPEC §D.15 / §V.20)
# ---------------------------------------------------------------------------

# Relative draw weights per buyable tier (T1-9), gated by Tempest rank (1-10).
# Rank 1 sees T1-2 only; the band slides up and widens to T1-9 by rank 10 with
# higher-tier weight. Cross-checked against TFT level-odds (rising windows,
# ~1% top-tier first appearance). Rank == deployable board cap (V.20), so the
# odds curve and the team-size curve advance on the same axis.
RANK_TIER_WEIGHTS: Final[dict[int, dict[int, float]]] = {
    1:  {1: 0.75, 2: 0.25},
    2:  {1: 0.55, 2: 0.35, 3: 0.10},
    3:  {1: 0.40, 2: 0.35, 3: 0.20, 4: 0.05},
    4:  {1: 0.30, 2: 0.30, 3: 0.25, 4: 0.13, 5: 0.02},
    5:  {1: 0.22, 2: 0.25, 3: 0.25, 4: 0.18, 5: 0.08, 6: 0.02},
    6:  {1: 0.16, 2: 0.20, 3: 0.24, 4: 0.20, 5: 0.13, 6: 0.05, 7: 0.02},
    7:  {1: 0.12, 2: 0.16, 3: 0.20, 4: 0.22, 5: 0.16, 6: 0.09, 7: 0.04, 8: 0.01},
    8:  {1: 0.09, 2: 0.12, 3: 0.16, 4: 0.20, 5: 0.18, 6: 0.13, 7: 0.08, 8: 0.03, 9: 0.01},
    9:  {1: 0.06, 2: 0.09, 3: 0.12, 4: 0.17, 5: 0.18, 6: 0.16, 7: 0.12, 8: 0.07, 9: 0.03},
    10: {1: 0.04, 2: 0.06, 3: 0.09, 4: 0.13, 5: 0.17, 6: 0.18, 7: 0.16, 8: 0.11, 9: 0.06},
}

# Buyable champion ids grouped by tier (T10 Primordials excluded), sorted for
# deterministic indexing.
CHAMPIONS_BY_TIER: Final[dict[int, tuple[str, ...]]] = {
    tier: tuple(sorted(d.id for d in CHAMPION_DEF_BY_ID.values() if d.tier == tier))
    for tier in range(1, 10)
}


def _assert_table() -> None:
    assert set(RANK_TIER_WEIGHTS) == set(range(1, economy.MAX_RANK + 1)), (
        f"RANK_TIER_WEIGHTS must cover ranks 1..{economy.MAX_RANK}"
    )
    for rank, weights in RANK_TIER_WEIGHTS.items():
        for tier in weights:
            assert CHAMPIONS_BY_TIER.get(tier), f"rank {rank}: no champions at tier {tier}"
        assert 10 not in weights, f"rank {rank}: T10 Primordials are not buyable"


_assert_table()


# ---------------------------------------------------------------------------
# Pure offer roll
# ---------------------------------------------------------------------------


def _roll_offers(rng: Random, rank: int, slots: int) -> list[str]:
    """Draw ``slots`` champion ids via rank-gated tier weights (consumes rng)."""
    if rank not in RANK_TIER_WEIGHTS:
        raise ValueError(f"no shop tier weights for rank {rank}")
    weights = RANK_TIER_WEIGHTS[rank]
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
    rank: int,
    *,
    slots: int = SHOP_SLOTS,
    reroll_count: int = 0,
) -> list[str | None]:
    """Roll ``slots`` champion offers at a Tempest rank, seed-deterministically.

    Each slot first draws a tier by the rank weight table, then a uniform
    champion of that tier. Same ``(run_seed, visit_index, reroll_count)`` → same
    offers (the rank only selects the weight row; it does not feed the seed, V.2).
    """
    rng = Random(shop_seed(run_seed, visit_index, reroll_count))
    return list(_roll_offers(rng, rank, slots))


# ---------------------------------------------------------------------------
# SUPPLY node resolution (SPEC §D.15 / t22 plan §3)
# ---------------------------------------------------------------------------


def generate_supply_offer(
    run_seed: int,
    node_index: int,
    rank: int,
    *,
    slots: int = SUPPLY_SLOTS,
) -> list[str]:
    """Generate the SUPPLY node's free champion offers, tier-scaled to Tempest rank.

    Deterministic via the T.19 ``CH_SUPPLY`` channel. Item bundles are deferred
    to T.29 — this returns champion ids only for now.
    """
    rng = Random(supply_seed(run_seed, node_index))
    return _roll_offers(rng, rank, slots)


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


def _rank(run: "Run", rank: int | None) -> int:
    """The shop rank: explicit override, else the run's current Tempest rank (V.20)."""
    return rank if rank is not None else run.tempest_rank


def _frozen_flags(run: "Run") -> list[bool]:
    """Per-slot freeze flags, normalized to ``SHOP_SLOTS`` (pads/truncates)."""
    flags = list(run.shop_frozen)
    if len(flags) < SHOP_SLOTS:
        flags += [False] * (SHOP_SLOTS - len(flags))
    return flags[:SHOP_SLOTS]


def _overlay_frozen(run: "Run", fresh: list[str | None]) -> tuple[list[str | None], list[bool]]:
    """Overlay frozen slots from the *current* offers onto a ``fresh`` roll.

    A frozen slot keeps its current id (and stays frozen); every other slot takes
    the fresh roll (and is unfrozen). A frozen-but-empty slot can't exist (freeze
    is cleared on buy), so a frozen slot always carries a real id. Deterministic —
    no RNG here (V.2/V.14)."""
    old = run.shop_offers
    frozen = _frozen_flags(run)
    offers: list[str | None] = []
    flags: list[bool] = []
    for i in range(SHOP_SLOTS):
        keep = frozen[i] and i < len(old) and old[i] is not None
        offers.append(old[i] if keep else (fresh[i] if i < len(fresh) else None))
        flags.append(bool(keep))
    return offers, flags


def refresh_shop(run: "Run", rank: int | None = None) -> None:
    """Auto-refresh the shop on node/Prep entry (free); resets the reroll counter.

    **Frozen slots persist** across the refresh (and thus across Prep phases) — only
    unfrozen slots take the new roll (V.75)."""
    fresh = roll_shop(run.seed, run.current_node_index, _rank(run, rank))
    run.shop_offers, run.shop_frozen = _overlay_frozen(run, fresh)
    run.shop_rerolls = 0


def reroll_cost(shop_rerolls: int) -> int:
    """Amber cost of the next manual reroll (the first each node is free)."""
    return 0 if shop_rerolls == 0 else REROLL_COST


def reroll_shop(run: "Run", rank: int | None = None) -> bool:
    """Manually reroll the offers. First reroll each node is free, then 1 Amber.

    **Frozen slots are kept** (not rerolled, V.75). Returns ``False`` (no-op) if the
    reroll is unaffordable.
    """
    cost = reroll_cost(run.shop_rerolls)
    if cost > run.amber:
        return False
    run.amber -= cost
    run.shop_rerolls += 1
    fresh = roll_shop(
        run.seed, run.current_node_index, _rank(run, rank), reroll_count=run.shop_rerolls
    )
    run.shop_offers, run.shop_frozen = _overlay_frozen(run, fresh)
    return True


def toggle_shop_freeze(run: "Run", slot: int) -> bool:
    """Toggle the freeze flag on ``slot``. Returns the **new** frozen state.

    No-op (returns ``False``) for an out-of-range or empty slot — only a real offer
    can be frozen."""
    if not 0 <= slot < len(run.shop_offers) or run.shop_offers[slot] is None:
        return False
    flags = _frozen_flags(run)
    flags[slot] = not flags[slot]
    run.shop_frozen = flags
    return flags[slot]


def buy_from_shop(run: "Run", slot: int) -> bool:
    """Buy the champion in ``slot``; on success the slot is consumed (set None).

    Returns ``False`` (no-op) for an out-of-range / empty slot or a failed buy
    (unaffordable / not buyable). A bought slot is also **unfrozen** (V.75).
    """
    if not 0 <= slot < len(run.shop_offers):
        return False
    champion_id = run.shop_offers[slot]
    if champion_id is None:
        return False
    if economy.buy_champion(run, champion_id):
        run.shop_offers[slot] = None
        flags = _frozen_flags(run)
        flags[slot] = False
        run.shop_frozen = flags
        return True
    return False
