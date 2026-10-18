"""Portable maths (exactfig.fmath): fixed bit patterns, accuracy against the platform library, and a guard that keeps
generator code off the platform's transcendental functions."""
import ast
import math
import os
import unittest

from exactfig import fmath as F
from exactfig.rng import Rng

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "exactfig")

# Results as IEEE 754 bit patterns. fmath uses basic arithmetic only, so these must hold on every platform: a failure here
# on some machine is exactly the kind of difference fmath exists to prevent.
GOLDEN = [
    ("sin", (1.0,), "0x1.aed548f090ceep-1"),
    ("sin", (-1516.4401607767743,), "-0x1.a032a440195e2p-1"),
    ("sin", (100000.0,), "0x1.24daa9c527e96p-5"),
    ("cos", (0.7,), "0x1.87996529f9d93p-1"),
    ("cos", (157.9,), "0x1.5d28e40602207p-1"),
    ("atan", (0.3,), "0x1.2a73a661eaf06p-2"),
    ("atan", (-12.5,), "-0x1.7daff85a63058p+0"),
    ("atan2", (1.0, -2.0), "0x1.56c6e7397f5aep+1"),
    ("atan2", (-3.0, 0.5), "-0x1.67d8863bc99bdp+0"),
    ("exp", (1.0,), "0x1.5bf0a8b14576ap+1"),
    ("exp", (-20.25,), "0x1.b93de1e27ca3bp-30"),
    ("log", (10.0,), "0x1.26bb1bbb55516p+1"),
    ("log", (1e-300,), "-0x1.5963447f87fb5p+9"),
    ("log2", (10.0,), "0x1.a934f0979a371p+1"),
    ("pow", (0.3, 2.4), "0x1.c77e018c0c76ep-5"),
    ("pow", (1.618033988749895, 0.73), "0x1.6bbf8ef6c2b1dp+0"),
    ("cbrt", (0.2,), "0x1.2b6b5edf6b54ap-1"),
    ("cbrt", (-27.5,), "-0x1.825b1b6bac03bp+1"),
]


def ulps(got: float, want: float) -> float:
    return 0.0 if got == want else abs(got - want) / math.ulp(want)


class BitPatterns(unittest.TestCase):
    def test_fixed_results_are_the_same_bits_everywhere(self):
        for name, args, want in GOLDEN:
            with self.subTest(f"{name}{args}"):
                self.assertEqual(getattr(F, name)(*args).hex(), want)


class Accuracy(unittest.TestCase):
    """Against the platform's library, which is itself within an ulp or so: the bound is on fmath, not a claim that the
    platform is exact."""

    N = 20000

    def sample(self, name, f, g, gen, bound):
        r = Rng(f"fmath-{name}")
        worst = 0.0
        for _ in range(self.N):
            args = gen(r)
            worst = max(worst, ulps(f(*args), g(*args)))
        self.assertLessEqual(worst, bound, f"{name}: {worst} ulp")

    def test_sin_cos_within_one_ulp(self):
        self.sample("sin", F.sin, math.sin, lambda r: (r.uniform(-2000.0, 2000.0),), 1.0)
        self.sample("cos", F.cos, math.cos, lambda r: (r.uniform(-2000.0, 2000.0),), 1.0)
        self.sample("sin-small", F.sin, math.sin, lambda r: (r.uniform(-1.0, 1.0) * 10.0 ** -r.randint(0, 12),), 1.0)

    def test_atan_atan2_within_one_ulp(self):
        self.sample("atan", F.atan, math.atan, lambda r: (r.uniform(-1.0, 1.0) * 10.0 ** r.randint(-8, 8),), 1.0)
        self.sample("atan2", F.atan2, math.atan2, lambda r: (r.uniform(-10.0, 10.0), r.uniform(-10.0, 10.0)), 1.0)

    def test_exp_log_within_one_ulp(self):
        self.sample("exp", F.exp, math.exp, lambda r: (r.uniform(-700.0, 700.0),), 1.0)
        self.sample("log", F.log, math.log, lambda r: (r.uniform(1.0, 10.0) * 10.0 ** r.randint(-300, 300),), 1.0)
        self.sample("log2", F.log2, math.log2, lambda r: (r.uniform(1.0, 10.0) * 10.0 ** r.randint(-300, 300),), 1.0)

    @unittest.skipUnless(hasattr(math, "cbrt"), "math.cbrt needs Python 3.11")
    def test_cbrt_within_two_ulps(self):
        self.sample("cbrt", F.cbrt, math.cbrt, lambda r: (r.uniform(-1.0, 1.0) * 10.0 ** r.randint(-200, 200),), 2.0)

    def test_pow_relative_error(self):
        r = Rng("fmath-pow")
        for _ in range(self.N):
            x, y = r.uniform(0.001, 10.0), r.uniform(-8.0, 8.0)
            want = math.pow(x, y)
            self.assertLess(abs(F.pow(x, y) - want) / want, 2e-14)


