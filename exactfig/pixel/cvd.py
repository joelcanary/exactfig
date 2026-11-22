"""
Colour vision deficiency: which colours of a figure run together / qué colores de una figura se confunden.

Around 8 % of men of European descent see red and green differently. A figure whose meaning rides on two colours that
such a reader cannot tell apart says less to them than to everyone else. This module simulates the three dichromacies with the
matrices of Machado, Oliveira and Fernandes (2009), at full severity, applied to linear sRGB, and measures how far
apart two colours remain as the Euclidean distance in OKLab (palette.delta_e):

  normal       the colours as they are
  protan       protanopia (no long-wavelength cones; red–green)
  deutan       deuteranopia (no medium-wavelength cones; red–green)
  tritan       tritanopia (no short-wavelength cones; blue–yellow, rare)

`closest(colours)` gives, for each vision, the pair of colours that come closest. A pair closer than a threshold is
reported (0.06 by default: in OKLab a difference of about 0.02 is barely visible, 0.1 is clear; adjustable). A
sequential ramp has close neighbouring steps by design; what matters is whether the colours that carry different
meanings (categories, the two sides of a comparison) stay apart.

Machado, G. M., Oliveira, M. M. and Fernandes, L. A. F. (2009), "A Physiologically-based Model for Simulation of Color
Vision Deficiency", IEEE Transactions on Visualization and Computer Graphics 15(6), 1291–1298,
doi:10.1109/TVCG.2009.113 (the severity-1.0 matrices of its supplementary table).
"""
from __future__ import annotations

from .palette import _lin, _srgb, delta_e

MACHADO = {                              # severity 1.0, rows sum to 1 so white and greys are unchanged
    "protan": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "deutan": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "tritan": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}
VISIONS = ("normal", "protan", "deutan", "tritan")
DEFAULT_MIN = 0.06


def simulate(rgb, vision: str) -> tuple[float, float, float]:
    """An sRGB colour (0–255 per channel) as a dichromat of this kind would see it, as sRGB 0–255."""
    if vision == "normal":
        return tuple(float(v) for v in rgb)
    m = MACHADO[vision]
    lin = [_lin(v) for v in rgb]
    out = []
    for row in m:
        v = row[0] * lin[0] + row[1] * lin[1] + row[2] * lin[2]
        out.append(_srgb(min(1.0, max(0.0, v))))
    return tuple(out)


def distance(a, b, vision: str) -> float:
    """OKLab distance between two sRGB colours as seen with this vision."""
    return delta_e(simulate(a, vision), simulate(b, vision))


def closest(colours: list, visions=VISIONS) -> dict:
    """{vision: (distance, i, j)}: the closest pair of `colours` (sRGB tuples) for each vision."""
    out = {}
    sims = {v: [simulate(c, v) for c in colours] for v in visions}
    for v in visions:
        best = None
        s = sims[v]
        for i in range(len(s)):
            for j in range(i + 1, len(s)):
                d = delta_e(s[i], s[j])
                if best is None or d < best[0]:
                    best = (d, i, j)
        out[v] = best
    return out


def audit(colours: list, minimum: float = DEFAULT_MIN) -> dict:
    """For each vision: the closest pair and every pair closer than `minimum` ((distance, i, j), closest first)."""
    out = {}
    for v in VISIONS:
        s = [simulate(c, v) for c in colours]
        pairs = sorted((delta_e(s[i], s[j]), i, j) for i in range(len(s)) for j in range(i + 1, len(s)))
        out[v] = {"closest": pairs[0] if pairs else None, "below": [p for p in pairs if p[0] < minimum]}
    return out
