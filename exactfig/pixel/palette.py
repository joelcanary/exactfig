"""
Palettes and palette lock / paletas y bloqueo de paleta.

A generator never invents a colour: every opaque pixel is an INDEX into a fixed palette, and `exactfig verify` checks that the
file on disk only uses those colours. Colour distance is OKLab (Björn Ottosson, 2020), where Euclidean distance follows what the
eye sees.
Un generador nunca inventa un color: cada píxel opaco es un ÍNDICE de una paleta fija (y verify lo comprueba en el fichero).

Built-in palettes are themselves made by code (`build_mf32`, `build_mono4`: OKLCh ramps with hue shifting, darker → cooler,
lighter → warmer). The hex values are frozen below so that a libm difference in the last bit can never move a colour; a test
checks that the builders still produce them.
Las paletas incluidas también salen de código (rampas OKLCh con desplazamiento de matiz) y se congelan aquí en hexadecimal.
"""
from __future__ import annotations

import math

from .. import fmath as fm
# ------------------------------------------------------------------------------------------------ OKLab


def _lin(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.04045 else fm.pow((c + 0.055) / 1.055, 2.4)


def _srgb(c: float) -> float:
    c = 12.92 * c if c <= 0.0031308 else 1.055 * fm.pow(max(0.0, c), 1 / 2.4) - 0.055
    return min(255.0, max(0.0, c * 255))


def oklab(rgb) -> tuple[float, float, float]:
    """sRGB (0–255 per channel) → OKLab (L, a, b), with portable arithmetic (fmath)."""
    r, g, b = (_lin(v) for v in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s_ = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s_ = (fm.cbrt(v) for v in (l, m, s_))
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s_,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s_,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s_)


def _cube(t: float) -> float:
    return t * t * t


def oklab_to_rgb(lab) -> tuple[float, float, float]:
    """OKLab → sRGB (0–255, clamped), the inverse of oklab up to rounding."""
    L, a, b = lab
    l = _cube(L + 0.3963377774 * a + 0.2158037573 * b)
    m = _cube(L - 0.1055613458 * a - 0.0638541728 * b)
    s_ = _cube(L - 0.0894841775 * a - 1.2914855480 * b)
    return tuple(_srgb(v) for v in (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s_,
                                     -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s_,
                                     -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s_))


def delta_e(c1, c2) -> float:
    """Diferencia perceptual entre dos colores RGB (~0,02 apenas se nota; ~0,1 se ve claramente)."""
    return fm.sqrt(fm.dist2(oklab(c1), oklab(c2)))


def to_hex(rgb) -> str:
    """'#rrggbb' of an RGB triple (rounded and clamped to 0..255)."""
    return "#%02x%02x%02x" % tuple(int(v) for v in rgb[:3])


def from_hex(h: str) -> tuple[int, int, int]:
    """RGB triple of '#rrggbb'."""
    h = h.lstrip("#")
    if len(h) != 6 or any(c not in "0123456789abcdefABCDEF" for c in h):
        raise ValueError(f"bad colour {h!r}: use #rrggbb")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


# ------------------------------------------------------------------------------------------------ builders (code-made palettes)


def _ramp(hue_deg: float, chroma: float, n: int = 5, l_lo: float = 0.30, l_hi: float = 0.90, shift: float = 28.0) -> list[str]:
    """n tonos de oscuro a claro en OKLCh: la croma es una campana (más color en los medios) y el matiz gira con la luz
    (sombras hacia el azul/violeta, luces hacia el amarillo), la regla clásica del pixel art."""
    out = []
    for k in range(n):
        t = k / (n - 1)
        L = l_lo + (l_hi - l_lo) * t
        C = chroma * (0.55 + 0.45 * fm.sin(math.pi * (0.15 + 0.7 * t)))
        warm = 85.0   # el amarillo en OKLCh
        h = hue_deg + shift * (0.5 - t) * (1 if (hue_deg - warm) % 360 < 180 else -1)
        a, b = C * fm.cos(fm.radians(h)), C * fm.sin(fm.radians(h))
        out.append(to_hex(tuple(round(v) for v in oklab_to_rgb((L, a, b)))))
    return out


MF32_RAMPS = (   # nombre, matiz OKLCh, croma
    ("stone", 60.0, 0.025), ("moss", 135.0, 0.11), ("sea", 235.0, 0.10),
    ("ember", 35.0, 0.15), ("sun", 85.0, 0.13), ("dusk", 305.0, 0.10),
)


def build_mf32() -> tuple[list[str], dict[str, list[int]]]:
    """6 rampas de 5 tonos + tinta y hueso = 32 colores."""
    colors, ramps = [], {}
    ink = to_hex(tuple(round(v) for v in oklab_to_rgb((0.18, 0.01, -0.025))))
    bone = to_hex(tuple(round(v) for v in oklab_to_rgb((0.96, 0.002, 0.015))))
    colors.append(ink)
    for name, hue, chroma in MF32_RAMPS:
        start = len(colors)
        colors += _ramp(hue, chroma)
        ramps[name] = list(range(start, start + 5))
    colors.append(bone)
    ramps["ink"] = [0]
    ramps["bone"] = [len(colors) - 1]
    ramps["grey"] = [0] + ramps["stone"] + [len(colors) - 1]
    return colors, ramps


def build_mono4() -> tuple[list[str], dict[str, list[int]]]:
    """4 tonos verdosos de pantalla de bolsillo clásica: L 0.25..0.85 a matiz 125°, croma baja."""
    colors = _ramp(125.0, 0.06, n=4, l_lo=0.25, l_hi=0.85, shift=10.0)
    return colors, {"all": [0, 1, 2, 3]}


def _oklch(L: float, C: float, h: float) -> str:
    return to_hex(tuple(round(v) for v in oklab_to_rgb((L, C * fm.cos(fm.radians(h)), C * fm.sin(fm.radians(h))))))


# Croma por paso: lo que cabe en sRGB con un 10 % de margen (y como mucho 0,11), así ningún tono se recorta y la luz es
# exactamente la diseñada.
SCI_SEQ_CHROMA = (0.110, 0.110, 0.093, 0.078, 0.077, 0.083, 0.097, 0.110, 0.110, 0.110, 0.110, 0.110)
SCI_DIV_CHROMA = (0.124, 0.104, 0.078, 0.052, 0.026, 0.0, 0.026, 0.052, 0.078, 0.104, 0.124)


def build_sci() -> tuple[list[str], dict[str, list[int]]]:
    """Paleta para datos (34 colores).
    seq   12 pasos de luz ESTRICTAMENTE creciente (OKLab L 0,22 → 0,93, lineal) con el matiz girando de violeta-azul a
          amarillo (285° → 100°): ordenada para la vista, legible en gris y sin el falso contraste de un arcoíris
    div   11 pasos divergentes: azul (255°) → gris claro neutro → rojo (30°), luz simétrica alrededor del centro
    grey  8 grises, L 0,15 → 0,97
    ink, paper, mark  líneas y curvas de nivel, fondo, y marcas de muestras (magenta, lejos de seq y div)
    cyc   12 matices a igual luz (L 0,72): rampa cíclica para fases y ángulos (va al final: los índices de antes no cambian)"""
    colors, ramps = [], {}

    def ramp(name, tones):
        start = len(colors)
        colors.extend(tones)
        ramps[name] = list(range(start, start + len(tones)))

    ramp("seq", [_oklch(0.22 + 0.71 * k / 11, SCI_SEQ_CHROMA[k], 285.0 - 185.0 * k / 11) for k in range(12)])
    ramp("div", [_oklch(0.42 + 0.51 * (1 - abs(2 * k / 10 - 1)), SCI_DIV_CHROMA[k], 255.0 if k < 5 else 30.0)
                 for k in range(11)])
    ramp("grey", [_oklch(0.15 + 0.82 * k / 7, 0.0, 0.0) for k in range(8)])
    ramp("ink", [_oklch(0.12, 0.0, 0.0)])
    ramp("paper", [_oklch(0.995, 0.0, 0.0)])
    ramp("mark", [_oklch(0.62, 0.20, 350.0)])
    ramp("cyc", [_oklch(0.72, 0.10, 30.0 * k) for k in range(12)])   # cyclic: 12 hues at equal lightness (phase)
    ramps["all"] = list(range(len(colors)))
    return colors, ramps


# Congeladas: tests/test_pixel.py comprueba que build_mf32 / build_mono4 siguen dando exactamente estos valores
MF32 = ['#120f1d', '#362b26', '#605249', '#8c7d72', '#b8ab9f', '#e6dcd1', '#023914', '#30632b', '#638f49', '#9bbb73',
        '#d5e7a9', '#062f52', '#195a84', '#3a89b3', '#69badd', '#a6eaff', '#5a0613', '#932c25', '#c9593d', '#f78e64',
        '#ffc89b', '#3b2d00', '#6d5100', '#a37800', '#d8a44c', '#ffd395', '#2f2550', '#5c4982', '#8e70b0', '#c29dd9',
        '#f4cffe', '#f7f1e7']
MONO4 = ['#1a260d', '#4d5b37', '#88956e', '#cad3b2']

SCI = ['#1a084a', '#14225f', '#0a3b69', '#13526f', '#1a677a', '#217e83', '#279589', '#44ab88', '#74bd85', '#a1ce84', '#cedc87', '#f9ea92', '#124c8e', '#3d6ba4', '#678ab6', '#91a9c7', '#bcc8d8', '#e8e8e8', '#d7c1bd', '#c59b93', '#b2756b', '#9c5045', '#832b20', '#0b0b0b', '#262626', '#434343', '#636363', '#868686', '#a9a9a9', '#cecece', '#f5f5f5', '#060606', '#fdfdfd', '#d84497', '#d88aa2', '#dc8c7f', '#d39562', '#bda257', '#9cae65', '#75b683', '#52b9a7', '#4ab6c7', '#67addd', '#8ca2e4', '#ae96da', '#c88ec3']

_BUILDERS = {"mf32": build_mf32, "mono4": build_mono4, "sci": build_sci}
_FROZEN = {"mf32": MF32, "mono4": MONO4, "sci": SCI}


class Palette:
    """An ordered list of distinct colours with named ramps (lists of indices) and an OKLab nearest-colour search."""
    def __init__(self, name: str, colors: list[str], ramps: dict[str, list[int]] | None = None):
        if not colors or len(colors) > 256:
            raise ValueError("a palette has 1..256 colours")
        self.name = name
        self.hex = [to_hex(from_hex(c)) for c in colors]
        if len(set(self.hex)) != len(self.hex):
            raise ValueError(f"palette {name}: repeated colour")
        self.rgb = [from_hex(c) for c in self.hex]
        self.lab = [oklab(c) for c in self.rgb]
        self.ramps = {k: list(v) for k, v in (ramps or {"all": list(range(len(colors)))}).items()}
        for k, v in self.ramps.items():
            if not v or any(not 0 <= i < len(colors) for i in v):
                raise ValueError(f"palette {name}: ramp {k} out of range")
        self._cache: dict = {}

    def __len__(self):
        return len(self.hex)

    def ramp(self, name: str) -> list[int]:
        if name not in self.ramps:
            raise ValueError(f"palette {self.name} has no ramp {name!r} (has: {', '.join(self.ramps)})")
        return self.ramps[name]

    def nearest(self, rgb, among: list[int] | None = None) -> int:
        """Índice del color más cercano A LA VISTA (OKLab), opcionalmente solo entre `among`."""
        key = (tuple(round(v, 6) for v in rgb), tuple(among) if among else None)
        hit = self._cache.get(key)
        if hit is None:
            lab = oklab(rgb)
            idx = among or range(len(self.hex))
            hit = min(idx, key=lambda i: (fm.dist2(self.lab[i], lab), i))
            if len(self._cache) < 65536:
                self._cache[key] = hit
        return hit

    def describe(self) -> dict:
        """The palette as a recipe would write it: name, colours and ramps."""
        return {"name": self.name, "colors": list(self.hex), "ramps": self.ramps}


def builtin(name: str) -> Palette:
    """A built-in palette (frozen colours, ramps from its builder)."""
    if name not in _FROZEN:
        raise ValueError(f"unknown palette {name!r} (built-in: {', '.join(_FROZEN)})")
    _, ramps = _BUILDERS[name]()
    return Palette(name, _FROZEN[name], ramps)


def get(spec) -> Palette:
    """Una paleta de la receta: el nombre de una incluida o {"name", "colors": ["#rrggbb", …], "ramps": {…}}."""
    if isinstance(spec, str):
        return builtin(spec)
    if isinstance(spec, dict):
        return Palette(spec.get("name", "custom"), spec["colors"], spec.get("ramps"))
    raise ValueError("palette must be a built-in name or {colors: [...]} ")


def builtin_names() -> list[str]:
    """Names of the built-in palettes."""
    return list(_FROZEN)
