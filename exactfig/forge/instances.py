"""
Instance masks (segmentation), checked before they are drawn / máscaras de instancias, comprobadas antes de dibujarlas.

The checks come from mistakes that are easy to make and that real evaluations punish, or worse, reward:

  empty masks     refused. A mask with no pixel is not an instance; scorers that accept them can be gamed (a few empty
                  masks once scored 1.00 on a public leaderboard).
  overlaps        refused unless `partition` is off (only allowed when drawing raw detections). Instances of one image
                  must not share a pixel: a panoptic evaluator rejects such a submission, and with overlaps a duplicate
                  of a prediction whose IoU exceeds the current PQ raises the score.
  matching        `compare` pairs a prediction with an annotation when IoU > 1/2. Because both sets are partitions, each
                  prediction pairs with at most one annotation and each annotation with at most one prediction (two
                  disjoint sets cannot both cover more than half of a third), so the matching is one-to-one by
                  construction; it is computed exactly with integers.
  stated numbers  `tp`, `fp`, `fn` and `pq` (a decimal such as 0.4326, or a fraction such as 3/7) are compared with the
                  exact values (PQ = Σ IoU over matches / (TP + FP/2 + FN/2), as a fraction); a decimal must equal the
                  exact value rounded to its digits.
  captions        `expect` ("date=2019-05-03;panel=left") must match the data's `meta`, so a caption cannot say what the
                  data does not (a figure once said "2020, top and bottom" for an image of 2019 shown left and right).

Pictures: `instances` draws one set (truth or prediction), each instance in its own hue; `compare` draws both on one
panel: the part of a match both agree on, the part only one of them has, unmatched predictions (false positives) and
unmatched annotations (false negatives), each in its own colour.
"""
from __future__ import annotations

from fractions import Fraction

from ..pixel.canvas import Canvas


def overlap(masks: list) -> tuple | None:
    """(i, j, shared pixels) for the first two masks that share a pixel, or None."""
    owner, shared = {}, {}
    for k, m in enumerate(masks):
        for px in m:
            o = owner.get(px)
            if o is None:
                owner[px] = k
            else:
                shared[(o, k)] = shared.get((o, k), 0) + 1
    if not shared:
        return None
    (i, j), n = min(shared.items())
    return i, j, n


def match(truth: list, pred: list) -> list[tuple[int, int, int, int]]:
    """Pairs (truth index, prediction index, intersection, union) with IoU > 1/2, exactly (2·inter > union). Assumes both
    are partitions, which makes every index appear at most once."""
    owner = {}
    for i, m in enumerate(truth):
        for px in m:
            owner[px] = i
    pairs = []
    for j, m in enumerate(pred):
        inter = {}
        for px in m:
            i = owner.get(px)
            if i is not None:
                inter[i] = inter.get(i, 0) + 1
        for i, n in inter.items():
            union = len(truth[i]) + len(m) - n
            if 2 * n > union:
                pairs.append((i, j, n, union))
    if len({p[0] for p in pairs}) != len(pairs) or len({p[1] for p in pairs}) != len(pairs):
        raise AssertionError("IoU > 1/2 matched an index twice between two partitions")    # impossible: see the module
    return sorted(pairs)


def panoptic_quality(pairs, n_truth: int, n_pred: int) -> dict:
    """TP, FP, FN, the sum of IoU over matches and PQ, as exact fractions (PQ is None when there is nothing at all)."""
    tp = len(pairs)
    fp, fn = n_pred - tp, n_truth - tp
    iou = sum((Fraction(n, u) for _, _, n, u in pairs), Fraction(0))
    den = Fraction(tp) + Fraction(fp + fn, 2)
    return {"tp": tp, "fp": fp, "fn": fn, "iou_sum": iou, "pq": iou / den if den else None,
            "sq": iou / tp if tp else None, "rq": Fraction(tp) / den if den else None}


def _stated(text: str) -> tuple[Fraction, Fraction]:
    """A stated value and the half-width it allows: '0.4326' → (0.4326, 0.00005); '3/7' → (3/7, 0)."""
    t = text.strip()
    try:
        if "/" in t:
            return Fraction(t), Fraction(0)
        if not t.replace(".", "", 1).isdigit():
            raise ValueError
        digits = len(t.split(".")[1]) if "." in t else 0
        return Fraction(t), Fraction(1, 2 * int("1" + "0" * digits))
    except (ValueError, ZeroDivisionError):
        raise ValueError(f"pq {text!r}: give a decimal such as 0.4326 or a fraction such as 3/7") from None


