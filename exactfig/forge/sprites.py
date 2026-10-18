"""
Critters / bichos: a sheet of small symmetric creatures, each from its own forked seed.

Half a body is drawn by probability (denser near the spine and the middle rows), smoothed by the cave automaton, mirrored,
shaded as a volume with the light at the top-left, given one pair of eyes and a 1 px outline. A variety gate (silhouette +
colour signature) rejects a creature too close to one already on the sheet.
Media silueta por probabilidad, suavizada con el autómata, reflejada, sombreada como volumen, con ojos y contorno.
"""
from __future__ import annotations

from ..pixel import pxmath as M
from ..pixel.canvas import Canvas, distance, signature
from ..rng import Rng


def _one(rng: Rng, pal, n: int, ramps: list[str], ink: int, eye: int) -> Canvas:
    core = n - 2
    half = (core + 1) // 2
    grid = [False] * (core * core)
    for y in range(core):
        for x in range(half):
            spine = x / max(1, half - 1)                       # 1 junto al eje
            mid = 1 - abs(y / max(1, core - 1) - 0.5) * 2       # 1 en las filas del medio
            grid[y * core + x] = rng.random() < 0.05 + 0.60 * spine + 0.35 * mid
    for y in range(core):
        for x in range(half):
            grid[y * core + (core - 1 - x)] = grid[y * core + x]
    for _ in range(2):
        grid = M.cave_step(grid, core, core, birth=5, survive=3, outside=False)
    cv = Canvas(n, n, pal)
    mask = {(x + 1, y + 1) for y in range(core) for x in range(core) if grid[y * core + x]}
    if len(mask) < core:                                       # demasiado poco cuerpo: una gota mínima
        mask |= cv.ellipse(n / 2 - 0.5, n / 2, n / 4, n / 3)
    ramp = pal.ramp(rng.pick(ramps))
    cv.shade_by_light(mask, ramp)
    # ojos: en la fila más alta donde el par cabe con cuerpo alrededor (arriba y a los lados), en tinta con brillo
    cx = (n - 1) / 2
    gap = rng.randint(0, max(0, n // 8))
    for y in range(2, n - 3):
        xl = int(cx - 1 - gap)
        xr = int(round(2 * cx - xl))
        if all({(x, y), (x, y - 1), (x - 1, y), (x + 1, y), (x, y + 1)} <= mask for x in (xl, xr)):
            for x in (xl, xr):
                cv.set(x, y, ink)
                if n >= 16:
                    cv.set(x, y - 1, eye)
            break
    cv.outline(ink)
    return cv


def critters(seed, pal, w, h, p) -> Canvas:
    """Generator forge.sprite.critters: a sheet of mirrored automaton shapes, each
    kept only if it differs enough from the ones before (signature distance)."""
    n, cols, count = p["cell"], p["cols"], p["count"]
    rows = (count + cols - 1) // cols
    if w != n * cols or h != n * rows:
        raise ValueError(f"size must be [{n * cols}, {n * rows}] for {count} critters of {n}px in {cols} columns")
    ink, eye = pal.ramp("ink")[0], pal.ramp("bone")[0]
    sheet = Canvas(w, h, pal)
    seen = []
    for k in range(count):
        base = Rng(f"critter:{seed}:{k}")
        for attempt in range(24):
            cv = _one(base.fork(str(attempt)), pal, n, p["ramps"], ink, eye)
            sig = signature(cv)
            if all(distance(sig, s) >= p["variety"] for s in seen):
                break
        seen.append(sig)
        sheet.paste(cv, (k % cols) * n, (k // cols) * n)
    return sheet
