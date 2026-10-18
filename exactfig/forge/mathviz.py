"""
Pictures of classical mathematics, each a direct computation (no data, no randomness):

domain    complex analysis: the phase portrait of f(z) (colour = arg f(z) on a cyclic ramp) with iso-lines of the modulus at
          |f| = 2^k, the "enhanced phase portrait" of E. Wegert, *Visual Complex Functions* (2012). Zeros and poles show
          as points where every colour meets; their order is how many times the colours turn around them.
logistic  dynamical systems: the bifurcation diagram of x ← r·x·(1 − x). For each column r, the orbit runs `warmup`
          steps and then `samples` steps are counted per pixel; the colour is the log of the visit count, so the
          period-doubling cascade and the windows of periodicity (period 3 near r = 3.83) are visible.
ulam      number theory: the integers 1, 2, 3, … on a square spiral (1 at the centre, then right, up, left, down),
          primes marked (S. Ulam, 1963) or every integer coloured by its residue mod m.
modmult   modular arithmetic: n points on a circle, the chord from j to k·j mod n for each j (the "times table" circle);
          k = 2 draws the cardioid, k = 3 the nephroid, and a non-integer k is allowed.

All arithmetic is IEEE 754 basic operations plus exactfig.fmath; integers stay exact.
"""
from __future__ import annotations

import math

from .. import fmath as fm
from ..data import field as F
from ..pixel.canvas import Canvas

# ------------------------------------------------------------------------------------------------ complex functions


def _mul(a, b):
    return (a[0] * b[0] - a[1] * b[1], a[0] * b[1] + a[1] * b[0])


def _div(a, b):
    d = b[0] * b[0] + b[1] * b[1]
    if d == 0.0:
        return (math.inf, 0.0)
    return ((a[0] * b[0] + a[1] * b[1]) / d, (a[1] * b[0] - a[0] * b[1]) / d)


def _exp(a):
    m = fm.exp(a[0])
    return (m * fm.cos(a[1]), m * fm.sin(a[1]))


def _sin(a):
    # sin(x + iy) = sin x cosh y + i cos x sinh y
    ey, emy = fm.exp(a[1]), fm.exp(-a[1])
    return (fm.sin(a[0]) * (ey + emy) / 2, fm.cos(a[0]) * (ey - emy) / 2)


def _wegert(z):
    z2 = _mul(z, z)
    t = _mul((z[0] - 2.0, z[1] - 1.0), (z[0] - 2.0, z[1] - 1.0))
    return _div(_mul((z2[0] - 1.0, z2[1]), t), (z2[0] + 2.0, z2[1] + 2.0))


FUNCTIONS = {
    "z": lambda z: z,
    "z^3-1": lambda z: (_mul(_mul(z, z), z)[0] - 1.0, _mul(_mul(z, z), z)[1]),
    "(z^2-1)(z-2-i)^2/(z^2+2+2i)": _wegert,
    "sin(z)": _sin,
    "exp(1/z)": lambda z: _exp(_div((1.0, 0.0), z)) if (z[0] or z[1]) else (math.nan, math.nan),
    "z^5+z^2+1": lambda z: (lambda z2: (lambda z5: (z5[0] + z2[0] + 1.0, z5[1] + z2[1]))(_mul(_mul(z2, z2), z)))(_mul(z, z)),
}


def _window(w, h, centre, span):
    """Complex coordinate of pixel (i, j): `span` is the width of the view; y grows upwards."""
    sx = span / w
    x0 = centre[0] - span / 2
    y1 = centre[1] + sx * h / 2
    return lambda i, j: (x0 + (i + 0.5) * sx, y1 - (j + 0.5) * sx)


def domain(seed, pal, w, h, p) -> Canvas:
    """Generator math.domain: phase of f on the cyclic ramp, iso-lines of log2|f| at every integer."""
    f = FUNCTIONS[p["function"]]
    at = _window(w, h, p["centre"], p["span"])
    ramp = pal.ramp(p["ramp"])
    n = len(ramp)
    cv = Canvas(w, h, pal)
    logmod = [math.nan] * (w * h)
    for j in range(h):
        for i in range(w):
            fz = f(at(i, j))
            if not (math.isfinite(fz[0]) and math.isfinite(fz[1])):
                continue
            mod2 = fz[0] * fz[0] + fz[1] * fz[1]
            if mod2 == 0.0:
                cv.px[j][i] = ramp[0]
                continue
            t = fm.atan2(fz[1], fz[0]) / fm.tau % 1.0          # phase in turns, [0, 1)
            cv.px[j][i] = ramp[min(n - 1, int(fm.floor(t * n)))]
            logmod[j * w + i] = 0.5 * fm.log2(mod2)
    if p["modulus_lines"]:
        ink = pal.ramp(p["line_ramp"])[0]
        fin = [v for v in logmod if v == v]
        if fin:
            lo, hi = max(-30, int(fm.floor(min(fin)))), min(30, int(fm.floor(max(fin))) + 1)
            for level in range(lo, hi + 1):
                for x0, y0, x1, y1 in F.contours(logmod, w, h, float(level)):
                    cv.line(fm.floor(x0), fm.floor(y0), fm.floor(x1), fm.floor(y1), ink)
    return cv


