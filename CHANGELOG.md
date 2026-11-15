# Changelog

## 0.4.0 (2026-11-15)

- **`data.instances`**: instance masks (COCO RLE, compressed or not, or cells) drawn only after they are checked: no
  empty mask, no shared pixel, one-to-one matching by IoU > 1/2, stated TP/FP/FN and PQ equal to the exact values
  (fractions), and captions (`expect`) equal to the data's meta. `compare` draws truth and prediction on one panel.
  New input format `instances`; `rle_string_from_counts` / `rle_counts_from_string` in `exactfig.data.io`, checked
  against pycocotools. Gallery: a synthetic scene and its comparison (PQ 0.4670).
- **`data.coloring`**: colourings of 1..n — the witnesses a SAT solver returns — drawn only after they are checked: no
  colour holds an arithmetic progression of its length (van der Waerden numbers, one length per colour allowed) or a sum
  x + y (Schur numbers; weak Schur with `distinct`). `proof_sha256` records the SHA-256 of the proof of the other half of
  the theorem. New input format `coloring`. Gallery: a SAT witness for w(4; 2,3,3,3) = 40 (OEIS A217008) naming its
  DRAT proof, and a partition showing S(3) ≥ 13. Tested against W(2;3) = 9, S(2) = 4 and WS(2) = 8 by brute force.

## 0.3.0 (2026-11-15)

- **Mistakes end in a clear message, never a traceback.** One line `exactfig: what and why`, and exit codes 0 / 1 (verify
  found a difference) / 2 (input or environment refused) / 3 (internal error; `EXACTFIG_DEBUG=1` shows the traceback) /
  130 (interrupted). A new test, `tests/misuse_bench.py`, runs more than 80 real mistakes, one process each.
- **Security:** a recipe's `output` must be a relative path inside its folder, with the extension of what is written;
  before, `"../x.png"` or an absolute path wrote outside the output folder.
- **`verify` of a manifest that does not exist, or of a path that is not in it, now fails**; before, it reported
  "0/0 assets reproduced exactly" and exited 0, so a typo in a CI job would have passed.
- Animations and simulations over the limits are refused **before** computing (a 1024² × 1000-frame animation used to
  run for many minutes and then be refused); a new limit of 400 million cell-steps for simulations.
- Text files (recipes, manifests, CSV, JSON, catalogues) may be UTF-8 with or without a BOM, or UTF-16 with a BOM (what
  Notepad and Windows PowerShell 5 write); other encodings are refused with how to fix them. Decimal commas get a hint.
- The PNG reader refuses truncated, corrupted (checksums, image data) and oversized files with a message, and never
  inflates more data than the image can hold. Malformed inline palettes and manifests are refused with a message.
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
