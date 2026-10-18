"""
The generator registry / el registro de generadores.

Only code registered here can produce an asset, and each generator declares a closed PARAMETER SCHEMA: unknown parameters are
rejected and every value has a type and a range. There is no "load a bitmap" or "paste these pixels" parameter anywhere, so a
recipe cannot smuggle an image in: what comes out is what the published algorithm computes from a few numbers.
Solo el código registrado produce assets, y cada generador tiene un esquema cerrado de parámetros (nada de colar un bitmap).

Each generator also names the modules it depends on; `code_sha256` hashes their source so the manifest says exactly which code
ran. Bump `version` whenever a change moves any output pixel or byte.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Any, Callable

PKG = os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------------------------------------------ parameter schema

@dataclass(frozen=True)
class P:
    """One parameter of a generator's closed schema: its kind, default, bounds or choices, and a line of documentation."""
    kind: str                     # int · float · str · bool · strlist · pair · numdict · text · shapes
    default: Any = None
    lo: float | None = None
    hi: float | None = None
    choices: tuple = ()
    maxlen: int = 8
    doc: str = ""

    def check(self, name: str, v):
        """Return `v` converted to this parameter's kind (ints accepted for floats), or raise ValueError saying why not."""
        bad = ValueError(f"param {name!r}: {v!r} is not a valid {self.kind}"
                         + (f" in [{self.lo}, {self.hi}]" if self.lo is not None else "")
                         + (f" from {list(self.choices)}" if self.choices else ""))
        if self.kind == "int":
            if isinstance(v, bool) or not isinstance(v, int) or not self.lo <= v <= self.hi: raise bad
        elif self.kind == "float":
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not self.lo <= v <= self.hi: raise bad
            v = float(v)
        elif self.kind == "str":
            if not isinstance(v, str) or (self.choices and v not in self.choices): raise bad
        elif self.kind == "text":
            if not isinstance(v, str) or len(v) > self.maxlen or not v.isascii(): raise bad
        elif self.kind == "bool":
            if not isinstance(v, bool): raise bad
        elif self.kind == "strlist":
            if not isinstance(v, list) or not 1 <= len(v) <= self.maxlen or any(not isinstance(x, str) for x in v): raise bad
            if self.choices and any(x not in self.choices for x in v): raise bad
        elif self.kind == "pair":
            if v is not None and (not isinstance(v, list) or len(v) != 2
                                  or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not self.lo <= x <= self.hi for x in v)):
                raise bad
        elif self.kind == "shapes":
            _check_shapes(name, v, self.maxlen)
        elif self.kind == "numdict":
            if not isinstance(v, dict) or len(v) > self.maxlen or any(
                    not isinstance(k, str) or len(k) > 16 or isinstance(x, bool) or not isinstance(x, (int, float)) or abs(x) > 1e6
                    for k, x in v.items()):
                raise bad
        else:
            raise AssertionError(self.kind)
        return v


SHAPE_TYPES = {"line": (2, 2), "polyline": (2, 64), "polygon": (3, 64), "rect": (2, 2), "circle": (1, 1),
               "marker": (1, 64), "arrow": (2, 2), "text": (1, 1), "scalebar": (1, 1)}
SHAPE_KEYS = {"type", "points", "r", "text", "ramp", "fill", "units"}


