"""Canvas primitives against facts that do not come from the code:

- polygon (scanline fill, sampling pixel centres, the polygon closed: a centre on an edge is inside): a 4 × 4 square
  fills exactly its 16 cells; the right triangle with legs 8 fills exactly the 36 cells whose centre (x + ½, y + ½)
  satisfies x + y ≤ 8 (28 strictly inside, 8 on the hypotenuse), counted here directly; an
  L-shaped (concave) polygon fills its area of 12 cells, by the even-odd rule; fewer than 3 vertices fill nothing;
- ellipse: symmetric about its centre in x and y, it contains its centre and the four ends of its axes and nothing one
  step beyond them, and a degenerate radius gives no points;
- painting with a colour sets exactly the returned points."""
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig.pixel.canvas import Canvas  # noqa: E402
from exactfig.pixel.palette import get as get_palette  # noqa: E402


def canvas(w=16, h=16):
    return Canvas(w, h, get_palette("sci"))


class TestCanvas(unittest.TestCase):
    def test_polygon_square_triangle_and_concave(self):
        cv = canvas()
        self.assertEqual(cv.polygon([(0, 0), (4, 0), (4, 4), (0, 4)]), {(x, y) for x in range(4) for y in range(4)})
        tri = cv.polygon([(0, 0), (8, 0), (0, 8)])
        want = {(x, y) for x in range(8) for y in range(8) if (x + 0.5) + (y + 0.5) <= 8}
        self.assertEqual(len(want), 36)
        self.assertEqual(tri, want)
        ell = cv.polygon([(0, 0), (4, 0), (4, 2), (2, 2), (2, 4), (0, 4)])     # an L: 4·2 + 2·2 = 12 cells
        self.assertEqual(len(ell), 12)
        self.assertNotIn((3, 3), ell)
        self.assertEqual(cv.polygon([(0, 0), (4, 4)]), set())

    def test_ellipse(self):
        cv = canvas(32, 32)
        cx, cy, rx, ry = 15, 12, 7, 4
        pts = cv.ellipse(cx, cy, rx, ry)
        self.assertEqual(pts, {(2 * cx - x, y) for x, y in pts})
        self.assertEqual(pts, {(x, 2 * cy - y) for x, y in pts})
        for p in ((cx, cy), (cx + rx, cy), (cx - rx, cy), (cx, cy + ry), (cx, cy - ry)):
            self.assertIn(p, pts)
        for p in ((cx + rx + 1, cy), (cx, cy + ry + 1)):
            self.assertNotIn(p, pts)
        self.assertEqual(cv.ellipse(5, 5, 0, 3), set())

    def test_painting_sets_exactly_the_points(self):
        cv = canvas()
        pts = cv.polygon([(1, 1), (6, 1), (6, 5)], c=3)
        self.assertEqual({(x, y) for x, y, c in cv.cells() if c is not None}, pts)
        self.assertTrue(all(cv.get(x, y) == 3 for x, y in pts))


if __name__ == "__main__":
    unittest.main()
