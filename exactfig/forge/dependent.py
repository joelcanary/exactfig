"""
Sets of cells in which every point has at most k neighbours, checked before they are drawn / conjuntos k-dependientes.

The cells of a board are the vertices of the kings graph: two cells are neighbours when they differ by at most 1 in each
coordinate. A set is k-dependent when each of its points has at most k neighbours in the set. The largest such sets on
the n×n torus are OEIS A101201 for k = 4 (A103139 on the ordinary board), and their density is the subject of the
conjectures of Ionascu, Pritikin and Wright. A search program writes the sets it found; before a single pixel is drawn
the generator checks them against what the recipe states, and refuses to draw (ValueError naming the first board that
fails) if anything does not hold:

  k            every point has at most k of its 8 neighbours in the set
  topology     "torus": rows and columns wrap around (on a side of 1 or 2 a neighbour may be the same cell twice and it
               counts twice, as in A101201); "plane": cells outside the board are empty
  population   every board has exactly this many points (0 = any)
  populations  the boards have exactly these numbers of points, in file order (a list, e.g. the terms of a sequence)
  count        exactly this many boards (0 = any)
  distinct     no two boards are the same up to the symmetries of the board: on the torus the translations together with
               the rotations and reflections that keep its shape; on the plane those rotations and reflections alone

Unlike data.catalog, the board keeps its declared size W×H, empty rows and columns included: on a torus the empty border
is part of the set's period. Each board is drawn whole, with a frame around it, so the picture shows the tile that wraps.
"""
from __future__ import annotations

from .. import fmath as fm
from ..pixel.canvas import Canvas

OFFSETS = tuple((dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy)


def neighbours(w, h, cells: set, x, y, torus: bool) -> int:
    """Points of `cells` among the 8 neighbours of (x, y), with multiplicity on a small torus."""
    s = 0
    for dx, dy in OFFSETS:
        u, v = x + dx, y + dy
        if torus:
            s += ((u % w, v % h) in cells)
        elif 0 <= u < w and 0 <= v < h:
            s += ((u, v) in cells)
    return s


def worst(w, h, cells, torus: bool):
    """(largest number of neighbours of a point, a point that has it); (0, None) for the empty set."""
    best, at = 0, None
    for x, y in sorted(cells):
        c = neighbours(w, h, cells, x, y, torus)
        if at is None or c > best:
            best, at = c, (x, y)
    return best, at


def _maps(w, h):
    """The rotations and reflections that keep a w×h board, as functions of (x, y)."""
    m = [lambda x, y: (x, y), lambda x, y: (w - 1 - x, y), lambda x, y: (x, h - 1 - y),
         lambda x, y: (w - 1 - x, h - 1 - y)]
    if w == h:
        m += [lambda x, y: (y, x), lambda x, y: (w - 1 - y, x), lambda x, y: (y, h - 1 - x),
              lambda x, y: (w - 1 - y, h - 1 - x)]
    return m


def canonical(w, h, cells, torus: bool) -> tuple:
    """The smallest image of the set under the symmetries of its board (see the module)."""
    best = None
    shifts = [(a, b) for a in range(w) for b in range(h)] if torus else [(0, 0)]
    for f in _maps(w, h):
        img = [f(x, y) for x, y in cells]
        for a, b in shifts:
            t = tuple(sorted(((x + a) % w, (y + b) % h) for x, y in img))
            if best is None or t < best:
                best = t
    return (w, h, best)


def parse_populations(text: str) -> list:
    if not text.strip():
        return []
    try:
        out = [int(t) for t in text.replace(" ", "").split(",")]
    except ValueError:
        raise ValueError(f"populations {text!r}: a comma-separated list of integers") from None
    if any(v < 0 for v in out):
        raise ValueError(f"populations {text!r}: a number of points is not negative")
    return out


def check(boards, p) -> dict:
    """Check the boards against the recipe; ValueError on the first board that fails. Returns what was checked."""
    torus = p["topology"] == "torus"
    if p["count"] and len(boards) != p["count"]:
        raise ValueError(f"boards: {len(boards)} boards, the recipe states {p['count']}")
    pops = parse_populations(p["populations"])
    if pops and len(pops) != len(boards):
        raise ValueError(f"boards: the recipe states {len(pops)} populations for {len(boards)} boards")
    seen, most = {}, 0
    for k, (w, h, cells) in enumerate(boards):
        where = f"board {k + 1} ({w}x{h})"
        cs = set(cells)
        if p["population"] and len(cs) != p["population"]:
            raise ValueError(f"{where}: {len(cs)} points, the recipe states {p['population']}")
        if pops and len(cs) != pops[k]:
            raise ValueError(f"{where}: {len(cs)} points, the recipe states {pops[k]}")
        m, at = worst(w, h, cs, torus)
        if m > p["k"]:
            raise ValueError(f"{where}: the point {at} has {m} neighbours "
                             f"({'on the torus' if torus else 'on the board'}), more than k = {p['k']}")
        most = max(most, m)
        if p["distinct"]:
            c = canonical(w, h, cs, torus)
            if c in seen:
                raise ValueError(f"{where}: the same as board {seen[c] + 1} up to the symmetries of the "
                                 f"{'torus' if torus else 'board'}")
            seen[c] = k
    return {"boards": len(boards), "most_neighbours": most}


def dependent(seed, pal, w, h, p, data) -> Canvas:
    """Generator data.dependent: check the boards (see the module), then draw each whole, framed, in file order."""
    boards = data.boards
    check(boards, p)
    n = len(boards)
    cols = p["columns"] or max(1, min(n, int(fm.floor(fm.sqrt(n * w / h) + 0.5))))
    rows = -(-n // cols)
    tile = min(w // cols, h // rows)
    side = max(max(bw, bh) for bw, bh, _ in boards)
    frame = 1 if p["frame"] else 0
    room = tile - 2 * p["padding"] - 2 * frame
    cell = room // side if room > 0 else 0
    if cell < 1:
        raise ValueError(f"data.dependent: {n} boards of side up to {side} do not fit in {w}x{h} "
                         f"({cols} columns, tiles of {tile} px); give a larger size or fewer columns")
    gap = min(p["cell_gap"], cell // 3)
    ramp = pal.ramp(p["ramp"])
    ink = ramp[min(len(ramp) - 1, int(p["tone"] * (len(ramp) - 1) + 0.5))]
    fr = pal.ramp(p["frame_ramp"])
    edge = fr[len(fr) // 2]          # the middle tone: the first of a ramp is its darkest, invisible on ink
    bg = pal.ramp(p["background"])[0] if p["background"] else None
    cv = Canvas(w, h, pal)
    if bg is not None:
        cv.rect(0, 0, w - 1, h - 1, bg)
    ox, oy = (w - cols * tile) // 2, (h - rows * tile) // 2
    for k, (bw, bh, cells) in enumerate(boards):
        tx = ox + (k % cols) * tile + (tile - bw * cell) // 2
        ty = oy + (k // cols) * tile + (tile - bh * cell) // 2
        if frame:
            x0, y0, x1, y1 = tx - 1, ty - 1, tx + bw * cell - gap, ty + bh * cell - gap
            for a, b, c, d in ((x0, y0, x1, y0), (x0, y1, x1, y1), (x0, y0, x0, y1), (x1, y0, x1, y1)):
                cv.line(a, b, c, d, edge)
        for x, y in cells:
            x0, y0 = tx + x * cell, ty + y * cell
            cv.rect(x0, y0, x0 + cell - 1 - gap, y0 + cell - 1 - gap, ink)
    return cv
