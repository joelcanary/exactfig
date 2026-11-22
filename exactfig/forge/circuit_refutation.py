"""
A proof that a function has no small circuit, checked before it is drawn / una cota inferior de circuitos, comprobada.

data.circuit checks the "yes" half of a circuit-size question (here is a circuit of s gates). This generator checks the
"no" half: an LRAT proof that no circuit of s two-input gates computes the function, so its size is at least s + 1.
As in data.refutation, the proof is checked against a formula that exactfig writes itself from what the recipe states,
so a proof of another claim does not check:

  the claim    some circuit of exactly s = `gates` gates over all 16 two-input operations, on n = `inputs` inputs, has
               its last gate equal to `function` (as in data.circuit: mod M R, threshold K, parity or table HEX) on
               every input. That is the same as "some circuit of at most s gates computes the function": a smaller
               circuit is padded with gates that copy one argument (the operation t0011) until its output is gate s,
               and gates after the output of a circuit can be dropped. So a refutation proves size ≥ s + 1.
  the nodes    1..n are the inputs, n + 1..n + s the gates; node v on input row t = 0..2^n − 1 is bit v − 1 of t for an
               input (a constant, written into the clauses, not a variable).
  variables    gate by gate, a = 1..s (node n + a), a block of:
                 sel(a, j, k)   for every pair of earlier nodes 1 ≤ j < k ≤ n + a − 1, in lexicographic order:
                                gate a reads nodes j and k
                 op(a, pq)      for pq = 00, 01, 10, 11: the gate's output when its arguments are p and q
                 val(a, t)      for t = 0..2^n − 1: the gate's value on input row t
  clauses      in this order (LRAT refers to them by position, 1 to m):
                 1. for each gate, at least one pair: sel(a, ·, ·) ∨ …
                 2. for each gate, each pair (j, k), each row t and each pq: if the gate reads (j, k) and on row t node j
                    is p and node k is q, then val(a, t) = op(a, pq); two clauses, ¬sel ∨ [j ≠ p] ∨ [k ≠ q] ∨ ¬val ∨ op
                    and ¬sel ∨ [j ≠ p] ∨ [k ≠ q] ∨ val ∨ ¬op, where a constant literal that is true drops the clause
                    and one that is false is left out;
                 3. for each row t, the last gate equals the function: val(s, t) or ¬val(s, t).
               (A gate may read several pairs; any one of them gives a circuit, so "at most one pair" is not needed.)
  steps        the number of added clauses up to the empty one (0 = any)

The proof itself is checked exactly as in data.refutation: reverse unit propagation along the hints, RAT refused, until
the empty clause. Then the size of the function is at least s + 1; together with a circuit of s + 1 gates (data.circuit,
whose recipe can name this proof in `proof_sha256`) it is exactly s + 1.

The picture: one row per gate 1..s, one column per slice of the added clauses in proof order; a cell takes the colour of
the kind of variable (pair choice, operation, value) that the clauses of its slice mention most for that gate, and the
last column, where the empty clause appears, is drawn across in the mark colour.
"""
from __future__ import annotations

from ..pixel.canvas import Canvas
from .circuit import target
from .refutation import check_lrat

MAX_FORMULA = 4_000_000          # clauses, an upper bound on what the pure-Python checker is meant for


def layout(n: int, s: int):
    """Variable numbering: [(first variable of the gate's block, {(j, k): sel}, [op00, op01, op10, op11], [val_t])]."""
    out, v = [], 1
    for a in range(1, s + 1):
        sel = {}
        for j in range(1, n + a):
            for k in range(j + 1, n + a):
                sel[(j, k)] = v
                v += 1
        ops = list(range(v, v + 4))
        v += 4
        vals = list(range(v, v + (1 << n)))
        v += 1 << n
        out.append((ops[0] - len(sel), sel, ops, vals))
    return out, v - 1


