"""
The terms of an integer sequence from an OEIS b-file, checked before they are drawn / términos de una secuencia.

A b-file (the OEIS format: `n a(n)` per line) is drawn as bars, one per term, on a linear or a logarithmic scale, with
the terms from `new_from` on in their own colour: what a contributor adds to an entry. Before drawing:

  indices   consecutive (the reader refuses gaps and repeats)
  first, last  the first and last index are the stated ones (-1 = any)
  terms     the terms from `new_from` on are exactly the stated ones (a comma-separated list), so the highlighted part of
            the figure is what the contribution says it is
  count     the number of terms (0 = any)
  nonneg    every term is ≥ 0 (needed by the logarithmic scale; on by default)

Terms may have thousands of digits: the logarithmic scale is computed from the integer itself (its bit length and
leading bits), never from a float that would overflow.
"""
from __future__ import annotations

from .. import fmath as fm
from ..pixel.canvas import Canvas

_LOG10_2 = 0.30102999566398120


def log10_int(v: int) -> float:
    """log10(v) for an integer v ≥ 1 of any size, from its bit length and leading 53 bits."""
    bl = v.bit_length()
    if bl <= 1000:
        return fm.log(float(v)) / fm.log(10.0)
    lead = v >> (bl - 53)
    return fm.log(float(lead)) / fm.log(10.0) + (bl - 53) * _LOG10_2


def parse_terms(text: str) -> list[int]:
    try:
        return [int(t) for t in text.replace(" ", "").split(",") if t]
    except ValueError:
        raise ValueError(f"terms {text[:40]!r}: write integers separated by commas, e.g. 6,10,18") from None


def check(seq, p) -> dict:
    terms = seq.terms
    first, last = terms[0][0], terms[-1][0]
    if p["first"] >= 0 and first != p["first"]:
        raise ValueError(f"the b-file starts at n = {first}, the recipe states {p['first']}")
    if p["last"] >= 0 and last != p["last"]:
        raise ValueError(f"the b-file ends at n = {last}, the recipe states {p['last']}")
    if p["count"] and len(terms) != p["count"]:
        raise ValueError(f"{len(terms)} terms, the recipe states {p['count']}")
    if p["nonneg"]:
        bad = next(((n, v) for n, v in terms if v < 0), None)
        if bad:
            raise ValueError(f"a({bad[0]}) = {bad[1]} is negative (set nonneg: false, and use the linear scale)")
    if p["terms"]:
        if p["new_from"] < 0:
            raise ValueError("terms are checked from new_from on: give new_from")
        want = parse_terms(p["terms"])
        got = [v for n, v in terms if n >= p["new_from"]]
        if got != want:
            k = next((i for i, (g, x) in enumerate(zip(got, want)) if g != x), min(len(got), len(want)))
            n = p["new_from"] + k
            raise ValueError(f"from n = {p['new_from']} the b-file has {len(got)} terms and the recipe {len(want)}; "
                             f"first difference at n = {n}: "
                             f"{got[k] if k < len(got) else 'none'} in the file, {want[k] if k < len(want) else 'none'} stated")
    return {"terms": len(terms), "first": first, "last": last}


def sequence(seed, pal, w, h, p, seq) -> Canvas:
    """Generator data.sequence: check, then one bar per term (several terms per pixel column show their maximum),
    old terms in `ramp_old`, terms from `new_from` on in `ramp_new`, a dashed line where the new terms start."""
    check(seq, p)
    terms = seq.terms
    if p["scale"] == "log":
        if any(v < 0 for _, v in terms):
            raise ValueError("the logarithmic scale needs non-negative terms")
        hv = [log10_int(v + 1) for _, v in terms]                     # log10(a + 1): 0 stays 0
    else:
        top = max(abs(v) for _, v in terms) or 1
        hv = [v / top for _, v in terms]                              # int / int is correctly rounded at any size
    peak = max(max(hv), 1e-300)
    n = len(terms)
    base = h - 2
    bar = max(1, w // n)
    gap = 1 if bar >= 4 else 0
    left = (w - bar * n) // 2 if bar * n <= w else 0
    old = pal.ramp(p["ramp_old"])
    new = pal.ramp(p["ramp_new"])
    c_old, c_new = old[len(old) // 2], new[(len(new) * 3) // 4]
    axis = pal.ramp(p["axis_ramp"])[0]
    bg = pal.ramp(p["background"])[0] if p["background"] else None
    cv = Canvas(w, h, pal)
    if bg is not None:
        cv.rect(0, 0, w - 1, h - 1, bg)
    cols = {}
    for i, ((idx, _), v) in enumerate(zip(terms, hv)):
        x = left + i * bar if bar * n <= w else i * w // n
        hpx = int(fm.floor(max(v, 0.0) / peak * (base - 1) + 0.5))
        is_new = p["new_from"] >= 0 and idx >= p["new_from"]
        prev = cols.get(x, (0, False))
        cols[x] = (max(hpx, prev[0]), is_new or prev[1])             # several terms per column: tallest, new if any is
    for x, (hpx, is_new) in cols.items():
        x1 = x + (bar - 1 - gap if bar * n <= w else 0)
        if hpx > 0:
            cv.rect(x, base - hpx, x1, base - 1, c_new if is_new else c_old)
    cv.line(0, base, w - 1, base, axis)
    if p["new_from"] >= 0:
        k = next((i for i, (idx, _) in enumerate(terms) if idx >= p["new_from"]), None)
        if k is not None:
            x = (left + k * bar if bar * n <= w else k * w // n) - (1 if gap else 0)
            for y in range(0, base, 6):
                cv.line(x, y, x, min(base - 1, y + 2), axis)
    return cv
