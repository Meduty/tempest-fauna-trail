#!/usr/bin/env python3
"""Assemble the project documentation PDF from the LIVING docs + synthesized chapters.

Cross-platform (Windows/macOS/Linux) — a Python port of the original
``assemble.ps1``, with no PowerShell dependency. Pipeline: read source markdown
-> fence-aware heading transform -> emoji/glyph sanitize -> concatenate into one
build ``.md`` -> pandoc (``--pdf-engine=tectonic``) -> PDF.

Run:   uv run python docs/report/assemble.py   (or plain ``python3``)
Out:   docs/report/TempestFaunaTrail-Documentation.pdf
Needs: ``pandoc`` + ``tectonic`` on PATH (both cross-platform; tectonic is a
       single static binary, pandoc ships static release tarballs).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

REPORT_DIR = Path(__file__).resolve().parent
REPO_ROOT = REPORT_DIR.parent.parent          # docs/report -> docs -> repo root
SECTIONS = REPORT_DIR / "sections"
BUILD_DIR = REPORT_DIR / "build"
COMBINED = BUILD_DIR / "combined.md"
OUT_PDF = REPORT_DIR / "TempestFaunaTrail-Documentation.pdf"
LIVE = REPO_ROOT / "docs" / "live"

# Map emoji/symbols that the PDF fonts don't cover to plain-text tokens. Ordered
# dict semantics aren't needed here (no key is a substring of another), but the
# codepoint spelling keeps this file pure-ASCII like the original .ps1.
_REPLACEMENTS: dict[str, str] = {
    "✅": "[done]", "\U0001F536": "[stub]", "\U0001F7E1": "[partial]", "\U0001F4CB": "[planned]",
    "▶": ">", "◀": "<", "▼": "v", "▲": "^",
    "→": "->", "←": "<-", "⟶": "-->", "⇒": "=>", "⇐": "<=",
    "↔": "<->", "≠": "!=", "≪": "<<", "≫": ">>", "∪": "U",
    "∩": "^", "∈": "in", "⨀": " Amber", "⟂": "perp", "∝": "proportional to",
    "≈": "~=", "≤": "<=", "≥": ">=",
    "×": "x", "·": "-", "—": "--", "–": "-", "…": "...",
    "“": '"', "”": '"', "‘": "'", "’": "'",
    "●": "*", "○": "o",   # copy-count badges — not in Latin Modern Mono
    # Box-drawing (ASCII-art diagrams) — Latin Modern Mono lacks these glyphs.
    "─": "-", "│": "|", "┌": "+", "┐": "+", "└": "+", "┘": "+",
    "├": "+", "┤": "+", "┬": "+", "┴": "+", "┼": "+",
}


def sanitize(text: str) -> str:
    for k, v in _REPLACEMENTS.items():
        text = text.replace(k, v)
    return text


_HEADING = re.compile(r"^(#{1,6}) (.*)$")
_FENCE = re.compile(r"^(```|~~~)")
_SECNUM = re.compile(r"^\d+(\.\d+)*\.?\s+")


def transform(path: Path, mode: str, title: str = "", shift: int = 0) -> str:
    """Transform a markdown file's ATX headings, skipping fenced code blocks.

    modes:
      "replace-title":       swap the first H1 for ``title``, leave the rest.
      "replace-title-denum": as above, and strip leading "N." / "N.M" section
                             numbers from lower headings (they'd collide with
                             pandoc's auto section numbers).
      "shift":               add ``shift`` '#' to every heading (h1 -> h(1+shift)).
      "none":                pass through unchanged.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    in_fence = False
    fence_tok: str | None = None
    title_done = False
    for line in lines:
        trim = line.lstrip()
        if not in_fence:
            m = _FENCE.match(trim)
            if m:
                in_fence = True
                fence_tok = m.group(1)
                out.append(line)
                continue
        elif fence_tok is not None and trim.startswith(fence_tok):
            in_fence = False
            fence_tok = None
            out.append(line)
            continue
        if not in_fence:
            m = _HEADING.match(line)
            if m:
                hashes, rest = m.group(1), m.group(2)
                if mode in ("replace-title", "replace-title-denum"):
                    if not title_done and len(hashes) == 1:
                        out.append(f"# {title}")
                        title_done = True
                        continue
                    if mode == "replace-title-denum":
                        rest = _SECNUM.sub("", rest)
                    out.append(f"{hashes} {rest}")
                    continue
                if mode == "shift":
                    out.append(("#" * shift) + hashes + " " + rest)
                    continue
        out.append(line)
    return "\n".join(out)


# docs/live docs in reading order, appended under Ch3 shifted to H2. Forward
# slashes are separator-agnostic — pathlib splits them on every platform.
LIVE_ORDER = [
    "systems/combat.md", "systems/effects.md", "systems/weather.md", "systems/formation.md",
    "systems/encounter.md", "systems/scaling.md", "systems/weather_api.md", "systems/save.md",
    "systems/items.md", "systems/kit_design_conventions.md",
    "content/rosters.md", "content/abilities.md", "content/traits.md", "content/items.md",
    "content/augments.md",
]


def main() -> int:
    for tool in ("pandoc", "tectonic"):
        if shutil.which(tool) is None:
            print(f"error: `{tool}` not found on PATH (needed for the PDF build).",
                  file=sys.stderr)
            return 1

    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    parts: list[str] = []

    def add_raw(text: str) -> None:
        parts.append(text)
        parts.append("\n\n")

    def add_file(path: Path, mode: str, title: str = "", shift: int = 0) -> None:
        add_raw(transform(path, mode, title, shift))

    # Ch1 Overview  <- README (title replaced so it becomes the numbered chapter).
    add_file(REPO_ROOT / "README.md", "replace-title", "Overview")
    # Ch2 Architecture <- ARCHITECTURE (strip its own "1./2." section numbers).
    add_file(REPO_ROOT / "ARCHITECTURE.md", "replace-title-denum", "Architecture")
    # Ch3 Systems & Features <- authored intro (owns the H1) + every docs/live doc @H2.
    add_file(SECTIONS / "03_systems_intro.md", "none")
    for rel in LIVE_ORDER:
        add_file(LIVE / rel, "shift", shift=1)
    # Ch4 & Ch5 <- authored (synthesized) chapters, own their H1.
    add_file(SECTIONS / "04_ai_collaboration.md", "none")
    add_file(SECTIONS / "05_implementation.md", "none")

    doc = sanitize("".join(parts))
    COMBINED.write_text(doc, encoding="utf-8")
    print(f"Wrote {COMBINED} ({len(doc.splitlines())} lines)")

    cmd = [
        "pandoc", str(REPORT_DIR / "meta.yaml"), str(COMBINED),
        "--pdf-engine=tectonic",
        f"--include-in-header={REPORT_DIR / 'header.tex'}",
        f"--lua-filter={REPORT_DIR / 'fit-tables.lua'}",
        "--from=gfm+yaml_metadata_block",
        "-o", str(OUT_PDF),
    ]
    subprocess.run(cmd, check=True)

    if OUT_PDF.exists():
        print(f"PDF OK: {OUT_PDF} ({round(OUT_PDF.stat().st_size / 1024)} KB)")
        return 0
    print("PDF not produced", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
