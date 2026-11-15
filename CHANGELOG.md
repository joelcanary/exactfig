# Changelog

## Unreleased

- **`data.catalog`**: a catalogue of cell patterns (one per line, `WxH: rows`) drawn as a mosaic only after it is checked
  against the recipe: still lifes or oscillators of an exact period under a Life-like rule (simulated on the infinite
  plane), strict rather than pseudo still lifes, the population of every pattern, the number of patterns (the sequence
  term) and no repeats up to symmetry. A refusal names the first pattern that fails. New input format `catalog`.
  Gallery: the 49 strict still lifes of 14 cells under Move (OEIS A175001(14) = 49). Tested against the classical still
  lifes and oscillators of Conway's Life and the counts of OEIS A019473 for n ≤ 7.
- Licensed under the Apache License 2.0 (`LICENSE`), declared in `pyproject.toml` and `CITATION.cff`.
- Continuous integration: the test suite and `exactfig selftest` on Linux, macOS and Windows, and the gallery verified
  bit for bit on Linux.
- Tests: `cbrt` is checked against the exact cube root (within 1 ulp) instead of the platform's `math.cbrt`, which is
  itself a few ulp off in glibc; the example PNG is compared by pixels, as `verify` does, since zlib builds compress
  differently (Python 3.14 on Windows).
- Continuous integration runs on the Node 24 versions of the GitHub actions (`actions/checkout@v5`,
  `actions/setup-python@v6`); the Node 20 ones are deprecated.

## 0.2.0 (2026-10-18)

First complete release under the name **exactfig**.

- **Reproducibility.** Portable transcendental functions (`fmath`, after fdlibm, ≤ 1 ulp) so a recipe gives the same bits
  on every platform; checked on x86-64 and ARM64. `exactfig selftest` checks a machine in a few seconds.
- **Data.** CSV, Netpbm PGM/PPM, NumPy `.npy`, JSON and PNG inputs, pinned by SHA-256 in the recipe. `data.field`
  (colour, hill-shading, iso-lines), `data.scatter` (exact Delaunay reconstruction), `data.image` (linear-light
  resampling, median-cut and k-means palettes, Sobel outlines), `anim.frames`.
- **Animations.** GIF and APNG written and read by exactfig, verified frame by frame: Life-like automata, the wave
  equation, the Lorenz system, the heat equation on data, Fourier epicycles. MP4 through FFmpeg for sharing.
- **Layers and editing.** `compose` (over, under, mask), `draw.annotate`, `exactfig edit`, per-entry history.
- **Mathematics.** Phase portraits, logistic bifurcations, the Ulam spiral, modular multiplication circles, Fourier
  partial sums and the Gibbs phenomenon.
- **Lean 4.** Kernel-checked facts about the line algorithm and Life, whose outputs are drawn and cross-checked.
- **Architecture.** A pure functional core enforced by tests; every mathematical claim tested against an independent fact.

## 0.1.0

Procedural pixel art and music with verifiable provenance (the initial import).
