# Changelog

## 0.14.1 (2026-11-23)

- **Security: animations from outside are read defensively.** Found by fuzzing the decoders (random mutations of the
  gallery's files). The GIF reader allocated the canvas its header declared before checking anything (65535 × 65535
  pixels: 17 GB), and neither the GIF nor the APNG reader checked that a frame lies inside the canvas, that a colour
  table exists and covers the indices used, or that the data is not truncated; the APNG reader inflated frame data
  without a limit (a "zip bomb" of a few kilobytes could inflate to gigabytes). `verify` reads files it did not write,
  so a crafted GIF or APNG could exhaust the memory of the machine checking it. Now the readers refuse, with a
  ValueError and before allocating, a canvas or a total (canvas × frames) above the renderer's own cap of 64 million
  pixels, more than 1000 frames, a frame outside the canvas, a missing or short colour table, data that inflates past
  its frame and any truncated structure; and `verify` decodes PNG and animations with the size the manifest recorded as
  the limit. No output changes; generator code hashes do, so the gallery is recorded again. Tests: a 65535 × 65535 GIF
  refused in under a second, a frame outside the canvas, a GIF without colour table, every truncation of a GIF and an
  APNG, an APNG zip bomb and a huge APNG canvas, the caller's limit, and the decoder's cap equal to the renderer's.

## 0.14.0 (2026-11-22)

- **`data.bounds`: tables of exact values and bounds, checked.** A new data format (`bounds`: labelled rows of cells,
  each an integer, a bound `>n`, `>=n`, `<n`, `<=n`, a range `a..b`, `?` or `-`) and a generator that refuses to draw
  a table whose ranges are empty, whose numbers of exact cells and bounds differ from the recipe's, whose values
  decrease where `monotone` says they cannot, that is not symmetric when `symmetric` says it is, or whose cells differ
  from the ones the recipe quotes (`claims`). Cells are coloured by kind (Okabe–Ito) and carry their value in the 3×5
  font; a legend names the kinds present; the alternative text says what was checked. Gallery: the known van der Waerden
  numbers W(r, k), 7 exact and 13 lower bounds, with their sources in the data file. Tested: the cell grammar by
  membership, W(2, 3) = 9 by brute force, a symmetric table of small Ramsey numbers and the same table spoiled, every
  refusal, and five new misuse cases. The gallery SVG's embedded code hash changes with the data reader; no other output
  changes.

## 0.13.0 (2026-11-22)

- **SVG output, with the provenance inside.** An image recipe whose `output` ends in `.svg` is written as SVG: the same
  pixels as the PNG (one `<path>` of merged rectangles per colour, `crispEdges`, the scale in the `viewBox`), so it
  decodes to exactly the PNG's RGBA and `content_sha256`; the exact alternative text as `<title>` and `<desc>`; and in
  `<metadata>` (`exactfig.svg/1`) the normal-form recipe and its SHA-256, the generator identity, the exactfig version,
  every input's SHA-256 and the content hash. `verify` decodes it with a strict reader that accepts only what exactfig
  writes and refuses an SVG whose embedded provenance is not the manifest's; `exactfig cvd` and `exactfig crate`
  read SVG too (`image/svg+xml`). Gallery: `mod3-circuit.svg`. Tested: the same pixels as the PNG for five gallery
  recipes (data, fractal, transparency, scale > 1), well-formed XML, record and `verify --strict`, and refusal of a
  changed colour, a changed recipe hash, an added element, overlapping and out-of-bounds rectangles.

## 0.12.0 (2026-11-22)

- **Ramp `cat`** in the `sci` palette: the seven categorical colours of Okabe and Ito (2008), without black, added at
  the end so that no earlier index changes; every pair stays at least 0.076 apart (OKLab) for normal vision,
  protanopia, deuteranopia and tritanopia (`exactfig cvd`). For colours that carry different meanings. The ramp `all`
  keeps the 46 colours it had, so image conversions (`data.image`) give the same pixels as before; the other images
  change only their PNG palette table (53 entries), not their pixels.
