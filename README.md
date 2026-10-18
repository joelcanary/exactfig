# exactfig

**Reproducible figures, animations and sonifications from data and published mathematics, verifiable bit for bit.**

[Leer en español](README.es.md)

exactfig turns a small JSON *recipe* (a generator, its parameters, a seed and, for data, a pinned input file) into an image,
an animation or a MIDI file, and records everything needed to reproduce it in a *manifest*. `exactfig verify` runs every
recipe again and compares the result with the file on disk, **pixel for pixel, frame by frame, byte for byte**, on any
machine. It is pure Python with no dependencies.

It is meant for engineers and researchers who need a figure that anyone can regenerate and check: a reconstruction from
scattered measurements, a shaded elevation model, the evolution of a cellular automaton, a wave-optics experiment, a
dynamical system. The figure, its data and the code that drew it are tied together by hashes; publishing one value
(`manifest_sha256`) pins the whole set.

| | | |
|---|---|---|
| ![Life](gallery/life-conway.gif) | ![double slit](gallery/wave-double-slit.gif) | ![Lorenz](gallery/lorenz.gif) |
| Conway's Life from a seeded soup, cells coloured by age | The wave equation through a double slit (leapfrog, absorbing border) | The Lorenz attractor, Runge–Kutta 4 |
| ![layered figure](gallery/figure-plate.png) | ![reconstruction](gallery/franke-linear.png) | ![phase portrait](gallery/domain-wegert.png) |
| A layered figure: exact Laplace solution, iso-lines, annotations | Franke's function from 256 scattered samples (exact Delaunay) | Phase portrait of a complex function with modulus lines |

## Contents

