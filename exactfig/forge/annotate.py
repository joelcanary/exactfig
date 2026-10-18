"""
Annotations: vector marks drawn on a transparent canvas, meant as the top layer of a `compose` figure.

Each shape is a small object (the schema caps their number, points and text, so annotations cannot carry a picture):

  {"type": "line",     "points": [[x0, y0], [x1, y1]]}
  {"type": "polyline", "points": [[x, y], …]}            open path
  {"type": "polygon",  "points": [[x, y], …], "fill": b}  closed path, optionally filled
  {"type": "rect",     "points": [[x0, y0], [x1, y1]], "fill": b}
  {"type": "circle",   "points": [[cx, cy]], "r": radius, "fill": b}
  {"type": "marker",   "points": [[x, y], …], "r": arm}    a cross at each point
  {"type": "arrow",    "points": [[x0, y0], [x1, y1]], "r": head length}
  {"type": "text",     "points": [[x, y]], "text": "T = 0.5", "r": size}   top-left corner; 3×5 font, size = pixel scale
  {"type": "scalebar", "points": [[x, y]], "r": length, "text": "10 KM"}  a bar of `r` pixels with ticks and a label

Every shape takes "ramp" (the palette ramp whose first colour it uses, default "ink"). Coordinates are pixels of the native
canvas, x to the right and y down, unless "units": "unit" is given on the shape, in which case (0, 0) is the top-left corner
and (1, 1) the bottom-right one.
"""
from __future__ import annotations

from .. import fmath as fm
from ..pixel.canvas import Canvas

# A 3×5 bitmap font designed for this project: five rows of three cells per glyph, '#' = ink, '.' = empty.
FONT = {
    '0': '### #.# #.# #.# ###', '1': '.#. ##. .#. .#. ###', '2': '### ..# ### #.. ###', '3': '### ..# ### ..# ###', '4': '#.# #.# ### ..# ..#',
    '5': '### #.. ### ..# ###', '6': '### #.. ### #.# ###', '7': '### ..# ..# ..# ..#', '8': '### #.# ### #.# ###', '9': '### #.# ### ..# ###',
    'A': '.#. #.# ### #.# #.#', 'B': '##. #.# ##. #.# ##.', 'C': '### #.. #.. #.. ###', 'D': '##. #.# #.# #.# ##.', 'E': '### #.. ### #.. ###',
    'F': '### #.. ### #.. #..', 'G': '### #.. #.# #.# ###', 'H': '#.# #.# ### #.# #.#', 'I': '### .#. .#. .#. ###', 'J': '..# ..# ..# #.# ###',
    'K': '#.# #.# ##. #.# #.#', 'L': '#.. #.. #.. #.. ###', 'M': '#.# ### ### #.# #.#', 'N': '##. #.# #.# #.# #.#', 'O': '### #.# #.# #.# ###',
    'P': '### #.# ### #.. #..', 'Q': '### #.# #.# ### ..#', 'R': '##. #.# ##. #.# #.#', 'S': '### #.. ### ..# ###', 'T': '### .#. .#. .#. .#.',
    'U': '#.# #.# #.# #.# ###', 'V': '#.# #.# #.# #.# .#.', 'W': '#.# #.# ### ### #.#', 'X': '#.# #.# .#. #.# #.#', 'Y': '#.# #.# .#. .#. .#.',
    'Z': '### ..# .#. #.. ###', ' ': '... ... ... ... ...', '.': '... ... ... ... .#.', ',': '... ... ... .#. #..', ':': '... .#. ... .#. ...',
    '-': '... ... ### ... ...', '+': '... .#. ### .#. ...', '/': '..# ..# .#. #.. #..', '(': '.#. #.. #.. #.. .#.', ')': '.#. ..# ..# ..# .#.',
    '=': '... ### ... ### ...', '%': '#.# ..# .#. #.. #.#', "'": '.#. .#. ... ... ...', '!': '.#. .#. .#. ... .#.', '?': '### ..# .#. ... .#.',
    '<': '..# .#. #.. .#. ..#', '>': '#.. .#. ..# .#. #..', '_': '... ... ... ... ###', '*': '... #.# .#. #.# ...', '#': '#.# ### #.# ### #.#',
}
FONT = {ch: glyph.replace(" ", "") for ch, glyph in FONT.items()}   # 15 cells, row by row


def text_width(s: str, size: int = 1) -> int:
    """Width in pixels of `s` in the 3×5 font at the given pixel size (4 columns per character, minus one)."""
    return max(0, 4 * len(s) - 1) * size


def _pt(p, w, h, unit):
    return (p[0] * (w - 1), p[1] * (h - 1)) if unit else (p[0], p[1])


def _text(cv, x, y, s, size, c):
    for k, ch in enumerate(s.upper()):
        glyph = FONT.get(ch, FONT["?"])
        for j in range(5):
            for i in range(3):
                if glyph[j * 3 + i] == "#":
                    for dy in range(size):
                        for dx in range(size):
                            cv.set(x + (4 * k + i) * size + dx, y + j * size + dy, c)


def annotate(seed, pal, w, h, p) -> Canvas:
    """Draw the recipe's shapes, in order, on a transparent canvas."""
    cv = Canvas(w, h, pal)
    for s in p["shapes"]:
        c = pal.ramp(s.get("ramp", "ink"))[0]
        unit = s.get("units") == "unit"
        pts = [_pt(q, w, h, unit) for q in s.get("points", [])]
        r = s.get("r", 1)
        r = r * min(w - 1, h - 1) if unit and s["type"] in ("circle", "scalebar") else r
        t = s["type"]
        if t in ("line", "polyline", "arrow"):
            for a, b in zip(pts, pts[1:]):
                cv.line(a[0], a[1], b[0], b[1], c)
            if t == "arrow":
                (x0, y0), (x1, y1) = pts[0], pts[-1]
                ang = fm.atan2(y1 - y0, x1 - x0)
                for side in (-1.0, 1.0):
                    a = ang + fm.pi - side * 0.45
                    cv.line(x1, y1, x1 + r * fm.cos(a), y1 + r * fm.sin(a), c)
        elif t == "polygon":
            if s.get("fill"):
                cv.polygon(pts, c)
            for a, b in zip(pts, pts[1:] + pts[:1]):
                cv.line(a[0], a[1], b[0], b[1], c)
        elif t == "rect":
            (x0, y0), (x1, y1) = pts
            if s.get("fill"):
                cv.rect(x0, y0, x1, y1, c)
            for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
                cv.line(a[0], a[1], b[0], b[1], c)
        elif t == "circle":
            (cx, cy), = pts
            (cv.disc if s.get("fill") else cv.circle)(cx, cy, int(fm.floor(r + 0.5)), c)
        elif t == "marker":
            arm = max(1, int(r))
            for x, y in pts:
                cv.line(x - arm, y, x + arm, y, c)
                cv.line(x, y - arm, x, y + arm, c)
        elif t == "text":
            (x, y), = pts
            _text(cv, int(fm.floor(x + 0.5)), int(fm.floor(y + 0.5)), s.get("text", ""), max(1, int(r)), c)
        elif t == "scalebar":
            (x, y), = pts
            length = int(fm.floor(r + 0.5))
            cv.line(x, y, x + length, y, c)
            cv.line(x, y - 2, x, y + 2, c)
            cv.line(x + length, y - 2, x + length, y + 2, c)
            label = s.get("text", "")
            if label:
                _text(cv, int(x + (length - text_width(label)) / 2), int(y) - 8, label, 1, c)
    return cv