- **`data.circuit` version 2**: gates are coloured by the operations the circuit uses (in the order of their truth
  tables, evenly round the ramp), so two operations never share a colour while the ramp has enough; the 0 cells of the
  truth row, the wires and the inputs are drawn in greys that stay clear of the background and of `cat`.
- Gallery: the van der Waerden witness, the instance masks and both circuits now use `cat`; none of their colour pairs
  falls below 0.06 for any vision, and a test keeps it so.
- Correction to 0.11.0's notes: the close pair in the circuit figures was the truth row's 0 cells against the
  background, not two gate colours.

## 0.11.0 (2026-11-22)

- **`exactfig cvd`**: a colour-blindness audit of every recorded image. It simulates protanopia, deuteranopia and
  tritanopia (Machado, Oliveira and Fernandes 2009, severity 1, linear sRGB; `pixel/cvd.py`, pure) on the colours each
  image actually uses (`--share`, default 0.5 % of the opaque pixels) and reports, per vision, the closest pair in OKLab
  and the pairs below `--min` (default 0.06); `--json` for a machine report. It informs and changes nothing. Tested
  against facts that do not depend on exactfig: every row of the three matrices sums to 1 (greys unchanged), red and
  green come together for protanopes and deuteranopes but not for tritanopes, blue and yellow stay apart.
  On this gallery it finds the van der Waerden witness (two colours at 0.017 for deuteranopes), the instance masks and
  the circuits' gate colours worth revisiting.

## 0.10.0 (2026-11-22)

