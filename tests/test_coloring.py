"""data.coloring: the colouring reader and the checks a witness must pass before it is drawn, against independent facts —
van der Waerden W(2;3) = 9, Schur S(2) = 4 and S(3) >= 13, the weak Schur number WS(2) = 8 (each decided here by brute
force over every colouring), and a SAT witness for w(4; 2,3,3,3) = 40 (OEIS A217008)."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from itertools import product

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig.data import io  # noqa: E402
from exactfig.forge import coloring as K  # noqa: E402
from exactfig.render import render  # noqa: E402

GALLERY = os.path.join(os.path.abspath(ROOT), "gallery")


def params(**kw):
    p = {"check": "ap", "lengths": "3", "distinct": False, "colors": 0, "length": 0, "count": 0, "proof_sha256": ""}
    p.update(kw)
    return p


def passes(col, **kw):
    try:
        K.check([tuple(col)], params(**kw))
        return True
    except ValueError:
        return False


class Reader(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="exactfig-coloring-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def read(self, text):
        path = os.path.join(self.dir, "c.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return io.load(path, "colorings", "coloring").colorings

    def test_digits_numbers_commas_and_comments(self):
        self.assertEqual(self.read("# c\n! d\n0110\n0 1 1 12\n3,2,1\n"), [(0, 1, 1, 0), (0, 1, 1, 12), (3, 2, 1)])

    def test_bad_input_is_refused_naming_the_line(self):
        for bad in ("01a1", "0 -1 1", "0 1.5", "0 64"):
            with self.assertRaises(io.DataError, msg=bad) as cm:
                self.read("# header\n" + bad + "\n")
            self.assertIn("line 2", str(cm.exception))
        with self.assertRaises(io.DataError):
            self.read("# nothing\n")


class Rules(unittest.TestCase):
    def test_progressions_and_sums(self):
        self.assertEqual(K.progression([1, 2, 4, 7, 10], 3), [1, 4, 7])
        self.assertIsNone(K.progression([1, 2, 4, 8], 3))
        self.assertEqual(K.progression([5], 1), [5])
        self.assertIsNone(K.progression([5], 2))
        self.assertEqual(K.sum_in_class([2, 4], False), (2, 2, 4))          # x = y counts for Schur numbers
        self.assertIsNone(K.sum_in_class([2, 4], True))                     # but not for weak Schur numbers
        self.assertEqual(K.sum_in_class([1, 2, 3], True), (1, 2, 3))

    def test_van_der_waerden_w_2_3_is_9(self):
        """Some 2-colouring of 1..8 has no monochromatic 3-term progression; every one of the 512 colourings of 1..9
        has one."""
        self.assertTrue(any(passes(c) for c in product((0, 1), repeat=8)))
        self.assertFalse(any(passes(c) for c in product((0, 1), repeat=9)))

    def test_schur_s2_is_4_and_s3_at_least_13(self):
        self.assertTrue(any(passes(c, check="schur") for c in product((0, 1), repeat=4)))
        self.assertFalse(any(passes(c, check="schur") for c in product((0, 1), repeat=5)))
        self.assertTrue(passes([int(c) for c in "0110222220110"], check="schur", colors=3, length=13))

    def test_weak_schur_ws2_is_8(self):
        self.assertTrue(any(passes(c, check="schur", distinct=True) for c in product((0, 1), repeat=8)))
        self.assertFalse(any(passes(c, check="schur", distinct=True) for c in product((0, 1), repeat=9)))

    def test_each_false_statement_is_refused_with_the_witness_of_the_failure(self):
        cases = [
            ([0, 0, 0], params(), "1, 2, 3"),            # a monochromatic 3-term progression
            ([0, 1], params(count=2), "states 2"),
            ([0, 1, 1, 0], params(length=5), "1..5"),
            ([0, 1, 2], params(colors=2), "2 colours"),
            ([0, 1], params(lengths="2,3,3", colors=2), "3 colours"),
            ([0, 1], params(proof_sha256="xyz"), "64"),
            ([0, 1, 1], params(lengths="3,2"), "2-term progression 2, 3"),
            ([1, 1, 0, 1], params(check="schur"), "1 + 1 = 2"),
        ]
        for col, p, words in cases:
            with self.assertRaises(ValueError, msg=(col, p)) as cm:
                K.check([tuple(col)], p)
            self.assertIn(words, str(cm.exception))
        with self.assertRaises(ValueError):
            K.parse_lengths("three")


class SatWitness(unittest.TestCase):
    """gallery/data/vdw-2-3-3-3.txt: a SAT solver's colouring of 1..39 for w(4; 2,3,3,3) = 40."""

    def setUp(self):
        self.col = io.load(os.path.join(GALLERY, "data", "vdw-2-3-3-3.txt"), "colorings", "coloring").colorings

    def test_it_is_a_witness(self):
        K.check(self.col, params(lengths="2,3,3,3", colors=4, length=39, count=1))
        self.assertEqual(self.col[0].count(0), 1)                       # colour 0 (length 2) is used exactly once

    def test_it_is_not_a_witness_for_a_stronger_statement(self):
        with self.assertRaises(ValueError):
            K.check(self.col, params(lengths="2,2,3,3", colors=4))       # colour 1 used more than once
        with self.assertRaises(ValueError):
            K.check(self.col, params(lengths="3", length=40))

    def test_every_extension_to_40_breaks_it(self):
        """Consistent with w = 40: none of the four colours can be given to 40 (a necessary condition, not the proof)."""
        for c in range(4):
            self.assertFalse(passes(self.col[0] + (c,), lengths="2,3,3,3", colors=4))

    def test_the_recipes_render_and_name_the_proof(self):
        for name in ("vdw-2-3-3-3", "schur-3"):
            with open(os.path.join(ROOT, "examples", "recipes", name + ".json"), encoding="utf-8") as fh:
                recipe = json.load(fh)
            render(recipe, GALLERY)
        with open(os.path.join(ROOT, "examples", "recipes", "vdw-2-3-3-3.json"), encoding="utf-8") as fh:
            recipe = json.load(fh)
        self.assertRegex(recipe["params"]["proof_sha256"], r"^[0-9a-f]{64}$")
        recipe["params"]["length"] = 40
        with self.assertRaises(ValueError):
            render(recipe, GALLERY)


if __name__ == "__main__":
    unittest.main()
