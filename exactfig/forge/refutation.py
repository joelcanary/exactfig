"""
A proof that 1..n cannot be coloured, checked before it is drawn / una refutación, comprobada antes de dibujarla.

A SAT solver's "yes" comes with a witness (data.coloring draws those); its "no" comes with a proof. This generator takes
that proof in the LRAT format and checks it against a formula that exactfig writes itself from what the recipe states,
so the figure cannot show a proof of something else:

  the formula   variables x(i, c) = (i − 1)·r + c + 1 for i in 1..n and colours c in 0..r − 1, and the clauses, in this
                order (LRAT refers to them by position, 1 to m):
                  1. every number has a colour: x(i, 0) ∨ … ∨ x(i, r − 1), for i = 1..n;
                  2. check "ap": for each colour c, each step d = 1, 2, … and each start a, the progression
                     a, a + d, …, a + (k_c − 1)d inside 1..n is not all of colour c: ¬x(a, c) ∨ … ;
                     check "schur": for each x = 1, 2, … and y = x, x + 1, … with x + y ≤ n (y > x with `distinct`),
                     and each colour c, the numbers {x, y, x + y} are not all of colour c.
                The formula is satisfiable exactly when 1..n can be coloured so (one colour per number is enough: the
                clauses only forbid, so a solution with several colours on a number keeps any one of them).
  the proof     every added clause is checked by reverse unit propagation along its hints: assume the clause false,
                and each hint, in order, must become unit (its one free literal is then set) until one becomes false.
                Deletions only remove clauses. RAT steps (negative hints) and new variables are refused; the proof is
                accepted when it adds the empty clause.
  steps         the number of added clauses (0 = any)

A refusal names the proof step and why it fails. Checking is linear in the size of the proof; the pure-Python checker
is meant for proofs of up to a few million steps (larger ones belong to a verified checker such as cake_lpr).

The picture: one row per number 1..n, one column per slice of the added clauses in proof order; a cell takes the colour
that the clauses of its slice mention most for that number (colours as in data.coloring), and the last column, where the
empty clause appears, is drawn across in the mark colour.
"""
from __future__ import annotations

from ..pixel.canvas import Canvas
from .coloring import parse_lengths


def formula(check: str, ks: list[int], r: int, n: int, distinct: bool = False) -> list[tuple[int, ...]]:
    """The clauses, in the documented order, of "1..n can be coloured with r colours under `check`"."""
    def x(i, c):
        return (i - 1) * r + c + 1
    out = [tuple(x(i, c) for c in range(r)) for i in range(1, n + 1)]
    if check == "ap":
        for c in range(r):
            k = ks[c] if len(ks) > 1 else ks[0]
            for d in range(1, n):
                for a in range(1, n - (k - 1) * d + 1):
                    out.append(tuple(-x(a + j * d, c) for j in range(k)))
    elif check == "schur":
        for xx in range(1, n + 1):
            for y in range(xx + (1 if distinct else 0), n - xx + 1):
                members = sorted({xx, y, xx + y})
                for c in range(r):
                    out.append(tuple(-x(i, c) for i in members))
    else:
        raise ValueError(f"check {check!r}: a refutation needs \"ap\" or \"schur\"")
    return out


