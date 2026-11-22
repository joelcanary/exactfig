"""
A manifest as an RO-Crate / el manifiesto como RO-Crate.

`exactfig crate [--manifest M.json] [--date YYYY-MM-DD] [--license SPDX] [--author NAME|ORCID] [--name NAME]` writes
`ro-crate-metadata.json` beside the manifest, so the folder (figures, input data, manifest) becomes an RO-Crate
(https://w3id.org/ro/crate/1.3), the packaging format that WorkflowHub reads and that Zenodo can archive, with each
recorded file described as a run in the Process Run Crate profile (https://w3id.org/ro/wfrun/process/0.6), whose
provenance terms align with W3C PROV:

  root "./"          a Dataset: name (default: the folder's), description, datePublished (given, or today), license
                     (an SPDX id; recommended, the command warns without it), author (optional), conformsTo the
                     profile, hasPart every file, mentions every run
  each output        a File with its encodingFormat, contentSize and sha256 (the workflow-run term)
  each input         a File with its format, size and sha256
  each run           a CreateAction "exactfig record <file>": instrument = the generator (name, version and the SHA-256
                     of its source code), object = the input files and the recipe's parameters as PropertyValues,
                     result = the file, actionStatus = CompletedActionStatus, agent = the author if one is given
  exactfig           a SoftwareApplication per version (with its url), the generators isPartOf it

Before writing, every file named is read from disk and must have the size and SHA-256 the manifest records, so the crate
never describes a file that is missing or has changed since `record` (a re-encoded figure that `verify` only warns
about is refused here). Beyond that the crate only restates the manifest: it adds no claim of its own and is not needed
to verify anything (`exactfig verify` does that). Not given: the times of the runs (the manifest does not record them).
Deterministic: the same manifest and files, date, licence, author and name give the same bytes. Paths are written into
@id with spaces and other reserved characters percent-encoded, as RO-Crate asks.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
from urllib.parse import quote

from . import load

RO_CRATE = "https://w3id.org/ro/crate/1.3"
PROFILE = "https://w3id.org/ro/wfrun/process/0.6"
CONTEXT = [RO_CRATE + "/context", "https://w3id.org/ro/terms/workflow-run/context"]
HOME = "https://github.com/joelcanary/exactfig"
METADATA = "ro-crate-metadata.json"
MIME = {".png": "image/png", ".gif": "image/gif", ".apng": "image/apng", ".mid": "audio/midi", ".json": "application/json",
        ".csv": "text/csv", ".npy": "application/octet-stream", ".pgm": "image/x-portable-graymap",
        ".ppm": "image/x-portable-pixmap"}
SPDX = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+-]{0,63}\Z")
ORCID = re.compile(r"https://orcid\.org/\d{4}-\d{4}-\d{4}-\d{3}[\dX]\Z")


def _mime(path: str) -> str:
    return MIME.get(os.path.splitext(path)[1].lower(), "text/plain")


def _id(path: str) -> str:
    """A relative path as an RO-Crate @id: '/' kept, everything reserved (space, %, #, ?) percent-encoded."""
    return quote(path.replace(os.sep, "/"), safe="/")


def _on_disk(base: str, rel: str, size: int, sha: str, what: str):
    """Refuse a file that is missing or whose bytes are not the recorded ones."""
    path = os.path.join(base, rel)
    if not os.path.isfile(path):
        raise ValueError(f"{rel}: {what} recorded in the manifest is not on disk; the crate would describe a file that "
                         f"is not there")
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    if os.path.getsize(path) != size or h.hexdigest() != sha:
        raise ValueError(f"{rel}: the file on disk is not the one the manifest records (size or SHA-256 differ); run "
                         f"`exactfig verify --strict` and record again")


def build(manifest_path: str, date: str | None = None, license_id: str | None = None, name: str | None = None,
          author: str | None = None) -> dict:
    """The RO-Crate metadata (a dict ready for json.dump) of the folder that holds `manifest_path`."""
    man = load(manifest_path)
    assets = man["assets"]
    if not assets:
        raise ValueError(f"{manifest_path}: the manifest records no file; nothing to describe")
    date = date or datetime.date.today().isoformat()
    try:
        datetime.date.fromisoformat(date)
    except ValueError:
        raise ValueError(f"--date {date!r} is not an ISO 8601 date (YYYY-MM-DD)") from None
    if license_id and not SPDX.match(license_id):
        raise ValueError(f"--license {license_id!r} is not an SPDX identifier (e.g. Apache-2.0, CC-BY-4.0)")
    if author is not None and not (author.strip() and len(author) <= 200 and "\n" not in author):
        raise ValueError("--author: a name (one line, up to 200 characters) or an ORCID URL")
    base = os.path.dirname(os.path.abspath(manifest_path))
    man_rel = os.path.basename(manifest_path)
    graph, files, runs, seen = [], [], [], set()

    def add(entity):
        if entity["@id"] not in seen:
            seen.add(entity["@id"])
            graph.append(entity)

    person = None
    if author:
        person = author if ORCID.match(author) else "#author"
        add({"@id": person, "@type": "Person", "name": author})
    for rel in sorted(assets):
        e = assets[rel]
        tool = e.get("tool", {}).get("version", "unknown")
        app = f"{HOME}/releases/tag/v{tool}"
        add({"@id": app, "@type": "SoftwareApplication", "name": "exactfig", "softwareVersion": tool, "url": HOME})
        g = e["generator"]
        gen_id = f"#generator-{quote(g['name'])}-{quote(g['version'])}-{g['code_sha256'][:12]}"
        add({"@id": gen_id, "@type": "SoftwareApplication", "name": f"exactfig generator {g['name']}",
             "softwareVersion": g["version"], "url": HOME, "isPartOf": {"@id": app},
             "description": f"source code SHA-256 {g['code_sha256']}"})
        out = e["output"]
        _on_disk(base, rel, out["bytes"], out["file_sha256"], "the output")
        add({"@id": _id(rel), "@type": "File", "name": rel, "encodingFormat": _mime(rel),
             "contentSize": str(out["bytes"]), "sha256": out["file_sha256"]})
        files.append(_id(rel))
        objects = []
        for inp in e.get("inputs", []):
            iid = _id(inp["path"])
            if iid not in seen:
                _on_disk(base, inp["path"], inp["bytes"], inp["sha256"], "an input")
            add({"@id": iid, "@type": "File", "name": inp["path"], "encodingFormat": _mime(inp["path"]),
                 "contentSize": str(inp["bytes"]), "sha256": inp["sha256"],
                 "description": f"exactfig input format {inp['format']}"})
            if iid not in files:
                files.append(iid)
            objects.append({"@id": iid})
        r = e["recipe"]
        values = [("seed", r.get("seed", "")), ("palette", r.get("palette", "")), ("size", r.get("size"))]
        values += sorted((r.get("params") or {}).items())
        for key, val in values:
            pid = f"#run-{_id(rel)}-{quote(key)}"
            add({"@id": pid, "@type": "PropertyValue", "name": key,
                 "value": val if isinstance(val, (str, int, float, bool)) else json.dumps(val, separators=(",", ":"))})
            objects.append({"@id": pid})
        run = f"#run-{_id(rel)}"
        action = {"@id": run, "@type": "CreateAction", "name": f"exactfig record {rel}",
                  "description": f"recipe SHA-256 {e['recipe_sha256']}; content SHA-256 {out['content_sha256']}",
                  "instrument": {"@id": gen_id}, "object": objects, "result": [{"@id": _id(rel)}],
                  "actionStatus": {"@id": "http://schema.org/CompletedActionStatus"}}
        if person:
            action["agent"] = {"@id": person}
        add(action)
        runs.append(run)
    with open(manifest_path, "rb") as fh:
        raw = fh.read()
    add({"@id": _id(man_rel), "@type": "File", "name": "exactfig manifest", "encodingFormat": "application/json",
         "contentSize": str(len(raw)), "sha256": hashlib.sha256(raw).hexdigest(),
         "description": f"exactfig.manifest/1; manifest_sha256 {man.get('manifest_sha256', '')}; "
                        "`exactfig verify` re-makes every file from it and compares bit for bit"})
    root = {"@id": "./", "@type": "Dataset", "name": name or (os.path.basename(base) or "exactfig figures"),
            "description": f"{len(assets)} files (figures, animations or pieces) made by exactfig from recipes recorded "
                           f"in {man_rel}; each one can be re-made and compared bit for bit with `exactfig verify`.",
            "datePublished": date, "conformsTo": [{"@id": PROFILE}],
            "hasPart": [{"@id": _id(man_rel)}] + [{"@id": f} for f in files], "mentions": [{"@id": r} for r in runs]}
    if person:
        root["author"] = {"@id": person}
    extra = [{"@id": PROFILE, "@type": "CreativeWork", "name": "Process Run Crate", "version": "0.6"}]
    if license_id:
        lic = f"https://spdx.org/licenses/{license_id}"
        root["license"] = {"@id": lic}
        extra.append({"@id": lic, "@type": "CreativeWork", "name": license_id,
                      "description": f"SPDX licence {license_id}"})
    descriptor = {"@id": METADATA, "@type": "CreativeWork", "conformsTo": {"@id": RO_CRATE}, "about": {"@id": "./"}}
    return {"@context": CONTEXT, "@graph": [descriptor, root] + extra + graph}


def write(manifest_path: str, **kw) -> str:
    """Write ro-crate-metadata.json beside the manifest (the crate's paths are relative to that folder, and the file
    must have that name) and return its path."""
    crate = build(manifest_path, **kw)
    out = os.path.join(os.path.dirname(os.path.abspath(manifest_path)), METADATA)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(crate, ensure_ascii=False, indent=1) + "\n")
    return out
