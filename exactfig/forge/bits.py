"""
The binary expansions of exact integers, with their ones checked before they are drawn / los unos de enteros exactos.

Some integers that look like noise in decimal are regular in binary: 2^n, 2^n − 1, repunits, Fermat numbers, the partial
quotients of some continued fractions. The terms of an OEIS b-file (`n a(n)` per line) are drawn one per row, each bit at
its place value, and the recipe says where the ones are. Before drawing:

  terms     every drawn term is positive
  first, last, count   the drawn indices and their number are the stated ones
  combs     `n:start,step,count; …`: the ones of a(n) are exactly at the positions start, start + step, …, count of them
  complete  every drawn term has a stated comb (on by default when combs are given)
  ones      `n:k; …`: a(n) has exactly k ones

Positions count from 0, the units bit. Everything is computed on Python integers; nothing passes through a float.
"""
from __future__ import annotations

from ..pixel.canvas import Canvas
from .annotate import _text, text_width


def ones(v: int) -> list[int]:
    """The positions of the ones of v ≥ 0 in binary, from the units bit up."""
    s = bin(v)[2:]
    return [k for k, ch in enumerate(reversed(s)) if ch == "1"]


def parse_combs(text: str) -> list[tuple[int, int, int, int]]:
    """`n:start,step,count; …` as (n, start, step, count)."""
    out, seen = [], set()
    for item in (t.strip() for t in text.split(";")):
        if not item:
            continue
        try:
            n, rest = item.split(":")
            start, step, count = (int(x) for x in rest.split(","))
            n = int(n)
        except ValueError:
            raise ValueError(f"comb {item[:40]!r}: write n:start,step,count, e.g. 5:8,19,3") from None
        if start < 0 or step < 1 or count < 1:
            raise ValueError(f"comb {item[:40]!r}: start is at least 0, step and count at least 1")
        if n in seen:
            raise ValueError(f"combs: two combs for n = {n}")
        seen.add(n)
        out.append((n, start, step, count))
    return out


def parse_ones(text: str) -> list[tuple[int, int]]:
    """`n:k; …` as (n, k)."""
    out, seen = [], set()
    for item in (t.strip() for t in text.split(";")):
        if not item:
            continue
        try:
            n, k = (int(x) for x in item.split(":"))
        except ValueError:
            raise ValueError(f"ones {item[:40]!r}: write n:k, e.g. 5:3") from None
        if n in seen:
            raise ValueError(f"ones: n = {n} is stated twice")
        seen.add(n)
        out.append((n, k))
    return out


def _short(v: int) -> str:
    s = str(v)
    return s if len(s) <= 20 else f"{s[:6]}…{s[-4:]} ({len(s)} digits)"


def check(seq, p) -> list:
    """The checks of the module; returns (n, value, positions of its ones) for each drawn term."""
    terms = [(n, v) for n, v in seq.terms if (p["first"] < 0 or n >= p["first"]) and (p["last"] < 0 or n <= p["last"])]
    if not terms:
        raise ValueError(f"the b-file has no term from n = {p['first']} to n = {p['last']}")
    if p["first"] >= 0 and terms[0][0] != p["first"]:
        raise ValueError(f"the b-file starts at n = {terms[0][0]}, the recipe asks for n = {p['first']}")
    if p["last"] >= 0 and terms[-1][0] != p["last"]:
        raise ValueError(f"the b-file ends at n = {terms[-1][0]}, the recipe asks for n = {p['last']}")
    if p["count"] and len(terms) != p["count"]:
        raise ValueError(f"{len(terms)} terms, the recipe states {p['count']}")
    for n, v in terms:
        if v <= 0:
            raise ValueError(f"a({n}) = {_short(v)} is not positive, so it has no binary expansion to draw (give first "
                             f"and last)")
    rows = [(n, v, ones(v)) for n, v in terms]
    by = {n: (v, u) for n, v, u in rows}
    combs = parse_combs(p["combs"])
    for n, start, step, count in combs:
        if n not in by:
            raise ValueError(f"comb for n = {n}: that term is not drawn")
        v, got = by[n]
        # compared without listing a stated comb that may be far longer than the term
        if len(got) != count:
            raise ValueError(f"a({n}) = {_short(v)} has {len(got)} ones, its comb states {count}")
        k = next((j for j in range(count) if got[j] != start + j * step), None)
        if k is not None:
            raise ValueError(f"a({n}) = {_short(v)}: one number {k + 1} is at position {got[k]}, its comb says "
                             f"{start + k * step}")
    if combs and p["complete"]:
        miss = [n for n, _, _ in rows if n not in {c[0] for c in combs}]
        if miss:
            raise ValueError(f"no comb is stated for n = {', '.join(map(str, miss[:8]))} (give it, or complete: false)")
    for n, k in parse_ones(p["ones"]):
        if n not in by:
            raise ValueError(f"ones for n = {n}: that term is not drawn")
        if len(by[n][1]) != k:
            raise ValueError(f"a({n}) = {_short(by[n][0])} has {len(by[n][1])} ones, the recipe states {k}")
    return rows