def formula(n: int, s: int, f: int):
    """(clauses in the documented order, number of variables, gate of each variable, kind of each variable 0/1/2)."""
    if n < 2 or s < 1:
        raise ValueError("a circuit claim needs at least 2 inputs (a gate reads two distinct nodes) and 1 gate")
    blocks, nvars = layout(n, s)
    rows = 1 << n
    count = 0
    for a in range(1, s + 1):
        count += len(blocks[a - 1][1]) * rows * 8
    if count > MAX_FORMULA:
        raise ValueError(f"the formula for {n} inputs and {s} gates would have about {count} clauses "
                         f"(more than {MAX_FORMULA})")

    def node(v, t):
        """(constant, None) for an input, (None, variable) for a gate."""
        if v <= n:
            return (t >> (v - 1)) & 1, None
        return None, blocks[v - n - 1][3][t]

    out = [tuple(blocks[a - 1][1].values()) for a in range(1, s + 1)]
    for a in range(1, s + 1):
        _, sel, ops, vals = blocks[a - 1]
        for (j, k), sv in sel.items():
            for t in range(rows):
                cj, vj = node(j, t)
                ck, vk = node(k, t)
                for pq in range(4):
                    p, q = pq >> 1, pq & 1
                    if (cj is not None and cj != p) or (ck is not None and ck != q):
                        continue                                  # [j ≠ p] or [k ≠ q] is true: no clause
                    body = [-sv]
                    if vj is not None:
                        body.append(vj if p == 0 else -vj)        # [j ≠ p]
                    if vk is not None:
                        body.append(vk if q == 0 else -vk)
                    out.append(tuple(body + [-vals[t], ops[pq]]))
                    out.append(tuple(body + [vals[t], -ops[pq]]))
    last = blocks[s - 1][3]
    for t in range(rows):
        out.append((last[t],) if f >> t & 1 else (-last[t],))
    gate, kind = [0] * (nvars + 1), [0] * (nvars + 1)
    for a, (_, sel, ops, vals) in enumerate(blocks, 1):
        for v in sel.values():
            gate[v], kind[v] = a, 0
        for v in ops:
            gate[v], kind[v] = a, 1
        for v in vals:
            gate[v], kind[v] = a, 2
    return out, nvars, gate, kind


def circuit_refutation(seed, pal, w, h, p, data) -> Canvas:
    """Generator data.circuit_refutation: check (see the module), then the proof as gates × proof order."""
    n, s = p["inputs"], p["gates"]
    if n < 1 or s < 1:
        raise ValueError("data.circuit_refutation: give `inputs` and `gates`, the n and s of the claim")
    clauses, nvars, gate, kind = formula(n, s, target(p["function"], n))
    steps = data.steps
    last = check_lrat(clauses, steps, nvars)
    added = [st[2] for st in steps[:last] if st[0] == "a"]
    if p["steps"] and len(added) != p["steps"]:
        raise ValueError(f"the proof adds {len(added)} clauses up to the empty one, the recipe states {p['steps']}")
    cell_h = h // s
    if cell_h < 1 or w < 4:
        raise ValueError(f"data.circuit_refutation: {s} gates do not fit in {w}x{h}; give a larger size")
    ramp = pal.ramp(p["ramp"])
    tone = [ramp[c * len(ramp) // 3] for c in range(3)]
    mark = pal.ramp(p["mark_ramp"])
    mark = mark[len(mark) // 2]
    mark_w = max(1, w // 128)
    cols = w - 2 * mark_w
    counts = [[[0, 0, 0] for _ in range(s)] for _ in range(cols)]
    total = len(added)
    for b in range(cols):                                         # each column: its slice of the proof, at least one
        j0 = b * total // cols                                    # clause, so a short proof is stretched, not striped
        for lits in added[j0:max(j0 + 1, (b + 1) * total // cols)]:
            for l in lits:
                v = abs(l)
                counts[b][gate[v] - 1][kind[v]] += 1
    cv = Canvas(w, h, pal)
    if p["background"]:
        cv.rect(0, 0, w - 1, h - 1, pal.ramp(p["background"])[0])
    oy = (h - s * cell_h) // 2
    for b in range(cols):
        for i in range(s):
            cnt = counts[b][i]
            best = max(range(3), key=lambda c: (cnt[c], -c))
            if cnt[best]:
                cv.rect(b, oy + i * cell_h, b, oy + (i + 1) * cell_h - 2 if cell_h > 2 else oy + i * cell_h, tone[best])
    cv.rect(w - mark_w, oy, w - 1, oy + s * cell_h - 1, mark)
    return cv
