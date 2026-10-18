"""
Palette-locked quantisation / cuantización con la paleta bloqueada.

Turn a continuous field into palette indices, never into new colours:
  to_ramp_ordered   scalar field [0,1] → a ramp, with Bayer 4×4 / 8×8 between steps (stable pattern, good for things that move)
  to_ramp_diffused  scalar field [0,1] → a ramp, Floyd–Steinberg or Atkinson (quiet gradients: skies, deep water)
  rgb_ordered       RGB field → nearest palette colour (OKLab) after a Bayer offset (classic ordered dithering to a fixed palette)
  rgb_diffused      RGB field → nearest palette colour with serpentine Floyd–Steinberg error diffusion
Un campo continuo se vuelve índices de la paleta, nunca colores nuevos.
"""
from __future__ import annotations

from . import pxmath as M
from .palette import Palette


def to_ramp_ordered(field: list[float], w: int, h: int, ramp: list[int], n: int = 4) -> list[int]:
    """Field in [0, 1] → ramp indices, with Bayer n×n thresholds between consecutive steps."""
    steps = len(ramp) - 1
    out = []
    for y in range(h):
        for x in range(w):
            v = min(1.0, max(0.0, field[y * w + x])) * steps
            k = int(v)
            if k < steps and (v - k) > M.bayer(x, y, n):
                k += 1
            out.append(ramp[min(k, steps)])
    return out


def to_ramp_diffused(field: list[float], w: int, h: int, ramp: list[int], kernel: str = "floyd") -> list[int]:
    """Field in [0, 1] → ramp indices by Floyd–Steinberg or Atkinson error diffusion."""
    fn = M.atkinson if kernel == "atkinson" else M.floyd_steinberg
    return [ramp[q] for q in fn(field, w, h, len(ramp))]


def rgb_ordered(rgb: list[tuple[float, float, float]], w: int, h: int, pal: Palette, spread: float = 48.0, n: int = 8,
                among: list[int] | None = None) -> list[int]:
    """RGB field → nearest palette colour (OKLab) after a Bayer offset of ±spread/2."""
    out = []
    for y in range(h):
        for x in range(w):
            o = (M.bayer(x, y, n) - 0.5) * spread
            r, g, b = rgb[y * w + x]
            out.append(pal.nearest((min(255, max(0, r + o)), min(255, max(0, g + o)), min(255, max(0, b + o))), among))
    return out


def rgb_diffused(rgb: list[tuple[float, float, float]], w: int, h: int, pal: Palette, among: list[int] | None = None) -> list[int]:
    """RGB field → nearest palette colour with serpentine Floyd–Steinberg diffusion of the RGB error."""
    err = [list(c) for c in rgb]
    out = [0] * (w * h)
    for y in range(h):
        rtl = y % 2 == 1
        xs = range(w - 1, -1, -1) if rtl else range(w)
        d = -1 if rtl else 1
        for x in xs:
            i = y * w + x
            c = tuple(min(255.0, max(0.0, v)) for v in err[i])
            q = pal.nearest(tuple(round(v) for v in c), among)
            out[i] = q
            e = [c[k] - pal.rgb[q][k] for k in range(3)]
            for dx, dy, f in ((d, 0, 7 / 16), (-d, 1, 3 / 16), (0, 1, 5 / 16), (d, 1, 1 / 16)):
                xx, yy = x + dx, y + dy
                if 0 <= xx < w and yy < h:
                    t = err[yy * w + xx]
                    for k in range(3):
                        t[k] += e[k] * f
    return out
