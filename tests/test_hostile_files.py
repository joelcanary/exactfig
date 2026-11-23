"""Animations and pictures from outside are read defensively (the GIF/APNG decoders and `verify`):

- a GIF whose header declares 65535 × 65535 pixels is refused at once, before any allocation (it used to allocate
  w × h × 4 bytes, 17 GB, and could bring a machine down);
- a frame rectangle outside the canvas, a frame without a colour table, a colour index beyond the table, every truncation
  of a valid GIF and APNG: each is a ValueError, never another exception;
- an APNG frame whose compressed data inflates to megabytes (a "zip bomb") is refused after inflating no more than the
  frame can hold, and an APNG declaring a huge canvas is refused;
- a caller's `max_pixels` (what `verify` passes: the size the manifest recorded) is enforced;
- the decoder's total cap is the renderer's own."""
import os
import struct
import sys
import time
import unittest
import zlib

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig import render  # noqa: E402
from exactfig.pixel import anim, png  # noqa: E402

PAL = [(0, 0, 0), (255, 255, 255), (255, 0, 0)]


def small_gif():
    frames = [(100, [0, 1, 2, 1] * 4), (100, [1, 1, 0, 0] * 4)]
    return anim.encode_gif(4, 4, frames, PAL)


def small_apng():
    frames = [(100, [0, 1, 2, 1] * 4), (100, [1, 1, 0, 0] * 4)]
    return anim.encode_apng(4, 4, frames, PAL)


def chunk(kind, body):
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)


class TestHostileFiles(unittest.TestCase):
    def test_valid_files_still_decode(self):
        w, h, frames = anim.decode(small_gif())
        self.assertEqual((w, h, len(frames)), (4, 4, 2))
        w, h, frames = anim.decode(small_apng())
        self.assertEqual((w, h, len(frames)), (4, 4, 2))

    def test_gif_huge_canvas_refused_at_once(self):
        g = bytearray(small_gif())
        g[6:10] = struct.pack("<HH", 65535, 65535)
        t = time.time()
        with self.assertRaisesRegex(ValueError, "pixel limit"):
            anim.decode(bytes(g))
        self.assertLess(time.time() - t, 1.0)

    def test_gif_frame_outside_canvas(self):
        g = bytearray(small_gif())
        i = g.index(0x2C, 13)                     # the first image descriptor
        g[i + 5:i + 9] = struct.pack("<HH", 40, 40)   # a 40 × 40 frame on a 4 × 4 canvas
        with self.assertRaisesRegex(ValueError, "not inside"):
            anim.decode(bytes(g))

    def test_gif_without_colour_table(self):
        g = bytearray(small_gif())
        n = 2 << (g[10] & 7)
        g[10] &= 0x7F                             # clear the "global colour table" flag
        del g[13:13 + 3 * n]
        with self.assertRaisesRegex(ValueError, "colour table"):
            anim.decode(bytes(g))

    def test_every_truncation_is_a_value_error(self):
        for name, data in (("gif", small_gif()), ("apng", small_apng())):
            for k in range(len(data)):
                try:
                    anim.decode(data[:k])
                except ValueError:
                    pass
                except Exception as ex:           # noqa: BLE001
                    self.fail(f"{name} cut at {k}: {type(ex).__name__}: {ex}")

    def test_apng_zip_bomb_and_huge_canvas(self):
        a = small_apng()
        bomb = zlib.compress(b"\0" * 20_000_000, 9)              # ~20 KB that inflate to 20 MB
        p, out, swapped = 8, bytearray(a[:8]), False
        while p < len(a):
            n, kind = struct.unpack(">I4s", a[p:p + 8])
            body = a[p + 8:p + 8 + n]
            if kind == b"IDAT" and not swapped:
                body, swapped = bomb, True
            out += chunk(kind, body)
            p += 12 + n
        t = time.time()
        with self.assertRaisesRegex(ValueError, "bytes of image data"):
            anim.decode(bytes(out))
        self.assertLess(time.time() - t, 2.0)
        i = a.index(b"IHDR")
        big = a[:i + 4] + struct.pack(">II", 60000, 60000) + a[i + 12:]
        with self.assertRaisesRegex(ValueError, "pixel limit"):
            anim.decode(big)

    def test_callers_cap(self):
        with self.assertRaisesRegex(ValueError, "pixel limit"):
            anim.decode(small_gif(), max_pixels=15)
        self.assertEqual(anim.decode(small_gif(), max_pixels=16)[0], 4)
        still = png.encode_indexed(4, 4, [0, 1, 2, 1] * 4, PAL, None)
        with self.assertRaisesRegex(ValueError, "limit"):
            png.decode(still, 15)
        self.assertEqual(png.decode(still, 16)[:2], (4, 4))

    def test_cap_is_the_renderers(self):
        self.assertEqual(anim.MAX_PIXELS, render.MAX_ANIMATION_PIXELS)


if __name__ == "__main__":
    unittest.main()
