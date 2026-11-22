"""
Recipes → assets / de la receta al asset.

A recipe is a small JSON object:

    {"generator": "forge.tile.stone", "seed": "slate-01", "palette": "mf32", "size": [32, 32], "scale": 4,
     "params": {"cells": 4}, "output": "stone.png"}

The pipeline has four stages, and only the second touches the file system:

  1. normalize   validate against the generator's closed schema and fill every default (pure). The recorded recipe then says
                 everything that was used, so a later change of a default cannot change what an old manifest means.
  2. inputs      read each data file named by the recipe and check it against its pinned SHA-256 (the only I/O).
  3. draw        call the generator: (seed, palette, size, params[, data]) → a Canvas, or (delay, Canvas) frames (pure).
  4. encode      scale by an integer, write PNG / GIF / APNG / MIDI bytes and the canonical content hash.

A `compose` recipe stacks image layers on one canvas; each layer is itself a recipe without palette, size or scale (it
inherits them) and with a `blend`:

    {"generator": "compose", "seed": "fig-3", "palette": "sci", "size": [256, 256],
     "layers": [{"generator": "data.field", "input": {"path": "data/plate-129.npy"}, "params": {"ramp": "seq"}},
                {"generator": "draw.annotate", "params": {"shapes": [...]}, "blend": "over"}],
     "output": "figure-3.png"}

`output` is where to write the result; it is not part of the recipe's identity (for animations it picks the container).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass

from . import registry
from .data import io as dataio
from .forge import describe
from .pixel import anim
from .pixel import palette as palettes
from .pixel import png

RECIPE_KEYS = {"generator", "seed", "palette", "size", "scale", "params", "output", "input", "layers"}
LAYER_KEYS = {"generator", "seed", "params", "input", "blend"}
BLENDS = ("over", "under", "mask")
MAX_LAYERS = 16
MAX_ANIMATION_PIXELS = 64_000_000
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def canonical(obj) -> bytes:
    """Canonical JSON: sorted keys, no spaces, UTF-8. This is what gets hashed."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256(b: bytes) -> str:
    """Hex SHA-256 of bytes."""
    return hashlib.sha256(b).hexdigest()


# ------------------------------------------------------------------------------------------------ 1. normal form

def _seed(seed):
    if isinstance(seed, bool) or not isinstance(seed, (str, int)) or len(str(seed)) > 64:
        raise ValueError("seed must be a string or integer (at most 64 characters)")
    return seed


def _input(gen, inp, base) -> dict:
    """The data file of a recipe: a relative path under `base`, its format and its SHA-256 (computed if not given)."""
    if not isinstance(inp, dict) or set(inp) - {"path", "format", "sha256"} or not isinstance(inp.get("path"), str):
        raise ValueError(f"{gen.name} needs \"input\": {{\"path\": …, \"format\": …, \"sha256\": …}}")
    path = inp["path"]
    parts = path.split("/")
    if (not path or len(path) > 256 or path.startswith("/") or "\\" in path or ":" in path
            or any(s in ("", ".", "..") for s in parts)):
        raise ValueError(f"input path {path!r} must be relative, with '/', and stay inside its folder")
    fmt = dataio.format_of(path, inp.get("format"))
    allowed = dataio.FORMATS[gen.data]
    if fmt not in allowed:
        raise ValueError(f"{gen.name}: format {fmt!r} cannot hold {gen.data} data (use one of {', '.join(allowed)})")
    sha = inp.get("sha256")
    if sha is None:
        if base is None:
            raise ValueError(f"input {path!r}: give its sha256, or render it from the folder that holds it")
        sha = dataio.sha256_file(os.path.join(base, path))
    elif not isinstance(sha, str) or not _HEX64.match(sha):
        raise ValueError("input sha256 must be 64 lowercase hex digits")
    return {"path": path, "format": fmt, "sha256": sha}


def _body(gen, recipe, base, seed) -> dict:
    """generator, seed, params and input of a recipe or a layer, in normal form."""
    out = {"generator": gen.name, "seed": seed, "params": gen.resolve(recipe.get("params", {}))}
    if gen.data:
        out["input"] = _input(gen, recipe.get("input"), base)
    elif "input" in recipe:
        raise ValueError(f"{gen.name} does not take an input file")
    return out


