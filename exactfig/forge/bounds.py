"""
A table of exact values and bounds, checked before it is drawn / una tabla de valores exactos y cotas.

The table of what is known about a family of numbers (Ramsey, van der Waerden, Schur numbers, the sizes of smallest
circuits…) mixes exact values, lower bounds, upper bounds and ranges. Each cell is read as the set of integers it allows,
lo ≤ x ≤ hi (an open end where nothing is known), and before drawing:

  shape      the rows and columns are the stated ones (0 = any)
  exact, bounded  the number of exact cells, and of cells that are bounds or ranges (-1 = any)
  monotone   along every row (left to right), every column (top to bottom) or both, the values never decrease: refused
             when two cells cannot be ordered that way, i.e. when the least value one allows is above the largest value
             a later one allows (a lower bound of 50 before an exact 49, say)
  symmetric  the table is square, its row labels are its column labels in order, and cell (i, j) allows exactly the
             integers cell (j, i) allows (as for Ramsey numbers, R(s, t) = R(t, s))
  claims     the stated cells, `row,col:cell; …`, allow exactly the stated integers, so the values a caption quotes are the
             values the table holds

Cells are coloured by their kind (exact, lower bound, range, upper bound), taken evenly from `ramp` (Okabe–Ito by
default, safe for colour-blind readers); unknown cells are grey. Each cell carries its value in the 3×5 font, so the
table reads without the colours, and a legend names the kinds that occur.
"""
from __future__ import annotations

import re

from ..pixel.canvas import Canvas
from .annotate import FONT, _text, text_width

KINDS = ("lower", "exact", "range", "upper")          # their order along the ramp
NAMES = {"exact": "EXACT", "lower": "LOWER BOUND", "upper": "UPPER BOUND", "range": "RANGE", "unknown": "UNKNOWN"}
MAX_DIGITS = 4000
_CELL = re.compile(r"(?P<exact>-?\d+)|(?P<op>>=|<=|>|<) ?(?P<b>-?\d+)|(?P<lo>-?\d+) ?\.\. ?(?P<hi>-?\d+)|(?P<q>\?)")


def parse_cell(tok: str):
    """One cell: None (empty or `-`), or (text, lo, hi), the integers lo ≤ x ≤ hi it allows, None for an open end.
    `9` is exact; `>170` allows 171 and up, `>=171` too; `<46` and `<=45` allow up to 45; `43..46` is a range; `?` is
    unknown. `≥`, `≤` are read as `>=`, `<=`; one space may follow the sign or surround `..`, no other."""
    t = tok.strip().replace("≥", ">=").replace("≤", "<=")
    if t in ("", "-"):
        return None
    if len(t) > MAX_DIGITS + 4:
        raise ValueError(f"a cell of more than {MAX_DIGITS} digits")
    m = _CELL.fullmatch(t)
    if not m:
        raise ValueError(f"cell {tok!r} is not an integer, a bound (>n, >=n, <n, <=n), a range a..b, ? or -")
    t = t.replace(" ", "")                     # the text drawn: `> 170` is shown as `>170`
    if m["exact"]:
        v = int(m["exact"])
        return (t, v, v)
    if m["op"]:
        b = int(m["b"])
        return (t,) + {">": (b + 1, None), ">=": (b, None), "<": (None, b - 1), "<=": (None, b)}[m["op"]]
    if m["lo"]:
        lo, hi = int(m["lo"]), int(m["hi"])
        if lo > hi:
            raise ValueError(f"the range {t} is empty")
        return (t, lo, hi)
    return (t, None, None)


def kind(cell) -> str:
    _, lo, hi = cell
    if lo is None and hi is None:
        return "unknown"
    if lo is None:
        return "upper"
    if hi is None:
        return "lower"
    return "exact" if lo == hi else "range"


def _can_precede(a, b) -> bool:
    """Some value allowed by a is ≤ some value allowed by b."""
    return a[1] is None or b[2] is None or a[1] <= b[2]


def parse_claims(text: str) -> list:
    out = []
    for item in text.split(";"):
        item = item.strip()
        if not item:
            continue
        rc, sep, cell = item.partition(":")
        parts = [x.strip() for x in rc.split(",")]
        if not sep or len(parts) != 2 or not all(parts):
            raise ValueError(f"claim {item!r}: write row,column:cell, e.g. 5,3:>2173")
        c = parse_cell(cell)
        if c is None:
            raise ValueError(f"claim {item!r}: the cell is empty")
        out.append((parts[0], parts[1], c))
    return out


