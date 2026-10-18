"""
Data input in standard formats / entrada de datos en formatos estándar.

Two shapes of data, each from several standard formats, all read with the standard library only:

  grid    a regular 2-D field of numbers (rows from top to bottom)
            .csv / .tsv / .txt   numbers separated by commas, semicolons, tabs or spaces; `#` starts a comment; empty fields,
                                 `nan` and `NA` are missing values
            .pgm                 Netpbm greymap, ASCII (P2) or binary (P5), 8 or 16 bits (big-endian, as the format says)
            .npy                 NumPy array file, format 1.0–3.0, 2-D, C or Fortran order; float16/32/64, signed and
                                 unsigned integers of 1–8 bytes, either byte order, bool (no pickled objects)
            .json                {"values": [[…], …]} or a bare list of rows; `null` is a missing value
  points  scattered samples (x, y, value)
            .csv / .tsv / .txt   three columns, an optional header row of names
            .json                {"points": [[x, y, v], …]} or {"x": […], "y": […], "value": […]}
  image   a true-colour picture to convert to palette pixels (data.image)
            .png                 8-bit grey, grey + alpha, RGB, RGBA or indexed, non-interlaced
            .ppm                 Netpbm pixmap, ASCII (P3) or binary (P6), 8 bits
  frames  a sequence of grids of the same shape (a simulation computed elsewhere, e.g. by a Lean program)
            .json                {"frames": [[[…], …], …]}; any other keys (a "source", a "theorem") are kept as metadata

The reader is chosen by `format` or else by the file extension. A file is data, never code: nothing is evaluated, object
arrays are refused, and sizes are capped (`MAX_CELLS`, `MAX_POINTS`, `MAX_BYTES`).

Every number is parsed by Python's `float`/`int`, which round correctly on every platform, so the same file gives the same
doubles everywhere. The recipe pins the file by its SHA-256.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import re
import struct
from dataclasses import dataclass

MAX_BYTES = 64 * 1024 * 1024
MAX_CELLS = 4096 * 4096
MAX_POINTS = 200_000

GRID_FORMATS = ("csv", "pgm", "npy", "json")
POINT_FORMATS = ("csv", "json")
FRAME_FORMATS = ("json",)
IMAGE_FORMATS = ("png", "ppm")
FORMATS = {"grid": GRID_FORMATS, "points": POINT_FORMATS, "frames": FRAME_FORMATS, "image": IMAGE_FORMATS}
MAX_IMAGE_PIXELS = 4096 * 4096
MAX_FRAMES = 1000
_EXT = {".csv": "csv", ".tsv": "csv", ".txt": "csv", ".pgm": "pgm", ".npy": "npy", ".json": "json", ".png": "png",
        ".ppm": "ppm"}
_MISSING = {"", "nan", "NaN", "NAN", "NA", "na", "null", "None"}


class DataError(ValueError):
    """A data file that cannot be read as asked; the message names the file and the reason."""
    pass


@dataclass
class Grid:
    """`values[y][x]`, y = 0 at the top. Missing values are NaN."""
    width: int
    height: int
    values: list[list[float]]

    def finite(self):
        """The values that are not missing, row by row."""
        for row in self.values:
            for v in row:
                if v == v:
                    yield v

    def describe(self) -> dict:
        vals = list(self.finite())
        return {"shape": [self.height, self.width], "missing": self.width * self.height - len(vals),
                "min": min(vals) if vals else None, "max": max(vals) if vals else None}


@dataclass
class Points:
    """Scattered samples: parallel lists of x, y and value."""
    xs: list[float]
    ys: list[float]
    vs: list[float]

    def __len__(self):
        return len(self.xs)

    def describe(self) -> dict:
        return {"points": len(self.xs), "min": min(self.vs), "max": max(self.vs),
                "x": [min(self.xs), max(self.xs)], "y": [min(self.ys), max(self.ys)]}


def sha256_file(path: str) -> str:
    """Hex SHA-256 of a file's bytes, read in 1 MiB chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def format_of(path: str, fmt: str | None = None) -> str:
    """The reader to use: `fmt` if given, else the one for the file's extension."""
    if fmt:
        return fmt
    ext = os.path.splitext(path)[1].lower()
    if ext not in _EXT:
        raise DataError(f"{path}: unknown data format (give 'format', or use one of {', '.join(sorted(_EXT))})")
    return _EXT[ext]


