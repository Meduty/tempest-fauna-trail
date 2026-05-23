"""Seeded RNG for deterministic combat (T20).

All randomness in combat flows through this. Content MUST use ctx.rng —
never import random directly. CI grep enforces this in game/.
"""

from __future__ import annotations

from random import Random


class SeededRng:
    """Deterministic RNG wrapper. Thin layer over stdlib Random for testability."""

    __slots__ = ("_rng",)

    def __init__(self, seed: int) -> None:
        self._rng = Random(seed)

    def random(self) -> float:
        """Uniform float in [0, 1)."""
        return self._rng.random()

    def randint(self, a: int, b: int) -> int:
        """Random integer N such that a <= N <= b."""
        return self._rng.randint(a, b)

    def choice(self, seq: list) -> object:
        """Random element from a non-empty sequence."""
        return self._rng.choice(seq)

    def shuffle(self, seq: list) -> None:
        """Shuffle list in place."""
        self._rng.shuffle(seq)

    def uniform(self, a: float, b: float) -> float:
        """Random float N such that a <= N <= b."""
        return self._rng.uniform(a, b)
