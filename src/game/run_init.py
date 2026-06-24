"""Run-start flow (T.10) — build a fresh in-progress ``Run`` from a seed.

Pure game logic, **Flet-free** (V.1) and the **sole owner of run-start state**
(V.63): the RunStart view picks a champion and calls in here; it never computes
the offer, the starting resources, or the first shop itself.

The champion offer is **seed-deterministic** (V.2) — same seed ⇒ same 3 ids —
derived through the shared :func:`encounter.derive_seed` integer mixer (no
``hash()``, no wall-clock). Starting conditions are the SPEC §G "Run-start
conditions": pick **1 of 3** Tier 1–2 champions, **10 Amber**, Tempest **rank 1**,
a **first shop** of 5 Tier-1 offers (``shop.refresh_shop``).
"""

from __future__ import annotations

from random import Random

from src.game import economy, shop
from src.game.content import CHAMPION_DEF_BY_ID
from src.game.encounter import derive_seed
from src.game.models import NodeState, Run, RunStatus
from src.game.route import build_route
from src.game.save import CURRENT_SCHEMA_VERSION

# SPEC §G "Run-start conditions".
STARTING_AMBER = 10
STARTING_RANK = 1
OFFER_SIZE = 3
OFFER_TIERS = (1, 2)
# derive_seed channel reserved for the run-start champion offer (node_index 0 —
# the offer precedes node 1). Distinct from the T.19 encounter channels.
_OFFER_CHANNEL = 701


def _offer_pool() -> list[str]:
    """Champion ids eligible for the starting offer, sorted for determinism."""
    return sorted(
        cid for cid, d in CHAMPION_DEF_BY_ID.items() if d.tier in OFFER_TIERS
    )


def champion_offer(seed: int) -> list[str]:
    """Return the seed-deterministic 1-of-``OFFER_SIZE`` champion offer.

    ``OFFER_SIZE`` distinct Tier 1–2 champion ids; same ``seed`` ⇒ same list
    (V.2). Pure — does not build a ``Run``.
    """
    pool = _offer_pool()
    rng = Random(derive_seed(seed, 0, _OFFER_CHANNEL))
    return rng.sample(pool, OFFER_SIZE)


def new_run(seed: int, chosen_champion_id: str) -> Run:
    """Build a fresh in-progress ``Run`` seeded at ``seed`` with the picked champion.

    ``chosen_champion_id`` must be one of :func:`champion_offer` for this seed
    (the RunStart view only ever passes an offered id). Sets node 1 ``CURRENT``,
    grants the starting champion at level 1, ``STARTING_AMBER`` / ``STARTING_RANK``,
    and rolls the first shop via :func:`shop.refresh_shop` (V.63 — economy/shop own
    the numbers). Deterministic (V.2): same ``(seed, chosen)`` ⇒ identical ``Run``.
    """
    if chosen_champion_id not in champion_offer(seed):
        raise ValueError(
            f"{chosen_champion_id!r} is not in the starting offer for seed {seed}."
        )

    route = build_route()
    route[0].state = NodeState.CURRENT  # node index 1 is first in route order

    run = Run(
        run_id=f"run_{seed & 0xFFFFFFFF:08x}",
        schema_version=CURRENT_SCHEMA_VERSION,
        seed=seed,
        status=RunStatus.IN_PROGRESS,
        roster=[],
        bench=[],
        route=route,
        current_node_index=1,
        amber=STARTING_AMBER,
        tempest_rank=STARTING_RANK,
    )

    # Grant the chosen champion at level 1 (one base copy) through the economy
    # materializer — keeps champion_copies + roster in sync like a buy (V.63).
    run.champion_copies[chosen_champion_id] = 1
    economy._materialize_champion(run, chosen_champion_id, 1)

    # First shop: 5 auto-populated offers for stage 1 (free; resets reroll count).
    shop.refresh_shop(run)
    return run