- [What is guaranteed](#what-is-guaranteed)
- [Quickstart](#quickstart)
- [Gallery](#gallery)
- [Using it for research](#using-it-for-research)
- [Recipes: seeds, palettes, parameters, editing](#recipes-seeds-palettes-parameters-editing)
- [Your own data](#your-own-data)
- [Animations and video](#animations-and-video)
- [Layers and editing](#layers-and-editing)
- [Lean](#lean)
- [Image conversion](#image-conversion)
- [Mathematics by area](#mathematics-by-area)
- [Verification](#verification)
- [Python API](#python-api)
- [Numerical reproducibility](#numerical-reproducibility)
- [Limits](#limits)
- [Architecture](#architecture)
- [References](#references)

## What is guaranteed

| Claim | How it is checked |
|---|---|
| The file is exactly what the recipe computes | `verify` re-runs the recipe and compares decoded pixels (every frame of an animation) or MIDI bytes |
| The input data is the data that was recorded | the recipe pins each input file by SHA-256; one changed byte fails `verify`, naming the file |
| The code is the code that was recorded | each entry stores a hash of the generator's source; a change is a warning, a failure with `--strict` |
| The colours are a declared palette | generators draw palette *indices*; `verify` checks every opaque pixel against the recorded palette |
| The same bits on every platform | transcendental functions come from `exactfig.fmath` (basic IEEE 754 arithmetic only); checked on x86-64 and ARM64 |
| The whole set is pinned | `manifest_sha256` covers every entry; sign or publish that one value |
| Recipes cannot smuggle a picture | closed parameter schemas: typed, ranged values, no pixel arrays; data enters only as a named, hashed file |

What it does not prove: who wrote the code or chose the recipe (sign the manifest digest for that), or that a model or a
dataset is right. It proves that *this output is what this code computes from these inputs*.

## Quickstart

Requires Python 3.10 or newer. Nothing to install.

```sh
python -m exactfig selftest                                # does this machine reproduce exactfig bit for bit? (seconds)
python -m exactfig list                                    # generators and their parameter schemas
python -m exactfig verify --manifest gallery/manifest.json --strict
python -m exactfig render examples/recipes/franke-linear.json --data-dir gallery --out-dir out
python -m unittest discover tests
```

`pip install -e .` also provides a `exactfig` command.

## Gallery

Every file below comes from a recipe in [`examples/recipes`](examples/recipes) and is recorded in
[`gallery/manifest.json`](gallery/manifest.json). The test suite verifies all of them.

### Data

| | | |
|---|---|---|
| ![plate](gallery/plate-temperature.png) | ![Franke linear](gallery/franke-linear.png) | ![Franke nearest](gallery/franke-nearest.png) |
| Steady temperature of a plate, the exact solution of Laplace's equation (`.npy`), iso-lines every 0.1 | Franke's function from 256 Halton samples (CSV), Delaunay piecewise-linear interpolation, samples marked | The same samples, nearest-sample reconstruction (Voronoi cells) |
| ![relief](gallery/dem-relief.png) | ![hillshade](gallery/dem-hillshade.png) | ![diffusion](gallery/dem-diffusion.gif) |
| Elevation model (16-bit PGM, 60 m cells): hypsometric tint with hill-shading and 200 m iso-lines | Hill-shading only (Horn's gradient, light from the north-west at 45°), Bayer dithering | The heat equation run on the same grid: its own diffusion, frame by frame |

### Dynamics

| | | |
|---|---|---|
| ![Conway](gallery/life-conway.gif) | ![B37/S2378](gallery/life-b37s2378.gif) | ![two sources](gallery/wave-two-sources.gif) |
| Conway's Life (B3/S23) from a seeded random soup, cells coloured by age | The rule B37/S2378 from the **same** soup (same seed): a controlled comparison of two rules | Two coherent point sources: interference and nodal lines |

### Layers and Lean

| | | |
|---|---|---|
| ![figure plate](gallery/figure-plate.png) | ![figure Franke](gallery/figure-franke.png) | ![Lean glider](gallery/lean-glider.gif) |
| `compose`: the plate's field, its iso-lines, and an annotation layer (text, arrow, frame) | `compose`: a paper background, the reconstruction on a diverging ramp with the samples crossed, and labels | `anim.frames`: the 33 frames a Lean program printed after its kernel checked that the glider returns in 32 generations |

### Classical mathematics

| | | |
|---|---|---|
| ![Wegert](gallery/domain-wegert.png) | ![roots](gallery/domain-roots.png) | ![logistic](gallery/logistic.png) |
| Enhanced phase portrait of (z²−1)(z−2−i)²/(z²+2+2i): zeros and poles are where all colours meet | z³ − 1: the three cube roots of unity | Bifurcation diagram of the logistic map, r from 2.8 to 4 |
| ![Ulam](gallery/ulam-primes.png) | ![cardioid](gallery/modmult-cardioid.png) | ![k34](gallery/modmult-k34.png) |
| The Ulam spiral of the primes up to 40 401 | Chords j → 2j mod 200: the cardioid | Chords j → 34j mod 300 |
| ![Fourier square](gallery/fourier-square.png) | ![epicycles](gallery/epicycles-heart.gif) | ![epicycles square](gallery/epicycles-square.gif) |
| Fourier partial sums of the square wave with 1, 3, 9 and 27 terms: the overshoot at the jump stays near 9 % (Gibbs) | A closed curve drawn by its 24 largest discrete Fourier coefficients, as rotating circles | A square needs more circles (40 here): its corners are where the series converges slowly |

### Mathematical structures

| | | |
|---|---|---|
| ![julia](gallery/julia.png) | ![fern](gallery/tree-fern.png) | ![terrain](gallery/terrain-0-0.png) ![terrain](gallery/terrain-1-0.png) |
| A Julia set by escape time, ordered dithering between ramp steps | A stochastic L-system (Lindenmayer) with Vogel-spiral leaf clusters | Domain-warped fBm in world coordinates: two adjacent tiles join without a seam |
| ![Voronoi](gallery/stone-slabs.png) | ![sky](gallery/sky-dusk.png) | ![sky mono](gallery/sky-mono.png) |
| Voronoi cells (F2 − F1 distance), periodic | Floyd–Steinberg error diffusion to a fixed palette, Poisson-disc sampling | The same gradient with 4 colours and Bayer 8×8 |

**Sonification.** `music.piece` reads a mathematical sequence (57 sources: Pisano periods, the golden angle, Thue–Morse,
Kepler's equation, zeros of the Riemann zeta function, sandpiles, the figure-eight three-body orbit…) as melody, harmonises it
by dynamic programming (Viterbi) and voices it with minimal voice leading. Examples:
[Pisano period of 7](gallery/music-pisano.mid), [Packard's snowflake](gallery/music-packard.mid),
[an L-system](gallery/music-lsystem.mid), [a Life glider](gallery/music-life-night.mid).

## Using it for research

Each example below is reproducible from this repository; the numbers quoted were measured with the commands shown.

**1. Compare two rules from the same initial condition.** A seed fixes the random soup, so changing only `rule` is a
controlled experiment ([Conway](examples/recipes/life-conway.json) and [B37/S2378](examples/recipes/life-b37s2378.json) in
the gallery differ in that one field):

```sh
python -m exactfig render examples/recipes/life-b37s2378.json --out-dir out
```

To sweep rules or densities, write one recipe per value and record them all; the manifest then documents the whole sweep:

```python
import json
for b in ("3", "36", "37", "38"):
    r = {"generator": "anim.life", "seed": "soup-1", "palette": "sci", "size": [96, 64], "scale": 3,
         "params": {"rule": f"B{b}/S23", "frames": 150}, "output": f"sweep/B{b}.gif"}
    json.dump(r, open(f"sweep-B{b}.json", "w"))
# python -m exactfig record sweep-*.json --manifest study/manifest.json
```

**2. Measure the accuracy of a reconstruction.** Piecewise-linear interpolation has error O(h²), with h ~ n^(−1/2) for n
well-spread samples. On Franke's function at the first n Halton points, rendered on 128 × 128 pixels inside the convex hull:

| samples | RMS error | pixels inside the hull |
|--:|--:|--:|
| 64 | 0.0246 | 84.3 % |
| 128 | 0.0151 | 91.1 % |
| 256 | 0.0084 | 94.8 % |

```python
from exactfig.data import io, scatter
p = io.read_points_csv("gallery/data/franke-halton-256.csv")
z = scatter.linear(p.xs[:64], p.ys[:64], p.vs[:64], 128, 128, (0.0, 1.0, 0.0, 1.0))   # NaN outside the hull
```

**3. Sensitivity to initial conditions.** Two Lorenz orbits started 10⁻⁹ apart (RK4, dt = 0.005) separate exponentially;
fitting log-distance against time (for t > 14, while the distance is between 10⁻⁸ and 10⁻²) gives a slope of 0.88, close to
the system's largest Lyapunov exponent (about 0.906); the distance reaches 1 at t ≈ 32.6. Because the arithmetic is
bit-reproducible, this divergence is the same on every machine:

```python
from exactfig.forge.motion import lorenz_path
a = lorenz_path(8000, 0.005, 10.0, 28.0, 8 / 3, (1.0, 1.0, 1.0))
b = lorenz_path(8000, 0.005, 10.0, 28.0, 8 / 3, (1.0 + 1e-9, 1.0, 1.0))
```

**4. Wave optics.** `anim.wave` solves u_tt = c²∇²u; change `separation` (slit spacing d) or `period` (wavelength
λ = speed × period cells) and the fringes move as sin θ = mλ/d. The double-slit field is exactly mirror-symmetric, bit for bit
(a test checks it), so any asymmetry you see in a variant comes from your geometry, not from rounding.

**5. Publish a figure with its data.** Put the data next to the manifest, write a recipe naming it, `record`, and publish the
figure, the data, the manifest and its `manifest_sha256`. A reader runs `verify`: it re-reads your data, checks its hash and
recomputes the figure.

## Recipes: seeds, palettes, parameters, editing

```json
{"generator": "data.scatter", "seed": "franke", "palette": "sci", "size": [256, 256], "scale": 1,
 "input": {"path": "data/franke-halton-256.csv"},
 "params": {"method": "linear", "contours": 9, "points": "dot"}, "output": "franke-linear.png"}
```

| Key | Meaning |
|---|---|
| `generator` | a registered generator (`exactfig list`) |
| `seed` | string or integer (≤ 64 characters). Hashed (SHA-256) into the generator's random streams, so the same seed gives the same result on any machine and in any process; a different seed, an independent draw. Generators with no randomness (data, wave, Lorenz, Julia, gem) ignore it |
| `palette` | a built-in name (`mf32`, `mono4`, `sci`; `exactfig palettes` lists their ramps) or your own: `{"name": "mine", "colors": ["#rrggbb", …], "ramps": {"seq": [0, 1, 2], …}}` (1–256 colours) |
| `size`, `scale` | native size in pixels, and an integer zoom by nearest neighbour (1–16) |
| `params` | checked against the generator's closed schema: unknown keys and out-of-range values are errors |
| `input` | data generators only: `{"path", "format", "sha256"}`; see [Your own data](#your-own-data) |
| `output` | file name, relative to the manifest folder; not part of the recipe's identity |

**Normal form.** When a recipe is recorded, every parameter is written with its value (defaults filled in) and the input's
hash is added. A later change of a default can therefore never change what an old manifest means.

**Editing.** Change the recipe and record it again: the manifest entry is replaced and `verify` checks the new one. A
generator whose code change moves any output pixel gets a new `version`; an asset recorded with an older version then fails
`verify` until it is re-recorded, so a silent change is impossible. The `sci` palette has a sequential ramp of strictly
increasing OKLab lightness (12 steps), a diverging ramp symmetric in lightness around a neutral grey (11), greys, ink, paper
and a marker colour.

## Your own data

| Format | Grid (`data.field`, `anim.diffuse`) | Points (`data.scatter`) |
|---|---|---|
| CSV, TSV, TXT | one row per line, top row first; `,` `;` tab or spaces; `#` comments; empty, `nan`, `NA` = missing | three columns x, y, value; optional header |
| Netpbm PGM | P2 or P5, 8 or 16 bits | — |
| NumPy `.npy` | format 1.0–3.0, 2-D, C or Fortran order; float16/32/64, integers, bool; either byte order | — |
| JSON | `{"values": [[…], …]}` or a list of rows; `null` = missing | `{"points": [[x, y, v], …]}` or `{"x": […], "y": […], "value": […]}` |

The input path is relative to the manifest folder and may not leave it; `record` fills in its SHA-256. Files are data only:
nothing is evaluated, object arrays are refused, sizes are capped (64 MiB, 4096 × 4096 cells, 200 000 points), and every
refusal says why. The readers agree with NumPy and Pillow on the same files (tested when those are installed).

`data.field` draws a grid by value, by hill-shading or by both (`mode`), with iso-lines (`contours` or `interval`), the colour
range from the data or from `range`, and optional dithering between palette steps. `data.scatter` reconstructs scattered
samples by Delaunay piecewise-linear interpolation (`linear`) or nearest sample (`nearest`); pixels outside the convex hull
have no value and stay transparent unless `nodata_ramp` is set. Full parameter lists: `python -m exactfig list`.

## Animations and video

| Generator | What it computes |
|---|---|
| `anim.life` | Life-like cellular automata, any rule `B…/S…`, torus or bounded board, random soup or a classic pattern (glider, R-pentomino, acorn, diehard, blinker); live cells coloured by age |
| `anim.wave` | the 2-D wave equation by leapfrog: double slit, single slit, a point source, two sources; reflecting walls, absorbing border; stable for Courant number ≤ 1/√2 (enforced) |
| `anim.lorenz` | the Lorenz system by RK4 with a warm-up past the initial transient, drawn as a fading trail |
| `anim.diffuse` | the heat equation on a data grid (FTCS, reflecting borders: the total is conserved), stable for α ≤ 1/4 (enforced) |

The output name picks the container: `.gif` (GIF89a) or `.png` (APNG). Both are written and read by exactfig itself, keep
the palette lock, and loop. The recorded content hash covers the size, the frame count and every frame's delay and pixels; it
does not depend on the container. GIF stores delays in hundredths of a second, so `delay` is a multiple of 10 ms.

For sharing, `python -m exactfig video RECIPE.json --out clip.mp4 --scale 4` encodes the frames as H.264 through
[FFmpeg](https://ffmpeg.org/) if it is installed. An MP4 is lossy and **not verifiable**; verify the GIF/APNG it was made
from (the command prints the frames' hash).

## Layers and editing

A `compose` recipe stacks layers on one canvas. Each layer is a recipe of any image generator, data ones included, without
palette, size or scale (it inherits them), and a `blend`: `over` (its opaque pixels cover what is below), `under` (it only
fills what is still transparent) or `mask` (what is below survives only where the layer is opaque):

```json
{"generator": "compose", "seed": "fig-plate", "palette": "sci", "size": [256, 256], "layers": [
  {"generator": "data.field", "input": {"path": "data/plate-129.npy"}, "params": {"interval": 0.1}},
  {"generator": "draw.annotate", "params": {"shapes": [
    {"type": "text", "points": [[6, 6]], "text": "U = 1 ON TOP", "r": 2},
    {"type": "arrow", "points": [[128, 200], [128, 120]], "r": 6, "ramp": "paper"}]}}],
 "output": "figure-plate.png"}
```

`draw.annotate` draws lines, polylines, polygons, rectangles, circles, markers, arrows, scale bars and text (a 3 × 5 bitmap
font defined in the code), in pixels or in unit coordinates of the canvas. At most 64 shapes of at most 64 points, so an
annotation cannot carry a picture. A composition's version and source hash cover every layer's generator.

To edit, change the recipe by hand or with `exactfig edit`, which checks the result against the schema before writing it:

```sh
python -m exactfig edit examples/recipes/figure-plate.json --set layers.0.params.interval=0.05 --set seed=v2
python -m exactfig record examples/recipes/figure-plate.json --manifest gallery/manifest.json
```

Recording an asset whose recipe or content changed keeps what it was in its entry's `history` (recipe and content hashes,
generator version, newest first), so the manifest documents its own edits; `verify` checks the current entry.

## Lean

[`lean/`](lean) holds plain Lean 4 (core only, no Mathlib), used two ways:

- **Proving properties of the algorithms exactfig uses.** `Line.lean` re-implements the Bresenham line of `pxmath.line`
  and proves, for every pair of endpoints in 0..4, that the line starts and ends at its endpoints, is 8-connected and has
  max(|Δx|, |Δy|) + 1 points. Its output for all 2401 lines with endpoints in −3..3 is compared, point by point, with
  what exactfig draws.
- **Computing data whose properties are proved, then drawing it.** `Life.lean` proves that a glider moves one cell
  diagonally in four generations and returns after 32 on an 8 × 8 torus, and that the blinker has period exactly 2; the
  frames it prints are animated by `anim.frames` and pinned by SHA-256. exactfig's own Life reproduces them frame by
  frame.

The theorems are checked by Lean's kernel (`decide +kernel`), exhaustively over the stated cases. `tests/test_lean.py`
needs no Lean: it compares the committed outputs with exactfig's code and refuses `sorry`, `axiom` or `native_decide`.
Details: [lean/README.md](lean/README.md).

The same pattern works for any computation you trust more in Lean than in Python: write it in Lean, prove what matters,
print JSON, and draw it with `anim.frames` (a sequence of grids) or `data.field` (one grid).

## Mathematics by area

The areas of [awesome-math](https://github.com/rossant/awesome-math), and what this repository already computes and draws
in each. Every entry is a generator or a recipe in the gallery.

| Area | In exactfig | Gallery |
|---|---|---|
| Complex analysis | enhanced phase portraits (Wegert): zeros, poles and their orders, essential singularities (`math.domain`) | [Wegert](gallery/domain-wegert.png), [z³ − 1](gallery/domain-roots.png) |
| Dynamical systems and chaos | logistic map bifurcations (`math.logistic`); Lorenz attractor by RK4 (`anim.lorenz`); sensitivity to initial conditions | [logistic](gallery/logistic.png), [Lorenz](gallery/lorenz.gif) |
| Number theory | Ulam spiral of primes or residues (`math.ulam`); modular multiplication circles (`math.modmult`); Pisano periods, Thue–Morse, zeta zeros as sound (`music.piece`) | [Ulam](gallery/ulam-primes.png), [cardioid](gallery/modmult-cardioid.png) |
| Partial differential equations | Laplace (exact plate solution), wave equation by leapfrog (`anim.wave`), heat equation on data (`anim.diffuse`) | [plate](gallery/plate-temperature.png), [double slit](gallery/wave-double-slit.gif), [diffusion](gallery/dem-diffusion.gif) |
| Numerical analysis | portable libm (`fmath`, ≤ 1 ulp), exact Delaunay predicates, O(h²) interpolation, RK4 of order 4, CFL stability enforced | [Franke](gallery/franke-linear.png) |
| Computational geometry | Delaunay triangulation (Lawson flips), Voronoi cells, signed distance fields, Bézier curves, Bresenham | [Voronoi](gallery/stone-slabs.png), [nearest](gallery/franke-nearest.png) |
| Combinatorics and discrete mathematics | Life-like cellular automata with any B/S rule (`anim.life`), L-systems; sandpiles as sound | [Life](gallery/life-conway.gif), [B37/S2378](gallery/life-b37s2378.gif), [fern](gallery/tree-fern.png) |
| Probability and stochastic processes | quasi-random Halton samples, Poisson-disc sampling, seeded random soups, fractional Brownian surfaces (fBm) | [terrain](gallery/terrain-0-0.png) |
| Fourier analysis | partial sums and the Gibbs phenomenon (`math.fourier`); the discrete Fourier transform of a closed curve drawn as epicycles (`anim.epicycles`) | [Gibbs](gallery/fourier-square.png), [epicycles](gallery/epicycles-heart.gif) |
| Signal processing and information | ordered (Bayer) and error-diffusion dithering, palette quantisation, LZW (GIF), sonification | [sky](gallery/sky-dusk.png), [mono](gallery/sky-mono.png) |
| Image processing | area resampling in linear light, median-cut and k-means palettes, Sobel edges (`data.image`) | [conversion](gallery/convert-kmeans16-edges.png) |
| Fractals | Julia sets by escape time | [Julia](gallery/julia.png) |
| Geography and surfaces | hill-shading (Horn), hypsometric tint, iso-lines (marching squares) | [relief](gallery/dem-relief.png), [hillshade](gallery/dem-hillshade.png) |
| Colour science | OKLab palettes: sequential ramp of increasing lightness, diverging ramp symmetric in lightness, cyclic ramp at equal lightness | every figure |
| Formal mathematics | Lean 4 proofs of the line algorithm and of automaton facts, their outputs drawn and cross-checked | [Lean glider](gallery/lean-glider.gif) |

**Obvious next steps, not implemented yet.** Each would be a pure generator with a test against a known fact: the
Mandelbrot set and zoom animations (fractals); percolation clusters and
their threshold (probability); a Galton board converging to the binomial law (statistics); Chladni figures and
eigenmodes of a membrane (PDE, linear algebra); Cayley graphs of small groups (group theory); minimal spanning trees and
shortest paths (graph theory); geodesics on a sphere or a torus (differential geometry).

## Image conversion

`data.image` turns a true-colour picture (PNG of any 8-bit colour type, or a Netpbm PPM) into palette pixels. The picture
is an input like any data file: named in the recipe, pinned by SHA-256, re-read by `verify`.

1. **Resampling** to the target size: `area` takes the exact area-weighted mean of the source pixels each target pixel
   covers, **in linear light** (averaging sRGB values directly darkens every edge between two colours: half black, half
   white must give sRGB 188, not 128); `nearest` takes the source pixel under each target centre.
2. **Quantisation** to the palette, nearest colour in OKLab: directly, after a Bayer 8 × 8 offset (`spread`), or with
   Floyd–Steinberg error diffusion. `ramp` restricts the colours a pixel may take.
3. **Optional outline**: the Sobel gradient of OKLab lightness above `edge_threshold`, drawn in `edge_ramp`.

A palette can be derived from the picture itself, by median cut (Heckbert) or k-means in OKLab started from median cut
(deterministic: the same picture always gives the same palette):

```sh
python -m exactfig palette gallery/data/testcard-480x320.png --k 16 --method kmeans --out testcard-k16.json
```

The output is a palette object (colours sorted dark to light, ramps `all`, `ink`, `paper`) to paste into a recipe's
`palette`. The gallery's source picture is itself made by code (`examples/data/make_data.py`): an OKLCh colour wheel, four
ramps and two anti-aliased shapes.

| | | | |
|---|---|---|---|
| ![source](gallery/data/testcard-480x320.png) | ![sci](gallery/convert-sci-floyd.png) | ![mono4](gallery/convert-mono4-bayer.png) | ![k16](gallery/convert-kmeans16-edges.png) |
| The source, 480 × 320 true colour | 120 × 80, palette `sci`, Floyd–Steinberg | 120 × 80, 4 colours (`mono4`), Bayer 8 × 8 | 120 × 80, 16 colours by k-means, Sobel outline |

## Verification

```sh
python -m exactfig verify --manifest gallery/manifest.json            # warnings for changed source or re-encoded files
python -m exactfig verify --manifest gallery/manifest.json --strict   # …which then fail
python -m exactfig verify --json                                       # a machine-readable report
```

For each entry, in order: the recipe hash and normal form, the generator and its version, the source hash, every input
file's hash, the re-run's content hash, the file on disk (decoded pixels for PNG, every frame for GIF/APNG, bytes for MIDI),
the palette lock, the file bytes (informative unless `--strict`), and finally `manifest_sha256`. A failure says what
differs: how many pixels and the first one, the first differing frame, the first differing byte, or which input changed.
Exit code 0 when everything passes. Specification: [docs/MANIFEST.md](docs/MANIFEST.md); JSON Schema:
[exactfig/provenance/manifest.schema.json](exactfig/provenance/manifest.schema.json).

## Python API

```python
from exactfig.render import render                      # recipe dict → Rendered (bytes, content hash, size, frames)
from exactfig.data import io, field, scatter              # readers, sampling, hill-shading, contours, Delaunay
from exactfig import fmath                                # portable sin, cos, atan2, exp, log, pow, cbrt, hypot
from exactfig.forge.motion import lorenz_path, life_step  # the simulations behind the animations

out = render({"generator": "anim.life", "seed": 7, "palette": "sci", "size": [64, 48],
              "params": {"rule": "B36/S23", "frames": 60}, "output": "highlife.gif"})
open("highlife.gif", "wb").write(out.data)
tris = scatter.delaunay([0.0, 1.0, 0.0, 1.0], [0.0, 0.0, 1.0, 1.0])     # counter-clockwise index triples
```

## Numerical reproducibility

The platform's `sin`, `pow` and friends may differ in the last bit between C libraries, and C code such as `math.hypot` may be
compiled with fused multiply-add; either can move a pixel that sits on a threshold. Generators therefore call
`exactfig.fmath`, which builds `sin`, `cos`, `atan`, `atan2`, `exp`, `log`, `log2`, `pow`, `cbrt`, `hypot` and distances from
`+ − × ÷` and `sqrt` only, all correctly rounded by IEEE 754, after fdlibm. Accuracy against the platform library: within
1 ulp for sin, cos, atan, atan2, exp, log and log2; 2 ulp for cbrt; pow relative error below 2·10⁻¹⁴. Arguments beyond the
exact range reduction are refused, never silently wrong. The tests pin fmath results as bit patterns and fail if package code
calls the platform's transcendental functions or `**` on floats. The Delaunay predicates are exact (integer arithmetic), and
numbers in input files are parsed by Python's correctly rounded `float`. The gallery reproduces exactly on x86-64 and ARM64,
on two operating systems.

## Limits

- **Speed.** Pure Python: a 256 × 256 field renders in one to two seconds; the gallery animations take seconds to a minute.
  Sizes are capped (2048 px per side for data figures, 1000 frames and 64 million pixels per animation).
- **PNG and GIF compression** may differ between implementations; `verify` compares decoded pixels and treats file bytes as
  informative unless `--strict`.
- **MP4** is for sharing only (lossy).
- **Cherry-picking is allowed.** Choosing the nicest seed is curation, and the seed is in the recipe.

## Architecture

```
exactfig/
  fmath.py       portable transcendental functions (fdlibm algorithms, basic IEEE 754 operations only)
  data/          io (CSV, PGM, NPY, JSON readers), field (sampling, hill-shading, marching squares), scatter (exact Delaunay)
  pixel/         pxmath (dithering, noise, Worley, automata, fractals, Bézier, Bresenham, SDFs, Poisson disc), palettes
                 (OKLab), palette-locked quantisation, Canvas of palette indices, PNG and GIF/APNG writers and readers
  forge/         generators: datavis (data.*), motion (anim.*), mathviz (math.*), annotate (draw.annotate), tiles, flora,
                 skies, icons, sprites
  music/         sequences, harmony (Viterbi), voice leading, composer, Standard MIDI File writer
  provenance/    record, verify, manifest JSON Schema
  registry.py    the generators, their versions and closed parameter schemas
  render.py      recipe → normal form → output
lean/            Lean 4 proofs and programs whose outputs exactfig draws and cross-checks
examples/        recipes and the code that makes the example datasets
gallery/         the recorded outputs, their data and manifest.json
```

The core (everything that computes a figure) is pure and the shell (files, command line, manifest) is thin; a test
enforces it. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the layers, the invariants and how to add a generator.

## References

- B. E. Bayer, *An optimum method for two-level rendition of continuous-tone pictures*, IEEE ICC, 1973.
- R. W. Floyd, L. Steinberg, *An adaptive algorithm for spatial greyscale*, Proc. SID 17(2), 1976.
- B. K. P. Horn, *Hill shading and the reflectance map*, Proc. IEEE 69(1), 1981.
- C. L. Lawson, *Software for C¹ surface interpolation*, in Mathematical Software III, 1977.
- R. Franke, *A critical comparison of some methods for interpolation of scattered data*, NPS-53-79-003, 1979.
- J. H. Halton, *On the efficiency of certain quasi-random sequences of points*, Numer. Math. 2, 1960.
- J. R. Shewchuk, *Adaptive precision floating-point arithmetic and fast robust geometric predicates*, DCG 18, 1997.
- E. N. Lorenz, *Deterministic nonperiodic flow*, J. Atmos. Sci. 20, 1963.
- M. Gardner, *The fantastic combinations of John Conway's new solitaire game "life"*, Sci. Am. 223, 1970.
- R. Courant, K. Friedrichs, H. Lewy, *Über die partiellen Differenzengleichungen der mathematischen Physik*, Math. Ann. 100, 1928.
- S. Worley, *A cellular texture basis function*, SIGGRAPH 1996.
- R. Bridson, *Fast Poisson disk sampling in arbitrary dimensions*, SIGGRAPH sketches, 2007.
- A. Lindenmayer, *Mathematical models for cellular interactions in development*, J. Theor. Biol. 18, 1968.
- H. Vogel, *A better way to construct the sunflower head*, Math. Biosci. 44, 1979.
- B. Ottosson, *A perceptual color space for image processing* (OKLab), 2020.
- E. Wegert, *Visual Complex Functions: An Introduction with Phase Portraits*, Birkhäuser, 2012.
- R. M. May, *Simple mathematical models with very complicated dynamics*, Nature 261, 1976.
- M. L. Stein, S. M. Ulam, M. B. Wells, *A visual display of some properties of the distribution of primes*, Amer. Math.
  Monthly 71, 1964.
- G. Marsaglia, *Xorshift RNGs*, J. Stat. Softw. 8(14), 2003.
- L. de Moura, S. Ullrich, *The Lean 4 theorem prover and programming language*, CADE 28, 2021.
- Sun Microsystems, *fdlibm*, 1993. CompuServe, *Graphics Interchange Format 89a*, 1990. *APNG specification*, Mozilla.
  *Netpbm PGM format*. *NumPy NEP 1: a simple file format for NumPy arrays*.

## Citing

[CITATION.cff](CITATION.cff) gives the citation; GitHub shows it as "Cite this repository". When a publication uses an
exactfig figure, publish the figure's manifest (or its `manifest_sha256`) with it: that is what lets a reader check it.
Changes by version: [CHANGELOG.md](CHANGELOG.md).

## Contributing, security, licence

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). Licence: to be decided by the owner before publishing.
