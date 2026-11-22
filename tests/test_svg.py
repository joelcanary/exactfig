"""SVG output (pixel/svg.py): the same pixels as the PNG, the provenance inside, and nothing else accepted.

- for several gallery recipes (data, a fractal, transparency, scale > 1) the SVG decodes to exactly the RGBA of the
  PNG, so both have the same content_sha256; the bytes are the same on a second render;
- it is well-formed XML (parsed by the standard library), <title> and <desc> carry the exact alternative text, and the
  embedded provenance has the recipe's SHA-256 computed here from its normal form;
- recorded, it verifies with --strict; a fill changed by hand, the recipe hash changed in the metadata, an extra
  element and overlapping rectangles are all refused."""
import json
import os
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig import provenance  # noqa: E402
from exactfig.pixel import png, svg  # noqa: E402
from exactfig.render import canonical, normalize, render, sha256  # noqa: E402

GALLERY = os.path.join(os.path.abspath(ROOT), "gallery")
RECIPES = os.path.join(os.path.abspath(ROOT), "examples", "recipes")


def recipe(name):
    with open(os.path.join(RECIPES, name + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


class TestSvg(unittest.TestCase):
    def test_same_pixels_as_png(self):
        for name in ("mod3-n3-circuit", "pratt-m127", "julia", "gem-round", "franke-linear"):
            r = recipe(name)
            a = render(dict(r, output="x.png"), GALLERY)
            b = render(dict(r, output="x.svg"), GALLERY)
            self.assertEqual(a.content_sha256, b.content_sha256, name)
            W, H, rgba, meta, alt = svg.decode(b.data)
            self.assertEqual((W, H, rgba), png.decode(a.data), name)
            self.assertEqual(b.data, render(dict(r, output="x.svg"), GALLERY).data, name)
            self.assertEqual(alt, b.alt, name)
            self.assertEqual(meta["recipe_sha256"], sha256(canonical(normalize(r, GALLERY))), name)

    def test_xml_title_desc(self):
        out = render(dict(recipe("mod3-circuit"), output="x.svg"), GALLERY)
        root = ET.fromstring(out.data)
        ns = "{http://www.w3.org/2000/svg}"
        self.assertTrue(out.alt.startswith(root.find(ns + "title").text[:-1]))
        self.assertEqual(root.find(ns + "desc").text, out.alt)
        self.assertEqual(root.get("role"), "img")

    def test_record_verify_and_tampering(self):
        d = tempfile.mkdtemp(prefix="exactfig-svg-")
        try:
            os.makedirs(os.path.join(d, "data"))
            shutil.copy(os.path.join(GALLERY, "data", "mod3-1-n3.circuit"), os.path.join(d, "data"))
            path = os.path.join(d, "r.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(dict(recipe("mod3-n3-circuit"), output="c.svg"), fh)
            man = os.path.join(d, "manifest.json")
            provenance.record([path], man, log=lambda *a, **k: None)
            checks, top = provenance.verify(man, strict=True)
            self.assertTrue(all(c.ok for c in checks) and not top, [c.problems for c in checks])
            f = os.path.join(d, "c.svg")
            with open(f, "rb") as fh:
                good = fh.read()

            def check_with(data):
                with open(f, "wb") as fh:
                    fh.write(data)
                cs, _ = provenance.verify(man, strict=False)
                return cs[0]

            text = good.decode()
            first_fill = text[text.index('fill="#') + 7:text.index('fill="#') + 13]
            c = check_with(text.replace(f'fill="#{first_fill}"', 'fill="#123456"', 1).encode())
            self.assertFalse(c.ok)
            meta_sha = json.loads(text[text.index("<![CDATA[") + 9:text.index("]]>")])["recipe_sha256"]
            c = check_with(text.replace(meta_sha, "0" * 64).encode())
            self.assertFalse(c.ok)
            self.assertTrue(any("provenance inside the SVG" in p for p in c.problems), c.problems)
            c = check_with(text.replace("</svg>", '<rect x="0" y="0" width="5" height="5"/>\n</svg>').encode())
            self.assertFalse(c.ok)
            with open(f, "wb") as fh:
                fh.write(good)
            self.assertTrue(all(ch.ok for ch in provenance.verify(man, strict=True)[0]))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_decoder_refuses(self):
        good = svg.encode(2, 1, [[0, 1]], ["#000000", "#ffffff"], 1, "Two squares.", {"x": 1})
        svg.decode(good)
        overlap = good.decode().replace('d="M1 0h1v1h-1z"', 'd="M0 0h2v1h-2z"').encode()
        with self.assertRaisesRegex(ValueError, "overlap"):
            svg.decode(overlap)
        with self.assertRaisesRegex(ValueError, "outside"):
            svg.decode(good.decode().replace('d="M1 0h1v1h-1z"', 'd="M1 0h5v1h-5z"').encode())
        with self.assertRaises(ValueError):
            svg.decode(b"<svg/>")
        with self.assertRaises(ValueError):
            svg.decode(good.replace(b'viewBox="0 0 2 1"', b'viewBox="0 0 3 1"'))


if __name__ == "__main__":
    unittest.main()
