"""
Image conversion: from a true-colour picture to palette-locked pixels / de una imagen en color real a píxeles de paleta.

  resample     to the target size: `nearest` (the source pixel under each target centre) or `area` (the exact
               area-weighted mean of the source pixels each target pixel covers, computed in LINEAR light: averaging sRGB
               values directly darkens every edge between two colours)
  median_cut   a k-colour palette by Heckbert's median cut (1982): repeatedly split the box of colours with the widest
               range along that channel, at its median, then take each box's mean; deterministic
  kmeans       a k-colour palette by Lloyd's k-means in OKLab, started from the median-cut palette (no random start, so
               the same image always gives the same palette), until no colour changes cluster or `iterations` is reached
  sobel        the gradient magnitude of OKLab lightness by the 3 × 3 Sobel operator (edges for an outline layer)

Everything is pure: the image comes in as RGBA8 bytes and goes out as numbers. The quantisation itself (nearest palette
colour in OKLab, Bayer or Floyd–Steinberg) is in pixel/dither.py.
"""
from __future__ import annotations

from .. import fmath as fm
from . import palette as P

_LUT_LIN = [P._lin(v) for v in range(256)]          # sRGB byte → linear light, computed once with fmath


def _lin2srgb(c: float) -> float:
    return P._srgb(c)


def resample(w0: int, h0: int, rgba: bytes, w: int, h: int, method: str = "area") -> list:
    """w×h list of (r, g, b) in 0..255 floats, or None where the result is transparent (alpha below one half)."""
    out: list = []
    if method == "nearest":
        for j in range(h):
            y = min(h0 - 1, int((j + 0.5) * h0 / h))
            for i in range(w):
                x = min(w0 - 1, int((i + 0.5) * w0 / w))
                q = (y * w0 + x) * 4
                out.append(None if rgba[q + 3] < 128 else (float(rgba[q]), float(rgba[q + 1]), float(rgba[q + 2])))
        return out
    sx, sy = w0 / w, h0 / h
    for j in range(h):
        ya, yb = j * sy, (j + 1) * sy
        for i in range(w):
            xa, xb = i * sx, (i + 1) * sx
            acc = [0.0, 0.0, 0.0]
            wa = area = 0.0
            for y in range(int(fm.floor(ya)), min(h0, int(fm.floor(yb - 1e-12)) + 1)):
                cy = min(yb, y + 1) - max(ya, y)
                for x in range(int(fm.floor(xa)), min(w0, int(fm.floor(xb - 1e-12)) + 1)):
                    cover = (min(xb, x + 1) - max(xa, x)) * cy
                    q = (y * w0 + x) * 4
                    a = rgba[q + 3] / 255.0
                    area += cover
                    wa += cover * a
                    for k in range(3):
                        acc[k] += cover * a * _LUT_LIN[rgba[q + k]]     # premultiplied, linear light
            if wa < 0.5 * area or wa == 0.0:
                out.append(None)
            else:
                out.append(tuple(_lin2srgb(acc[k] / wa) for k in range(3)))
    return out


def _channel_range(box, c):
    vals = [p[c] for p in box]
    return max(vals) - min(vals)


def median_cut(colours: list, k: int) -> list[tuple[int, int, int]]:
    """k (or fewer, if there are fewer distinct colours) RGB colours. Ties are broken by channel order, then by the
    colours themselves, so the result depends on the set of colours only."""
    pts = sorted({(int(fm.floor(c[0] + 0.5)), int(fm.floor(c[1] + 0.5)), int(fm.floor(c[2] + 0.5))) for c in colours if c})
    if not pts:
        raise ValueError("the image has no opaque pixel")
    boxes = [pts]
    while len(boxes) < k:
        best = max(range(len(boxes)), key=lambda b: (max(_channel_range(boxes[b], c) for c in range(3)), -b))
        box = boxes[best]
        if len(box) < 2:
            break
        c = max(range(3), key=lambda ch: (_channel_range(box, ch), -ch))
        box = sorted(box, key=lambda p: (p[c], p))
        mid = len(box) // 2
        boxes[best:best + 1] = [box[:mid], box[mid:]]
    return [tuple(int(fm.floor(sum(p[c] for p in b) / len(b) + 0.5)) for c in range(3)) for b in boxes]


def kmeans(colours: list, k: int, iterations: int = 30) -> list[tuple[int, int, int]]:
    """k RGB colours minimising the summed squared OKLab distance of the image's colours to their nearest centre (a local
    minimum: Lloyd's iterations from the median-cut palette). Every pixel counts, so large areas weigh more."""
    pts = [c for c in colours if c]
    labs = [P.oklab(c) for c in pts]
    centres = [P.oklab(c) for c in median_cut(pts, k)]
    assign = [-1] * len(labs)
    for _ in range(iterations):
        changed = 0
        for i, lab in enumerate(labs):
            best = min(range(len(centres)), key=lambda c: (fm.dist2(lab, centres[c]), c))
            if best != assign[i]:
                assign[i] = best
                changed += 1
        sums = [[0.0, 0.0, 0.0, 0] for _ in centres]
        for lab, a in zip(labs, assign):
            s = sums[a]
            s[0] += lab[0]; s[1] += lab[1]; s[2] += lab[2]; s[3] += 1
        centres = [(s[0] / s[3], s[1] / s[3], s[2] / s[3]) if s[3] else centres[c] for c, s in enumerate(sums)]
        if not changed:
            break
    return [tuple(int(fm.floor(v + 0.5)) for v in P.oklab_to_rgb(c)) for c in centres]


def lightness(pixels: list) -> list[float]:
    """OKLab L of each pixel (NaN where transparent)."""
    return [float("nan") if p is None else P.oklab(p)[0] for p in pixels]


def sobel(field: list[float], w: int, h: int) -> list[float]:
    """|∇f| by the Sobel operator, edges reusing the nearest pixel; NaN where the centre is NaN (missing neighbours count
    as the centre)."""
    out = [float("nan")] * (w * h)

    def at(x, y, c):
        x = min(w - 1, max(0, x)); y = min(h - 1, max(0, y))
        v = field[y * w + x]
        return c if v != v else v

    for y in range(h):
        for x in range(w):
            c = field[y * w + x]
            if c != c:
                continue
            a, b, d = at(x - 1, y - 1, c), at(x, y - 1, c), at(x + 1, y - 1, c)
            e, f = at(x - 1, y, c), at(x + 1, y, c)
            g, hh, i = at(x - 1, y + 1, c), at(x, y + 1, c), at(x + 1, y + 1, c)
            gx = (d + 2 * f + i) - (a + 2 * e + g)
            gy = (g + 2 * hh + i) - (a + 2 * b + d)
            out[y * w + x] = fm.sqrt(gx * gx + gy * gy)
    return out


def palette_object(name: str, rgb: list) -> dict:
    """A recipe palette {name, colors, ramps} with the colours sorted by OKLab lightness (dark to light): ramp `all` is then
    a usable dark-to-light ramp, and `ink` / `paper` are its ends."""
    order = sorted(set(rgb), key=lambda c: (P.oklab(c)[0], c))
    hexes = [P.to_hex(c) for c in order]
    n = len(hexes)
    return {"name": name, "colors": hexes, "ramps": {"all": list(range(n)), "ink": [0], "paper": [n - 1]}}
