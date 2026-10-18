"""
`exactfig selftest`: does this machine reproduce exactfig's results bit for bit?

Three checks, a few seconds in all, and a fourth on request:

  1. fmath   portable functions against IEEE 754 bit patterns fixed when they were written (sin, cos, atan2, exp, log, pow)
  2. render  small recipes of every kind (automaton, wave equation, epicycles, fractal, phase portrait, Fourier sums,
             logistic map, fBm terrain, annotations, MIDI) against the content hashes they gave when recorded
  3. repeat  the same recipe twice in this process gives the same bytes (no hidden state)
  4. gallery with --gallery: `verify --strict` on a manifest

A failure means this platform or Python computes something differently from the machines exactfig was checked on; the
report says which function or which generator. The expected values belong to the current generator versions: a change
that moves an output must bump that generator's version and update its line here (tests/test_selftest.py enforces it).
"""
from __future__ import annotations

from . import fmath
from .render import render

FMATH = [
    ("sin", (1.0,), "0x1.aed548f090ceep-1"),
    ("sin", (100000.0,), "0x1.24daa9c527e96p-5"),
    ("cos", (157.9,), "0x1.5d28e40602207p-1"),
    ("atan2", (1.0, -2.0), "0x1.56c6e7397f5aep+1"),
    ("exp", (-20.25,), "0x1.b93de1e27ca3bp-30"),
    ("log", (1e-300,), "-0x1.5963447f87fb5p+9"),
    ("log2", (10.0,), "0x1.a934f0979a371p+1"),
    ("pow", (0.3, 2.4), "0x1.c77e018c0c76ep-5"),
]

RECIPES = [
    ({"generator": "anim.life", "seed": "selftest", "palette": "sci", "size": [16, 12], "params": {"frames": 6}},
     "4580498b9c7899cb1857155b385b2ce2dd710cb94409ec1f732814988b8af025"),
    ({"generator": "anim.wave", "seed": "selftest", "palette": "sci", "size": [24, 16],
      "params": {"frames": 3, "every": 3, "sponge": 3}},
     "ee4d9c22bbd09f92d3d0eb46e9c7a95cde4c3986a9f5dcf68e2b1d88ae38a3ff"),
    ({"generator": "anim.epicycles", "seed": "selftest", "palette": "sci", "size": [24, 24],
      "params": {"samples": 32, "terms": 6, "frames": 3}},
     "6b3ea50275de00707715fb05c138525541d4d6ab356f302ac3561cd4ae7347a8"),
    ({"generator": "forge.fractal.julia", "seed": "selftest", "size": [24, 24]},
     "c66ec17aad3f862c8f1a0567eb8f81ce5c2dabf63766e472d5284e318e4266e3"),
    ({"generator": "math.domain", "seed": "selftest", "palette": "sci", "size": [24, 24]},
     "be46f2de5c7864762793aa63bb89ee4c587a8a6f8293da8bd2b340eff0b37dde"),
    ({"generator": "math.fourier", "seed": "selftest", "palette": "sci", "size": [40, 24], "params": {"orders": "1,9"}},
     "33341d708776d3f6e7a619bb2ecdab5d3e062e0206a8f410d5cd5feeed4c85cb"),
    ({"generator": "math.logistic", "seed": "selftest", "palette": "sci", "size": [32, 20],
      "params": {"warmup": 100, "samples": 60}},
     "1b7049532d5567ae143f42f64dc3a950614b6e4f508ff6b09194ed6b9e2424c6"),
    ({"generator": "forge.tile.terrain", "seed": "selftest", "size": [16, 16]},
     "3b8eced5e7553a52ccd4cddc3f2cef96359c5999857a4618c2af7e25687c9af4"),
    ({"generator": "draw.annotate", "seed": "selftest", "palette": "sci", "size": [24, 12],
      "params": {"shapes": [{"type": "text", "points": [[1, 1]], "text": "EXACT 0.2"},
                            {"type": "arrow", "points": [[2, 10], [20, 10]], "r": 3}]}},
     "1cd6235f544564c7ccdd37598096d2142ae0d61f11dcc6a028392f5a2ed410a9"),
    ({"generator": "music.piece", "seed": "selftest", "params": {"bars": 8, "source": "pisano"}},
     "ad56bb2cb6ad93af5107ac5cdcf49e55dd19f176e65ba1a48f3e1c6e13dc7c5e"),
]


def run(log=print, gallery: str | None = None) -> bool:
    """Run the checks, report each one through `log`, and return True when all pass."""
    ok = True
    for name, args, want in FMATH:
        got = getattr(fmath, name)(*args).hex()
        good = got == want
        ok &= good
        log(f"{'ok  ' if good else 'FAIL'} fmath.{name}{args}" + ("" if good else f": {got}, expected {want}"))
    first = None
    for recipe, want in RECIPES:
        try:
            got = render(recipe).content_sha256
        except Exception as ex:   # noqa: BLE001  (report, do not crash: this is a diagnostic)
            got = f"error: {ex}"
        good = got == want
        ok &= good
        log(f"{'ok  ' if good else 'FAIL'} {recipe['generator']}" + ("" if good else f": {got[:16]}…, expected {want[:16]}…"))
        first = first or recipe
    again = render(first).content_sha256 == render(first).content_sha256
    ok &= again
    log(f"{'ok  ' if again else 'FAIL'} the same recipe twice gives the same bytes")
    if gallery:
        from . import provenance
        checks, top = provenance.verify(gallery, strict=True)
        bad = [c for c in checks if not c.ok]
        good = not bad and not top
        ok &= good
        log(f"{'ok  ' if good else 'FAIL'} {gallery}: {len(checks) - len(bad)}/{len(checks)} assets reproduced exactly"
            + "".join(f"\n     ✗ {c.path}: {c.problems[0]}" for c in bad[:10]))
    log("all checks passed: this machine reproduces exactfig bit for bit" if ok else "some checks FAILED (see above)")
    return ok