class ExactFacts(unittest.TestCase):
    def test_exact_values(self):
        for k in range(-60, 61):
            self.assertEqual(F.log2(2.0 ** k), k)
        self.assertEqual(F.sin(0.0), 0.0)
        self.assertEqual(F.cos(0.0), 1.0)
        self.assertEqual(F.exp(0.0), 1.0)
        self.assertEqual(F.log(1.0), 0.0)
        self.assertEqual(F.pow(2.0, 10.0), 1024.0)
        self.assertEqual(F.pow(9.0, 0.5), 3.0)
        self.assertEqual(F.cbrt(-8.0), -2.0)

    def test_atan2_quadrants_and_zeros(self):
        self.assertEqual(F.atan2(0.0, -1.0), math.pi)
        self.assertEqual(F.atan2(-0.0, -1.0), -math.pi)
        self.assertEqual(math.copysign(1.0, F.atan2(-0.0, 1.0)), -1.0)
        self.assertEqual(F.atan2(1.0, 0.0), math.pi / 2)
        self.assertEqual(F.atan2(-1.0, 0.0), -math.pi / 2)

    def test_domain_errors_are_explicit(self):
        with self.assertRaises(ValueError):
            F.log(0.0)
        with self.assertRaises(ValueError):
            F.pow(-2.0, 0.5)
        with self.assertRaises(ValueError):
            F.sin(1e7)                      # beyond the exact argument reduction: refused, never silently wrong


FORBIDDEN = {"sin", "cos", "tan", "asin", "acos", "atan", "atan2", "sinh", "cosh", "tanh", "exp", "expm1", "log",
             "log2", "log10", "log1p", "pow", "hypot", "dist", "cbrt", "erf", "erfc", "gamma", "lgamma"}


class Guard(unittest.TestCase):
    """Code that produces assets must not call the platform's transcendental functions, nor `**` (CPython's float `**`
    is the C library's pow, even for an integer exponent)."""

    def test_no_platform_transcendentals_in_the_package(self):
        bad = []
        for dirpath, _, files in os.walk(PKG):
            for f in files:
                if not f.endswith(".py") or f == "fmath.py":
                    continue
                path = os.path.join(dirpath, f)
                rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
                with open(path, encoding="utf-8") as fh:
                    tree = ast.parse(fh.read(), rel)
                for node in ast.walk(tree):
                    if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "math"
                            and node.attr in FORBIDDEN):
                        bad.append(f"{rel}:{node.lineno} math.{node.attr}")
                    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
                        ints = all(isinstance(v, ast.Constant) and type(v.value) is int for v in (node.left, node.right))
                        if not ints and not rel.endswith(("music/smf.py", "provenance/__init__.py")):
                            bad.append(f"{rel}:{node.lineno} '**' (use fmath.pow or a product)")
        self.assertEqual(bad, [], "use exactfig.fmath instead:\n" + "\n".join(bad))


if __name__ == "__main__":
    unittest.main()
