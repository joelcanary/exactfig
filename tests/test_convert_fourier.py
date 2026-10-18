"""Image conversion and Fourier analysis, against facts: colour science (linear-light mixing), clustering (Lloyd never
increases the cost it starts from), the Gibbs constant, Leibniz's series, and the exactness of the inverse DFT."""
import io
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig import fmath as fm  # noqa: E402
from exactfig.data import io as dataio  # noqa: E402
from exactfig.forge import mathviz as MV, motion as Mo  # noqa: E402
from exactfig.pixel import convert as C, palette as P, png  # noqa: E402
from exactfig.render import render  # noqa: E402

GALLERY = os.path.join(os.path.abspath(ROOT), "gallery")


def cost(pixels, palette):
    labs = [P.oklab(c) for c in palette]
    return sum(min(fm.dist2(P.oklab(p), q) for q in labs) for p in pixels)


class Resample(unittest.TestCase):
    def test_mixing_happens_in_linear_light(self):
        """Half black, half white averages to linear 0.5, which is sRGB ≈ 187.5, not 127.5."""
        rgba = bytes([0, 0, 0, 255, 255, 255, 255, 255])
        (r, g, b), = C.resample(2, 1, rgba, 1, 1, "area")
        self.assertAlmostEqual(r, 255 * (1.055 * 0.5 ** (1 / 2.4) - 0.055), places=6)
        self.assertTrue(187 < r < 188)

    def test_same_size_keeps_every_pixel_and_transparency(self):
        rgba = bytes([10, 20, 30, 255, 200, 100, 50, 255, 0, 0, 0, 0, 255, 255, 255, 255])
        out = C.resample(2, 2, rgba, 2, 2, "area")
        self.assertEqual([None if p is None else tuple(round(v) for v in p) for p in out],
                         [(10, 20, 30), (200, 100, 50), None, (255, 255, 255)])


class Palettes(unittest.TestCase):
    def test_median_cut_finds_the_colours_of_a_four_colour_image(self):
        cols = [(255, 0, 0)] * 30 + [(0, 255, 0)] * 10 + [(0, 0, 255)] * 5 + [(255, 255, 255)] * 2
        self.assertEqual(sorted(C.median_cut(cols, 4)), sorted({(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)}))

    def test_kmeans_never_does_worse_than_its_median_cut_start(self):
        img = dataio.read_png(os.path.join(GALLERY, "data", "testcard-480x320.png"))
        px = [p for p in C.resample(img.width, img.height, img.rgba, 60, 40, "area") if p]
        for k in (4, 8, 16):
            self.assertLessEqual(cost(px, C.kmeans(px, k)), cost(px, C.median_cut(px, k)) + 1e-9, k)

    def test_derived_palette_object_is_a_valid_recipe_palette(self):
        pal = C.palette_object("t", [(250, 250, 250), (5, 5, 5), (120, 30, 30)])
        self.assertEqual(pal["colors"][0], "#050505")                       # sorted dark to light
        P.get(pal)


class Sobel(unittest.TestCase):
    def test_flat_is_zero_and_a_step_has_the_textbook_magnitude(self):
        flat = [0.3] * 25
        self.assertTrue(all(v == 0.0 for v in C.sobel(flat, 5, 5)))
        step = [0.0 if x < 2 else 1.0 for y in range(5) for x in range(5)]
        g = C.sobel(step, 5, 5)
        self.assertEqual(g[2 * 5 + 1], 4.0)                                # kernel weights 1 + 2 + 1 across the step
        self.assertEqual(g[2 * 5 + 2], 4.0)
        self.assertEqual(g[2 * 5 + 4], 0.0)


class Conversion(unittest.TestCase):
    def test_output_uses_only_the_palette_and_ppm_reads_like_png(self):
        out = render({"generator": "data.image", "seed": "c", "palette": "mono4", "size": [48, 32],
                      "input": {"path": "data/testcard-480x320.png"}, "params": {"dither": "bayer"}}, GALLERY)
        _, _, rgba = png.decode(out.data)
        seen = {rgba[i:i + 3] for i in range(0, len(rgba), 4)}
        self.assertLessEqual(seen, {bytes(c) for c in P.builtin("mono4").rgb})
        img = dataio.read_png(os.path.join(GALLERY, "data", "testcard-480x320.png"))
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p6 = os.path.join(d, "t.ppm")
            with open(p6, "wb") as fh:
                fh.write(b"P6\n# test\n480 320\n255\n" + bytes(b for i in range(0, len(img.rgba), 4) for b in img.rgba[i:i + 3]))
            self.assertEqual(dataio.read_ppm(p6).rgba, img.rgba)
            p3 = os.path.join(d, "a.ppm")
            with open(p3, "w") as fh:
                fh.write("P3 2 1 15\n15 0 0  0 15 7\n")
            self.assertEqual(dataio.read_ppm(p3).rgba, bytes([255, 0, 0, 255, 0, 255, 119, 255]))

    def test_pillow_reads_the_test_card_like_we_do(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed (optional cross-check)")
        path = os.path.join(GALLERY, "data", "testcard-480x320.png")
        with open(path, "rb") as fh:
            data = fh.read()
        self.assertEqual(Image.open(io.BytesIO(data)).convert("RGBA").tobytes(), dataio.read_png(path).rgba)


class Fourier(unittest.TestCase):
    def test_gibbs_overshoot_tends_to_the_wilbraham_gibbs_constant(self):
        """max S_N of the square wave → (2/π)·Si(π) = 1.178979744… (an overshoot of about 9 % of the jump of 2)."""
        n = 200
        peak = max(MV.fourier_partial("square", n, k * fm.pi / (2 * n) / 50) for k in range(1, 200))
        self.assertAlmostEqual(peak, 1.178979744, delta=2e-3)

    def test_leibniz_series_at_a_quarter_period(self):
        """S_N(π/2) = (4/π)(1 − 1/3 + 1/5 − …) → 1, with error below 4/(π·(2N+1))."""
        for n in (10, 100, 1000):
            self.assertLess(abs(MV.fourier_partial("square", n, fm.pi / 2) - 1.0), 4 / (fm.pi * (2 * n + 1)))

    def test_inverse_dft_reproduces_the_curve_and_parseval_holds(self):
        pts = Mo.closed_curve("trefoil", 64)
        coeffs = Mo.dft(pts)
        for j in range(64):
            x, y = Mo.epicycle_position(coeffs, j / 64, len(coeffs))[-1]
            self.assertAlmostEqual(x, pts[j][0], places=12)
            self.assertAlmostEqual(y, pts[j][1], places=12)
        energy = sum(x * x + y * y for x, y in pts) / 64
        self.assertAlmostEqual(energy, sum(re * re + im * im for _, re, im in coeffs), places=12)


if __name__ == "__main__":
    unittest.main()
