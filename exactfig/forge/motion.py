"""
Animated generators / generadores animados. Each returns a list of (delay_ms, Canvas) frames.

life     Life-like cellular automata, any rule written B…/S… (Conway's B3/S23, HighLife B36/S23, B37/S2378, …), on a torus or
         a bounded board, from a seeded random soup or a classic pattern; live cells coloured by age along a ramp.
wave     the 2-D wave equation u_tt = c² ∇²u by the leapfrog scheme (second order in time and space), with a periodic source,
         reflecting walls and an absorbing sponge at the border: double slit, single slit, a point source, two sources.
         Stable when c ≤ 1/√2 (the schema enforces it).
lorenz   the Lorenz system (σ, ρ, β) integrated by classical Runge–Kutta (RK4), drawn as a trail whose colour shows recency.
diffuse  the heat equation u_t = α ∇²u on a data grid (FTCS, reflecting borders, so the total is conserved), stable for
         α ≤ 1/4: the data's own diffusion, frame by frame.
frames   a sequence of grids computed elsewhere (for instance by a Lean program whose theorems are checked by Lean's kernel),
         drawn frame by frame with a colour ramp: the animation is then pinned to that program's output by its SHA-256.

All arithmetic is IEEE 754 basic operations plus exactfig.fmath, so every frame is the same bits on every platform.
"""
from __future__ import annotations

import re

from .. import fmath as fm
from ..data import field as F
from ..pixel.canvas import Canvas
from ..rng import Rng

PATTERNS = {                            # classic small patterns, cell (x, y) offsets
    "glider": [(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)],
    "r-pentomino": [(1, 0), (2, 0), (0, 1), (1, 1), (1, 2)],
    "acorn": [(1, 0), (3, 1), (0, 2), (1, 2), (4, 2), (5, 2), (6, 2)],
    "diehard": [(6, 0), (0, 1), (1, 1), (1, 2), (5, 2), (6, 2), (7, 2)],
    "blinker": [(0, 0), (1, 0), (2, 0)],
}
_RULE = re.compile(r"^B([0-8]*)/S([0-8]*)$")


def parse_rule(rule: str) -> tuple[frozenset, frozenset]:
    """(birth, survive) neighbour counts from a rule written B…/S…; ValueError for anything else."""
    m = _RULE.match(rule)
    if not m:
        raise ValueError(f"rule {rule!r} must look like B3/S23 (digits 0-8, each at most once)")
    b, s = m.group(1), m.group(2)
    if len(set(b)) != len(b) or len(set(s)) != len(s):
        raise ValueError(f"rule {rule!r}: a digit appears twice")
    return frozenset(int(c) for c in b), frozenset(int(c) for c in s)


def _check_delay(d: int):
    if d % 10:
        raise ValueError("delay must be a multiple of 10 ms (GIF stores hundredths of a second)")


def life_step(cells: bytearray, w: int, h: int, birth, survive, wrap: bool) -> bytearray:
    """One generation of a Life-like rule on a w×h board of 0/1 cells (row-major), on a torus if `wrap`."""
    out = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            n = 0
            for dy in (-1, 0, 1):
                yy = y + dy
                if wrap:
                    yy %= h
                elif not 0 <= yy < h:
                    continue
                row = yy * w
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    xx = x + dx
                    if wrap:
                        xx %= w
                    elif not 0 <= xx < w:
                        continue
                    n += cells[row + xx]
            alive = cells[y * w + x]
            out[y * w + x] = 1 if (n in survive if alive else n in birth) else 0
    return out


def life_seed(seed, w, h, p) -> bytearray:
    """The initial board: a seeded random soup in the central box, or a named pattern at the centre."""
    cells = bytearray(w * h)
    if p["pattern"] == "random":
        r = Rng(f"life:{seed}")
        bw, bh = max(1, int(w * p["box"])), max(1, int(h * p["box"]))
        x0, y0 = (w - bw) // 2, (h - bh) // 2
        for y in range(y0, y0 + bh):
            for x in range(x0, x0 + bw):
                cells[y * w + x] = 1 if r.random() < p["fill"] else 0
    else:
        pts = PATTERNS[p["pattern"]]
        pw, ph = max(x for x, _ in pts) + 1, max(y for _, y in pts) + 1
        x0, y0 = (w - pw) // 2, (h - ph) // 2
        for x, y in pts:
            cells[(y0 + y) * w + x0 + x] = 1
    return cells