def _check_shapes(name: str, v, maxlen: int):
    """Annotation shapes (forge/annotate.py): at most `maxlen` shapes, each with a known type, the right number of
    points (at most 64), numbers within ±10⁴ and short ASCII text in the built-in font. Nothing here can hold an image."""
    from .forge.annotate import FONT
    if not isinstance(v, list) or len(v) > maxlen:
        raise ValueError(f"param {name!r}: a list of at most {maxlen} shapes")
    for k, s in enumerate(v):
        where = f"param {name!r}, shape {k}"
        if not isinstance(s, dict) or set(s) - SHAPE_KEYS or s.get("type") not in SHAPE_TYPES:
            raise ValueError(f"{where}: keys among {sorted(SHAPE_KEYS)}, type one of {sorted(SHAPE_TYPES)}")
        lo, hi = SHAPE_TYPES[s["type"]]
        pts = s.get("points")
        if (not isinstance(pts, list) or not lo <= len(pts) <= hi
                or any(not isinstance(q, list) or len(q) != 2 or any(isinstance(c, bool) or not isinstance(c, (int, float))
                       or not abs(c) <= 1e4 for c in q) for q in pts)):
            raise ValueError(f"{where}: {s['type']} takes {lo}..{hi} points [x, y] with |x|, |y| ≤ 10⁴")
        r = s.get("r", 1)
        if isinstance(r, bool) or not isinstance(r, (int, float)) or not 0 <= r <= 1e4:
            raise ValueError(f"{where}: r must be a number in [0, 10⁴]")
        t = s.get("text", "")
        if not isinstance(t, str) or len(t) > 48 or any(ch.upper() not in FONT for ch in t):
            raise ValueError(f"{where}: text is at most 48 characters of the built-in font (A-Z, 0-9, punctuation)")
        if s.get("ramp", "ink") not in DATA_RAMPS or not isinstance(s.get("fill", False), bool) \
                or s.get("units", "pixel") not in ("pixel", "unit"):
            raise ValueError(f"{where}: ramp one of the palette ramps, fill true/false, units pixel or unit")


@dataclass
class Generator:
    """A registered generator: name, version, kind, the function that draws, its parameter schema, the source
    files its output depends on (hashed into code_sha256), default and maximum size, and the input it reads."""
    name: str
    version: str
    kind: str                                   # "image" | "animation" | "midi"
    fn: Callable
    params: dict[str, P]
    modules: tuple[str, ...]                    # rutas relativas al paquete (fichero .py o carpeta)
    summary: str
    size: tuple[int, int] = (32, 32)            # tamaño por defecto (imágenes)
    max_size: int = 512
    data: str | None = None                     # "grid" | "points": the recipe names an input file
    _code: str | None = field(default=None, repr=False)

    def resolve(self, given: dict) -> dict:
        """Check the given parameters against the schema and return all of them, defaults filled in."""
        unknown = set(given) - set(self.params)
        if unknown:
            raise ValueError(f"{self.name}: unknown params {sorted(unknown)} (known: {sorted(self.params)})")
        return {k: spec.check(k, given[k]) if k in given else spec.default for k, spec in self.params.items()}

    def code_sha256(self) -> str:
        """SHA-256 del código fuente del que depende la salida (finales de línea normalizados a \\n)."""
        if self._code is None:
            files = set()
            for m in self.modules + ("rng.py", "fmath.py", "registry.py"):
                path = os.path.join(PKG, m)
                if os.path.isdir(path):
                    files |= {os.path.join(m, f) for f in os.listdir(path) if f.endswith(".py")}
                else:
                    files.add(m)
            h = hashlib.sha256()
            for rel in sorted(f.replace(os.sep, "/") for f in files):
                with open(os.path.join(PKG, rel), "rb") as fh:
                    h.update(rel.encode() + b"\0" + fh.read().replace(b"\r\n", b"\n") + b"\0")
            self._code = h.hexdigest()
        return self._code


RAMPS = ("stone", "moss", "sea", "ember", "sun", "dusk", "ink", "bone", "grey", "all")
DATA_RAMPS = RAMPS + ("seq", "div", "cyc", "paper", "mark")