def check(tab, p) -> dict:
    """The checks of the module; returns the counts by kind."""
    rows, cols = tab.rows, tab.cols
    if p["rows"] and len(rows) != p["rows"]:
        raise ValueError(f"the table has {len(rows)} rows, the recipe states {p['rows']}")
    if p["columns"] and len(cols) != p["columns"]:
        raise ValueError(f"the table has {len(cols)} columns, the recipe states {p['columns']}")
    for lab in [tab.corner] + list(cols) + [r[0] for r in rows]:
        bad = sorted({ch for ch in lab.upper() if ch not in FONT})
        if bad:
            raise ValueError(f"label {lab!r}: the 3×5 font has no {' '.join(bad)} (letters, digits and . , : - + / ( ) "
                             f"= % ' ! ? < > _ * # only)")
    counts = {k: 0 for k in NAMES}
    for _, cells in rows:
        for c in cells:
            if c is not None:
                counts[kind(c)] += 1
    bounded = counts["lower"] + counts["upper"] + counts["range"]
    if p["exact"] >= 0 and counts["exact"] != p["exact"]:
        raise ValueError(f"{counts['exact']} exact cells, the recipe states {p['exact']}")
    if p["bounded"] >= 0 and bounded != p["bounded"]:
        raise ValueError(f"{bounded} cells are bounds or ranges, the recipe states {p['bounded']}")
    lines = []
    if p["monotone"] in ("rows", "both"):
        lines += [(f"row {lab}", list(zip(cols, cells))) for lab, cells in rows]
    if p["monotone"] in ("columns", "both"):
        lines += [(f"column {cols[j]}", [(lab, cells[j]) for lab, cells in rows]) for j in range(len(cols))]
    for name, line in lines:
        line = [(lab, c) for lab, c in line if c is not None]
        for i in range(len(line)):
            for j in range(i + 1, len(line)):
                if not _can_precede(line[i][1], line[j][1]):
                    raise ValueError(f"{name}: {line[i][1][0]} at {line[i][0]} cannot come before {line[j][1][0]} at "
                                     f"{line[j][0]} if the values do not decrease")
    if p["symmetric"]:
        labels = [r[0] for r in rows]
        if labels != list(cols):
            raise ValueError("a symmetric table has its column labels as row labels, in the same order")
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, b = rows[i][1][j], rows[j][1][i]
                if (a is None) != (b is None) or (a is not None and a[1:] != b[1:]):
                    raise ValueError(f"cell ({labels[i]}, {labels[j]}) is {a[0] if a else 'empty'} but "
                                     f"({labels[j]}, {labels[i]}) is {b[0] if b else 'empty'}")
    for r, c, want in parse_claims(p["claims"]):
        ri = next((i for i, (lab, _) in enumerate(rows) if lab == r), None)
        cj = next((j for j, lab in enumerate(cols) if lab == c), None)
        if ri is None or cj is None:
            raise ValueError(f"claim {r},{c}: the table has no {'row' if ri is None else 'column'} "
                             f"{r if ri is None else c!r}")
        got = rows[ri][1][cj]
        if got is None or got[1:] != want[1:]:
            raise ValueError(f"claim {r},{c}:{want[0]}: the table says {got[0] if got else 'nothing'} there")
    return counts


def layout(tab, p) -> dict:
    """Pixel sizes of the table at text size s: one width per column, the row-label column, a cell height."""
    s = p["text_size"]
    pad = s + 1
    tw = lambda t: text_width(t, s)  # noqa: E731
    colw = [max([tw(c)] + [tw(cells[j][0]) for _, cells in tab.rows if cells[j] is not None]) + 2 * pad
            for j, c in enumerate(tab.cols)]
    labw = max([tw(tab.corner)] + [tw(lab) for lab, _ in tab.rows]) + 2 * pad
    ch = 5 * s + 2 * pad
    width = labw + sum(w + 1 for w in colw)
    height = (len(tab.rows) + 1) * (ch + 1) - 1
    return {"s": s, "pad": pad, "colw": colw, "labw": labw, "ch": ch, "width": width, "height": height}


def _legend(counts, s):
    present = [k for k in KINDS + ("unknown",) if counts[k]]
    return present, sum(5 * s + 2 * s + text_width(NAMES[k], s) for k in present) + 4 * s * (len(present) - 1)


def bounds(seed, pal, w, h, p, tab) -> Canvas:
    """Generator data.bounds: check, then the table: column labels on top, row labels on the left, one coloured cell
    per entry with its value written in it, and the legend of the kinds present underneath."""
    counts = check(tab, p)
    L = layout(tab, p)
    s, pad, ch = L["s"], L["pad"], L["ch"]
    present, legw = _legend(counts, s) if p["legend"] else ([], 0)
    width = max(L["width"], legw)
    height = L["height"] + ((ch + 1) if present else 0)
    if width > w or height > h:
        raise ValueError(f"the table needs {width} × {height} pixels at text_size {s}; give a larger size or a smaller "
                         f"text_size")
    ramp = pal.ramp(p["ramp"])
    colour = {k: ramp[i * len(ramp) // len(KINDS)] for i, k in enumerate(KINDS)}
    grid = pal.ramp(p["grid_ramp"])
    colour["unknown"] = grid[len(grid) // 2]
    ink = pal.ramp(p["text_ramp"])[0]
    label = pal.ramp(p["label_ramp"])[0]
    cv = Canvas(w, h, pal)
    if p["background"]:
        cv.rect(0, 0, w - 1, h - 1, pal.ramp(p["background"])[0])
    ox, oy = (w - width) // 2, (h - height) // 2
    _text(cv, ox + pad, oy + pad, tab.corner, s, label)
    xs, x = [], ox + L["labw"] + 1
    for cw in L["colw"]:
        xs.append(x)
        x += cw + 1
    for j, c in enumerate(tab.cols):
        _text(cv, xs[j] + (L["colw"][j] - text_width(c, s)) // 2, oy + pad, c, s, label)
    for i, (lab, cells) in enumerate(tab.rows):
        y = oy + (i + 1) * (ch + 1)
        _text(cv, ox + pad, y + pad, lab, s, label)
        for j, c in enumerate(cells):
            if c is None:
                continue
            cw = L["colw"][j]
            cv.rect(xs[j], y, xs[j] + cw - 1, y + ch - 1, colour[kind(c)])
            _text(cv, xs[j] + (cw - text_width(c[0], s)) // 2, y + pad, c[0], s, ink)
    if present:
        y = oy + L["height"] + 1 + pad
        x = ox
        for k in present:
            cv.rect(x, y, x + 5 * s - 1, y + 5 * s - 1, colour[k])
            x += 5 * s + 2 * s
            _text(cv, x, y, NAMES[k], s, label)
            x += text_width(NAMES[k], s) + 4 * s
    return cv
