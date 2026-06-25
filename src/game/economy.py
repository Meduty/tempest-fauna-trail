"""Amber economy & Tempest team-size progression (T.22).

Pure game logic — no Flet imports, no I/O (V.1). All randomness derives from
``(run_seed, node_index, channel)`` via :mod:`src.game.encounter`, mirroring the
seed-deterministic encounter contract (same seed → same income / shop).

Currency is **Amber**; the team-size XP analogue is **Tempest** (1 Amber : 1
Tempest for rush buy-ups). See SPEC §D.13 (champion economy), §D.14 (team cap),
§D.15 (shop), and ``docs/design/tasks/t22_meta_progression_plan.md``.
"""
from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import TYPE_CHECKING, Final

from .content import CHAMPION_DEF_BY_ID, build_champion_at_level
from .encounter import economy_seed, generate_node_reward
from .models import CombatOutcome, NodeType, RunStatus

if TYPE_CHECKING:  # avoid a hard import cycle; Run/BattleResult only for typing
    from .models import BattleResult, Run

# ---------------------------------------------------------------------------
# Amber income (SPEC §D.13)
# ---------------------------------------------------------------------------

AMBER_BASE_INCOME: Final[int] = 3
WIN_BONUS_MIN: Final[int] = 1
WIN_BONUS_MAX: Final[int] = 3

# Interest (TFT-style): +1 Amber per INTEREST_PER banked, capped at INTEREST_CAP
# (overrides the original §D.13 "interest: none"; resolved per user amendment).
INTEREST_PER: Final[int] = 10
INTEREST_CAP: Final[int] = 5

# ---------------------------------------------------------------------------
# Champion cost curve (SPEC §D.13 / T.18 §5 — Cost(T) = T)
# ---------------------------------------------------------------------------

# Base-copy counts that materialize each level: 3 copies → L2, 9 copies → L3.
LEVEL_COPY_THRESHOLDS: Final[tuple[int, int]] = (3, 9)
MAX_LEVEL: Final[int] = 3
# A fully-levelled (L3) unit is built from this many base copies; buying more is
# wasted Amber, so a maxed champion is no longer purchasable / recruitable.
MAX_COPIES: Final[int] = LEVEL_COPY_THRESHOLDS[-1]

# ---------------------------------------------------------------------------
# Tempest team-size progression (SPEC §D.14)
# ---------------------------------------------------------------------------

START_RANK: Final[int] = 1
MAX_RANK: Final[int] = 10
TEMPEST_PER_FIGHT: Final[int] = 2

# Tempest needed to raise rank N → N+1. Accelerating curve (steeper than the
# original flat 2N): free +2/fight tops out around rank 7-8 over ~38 combat
# nodes; ranks 9-10 require an Amber rush. Preserves the fast early ramp
# (rank 3 in 3 fights). See t22 plan §5.
TEMPEST_THRESHOLD: Final[dict[int, int]] = {
    1: 2,
    2: 4,
    3: 6,
    4: 10,
    5: 14,
    6: 18,
    7: 24,
    8: 30,
    9: 36,
}


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def champion_cost(tier: int) -> int:
    """Amber cost to buy one copy of a tier-``T`` champion: ``Cost(T) = T``."""
    if tier < 1:
        raise ValueError(f"tier must be >= 1, got {tier}")
    return tier


def sell_value(tier: int, copies: int = 1) -> int:
    """Sell refund: ``floor(Cost / 2)`` per copy invested.

    For a single copy this is ``floor(tier / 2)`` (the literal §D.13 rule); a
    levelled unit refunds half of every copy fed into it.
    """
    if copies < 1:
        raise ValueError(f"copies must be >= 1, got {copies}")
    return (tier * copies) // 2


def level_from_copies(copies: int) -> int:
    """Derive a champion's level from total base copies (3 → L2, 9 → L3)."""
    level = 1
    for threshold in LEVEL_COPY_THRESHOLDS:
        if copies >= threshold:
            level += 1
    return min(level, MAX_LEVEL)


