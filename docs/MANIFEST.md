# The provenance manifest, format 1

*El manifiesto de procedencia, formato 1 (resumen en español al final).*

JSON Schema: [`exactfig/provenance/manifest.schema.json`](../exactfig/provenance/manifest.schema.json).

## File

```json
{
 "format": "exactfig.manifest/1",
 "assets": { "<path>": { …entry… }, … },
 "manifest_sha256": "<sha256 of canonical(assets)>"
}
```

- `<path>` is relative to the folder of the manifest, with `/`, and may not leave it.
- `manifest_sha256` pins the whole set. Publish that single value (signed tag, release notes, a signature with
  `ssh-keygen -Y sign`) and every asset is pinned with it.

## Entry

| Field | Meaning |
|---|---|
| `kind` | `image`, `animation` or `midi` |
| `generator.name`, `generator.version` | the registered generator; the version is bumped whenever a change moves any output pixel or byte.
  For `compose`, the version lists every layer's generator: `1+data.field@1+draw.annotate@1` |
| `generator.code_sha256` | SHA-256 over the source files the generator depends on (sorted relative paths, LF line endings);
  for `compose`, the SHA-256 of its own hash and every layer generator's hash, in name order |
| `tool` | `exactfig` and its version |
| `recipe` | the recipe in **normal form**: every parameter present with its value, defaults filled in |
| `recipe_sha256` | SHA-256 of `canonical(recipe)` |
| `palette` | (images) the resolved palette, `#rrggbb` |
| `output.content_sha256` | images: SHA-256 of `"exactfig-rgba8\0" + width (u32 BE) + height (u32 BE) + RGBA8` with fully transparent pixels as `00000000`; animations: SHA-256 of `"exactfig-anim1\0"` + width, height, frame count (u32 BE)
  + for each frame its delay in ms (u32 BE) and its canonical RGBA8, the same for GIF and APNG; MIDI: SHA-256 of the file |
| `output.file_sha256`, `output.bytes` | the file as written (for PNG informative: another zlib may compress differently) |
| `output.width`, `output.height` | (images, animations) final size, after the integer `scale` |
| `output.frames`, `output.duration_ms` | (animations) number of frames and the sum of their delays |
| `inputs` | (data generators) informative: each input file with its path, format, SHA-256, size in bytes and what was read
  (grid shape and missing cells, or number of points; minimum and maximum) |
| `budget` | informative: canonical recipe size, native pixel count and, for data, input bytes |
| `history` | informative: what this file was before each re-recording that changed it (recipe and content hashes, generator
  name and version), newest first, at most 20. `verify` checks only the current entry |

**Canonical JSON** = UTF-8 of Python's `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`. Floats are
written as Python writes them (`225.0`).

## Recipe

```json
{"generator": "forge.tile.stone", "seed": "slabs-01", "palette": "mf32", "size": [32, 32], "scale": 4,
 "params": {"cells": 4, "jitter": 0.9}, "output": "stone-slabs.png"}
```

- `generator` (required), `seed` (string or integer, ≤ 64 characters), `params` (checked against the generator's closed schema;
  unknown keys and out-of-range values are errors).
- Images only: `palette` (a built-in name or `{"name", "colors": [...], "ramps": {...}}`), `size` `[w, h]`, `scale` 1–16
  (nearest neighbour).
- `output`: the file name, relative to the manifest folder (`record`) or to `--out-dir` (`render`). Not part of the identity.
- Data generators only (`data.field`, `data.scatter`): `input` `{"path", "format", "sha256"}`. `path` is relative to the
  manifest folder (`record`, `verify`) or to `--data-dir` (`render`), written with `/`, and may not leave it. `format` is
  `csv`, `pgm`, `npy` or `json`, taken from the extension when omitted. `sha256` is the SHA-256 of the file's bytes: `record`
  fills it in, so the normal form always pins the exact data; when it is given, the file must match it.

### Compositions

```json
{"generator": "compose", "seed": "fig-1", "palette": "sci", "size": [256, 256],
 "layers": [{"generator": "data.field", "input": {"path": "data/plate-129.npy"}, "params": {"interval": 0.1}},
            {"generator": "draw.annotate", "params": {"shapes": [{"type": "text", "points": [[6, 6]], "text": "T = 1"}]},
             "blend": "over"}],
 "output": "figure-1.png"}
```

