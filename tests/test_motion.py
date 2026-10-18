"""Animations: the containers against an independent decoder, and every animated generator against facts of its
mathematics (automaton periods, exact mirror symmetry, Runge–Kutta order, conservation of heat)."""
import io
import json
import os
import random
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig import provenance  # noqa: E402
from exactfig.data import io as dataio  # noqa: E402
from exactfig.forge import motion as Mo  # noqa: E402
from exactfig.pixel import anim  # noqa: E402
from exactfig.render import render  # noqa: E402

GALLERY = os.path.join(os.path.abspath(ROOT), "gallery")


def rgba_of(frames, pal):
    return [(d, b"".join(b"\0\0\0\0" if c is None else bytes(pal[c]) + b"\xff" for c in f)) for d, f in frames]


class Containers(unittest.TestCase):
    def sample(self, alpha, n_colours=34, w=37, h=23, n=5, seed=1):
        r = random.Random(seed)
        pal = [(r.randrange(256), r.randrange(256), r.randrange(256)) for _ in range(n_colours)]
        frames = []
        for k in range(n):
            f = [r.randrange(n_colours) if r.random() < 0.5 else (i // 7 + k) % n_colours for i in range(w * h)]
            if alpha:
                f = [None if r.random() < 0.2 else c for c in f]
            frames.append((40 + 10 * k, f))
        return w, h, frames, pal

    def test_gif_and_apng_round_trip(self):
        for alpha in (False, True):
            w, h, frames, pal = self.sample(alpha)
            for enc in (anim.encode_gif, anim.encode_apng):
                W, H, got = anim.decode(enc(w, h, frames, pal))
                self.assertEqual((W, H), (w, h))
                self.assertEqual(got, rgba_of(frames, pal), (enc.__name__, alpha))

    def test_lzw_table_reset_at_4096_codes(self):
        r = random.Random(2)
        pal = [(i, 255 - i, i * 7 % 256) for i in range(256)]
        f = [r.randrange(256) for _ in range(160 * 160)]
        _, _, got = anim.decode(anim.encode_gif(160, 160, [(100, f)], pal))
        self.assertEqual(got[0][1], rgba_of([(100, f)], pal)[0][1])

    def test_an_independent_decoder_reads_the_same_frames(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed (optional cross-check)")
        w, h, frames, pal = self.sample(True)
        want = [rgba for _, rgba in rgba_of(frames, pal)]
        for enc in (anim.encode_gif, anim.encode_apng):
            im = Image.open(io.BytesIO(enc(w, h, frames, pal)))
            got = []
            for k in range(im.n_frames):
                im.seek(k)
                got.append(im.convert("RGBA").tobytes())
            self.assertEqual([anim.png.canonical_rgba(g) for g in got], [anim.png.canonical_rgba(x) for x in want], enc.__name__)

    def test_the_content_hash_does_not_depend_on_the_container(self):
        r = {"generator": "anim.life", "seed": "c", "palette": "sci", "size": [16, 12], "params": {"frames": 5}}
        self.assertEqual(render(dict(r, output="a.gif")).content_sha256, render(dict(r, output="a.png")).content_sha256)

    def test_gif_delays_must_be_whole_hundredths(self):
        with self.assertRaises(ValueError):
            render({"generator": "anim.life", "seed": "c", "palette": "sci", "size": [8, 8], "params": {"frames": 2, "delay": 45}})


class Life(unittest.TestCase):
    def run_rule(self, cells, w, h, rule, n, wrap=True):
        b, s = Mo.parse_rule(rule)
        for _ in range(n):
            cells = Mo.life_step(cells, w, h, b, s, wrap)
        return cells

    def board(self, w, h, pts, dx=0, dy=0):
        c = bytearray(w * h)
        for x, y in pts:
            c[((y + dy) % h) * w + (x + dx) % w] = 1
        return c

    def test_glider_moves_one_cell_diagonally_every_four_generations(self):
        g = Mo.PATTERNS["glider"]
        start = self.board(8, 8, g, 2, 2)
        self.assertEqual(self.run_rule(start, 8, 8, "B3/S23", 4), self.board(8, 8, g, 3, 3))
        self.assertEqual(self.run_rule(start, 8, 8, "B3/S23", 32), start)          # 8 steps round the torus

    def test_oscillator_and_still_life(self):
        blinker = self.board(5, 5, [(1, 2), (2, 2), (3, 2)])
        once = self.run_rule(blinker, 5, 5, "B3/S23", 1, wrap=False)
        self.assertEqual(once, self.board(5, 5, [(2, 1), (2, 2), (2, 3)]))
        self.assertEqual(self.run_rule(blinker, 5, 5, "B3/S23", 2, wrap=False), blinker)
        block = self.board(4, 4, [(1, 1), (2, 1), (1, 2), (2, 2)])
        self.assertEqual(self.run_rule(block, 4, 4, "B3/S23", 5, wrap=False), block)

    def test_rules_are_parsed_strictly(self):
        self.assertEqual(Mo.parse_rule("B37/S2378"), (frozenset({3, 7}), frozenset({2, 3, 7, 8})))
        for bad in ("B3S23", "b3/s23", "B9/S23", "B33/S23", "B3/S23/x"):
            with self.assertRaises(ValueError, msg=bad):
                Mo.parse_rule(bad)


class Wave(unittest.TestCase):
    def test_the_double_slit_field_is_exactly_mirror_symmetric(self):
        """The geometry is symmetric about the horizontal centre line, and a + b = b + a exactly in IEEE 754, so every
        frame must be its own mirror image, bit for bit (any asymmetry would be a bug in the stencil or the walls)."""
        p = {"scene": "double-slit", "speed": 0.5, "period": 10.0, "separation": 12.0, "opening": 3.0, "sponge": 6,
             "contrast": 1.5, "frames": 6, "every": 6, "delay": 60, "ramp": "div", "wall_ramp": "ink"}
        from exactfig.pixel import palette
        frames = Mo.wave("x", palette.builtin("sci"), 64, 40, p)
        for _, cv in frames:
            self.assertEqual(cv.px, cv.px[::-1])

    def test_unstable_courant_numbers_are_refused(self):
        with self.assertRaises(ValueError):
            render({"generator": "anim.wave", "seed": "x", "palette": "sci", "size": [16, 16], "params": {"speed": 0.75}})


class Lorenz(unittest.TestCase):
    def test_runge_kutta_is_fourth_order(self):
        """Halving the step divides the error at a fixed time by about 2⁴ = 16 once the step is in the asymptotic range
        (at dt = 0.01 the ratio is still about 38; from dt = 0.005 down it stays near 14-15)."""
        def at_t1(dt):
            return Mo.lorenz_path(int(round(1 / dt)), dt, 10.0, 28.0, 8 / 3, (1.0, 1.0, 1.0))[-1]
        ref = at_t1(0.0001)

        def err(dt):
            return max(abs(a - b) for a, b in zip(at_t1(dt), ref))
        ratio = err(0.005) / err(0.0025)
        self.assertTrue(12 < ratio < 20, ratio)

    def test_the_fixed_points_do_not_move(self):
        b, r = 8 / 3, 28.0
        c = (b * (r - 1)) ** 0.5
        x, y, z = Mo.lorenz_path(1000, 0.005, 10.0, r, b, (c, c, r - 1))[-1]
        self.assertAlmostEqual(x, c, places=9)
        self.assertAlmostEqual(z, r - 1, places=9)


class Diffuse(unittest.TestCase):
    def test_heat_is_conserved_and_the_extremes_relax(self):
        g = dataio.read_pgm(os.path.join(GALLERY, "data", "dem-192.pgm"))
        w = h = 24
        from exactfig.data import field as F
        z = F.sample(g, w, h, "bilinear")
        total, hi, lo = sum(z), max(z), min(z)
        for _ in range(50):                                  # the same update as motion.diffuse
            nz = z[:]
            for y in range(h):
                for x in range(w):
                    acc = 0.0
                    for xx, yy in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                        if 0 <= xx < w and 0 <= yy < h:
                            acc += z[yy * w + xx] - z[y * w + x]
                    nz[y * w + x] = z[y * w + x] + 0.2 * acc
            z = nz
        self.assertAlmostEqual(sum(z) / total, 1.0, places=12)
        self.assertLess(max(z), hi)
        self.assertGreater(min(z), lo)


class Provenance(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="exactfig-anim-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_record_verify_and_a_changed_pixel_in_one_frame(self):
        man = os.path.join(self.dir, "manifest.json")
        for ext in ("gif", "png"):
            rf = os.path.join(self.dir, f"r-{ext}.json")
            with open(rf, "w", encoding="utf-8") as fh:
                json.dump({"generator": "anim.life", "seed": "v", "palette": "sci", "size": [20, 14], "scale": 2,
                           "params": {"frames": 6}, "output": f"life.{ext}"}, fh)
            provenance.record([rf], man, log=lambda *_: None)
        checks, top = provenance.verify(man, strict=True)
        self.assertTrue(all(c.ok for c in checks) and not top, [c.problems for c in checks])
        path = os.path.join(self.dir, "life.gif")
        with open(path, "rb") as fh:
            w, h, frames = anim.decode(fh.read())
        pal = [tuple(int(x[i:i + 2], 16) for i in (1, 3, 5)) for x in json.load(open(man, encoding="utf-8"))["assets"]["life.gif"]["palette"]]
        lookup = {bytes(c): i for i, c in enumerate(pal)}
        idx = [(d, [lookup[rgba[q:q + 3]] if rgba[q + 3] else None for q in range(0, len(rgba), 4)]) for d, rgba in frames]
        idx[3][1][5] = (idx[3][1][5] + 1) % len(pal)                  # one pixel of the fourth frame
        with open(path, "wb") as fh:
            fh.write(anim.encode_gif(w, h, idx, pal))
        bad = {c.path: c for c in provenance.verify(man)[0]}["life.gif"]
        self.assertFalse(bad.ok)
        self.assertIn("frame 3: 1 pixel(s) differ", bad.problems[0])


if __name__ == "__main__":
    unittest.main()
