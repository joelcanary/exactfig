"""
Certified enclosures that exclude zero, checked before they are drawn / cajas certificadas que excluyen el cero.

A computer-assisted proof often ends in a number known only inside a small ball: interval arithmetic (a Krawczyk or
Newton test, a validated quadrature) proves that the true value z lies in |z − c| ≤ r, and the proof needs only that the
ball does not contain 0, or that |z| stays above some bound. This generator draws a list of such balls, one per row, on a
logarithmic axis: a bar from the radius r to the distance |c| of the centre from 0. Its length is the number of decimal
digits by which the ball misses 0, so a certificate with plenty of room and one that barely passes look different.

Each row is `label, re, im, radius` with exact decimals (`29.58833207712801`, `-6.768887738202834`, `3.88e-46`); the
numbers are read as fractions, never rounded, and every check below is exact:

  zero       every ball excludes 0 (|c| > r), always; a ball that contains 0 proves nothing and is refused
  rows       the number of rows (0 = any)
  min_digits every ball misses 0 by at least that many digits: |c| ≥ 10^d · r
  claims     bounds on |z| a caption quotes, `label:>=30.35; label:<=31`, each holding for EVERY z in the ball
             (|c| − r ≥ v, or |c| + r ≤ v)
  agrees     a published value each ball must lie near, `label:re,im,tol; …`: |z − (re + im·i)| ≤ tol for every z in the
             ball (|c − ref| + r ≤ tol), so the figure cannot disagree with the source it reproduces

The digits written at the end of each row are the whole number of decimal digits by which its ball misses 0, computed
exactly; the axis is labelled in powers of ten.
"""
from __future__ import annotations

import re
from fractions import Fraction

from ..pixel.canvas import Canvas
from .annotate import FONT, _text, text_width
from .sequence import log10_int

MAX_DIGITS = 4000
MAX_EXPONENT = 1000
_DEC = re.compile(r"(?P<s>[-+]?)(?P<i>\d+)(?:\.(?P<f>\d+))?(?:[eE](?P<e>[-+]?\d+))?")


def p10(e: int) -> Fraction:
    """10^e as an exact fraction, for any integer e (integer powers only: no float is ever raised)."""
    return Fraction(pow(10, e)) if e >= 0 else Fraction(1, pow(10, -e))


def parse_decimal(tok: str) -> Fraction:
    """An exact decimal: `12`, `-0.5`, `3.88e-46`; read as a fraction, never rounded."""
    t = tok.strip()
    m = _DEC.fullmatch(t)
    if not m:
        raise ValueError(f"{tok!r} is not a decimal number (write e.g. -6.7688, 3.88e-46)")
    digits = m["i"] + (m["f"] or "")
    if len(digits) > MAX_DIGITS:
        raise ValueError(f"a number of more than {MAX_DIGITS} digits")
    e = int(m["e"] or "0")
    if abs(e) > MAX_EXPONENT or len(m["e"] or "") > 6:
        raise ValueError(f"the exponent of {t[:40]!r} is beyond ±{MAX_EXPONENT}")
    e -= len(m["f"] or "")
    v = Fraction(int(digits)) * p10(e)
    return -v if m["s"] == "-" else v


def _log10(q: Fraction) -> float:
    """log10 of a positive fraction, deterministic (exactfig.fmath through log10_int)."""
    return log10_int(q.numerator) - log10_int(q.denominator)


def norm2(re_: Fraction, im: Fraction) -> Fraction:
    return re_ * re_ + im * im


def digits_missed(c2: Fraction, r: Fraction) -> int:
    """The largest integer d with |c| ≥ 10^d · r, i.e. c2 ≥ 10^(2d) · r² (c2 = |c|²), exactly."""
    d = int(_log10(c2) / 2 - _log10(r)) + 1
    while d > -MAX_EXPONENT * 4 and c2 < p10(2 * d) * r * r:
        d -= 1
    while c2 >= p10(2 * (d + 1)) * r * r:
        d += 1
    return d


