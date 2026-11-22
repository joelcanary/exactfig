"""data.circuit_refutation against independent facts:

- the formula is satisfiable exactly when the function has a circuit of at most s gates: for every function of 2
  inputs and s = 1, 2, and for several of 3 inputs and s up to 4, a small DPLL solver written here decides the formula
  and a brute-force enumeration of circuits (also written here) gives the true minimum size;
- a satisfying assignment found by that solver is a real circuit: read back and evaluated on every input;
- the LRAT checker accepts a proof only for its own claim: the proof that MOD_3 with residue 1 on 3 inputs has no
  circuit of 3 gates (CaDiCaL, tests/data) checks, and fails for residue 2, for 2 gates and for 4 inputs."""
import itertools
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig.data import io  # noqa: E402
from exactfig.forge import circuit_refutation as CR  # noqa: E402
from exactfig.forge.circuit import target  # noqa: E402
from exactfig.forge.refutation import check_lrat  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def dpll(clauses, nvars):
    """A satisfying assignment {var: bool} or None (unit propagation + branching; small formulas only)."""
    def simplify(cls, lit):
        out = []
        for c in cls:
            if lit in c:
                continue
            if -lit in c:
                c = tuple(x for x in c if x != -lit)
                if not c:
                    return None
            out.append(c)
        return out

    def go(cls, asg):
        while True:
            unit = next((c[0] for c in cls if len(c) == 1), None)
            if unit is None:
                break
            asg = dict(asg)
            asg[abs(unit)] = unit > 0
            cls = simplify(cls, unit)
            if cls is None:
                return None
        if not cls:
            return asg
        v = abs(cls[0][0])
        for lit in (v, -v):
            nxt = simplify(cls, lit)
            if nxt is not None:
                r = go(nxt, {**asg, v: lit > 0})
                if r is not None:
                    return r
        return None

    return go([tuple(c) for c in clauses], {})


def min_size(n, f, cap):
    """Smallest number of gates (≤ cap) of a circuit computing f, by enumerating circuits; cap + 1 if none."""
    rows = 1 << n
    full = (1 << rows) - 1
    inputs = []
    for i in range(n):
        t = 0
        for m in range(rows):
            if m >> i & 1:
                t |= 1 << m
        inputs.append(t)
    if f in inputs:
        return 0

    def apply(op, a, b):
        r = 0
        if op & 8:
            r |= full & ~a & ~b
        if op & 4:
            r |= full & ~a & b
        if op & 2:
            r |= a & full & ~b
        if op & 1:
            r |= a & b
        return r

    level = {frozenset(inputs)}                 # a state: the set of functions computed so far (order is irrelevant)
    for size in range(1, cap + 1):
        nxt = set()
        for nodes in level:
            for a, b in itertools.combinations(sorted(nodes), 2):
                for op in range(16):
                    v = apply(op, a, b)
                    if v == f:
                        return size
                    if size < cap and v not in nodes:
                        nxt.add(nodes | {v})
        level = nxt
    return cap + 1


def read_back(n, s, asg):
    """The circuit a satisfying assignment describes, evaluated on every input: the last gate's truth table."""
    blocks, _ = CR.layout(n, s)
    vals = {}
    for v in range(1, n + 1):
        vals[v] = [(t >> (v - 1)) & 1 for t in range(1 << n)]
    for a, (_, sel, ops, _) in enumerate(blocks, 1):
        j, k = next(pair for pair, var in sel.items() if asg.get(var))
        table = [int(bool(asg.get(o))) for o in ops]
        vals[n + a] = [table[2 * vals[j][t] + vals[k][t]] for t in range(1 << n)]
    return sum(b << t for t, b in enumerate(vals[n + s]))


class TestCircuitRefutation(unittest.TestCase):
    def test_formula_means_size_at_most_s(self):
        cases = [(2, f, s) for f in range(16) for s in (1, 2)]
        cases += [(3, target(spec, 3), s) for spec in ("mod 3 1", "mod 3 0", "parity", "threshold 2", "threshold 3")
                  for s in (1, 2, 3, 4)]
        for n, f, s in cases:
            clauses, nvars, _, _ = CR.formula(n, s, f)
            asg = dpll(clauses, nvars)
            truth = min_size(n, f, s) <= s
            self.assertEqual(asg is not None, truth, (n, f, s))
            if asg is not None:
                self.assertEqual(read_back(n, s, asg), f, (n, f, s))

    def test_known_sizes(self):
        self.assertEqual(min_size(3, target("parity", 3), 3), 2)
        self.assertEqual(min_size(3, target("threshold 2", 3), 5), 4)
        self.assertEqual(min_size(3, target("mod 3 1", 3), 5), 4)

    def test_proof_checks_only_its_own_claim(self):
        proof = io.read_lrat(os.path.join(DATA, "circuit-mod3-1-n3-s3.lrat"))
        f = target("mod 3 1", 3)
        clauses, nvars, _, _ = CR.formula(3, 3, f)
        check_lrat(clauses, proof.steps, nvars)
        for n, s, spec in ((3, 3, "mod 3 2"), (3, 2, "mod 3 1"), (4, 3, "mod 3 1")):
            clauses, nvars, _, _ = CR.formula(n, s, target(spec, n))
            with self.assertRaises(ValueError):
                check_lrat(clauses, proof.steps, nvars)

    def test_refuses_too_few_inputs(self):
        with self.assertRaises(ValueError):
            CR.formula(1, 1, 1)


if __name__ == "__main__":
    unittest.main()
