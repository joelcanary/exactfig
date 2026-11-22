"""
SVG output: the same pixels as the PNG, with the provenance inside / salida SVG: los mismos píxeles, con su procedencia.

A recorded figure can be written as `.svg` instead of `.png`. The picture is the same grid of palette colours: each
colour is one `<path>` of axis-aligned rectangles (runs of a row, merged with identical runs of the rows below), drawn
with `shape-rendering="crispEdges"` in a `viewBox` of the unscaled grid, so it scales to any size without blur and
decodes back to exactly the pixels the PNG would have (`content_sha256` is the same for both). Inside the file:

  <title> and <desc>   the figure's exact alternative text (forge/describe.py), which screen readers announce
  <metadata>           exactfig's provenance as JSON: the normal-form recipe and its SHA-256, the generator's name,
                       version and source hash, the exactfig version, every input file's path and SHA-256, and the
                       content hash of the pixels

`decode` reads back only what `encode` writes (an XML prolog, one `<svg>` with width, height and viewBox, `<title>`,
`<desc>`, one `<metadata>`, and `<path fill="#rrggbb" d="M x y h w v h h -w z …"/>` elements whose rectangles do not
overlap); anything else is refused, so a hand-edited or foreign SVG cannot pass for one. `exactfig verify` decodes it,
compares the pixels and checks that the embedded provenance is the manifest's. Pure functions: bytes in, bytes out.
"""
from __future__ import annotations

import json
import re

FORMAT = "exactfig.svg/1"
NS = "https://github.com/joelcanary/exactfig"
MAX_PIXELS = 64 * 1024 * 1024


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _rects(w: int, h: int, px) -> dict:
    """{colour index: [(x, y, width, height)]}: row runs, merged downwards while the rows below repeat them."""
    out, open_ = {}, {}
    for y in range(h + 1):
        runs = set()
        if y < h:
            row, x = px[y], 0
            while x < w:
                c = row[x]
                x0 = x
                while x < w and row[x] == c:
                    x += 1
                if c is not None:
                    runs.add((x0, x - x0, c))
        for key in [k for k in open_ if k not in runs]:
            x0, rw, c = key
            out.setdefault(c, []).append((x0, open_.pop(key), rw, y - 0))
        for key in runs:
            open_.setdefault(key, y)
    return {c: sorted((x, y0, rw, y1 - y0) for x, y0, rw, y1 in rs) for c, rs in out.items()}


def encode(w: int, h: int, px, palette_hex: list, scale: int = 1, alt: str = "", meta: dict | None = None) -> bytes:
    """The SVG of a w×h grid of palette indices (None = transparent), drawn `scale` times larger."""
    rects = _rects(w, h, px)
    title = alt.split(". ")[0].rstrip(".") + "." if alt else "exactfig figure"
    blob = json.dumps(dict(meta or {}, format=FORMAT), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    blob = blob.replace("]]>", "]]]]><![CDATA[>")
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<svg xmlns="http://www.w3.org/2000/svg" width="{w * scale}" height="{h * scale}" viewBox="0 0 {w} {h}" '
             f'shape-rendering="crispEdges" role="img" aria-labelledby="t d">',
             f'<title id="t">{_esc(title)}</title>',
             f'<desc id="d">{_esc(alt)}</desc>',
             f'<metadata><exactfig:provenance xmlns:exactfig="{NS}"><![CDATA[{blob}]]></exactfig:provenance></metadata>']
    for c in sorted(rects):
        d = "".join(f"M{x} {y}h{rw}v{rh}h-{rw}z" for x, y, rw, rh in rects[c])
        lines.append(f'<path fill="{palette_hex[c]}" d="{d}"/>')
    lines.append("</svg>")
    return ("\n".join(lines) + "\n").encode("utf-8")


_SVG = re.compile(r'<svg xmlns="http://www\.w3\.org/2000/svg" width="(\d+)" height="(\d+)" viewBox="0 0 (\d+) (\d+)" '
                  r'shape-rendering="crispEdges" role="img" aria-labelledby="t d">')
_PATH = re.compile(r'<path fill="#([0-9a-f]{6})" d="((?:M\d+ \d+h\d+v\d+h-\d+z)*)"/>')
_RECT = re.compile(r"M(\d+) (\d+)h(\d+)v(\d+)h-(\d+)z")
_META = re.compile(r'<metadata><exactfig:provenance xmlns:exactfig="' + re.escape(NS) +
                   r'"><!\[CDATA\[(.*?)\]\]></exactfig:provenance></metadata>', re.S)


def decode(data: bytes) -> tuple[int, int, bytes, dict, str]:
    """(width, height, RGBA8 of the scaled picture, provenance dict, alternative text); ValueError for anything that
    is not exactly what encode writes."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("not an exactfig SVG (not UTF-8)") from None
    lines = text.rstrip("\n").split("\n")
    if len(lines) < 6 or lines[0] != '<?xml version="1.0" encoding="UTF-8"?>' or lines[-1] != "</svg>":
        raise ValueError("not an exactfig SVG (prolog or closing tag)")
    m = _SVG.fullmatch(lines[1])
    if not m:
        raise ValueError("not an exactfig SVG (the <svg> element is not the one exactfig writes)")
    W, H, w, h = (int(v) for v in m.groups())
    if not w or not h or W % w or H % h or W // w != H // h:
        raise ValueError("not an exactfig SVG (width and height must be the viewBox times one integer scale)")
    scale = W // w
    if W * H > MAX_PIXELS:
        raise ValueError(f"SVG of {W}x{H} pixels is larger than {MAX_PIXELS}")
    t = re.fullmatch(r'<title id="t">([^<]*)</title>', lines[2])
    d = re.fullmatch(r'<desc id="d">([^<]*)</desc>', lines[3])
    mm = _META.fullmatch(lines[4])
    if not (t and d and mm):
        raise ValueError("not an exactfig SVG (title, desc or metadata)")
    try:
        meta = json.loads(mm.group(1).replace("]]]]><![CDATA[>", "]]>"))
    except ValueError:
        raise ValueError("the SVG's provenance is not valid JSON") from None
    if meta.get("format") != FORMAT:
        raise ValueError(f"the SVG's provenance is not {FORMAT}")
    alt = d.group(1).replace("&quot;", '"').replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&")
    grid = [[None] * w for _ in range(h)]
    for line in lines[5:-1]:
        pm = _PATH.fullmatch(line)
        if not pm:
            raise ValueError(f"not an exactfig SVG (unexpected element: {line[:60]})")
        rgb = bytes.fromhex(pm.group(1))
        for rm in _RECT.finditer(pm.group(2)):
            x, y, rw, rh, back = (int(v) for v in rm.groups())
            if back != rw or rw < 1 or rh < 1 or x + rw > w or y + rh > h:
                raise ValueError("not an exactfig SVG (a rectangle is malformed or outside the picture)")
            for yy in range(y, y + rh):
                row = grid[yy]
                for xx in range(x, x + rw):
                    if row[xx] is not None:
                        raise ValueError(f"not an exactfig SVG (rectangles overlap at x={xx}, y={yy})")
                    row[xx] = rgb
    out = bytearray(W * H * 4)
    for yy in range(H):
        src = grid[yy // scale]
        base = yy * W * 4
        for xx in range(W):
            c = src[xx // scale]
            if c is not None:
                i = base + xx * 4
                out[i:i + 3] = c
                out[i + 3] = 255
    return W, H, bytes(out), meta, alt
