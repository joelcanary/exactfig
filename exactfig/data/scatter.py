"""
Scattered data: Delaunay triangulation and reconstruction / datos dispersos: triangulación de Delaunay y reconstrucción.

  delaunay     the Delaunay triangulation of n points: a sweep builds any triangulation of the convex hull, then Lawson's
               flips make every edge locally Delaunay, which makes the whole triangulation Delaunay (Lawson 1977). The two
               predicates (orientation and in-circle) are evaluated EXACTLY: every double is an integer times a power of
               two, so the coordinates are scaled to integers and the determinants computed with Python's exact integers.
               Collinear and co-circular points (a regular grid) therefore never produce a wrong or inconsistent answer;
               ties are broken by the input order, so the result is reproducible.
  linear       piecewise-linear interpolation on that triangulation (barycentric coordinates): exact for any affine
               function, continuous, no overshoot; undefined (missing) outside the convex hull of the samples
  nearest      the value of the nearest sample (the Voronoi cells of the samples), ties to the lower index

The result is a w×h raster over a rectangle of the data plane (by default the samples' bounding box), y pointing up.
"""
from __future__ import annotations

import math

MAX_TRIANGULATE = 20_000


class ScatterError(ValueError):
    """Samples that cannot be triangulated or reconstructed (collinear, no area, too many)."""
    pass


