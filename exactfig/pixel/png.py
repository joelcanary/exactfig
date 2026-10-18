"""
Minimal PNG writer and reader, pure Python (zlib + struct) / PNG mínimo sin dependencias.

Writes 8-bit INDEXED PNGs (colour type 3, PLTE + tRNS): the palette lives inside the file, which makes the palette lock visible to
any viewer. No text chunks, no timestamps, no gamma: the same pixels always give the same bytes with the same zlib.
Reads colour types 0 (grey), 2 (RGB), 3 (indexed), 4 (grey + alpha) and 6 (RGBA) at 8 bits, non-interlaced, all five
filters (what most tools save at 8 bits). `encode_rgba` writes true-colour RGBA, for source images that are not
palette-locked (the inputs of an image conversion).

What `verify` compares is the PIXELS (`pixels_sha256`), not the compressed bytes: two zlib builds may compress differently.
Lo que verify compara son los PÍXELES; el hash del fichero es informativo.
"""
from __future__ import annotations

import hashlib
import struct
import zlib

SIG = b"\x89PNG\r\n\x1a\n"


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def encode_indexed(w: int, h: int, idx: list[int], palette_rgb: list[tuple[int, int, int]], transparent: int | None) -> bytes:
    """idx: w*h índices de la paleta. `transparent`: índice que es transparente (o None)."""
    if len(palette_rgb) > 256:
        raise ValueError("indexed PNG holds at most 256 colours")
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += bytes(idx[y * w:(y + 1) * w])
    plte = b"".join(bytes(c) for c in palette_rgb)
    out = SIG + _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 3, 0, 0, 0)) + _chunk(b"PLTE", plte)
    if transparent is not None:
        trns = bytes(255 if i != transparent else 0 for i in range(transparent + 1))
        out += _chunk(b"tRNS", trns)
    out += _chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + _chunk(b"IEND", b"")
    return out


def encode_rgba(w: int, h: int, rgba: bytes) -> bytes:
    """True-colour PNG (colour type 6, 8 bits), filter 0 on every row, zlib level 9: the same pixels give the same bytes."""
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += rgba[y * w * 4:(y + 1) * w * 4]
    return (SIG + _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + _chunk(b"IEND", b""))


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else b if pb <= pc else c


def _unfilter(raw: bytes, w: int, h: int, bpp: int) -> list[bytearray]:
    """Undo the five PNG row filters (8-bit samples, `bpp` bytes per pixel)."""
    stride = w * bpp
    prev = bytearray(stride)
    rows = []
    q = 0
    for _ in range(h):
        f = raw[q]; q += 1
        line = bytearray(raw[q:q + stride]); q += stride
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1: line[i] = (line[i] + a) & 255
            elif f == 2: line[i] = (line[i] + b) & 255
            elif f == 3: line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif f == 4: line[i] = (line[i] + _paeth(a, b, c)) & 255
            elif f != 0: raise ValueError(f"bad PNG filter {f}")
        rows.append(line)
        prev = line
    return rows


def decode(data: bytes) -> tuple[int, int, bytes]:
    """→ (w, h, RGBA8 bytes)."""
    if data[:8] != SIG:
        raise ValueError("not a PNG file")
    p, idat, plte, trns = 8, bytearray(), None, None
    w = h = depth = ctype = interlace = None
    while p < len(data):
        n, kind = struct.unpack(">I4s", data[p:p + 8])
        body = data[p + 8:p + 8 + n]
        p += 12 + n
        if kind == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
            plte = body
        elif kind == b"tRNS":
            trns = body
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
    if depth != 8 or interlace or ctype not in (0, 2, 3, 4, 6):
        raise ValueError(f"unsupported PNG (bit depth {depth}, colour type {ctype}, interlace {interlace})")
    bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    stride = w * bpp
    rows = _unfilter(zlib.decompress(bytes(idat)), w, h, bpp)
    out = bytearray()
    for line in rows:
        if ctype == 6:
            out += line
        elif ctype == 2:
            for i in range(0, stride, 3):
                out += line[i:i + 3] + b"\xff"
        elif ctype == 0:
            for v in line:
                out += bytes((v, v, v, 255))
        elif ctype == 4:
            for i in range(0, stride, 2):
                out += bytes((line[i], line[i], line[i], line[i + 1]))
        else:
            for i in line:
                out += plte[3 * i:3 * i + 3] + bytes([trns[i] if trns is not None and i < len(trns) else 255])
    return w, h, bytes(out)


def canonical_rgba(rgba: bytes) -> bytes:
    """Los píxeles totalmente transparentes cuentan como iguales (0,0,0,0), tengan el color que tengan debajo."""
    b = bytearray(rgba)
    for i in range(3, len(b), 4):
        if b[i] == 0:
            b[i - 3:i] = b"\0\0\0"
    return bytes(b)


def pixels_sha256(w: int, h: int, rgba: bytes) -> str:
    """Hash canónico de una imagen: tamaño + RGBA8 canónico. Es lo que firma el manifiesto."""
    return hashlib.sha256(b"exactfig-rgba8\0" + struct.pack(">II", w, h) + canonical_rgba(rgba)).hexdigest()
