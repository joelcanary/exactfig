"""
Make the example datasets in gallery/data, deterministically, from published formulas.

  franke-halton-256.csv   Franke's function (R. Franke, 1979, the standard test of scattered-data interpolation) at the
                          first 256 points of the Halton sequence in bases 2 and 3 on [0, 1]²; columns x, y, value
  plate-129.npy           steady temperature of a unit square plate whose top edge is held at sin(πx) and the other three
                          at 0: the exact solution of Laplace's equation, u(x, y) = sin(πx) · sinh(πy) / sinh(π), on a
                          129 × 129 grid (row 0 is y = 1), float64
  dem-192.pgm             a synthetic elevation model: four Gaussian massifs and fractal (fBm) detail on a
                          192 × 192 grid of 60 m cells, as a 16-bit greymap: elevation in metres = value × 2000 / 65535
  testcard-480x320.png    a true-colour test card for image conversion: an OKLCh colour wheel (hue = angle, lightness
                          = radius), grey, red, green and blue ramps, and two shapes with anti-aliased edges (RGBA, 8 bits)

Run from the repository root:  python examples/data/make_data.py [OUT_DIR]   (default gallery/data)
The test suite regenerates them and checks every byte.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))

from exactfig import fmath as fm  # noqa: E402
from exactfig.data.io import write_npy, write_pgm  # noqa: E402
from exactfig.pixel import palette as PAL, png  # noqa: E402
from exactfig.pixel import pxmath as M  # noqa: E402


def halton(i: int, base: int) -> float:
    f, r = 1.0, 0.0
    while i > 0:
        f /= base
        r += f * (i % base)
        i //= base
    return r


def franke(x: float, y: float) -> float:
    a = 9 * x - 2
    b = 9 * y - 2
    return (0.75 * fm.exp(-(a * a + b * b) / 4)
            + 0.75 * fm.exp(-((9 * x + 1) * (9 * x + 1)) / 49 - (9 * y + 1) / 10)
            + 0.5 * fm.exp(-((9 * x - 7) * (9 * x - 7) + (9 * y - 3) * (9 * y - 3)) / 4)
            - 0.2 * fm.exp(-((9 * x - 4) * (9 * x - 4)) - (9 * y - 7) * (9 * y - 7)))


def sinh(t: float) -> float:
    return (fm.exp(t) - fm.exp(-t)) / 2


def dem(x: float, y: float) -> float:
    """Elevation in [0, 1] at (x, y) ∈ [0, 1]²."""
    def hill(cx, cy, r, hgt):
        dx, dy = x - cx, y - cy
        return hgt * fm.exp(-(dx * dx + dy * dy) / (2 * r * r))
    base = (hill(0.30, 0.30, 0.13, 0.9) + hill(0.70, 0.62, 0.17, 0.75) + hill(0.55, 0.20, 0.08, 0.45)
            + hill(0.22, 0.78, 0.10, 0.35))
    return base + 0.06 * M.fbm(x * 9.0, y * 9.0, seed=7, octaves=5)


def testcard(w: int = 480, h: int = 320) -> bytes:
    """RGBA8 bytes of the test card."""
    out = bytearray()
    cx, cy, rmax = w * 0.36, h * 0.42, h * 0.40
    bars = h - 56
    for j in range(h):
        for i in range(w):
            x, y = i + 0.5, j + 0.5
            if y >= bars:                                     # four ramps, 14 px each
                k = int((y - bars) // 14)
                t = (x / w) * 255.0
                rgb = ((t, t, t), (t, 0.0, 0.0), (0.0, t, 0.0), (0.0, 0.0, t))[min(3, k)]
            else:
                dx, dy = x - cx, y - cy
                r = fm.sqrt(dx * dx + dy * dy) / rmax
                hue = fm.atan2(-dy, dx) * 180.0 / fm.pi % 360.0
                L = 0.86 - 0.45 * min(1.0, r)
                C = 0.13 * min(1.0, r * 1.6)
                rgb = PAL.oklab_to_rgb((L, C * fm.cos(fm.radians(hue)), C * fm.sin(fm.radians(hue))))
                # two shapes on the right, edges anti-aliased over one pixel by their signed distance
                for sd, col in ((M.sd_circle(x - w * 0.80, y - h * 0.28, 44.0), (250.0, 236.0, 120.0)),
                                (M.sd_box(x - w * 0.80, y - h * 0.66, 40.0, 26.0), (40.0, 60.0, 150.0))):
                    a = min(1.0, max(0.0, 0.5 - sd))
                    rgb = tuple(c * (1 - a) + q * a for c, q in zip(rgb, col))
            out += bytes(min(255, max(0, int(fm.floor(v + 0.5)))) for v in rgb) + b"\xff"
    return bytes(out)


def make(out_dir: str) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    p = os.path.join(out_dir, "franke-halton-256.csv")
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("x,y,value\n")
        for i in range(1, 257):
            x, y = halton(i, 2), halton(i, 3)
            fh.write(f"{x!r},{y!r},{franke(x, y)!r}\n")
    paths.append(p)
    n = 129
    rows = [[fm.sin(fm.pi * (i / (n - 1))) * sinh(fm.pi * (1 - j / (n - 1))) / sinh(fm.pi) for i in range(n)]
            for j in range(n)]
    for r in rows:                              # sin(π · 1) is not exactly 0 in floating point; the boundary is
        r[0] = r[-1] = 0.0
    p = os.path.join(out_dir, "plate-129.npy")
    write_npy(p, rows)
    paths.append(p)
    n = 192
    z = [[dem((i + 0.5) / n, 1 - (j + 0.5) / n) for i in range(n)] for j in range(n)]
    lo = min(min(r) for r in z)
    hi = max(max(r) for r in z)
    p = os.path.join(out_dir, "dem-192.pgm")
    write_pgm(p, [[int(fm.floor((v - lo) / (hi - lo) * 65535 + 0.5)) for v in r] for r in z], 65535)
    paths.append(p)
    p = os.path.join(out_dir, "testcard-480x320.png")
    with open(p, "wb") as fh:
        fh.write(png.encode_rgba(480, 320, testcard()))
    paths.append(p)
    return paths


if __name__ == "__main__":
    for path in make(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "gallery", "data")):
        print(path)
