"""
A Boolean circuit, checked on every input before it is drawn / un circuito booleano, comprobado en todas sus entradas.

The size of the smallest circuit of two-input gates that computes a function is the most concrete measure of how hard
the function is (lower bounds on it, for explicit functions, are the open core of P versus NP). A search that finds a
small circuit gives the circuit itself as its witness; this generator checks that witness exactly and draws it:

  function   what the circuit must compute on n = `inputs` inputs, the input m = 0..2^n − 1 setting x_i to bit i − 1
             of m:
               mod M R      1 when x_1 + … + x_n ≡ R (mod M)   (e.g. MOD_3 with residue 0, 1 or 2)
               threshold K  1 when x_1 + … + x_n ≥ K           (majority of 5: threshold 3)
               parity       1 when x_1 + … + x_n is odd
               table HEX    the truth table as a hexadecimal number whose bit m is the value on input m
  the check  every gate is evaluated on all 2^n inputs at once (one bit per input, exact integer operations) and the
             output must equal the function on every one; a refusal names the first input where they differ.
  inputs     the file's `inputs n` equals the recipe's (0 = any)
  gates      the file has exactly this many gates (0 = any)
  strict     every gate is used on the way to the output, so `gates` is the size of the circuit and not padding

A circuit that passes is an upper bound: the function needs at most that many gates. That no smaller circuit exists is
a different claim that needs a proof (a refutation of the smaller sizes); the recipe can record its SHA-256 in
`proof_sha256`, which is kept in the manifest but not checked here.

The picture: the inputs on the top row, each gate on the row of its depth (one more than its deeper argument), in file
order within a row; a line from each argument to its gate; the gate's disc coloured by its operation (the 16 two-input
functions taken evenly round the ramp), the output ringed. Along the bottom, the circuit's value on each input m, in
order, one cell per input.
"""
from __future__ import annotations

from .. import fmath as fm
from ..pixel.canvas import Canvas

MAX_TABLE_HEX = 1 << 18          # hex digits of a `table` function (2^20 inputs need 2^18)


def target(spec: str, n: int) -> int:
    """The truth table of `spec` on n inputs as an integer whose bit m is the value on input m."""
    toks = spec.split()
    if not toks:
        raise ValueError("the recipe names no function (mod M R, threshold K, parity or table HEX)")
    kind, args = toks[0], toks[1:]

    def nat(t, what):
        if not (t.isdigit() and t.isascii()) or len(t) > 6:
            raise ValueError(f"function {spec[:60]!r}: {what} {t[:20]!r} is not a natural number")
        return int(t)

    if kind == "table":
        if len(args) != 1:
            raise ValueError("function `table HEX`: one hexadecimal number")
        h = args[0].lower()
        h = h[2:] if h.startswith("0x") else h
        if not h or len(h) > MAX_TABLE_HEX or any(c not in "0123456789abcdef" for c in h):
            raise ValueError(f"function `table`: {args[0][:40]!r} is not a hexadecimal number")
        t = int(h, 16)
        if t >> (1 << n):
            raise ValueError(f"function `table`: the table has bits beyond input {(1 << n) - 1} (n = {n})")
        return t
    if kind == "parity" and not args:
        test = lambda s: s % 2 == 1
    elif kind == "mod" and len(args) == 2:
        m, r = nat(args[0], "the modulus"), nat(args[1], "the residue")
        if m < 2 or r >= m:
            raise ValueError(f"function `mod M R`: M ≥ 2 and 0 ≤ R < M (got {m}, {r})")
        test = lambda s: s % m == r
    elif kind == "threshold" and len(args) == 1:
        k = nat(args[0], "the threshold")
        test = lambda s: s >= k
    else:
        raise ValueError(f"function {spec[:60]!r}: use mod M R, threshold K, parity or table HEX")
    t = 0
    for i in range(1 << n):
        if test(bin(i).count("1")):
            t |= 1 << i
    return t


def evaluate(circ) -> dict:
    """{name: truth table} of every input and gate, each an integer with bit m = its value on input m."""
    n = circ.inputs
    full = (1 << (1 << n)) - 1
    val = {}
    for i in range(1, n + 1):
        t = 0
        for m in range(1 << n):
            if m >> (i - 1) & 1:
                t |= 1 << m
        val[f"x{i}"] = t
    for name, table, a, b in circ.gates:
        va, vb = val[a], val[b]
        na, nb = full & ~va, full & ~vb
        r = 0
        if table[0] == "1":
            r |= na & nb
        if table[1] == "1":
            r |= na & vb
        if table[2] == "1":
            r |= va & nb
        if table[3] == "1":
            r |= va & vb
        val[name] = r
    return val


