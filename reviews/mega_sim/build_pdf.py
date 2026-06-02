#!/usr/bin/env python3
"""Convert mega3_analysis_report.md -> LaTeX -> PDF (xelatex).

Targeted converter for THIS report's markdown subset: headings, pipe tables,
images, blockquotes, bullet lists, horizontal rules, **bold**, `code`,
[text](url), and a fixed set of unicode glyphs. No pandoc dependency.

Run from repo root:  python3 reviews/mega_sim/build_pdf.py
Compiles in reviews/mega_sim/ so plots/<...>.png paths resolve.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MD = os.path.join(HERE, "mega3_analysis_report.md")
TEX = os.path.join(HERE, "mega3_analysis_report.tex")

# unicode glyph -> LaTeX (applied to text AFTER special-char escaping, via tokens)
GLYPH = {
    "§": r"\S{}", "→": r"$\rightarrow$", "←": r"$\leftarrow$", "×": r"$\times$",
    "±": r"$\pm$", "≈": r"$\approx$", "≤": r"$\leq$", "≥": r"$\geq$",
    "Δ": r"$\Delta$", "Σ": r"$\Sigma$", "√": r"$\sqrt{\,}$", "·": r"$\cdot$",
    "≠": r"$\neq$", "✅": r"\textbf{[OK]}", "❌": r"\textbf{[X]}",
    "⚠️": r"\textbf{[!]}", "⚠": r"\textbf{[!]}", "—": "---", "–": "--",
    "“": "``", "”": "''", "‘": "`", "’": "'", "≈": r"$\approx$",
    "²": r"\textsuperscript{2}", "✓": r"[y]", "✗": r"[n]",
    "↔": r"$\leftrightarrow$", "∈": r"$\in$",
}
SPECIAL = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
           "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
           "^": r"\textasciicircum{}"}


def esc(text):
    """Escape LaTeX specials in plain text (backslash first)."""
    text = text.replace("\\", r"\textbackslash{}")
    for k, v in SPECIAL.items():
        text = text.replace(k, v)
    return text


def inline(text):
    """Markdown inline -> LaTeX. Glyphs tokenized so escaping skips them."""
    # tokenize glyphs
    toks = {}
    for i, (g, lat) in enumerate(GLYPH.items()):
        if g in text:
            t = f"\x00G{i}\x00"
            toks[t] = lat
            text = text.replace(g, t)
    # protect inline code spans before escaping
    codes = []

    def _code(m):
        codes.append(m.group(1))
        return f"\x00C{len(codes)-1}\x00"
    text = re.sub(r"`([^`]+)`", _code, text)
    # links [t](u) -> t  (drop url; keep label)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # escape specials in remaining text
    text = esc(text)
    # bold **x** (after escaping; ** survived)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\\textbf{\1}", text)
    # restore code spans (escape; add break opportunities so long ids wrap)
    for i, c in enumerate(codes):
        c2 = re.sub(r"([,/_{}().+-])", "\\1\x00B\x00", c)
        c2 = esc(c2).replace("\x00B\x00", r"\allowbreak{}")
        text = text.replace(f"\x00C{i}\x00", r"\texttt{" + c2 + "}")
    # restore glyph tokens
    for t, lat in toks.items():
        text = text.replace(t, lat)
    return text


def is_num(cell):
    c = re.sub(r"\\textbf\{|\}|\s|\\texttt\{", "", cell).strip()
    c = c.replace("$", "").replace("+", "").replace("-", "").replace(",", "")
    c = c.replace(".", "").replace("%", "").replace(r"\pm", "")
    return c.isdigit() and len(re.sub(r"[^\d]", "", cell)) > 0


def conv_table(rows):
    """rows: list of raw markdown rows (incl header + separator)."""
    header = rows[0]
    body = rows[2:]

    def split(r):
        r = r.strip().strip("|")
        # protect escaped pipes \|
        r = r.replace(r"\|", "\x00P\x00")
        cells = [c.strip().replace("\x00P\x00", "|") for c in r.split("|")]
        return cells
    hcells = split(header)
    ncol = len(hcells)
    bcells = [split(r) for r in body if r.strip()]
    bcells = [c + [""] * (ncol - len(c)) for c in bcells]
    # column types: numeric -> r, else X (wrapping)
    types = []
    for j in range(ncol):
        col = [inline(r[j]) for r in bcells] if bcells else [""]
        types.append("r" if col and all(is_num(x) or x == "" for x in col)
                     and any(x for x in col) else "X")
    has_x = "X" in types
    colspec = "".join("L" if t == "X" else "r" for t in types)
    out = []
    if has_x:
        out.append(r"\begin{tabularx}{\linewidth}{" + colspec + "}")
    else:
        out.append(r"\begin{center}\begin{tabular}{" +
                   "".join(types) + "}")
    out.append(r"\toprule")
    out.append(" & ".join(r"\textbf{" + inline(h) + "}" for h in hcells)
               + r" \\")
    out.append(r"\midrule")
    for r in bcells:
        out.append(" & ".join(inline(x) for x in r[:ncol]) + r" \\")
    out.append(r"\bottomrule")
    out.append(r"\end{tabularx}" if has_x else r"\end{tabular}\end{center}")
    return "\n".join(out)


def convert(md):
    lines = md.split("\n")
    out, i = [], 0
    in_list = False

    def close_list():
        nonlocal in_list
        if in_list:
            out.append(r"\end{itemize}")
            in_list = False
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        # fenced code block ```lang ... ```
        if s.startswith("```"):
            close_list()
            i += 1
            code = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            out.append(r"\begin{lstlisting}")
            out.extend(code)
            out.append(r"\end{lstlisting}")
            continue
        # table block
        if s.startswith("|") and i + 1 < len(lines) and re.match(
                r"^\s*\|[\s:|-]+\|?\s*$", lines[i + 1]):
            close_list()
            blk = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                blk.append(lines[i])
                i += 1
            out.append(r"\medskip")
            out.append(conv_table(blk))
            out.append(r"\medskip")
            continue
        # image
        m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", s)
        if m:
            close_list()
            alt, path = m.group(1), m.group(2)
            out.append(r"\begin{figure}[H]\centering")
            out.append(r"\includegraphics[width=0.86\linewidth,"
                       r"height=0.42\textheight,keepaspectratio]{%s}" % path)
            if alt:
                out.append(r"\caption*{\small " + inline(alt) + "}")
            out.append(r"\end{figure}")
            i += 1
            continue
        # heading
        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            close_list()
            lvl = len(m.group(1))
            title = inline(m.group(2))
            cmd = {1: "section", 2: "section", 3: "subsection",
                   4: "subsubsection"}[lvl]
            out.append("\\%s*{%s}" % (cmd, title))
            i += 1
            continue
        # horizontal rule
        if re.match(r"^---+$", s):
            close_list()
            i += 1
            continue
        # blockquote (consume consecutive)
        if s.startswith(">"):
            close_list()
            q = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                q.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append(r"\begin{quotebox}")
            out.append(inline(" ".join(x.strip() for x in q if x.strip())))
            out.append(r"\end{quotebox}")
            continue
        # bullet list item
        m = re.match(r"^[-*]\s+(.*)$", s)
        if m:
            if not in_list:
                out.append(r"\begin{itemize}")
                in_list = True
            out.append(r"\item " + inline(m.group(1)))
            i += 1
            continue
        # blank
        if s == "":
            close_list()
            out.append("")
            i += 1
            continue
        # paragraph (gather until blank/structural)
        close_list()
        out.append(inline(s) + r"\\")
        i += 1
    close_list()
    return "\n".join(out)


PREAMBLE = r"""\documentclass[10pt]{article}
\usepackage{fontspec}
\setmainfont{Latin Modern Roman}
\setmonofont{Latin Modern Mono}[Scale=0.9]
\usepackage[a4paper,margin=2cm]{geometry}
\usepackage{graphicx}
\usepackage{float}
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{array}
\usepackage{caption}
\usepackage{xcolor}
\usepackage[most]{tcolorbox}
\usepackage{microtype}
\usepackage{listings}
\lstset{basicstyle=\ttfamily\small,breaklines=true,breakatwhitespace=false,
  columns=fullflexible,backgroundcolor=\color{gray!8},frame=single,
  rulecolor=\color{gray!40},xleftmargin=4pt,xrightmargin=4pt,aboveskip=6pt,
  belowskip=6pt}
