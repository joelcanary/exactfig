"""
Data → picture / de los datos a la imagen.

field    a gridded field (CSV, PGM, NPY or JSON) resampled to the output size and drawn as
           value   colour by value along a ramp (quantised to the palette, optionally dithered)
           shade   hill-shading of the field as a surface (Horn's gradient, light from `azimuth`, `altitude`)
           relief  colour by value, each pixel moved up or down its ramp by the shading (hypsometric tint + hill-shade)
         with optional iso-lines (marching squares) every `interval`, or `contours` evenly spaced.
scatter  scattered samples (x, y, value) reconstructed on the raster, by Delaunay piecewise-linear interpolation (`linear`)
         or nearest sample (`nearest`, the Voronoi cells), then drawn like a field, with the samples marked if asked.

Pixels with no value (missing data, or outside the convex hull of the samples) stay transparent unless `nodata_ramp` is
set. The colour range is the data's finite min..max unless `range` is given (values outside it are clamped to the ends).
"""
from __future__ import annotations

from .. import fmath as fm
from ..data import field as F
from ..data import scatter as S
from ..pixel.canvas import Canvas
from ..pixel import convert as C
from ..pixel.dither import rgb_diffused, rgb_ordered, to_ramp_diffused, to_ramp_ordered


def _quantise(t: list[float], w: int, h: int, ramp: list[int], dither: str) -> list[int]:
    filled = [0.0 if v != v else v for v in t]        # missing pixels are masked afterwards
    if dither == "bayer":
        return to_ramp_ordered(filled, w, h, ramp, 8)
    if dither in ("floyd", "atkinson"):
        return to_ramp_diffused(filled, w, h, ramp, dither)
    steps = len(ramp) - 1
    return [ramp[int(fm.floor(v * steps + 0.5))] for v in filled]


def _paint(cv: Canvas, z: list[float], lo: float, hi: float, pal, p, cell: float):
    w, h = cv.w, cv.h
    ramp = pal.ramp(p["ramp"])
    if p["mode"] == "value":
        idx = _quantise(F.unit(z, lo, hi), w, h, ramp, p["dither"])
    else:
        shade = F.hillshade(z, w, h, cell, p["azimuth"], p["altitude"], p["exaggeration"])
        if p["mode"] == "shade":
            idx = _quantise(shade, w, h, ramp, p["dither"])
        else:
            base = _quantise(F.unit(z, lo, hi), w, h, list(range(len(ramp))), p["dither"])
            idx = []
            for k, s in zip(base, shade):
                if s != s:
                    idx.append(ramp[k]); continue
                shift = int(fm.floor((s - 0.5) * 2.0 * p["relief"] + 0.5))
                idx.append(ramp[min(len(ramp) - 1, max(0, k + shift))])
    nodata = pal.ramp(p["nodata_ramp"])[0] if p["nodata_ramp"] else None
    for i, v in enumerate(z):
        cv.px[i // w][i % w] = nodata if v != v else idx[i]
    if p["contours"] or p["interval"]:
        ink = pal.ramp(p["contour_ramp"])[0]
        for level in F.levels(lo, hi, p["contours"], p["interval"]):
            for x0, y0, x1, y1 in F.contours(z, w, h, level):
                cv.line(fm.floor(x0), fm.floor(y0), fm.floor(x1), fm.floor(y1), ink)


def field(seed, pal, w, h, p, grid) -> Canvas:
    """Generator data.field: resample the grid to w×h, colour it (value, shade or relief) and add the iso-lines."""
    z = F.sample(grid, w, h, p["resample"])
    lo, hi = F.extent(list(grid.finite()), p["range"])
    cv = Canvas(w, h, pal)
    _paint(cv, z, lo, hi, pal, p, p["cell"] * grid.width / w)
    return cv


def scatter(seed, pal, w, h, p, pts) -> Canvas:
    """Generator data.scatter: reconstruct the samples on w×h pixels over their bounding box, colour as data.field,
    and mark the sample positions if asked."""
    box = S.bbox(pts.xs, pts.ys)
    if p["method"] == "linear":
        z = S.linear(pts.xs, pts.ys, pts.vs, w, h, box)
    else:
        z = S.nearest(pts.xs, pts.ys, pts.vs, w, h, box)
    lo, hi = F.extent(pts.vs, p["range"])
    cv = Canvas(w, h, pal)
    _paint(cv, z, lo, hi, pal, p, p["cell"] * (box[1] - box[0]) / w)
    if p["points"] != "none":
        mark = pal.ramp(p["point_ramp"])[0]
        x0, x1, y0, y1 = box
        for x, y in zip(pts.xs, pts.ys):
            i = min(w - 1, int(fm.floor((x - x0) / (x1 - x0) * w)))
            j = min(h - 1, int(fm.floor((y1 - y) / (y1 - y0) * h)))
            cv.set(i, j, mark)
            if p["points"] == "cross":
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    cv.set(i + dx, j + dy, mark)
    return cv


def image(seed, pal, w, h, p, img) -> Canvas:
    """Generator data.image: a true-colour picture resampled to w×h (nearest, or area-weighted in linear light), each
    pixel mapped to the nearest palette colour of `ramp` in OKLab (directly, after a Bayer offset, or with Floyd–Steinberg
    error diffusion), and, if asked, a Sobel outline where OKLab lightness changes by more than `edge_threshold`."""
    px = C.resample(img.width, img.height, img.rgba, w, h, p["resample"])
    among = pal.ramp(p["ramp"])
    rgb = [c if c is not None else (0.0, 0.0, 0.0) for c in px]
    if p["dither"] == "bayer":
        idx = rgb_ordered(rgb, w, h, pal, p["spread"], 8, among)
    elif p["dither"] == "floyd":
        idx = rgb_diffused(rgb, w, h, pal, among)
    else:
        idx = [pal.nearest(tuple(fm.floor(v + 0.5) for v in c), among) for c in rgb]
    cv = Canvas(w, h, pal)
    for i, c in enumerate(px):
        cv.px[i // w][i % w] = None if c is None else idx[i]
    if p["edges"]:
        ink = pal.ramp(p["edge_ramp"])[0]
        grad = C.sobel(C.lightness(px), w, h)
        for i, g in enumerate(grad):
            if g == g and g > p["edge_threshold"]:
                cv.px[i // w][i % w] = ink
    return cv
