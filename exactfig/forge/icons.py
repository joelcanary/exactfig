"""
Gem icons / gemas: a signed distance field gives the silhouette, angular sectors give the facets.

Inside the SDF (d < 0) each pixel belongs to a facet (sector of angle around the centre) or to the table (the inner shape at
`table` of the size). A facet's tone is the cosine between its normal and the light, quantised to the ramp; one sparkle in the
lit corner; outline in ink.
La silueta sale de una función de distancia con signo; las facetas, de sectores angulares sombreados por el coseno con la luz.
"""
from __future__ import annotations

import math

from .. import fmath as fm
from ..pixel import pxmath as M
from ..pixel.canvas import Canvas


def _sdf(shape: str, x: float, y: float, r: float) -> float:
    if shape == "round":
        return M.sd_circle(x, y, r)
    if shape == "square":
        return M.sd_box(x, y, r * 0.82, r * 0.82)
    if shape == "diamond":
        return (abs(x) + abs(y)) / math.sqrt(2) - r * 0.74
    if shape == "hex":
        q = (abs(x), abs(y))
        return max(q[0] * 0.866025 + q[1] * 0.5, q[1]) - r * 0.86
    if shape == "drop":
        return min(M.sd_circle(x, y - r * 0.25, r * 0.72), max(abs(x) * 1.2 + (y + r * 0.1) * 0.55 - r * 0.55, -(y + r)))
    raise ValueError(shape)


def gem(seed, pal, w, h, p) -> Canvas:
    """Generator forge.icon.gem: a signed-distance shape cut into angular facets lit from `light_deg`."""
    ramp = pal.ramp(p["ramp"])
    ink, spark = pal.ramp("ink")[0], pal.ramp("bone")[0]
    shape, facets, table = p["shape"], p["facets"], p["table"]
    cx, cy = (w - 1) / 2, (h - 1) / 2
    r = min(w, h) / 2 - 1.5
    la = fm.radians(p["light_deg"])
    cv = Canvas(w, h, pal)
    n = len(ramp)
    for y in range(h):
        for x in range(w):
            dx, dy = x - cx, y - cy
            if _sdf(shape, dx, dy, r) >= 0:
                continue
            if _sdf(shape, dx / table, dy / table, r) < 0:
                lit = 0.62 + 0.25 * (-(dx + dy) / (r * 2))           # la mesa: plana y clara
            else:
                sector = 2 * math.pi / facets
                k = math.floor((fm.atan2(dy, dx) + math.pi) / sector)
                mid = -math.pi + (k + 0.5) * sector
                lit = 0.5 + 0.5 * fm.cos(mid - la)
            cv.px[y][x] = ramp[max(0, min(n - 1, int(lit * n)))]
    # destello: el píxel interior más cercano a la luz, en cruz
    sx = int(round(cx + fm.cos(la) * r * 0.45)); sy = int(round(cy + fm.sin(la) * r * 0.45))
    if cv.get(sx, sy) is not None:
        for ddx, ddy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)) if w >= 16 else ((0, 0),):
            if cv.get(sx + ddx, sy + ddy) is not None:
                cv.set(sx + ddx, sy + ddy, spark)
    cv.outline(ink)
    return cv