\usepackage{hyperref}
\hypersetup{colorlinks=true,linkcolor=blue!50!black,urlcolor=blue!50!black}
\newcolumntype{L}{>{\raggedright\arraybackslash}X}
\newtcolorbox{quotebox}{colback=gray!8,colframe=gray!40,boxrule=0.5pt,
  left=6pt,right=6pt,top=4pt,bottom=4pt,arc=2pt}
\setlength{\tabcolsep}{4pt}
\renewcommand{\arraystretch}{1.12}
\captionsetup{font=small,labelformat=empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{4pt}
\usepackage{sectsty}
\sectionfont{\large\bfseries\color{blue!30!black}}
\begin{document}
"""

POST = r"\end{document}"


def main():
    with open(MD, encoding="utf-8") as f:
        md = f.read()
    # pull first H1 as title, drop it from body
    lines = md.split("\n")
    title = "Simulation Analysis Report"
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        lines = lines[1:]
    md = "\n".join(lines)
    body = convert(md)
    tex = (PREAMBLE
           + r"\begin{center}{\LARGE\bfseries " + inline(title)
           + r"}\end{center}\vspace{6pt}" + "\n" + body + "\n" + POST)
    with open(TEX, "w", encoding="utf-8") as f:
        f.write(tex)
    # compile twice (refs)
    for _ in range(2):
        r = subprocess.run(
            ["xelatex", "-interaction=nonstopmode", "-halt-on-error",
             os.path.basename(TEX)],
            cwd=HERE, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stdout[-3000:])
        sys.exit("xelatex FAILED")
    print("PDF built:", os.path.join(HERE, "mega3_analysis_report.pdf"))


if __name__ == "__main__":
    main()
