"""data.catalog: the pattern catalogue reader and the checks a mosaic must pass before it is drawn, against independent
facts — the classical still lifes and oscillators of Conway's Life, the counts of OEIS A019473, and a published catalogue
(every strict still life of 14 cells under Move, OEIS A175001(14) = 49)."""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig.data import io  # noqa: E402
from exactfig.forge import catalog as K  # noqa: E402
from exactfig.forge.motion import parse_rule  # noqa: E402
from exactfig.render import render  # noqa: E402

GALLERY = os.path.join(os.path.abspath(ROOT), "gallery")
LIFE = parse_rule("B3/S23")
BLOCK = "2x2: OO OO"
TUB = "3x3: .O. O.O .O."
BOAT = "3x3: OO. O.O .O."
BEEHIVE = "4x3: .OO. O..O .OO."
GLIDER = "3x3: .O. ..O OOO"
BLINKER = "3x1: OOO"
BI_BLOCK = "5x2: OO.OO OO.OO"


def params(**kw):
    p = {"rule": "B3/S23", "check": "still", "period": 2, "strict": False, "population": 0, "count": 0,
         "distinct": True}
    p.update(kw)
    return p


class Tmp(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="exactfig-catalog-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def cat(self, *lines):
        path = os.path.join(self.dir, "c.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return io.load(path, "patterns", "catalog").patterns


class Reader(Tmp):
    def test_rows_comments_and_both_alive_marks(self):
        pats = self.cat("# a comment", "! another", "", BLOCK, "3x3: .*. *.* .*.")
        self.assertEqual(pats[0], ((0, 0), (0, 1), (1, 0), (1, 1)))
        self.assertEqual(sorted(pats[1]), [(0, 1), (1, 0), (1, 2), (2, 1)])

    def test_a_pattern_is_moved_to_start_at_the_origin(self):
        self.assertEqual(self.cat("... .OO .OO")[0], ((0, 0), (0, 1), (1, 0), (1, 1)))

    def test_bad_input_is_refused_naming_the_line(self):
        for bad in ("3x3: OO OO", "2x2: OX OO", "2by2: OO OO", "... ...", "2x2:"):
            with self.assertRaises(io.DataError, msg=bad) as cm:
                self.cat("# header", bad)
            self.assertIn("line 2", str(cm.exception))
        with self.assertRaises(io.DataError):
            self.cat("# only a comment")

    def test_the_schema_knows_the_format(self):
        self.assertIn("catalog", io.FORMATS["patterns"])


class Dynamics(unittest.TestCase):
    def cells(self, line):
        rows = line.split(":", 1)[1].split()
        return [(x, y) for y, r in enumerate(rows) for x, ch in enumerate(r) if ch == "O"]

    def test_classical_still_lifes_and_oscillators(self):
        for s in (BLOCK, TUB, BOAT, BEEHIVE):
            self.assertEqual(K.returns_after(self.cells(s), LIFE, 1), [True], s)
        self.assertEqual(K.returns_after(self.cells(BLINKER), LIFE, 2), [False, True])
        self.assertEqual(K.returns_after(self.cells(GLIDER), LIFE, 4), [False] * 4)      # a glider moves
        toad = [(1, 0), (2, 0), (3, 0), (0, 1), (1, 1), (2, 1)]
        self.assertEqual(K.returns_after(toad, LIFE, 2), [False, True])

    def test_s0_keeps_an_isolated_cell(self):
        self.assertEqual(K.returns_after([(0, 0)], parse_rule("B3/S0"), 1), [True])
        self.assertEqual(K.returns_after([(0, 0)], LIFE, 1), [False])

    def test_islands_and_pseudo_still_lifes(self):
        self.assertEqual(len(K.islands(self.cells(BI_BLOCK))), 2)
        self.assertTrue(K.is_pseudo(self.cells(BI_BLOCK), LIFE))
        self.assertFalse(K.is_pseudo(self.cells(BEEHIVE), LIFE))
        # two blocks touching at a corner are one island, so never pseudo (they are not even still: the corners die)
        self.assertFalse(K.is_pseudo([(0, 0), (1, 0), (0, 1), (1, 1), (2, 2), (3, 2), (2, 3), (3, 3)], LIFE))
        self.assertFalse(K.returns_after([(0, 0), (1, 0), (0, 1), (1, 1), (2, 2), (3, 2), (2, 3), (3, 3)], LIFE, 1)[0])

    def test_canonical_form_ignores_rotation_and_reflection(self):
        boat = self.cells(BOAT)
        turned = [(2 - y, x) for x, y in boat]
        mirrored = [(2 - x, y) for x, y in boat]
        self.assertEqual(K.canonical(boat), K.canonical(turned))
        self.assertEqual(K.canonical(boat), K.canonical(mirrored))
        self.assertNotEqual(K.canonical(boat), K.canonical(self.cells(TUB)))

    def test_conway_still_lifes_of_up_to_7_cells_match_oeis_a019473(self):
        """Every set of n live cells in a 5x4 box (each still life of up to 7 cells fits in some orientation), up to
        symmetry: A019473 = 0, 0, 0, 2, 1, 5, 4 for n = 1..7, none of them pseudo."""
        from itertools import combinations
        box = [(x, y) for y in range(4) for x in range(5)]
        found = {n: set() for n in range(1, 8)}
        for n in range(1, 8):
            for cells in combinations(box, n):
                if min(x for x, _ in cells) or min(y for _, y in cells):
                    continue                       # each placement once, touching the top and left edges
                if K.returns_after(cells, LIFE, 1)[0]:
                    self.assertFalse(K.is_pseudo(cells, LIFE))
                    found[n].add(K.canonical(cells))
        self.assertEqual([len(found[n]) for n in range(1, 8)], [0, 0, 0, 2, 1, 5, 4])


class Checks(Tmp):
    def test_a_correct_catalogue_passes(self):
        info = K.check(self.cat(BLOCK, TUB), params(population=4, count=2, strict=True))
        self.assertEqual(info["patterns"], 2)

    def test_each_false_statement_is_refused_naming_the_pattern(self):
        cases = [
            ((BLOCK, GLIDER), params(), "pattern 2"),                        # not a still life
            ((BLOCK, TUB), params(count=3), "states 3"),                     # wrong term
            ((BLOCK, BOAT), params(population=4), "pattern 2"),              # wrong population
            ((BLOCK, "2x2: OO OO"), params(), "pattern 2"),                  # the same pattern twice
            ((BI_BLOCK,), params(strict=True), "pseudo"),                    # pseudo still life
            ((BLINKER,), params(check="oscillator", period=3), "returns after 2"),
            ((GLIDER,), params(check="oscillator", period=2), "does not return"),
            ((BLOCK,), params(rule="B03/S23"), "B0"),
        ]
        for lines, p, words in cases:
            with self.assertRaises(ValueError, msg=lines) as cm:
                K.check(self.cat(*lines), p)
            self.assertIn(words, str(cm.exception))

    def test_an_oscillator_of_the_right_period_passes(self):
        K.check(self.cat(BLINKER), params(check="oscillator", period=2))
        with self.assertRaises(ValueError):                                 # a blinker is not a still life
            K.check(self.cat(BLINKER), params())

    def test_without_strict_a_pseudo_still_life_passes(self):
        K.check(self.cat(BI_BLOCK), params())


class PublishedCatalogue(unittest.TestCase):
    """gallery/data/A175001-n14.txt: the 49 strict still lifes of 14 cells under Move (OEIS A175001)."""

    def setUp(self):
        self.pats = io.load(os.path.join(GALLERY, "data", "A175001-n14.txt"), "patterns", "catalog").patterns

    def test_it_is_what_the_oeis_term_says(self):
        K.check(self.pats, params(rule="B368/S245", strict=True, population=14, count=49))

    def test_under_conway_it_is_not(self):
        with self.assertRaises(ValueError):
            K.check(self.pats, params(population=14, count=49))

    def test_the_recipe_renders_and_a_wrong_term_does_not(self):
        with open(os.path.join(ROOT, "examples", "recipes", "still-lifes-a175001.json"), encoding="utf-8") as fh:
            recipe = json.load(fh)
        out = render(recipe, GALLERY)
        self.assertEqual((out.width, out.height), (448, 448))
        recipe["params"]["count"] = 48
        with self.assertRaises(ValueError):
            render(recipe, GALLERY)


if __name__ == "__main__":
    unittest.main()