def check(circ, p) -> dict:
    """Raise ValueError naming the first broken condition; else {"inputs", "gates", "depth"}."""
    n = circ.inputs
    if p["inputs"] and n != p["inputs"]:
        raise ValueError(f"the circuit has {n} inputs, the recipe states {p['inputs']}")
    if p["gates"] and len(circ.gates) != p["gates"]:
        raise ValueError(f"the circuit has {len(circ.gates)} gates, the recipe states {p['gates']}")
    if p["strict"]:
        args = {name: (a, b) for name, _, a, b in circ.gates}
        used, todo = {circ.output}, [circ.output]
        while todo:
            for x in args.get(todo.pop(), ()):
                if x not in used:
                    used.add(x)
                    todo.append(x)
        dead = [name for name, _, _, _ in circ.gates if name not in used]
        if dead:
            raise ValueError(f"gate {dead[0]} does not lead to the output ({len(dead)} unused; strict counts only "
                             f"gates that are used)")
    want = target(p["function"], n)
    got = evaluate(circ)[circ.output]
    if got != want:
        diff = got ^ want
        m = (diff & -diff).bit_length() - 1
        xs = " ".join(f"x{i}={m >> (i - 1) & 1}" for i in range(1, n + 1))
        raise ValueError(f"on input m = {m} ({xs}) the circuit gives {got >> m & 1}, the function {want >> m & 1}")
    return {"inputs": n, "gates": len(circ.gates), "depth": max(depths(circ).values())}


def depths(circ) -> dict:
    """{name: depth}: 0 for an input, 1 + the deeper argument for a gate."""
    d = {f"x{i}": 0 for i in range(1, circ.inputs + 1)}
    for name, _, a, b in circ.gates:
        d[name] = 1 + max(d[a], d[b])
    return d


def circuit(seed, pal, w, h, p, data) -> Canvas:
    """Generator data.circuit: check (see the module), then the circuit by depth, inputs on top, truth row below."""
    circ = data
    check(circ, p)
    n = circ.inputs
    d = depths(circ)
    rows = {}
    for name in [f"x{i}" for i in range(1, n + 1)] + [g[0] for g in circ.gates]:
        rows.setdefault(d[name], []).append(name)
    depth = max(rows)
    ops = {name: table for name, table, _, _ in circ.gates}
    cv = Canvas(w, h, pal)
    if p["background"]:
        cv.rect(0, 0, w - 1, h - 1, pal.ramp(p["background"])[0])
    pad = max(2, min(w, h) // 24)
    strip = max(3, h // 10)                                          # the truth row along the bottom
    top, bottom = pad, h - pad - strip - pad
    widest = max(len(v) for v in rows.values())
    r = max(1, int(fm.floor(min((bottom - top) / (3.0 * (depth + 1)), (w - 2 * pad) / (3.0 * widest)) + 0.5)))
    gap_y = (bottom - top - 2 * r) / max(1, depth)
    args = {name: (a, b) for name, _, a, b in circ.gates}
    lo, hi = pad + r, w - pad - r
    fx = {}
    for k in range(depth + 1):
        names = rows.get(k, [])
        if k == 0:
            for j, name in enumerate(names):
                fx[name] = pad + (w - 2 * pad) * (j + 0.5) / len(names)
            continue
        want = sorted(((fx[args[nm][0]] + fx[args[nm][1]]) / 2.0, j, nm) for j, nm in enumerate(names))
        gap = min(3.0 * r, (hi - lo) / max(1, len(want) - 1))        # a gate sits midway between its arguments,
        xs = [x for x, _, _ in want]                                   # pushed apart to `gap` within its row
        for i in range(1, len(xs)):
            xs[i] = max(xs[i], xs[i - 1] + gap)
        shift = max(0.0, xs[-1] - hi)
        xs = [x - shift for x in xs]
        for i in range(len(xs) - 2, -1, -1):
            xs[i] = min(xs[i], xs[i + 1] - gap)
        shift = max(0.0, lo - xs[0])
        for (_, _, nm), x in zip(want, xs):
            fx[nm] = x + shift
    pos = {}
    for k, names in rows.items():
        y = top + r + gap_y * k if depth else (top + bottom) / 2.0
        for name in names:
            pos[name] = (int(fm.floor(fx[name] + 0.5)), int(fm.floor(y + 0.5)))
    er = pal.ramp(p["edge_ramp"])
    edge = er[len(er) // 2]                                          # a middle step: the first is the darkest
    for name, _, a, b in circ.gates:
        for arg in (a, b):
            (x0, y0), (x1, y1) = pos[arg], pos[name]
            cv.line(x0, y0, x1, y1, edge)
    ramp = pal.ramp(p["ramp"])
    ir = pal.ramp(p["input_ramp"])
    mark = pal.ramp(p["mark_ramp"])
    for name, (x, y) in pos.items():
        if name in ops:
            col = ramp[int(ops[name], 2) * len(ramp) // 16]
        else:
            col = ir[len(ir) // 2]
        cv.disc(x, y, r, col)
    ox, oy = pos[circ.output]
    cv.circle(ox, oy, r + max(1, r // 3), mark[len(mark) // 2])
    out = evaluate(circ)[circ.output]
    cells = 1 << n
    span = w - 2 * pad
    on, off = mark[len(mark) // 2], er[0]
    for m in range(cells):
        x0 = pad + span * m // cells
        x1 = pad + span * (m + 1) // cells - 1
        if x1 - x0 >= 2:
            x1 -= 1                                                  # a one-pixel gap between cells that are wide
        cv.rect(x0, h - pad - strip, max(x0, x1), h - pad - 1, on if out >> m & 1 else off)
    return cv
