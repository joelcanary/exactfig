"""
Alternative text, exact / texto alternativo, exacto.

A figure needs a text description for readers who cannot see it (screen readers, the `alt` attribute of a web page, a
journal's figure description). Tools that write it after the fact can only guess what a picture shows. exactfig knows:
a data generator draws only after its data have passed the checks its recipe states, so the description can state
those checks as facts. `text` is called after the generator has drawn; it never draws or checks anything itself.

  data.pratt               the prime, the number of certificate lines, what was checked on each
  data.circuit             gates, inputs, depth, the function, how many inputs give 1, checked on all 2^n inputs
  data.circuit_refutation  the claim refuted, the size it proves, the number of clauses up to the empty one
  data.refutation          the colouring claim refuted, n, the colours, the number of clauses
  data.coloring            the colourings, n, the colours, the rule each colour obeys
  data.catalog             the patterns, their cells, the rule, what each was checked to be, distinct or not
  data.instances           the masks; in compare mode TP, FP, FN and the exact panoptic quality
  data.sequence            the indices, the scale, the largest term, the new terms checked
  data.triangle            the areas, squarefree or not, a² + b² = c² and a·b/2 = n checked
  math.sandpile            the grid, the checks on the identity, the group order if stated
  anything else            the generator's own summary, its name and the picture's size

Pure functions: the same recipe and data give the same text, in English (the language of the generators' own names
and of most journals), with numbers written in full.
"""
from __future__ import annotations

from .circuit import target
from .coloring import parse_lengths

MAX_ALT = 1000


def _num(n: int) -> str:
    """An integer in full, or its digit count when it is very long."""
    s = str(n)
    return s if len(s) <= 40 else f"a {len(s)}-digit number ({s[:12]}…{s[-12:]})"


def function_words(spec: str, n: int) -> str:
    """'mod 3 1' → 'outputs 1 exactly when x1 + … + x5 leaves remainder 1 on division by 3', and so on."""
    toks = spec.split()
    xs = " + ".join(f"x{i}" for i in range(1, n + 1)) if n <= 4 else f"x1 + … + x{n}"
    if toks[0] == "mod":
        return f"outputs 1 exactly when {xs} leaves remainder {toks[2]} on division by {toks[1]}"
    if toks[0] == "threshold":
        return f"outputs 1 exactly when at least {toks[1]} of its {n} inputs are 1"
    if toks[0] == "parity":
        return f"outputs the parity of its {n} inputs"
    return f"computes the function with truth table {toks[1]} (bit m is its value on input m)"


def _pratt(p, data, w, h):
    root = data.nodes[0][0]
    return (f"The Pratt certificate that {_num(root)} is prime, drawn as a tree: {len(data.nodes)} lines, each checked "
            f"(p − 1 is the product of the stated factors and the witness has order exactly p − 1), every factor above "
            f"2 with a line of its own, down to the leaves 2. A node's disc grows with the bits of its prime.")


def _circuit(p, data, w, h):
    n, g = data.inputs, len(data.gates)
    d = {f"x{i}": 0 for i in range(1, n + 1)}
    for name, _, a, b in data.gates:
        d[name] = 1 + max(d[a], d[b])
    ones = bin(target(p["function"], n)).count("1")
    return (f"A Boolean circuit of {g} two-input gates on {n} inputs that {function_words(p['function'], n)}, checked on "
            f"all {1 << n} inputs{'; every gate leads to the output' if p['strict'] else ''}. Inputs on the top row, each "
            f"gate on the row of its depth ({d[data.output]} levels), coloured by its operation, the output ringed; along "
            f"the bottom, its value on each input in order, 1 on {ones} of the {1 << n}.")


def _added(data):
    for k, st in enumerate(data.steps):
        if st[0] == "a" and not st[2]:
            return sum(1 for s in data.steps[:k + 1] if s[0] == "a")
    return sum(1 for s in data.steps if s[0] == "a")


def _circuit_refutation(p, data, w, h):
    n, s = p["inputs"], p["gates"]
    return (f"An LRAT proof, checked step by step against a formula written from the claim, that no circuit of {s} "
            f"two-input gates on {n} inputs {function_words(p['function'], n)}; so such a circuit needs at least {s + 1} "
            f"gates. {_added(data)} added clauses up to the empty one, in proof order from left to right, one row per "
            f"gate, coloured by the kind of variable (choice of inputs, operation, value) most mentioned.")


def _claim(check, ks, r, distinct):
    if check == "ap":
        if len(set(ks)) == 1:
            return f"no colour holds a {ks[0]}-term arithmetic progression"
        return (f"colours 0 to {len(ks) - 1} hold no arithmetic progression of length "
                + ", ".join(str(k) for k in ks) + " respectively")
    if check == "schur":
        return "no colour holds x, y and x + y" + (" with x < y" if distinct else "")
    return "nothing is checked about the colours"


def _refutation(p, data, w, h):
    ks = parse_lengths(p["lengths"]) if p["check"] == "ap" else []
    r = p["colors"] or len(ks)
    return (f"An LRAT proof, checked step by step against a formula written from the claim, that 1..{p['length']} "
            f"cannot be coloured with {r} colours so that {_claim(p['check'], ks, r, p['distinct'])}. "
            f"{_added(data)} added clauses up to the empty one; one row per number, in proof order from left to right, "
            f"coloured by the colour its clauses mention most.")