def _read(path: str) -> bytes:
    size = os.path.getsize(path)
    if size > MAX_BYTES:
        raise DataError(f"{path}: {size} bytes is more than the {MAX_BYTES}-byte limit")
    with open(path, "rb") as fh:
        return fh.read()


def _num(tok: str, where: str) -> float:
    t = tok.strip()
    if t in _MISSING:
        return math.nan
    try:
        v = float(t)
    except ValueError:
        raise DataError(f"{where}: {tok!r} is not a number") from None
    if math.isinf(v):
        raise DataError(f"{where}: infinite value")
    return v


def _check_grid(rows: list[list[float]], path: str) -> Grid:
    if not rows or not rows[0]:
        raise DataError(f"{path}: no data")
    w = len(rows[0])
    for i, r in enumerate(rows):
        if len(r) != w:
            raise DataError(f"{path}: row {i + 1} has {len(r)} values, the first row has {w}")
    if w * len(rows) > MAX_CELLS:
        raise DataError(f"{path}: {w}×{len(rows)} cells is more than the limit of {MAX_CELLS}")
    if not any(v == v for r in rows for v in r):
        raise DataError(f"{path}: every value is missing")
    return Grid(w, len(rows), rows)


# ------------------------------------------------------------------------------------------------ text tables

_SPLIT = re.compile(r"\s*[,;\t]\s*|\s+")


def _table(text: str):
    """Rows of tokens; the separator is the first of `,` `;` tab found in the first data line, else whitespace."""
    lines = [ln.split("#", 1)[0].strip() for ln in text.splitlines()]
    lines = [(i + 1, ln) for i, ln in enumerate(lines) if ln]
    if not lines:
        return []
    first = lines[0][1]
    sep = next((s for s in (",", ";", "\t") if s in first), None)
    out = []
    for n, ln in lines:
        toks = [t.strip() for t in ln.split(sep)] if sep else ln.split()
        out.append((n, toks))
    return out


def read_grid_csv(path: str) -> Grid:
    """A grid from a delimited text file (comma, semicolon, tab or spaces; '#' comments; empty/nan/NA missing)."""
    text = _read(path).decode("utf-8-sig")
    rows = [[_num(t, f"{path}:{n}") for t in toks] for n, toks in _table(text)]
    return _check_grid(rows, path)


def read_points_csv(path: str) -> Points:
    """Scattered points from three delimited columns x, y, value, with an optional header row."""
    text = _read(path).decode("utf-8-sig")
    table = _table(text)
    if table and not _is_number(table[0][1][0]):
        table = table[1:]                       # header row of names
    xs, ys, vs = [], [], []
    for n, toks in table:
        if len(toks) != 3:
            raise DataError(f"{path}:{n}: a point needs three columns (x, y, value), found {len(toks)}")
        x, y, v = (_num(t, f"{path}:{n}") for t in toks)
        if x != x or y != y or v != v:
            raise DataError(f"{path}:{n}: a scattered sample cannot have a missing coordinate or value")
        xs.append(x); ys.append(y); vs.append(v)
    return _check_points(xs, ys, vs, path)


def _is_number(tok: str) -> bool:
    try:
        float(tok)
        return True
    except ValueError:
        return tok.strip() in _MISSING


def _check_points(xs, ys, vs, path) -> Points:
    if len(xs) < 3:
        raise DataError(f"{path}: at least 3 points are needed, found {len(xs)}")
    if len(xs) > MAX_POINTS:
        raise DataError(f"{path}: {len(xs)} points is more than the limit of {MAX_POINTS}")
    seen = set()
    for x, y in zip(xs, ys):
        if (x, y) in seen:
            raise DataError(f"{path}: duplicate point ({x!r}, {y!r})")
        seen.add((x, y))
    return Points(xs, ys, vs)


# ------------------------------------------------------------------------------------------------ Netpbm (PGM)

