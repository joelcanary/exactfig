# Changelog

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
