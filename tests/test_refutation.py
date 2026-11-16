"""data.refutation against independent facts:

- the formula exactfig writes means what it says: for every colouring of 1..n (small n), its one-hot assignment
  satisfies the formula exactly when data.coloring's own check accepts the colouring (van der Waerden, Schur, weak Schur);
- real proofs from a SAT solver (CaDiCaL, --lrat), also accepted by the verified checker cake_lpr, are accepted:
  W(2;3) = 9, W(2;4) = 35 and, in the gallery, S(3) = 13 (no 3-colouring of 1..14);
- the same proofs are refused for any other claim, and every way of spoiling one is refused for its own reason."""
import itertools
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig.data import io  # noqa: E402
from exactfig.forge import coloring as C, refutation as R  # noqa: E402
from exactfig.render import render  # noqa: E402

GALLERY = os.path.join(os.path.abspath(ROOT), "gallery")
DATA = os.path.join(os.path.abspath(ROOT), "tests", "data")


def steps(path):
    return io.load(path, "proof", "lrat").steps


def ref_params(**kw):
    p = {"check": "ap", "lengths": "3", "distinct": False, "colors": 2, "length": 9, "steps": 0, "ramp": "cyc",
         "mark_ramp": "paper", "background": "ink"}
    p.update(kw)
    return p


class Formula(unittest.TestCase):
    def satisfied(self, clauses, true):
        return all(any((l > 0) == (abs(l) in true) for l in c) for c in clauses)

    def agree(self, check, ks, r, n, distinct=False):
        clauses = R.formula(check, ks, r, n, distinct)
        cp = {"check": check, "lengths": ",".join(map(str, ks)) or "3", "distinct": distinct, "colors": r,
              "length": n, "count": 0, "proof_sha256": ""}
        for col in itertools.product(range(r), repeat=n):
            true = {(i - 1) * r + c + 1 for i, c in enumerate(col, 1)}
            try:
                C.check([col], cp)
                ok = True
            except ValueError:
                ok = False
            self.assertEqual(self.satisfied(clauses, true), ok, (check, ks, n, col))

    def test_the_formula_is_the_claim(self):
        self.agree("ap", [3], 2, 9)                 # W(2;3) = 9: 1..8 colourable, 1..9 not
        self.agree("ap", [2, 3], 2, 7)
        self.agree("schur", [], 2, 5)               # S(2) = 4
        self.agree("schur", [], 2, 9, distinct=True)  # weak Schur WS(2) = 8
        self.agree("schur", [], 3, 7)

    def test_clause_order_is_the_documented_one(self):
        cl = R.formula("ap", [3], 2, 5)
        self.assertEqual(cl[:5], [(1, 2), (3, 4), (5, 6), (7, 8), (9, 10)])          # every number has a colour
        self.assertEqual(cl[5:9], [(-1, -3, -5), (-3, -5, -7), (-5, -7, -9), (-1, -5, -9)])  # colour 0, d = 1, 2
        cl = R.formula("schur", [], 2, 4)
        self.assertEqual(cl[4:8], [(-1, -3), (-2, -4), (-1, -3, -5), (-2, -4, -6)])   # {1, 2} then {1, 2, 3}


class Proofs(unittest.TestCase):
    def test_real_proofs_are_accepted(self):
        for f, (chk, ks, r, n) in {"w2-3-n9.lrat": ("ap", [3], 2, 9), "w2-4-n35.lrat": ("ap", [4], 2, 35)}.items():
            st = steps(os.path.join(DATA, f))
            self.assertEqual(R.check_lrat(R.formula(chk, ks, r, n), st, n * r), len(st), f)
        st = steps(os.path.join(GALLERY, "data", "schur-3-n14.lrat"))
        k = R.check_lrat(R.formula("schur", [], 3, 14), st, 42)
        self.assertEqual(sum(1 for s in st[:k] if s[0] == "a"), 311)

    def test_a_proof_proves_only_its_own_claim(self):
        st = steps(os.path.join(DATA, "w2-3-n9.lrat"))
        for chk, ks, r, n in [("ap", [3], 2, 8), ("ap", [4], 2, 9), ("ap", [3, 4], 2, 9), ("schur", [], 2, 9),
                              ("ap", [3], 2, 10)]:
            with self.assertRaises(ValueError, msg=(chk, ks, n)):
                R.check_lrat(R.formula(chk, ks, r, n), st, n * r)


class Spoiled(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="exactfig-ref-")
        with open(os.path.join(DATA, "w2-3-n9.lrat"), encoding="utf-8") as fh:
            self.lines = fh.read().splitlines()
        self.cl = R.formula("ap", [3], 2, 9)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_lines(self, lines):
        p = os.path.join(self.dir, "p.lrat")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return R.check_lrat(self.cl, steps(p), 18)

    def refused(self, lines, words):
        with self.assertRaises((ValueError, io.DataError)) as cm:
            self.run_lines(lines)
        self.assertIn(words, str(cm.exception))

    def test_each_spoiled_proof_is_refused_for_its_reason(self):
        self.assertEqual(self.run_lines(self.lines), len([l for l in self.lines if l.strip()]))
        first = self.lines[0].split()                        # '42 -16 -17 -18 0 32 7 21 … 0'
        z = first.index("0")
        flipped = [first[0], str(-int(first[1]))] + first[2:]
        self.refused([" ".join(flipped)] + self.lines[1:], "hint")
        no_hints = first[:z + 1] + [first[z + 1], "0"]
        self.refused([" ".join(no_hints)] + self.lines[1:], "never reach a conflict")
        self.refused(self.lines[:-1], "never adds the empty clause")
        rat = first[:z + 1] + ["-" + first[z + 1]] + first[z + 2:]
        self.refused([" ".join(rat)] + self.lines[1:], "RAT step")
        newvar = [first[0], "19"] + first[1:]
        self.refused([" ".join(newvar)] + self.lines[1:], "outside the formula")
        self.refused([" ".join(["41"] + first[1:])] + self.lines[1:], "must be new")
        self.refused([" ".join(first[:z]) + " " + " ".join(first[z + 1:])] + self.lines[1:], "two zeros")
        self.refused(["42 d x 0"], "a deletion is")
        self.refused([" ".join(first[:z + 1] + ["99"] + first[z + 1:])] + self.lines[1:], "hint 99 is not a clause")

    def test_binary_lrat_is_refused_with_a_hint(self):
        p = os.path.join(self.dir, "b.lrat")
        with open(p, "wb") as fh:
            fh.write(b"a\x54\x21\x00\x02\x00")
        with self.assertRaises(io.DataError) as cm:
            steps(p)
        self.assertIn("binary LRAT", str(cm.exception))


class Figure(unittest.TestCase):
    def test_recipe_renders_and_states_its_steps(self):
        with open(os.path.join(ROOT, "examples", "recipes", "schur-3-refutation.json"), encoding="utf-8") as fh:
            rec = json.load(fh)
        out = render(rec, GALLERY)
        self.assertEqual((out.width, out.height), (416, 112))
        rec["params"]["steps"] = 310
        with self.assertRaises(ValueError) as cm:
            render(rec, GALLERY)
        self.assertIn("adds 311 clauses", str(cm.exception))
        rec["params"].update(steps=0, length=13)
        with self.assertRaises(ValueError):
            render(rec, GALLERY)


if __name__ == "__main__":
    unittest.main()
