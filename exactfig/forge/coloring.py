"""
Colourings of 1..n, checked before they are drawn / coloraciones de 1..n, comprobadas antes de dibujarlas.

A SAT solver answers questions such as "can 1..n be coloured so that no colour holds an arithmetic progression of its
length?" (van der Waerden numbers) or "can 1..n be split into k sum-free sets?" (Schur numbers). A "yes" comes with a
witness, a colouring, which anyone can check in a moment; a "no" comes with a proof (DRAT, LRAT) that needs a proof
checker. This generator draws witnesses, and only after checking them against what the recipe states:

  check  "ap"     no colour c contains an arithmetic progression a, a+d, …, a+(k_c − 1)d (d ≥ 1) of the length k_c
                  that `lengths` gives it: one number for every colour, or one per colour ("2,3,3,3")
         "schur"  no colour contains x, y and x + y (x = y allowed); with `distinct`, only x < y (weak Schur numbers)
         "none"   nothing is checked about the colouring itself
  colors       the number of colours: every colour is below it (0 = from `lengths`, or any)
  length       every colouring colours exactly 1..length (0 = any)
  count        the file has exactly this many colourings (0 = any)
  proof_sha256 the SHA-256 of the proof that 1..length+1 has no such colouring (the other half of the theorem). It is
               recorded in the manifest so the figure names the proof; exactfig does not read or check it (that is the
               job of a proof checker such as drat-trim or cake_lpr).

A refusal names the colouring, the colour and the numbers that break the rule.
"""
from __future__ import annotations

import re

from ..pixel.canvas import Canvas

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def parse_lengths(text: str) -> list[int]:
    """'3' or '2,3,3,3' → [3] or [2, 3, 3, 3]; each length 1..1000."""
    try:
        ks = [int(t) for t in text.replace(" ", "").split(",")]
    except ValueError:
        raise ValueError(f"lengths {text!r}: give one number or one per colour, e.g. 3 or 2,3,3,3") from None
    if not ks or any(not 1 <= k <= 1000 for k in ks):
        raise ValueError(f"lengths {text!r}: each length must be 1..1000")
    return ks


def progression(cells: list[int], k: int):
    """A k-term arithmetic progression inside the sorted list `cells`, or None."""
    if k <= 1:
        return [cells[0]] if cells else None
    s = set(cells)
    for i, a in enumerate(cells):
        for b in cells[i + 1:]:
            d = b - a
            if a + (k - 1) * d > cells[-1]:
                break
            if all(a + j * d in s for j in range(2, k)):
                return [a + j * d for j in range(k)]
    return None


def sum_in_class(cells: list[int], distinct: bool):
    """x, y, x + y all in `cells` (x <= y, or x < y if distinct), or None."""
    s = set(cells)
    for i, x in enumerate(cells):
        for y in cells[i + (1 if distinct else 0):]:
            if x + y > cells[-1]:
                break
            if x + y in s:
                return x, y, x + y
    return None


def check(colorings, p) -> dict:
    """ValueError naming the first colouring, colour and numbers that break the recipe's statement."""
    if p["count"] and len(colorings) != p["count"]:
        raise ValueError(f"{len(colorings)} colourings in the file, the recipe states {p['count']}")
    ks = parse_lengths(p["lengths"]) if p["check"] == "ap" else []
    colors = p["colors"] or (len(ks) if len(ks) > 1 else 0)
    if colors and len(ks) > 1 and len(ks) != colors:
        raise ValueError(f"lengths gives {len(ks)} colours, the recipe states colors = {colors}")
    if p["proof_sha256"] and not _HEX64.match(p["proof_sha256"]):
        raise ValueError("proof_sha256 must be 64 lowercase hex digits (or empty)")
    for m, col in enumerate(colorings, 1):
        where = f"colouring {m}"
        if p["length"] and len(col) != p["length"]:
            raise ValueError(f"{where}: colours 1..{len(col)}, the recipe states 1..{p['length']}")
        if colors and max(col) >= colors:
            raise ValueError(f"{where}: colour {max(col)} at {col.index(max(col)) + 1}, but there are {colors} colours")
        classes = {}
        for i, c in enumerate(col, 1):
            classes.setdefault(c, []).append(i)
        for c in sorted(classes):
            cells = classes[c]
            if p["check"] == "ap":
                k = ks[c] if len(ks) > 1 else ks[0]
                ap = progression(cells, k)
                if ap:
                    raise ValueError(f"{where}: colour {c} holds the {k}-term progression {', '.join(map(str, ap))}")
            elif p["check"] == "schur":
                t = sum_in_class(cells, p["distinct"])
                if t:
                    raise ValueError(f"{where}: colour {c} holds {t[0]} + {t[1]} = {t[2]}")
    return {"colorings": len(colorings), "check": p["check"]}


def coloring(seed, pal, w, h, p, data) -> Canvas:
    """Generator data.coloring: check (see the module), then draw each colouring as rows of squares, 1 at the top left,
    `columns` numbers per row (0 = all on one row when they fit), the colourings one under the other."""
    cols_ = data.colorings
    check(cols_, p)
    n = max(len(c) for c in cols_)
    ncol = max(1 + max(c) for c in cols_)
    per_row = p["columns"] or n
    rows_each = -(-n // per_row)
    total_rows = rows_each * len(cols_) + (len(cols_) - 1) * (1 if p["separate"] else 0)
    cell = min(w // per_row, h // total_rows)
    if cell < 1:
        raise ValueError(f"data.coloring: {len(cols_)} colouring(s) of up to {n} numbers in rows of {per_row} do not fit in "
                         f"{w}x{h}; give a larger size or set `columns`")
    gap = min(p["cell_gap"], cell // 3)
    ramp = pal.ramp(p["ramp"])
    if ncol > len(ramp):
        raise ValueError(f"{ncol} colours, the ramp {p['ramp']!r} has {len(ramp)}")
    tone = [ramp[c * len(ramp) // ncol] for c in range(ncol)]     # evenly round the ramp: on `cyc`, evenly spaced hues
    bg = pal.ramp(p["background"])[0] if p["background"] else None
    cv = Canvas(w, h, pal)
    if bg is not None:
        cv.rect(0, 0, w - 1, h - 1, bg)
    ox = (w - per_row * cell) // 2
    oy = (h - total_rows * cell) // 2
    row0 = 0
    for col in cols_:
        for i, c in enumerate(col):
            x = ox + (i % per_row) * cell
            y = oy + (row0 + i // per_row) * cell
            cv.rect(x, y, x + cell - 1 - gap, y + cell - 1 - gap, tone[c])
        row0 += rows_each + (1 if p["separate"] else 0)
    return cv