def read_pgm(path: str) -> Grid:
    """A grid from a Netpbm greymap, ASCII (P2) or binary (P5), 8 or 16 bits (big-endian)."""
    data = _read(path)
    magic = data[:2]
    if magic not in (b"P2", b"P5"):
        raise DataError(f"{path}: not a PGM file (P2 or P5)")
    pos, head = 2, []
    while len(head) < 3:                         # width, height, maxval; comments run to the end of the line
        while pos < len(data) and data[pos:pos + 1].isspace():
            pos += 1
        if data[pos:pos + 1] == b"#":
            while pos < len(data) and data[pos:pos + 1] not in (b"\n", b"\r"):
                pos += 1
            continue
        start = pos
        while pos < len(data) and data[pos:pos + 1].isdigit():
            pos += 1
        if start == pos:
            raise DataError(f"{path}: bad PGM header")
        head.append(int(data[start:pos]))
    w, h, maxval = head
    if not (w > 0 and h > 0 and 0 < maxval < 65536):
        raise DataError(f"{path}: bad PGM size or maxval")
    if w * h > MAX_CELLS:
        raise DataError(f"{path}: {w}×{h} cells is more than the limit of {MAX_CELLS}")
    if magic == b"P5":
        pos += 1                                 # exactly one whitespace byte before the raster
        nb = 1 if maxval < 256 else 2
        raw = data[pos:pos + w * h * nb]
        if len(raw) != w * h * nb:
            raise DataError(f"{path}: the raster is truncated")
        vals = list(raw) if nb == 1 else list(struct.unpack(f">{w * h}H", raw))
    else:
        toks = data[pos:].split()
        if len(toks) < w * h:
            raise DataError(f"{path}: {len(toks)} samples, expected {w * h}")
        vals = [int(t) for t in toks[:w * h]]
    if any(v > maxval for v in vals):
        raise DataError(f"{path}: a sample is larger than maxval {maxval}")
    rows = [[float(v) for v in vals[y * w:(y + 1) * w]] for y in range(h)]
    return Grid(w, h, rows)


# ------------------------------------------------------------------------------------------------ NumPy .npy

_NPY_KINDS = {"f": {2: "e", 4: "f", 8: "d"}, "i": {1: "b", 2: "h", 4: "i", 8: "q"}, "u": {1: "B", 2: "H", 4: "I", 8: "Q"},
              "b": {1: "?"}}


def read_npy(path: str) -> Grid:
    """A grid from a NumPy .npy file (format 1–3, 2-D, C or Fortran order, numeric or bool dtype, either byte
    order). The header is parsed as a literal, never executed; object and structured arrays are refused."""
    data = _read(path)
    if data[:6] != b"\x93NUMPY":
        raise DataError(f"{path}: not a .npy file")
    major = data[6]
    if major == 1:
        hlen, start = struct.unpack("<H", data[8:10])[0], 10
    elif major in (2, 3):
        hlen, start = struct.unpack("<I", data[8:12])[0], 12
    else:
        raise DataError(f"{path}: .npy format {major} is not supported")
    header = data[start:start + hlen].decode("latin-1" if major < 3 else "utf-8")
    try:
        meta = ast.literal_eval(header.strip())   # a Python literal (dict of str/bool/tuple): evaluated, never executed
    except (ValueError, SyntaxError):
        raise DataError(f"{path}: bad .npy header") from None
    if not isinstance(meta, dict) or set(meta) != {"descr", "fortran_order", "shape"}:
        raise DataError(f"{path}: bad .npy header")
    descr, fortran, shape = meta["descr"], meta["fortran_order"], meta["shape"]
    if not isinstance(descr, str) or len(descr) < 3 or descr[0] not in "<>|=":
        raise DataError(f"{path}: unsupported dtype {descr!r} (structured and object arrays are refused)")
    kind, size = descr[1], int(descr[2:]) if descr[2:].isdigit() else -1
    code = _NPY_KINDS.get(kind, {}).get(size)
    if code is None:
        raise DataError(f"{path}: unsupported dtype {descr!r}")
    order = ">" if descr[0] == ">" else "<"
    if not (isinstance(shape, tuple) and len(shape) == 2 and all(isinstance(n, int) and n > 0 for n in shape)):
        raise DataError(f"{path}: a grid must be a 2-D array, the shape is {shape!r}")
    h, w = shape
    if w * h > MAX_CELLS:
        raise DataError(f"{path}: {w}×{h} cells is more than the limit of {MAX_CELLS}")
    body = data[start + hlen:]
    if len(body) != w * h * size:
        raise DataError(f"{path}: {len(body)} data bytes, expected {w * h * size}")
    flat = struct.unpack(f"{order}{w * h}{code}", body)
    if fortran:
        rows = [[float(flat[x * h + y]) for x in range(w)] for y in range(h)]
    else:
        rows = [[float(v) for v in flat[y * w:(y + 1) * w]] for y in range(h)]
    if any(math.isinf(v) for r in rows for v in r):
        raise DataError(f"{path}: infinite value")
    return _check_grid(rows, path)


