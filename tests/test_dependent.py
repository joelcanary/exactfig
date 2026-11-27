"""data.dependent: the board reader and the checks a set of cells must pass before it is drawn, against independent facts —
the first terms of OEIS A101201 (a(1) = 0, a(2) = 2: on a small torus a neighbour can be the same cell several times),
the periodic set {(x, y): 2x + y mod 5 in {0, 1, 2}} of Ionascu, Pritikin and Wright (every point has exactly 4
neighbours), a set that is 4-dependent on the board but not on the torus, and the symmetries of the torus."""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig.data import io  # noqa: E402
from exactfig.forge import dependent as D  # noqa: E402
from exactfig.forge.describe import text  # noqa: E402
from exactfig import registry  # noqa: E402
from exactfig.render import render  # noqa: E402

GALLERY = os.path.join(os.path.abspath(ROOT), "gallery")


def board(w, h, cells):
    rows = [["."] * w for _ in range(h)]
    for x, y in cells:
        rows[y][x] = "O"
    return f"{w}x{h}: " + " ".join("".join(r) for r in rows)


def params(**kw):
    p = {"k": 4, "topology": "torus", "population": 0, "populations": "", "count": 0, "distinct": True}
    p.update(kw)
    return p


S4_5 = [(x, y) for x in range(5) for y in range(5) if (2 * x + y) % 5 in (0, 1, 2)]     # 15 points on T[5, 5]
EDGES_4 = [(0, y) for y in range(4)] + [(3, y) for y in range(4)]                           # columns 0 and 3 of 4x4


class Tmp(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="exactfig-dependent-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, name, text):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        return path


class TestReader(Tmp):
    def test_keeps_the_board_and_its_empty_rows(self):
        b = io.read_boards(self.write("a.boards", "# comment\n4x3: .... .O.. ....\n2x2: .. ..\n"))
        self.assertEqual(b.boards, [(4, 3, ((1, 1),)), (2, 2, ())])

    def test_refusals(self):
        for bad in ("O.O", "3x1 O.O", "3x1: O.", "2x2: OX O.", "0x1:", "300x1: " + "." * 300, ""):
            with self.subTest(bad=bad), self.assertRaises(io.DataError):
                io.read_boards(self.write("b.boards", bad + "\n"))


class TestChecks(unittest.TestCase):
    def test_small_tori_count_a_neighbour_several_times(self):
        # A101201: a(1) = 0 (one point on the 1x1 torus is its own neighbour 8 times), a(2) = 2
        self.assertEqual(D.worst(1, 1, {(0, 0)}, True)[0], 8)
        D.check([(2, 2, ((0, 0), (1, 1)))], params())
        with self.assertRaises(ValueError):
            D.check([(2, 2, ((0, 0), (1, 0), (0, 1)))], params())
        with self.assertRaises(ValueError):
            D.check([(1, 1, ((0, 0),))], params())

    def test_ipw_set_has_exactly_four_neighbours(self):
        cs = set(S4_5)
        self.assertEqual(len(cs), 15)
        self.assertEqual({D.neighbours(5, 5, cs, x, y, True) for x, y in cs}, {4})
        D.check([(5, 5, tuple(S4_5))], params(population=15))
        with self.assertRaises(ValueError) as e:
            D.check([(5, 5, tuple(S4_5))], params(k=3))
        self.assertIn("4 neighbours", str(e.exception))

    def test_torus_and_plane_differ(self):
        b = [(4, 4, tuple(EDGES_4))]
        D.check(b, params(topology="plane"))
        with self.assertRaises(ValueError):
            D.check(b, params())

    def test_stated_numbers(self):
        b = [(5, 5, tuple(S4_5)), (2, 2, ((0, 0), (1, 1)))]
        D.check(b, params(populations="15,2", count=2))
        for kw in ({"populations": "15,3"}, {"populations": "15"}, {"count": 3}, {"population": 15},
                   {"populations": "15,x"}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                D.check(b, params(**kw))

    def test_distinct_up_to_the_symmetries_of_the_torus(self):
        shifted = tuple(sorted(((x + 1) % 5, (y + 2) % 5) for x, y in S4_5))
        mirrored = tuple(sorted((4 - x, y) for x, y in S4_5))
        for other in (shifted, mirrored):
            with self.assertRaises(ValueError):
                D.check([(5, 5, tuple(S4_5)), (5, 5, other)], params())
            D.check([(5, 5, tuple(S4_5)), (5, 5, other)], params(distinct=False))
        # on the plane a translation is not a symmetry of the board
        a, b = ((0, 0),), ((1, 0),)
        D.check([(3, 1, a), (3, 1, b)], params(topology="plane"))
        with self.assertRaises(ValueError):
            D.check([(3, 1, a), (3, 1, b)], params())


class TestRender(Tmp):
    def recipe(self, path, **kw):
        r = {"generator": "data.dependent", "seed": "x", "palette": "sci", "size": [120, 60],
             "input": {"path": path, "format": "boards"}, "params": {"k": 4, "count": 2}, "output": "o.png"}
        r["params"].update(kw)
        return r

    def test_draws_and_is_deterministic(self):
        self.write("c.boards", board(5, 5, S4_5) + "\n" + board(4, 4, EDGES_4) + "\n")
        r = self.recipe("c.boards", topology="plane")
        a, b = render(r, self.dir), render(json.loads(json.dumps(r)), self.dir)
        self.assertEqual(a.content_sha256, b.content_sha256)
        self.assertEqual(a.data, b.data)

    def test_refuses_before_drawing(self):
        self.write("c.boards", board(5, 5, S4_5) + "\n" + board(4, 4, EDGES_4) + "\n")
        with self.assertRaises(ValueError):
            render(self.recipe("c.boards"), self.dir)       # torus: the second board fails

    def test_alt_text_states_the_checks(self):
        path = self.write("c.boards", board(5, 5, S4_5) + "\n")
        gen = registry.get("data.dependent")
        t = text(gen, gen.resolve({"k": 4, "count": 1, "population": 15}), io.read_boards(path), 120, 60)
        self.assertIn("at most 4 of its 8 neighbours", t)
        self.assertIn("torus", t)
        self.assertIn("1 board of 5 by 5 cells with 15 points", t)

    def test_gallery_recipe(self):
        b = io.read_boards(os.path.join(GALLERY, "data", "kings-a101201.boards"))
        p = params(populations="5,9,15,21,28,37,47,60", count=8)
        self.assertEqual(D.check(b.boards, p)["boards"], 8)


if __name__ == "__main__":
    unittest.main()
