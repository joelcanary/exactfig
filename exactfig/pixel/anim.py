"""
Animations: GIF and APNG, written and read in pure Python / animaciones GIF y APNG sin dependencias.

Both containers keep the palette lock: every frame is palette INDICES and the palette sits in the file (GIF global colour
table; PNG PLTE). Frames are full-size and replace the previous one, so any viewer shows exactly the computed frames.

  encode_gif    GIF89a, global colour table, LZW written here, NETSCAPE2.0 loop, delays in hundredths of a second
  encode_apng   APNG (PNG with acTL / fcTL / fdAT), delays in milliseconds
  decode        either container → (w, h, [(delay_ms, RGBA8 bytes), …]), composing frame rectangles and disposal as the
                formats say (enough to read back any GIF or APNG with 8-bit frames)
  frames_sha256 the canonical hash of an animation: size, frame count, and every frame's delay and canonical RGBA. It does not
                depend on the container: the same frames give the same hash as GIF or as APNG.

As with still images, `verify` compares decoded pixels; the file hash is informative unless --strict.
"""
from __future__ import annotations

import hashlib
import struct
import zlib

from . import png

MAX_FRAMES = 1000


# ------------------------------------------------------------------------------------------------ canonical hash

def frames_sha256(w: int, h: int, frames: list[tuple[int, bytes]]) -> str:
    """The animation's canonical hash: size, frame count, then every frame's delay and canonical RGBA."""
    hsh = hashlib.sha256(b"exactfig-anim1\0" + struct.pack(">III", w, h, len(frames)))
    for delay, rgba in frames:
        hsh.update(struct.pack(">I", delay) + png.canonical_rgba(rgba))
    return hsh.hexdigest()


# ------------------------------------------------------------------------------------------------ GIF

def _lzw_encode(idx: list[int], min_size: int) -> bytes:
    """GIF LZW. Code widths follow the decoder's table exactly (it lags the encoder by one entry)."""
    clear, eoi = 1 << min_size, (1 << min_size) + 1
    out = bytearray()
    acc = nbits = 0

    def emit(code, width):
        nonlocal acc, nbits
        acc |= code << nbits
        nbits += width
        while nbits >= 8:
            out.append(acc & 255)
            acc >>= 8
            nbits -= 8

    table: dict[int, int] = {}
    nxt = eoi + 1                      # the encoder's next free code
    avail = eoi + 1                    # the decoder's next free code when it reads the next code
    first = True

    def put(code):
        nonlocal avail, first
        emit(code, min(12, avail.bit_length()))
        if first:
            first = False
        elif avail < 4096:
            avail += 1

    emit(clear, min_size + 1)
    prefix = idx[0]
    for k in idx[1:]:
        key = prefix << 8 | k
        code = table.get(key)
        if code is not None:
            prefix = code
            continue
        put(prefix)
        if nxt < 4096:
            table[key] = nxt
            nxt += 1
        else:                          # table full: start again
            emit(clear, min(12, avail.bit_length()))
            table.clear()
            nxt = avail = eoi + 1
            first = True
        prefix = k
    put(prefix)
    emit(eoi, min(12, avail.bit_length()))
    if nbits:
        out.append(acc & 255)
    return bytes(out)


def _lzw_decode(data: bytes, min_size: int, n: int) -> list[int]:
    clear, eoi = 1 << min_size, (1 << min_size) + 1
    size, avail = min_size + 1, eoi + 1
    table = {i: (i,) for i in range(clear)}
    out: list[int] = []
    prev = None
    acc = nbits = pos = 0
    while len(out) < n:
        while nbits < size:
            if pos >= len(data):
                raise ValueError("GIF: image data ends early")
            acc |= data[pos] << nbits
            pos += 1
            nbits += 8
        code = acc & ((1 << size) - 1)
        acc >>= size
        nbits -= size
        if code == clear:
            size, avail, prev = min_size + 1, eoi + 1, None
            table = {i: (i,) for i in range(clear)}
            continue
        if code == eoi:
            break
        if prev is None:
            if code not in table:
                raise ValueError("GIF: bad first code")
            entry = table[code]
        else:
            if code in table:
                entry = table[code]
                new = table[prev] + entry[:1]
            elif code == avail:
                entry = new = table[prev] + table[prev][:1]
            else:
                raise ValueError("GIF: bad LZW code")
            if avail < 4096:
                table[avail] = new
                avail += 1
                if avail == 1 << size and size < 12:
                    size += 1
        out.extend(entry)
        prev = code
    if len(out) < n:
        raise ValueError("GIF: too few pixels")
    return out[:n]


