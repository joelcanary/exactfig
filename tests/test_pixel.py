"""Pixel primitives, palettes and PNG / primitivas, paletas y PNG (python -m unittest discover tests)."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from exactfig.pixel import png, pxmath as M, palette as P  # noqa: E402
from exactfig.pixel.canvas import Canvas  # noqa: E402
from exactfig.pixel.dither import rgb_diffused, rgb_ordered, to_ramp_ordered  # noqa: E402
from exactfig.rng import Rng  # noqa: E402


class PxMath(unittest.TestCase):
    def test_bayer8_is_a_permutation_with_the_classic_rows(self):
        flat = [v for row in M.BAYER8 for v in row]
        assert sorted(flat) == list(range(64))
        assert M.BAYER8[0] == (0, 32, 8, 40, 2, 34, 10, 42)
        assert M.BAYER8[1] == (48, 16, 56, 24, 50, 18, 58, 26)
        assert 0 < M.bayer(3, 5, 8) < 1 and 0 < M.bayer(3, 5) < 1


    def test_noise_in_range_and_deterministic(self):
        for i in range(500):
            x, y = i * 0.37 - 30, i * 0.61 + 4
            for v in (M.value_noise(x, y, 3), M.fbm(x, y, 3), M.ridged(x, y, 3)):
                assert 0 <= v <= 1
            assert M.fbm(x, y, 3) == M.fbm(x, y, 3)


    def test_worley_orders_f1_f2_and_grid_without_jitter(self):
        for i in range(200):
            f1, f2, cell, dx, dy = M.worley(i * 0.13, i * 0.29, 5)
            assert 0 <= f1 <= f2
            assert abs(math.hypot(dx, dy) - f1) < 1e-9
        assert M.worley(3.5, 7.5, 1, jitter=0)[0] < 1e-9


    def test_cave_step_closes_holes_and_erases_specks(self):
        w = h = 9
        rock = [True] * (w * h); rock[4 * w + 4] = False
        assert M.cave_step(rock, w, h)[4 * w + 4]
        speck = [False] * (w * h); speck[4 * w + 4] = True
        assert not M.cave_step(speck, w, h, outside=False)[4 * w + 4]


    def test_fractals(self):
        assert M.julia(0, 0, 0, 0, 40) == 40
        assert M.julia(1.9, 1.9, 0, 0, 40) < 3
        assert M.mandelbrot(-1, 0, 50) == 50 and M.mandelbrot(1, 1, 50) < 5
        assert M.sierpinski(5, 2) and not M.sierpinski(3, 1)


    def test_bezier_and_vogel(self):
        p0, p1, p2, p3 = (0, 0), (5, 10), (15, -4), (20, 3)
        assert M.bezier(p0, p1, p2, p3, 0) == (0, 0)
        assert math.dist(M.bezier(p0, p1, p2, p3, 1), p3) < 1e-9
        assert M.bezier_tangent(p0, p1, p2, p3, 0) == (15, 30)
        pts = M.bezier_points(p0, p1, p2, p3)
        assert pts[0] == (0, 0) and pts[-1] == (20, 3)
        assert all(max(abs(a[0] - b[0]), abs(a[1] - b[1])) == 1 for a, b in zip(pts, pts[1:])), "8-conexa"
        v = M.vogel(50, 2)
        assert len(v) == 50 and abs(math.hypot(*v[49]) - 2 * 7) < 1e-9


    def test_dither_diffusion_keeps_the_mean(self):
        w = h = 48
        field = [x / (w - 1) for y in range(h) for x in range(w)]
        for fn in (M.floyd_steinberg, M.atkinson):
            q = fn(field, w, h, 2)
            assert set(q) <= {0, 1}
            mean = sum(q) / len(q)
            assert abs(mean - sum(field) / len(field)) < (0.03 if fn is M.floyd_steinberg else 0.08), (fn.__name__, mean)


    def test_discrete_geometry(self):
        line = M.line(2, 3, 20, 11)
        assert line[0] == (2, 3) and line[-1] == (20, 11) and {x for x, _ in line} == set(range(2, 21))
        c = M.circle(6)
        assert (6, 0) in c and (0, -6) in c and all(abs(math.hypot(x, y) - 6) < 1 for x, y in c)
        assert M.sd_circle(3, 4, 5) == 0 and M.sd_box(0, 0, 2, 3) == -2 and M.sd_segment(0, 1, -1, 0, 1, 0) == 1

    def test_noise_and_worley_tile_with_a_period(self):
        for i in range(60):
            x, y = i * 0.37, i * 0.73 % 5
            self.assertAlmostEqual(M.value_noise(x, y, 4, period=5), M.value_noise(x + 5, y + 10, 4, period=5), places=12)
            self.assertAlmostEqual(M.fbm(x, y, 4, 3, period=4), M.fbm(x + 4, y - 8, 4, 3, period=4), places=12)
            a, b = M.worley(x, y, 9, 0.9, period=6), M.worley(x + 6, y + 12, 9, 0.9, period=6)
            self.assertAlmostEqual(a[0], b[0], places=9); self.assertEqual(a[2], b[2])


class Palettes(unittest.TestCase):
    def test_builtin_palettes_are_what_their_builders_compute(self):
        self.assertEqual(P.build_mf32()[0], P.MF32)
        self.assertEqual(P.build_mono4()[0], P.MONO4)

    def test_ramps_go_from_dark_to_light(self):
        pal = P.builtin("mf32")
        for name in ("stone", "moss", "sea", "ember", "sun", "dusk"):
            Ls = [pal.lab[i][0] for i in pal.ramp(name)]
            self.assertEqual(Ls, sorted(Ls), name)

    def test_nearest_is_exact_on_palette_colours(self):
        pal = P.builtin("mf32")
        for i, c in enumerate(pal.rgb):
            self.assertEqual(pal.nearest(c), i)

    def test_custom_palette_validation(self):
        with self.assertRaises(ValueError):
            P.get({"colors": ["#zzzzzz"]})
        with self.assertRaises(ValueError):
            P.get({"colors": ["#000000", "#000000"]})
        self.assertEqual(len(P.get({"colors": ["#000000", "#ffffff"]})), 2)

    def test_dithering_never_leaves_the_palette(self):
        pal = P.builtin("mono4")
        w = h = 24
        field = [(x * 10.0, y * 10.0, (x + y) * 5.0) for y in range(h) for x in range(w)]
        for q in (rgb_ordered(field, w, h, pal), rgb_diffused(field, w, h, pal)):
            self.assertTrue(set(q) <= set(range(len(pal))))
        q = to_ramp_ordered([x / 23 for _ in range(h) for x in range(w)], w, h, [3, 2, 1, 0])
        self.assertEqual(q[0], 3); self.assertEqual(q[w - 1], 0)

    def test_canvas_refuses_colours_outside_the_palette(self):
        cv = Canvas(4, 4, P.builtin("mono4"))
        with self.assertRaises(ValueError):
            cv.set(1, 1, 4)


class Png(unittest.TestCase):
    def test_indexed_round_trip_and_canonical_hash(self):
        pal = P.builtin("mf32")
        cv = Canvas(9, 7, pal)
        rng = Rng("png")
        for x, y, _ in list(cv.cells()):
            if rng.chance(0.7):
                cv.set(x, y, rng.randint(0, 31))
        data = cv.to_png()
        w, h, rgba = png.decode(data)
        self.assertEqual((w, h), (9, 7))
        self.assertEqual(rgba, cv.to_rgba())
        self.assertEqual(png.pixels_sha256(w, h, rgba), png.pixels_sha256(9, 7, cv.to_rgba()))
        self.assertEqual(data, cv.to_png(), "same pixels, same bytes")

    def test_rng_is_stable_across_versions(self):
        r = Rng("exactfig")
        self.assertEqual([r.u32() for _ in range(3)], [3710267804, 2040676054, 4049919146], "pinned: xorshift32 of sha256")
        a, b = Rng("abc"), Rng("abc")
        self.assertEqual([a.u32() for _ in range(50)], [b.u32() for _ in range(50)])
        self.assertNotEqual(Rng("abc").u32(), Rng("abd").u32())


if __name__ == "__main__":
    unittest.main()
