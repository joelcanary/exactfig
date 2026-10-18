"""
pxmath: math primitives for pixel art / primitivas MATEMÁTICAS para pixel art.

Pure Python, no Pillow and no palette: just numbers. Everything is deterministic: the same input gives the same numbers, so a
recorded asset can be regenerated and checked pixel for pixel (`exactfig verify`).
Puro Python, sin Pillow ni paleta: solo números. Todo es determinista (misma entrada, mismos números).

  Tramado      BAYER4, BAYER8, bayer(x, y, n), dither(x, y, t) · floyd_steinberg / atkinson (difusión de error a n niveles)
  Ruido        hash2, value_noise, fbm, ridged (fractal de crestas), warp (deformación del dominio); `period` = enlosable
  Voronoi      worley(x, y, seed, jitter, period) → (F1, F2, celda, dx, dy): losas, rocas, grietas, escamas
  Autómatas    cave_step (vecindad de Moore, B/S), cellular (sobre conjuntos)
  Fractales    julia, mandelbrot (iteraciones de escape), sierpinski (bit a bit), JULIA_SEEDS
  Curvas       bezier (cúbica), bezier_tangent, bezier_points, vogel (girasol, ángulo áureo)
  Geometría    line (Bresenham), circle (punto medio), sd_circle, sd_box, sd_segment (distancias con signo)
  Reparto      poisson_disc (Bridson), con cualquier Rng que tenga .random()

Noise takes WORLD coordinates: sample it at (tile_x * size + x, tile_y * size + y) and neighbouring tiles join without seams.
El ruido va en coordenadas del MUNDO: muestreado por casilla, se ve la rejilla.
"""
from __future__ import annotations

import math

from .. import fmath as fm
# ------------------------------------------------------------------------------------------------ tramado ordenado

BAYER4 = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


def _bayer8() -> tuple:
    """Bayer 8×8 por intercalado de bits de (x⊕y, y), invertidos: la primera fila es 0, 32, 8, 40, 2, 34, 10, 42."""
    rows = []
    for y in range(8):
        row = []
        for x in range(8):
            v = 0
            for b in range(3):
                v |= ((x ^ y) >> b & 1) << (2 * (2 - b) + 1) | (y >> b & 1) << (2 * (2 - b))
            row.append(v)
        rows.append(tuple(row))
    return tuple(rows)


BAYER8 = _bayer8()


def bayer(x: int, y: int, n: int = 4) -> float:
    """Umbral de Bayer en (0, 1) del píxel (x, y) con la matriz n×n (4 u 8)."""
    if n == 8:
        return (BAYER8[y & 7][x & 7] + 0.5) / 64
    return (BAYER4[y & 3][x & 3] + 0.5) / 16


def dither(x: int, y: int, t: float) -> bool:
    """Tramado ordenado: ¿este píxel toma el tono siguiente? t en [0,1] es la proporción (patrón estable, sin ruido)."""
    return t * 16 > BAYER4[y & 3][x & 3] + 0.5


def floyd_steinberg(field: list[float], w: int, h: int, levels: int = 2, serpentine: bool = True) -> list[int]:
    """Cuantiza un campo [0,1] a `levels` niveles repartiendo el error (7/16, 3/16, 5/16, 1/16), en serpentina. Para degradados QUIETOS
    (cielos horneados, agua honda): el patrón no tiene la trama de Bayer pero cambia entero si cambia el campo."""
    err = list(field)
    out = [0] * (w * h)
    top = levels - 1
    for y in range(h):
        rtl = serpentine and y % 2 == 1
        xs = range(w - 1, -1, -1) if rtl else range(w)
        d = -1 if rtl else 1
        for x in xs:
            i = y * w + x
            v = min(1.0, max(0.0, err[i])) * top
            q = min(top, max(0, int(round(v))))
            out[i] = q
            e = (v - q) / top
            if 0 <= x + d < w:
                err[i + d] += e * 7 / 16
            if y + 1 < h:
                if 0 <= x - d < w:
                    err[i + w - d] += e * 3 / 16
                err[i + w] += e * 5 / 16
                if 0 <= x + d < w:
                    err[i + w + d] += e * 1 / 16
    return out