def _blocks(data: bytes) -> bytes:
    return b"".join(bytes([len(data[i:i + 255])]) + data[i:i + 255] for i in range(0, len(data), 255)) + b"\0"


def encode_gif(w: int, h: int, frames: list[tuple[int, list[int | None]]], palette_rgb: list[tuple[int, int, int]]) -> bytes:
    """frames: (delay_ms, w*h indices or None for transparent). Delays must be multiples of 10 ms."""
    if not 1 <= len(frames) <= MAX_FRAMES:
        raise ValueError(f"an animation has 1..{MAX_FRAMES} frames")
    has_alpha = any(c is None for _, f in frames for c in f)
    pal = list(palette_rgb)
    t = None
    if has_alpha:
        if len(pal) >= 256:
            raise ValueError("no room for a transparent index")
        t = len(pal)
        pal.append((0, 0, 0))
    bits = max(1, (len(pal) - 1).bit_length())
    gct = b"".join(bytes(c) for c in pal) + b"\0\0\0" * ((1 << bits) - len(pal))
    out = bytearray(b"GIF89a" + struct.pack("<HHBBB", w, h, 0x80 | 0x70 | (bits - 1), 0, 0) + gct)
    out += b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"           # loop forever
    min_size = max(2, bits)
    for delay, f in frames:
        if delay % 10:
            raise ValueError("GIF delays are in hundredths of a second: use multiples of 10 ms")
        packed = (2 << 2 if has_alpha else 1 << 2) | (1 if has_alpha else 0)   # restore to background / keep
        out += b"\x21\xf9\x04" + struct.pack("<BHB", packed, delay // 10, t or 0) + b"\0"
        out += b"\x2c" + struct.pack("<HHHHB", 0, 0, w, h, 0)
        out += bytes([min_size]) + _blocks(_lzw_encode([t if c is None else c for c in f], min_size))
    out += b"\x3b"
    return bytes(out)


def _decode_gif(data: bytes):
    if data[:6] not in (b"GIF87a", b"GIF89a"):
        raise ValueError("not a GIF file")
    w, h, flags, bg, _ = struct.unpack("<HHBBB", data[6:13])
    p = 13
    gct = None
    if flags & 0x80:
        n = 2 << (flags & 7)
        gct = data[p:p + 3 * n]
        p += 3 * n
    canvas = bytearray(w * h * 4)
    frames = []
    delay, transp, disposal = 0, None, 0
    while p < len(data):
        b = data[p]
        if b == 0x3B:
            break
        if b == 0x21:
            label = data[p + 1]
            p += 2
            body = bytearray()
            while data[p]:
                body += data[p + 1:p + 1 + data[p]]
                p += 1 + data[p]
            p += 1
            if label == 0xF9 and len(body) >= 4:
                disposal = (body[0] >> 2) & 7
                delay = struct.unpack("<H", bytes(body[1:3]))[0] * 10
                transp = body[3] if body[0] & 1 else None
            continue
        if b != 0x2C:
            raise ValueError("GIF: unexpected block")
        x0, y0, fw, fh, fl = struct.unpack("<HHHHB", data[p + 1:p + 10])
        p += 10
        ct = gct
        if fl & 0x80:
            n = 2 << (fl & 7)
            ct = data[p:p + 3 * n]
            p += 3 * n
        if fl & 0x40:
            raise ValueError("GIF: interlaced frames are not supported")
        min_size = data[p]
        p += 1
        body = bytearray()
        while data[p]:
            body += data[p + 1:p + 1 + data[p]]
            p += 1 + data[p]
        p += 1
        idx = _lzw_decode(bytes(body), min_size, fw * fh)
        before = bytes(canvas)
        for j in range(fh):
            for i in range(fw):
                c = idx[j * fw + i]
                if c == transp:
                    continue
                q = ((y0 + j) * w + x0 + i) * 4
                canvas[q:q + 4] = ct[3 * c:3 * c + 3] + b"\xff"
        frames.append((delay, bytes(canvas)))
        if disposal == 2:
            for j in range(fh):
                for i in range(fw):
                    q = ((y0 + j) * w + x0 + i) * 4
                    canvas[q:q + 4] = b"\0\0\0\0"
        elif disposal == 3:
            canvas = bytearray(before)
        delay, transp, disposal = 0, None, 0
    return w, h, frames


# ------------------------------------------------------------------------------------------------ APNG

def encode_apng(w: int, h: int, frames: list[tuple[int, list[int | None]]], palette_rgb: list[tuple[int, int, int]]) -> bytes:
    """APNG bytes (acTL / fcTL / IDAT / fdAT) for full-size frames of palette indices; None is transparent."""
    if not 1 <= len(frames) <= MAX_FRAMES:
        raise ValueError(f"an animation has 1..{MAX_FRAMES} frames")
    has_alpha = any(c is None for _, f in frames for c in f)
    pal = list(palette_rgb)
    t = None
    if has_alpha:
        if len(pal) >= 256:
            raise ValueError("no room for a transparent index")
        t = len(pal)
        pal.append((0, 0, 0))
    out = png.SIG + png._chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 3, 0, 0, 0))
    out += png._chunk(b"acTL", struct.pack(">II", len(frames), 0))
    out += png._chunk(b"PLTE", b"".join(bytes(c) for c in pal))
    if t is not None:
        out += png._chunk(b"tRNS", bytes(255 if i != t else 0 for i in range(t + 1)))
    seq = 0
    for k, (delay, f) in enumerate(frames):
        out += png._chunk(b"fcTL", struct.pack(">IIIIIHHBB", seq, w, h, 0, 0, delay, 1000, 0, 0))
        seq += 1
        raw = bytearray()
        for y in range(h):
            raw.append(0)
            raw += bytes(t if c is None else c for c in f[y * w:(y + 1) * w])
        z = zlib.compress(bytes(raw), 9)
        if k == 0:
            out += png._chunk(b"IDAT", z)
        else:
            out += png._chunk(b"fdAT", struct.pack(">I", seq) + z)
            seq += 1
    return out + png._chunk(b"IEND", b"")