def check_lrat(clauses, steps, nvars: int) -> int:
    """Index of the step that adds the empty clause; ValueError naming the first step that does not check."""
    db = {i + 1: c for i, c in enumerate(clauses)}
    top = len(clauses)
    for k, st in enumerate(steps, 1):
        if st[0] == "d":
            for i in st[1]:
                db.pop(i, None)                       # deleting can only weaken what follows: nothing to check
            continue
        _, cid, lits, hints = st
        where = f"proof step {k} (clause {cid})"
        if cid <= top or cid in db:
            raise ValueError(f"{where}: clause ids must be new and above {top} (the formula has {len(clauses)} clauses)")
        if any(h < 0 for h in hints):
            raise ValueError(f"{where}: a RAT step (negative hint); only reverse unit propagation is accepted")
        if any(l == 0 or abs(l) > nvars for l in lits):
            raise ValueError(f"{where}: a literal outside the formula's {nvars} variables")
        true = {-l for l in lits}                     # the clause assumed false
        if any(-l in true for l in true):
            conflict = True                           # a tautology needs no hints
        else:
            conflict = False
            for h in hints:
                d = db.get(h)
                if d is None:
                    raise ValueError(f"{where}: hint {h} is not a clause at this point")
                free, nfree = 0, 0
                for l in d:
                    if l in true:
                        raise ValueError(f"{where}: hint {h} is already satisfied, it cannot propagate")
                    if -l not in true:
                        nfree += 1
                        free = l
                        if nfree > 1:
                            break
                if nfree == 0:
                    conflict = True
                    break
                if nfree > 1:
                    raise ValueError(f"{where}: hint {h} is not unit (two or more free literals)")
                true.add(free)
        if not conflict:
            raise ValueError(f"{where}: its hints never reach a conflict")
        db[cid] = lits
        top = cid
        if not lits:
            return k
    raise ValueError("the proof never adds the empty clause")


def refutation(seed, pal, w, h, p, data) -> Canvas:
    """Generator data.refutation: check (see the module), then the proof as numbers × proof order."""
    n = p["length"]
    if n < 1:
        raise ValueError("data.refutation: give `length`, the n of the claim '1..n cannot be coloured'")
    ks = parse_lengths(p["lengths"]) if p["check"] == "ap" else []
    r = p["colors"] or (len(ks) if len(ks) > 1 else 0)
    if r < 1:
        raise ValueError("data.refutation: give `colors` (or one length per colour)")
    if len(ks) > 1 and len(ks) != r:
        raise ValueError(f"lengths gives {len(ks)} colours, the recipe states colors = {r}")
    clauses = formula(p["check"], ks, r, n, p["distinct"])
    steps = data.steps
    last = check_lrat(clauses, steps, n * r)
    added = [s[2] for s in steps[:last] if s[0] == "a"]
    if p["steps"] and len(added) != p["steps"]:
        raise ValueError(f"the proof adds {len(added)} clauses up to the empty one, the recipe states {p['steps']}")
    rows = n
    cell_h = h // rows
    if cell_h < 1 or w < 4:
        raise ValueError(f"data.refutation: {n} numbers do not fit in {w}x{h}; give a larger size")
    ramp = pal.ramp(p["ramp"])
    if r > len(ramp):
        raise ValueError(f"{r} colours, the ramp {p['ramp']!r} has {len(ramp)}")
    tone = [ramp[c * len(ramp) // r] for c in range(r)]          # the colours of data.coloring
    mark = pal.ramp(p["mark_ramp"])
    mark = mark[len(mark) // 2]
    mark_w = max(1, w // 128)
    cols = w - 2 * mark_w                                         # at the right: a gap and the empty clause
    counts = [[[0] * r for _ in range(n)] for _ in range(cols)]
    total = len(added)
    for b in range(cols):                                         # each column: its slice of the proof, at least one
        j0 = b * total // cols                                    # clause, so a short proof is stretched, not striped
        for lits in added[j0:max(j0 + 1, (b + 1) * total // cols)]:
            for l in lits:
                v = abs(l) - 1
                counts[b][v // r][v % r] += 1
    cv = Canvas(w, h, pal)
    if p["background"]:
        cv.rect(0, 0, w - 1, h - 1, pal.ramp(p["background"])[0])
    oy = (h - rows * cell_h) // 2
    for b in range(cols):
        for i in range(n):
            cnt = counts[b][i]
            best = max(range(r), key=lambda c: (cnt[c], -c))
            if cnt[best]:
                cv.rect(b, oy + i * cell_h, b, oy + (i + 1) * cell_h - 2 if cell_h > 2 else oy + i * cell_h, tone[best])
    cv.rect(w - mark_w, oy, w - 1, oy + rows * cell_h - 1, mark)
    return cv
