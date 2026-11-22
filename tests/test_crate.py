"""`exactfig crate`: the gallery's manifest as an RO-Crate 1.3 / Process Run Crate 0.6.

Checked here: every MUST rule of both specifications that applies (descriptor @id, @type, about and conformsTo; root
@type Dataset and datePublished; the profile in the root's conformsTo, as a CreativeWork in the graph; every
CreateAction with @id, @type and instrument) and these SHOULD rules: root name, description and license (with
--license), instrument name, version and url, run name, description, result, actionStatus, agent (with --author),
percent-encoded @ids. Not given, and so not checked: endTime/startTime (the manifest records no times) and agent when no
--author is given. Also: every @id unique, every reference resolves, every File's sha256 and size equal to the bytes on
disk, and a missing or changed file refused before anything is written. Same inputs, same bytes."""
import datetime
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig.provenance import crate  # noqa: E402

GALLERY = os.path.join(os.path.abspath(ROOT), "gallery")
MANIFEST = os.path.join(GALLERY, "manifest.json")


def refs(entity):
    """Every {"@id": …} the entity points to, through the properties the crate uses."""
    for key in ("hasPart", "mentions", "instrument", "object", "result", "isPartOf", "license", "conformsTo", "about",
                "agent", "author"):
        val = entity.get(key)
        for v in val if isinstance(val, list) else [val] if val else []:
            yield key, v["@id"]


class TestCrate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = crate.build(MANIFEST, date="2026-11-22", license_id="Apache-2.0", author="A. Researcher")
        cls.by = {e["@id"]: e for e in cls.c["@graph"]}

    def test_context_and_descriptor(self):
        self.assertEqual(self.c["@context"], ["https://w3id.org/ro/crate/1.3/context",
                                              "https://w3id.org/ro/terms/workflow-run/context"])
        d = self.by["ro-crate-metadata.json"]
        self.assertEqual(d["@type"], "CreativeWork")
        self.assertEqual(d["about"], {"@id": "./"})
        self.assertEqual(d["conformsTo"], {"@id": "https://w3id.org/ro/crate/1.3"})

    def test_root(self):
        r = self.by["./"]
        self.assertEqual(r["@type"], "Dataset")
        datetime.date.fromisoformat(r["datePublished"])
        self.assertTrue(r["name"] and r["description"])
        self.assertIn({"@id": "https://w3id.org/ro/wfrun/process/0.6"}, r["conformsTo"])
        prof = self.by["https://w3id.org/ro/wfrun/process/0.6"]
        self.assertEqual((prof["@type"], prof["version"]), ("CreativeWork", "0.6"))
        self.assertEqual(r["license"], {"@id": "https://spdx.org/licenses/Apache-2.0"})
        self.assertEqual(self.by[r["author"]["@id"]], {"@id": "#author", "@type": "Person", "name": "A. Researcher"})

    def test_ids_unique_and_references_resolve(self):
        ids = [e["@id"] for e in self.c["@graph"]]
        self.assertEqual(len(ids), len(set(ids)))
        for e in self.c["@graph"]:
            for key, target in refs(e):
                if key == "conformsTo" and e["@id"] == "ro-crate-metadata.json":
                    continue                                   # the RO-Crate specification itself, not an entity
                self.assertIn(target, self.by, f"{e['@id']}.{key} -> {target}")

    def test_runs_and_files_match_the_disk(self):
        actions = [e for e in self.c["@graph"] if e["@type"] == "CreateAction"]
        with open(MANIFEST, encoding="utf-8") as fh:
            self.assertEqual(len(actions), len(json.load(fh)["assets"]))
        for a in actions:
            inst = self.by[a["instrument"]["@id"]]
            self.assertEqual(inst["@type"], "SoftwareApplication")
            self.assertTrue(inst["name"] and inst["softwareVersion"] and inst["url"])
            self.assertTrue(a["name"] and a["description"] and a["result"])
            self.assertEqual(a["actionStatus"], {"@id": "http://schema.org/CompletedActionStatus"})
            self.assertEqual(a["agent"], {"@id": "#author"})
        for f in (e for e in self.c["@graph"] if e["@type"] == "File"):
            with open(os.path.join(GALLERY, f["name"] if f["name"] != "exactfig manifest" else "manifest.json"),
                      "rb") as fh:
                raw = fh.read()
            self.assertEqual(f["sha256"], hashlib.sha256(raw).hexdigest(), f["@id"])
            self.assertEqual(f["contentSize"], str(len(raw)), f["@id"])
        self.assertEqual({p["@id"] for p in self.by["./"]["hasPart"]},
                         {e["@id"] for e in self.c["@graph"] if e["@type"] == "File"})

    def test_deterministic_refusals_and_disk(self):
        same = [json.dumps(crate.build(MANIFEST, date="2026-11-22", license_id="CC-BY-4.0")) for _ in range(2)]
        self.assertEqual(same[0], same[1])
        for kw in ({"date": "22/11/2026"}, {"date": "2026-02-30"}, {"license_id": "Apache 2.0"},
                   {"license_id": "../x"}, {"author": ""}, {"author": "a\nb"}):
            with self.assertRaises(ValueError, msg=kw):
                crate.build(MANIFEST, **kw)
        orcid = crate.build(MANIFEST, date="2026-11-22", author="https://orcid.org/0000-0002-1825-0097")
        self.assertIn("https://orcid.org/0000-0002-1825-0097", {e["@id"] for e in orcid["@graph"]})
        d = tempfile.mkdtemp(prefix="exactfig-crate-")
        try:
            empty = os.path.join(d, "manifest.json")
            with open(empty, "w", encoding="utf-8") as fh:
                json.dump({"format": "exactfig.manifest/1", "assets": {}}, fh)
            with self.assertRaises(ValueError):
                crate.build(empty, date="2026-11-22")
            g = os.path.join(d, "gal")                          # a copy of the gallery, then spoiled two ways
            shutil.copytree(GALLERY, g)
            crate.write(os.path.join(g, "manifest.json"), date="2026-11-22")
            self.assertTrue(os.path.isfile(os.path.join(g, "ro-crate-metadata.json")))
            os.remove(os.path.join(g, "pratt-m127.png"))
            with self.assertRaisesRegex(ValueError, "not on disk"):
                crate.build(os.path.join(g, "manifest.json"), date="2026-11-22")
            shutil.copy(os.path.join(GALLERY, "pratt-m127.png"), os.path.join(g, "pratt-m127.png"))
            with open(os.path.join(g, "data", "pratt-m127.txt"), "ab") as fh:
                fh.write(b"\n")
            with self.assertRaisesRegex(ValueError, "not the one the manifest records"):
                crate.build(os.path.join(g, "manifest.json"), date="2026-11-22")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_ids_are_percent_encoded(self):
        self.assertEqual(crate._id("data/a b%#?.txt"), "data/a%20b%25%23%3F.txt")
        self.assertEqual(crate._id("plain/name.png"), "plain/name.png")


if __name__ == "__main__":
    unittest.main()