def _expectations(text: str) -> list[tuple[str, str]]:
    out = []
    for part in filter(None, (s.strip() for s in text.split(";"))):
        key, sep, value = part.partition("=")
        if not sep or not key.strip():
            raise ValueError(f"expect {text!r}: write key=value pairs separated by ';'")
        out.append((key.strip(), value.strip()))
    return out


def check(data, p) -> dict:
    """ValueError naming the first mask, pair or number that breaks the recipe's statement; else the exact scores."""
    sets = [("truth", data.truth)] + ([("prediction", data.prediction)] if data.prediction is not None else [])
    for role, masks in sets:
        for k, m in enumerate(masks):
            if not m:
                raise ValueError(f"{role} {k + 1} is an empty mask: an empty mask is not an instance")
        if p["partition"]:
            o = overlap(masks)
            if o:
                raise ValueError(f"{role} {o[0] + 1} and {o[1] + 1} share {o[2]} pixel(s): instances of one image must "
                                 "not overlap (set partition: false only to draw raw detections)")
    for key, value in _expectations(p["expect"]):
        if key not in data.meta:
            raise ValueError(f"expect {key}={value}: the data has no {key!r} in its meta")
        if str(data.meta[key]) != value:
            raise ValueError(f"expect {key}={value}: the data says {key}={data.meta[key]}")
    out = {"truth": len(data.truth)}
    if p["mode"] == "compare":
        if data.prediction is None:
            raise ValueError("mode compare needs a \"prediction\" list in the data")
        if not p["partition"]:
            raise ValueError("mode compare needs partition: true (IoU > 1/2 is one-to-one only between partitions)")
        pairs = match(data.truth, data.prediction)
        s = panoptic_quality(pairs, len(data.truth), len(data.prediction))
        for key in ("tp", "fp", "fn"):
            if p[key] >= 0 and p[key] != s[key]:
                raise ValueError(f"{key} = {s[key]} in the data, the recipe states {p[key]}")
        if p["pq"]:
            if s["pq"] is None:
                raise ValueError("PQ is undefined: no annotation and no prediction")
            value, slack = _stated(p["pq"])
            if abs(s["pq"] - value) > slack:
                raise ValueError(f"PQ = {s['pq']} = {float(s['pq']):.6f} exactly, the recipe states {p['pq']}")
        out.update(pairs=pairs, **s)
    return out


def instances(seed, pal, w, h, p, data) -> Canvas:
    """Generator data.instances: check (see the module), then draw one set of instances, or truth and prediction
    compared, resampled to w×h by nearest pixel."""
    info = check(data, p)
    W, H = data.width, data.height
    bg = pal.ramp(p["background"])[0] if p["background"] else None
    cv = Canvas(w, h, pal)
    colour = {}                                           # data pixel → palette index
    if p["mode"] == "instances":
        masks = data.truth if p["show"] == "truth" or data.prediction is None else data.prediction
        cyc = pal.ramp(p["ramp"])
        for k, m in enumerate(masks):
            c = cyc[(k * 5) % len(cyc)]                       # 5 is coprime with 12: neighbours get distant hues
            for px in m:
                colour[px] = c
    else:
        missing = [r for r in ("seq", "grey", "div") if r not in pal.ramps]
        if missing:
            raise ValueError(f"mode compare needs a palette with seq, grey and div ramps (such as sci); missing {missing}")

        def at(name, t):
            r = pal.ramp(name)
            return r[int(t * (len(r) - 1) + 0.5)]
        both, one = at("seq", 0.85), at("grey", 0.5)     # agreed pixels bright; pixels only one side has, mid grey
        fp_c, fn_c = at("div", 0.8), at("div", 0.2)      # false positives warm, false negatives cool
        matched_t = {i: j for i, j, _, _ in info["pairs"]}
        matched_p = {j for _, j, _, _ in info["pairs"]}
        for j, m in enumerate(data.prediction):
            for px in m:
                colour[px] = one if j in matched_p else fp_c
        for i, m in enumerate(data.truth):
            if i in matched_t:
                mine = set(data.prediction[matched_t[i]])
                for px in m:
                    colour[px] = both if px in mine else one
            else:
                for px in m:
                    colour.setdefault(px, fn_c)           # where a false positive covers it, the false positive shows
    for y in range(h):
        row = (y * H // h) * W
        for x in range(w):
            c = colour.get(row + x * W // w)
            cv.px[y][x] = c if c is not None else bg
    return cv