def atkinson(field: list[float], w: int, h: int, levels: int = 2) -> list[int]:
    """Difusión de Atkinson (reparte 6/8 del error a seis vecinos): más contraste y blancos limpios que Floyd–Steinberg."""
    err = list(field)
    out = [0] * (w * h)
    top = levels - 1
    for y in range(h):
        for x in range(w):
            i = y * w + x
            v = min(1.0, max(0.0, err[i])) * top
            q = min(top, max(0, int(round(v))))
            out[i] = q
            e = (v - q) / top / 8
            for dx, dy in ((1, 0), (2, 0), (-1, 1), (0, 1), (1, 1), (0, 2)):
                xx, yy = x + dx, y + dy
                if 0 <= xx < w and yy < h:
                    err[yy * w + xx] += e
    return out


# ------------------------------------------------------------------------------------------------ ruido


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation a + (b − a)·t."""
    return a + (b - a) * t


def hash2(ix: int, iy: int, seed: int) -> float:
    """Hash de dos enteros con semilla en [0, 1)."""
    h = (ix * 374761393 + iy * 668265263 + seed * 2246822519) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return (h ^ (h >> 16)) / 4294967296.0


def _wrap(i: int, period: int | None) -> int:
    return i % period if period else i


def value_noise(x: float, y: float, seed: int = 0, period: int | None = None) -> float:
    """Ruido de valor con interpolación suave (smoothstep) entre las esquinas de la rejilla: 0..1, continuo y determinista.
    period: la rejilla se repite cada `period` unidades (textura enlosable / tileable)."""
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    x0, x1, y0, y1 = _wrap(ix, period), _wrap(ix + 1, period), _wrap(iy, period), _wrap(iy + 1, period)
    a, b = hash2(x0, y0, seed), hash2(x1, y0, seed)
    c, d = hash2(x0, y1, seed), hash2(x1, y1, seed)
    return lerp(lerp(a, b, sx), lerp(c, d, sx), sy)


def fbm(x: float, y: float, seed: int = 0, octaves: int = 4, lacunarity: float = 2.0, gain: float = 0.5,
        period: int | None = None) -> float:
    """Suma de octavas de ruido (movimiento browniano fraccional): manchas de piel, roca, nubes, lava. 0..1.
    Con `period` (y lacunarity entera) cada octava se repite a la vez: enlosable."""
    total, amp, freq, norm = 0.0, 1.0, 1.0, 0.0
    for o in range(octaves):
        p = int(period * freq) if period else None
        total += amp * value_noise(x * freq, y * freq, seed + o * 101, p)
        norm += amp; amp *= gain; freq *= lacunarity
    return total / norm


def ridged(x: float, y: float, seed: int = 0, octaves: int = 4, period: int | None = None) -> float:
    """Fractal de crestas 1 − |2·fbm − 1|: vale 1 en crestas finas que se ramifican (vetas, grietas, relámpagos)."""
    return 1 - abs(2 * fbm(x, y, seed, octaves, period=period) - 1)


def warp(x: float, y: float, seed: int = 0, amount: float = 4.0, scale: float = 8.0) -> tuple[float, float]:
    """Deformación del dominio: el punto desplazado por dos fbm (bordes orgánicos sin ruido de píxel suelto)."""
    return (x + (fbm(x / scale, y / scale, seed + 11, 2) - 0.5) * 2 * amount,
            y + (fbm(x / scale, y / scale, seed + 23, 2) - 0.5) * 2 * amount)


# ------------------------------------------------------------------------------------------------ Voronoi / Worley


def worley(x: float, y: float, seed: int = 0, jitter: float = 0.9,
           period: int | None = None) -> tuple[float, float, tuple[int, int], float, float]:
    """Ruido celular (coordenadas en unidades de celda): F1, F2, la celda más cercana y el vector del punto a su semilla.
    jitter 0 = cuadrícula exacta (losas talladas), ~1 = Voronoi libre (piedra natural). F2 − F1 pequeño = junta o grieta.
    period: las celdas se repiten cada `period` (enlosable); la celda devuelta va ya envuelta."""
    ix, iy = math.floor(x), math.floor(y)
    f1 = f2 = 1e9
    best = (ix, iy); bdx = bdy = 0.0
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            cx, cy = ix + ox, iy + oy
            hx, hy = _wrap(cx, period), _wrap(cy, period)
            px = cx + 0.5 + (hash2(hx, hy, seed) - 0.5) * jitter
            py = cy + 0.5 + (hash2(hx, hy, seed + 7919) - 0.5) * jitter
            dx, dy = x - px, y - py
            d = fm.hypot(dx, dy)
            if d < f1:
                f2, f1, best, bdx, bdy = f1, d, (hx, hy), dx, dy
            elif d < f2:
                f2 = d
    return f1, f2, best, bdx, bdy


# ------------------------------------------------------------------------------------------------ autómatas


def cave_step(rock: list[bool], w: int, h: int, birth: int = 5, survive: int = 4, outside: bool = True) -> list[bool]:
    """Un paso del autómata de cuevas sobre una rejilla plana: nace con ≥ birth vecinos de roca (de 8), sigue con ≥ survive."""
    out = [False] * (w * h)
    for y in range(h):
        for x in range(w):
            n = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    xx, yy = x + dx, y + dy
                    n += outside if (xx < 0 or yy < 0 or xx >= w or yy >= h) else rock[yy * w + xx]
            out[y * w + x] = n >= survive if rock[y * w + x] else n >= birth
    return out


def cellular(w: int, h: int, rng, fill: float = 0.45, steps: int = 4, birth: int = 5, survive: int = 4) -> set:
    """Autómata celular «cuevas» (regla B5678/S45678 por defecto) sobre conjuntos: manchas orgánicas para musgo, cuevas, costras."""
    alive = {(x, y) for y in range(h) for x in range(w) if rng.random() < fill}
    for _ in range(steps):
        nxt = set()
        for y in range(h):
            for x in range(w):
                n = sum((x + dx, y + dy) in alive for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)
                if ((x, y) in alive and n >= survive) or ((x, y) not in alive and n >= birth):
                    nxt.add((x, y))
        alive = nxt
    return alive


# ------------------------------------------------------------------------------------------------ fractales

JULIA_SEEDS = ((-0.8, 0.156), (-0.7269, 0.1889), (0.285, 0.01), (-0.4, 0.6), (0.355, 0.355), (-0.123, 0.745), (-0.70176, -0.3842))


def julia(zx: float, zy: float, cx: float, cy: float, max_iter: int = 32) -> int:
    """Iteraciones de escape de z ← z² + c (max_iter si no escapa: dentro del conjunto de Julia de c)."""
    for i in range(max_iter):
        x2, y2 = zx * zx, zy * zy
        if x2 + y2 > 4:
            return i
        zx, zy = x2 - y2 + cx, 2 * zx * zy + cy
    return max_iter


def mandelbrot(cx: float, cy: float, max_iter: int = 32) -> int:
    """Iteraciones de escape del conjunto de Mandelbrot en c."""
    return julia(0.0, 0.0, cx, cy, max_iter)


def sierpinski(x: int, y: int) -> bool:
    """Triángulo de Sierpiński bit a bit: (x AND y) == 0."""
    return (x & y) == 0


# ------------------------------------------------------------------------------------------------ curvas


def bezier(p0, p1, p2, p3, t: float) -> tuple[float, float]:
    """Punto de una Bézier cúbica (Bernstein)."""
    u = 1 - t
    a, b, c, d = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
    return (a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1])


def bezier_tangent(p0, p1, p2, p3, t: float) -> tuple[float, float]:
    """Derivative of the cubic Bézier curve at t."""
    u = 1 - t
    return (3 * u * u * (p1[0] - p0[0]) + 6 * u * t * (p2[0] - p1[0]) + 3 * t * t * (p3[0] - p2[0]),
            3 * u * u * (p1[1] - p0[1]) + 6 * u * t * (p2[1] - p1[1]) + 3 * t * t * (p3[1] - p2[1]))


def bezier_points(p0, p1, p2, p3) -> list[tuple[int, int]]:
    """Los píxeles enteros de la curva, 8-conexos y sin repetir (paso fino y se quedan los distintos)."""
    n = max(8, int((fm.dist(p0, p1) + fm.dist(p1, p2) + fm.dist(p2, p3)) * 2))
    out: list[tuple[int, int]] = []
    for k in range(n + 1):
        x, y = bezier(p0, p1, p2, p3, k / n)
        p = (int(round(x)), int(round(y)))
        if not out or out[-1] != p:
            out.append(p)
    return out


GOLDEN_ANGLE = math.pi * (3 - math.sqrt(5))


def vogel(n: int, scale: float = 1.0) -> list[tuple[float, float]]:
    """Girasol de Vogel: el k-ésimo punto a radio scale·√k y ángulo k·137,5° (reparto sin huecos ni filas)."""
    return [(scale * math.sqrt(k) * fm.cos(k * GOLDEN_ANGLE), scale * math.sqrt(k) * fm.sin(k * GOLDEN_ANGLE)) for k in range(n)]


# ------------------------------------------------------------------------------------------------ geometría discreta


def line(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """Recta de Bresenham, extremos incluidos."""
    pts = []
    dx, sx = abs(x1 - x0), 1 if x0 < x1 else -1
    dy, sy = -abs(y1 - y0), 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        pts.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy; x0 += sx
        if e2 <= dx:
            err += dx; y0 += sy
    return pts


def circle(r: int) -> list[tuple[int, int]]:
    """Contorno del círculo de radio r por el punto medio (los 8 octantes, sin repetir)."""
    pts = set()
    x, y, d = r, 0, 1 - r
    while x >= y:
        for a, b in ((x, y), (y, x), (-y, x), (-x, y), (-x, -y), (-y, -x), (y, -x), (x, -y)):
            pts.add((a, b))
        y += 1
        if d < 0:
            d += 2 * y + 1
        else:
            x -= 1; d += 2 * (y - x) + 1
    return sorted(pts)


def sd_circle(x: float, y: float, r: float) -> float:
    """Signed distance to a circle of radius r at the origin (negative inside)."""
    return fm.hypot(x, y) - r


def sd_box(x: float, y: float, bx: float, by: float) -> float:
    """Signed distance to an axis-aligned box of half-sizes (bx, by) at the origin."""
    qx, qy = abs(x) - bx, abs(y) - by
    return fm.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0)


def sd_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    """Distance from (px, py) to the segment from (ax, ay) to (bx, by)."""
    pax, pay, bax, bay = px - ax, py - ay, bx - ax, by - ay
    h = max(0.0, min(1.0, (pax * bax + pay * bay) / max(1e-9, bax * bax + bay * bay)))
    return fm.hypot(pax - bax * h, pay - bay * h)


# ------------------------------------------------------------------------------------------------ reparto sin grumos


def poisson_disc(w: float, h: float, r: float, rng, k: int = 30) -> list[tuple[float, float]]:
    """Muestreo de disco de Poisson (Bridson, 2007): puntos al azar pero nunca a menos de r entre sí. Árboles, rocas,
    estrellas o criaturas repartidas sin grumos ni rejilla. Determinista con exactfig.rng.Rng."""
    cell = r / math.sqrt(2)
    gw, gh = int(math.ceil(w / cell)), int(math.ceil(h / cell))
    grid: list = [None] * (gw * gh)
    pts: list[tuple[float, float]] = []
    active: list[int] = []

    def add(p):
        pts.append(p)
        grid[int(p[1] / cell) * gw + int(p[0] / cell)] = len(pts) - 1
        active.append(len(pts) - 1)

    add((rng.random() * w, rng.random() * h))
    while active:
        i = int(rng.random() * len(active))
        px, py = pts[active[i]]
        for _ in range(k):
            ang, rad = rng.random() * 2 * math.pi, r * (1 + rng.random())
            q = (px + rad * fm.cos(ang), py + rad * fm.sin(ang))
            if not (0 <= q[0] < w and 0 <= q[1] < h):
                continue
            gx, gy = int(q[0] / cell), int(q[1] / cell)
            if all(grid[yy * gw + xx] is None or fm.dist(q, pts[grid[yy * gw + xx]]) >= r
                   for yy in range(max(0, gy - 2), min(gh, gy + 3)) for xx in range(max(0, gx - 2), min(gw, gx + 3))):
                add(q)
                break
        else:
            active.pop(i)
    return pts
