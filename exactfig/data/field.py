"""
Scalar fields on the output raster / campos escalares sobre la rejilla de salida.

  sample      resample a Grid to w×h pixel centres: nearest, or bilinear over the finite neighbours only (a missing cell
              never leaks into its neighbours as a number)
  extent      the value range used for colour: given, or the finite minimum and maximum
  hillshade   illumination of a surface z(x, y) by a distant light, from Horn's 3×3 gradient (Horn 1981, the method of
              most GIS software): cos of the angle between the surface normal and the light
  contours    iso-lines by marching squares, with the saddle cases decided by the value at the cell centre (the
              asymptotic choice for bilinear cells is not needed at pixel scale); returns segments in pixel coordinates

All arithmetic is IEEE 754 basic operations plus exactfig.fmath, so results are the same bits on every platform.
NaN marks missing values throughout.
"""
from __future__ import annotations

import math

from .. import fmath as fm
from .io import Grid

NAN = math.nan


def sample(g: Grid, w: int, h: int, method: str = "bilinear") -> list[float]:
    """Row-major w×h values; pixel (i, j) samples the grid at its centre, the grid's cells being centred on integers."""
    out = [NAN] * (w * h)
    sx, sy = g.width / w, g.height / h
    vals = g.values
    for j in range(h):
        gy = (j + 0.5) * sy - 0.5
        for i in range(w):
            gx = (i + 0.5) * sx - 0.5
            if method == "nearest":
                x = min(g.width - 1, max(0, int(fm.floor(gx + 0.5))))
                y = min(g.height - 1, max(0, int(fm.floor(gy + 0.5))))
                out[j * w + i] = vals[y][x]
                continue
            x0, y0 = int(fm.floor(gx)), int(fm.floor(gy))
            fx, fy = gx - x0, gy - y0
            acc = wsum = 0.0
            for dy, wy in ((0, 1.0 - fy), (1, fy)):
                yy = min(g.height - 1, max(0, y0 + dy))
                for dx, wx in ((0, 1.0 - fx), (1, fx)):
                    xx = min(g.width - 1, max(0, x0 + dx))
                    v = vals[yy][xx]
                    wt = wx * wy
                    if v == v and wt > 0.0:
                        acc += v * wt
                        wsum += wt
            if wsum > 0.0:
                out[j * w + i] = acc / wsum
    return out


def extent(values, given=None) -> tuple[float, float]:
    """The colour range: `given` as [low, high], or the finite minimum and maximum; a constant field gets a range of 1."""
    if given is not None:
        lo, hi = float(given[0]), float(given[1])
    else:
        fin = [v for v in values if v == v]
        if not fin:
            raise ValueError("no finite values to colour")
        lo, hi = min(fin), max(fin)
    if not hi > lo:
        hi = lo + 1.0                              # a constant field: everything at the bottom of the ramp
    return lo, hi


def unit(values, lo: float, hi: float) -> list[float]:
    """Values mapped to [0, 1] over [lo, hi], clamped at both ends; NaN (no data) stays NaN."""
    span = hi - lo
    return [NAN if v != v else min(1.0, max(0.0, (v - lo) / span)) for v in values]