def _ge_dist(c2: Fraction, v: Fraction) -> bool:
    """|c| ≥ v."""
    return v <= 0 or c2 >= v * v


def _le_dist(c2: Fraction, v: Fraction) -> bool:
    """|c| ≤ v."""
    return v >= 0 and c2 <= v * v


def _items(text: str, what: str):
    for item in text.split(";"):
        item = item.strip()
        if not item:
            continue
        lab, sep, rest = item.partition(":")
        if not sep or not lab.strip() or not rest.strip():
            raise ValueError(f"{what} {item!r}: write label:{'>=30.35' if what == 'claim' else 're,im,tol'}")
        yield lab.strip(), rest.strip(), item


def parse_claims(text: str) -> list:
    out = []
    for lab, rest, item in _items(text, "claim"):
        m = re.fullmatch(r"(>=|<=|≥|≤) ?(.+)", rest)
        if not m:
            raise ValueError(f"claim {item!r}: a bound on |z| is >=v or <=v")
        out.append((lab, ">=" if m[1] in (">=", "≥") else "<=", parse_decimal(m[2]), rest.replace(" ", "")))
    return out


def parse_agrees(text: str) -> list:
    out = []
    for lab, rest, item in _items(text, "agreement"):
        parts = [x.strip() for x in rest.split(",")]
        if len(parts) != 3:
            raise ValueError(f"agreement {item!r}: write label:re,im,tol")
        re_, im, tol = (parse_decimal(x) for x in parts)
        if tol <= 0:
            raise ValueError(f"agreement {item!r}: the tolerance must be positive")
        out.append((lab, re_, im, tol))
    return out


def check(rows, p) -> list:
    """The checks of the module; returns, per row, (label, |c|², r, digits missed)."""
    if p["rows"] and len(rows) != p["rows"]:
        raise ValueError(f"{len(rows)} enclosures, the recipe states {p['rows']}")
    for lab, *_ in rows:
        bad = sorted({ch for ch in lab.upper() if ch not in FONT})
        if bad:
            raise ValueError(f"label {lab!r}: the 3×5 font has no {' '.join(bad)}")
    out, by = [], {}
    for lab, re_, im, r in rows:
        c2 = norm2(re_, im)
        if c2 <= r * r:
            raise ValueError(f"{lab}: the ball of radius {float(r):.3g} around {float(re_):.6g}{float(im):+.6g}i "
                             f"contains 0, so it proves nothing about the sign or size of the value")
        d = digits_missed(c2, r)
        if d < p["min_digits"]:
            raise ValueError(f"{lab}: the ball misses 0 by {d} digits, the recipe asks for at least {p['min_digits']}")
        out.append((lab, c2, r, d))
        by[lab] = (re_, im, r, c2)
    for lab, op, v, text in parse_claims(p["claims"]):
        if lab not in by:
            raise ValueError(f"claim {lab}:{text}: no enclosure is labelled {lab!r}")
        _, _, r, c2 = by[lab]
        ok = _ge_dist(c2, v + r) if op == ">=" else _le_dist(c2, v - r)
        if not ok:
            raise ValueError(f"claim {lab}:{text}: not every value in the ball satisfies |z| {op} {text[2:]}")
    for lab, re_, im, tol in parse_agrees(p["agrees"]):
        if lab not in by:
            raise ValueError(f"agreement {lab}: no enclosure is labelled {lab!r}")
        cr, ci, r, _ = by[lab]
        if not _le_dist(norm2(cr - re_, ci - im), tol - r):
            raise ValueError(f"agreement {lab}: the ball is not within {float(tol):.3g} of {float(re_):.10g}"
                             f"{float(im):+.10g}i")
    return out