def _exact(xs, ys):
    """Integer coordinates X = x · 2^s, Y = y · 2^s for one shift s that makes all of them integers (exact)."""
    dens = [v.as_integer_ratio()[1] for v in xs + ys]
    D = max(dens)
    return ([n * (D // d) for n, d in (v.as_integer_ratio() for v in xs)],
            [n * (D // d) for n, d in (v.as_integer_ratio() for v in ys)])


def delaunay(xs: list[float], ys: list[float]) -> list[tuple[int, int, int]]:
    """Counter-clockwise triangles (indices into the points) of the Delaunay triangulation."""
    n = len(xs)
    if n > MAX_TRIANGULATE:
        raise ScatterError(f"{n} points: the triangulation is limited to {MAX_TRIANGULATE}")
    X, Y = _exact(xs, ys)

    def orient(a, b, c):
        return (X[b] - X[a]) * (Y[c] - Y[a]) - (Y[b] - Y[a]) * (X[c] - X[a])

    def incircle(a, b, c, d):
        """> 0 when d is strictly inside the circle through the counter-clockwise triangle a, b, c."""
        adx, ady = X[a] - X[d], Y[a] - Y[d]
        bdx, bdy = X[b] - X[d], Y[b] - Y[d]
        cdx, cdy = X[c] - X[d], Y[c] - Y[d]
        return ((adx * adx + ady * ady) * (bdx * cdy - cdx * bdy)
                - (bdx * bdx + bdy * bdy) * (adx * cdy - cdx * ady)
                + (cdx * cdx + cdy * cdy) * (adx * bdy - bdx * ady))

    order = sorted(range(n), key=lambda i: (X[i], Y[i], i))
    # first non-collinear point
    k = 2
    while k < n and orient(order[0], order[1], order[k]) == 0:
        k += 1
    if k == n:
        raise ScatterError("all points are collinear: there is no triangle")
    tris: list[list[int]] = []
    q = order[k]
    chain = order[:k]                           # collinear, sorted along their line
    for i in range(k - 1):
        a, b = chain[i], chain[i + 1]
        tris.append([a, b, q] if orient(a, b, q) > 0 else [b, a, q])
    # counter-clockwise hull: along the line and back through q (q on the left), or through q first (q on the right)
    hull = chain + [q] if orient(chain[0], chain[-1], q) > 0 else [chain[0], q] + chain[:0:-1]
    # sweep: each next point is outside the current hull; join it to the hull edges it sees
    for p in order[k + 1:]:
        m = len(hull)
        vis = [orient(hull[i], hull[(i + 1) % m], p) < 0 for i in range(m)]
        s = next(i for i in range(m) if vis[i] and not vis[i - 1])
        cnt = 0
        while vis[(s + cnt) % m]:
            u, v = hull[(s + cnt) % m], hull[(s + cnt + 1) % m]
            tris.append([v, u, p])
            cnt += 1
        hull = [hull[(s + cnt + i) % m] for i in range(m - cnt + 1)] + [p]
    # Lawson flips
    edge = {}
    for t, (a, b, c) in enumerate(tris):
        edge[(a, b)] = t; edge[(b, c)] = t; edge[(c, a)] = t
    stack = [e for e in edge if (e[1], e[0]) in edge and e[0] < e[1]]
    while stack:
        a, b = stack.pop()
        t1, t2 = edge.get((a, b)), edge.get((b, a))
        if t1 is None or t2 is None:
            continue
        c = next(v for v in tris[t1] if v != a and v != b)
        d = next(v for v in tris[t2] if v != a and v != b)
        # t1 = (a, b, c) and t2 = (b, a, d), both counter-clockwise
        if incircle(a, b, c, d) <= 0:
            continue
        for e in ((a, b), (b, c), (c, a)):
            edge.pop(e, None)
        for e in ((b, a), (a, d), (d, b)):
            edge.pop(e, None)
        tris[t1] = [a, d, c]
        tris[t2] = [d, b, c]
        for e in ((a, d), (d, c), (c, a)):
            edge[e] = t1
        for e in ((d, b), (b, c), (c, d)):
            edge[e] = t2
        stack.extend(((a, d), (d, b), (b, c), (c, a)))
    return [tuple(t) for t in tris]


def _raster(xs, ys, w, h, box):
    x0, x1, y0, y1 = box
    sx, sy = (x1 - x0) / w, (y1 - y0) / h
    return ([(px - x0) / sx for px in xs], [(y1 - py) / sy for py in ys])


def bbox(xs, ys) -> tuple[float, float, float, float]:
    """(x0, x1, y0, y1) of the samples; ScatterError if they span no area."""
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    if not (x1 > x0 and y1 > y0):
        raise ScatterError("the samples span no area")
    return x0, x1, y0, y1


def linear(xs, ys, vs, w: int, h: int, box=None, tris=None) -> list[float]:
    """Row-major w×h values of the piecewise-linear interpolant at the pixel centres; NaN outside the hull."""
    box = box or bbox(xs, ys)
    tris = tris if tris is not None else delaunay(xs, ys)
    px, py = _raster(xs, ys, w, h, box)
    out = [math.nan] * (w * h)
    for a, b, c in tris:
        ax, ay, bx, by, cx, cy = px[a], py[a], px[b], py[b], px[c], py[c]
        det = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
        if det == 0.0:
            continue
        i0 = max(0, int(math.floor(min(ax, bx, cx) - 0.5)))
        i1 = min(w - 1, int(math.ceil(max(ax, bx, cx) - 0.5)))
        j0 = max(0, int(math.floor(min(ay, by, cy) - 0.5)))
        j1 = min(h - 1, int(math.ceil(max(ay, by, cy) - 0.5)))
        va, vb, vc = vs[a], vs[b], vs[c]
        for j in range(j0, j1 + 1):
            qy = j + 0.5
            for i in range(i0, i1 + 1):
                qx = i + 0.5
                l1 = ((bx - qx) * (cy - qy) - (by - qy) * (cx - qx)) / det
                l2 = ((cx - qx) * (ay - qy) - (cy - qy) * (ax - qx)) / det
                l3 = 1.0 - l1 - l2
                if l1 >= -1e-12 and l2 >= -1e-12 and l3 >= -1e-12:
                    out[j * w + i] = l1 * va + l2 * vb + l3 * vc
    return out


def nearest(xs, ys, vs, w: int, h: int, box=None) -> list[float]:
    """Row-major w×h values of the nearest sample at each pixel centre (squared distances, ties to the lower index)."""
    box = box or bbox(xs, ys)
    px, py = _raster(xs, ys, w, h, box)
    n = len(xs)
    g = max(1, int(math.sqrt(n / 2)))              # bucket grid over the raster, about two samples per bucket
    cw, ch = w / g, h / g
    buckets: dict = {}
    for k in range(n):
        bx = min(g - 1, max(0, int(px[k] / cw))); by = min(g - 1, max(0, int(py[k] / ch)))
        buckets.setdefault((bx, by), []).append(k)
    out = [math.nan] * (w * h)
    for j in range(h):
        qy = j + 0.5
        for i in range(w):
            qx = i + 0.5
            bx0, by0 = min(g - 1, int(qx / cw)), min(g - 1, int(qy / ch))
            best, bd, r = -1, math.inf, 0
            while True:
                for by in range(by0 - r, by0 + r + 1):
                    for bx in range(bx0 - r, bx0 + r + 1):
                        if max(abs(bx - bx0), abs(by - by0)) != r:
                            continue
                        for k in buckets.get((bx, by), ()):
                            dx, dy = px[k] - qx, py[k] - qy
                            d = dx * dx + dy * dy
                            if d < bd or (d == bd and k < best):
                                best, bd = k, d
                # every sample in an unvisited bucket is at least r·min(cw, ch) away
                reach = r * min(cw, ch)
                if best >= 0 and bd <= reach * reach:
                    break
                if r > g:
                    break
                r += 1
            out[j * w + i] = vs[best]
    return out
