"""
exactfig command line / línea de órdenes.

  exactfig render RECIPE.json …  [--out-dir DIR]          draw / compose and write the file(s), no manifest
  exactfig record RECIPE.json …  --manifest M.json        render, write next to the manifest and record provenance
  exactfig verify [--manifest M.json] [--strict] [--json] [PATH …]
                                                           re-run every recorded recipe and compare pixel/byte for byte
  exactfig cvd [--manifest M.json] [--min D] [--share S] [--json]
                                                           colour pairs that colour-blind readers may confuse (inform)
  exactfig alt [--manifest M.json] [--json]               the alternative text of every recorded file (exact)
  exactfig crate [--manifest M.json] [--date D] [--license SPDX] [--author A] [--name N]
                                                           write ro-crate-metadata.json beside the manifest (RO-Crate
                                                           1.3, Process Run Crate 0.6), files checked against it first
  exactfig video RECIPE.json --out FILE.mp4 [--scale K]   an animation as MP4 through ffmpeg (for sharing; not verifiable:
                                                           the codec is lossy; verify the GIF/APNG instead)
  exactfig edit RECIPE.json --set KEY=VALUE …  [--out NEW.json] [--data-dir DIR]
                                                           change a recipe field (dotted path, JSON value), check the
                                                           result against the schema, and write it back
  exactfig palette IMAGE --k K [--method median-cut|kmeans] [--size N] [--name NAME] [--out PAL.json]
                                                           a K-colour palette from a picture, written as a recipe palette
  exactfig selftest [--gallery M.json]                    does this machine reproduce exactfig bit for bit?
  exactfig list                                           generators and their parameters
  exactfig palettes                                       built-in palettes and ramps
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__, provenance, registry
from .pixel import palette as palettes
from .render import load_recipe, output_name, render


def _render(files, out_dir, data_dir):
    if os.path.exists(out_dir) and not os.path.isdir(out_dir):
        raise ValueError(f"--out-dir {out_dir!r} is a file, not a folder")
    for rf in files:
        recipe = load_recipe(rf)
        out = render(recipe, data_dir)
        ext = {"image": ".png", "animation": ".gif", "midi": ".mid"}[out.kind]
        if "output" in recipe:
            name = output_name(recipe["output"], out.kind)
        else:
            name = os.path.splitext(os.path.basename(rf))[0] + ext
        path = os.path.join(out_dir, name)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(out.data)
        print(f"{path}  {out.content_sha256[:16]}")
    return 0


def _list():
    for g in registry.all_generators().values():
        print(f"{g.name}  v{g.version}  [{g.kind}]  {g.summary}")
        if g.kind in ("image", "animation"):
            print(f"    size default {list(g.size)}, max {g.max_size}")
        for k, p in g.params.items():
            rng = f" {p.lo}..{p.hi}" if p.lo is not None else ""
            ch = f" one of {list(p.choices)}" if p.choices and len(p.choices) <= 12 else f" ({len(p.choices)} choices)" if p.choices else ""
            print(f"    {k:12} {p.kind}{rng}{ch}  default {json.dumps(p.default)}" + (f"  — {p.doc}" if p.doc else ""))
    return 0


def _video(rf, out_path, scale, data_dir):
    import shutil
    import subprocess
    from .pixel import anim as A
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError("ffmpeg is not installed: install it, or share the GIF/APNG (which verify can check)")
    recipe = load_recipe(rf)
    out = render(recipe, data_dir, "apng")
    if out.kind != "animation":
        raise ValueError(f"{rf} is not an animation")
    w, h, frames = A.decode(out.data)
    W, H = w * scale, h * scale
    W2, H2 = W + W % 2, H + H % 2              # yuv420p needs even sides: pad with the first palette colour
    fill = bytes(int(out.palette[0][i:i + 2], 16) for i in (1, 3, 5))
    fps = 1000 / frames[0][0]
    proc = subprocess.Popen([ffmpeg, "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W2}x{H2}",
                             "-r", f"{fps:.6g}", "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "12",
                             "-movflags", "+faststart", out_path], stdin=subprocess.PIPE)
    for _, rgba in frames:
        img = bytearray()
        for y in range(H2):
            for x in range(W2):
                if x < W and y < H:
                    q = ((y // scale) * w + x // scale) * 4
                    img += rgba[q:q + 3] if rgba[q + 3] else fill
                else:
                    img += fill
        proc.stdin.write(bytes(img))
    proc.stdin.close()
    if proc.wait():
        raise ValueError("ffmpeg failed")
    print(f"{out_path}  {len(frames)} frames, {W2}x{H2}, {fps:.3g} fps  (frames: {out.content_sha256[:16]})")
    return 0


def _edit(rf, sets, out_path, data_dir):
    """`--set params.contours=12`, `--set layers.1.blend=\"under\"`, `--set seed=7`: the value is JSON, or a plain
    string when it is not valid JSON. The edited recipe must still normalise; nothing is written otherwise."""
    from .render import normalize
    recipe = load_recipe(rf)
    for item in sets:
        key, sep, raw = item.partition("=")
        if not sep or not key:
            raise ValueError(f"--set {item!r}: use KEY=VALUE")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        node, parts = recipe, key.split(".")
        for part in parts[:-1]:
            node = node[int(part)] if isinstance(node, list) else node.setdefault(part, {})
        last = parts[-1]
        if isinstance(node, list):
            node[int(last)] = value
        else:
            node[last] = value
    normalize(recipe, data_dir)                    # raises with the reason if the edit is not valid
    path = out_path or rf
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(recipe, ensure_ascii=False) + "\n")
    print(f"{path}: {len(sets)} change(s), valid")
    return 0


def _palette_from(path, k, method, size, name, out_path):
    """Read a PNG/PPM, resample it so its long side is `size` (area, linear light), and derive a k-colour palette by
    median cut or k-means in OKLab. The result is a palette object a recipe can carry inline."""
    from .data import io as dataio
    from .pixel import convert
    img = dataio.load(path, "image")
    scale = max(img.width, img.height) / size
    w, h = max(1, round(img.width / scale)), max(1, round(img.height / scale))
    px = convert.resample(img.width, img.height, img.rgba, w, h, "area")
    rgb = convert.median_cut(px, k) if method == "median-cut" else convert.kmeans(px, k)
    pal = convert.palette_object(name, rgb)
    text = json.dumps(pal, ensure_ascii=False)
    if out_path:
        with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
    print(text)
    return 0


def _palettes():
    for name in palettes.builtin_names():
        pal = palettes.builtin(name)
        print(f"{name}  ({len(pal)} colours)")
        for r, idx in pal.ramps.items():
            print(f"    {r:6} " + " ".join(pal.hex[i] for i in idx))
    return 0


def main(argv=None) -> int:
    """Parse the command line, run one sub-command and return its exit code (2 for a reported error)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")   # consolas de Windows
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="exactfig", description="Reproducible figures, animations and sonifications, verifiable bit for bit.")
    ap.add_argument("--version", action="version", version=f"exactfig {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("render", help="render recipes to files")
    a.add_argument("recipes", nargs="+")
    a.add_argument("--out-dir", default=".")
    a.add_argument("--data-dir", default=".", help="folder that input paths in the recipes are relative to")
    a = sub.add_parser("record", help="render recipes and record them in a manifest")
    a.add_argument("recipes", nargs="+")
    a.add_argument("--manifest", required=True)
    a = sub.add_parser("verify", help="re-run a manifest and compare")
    a.add_argument("paths", nargs="*", help="only these recorded paths")
    a.add_argument("--manifest", default="gallery/manifest.json")
    a.add_argument("--strict", action="store_true", help="also fail on changed generator source or re-encoded files")
    a.add_argument("--json", action="store_true")
    a = sub.add_parser("cvd", help="which colours of each recorded image run together for colour-blind readers")
    a.add_argument("--manifest", default="gallery/manifest.json")
    a.add_argument("--min", type=float, default=0.06, help="report pairs closer than this OKLab distance (default 0.06)")
    a.add_argument("--share", type=float, default=0.005,
                   help="only colours covering at least this share of the opaque pixels (default 0.005)")
    a.add_argument("--json", action="store_true")
    a = sub.add_parser("alt", help="the alternative text of every recorded file (exact: stated from the checks)")
    a.add_argument("--manifest", default="gallery/manifest.json")
    a.add_argument("--json", action="store_true", help="a JSON object {file: text}")
    a = sub.add_parser("crate", help="describe a manifest's folder as an RO-Crate (Process Run Crate, W3C PROV terms)")
    a.add_argument("--manifest", default="gallery/manifest.json",
                   help="the manifest; ro-crate-metadata.json is written beside it")
    a.add_argument("--date", help="datePublished, YYYY-MM-DD (default: today)")
    a.add_argument("--license", help="SPDX licence identifier of the files, e.g. CC-BY-4.0 (recommended)")
    a.add_argument("--author", help="the person who recorded the files: a name or an ORCID URL")
    a.add_argument("--name", help="name of the crate (default: the folder's name)")
    a = sub.add_parser("palette", help="derive a palette from a picture (median cut or k-means in OKLab)")
    a.add_argument("image")
    a.add_argument("--k", type=int, required=True, help="number of colours (2..256)")
    a.add_argument("--method", choices=("median-cut", "kmeans"), default="kmeans")
    a.add_argument("--size", type=int, default=128, help="long side of the resampled picture the palette is taken from")
    a.add_argument("--name", default="derived")
    a.add_argument("--out")
    a = sub.add_parser("edit", help="change fields of a recipe and check it")
    a.add_argument("recipe")
    a.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", required=True)
    a.add_argument("--out", help="write here instead of over the recipe")
    a.add_argument("--data-dir", default=".")
    a = sub.add_parser("video", help="write an animation as MP4 through ffmpeg (not verifiable)")
    a.add_argument("recipe")
    a.add_argument("--out", required=True)
    a.add_argument("--scale", type=int, default=4, help="integer zoom, nearest neighbour")
    a.add_argument("--data-dir", default=".")
    a = sub.add_parser("selftest", help="check that this machine reproduces exactfig bit for bit")
    a.add_argument("--gallery", help="also verify this manifest (--strict)")
    sub.add_parser("list", help="list generators and parameters")
    sub.add_parser("palettes", help="list built-in palettes")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "render":
            return _render(args.recipes, args.out_dir, args.data_dir)
        if args.cmd == "record":
            provenance.record(args.recipes, args.manifest)
            return 0
        if args.cmd == "verify":
            return provenance.main_verify(args.manifest, args.strict, args.json, args.paths or None)
        if args.cmd == "cvd":
            return _cvd(args.manifest, args.min, args.share, args.json)
        if args.cmd == "alt":
            assets = provenance.load(args.manifest)["assets"]
            texts = {rel: e.get("alt", "") for rel, e in sorted(assets.items())}
            if args.json:
                print(json.dumps(texts, ensure_ascii=False, indent=1))
            else:
                for rel, t in texts.items():
                    print(f"{rel}	{t or '(no alternative text: recorded before 0.10.0; record again)'}")
            return 0
        if args.cmd == "crate":
            from .provenance import crate
            print(crate.write(args.manifest, date=args.date, license_id=args.license, name=args.name,
                              author=args.author))
            if not args.license:
                print("exactfig: note: no --license given; RO-Crate recommends one (e.g. --license CC-BY-4.0)",
                      file=sys.stderr)
            return 0
        if args.cmd == "palette":
            if not 2 <= args.k <= 256 or not 1 <= args.size <= 4096:
                raise ValueError("--k must be 2..256 and --size 1..4096")
            return _palette_from(args.image, args.k, args.method, args.size, args.name, args.out)
        if args.cmd == "edit":
            return _edit(args.recipe, args.set, args.out, args.data_dir)
        if args.cmd == "video":
            return _video(args.recipe, args.out, max(1, min(16, args.scale)), args.data_dir)
        if args.cmd == "selftest":
            from . import selftest
            return 0 if selftest.run(gallery=args.gallery) else 1
        if args.cmd == "list":
            return _list()
        return _palettes()
    except KeyboardInterrupt:
        print("exactfig: interrupted", file=sys.stderr)
        return 130
    except BrokenPipeError:                      # e.g. `exactfig list | head`: the reader went away
        return 0
    except (ValueError, OSError) as ex:          # the user's input or environment: one line saying what and why
        print(f"exactfig: {_plain(ex)}", file=sys.stderr)
        return 2
    except Exception as ex:                      # a bug in exactfig: say so, and how to get the details
        if os.environ.get("EXACTFIG_DEBUG"):
            raise
        print(f"exactfig: internal error ({type(ex).__name__}: {ex}). This is a bug in exactfig, not in your input: "
              "run again with EXACTFIG_DEBUG=1 for the traceback and report it.", file=sys.stderr)
        return 3


def _cvd(manifest: str, minimum: float, share: float, as_json: bool) -> int:
    """Colour-blindness audit of every recorded PNG image (animations and MIDI are skipped); exit 0 even when pairs
    are reported: it informs, it does not judge a figure."""
    from .pixel import cvd, png as pngmod
    if not 0 < minimum < 1 or not 0 <= share < 1:
        raise ValueError("--min must be between 0 and 1, --share between 0 and 1")
    base = os.path.dirname(os.path.abspath(manifest))
    report = {}
    for rel, e in sorted(provenance.load(manifest)["assets"].items()):
        if e.get("kind") != "image":
            continue
        with open(os.path.join(base, rel), "rb") as fh:
            raw = fh.read()
        if rel.lower().endswith(".svg"):
            from .pixel import svg as svgmod
            w, h, rgba = svgmod.decode(raw)[:3]
        else:
            w, h, rgba = pngmod.decode(raw)
        counts = {}
        for i in range(0, len(rgba), 4):
            if rgba[i + 3]:
                key = (rgba[i], rgba[i + 1], rgba[i + 2])
                counts[key] = counts.get(key, 0) + 1
        total = sum(counts.values()) or 1
        cols = sorted(c for c, n in counts.items() if n >= share * total)
        hexes = ["#%02x%02x%02x" % c for c in cols]
        res = cvd.audit(cols, minimum)
        report[rel] = {v: {"closest": round(r["closest"][0], 4) if r["closest"] else None,
                           "pair": [hexes[r["closest"][1]], hexes[r["closest"][2]]] if r["closest"] else None,
                           "below": len(r["below"])} for v, r in res.items()}
        report[rel]["colours"] = len(cols)
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0
    for rel, r in report.items():
        cells = []
        for v in cvd.VISIONS:
            x = r[v]
            cells.append(f"{v} {x['closest']:.3f}" + (f" ({x['below']} pairs below)" if x["below"] else "")
                         if x["closest"] is not None else f"{v} -")
        print(f"{rel}	{r['colours']} colours	" + " | ".join(cells))
    return 0


def _plain(ex: Exception) -> str:
    """An OSError as 'file: reason' instead of '[Errno 2] No such file or directory: …'."""
    if isinstance(ex, OSError) and ex.filename is not None and ex.strerror:
        return f"{ex.filename}: {ex.strerror.lower()}"
    return str(ex)


if __name__ == "__main__":
    sys.exit(main())