def _layers(layers, base, parent_seed) -> list:
    if not isinstance(layers, list) or not 1 <= len(layers) <= MAX_LAYERS:
        raise ValueError(f"compose needs \"layers\": a list of 1..{MAX_LAYERS} layer recipes")
    out = []
    for k, layer in enumerate(layers):
        if not isinstance(layer, dict) or set(layer) - LAYER_KEYS:
            raise ValueError(f"layer {k}: keys must be among {sorted(LAYER_KEYS)} (palette, size and scale come from the parent)")
        gen = registry.get(layer.get("generator", ""))
        if gen.kind != "image" or gen.name == "compose":
            raise ValueError(f"layer {k}: {gen.name} is not an image generator")
        blend = layer.get("blend", "over")
        if blend not in BLENDS:
            raise ValueError(f"layer {k}: blend must be one of {', '.join(BLENDS)}")
        n = _body(gen, layer, base, _seed(layer.get("seed", parent_seed)))
        n["blend"] = blend
        out.append(n)
    return out


def normalize(recipe: dict, base: str | None = None) -> dict:
    """Validate a recipe and return it in normal form (every parameter present, input hashes filled in)."""
    if not isinstance(recipe, dict):
        raise ValueError("a recipe is a JSON object")
    unknown = set(recipe) - RECIPE_KEYS
    if unknown:
        raise ValueError(f"unknown recipe keys {sorted(unknown)}")
    gen = registry.get(recipe.get("generator", ""))
    seed = _seed(recipe.get("seed"))
    if gen.name == "compose":
        out = {"generator": "compose", "seed": seed, "params": gen.resolve(recipe.get("params", {})),
               "layers": _layers(recipe.get("layers"), base, seed)}
    else:
        if "layers" in recipe:
            raise ValueError(f"{gen.name} does not take layers (use the compose generator)")
        out = _body(gen, recipe, base, seed)
    if gen.kind in ("image", "animation"):
        pal = recipe.get("palette", "mf32")
        palettes.get(pal)                              # validates
        size = recipe.get("size", list(gen.size))
        if (not isinstance(size, list) or len(size) != 2 or any(isinstance(v, bool) or not isinstance(v, int) for v in size)
                or not all(1 <= v <= gen.max_size for v in size)):
            raise ValueError(f"size must be [w, h] with 1..{gen.max_size}")
        scale = recipe.get("scale", 1)
        if isinstance(scale, bool) or not isinstance(scale, int) or not 1 <= scale <= 16:
            raise ValueError("scale must be an integer 1..16 (nearest neighbour)")
        out.update(palette=pal, size=size, scale=scale)
    else:
        for k in ("palette", "size", "scale"):
            if k in recipe:
                raise ValueError(f"{gen.name} does not take {k!r}")
    return out


def identity(r: dict) -> dict:
    """Generator name, version and source hash of a normal-form recipe. A composition's version and hash cover every
    layer's generator, so changing any of them is seen by verify."""
    gen = registry.get(r["generator"])
    if gen.name != "compose":
        return {"name": gen.name, "version": gen.version, "code_sha256": gen.code_sha256()}
    used = sorted({layer["generator"] for layer in r["layers"]})
    parts = [registry.get(n) for n in used]
    version = gen.version + "+" + "+".join(f"{g.name}@{g.version}" for g in parts)
    code = sha256(("\0".join([gen.code_sha256()] + [g.code_sha256() for g in parts])).encode())
    return {"name": "compose", "version": version, "code_sha256": code}


# ------------------------------------------------------------------------------------------------ 2. inputs

def _load(gen, inp, base):
    path = os.path.join(base, inp["path"])
    if not os.path.isfile(path):
        raise ValueError(f"input {inp['path']!r} not found under {base!r}")
    got = dataio.sha256_file(path)
    if got != inp["sha256"]:
        raise ValueError(f"input {inp['path']!r} changed: sha256 {got[:16]}…, the recipe pins {inp['sha256'][:16]}…")
    data = dataio.load(path, gen.data, inp["format"])
    return data, {**inp, "bytes": os.path.getsize(path), **data.describe()}


