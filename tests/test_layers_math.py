"""Layers (compose, annotate, edit, history) and the classical-mathematics generators, against what they must satisfy."""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig import fmath as fm, provenance  # noqa: E402
from exactfig.forge import mathviz as MV  # noqa: E402
from exactfig.pixel import palette, png  # noqa: E402
from exactfig.render import identity, normalize, render  # noqa: E402

GALLERY = os.path.join(os.path.abspath(ROOT), "gallery")
SCI = palette.builtin("sci")


def pixels(out):
    w, h, rgba = png.decode(out.data)
    return w, h, [rgba[i:i + 4] for i in range(0, len(rgba), 4)]


def solid(colour_ramp, w=8, h=8):
    return {"generator": "draw.annotate", "params": {"shapes": [
        {"type": "rect", "points": [[0, 0], [w - 1, h - 1]], "fill": True, "ramp": colour_ramp}]}}


def dot(x, y, colour_ramp):
    return {"generator": "draw.annotate", "params": {"shapes": [{"type": "rect", "points": [[x, y], [x, y]], "ramp": colour_ramp}]}}


class Compose(unittest.TestCase):
    def fig(self, layers):
        return render({"generator": "compose", "seed": "c", "palette": "sci", "size": [8, 8], "layers": layers})

    def colour(self, ramp):
        return bytes(SCI.rgb[SCI.ramp(ramp)[0]]) + b"\xff"

    def test_over_under_and_mask(self):
        _, _, px = pixels(self.fig([solid("paper"), dot(3, 3, "mark")]))
        self.assertEqual(px[3 * 8 + 3], self.colour("mark"))                       # over: the dot covers
        self.assertEqual(px[0], self.colour("paper"))
        _, _, px = pixels(self.fig([solid("paper"), dict(dot(3, 3, "mark"), blend="under")]))
        self.assertEqual(px[3 * 8 + 3], self.colour("paper"))                      # under: only fills holes
        _, _, px = pixels(self.fig([dot(3, 3, "mark"), dict(solid("paper"), blend="under")]))
        self.assertEqual((px[3 * 8 + 3], px[0]), (self.colour("mark"), self.colour("paper")))
        _, _, px = pixels(self.fig([solid("paper"), dict(dot(3, 3, "mark"), blend="mask")]))
        self.assertEqual(px[3 * 8 + 3], self.colour("paper"))                      # mask: what is below survives…
        self.assertEqual(px[0][3], 0)                                               # …only under the layer

    def test_a_layer_cannot_bring_its_own_palette_or_be_an_animation(self):
        for bad in ([dict(solid("ink"), palette="mf32")], [{"generator": "anim.life"}], [{"generator": "compose"}], []):
            with self.assertRaises(ValueError, msg=json.dumps(bad)):
                normalize({"generator": "compose", "seed": "c", "palette": "sci", "size": [8, 8], "layers": bad})

    def test_identity_covers_every_layer(self):
        r = normalize({"generator": "compose", "seed": "c", "palette": "sci", "size": [8, 8],
                       "layers": [solid("ink"), {"generator": "math.ulam"}]})
        ident = identity(r)
        self.assertEqual(ident["version"], "1+draw.annotate@1+math.ulam@1")
        alone = normalize({"generator": "compose", "seed": "c", "palette": "sci", "size": [8, 8], "layers": [solid("ink")]})
        self.assertNotEqual(identity(alone)["code_sha256"], ident["code_sha256"])

    def test_data_layers_pin_their_inputs(self):
        r = normalize({"generator": "compose", "seed": "c", "palette": "sci", "size": [16, 16],
                       "layers": [{"generator": "data.field", "input": {"path": "data/plate-129.npy"}}]}, GALLERY)
        self.assertRegex(r["layers"][0]["input"]["sha256"], "^[0-9a-f]{64}$")
        out = render(r, GALLERY)
        self.assertEqual(out.inputs[0]["path"], "data/plate-129.npy")


class Annotate(unittest.TestCase):
    def test_shapes_are_checked(self):
        bad = [[{"type": "teapot", "points": [[0, 0]]}], [{"type": "line", "points": [[0, 0]]}],
               [{"type": "text", "points": [[0, 0]], "text": "é"}], [{"type": "line", "points": [[0, 0], [1e9, 0]]}],
               [{"type": "circle", "points": [[0, 0]], "r": -1}], [{"type": "rect", "points": [[0, 0], [1, 1]], "extra": 1}],
               [{"type": "marker", "points": [[0, 0]]}] * 65]
        for shapes in bad:
            with self.assertRaises(ValueError):
                normalize({"generator": "draw.annotate", "seed": "a", "palette": "sci", "params": {"shapes": shapes}})

    def test_text_uses_the_font_and_unit_coordinates_reach_the_corners(self):
        out = render({"generator": "draw.annotate", "seed": "a", "palette": "sci", "size": [16, 8],
                      "params": {"shapes": [{"type": "text", "points": [[0, 0]], "text": "1"},
                                            {"type": "marker", "points": [[1, 1]], "r": 1, "units": "unit"}]}})
        w, h, px = pixels(out)
        glyph = [px[y * w + x][3] == 255 for y in range(5) for x in range(3)]
        from exactfig.forge.annotate import FONT
        self.assertEqual(glyph, [c == "#" for c in FONT["1"]])
        self.assertEqual(px[(h - 1) * w + (w - 1)][3], 255)


