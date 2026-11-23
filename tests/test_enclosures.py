"""data.enclosures against independent facts:

- decimals are read exactly: each parsed number equals the fraction written by hand, and malformed or oversized numbers
  are refused;
- the digits by which a ball misses 0 equal the definition (the largest d with |c| ≥ 10^d · r), checked by brute force on
  integer data with Python's exact integer square root, not with the module's own logarithms;
- the gallery file: every ball excludes 0, its distance from 0 agrees with the lower bounds quoted in the papers, and
  Peterson's published value lies in his ball, all recomputed here with the decimal module at 120 digits;
- a ball that contains 0, a false bound, a value outside the tolerance, too few digits and a wrong count are refused."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from decimal import Decimal, getcontext
from fractions import Fraction
from math import isqrt

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig.data import io  # noqa: E402
from exactfig.forge import enclosures as E  # noqa: E402
from exactfig.render import render  # noqa: E402

GALLERY = os.path.join(os.path.abspath(ROOT), "gallery")
RECIPES = os.path.join(os.path.abspath(ROOT), "examples", "recipes")


def params(**kw):
    p = {"rows": 0, "min_digits": 0, "claims": "", "agrees": "", "text_size": 1, "legend": True}
    p.update(kw)
    return p


class TestEnclosures(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="exactfig-enclosures-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def read(self, text):
        p = os.path.join(self.dir, "t.enclosures")
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        return io.read_enclosures(p)

    def test_decimals_are_exact(self):
        for text, want in (("3.88e-46", Fraction(388, 10 ** 48)), ("-0.5", Fraction(-1, 2)), ("12", Fraction(12)),
                           ("1.9215e+1", Fraction(192150, 10 ** 4)), ("+7E2", Fraction(700)),
                           ("0.1", Fraction(1, 10))):
            self.assertEqual(E.parse_decimal(text), want, text)
        for bad in ("", "abc", "1.", ".5", "1e", "1e2000", "1,5", "0x10", "nan", "inf", "1" * 4001):
            with self.assertRaises(ValueError, msg=bad[:20]):
                E.parse_decimal(bad)

    def test_digits_by_definition(self):
        for a, b, r in ((3, 4, Fraction(1, 10)), (3, 4, Fraction(1, 2)), (3, 4, Fraction(49, 10)),
                        (1, 0, Fraction(1, 10 ** 30)), (10 ** 6, 0, Fraction(1)), (7, 24, Fraction(25, 10 ** 9))):
            c2 = Fraction(a * a + b * b)
            want = max(d for d in range(-5, 80) if c2 >= Fraction(10) ** (2 * d) * r * r)
            self.assertEqual(E.digits_missed(c2, r), want, (a, b, r))
        # |3 + 4i| = 5 exactly: a ball of radius 5 touches 0 and is refused, 4.9 passes by 0 digits
        with self.assertRaisesRegex(ValueError, "contains 0"):
            E.check([("A", Fraction(3), Fraction(4), Fraction(5))], params())
        self.assertEqual(E.check([("A", Fraction(3), Fraction(4), Fraction(49, 10))], params())[0][3], 0)

    def test_gallery_against_the_papers(self):
        data = io.read_enclosures(os.path.join(GALLERY, "data", "hodge-residues.enclosures"))
        getcontext().prec = 120
        papers = {"D35 I34": "30.35", "D44 I02": "0.189", "D51A I04": "1.557", "D51B I23": "4.598",
                  "D52A I02": "19.95", "D52B I12": "7.723"}
        self.assertEqual(sorted(lab for lab, *_ in data.rows), sorted(papers))
        for lab, re_, im, r in data.rows:
            dre = Decimal(re_.numerator) / Decimal(re_.denominator)
            dim = Decimal(im.numerator) / Decimal(im.denominator)
            dr = Decimal(r.numerator) / Decimal(r.denominator)
            dist = (dre * dre + dim * dim).sqrt()
            self.assertGreater(dist - dr, Decimal(papers[lab]), lab)
            self.assertLess(dr, Decimal("1e-9"), lab)
        pet = next(row for row in data.rows if row[0] == "D35 I34")
        diff = Fraction("29.588332077128010399") - pet[1], Fraction("-6.7688877382028338180") - pet[2]
        n = diff[0] ** 2 + diff[1] ** 2                         # his value within 1e-18 of every point of the ball
        bound = Fraction(1, 10 ** 18) - pet[3]
        self.assertTrue(bound > 0 and n <= bound * bound)
        with open(os.path.join(RECIPES, "hodge-residues.json"), encoding="utf-8") as fh:
            r = json.load(fh)
        rows = E.check(data.rows, params(**r["params"]))
        self.assertEqual({lab: d for lab, _, _, d in rows}["D44 I02"], 9)

    def test_reader_refuses(self):
        for text, why in (("A, 1, 0\n", "4 fields|3 fields"), ("A, 1, 0, 0\n", "positive"),
                          ("A, 1, 0, -1e-3\n", "positive"), ("A:B, 1, 0, 1e-3\n", "no ':'"),
                          ("A, 1, 0, 1e-3\nA, 2, 0, 1e-3\n", "same label"), ("A, x, 0, 1e-3\n", "decimal"),
                          ("# nothing\n", "no enclosures"), ("A" * 17 + ", 1, 0, 1e-3\n", "1 to 16")):
            with self.assertRaisesRegex(io.DataError, why):
                self.read(text)

    def test_checks_refuse(self):
        rows = self.read("A, 3, 4, 1e-6\nB, -2, 0, 1e-1\n").rows
        E.check(rows, params(rows=2, min_digits=1, claims="A:>=4.99; A:<=5.01; B:>=1.8",
                             agrees="A:3,4,1e-5; B:-2.05,0,0.2"))
        with self.assertRaisesRegex(ValueError, "contains 0"):
            E.check(self.read("Z, 1e-3, 0, 2e-3\n").rows, params())
        with self.assertRaisesRegex(ValueError, "not every value"):
            E.check(rows, params(claims="A:>=5"))                # 5 − 1e-6 < 5
        with self.assertRaisesRegex(ValueError, "not every value"):
            E.check(rows, params(claims="A:<=5"))
        with self.assertRaisesRegex(ValueError, "not within"):
            E.check(rows, params(agrees="A:3,4,5e-7"))           # the radius alone is more than the tolerance
        with self.assertRaisesRegex(ValueError, "at least 2"):
            E.check(rows, params(min_digits=2))                  # B misses 0 by 1 digit (|c| = 2, r = 0.1)
        with self.assertRaisesRegex(ValueError, "states 3"):
            E.check(rows, params(rows=3))
        with self.assertRaisesRegex(ValueError, "no enclosure is labelled"):
            E.check(rows, params(claims="C:>=1"))
        with self.assertRaisesRegex(ValueError, "label:"):
            E.check(rows, params(agrees="A:3,4"))
        with self.assertRaisesRegex(ValueError, ">=v or <=v"):
            E.check(rows, params(claims="A:=5"))

    def test_render_alt_and_size(self):
        with open(os.path.join(RECIPES, "hodge-residues.json"), encoding="utf-8") as fh:
            r = json.load(fh)
        out = render(r, GALLERY)
        self.assertEqual(out.data, render(r, GALLERY).data)
        self.assertIn("6 certified enclosures", out.alt)
        self.assertIn("from 9 for D44 I02 to 69", out.alt)
        with self.assertRaisesRegex(ValueError, "needs"):
            render(dict(r, size=[120, 144]), GALLERY)
        with self.assertRaisesRegex(ValueError, "legend needs"):
            render(dict(r, size=[300, 144]), GALLERY)


if __name__ == "__main__":
    unittest.main()
