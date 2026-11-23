"""`verify` and the command line, exercised in process where the misuse bench only sees refusals:

- the palette lock: a recorded PNG with one pixel changed to a colour outside the palette, or made semi-transparent, is
  refused for that reason (besides the pixel hash);
- an animation replaced by bytes that are not one is refused as unreadable;
- `verify --json` is valid JSON whose "ok" is true for an untouched folder and false for a tampered one;
- the commands that succeed: `list` names every generator, `palettes` the built-in palettes, `alt --json` gives the
  recorded text, `cvd --json` one report per image, `edit` writes a checked recipe, `palette` derives a palette file."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig import cli, provenance, registry  # noqa: E402
from exactfig.pixel import png  # noqa: E402

STILL = {"generator": "math.ulam", "seed": "u", "palette": "sci", "size": [21, 21], "output": "u.png"}
ANIM = {"generator": "anim.life", "seed": "l", "palette": "sci", "size": [16, 12], "params": {"frames": 4},
        "output": "l.gif"}


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli.main(argv)
        except SystemExit as ex:
            code = ex.code
    return code, out.getvalue(), err.getvalue()


class TestVerifyAndCli(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="exactfig-vcli-")
        self.old = os.getcwd()
        os.chdir(self.d)
        for name, r in (("u.json", STILL), ("l.json", ANIM)):
            with open(name, "w", encoding="utf-8") as fh:
                json.dump(r, fh)
        provenance.record(["u.json", "l.json"], "m.json", log=lambda *a, **k: None)

    def tearDown(self):
        os.chdir(self.old)
        shutil.rmtree(self.d, ignore_errors=True)

    def tamper_png(self, rgba_change):
        w, h, rgba = png.decode(open("u.png", "rb").read())
        b = bytearray(rgba)
        b[0:4] = rgba_change
        open("u.png", "wb").write(png.encode_rgba(w, h, bytes(b)))

    def problems(self, path):
        checks, _ = provenance.verify("m.json", strict=False)
        return next(c for c in checks if c.path == path).problems

    def test_palette_lock_foreign_colour(self):
        self.tamper_png(bytes((0x12, 0x34, 0x56, 255)))
        probs = " ".join(self.problems("u.png"))
        self.assertIn("palette lock broken: 1 colour(s) not in the palette, e.g. #123456", probs)

    def test_palette_lock_semi_transparent(self):
        w, h, rgba = png.decode(open("u.png", "rb").read())
        self.tamper_png(bytes(rgba[0:3]) + bytes((128,)))
        self.assertIn("palette lock broken: semi-transparent pixels", " ".join(self.problems("u.png")))

    def test_unreadable_animation(self):
        open("l.gif", "wb").write(b"GIF89a" + b"\x00" * 7 + b"garbage")
        self.assertTrue(any("cannot read the animation" in p for p in self.problems("l.gif")))

    def test_verify_json(self):
        code, out, _ = run(["verify", "--manifest", "m.json", "--json"])
        rep = json.loads(out)
        self.assertEqual((code, rep["ok"], len(rep["assets"])), (0, True, 2))
        self.tamper_png(bytes((0x12, 0x34, 0x56, 255)))
        code, out, _ = run(["verify", "--manifest", "m.json", "--json"])
        rep = json.loads(out)
        self.assertEqual((code, rep["ok"]), (1, False))

    def test_commands_that_succeed(self):
        code, out, _ = run(["list"])
        self.assertEqual(code, 0)
        for name in registry.all_generators():
            self.assertIn(name, out)
        code, out, _ = run(["palettes"])
        self.assertEqual(code, 0)
        self.assertIn("sci", out)
        code, out, _ = run(["alt", "--manifest", "m.json", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(set(json.loads(out)), {"u.png", "l.gif"})
        code, out, _ = run(["cvd", "--manifest", "m.json", "--json"])
        self.assertEqual(code, 0)
        self.assertIn("u.png", json.dumps(json.loads(out)))
        code, _, _ = run(["edit", "u.json", "--set", "size=[25,25]", "--out", "u2.json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.load(open("u2.json", encoding="utf-8"))["size"], [25, 25])
        code, _, _ = run(["palette", "u.png", "--k", "4", "--out", "p.json"])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.getsize("p.json") > 0)


if __name__ == "__main__":
    unittest.main()