def life(seed, pal, w, h, p) -> list:
    """Generator anim.life: `frames` frames, `every` generations apart, live cells coloured by age."""
    _check_delay(p["delay"])
    birth, survive = parse_rule(p["rule"])
    cells = life_seed(seed, w, h, p)
    age = [1 if c else 0 for c in cells]
    ramp = pal.ramp(p["ramp"])
    bg = pal.ramp(p["background"])[0] if p["background"] else None
    frames = []
    for k in range(p["frames"]):
        cv = Canvas(w, h, pal)
        n = len(ramp)
        for i, c in enumerate(cells):
            if c:
                a = min(n - 1, (age[i] - 1) // p["age_step"])
                cv.px[i // w][i % w] = ramp[n - 1 - a]          # newborn cells at the bright end, old ones darker
            else:
                cv.px[i // w][i % w] = bg
        frames.append((p["delay"], cv))
        if k == p["frames"] - 1:
            break
        for _ in range(p["every"]):
            cells = life_step(cells, w, h, birth, survive, p["wrap"])
            age = [a + 1 if c else 0 for a, c in zip(age, cells)]
    return frames


def _walls(w, h, p):
    wall = bytearray(w * h)
    if p["scene"] in ("double-slit", "single-slit"):
        x0 = w // 4
        cy = h / 2
        holes = [cy - p["separation"] / 2, cy + p["separation"] / 2] if p["scene"] == "double-slit" else [cy]
        for y in range(h):
            if any(abs(y + 0.5 - c) < p["opening"] / 2 for c in holes):
                continue
            for x in range(x0, x0 + 2):
                wall[y * w + x] = 1
    return wall


def wave(seed, pal, w, h, p) -> list:
    """Generator anim.wave: leapfrog steps of the 2-D wave equation with the chosen source, walls and sponge."""
    _check_delay(p["delay"])
    c2 = p["speed"] * p["speed"]
    omega = fm.tau / p["period"]
    wall = _walls(w, h, p)
    sponge = p["sponge"]
    damp = [1.0] * (w * h)
    for y in range(h):
        for x in range(w):
            d = min(x, y, w - 1 - x, h - 1 - y)
            if d < sponge and not (p["scene"] in ("double-slit", "single-slit") and x < 3):
                t = (sponge - d) / sponge
                damp[y * w + x] = 1.0 - 0.12 * t * t
    u = [0.0] * (w * h)
    prev = [0.0] * (w * h)
    ramp = pal.ramp(p["ramp"])
    ink = pal.ramp(p["wall_ramp"])[0]
    gain = p["contrast"]
    frames = []
    step = 0
    for k in range(p["frames"]):
        t = [min(1.0, max(0.0, 0.5 + 0.5 * v * gain)) for v in u]
        steps = len(ramp) - 1
        cv = Canvas(w, h, pal)
        for i, v in enumerate(t):
            cv.px[i // w][i % w] = ink if wall[i] else ramp[int(fm.floor(v * steps + 0.5))]
        frames.append((p["delay"], cv))
        if k == p["frames"] - 1:
            break
        for _ in range(p["every"]):
            s = fm.sin(omega * step)
            nxt = [0.0] * (w * h)
            for y in range(1, h - 1):
                row = y * w
                for x in range(1, w - 1):
                    i = row + x
                    if wall[i]:
                        continue
                    lap = (u[i - w] + u[i + w]) + (u[i - 1] + u[i + 1]) - 4.0 * u[i]
                    nxt[i] = (2.0 * u[i] - prev[i] + c2 * lap) * damp[i]
            if p["scene"] in ("double-slit", "single-slit"):
                for y in range(1, h - 1):
                    nxt[y * w + 2] = s                       # a plane wave enters from the left
            elif p["scene"] == "point":
                nxt[(h // 2) * w + w // 2] = s
            else:
                d = int(p["separation"] / 2)
                nxt[(h // 2 - d) * w + w // 3] = s
                nxt[(h // 2 + d) * w + w // 3] = s
            prev, u = u, nxt
            step += 1
    return frames


def _lorenz_f(x, y, z, s, r, b):
    return s * (y - x), x * (r - z) - y, x * y - b * z


def lorenz_path(n, dt, s, r, b, start):
    """n RK4 steps of the Lorenz system from `start`; returns the n + 1 points (x, y, z)."""
    x, y, z = start
    out = [(x, y, z)]
    for _ in range(n):
        k1 = _lorenz_f(x, y, z, s, r, b)
        k2 = _lorenz_f(x + 0.5 * dt * k1[0], y + 0.5 * dt * k1[1], z + 0.5 * dt * k1[2], s, r, b)
        k3 = _lorenz_f(x + 0.5 * dt * k2[0], y + 0.5 * dt * k2[1], z + 0.5 * dt * k2[2], s, r, b)
        k4 = _lorenz_f(x + dt * k3[0], y + dt * k3[1], z + dt * k3[2], s, r, b)
        x += dt / 6.0 * (k1[0] + 2.0 * k2[0] + 2.0 * k3[0] + k4[0])
        y += dt / 6.0 * (k1[1] + 2.0 * k2[1] + 2.0 * k3[1] + k4[1])
        z += dt / 6.0 * (k1[2] + 2.0 * k2[2] + 2.0 * k3[2] + k4[2])
        out.append((x, y, z))
    return out


def lorenz(seed, pal, w, h, p) -> list:
    """Generator anim.lorenz: the orbit after `warmup`, drawn as a trail of the last `trail` steps per frame."""
    _check_delay(p["delay"])
    per = p["steps_per_frame"]
    skip = p["warmup"]
    path = lorenz_path(skip + per * (p["frames"] - 1), p["dt"], p["sigma"], p["rho"], p["beta"],
                       tuple(p["start"]) + (p["start_z"],))[skip:]
    ax = {"xz": (0, 2), "xy": (0, 1), "yz": (1, 2)}[p["view"]]
    lo = {0: -25.0, 1: -30.0, 2: 0.0}
    hi = {0: 25.0, 1: 30.0, 2: 55.0}
    a, b = ax
    ramp = pal.ramp(p["ramp"])
    bg = pal.ramp(p["background"])[0] if p["background"] else None
    head = pal.ramp(p["head_ramp"])[0]
    trail = p["trail"]
    frames = []
    for k in range(p["frames"]):
        cv = Canvas(w, h, pal)
        if bg is not None:
            for row in cv.px:
                for i in range(w):
                    row[i] = bg
        end = k * per
        start = max(0, end - trail)
        prev = None
        for q in range(start, end + 1):
            pt = path[q]
            px = (pt[a] - lo[a]) / (hi[a] - lo[a]) * (w - 1)
            py = (1.0 - (pt[b] - lo[b]) / (hi[b] - lo[b])) * (h - 1)
            age = (end - q) / max(1, trail)
            c = ramp[len(ramp) - 1 - min(len(ramp) - 1, int(age * len(ramp)))]
            if prev is not None:
                cv.line(prev[0], prev[1], px, py, c)
            prev = (px, py)
        if prev is not None:
            cv.disc(prev[0], prev[1], 1, head)
        frames.append((p["delay"], cv))
    return frames


def diffuse(seed, pal, w, h, p, grid) -> list:
    """Generator anim.diffuse: FTCS steps of the heat equation on the resampled grid, colours on a fixed range."""
    _check_delay(p["delay"])
    z = F.sample(grid, w, h, "bilinear")
    lo, hi = F.extent([v for v in z if v == v], p["range"])
    a = p["alpha"]
    ramp = pal.ramp(p["ramp"])
    steps = len(ramp) - 1
    frames = []
    for k in range(p["frames"]):
        cv = Canvas(w, h, pal)
        for i, v in enumerate(F.unit(z, lo, hi)):
            cv.px[i // w][i % w] = None if v != v else ramp[int(fm.floor(v * steps + 0.5))]
        frames.append((p["delay"], cv))
        if k == p["frames"] - 1:
            break
        for _ in range(p["every"]):
            nz = z[:]
            for y in range(h):
                for x in range(w):
                    i = y * w + x
                    c = z[i]
                    if c != c:
                        continue
                    acc = 0.0
                    for xx, yy in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                        if 0 <= xx < w and 0 <= yy < h:
                            v = z[yy * w + xx]
                            if v == v:
                                acc += v - c          # a missing or outside neighbour exchanges nothing: reflecting
                    nz[i] = c + a * acc
            z = nz
    return frames


def frames(seed, pal, w, h, p, seq) -> list:
    """Each input grid resampled (nearest cell) to w×h and coloured along `ramp` over a fixed range for all frames."""
    _check_delay(p["delay"])
    allv = [v for g in seq.grids for v in g.finite()]
    lo, hi = F.extent(allv, p["range"])
    ramp = pal.ramp(p["ramp"])
    steps = len(ramp) - 1
    out = []
    for g in seq.grids:
        cv = Canvas(w, h, pal)
        for i, v in enumerate(F.unit(F.sample(g, w, h, "nearest"), lo, hi)):
            cv.px[i // w][i % w] = None if v != v else ramp[int(fm.floor(v * steps + 0.5))]
        out.append((p["delay"], cv))
    return out


CURVES = ("heart", "trefoil", "square", "lissajous")


def closed_curve(name: str, m: int) -> list[tuple[float, float]]:
    """m points of a closed curve at equal parameter steps, scaled to fit [−1, 1]² (y up)."""
    pts = []
    for j in range(m):
        t = fm.tau * j / m
        if name == "heart":
            s = fm.sin(t)
            x, y = 16 * s * s * s, 13 * fm.cos(t) - 5 * fm.cos(2 * t) - 2 * fm.cos(3 * t) - fm.cos(4 * t)
        elif name == "trefoil":
            x, y = fm.sin(t) + 2 * fm.sin(2 * t), fm.cos(t) - 2 * fm.cos(2 * t)
        elif name == "lissajous":
            x, y = fm.sin(3 * t), fm.sin(2 * t)
        else:                                           # square, walked at constant speed
            u = 4.0 * j / m
            side, f = int(u), u - int(u)
            x, y = ((-1 + 2 * f, -1.0), (1.0, -1 + 2 * f), (1 - 2 * f, 1.0), (-1.0, 1 - 2 * f))[side]
        pts.append((x, y))
    r = max(max(abs(x), abs(y)) for x, y in pts)
    return [(x / r, y / r) for x, y in pts]


def dft(points: list[tuple[float, float]]) -> list[tuple[int, float, float]]:
    """Discrete Fourier coefficients c_k = (1/M) Σ z_m e^(−2πi k m / M) of the points as complex numbers z = x + iy, for
    k = −M/2 … M/2 − 1, as (k, re, im). Then z_m = Σ_k c_k e^(2πi k m / M) exactly (inverse DFT)."""
    m = len(points)
    out = []
    for k in range(-(m // 2), m - m // 2):
        re = im = 0.0
        for j, (x, y) in enumerate(points):
            a = -fm.tau * ((k * j) % m) / m
            c, s = fm.cos(a), fm.sin(a)
            re += x * c - y * s
            im += x * s + y * c
        out.append((k, re / m, im / m))
    return out


def epicycle_position(coeffs, t: float, upto: int) -> list[tuple[float, float]]:
    """The chain of circle centres at time t ∈ [0, 1): partial sums of the first `upto` coefficients (in the given
    order), starting at 0; the last point is the drawing pen."""
    x = y = 0.0
    chain = [(0.0, 0.0)]
    for k, re, im in coeffs[:upto]:
        a = fm.tau * ((k * t) % 1.0)
        c, s = fm.cos(a), fm.sin(a)
        x += re * c - im * s
        y += re * s + im * c
        chain.append((x, y))
    return chain


def epicycles(seed, pal, w, h, p) -> list:
    """Generator anim.epicycles: the curve's DFT, its `terms` largest coefficients as rotating circles (largest first,
    ties to the lower frequency), the pen tracing the curve; the target curve in grey underneath."""
    _check_delay(p["delay"])
    pts = closed_curve(p["curve"], p["samples"])
    coeffs = sorted(dft(pts), key=lambda c: (-(c[1] * c[1] + c[2] * c[2]), abs(c[0]), c[0]))[:p["terms"]]
    cx, cy, sc = (w - 1) / 2, (h - 1) / 2, (min(w, h) - 4) / 2 / 1.25
    P = lambda q: (cx + q[0] * sc, cy - q[1] * sc)
    bg = pal.ramp(p["background"])[0] if p["background"] else None
    mid = lambda name: pal.ramp(name)[len(pal.ramp(name)) // 2]     # the middle tone: visible on a dark or light ground
    grey, ring = mid(p["curve_ramp"]), mid(p["circle_ramp"])
    pen = pal.ramp(p["ramp"])
    pen = pen[len(pen) // 2:]                                          # the trace fades from mid-tone to the bright end
    trace: list = []
    frames = []
    for f in range(p["frames"]):
        t = f / p["frames"]
        chain = epicycle_position(coeffs, t, len(coeffs))
        trace.append(chain[-1])
        cv = Canvas(w, h, pal)
        if bg is not None:
            for row in cv.px:
                for i in range(w):
                    row[i] = bg
        for a, b in zip(pts, pts[1:] + pts[:1]):
            (x0, y0), (x1, y1) = P(a), P(b)
            cv.line(x0, y0, x1, y1, grey)
        for (k, re, im), centre in zip(coeffs, chain):
            r = fm.sqrt(re * re + im * im) * sc
            if r >= 1.5:
                (x0, y0) = P(centre)
                cv.circle(int(fm.floor(x0 + 0.5)), int(fm.floor(y0 + 0.5)), int(fm.floor(r + 0.5)), ring)
        for a, b in zip(chain, chain[1:]):
            (x0, y0), (x1, y1) = P(a), P(b)
            cv.line(x0, y0, x1, y1, ring)
        for q, (a, b) in enumerate(zip(trace, trace[1:])):
            (x0, y0), (x1, y1) = P(a), P(b)
            cv.line(x0, y0, x1, y1, pen[min(len(pen) - 1, (q + 1) * len(pen) // len(trace))])
        frames.append((p["delay"], cv))
    return frames