# ------------------------------------------------------------------------------------------------ 3. draw

def _draw(body: dict, pal, w: int, h: int, base: str, inputs: list, alts: list | None = None):
    """Draw one generator; append its input's description to `inputs` and, after it has drawn (and so after its data
    have passed their checks), its alternative text to `alts`."""
    gen = registry.get(body["generator"])
    data = None
    if gen.data:
        data, info = _load(gen, body["input"], base)
        inputs.append(info)
        out = gen.fn(str(body["seed"]), pal, w, h, body["params"], data)
    else:
        out = gen.fn(str(body["seed"]), pal, w, h, body["params"])
    if alts is not None:
        alts.append(describe.text(gen, body["params"], data, w, h))
    return out


def _compose(r, pal, w, h, base, inputs, alts=None):
    """Stack the layers in order. `over`: the layer's opaque pixels cover what is below; `under`: they only fill what is
    still transparent; `mask`: what is below survives only where the layer is opaque."""
    from .pixel.canvas import Canvas
    out = Canvas(w, h, pal)
    for layer in r["layers"]:
        cv = _draw(layer, pal, w, h, base, inputs, alts)
        if (cv.w, cv.h) != (w, h):
            raise AssertionError(f"{layer['generator']} drew {cv.w}x{cv.h}, asked {w}x{h}")
        for y in range(h):
            row, top = out.px[y], cv.px[y]
            for x in range(w):
                c = top[x]
                if layer["blend"] == "over":
                    if c is not None:
                        row[x] = c
                elif layer["blend"] == "under":
                    if row[x] is None:
                        row[x] = c
                elif c is None:                       # mask
                    row[x] = None
    return out


# ------------------------------------------------------------------------------------------------ 4. encode

@dataclass
class Rendered:
    """The output of a recipe: the file's bytes, its canonical content hash, and what verify needs to check it."""
    kind: str                 # image | animation | midi
    data: bytes               # the file's bytes
    content_sha256: str       # canonical pixels (image), canonical frames (animation) or the bytes (MIDI)
    width: int = 0
    height: int = 0
    palette: list | None = None
    inputs: list | None = None
    frames: int = 0
    duration_ms: int = 0
    alt: str = ""             # alternative text, exact (forge/describe.py)


MAX_SIMULATION_WORK = 400_000_000      # cells × generations a simulation may compute (a few minutes in pure Python)
OUTPUT_EXTENSIONS = {"image": (".png",), "animation": (".gif", ".png", ".apng"), "midi": (".mid", ".midi")}


def load_recipe(path: str) -> dict:
    """A recipe file: a JSON object in UTF-8 (with or without a BOM) or UTF-16 with a BOM."""
    with open(path, "rb") as fh:
        raw = fh.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError(f"{path}: a recipe of more than 4 MiB (recipes are small; data goes in input files)")
    try:
        recipe = json.loads(dataio.decode_text(raw, path))
    except json.JSONDecodeError as ex:
        raise ValueError(f"{path}: not valid JSON ({ex.msg}, line {ex.lineno}, column {ex.colno})") from None
    if not isinstance(recipe, dict):
        raise ValueError(f"{path}: a recipe is a JSON object {{\"generator\": …}}")
    return recipe


def output_name(name, kind: str) -> str:
    """Check a recipe's `output`: a relative path with '/', inside its folder, with an extension that matches `kind`."""
    if not isinstance(name, str):
        raise ValueError("output must be a file name")
    parts = name.split("/")
    if (not name or len(name) > 256 or name.startswith("/") or "\\" in name or ":" in name
            or any(s in ("", ".", "..") for s in parts)):
        raise ValueError(f"output {name!r} must be relative, with '/', and stay inside its folder")
    ext = os.path.splitext(name)[1].lower()
    if ext not in OUTPUT_EXTENSIONS[kind]:
        what = {"image": "an image", "animation": "an animation", "midi": "a MIDI file"}[kind]
        raise ValueError(f"output {name!r}: {what} is written as {' or '.join(OUTPUT_EXTENSIONS[kind])}")
    return name


