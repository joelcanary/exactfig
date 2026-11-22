"""The colour-blindness audit (pixel/cvd.py, `exactfig cvd`) against facts that do not depend on exactfig:

- every row of the three Machado et al. (2009) matrices sums to 1, so white, black and every grey look the same to all
  four visions (a dichromat still tells light from dark);
- red and green, far apart for normal vision, come much closer for protanopes and deuteranopes than for tritanopes
  (red–green blindness), and blue and yellow stay far apart for protanopes and deuteranopes;
- the closest pair of a set is found, and a pair below the threshold is reported, above it is not;
- `exactfig cvd --json` on a recorded figure reports its colours for the four visions and exits 0."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig import provenance  # noqa: E402
from exactfig.pixel import cvd  # noqa: E402

GALLERY = os.path.join(os.path.abspath(ROOT), "gallery")
RED, GREEN, BLUE, YELLOW = (255, 0, 0), (0, 160, 0), (0, 0, 255), (255, 255, 0)


class TestCvd(unittest.TestCase):
    def test_rows_sum_to_one_and_greys_are_kept(self):
        for m in cvd.MACHADO.values():
            for row in m:
                self.assertAlmostEqual(sum(row), 1.0, places=5)
        for g in (0, 64, 128, 200, 255):
            for v in cvd.VISIONS:
                sim = cvd.simulate((g, g, g), v)
                self.assertTrue(all(abs(x - g) < 0.6 for x in sim), (g, v, sim))

    def test_red_green_and_blue_yellow(self):
        normal = cvd.distance(RED, GREEN, "normal")
        for v in ("protan", "deutan"):
            self.assertLess(cvd.distance(RED, GREEN, v), 0.6 * normal, v)
            self.assertLess(cvd.distance(RED, GREEN, v), cvd.distance(RED, GREEN, "tritan"), v)
            self.assertGreater(cvd.distance(BLUE, YELLOW, v), 0.5, v)

    def test_closest_and_threshold(self):
        cols = [(0, 0, 0), (255, 255, 255), (250, 250, 250)]
        d, i, j = cvd.closest(cols)["normal"]
        self.assertEqual((i, j), (1, 2))
        a = cvd.audit(cols, minimum=0.05)["normal"]
        self.assertEqual([(p[1], p[2]) for p in a["below"]], [(1, 2)])
        self.assertEqual(cvd.audit([(0, 0, 0), (255, 255, 255)], minimum=0.05)["deutan"]["below"], [])

    def test_gallery_figures_that_carry_meaning_in_colour(self):
        """0.12.0 regression guard: the figures whose colours carry different meanings (the colouring, the instances,
        the circuits) keep every pair of their colours at least 0.06 apart for all four visions."""
        from exactfig.render import render
        from exactfig.pixel import png
        for name in ("vdw-2-3-3-3", "instances-truth", "mod3-circuit", "mod3-n3-circuit"):
            with open(os.path.join(ROOT, "examples", "recipes", name + ".json"), encoding="utf-8") as fh:
                out = render(json.load(fh), GALLERY)
            w, h, rgba = png.decode(out.data)
            counts = {}
            for i in range(0, len(rgba), 4):
                if rgba[i + 3]:
                    counts[tuple(rgba[i:i + 3])] = counts.get(tuple(rgba[i:i + 3]), 0) + 1
            total = sum(counts.values())
            cols = sorted(c for c, n in counts.items() if n >= 0.005 * total)
            for v, r in cvd.audit(cols, cvd.DEFAULT_MIN).items():
                self.assertEqual(r["below"], [], (name, v))

    def test_cat_ramp_is_safe(self):
        from exactfig.pixel import palette
        sci = palette.builtin("sci")
        cat = [sci.rgb[i] for i in sci.ramps["cat"]]
        self.assertEqual(len(cat), 7)
        for v, r in cvd.audit(cat, 0.07).items():
            self.assertEqual(r["below"], [], v)

    def test_cli_json(self):
        d = tempfile.mkdtemp(prefix="exactfig-cvd-")
        try:
            os.makedirs(os.path.join(d, "data"))
            shutil.copy(os.path.join(GALLERY, "data", "schur-3.txt"), os.path.join(d, "data"))
            with open(os.path.join(ROOT, "examples", "recipes", "schur-3.json"), encoding="utf-8") as fh:
                r = json.load(fh)
            path = os.path.join(d, "r.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(r, fh)
            man = os.path.join(d, "manifest.json")
            provenance.record([path], man, log=lambda *a, **k: None)
            out = subprocess.run([sys.executable, "-m", "exactfig", "cvd", "--manifest", man, "--json"], cwd=ROOT,
                                 capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(out.returncode, 0, out.stderr)
            rep = json.loads(out.stdout)[r["output"]]
            self.assertEqual(set(rep), set(cvd.VISIONS) | {"colours"})
            self.assertGreaterEqual(rep["colours"], 3)
            bad = subprocess.run([sys.executable, "-m", "exactfig", "cvd", "--manifest", man, "--min", "2"], cwd=ROOT,
                                 capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(bad.returncode, 2)
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
