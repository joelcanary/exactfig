"""
Skies and fractals / cielos y fractales.

sky    a vertical gradient through one or more ramps, quantised by Floyd–Steinberg, Atkinson or Bayer, with stars placed by
       Poisson-disc sampling (never closer than `star_gap`) in the dark part.
julia  escape-time iterations of z ← z² + c mapped to a ramp with Bayer 8×8 between steps; the set itself in ink.
"""
from __future__ import annotations

from .. import fmath as fm
from ..pixel import pxmath as M
from ..pixel.canvas import Canvas
from ..pixel.dither import to_ramp_diffused, to_ramp_ordered
from ..rng import Rng


def sky(seed, pal, w, h, p) -> Canvas:
    """Generator forge.sky.gradient: a vertical gradient (gamma-shaped) quantised to the ramps, with Poisson-disc stars."""
    ramp = [i for name in p["ramps"] for i in pal.ramp(name)]
    if p["reverse"]:
        ramp = ramp[::-1]
    g = p["gamma"]
    field = [fm.pow((y + 0.5) / h, g) for y in range(h) for _ in range(w)]
    if p["dither"] == "bayer":
        q = to_ramp_ordered(field, w, h, ramp, 8)
    else:
        q = to_ramp_diffused(field, w, h, ramp, p["dither"])
    cv = Canvas(w, h, pal)
    for i, c in enumerate(q):
        cv.px[i // w][i % w] = c
    if p["star_gap"] > 0:
        star = pal.ramp("bone")[0]
        for (x, y) in M.poisson_disc(w, h * p["star_band"], p["star_gap"], Rng(f"sky:{seed}")):
            cv.set(int(x), int(y), star)
    return cv


def julia(seed, pal, w, h, p) -> Canvas:
    """Generator forge.fractal.julia: escape-time iterations of z ← z² + c, Bayer-dithered between ramp steps."""
    if p["c"] is not None:
        cx, cy = p["c"]
    else:
        cx, cy = M.JULIA_SEEDS[p["preset"] % len(M.JULIA_SEEDS)]
    ramp = pal.ramp(p["ramp"])
    ink = pal.ramp("ink")[0]
    it = p["max_iter"]
    zoom = p["zoom"]
    field, inside = [], []
    asp = w / h
    for y in range(h):
        for x in range(w):
            zx = ((x + 0.5) / w - 0.5) * 3.2 * asp / zoom
            zy = ((y + 0.5) / h - 0.5) * 3.2 / zoom
            n = M.julia(zx, zy, cx, cy, it)
            inside.append(n >= it)
            field.append(fm.sqrt(n / it))
    q = to_ramp_ordered(field, w, h, ramp, 8)
    cv = Canvas(w, h, pal)
    for i, c in enumerate(q):
        cv.px[i // w][i % w] = ink if inside[i] else c
    return cv