def _coloring(p, data, w, h):
    cols = data.colorings
    ks = parse_lengths(p["lengths"]) if p["check"] == "ap" else []
    r = p["colors"] or max(1 + max(c) for c in cols)
    n = max(len(c) for c in cols)
    what = "colouring" if len(cols) == 1 else "colourings"
    return (f"{len(cols)} {what} of 1..{n} with {r} colours, checked: {_claim(p['check'], ks, r, p['distinct'])}. "
            f"Each number is a square coloured by its colour, 1 at the top left.")


def _catalog(p, data, w, h):
    pats = data.patterns
    pops = sorted({len(c) for c in pats})
    pop = f"{pops[0]} cells" if len(pops) == 1 else f"{pops[0]} to {pops[-1]} cells"
    what = {"still": ("strict still life" if p["strict"] else "still life"),
            "oscillator": f"oscillator of period exactly {p['period']}",
            "ship": f"spaceship that moves by ({p['shift']}) every {p['period']} generations",
            "none": "pattern"}[p["check"]]
    checked = "checked by simulation" if p["check"] != "none" else "not checked"
    distinct = ", no two equal up to rotation and reflection" if p["distinct"] else ""
    return (f"A catalogue of {len(pats)} patterns of {pop} under the Life-like rule {p['rule']}, each a {what} "
            f"({checked}{distinct}), drawn in a grid, live cells as squares.")


def _instances(p, data, w, h):
    from .instances import match, panoptic_quality
    if p["mode"] == "instances":
        masks = data.truth if p["show"] == "truth" else data.prediction
        sep = ", no two sharing a pixel" if p["partition"] else ""
        return (f"{len(masks)} instance masks ({p['show']}) of a {data.width} × {data.height} image, none empty{sep}, "
                f"each in its own hue.")
    q = panoptic_quality(match(data.truth, data.prediction), len(data.truth), len(data.prediction))
    pq = f"{float(q['pq']):.4f} (exactly {q['pq'].numerator}/{q['pq'].denominator})" if q["pq"] is not None else "undefined"
    return (f"{len(data.truth)} ground-truth instances against {len(data.prediction)} predictions in a "
            f"{data.width} × {data.height} image, matched one to one by IoU above 1/2: {q['tp']} true positives, "
            f"{q['fp']} false positives, {q['fn']} false negatives, panoptic quality {pq}. Agreed pixels in colour, "
            f"pixels only one side has in grey, false positives warm, false negatives cool.")


def _sequence(p, data, w, h):
    terms = data.terms
    first, last = terms[0][0], terms[-1][0]
    new = ""
    if p["new_from"] >= 0:
        k = sum(1 for n, _ in terms if n >= p["new_from"])
        new = f"; the {k} terms from n = {p['new_from']} on are highlighted and checked against the stated values"
    return (f"The terms a({first}) to a({last}) of an integer sequence as bars on a "
            f"{'logarithmic' if p['scale'] == 'log' else 'linear'} scale, the largest {_num(max(a for _, a in terms))}"
            f"{new}.")


def _triangles(p, data, w, h):
    ns = [str(t[0]) for t in data.triangles]
    areas = ", ".join(ns) if len(ns) <= 12 else ", ".join(ns[:12]) + f" and {len(ns) - 12} more"
    return (f"{len(ns)} right triangles with rational sides, of areas {areas}"
            f"{' (each squarefree, a congruent number)' if p['squarefree'] else ''}; for each, a² + b² = c² and "
            f"a·b/2 = n were checked in exact fractions.")


def _sandpile(p, data, w, h):
    n = p["n"]
    order = f" Its group order {p['order']} was checked against the number of spanning trees." if p["order"] else ""
    return (f"The identity of the sandpile group of a {n} × {n} grid, computed with Creutz's formula and checked to be "
            f"stable and to satisfy e ⊕ e = e; 0, 1, 2 and 3 grains as four steps of colour.{order}")


DESCRIBE = {"data.catalog": _catalog, "data.instances": _instances, "data.sequence": _sequence,
            "data.triangle": _triangles, "math.sandpile": _sandpile, "data.pratt": _pratt, "data.circuit": _circuit, "data.circuit_refutation": _circuit_refutation,
            "data.refutation": _refutation, "data.coloring": _coloring}


def text(gen, params: dict, data, w: int, h: int) -> str:
    """The alternative text of one drawn layer (see the module)."""
    fn = DESCRIBE.get(gen.name)
    if fn:
        out = fn(params, data, w, h)
    else:
        kind = {"image": "image", "animation": "animation", "midi": "MIDI piece"}[gen.kind]
        size = f"{w} × {h} pixels, " if gen.kind != "midi" else ""
        out = f"{gen.summary[:1].upper()}{gen.summary[1:]} ({kind}, {size}exactfig generator {gen.name})."
    return out if len(out) <= MAX_ALT else out[:MAX_ALT - 1] + "…"
