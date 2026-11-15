"""Misuse bench: runs the command line on inputs a real user can produce by mistake and reports every case that ends in
a Python traceback, an unexpected exit code, or a hang, instead of a one-line `exactfig: …` message.

    python tests/misuse_bench.py            # prints one line per case and a summary; exit 1 if any case misbehaves

It is also run by tests/test_misuse.py. Each case is a separate process, as a user would run it."""
from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
GALLERY = os.path.join(ROOT, "gallery")
OK_CODES = (0, 1, 2)
# Cases a user can legitimately run, which must SUCCEED; every other case must FAIL with a one-line message.
SHOULD_WORK = {
    "recipe with UTF-8 BOM (Notepad)", "recipe in UTF-16 (PowerShell >)", "csv constant", "csv one cell",
    "csv CRLF and BOM", "csv UTF-16", "catalog does not fit in a tiny size but cells of 1 px still fit",
    "record into a folder that does not exist", "folder with non-ASCII name",
}
GOOD ={"generator": "math.ulam", "seed": "x", "palette": "sci", "size": [21, 21], "output": "u.png"}


def _png(w, h, raw: bytes, corrupt=False) -> bytes:
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    data = zlib.compress(raw)
    if corrupt:
        data = data[: len(data) // 2]
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", data) + chunk(b"IEND", b"")


def field(path, fmt=None):
    inp = {"path": path}
    if fmt:
        inp["format"] = fmt
    return {"generator": "data.field", "seed": "x", "palette": "sci", "size": [16, 16], "input": inp, "output": "f.png"}


def cases():
    """(name, files {relative path: bytes or str}, argv after `exactfig`)."""
    j = json.dumps
    yield "recipe file missing", {}, ["render", "nope.json"]
    yield "recipe not JSON", {"r.json": "{generator: ulam"}, ["render", "r.json"]
    yield "recipe is a list", {"r.json": "[1, 2]"}, ["render", "r.json"]
    yield "recipe is a number", {"r.json": "7"}, ["render", "r.json"]
    yield "recipe empty file", {"r.json": ""}, ["render", "r.json"]
    yield "recipe with UTF-8 BOM (Notepad)", {"r.json": b"\xef\xbb\xbf" + j(GOOD).encode()}, ["render", "r.json"]
    yield "recipe in UTF-16 (PowerShell >)", {"r.json": "﻿".encode("utf-16-le") + j(GOOD).encode("utf-16-le")}, ["render", "r.json"]
    yield "recipe in Latin-1", {"r.json": json.dumps(dict(GOOD, seed="año"), ensure_ascii=False).encode("latin-1")}, ["render", "r.json"]
    yield "unknown generator", {"r.json": j(dict(GOOD, generator="math.nope"))}, ["render", "r.json"]
    yield "generator not a string", {"r.json": j(dict(GOOD, generator=5))}, ["render", "r.json"]
    yield "no generator", {"r.json": j({"seed": 1})}, ["render", "r.json"]
    yield "params is a list", {"r.json": j(dict(GOOD, params=[1]))}, ["render", "r.json"]
    yield "unknown param", {"r.json": j(dict(GOOD, params={"zzz": 1}))}, ["render", "r.json"]
    yield "param of wrong type", {"r.json": j(dict(GOOD, params={"modulus": "six"}))}, ["render", "r.json"]
    yield "param NaN", {"r.json": '{"generator": "math.modmult", "seed": "x", "palette": "sci", "size": [24, 24], "params": {"k": NaN}, "output": "m.png"}'}, ["render", "r.json"]
    yield "param Infinity", {"r.json": '{"generator": "math.modmult", "seed": "x", "palette": "sci", "size": [24, 24], "params": {"k": Infinity}, "output": "m.png"}'}, ["render", "r.json"]
    yield "size zero", {"r.json": j(dict(GOOD, size=[0, 0]))}, ["render", "r.json"]
    yield "size negative", {"r.json": j(dict(GOOD, size=[-5, 10]))}, ["render", "r.json"]
    yield "size huge", {"r.json": j(dict(GOOD, size=[10 ** 9, 10 ** 9]))}, ["render", "r.json"]
    yield "size floats", {"r.json": j(dict(GOOD, size=[20.5, 20]))}, ["render", "r.json"]
    yield "size a string", {"r.json": j(dict(GOOD, size="21x21"))}, ["render", "r.json"]
    yield "size one number", {"r.json": j(dict(GOOD, size=[21]))}, ["render", "r.json"]
    yield "scale huge", {"r.json": j(dict(GOOD, scale=10 ** 6))}, ["render", "r.json"]
    yield "unknown palette", {"r.json": j(dict(GOOD, palette="rainbow"))}, ["render", "r.json"]
    yield "palette object malformed", {"r.json": j(dict(GOOD, palette={"name": "x"}))}, ["render", "r.json"]
    yield "seed is a list", {"r.json": j(dict(GOOD, seed=[1]))}, ["render", "r.json"]
    yield "output leaves the folder", {"r.json": j(dict(GOOD, output="../escape.png"))}, ["render", "r.json"]
    yield "output absolute path", {"r.json": j(dict(GOOD, output="/tmp/abs.png"))}, ["render", "r.json"]
    yield "output odd extension", {"r.json": j(dict(GOOD, output="u.bmp"))}, ["render", "r.json"]
    yield "out-dir is a file", {"r.json": j(GOOD), "afile": "x"}, ["render", "r.json", "--out-dir", "afile"]
    yield "data input missing", {"r.json": j(field("nope.csv"))}, ["render", "r.json"]
    yield "data input wrong hash", {"r.json": j(dict(field("d.csv"), input={"path": "d.csv", "sha256": "0" * 64})), "d.csv": "1,2\n3,4\n"}, ["render", "r.json"]
    yield "csv ragged", {"r.json": j(field("d.csv")), "d.csv": "1,2,3\n4,5\n"}, ["render", "r.json"]
    yield "csv words", {"r.json": j(field("d.csv")), "d.csv": "a,b\nc,d\n"}, ["render", "r.json"]
    yield "csv empty", {"r.json": j(field("d.csv")), "d.csv": ""}, ["render", "r.json"]
    yield "csv all missing", {"r.json": j(field("d.csv")), "d.csv": "nan,nan\nnan,nan\n"}, ["render", "r.json"]
    yield "csv constant", {"r.json": j(field("d.csv")), "d.csv": "3,3\n3,3\n"}, ["render", "r.json"]
    yield "csv one cell", {"r.json": j(field("d.csv")), "d.csv": "3\n"}, ["render", "r.json"]
    yield "csv CRLF and BOM", {"r.json": j(field("d.csv")), "d.csv": b"\xef\xbb\xbf1,2\r\n3,4\r\n"}, ["render", "r.json"]
    yield "csv UTF-16", {"r.json": j(field("d.csv")), "d.csv": "1,2\n3,4\n".encode("utf-16")}, ["render", "r.json"]
    yield "csv decimal comma", {"r.json": j(field("d.csv")), "d.csv": "1,5;2,5\n3,5;4,5\n"}, ["render", "r.json"]
    yield "npy truncated", {"r.json": j(field("d.npy")), "d.npy": b"\x93NUMPY\x01\x00v\x00{'descr': '<f8', 'fortran_order': False, 'shape': (4, 4), }" + b" " * 40 + b"\n" + b"\x00" * 10}, ["render", "r.json"]
    yield "npy garbage", {"r.json": j(field("d.npy")), "d.npy": b"\x93NUMPY" + os.urandom(64)}, ["render", "r.json"]
    yield "pgm truncated", {"r.json": j(field("d.pgm")), "d.pgm": b"P5\n4 4\n255\n\x00\x01"}, ["render", "r.json"]
    yield "pgm garbage header", {"r.json": j(field("d.pgm")), "d.pgm": b"P5\nxx yy\n255\n"}, ["render", "r.json"]
    yield "json grid ragged", {"r.json": j(field("d.json")), "d.json": j({"values": [[1, 2], [3]]})}, ["render", "r.json"]
    yield "json grid nested wrong", {"r.json": j(field("d.json")), "d.json": j({"values": [[[1]]]})}, ["render", "r.json"]
    yield "scatter too few points", {"r.json": j({"generator": "data.scatter", "seed": "x", "palette": "sci", "size": [16, 16], "input": {"path": "p.csv"}, "output": "s.png"}), "p.csv": "0,0,1\n1,1,2\n"}, ["render", "r.json"]
    yield "scatter collinear points", {"r.json": j({"generator": "data.scatter", "seed": "x", "palette": "sci", "size": [16, 16], "input": {"path": "p.csv"}, "output": "s.png"}), "p.csv": "0,0,1\n1,1,2\n2,2,3\n3,3,4\n"}, ["render", "r.json"]
    yield "scatter duplicate points", {"r.json": j({"generator": "data.scatter", "seed": "x", "palette": "sci", "size": [16, 16], "input": {"path": "p.csv"}, "output": "s.png"}), "p.csv": "0,0,1\n0,0,2\n1,0,3\n0,1,4\n"}, ["render", "r.json"]
    img = {"generator": "data.image", "seed": "x", "palette": "sci", "size": [8, 8], "input": {"path": "i.png"}, "output": "i2.png"}
    yield "png corrupt data", {"r.json": j(img), "i.png": _png(4, 4, b"\x00" + b"\x00" * 12, corrupt=True)}, ["render", "r.json"]
    yield "png truncated", {"r.json": j(img), "i.png": _png(4, 4, (b"\x00" + b"\x00" * 12) * 4)[:40]}, ["render", "r.json"]
    yield "png not a png", {"r.json": j(img), "i.png": b"GIF89a....."}, ["render", "r.json"]
    yield "png huge declared size", {"r.json": j(img), "i.png": _png(100000, 100000, b"\x00")}, ["render", "r.json"]
    cat = {"generator": "data.catalog", "seed": "x", "palette": "sci", "size": [64, 64], "input": {"path": "c.txt", "format": "catalog"}, "params": {"count": 1}, "output": "c.png"}
    yield "catalog binary", {"r.json": j(cat), "c.txt": os.urandom(200)}, ["render", "r.json"]
    yield "catalog wrong format name", {"r.json": j(dict(cat, input={"path": "c.txt", "format": "cells"})), "c.txt": "2x2: OO OO\n"}, ["render", "r.json"]
    yield "catalog without format", {"r.json": j(dict(cat, input={"path": "c.txt"})), "c.txt": "2x2: OO OO\n"}, ["render", "r.json"]
    yield "catalog does not fit in a tiny size but cells of 1 px still fit", {"r.json": j(dict(cat, size=[4, 4])), "c.txt": "2x2: OO OO\n"}, ["render", "r.json"]
    yield "catalog does not fit", {"r.json": j(dict(cat, size=[3, 3])), "c.txt": "2x2: OO OO\n"}, ["render", "r.json"]
    yield "catalog bad rule", {"r.json": j(dict(cat, params={"rule": "life"})), "c.txt": "2x2: OO OO\n"}, ["render", "r.json"]
    yield "catalog wrong term", {"r.json": j(dict(cat, params={"count": 2})), "c.txt": "2x2: OO OO\n"}, ["render", "r.json"]
    yield "catalog many islands strict", {"r.json": j(dict(cat, size=[256, 64], params={"strict": True})), "c.txt": "39x2: " + " ".join(["OO." * 13] * 2) + "\n"}, ["render", "r.json"]
    colr = {"generator": "data.coloring", "seed": "x", "palette": "sci", "size": [64, 8], "input": {"path": "c.txt", "format": "coloring"}, "params": {"lengths": "3"}, "output": "k.png"}
    yield "coloring with a letter", {"r.json": j(colr), "c.txt": "01x10\n"}, ["render", "r.json"]
    yield "coloring that is not a witness", {"r.json": j(colr), "c.txt": "000\n"}, ["render", "r.json"]
    yield "coloring lengths not numbers", {"r.json": j(dict(colr, params={"lengths": "three"})), "c.txt": "0110\n"}, ["render", "r.json"]
    yield "coloring proof hash malformed", {"r.json": j(dict(colr, params={"proof_sha256": "abc"})), "c.txt": "0110\n"}, ["render", "r.json"]
    yield "coloring of 5000 numbers on one row", {"r.json": j(colr), "c.txt": "01" * 2500 + "\n"}, ["render", "r.json"]
    inst = {"generator": "data.instances", "seed": "x", "palette": "sci", "size": [8, 8], "input": {"path": "i.json", "format": "instances"}, "params": {"mode": "instances"}, "output": "i.png"}
    yield "instances overlapping", {"r.json": j(inst), "i.json": j({"width": 4, "height": 4, "truth": [{"cells": [[0, 0], [1, 0]]}, {"cells": [[1, 0]]}]})}, ["render", "r.json"]
    yield "instances empty mask", {"r.json": j(inst), "i.json": j({"width": 4, "height": 4, "truth": [{"size": [4, 4], "counts": [16]}]})}, ["render", "r.json"]
    yield "instances RLE of the wrong size", {"r.json": j(inst), "i.json": j({"width": 4, "height": 4, "truth": [{"size": [5, 4], "counts": [20]}]})}, ["render", "r.json"]
    yield "instances RLE string damaged", {"r.json": j(inst), "i.json": j({"width": 4, "height": 4, "truth": [{"size": [4, 4], "counts": "1o"}]})}, ["render", "r.json"]
    yield "instances not an object", {"r.json": j(inst), "i.json": "[1, 2]"}, ["render", "r.json"]
    yield "instances compare without prediction", {"r.json": j(dict(inst, params={"mode": "compare"})), "i.json": j({"width": 4, "height": 4, "truth": [{"cells": [[0, 0]]}]})}, ["render", "r.json"]
    yield "instances caption that the data contradicts", {"r.json": j(dict(inst, params={"expect": "date=2020"})), "i.json": j({"width": 4, "height": 4, "meta": {"date": "2019"}, "truth": [{"cells": [[0, 0]]}]})}, ["render", "r.json"]
    yield "instances image too large", {"r.json": j(inst), "i.json": j({"width": 100000, "height": 100000, "truth": []})}, ["render", "r.json"]
    yield "animation too many pixels", {"r.json": j({"generator": "anim.life", "seed": "x", "palette": "sci", "size": [1024, 1024], "params": {"frames": 1000}, "output": "l.gif"})}, ["render", "r.json"]
    yield "animation odd delay", {"r.json": j({"generator": "anim.life", "seed": "x", "palette": "sci", "size": [16, 16], "params": {"delay": 33, "frames": 2}, "output": "l.gif"})}, ["render", "r.json"]
    yield "verify manifest missing", {}, ["verify", "--manifest", "nope.json"]
    yield "verify manifest not JSON", {"m.json": "not json"}, ["verify", "--manifest", "m.json"]
    yield "verify manifest wrong shape", {"m.json": j({"format": "x"})}, ["verify", "--manifest", "m.json"]
    yield "verify manifest assets not a dict", {"m.json": j({"format": "exactfig.manifest/1", "assets": [1]})}, ["verify", "--manifest", "m.json"]
    yield "verify unknown path", {}, ["verify", "nope.png", "--manifest", os.path.join(GALLERY, "manifest.json")]
    yield "record into a folder that does not exist", {"r.json": j(GOOD)}, ["record", "r.json", "--manifest", "no/such/dir/m.json"]
    yield "record a manifest that is not JSON", {"r.json": j(GOOD), "m.json": "garbage"}, ["record", "r.json", "--manifest", "m.json"]
    yield "edit malformed --set", {"r.json": j(GOOD)}, ["edit", "r.json", "--set", "noequals"]
    yield "edit unknown key", {"r.json": j(GOOD)}, ["edit", "r.json", "--set", "params.zzz=1"]
    yield "edit bad value", {"r.json": j(GOOD)}, ["edit", "r.json", "--set", "size=[a"]
    yield "palette missing image", {}, ["palette", "nope.png", "--k", "4"]
    yield "palette k out of range", {}, ["palette", "nope.png", "--k", "1"]
    yield "video missing ffmpeg or recipe", {"r.json": j({"generator": "anim.life", "seed": "x", "palette": "sci", "size": [16, 16], "params": {"frames": 2}, "output": "l.gif"})}, ["video", "r.json", "--out", "v.mp4"]
    yield "video of a still image", {"r.json": j(GOOD)}, ["video", "r.json", "--out", "v.mp4"]
    yield "no command", {}, []
    yield "unknown command", {}, ["paint"]
    yield "folder with non-ASCII name", {"carpeta ñ é/r.json": j(GOOD)}, ["render", "carpeta ñ é/r.json", "--out-dir", "carpeta ñ é"]


def run_all(verbose=True, timeout=120):
    bad = []
    env = dict(os.environ, PYTHONPATH=ROOT + os.pathsep + os.environ.get("PYTHONPATH", ""), PYTHONIOENCODING="utf-8",
               PATH=os.environ.get("PATH", "") if os.environ.get("EXACTFIG_BENCH_FFMPEG") else "")
    for name, files, argv in cases():
        d = tempfile.mkdtemp(prefix="exactfig-misuse-")
        try:
            for rel, data in files.items():
                p = os.path.join(d, rel)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "wb") as fh:
                    fh.write(data if isinstance(data, bytes) else data.encode("utf-8"))
            try:
                pr = subprocess.run([sys.executable, "-m", "exactfig"] + argv, cwd=d, env=env, capture_output=True,
                                    timeout=timeout)
                err = pr.stderr.decode("utf-8", "replace")
                problem = None
                if "Traceback" in err:
                    problem = "traceback: " + err.strip().splitlines()[-1]
                elif pr.returncode not in OK_CODES:
                    problem = f"exit code {pr.returncode}"
                elif name in SHOULD_WORK and pr.returncode != 0:
                    problem = "should work, failed: " + (err.strip().splitlines() or [""])[-1]
                elif name not in SHOULD_WORK and pr.returncode == 0:
                    problem = "should be refused, ran"
                elif name not in SHOULD_WORK and "exactfig" not in (err.strip().splitlines() or [""])[-1]:
                    problem = "refused without an exactfig message"
                msg = (err.strip().splitlines() or [""])[-1][:150]
            except subprocess.TimeoutExpired:
                problem, msg = f"hang (> {timeout} s)", ""
            if problem:
                bad.append((name, problem))
            if verbose:
                print(("FAIL " if problem else "ok   ") + f"{name:42s} " + (problem or msg), flush=True)
        finally:
            shutil.rmtree(d, ignore_errors=True)
    return bad


if __name__ == "__main__":
    bad = run_all()
    print(f"\n{len(bad)} case(s) misbehave" if bad else "\nevery case ends in a clear message")
    sys.exit(1 if bad else 0)
