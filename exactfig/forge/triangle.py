"""
Right triangles with rational sides, checked before they are drawn / triángulos rectángulos racionales, comprobados antes.

A positive integer n is a *congruent number* when it is the area of a right triangle whose three sides are rational:
6 (3, 4, 5), 5 (3/2, 20/3, 41/6), 7 (24/5, 35/12, 337/60), and 157, whose simplest triangle has sides with numerators of
up to 48 digits (Zagier). A triangle is a certificate anyone can check with exact arithmetic, and that is what happens
here before anything is drawn:

  every triangle   a, b, c > 0, a² + b² = c² and a·b/2 = n, in exact fractions (no floating point decides anything)
  squarefree       n is squarefree (the usual convention: n and n·k² are congruent together), on by default
  count            the file has exactly this many triangles (0 = any)
  distinct         no n appears twice, on by default

A refusal names the triangle and the equation that fails, with the exact difference. Each triangle is drawn in its own
tile with legs along the axes, scaled to fit (the right angle at the bottom left, so its shape is true); the shading is
the order of n in the file (smallest to largest) along the light part of the ramp.
"""
from __future__ import annotations

from fractions import Fraction

from .. import fmath as fm
from ..pixel.canvas import Canvas


def squarefree(n: int) -> bool:
    if n < 1:
        return False
    d = 2
    while d * d <= n:
        if n % (d * d) == 0:
            return False
        d += 1
    return True


def check(tris, p) -> dict:
    if p["count"] and len(tris) != p["count"]:
        raise ValueError(f"{len(tris)} triangles in the file, the recipe states {p['count']}")
    seen = {}
    for k, (n, a, b, c) in enumerate(tris, 1):
        where = f"triangle {k} (n = {n})"
        if n.denominator != 1 or n < 1:
            raise ValueError(f"{where}: the area n must be a positive integer")
        if min(a, b, c) <= 0:
            raise ValueError(f"{where}: sides must be positive")
        if a * a + b * b != c * c:
            raise ValueError(f"{where}: a² + b² − c² = {a * a + b * b - c * c}, not 0: not a right triangle")
        if a * b != 2 * n:
            raise ValueError(f"{where}: a·b/2 = {a * b / 2}, not {n}")
        if p["squarefree"] and not squarefree(int(n)):
            raise ValueError(f"{where}: {n} is not squarefree (state the squarefree part, or set squarefree: false)")
        if p["distinct"]:
            if n in seen:
                raise ValueError(f"{where}: n = {n} already appears as triangle {seen[n]}")
            seen[n] = k
    return {"triangles": len(tris)}


def triangles(seed, pal, w, h, p, data) -> Canvas:
    """Generator data.triangle: check (see the module), then one triangle per tile, legs on the axes, right angle at
    the bottom left, filled by area along the ramp, the hypotenuse in `edge_ramp`."""
    tris = data.triangles
    check(tris, p)
    k = len(tris)
    cols = p["columns"] or max(1, min(k, int(fm.floor(fm.sqrt(k * w / h) + 0.5))))
    rows = -(-k // cols)
    tile = min(w // cols, h // rows)
    pad = max(1, tile // 10)
    if tile - 2 * pad < 4:
        raise ValueError(f"data.triangle: {k} triangles do not fit in {w}x{h}; give a larger size")
    ramp = pal.ramp(p["ramp"])
    edge = pal.ramp(p["edge_ramp"])[0]
    bg = pal.ramp(p["background"])[0] if p["background"] else None
    rank = {n: r for r, n in enumerate(sorted({t[0] for t in tris}))}      # colour by order of n, not by its size
    top = max(1, len(rank) - 1)
    cv = Canvas(w, h, pal)
    if bg is not None:
        cv.rect(0, 0, w - 1, h - 1, bg)
    ox, oy = (w - cols * tile) // 2, (h - rows * tile) // 2
    for i, (n, a, b, c) in enumerate(tris):
        s = Fraction(tile - 2 * pad - 1) / max(a, b)                   # exact scale: the longer leg fills the tile
        aw, bh = int(a * s), int(b * s)                                # floor of exact rationals: no rounding drift
        x0 = ox + (i % cols) * tile + pad
        y0 = oy + (i // cols) * tile + pad + (tile - 2 * pad - 1)       # bottom-left corner (the right angle)
        t = 0.4 + 0.6 * rank[n] / top                                     # the light part of the ramp, on a dark ground
        fill = ramp[int(fm.floor(t * (len(ramp) - 1) + 0.5))]
        for yy in range(bh + 1):                                        # rows from the bottom: x ≤ a·(1 − y/b)
            xmax = int(Fraction(aw) * (bh - yy) / bh) if bh else aw
            for xx in range(xmax + 1):
                cv.set(x0 + xx, y0 - yy, fill)
        cv.line(x0, y0, x0 + aw, y0, edge)
        cv.line(x0, y0, x0, y0 - bh, edge)
        cv.line(x0 + aw, y0, x0, y0 - bh, edge)
    return cv