class EditAndHistory(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="exactfig-edit-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "exactfig", *args], cwd=ROOT, capture_output=True, text=True)

    def test_edit_checks_then_record_keeps_the_history(self):
        rf = os.path.join(self.dir, "r.json")
        with open(rf, "w", encoding="utf-8") as fh:
            json.dump({"generator": "math.modmult", "seed": "m", "palette": "sci", "size": [32, 32], "params": {"n": 40},
                       "output": "m.png"}, fh)
        man = os.path.join(self.dir, "manifest.json")
        provenance.record([rf], man, log=lambda *_: None)
        first = provenance.load(man)["assets"]["m.png"]
        bad = self.cli("edit", rf, "--set", "params.k=-1")
        self.assertNotEqual(bad.returncode, 0)                                     # out of range: nothing written
        ok = self.cli("edit", rf, "--set", "params.k=3", "--set", "params.circle_ramp=ink")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        provenance.record([rf], man, log=lambda *_: None)
        second = provenance.load(man)["assets"]["m.png"]
        self.assertEqual(second["recipe"]["params"]["k"], 3.0)
        self.assertEqual(second["history"][0]["content_sha256"], first["output"]["content_sha256"])
        self.assertTrue(all(c.ok for c in provenance.verify(man, strict=True)[0]))


class ClassicalMathematics(unittest.TestCase):
    def test_logistic_fixed_point_and_two_cycle(self):
        self.assertTrue(all(abs(x - 0.6) < 1e-12 for x in MV.logistic_orbit(2.5, 0.3, 2000, 20)))
        r = 3.2
        d = fm.sqrt((r - 3) * (r + 1))
        lo, hi = (r + 1 - d) / (2 * r), (r + 1 + d) / (2 * r)
        orbit = MV.logistic_orbit(r, 0.3, 3000, 20)
        self.assertTrue(all(min(abs(x - lo), abs(x - hi)) < 1e-12 for x in orbit))
        self.assertTrue(any(abs(x - lo) < 1e-12 for x in orbit) and any(abs(x - hi) < 1e-12 for x in orbit))

    def test_ulam_spiral_places_every_integer_once_and_counts_primes(self):
        pos = MV.ulam_positions(10000)
        self.assertEqual(len(set(pos)), 10000)
        self.assertEqual(pos[:9], [(0, 0), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)])
        self.assertEqual(sum(MV.primes_upto(10000)), 1229)                         # π(10⁴)
        out = render({"generator": "math.ulam", "seed": "u", "palette": "sci", "size": [100, 100],
                      "params": {"background": ""}})
        _, _, px = pixels(out)
        self.assertEqual(sum(p[3] == 255 for p in px), 1229)

    def test_phase_of_the_identity_is_the_angle(self):
        out = render({"generator": "math.domain", "seed": "d", "palette": "sci", "size": [40, 40],
                      "params": {"function": "z", "span": 4.0, "modulus_lines": False}})
        _, _, px = pixels(out)
        cyc = SCI.ramp("cyc")
        for j in range(0, 40, 7):
            for i in range(0, 40, 7):
                x, y = -2 + (i + 0.5) * 0.1, 2 - (j + 0.5) * 0.1
                k = int(math.floor((math.atan2(y, x) / (2 * math.pi) % 1.0) * 12))
                want = bytes(SCI.rgb[cyc[k]]) + b"\xff"
                if abs((math.atan2(y, x) / (2 * math.pi) % 1.0) * 12 - round((math.atan2(y, x) / (2 * math.pi) % 1.0) * 12)) > 1e-9:
                    self.assertEqual(px[j * 40 + i], want, (i, j))

    def test_times_table_chords(self):
        chords = MV.modmult_chords(10, 2.0)
        self.assertEqual(len(chords), 10)
        self.assertEqual(chords[3], (0.3, 0.6))
        self.assertEqual(chords[7], (0.7, 0.4))                                    # 14 mod 10 = 4


if __name__ == "__main__":
    unittest.main()