A layer is a recipe of any image generator without `palette`, `size` or `scale` (it inherits them) and with an optional
`seed` (default: the parent's) and `blend`: `over` (its opaque pixels cover what is below), `under` (they only fill what
is still transparent) or `mask` (what is below survives only where the layer is opaque). Layers are drawn bottom first;
1 to 16 of them; data layers pin their inputs like any data recipe. In normal form every layer carries its seed, all its
parameters and its blend.

### Input formats

| Format | Grid (`data.field`) | Points (`data.scatter`) |
|---|---|---|
| `csv` (`.csv` `.tsv` `.txt`) | numbers separated by `,` `;` tab or spaces, one row per line, top row first; `#` comments;
  empty, `nan`, `NA` = missing | three columns x, y, value, optional header row |
| `pgm` | Netpbm greymap, P2 or P5, 8 or 16 bits (big-endian) | — |
| `npy` | NumPy format 1.0–3.0, 2-D, C or Fortran order; float16/32/64, signed or unsigned integers, bool; either byte
  order; object arrays refused | — |
| `json` | `{"values": [[…], …]}` or a list of rows; `null` = missing | `{"points": [[x, y, v], …]}` or
  `{"x": […], "y": […], "value": […]}` |

`data.image` reads a picture: PNG (8-bit grey, grey + alpha, RGB, RGBA or indexed, non-interlaced) or Netpbm PPM (P3/P6,
maxval ≤ 255), at most 4096 × 4096 pixels.

`anim.frames` reads a third shape, a sequence of grids, from JSON only: `{"frames": [[[…], …], …]}`, every frame the same
size, at most 1000 frames; other scalar keys (a `source`, the `theorems` the data illustrates) are kept and reported.

Every number is parsed by Python's correctly rounded `float`/`int`, so a file gives the same doubles on every platform.
Limits: 64 MiB per file, 4096 × 4096 cells, 200 000 points (20 000 for the triangulation).

`exactfig list` prints every generator and its schema.

## What `verify` checks, in order

1. `recipe_sha256` matches the recipe, and the recipe is in normal form for the installed generator.
2. The generator exists and has the recorded `version` (else: fail).
3. `code_sha256` matches the installed source (else: warning; failure with `--strict`).
4. Data generators: every input file exists under the manifest folder and its SHA-256 equals `recipe.input.sha256`
   (else: fail, naming the file).
5. Re-running the recipe gives `output.content_sha256`.
6. The file on disk has that same content: for an animation (GIF or APNG, by the file's extension) every decoded frame and
   its delay (the report names the first differing frame); decoded pixels for PNG (the report gives the number of differing pixels and the first
   one), exact bytes for MIDI (the report gives the first differing byte).
7. Images: every opaque pixel is a palette colour, and there are no semi-transparent pixels.
8. The file bytes equal `output.file_sha256` (else: warning, the PNG was re-encoded with the same pixels; failure with `--strict`).
9. `manifest_sha256` matches the entries.

Exit code 0 when everything passes, 1 otherwise; `--json` gives a machine report.

## Threat model in short

- *A file was edited after recording* → step 6.
- *The input data was edited* → step 4: one changed byte changes its SHA-256.
- *A recipe carries data* → only the data generators read data, only from a named file under the manifest folder, and the
  manifest says which bytes. For them the claim is "this image is what this code computes from these bytes", not
  "the information comes from the algorithm alone".
- *Someone wrote a recipe that encodes an image* → impossible by schema: no generator accepts pixel data, free arrays or long
  strings (MIDI title/text fields are short ASCII and only go into meta events).
- *The manifest was edited to match an edited file* → step 5 re-runs the recipe; the result would not match.
- *The manifest was replaced wholesale* → compare `manifest_sha256` with the published, signed value.
- *Who made it* → out of scope: sign the manifest digest.

---

### Resumen en español

Cada entrada guarda la receta en forma normal (todos los parámetros), el generador con su versión y el hash de su código, la
paleta y los hashes de la salida (píxeles canónicos y fichero). `verify` comprueba la receta, el generador, vuelve a ejecutarlo y
compara con el fichero píxel a píxel (o byte a byte en MIDI), comprueba la paleta, la huella SHA-256 de cada fichero de datos
de entrada (CSV, PGM, NPY o JSON; la receta lo fija por su hash) y el resumen `manifest_sha256` del conjunto,
que es el único valor que hace falta publicar o firmar.