def _step(lo: int, hi: int, room: int, labw: int) -> int:
    for st in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000):
        if ((hi - lo) // st + 1) * (labw + 4) <= room:
            return st
    return hi - lo or 1


def x_legend_width(s: int) -> int:
    return 3 * s + text_width("RADIUS", s) + 4 * s + 5 * s + text_width("DISTANCE OF THE CENTRE FROM 0", s)


def enclosures(seed, pal, w, h, p, data) -> Canvas:
    """Generator data.enclosures: check, then one row per ball: its label, a bar on a log10 axis from the radius to the
    distance of the centre from 0, and the number of digits by which it misses 0; powers of ten along the bottom."""
    rows = check(data.rows, p)
    s = p["text_size"]
    pad = s + 1
    rowh = 5 * s + 2 * pad
    labw = max(text_width(lab, s) for lab, *_ in rows) + 2 * pad
    tags = [f"{d} DIGITS" if d != 1 else "1 DIGIT" for *_, d in rows]
    tagw = max(text_width(t, s) for t in tags) + 2 * pad
    lr = [_log10(r) for *_, r, _ in rows]
    lc = [_log10(c2) / 2 for _, c2, _, _ in rows]
    lo, hi = int(min(lr) // 1), -int(-max(lc) // 1)
    hi = max(hi, lo + 1)
    room = w - labw - tagw - 2 * pad
    if room < 24:
        raise ValueError(f"the figure needs more than {labw + tagw + 2 * pad + 24} pixels of width at text_size {s}")
    tickw = max(text_width(f"1E{k}", s) for k in (lo, hi))
    st = _step(lo, hi, room, tickw)
    legend = p["legend"]
    if legend and x_legend_width(s) + labw + pad > w:
        raise ValueError(f"the legend needs {x_legend_width(s) + labw + pad} pixels of width at text_size {s}; give a "
                         f"larger size or legend false")
    height = len(rows) * (rowh + 1) + (2 * s + 5 * s + 2 * pad) + ((rowh + 1) if legend else 0)
    if height > h:
        raise ValueError(f"the figure needs {height} pixels of height at text_size {s}; give a larger size")
    ramp = pal.ramp(p["ramp"])
    bar, dot = ramp[len(ramp) // 2], ramp[-1]
    grid = pal.ramp(p["grid_ramp"])
    gridc = grid[len(grid) // 2]
    label = pal.ramp(p["label_ramp"])[0]
    cv = Canvas(w, h, pal)
    if p["background"]:
        cv.rect(0, 0, w - 1, h - 1, pal.ramp(p["background"])[0])
    oy = (h - height) // 2
    x0 = labw + pad
    x1 = x0 + room - 1

    def X(v: float) -> int:
        return x0 + int(round((v - lo) / (hi - lo) * (x1 - x0)))

    ybot = oy + len(rows) * (rowh + 1)
    first = -(-lo // st) * st
    for k in range(first, hi + 1, st):
        x = X(k)
        cv.line(x, oy, x, ybot + s, gridc)
        t = f"1E{k}"
        _text(cv, max(0, min(w - text_width(t, s), x - text_width(t, s) // 2)), ybot + 2 * s, t, s, label)
    for i, ((lab, _, _, d), a, b, tag) in enumerate(zip(rows, lr, lc, tags)):
        y = oy + i * (rowh + 1)
        ym = y + rowh // 2
        _text(cv, pad, y + pad, lab, s, label)
        xa, xb = X(a), X(b)
        cv.rect(xa, ym - s // 2, xb, ym + s // 2, bar)
        cv.rect(xa, y + pad, xa + max(0, s - 1), y + rowh - pad - 1, label)          # the radius: a bar across
        cv.rect(xb - s, ym - s, xb + s, ym + s, dot)                                 # the centre's distance to 0
        _text(cv, x1 + 2 * pad, y + pad, tag, s, label)
    if legend:
        y = ybot + 2 * s + 5 * s + 2 * pad + 1 + pad
        x = x0
        cv.rect(x, y, x + max(0, s - 1), y + 5 * s - 1, label)
        x += s + 2 * s
        _text(cv, x, y, "RADIUS", s, label)
        x += text_width("RADIUS", s) + 4 * s
        cv.rect(x, y + s, x + 2 * s, y + 3 * s, dot)
        x += 3 * s + 2 * s
        _text(cv, x, y, "DISTANCE OF THE CENTRE FROM 0", s, label)
    return cv