def _data_params() -> dict:
    """Parameters shared by the data generators (forge/datavis.py)."""
    return {
        "mode": P("str", "value", choices=("value", "shade", "relief"),
                  doc="colour by value, hill-shade, or both (colour moved along its ramp by the shading)"),
        "ramp": P("str", "seq", choices=DATA_RAMPS, doc="the palette ramp values are mapped to, low to high"),
        "dither": P("str", "none", choices=("none", "bayer", "floyd", "atkinson"),
                    doc="between ramp steps: none (nearest step), ordered Bayer 8×8, or error diffusion"),
        "range": P("pair", None, -1e12, 1e12, doc="[low, high] of the colour scale; default: the data's finite min, max"),
        "contours": P("int", 0, 0, 64, doc="number of evenly spaced iso-lines inside the range"),
        "interval": P("float", 0.0, 0.0, 1e12, doc="iso-lines at every multiple of this value (overrides contours)"),
        "contour_ramp": P("str", "ink", choices=DATA_RAMPS),
        "azimuth": P("float", 315.0, 0.0, 360.0, doc="light direction, degrees clockwise from up (315 = top-left)"),
        "altitude": P("float", 45.0, 0.0, 90.0, doc="light elevation above the horizon, degrees"),
        "exaggeration": P("float", 1.0, 0.0, 1e6, doc="multiplies the values before shading: unit conversion to ground units × vertical exaggeration"),
        "cell": P("float", 1.0, 1e-9, 1e12, doc="ground size of one data cell (field) or data unit (scatter), in value units"),
        "relief": P("float", 2.0, 0.0, 8.0, doc="relief mode: ramp steps moved by full light or full shadow"),
        "nodata_ramp": P("str", "", choices=("",) + DATA_RAMPS, doc="colour for pixels without data; empty = transparent"),
    }