# ------------------------------------------------------------------------------------------------ logistic map

def logistic_orbit(r: float, x0: float, warmup: int, n: int) -> list[float]:
    """`n` points of the orbit of x0 under x ← r·x·(1 − x), after `warmup` discarded steps."""
    x = x0
    for _ in range(warmup):
        x = r * x * (1.0 - x)
    out = []
    for _ in range(n):
        x = r * x * (1.0 - x)
        out.append(x)
    return out


def logistic(seed, pal, w, h, p) -> Canvas:
    """Generator math.logistic: per column r, visit counts of the orbit per pixel, coloured by log count."""
    r0, r1 = p["r"]
    x0, x1 = p["x"]
    counts = [0] * (w * h)
    for i in range(w):
        r = r0 + (i + 0.5) / w * (r1 - r0)
        for x in logistic_orbit(r, p["x0"], p["warmup"], p["samples"]):
            if x0 <= x <= x1:
                j = min(h - 1, int(fm.floor((x1 - x) / (x1 - x0) * h)))
                counts[j * w + i] += 1
    top = max(counts) or 1
    ramp = pal.ramp(p["ramp"])
    bg = pal.ramp(p["background"])[0] if p["background"] else None
    steps = len(ramp) - 1
    norm = fm.log(1.0 + top)
    cv = Canvas(w, h, pal)
    for k, c in enumerate(counts):
        cv.px[k // w][k % w] = bg if c == 0 else ramp[min(steps, int(fm.floor(fm.log(1.0 + c) / norm * steps + 0.5)))]
    return cv


# ------------------------------------------------------------------------------------------------ Ulam spiral

def ulam_positions(n: int) -> list[tuple[int, int]]:
    """Positions of 1..n on the square spiral (1 at (0, 0), 2 at (1, 0), then up, left, down…; y up)."""
    out = [(0, 0)]
    x = y = 0
    step, d = 1, 0
    dirs = ((1, 0), (0, 1), (-1, 0), (0, -1))
    while len(out) < n:
        for _ in range(2):
            dx, dy = dirs[d % 4]
            for _ in range(step):
                if len(out) >= n:
                    break
                x += dx
                y += dy
                out.append((x, y))
            d += 1
        step += 1
    return out


def primes_upto(n: int) -> bytearray:
    """Sieve of Eratosthenes: a bytearray whose entry k is 1 exactly when k ≤ n is prime."""
    sieve = bytearray([1]) * (n + 1)
    sieve[0:2] = b"\0\0"
    for q in range(2, math.isqrt(n) + 1):
        if sieve[q]:
            sieve[q * q::q] = bytearray(len(range(q * q, n + 1, q)))
    return sieve


def ulam(seed, pal, w, h, p) -> Canvas:
    """Generator math.ulam: 1..w·h on the square spiral centred on the canvas; primes or residues mod m."""
    n = w * h
    pos = ulam_positions(n)
    cx, cy = (w - 1) // 2, h // 2
    cv = Canvas(w, h, pal)
    bg = pal.ramp(p["background"])[0] if p["background"] else None
    for row in cv.px:
        for i in range(w):
            row[i] = bg
    ramp = pal.ramp(p["ramp"])
    sieve = primes_upto(n) if p["mode"] == "primes" else None
    for k, (x, y) in enumerate(pos, start=1):
        i, j = cx + x, cy - y
        if not (0 <= i < w and 0 <= j < h):
            continue
        if sieve is not None:
            if sieve[k]:
                cv.px[j][i] = ramp[-1]
        else:
            cv.px[j][i] = ramp[(k % p["modulus"]) * len(ramp) // p["modulus"]]
    return cv


# ------------------------------------------------------------------------------------------------ times-table circle

def modmult_chords(n: int, k: float) -> list[tuple[float, float]]:
    """The chord from point j to point k·j (mod n), as angles in turns, j = 0..n−1 (point 0 on the left)."""
    return [(j / n, (k * j % n) / n) for j in range(n)]


def modmult(seed, pal, w, h, p) -> Canvas:
    """Generator math.modmult: the n chords j → k·j mod n, coloured by j along the ramp."""
    cv = Canvas(w, h, pal)
    bg = pal.ramp(p["background"])[0] if p["background"] else None
    for row in cv.px:
        for i in range(w):
            row[i] = bg
    cx, cy = (w - 1) / 2, (h - 1) / 2
    rad = (min(w, h) - 3) / 2
    ramp = pal.ramp(p["ramp"])
    n = p["n"]

    def pt(turn):
        a = fm.pi + fm.tau * turn                         # 0 on the left, counter-clockwise on screen
        return cx + rad * fm.cos(a), cy - rad * fm.sin(a)

    for j, (a, b) in enumerate(modmult_chords(n, p["k"])):
        (x0, y0), (x1, y1) = pt(a), pt(b)
        cv.line(x0, y0, x1, y1, ramp[j * len(ramp) // n])
    if p["circle_ramp"]:
        cv.circle(int(fm.floor(cx + 0.5)), int(fm.floor(cy + 0.5)), int(fm.floor(rad + 0.5)), pal.ramp(p["circle_ramp"])[0])
    return cv


# ------------------------------------------------------------------------------------------------ Fourier series

def fourier_partial(wave: str, n: int, x: float) -> float:
    """The n-term Fourier partial sum at x of a 2π-periodic wave of amplitude 1:
    square    (4/π) Σ_{k=1..n} sin((2k−1)x) / (2k−1)
    sawtooth  (2/π) Σ_{k=1..n} (−1)^(k+1) sin(kx) / k            (the wave x/π on (−π, π))
    triangle  (8/π²) Σ_{k=0..n−1} (−1)^k sin((2k+1)x) / (2k+1)²"""
    s = 0.0
    if wave == "square":
        for k in range(1, n + 1):
            m = 2 * k - 1
            s += fm.sin(m * x) / m
        return 4.0 / fm.pi * s
    if wave == "sawtooth":
        for k in range(1, n + 1):
            s += (1.0 if k % 2 else -1.0) * fm.sin(k * x) / k
        return 2.0 / fm.pi * s
    for k in range(n):
        m = 2 * k + 1
        s += (1.0 if k % 2 == 0 else -1.0) * fm.sin(m * x) / (m * m)
    return 8.0 / (fm.pi * fm.pi) * s


def fourier_target(wave: str, x: float) -> float:
    """The wave itself on (−π, π]."""
    if wave == "square":
        return 0.0 if x == 0.0 or abs(x) == fm.pi else (1.0 if x > 0 else -1.0)
    if wave == "sawtooth":
        return x / fm.pi
    return 2.0 / fm.pi * (fm.pi / 2 - abs(abs(x) - fm.pi / 2)) * (1.0 if x >= 0 else -1.0) if abs(x) <= fm.pi else 0.0


def fourier(seed, pal, w, h, p) -> Canvas:
    """Generator math.fourier: the wave in grey and its partial sums for each order in `orders`, x from −π to π, y from
    −1.4 to 1.4, with the axes. The overshoot next to each jump of the square wave and the sawtooth does not shrink as
    the order grows (Gibbs phenomenon): it tends to about 9 % of the jump."""
    orders = [int(t) for t in p["orders"].split(",")]
    if not orders or any(not 1 <= n <= 2000 for n in orders):
        raise ValueError("orders: comma-separated term counts, each 1..2000")
    cv = Canvas(w, h, pal)
    bg = pal.ramp(p["background"])[0] if p["background"] else None
    for row in cv.px:
        for i in range(w):
            row[i] = bg
    axis_ramp = pal.ramp(p["axis_ramp"])
    axis = axis_ramp[len(axis_ramp) // 2]                              # mid-tone: visible on a dark or light ground
    X = lambda x: (x + fm.pi) / (2 * fm.pi) * (w - 1)
    Y = lambda y: (1.4 - y) / 2.8 * (h - 1)
    cv.line(0, Y(0.0), w - 1, Y(0.0), axis)
    cv.line(X(0.0), 0, X(0.0), h - 1, axis)
    for yy in (-1.0, 1.0):
        for i in range(0, w, 4):
            cv.set(i, Y(yy), axis)
    xs = [-fm.pi + 2 * fm.pi * i / (w - 1) for i in range(w)]
    prev = None
    for x in xs:
        pt = (X(x), Y(fourier_target(p["wave"], x)))
        if prev is not None and abs(pt[1] - prev[1]) < h / 4:
            cv.line(prev[0], prev[1], pt[0], pt[1], axis)
        prev = pt
    ramp = pal.ramp(p["ramp"])
    for k, n in enumerate(orders):
        c = ramp[min(len(ramp) - 1, (k + 1) * (len(ramp) - 1) // len(orders))]
        prev = None
        for x in xs:
            pt = (X(x), Y(fourier_partial(p["wave"], n, x)))
            if prev is not None:
                cv.line(prev[0], prev[1], pt[0], pt[1], c)
            prev = pt
    return cv
