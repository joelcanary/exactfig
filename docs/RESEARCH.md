# Research: what already exists, and the gap

*Investigación: qué existe ya y qué hueco cubre este repositorio (resumen en español al final).*

Survey made in October 2026 by reading project pages, specifications and papers. One line per project.

## 1. Procedural pixel art

| Project | What it does | What it does not do |
|---|---|---|
| [pixel-sprite-generator](https://github.com/zfedoran/pixel-sprite-generator) (JS) and ports to [Haxe](https://lib.haxe.org/p/pixel-sprite-generator/) and [Rust](https://docs.rs/sprite) | Random mirrored masks → small sprites | No palette lock, no record of how a sprite was made |
| [simple-pixel-sprite-generator](https://github.com/maclovin/simple-pixel-sprite-generator) | Pixelates an existing image | Starts from someone's image: the opposite of generating |
| [hitherdither](https://github.com/missionfloyd/hitherdither) | Bayer, Yliluoma and error diffusion to an arbitrary palette (Pillow) | Filters an input image; no generators, no provenance |
| [dither-go](https://pypi.org/project/dither-go) | Fast, colour-correct dithering with many kernels | Same: a filter, not a generator |
| [Lospec palette list](https://lospec.com/palette-list) | The reference catalogue of limited palettes | Palettes only |
| [FastNoiseLite](https://github.com/Auburn/FastNoiseLite), [opensimplex](https://pypi.org/project/opensimplex/) | Noise functions (Perlin, Simplex, cellular, fractal) | Floats, not palette-locked pixels; nothing about output identity |
| [WaveFunctionCollapse](https://github.com/mxgmn/WaveFunctionCollapse) | Tile/bitmap synthesis from an example | Needs an input bitmap: provenance depends on that input |
| [Pyxel](https://github.com/kitao/pyxel) | Retro engine with a fixed palette and editors | Hand editing, no generators |
| [bramp/assets](https://github.com/bramp/assets) | Lockfile that tells CI whether generated assets are stale | Checks freshness by input hashes, does not re-run and compare outputs |

## 2. Algorithmic and mathematical music

| Project | What it does | What it does not do |
|---|---|---|
| [music21](https://github.com/cuthbertLab/music21) | Musicology toolkit: analysis, notation, MIDI I/O | Not a generator; no provenance |
| [isobar](https://github.com/ideoforms/isobar) | Pattern library for algorithmic composition, MIDI out | You write the maths; no record/verify |
| [athenaCL](https://github.com/ariza/athenaCL) | Classic algorithmic composition: Markov, cellular automata, L-systems | No harmonisation by optimisation, no output identity |
| [aldakit](https://pypi.org/project/aldakit/) | Alda language + Markov, L-system, CA, Euclidean rhythms | Same gap |
| [Wolfram Tones](https://tones.wolfram.com/) | Cellular-automaton music in the browser (historic) | Closed; no recipes to re-run |
| [Magenta](https://github.com/magenta/magenta) | Machine-learning music | The opposite of this project |
| [mido](https://github.com/mido/mido) | MIDI read/write | A file library |

None of them ships a catalogue of named mathematical sources (Pisano periods, Packard's snowflake, Thue–Morse, Kepler's
equation, the Riemann zeros, sandpiles, the three-body figure-eight…) feeding a composer that harmonises by dynamic programming
with optimal voice leading, with byte-identical regeneration.

## 3. Provenance, reproducibility, "proof of no AI"

| Project / idea | What it proves | Why it is not enough here |
|---|---|---|
| [C2PA / Content Credentials](https://c2pa.org/specifications/specifications/2.0/specs/C2PA_Specification.html) | A signed claim of WHO (or which tool) made or edited a file, and that the claim was not tampered with | It is a *claim*; it does not let anyone re-derive the file. Credentials are stripped by re-encoding, and their absence proves nothing ([critique, arXiv 2026](https://arxiv.org/pdf/2604.24890)) |
| [Reproducible Builds](https://reproducible-builds.org/), [diffoscope](https://diffoscope.org/) | A binary is exactly what its source builds to | Software packages, not art; no notion of palette or pixels |
| [in-toto](https://in-toto.io/), [SLSA](https://slsa.dev/) | Signed attestations of supply-chain steps | Again claims about steps, not re-execution of the artefact itself |
| [Art Blocks on-chain generator](https://docs.artblocks.io/protocol/on-chain-generator.md) | Script on a blockchain + token hash → the page that draws the piece | The closest idea. Tied to a chain, a browser and JavaScript; the output is a live canvas, not a file with a hash; no pixel-exact verifier, no palette lock |
| [Not By AI](https://notbyai.fyi/), "AI-free" and "human-made" badges | Self-declaration (sometimes a process review) | Nothing anyone can check from the file |
| Seed/hash "reproducibility" in image-model UIs | That a model run can be repeated | Proves the opposite of what we want |

## 4. The gap

The hypothesis was: *every asset ships with a manifest (generator, version, parameters, seed, palette, hash) and a `verify`
command re-runs the generator and compares pixel for pixel / byte for byte.*

**Verdict: confirmed, with one correction.** We found no tool that does this for files. The pieces exist apart: deterministic
art scripts (Art Blocks), bit-exact rebuild verification (Reproducible Builds), signed provenance claims (C2PA), pixel art
generators and dithering libraries. Nobody combines them into an **offline, file-level, re-executable proof** for images,
animations and music files.

The correction: a hash alone is not a "cryptographic proof of no AI". What re-execution proves is narrower and stronger:

1. **This file is exactly what this published code computes from this small recipe.** Anyone can check it, offline, with no
   trust in the author: `exactfig verify`.
2. **The recipe cannot carry a picture.** Every generator has a closed parameter schema (typed, ranged, no bitmaps, no free
   arrays), so the information in the output comes from the algorithm, not from smuggled data. This is the part that makes
   "no AI model was involved in *producing* the file" checkable, and we have not seen it elsewhere.
3. **The palette is locked**, and verify checks every pixel of the file against it.

It does **not** prove who wrote the code or the recipe (sign `manifest_sha256` for that: a signed git tag or `ssh-keygen -Y
sign` is enough), nor that the code itself was written without assistance. It proves how the asset was made, which is
exactly what C2PA does not.

**Differentiator, in one line:** *re-execution as evidence*: assets whose only source is a published algorithm and a
few-number recipe, checkable by anyone, pixel for pixel and byte for byte, plus palette-locked math primitives and math-sourced
music that live under the same rule.

Floating point (also in the README): the platform library's `sin`, `pow`… may differ in the last bit between C libraries, so
generators use `exactfig.fmath`, built from correctly rounded IEEE 754 operations only (after fdlibm). The gallery reproduces
exactly on x86-64 and ARM64 and on two operating systems; integers (hashes, RNG, Bayer, Bresenham, automata, MIDI) are exact
everywhere.

## Reproducible scientific figures

| Practice or tool | What it does | What it does not do |
|---|---|---|
| Notebooks and scripts in a repository, a DOI for the code (e.g. Zenodo) | keep the code that made a figure | do not check that
  the published file is what that code produces, nor pin the data byte for byte |
| Image-comparison tests (e.g. pytest-mpl for Matplotlib) | compare a rendered figure with a baseline, within a tolerance | a
  tolerance, not identity; the platform's maths and rendering stack may legitimately move pixels |
| Data versioning by content hash (e.g. DVC) | pin datasets by hash | do not tie a figure to the data and the code that drew it |
| Replication journals (e.g. ReScience C) | publish independent replications of computational results | a social process, not a
  machine check of a file |

exactfig's angle is narrower: a figure, an animation or a MIDI file is checked **exactly** (decoded pixels, every frame,
every byte) against a re-run of the recorded recipe, with the input data pinned by SHA-256, and the arithmetic made
portable (`exactfig.fmath`) so that the check holds on any platform rather than on the author's machine only.

---

### Resumen en español

Existen por separado generadores de sprites, librerías de tramado y de ruido, compositores algorítmicos, credenciales C2PA (que
dicen **quién**, no **cómo**), compilaciones reproducibles (para software) y el generador en cadena de Art Blocks (lo más
parecido, pero atado a una cadena y a un navegador). En figuras científicas, los cuadernos y los DOI guardan el código, las
pruebas de comparación de imágenes admiten una tolerancia y el versionado de datos fija los datos por hash, pero nada ata la
figura publicada, sus datos y su código con una comprobación exacta. **No** existe una herramienta que, para imágenes,
animaciones y MIDI,
vuelva a ejecutar el generador publicado y compare píxel a píxel / byte a byte, con esquemas de parámetros cerrados (la receta
no puede colar una imagen) y la paleta bloqueada. Eso es lo que aporta este repositorio: **la reejecución como prueba**. No
prueba quién escribió el código: para eso se firma el `manifest_sha256`.