def _gens() -> dict[str, Generator]:
    from .forge import annotate, datavis, flora, icons, mathviz, motion, skies, sprites, tiles
    from .music import composer, generator as music_gen
    from .music.sources import SOURCES
    from .music.theory import MODES
    pix = ("pixel",)
    gens = [
        Generator("forge.tile.stone", "1", "image", tiles.stone, {
            "cells": P("int", 4, 1, 32, doc="slabs across the tile"),
            "jitter": P("float", 0.9, 0.0, 1.0, doc="0 = exact grid, 1 = free Voronoi"),
            "mortar": P("float", 0.10, 0.0, 0.6, doc="joint width (F2 − F1 threshold)"),
            "cracks": P("float", 0.4, 0.0, 1.0),
            "ramp": P("str", "stone", choices=RAMPS),
            "joint_ramp": P("str", "ink", choices=RAMPS),
        }, pix + ("forge/tiles.py",), "tileable Voronoi slabs with bevel, fBm grain and ridged cracks"),
        Generator("forge.tile.terrain", "1", "image", tiles.terrain, {
            "world_x": P("int", 0, -100000, 100000, doc="tile column in the world"),
            "world_y": P("int", 0, -100000, 100000, doc="tile row in the world"),
            "scale": P("float", 24.0, 2.0, 512.0, doc="pixels per noise unit"),
            "water": P("float", 0.40, 0.0, 1.0), "sand": P("float", 0.04, 0.0, 0.3),
            "forest": P("float", 0.62, 0.0, 1.0), "rock": P("float", 0.78, 0.0, 1.0),
        }, pix + ("forge/tiles.py",), "fBm terrain in world coordinates (seamless across tiles), Bayer band edges"),
        Generator("forge.tile.cave", "1", "image", tiles.cave, {
            "fill": P("float", 0.53, 0.0, 1.0), "steps": P("int", 4, 0, 12),
            "moss": P("float", 0.35, 0.0, 1.0),
            "ramp": P("str", "stone", choices=RAMPS), "floor_ramp": P("str", "stone", choices=RAMPS),
        }, pix + ("forge/tiles.py",), "tileable cellular-automaton caves with depth-shaded walls"),
        Generator("forge.sprite.critters", "1", "image", sprites.critters, {
            "cell": P("int", 16, 8, 64), "cols": P("int", 4, 1, 32), "count": P("int", 8, 1, 256),
            "ramps": P("strlist", ["moss", "sea", "ember", "sun", "dusk"], choices=RAMPS, maxlen=10),
            "variety": P("float", 0.12, 0.0, 0.5, doc="minimum signature distance between two critters"),
        }, pix + ("forge/sprites.py",), "a sheet of symmetric critters: probability mask, automaton, volume shading", (64, 32)),
        Generator("forge.icon.gem", "1", "image", icons.gem, {
            "shape": P("str", "round", choices=("round", "square", "diamond", "hex", "drop")),
            "facets": P("int", 8, 3, 24), "table": P("float", 0.45, 0.1, 0.9),
            "light_deg": P("float", 225.0, 0.0, 360.0, doc="direction of the light (225 = top-left)"),
            "ramp": P("str", "sea", choices=RAMPS),
        }, pix + ("forge/icons.py",), "SDF gem icon with angular facets", (16, 16)),
        Generator("forge.flora.tree", "1", "image", flora.tree, {
            "preset": P("str", "bush", choices=tuple(flora.PRESETS)), "iterations": P("int", 4, 1, 7),
            "angle": P("float", 24.0, 1.0, 90.0), "sway": P("float", 8.0, 0.0, 45.0),
            "leaf_size": P("float", 3.0, 0.0, 12.0), "foliage": P("float", 0.8, 0.0, 1.0),
            "wood_ramp": P("str", "stone", choices=RAMPS), "leaf_ramp": P("str", "moss", choices=RAMPS),
        }, pix + ("forge/flora.py",), "stochastic L-system tree with Vogel-spiral leaf clumps", (48, 48)),
        Generator("forge.sky.gradient", "1", "image", skies.sky, {
            "ramps": P("strlist", ["dusk", "ember"], choices=RAMPS, maxlen=4), "reverse": P("bool", False),
            "gamma": P("float", 1.0, 0.2, 5.0), "dither": P("str", "floyd", choices=("floyd", "atkinson", "bayer")),
            "star_gap": P("float", 6.0, 0.0, 64.0, doc="Poisson-disc radius between stars, 0 = none"),
            "star_band": P("float", 0.45, 0.0, 1.0, doc="top fraction of the sky that gets stars"),
        }, pix + ("forge/skies.py",), "palette-locked gradient sky (error diffusion or Bayer) with Poisson-disc stars", (64, 32)),
        Generator("forge.fractal.julia", "1", "image", skies.julia, {
            "preset": P("int", 0, 0, 63), "c": P("pair", None, -2.0, 2.0, doc="explicit c = [re, im]"),
            "zoom": P("float", 1.0, 0.1, 1000.0), "max_iter": P("int", 32, 4, 512),
            "ramp": P("str", "dusk", choices=RAMPS),
        }, pix + ("forge/skies.py",), "Julia set, escape time to a ramp with Bayer 8×8", (48, 48)),
        Generator("data.field", "1", "image", datavis.field, {
            **_data_params(),
            "resample": P("str", "bilinear", choices=("bilinear", "nearest"), doc="grid → output pixels"),
        }, pix + ("data", "forge/datavis.py"), "a gridded data field (CSV, PGM, NPY, JSON): colour scale, hill-shading, iso-lines",
            (256, 256), 2048, data="grid"),
        Generator("data.scatter", "1", "image", datavis.scatter, {
            **_data_params(),
            "method": P("str", "linear", choices=("linear", "nearest"),
                        doc="Delaunay piecewise-linear interpolation, or nearest sample (Voronoi cells)"),
            "points": P("str", "none", choices=("none", "dot", "cross"), doc="mark the samples"),
            "point_ramp": P("str", "mark", choices=DATA_RAMPS),
        }, pix + ("data", "forge/datavis.py"), "scattered samples (x, y, value) reconstructed on the raster (exact Delaunay)",
            (256, 256), 2048, data="points"),
        Generator("anim.life", "1", "animation", motion.life, {
            "rule": P("text", "B3/S23", maxlen=24, doc="Life-like rule: birth and survival neighbour counts, e.g. B36/S23"),
            "pattern": P("str", "random", choices=("random",) + tuple(motion.PATTERNS), doc="random soup or a classic pattern"),
            "fill": P("float", 0.35, 0.0, 1.0, doc="random soup: probability that a cell starts alive"),
            "box": P("float", 0.5, 0.0, 1.0, doc="random soup: side of the seeded central box, as a fraction of the board"),
            "wrap": P("bool", True, doc="torus (edges join) or a bounded board"),
            "frames": P("int", 60, 1, 1000), "every": P("int", 1, 1, 64, doc="generations per frame"),
            "delay": P("int", 80, 20, 5000, doc="milliseconds per frame (multiple of 10)"),
            "ramp": P("str", "seq", choices=DATA_RAMPS, doc="live cells by age: newborn at the bright end"),
            "age_step": P("int", 2, 1, 1000, doc="generations per ramp step"),
            "background": P("str", "ink", choices=("",) + DATA_RAMPS, doc="dead cells; empty = transparent"),
        }, pix + ("forge/motion.py", "data"), "Life-like cellular automata, any B/S rule, coloured by age", (96, 64), 1024),
        Generator("anim.wave", "1", "animation", motion.wave, {
            "scene": P("str", "double-slit", choices=("double-slit", "single-slit", "point", "two-sources")),
            "speed": P("float", 0.5, 0.05, 0.7, doc="Courant number c·dt/dx (stable up to 1/√2)"),
            "period": P("float", 12.0, 3.0, 200.0, doc="source period in time steps"),
            "separation": P("float", 16.0, 1.0, 1000.0, doc="slit or source separation, in cells"),
            "opening": P("float", 4.0, 1.0, 1000.0, doc="slit width, in cells"),
            "sponge": P("int", 10, 1, 200, doc="width of the absorbing border, in cells"),
            "contrast": P("float", 1.5, 0.1, 100.0, doc="amplitude 1/contrast reaches the ends of the ramp"),
            "frames": P("int", 60, 1, 1000), "every": P("int", 4, 1, 64, doc="time steps per frame"),
            "delay": P("int", 60, 20, 5000), "ramp": P("str", "div", choices=DATA_RAMPS),
            "wall_ramp": P("str", "ink", choices=DATA_RAMPS),
        }, pix + ("forge/motion.py", "data"), "the 2-D wave equation (leapfrog): slits, diffraction, interference", (128, 80), 1024),
        Generator("anim.lorenz", "1", "animation", motion.lorenz, {
            "sigma": P("float", 10.0, 0.0, 100.0), "rho": P("float", 28.0, 0.0, 200.0), "beta": P("float", 8.0 / 3.0, 0.0, 20.0),
            "start": P("pair", [1.0, 1.0], -100.0, 100.0, doc="initial x, y"), "start_z": P("float", 1.0, -100.0, 200.0),
            "dt": P("float", 0.005, 1e-5, 0.05, doc="RK4 time step"),
            "warmup": P("int", 2600, 0, 1000000, doc="steps run before the first frame (from (1, 1, 1) the orbit circles one "
                        "focus until t ≈ 13.5 before it starts to switch wings)"),
            "steps_per_frame": P("int", 20, 1, 1000), "trail": P("int", 2500, 2, 100000, doc="steps kept in the trail"),
            "view": P("str", "xz", choices=("xz", "xy", "yz")),
            "frames": P("int", 120, 1, 1000), "delay": P("int", 40, 20, 5000),
            "ramp": P("str", "seq", choices=DATA_RAMPS), "head_ramp": P("str", "mark", choices=DATA_RAMPS),
            "background": P("str", "ink", choices=("",) + DATA_RAMPS),
        }, pix + ("forge/motion.py", "data"), "the Lorenz attractor by Runge-Kutta 4, drawn as a fading trail", (128, 128), 1024),
        Generator("anim.diffuse", "1", "animation", motion.diffuse, {
            "alpha": P("float", 0.2, 0.0, 0.25, doc="diffusion number α·dt/dx² (stable up to 1/4)"),
            "frames": P("int", 40, 1, 1000), "every": P("int", 10, 1, 1000, doc="time steps per frame"),
            "delay": P("int", 80, 20, 5000), "ramp": P("str", "seq", choices=DATA_RAMPS),
            "range": P("pair", None, -1e12, 1e12, doc="[low, high] of the colour scale; default: the first frame's min, max"),
        }, pix + ("forge/motion.py", "data"), "the heat equation run on a data grid: its own diffusion, frame by frame",
            (128, 128), 1024, data="grid"),
        Generator("compose", "1", "image", None, {},
                  ("render.py",), "stack image layers (any image generator, data included) with over / under / mask",
                  (256, 256), 2048),
        Generator("draw.annotate", "1", "image", annotate.annotate, {
            "shapes": P("shapes", [], maxlen=64, doc="lines, arrows, rectangles, circles, markers, text, scale bars"),
        }, pix + ("forge/annotate.py",), "vector annotations on a transparent canvas (the top layer of a figure)",
            (256, 256), 2048),
        Generator("math.domain", "1", "image", mathviz.domain, {
            "function": P("str", "(z^2-1)(z-2-i)^2/(z^2+2+2i)", choices=tuple(mathviz.FUNCTIONS)),
            "centre": P("pair", [0.0, 0.0], -1e6, 1e6, doc="centre of the view in the complex plane"),
            "span": P("float", 6.0, 1e-9, 1e6, doc="width of the view"),
            "modulus_lines": P("bool", True, doc="iso-lines of |f| at powers of two"),
            "ramp": P("str", "cyc", choices=DATA_RAMPS, doc="cyclic ramp for the phase"),
            "line_ramp": P("str", "ink", choices=DATA_RAMPS),
        }, pix + ("forge/mathviz.py", "data"), "enhanced phase portrait of a complex function (Wegert)", (256, 256), 2048),
        Generator("math.logistic", "1", "image", mathviz.logistic, {
            "r": P("pair", [2.8, 4.0], 0.0, 4.0, doc="range of the parameter r, one column each"),
            "x": P("pair", [0.0, 1.0], 0.0, 1.0, doc="range of x shown, bottom to top"),
            "x0": P("float", 0.5, 0.0, 1.0), "warmup": P("int", 600, 0, 100000), "samples": P("int", 400, 1, 100000),
            "ramp": P("str", "seq", choices=DATA_RAMPS), "background": P("str", "ink", choices=("",) + DATA_RAMPS),
        }, pix + ("forge/mathviz.py", "data"), "bifurcation diagram of the logistic map", (320, 200), 2048),
        Generator("math.ulam", "1", "image", mathviz.ulam, {
            "mode": P("str", "primes", choices=("primes", "residue")),
            "modulus": P("int", 6, 2, 64, doc="residue mode: colour n by n mod m"),
            "ramp": P("str", "seq", choices=DATA_RAMPS), "background": P("str", "ink", choices=("",) + DATA_RAMPS),
        }, pix + ("forge/mathviz.py",), "the Ulam spiral: primes, or residues mod m", (201, 201), 2048),
        Generator("math.modmult", "1", "image", mathviz.modmult, {
            "n": P("int", 200, 2, 5000, doc="points on the circle"), "k": P("float", 2.0, 0.0, 1000.0, doc="multiplier"),
            "ramp": P("str", "seq", choices=DATA_RAMPS), "background": P("str", "ink", choices=("",) + DATA_RAMPS),
            "circle_ramp": P("str", "", choices=("",) + DATA_RAMPS),
        }, pix + ("forge/mathviz.py",), "chords j → k·j mod n on a circle (cardioid, nephroid, …)", (256, 256), 2048),
        Generator("data.image", "1", "image", datavis.image, {
            "resample": P("str", "area", choices=("area", "nearest"),
                          doc="area: exact area-weighted mean in linear light; nearest: the source pixel under each centre"),
            "dither": P("str", "floyd", choices=("none", "bayer", "floyd"),
                        doc="nearest palette colour directly, after a Bayer 8×8 offset, or with Floyd–Steinberg diffusion"),
            "spread": P("float", 48.0, 0.0, 255.0, doc="Bayer: size of the offset, in 0..255 units"),
            "ramp": P("str", "all", choices=DATA_RAMPS, doc="the palette colours a pixel may take"),
            "edges": P("bool", False, doc="draw a Sobel outline where OKLab lightness changes fast"),
            "edge_threshold": P("float", 0.25, 0.0, 10.0, doc="gradient of OKLab lightness above which a pixel is an edge"),
            "edge_ramp": P("str", "ink", choices=DATA_RAMPS),
        }, pix + ("data", "forge/datavis.py"), "a true-colour picture (PNG, PPM) resampled and quantised to the palette",
            (128, 128), 2048, data="image"),
        Generator("math.fourier", "1", "image", mathviz.fourier, {
            "wave": P("str", "square", choices=("square", "sawtooth", "triangle")),
            "orders": P("text", "1,3,9,27", maxlen=64, doc="comma-separated numbers of terms, one curve each (1..2000)"),
            "ramp": P("str", "seq", choices=DATA_RAMPS), "axis_ramp": P("str", "grey", choices=DATA_RAMPS),
            "background": P("str", "ink", choices=("",) + DATA_RAMPS),
        }, pix + ("forge/mathviz.py",), "Fourier partial sums of a square, sawtooth or triangle wave (Gibbs phenomenon)",
            (320, 200), 2048),
        Generator("anim.epicycles", "1", "animation", motion.epicycles, {
            "curve": P("str", "heart", choices=motion.CURVES),
            "samples": P("int", 256, 8, 1024, doc="points of the curve, and size of the DFT"),
            "terms": P("int", 24, 1, 1024, doc="largest coefficients kept, one circle each"),
            "frames": P("int", 120, 1, 1000), "delay": P("int", 40, 20, 5000),
            "ramp": P("str", "seq", choices=DATA_RAMPS), "circle_ramp": P("str", "grey", choices=DATA_RAMPS),
            "curve_ramp": P("str", "grey", choices=DATA_RAMPS), "background": P("str", "ink", choices=("",) + DATA_RAMPS),
        }, pix + ("forge/motion.py",), "a closed curve drawn by epicycles: its discrete Fourier transform, term by term",
            (192, 192), 1024),
        Generator("anim.frames", "1", "animation", motion.frames, {
            "ramp": P("str", "seq", choices=DATA_RAMPS),
            "range": P("pair", None, -1e12, 1e12, doc="[low, high] of the colour scale; default: min, max over all frames"),
            "delay": P("int", 100, 20, 5000),
        }, pix + ("forge/motion.py", "data"), "a sequence of grids computed elsewhere (e.g. by Lean), frame by frame",
            (64, 64), 1024, data="frames"),
        Generator("music.piece", "1", "midi", music_gen.piece, {
            "title": P("text", "Untitled", maxlen=64), "text": P("text", "", maxlen=200),
            "copyright": P("text", "", maxlen=120),
            "source": P("str", "pisano", choices=tuple(SOURCES)), "args": P("numdict", {}, maxlen=4),
            "mode": P("str", "dorian", choices=tuple(MODES)), "tonic": P("int", 62, 36, 84),
            "bpm": P("int", 96, 30, 220), "meter": P("str", "4/4", choices=tuple(composer.METERS)),
            "bars": P("int", 16, 8, 64), "ensemble": P("str", "forest", choices=tuple(composer.ENSEMBLES)),
            "density": P("str", "flow", choices=tuple(composer.DENSITY)), "lush": P("bool", True),
            "perc": P("str", "", choices=("", "hand")),
            "kind": P("str", "day", choices=("day", "night", "combat")),
        }, ("music",), "a looping piece from a mathematical sequence: harmonised by dynamic programming, optimal voice leading"),
    ]
    return {g.name: g for g in gens}


_REG: dict[str, Generator] | None = None


def all_generators() -> dict[str, Generator]:
    """Every registered generator by name (built on first use)."""
    global _REG
    if _REG is None:
        _REG = _gens()
    return _REG


def get(name: str) -> Generator:
    """The generator called `name`; ValueError listing the known names if there is none."""
    reg = all_generators()
    if name not in reg:
        raise ValueError(f"unknown generator {name!r} (known: {', '.join(reg)})")
    return reg[name]
