"""
L-system trees / árboles por sistema L: a stochastic grammar, a turtle, and leaf clusters on a Vogel spiral.

The grammar is rewritten `iterations` times; when a symbol has several productions the choice is a hash of (seed, iteration,
position), so the same seed gives the same tree. The turtle walks the string (F forward, + − turn, [ ] push/pop); the tree is
scaled to fit the canvas; branches are Bresenham lines, thicker near the root; every tip gets a clump of leaves placed by the
golden angle and shaded like a sphere lit from the top-left.
Gramática estocástica, tortuga, ramas de Bresenham y copas en espiral de Vogel sombreadas como esferas.
"""
from __future__ import annotations

import math

from .. import fmath as fm
from ..pixel import pxmath as M
from ..pixel.canvas import Canvas
from ..rng import seed_int

PRESETS = {
    "bush": ("X", {"X": ["F[+X][-X]FX", "F[-X]FX", "F[+X]FX"], "F": ["FF"]}),
    "weeping": ("X", {"X": ["F[++X]F[-X]+X", "F[+X]F[--X]-X"], "F": ["FF"]}),
    "fern": ("X", {"X": ["F+[[X]-X]-F[-FX]+X"], "F": ["FF"]}),
    "sapling": ("F", {"F": ["F[+F]F[-F]F", "F[+F]F", "F[-F]F"]}),
}


def rewrite(axiom: str, rules: dict, iterations: int, seed: int) -> str:
    """Apply the productions `iterations` times. Where a symbol has several, the choice is hash2(iteration,
    position, seed): stochastic, yet the same on every machine. Stops growing past 200 000 symbols."""
    s = axiom
    for it in range(iterations):
        out = []
        for i, ch in enumerate(s):
            opts = rules.get(ch)
            out.append(opts[int(M.hash2(it, i, seed) * len(opts))] if opts else ch)
        s = "".join(out)
        if len(s) > 200_000:
            raise ValueError("L-system string too long: lower `iterations`")
    return s


def _walk(s: str, angle: float, sway: float, seed: int):
    x = y = 0.0
    a = -90.0
    stack, segs, tips = [], [], []
    depth = 0
    for i, ch in enumerate(s):
        if ch == "F":
            jitter = (M.hash2(i, 7, seed) - 0.5) * sway
            nx, ny = x + fm.cos(fm.radians(a + jitter)), y + fm.sin(fm.radians(a + jitter))
            segs.append((x, y, nx, ny, depth))
            x, y = nx, ny
        elif ch == "+":
            a += angle
        elif ch == "-":
            a -= angle
        elif ch == "[":
            stack.append((x, y, a, depth)); depth += 1
        elif ch == "]":
            tips.append((x, y))
            x, y, a, depth = stack.pop()
    tips.append((x, y))
    return segs, tips


def tree(seed, pal, w, h, p) -> Canvas:
    """Generator forge.flora.tree: interpret the rewritten string with a turtle, then add leaves."""
    sd = seed_int(seed, "tree")
    axiom, rules = PRESETS[p["preset"]]
    s = rewrite(axiom, rules, p["iterations"], sd)
    segs, tips = _walk(s, p["angle"], p["sway"], sd)
    xs = [v for sg in segs for v in (sg[0], sg[2])] or [0]
    ys = [v for sg in segs for v in (sg[1], sg[3])] or [0]
    leaf_r = p["leaf_size"]
    pad = leaf_r + 2
    k = min((w - 2 * pad) / max(1e-9, max(xs) - min(xs)), (h - pad - 1) / max(1e-9, max(ys) - min(ys)))
    bx, by = (w - 1) / 2 - k * (max(xs) + min(xs)) / 2, h - 1 - k * max(ys)

    def tr(px, py):
        return int(round(bx + k * px)), int(round(by + k * py))
    wood, leaf = pal.ramp(p["wood_ramp"]), pal.ramp(p["leaf_ramp"])
    ink = pal.ramp("ink")[0]
    cv = Canvas(w, h, pal)
    maxd = max((sg[4] for sg in segs), default=0) or 1
    for x0, y0, x1, y1, d in segs:
        a, b = tr(x0, y0), tr(x1, y1)
        thick = 0 if d > maxd * 0.4 else 1
        tone = wood[min(len(wood) - 1, 1 + (1 if d > maxd * 0.5 else 0))]
        pts = cv.line(*a, *b)
        for (x, y) in pts:
            cv.set(x, y, tone)
            if thick:
                cv.set(x + 1, y, wood[0])
    # copas: racimos de Vogel en las puntas, sombreados como esferas (luz arriba-izquierda)
    n_leaf = max(3, int(leaf_r * leaf_r * 1.6))
    seen = set()
    for i, (tx, ty) in enumerate(tips):
        cxp, cyp = tr(tx, ty)
        if (cxp, cyp) in seen or M.hash2(i, 3, sd) > p["foliage"]:
            continue
        seen.add((cxp, cyp))
        for (vx, vy) in M.vogel(n_leaf, leaf_r / math.sqrt(n_leaf)):
            x, y = int(round(cxp + vx)), int(round(cyp + vy))
            nx, ny = vx / leaf_r, vy / leaf_r
            lit = 0.55 - 0.45 * (nx + ny) / 1.4
            cv.set(x, y, leaf[max(0, min(len(leaf) - 1, int(lit * len(leaf))))])
    cv.outline(ink)
    return cv
