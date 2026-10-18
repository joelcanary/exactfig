"""
Provenance: record and verify / procedencia: apuntar y verificar.

record   renders each recipe (twice, to catch any nondeterminism), writes the file and stores in the manifest: the normalised
         recipe and its hash, the generator name + version + hash of its source code, the palette, and the hashes of the
         output (file bytes and canonical content).
verify   for every manifest entry: the recipe hash still matches, the generator exists with the same version, re-running it
         gives the recorded content hash, the file on disk has that same content, and an image uses only its palette.
         Reports the number of differing pixels / the first differing byte.

The manifest carries a `manifest_sha256` over all its entries: publish that one hash (in a signed tag, a release note) and the
whole gallery is pinned. See docs/MANIFEST.md.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field

from .. import __version__, registry
from ..pixel import anim, png
from ..render import canonical, container_of, identity, normalize, render, sha256

MAX_HISTORY = 20

FORMAT = "exactfig.manifest/1"


def empty() -> dict:
    """A manifest with no assets."""
    return {"format": FORMAT, "assets": {}, "manifest_sha256": sha256(canonical({}))}


def load(path: str) -> dict:
    """Read a manifest (an empty one if the file does not exist); ValueError for another format."""
    if not os.path.exists(path):
        return empty()
    with open(path, encoding="utf-8") as fh:
        man = json.load(fh)
    if man.get("format") != FORMAT:
        raise ValueError(f"{path}: not a {FORMAT} file")
    return man


def save(path: str, man: dict):
    """Write a manifest with sorted entries and its manifest_sha256 recomputed."""
    man["assets"] = {k: man["assets"][k] for k in sorted(man["assets"])}
    man["manifest_sha256"] = sha256(canonical(man["assets"]))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(man, ensure_ascii=False, indent=1, sort_keys=False) + "\n")


def entry_for(recipe: dict, out, base: str | None = None) -> dict:
    """The manifest entry for a recipe and its rendered output: normal-form recipe, identity, hashes, inputs."""
    r = normalize(recipe, base)
    e = {
        "kind": out.kind,
        "generator": identity(r),
        "tool": {"name": "exactfig", "version": __version__},
        "recipe": r,
        "recipe_sha256": sha256(canonical(r)),
        "output": {"file_sha256": sha256(out.data), "content_sha256": out.content_sha256, "bytes": len(out.data)},
        "budget": {"recipe_bytes": len(canonical(r))},
    }
    if out.kind == "animation":
        e["output"].update(width=out.width, height=out.height, frames=out.frames, duration_ms=out.duration_ms)
        e["palette"] = out.palette
        e["budget"]["pixels"] = out.width * out.height * out.frames // (r["scale"] ** 2)
    if out.kind == "image":
        e["output"].update(width=out.width, height=out.height)
        e["palette"] = out.palette
        e["budget"]["pixels"] = out.width * out.height // (r["scale"] ** 2)
    if out.inputs:
        e["inputs"] = out.inputs
        e["budget"]["input_bytes"] = sum(i["bytes"] for i in out.inputs)
    return e


def _rel(path: str, base: str) -> str:
    rel = os.path.relpath(os.path.abspath(path), os.path.abspath(base)).replace(os.sep, "/")
    if rel.startswith("../"):
        raise ValueError(f"{path}: outputs must live under the manifest folder")
    return rel


def record(recipe_files: list[str], manifest_path: str, log=print) -> dict:
    """Render each recipe twice (they must agree), write the file next to the manifest and record its entry; an
    entry that changes keeps the previous recipe and content hashes in its history."""
    man = load(manifest_path)
    base = os.path.dirname(os.path.abspath(manifest_path))
    for rf in recipe_files:
        with open(rf, encoding="utf-8") as fh:
            recipe = json.load(fh)
        if "output" not in recipe:
            raise ValueError(f"{rf}: the recipe needs an 'output' file name")
        a, b = render(recipe, base), render(recipe, base)
        if a.data != b.data or a.content_sha256 != b.content_sha256:
            raise RuntimeError(f"{rf}: two renders differ: the generator is not deterministic")
        target = os.path.join(base, recipe["output"])
        rel = _rel(target, base)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as fh:
            fh.write(a.data)
        new = entry_for(recipe, a, base)
        old = man["assets"].get(rel)
        if old and (old.get("recipe_sha256"), old["output"].get("content_sha256")) != (new["recipe_sha256"],
                                                                         new["output"]["content_sha256"]):
            # an edit: keep what the file used to be, newest first (informative; verify checks the current entry)
            was = {"recipe_sha256": old.get("recipe_sha256"), "content_sha256": old["output"].get("content_sha256"),
                   "generator": {k: old.get("generator", {}).get(k) for k in ("name", "version")}}
            new["history"] = ([was] + old.get("history", []))[:MAX_HISTORY]
        elif old and old.get("history"):
            new["history"] = old["history"]
        man["assets"][rel] = new
        log(f"recorded {rel}  {a.content_sha256[:16]}  ({len(a.data)} bytes)")
    save(manifest_path, man)
    return man


# ------------------------------------------------------------------------------------------------ verify


@dataclass
class Check:
    """The result of verifying one entry: ok, the problems that make it fail and the warnings."""
    path: str
    ok: bool = True
    problems: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def fail(self, msg):
        self.ok = False; self.problems.append(msg)


def _pixel_diff(w, h, a: bytes, b: bytes):
    a, b = png.canonical_rgba(a), png.canonical_rgba(b)
    diff = [i // 4 for i in range(0, len(a), 4) if a[i:i + 4] != b[i:i + 4]]
    if not diff:
        return 0, None
    return len(diff), (diff[0] % w, diff[0] // w)


def verify_entry(rel: str, e: dict, base: str, strict: bool = False) -> Check:
    """Check one manifest entry against the installed code and the file on disk (see docs/MANIFEST.md)."""
    c = Check(rel)
    r = e.get("recipe", {})
    if sha256(canonical(r)) != e.get("recipe_sha256"):
        c.fail("the recipe was edited after recording (recipe_sha256 mismatch)")
        return c
    try:
        if normalize(r) != r:
            c.fail("the recorded recipe is not in normal form for this version of its generator")
            return c
    except ValueError as ex:
        c.fail(str(ex)); return c
    g, now = e.get("generator", {}), identity(r)
    if g.get("version") != now["version"]:
        c.fail(f"generator {now['name']} is version {now['version']}, the asset was made with {g.get('version')}")
        return c
    if g.get("code_sha256") != now["code_sha256"]:
        (c.fail if strict else c.warnings.append)(f"generator source changed since recording ({g.get('code_sha256', '')[:12]} → {now['code_sha256'][:12]})")
    out = e["output"]
    try:
        again = render(r, base, container_of(rel) if e.get("kind") == "animation" else None)
    except ValueError as ex:                          # an input file missing or changed
        c.fail(str(ex)); return c
    if again.content_sha256 != out["content_sha256"]:
        c.fail(f"re-running {now['name']} gives different content ({again.content_sha256[:16]} ≠ {out['content_sha256'][:16]})")
    path = os.path.join(base, rel)
    if not os.path.exists(path):
        c.fail("file missing"); return c
    with open(path, "rb") as fh:
        data = fh.read()
    if e["kind"] == "animation":
        _verify_animation(c, e, out, data, again)
    elif e["kind"] == "image":
        try:
            w, h, rgba = png.decode(data)
        except Exception as ex:   # noqa: BLE001  (un fichero ajeno o roto: es un fallo, no un error del programa)
            c.fail(f"cannot read the PNG: {ex}"); return c
        if (w, h) != (out["width"], out["height"]):
            c.fail(f"size {w}x{h}, recorded {out['width']}x{out['height']}"); return c
        if png.pixels_sha256(w, h, rgba) != out["content_sha256"]:
            _, _, mine = png.decode(again.data)
            n, first = _pixel_diff(w, h, mine, rgba)
            c.fail(f"{n} pixel(s) differ from what the recipe produces (first at x={first[0]}, y={first[1]})" if n else "pixel hash mismatch")
        allowed = {tuple(int(e["palette"][i][k:k + 2], 16) for k in (1, 3, 5)) for i in range(len(e["palette"]))}
        off = {tuple(rgba[i:i + 3]) for i in range(0, len(rgba), 4) if rgba[i + 3] and tuple(rgba[i:i + 3]) not in allowed}
        partial = any(0 < rgba[i] < 255 for i in range(3, len(rgba), 4))
        if off:
            c.fail(f"palette lock broken: {len(off)} colour(s) not in the palette, e.g. #{bytes(sorted(off)[0]).hex()}")
        if partial:
            c.fail("palette lock broken: semi-transparent pixels")
    else:
        if sha256(data) != out["content_sha256"]:
            first = next((i for i, (x, y) in enumerate(zip(data, again.data)) if x != y), min(len(data), len(again.data)))
            c.fail(f"MIDI bytes differ from what the recipe produces (first difference at byte {first}; {len(data)} vs {len(again.data)} bytes)")
    if sha256(data) != out["file_sha256"] and c.ok:
        (c.fail if strict else c.warnings.append)("file bytes re-encoded (same pixels, different compression)")
    return c


def _palette_problems(e, rgba) -> list:
    allowed = {tuple(int(e["palette"][i][k:k + 2], 16) for k in (1, 3, 5)) for i in range(len(e["palette"]))}
    off = {tuple(rgba[i:i + 3]) for i in range(0, len(rgba), 4) if rgba[i + 3] and tuple(rgba[i:i + 3]) not in allowed}
    probs = []
    if off:
        probs.append(f"palette lock broken: {len(off)} colour(s) not in the palette, e.g. #{bytes(sorted(off)[0]).hex()}")
    if any(0 < rgba[i] < 255 for i in range(3, len(rgba), 4)):
        probs.append("palette lock broken: semi-transparent pixels")
    return probs


def _verify_animation(c, e, out, data, again):
    try:
        w, h, frames = anim.decode(data)
    except Exception as ex:   # noqa: BLE001  (un fichero ajeno o roto: es un fallo, no un error del programa)
        c.fail(f"cannot read the animation: {ex}"); return
    if (w, h, len(frames)) != (out["width"], out["height"], out["frames"]):
        c.fail(f"{w}x{h}, {len(frames)} frames; recorded {out['width']}x{out['height']}, {out['frames']} frames"); return
    if anim.frames_sha256(w, h, frames) != out["content_sha256"]:
        _, _, mine = anim.decode(again.data)
        for k, ((d1, a), (d2, b)) in enumerate(zip(mine, frames)):
            if d1 != d2:
                c.fail(f"frame {k}: delay {d2} ms, the recipe gives {d1} ms"); break
            n, first = _pixel_diff(w, h, a, b)
            if n:
                c.fail(f"frame {k}: {n} pixel(s) differ from what the recipe produces (first at x={first[0]}, y={first[1]})"); break
        else:
            c.fail("frame hash mismatch")
    for k, (_, rgba) in enumerate(frames):
        for p in _palette_problems(e, rgba):
            c.fail(f"frame {k}: {p}")
        if not c.ok:
            break


def verify(manifest_path: str, strict: bool = False, only: list[str] | None = None) -> tuple[list[Check], list[str]]:
    """Verify every entry (or only the given paths) and the manifest digest."""
    man = load(manifest_path)
    base = os.path.dirname(os.path.abspath(manifest_path))
    top = []
    if man.get("manifest_sha256") != sha256(canonical(man.get("assets", {}))):
        top.append("manifest_sha256 does not match its entries (the manifest was edited by hand)")
    checks = [verify_entry(rel, e, base, strict) for rel, e in sorted(man["assets"].items()) if not only or rel in only]
    return checks, top


def main_verify(manifest_path: str, strict: bool, as_json: bool, only=None) -> int:
    """The `verify` command: print a report (or JSON) and return 0 when everything passes."""
    checks, top = verify(manifest_path, strict, only)
    bad = [c for c in checks if not c.ok]
    if as_json:
        json.dump({"manifest": manifest_path, "ok": not bad and not top, "problems": top,
                   "assets": [c.__dict__ for c in checks]}, sys.stdout, indent=1, ensure_ascii=False)
        print()
    else:
        for c in checks:
            print(f"{'ok  ' if c.ok else 'FAIL'} {c.path}")
            for p in c.problems: print(f"     ✗ {p}")
            for w in c.warnings: print(f"     ! {w}")
        for p in top: print(f"FAIL {p}")
        print(f"{len(checks) - len(bad)}/{len(checks)} assets reproduced exactly" + ("" if not top else "; manifest digest broken"))
    return 1 if bad or top else 0
