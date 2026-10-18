# Lean

Two ways exactfig uses [Lean 4](https://lean-lang.org/) (plain core Lean, no Mathlib):

1. **Proving properties of the algorithms it uses.** `Line.lean` re-implements Bresenham's line exactly as
   `exactfig.pixel.pxmath.line` and proves, for every pair of endpoints with coordinates in 0..4, that the line starts and
   ends at its endpoints, that consecutive points are 8-neighbours, and that it has max(|Δx|, |Δy|) + 1 points.
2. **Computing data whose properties are proved, then drawing it.** `Life.lean` defines Life-like rules on a torus and
   proves that a glider moves one cell diagonally in four generations, returns to its start after 32 on an 8 × 8 torus,
   and that the blinker has period exactly 2. Its `main` prints the glider's 33 frames; exactfig animates them
   (`examples/recipes/lean-glider.json`), and the animation is pinned to that output by SHA-256.

The proofs are by `decide +kernel`: Lean's kernel evaluates the statements. They are exhaustive over the stated finite
cases, not general theorems about all lines or all boards.

| File | Theorems | Output (committed) |
|---|---|---|
| `Life.lean` | `glider_moves`, `glider_returns`, `blinker_period_two`, `blinker_moves` | `gallery/data/lean-glider.json` |
| `Line.lean` | `bresenham_correct_on_box` | `lean/data/lines.json` (2401 lines, endpoints in −3..3) |

## Checking

```sh
lean lean/Life.lean                                   # the kernel checks the theorems (a few seconds)
lean lean/Line.lean
lean --run lean/Life.lean > gallery/data/lean-glider.json
lean --run lean/Line.lean > lean/data/lines.json
python -m unittest tests.test_lean                    # no Lean needed: compares the outputs with exactfig's own code
```

`tests/test_lean.py` checks, without Lean installed, that exactfig draws exactly the 2401 lines Lean computed and that
its own Life reproduces Lean's 33 frames, that every theorem the data cites exists in its file, and that no Lean file uses
`sorry`, `admit`, `axiom`, `native_decide` or `implemented_by`. Tested with Lean v4.35.
