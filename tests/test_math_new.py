"""The four checked generators of 0.5.0, against independent facts:

- ships (data.catalog): Conway's glider and the light, middle and heavy spaceships, simulated; a blinker or a still life
  is not a ship; a ship stated with the wrong shift or period is refused;
- data.triangle: the classical triangles of the congruent numbers 5, 6, 7 and the 48-digit triangle of 157, in exact
  fractions; a triangle that misses by one unit in the last digit is refused;
- data.sequence: the OEIS b-file format, consecutive indices, stated new terms, logarithms of integers of any size;
- math.sandpile: the group order equals the number of spanning trees (the product formula, for small grids), and the
  identity satisfies e ⊕ e = e and differs from the stabilised all-3 configuration."""
import json
import math
import os
import shutil
import sys
import tempfile
import unittest
from fractions import Fraction

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig.data import io  # noqa: E402
from exactfig.forge import catalog as K, sandpile as S, sequence as Q, triangle as T  # noqa: E402
from exactfig.forge.motion import parse_rule  # noqa: E402
from exactfig.render import render  # noqa: E402

GALLERY = os.path.join(os.path.abspath(ROOT), "gallery")
LIFE = parse_rule("B3/S23")


class Tmp(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="exactfig-new-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def file(self, text):
        p = os.path.join(self.dir, "d.txt")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return p


def cat_params(**kw):
    p = {"rule": "B3/S23", "check": "ship", "period": 4, "shift": "1,1", "strict": False, "population": 0, "count": 0,
         "distinct": True}
    p.update(kw)
    return p


class Ships(Tmp):
    GLIDER = "3x3: .O. ..O OOO"

    def ships(self, *lines):
        return io.load(self.file("\n".join(lines) + "\n"), "patterns", "catalog").patterns

    def test_glider_and_the_three_orthogonal_ships(self):
        K.check(self.ships(self.GLIDER), cat_params())
        pats = io.load(os.path.join(GALLERY, "data", "conway-ships.txt"), "patterns", "catalog").patterns
        K.check(pats, cat_params(shift="-2,0", count=3))
        self.assertEqual([len(p) for p in pats], [9, 11, 13])

    def test_false_ships_are_refused(self):
        cases = [((self.GLIDER,), cat_params(shift="-1,1"), "moved by (1, 1)"),
                 ((self.GLIDER,), cat_params(period=8, shift="1,1"), "already a translate after 4"),
                 (("3x1: OOO",), cat_params(period=2), "moved by (0, 0)"),            # an oscillator
                 (("2x2: OO OO",), cat_params(period=1), "moved by (0, 0)"),
                 ((self.GLIDER,), cat_params(shift="0,0"), "oscillator"),
                 ((self.GLIDER,), cat_params(shift="x"), "dx,dy")]
        for lines, p, words in cases:
            with self.assertRaises(ValueError, msg=(lines, p)) as cm:
                K.check(self.ships(*lines), p)
            self.assertIn(words, str(cm.exception))

    def test_translations_follow_the_glider(self):
        cells = [(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)]
        self.assertEqual(K.translations(cells, LIFE, 8), [None, None, None, (1, 1), None, None, None, (2, 2)])


def tri_params(**kw):
    p = {"squarefree": True, "distinct": True, "count": 0}
    p.update(kw)
    return p


class Triangles(Tmp):
    def test_the_classical_triangles_and_157(self):
        tris = io.load(os.path.join(GALLERY, "data", "congruent-triangles.txt"), "triangles", "triangles").triangles
        T.check(tris, tri_params(count=4))
        n, a, b, c = tris[3]
        self.assertEqual(n, 157)
        self.assertEqual(len(str(c.numerator)), 48)
        self.assertEqual(a * a + b * b, c * c)                                  # independent of exactfig's check

    def test_wrong_triangles_are_refused_with_the_exact_difference(self):
        cases = [("6 3 4 6\n", "a² + b² − c² = -11"), ("6 3 4 5\n6 3 4 5\n", "already appears"),
                 ("12 3 8 73/1\n", "not a right triangle"), ("24 6 8 10\n", "not squarefree"),
                 ("5 3/2 20/3 41/6\n7 3/2 20/3 41/6\n", "a·b/2 = 5, not 7"), ("6 -3 -4 5\n", "positive"),
                 ("6 3 4\n", "4 numbers"), ("6 3.0 4 5\n", "not an integer or a fraction"), ("6 3/0 4 5\n", "zero")]
        for text, words in cases:
            with self.assertRaises((ValueError, io.DataError), msg=text) as cm:
                T.check(io.load(self.file(text), "triangles", "triangles").triangles, tri_params())
            self.assertIn(words, str(cm.exception))

    def test_one_unit_off_in_the_last_digit_of_157(self):
        with open(os.path.join(GALLERY, "data", "congruent-triangles.txt"), encoding="utf-8") as fh:
            line = [l for l in fh if l.startswith("157 ")][0]
        bad = line.replace("8912332268928859588025535178967163570016480830", "8912332268928859588025535178967163570016480831")
        with self.assertRaises(ValueError):
            T.check(io.load(self.file(bad), "triangles", "triangles").triangles, tri_params())

    def test_squarefree(self):
        self.assertEqual([n for n in range(1, 20) if T.squarefree(n)], [1, 2, 3, 5, 6, 7, 10, 11, 13, 14, 15, 17, 19])


def seq_params(**kw):
    p = {"scale": "log", "new_from": -1, "terms": "", "first": -1, "last": -1, "count": 0, "nonneg": True}
    p.update(kw)
    return p


class Sequences(Tmp):
    def test_bfile_reader(self):
        s = io.load(self.file("# A000045\n\n0 0\n1 1\n2 1\n3 2\n"), "sequence", "bfile")
        self.assertEqual(s.terms, [(0, 0), (1, 1), (2, 1), (3, 2)])
        for bad in ("0 0\n2 1\n", "0 0\n0 1\n", "0 x\n", "0 1 2\n", "# nothing\n"):
            with self.assertRaises(io.DataError, msg=bad):
                io.load(self.file(bad), "sequence", "bfile")

    def test_the_published_terms_of_a175001(self):
        s = io.load(os.path.join(GALLERY, "data", "b175001.txt"), "sequence", "bfile")
        Q.check(s, seq_params(new_from=11, terms="6,10,18,49,103,228,376,745", first=1, last=18, count=18))
        for p, words in ((seq_params(new_from=11, terms="6,10,18,49,103,228,376,746"), "n = 18"),
                         (seq_params(new_from=11, terms="6,10,18"), "first difference at n = 14"),
                         (seq_params(terms="6"), "new_from"), (seq_params(last=19), "ends at n = 18"),
                         (seq_params(count=17), "18 terms")):
            with self.assertRaises(ValueError, msg=p) as cm:
                Q.check(s, p)
            self.assertIn(words, str(cm.exception))

    def test_logarithms_of_huge_integers(self):
        for k in (1, 10, 300, 307, 400, 5000):
            v = 10 ** k
            self.assertAlmostEqual(Q.log10_int(v), k, places=9)
        self.assertAlmostEqual(Q.log10_int(3 * 10 ** 4000), 4000 + math.log10(3), places=9)


class Sandpile(unittest.TestCase):
    def test_group_order_is_the_number_of_spanning_trees(self):
        for n in range(1, 6):                                              # the product formula is exact enough here
            prod = 1.0
            for j in range(1, n + 1):
                for k in range(1, n + 1):
                    prod *= 4 - 2 * math.cos(j * math.pi / (n + 1)) - 2 * math.cos(k * math.pi / (n + 1))
            self.assertEqual(S.group_order(n), round(prod), n)
        self.assertEqual(S.group_order(2), 192)

    def test_identity(self):
        for n in (1, 2, 5, 17, 40):
            e = S.identity(n)
            self.assertTrue(all(0 <= v <= 3 for v in e))
            self.assertEqual(S.stabilise([2 * v for v in e], n), e)        # e ⊕ e = e
            m = S.stabilise([3] * (n * n), n)
            self.assertEqual(S.stabilise([a + b for a, b in zip(m, e)], n), m)   # e is neutral for the all-3 one
        self.assertEqual(S.identity(1), [0])                               # one cell: the group is Z/4, identity 0

    def test_stated_order(self):
        p = {"order": "192"}
        S.check(S.identity(2), 2, p)
        with self.assertRaises(ValueError):
            S.check(S.identity(2), 2, {"order": "193"})
        with self.assertRaises(ValueError):
            S.check(S.identity(15), 15, {"order": "1"})                    # too large to check: refused, not trusted


class Recipes(unittest.TestCase):
    def test_gallery_recipes_render(self):
        for name in ("conway-ships", "congruent-triangles", "oeis-a175001"):
            with open(os.path.join(ROOT, "examples", "recipes", name + ".json"), encoding="utf-8") as fh:
                render(json.load(fh), GALLERY)
        render({"generator": "math.sandpile", "seed": "s", "palette": "sci", "size": [24, 24],
                "params": {"n": 12, "order": str(S.group_order(12))}})


if __name__ == "__main__":
    unittest.main()
