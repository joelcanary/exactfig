"""
The identity of the sandpile group, checked before it is drawn / la identidad del grupo de la pila de arena.

On an n × n grid whose border leaks grains to a sink, a cell with 4 or more grains topples, giving one to each
neighbour; a configuration with every cell below 4 is stable. Stable *recurrent* configurations form a group under
"add cell by cell, then stabilise" (the order of topplings does not matter: the abelian property), and its identity
is a famous fractal-looking picture. It is computed with Creutz's formula, e = stab(2·m − stab(2·m)), where m has 3
grains everywhere, and before drawing it is checked:

  stable        every cell of e holds 0..3 grains
  identity      stab(e + e) = e, cell by cell
  order         if `order` is stated, it must equal the order of the group, which the matrix-tree theorem says is the
                determinant of the reduced Laplacian (the number of spanning trees of the grid plus sink); it is
                computed exactly with fraction-free Gaussian elimination (Bareiss), for n up to 14

The cells are drawn with 0, 1, 2 and 3 grains as four steps of the ramp.
"""
from __future__ import annotations

from ..pixel.canvas import Canvas

MAX_N = 160
MAX_N_ORDER = 14


def stabilise(cells: list[int], n: int) -> list[int]:
    """Topple until every cell holds at most 3 grains; grains leaving the border are lost (the sink)."""
    c = list(cells)
    todo = [i for i, v in enumerate(c) if v >= 4]
    while todo:
        nxt = []
        for i in todo:
            v = c[i]
            if v < 4:
                continue
            q, c[i] = v >> 2, v & 3
            y, x = divmod(i, n)
            for j, ok in ((i - 1, x > 0), (i + 1, x < n - 1), (i - n, y > 0), (i + n, y < n - 1)):
                if ok:
                    c[j] += q
                    if c[j] >= 4:
                        nxt.append(j)
        todo = nxt
    return c


def identity(n: int) -> list[int]:
    s = stabilise([6] * (n * n), n)
    return stabilise([6 - v for v in s], n)


def group_order(n: int) -> int:
    """det of the reduced Laplacian of the n × n grid with sink, exactly (Bareiss): the number of spanning trees."""
    N = n * n
    a = [[0] * N for _ in range(N)]
    for i in range(N):
        y, x = divmod(i, n)
        a[i][i] = 4
        for j, ok in ((i - 1, x > 0), (i + 1, x < n - 1), (i - n, y > 0), (i + n, y < n - 1)):
            if ok:
                a[i][j] = -1
    prev = 1
    for k in range(N - 1):
        piv = a[k][k]                                   # the reduced Laplacian is positive definite: pivots are > 0
        rk = a[k]
        for i in range(k + 1, N):
            ri, f = a[i], a[i][k]
            for j in range(k + 1, N):
                ri[j] = (ri[j] * piv - f * rk[j]) // prev
            ri[k] = 0
        prev = piv
    return a[N - 1][N - 1]


def check(e: list[int], n: int, p) -> dict:
    if any(not 0 <= v <= 3 for v in e):
        raise AssertionError("the identity is not stable")              # cannot happen: stabilise guarantees it
    twice = stabilise([2 * v for v in e], n)
    if twice != e:
        k = next(i for i, (a, b) in enumerate(zip(twice, e)) if a != b)
        raise AssertionError(f"stab(e + e) differs from e at cell {divmod(k, n)}")
    out = {"n": n, "grains": sum(e)}
    if p["order"]:
        if n > MAX_N_ORDER:
            raise ValueError(f"order is checked for n up to {MAX_N_ORDER} (the determinant grows as n⁶); n = {n}")
        try:
            stated = int(p["order"])
        except ValueError:
            raise ValueError(f"order {p['order']!r} must be an integer") from None
        got = group_order(n)
        if got != stated:
            raise ValueError(f"the sandpile group of the {n}x{n} grid has order {got}, the recipe states {stated}")
        out["order"] = got
    return out


def sandpile(seed, pal, w, h, p) -> Canvas:
    """Generator math.sandpile: the identity of the n × n sandpile group, checked (see the module), one square per cell."""
    n = p["n"]
    e = identity(n)
    check(e, n, p)
    ramp = pal.ramp(p["ramp"])
    tone = [ramp[(k * (len(ramp) - 1)) // 3] for k in range(4)]
    cell = min(w // n, h // n)
    if cell < 1:
        raise ValueError(f"math.sandpile: an {n}x{n} grid needs at least {n}x{n} pixels")
    cv = Canvas(w, h, pal)
    ox, oy = (w - n * cell) // 2, (h - n * cell) // 2
    bg = pal.ramp(p["background"])[0] if p["background"] else None
    if bg is not None:
        cv.rect(0, 0, w - 1, h - 1, bg)
    for i, v in enumerate(e):
        y, x = divmod(i, n)
        cv.rect(ox + x * cell, oy + y * cell, ox + (x + 1) * cell - 1, oy + (y + 1) * cell - 1, tone[v])
    return cv
