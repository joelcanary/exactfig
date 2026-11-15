"""data.instances: COCO run-length encoding (checked against pycocotools when it is installed), and the checks an
instance figure must pass, against independent facts — brute-force panoptic quality with exact fractions, the
one-to-one property of IoU > 1/2 between partitions, and why overlaps are refused (a duplicate whose IoU exceeds PQ
raises a naive score)."""
import json
import os
import random
import shutil
import sys
import tempfile
import unittest
from fractions import Fraction

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig.data import io  # noqa: E402
from exactfig.forge import instances as I  # noqa: E402
from exactfig.render import render  # noqa: E402

GALLERY = os.path.join(os.path.abspath(ROOT), "gallery")


def params(**kw):
    p = {"mode": "compare", "show": "truth", "partition": True, "tp": -1, "fp": -1, "fn": -1, "pq": "", "expect": ""}
    p.update(kw)
    return p


def rle_of(cells, w, h):
    """Uncompressed COCO RLE of a set of (x, y), written here independently of exactfig."""
    counts, run, cur = [], 0, 0
    for x in range(w):
        for y in range(h):
            v = int((x, y) in cells)
            if v != cur:
                counts.append(run)
                run, cur = 0, v
            run += 1
    counts.append(run)
    return {"size": [h, w], "counts": counts}


