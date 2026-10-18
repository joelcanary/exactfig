"""`exactfig selftest` passes here, and covers what it says it covers."""
import os
import subprocess
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig import registry, selftest  # noqa: E402


class SelfTest(unittest.TestCase):
    def test_passes_on_this_machine(self):
        lines = []
        self.assertTrue(selftest.run(lines.append), "\n".join(lines))

    def test_every_kind_of_generator_is_represented(self):
        kinds = {registry.get(r["generator"]).kind for r, _ in selftest.RECIPES}
        self.assertEqual(kinds, {"image", "animation", "midi"})

    def test_the_command_line_reports_and_exits_zero(self):
        out = subprocess.run([sys.executable, "-m", "exactfig", "selftest"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("all checks passed", out.stdout)


if __name__ == "__main__":
    unittest.main()
