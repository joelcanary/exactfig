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
  patterns a catalogue of cell patterns (e.g. every still life of n cells of a Life-like rule, listed by a search program)
            catalog (any extension, `format` must say so)   one pattern per line, its rows separated by spaces, `O` or `*`
                                 alive and `.` dead, optionally preceded by `WxH:`, which is then checked; `#` or `!`
                                 starts a comment line
  instances instance masks of one image (segmentation): the ground truth and, optionally, a prediction
            instances (a .json file, `format` must say so)  {"width": W, "height": H, "truth": [mask, …],
                                 "prediction": [mask, …], "meta": {"date": "…", …}}; a mask is COCO run-length encoding
                                 {"size": [H, W], "counts": [ …] or "compressed string"} or {"cells": [[x, y], …]}
  colorings colourings of 1..n (e.g. a SAT solver's witness that 1..n can be coloured without a monochromatic
            arithmetic progression, or split into sum-free sets)
            coloring (any extension, `format` must say so)  one colouring per line: either one digit per number
                                 (`0112…`, colours 0-9) or numbers separated by spaces or commas; `#` or `!` starts a
                                 comment line

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
PATTERN_FORMATS = ("catalog",)
COLORING_FORMATS = ("coloring",)
INSTANCE_FORMATS = ("instances",)
FORMATS = {"grid": GRID_FORMATS, "points": POINT_FORMATS, "frames": FRAME_FORMATS, "image": IMAGE_FORMATS,
           "patterns": PATTERN_FORMATS, "colorings": COLORING_FORMATS, "instances": INSTANCE_FORMATS}
MAX_INSTANCE_PIXELS = 2048 * 2048
MAX_INSTANCES = 10_000
MAX_COLORING = 5000
MAX_COLORS = 64
MAX_PATTERNS = 100_000
MAX_PATTERN_SIDE = 256
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


