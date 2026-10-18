"""Data input, fields and scattered-data reconstruction, checked against independent facts: what other readers of the
same standard formats return, exact geometry (rational arithmetic), interpolation theory, and closed-form surfaces."""
import json
import math
import os
import shutil
import struct
import sys
import tempfile
import unittest
from fractions import Fraction

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig import fmath as fm, provenance  # noqa: E402
from exactfig.data import field as F, io, scatter as S  # noqa: E402
from exactfig.pixel import palette as P  # noqa: E402
from exactfig.render import normalize, render  # noqa: E402
from exactfig.rng import Rng  # noqa: E402

GALLERY = os.path.join(os.path.abspath(ROOT), "gallery")


class Tmp(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="exactfig-data-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def file(self, name, data):
        p = os.path.join(self.dir, name)
        with open(p, "wb" if isinstance(data, bytes) else "w", **({} if isinstance(data, bytes) else {"encoding": "utf-8"})) as fh:
            fh.write(data)
        return p


class Readers(Tmp):
    def test_csv_grid_separators_comments_and_missing_values(self):
        for text in ("1,2,3\n4,,6\n", "# a comment\n1;2;3\n4;nan;6\n", "1\t2\t3\n4\tNA\t6\n", "1 2 3  # end\n4 nan 6\n"):
            g = io.read_grid_csv(self.file("g.csv", text))
            self.assertEqual((g.width, g.height), (3, 2))
            self.assertEqual(g.values[0], [1.0, 2.0, 3.0])
            self.assertTrue(math.isnan(g.values[1][1]))

    def test_csv_points_with_and_without_header(self):
        for text in ("x,y,value\n0,0,1\n1,0,2\n0,1,3\n", "0 0 1\n1 0 2\n0 1 3\n"):
            p = io.read_points_csv(self.file("p.csv", text))
            self.assertEqual((p.xs, p.ys, p.vs), ([0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [1.0, 2.0, 3.0]))

    def test_pgm_ascii_binary_8_and_16_bit(self):
        rows = [[0, 1, 2], [300, 65535, 7]]
        p16 = os.path.join(self.dir, "a.pgm")
        io.write_pgm(p16, rows, 65535)
        self.assertEqual(io.read_pgm(p16).values, [[float(v) for v in r] for r in rows])
        p8 = self.file("b.pgm", b"P5\n# made by hand\n3 1\n255\n" + bytes([0, 128, 255]))
        self.assertEqual(io.read_pgm(p8).values, [[0.0, 128.0, 255.0]])
        p2 = self.file("c.pgm", "P2\n2 2\n# comment\n15\n0 15\n7 8\n")
        self.assertEqual(io.read_pgm(p2).values, [[0.0, 15.0], [7.0, 8.0]])

    def npy(self, descr, shape, payload, fortran=False, name="a.npy"):
        header = "{'descr': '%s', 'fortran_order': %s, 'shape': (%d, %d), }" % (descr, fortran, *shape)
        header += " " * ((64 - (10 + len(header) + 1) % 64) % 64) + "\n"
        return self.file(name, b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header.encode() + payload)

    def test_npy_dtypes_byte_orders_and_fortran_order(self):
        vals = [1, -2, 3, 4, 5, -6]
        for descr, code in (("<f8", "<6d"), (">f8", ">6d"), ("<f4", "<6f"), ("<i2", "<6h"), (">i4", ">6i"), ("<f2", "<6e")):
            g = io.read_npy(self.npy(descr, (2, 3), struct.pack(code, *vals)))
            self.assertEqual(g.values, [[1.0, -2.0, 3.0], [4.0, 5.0, -6.0]], descr)
        g = io.read_npy(self.npy("|u1", (2, 3), bytes([1, 4, 2, 5, 3, 6]), fortran=True))   # column-major on disk
        self.assertEqual(g.values, [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        p = os.path.join(self.dir, "w.npy")
        io.write_npy(p, [[0.5, 1.5], [2.5, -3.25]])
        self.assertEqual(io.read_npy(p).values, [[0.5, 1.5], [2.5, -3.25]])

    def test_npy_agrees_with_numpy_when_it_is_installed(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not installed (optional cross-check)")
        p = os.path.join(self.dir, "n.npy")
        for dt in ("<f4", ">f8", "<i2", ">u2", "|u1", "<f2", "<i8"):
            for order in ("C", "F"):
                x = np.asarray((np.arange(12).reshape(3, 4) * 3 - 5).astype(dt), order=order)
                np.save(p, x)
                self.assertEqual(io.read_npy(p).values, x.astype(float).tolist(), (dt, order))
        io.write_npy(p, [[1.0, 2.0], [3.0, 4.0]])
        self.assertEqual(np.load(p).tolist(), [[1.0, 2.0], [3.0, 4.0]])

    def test_json_grid_and_points(self):
        g = io.read_grid_json(self.file("g.json", json.dumps({"values": [[1, None], [3, 4.5]]})))
        self.assertTrue(math.isnan(g.values[0][1]))
        self.assertEqual(g.values[1], [3.0, 4.5])
        a = io.read_points_json(self.file("p.json", json.dumps({"points": [[0, 0, 1], [1, 0, 2], [0, 1, 3]]})))
        b = io.read_points_json(self.file("q.json", json.dumps({"x": [0, 1, 0], "y": [0, 0, 1], "value": [1, 2, 3]})))
        self.assertEqual((a.xs, a.ys, a.vs), (b.xs, b.ys, b.vs))

    def test_bad_files_are_refused_with_a_reason(self):
        bad = [
            (io.read_grid_csv, self.file("r.csv", "1,2,3\n4,5\n"), "row 2"),
            (io.read_grid_csv, self.file("t.csv", "1,x\n"), "not a number"),
            (io.read_grid_csv, self.file("i.csv", "1,inf\n"), "infinite"),
            (io.read_points_csv, self.file("d.csv", "0,0,1\n0,0,2\n1,1,1\n"), "duplicate"),
            (io.read_points_csv, self.file("m.csv", "0,0,1\n1,0,\n1,1,1\n"), "missing"),
            (io.read_pgm, self.file("s.pgm", b"P5\n4 4\n255\n\x00\x01"), "truncated"),
            (io.read_npy, self.npy("|O", (1, 1), b"\x00" * 8, name="o.npy"), "dtype"),
            (io.read_npy, self.npy("<f8", (2, 2), b"\x00" * 8, name="short.npy"), "data bytes"),
            (io.read_npy, self.file("h.npy", b"\x93NUMPY\x01\x00\x10\x00__import__('os') \n"), "header"),
        ]
        for fn, path, why in bad:
            with self.assertRaises(io.DataError, msg=path) as cm:
                fn(path)
            self.assertIn(why, str(cm.exception))


class Delaunay(unittest.TestCase):
    def exact_checks(self, xs, ys):
        T = S.delaunay(xs, ys)
        Q = [(Fraction(x), Fraction(y)) for x, y in zip(xs, ys)]

        def orient(a, b, c):
            return (Q[b][0] - Q[a][0]) * (Q[c][1] - Q[a][1]) - (Q[b][1] - Q[a][1]) * (Q[c][0] - Q[a][0])

        def incircle(a, b, c, d):
            m = [(Q[i][0] - Q[d][0], Q[i][1] - Q[d][1]) for i in (a, b, c)]
            m = [(u, v, u * u + v * v) for u, v in m]
            return (m[0][0] * (m[1][1] * m[2][2] - m[2][1] * m[1][2]) - m[1][0] * (m[0][1] * m[2][2] - m[2][1] * m[0][2])
                    + m[2][0] * (m[0][1] * m[1][2] - m[1][1] * m[0][2]))

        self.assertTrue(all(orient(*t) > 0 for t in T), "every triangle counter-clockwise and non-degenerate")
        self.assertFalse([(t, d) for t in T for d in range(len(xs)) if d not in t and incircle(*t, d) > 0],
                         "empty circumcircle property")
        return T, sum(orient(*t) for t in T) / 2

    def test_random_points_satisfy_the_empty_circle_property(self):
        r = Rng("delaunay")
        xs = [r.random() for _ in range(120)]
        ys = [r.random() for _ in range(120)]
        T, _ = self.exact_checks(xs, ys)
        # Euler: a triangulation of n points with h on the hull (vertices of the convex hull, counted with collinear ones)
        self.assertEqual(len(T), 2 * 120 - 2 - self.hull_size(xs, ys))

    @staticmethod
    def hull_size(xs, ys):
        pts = sorted(set(zip(xs, ys)))

        def cross(o, a, b):
            return (Fraction(a[0]) - Fraction(o[0])) * (Fraction(b[1]) - Fraction(o[1])) - (Fraction(a[1]) - Fraction(o[1])) * (Fraction(b[0]) - Fraction(o[0]))
        lo, hi = [], []
        for p in pts:
            while len(lo) >= 2 and cross(lo[-2], lo[-1], p) < 0:
                lo.pop()
            lo.append(p)
        for p in reversed(pts):
            while len(hi) >= 2 and cross(hi[-2], hi[-1], p) < 0:
                hi.pop()
            hi.append(p)
        return len(lo) + len(hi) - 2              # keeps collinear hull points (cross == 0 is not popped)

    def test_cocircular_and_collinear_points_are_handled_exactly(self):
        g = [(i / 7, j / 7) for i in range(8) for j in range(8)]          # every cell's four corners are co-circular
        T, area = self.exact_checks([p[0] for p in g], [p[1] for p in g])
        self.assertEqual(area, 1)                                          # covers the square exactly
        self.assertEqual(len(T), 2 * 64 - 2 - 28)
        T, area = self.exact_checks([0.0, 1.0, 2.0, 3.0, 0.0, 1.0, 2.0, 3.0], [0.0] * 4 + [1.0] * 4)
        self.assertEqual(area, 3)
        with self.assertRaises(S.ScatterError):
            S.delaunay([0.0, 1.0, 2.0], [0.0, 1.0, 2.0])

    def test_linear_interpolation_reproduces_affine_functions(self):
        r = Rng("affine")
        xs = [r.uniform(-3.0, 5.0) for _ in range(60)]
        ys = [r.uniform(1.0, 2.0) for _ in range(60)]
        vs = [2.5 * x - 4.0 * y + 7.0 for x, y in zip(xs, ys)]
        box = S.bbox(xs, ys)
        z = S.linear(xs, ys, vs, 40, 30, box)
        x0, x1, y0, y1 = box
        worst = max(abs(v - (2.5 * (x0 + (i % 40 + 0.5) / 40 * (x1 - x0)) - 4.0 * (y1 - (i // 40 + 0.5) / 30 * (y1 - y0)) + 7.0))
                    for i, v in enumerate(z) if v == v)
        self.assertLess(worst, 1e-11)
        self.assertGreater(sum(v == v for v in z), 0.6 * 1200)            # most of the box is inside the hull

    def test_linear_reconstruction_converges_on_franke(self):
        """The error of piecewise-linear interpolation falls like h² (h ~ n^(-1/2)): four times the samples, about a
        quarter of the error."""
        def franke(x, y):
            return (0.75 * fm.exp(-((9 * x - 2) ** 2 + (9 * y - 2) ** 2) / 4) + 0.75 * fm.exp(-((9 * x + 1) ** 2) / 49 - (9 * y + 1) / 10)
                    + 0.5 * fm.exp(-((9 * x - 7) ** 2 + (9 * y - 3) ** 2) / 4) - 0.2 * fm.exp(-(9 * x - 4) ** 2 - (9 * y - 7) ** 2))

        def rms(n):
            g = [(i / (n - 1), j / (n - 1)) for i in range(n) for j in range(n)]
            xs, ys = [p[0] for p in g], [p[1] for p in g]
            z = S.linear(xs, ys, [franke(x, y) for x, y in g], 64, 64, (0.0, 1.0, 0.0, 1.0))
            e = [(v - franke((i % 64 + 0.5) / 64, 1 - (i // 64 + 0.5) / 64)) ** 2 for i, v in enumerate(z)]
            return math.sqrt(sum(e) / len(e))
        coarse, fine = rms(9), rms(17)                                     # h halves
        self.assertLess(fine, coarse / 3.0)

    def test_nearest_is_the_closest_sample(self):
        xs, ys, vs = [0.0, 1.0, 0.0, 1.0, 0.5], [0.0, 0.0, 1.0, 1.0, 0.5], [1.0, 2.0, 3.0, 4.0, 5.0]
        z = S.nearest(xs, ys, vs, 10, 10)
        self.assertEqual(z[0], 3.0)                                        # top-left pixel: closest to (0, 1)
        self.assertEqual(z[5 * 10 + 5], 5.0)                               # centre
        self.assertEqual(z[9 * 10 + 9], 2.0)                               # bottom-right: closest to (1, 0)


class Fields(unittest.TestCase):
    def test_contour_of_a_cone_is_a_circle(self):
        w = h = 81
        z = [fm.sqrt((i - 40) * (i - 40) + (j - 40) * (j - 40)) for j in range(h) for i in range(w)]
        segs = F.contours(z, w, h, 25.0)
        self.assertGreater(len(segs), 100)
        for x0, y0, x1, y1 in segs:
            for x, y in ((x0, y0), (x1, y1)):
                self.assertAlmostEqual(fm.sqrt((x - 40.5) * (x - 40.5) + (y - 40.5) * (y - 40.5)), 25.0, delta=0.05)

    def test_saddle_cell_follows_the_centre_value(self):
        z = [1.0, 0.0, 0.0, 1.0]                                           # tl, tr / bl, br: a saddle, centre 0.5
        self.assertEqual(len(F.contours(z, 2, 2, 0.4)), 2)                 # centre above: the two low corners cut off
        a = F.contours(z, 2, 2, 0.4)
        b = F.contours(z, 2, 2, 0.6)
        self.assertNotEqual(sorted(a), sorted(b))

    def test_hillshade_of_a_dome_and_a_plane(self):
        w = h = 41
        dome = [fm.sqrt(max(0.0, 4 - ((i - 20) / 10) ** 2 - ((20 - j) / 10) ** 2)) for j in range(h) for i in range(w)]
        s = F.hillshade(dome, w, h, 0.1, 315.0, 45.0)
        self.assertGreater(s[10 * w + 10], 0.95)                           # north-west flank faces the light
        self.assertLess(s[30 * w + 30], 0.05)                              # south-east flank faces away
        self.assertAlmostEqual(s[20 * w + 20], fm.cos(fm.radians(45.0)), places=12)   # flat top: cos(zenith)
        plane = [(i - 20) * 0.1 for j in range(h) for i in range(w)]       # rises east at 45°
        self.assertAlmostEqual(F.hillshade(plane, w, h, 0.1, 270.0, 45.0)[20 * w + 20], 1.0, places=12)
        self.assertAlmostEqual(F.hillshade(plane, w, h, 0.1, 90.0, 45.0)[20 * w + 20], 0.0, places=12)

    def test_bilinear_sampling_keeps_missing_cells_out(self):
        g = io.Grid(2, 1, [[1.0, math.nan]])
        z = F.sample(g, 4, 1)
        self.assertEqual(z[:3], [1.0, 1.0, 1.0])                          # weights renormalised over the finite cell only
        self.assertTrue(math.isnan(z[3]))                                  # no finite neighbour: stays missing


class SciencePalette(unittest.TestCase):
    def test_frozen_values_and_perceptual_order(self):
        self.assertEqual(P.build_sci()[0], P.SCI)
        pal = P.builtin("sci")
        L = [pal.lab[i][0] for i in pal.ramp("seq")]
        self.assertEqual(L, sorted(L))
        self.assertTrue(all(b - a > 0.05 for a, b in zip(L, L[1:])), "every step visibly lighter")
        D = [pal.lab[i][0] for i in pal.ramp("div")]
        self.assertTrue(all(abs(D[k] - D[-1 - k]) < 0.01 for k in range(len(D))), "diverging ramp symmetric in lightness")
        self.assertLess(math.hypot(pal.lab[pal.ramp("div")[5]][1], pal.lab[pal.ramp("div")[5]][2]), 0.005, "neutral centre")


class SchemaAgreement(unittest.TestCase):
    def test_the_manifest_schema_lists_exactly_the_formats_the_readers_accept(self):
        """Checked without jsonschema: the schema's enum of input formats and data/io.FORMATS must not drift apart."""
        with open(os.path.join(ROOT, "exactfig", "provenance", "manifest.schema.json"), encoding="utf-8") as fh:
            schema = json.load(fh)
        enum = schema["$defs"]["asset"]["properties"]["recipe"]["properties"]["input"]["properties"]["format"]["enum"]
        self.assertEqual(sorted(enum), sorted({f for fmts in io.FORMATS.values() for f in fmts}))


class DataProvenance(Tmp):
    def test_example_datasets_regenerate_byte_for_byte(self):
        sys.path.insert(0, os.path.join(ROOT, "examples", "data"))
        import make_data
        for p in make_data.make(self.dir):
            with open(p, "rb") as a, open(os.path.join(GALLERY, "data", os.path.basename(p)), "rb") as b:
                self.assertEqual(a.read(), b.read(), os.path.basename(p))

    def test_a_changed_input_byte_is_caught(self):
        shutil.copytree(os.path.join(GALLERY, "data"), os.path.join(self.dir, "data"))
        with open(os.path.join(ROOT, "examples", "recipes", "franke-linear.json"), encoding="utf-8") as fh:
            recipe = dict(json.load(fh), output="f.png", size=[32, 32])
        rf = self.file("f.json", json.dumps(recipe))
        man = os.path.join(self.dir, "manifest.json")
        provenance.record([rf], man, log=lambda *_: None)
        self.assertTrue(all(c.ok for c in provenance.verify(man)[0]))
        csv = os.path.join(self.dir, "data", "franke-halton-256.csv")
        with open(csv, "r+b") as fh:
            fh.seek(40)
            b = fh.read(1)
            fh.seek(40)
            fh.write(b"7" if b != b"7" else b"8")
        checks, _ = provenance.verify(man)
        self.assertFalse(checks[0].ok)
        self.assertIn("changed", checks[0].problems[0])

    def test_input_paths_cannot_leave_their_folder(self):
        base = {"generator": "data.field", "seed": "x", "palette": "sci", "size": [8, 8]}
        for path in ("../secret.csv", "/etc/passwd", "C:/x.csv", "a/../../b.csv", "a\\b.csv", ""):
            with self.assertRaises(ValueError, msg=path):
                normalize(dict(base, input={"path": path, "sha256": "0" * 64}))
        with self.assertRaises(ValueError):
            normalize(dict(base, input={"path": "data/plate-129.npy", "sha256": "0" * 64, "extra": 1}))
        with self.assertRaises(ValueError):
            normalize({"generator": "forge.icon.gem", "seed": "g", "input": {"path": "a.csv"}})

    def test_pinned_hash_must_match(self):
        r = {"generator": "data.field", "seed": "x", "palette": "sci", "size": [8, 8],
             "input": {"path": "data/plate-129.npy", "sha256": "0" * 64}}
        with self.assertRaises(ValueError) as cm:
            render(r, GALLERY)
        self.assertIn("changed", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
