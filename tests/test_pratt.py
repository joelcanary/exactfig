"""data.pratt against independent facts:

- the gallery certificate proves 2^127 - 1 (checked here again line by line, without exactfig's check);
- every prime below 2000 gets a certificate built here by trial division, and exactfig accepts it;
- no composite below 700 can be certified: every witness g, with the true factorisation of n - 1, is refused
  (Carmichael 561 included, where Fermat's test alone passes for every g coprime to it);
- each way of spoiling a certificate is refused for its own reason;
- the tree: one leaf per path down to 2, each parent midway between its first and last child."""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig.data import io  # noqa: E402
from exactfig.forge import pratt as PR  # noqa: E402
from exactfig.render import render  # noqa: E402

GALLERY = os.path.join(os.path.abspath(ROOT), "gallery")
M127 = (1 << 127) - 1


def params(**kw):
    p = {"prime": "", "primes": 0}
    p.update(kw)
    return p


def factor(n):
    out, d = {}, 2
    while d * d <= n:
        while n % d == 0:
            out[d] = out.get(d, 0) + 1
            n //= d
        d += 1
    if n > 1:
        out[n] = out.get(n, 0) + 1
    return out


def is_prime(n):
    return n >= 2 and all(n % d for d in range(2, int(n ** 0.5) + 1))


def certificate(p, lines=None):
    """A Pratt certificate of p, built by trial division (independent of exactfig)."""
    lines = {} if lines is None else lines
    if p in lines:
        return lines
    if p == 2:
        lines[2] = "2"
        return lines
    fac = factor(p - 1)
    g = next(g for g in range(2, p) if all(pow(g, (p - 1) // q, p) != 1 for q in fac))
    lines[p] = f"{p} {g} " + " ".join(f"{q}^{e}" if e > 1 else str(q) for q, e in sorted(fac.items()))
    for q in fac:
        certificate(q, lines)
    return lines


def text(p):
    lines = certificate(p)
    return "\n".join([lines[p]] + [lines[q] for q in sorted(lines, reverse=True) if q != p]) + "\n"


class Tmp(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="exactfig-pratt-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def nodes(self, body):
        p = os.path.join(self.dir, "c.txt")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(body)
        return io.load(p, "primes", "pratt").nodes


class Gallery(Tmp):
    def test_the_certificate_of_2_127_minus_1(self):
        nodes = io.load(os.path.join(GALLERY, "data", "pratt-m127.txt"), "primes", "pratt").nodes
        self.assertEqual(PR.check(nodes, params(prime=str(M127), primes=19)), {"primes": 19, "digits": 39})
        lines = {p: (g, fac) for p, g, fac in nodes}
        self.assertEqual(nodes[0][0], M127)
        for p, (g, fac) in lines.items():                       # again, without exactfig's check
            if p == 2:
                continue
            prod = 1
            for q, e in fac:
                prod *= q ** e
                self.assertTrue(q == 2 or q in lines, q)
            self.assertEqual(prod, p - 1)
            self.assertEqual(pow(g, p - 1, p), 1)
            self.assertTrue(all(pow(g, (p - 1) // q, p) != 1 for q, _ in fac))

    def test_recipe_renders(self):
        with open(os.path.join(ROOT, "examples", "recipes", "pratt-m127.json"), encoding="utf-8") as fh:
            out = render(json.load(fh), GALLERY)
        self.assertEqual((out.width, out.height), (640, 260))


class Soundness(Tmp):
    def test_every_prime_below_2000_is_accepted(self):
        for p in range(2, 2000):
            if is_prime(p):
                PR.check(self.nodes(text(p)), params(prime=str(p)))

    def test_no_composite_below_700_has_a_certificate(self):
        for n in range(4, 700):
            if is_prime(n):
                continue
            fac = factor(n - 1)
            sub = {}
            for q in fac:
                certificate(q, sub)
            rest = self.nodes("\n".join(sub[q] for q in sorted(sub, reverse=True)) + "\n")
            facs = sorted(fac.items())
            for g in range(1, n):                                 # nodes in memory: one file per n, not one per g
                with self.assertRaises(ValueError, msg=(n, g)) as cm:
                    PR.check([(n, g, facs)] + rest, params())
                self.assertRegex(str(cm.exception), "Fermat fails|order of g", (n, g))   # refused by Lucas itself

    def test_carmichael_561_passes_fermat_but_not_lucas(self):
        coprime = [g for g in range(2, 561) if all(g % d for d in (3, 11, 17))]
        self.assertTrue(all(pow(g, 560, 561) == 1 for g in coprime))       # Fermat alone is fooled
        rest = self.nodes("7 3 2 3\n5 2 2^2\n3 2 2\n2\n")
        for g in coprime:
            with self.assertRaises(ValueError) as cm:
                PR.check([(561, g, [(2, 4), (5, 1), (7, 1)])] + rest, params())
            self.assertIn("order of g", str(cm.exception))


class Refusals(Tmp):
    def test_each_spoiled_certificate_is_refused_for_its_reason(self):
        good = "97 5 2^5 3\n3 2 2\n2\n"
        PR.check(self.nodes(good), params(prime="97", primes=3))
        cases = [
            ("97 2 2^5 3\n3 2 2\n2\n", params(), "order of g = 2 is not p − 1"),       # 2^48 ≡ 1 mod 97
            ("97 5 2^5 3\n2\n", params(), "the factor 3 has no line"),
            ("97 5 2^4 3\n3 2 2\n2\n", params(), "multiply to 48"),
            ("97 5 2^5 3 3\n3 2 2\n2\n", params(), "listed twice"),
            ("97 5 2^5 3\n3 2 2\n5 2 2^2\n2\n", params(), "p = 5) is not used"),
            ("97 5 2^5 3\n3 2 2\n2\n", params(prime="89"), "the recipe states 89"),
            ("97 5 2^5 3\n3 2 2\n2\n", params(primes=4), "3 lines"),
            ("97 97 2^5 3\n3 2 2\n2\n", params(), "not between 1 and p − 1"),
            ("91 2 2 3^2 5\n5 2 2^2\n3 2 2\n2\n", params(), "Fermat fails"),           # 91 = 7·13
            ("97 5 2^5 3\n3 2 2\n2 1\n", params(), "just '2'"),
            ("97 5 2^5 3\n97 5 2^5 3\n", params(), "already has a line"),
            ("97 5 2^5 x\n", params(), "the factor 'x'"),
            ("97 5\n", params(), "the prime, a witness and the factors"),
            ("97 5 1^3 2^5 3\n3 2 2\n2\n", params(), "factors are ≥ 2"),
        ]
        for body, p, words in cases:
            with self.assertRaises((ValueError, io.DataError), msg=body) as cm:
                PR.check(self.nodes(body), p)
            self.assertIn(words, str(cm.exception), body)


class Tree(Tmp):
    def test_layout(self):
        pts, edges, leaves = PR.tree(self.nodes("97 5 2^5 3\n3 2 2\n2\n"))
        self.assertEqual([q for q, _, _ in pts], [97, 2, 3, 2])          # children from the smallest prime
        self.assertEqual(leaves, 2)
        self.assertEqual(edges, [(0, 1), (0, 2), (2, 3)])
        self.assertEqual([x for _, _, x in pts], [1, 0, 2, 2])            # the root midway between its children
        nodes = io.load(os.path.join(GALLERY, "data", "pratt-m127.txt"), "primes", "pratt").nodes
        pts, _, leaves = PR.tree(nodes)
        self.assertEqual(sum(1 for q, _, _ in pts if q == 2), leaves)    # every path ends in 2


if __name__ == "__main__":
    unittest.main()