def decode_text(raw: bytes, path: str) -> str:
    """Text of a file: UTF-8 with or without a BOM (Notepad writes one), or UTF-16 with its BOM (what `>` writes in
    Windows PowerShell 5). Anything else is refused with a message that says how to fix it."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError:
            raise DataError(f"{path}: damaged UTF-16 text; save it as UTF-8") from None
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as ex:
        raise DataError(f"{path}: not UTF-8 text (byte {ex.start} is 0x{raw[ex.start]:02x}); save it as UTF-8") from None


def read_text(path: str) -> str:
    """`decode_text` of a file, within the size limit."""
    return decode_text(_read(path), path)


def _json(path: str):
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as ex:
        raise DataError(f"{path}: not valid JSON ({ex.msg}, line {ex.lineno}, column {ex.colno})") from None


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
        hint = (" (decimal commas are not read: write 1.5, not 1,5, and separate columns with ';' or tabs only if "
                "the decimals use a point)") if re.search(r"[0-9],[0-9]", t) or re.search(r"[0-9];[0-9]", t) else ""
        raise DataError(f"{where}: {tok!r} is not a number{hint}") from None
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
    text = read_text(path)
    rows = [[_num(t, f"{path}:{n}") for t in toks] for n, toks in _table(text)]
    return _check_grid(rows, path)


def read_points_csv(path: str) -> Points:
    """Scattered points from three delimited columns x, y, value, with an optional header row."""
    text = read_text(path)
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
    obj = _json(path)
    rows = obj.get("values") if isinstance(obj, dict) else obj
    if not isinstance(rows, list) or not all(isinstance(r, list) for r in rows):
        raise DataError(f"{path}: expected {{\"values\": [[…], …]}} or a list of rows")
    return _check_grid([[_json_num(v, path) for v in r] for r in rows], path)


def read_points_json(path: str) -> Points:
    """Points from {"points": [[x, y, v], …]} or {"x": […], "y": […], "value": […]}."""
    obj = _json(path)
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
    obj = _json(path)
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
        w, h, rgba = png.decode(data, MAX_IMAGE_PIXELS)
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

@dataclass
class Catalog:
    """Cell patterns in file order, each a sorted tuple of live (x, y) cells, its box moved to start at (0, 0)."""
    patterns: list

    def __len__(self):
        return len(self.patterns)

    def describe(self) -> dict:
        pops = [len(c) for c in self.patterns]
        side = max(max(max(x for x, _ in c), max(y for _, y in c)) + 1 for c in self.patterns)
        return {"patterns": len(pops), "population": [min(pops), max(pops)], "largest_side": side}


_SIZE = re.compile(r"^([0-9]+)x([0-9]+)$")


def read_catalog(path: str) -> Catalog:
    """One pattern per line: `[WxH:] row row …`, `O`/`*` alive, `.` dead. A declared WxH must match the rows."""
    text = read_text(path)
    out = []
    for k, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line[0] in "#!":
            continue
        where = f"{path}, line {k}"
        head = None
        if ":" in line:
            head, line = (t.strip() for t in line.split(":", 1))
            m = _SIZE.match(head)
            if not m:
                raise DataError(f"{where}: {head!r} before ':' must be WxH")
            head = (int(m.group(1)), int(m.group(2)))
        rows = line.split()
        if not rows or any(set(r) - set("O*.") for r in rows):
            raise DataError(f"{where}: rows must be made of 'O', '*' and '.' only")
        if len(rows) > MAX_PATTERN_SIDE or any(len(r) > MAX_PATTERN_SIDE for r in rows):
            raise DataError(f"{where}: a pattern side is longer than {MAX_PATTERN_SIDE}")
        if head and (len(rows) != head[1] or any(len(r) != head[0] for r in rows)):
            raise DataError(f"{where}: the rows do not form the declared {head[0]}x{head[1]} box")
        cells = [(x, y) for y, r in enumerate(rows) for x, ch in enumerate(r) if ch != "."]
        if not cells:
            raise DataError(f"{where}: a pattern with no live cell")
        x0, y0 = min(x for x, _ in cells), min(y for _, y in cells)
        out.append(tuple(sorted((x - x0, y - y0) for x, y in cells)))
        if len(out) > MAX_PATTERNS:
            raise DataError(f"{path}: more than {MAX_PATTERNS} patterns")
    if not out:
        raise DataError(f"{path}: no pattern")
    return Catalog(out)


@dataclass
class Colorings:
    """Colourings of 1..n in file order, each a tuple of colours (the colour of 1, of 2, …)."""
    colorings: list

    def __len__(self):
        return len(self.colorings)

    def describe(self) -> dict:
        return {"colorings": len(self.colorings), "n": sorted({len(c) for c in self.colorings}),
                "colors": max(max(c) for c in self.colorings) + 1}


def read_coloring(path: str) -> Colorings:
    """One colouring per line: digits (`0112…`) or numbers separated by spaces or commas."""
    text = read_text(path)
    out = []
    for k, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line[0] in "#!":
            continue
        where = f"{path}, line {k}"
        toks = line.replace(",", " ").split()
        if len(toks) == 1:
            toks = list(toks[0])
        if not all(t.isdigit() and t.isascii() for t in toks):
            raise DataError(f"{where}: a colouring is digits, or numbers separated by spaces or commas")
        cols = tuple(int(t) for t in toks)
        if len(cols) > MAX_COLORING:
            raise DataError(f"{where}: {len(cols)} numbers, more than {MAX_COLORING}")
        if max(cols) >= MAX_COLORS:
            raise DataError(f"{where}: colour {max(cols)}; at most {MAX_COLORS} colours (0..{MAX_COLORS - 1})")
        out.append(cols)
        if len(out) > MAX_PATTERNS:
            raise DataError(f"{path}: more than {MAX_PATTERNS} colourings")
    if not out:
        raise DataError(f"{path}: no colouring")
    return Colorings(out)


def rle_counts_from_string(s: str) -> list[int]:
    """The run lengths of a compressed COCO RLE string (the encoding of pycocotools' rleToString: 5 bits per character
    plus a continuation bit, signed, and from the third count on a difference from the count two places before)."""
    counts, p = [], 0
    while p < len(s):
        x, k, more = 0, 0, True
        while more:
            if p >= len(s):
                raise ValueError("a compressed RLE string ends in the middle of a number")
            c = ord(s[p]) - 48
            if not 0 <= c < 64:
                raise ValueError(f"character {s[p]!r} cannot appear in a compressed RLE string")
            x |= (c & 0x1F) << (5 * k)
            more = bool(c & 0x20)
            p += 1
            k += 1
            if not more and c & 0x10:
                x |= -1 << (5 * k)
        if len(counts) > 2:
            x += counts[-2]
        counts.append(x)
    return counts


def rle_string_from_counts(counts: list[int]) -> str:
    """The inverse of rle_counts_from_string (pycocotools' rleToString), for writing COCO data."""
    out = []
    for i, c in enumerate(counts):
        x = c - counts[i - 2] if i > 2 else c
        more = True
        while more:
            ch = x & 0x1F
            x >>= 5
            more = not ((ch & 0x10 and x == -1) or (not ch & 0x10 and x == 0))
            if more:
                ch |= 0x20
            out.append(chr(ch + 48))
    return "".join(out)


def _mask_pixels(m, w: int, h: int, where: str) -> list[int]:
    """Row-major pixel indices (y·W + x) of one mask: COCO RLE (column-major, runs starting with background) or cells."""
    if not isinstance(m, dict):
        raise DataError(f"{where}: a mask is {{\"size\": [H, W], \"counts\": …}} or {{\"cells\": [[x, y], …]}}")
    if "cells" in m:
        cells = m["cells"]
        if not isinstance(cells, list) or any(not isinstance(c, list) or len(c) != 2 or
                                              any(isinstance(v, bool) or not isinstance(v, int) for v in c) for c in cells):
            raise DataError(f"{where}: cells must be [[x, y], …] with integer coordinates")
        out = set()
        for x, y in cells:
            if not (0 <= x < w and 0 <= y < h):
                raise DataError(f"{where}: cell ({x}, {y}) outside the {w}x{h} image")
            out.add(y * w + x)
        return sorted(out)
    size, counts = m.get("size"), m.get("counts")
    if size != [h, w]:
        raise DataError(f"{where}: RLE size {size} is not the image's [H, W] = [{h}, {w}]")
    if isinstance(counts, str):
        try:
            counts = rle_counts_from_string(counts)
        except ValueError as ex:
            raise DataError(f"{where}: {ex}") from None
    if not isinstance(counts, list) or any(isinstance(c, bool) or not isinstance(c, int) or c < 0 for c in counts):
        raise DataError(f"{where}: RLE counts must be non-negative integers")
    if sum(counts) != w * h:
        raise DataError(f"{where}: RLE counts add up to {sum(counts)}, the image has {w * h} pixels")
    out, i = [], 0
    for k, run in enumerate(counts):
        if k % 2:                                     # odd runs are the mask (COCO starts with background)
            for j in range(i, i + run):
                out.append((j % h) * w + j // h)      # COCO runs go down the columns
        i += run
    out.sort()
    return out


@dataclass
class Instances:
    """Instance masks of one image: `truth` and `prediction` are lists of sorted row-major pixel indices."""
    width: int
    height: int
    truth: list
    prediction: list | None
    meta: dict

    def describe(self) -> dict:
        d = {"size": [self.width, self.height], "truth": len(self.truth)}
        if self.prediction is not None:
            d["prediction"] = len(self.prediction)
        return d


def read_instances(path: str) -> Instances:
    """{"width", "height", "truth": [mask…], "prediction": [mask…] (optional), "meta": {str: str|number} (optional)}."""
    obj = _json(path)
    if not isinstance(obj, dict) or set(obj) - {"width", "height", "truth", "prediction", "meta"}:
        raise DataError(f"{path}: expected {{\"width\", \"height\", \"truth\", \"prediction\", \"meta\"}}")
    w, h = obj.get("width"), obj.get("height")
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 1 for v in (w, h)) or w * h > MAX_INSTANCE_PIXELS:
        raise DataError(f"{path}: width and height must be positive integers, at most {MAX_INSTANCE_PIXELS} pixels in all")
    meta = obj.get("meta", {})
    if not isinstance(meta, dict) or any(not isinstance(v, (str, int, float)) or isinstance(v, bool) for v in meta.values()):
        raise DataError(f"{path}: meta must map names to strings or numbers")
    sets = {}
    for role in ("truth", "prediction"):
        masks = obj.get(role)
        if masks is None:
            if role == "truth":
                raise DataError(f"{path}: no \"truth\" list")
            sets[role] = None
            continue
        if not isinstance(masks, list) or len(masks) > MAX_INSTANCES:
            raise DataError(f"{path}: \"{role}\" must be a list of at most {MAX_INSTANCES} masks")
        sets[role] = [_mask_pixels(m, w, h, f"{path}, {role} {k + 1}") for k, m in enumerate(masks)]
    return Instances(w, h, sets["truth"], sets["prediction"], meta)


def load(path: str, shape: str, fmt: str | None = None):
    """Read `path` as a `grid`, `points`, `frames`, an `image` or `patterns`."""
    f = format_of(path, fmt)
    if shape == "grid":
        readers = {"csv": read_grid_csv, "pgm": read_pgm, "npy": read_npy, "json": read_grid_json}
    elif shape == "points":
        readers = {"csv": read_points_csv, "json": read_points_json}
    elif shape == "frames":
        readers = {"json": read_frames_json}
    elif shape == "image":
        readers = {"png": read_png, "ppm": read_ppm}
    elif shape == "patterns":
        readers = {"catalog": read_catalog}
    elif shape == "colorings":
        readers = {"coloring": read_coloring}
    elif shape == "instances":
        readers = {"instances": read_instances}
    else:
        raise AssertionError(shape)
    if f not in readers:
        raise DataError(f"{path}: {f!r} cannot hold {shape} data (use one of {', '.join(readers)})")
    return readers[f](path)