def hillshade(z: list[float], w: int, h: int, cell: float, azimuth_deg: float, altitude_deg: float,
              zfactor: float = 1.0) -> list[float]:
    """Shade in [0, 1] (0 = facing away, 1 = facing the light). Azimuth clockwise from north (up), altitude above the
    horizon; `cell` is the ground size of one pixel in the units of z. Edges reuse the nearest valid pixel."""
    az = fm.radians(360.0 - azimuth_deg + 90.0)    # to the mathematical angle, counter-clockwise from +x
    zen = fm.radians(90.0 - altitude_deg)
    cz, sz = fm.cos(zen), fm.sin(zen)
    out = [NAN] * (w * h)

    def at(x, y, centre):
        x = min(w - 1, max(0, x)); y = min(h - 1, max(0, y))
        v = z[y * w + x]
        return centre if v != v else v

    for y in range(h):
        for x in range(w):
            c = z[y * w + x]
            if c != c:
                continue
            a, b, cc = at(x - 1, y - 1, c), at(x, y - 1, c), at(x + 1, y - 1, c)
            d, f = at(x - 1, y, c), at(x + 1, y, c)
            g, hh, i = at(x - 1, y + 1, c), at(x, y + 1, c), at(x + 1, y + 1, c)
            dzdx = ((cc + 2 * f + i) - (a + 2 * d + g)) / (8.0 * cell) * zfactor
            dzdy = ((g + 2 * hh + i) - (a + 2 * b + cc)) / (8.0 * cell) * zfactor   # rows grow downwards = south
            slope = fm.atan(fm.sqrt(dzdx * dzdx + dzdy * dzdy))
            aspect = fm.atan2(dzdy, -dzdx) if (dzdx or dzdy) else 0.0
            s = cz * fm.cos(slope) + sz * fm.sin(slope) * fm.cos(az - aspect)
            out[y * w + x] = min(1.0, max(0.0, s))
    return out


# Marching squares: corners numbered 1 (top-left), 2 (top-right), 4 (bottom-right), 8 (bottom-left), bit set when the corner
# is at or above the level; edges 0 top, 1 right, 2 bottom, 3 left.
_CASES = {1: ((3, 0),), 2: ((0, 1),), 3: ((3, 1),), 4: ((1, 2),), 6: ((0, 2),), 7: ((3, 2),), 8: ((2, 3),), 9: ((2, 0),),
          11: ((2, 1),), 12: ((1, 3),), 13: ((1, 0),), 14: ((0, 3),)}
# saddles (two opposite corners above): if the centre is above too, the two corners below are cut off, else the two above
_CUT_TR_BL = ((0, 1), (2, 3))
_CUT_TL_BR = ((3, 0), (1, 2))


def contours(z: list[float], w: int, h: int, level: float) -> list[tuple[float, float, float, float]]:
    """Segments (x0, y0, x1, y1) of the iso-line z = level, in pixel coordinates (pixel centres at i + 0.5)."""
    segs = []
    for y in range(h - 1):
        for x in range(w - 1):
            tl, tr = z[y * w + x], z[y * w + x + 1]
            bl, br = z[(y + 1) * w + x], z[(y + 1) * w + x + 1]
            if tl != tl or tr != tr or bl != bl or br != br:
                continue
            k = (tl >= level) | (tr >= level) << 1 | (br >= level) << 2 | (bl >= level) << 3
            if k in (0, 15):
                continue

            def cross(e):
                if e == 0: a, b, p, q = tl, tr, (x, y), (x + 1, y)
                elif e == 1: a, b, p, q = tr, br, (x + 1, y), (x + 1, y + 1)
                elif e == 2: a, b, p, q = bl, br, (x, y + 1), (x + 1, y + 1)
                else: a, b, p, q = tl, bl, (x, y), (x, y + 1)
                t = (level - a) / (b - a)
                return p[0] + (q[0] - p[0]) * t + 0.5, p[1] + (q[1] - p[1]) * t + 0.5

            if k in (5, 10):                     # 5: tl and br above; 10: tr and bl above
                centre_above = (tl + tr + bl + br) * 0.25 >= level
                pairs = _CUT_TR_BL if centre_above == (k == 5) else _CUT_TL_BR
            else:
                pairs = _CASES[k]
            for e0, e1 in pairs:
                segs.append((*cross(e0), *cross(e1)))
    return segs


def levels(lo: float, hi: float, n: int = 0, interval: float = 0.0) -> list[float]:
    """Contour levels strictly inside (lo, hi): every `interval` from a multiple of it, or `n` evenly spaced."""
    if interval > 0.0:
        k = int(fm.floor(lo / interval)) + 1
        out = []
        while k * interval < hi and len(out) < 1000:
            out.append(k * interval)
            k += 1
        return out
    return [lo + (hi - lo) * (i + 1) / (n + 1) for i in range(n)]