def write_npy(path: str, rows: list[list[float]]):
    """Little-endian float64, C order, format 1.0 (what numpy.save writes for such an array)."""
    h, w = len(rows), len(rows[0])
    header = "{'descr': '<f8', 'fortran_order': False, 'shape': (%d, %d), }" % (h, w)
    pad = 64 - (10 + len(header) + 1) % 64
    header = header + " " * (pad % 64) + "\n"
    with open(path, "wb") as fh:
        fh.write(b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header.encode("latin-1"))
        fh.write(struct.pack(f"<{w * h}d", *(v for r in rows for v in r)))


def write_pgm(path: str, rows: list[list[int]], maxval: int):
    """Write a binary (P5) greymap; 16-bit big-endian when maxval > 255."""
    h, w = len(rows), len(rows[0])
    fmt = ">%dH" % w if maxval > 255 else "%dB" % w
    with open(path, "wb") as fh:
        fh.write(b"P5\n%d %d\n%d\n" % (w, h, maxval))
        for r in rows:
            fh.write(struct.pack(fmt, *r))


# ------------------------------------------------------------------------------------------------ JSON

def _json_num(v, where):
    if v is None:
        return math.nan
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise DataError(f"{where}: {v!r} is not a number")
    return _num(repr(float(v)), where)


def read_grid_json(path: str) -> Grid:
    """A grid from {"values": [[…], …]} or a bare list of rows; null is a missing value."""
    obj = json.loads(_read(path).decode("utf-8"))
    rows = obj.get("values") if isinstance(obj, dict) else obj
    if not isinstance(rows, list) or not all(isinstance(r, list) for r in rows):
        raise DataError(f"{path}: expected {{\"values\": [[…], …]}} or a list of rows")
    return _check_grid([[_json_num(v, path) for v in r] for r in rows], path)


def read_points_json(path: str) -> Points:
    """Points from {"points": [[x, y, v], …]} or {"x": […], "y": […], "value": […]}."""
    obj = json.loads(_read(path).decode("utf-8"))
    if isinstance(obj, dict) and "points" in obj:
        pts = obj["points"]
        if not isinstance(pts, list) or any(not isinstance(p, list) or len(p) != 3 for p in pts):
            raise DataError(f"{path}: 'points' must be a list of [x, y, value]")
        cols = list(zip(*pts)) if pts else ([], [], [])
    elif isinstance(obj, dict) and {"x", "y", "value"} <= set(obj):
        cols = (obj["x"], obj["y"], obj["value"])
        if len({len(c) for c in cols}) != 1:
            raise DataError(f"{path}: x, y and value have different lengths")
    else:
        raise DataError(f"{path}: expected {{\"points\": [[x, y, v], …]}} or {{\"x\": […], \"y\": […], \"value\": […]}}")
    xs, ys, vs = ([_json_num(v, path) for v in c] for c in cols)
    if any(v != v for v in xs + ys + vs):
        raise DataError(f"{path}: a scattered sample cannot have a missing coordinate or value")
    return _check_points(xs, ys, vs, path)


@dataclass
class Frames:
    """A sequence of grids of one shape, plus the file's other top-level keys (text metadata such as its source)."""
    grids: list[Grid]
    meta: dict

    def describe(self) -> dict:
        g = self.grids[0]
        vals = [v for grid in self.grids for v in grid.finite()]
        return {"frames": len(self.grids), "shape": [g.height, g.width], "min": min(vals), "max": max(vals)}


def read_frames_json(path: str) -> Frames:
    """A sequence of equal-shaped grids from {"frames": [[[…], …], …]}, keeping the file's other scalar keys."""
    obj = json.loads(_read(path).decode("utf-8"))
    if not isinstance(obj, dict) or not isinstance(obj.get("frames"), list) or not obj["frames"]:
        raise DataError(f"{path}: expected {{\"frames\": [[[…], …], …]}}")
    if len(obj["frames"]) > MAX_FRAMES:
        raise DataError(f"{path}: {len(obj['frames'])} frames is more than the limit of {MAX_FRAMES}")
    grids = []
    for k, rows in enumerate(obj["frames"]):
        if not isinstance(rows, list) or not all(isinstance(r, list) for r in rows):
            raise DataError(f"{path}: frame {k} is not a list of rows")
        g = _check_grid([[_json_num(v, f"{path} frame {k}") for v in r] for r in rows], f"{path} frame {k}")
        if grids and (g.width, g.height) != (grids[0].width, grids[0].height):
            raise DataError(f"{path}: frame {k} is {g.width}×{g.height}, frame 0 is {grids[0].width}×{grids[0].height}")
        grids.append(g)
    if sum(g.width * g.height for g in grids) > MAX_CELLS:
        raise DataError(f"{path}: more than {MAX_CELLS} cells in all")
    meta = {k: v for k, v in obj.items() if k != "frames" and isinstance(v, (str, int, float, bool))}
    return Frames(grids, meta)