- **Alternative text, exact.** Every recorded file now carries an `alt` text in the manifest (schema: `alt`, at most
  1000 characters), written by `forge/describe.py` after the generator has drawn, and so after its data passed their
  checks: the checked generators state the checked numbers (a circuit's gates, inputs, depth, function and how many
  inputs give 1; a refutation's claim, the size it proves and its clauses; TP, FP, FN and the exact PQ; the patterns,
  cells and rule of a catalogue; the prime and lines of a Pratt certificate; …), the others their own summary, name and
  size. `exactfig alt` lists the texts (`--json`); `verify` warns, and fails with `--strict`, when the text differs
  from the recorded one; `exactfig crate` uses it as each file's description. No pixel changes. Tested against
  independent facts (2^127 − 1 and its 19 lines, 1 on C(5,1) + C(5,4) = 10 of 32 inputs, clause counts read from the
  proof files, the README's exact PQ).

## 0.9.0 (2026-11-22)

- **`exactfig crate`**: writes `ro-crate-metadata.json` beside a manifest, so a gallery folder becomes an RO-Crate 1.3
  in the Process Run Crate 0.6 profile (provenance aligned with W3C PROV), the packaging WorkflowHub reads and Zenodo
  can archive: each file and input with its size and SHA-256, each recorded file as a `CreateAction` with its generator
  (name, version, source hash) as instrument, its inputs and recipe parameters as object, the file as result and
  `--author` (a name or an ORCID URL) as agent. Every file is read first and must match the manifest, so a missing or
  changed file is refused. Deterministic for given files, date, licence, author and name; warns without `--license`.
  Tested against every applicable MUST rule of both specifications and the SHOULD rules it can meet; not given: run
  times, which the manifest does not record.
- Documentation: the architecture trees, `docs/MANIFEST.md` (all 14 input formats, exit codes), CONTRIBUTING (where the
  gallery's data come from), SECURITY.md and the Spanish README (gallery of checked figures, anchors) brought in line
  with the code.

## 0.8.0 (2026-11-22)

- **`data.circuit_refutation`**: the other half of a circuit size. An LRAT proof that no circuit of s two-input gates
  computes a function (so its size is at least s + 1) is checked by reverse unit propagation against a formula exactfig
  writes itself from the claim (`function`, `inputs`, `gates`): a choice of two earlier nodes, an operation of the 16
  and a value on every input row for each gate, the last gate equal to the function. A smaller circuit pads to s gates
  with gates that copy an argument, so the formula is satisfiable exactly when the size is at most s. Drawn as the
  gates against proof order. Gallery: MOD_3 with residue 1 on 3 inputs, a 4-gate circuit and the CaDiCaL proof that 3
  gates do not suffice (677 clauses), whose SHA-256 the circuit's recipe names: the size is exactly 4. Tested against
  a DPLL solver and a brute-force enumeration of circuits on every function of 2 inputs and several of 3: the formula
  is satisfiable exactly when a circuit of that size exists, and a solution reads back as a working circuit.

## 0.7.0 (2026-11-22)

- **`data.circuit`**: a Boolean circuit of two-input gates (a straight-line program), drawn by depth with its value on
  every input along the bottom, only after it is evaluated on all 2^n inputs (bit-parallel, exact) and found equal to
  the stated function: `mod M R`, `threshold K`, `parity` or a hexadecimal truth table. `inputs` and `gates` pin the
  size; `strict` (default) refuses gates that do not lead to the output, so `gates` is the size of the circuit; the
  recipe can name a proof that no smaller circuit exists by its SHA-256 (`proof_sha256`, recorded, not checked). New
  input format `circuit`. Gallery: a 9-gate circuit for MOD_3 with residue 1 on 5 inputs, the smallest size (Knuth,
  TAOCP 7.1.2). Tested on all 16 two-input functions, against a direct count of ones for every target up to 6 inputs,
  and with textbook circuits (the XOR chain is parity, four gates make the majority of 3).

## 0.6.0 (2026-11-16)

- **`data.pratt`**: a Pratt certificate of primality drawn as a tree, only after every line is checked in exact integer
  arithmetic: p − 1 is the product of the stated factors, the witness g has order exactly p − 1 (g^(p−1) ≡ 1 and
  g^((p−1)/q) ≢ 1 for each q), each factor above 2 has its own line, and no line is unused. A composite number has no
  certificate, so none can be drawn (tested for every witness of every composite below 700, Carmichael 561 included).
  New input format `pratt`. Gallery: the 19-line certificate of 2^127 − 1, the prime Lucas proved by hand in 1876.
- **`data.refutation`**: the "no" half of a SAT answer. An LRAT proof that 1..n cannot be coloured (van der Waerden,
  Schur, weak Schur) is checked by reverse unit propagation against a formula exactfig writes itself from the recipe,
  so a proof of another claim does not check; RAT steps are refused; it must reach the empty clause. Drawn as the
  numbers against proof order. New input format `lrat` (textual). Gallery: the proof that 1..14 has no 3-colouring
  without x + y in a colour, beside the witness for 13, whose recipe now names the proof by its SHA-256: S(3) = 13.
  Tested against W(2;3) = 9 and W(2;4) = 35 (CaDiCaL proofs, also accepted by cake_lpr) and against `data.coloring`'s
  check on every colouring of small cases.
- `data.coloring`: `proof_sha256` now points to `data.refutation` for checking the proof.

## 0.5.0 (2026-11-15)

- **`data.sequence`**: OEIS b-files as bars (log or linear), the new terms highlighted and checked against the stated
  `terms`, `first`, `last` and `count`; consecutive indices enforced; terms of up to 4000 digits.
- **`data.triangle`**: right triangles with rational sides (congruent numbers), checked in exact fractions: a² + b² = c²,
  a·b/2 = n, squarefree n, no repeats. Gallery: 5, 6, 7 and the 48-digit triangle of 157.
- **`math.sandpile`**: the identity of the sandpile group (Creutz's formula), checked e ⊕ e = e; a stated group order is
  checked against the number of spanning trees (exact Bareiss determinant), n ≤ 14.
- **Ships in `data.catalog`** (`check: "ship"`, `shift`): Conway's light, middle and heavy spaceships in the gallery.
- Readers refuse numbers of more than 4000 digits with a message (Python 3.11+ refuses to convert more than 4300).

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

- **Reproducibility.** Portable transcendental functions (`fmath`, after fdlibm, ≤ 1 ulp for sin…log2, 2 ulp for cbrt) so a recipe gives the same bits
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
