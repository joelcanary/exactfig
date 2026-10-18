"""The Lean side (lean/): its outputs agree with exactfig's own code, and its proofs have no holes.

Lean itself is not needed to run these tests: they read what the Lean programs printed (gallery/data/lean-glider.json,
lean/data/lines.json) and compare it with what exactfig computes. The theorems behind those files are checked by
Lean's kernel when the files are compiled (see lean/README.md)."""
import json
import os
import re
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig.forge import motion  # noqa: E402
from exactfig.pixel import pxmath  # noqa: E402

LEAN = os.path.join(ROOT, "lean")


def jload(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class Agreement(unittest.TestCase):
    def test_bresenham_matches_lean_on_every_line_in_the_box(self):
        lines = jload(os.path.join(LEAN, "data", "lines.json"))["lines"]
        self.assertEqual(len(lines), 7 ** 4)                         # every pair of endpoints in −3..3
        for (x0, y0, x1, y1), pts in lines:
            self.assertEqual(pxmath.line(x0, y0, x1, y1), [tuple(p) for p in pts], (x0, y0, x1, y1))

    def test_life_matches_lean_frame_by_frame(self):
        data = jload(os.path.join(ROOT, "gallery", "data", "lean-glider.json"))
        frames = data["frames"]
        self.assertEqual(len(frames), 33)
        h, w = len(frames[0]), len(frames[0][0])
        cells = bytearray(v for row in frames[0] for v in row)
        birth, survive = motion.parse_rule(data["rule"])
        for k, want in enumerate(frames):
            self.assertEqual(list(cells), [v for row in want for v in row], f"generation {k}")
            cells = motion.life_step(cells, w, h, birth, survive, True)
        self.assertEqual(frames[32], frames[0])                     # the theorem glider_returns, seen in the data


class Proofs(unittest.TestCase):
    def test_no_lean_file_leaves_a_hole(self):
        for f in os.listdir(LEAN):
            if f.endswith(".lean"):
                with open(os.path.join(LEAN, f), encoding="utf-8") as fh:
                    src = re.sub(r"/-.*?-/|--[^\n]*", "", fh.read(), flags=re.S)   # comments out
                for hole in ("sorry", "admit", "axiom", "native_decide", "implemented_by"):
                    self.assertNotIn(hole, src, f"{f}: {hole}")

    def test_the_files_name_the_theorems_their_data_cites(self):
        with open(os.path.join(LEAN, "Life.lean"), encoding="utf-8") as fh:
            life = fh.read()
        for name in jload(os.path.join(ROOT, "gallery", "data", "lean-glider.json"))["theorems"].split():
            self.assertIn(f"theorem {name}", life)
        with open(os.path.join(LEAN, "Line.lean"), encoding="utf-8") as fh:
            self.assertIn("theorem " + jload(os.path.join(LEAN, "data", "lines.json"))["theorem"], fh.read())


if __name__ == "__main__":
    unittest.main()