def _budget(gen, r, w, h):
    """Refuse an animation or simulation that would be too large BEFORE computing it, not after."""
    p, k = r["params"], r["scale"]
    frames = p.get("frames")
    if gen.kind == "animation" and isinstance(frames, int) and w * h * k * k * frames > MAX_ANIMATION_PIXELS:
        raise ValueError(f"{frames} frames of {w * k}×{h * k} is more than {MAX_ANIMATION_PIXELS} pixels in all: "
                         "use fewer frames, a smaller size or a smaller scale")
    every = p.get("every")
    if isinstance(frames, int) and isinstance(every, int) and w * h * frames * every > MAX_SIMULATION_WORK:
        raise ValueError(f"{w}×{h} cells for {frames}×{every} steps is more than {MAX_SIMULATION_WORK} cell-steps "
                         "(it would run for a very long time): use fewer frames, fewer steps per frame or a smaller size")


def container_of(output: str | None) -> str:
    """Animation container from the output name: .gif (default) or .png / .apng (APNG)."""
    ext = os.path.splitext(output or "")[1].lower()
    if ext in (".png", ".apng"):
        return "apng"
    if ext in ("", ".gif"):
        return "gif"
    raise ValueError(f"an animation is written as .gif or .png (APNG), not {ext}")


def render(recipe: dict, base: str = ".", container: str | None = None) -> Rendered:
    """Run a recipe. Input files are read from `base` (the manifest folder when recording) and must match their sha256."""
    r = normalize(recipe, base)
    gen = registry.get(r["generator"])
    if gen.kind == "midi":
        data = gen.fn(str(r["seed"]), r["params"])
        return Rendered("midi", data, sha256(data), alt=describe.text(gen, r["params"], None, 0, 0))
    pal = palettes.get(r["palette"])
    w, h = r["size"]
    _budget(gen, r, w, h)
    inputs: list = []
    alts: list = []
    out = _compose(r, pal, w, h, base, inputs, alts) if gen.name == "compose" else _draw(r, pal, w, h, base, inputs, alts)
    inputs = inputs or None
    alt = alts[0] if len(alts) == 1 else " ".join(f"Layer {i}: {a}" for i, a in enumerate(alts, 1))
    if gen.kind == "animation":
        ren = _animation(gen, r, out, pal, w, h, inputs, container or container_of(recipe.get("output")))
        ren.alt = alt
        return ren
    if (out.w, out.h) != (w, h):
        raise AssertionError(f"{gen.name} drew {out.w}x{out.h}, asked {w}x{h}")
    cv = out.scaled(r["scale"])
    rgba = cv.to_rgba()
    return Rendered("image", cv.to_png(), png.pixels_sha256(cv.w, cv.h, rgba), cv.w, cv.h, list(pal.hex), inputs,
                    alt=alt)


def _animation(gen, r, frames, pal, w, h, inputs, container) -> Rendered:
    if not frames or len(frames) > anim.MAX_FRAMES:
        raise AssertionError(f"{gen.name} made {len(frames)} frames")
    k = r["scale"]
    if w * h * k * k * len(frames) > MAX_ANIMATION_PIXELS:
        raise ValueError(f"{len(frames)} frames of {w * k}×{h * k} is more than {MAX_ANIMATION_PIXELS} pixels in all")
    idx, canon = [], []
    for delay, cv in frames:
        if (cv.w, cv.h) != (w, h):
            raise AssertionError(f"{gen.name} drew {cv.w}x{cv.h}, asked {w}x{h}")
        cv = cv.scaled(k)
        idx.append((delay, [c for _, _, c in cv.cells()]))
        canon.append((delay, cv.to_rgba()))
    W, H = w * k, h * k
    enc = anim.encode_gif if container == "gif" else anim.encode_apng
    data = enc(W, H, idx, pal.rgb)
    out = Rendered("animation", data, anim.frames_sha256(W, H, canon), W, H, list(pal.hex), inputs)
    out.frames, out.duration_ms = len(frames), sum(d for d, _ in frames)
    return out
