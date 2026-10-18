"""
Provenance tests / pruebas de procedencia: determinism, palette lock, and verify catching one changed pixel or one changed byte.
"""
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig import provenance, registry  # noqa: E402
from exactfig.pixel import png  # noqa: E402
from exactfig.render import normalize, render  # noqa: E402

GEM = {"generator": "forge.icon.gem", "seed": "t", "size": [16, 16], "params": {"shape": "hex"}, "output": "gem.png"}
SONG = {"generator": "music.piece", "seed": "t", "params": {"title": "Test", "source": "fifths", "bars": 8}, "output": "song.mid"}
SMALL = {
    "forge.tile.stone": {"size": [24, 24], "params": {"cells": 3}},
    "forge.tile.terrain": {"size": [24, 24]},
    "forge.tile.cave": {"size": [24, 24]},
    "forge.sprite.critters": {"size": [32, 16], "params": {"cell": 16, "cols": 2, "count": 2}},
    "forge.icon.gem": {"size": [16, 16]},
    "forge.flora.tree": {"size": [32, 32], "params": {"iterations": 3}},
    "forge.sky.gradient": {"size": [32, 16]},
    "forge.fractal.julia": {"size": [24, 24]},
    "music.piece": {"params": {"bars": 8}},
    "data.field": {"palette": "sci", "size": [24, 24], "input": {"path": "data/plate-129.npy"}, "params": {"contours": 3}},
    "data.scatter": {"palette": "sci", "size": [24, 24], "input": {"path": "data/franke-halton-256.csv"},
                     "params": {"points": "dot"}},
    "anim.life": {"palette": "sci", "size": [16, 12], "params": {"frames": 4}},
    "anim.wave": {"palette": "sci", "size": [24, 16], "params": {"frames": 3, "every": 2, "sponge": 3}},
    "anim.lorenz": {"palette": "sci", "size": [24, 24], "params": {"frames": 3, "warmup": 10, "trail": 50}},
    "anim.diffuse": {"palette": "sci", "size": [16, 16], "input": {"path": "data/plate-129.npy"}, "params": {"frames": 3}},
    "anim.frames": {"palette": "sci", "size": [16, 16], "input": {"path": "data/lean-glider.json"}},
    "compose": {"palette": "sci", "size": [24, 24], "layers": [
        {"generator": "data.field", "input": {"path": "data/plate-129.npy"}},
        {"generator": "draw.annotate", "params": {"shapes": [{"type": "line", "points": [[0, 0], [23, 23]]}]}}]},
    "draw.annotate": {"palette": "sci", "size": [24, 24], "params": {"shapes": [{"type": "text", "points": [[1, 1]], "text": "A1"}]}},
    "math.domain": {"palette": "sci", "size": [24, 24]},
    "math.logistic": {"palette": "sci", "size": [24, 16], "params": {"warmup": 50, "samples": 40}},
    "math.ulam": {"palette": "sci", "size": [21, 21]},
    "math.modmult": {"palette": "sci", "size": [24, 24], "params": {"n": 30}},
    "data.image": {"palette": "sci", "size": [24, 16], "input": {"path": "data/testcard-480x320.png"}},
    "math.fourier": {"palette": "sci", "size": [40, 24], "params": {"orders": "1,5"}},
    "anim.epicycles": {"palette": "sci", "size": [24, 24], "params": {"samples": 16, "terms": 4, "frames": 3}},
}
DATA = os.path.join(os.path.abspath(ROOT), "gallery")   # input paths of the data recipes are relative to the gallery folder
SEEDLESS = ("forge.icon.gem", "forge.fractal.julia", "data.field", "data.scatter", "anim.wave", "anim.lorenz", "anim.diffuse",
            "anim.frames", "compose", "draw.annotate", "math.domain", "math.logistic", "math.ulam", "math.modmult",
            "data.image", "math.fourier", "anim.epicycles")   # the output does not depend on the seed


def rb(path):
    with open(path, "rb") as fh:
        return fh.read()


def wb(path, data):
    with open(path, "wb") as fh:
        fh.write(data)