def _decode_apng(data: bytes):
    if data[:8] != png.SIG:
        raise ValueError("not a PNG file")
    p = 8
    w = h = None
    plte = trns = None
    frames_meta = []                   # (fcTL fields, compressed data)
    cur = None
    actl = False
    while p < len(data):
        n, kind = struct.unpack(">I4s", data[p:p + 8])
        body = data[p + 8:p + 8 + n]
        p += 12 + n
        if kind == b"IHDR":
            w, h, depth, ctype, _, _, inter = struct.unpack(">IIBBBBB", body)
            if depth != 8 or ctype != 3 or inter:
                raise ValueError("APNG: only 8-bit indexed, non-interlaced frames are read")
        elif kind == b"acTL":
            actl = True
        elif kind == b"PLTE":
            plte = body
        elif kind == b"tRNS":
            trns = body
        elif kind == b"fcTL":
            cur = [struct.unpack(">IIIIIHHBB", body), bytearray()]
            frames_meta.append(cur)
        elif kind == b"IDAT" and cur is not None:
            cur[1] += body
        elif kind == b"fdAT" and cur is not None:
            cur[1] += body[4:]
        elif kind == b"IEND":
            break
    if not actl or not frames_meta:
        raise ValueError("not an animated PNG (no acTL / fcTL)")
    canvas = bytearray(w * h * 4)
    out = []
    for (seq, fw, fh, x0, y0, dn, dd, dispose, blend), z in frames_meta:
        raw = zlib.decompress(bytes(z))
        rows = png._unfilter(raw, fw, fh, 1)
        before = bytes(canvas)
        for j, line in enumerate(rows):
            for i, c in enumerate(line):
                a = trns[c] if trns is not None and c < len(trns) else 255
                q = ((y0 + j) * w + x0 + i) * 4
                if a == 0 and blend == 1:
                    continue
                canvas[q:q + 4] = plte[3 * c:3 * c + 3] + bytes([a])
        out.append((dn * 1000 // (dd or 100), bytes(canvas)))
        if dispose == 1:
            for j in range(fh):
                for i in range(fw):
                    q = ((y0 + j) * w + x0 + i) * 4
                    canvas[q:q + 4] = b"\0\0\0\0"
        elif dispose == 2:
            canvas = bytearray(before)
    return w, h, out


def decode(data: bytes):
    """GIF or APNG bytes → (w, h, [(delay_ms, RGBA8), …])."""
    if data[:3] == b"GIF":
        return _decode_gif(data)
    return _decode_apng(data)
