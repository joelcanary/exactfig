"""
A catalogue of cell patterns drawn as a mosaic, checked before it is drawn / un catálogo de patrones, comprobado antes de dibujarlo.

A search program lists, say, every still life of 14 cells under the rule B368/S245; the count is a term of an integer
sequence and the mosaic is its picture. Before a single pixel is drawn the generator checks the catalogue against what the
recipe states, and refuses to draw (ValueError naming the first pattern that fails) if anything does not hold:

  check       "still"       every pattern is unchanged by one generation of `rule`
              "oscillator"  every pattern returns to itself after exactly `period` generations and not before
              "none"        nothing is checked about the dynamics
  strict      (still lifes) no pattern splits into two or more groups of its islands (8-connected components) that are
              each still on their own: the "strict" still lifes that sequences such as OEIS A019473 count
  population  every pattern has exactly this many live cells (0 = any)
  count       the catalogue has exactly this many patterns (0 = any): the term of the sequence
  distinct    no two patterns are the same up to rotation and reflection

Patterns are simulated on the infinite plane (only the live cells and their neighbours are stored), so no board edge
decides anything. Rules with B0 are refused: under them the empty background itself changes, and "a finite pattern that
does not change" means something else.
"""
from __future__ import annotations

from .. import fmath as fm
from ..pixel.canvas import Canvas
from .motion import parse_rule

MAX_ISLANDS = 9          # set partitions of 9 islands: 21147 (Bell number), each checked in a few generations


def step(cells: set, birth, survive) -> set:
    """One generation of a Life-like rule (without B0) on the infinite plane."""
    near = {c: 0 for c in cells}                 # a live cell with no live neighbour still has to be looked at (S0)
    for x, y in cells:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    k = (x + dx, y + dy)
                    near[k] = near.get(k, 0) + 1
    return {c for c, n in near.items() if (n in survive if c in cells else n in birth)}


def returns_after(cells, rule, generations: int) -> list[bool]:
    """[after 1 generation the pattern is itself?, after 2?, …] for 1..generations."""
    birth, survive = rule
    start = set(cells)
    now, out = start, []
    for _ in range(generations):
        now = step(now, birth, survive)
        out.append(now == start)
    return out


def islands(cells) -> list[list[tuple[int, int]]]:
    """The 8-connected components of a set of cells, each sorted, in order of their first cell."""
    left, comps = set(cells), []
    for c in sorted(cells):
        if c not in left:
            continue
        left.discard(c)
        comp, stack = [c], [c]
        while stack:
            x, y = stack.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    n = (x + dx, y + dy)
                    if n in left:
                        left.discard(n)
                        comp.append(n)
                        stack.append(n)
        comps.append(sorted(comp))
    return comps


def _partitions(items: list):
    """Every partition of `items` into non-empty groups (restricted growth strings)."""
    if not items:
        yield []
        return
    first, rest = items[0], items[1:]
    for part in _partitions(rest):
        for k in range(len(part)):
            yield part[:k] + [[first] + part[k]] + part[k + 1:]
        yield [[first]] + part


def is_pseudo(cells, rule) -> bool:
    """True if the islands of a still life split into two or more groups that are each still on their own."""
    comps = islands(cells)
    if len(comps) < 2:
        return False
    if len(comps) > MAX_ISLANDS:
        raise ValueError(f"strict check: {len(comps)} islands, more than {MAX_ISLANDS}")
    for part in _partitions(list(range(len(comps)))):
        if len(part) < 2:
            continue
        if all(returns_after([c for i in group for c in comps[i]], rule, 1)[0] for group in part):
            return True
    return False


def canonical(cells) -> tuple:
    """The smallest of the 8 rotations and reflections of a pattern, each moved to start at (0, 0)."""
    forms = []
    for sx in (1, -1):
        for sy in (1, -1):
            for swap in (False, True):
                t = [((y if swap else x) * sx, (x if swap else y) * sy) for x, y in cells]
                x0, y0 = min(a for a, _ in t), min(b for _, b in t)
                forms.append(tuple(sorted((a - x0, b - y0) for a, b in t)))
    return min(forms)


def check(patterns, p) -> dict:
    """Check the catalogue against the recipe; ValueError on the first pattern that fails. Returns what was checked."""
    if p["count"] and len(patterns) != p["count"]:
        raise ValueError(f"catalogue: {len(patterns)} patterns, the recipe states {p['count']}")
    rule = parse_rule(p["rule"])
    if p["check"] != "none" and 0 in rule[0]:
        raise ValueError(f"rule {p['rule']}: B0 rules are refused (the empty background is not still)")
    seen = {}
    for k, cells in enumerate(patterns):
        where = f"pattern {k + 1}"
        if p["population"] and len(cells) != p["population"]:
            raise ValueError(f"{where}: {len(cells)} live cells, the recipe states {p['population']}")
        if p["check"] == "still":
            if not returns_after(cells, rule, 1)[0]:
                raise ValueError(f"{where}: changes after one generation of {p['rule']}, not a still life")
            if p["strict"] and is_pseudo(cells, rule):
                raise ValueError(f"{where}: a pseudo still life (its islands split into still groups), not strict")
        elif p["check"] == "oscillator":
            back = returns_after(cells, rule, p["period"])
            if not back[-1] or any(back[:-1]):
                first = next((g + 1 for g, b in enumerate(back) if b), None)
                raise ValueError(f"{where}: not of period {p['period']} under {p['rule']}"
                                 + (f" (it returns after {first})" if first else " (it does not return)"))
        if p["distinct"]:
            c = canonical(cells)
            if c in seen:
                raise ValueError(f"{where}: the same as pattern {seen[c] + 1} up to rotation and reflection")
            seen[c] = k
    return {"patterns": len(patterns), "check": p["check"], "rule": p["rule"]}


def catalog(seed, pal, w, h, p, cat) -> Canvas:
    """Generator data.catalog: check the catalogue (see the module), then draw it as a mosaic in file order."""
    pats = cat.patterns
    check(pats, p)
    n = len(pats)
    cols = p["columns"] or max(1, min(n, int(fm.floor(fm.sqrt(n * w / h) + 0.5))))
    rows = -(-n // cols)
    tile = min(w // cols, h // rows)
    side = max(max(max(x for x, _ in c), max(y for _, y in c)) + 1 for c in pats)
    room = tile - 2 * p["padding"]
    cell = room // side if room > 0 else 0
    if cell < 1:
        raise ValueError(f"data.catalog: {n} patterns of side up to {side} do not fit in {w}x{h} "
                         f"({cols} columns, tiles of {tile} px); give a larger size or fewer columns")
    gap = min(p["cell_gap"], cell // 3)
    ramp = pal.ramp(p["ramp"])
    ink = ramp[min(len(ramp) - 1, int(p["tone"] * (len(ramp) - 1) + 0.5))]
    bg = pal.ramp(p["background"])[0] if p["background"] else None
    cv = Canvas(w, h, pal)
    if bg is not None:
        cv.rect(0, 0, w - 1, h - 1, bg)
    ox, oy = (w - cols * tile) // 2, (h - rows * tile) // 2
    for k, cells in enumerate(pats):
        bw = max(x for x, _ in cells) + 1
        bh = max(y for _, y in cells) + 1
        tx = ox + (k % cols) * tile + (tile - bw * cell) // 2
        ty = oy + (k // cols) * tile + (tile - bh * cell) // 2
        for x, y in cells:
            x0, y0 = tx + x * cell, ty + y * cell
            cv.rect(x0, y0, x0 + cell - 1 - gap, y0 + cell - 1 - gap, ink)
    return cv
