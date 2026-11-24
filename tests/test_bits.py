"""data.bits against independent facts:

- the positions of the ones equal those found by repeated division by 2, and rebuild the number;
- the gallery: the combs its recipe states are recomputed here from Adams and Davison's closed form, with the convergents to
  log2 3 found by comparing powers of 2 and 3, and the terms of the b-file equal the closed form;
- the picture: in a figure with room for every bit, the marks of each row are as many as the ones of its term, and the
  rightmost mark of an odd term touches the units column;
- a wrong position, a wrong step, a wrong number of ones, a missing comb, a term that is not positive, a wrong range and a
  figure that is too small are refused."""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig.data import io  # noqa: E402
from exactfig.forge import bits as B  # noqa: E402
from exactfig.pixel import palette  # noqa: E402
from exactfig.render import render  # noqa: E402

GALLERY = os.path.join(os.path.abspath(ROOT), "gallery")
RECIPES = os.path.join(os.path.abspath(ROOT), "examples", "recipes")


def params(**kw):
    p = {"combs": "", "complete": True, "ones": "", "first": -1, "last": -1, "count": 0, "scale": "each", "text_size": 1,
         "ramp": "seq", "zero_ramp": "grey", "label_ramp": "paper", "background": "ink"}
    p.update(kw)
    return p


def by_division(v):
    out, k = [], 0
    while v:
        v, r = divmod(v, 2)
        if r:
            out.append(k)
        k += 1
    return out


def numerators(n):
    """The first n numerators of the convergents to log2 3: p/q < log2 3 exactly when 2^p < 3^q."""
    ps, qs = [1, 2], [1, 1]
    while len(ps) < n:
        below = pow(2, ps[-2]) < pow(3, qs[-2])
        p, q = ps[-2], qs[-2]
        while (pow(2, p + ps[-1]) < pow(3, q + qs[-1])) == below:
            p, q = p + ps[-1], q + qs[-1]
        ps.append(p)
        qs.append(q)
    return ps[:n]


class TestBits(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="exactfig-bits-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def seq(self, text):
        path = os.path.join(self.dir, "b.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        return io.load(path, "sequence", "bfile")

    def test_the_positions_of_the_ones(self):
        for v in list(range(1, 600)) + [pow(2, 400) + 5, pow(3, 250), pow(10, 300) - 1]:
            u = B.ones(v)
            self.assertEqual(u, by_division(v))
            self.assertEqual(sum(1 << k for k in u), v)

    def test_the_gallery_combs_are_adams_and_davison_s(self):
        with open(os.path.join(RECIPES, "oeis-a402278-bits.json"), encoding="utf-8") as f:
            recipe = json.load(f)
        p = numerators(9)
        self.assertEqual(p, [1, 2, 3, 8, 19, 65, 84, 485, 1054])
        want = [(n, p[n - 2], p[n - 1], (p[n] - p[n - 2]) // p[n - 1]) for n in range(2, 9)]
        self.assertEqual(B.parse_combs(recipe["params"]["combs"]), want)
        terms = dict(io.load(os.path.join(GALLERY, "data", "b402278.txt"), "sequence", "bfile").terms)
        self.assertEqual(sorted(terms), list(range(9)))
        for n in range(2, 9):
            num, den = pow(2, p[n]) - pow(2, p[n - 2]), pow(2, p[n - 1]) - 1
            self.assertEqual(num % den, 0)
            self.assertEqual(terms[n], num // den)
            self.assertEqual(by_division(terms[n]), [p[n - 2] + j * p[n - 1] for j in range(want[n - 2][3])])
        self.assertEqual(render(recipe, GALLERY).data, render(recipe, GALLERY).data)
        bad = dict(recipe, params=dict(recipe["params"], combs=recipe["params"]["combs"].replace("5:8,19,3", "5:8,19,2")))
        with self.assertRaises(Exception) as e:
            render(bad, GALLERY)
        self.assertIn("a(5)", str(e.exception))

    def test_the_marks_of_the_picture_are_the_ones(self):
        pal = palette.get("sci")
        terms = [37, 64, 1023, 682]
        s = self.seq("".join(f"{i + 1} {v}\n" for i, v in enumerate(terms)))
        w, rowh = 360, 9
        cv = B.bits("x", pal, w, rowh * len(terms), params(), s)
        ramp = pal.ramp("seq")
        ink = ramp[(len(ramp) * 3) // 4]
        for i, v in enumerate(terms):
            y = i * rowh + 3                                              # a row of the marks above the line of zeros
            row = [cv.get(x, y) == ink for x in range(w)]
            runs = sum(1 for x in range(w) if row[x] and (x == 0 or not row[x - 1]))
            self.assertEqual(runs, bin(v).count("1"), v)

    def test_refusals(self):
        s = self.seq("1 9\n2 2056\n3 1\n")
        good = "1:0,3,2; 2:3,8,2; 3:0,1,1"
        B.check(s, params(combs=good, ones="1:2; 3:1", first=1, last=3, count=3))
        for bad, why in ((dict(combs="1:0,3,2; 2:3,9,2; 3:0,1,1"), "its comb says 12"),
                         (dict(combs="1:1,3,2; 2:3,8,2; 3:0,1,1"), "its comb says 1"),
                         (dict(combs="1:0,3,3; 2:3,8,2; 3:0,1,1"), "its comb states 3"),
                         (dict(combs="1:0,3,10000000000000; 2:3,8,2; 3:0,1,1"), "its comb states"),
                         (dict(combs="1:0,3,2"), "no comb is stated for n = 2, 3"),
                         (dict(combs="9:0,1,1", complete=False), "not drawn"),
                         (dict(combs="1:0,0,2"), "at least 1"),
                         (dict(combs="1:0,3,2; 1:0,3,2"), "two combs"),
                         (dict(combs="1:0,3"), "write n:start,step,count"),
                         (dict(ones="1:3"), "has 2 ones"),
                         (dict(ones="1:2;1:2"), "stated twice"),
                         (dict(ones="one"), "write n:k"),
                         (dict(ones="7:1"), "not drawn"),
                         (dict(first=0), "starts at n = 1"),
                         (dict(last=4), "ends at n = 3"),
                         (dict(first=8, last=9), "no term"),
                         (dict(count=4), "states 4")):
            with self.assertRaises(ValueError) as e:
                B.check(s, params(**bad))
            self.assertIn(why, str(e.exception))
        B.check(s, params(combs="1:0,3,2", complete=False))
        for text in ("1 0\n", "1 5\n2 -3\n"):
            with self.assertRaises(ValueError) as e:
                B.check(self.seq(text), params())
            self.assertIn("is not positive", str(e.exception))
        pal = palette.get("sci")
        for size, why in (((30, 40), "pixels of width"), ((200, 20), "pixels of height")):
            with self.assertRaises(ValueError) as e:
                B.bits("x", pal, size[0], size[1], params(), s)
            self.assertIn(why, str(e.exception))


if __name__ == "__main__":
    unittest.main()