@dataclass
class Image:
    """A decoded picture: width, height and RGBA8 bytes, row 0 at the top."""
    width: int
    height: int
    rgba: bytes

    def describe(self) -> dict:
        opaque = sum(1 for i in range(3, len(self.rgba), 4) if self.rgba[i] >= 128)
        return {"shape": [self.height, self.width], "opaque": opaque}


def _check_image(w, h, rgba, path) -> Image:
    if w * h > MAX_IMAGE_PIXELS:
        raise DataError(f"{path}: {w}×{h} pixels is more than the limit of {MAX_IMAGE_PIXELS}")
    return Image(w, h, rgba)


def read_png(path: str) -> Image:
    """An 8-bit, non-interlaced PNG of any colour type (decoded by exactfig's own reader)."""
    from ..pixel import png
    data = _read(path)
    try:
        w, h, rgba = png.decode(data)
    except (ValueError, KeyError, IndexError) as ex:
        raise DataError(f"{path}: {ex}") from None
    return _check_image(w, h, rgba, path)


def read_ppm(path: str) -> Image:
    """A Netpbm pixmap, ASCII (P3) or binary (P6), with maxval up to 255 (scaled to 0..255)."""
    data = _read(path)
    magic = data[:2]
    if magic not in (b"P3", b"P6"):
        raise DataError(f"{path}: not a PPM file (P3 or P6)")
    pos, head = 2, []
    while len(head) < 3:
        while pos < len(data) and data[pos:pos + 1].isspace():
            pos += 1
        if data[pos:pos + 1] == b"#":
            while pos < len(data) and data[pos:pos + 1] not in (b"\n", b"\r"):
                pos += 1
            continue
        start = pos
        while pos < len(data) and data[pos:pos + 1].isdigit():
            pos += 1
        if start == pos:
            raise DataError(f"{path}: bad PPM header")
        head.append(int(data[start:pos]))
    w, h, maxval = head
    if not (w > 0 and h > 0 and 0 < maxval < 256):
        raise DataError(f"{path}: only 8-bit PPM (maxval ≤ 255) is read")
    if w * h > MAX_IMAGE_PIXELS:
        raise DataError(f"{path}: {w}×{h} pixels is more than the limit of {MAX_IMAGE_PIXELS}")
    if magic == b"P6":
        raw = data[pos + 1:pos + 1 + 3 * w * h]
        if len(raw) != 3 * w * h:
            raise DataError(f"{path}: the raster is truncated")
        vals = list(raw)
    else:
        toks = data[pos:].split()
        if len(toks) < 3 * w * h:
            raise DataError(f"{path}: {len(toks)} samples, expected {3 * w * h}")
        vals = [int(t) for t in toks[:3 * w * h]]
    if any(v > maxval for v in vals):
        raise DataError(f"{path}: a sample is larger than maxval {maxval}")
    out = bytearray()
    for i in range(0, len(vals), 3):
        out += bytes(v * 255 // maxval for v in vals[i:i + 3]) + b"\xff"
    return Image(w, h, bytes(out))


# ------------------------------------------------------------------------------------------------ entry point

def load(path: str, shape: str, fmt: str | None = None):
    """Read `path` as a `grid`, `points`, `frames` or an `image`."""
    f = format_of(path, fmt)
    if shape == "grid":
        readers = {"csv": read_grid_csv, "pgm": read_pgm, "npy": read_npy, "json": read_grid_json}
    elif shape == "points":
        readers = {"csv": read_points_csv, "json": read_points_json}
    elif shape == "frames":
        readers = {"json": read_frames_json}
    elif shape == "image":
        readers = {"png": read_png, "ppm": read_ppm}
    else:
        raise AssertionError(shape)
    if f not in readers:
        raise DataError(f"{path}: {f!r} cannot hold {shape} data (use one of {', '.join(readers)})")
    return readers[f](path)