def interest(amber: int) -> int:
    """Banked-Amber interest: ``min(cap, amber // per)`` (TFT-style)."""
    if amber < 0:
        return 0
    return min(INTEREST_CAP, amber // INTEREST_PER)


def win_bonus(run_seed: int, node_index: int) -> int:
    """Deterministic win bonus in ``[WIN_BONUS_MIN, WIN_BONUS_MAX]`` Amber."""
    rng = Random(economy_seed(run_seed, node_index))
    return rng.randint(WIN_BONUS_MIN, WIN_BONUS_MAX)


def node_income(amber: int, won: bool, run_seed: int, node_index: int) -> int:
    """Total Amber granted on resolving a node (excludes REWARD loot drops).

    ``base + (win bonus if won) + interest(amber-held-before-income)``.
    """
    income = AMBER_BASE_INCOME + interest(amber)
    if won:
        income += win_bonus(run_seed, node_index)
    return income


def is_max_rank(rank: int) -> bool:
    return rank >= MAX_RANK


def tempest_threshold(rank: int) -> int:
    """Tempest needed to raise ``rank`` → ``rank + 1`` (rank in [1, 9])."""
    if rank not in TEMPEST_THRESHOLD:
        raise ValueError(f"no rank-up threshold for rank {rank} (max rank {MAX_RANK})")
    return TEMPEST_THRESHOLD[rank]


def rank_up_cost_amber(tempest: int, rank: int) -> int:
    """Amber to instantly complete the current rank-up (1 Amber : 1 Tempest).

    The full remaining cost only — all-or-nothing (no partial buy). Returns 0 at
    max rank (no rank-up available).
    """
    if is_max_rank(rank):
        return 0
    return max(0, tempest_threshold(rank) - tempest)


# ---------------------------------------------------------------------------
# Run mutators (pure — mutate the passed Run, no I/O)
# ---------------------------------------------------------------------------


def _cascade_rank_ups(run: "Run") -> None:
    """Consume banked Tempest into rank-ups while a threshold is met.

    Rank is monotonic non-decreasing and capped at ``MAX_RANK``; overflow
    Tempest carries to the next rank.
    """
    while run.tempest_rank < MAX_RANK and run.tempest >= TEMPEST_THRESHOLD[run.tempest_rank]:
        run.tempest -= TEMPEST_THRESHOLD[run.tempest_rank]
        run.tempest_rank += 1


def grant_tempest(run: "Run", amount: int) -> None:
    """Add ``amount`` Tempest then cascade any earned rank-ups."""
    if amount < 0:
        raise ValueError("grant_tempest amount must be >= 0")
    run.tempest += amount
    _cascade_rank_ups(run)


def grant_fight_tempest(run: "Run") -> None:
    """Award the standard ``+2`` Tempest for clearing a fight."""
    grant_tempest(run, TEMPEST_PER_FIGHT)


def try_rank_up_with_amber(run: "Run") -> bool:
    """Spend Amber to complete the current rank-up immediately (all-or-nothing).

    Returns ``True`` on success. No-op + ``False`` if at max rank or the full
    remaining cost is unaffordable.
    """
    if is_max_rank(run.tempest_rank):
        return False
    cost = rank_up_cost_amber(run.tempest, run.tempest_rank)
    if cost > run.amber:
        return False
    run.amber -= cost
    run.tempest += cost
    _cascade_rank_ups(run)
    return True


def apply_node_income(run: "Run", won: bool, node_index: int) -> int:
    """Grant per-node Amber income to ``run``; returns the amount granted."""
    granted = node_income(run.amber, won, run.seed, node_index)
    run.amber += granted
    return granted


@dataclass(frozen=True)
class NodeResultSummary:
    """What one fought node did to the run — the reward-panel's display payload."""

    won: bool
    amber_gained: int
    tempest_gained: int
    terminal: bool          # run.is_complete() after applying
    status: RunStatus       # IN_PROGRESS | VICTORY | DEFEAT
    hearts_remaining: int = 3
    item_ids: tuple[str, ...] = ()      # type-reward loot deposited to inventory (win only)
    bonus_amber: int = 0                # CHALLENGE reward amber, beyond base income (win only)
    champion_offer: str | None = None   # pending CHALLENGE recruit — applied via recruit_challenge_offer


def _is_last_node(run: "Run", node: "Node") -> bool:
    """True if ``node`` is the final route node (no node has a greater index)."""
    return not any(other.index > node.index for other in run.route)


def apply_node_result(run: "Run", result: "BattleResult") -> NodeResultSummary:
    """Apply one fought node's outcome to ``run`` — the single reward-step
    orchestrator (V.69/V.70/V.71). Appends ``result`` to ``run.battle_log`` and
    grants seeded income (win bonus on a win only, V.2).

    **On a win:** fight tempest + the node's **type auto-reward** (V.70) —
    ``generate_node_reward`` loot → ``Run.inventory``, CHALLENGE amber → ``amber``,
    tempest bonus → ``grant_tempest``; the CHALLENGE ``champion_offer`` is surfaced
    *pending* (``NodeResultSummary.champion_offer``), **not** auto-applied (player
    Recruit via :func:`recruit_challenge_offer`). Then marks CLEARED + advances
    (→ ``VICTORY`` if last).

    **On a non-win (LOSS/DRAW, V.60):** decrements ``Run.hearts`` (Hearts model,
    V.71). A **non-boss, non-final** loss with ``hearts > 0`` marks CLEARED +
    advances (survive); a **BOSS_FIGHT loss** (hard gate), a **final-node loss**,
    or ``hearts <= 0`` sets ``status = DEFEAT``. Unique payouts are win-only ⇒ a
    loss yields base income+interest with no win-bonus/type reward.

    Pure progression — no Flet, no re-resolve, no I/O (the producer autosaves
    after, V.65). The producer calls this **exactly once per fight** (V.64).
    """
    node = run.current_node()           # captured before advancing (None only if not in progress)
    if node is None:                    # guard *before* any mutation — never leave a partial run (V.64)
        raise ValueError("apply_node_result requires an in-progress run with a current node.")
    node_index = run.current_node_index
    won = result.outcome == CombatOutcome.WIN
    run.battle_log.append(result)
    amber_gained = apply_node_income(run, won, node_index)
    tempest_gained = 0
    item_ids: tuple[str, ...] = ()
    bonus_amber = 0
    champion_offer: str | None = None
    if won:
        grant_fight_tempest(run)            # +TEMPEST_PER_FIGHT, cascades rank-ups
        tempest_gained = TEMPEST_PER_FIGHT
        reward = generate_node_reward(run.seed, node)   # node guaranteed non-None (guarded above)
        if reward is not None:              # REWARD loot / CHALLENGE payload (V.70)
            for item_id in reward.item_ids:
                run.inventory[item_id] = run.inventory.get(item_id, 0) + 1
            run.amber += reward.amber
            if reward.tempest_bonus:
                grant_tempest(run, reward.tempest_bonus)
                tempest_gained += reward.tempest_bonus
            item_ids = tuple(reward.item_ids)
            bonus_amber = reward.amber
            champion_offer = reward.champion_offer
        run.mark_current_node_cleared()
        run.advance_to_next_node()          # → status VICTORY if no next node
    else:                                   # Hearts model (V.71): loss is survivable
        run.hearts -= 1
        is_boss = node.node_type == NodeType.BOSS_FIGHT
        is_last = _is_last_node(run, node)
        if run.hearts <= 0 or is_boss or is_last:
            run.status = RunStatus.DEFEAT   # hearts gone OR boss gate OR final node
        else:
            run.mark_current_node_cleared() # resolved (CLEARED, no FAILED state)
            run.advance_to_next_node()      # survive → next node
    return NodeResultSummary(
        won=won,
        amber_gained=amber_gained,
        tempest_gained=tempest_gained,
        terminal=run.is_complete(),
        status=run.status,
        hearts_remaining=run.hearts,
        item_ids=item_ids,
        bonus_amber=bonus_amber,
        champion_offer=champion_offer,
    )


def recruit_challenge_offer(run: "Run", champion_id: str) -> bool:
    """Recruit a CHALLENGE ``champion_offer`` to the bench (T.38, V.70).

    Materializes ``champion_id`` at level 1 on ``run.bench`` (mirrors a 1-copy
    buy via :func:`_materialize_champion`). Returns ``False`` (no-op) for an
    unknown id or one already owned (in ``champion_copies``) — no Amber refund,
    no duplicate. The player's Recruit click routes here (V.63 — view chooses,
    game mutates); Skip simply never calls it.
    """
    if champion_id not in CHAMPION_DEF_BY_ID:
        return False
    if run.champion_copies.get(champion_id):
        return False
    run.champion_copies[champion_id] = 1
    fresh = build_champion_at_level(champion_id, 1)
    run.bench.append(fresh)
    return True


def _materialize_champion(run: "Run", champion_id: str, level: int) -> None:
    """Insert or re-level the owned Champion instance for ``champion_id``."""
    fresh = build_champion_at_level(champion_id, level)
    for collection in (run.roster, run.bench):
        for i, champion in enumerate(collection):
            if champion.id == champion_id:
                collection[i] = fresh
                return
    run.roster.append(fresh)


def buy_champion(run: "Run", champion_id: str) -> bool:
    """Buy one copy of ``champion_id``, auto-levelling on the 3rd / 9th copy.

    Returns ``False`` (no-op) for unknown ids, tier-10 Primordials (boss-only,
    not purchasable), an already-maxed (L3 / 9-copy) unit, or when unaffordable.
    """
    champ_def = CHAMPION_DEF_BY_ID.get(champion_id)
    if champ_def is None or champ_def.tier == 10:
        return False
    if run.champion_copies.get(champion_id, 0) >= MAX_COPIES:
        return False
    cost = champion_cost(champ_def.tier)
    if cost > run.amber:
        return False
    run.amber -= cost
    copies = run.champion_copies.get(champion_id, 0) + 1
    run.champion_copies[champion_id] = copies
    _materialize_champion(run, champion_id, level_from_copies(copies))
    return True


def sell_champion(run: "Run", champion_id: str) -> bool:
    """Sell the owned unit for ``champion_id``, refunding ``floor(Cost/2)``/copy.

    Returns ``False`` (no-op) if the champion is not owned.
    """
    copies = run.champion_copies.get(champion_id)
    if copies is None:
        return False
    champ_def = CHAMPION_DEF_BY_ID.get(champion_id)
    tier = champ_def.tier if champ_def is not None else 1
    run.amber += sell_value(tier, copies)
    del run.champion_copies[champion_id]
    for collection in (run.roster, run.bench):
        for i, champion in enumerate(collection):
            if champion.id == champion_id:
                del collection[i]
                break
    return True