def bits(seed, pal, w, h, p, seq) -> Canvas:
    """Generator data.bits: check, then one row per term: its index, its bits with the units on the right, and its length
    in bits. A pixel column that holds several bits is a one when any of them is."""
    rows = check(seq, p)
    s = p["text_size"]
    pad = s + 1
    rowh = 5 * s + 2 * pad
    labs = [f"A({n})" for n, _, _ in rows]
    tags = [f"{u[-1] + 1} BITS" if u[-1] else "1 BIT" for _, _, u in rows]
    labw = max(text_width(t, s) for t in labs) + 2 * pad
    tagw = max(text_width(t, s) for t in tags) + 2 * pad
    room = w - labw - tagw
    if room < 16:
        raise ValueError(f"the figure needs more than {labw + tagw + 16} pixels of width at text_size {s}")
    if len(rows) * rowh > h:
        raise ValueError(f"the figure needs {len(rows) * rowh} pixels of height at text_size {s}; give a larger size")
    one = pal.ramp(p["ramp"])
    c_one = one[(len(one) * 3) // 4]
    zero = pal.ramp(p["zero_ramp"])
    c_zero = zero[len(zero) // 2]
    label = pal.ramp(p["label_ramp"])[0]
    cv = Canvas(w, h, pal)
    if p["background"]:
        cv.rect(0, 0, w - 1, h - 1, pal.ramp(p["background"])[0])
    oy = (h - len(rows) * rowh) // 2
    longest = max(u[-1] + 1 for _, _, u in rows)
    x0, x1 = labw, labw + room - 1
    tooth = 2 * rowh // 3                                                # the widest mark of a one
    for i, ((n, v, u), lab, tag) in enumerate(zip(rows, labs, tags)):
        y = oy + i * rowh
        nb = u[-1] + 1
        full = longest if p["scale"] == "common" else nb
        wide = room // full >= 4 * s                                     # room for a mark at every bit

        def span(k: int) -> tuple[int, int]:
            """First and last pixel column of bit k: the row is `full` bits wide, the units on the right."""
            a, b = x0 + (full - 1 - k) * room // full, x0 + (full - k) * room // full - 1
            if b - a + 1 > tooth:
                a += (b - a + 1 - tooth) // 2
                b = a + tooth - 1
            return a, max(a, b)

        base = y + rowh - pad - 1
        _text(cv, pad, y + pad, lab, s, label)
        _text(cv, x1 + pad, y + pad, tag, s, label)
        cv.rect(x0 + (full - nb) * room // full, base, x1, base, c_zero)  # the zeros: a line as long as the number
        if wide:
            for k in range(nb):
                a, b = span(k)
                m = (a + b) // 2
                cv.rect(m, base - s, m, base, c_zero)
        for k in u:
            a, b = span(k)
            if wide and b - a + 1 < tooth:
                b -= 1                                                   # neighbouring ones stay apart
            cv.rect(a, y + pad, max(a, b), base, c_one)
    return cv
