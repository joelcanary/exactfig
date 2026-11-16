"""
A Pratt certificate of primality, checked before it is drawn / certificado de Pratt, comprobado antes de dibujarlo.

Lucas's converse of Fermat's little theorem: p is prime when some g has order exactly p − 1 modulo p, that is

  g^(p−1) ≡ 1 (mod p)   and   g^((p−1)/q) ≢ 1 (mod p) for every prime q dividing p − 1.

Pratt (1975) noticed that this gives a short proof of primality, provided each q is itself proved prime the same way,
down to 2. Finding the certificate is the hard part (it needs p − 1 factored); checking it takes a few modular
exponentiations per line. exactfig does only the checking, in exact integer arithmetic, before anything is drawn:

  every line    p − 1 is exactly the product of the stated q^e, the factors are distinct, 1 ≤ g < p,
                g^(p−1) mod p = 1 and g^((p−1)/q) mod p ≠ 1 for each q
  every factor  q = 2, or q has a line of its own (which is checked in turn)
  every line    is used: it is reachable from the first line (a certificate carries nothing else)
  prime         the first line proves this number (empty = any), compared as an exact integer
  primes        the file has this many lines (0 = any)

A refusal names the line and the condition that fails. A composite number has no certificate at all (no g has order
n − 1), so no file can make exactfig draw one: Carmichael numbers such as 561 included.

The tree: the prime on top, below each node the primes of its p − 1 from smallest to largest, down to the leaves 2. A
prime that divides several p − 1 is drawn under each of them. The disc of a node grows with the number of bits of its
prime (the area with the bits), and its colour goes along the ramp the same way, so the size of the numbers shows.
"""
from __future__ import annotations

from .. import fmath as fm
from ..pixel.canvas import Canvas

MAX_TREE = 8192          # nodes of the drawn tree (a prime under several parents is drawn under each)


def check(nodes, p) -> dict:
    lines = {}
    for k, (q, g, fac) in enumerate(nodes, 1):
        lines[q] = (k, g, fac)
    root = nodes[0][0]
    if p["prime"]:
        want = p["prime"].strip()
        if not (want.isdigit() and want.isascii()) or int(want) != root:
            shown = str(root) if len(str(root)) <= 60 else str(root)[:28] + "…" + str(root)[-28:]
            raise ValueError(f"the certificate is for {shown}, the recipe states {want[:60]}")
    if p["primes"] and len(nodes) != p["primes"]:
        raise ValueError(f"{len(nodes)} lines in the certificate, the recipe states {p['primes']}")
    for n, (k, g, fac) in lines.items():
        where = f"line {k} (p = {n})"
        if n == 2:
            continue
        if n < 2:
            raise ValueError(f"{where}: a prime is at least 2")
        prod, qs = 1, set()
        for q, e in fac:
            if q < 2 or e < 1:
                raise ValueError(f"{where}: factor {q}^{e}: factors are ≥ 2, exponents ≥ 1")
            if q in qs:
                raise ValueError(f"{where}: the factor {q} is listed twice (write it once, with its exponent)")
            qs.add(q)
            for _ in range(e):
                prod *= q
                if prod > n - 1:
                    raise ValueError(f"{where}: the factors multiply to more than p − 1")
        if prod != n - 1:
            raise ValueError(f"{where}: the factors multiply to {prod}, not p − 1 = {n - 1}")
        if not 1 <= g < n:
            raise ValueError(f"{where}: the witness g = {g} is not between 1 and p − 1")
        if pow(g, n - 1, n) != 1:
            raise ValueError(f"{where}: g^(p−1) mod p = {pow(g, n - 1, n)}, not 1 (Fermat fails: p is not prime, "
                             f"or g is wrong)")
        for q in sorted(qs):
            if pow(g, (n - 1) // q, n) == 1:
                raise ValueError(f"{where}: g^((p−1)/{q}) mod p = 1: the order of g = {g} is not p − 1")
            if q != 2 and q not in lines:
                raise ValueError(f"{where}: the factor {q} has no line of its own (each factor > 2 needs its proof)")
    used, todo = {root}, [root]
    while todo:
        n = todo.pop()
        for q, _ in lines[n][2]:
            if q in lines and q not in used:
                used.add(q)
                todo.append(q)
    extra = [n for n in lines if n not in used]
    if extra:
        k = lines[extra[0]][0]
        raise ValueError(f"line {k} (p = {extra[0]}) is not used by the certificate of the first line")
    return {"primes": len(nodes), "digits": len(str(root))}


def tree(nodes):
    """The certificate as a tree: [(prime, depth, x2)] in drawing order and [(parent index, child index)] edges;
    x2 is twice the horizontal slot (leaves at even slots, a parent midway between its first and last child)."""
    kids = {q: sorted(f for f, _ in fac) for q, _, fac in nodes}
    out, edges = [], []
    leaf = [0]

    def walk(n, depth, parent):
        if len(out) >= MAX_TREE:
            raise ValueError(f"the tree has more than {MAX_TREE} nodes; draw a smaller certificate")
        i = len(out)
        out.append([n, depth, 0])
        if parent >= 0:
            edges.append((parent, i))
        cs = kids.get(n, [])
        if not cs:
            out[i][2] = 2 * leaf[0]
            leaf[0] += 1
        else:
            first = last = None
            for q in cs:
                j = walk(q, depth + 1, i)
                first = out[j][2] if first is None else first
                last = out[j][2]
            out[i][2] = (first + last) // 2
        return i

    walk(nodes[0][0], 0, -1)
    return out, edges, leaf[0]


def pratt(seed, pal, w, h, p, data) -> Canvas:
    """Generator data.pratt: check (see the module), then the certificate as a tree, root on top, discs by bits."""
    nodes = data.nodes
    check(nodes, p)
    pts, edges, leaves = tree(nodes)
    depth = max(d for _, d, _ in pts)
    pad = max(2, min(w, h) // 24)
    rmax = max(1.0, min((h - 2 * pad) / (3.0 * max(1, depth) + 2.0), (w - 2 * pad) / 12.0))
    gap_y = (h - 2 * pad - 2 * rmax) / max(1, depth)              # the root's disc stays inside the picture
    gap_x = (w - 2 * pad) / max(1, leaves - 1)
    top_bits = max(q.bit_length() for q, _, _ in pts)
    ramp = pal.ramp(p["ramp"])
    er = pal.ramp(p["edge_ramp"])
    edge = er[len(er) // 2]                                          # a middle step: the first is the darkest
    cv = Canvas(w, h, pal)
    if p["background"]:
        cv.rect(0, 0, w - 1, h - 1, pal.ramp(p["background"])[0])

    def xy(i):
        _, d, x2 = pts[i]
        x = w / 2.0 if leaves == 1 else pad + gap_x * x2 / 2.0
        y = pad + rmax + gap_y * d if depth else h / 2.0
        return int(fm.floor(x + 0.5)), int(fm.floor(y + 0.5))

    for a, b in edges:
        (x0, y0), (x1, y1) = xy(a), xy(b)
        cv.line(x0, y0, x1, y1, edge)
    for i, (q, _, _) in enumerate(pts):
        t = fm.sqrt(q.bit_length() / top_bits)                        # area grows with the share of the root's bits
        r = int(fm.floor(rmax * t + 0.5))
        col = ramp[int(fm.floor((0.3 + 0.7 * t) * (len(ramp) - 1) + 0.5))]
        x, y = xy(i)
        if r < 1:
            cv.set(x, y, col)
        else:
            cv.disc(x, y, r, col)
    return cv
