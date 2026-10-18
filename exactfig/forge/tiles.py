"""
Tiles / losetas: stone (Voronoi), terrain (fBm in world coordinates), cave (cellular automaton).

stone and cave are TILEABLE (the noise wraps with `period`); terrain is CONTINUOUS across tiles (world_x / world_y offsets):
render (0,0) and (1,0) and they join without a seam. Piedra y cueva se repiten; el terreno continúa entre losetas vecinas.
"""
from __future__ import annotations

from ..pixel import pxmath as M
from ..pixel.canvas import Canvas, distance_to_edge
from ..pixel.dither import to_ramp_ordered
from ..rng import Rng, seed_int


def stone(seed, pal, w, h, p) -> Canvas:
    """Losas de Voronoi: junta donde F2 − F1 es pequeño, bisel con la luz arriba-izquierda, grano de fBm y grietas de crestas."""
    s = seed_int(seed, "stone")
    cells, jitter, mortar = p["cells"], p["jitter"], p["mortar"]
    ramp = pal.ramp(p["ramp"])
    joint = pal.ramp(p["joint_ramp"])[0]
    cv = Canvas(w, h, pal)
    field, body = [0.0] * (w * h), [False] * (w * h)
    for y in range(h):
        for x in range(w):
            u, v = (x + 0.5) * cells / w, (y + 0.5) * cells / h
            f1, f2, cell, dx, dy = M.worley(u, v, s, jitter, period=cells)
            i = y * w + x
            if f2 - f1 < mortar:
                continue
            body[i] = True
            t = 0.30 + 0.35 * M.hash2(cell[0], cell[1], s + 3)
            t += -(dx + dy) * 0.55                                     # bisel: lo que mira arriba-izquierda, claro
            if f2 - f1 < mortar * 2.2:
                t -= 0.12
            t += (M.fbm(u * 3, v * 3, s + 9, 3, period=cells * 3) - 0.5) * 0.35
            if M.ridged(u * 2, v * 2, s + 17, 3, period=cells * 2) > 1 - p["cracks"] * 0.12:
                t -= 0.35
            field[i] = t
    q = to_ramp_ordered(field, w, h, ramp, 4)
    for y in range(h):
        for x in range(w):
            i = y * w + x
            cv.px[y][x] = q[i] if body[i] else joint
    return cv


def terrain(seed, pal, w, h, p) -> Canvas:
    """Altura = fBm deformado en coordenadas del MUNDO → agua honda, agua, arena, hierba, bosque, roca.
    Dentro de cada banda, dos tonos con Bayer 4×4: el borde de mancha va tramado, no a escalones."""
    s = seed_int(seed, "terrain")
    ox, oy, sc = p["world_x"] * w, p["world_y"] * h, p["scale"]
    water, sand, forest, rock = p["water"], p["sand"], p["forest"], p["rock"]
    sea, sun, moss, stone_r = pal.ramp("sea"), pal.ramp("sun"), pal.ramp("moss"), pal.ramp("stone")
    bands = [   # (hasta, tono bajo, tono alto)
        (water - 0.10, sea[0], sea[1]), (water, sea[1], sea[2]), (water + sand, sun[3], sun[4]),
        (forest, moss[3], moss[2]), (rock, moss[1], moss[0]), (1.01, stone_r[2], stone_r[4]),
    ]
    cv = Canvas(w, h, pal)
    for y in range(h):
        for x in range(w):
            wx, wy = M.warp((ox + x) / sc, (oy + y) / sc, s, amount=0.6, scale=2.0)
            e = M.fbm(wx, wy, s, 5)
            e = min(1.0, max(0.0, (e - 0.5) * 1.6 + 0.5))
            lo = 0.0
            for top, a, b in bands:
                if e < top:
                    t = (e - lo) / max(1e-9, top - lo)
                    cv.px[y][x] = b if t > 0.5 + 0.5 * (M.bayer(ox + x, oy + y) - 0.5) else a
                    break
                lo = top
    return cv


def cave(seed, pal, w, h, p) -> Canvas:
    """Autómata de cuevas (B5678/S45678): roca al azar, unos pasos y salen cavernas; la roca se sombrea por hondura y el suelo
    lleva fBm y musgo junto a las paredes. Enlosable: el autómata envuelve los bordes."""
    rng = Rng(f"cave:{seed}")
    s = seed_int(seed, "cave")
    rock = [rng.random() < p["fill"] for _ in range(w * h)]
    for _ in range(p["steps"]):
        out = [False] * (w * h)
        for y in range(h):
            for x in range(w):
                n = sum(rock[((y + dy) % h) * w + (x + dx) % w] for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy)
                out[y * w + x] = n >= 4 if rock[y * w + x] else n >= 5
        rock = out
    wall, floor_r, moss = pal.ramp(p["ramp"]), pal.ramp(p["floor_ramp"]), pal.ramp("moss")
    floor = {(x, y) for y in range(h) for x in range(w) if not rock[y * w + x]}
    solid = {(x, y) for y in range(h) for x in range(w) if rock[y * w + x]}
    depth = distance_to_edge(solid) if solid else {}
    cv = Canvas(w, h, pal)
    for (x, y), d in depth.items():
        lit = (x, y + 1) in floor or (x - 1, y) in floor     # la cara que mira al suelo, con luz
        cv.px[y][x] = wall[min(len(wall) - 1, 3)] if lit and d == 1 else wall[max(0, 2 - d // 2)]
    for (x, y) in floor:
        t = M.fbm(x / 6, y / 6, s, 3, period=None)
        near = sum((x + dx, y + dy) in solid for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        c = floor_r[1] if t < 0.5 + 0.2 * (M.bayer(x, y) - 0.5) else floor_r[2]
        if near and M.fbm(x / 3, y / 3, s + 5, 2) > 1 - p["moss"]:
            c = moss[2]
        cv.px[y][x] = c
    return cv
