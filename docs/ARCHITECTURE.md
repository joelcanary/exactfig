# Architecture

exactfig is a build system for figures. Its shape follows the tools that make *software* builds reproducible, applied
to images, animations and MIDI files:

- **content addressing** (as in Nix or Bazel): every output is named by hashes of what produced it, and checking means
  rebuilding and comparing;
- **a functional core and an imperative shell** (G. Bernhardt's term): everything that computes a figure is a pure
  function; the little code that touches files lives around it;
- **a plugin registry with closed, declarative schemas**: generators are entries in a table, and a recipe can only say
  what a schema allows.

Each property below is enforced by a test, not only described.

## Layers

```
                ┌──────────────────────────────────────────────────────────────┐
  shell         │ cli.py · provenance/ (record, verify, manifest) · render.py │  reads and writes files
                │ data/io.py (CSV, PGM, NPY, JSON readers) · registry.py        │
                └───────────────▲──────────────────────────────────────────────┘
                                │ calls, never the other way round
                ┌───────────────┴──────────────────────────────────────────────┐
  core          │ forge/ (generators) · data/field.py · data/scatter.py        │  pure functions:
                │ pixel/ (canvas, palettes, dithering, PNG/GIF/APNG encoders)  │  same arguments,
                │ music/ · fmath.py · rng.py                                   │  same bytes
                └──────────────────────────────────────────────────────────────┘
```

`tests/test_architecture.py` parses every core module and fails if one imports `os`, `sys`, `time`, `random`, `socket`,
`subprocess`… or the shell, or calls `open`, `print`, `eval`, `exec`, `hash` (randomised per process for strings) or `id`.
It also checks that every registered generator is a core function and that every numeric parameter has a range and every
string parameter a closed list of choices.

## The pipeline of one recipe (`render.py`)

| Stage | Pure? | What happens | Guarded by |
|---|---|---|---|
| 1. normalize | yes | the recipe is checked against the generator's schema and every default written in; layers are normalised one by one | `test_provenance.Schema` |
| 2. inputs | no | each named data file is read and must match its pinned SHA-256 | `test_data.DataProvenance` |
| 3. draw | yes | `generator(seed, palette, w, h, params[, data])` → a Canvas or `(delay, Canvas)` frames | `test_provenance.Determinism` (twice in-process, and in fresh processes with other `PYTHONHASHSEED`s) |
| 4. encode | yes | integer scale, then PNG / GIF / APNG / MIDI bytes and the canonical content hash | `test_motion.Containers`, `test_pixel` |

`identity(recipe)` gives the generator's name, version and source hash; for a composition it covers every layer's
generator, so editing any of them is seen by `verify`.

## Invariants and where they are checked

| Invariant | Why it matters | Test |
|---|---|---|
| A recipe gives the same bytes on every platform | the whole point: anyone can check | `test_fmath` (bit patterns), gallery verified on x86-64 and ARM64 |
| No transcendental function or float `**` from the platform library | C libraries round `sin`, `pow`… differently | `test_fmath.Guard` |
| Generators draw palette indices only | colours are declared, `verify` can check them | `Canvas.set` refuses other indices; `verify` checks every pixel |
| A recipe cannot carry a picture | the information comes from the code (or a named, hashed data file) | closed schemas (`registry.P.check`), shapes capped at 64 |
| Data enters only as a named file pinned by SHA-256, inside the manifest folder | the figure is tied to exact bytes | `render._input`, `test_data.DataProvenance` |
| Outputs that change get a new generator version | an old manifest can never silently mean something else | `verify` refuses a version mismatch |
| Every claim about mathematics is tested against an independent fact | the code's own output is not evidence | `test_data`, `test_motion`, `test_layers_math`, `test_lean` |

## Extending it

**A new generator.**

1. Write a pure function in `forge/` with the signature `(seed, pal, w, h, p)` returning a `Canvas`, or `(seed, pal, w, h,
   p, data)` if it reads data, or a list of `(delay_ms, Canvas)` for an animation.
2. Use `exactfig.fmath` for every transcendental function and `exactfig.rng.Rng(seed)` for randomness. Draw palette
   indices from `pal.ramp(name)`.
3. Register it in `registry._gens()`: a name, version `"1"`, its kind, a schema in which every parameter has a range or
   a list of choices, and the modules its output depends on.
4. Add a small recipe to `SMALL` in `tests/test_provenance.py`. The determinism tests then cover it.
5. Add a test against a fact of its mathematics: a known period, an exact symmetry, a convergence order, a count.
6. If it is worth showing, add a recipe to `examples/recipes/` and `record` it.

**A new data format.** Add a reader to `data/io.py` returning a `Grid`, `Points` or `Frames`, list its extension in `_EXT`
and its shape in `FORMATS`, cap its size, and test it against an independent reader of the same format where one exists.

**Changing a generator's output.** Bump its `version`, re-record the gallery, and say why in the commit message.

## Why not a dependency stack

NumPy, Pillow or Matplotlib would make some things faster. They would also make the output depend on their versions,
their build flags and the platform's libm. The guarantee "same bytes everywhere" is cheaper to keep with a small,
dependency-free core. External tools are used where they cannot affect a verified output: FFmpeg for MP4 (documented as
not verifiable), and NumPy and Pillow in the tests, as independent checks of the readers and the containers.
