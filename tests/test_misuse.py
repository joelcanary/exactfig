"""Every misuse in tests/misuse_bench.py ends as it should: legitimate inputs (a recipe saved by Notepad with a BOM, or by
Windows PowerShell in UTF-16, CRLF line ends, folders with accents) work; everything else is refused with a one-line
`exactfig: …` message — never a traceback, never a hang, and never a silent success (an output written outside its
folder, or a `verify` that checked nothing)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import misuse_bench  # noqa: E402


class Misuse(unittest.TestCase):
    def test_every_case_ends_as_it_should(self):
        bad = misuse_bench.run_all(verbose=False)
        self.assertEqual(bad, [], "\n".join(f"{n}: {p}" for n, p in bad))


if __name__ == "__main__":
    unittest.main()
