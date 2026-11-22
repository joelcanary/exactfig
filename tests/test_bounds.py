"""data.bounds against independent facts:

- the cell grammar: each form allows exactly the integers it should (checked by membership on a range of integers, not by
  comparing to the parser's own tuples), `≥`/`≤` read as `>=`/`<=`, and malformed cells refused;
- the gallery table of van der Waerden numbers: W(2, 3) = 9 recomputed here by brute force over all 2-colourings, the
  exact cells equal to the values in the literature, and every lower bound below the next entries along its row and
  column as the monotone check demands;
- a symmetric table (small Ramsey numbers, R(5, 5) as the range 43..46) passes, and the same table with one cell changed
  is refused; monotone, claims, counts, labels and size are refused when the data say otherwise."""
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
from exactfig.forge import bounds as B  # noqa: E402
from exactfig.render import render  # noqa: E402

GALLERY = os.path.join(os.path.abspath(ROOT), "gallery")
RECIPES = os.path.join(os.path.abspath(ROOT), "examples", "recipes")


def params(**kw):
    p = {"rows": 0, "columns": 0, "exact": -1, "bounded": -1, "monotone": "none", "symmetric": False, "claims": "",
         "text_size": 1, "legend": True}
    p.update(kw)
    return p


def allows(cell, x):
    return (cell[1] is None or cell[1] <= x) and (cell[2] is None or x <= cell[2])


class TestBounds(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="exactfig-bounds-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def read(self, text):
        p = os.path.join(self.dir, "t.bounds")
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        return io.read_bounds(p)

    def test_cell_grammar_by_membership(self):
        want = {"9": lambda x: x == 9, ">170": lambda x: x > 170, ">=171": lambda x: x >= 171, "≥171": lambda x: x >= 171,
                "<46": lambda x: x < 46, "<=45": lambda x: x <= 45, "≤45": lambda x: x <= 45,
                "43..46": lambda x: 43 <= x <= 46, "?": lambda x: True, "-3": lambda x: x == -3}
        for text, f in want.items():
            cell = B.parse_cell(text)
            self.assertEqual([allows(cell, x) for x in range(-10, 300)], [f(x) for x in range(-10, 300)], text)
        self.assertIsNone(B.parse_cell(""))
        self.assertIsNone(B.parse_cell("-"))
        self.assertEqual([B.kind(B.parse_cell(t)) for t in ("9", ">9", "<9", "8..9", "?")],
                         ["exact", "lower", "upper", "range", "unknown"])
        for bad in ("9.5", "> =3", "3..2", "abc", ">", "1,048", "1e3", "=9"):
            with self.assertRaises(ValueError, msg=bad):
                B.parse_cell(bad)

    def test_reader_refuses(self):
        for text, why in (("a,1,2\nx,1\n", "cells"), ("a,1,1\nx,1,2\n", "same label"),
                          ("a,1\nx,1\nx,2\n", "same label"), ("a,1\nx,3..2\n", "empty"),
                          ("a,1\n", "at least one row"), ("a,1\n" + "x" * 17 + ",1\n", "longer")):
            with self.assertRaisesRegex(io.DataError, why):
                self.read(text)

    def test_gallery_table_against_the_literature(self):
        tab = io.read_bounds(os.path.join(GALLERY, "data", "vdw-numbers.bounds"))
        exact = {(r, c[0]): c[1] for r, cells in tab.rows for c in zip(tab.cols, cells) if B.kind(c[1]) == "exact"}
        literature = {("3", "2"): 9, ("3", "3"): 27, ("3", "4"): 76, ("4", "2"): 35, ("4", "3"): 293, ("5", "2"): 178,
                      ("6", "2"): 1132}
        self.assertEqual({k: v[1] for k, v in exact.items()}, literature)

        def colourable(n, k):         # 1..n in 2 colours with no monochromatic k-term progression?
            aps = [[a + i * d for i in range(k)] for d in range(1, n) for a in range(1, n + 1) if a + (k - 1) * d <= n]
            return any(all(len({col[x - 1] for x in ap}) > 1 for ap in aps) for col in product((0, 1), repeat=n))
        self.assertTrue(colourable(8, 3))
        self.assertFalse(colourable(9, 3))                    # so W(2, 3) = 9, as the table says
        r = json.load(open(os.path.join(RECIPES, "vdw-numbers.json"), encoding="utf-8"))
        B.check(tab, params(**r["params"]))                    # the gallery recipe's checks pass

    def test_symmetric_ramsey(self):
        text = "R,3,4,5\n3,6,9,14\n4,9,18,25\n5,14,25,43..46\n"
        tab = self.read(text)
        counts = B.check(tab, params(symmetric=True, monotone="both", exact=8, bounded=1, claims="5,5:43..46"))
        self.assertEqual((counts["exact"], counts["range"]), (8, 1))
        with self.assertRaisesRegex(ValueError, "cell"):
            B.check(self.read(text.replace("4,9,18", "4,10,18")), params(symmetric=True))
        with self.assertRaisesRegex(ValueError, "column labels as row labels"):
            B.check(self.read("R,3,4\n3,6,9\n5,9,18\n"), params(symmetric=True))

    def test_checks_refuse(self):
        tab = self.read("K/R,2,3\n3,9,27\n4,35,>20\n")
        B.check(tab, params(monotone="rows"))                   # 35 before >20: possible (the bound allows 21 and up)
        with self.assertRaisesRegex(ValueError, "cannot come before"):
            B.check(self.read("K/R,2,3\n3,9,8\n"), params(monotone="rows"))
        with self.assertRaisesRegex(ValueError, "cannot come before"):
            B.check(self.read("K/R,2\n3,>50\n4,49\n"), params(monotone="columns"))
        with self.assertRaisesRegex(ValueError, "the table says"):
            B.check(tab, params(claims="4,3:>21"))
        with self.assertRaisesRegex(ValueError, "no row"):
            B.check(tab, params(claims="7,3:9"))
        with self.assertRaisesRegex(ValueError, "row,column:cell"):
            B.check(tab, params(claims="4:9"))
        with self.assertRaisesRegex(ValueError, "exact cells"):
            B.check(tab, params(exact=4))
        with self.assertRaisesRegex(ValueError, "bounds or ranges"):
            B.check(tab, params(bounded=0))
        with self.assertRaisesRegex(ValueError, "rows"):
            B.check(tab, params(rows=3))
        with self.assertRaisesRegex(ValueError, "font has no"):
            B.check(self.read("K\\R,2\n3,9\n"), params())

    def test_render_alt_and_size(self):
        r = json.load(open(os.path.join(RECIPES, "vdw-numbers.json"), encoding="utf-8"))
        out = render(r, GALLERY)
        self.assertEqual(out.data, render(r, GALLERY).data)
        self.assertIn("7 exact values, 13 lower bounds", out.alt)
        self.assertIn("3, 2: 9", out.alt)
        with self.assertRaisesRegex(ValueError, "needs"):
            render(dict(r, size=[100, 40]), GALLERY)


if __name__ == "__main__":
    unittest.main()