def jload(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def jsave(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def recipe_for(name, seed="s"):
    return dict({"generator": name, "seed": seed}, **SMALL[name])


class Determinism(unittest.TestCase):
    def test_every_generator_has_a_small_test_recipe(self):
        self.assertEqual(set(SMALL), set(registry.all_generators()))

    def test_same_recipe_same_output_and_seed_matters(self):
        for name in SMALL:
            a, b = render(recipe_for(name), DATA), render(recipe_for(name), DATA)
            self.assertEqual(a.data, b.data, name)
            self.assertEqual(a.content_sha256, b.content_sha256, name)
            if name not in SEEDLESS:
                self.assertNotEqual(render(recipe_for(name, "other"), DATA).content_sha256, a.content_sha256, name)

    def test_same_output_in_a_fresh_process_with_another_hash_seed(self):
        """Python randomises str hashing per process: an iteration over a set of strings would change the output. Not here."""
        code = ("import sys, json; sys.path.insert(0, %r); from exactfig.render import render; "
                "print(json.dumps([render(r, sys.argv[2]).content_sha256 for r in json.loads(sys.argv[1])]))") % os.path.abspath(ROOT)
        recipes = [recipe_for(n) for n in SMALL]
        here = [render(r, DATA).content_sha256 for r in recipes]
        for hs in ("1", "4242"):
            out = subprocess.run([sys.executable, "-c", code, json.dumps(recipes), DATA], capture_output=True, text=True,
                                 env=dict(os.environ, PYTHONHASHSEED=hs), check=True).stdout
            self.assertEqual(json.loads(out), here, f"PYTHONHASHSEED={hs}")

    def test_terrain_is_seamless_across_tiles(self):
        whole = render({"generator": "forge.tile.terrain", "seed": "w", "size": [64, 32], "params": {"world_x": 0}})
        left = render({"generator": "forge.tile.terrain", "seed": "w", "size": [32, 32], "params": {"world_x": 0}})
        right = render({"generator": "forge.tile.terrain", "seed": "w", "size": [32, 32], "params": {"world_x": 1}})
        _, _, W = png.decode(whole.data)
        _, _, L = png.decode(left.data)
        _, _, R = png.decode(right.data)
        for y in range(32):
            self.assertEqual(W[y * 256:(y + 1) * 256], L[y * 128:(y + 1) * 128] + R[y * 128:(y + 1) * 128], f"row {y}")


class Mismatch(unittest.TestCase):
    def test_a_recorded_hash_that_the_recipe_no_longer_gives_is_reported_not_raised(self):
        """The path where re-running the recipe gives other content than recorded (a generator changed without a version
        bump, or a hand-edited hash) must produce a readable failure, for a plain recipe and for a composition."""
        d = tempfile.mkdtemp(prefix="exactfig-mismatch-")
        try:
            man = os.path.join(d, "manifest.json")
            for name, recipe in (("gem", dict(GEM, output="gem.png")),
                                 ("fig", {"generator": "compose", "seed": "m", "palette": "sci", "size": [8, 8], "output": "fig.png",
                                          "layers": [{"generator": "math.ulam"}]})):
                rf = os.path.join(d, name + ".json")
                jsave(rf, recipe)
                provenance.record([rf], man, log=lambda *_: None)
            m = jload(man)
            for rel in ("gem.png", "fig.png"):
                m["assets"][rel]["output"]["content_sha256"] = "0" * 64
            provenance.save(man, m)
            checks = {c.path: c for c in provenance.verify(man)[0]}
            for rel, name in (("gem.png", "forge.icon.gem"), ("fig.png", "compose")):
                self.assertFalse(checks[rel].ok)
                self.assertIn(f"re-running {name} gives different content", checks[rel].problems[0])
        finally:
            shutil.rmtree(d, ignore_errors=True)


class Schema(unittest.TestCase):
    def test_unknown_or_out_of_range_params_are_rejected(self):
        bad = [
            dict(GEM, params={"pixels": [[1, 2, 3]]}),               # nada de colar un bitmap
            dict(GEM, params={"facets": 999}),
            dict(GEM, params={"shape": "teapot"}),
            dict(GEM, size=[16, 16, 3]),
            dict(GEM, scale=0),
            dict(GEM, extra="hello"),
            dict(SONG, params={"title": "x" * 300}),
            dict(SONG, palette="mf32"),
        ]
        for r in bad:
            with self.assertRaises(ValueError, msg=json.dumps(r)):
                normalize(r)

    def test_normal_form_fills_every_default(self):
        n = normalize(GEM)
        self.assertEqual(set(n["params"]), set(registry.get("forge.icon.gem").params))
        self.assertEqual(normalize(n), n, "idempotent")


class RecordVerify(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="exactfig-test-")
        self.man = os.path.join(self.dir, "manifest.json")
        files = []
        for r in (GEM, SONG):
            f = os.path.join(self.dir, r["output"] + ".json")
            with open(f, "w", encoding="utf-8") as fh:
                json.dump(r, fh)
            files.append(f)
        provenance.record(files, self.man, log=lambda *_: None)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def verify(self, strict=False):
        checks, top = provenance.verify(self.man, strict)
        return {c.path: c for c in checks}, top

    def test_fresh_record_verifies(self):
        checks, top = self.verify(strict=True)
        self.assertEqual(top, [])
        self.assertTrue(all(c.ok for c in checks.values()), {k: c.problems for k, c in checks.items()})

    def test_one_changed_pixel_is_caught(self):
        path = os.path.join(self.dir, "gem.png")
        w, h, rgba = png.decode(rb(path))
        man = jload(self.man)
        pal = [tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in man["assets"]["gem.png"]["palette"]]
        i = (8 * w + 8) * 4                                   # el centro de la gema
        cur = tuple(rgba[i:i + 3])
        other = next(c for c in pal if c != cur)               # otro color DE LA PALETA: solo el hash puede pillarlo
        idx = [pal.index(tuple(rgba[k:k + 3])) if rgba[k + 3] else len(pal) for k in range(0, len(rgba), 4)]
        idx[8 * w + 8] = pal.index(other)
        wb(path, png.encode_indexed(w, h, idx, pal + [(0, 0, 0)], len(pal)))
        checks, _ = self.verify()
        c = checks["gem.png"]
        self.assertFalse(c.ok)
        self.assertTrue(any("1 pixel(s) differ" in p and "x=8, y=8" in p for p in c.problems), c.problems)
        self.assertTrue(checks["song.mid"].ok)

    def test_a_colour_outside_the_palette_is_caught(self):
        path = os.path.join(self.dir, "gem.png")
        w, h, rgba = png.decode(rb(path))
        b = bytearray(rgba)
        i = (8 * w + 8) * 4
        b[i:i + 4] = bytes((b[i] ^ 1, b[i + 1], b[i + 2], 255))   # un solo bit de rojo
        raw = b"".join(b"\0" + bytes(b[y * w * 4:(y + 1) * w * 4]) for y in range(h))
        data = (png.SIG + png._chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                + png._chunk(b"IDAT", zlib.compress(raw)) + png._chunk(b"IEND", b""))
        wb(path, data)
        c = self.verify()[0]["gem.png"]
        self.assertFalse(c.ok)
        self.assertTrue(any("palette lock broken" in p for p in c.problems), c.problems)
        self.assertTrue(any("1 pixel(s) differ" in p for p in c.problems), c.problems)

    def test_one_changed_midi_byte_is_caught(self):
        path = os.path.join(self.dir, "song.mid")
        data = bytearray(rb(path))
        k = len(data) // 2
        data[k] ^= 0x01
        wb(path, bytes(data))
        c = self.verify()[0]["song.mid"]
        self.assertFalse(c.ok)
        self.assertTrue(any(f"first difference at byte {k}" in p for p in c.problems), c.problems)

    def test_an_edited_recipe_or_manifest_is_caught(self):
        man = jload(self.man)
        man["assets"]["gem.png"]["recipe"]["params"]["facets"] = 9
        jsave(self.man, man)
        checks, top = self.verify()
        self.assertFalse(checks["gem.png"].ok)
        self.assertTrue(any("recipe_sha256" in p for p in checks["gem.png"].problems))
        self.assertTrue(top, "the manifest digest no longer matches")

    def test_re_encoded_png_with_same_pixels_passes_but_not_strict(self):
        path = os.path.join(self.dir, "gem.png")
        w, h, rgba = png.decode(rb(path))
        raw = b"".join(b"\0" + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
        wb(path, png.SIG + png._chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + png._chunk(b"IDAT", zlib.compress(raw, 1)) + png._chunk(b"IEND", b""))
        self.assertTrue(self.verify()[0]["gem.png"].ok)
        self.assertFalse(self.verify(strict=True)[0]["gem.png"].ok)


class Gallery(unittest.TestCase):
    def test_the_committed_gallery_verifies(self):
        man = os.path.join(ROOT, "gallery", "manifest.json")
        if not os.path.exists(man):
            self.skipTest("no gallery yet")
        checks, top = provenance.verify(man)
        self.assertEqual(top, [])
        self.assertEqual([c.path for c in checks if not c.ok], [])
        recipes = {jload(os.path.join(ROOT, "examples", "recipes", f))["output"]
                   for f in os.listdir(os.path.join(ROOT, "examples", "recipes"))}
        self.assertEqual({c.path for c in checks}, recipes, "every example recipe is in the gallery and nothing else")

    def test_the_gallery_manifest_follows_its_json_schema(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed (optional)")
        schema = jload(os.path.join(ROOT, "exactfig", "provenance", "manifest.schema.json"))
        jsonschema.validate(jload(os.path.join(ROOT, "gallery", "manifest.json")), schema)


if __name__ == "__main__":
    unittest.main()
