"""The architecture, enforced: a pure functional core and a thin shell around it (docs/ARCHITECTURE.md).

Core modules compute: given the same arguments they return the same value, on any machine, in any process. They may
not read or write files, the clock, the environment or the network, nor draw from the system's randomness, nor call
`hash()` (randomised per process for strings), nor print. Only the shell (`render`, `provenance`, `cli`, `registry`,
`data/io`) does I/O, and core modules never import the shell. A registered generator must live in the core.
"""
import ast
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig import registry  # noqa: E402

PKG = os.path.join(os.path.abspath(ROOT), "exactfig")
SHELL = {"__main__.py", "cli.py", "render.py", "registry.py", "provenance/__init__.py", "data/io.py", "selftest.py"}
FORBIDDEN_MODULES = {"os", "sys", "io", "time", "datetime", "random", "secrets", "uuid", "socket", "subprocess", "threading",
                     "multiprocessing", "pathlib", "tempfile", "shutil", "glob", "urllib", "http", "asyncio", "signal",
                     "platform", "locale", "ctypes", "importlib"}
FORBIDDEN_CALLS = {"open", "input", "print", "eval", "exec", "compile", "__import__", "hash", "id", "globals", "vars"}
SHELL_MODULES = {"render", "provenance", "cli", "registry", "io"}


def modules():
    for dirpath, _, files in os.walk(PKG):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(dirpath, f)
                yield os.path.relpath(path, PKG).replace(os.sep, "/"), path


class PureCore(unittest.TestCase):
    def test_core_modules_do_no_io_and_no_hidden_state(self):
        bad = []
        for rel, path in modules():
            if rel in SHELL:
                continue
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), rel)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    bad += [f"{rel}:{node.lineno} import {a.name}" for a in node.names if a.name.split(".")[0] in FORBIDDEN_MODULES]
                elif isinstance(node, ast.ImportFrom):
                    if node.level == 0 and (node.module or "").split(".")[0] in FORBIDDEN_MODULES:
                        bad.append(f"{rel}:{node.lineno} from {node.module} import …")
                    if node.level > 0:
                        target = {(node.module or "").split(".")[-1]} | {a.name for a in node.names}
                        if (node.module or "").startswith("data") and "io" in target or target & (SHELL_MODULES - {"io"}):
                            bad.append(f"{rel}:{node.lineno} imports the shell ({node.module})")
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                    bad.append(f"{rel}:{node.lineno} {node.func.id}(…)")
        self.assertEqual(bad, [], "core modules must stay pure:\n" + "\n".join(bad))

    def test_every_generator_lives_in_the_core(self):
        for g in registry.all_generators().values():
            if g.fn is None:                                   # compose is assembled by render itself
                continue
            mod = g.fn.__module__.replace("exactfig.", "").replace(".", "/") + ".py"
            self.assertNotIn(mod, SHELL, g.name)
            for m in g.modules:
                self.assertTrue(os.path.exists(os.path.join(PKG, m)), f"{g.name}: module {m} does not exist")

    def test_every_generator_documents_its_parameters_range(self):
        for g in registry.all_generators().values():
            for name, p in g.params.items():
                if p.kind in ("int", "float"):
                    self.assertTrue(p.lo is not None and p.hi is not None, f"{g.name}.{name} has no range")
                if p.kind == "str":
                    self.assertTrue(p.choices, f"{g.name}.{name} has no closed list of choices")


if __name__ == "__main__":
    unittest.main()
