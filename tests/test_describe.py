"""Alternative text (forge/describe.py), against independent facts:

- every gallery recipe gets a text of at most 1000 characters, the same on a second render;
- the checked figures state numbers that are known independently of exactfig: 2^127 − 1 and its 19 certificate lines;
  1 on 10 of the 32 inputs for MOD_3 residue 1 on 5 inputs (the inputs with one or four ones: C(5,1) + C(5,4));
  677 and 311 clauses (the proofs in the gallery, counted here from the files); TP 4, FP 2, FN 2 and the exact PQ
  21153891139/45297262530 of the README; 49 still lifes of 14 cells (A175001(14));
- a text is written only after the data passed their checks: a recipe that fails its check gets no text, only the
  refusal;
- record writes the text into the manifest, `exactfig alt` lists it, the RO-Crate carries it, and verify notices a text
  that no longer matches."""
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
from exactfig.forge import describe  # noqa: E402
from exactfig.render import render  # noqa: E402

GALLERY = os.path.join(os.path.abspath(ROOT), "gallery")
RECIPES = os.path.join(os.path.abspath(ROOT), "examples", "recipes")


def recipe(name):
    with open(os.path.join(RECIPES, name + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


def added_clauses(path):
    n = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            t = line.split()
            if not t or t[0] == "c" or (len(t) > 1 and t[1] == "d"):
                continue
            n += 1
            if t[1] == "0":                                          # the empty clause: `id 0 hints 0`
                return n
    return n


class TestDescribe(unittest.TestCase):
    def test_known_numbers(self):
        alt = {n: render(recipe(n), GALLERY).alt for n in ("pratt-m127", "mod3-circuit", "mod3-n3-refutation",
                                                           "schur-3-refutation", "instances-compare",
                                                           "still-lifes-a175001")}
        self.assertIn(str((1 << 127) - 1), alt["pratt-m127"])
        self.assertIn("19 lines", alt["pratt-m127"])
        self.assertIn("1 on 10 of the 32", alt["mod3-circuit"])
        self.assertIn("9 two-input gates on 5 inputs", alt["mod3-circuit"])
        for name, data in (("mod3-n3-refutation", "circuit-mod3-1-n3-s3.lrat"), ("schur-3-refutation", "schur-3-n14.lrat")):
            self.assertIn(f"{added_clauses(os.path.join(GALLERY, 'data', data))} added clauses", alt[name])
        self.assertIn("at least 4 gates", alt["mod3-n3-refutation"])
        self.assertIn("4 true positives, 2 false positives, 2 false negatives", alt["instances-compare"])
        self.assertIn("21153891139/45297262530", alt["instances-compare"])
        self.assertIn("49 patterns of 14 cells under the Life-like rule B368/S245", alt["still-lifes-a175001"])

    def test_every_recorded_file_has_a_bounded_text(self):
        """The gallery manifest (recorded with this version) has a text for every file; verify --strict, which the
        provenance tests run, re-renders each one and compares, so determinism is checked there."""
        assets = provenance.load(os.path.join(GALLERY, "manifest.json"))["assets"]
        for rel, e in assets.items():
            self.assertTrue(e.get("alt"), rel)
            self.assertLessEqual(len(e["alt"]), describe.MAX_ALT, rel)
        r = recipe("vdw-2-3-3-3")
        self.assertEqual(render(r, GALLERY).alt, render(r, GALLERY).alt)

    def test_no_text_for_a_refused_figure(self):
        r = recipe("mod3-circuit")
        r["params"]["function"] = "mod 3 2"
        with self.assertRaises(ValueError):
            render(r, GALLERY)

    def test_function_words(self):
        self.assertEqual(describe.function_words("mod 3 1", 3),
                         "outputs 1 exactly when x1 + x2 + x3 leaves remainder 1 on division by 3")
        self.assertEqual(describe.function_words("threshold 3", 5), "outputs 1 exactly when at least 3 of its 5 inputs are 1")
        self.assertIn("x1 + … + x6", describe.function_words("mod 3 0", 6))

    def test_manifest_cli_crate_and_verify(self):
        d = tempfile.mkdtemp(prefix="exactfig-alt-")
        try:
            os.makedirs(os.path.join(d, "data"))
            shutil.copy(os.path.join(GALLERY, "data", "mod3-1-n3.circuit"), os.path.join(d, "data"))
            path = os.path.join(d, "c.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(recipe("mod3-n3-circuit"), fh)
            man = os.path.join(d, "manifest.json")
            provenance.record([path], man, log=lambda *a, **k: None)
            e = provenance.load(man)["assets"]["mod3-n3-circuit.png"]
            self.assertIn("4 two-input gates on 3 inputs", e["alt"])
            out = subprocess.run([sys.executable, "-m", "exactfig", "alt", "--manifest", man, "--json"], cwd=ROOT,
                                 capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(json.loads(out.stdout), {"mod3-n3-circuit.png": e["alt"]})
            from exactfig.provenance import crate
            c = crate.build(man, date="2026-11-22")
            self.assertEqual({x["@id"]: x for x in c["@graph"]}["mod3-n3-circuit.png"]["description"], e["alt"])
            checks, _ = provenance.verify(man, strict=True)
            self.assertTrue(all(ch.ok for ch in checks))
            m = provenance.load(man)
            m["assets"]["mod3-n3-circuit.png"]["alt"] = "a nice picture"
            provenance.save(man, m)
            checks, _ = provenance.verify(man, strict=False)
            self.assertTrue(any("alternative text" in w for ch in checks for w in ch.warnings))
            checks, _ = provenance.verify(man, strict=True)
            self.assertFalse(all(ch.ok for ch in checks))
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
