"""Regenerate docs/design/tasks/t32_role_matrix.txt — the role-classification
matrix (T.32, expanded for the 7-level speed axis in T.33b).

Enumerates every axis combination, derives role_code + role from the canonical
content functions, and writes the aligned fixture the role tests validate against.

    uv run python -m tools.gen_role_matrix
"""
from __future__ import annotations

from pathlib import Path

from src.game.content import (
    _DURABILITY,
    _INTENT,
    _PLAYSTYLE,
    _PRIMARY_STAT,
    _RANGE,
    _SPEED,
    build_role_code,
    classify_role,
)

OUT = Path(__file__).resolve().parents[1] / "docs" / "design" / "tasks" / "t32_role_matrix.txt"

# Axis values in canonical (content dict insertion) order.
STATS = tuple(_PRIMARY_STAT)
REACHES = tuple(_RANGE)
DURABILITIES = tuple(_DURABILITY)
PLAYSTYLES = tuple(_PLAYSTYLE)
SPEEDS = tuple(_SPEED)
INTENTS = tuple(_INTENT)
AXES = (STATS, REACHES, DURABILITIES, PLAYSTYLES, SPEEDS, INTENTS)
HEADERS = ("stat", "reach", "durability", "playstyle", "speed", "intent")


def _combos():
    for stat in STATS:
        for reach in REACHES:
            for dur in DURABILITIES:
                for play in PLAYSTYLES:
                    for speed in SPEEDS:
                        for intent in INTENTS:
                            yield (stat, reach, dur, play, speed, intent)


def render() -> str:
    rows = [(axes, build_role_code(*axes), classify_role(*axes)) for axes in _combos()]
    total = len(rows)
    # Column widths: max of header + every value in that axis (+padding).
    widths = [
        max(len(HEADERS[i]), max(len(v) for v in AXES[i])) + 1 for i in range(6)
    ]
    code_w = max(len("role_code"), max(len(c) for _, c, _ in rows)) + 1

    def fmt_axes(axes):
        return "".join(a.ljust(widths[i]) for i, a in enumerate(axes))

    lines = [
        "# T.32 Role Classification Matrix — full enumeration (generated)",
        "# axes: stat | reach | durability | playstyle | speed | intent  =>  role_code  =>  role",
        f"# total combos: {total}",
        "",
        fmt_axes(HEADERS) + "| " + "role_code".ljust(code_w) + "| role",
        "-" * (sum(widths) + code_w + 8),
    ]
    for axes, code, role in rows:
        lines.append(f"{fmt_axes(axes)}| {code.ljust(code_w)}| {role}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    OUT.write_text(render())
    n = render().count("\n") - 6
    print(f"wrote {OUT} ({n} combos)")
