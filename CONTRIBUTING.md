# Contributing / Contribuir

Thanks for helping. The project has one rule that every change must keep: **every asset is the output of published code**.

## Ground rules

1. **No AI-generated content** in art, music, palettes or examples. Everything in `gallery/` comes from a recipe in
   `examples/recipes/` through `exactfig record`, and every input file in `gallery/data/` (including the source picture
   of the image-conversion examples) is made by code: `examples/data/make_data.py`, or the Lean programs in `lean/`.
   Users may of course convert and plot their own data and pictures; the gallery only holds what this repository can
   regenerate.
2. **Determinism.** A generator must give the same output for the same recipe, in any process and on any platform. Use
   `exactfig.rng.Rng` (never `random`) and `exactfig.fmath` for `sin`, `cos`, `atan2`, `exp`, `log`, `pow`, `hypot` and
   distances (never `math.sin`… or `**` on floats: `tests/test_fmath.py` checks it), never iterate over sets or dicts of
   strings when the order affects output, never read the clock, the environment or files.
3. **Closed schemas.** New parameters have a type and a range (or a list of choices). No parameter may accept pixel data, free
   arrays or long strings.
4. **Versions.** If a change moves any output pixel or byte of an existing generator, bump its `version` in
   `exactfig/registry.py` and re-record the gallery.
5. **Palette lock.** Draw palette indices on a `Canvas`; never write RGB directly.
6. No dependencies beyond the Python standard library.
7. **Pure core.** Generators and everything they call do no I/O, read no clock or environment and never call `hash()`;
   only the shell (`render`, `provenance`, `cli`, `registry`, `data/io`) touches files. `tests/test_architecture.py` checks
   it; [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) explains the layers and how to add a generator.
8. **Documentation.** Every public function says what it returns, in which units, and what it guarantees or refuses;
   every generator's module docstring names its method and its source.
9. **Lean files** (`lean/`) use core Lean only and no `sorry`, `axiom` or `native_decide`; when one changes, re-run it and
   commit its output with it (see [lean/README.md](lean/README.md)).

## Workflow

```sh
python -m unittest discover tests
python -m exactfig record examples/recipes/*.json --manifest gallery/manifest.json   # only if outputs changed
python -m exactfig verify --manifest gallery/manifest.json --strict
```

Add tests for new maths against known, independent facts (e.g. "the Pisano period of 7 is 16", "Menger level 2 keeps 400 of
729 cubes"), not against the code's own output.

Comments may be in English or Spanish; public docs are bilingual (README.md and README.es.md).

---

**En español:** todo asset sale de código publicado (nada de IA, nada importado), los generadores son deterministas, los
parámetros tienen esquema cerrado, si cambias un píxel subes la versión del generador y vuelves a apuntar la galería, y sin
dependencias fuera de la biblioteca estándar.
