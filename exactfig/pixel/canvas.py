"""
Canvas: an integer grid of PALETTE INDICES / lienzo de índices de la paleta (ported from the original pxkit).

None = transparent. Nothing ever blends: every pixel is decided by a rule (discrete geometry, symmetry, ramps, noise, automata).
Ningún píxel sale de una mezcla suave; cada punto lo decide una regla.

  Primitivas   line (Bresenham), circle/disc (punto medio), ellipse, rect, polygon (relleno por barrido), star
  Simetría     mirror_x / mirror_y / radial (n ejes por rotación discreta)
  Volumen      shade_by_light (tono según la normal aproximada y la luz), outline (contorno selectivo), clean_orphans
  Salida       to_rgba, to_png (PNG indexado, escala entera), ascii (para pruebas)
"""
from __future__ import annotations

import math
from collections import deque

from .. import fmath as fm
from . import png
from .palette import Palette


def _sq(t: float) -> float:
    return t * t


class Canvas:
    """A w×h grid of palette indices (None = transparent). Every drawing call checks the index against the palette,
    so a canvas can only ever hold palette colours."""
    def __init__(self, w: int, h: int, palette: Palette):
        if not (1 <= w <= 4096 and 1 <= h <= 4096):
            raise ValueError("canvas size must be 1..4096")
        self.w, self.h, self.palette = w, h, palette
        self.px: list[list[int | None]] = [[None] * w for _ in range(h)]

    # -- básicos
    def inside(self, x: int, y: int) -> bool:
        """True when (x, y) is on the canvas."""
        return 0 <= x < self.w and 0 <= y < self.h

    def set(self, x, y, c: int | None):
        """Set the pixel nearest (x, y) to palette index c (or None); silently clipped outside the canvas."""
        x, y = int(round(x)), int(round(y))
        if self.inside(x, y):
            if c is not None and not 0 <= c < len(self.palette):
                raise ValueError(f"colour index {c} outside the palette")   # el bloqueo de paleta, en origen
            self.px[y][x] = c

    def get(self, x: int, y: int):
        """The index at (x, y), or None outside the canvas."""
        return self.px[y][x] if self.inside(x, y) else None

    def copy(self) -> "Canvas":
        """An independent copy of the pixels."""
        out = Canvas(self.w, self.h, self.palette)
        out.px = [row[:] for row in self.px]
        return out

    def cells(self):
        """Every (x, y, index) in row order."""
        for y in range(self.h):
            for x in range(self.w):
                yield x, y, self.px[y][x]

    def mask(self) -> set:
        """The set of opaque (x, y)."""
        return {(x, y) for x, y, c in self.cells() if c is not None}

    def fill_mask(self, mask, color):
        """Paint the points of `mask` (in sorted order) with a colour or a function of (x, y)."""
        for x, y in sorted(mask):
            self.set(x, y, color(x, y) if callable(color) else color)

    # -- primitivas (devuelven el conjunto de puntos; pintan si se da color)
    def line(self, x0, y0, x1, y1, c=None) -> set:
        """The Bresenham line between two points (rounded), painted with c if given; returns its points."""
        from .pxmath import line
        pts = set(line(*(int(round(v)) for v in (x0, y0, x1, y1))))
        if c is not None: self.fill_mask(pts, c)
        return pts

    def circle(self, cx, cy, r, c=None) -> set:
        """The midpoint circle of radius r around (cx, cy), painted with c if given; returns its points."""
        from .pxmath import circle
        cx, cy = int(round(cx)), int(round(cy))
        pts = {(cx + a, cy + b) for a, b in circle(int(round(r)))}
        if c is not None: self.fill_mask(pts, c)
        return pts

    def disc(self, cx, cy, r, c=None) -> set:
        """Todos los centros de píxel con (x−cx)² + (y−cy)² ≤ r² (+0,25 para que no queden muescas)."""
        pts = {(x, y) for y in range(int(cy - r - 1), int(cy + r + 2)) for x in range(int(cx - r - 1), int(cx + r + 2))
               if (x - cx) * (x - cx) + (y - cy) * (y - cy) <= r * r + 0.25}
        if c is not None: self.fill_mask(pts, c)
        return pts

    def ellipse(self, cx, cy, rx, ry, c=None) -> set:
        """The filled axis-aligned ellipse, painted with c if given; returns its points."""
        pts = {(x, y) for y in range(int(cy - ry - 1), int(cy + ry + 2)) for x in range(int(cx - rx - 1), int(cx + rx + 2))
               if rx > 0 and ry > 0 and _sq((x - cx) / rx) + _sq((y - cy) / ry) <= 1.05}
        if c is not None: self.fill_mask(pts, c)
        return pts

    def rect(self, x0, y0, x1, y1, c=None) -> set:
        """The filled rectangle between two corners, painted with c if given; returns its points."""
        pts = {(x, y) for y in range(int(y0), int(y1) + 1) for x in range(int(x0), int(x1) + 1)}
        if c is not None: self.fill_mask(pts, c)
        return pts

    def polygon(self, pts_in, c=None) -> set:
        """Relleno por barrido (regla par-impar) muestreando el centro de cada píxel."""
        pts = set()
        if len(pts_in) < 3: return pts
        ys = [p[1] for p in pts_in]
        for y in range(int(math.floor(min(ys))), int(math.ceil(max(ys))) + 1):
            yc = y + 0.5
            xs = []
            for (x0, y0), (x1, y1) in zip(pts_in, pts_in[1:] + pts_in[:1]):
                if (y0 <= yc < y1) or (y1 <= yc < y0):
                    xs.append(x0 + (yc - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for a, b in zip(xs[::2], xs[1::2]):
                for x in range(int(math.ceil(a - 0.5)), int(math.floor(b - 0.5)) + 1):
                    pts.add((x, y))
        if c is not None: self.fill_mask(pts, c)
        return pts

    @staticmethod
    def star(cx, cy, r_out, r_in, n, rot=0.0):
        """Vértices de una estrella (o de un polígono regular si r_in = r_out)."""
        out = []
        for k in range(2 * n):
            r = r_out if k % 2 == 0 else r_in
            a = rot - math.pi / 2 + k * math.pi / n
            out.append((cx + fm.cos(a) * r, cy + fm.sin(a) * r))
        return out

    # -- simetría
    def mirror_x(self, axis: float | None = None, from_left=True):
        """Refleja la mitad izquierda sobre la derecha (o al revés). Con w par, el eje está entre dos columnas."""
        axis = (self.w - 1) / 2 if axis is None else axis
        for y in range(self.h):
            for x in range(self.w):
                mx = int(round(2 * axis - x))
                if self.inside(mx, y) and ((from_left and x < axis) or (not from_left and x > axis)):
                    self.px[y][mx] = self.px[y][x]

    def mirror_y(self, axis: float | None = None):
        """Copy the rows above a horizontal axis (default: the middle) onto the rows below it."""
        axis = (self.h - 1) / 2 if axis is None else axis
        for y in range(self.h):
            my = int(round(2 * axis - y))
            if y < axis and self.inside(0, my):
                self.px[my] = self.px[y][:]

    def radial(self, n: int, cx=None, cy=None):
        """Simetría radial de orden n: copia el sector [0, 360/n) en los demás (muestreo inverso, sin huecos)."""
        cx = (self.w - 1) / 2 if cx is None else cx
        cy = (self.h - 1) / 2 if cy is None else cy
        src = self.copy()
        sector = 2 * math.pi / n
        for y in range(self.h):
            for x in range(self.w):
                dx, dy = x - cx, y - cy
                k = int((fm.atan2(dy, dx) % (2 * math.pi)) // sector)
                if k == 0: continue
                ca, sa = fm.cos(-k * sector), fm.sin(-k * sector)
                self.px[y][x] = src.get(int(round(cx + dx * ca - dy * sa)), int(round(cy + dx * sa + dy * ca)))

    def paste(self, other: "Canvas", ox: int, oy: int):
        """Copy another canvas's opaque pixels at offset (ox, oy)."""
        for x, y, c in other.cells():
            if c is not None: self.set(x + ox, y + oy, c)

    # -- volumen y contorno
    def shade_by_light(self, mask: set, ramp: list[int], light=(-1.0, -1.0), rim=True):
        """Cada punto toma un tono de la rampa según hacia dónde «mira» (desplazamiento al centro + distancia al borde)
        respecto a la luz. Arriba-izquierda iluminado por defecto, borde opuesto oscuro."""
        if not mask: return
        n = len(ramp)
        cx = sum(p[0] for p in mask) / len(mask)
        cy = sum(p[1] for p in mask) / len(mask)
        ln = fm.hypot(*light) or 1
        lx, ly = light[0] / ln, light[1] / ln
        depth = distance_to_edge(mask)
        maxd = max(depth.values()) or 1
        rx = max(1.0, max(abs(p[0] - cx) for p in mask))
        ry = max(1.0, max(abs(p[1] - cy) for p in mask))
        for (x, y) in sorted(mask):
            facing = (x - cx) / rx * lx + (y - cy) / ry * ly
            v = (1.6 + 1.4 * facing + 0.6 * depth[(x, y)] / maxd) / 3.6     # ~0..1
            level = max(0, min(n - 1, int(v * n)))
            if rim and depth[(x, y)] == 1 and facing < -0.2: level = 0
            self.set(x, y, ramp[level])

    def outline(self, color: int):
        """Contorno de 1 px por fuera de lo pintado (4 vecinos)."""
        filled = self.mask()
        ring = {(x + dx, y + dy) for (x, y) in filled for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))} - filled
        for (x, y) in sorted(ring):
            self.set(x, y, color)

    def clean_orphans(self):
        """Quita píxeles sueltos (sin ningún vecino pintado en 4 direcciones)."""
        out = [row[:] for row in self.px]
        for x, y, c in self.cells():
            if c is not None and all(self.get(x + dx, y + dy) is None for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                out[y][x] = None
        self.px = out

    # -- salida
    def scaled(self, k: int) -> "Canvas":
        """Escala entera por vecino más cercano (nunca suavizado)."""
        if k == 1: return self
        out = Canvas(self.w * k, self.h * k, self.palette)
        out.px = [[self.px[y // k][x // k] for x in range(self.w * k)] for y in range(self.h * k)]
        return out

    def to_rgba(self) -> bytes:
        """RGBA8 bytes of the canvas, transparent pixels as 00000000."""
        b = bytearray()
        rgb = self.palette.rgb
        for row in self.px:
            for c in row:
                b += bytes((0, 0, 0, 0)) if c is None else bytes(rgb[c]) + b"\xff"
        return bytes(b)

    def to_png(self) -> bytes:
        """PNG indexado: la paleta entera en PLTE (+ un índice transparente al final si hace falta)."""
        pal = list(self.palette.rgb)
        has_alpha = any(c is None for _, _, c in self.cells())
        t = None
        if has_alpha:
            if len(pal) >= 256: raise ValueError("no room for a transparent index")
            t = len(pal); pal.append((0, 0, 0))
        idx = [t if c is None else c for _, _, c in self.cells()]
        return png.encode_indexed(self.w, self.h, idx, pal, t)

    def ascii(self) -> str:
        """A text picture of the canvas (one character per index), for tests and debugging."""
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return "\n".join("".join("." if c is None else chars[c % len(chars)] for c in row) for row in self.px)


def distance_to_edge(mask: set) -> dict:
    """Distancia (pasos de 4 vecinos) de cada punto de la máscara al exterior: 1 en el borde (BFS)."""
    dist, q = {}, deque()
    for (x, y) in sorted(mask):
        if any((x + dx, y + dy) not in mask for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            dist[(x, y)] = 1; q.append((x, y))
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            p = (x + dx, y + dy)
            if p in mask and p not in dist:
                dist[p] = dist[(x, y)] + 1; q.append(p)
    return dist


def signature(cv: Canvas, cells: int = 8) -> tuple:
    """Firma de un dibujo: silueta en una rejilla cells×cells y reparto de colores. Dos dibujos parecidos, firmas cercanas."""
    shape = []
    bw, bh = cv.w / cells, cv.h / cells
    for j in range(cells):
        for i in range(cells):
            n = sum(1 for y in range(int(j * bh), int((j + 1) * bh)) for x in range(int(i * bw), int((i + 1) * bw)) if cv.px[y][x] is not None)
            shape.append(1 if n > bw * bh * 0.35 else 0)
    hist: dict = {}
    for _, _, c in cv.cells():
        if c is not None: hist[c] = hist.get(c, 0) + 1
    total = sum(hist.values()) or 1
    return tuple(shape), {k: v / total for k, v in hist.items()}


def distance(a: tuple, b: tuple) -> float:
    """0 = iguales; 1 = nada que ver. Mitad silueta (Hamming), mitad colores (variación total)."""
    (sa, ha), (sb, hb) = a, b
    shape = sum(x != y for x, y in zip(sa, sb)) / max(1, len(sa))
    color = 0.5 * sum(abs(ha.get(k, 0) - hb.get(k, 0)) for k in set(ha) | set(hb))
    return 0.5 * shape + 0.5 * color