class Tmp(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="exactfig-inst-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def load(self, obj):
        path = os.path.join(self.dir, "i.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        return io.load(path, "instances", "instances")


class Rle(Tmp):
    def test_runs_go_down_the_columns_and_start_with_background(self):
        # 3 wide, 2 high; mask = (1, 0) and (1, 1) and (2, 1): column-major order is x0y0 x0y1 x1y0 x1y1 x2y0 x2y1
        d = self.load({"width": 3, "height": 2, "truth": [{"size": [2, 3], "counts": [2, 2, 1, 1]}]})
        self.assertEqual(d.truth[0], sorted([0 * 3 + 1, 1 * 3 + 1, 1 * 3 + 2]))

    def test_compressed_strings_round_trip(self):
        rnd = random.Random(7)
        for _ in range(200):
            counts = [rnd.randrange(0, 3000) for _ in range(rnd.randrange(1, 30))]
            self.assertEqual(io.rle_counts_from_string(io.rle_string_from_counts(counts)), counts)

    def test_agrees_with_pycocotools(self):
        try:
            import numpy as np
            from pycocotools import mask as M
        except ImportError:
            self.skipTest("pycocotools not installed")
        rnd = random.Random(11)
        for _ in range(150):
            h, w = rnd.randint(1, 30), rnd.randint(1, 30)
            a = np.zeros((h, w), dtype=np.uint8, order="F")
            for _ in range(rnd.randint(0, 4)):
                x, y = rnd.randrange(w), rnd.randrange(h)
                a[y:y + rnd.randint(1, 12), x:x + rnd.randint(1, 12)] = 1
            s = M.encode(np.asfortranarray(a))["counts"].decode()
            self.assertEqual(io.rle_string_from_counts(io.rle_counts_from_string(s)), s)
            got = io._mask_pixels({"size": [h, w], "counts": s}, w, h, "t")
            self.assertEqual(got, sorted(int(y) * w + int(x) for y, x in zip(*np.nonzero(a))))

    def test_bad_masks_are_refused_naming_them(self):
        bad = [{"size": [2, 2], "counts": [1, 1]},                      # adds up to 2, the image has 6
               {"size": [3, 2], "counts": [6]},                         # wrong size
               {"size": [2, 3], "counts": "\x7f"},                      # not an RLE character
               {"size": [2, 3], "counts": [-1, 7]},
               {"cells": [[5, 0]]}]                                     # outside
        for m in bad:
            with self.assertRaises(io.DataError, msg=m) as cm:
                self.load({"width": 3, "height": 2, "truth": [{"cells": [[0, 0]]}, m]})
            self.assertIn("truth 2", str(cm.exception))


def random_partition(rnd, w, h, k):
    """k disjoint random blobs on a w×h grid (as sets of row-major indices)."""
    owner = {}
    for lab in range(k):
        x, y = rnd.randrange(w), rnd.randrange(h)
        for _ in range(rnd.randint(3, 40)):
            owner.setdefault(y * w + x, lab)
            x = min(w - 1, max(0, x + rnd.choice((-1, 0, 1))))
            y = min(h - 1, max(0, y + rnd.choice((-1, 0, 1))))
    out = [[] for _ in range(k)]
    for px, lab in owner.items():
        out[lab].append(px)
    return [sorted(m) for m in out if m]


class Scores(unittest.TestCase):
    def test_matching_is_one_to_one_and_pq_matches_brute_force(self):
        rnd = random.Random(2026)
        for _ in range(300):
            t = random_partition(rnd, 12, 10, rnd.randint(1, 6))
            p = random_partition(rnd, 12, 10, rnd.randint(1, 6))
            pairs = I.match(t, p)
            # brute force over every pair, sets and fractions only
            brute = []
            for i, a in enumerate(t):
                for j, b in enumerate(p):
                    inter, union = len(set(a) & set(b)), len(set(a) | set(b))
                    if Fraction(inter, union) > Fraction(1, 2):
                        brute.append((i, j, inter, union))
            self.assertEqual(sorted(brute), pairs)
            self.assertEqual(len({i for i, *_ in brute}), len(brute))   # one-to-one, as the module argues
            s = I.panoptic_quality(pairs, len(t), len(p))
            den = len(brute) + Fraction(len(t) - len(brute) + len(p) - len(brute), 2)
            self.assertEqual(s["pq"], sum((Fraction(n, u) for *_, n, u in brute), Fraction(0)) / den)

    def test_why_overlaps_are_refused(self):
        """With overlaps allowed and every pair counted, a duplicate of a prediction whose IoU exceeds PQ raises
        the score (the inflation a one-to-one, partition-only matching prevents)."""
        truth = [[0, 1, 2, 3], [10, 11, 12, 13]]
        pred = [[0, 1, 2], [20, 21]]                                      # IoU 3/4 with truth 0; a false positive
        honest = I.panoptic_quality(I.match(truth, pred), 2, 2)["pq"]
        dup = pred + [[0, 1, 2]]
        naive_pairs = [(0, j, 3, 4) for j in (0, 2)]                      # counts both copies as matches
        # an accumulating scorer: TP = pairs, FP = predictions in no pair (1), FN = annotations in no pair (1)
        naive = sum(Fraction(n, u) for *_, n, u in naive_pairs) / (2 + Fraction(1 + 1, 2))
        self.assertGreater(Fraction(3, 4), honest)
        self.assertGreater(naive, honest)
        with self.assertRaises(ValueError):
            I.check(io.Instances(5, 5, truth, dup, {}), params())

    def test_decimal_and_fraction_statements(self):
        self.assertEqual(I._stated("3/7"), (Fraction(3, 7), 0))
        self.assertEqual(I._stated("0.43"), (Fraction(43, 100), Fraction(1, 200)))
        for bad in ("abc", "1/0", "-0.5", "0.4.3"):
            with self.assertRaises(ValueError):
                I._stated(bad)


class Checks(Tmp):
    def scene(self):
        return self.load({"width": 6, "height": 4, "meta": {"date": "2019-05-03", "panel": "left"},
                          "truth": [rle_of({(0, 0), (1, 0), (0, 1), (1, 1)}, 6, 4), rle_of({(4, 2), (5, 2), (4, 3)}, 6, 4)],
                          "prediction": [{"cells": [[0, 0], [1, 0], [0, 1]]}, {"cells": [[3, 0]]}]})

    def test_a_true_statement_passes(self):
        s = I.check(self.scene(), params(tp=1, fp=1, fn=1, pq="3/8", expect="date=2019-05-03;panel=left"))
        self.assertEqual(s["pq"], Fraction(3, 8))                       # IoU 3/4 over 1 + (1 + 1)/2
        I.check(self.scene(), params(pq="0.375"))
        I.check(self.scene(), params(pq="0.38"))                        # rounded to its two digits

    def test_each_false_statement_is_refused(self):
        cases = [(params(tp=2), "tp = 1"), (params(fn=0), "fn = 1"), (params(pq="0.36"), "PQ = 3/8"),
                 (params(pq="1/3"), "PQ = 3/8"), (params(expect="date=2020-05-03"), "date=2019-05-03"),
                 (params(expect="panel=top"), "panel=left"), (params(expect="side=left"), "no 'side'"),
                 (params(expect="nonsense"), "key=value")]
        for p, words in cases:
            with self.assertRaises(ValueError, msg=p) as cm:
                I.check(self.scene(), p)
            self.assertIn(words, str(cm.exception))

    def test_empty_and_overlapping_masks(self):
        d = self.load({"width": 3, "height": 2, "truth": [{"cells": [[0, 0]]}, {"size": [2, 3], "counts": [6]}]})
        with self.assertRaises(ValueError) as cm:
            I.check(d, params(mode="instances"))
        self.assertIn("empty", str(cm.exception))
        d = self.load({"width": 3, "height": 2, "truth": [{"cells": [[0, 0], [1, 0]]}, {"cells": [[1, 0]]}]})
        with self.assertRaises(ValueError) as cm:
            I.check(d, params(mode="instances"))
        self.assertIn("truth 1 and 2 share 1", str(cm.exception))
        I.check(d, params(mode="instances", partition=False))           # raw detections may be drawn
        with self.assertRaises(ValueError):
            I.check(self.load({"width": 3, "height": 2, "truth": [{"cells": [[0, 0]]}]}), params())   # no prediction


class Gallery(unittest.TestCase):
    def test_the_demo_scene_is_what_its_recipe_states(self):
        d = io.load(os.path.join(GALLERY, "data", "instances-demo.json"), "instances", "instances")
        s = I.check(d, params(tp=4, fp=2, fn=2, pq="0.4670", expect="panel=single"))
        self.assertEqual(len(s["pairs"]), 4)
        for name in ("instances-compare", "instances-truth"):
            with open(os.path.join(ROOT, "examples", "recipes", name + ".json"), encoding="utf-8") as fh:
                render(json.load(fh), GALLERY)

    def test_make_data_writes_the_same_bytes(self):
        sys.path.insert(0, os.path.join(ROOT, "examples", "data"))
        import make_data
        with open(os.path.join(GALLERY, "data", "instances-demo.json"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), make_data.instances_demo())


if __name__ == "__main__":
    unittest.main()
