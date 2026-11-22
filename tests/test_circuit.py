"""data.circuit against independent facts:

- each of the 16 two-input functions, as a one-gate circuit, has the truth table of its name or its t-table;
- the targets (mod M R, threshold K, parity) agree with a direct count of ones, input by input, for n up to 6;
- the gallery circuit computes MOD_3 with residue 1 on 5 inputs, evaluated here input by input with Python's own
  operators (not the bit-parallel evaluation), and nothing else of its kind (residues 0, 2, parity, majority);
- textbook circuits: the chain of n − 1 XORs is parity, and (x1 ∧ x2) ∨ (x3 ∧ (x1 ⊕ x2)) is the majority of 3;
- every way of spoiling a circuit is refused for its own reason."""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig.data import io  # noqa: E402
from exactfig.forge import circuit as CI  # noqa: E402
from exactfig.render import render  # noqa: E402

GALLERY = os.path.join(os.path.abspath(ROOT), "gallery")
NAMED = {"and": lambda a, b: a & b, "or": lambda a, b: a | b, "xor": lambda a, b: a ^ b,
         "nand": lambda a, b: 1 - (a & b), "nor": lambda a, b: 1 - (a | b), "xnor": lambda a, b: 1 - (a ^ b),
         "andnot": lambda a, b: a & (1 - b), "notand": lambda a, b: (1 - a) & b,
         "ornot": lambda a, b: a | (1 - b), "notor": lambda a, b: (1 - a) | b}


def params(**kw):
    p = {"function": "", "inputs": 0, "gates": 0, "strict": True}
    p.update(kw)
    return p


class TestCircuit(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="exactfig-circuit-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def read(self, text):
        p = os.path.join(self.dir, "c.txt")
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        return io.read_circuit(p)

    def run_inputs(self, circ, bits):
        """Evaluate gate by gate with Python's operators on one input (independent of CI.evaluate)."""
        v = {f"x{i}": bits[i - 1] for i in range(1, circ.inputs + 1)}
        for name, table, a, b in circ.gates:
            v[name] = int(table[2 * v[a] + v[b]])
        return v[circ.output]

    def test_every_two_input_function(self):
        for name, f in NAMED.items():
            c = self.read(f"inputs 2\ng = {name} x1 x2\noutput g\n")
            want = "".join(str(f(a, b)) for a in (0, 1) for b in (0, 1))
            self.assertEqual(c.gates[0][1], want, name)
            t = sum(f(m & 1, m >> 1 & 1) << m for m in range(4))
            CI.check(c, params(function=f"table {t:x}"))
        for k in range(16):
            table = f"{k:04b}"
            c = self.read(f"inputs 2\ng = t{table} x1 x2\noutput g\n")
            got = CI.evaluate(c)["g"]
            for m in range(4):
                self.assertEqual(got >> m & 1, int(table[2 * (m & 1) + (m >> 1 & 1)]))

    def test_targets_count_ones(self):
        for n in range(1, 7):
            for m in range(2, 5):
                for r in range(m):
                    t = CI.target(f"mod {m} {r}", n)
                    for x in range(1 << n):
                        self.assertEqual(t >> x & 1, int(bin(x).count("1") % m == r))
            for k in range(n + 2):
                t = CI.target(f"threshold {k}", n)
                self.assertEqual([t >> x & 1 for x in range(1 << n)],
                                 [int(bin(x).count("1") >= k) for x in range(1 << n)])
            self.assertEqual(CI.target("parity", n), CI.target("mod 2 1", n))
        self.assertEqual(CI.target("mod 3 1", 5), 0x68818116)

    def test_gallery_circuit_is_mod3_residue_1(self):
        c = io.read_circuit(os.path.join(GALLERY, "data", "mod3-1-n5.circuit"))
        self.assertEqual((c.inputs, len(c.gates)), (5, 9))
        for m in range(32):
            bits = [m >> i & 1 for i in range(5)]
            self.assertEqual(self.run_inputs(c, bits), int(sum(bits) % 3 == 1), m)
        self.assertEqual(CI.check(c, params(function="mod 3 1", inputs=5, gates=9))["gates"], 9)
        for other in ("mod 3 0", "mod 3 2", "parity", "threshold 3"):
            with self.assertRaises(ValueError):
                CI.check(c, params(function=other))

    def test_textbook_circuits(self):
        for n in range(2, 9):
            lines = [f"inputs {n}", "g2 = xor x1 x2"] + [f"g{i} = xor g{i - 1} x{i}" for i in range(3, n + 1)]
            c = self.read("\n".join(lines + [f"output g{n}"]) + "\n")
            CI.check(c, params(function="parity", gates=n - 1))
        c = self.read("inputs 3\na = and x1 x2\nx = xor x1 x2\nb = and x3 x\nm = or a b\noutput m\n")
        CI.check(c, params(function="threshold 2", inputs=3, gates=4))

    def test_spoiled_circuits_are_refused(self):
        ok = "inputs 2\ng = xor x1 x2\noutput g\n"
        CI.check(self.read(ok), params(function="parity"))
        cases = [
            ("inputs 2\ng = and x1 x2\noutput g\n", "parity", "on input m = 1"),
            ("inputs 2\nd = and x1 x2\ng = xor x1 x2\noutput g\n", "parity", "does not lead to the output"),
        ]
        for text, f, msg in cases:
            with self.assertRaisesRegex(ValueError, msg):
                CI.check(self.read(text), params(function=f))
        with self.assertRaisesRegex(ValueError, "2 inputs, the recipe states 3"):
            CI.check(self.read(ok), params(function="parity", inputs=3))
        with self.assertRaisesRegex(ValueError, "1 gates, the recipe states 2"):
            CI.check(self.read(ok), params(function="parity", gates=2))
        CI.check(self.read("inputs 2\nd = and x1 x2\ng = xor x1 x2\noutput g\n"), params(function="parity",
                                                                                         strict=False))
        for spec in ("", "mod 3 3", "mod 1 0", "threshold", "table 0x1ff", "table zz", "majority"):
            with self.assertRaises(ValueError, msg=spec):
                CI.target(spec, 3)
        bad = [("g = xor x1 x2\noutput g\n", "inputs n"), ("inputs 2\ng = xor x1 h\noutput g\n", "before it is defined"),
               ("inputs 2\ng = xor x1 x2\ng = and x1 x2\noutput g\n", "already defined"),
               ("inputs 2\ng = maj x1 x2\noutput g\n", "unknown gate"), ("inputs 2\ng = xor x1 x2\n", "no `output`"),
               ("inputs 2\noutput x1\ng = xor x1 x2\n", "nothing may follow"), ("inputs 2\nx1 = xor x1 x2\noutput x1\n",
                                                                               "already defined"),
               ("inputs 21\noutput x1\n", "between 1 and 20"), ("inputs 2\ng = xor x1 x3\noutput g\n", "before it is"),
               ("inputs 2\n9g = xor x1 x2\noutput 9g\n", "not a name"), ("inputs 2\ng xor x1 x2\noutput g\n", "name = op")]
        for text, msg in bad:
            with self.assertRaisesRegex(io.DataError, msg):
                self.read(text)

    def test_recipe_renders(self):
        with open(os.path.join(ROOT, "examples", "recipes", "mod3-circuit.json"), encoding="utf-8") as fh:
            out = render(json.load(fh), GALLERY)
        self.assertEqual((out.width, out.height), (560, 360))


if __name__ == "__main__":
    unittest.main()
