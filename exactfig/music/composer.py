"""
Compositor: de una sucesión matemática a una pieza en bucle, con oficio de compositor.

1. La fuente da las notas ESTRUCTURALES de la melodía (una por tiempo fuerte). Se elige su octava (la más cercana a la
   anterior, dentro de un registro), así una sucesión de grados se vuelve una línea cantable.
2. Se ARMONIZA esa melodía dada, como un cantus firmus: cada compás un acorde que contiene la nota del tiempo fuerte,
   elegido por programación dinámica (theory.harmonize) con cadencias en su sitio: semicadencia al final de cada frase
   de 4 compases, cadencia a la tónica al final de cada 8, y el último compás en dominante para que el bucle resuelva
   en el primero.
3. DISMINUCIÓN: entre dos notas estructurales se rellenan notas de paso y floreos con ritmos de un vocabulario de
   células; los compases 1 y 3 de cada frase comparten ritmo (motivo), el 4 cierra con nota larga y respiración.
4. Acompañamiento con conducción de voces óptima (theory.best_voicing), bajo, contramelodía (tonos del acorde bajo la
   melodía, por movimiento mínimo) y una capa de campanas que dibuja la estructura matemática (primos, celdas vivas...).
5. Noche = el mismo tema, más lento, solo notas estructurales y timbres suaves. Combate = capa que suena ENCIMA de la de
   día, mismo tempo y duración, sobre los mismos acordes (ostinato de cuerda, metales, timbales y tambores).

English: a mathematical sequence gives the structural melody notes; the melody is harmonised by dynamic programming with
cadences in place, decorated with passing notes from a rhythm-cell vocabulary, and accompanied with optimal voice leading.
`kind` = "day" (full), "night" (slower, structural notes only) or "combat" (a layer that plays over "day").
"""
from .theory import MODES, CADENCE, FUNCTIONS, pitch, chord_pcs, harmonize, best_voicing
from .sources import SOURCES

E8 = 240   # un octavo con 480 ticks por negra
METERS = {
    "4/4": dict(beats=4, unit=4, bar=1920, slots=2, seg=4),
    "3/4": dict(beats=3, unit=4, bar=1440, slots=1, seg=6),
    "6/8": dict(beats=6, unit=8, bar=1440, slots=2, seg=3),
}
CELLS = {
    4: [[4], [3, 1], [2, 2], [2, 1, 1], [1, 1, 2], [1, 1, 1, 1], [1, 2, 1]],
    6: [[6], [4, 2], [2, 2, 2], [3, 1, 2], [2, 1, 1, 2], [4, 1, 1], [2, 4], [3, 3]],
    3: [[3], [2, 1], [1, 1, 1], [1, 2]],
}
CADENCE_CELLS = {4: [[4], [3, -1], [2, -2]], 6: [[6], [4, -2], [5, -1]], 3: [[3], [2, -1]]}
DENSITY = {   # preferencia por número de notas de la célula (1..4); en 3/4 una sola nota es un compás entero quieto
    "calm": {1: 1.5, 2: 5, 3: 3, 4: 0.8},
    "flow": {1: 0.6, 2: 4, 3: 5, 4: 2},
    "lively": {1: 0.2, 2: 2, 3: 5, 4: 5},
}

# Instrumentos General MIDI y su registro cómodo (para encajar cada pista y para validar)
GM_RANGE = {
    0: (36, 96), 4: (40, 88), 8: (60, 108), 9: (72, 108), 10: (60, 100), 11: (53, 89), 12: (45, 96), 13: (65, 108),
    14: (60, 77), 15: (48, 84), 19: (36, 96), 24: (40, 83), 32: (28, 55), 33: (28, 55), 35: (28, 55), 42: (36, 76),
    43: (28, 55), 45: (36, 96), 46: (24, 103), 47: (36, 57), 48: (36, 96), 49: (36, 96), 52: (48, 79), 53: (48, 79),
    60: (41, 77), 61: (36, 79), 68: (58, 91), 69: (52, 81), 70: (34, 72), 71: (50, 91), 73: (60, 96), 74: (60, 96),
    75: (60, 96), 79: (60, 96), 88: (36, 96), 89: (36, 96), 91: (36, 96), 92: (36, 96), 94: (36, 96), 104: (48, 77),
    107: (48, 84), 108: (55, 84), 112: (72, 96), 113: (60, 84), 115: (60, 84),
}

P = dict(piano=0, epiano=4, celesta=8, glock=9, musicbox=10, vibes=11, marimba=12, xylo=13, tubular=14, organ=19,
         guitar=24, bass=32, fbass=33, fretless=35, cello=42, contrabass=43, pizz=45, harp=46, timpani=47, strings=48,
         slowstr=49, choir=52, oohs=53, horn=60, brass=61, oboe=68, ehorn=69, bassoon=70, clarinet=71, flute=73,
         recorder=74, panflute=75, ocarina=79, newage=88, warm=89, choirpad=91, glass=92, halo=94, sitar=104,
         koto=107, kalimba=108, agogo=113, woodblock=115)

ENSEMBLES = {   # (los antiguos «palettes» de timbres: aquí «ensembles» para no confundir con las paletas de color)
    #          melodía     melodía B    contramelodía pad          acompañamiento     bajo          campanas     noche: melodía, pad, acomp.
    "town":    ("flute", "clarinet", "cello", "strings", ("harp", "arp"), ("bass", "root5"), "glock", ("flute", "warm", "harp")),
    "forest":  ("panflute", "oboe", "cello", "slowstr", ("guitar", "arp"), ("contrabass", "whole"), "kalimba", ("ocarina", "halo", "harp")),
    "coast":   ("oboe", "flute", "horn", "choir", ("harp", "arp"), ("bass", "root5"), "tubular", ("flute", "halo", "harp")),
    "meadow":  ("clarinet", "flute", "bassoon", "strings", ("guitar", "arp"), ("pizz", "root5"), "marimba", ("ehorn", "warm", "guitar")),
    "hills":   ("horn", "oboe", "cello", "strings", ("harp", "harp"), ("contrabass", "root5"), "tubular", ("clarinet", "slowstr", "harp")),
    "snow":    ("celesta", "flute", "cello", "glass", ("harp", "arp"), ("contrabass", "whole"), "glock", ("musicbox", "halo", "harp")),
    "frost":   ("ehorn", "clarinet", "cello", "warm", ("harp", "harp"), ("fretless", "whole"), "vibes", ("oohs", "halo", "harp")),
    "glow":    ("vibes", "flute", "cello", "newage", ("marimba", "arp"), ("fretless", "root5"), "kalimba", ("vibes", "halo", "harp")),
    "fire":    ("horn", "cello", "bassoon", "slowstr", ("pizz", "pulse"), ("contrabass", "root5"), "tubular", ("ehorn", "warm", "harp")),
    "wind":    ("panflute", "flute", "cello", "glass", ("harp", "arp"), ("fretless", "whole"), "glock", ("ocarina", "halo", "harp")),
    "desert":  ("oboe", "panflute", "bassoon", "slowstr", ("sitar", "arp"), ("bass", "root5"), "kalimba", ("flute", "halo", "koto")),
    "dark":    ("cello", "ehorn", "clarinet", "choir", ("harp", "harp"), ("contrabass", "whole"), "celesta", ("oohs", "choirpad", "harp")),
    "grey":    ("horn", "cello", "bassoon", "strings", ("harp", "arp"), ("contrabass", "root5"), "tubular", ("clarinet", "warm", "harp")),
    "ruins":   ("recorder", "ocarina", "cello", "choir", ("harp", "harp"), ("contrabass", "pedal"), "tubular", ("ocarina", "choirpad", "harp")),
    "mist":    ("ocarina", "ehorn", "cello", "halo", ("harp", "arp"), ("fretless", "whole"), "vibes", ("ocarina", "halo", "harp")),
    "island":  ("flute", "oboe", "cello", "choir", ("harp", "arp"), ("bass", "root5"), "kalimba", ("flute", "halo", "harp")),
    "mine":    ("marimba", "clarinet", "bassoon", "strings", ("pizz", "pulse"), ("fbass", "walk"), "xylo", None),
    "roots":   ("cello", "clarinet", "bassoon", "slowstr", ("kalimba", "arp"), ("contrabass", "whole"), "vibes", None),
    "crypt":   ("celesta", "oohs", "cello", "choir", ("harp", "harp"), ("contrabass", "whole"), "glock", None),
    "archive": ("flute", "celesta", "cello", "glass", ("harp", "arp"), ("contrabass", "whole"), "musicbox", None),
    "vault":   ("vibes", "horn", "cello", "strings", ("harp", "arp"), ("bass", "root5"), "glock", None),
    "forge":   ("horn", "cello", "bassoon", "slowstr", ("pizz", "pulse"), ("contrabass", "root5"), "tubular", None),
    "throne":  ("horn", "choir", "cello", "organ", ("strings", "chorale"), ("contrabass", "whole"), "tubular", None),
    "battle":  ("brass", "horn", "cello", "strings", ("pizz", "pulse"), ("contrabass", "root5"), "tubular", None),
    "home":    ("piano", "flute", "cello", "strings", ("harp", "arp"), ("bass", "root5"), "musicbox", ("epiano", "warm", "harp")),
    "moon":    ("celesta", "oohs", "cello", "halo", ("harp", "harp"), ("fretless", "whole"), "glock", ("musicbox", "halo", "harp")),
    "sea":     ("horn", "oboe", "cello", "strings", ("harp", "lilt"), ("contrabass", "lilt"), "tubular", ("clarinet", "halo", "harp")),
    # elementos
    "spiral":  ("ocarina", "panflute", "cello", "halo", ("kalimba", "arp"), ("fretless", "whole"), "vibes", ("ocarina", "halo", "harp")),
    "grove":   ("recorder", "oboe", "cello", "slowstr", ("koto", "arp"), ("contrabass", "whole"), "kalimba", ("ocarina", "halo", "koto")),
    "flame":   ("cello", "horn", "bassoon", "warm", ("pizz", "pulse"), ("contrabass", "pedal"), "tubular", ("ehorn", "warm", "harp")),
    "gravity": ("horn", "cello", "bassoon", "slowstr", ("strings", "chorale"), ("contrabass", "pedal"), "tubular", ("cello", "slowstr", "harp")),
    "ether":   ("celesta", "flute", "cello", "glass", ("musicbox", "arp"), ("fretless", "whole"), "glock", ("musicbox", "halo", "harp")),
    "void":    ("ehorn", "cello", "clarinet", "choirpad", ("harp", "harp"), ("contrabass", "whole"), "celesta", ("oohs", "choirpad", "harp")),
}

# octava de la melodía según el instrumento (respecto a la tónica de la pieza)
MEL_SHIFT = {"celesta": 12, "glock": 12, "musicbox": 12, "cello": -12, "bassoon": -12}   # solo octavas: otra cosa transporta


class Rng:
    """xorshift32: la misma semilla, la misma pieza."""
    def __init__(self, seed):
        self.s = seed & 0xFFFFFFFF or 1

    def next(self):
        s = self.s
        s ^= (s << 13) & 0xFFFFFFFF; s ^= s >> 17; s ^= (s << 5) & 0xFFFFFFFF
        self.s = s
        return s

    def pick(self, items, weights):
        tot = sum(weights)
        x = (self.next() / 0xFFFFFFFF) * tot
        for it, w in zip(items, weights):
            x -= w
            if x <= 0:
                return it
        return items[-1]


def fnv(text):
    h = 2166136261
    for c in text.encode():
        h = ((h ^ c) * 16777619) & 0xFFFFFFFF
    return h


def sections(bars):
    if bars <= 16:
        return ["A"] * 8 + ["B"] * (bars - 8)
    if bars <= 24:
        return ["A"] * 8 + ["B"] * 8 + ["A2"] * (bars - 16)
    return ["A"] * 8 + ["A2"] * 8 + ["B"] * 8 + ["A3"] * (bars - 24)


def fold(raw, lo, hi):
    """Octava de cada grado: la más cercana a la nota anterior, dentro de [lo, hi]."""
    out, prev = [], None
    for d in raw:
        base = d % 7
        cands = [base + 7 * k for k in range(-3, 4) if lo <= base + 7 * k <= hi]
        if not cands:
            cands = [min(max(base, lo), hi)]
        cur = cands[0] if prev is None else min(cands, key=lambda c: (abs(c - prev), c))
        if prev is None:
            cur = min(cands, key=lambda c: abs(c - (lo + hi) / 2))
        out.append(cur)
        prev = cur
    return out


def chord_degrees(r):
    return {(r + k) % 7 for k in (0, 2, 4)}


def snap_to_chord(d, r, prev):
    tones = chord_degrees(r)
    if d % 7 in tones:
        return d
    cands = [d + s for s in (-1, 1, -2, 2) if (d + s) % 7 in tones]
    return min(cands, key=lambda c: (abs(c - d), abs(c - prev)))


def figure(a, b, n):
    """n notas de a hacia b (b llega en el siguiente tiempo fuerte): notas de paso, floreos o bordaduras."""
    if n == 1:
        return [a]
    diff = b - a
    s = 1 if diff > 0 else -1
    if diff == 0:
        return [a, a + 1, a, a - 1][:n] if n != 3 else [a, a + 1, a - 1]
    if abs(diff) >= n:
        return [a + round(diff * k / n) for k in range(n)]
    core = [a] + [a + s * k for k in range(1, abs(diff))]
    need = n - len(core)
    if need == 1:
        return [a, a - s] + core[1:]
    if need == 2:
        return [a, a - s, a] + core[1:]
    return [a, a + s, a, a - s][:n]


def plan(spec):
    """Lo común a día, noche y combate: compás, escala, notas estructurales y acordes."""
    m = METERS[spec["meter"]]
    bars = spec["bars"]
    slots = bars * m["slots"]
    mode = spec["mode"]
    src = SOURCES[spec["source"]](slots, bars, **spec.get("args", {}))
    raw = src["skeleton"][:slots]
    if len(raw) < slots:
        raw = (raw * (slots // max(1, len(raw)) + 1))[:slots]
    lo, hi = spec.get("range", (-2, 8))
    deg = fold(raw, lo, hi)
    half, pre = CADENCE[mode]
    cad = {0: [0]}
    for b in range(1, bars):
        pos = b % 8
        if b == bars - 1:
            cad[b] = half
        elif pos == 3:
            cad[b] = half
        elif pos == 6 and b != bars - 2:
            cad[b] = pre
        elif pos == 7:
            cad[b] = [0]
    roots, down = harmonize(mode, [deg[b * m["slots"]] for b in range(bars)], cad)
    for b in range(bars):
        deg[b * m["slots"]] = down[b]
        for k in range(1, m["slots"]):
            j = b * m["slots"] + k
            deg[j] = snap_to_chord(deg[j], roots[b], deg[j - 1])
    return dict(spec=spec, m=m, bars=bars, slots=slots, mode=mode, scale=MODES[mode], tonic=spec["tonic"], src=src,
                deg=deg, roots=roots, sect=sections(bars), raw=raw)


def _vel(x):
    return max(1, min(127, round(x)))


def _fit(notes, prog):
    """Mueve la pista entera por octavas para que su mediana caiga en el registro cómodo del instrumento."""
    lo, hi = GM_RANGE.get(prog, (24, 108))
    if not notes:
        return notes
    ps = sorted(n[2] for n in notes)
    med = ps[len(ps) // 2]
    shift = 0
    while med + shift < lo + 4 and shift < 36:
        shift += 12
    while med + shift > hi - 4 and shift > -36:
        shift -= 12
    return [(t, d, p + shift, v) for t, d, p, v in notes]


def _track(name, ch, prog, notes, volume=100, pan=64):
    notes = _fit(notes, prog) if prog is not None else notes
    return dict(name=name, channel=ch, program=prog, volume=volume, pan=pan, notes=sorted(notes))


def voicings_for(pl, lush):
    scale, tonic = pl["scale"], pl["tonic"]
    out, prev = [], None
    fn = FUNCTIONS[pl["mode"]]
    for b, r in enumerate(pl["roots"]):
        seventh = lush and fn[r] != "T"
        pcs = chord_pcs(scale, tonic % 12, r, seventh)
        v = best_voicing(prev, pcs, tonic - 19, tonic + 2, 4)
        out.append(v)
        prev = v
    return out


def compose_day(pl, night=False):
    spec, m, scale, tonic = pl["spec"], pl["m"], pl["scale"], pl["tonic"]
    pal = ENSEMBLES[spec["ensemble"]]
    mel_i, mel2_i, ctr_i, pad_i, (acc_i, acc_style), (bass_i, bass_style), feat_i, night_pal = pal
    if night:
        mel_i, pad_i, acc_i = night_pal
        acc_style = "harp"
    bar, seg, slots_pb = m["bar"], m["seg"], m["slots"]
    slot_ticks = bar // slots_pb
    rng = Rng(fnv(str(spec["seed"]) + ("n" if night else "")))
    dens = DENSITY[spec.get("density", "flow")]
    src = pl["src"]
    dyn = src.get("dyn") or [0.6] * pl["bars"]
    mask = src.get("mask") or {}
    lush = spec.get("lush", True)
    voic = voicings_for(pl, lush)
    sect = pl["sect"]
    deg = pl["deg"]
    mshift = MEL_SHIFT.get(mel_i, 0)

    # ---- melodía
    mel, mel2 = [], []
    rhythm_cache = {}
    for j in range(pl["slots"]):
        b, k = divmod(j, slots_pb)
        a, nxt = deg[j], deg[(j + 1) % pl["slots"]]
        cadence = k == slots_pb - 1 and b % 4 == 3
        s_letter = "B" if sect[b] == "B" else "A"
        if night:
            cell = [seg] if not cadence else CADENCE_CELLS[seg][1]
        elif cadence:
            cell = rng.pick(CADENCE_CELLS[seg], [3, 4, 2][:len(CADENCE_CELLS[seg])])
        else:
            key = (s_letter, 0 if b % 4 in (0, 2) else b % 4, k)
            if key not in rhythm_cache:
                w = [dens[len(c)] * (1.3 if s_letter == "B" and len(c) >= 3 else 1) * (0.25 if seg == 6 and len(c) == 1 else 1)
                     for c in CELLS[seg]]
                rhythm_cache[key] = rng.pick(CELLS[seg], w)
            cell = rhythm_cache[key]
        notes_n = sum(1 for d in cell if d > 0)
        fig = figure(a, nxt, notes_n)
        t = b * bar + k * slot_ticks
        idx = 0
        arc = 0.9 + 0.12 * [0.2, 0.6, 1.0, 0.4][b % 4]
        for d in cell:
            if d > 0:
                accent = 1.0 if idx == 0 and k == 0 else 0.93 if idx == 0 else 0.84
                v = (64 if night else 86) * accent * arc * (0.82 + 0.36 * dyn[b % len(dyn)])
                p = pitch(scale, tonic + mshift, fig[idx])
                dur = d * E8 - (30 if not night else 10)
                (mel2 if sect[b] == "B" and not night else mel).append((t, dur, p, _vel(v)))
                idx += 1
            t += abs(d) * E8

    if night:   # de noche, dos notas estructurales iguales seguidas son una sola nota larga
        merged = []
        for n in sorted(mel):
            if merged and merged[-1][2] == n[2] and merged[-1][0] + merged[-1][1] + 10 >= n[0] and n[0] % bar != 0:
                t0, d0, p0, v0 = merged[-1]
                merged[-1] = (t0, n[0] + n[1] - t0, p0, v0)
            else:
                merged.append(n)
        mel = merged

    # ---- pad (conducción de voces óptima; acordes iguales seguidos se ligan)
    pad = []
    for b, v in enumerate(voic):
        if b > 0 and voic[b - 1] == v and b % 4 != 0:
            pad = [(t, d + bar if t + d == b * bar and p in v else d, p, vv) for t, d, p, vv in pad]
            continue
        for p in v:
            pad.append((b * bar, bar, p, _vel((46 if night else 52) * (0.85 + 0.3 * dyn[b % len(dyn)]))))

    # ---- acompañamiento
    acc = []
    eighths = bar // E8
    arp_pats = [[0, 1, 2, 3, 4, 3, 2, 1], [0, 2, 1, 3, 2, 4, 3, 1], [0, 1, 2, 4, 3, 2, 1, 2], [0, 2, 4, 2, 3, 1, 3, 2]]
    pat = arp_pats[fnv(str(spec["seed"])) % len(arp_pats)]
    for b, v in enumerate(voic):
        if mask.get("acc") and not mask["acc"][b]:
            continue
        up = sorted(list(v) + [v[1] + 12])
        t0 = b * bar
        accv = (44 if night else 56) * (0.85 + 0.3 * dyn[b % len(dyn)])
        if acc_style == "arp":
            step = E8 if spec["bpm"] < 90 or spec["meter"] != "4/4" else E8
            for i in range(eighths):
                acc.append((t0 + i * step, 2 * E8, up[pat[i % len(pat)] % len(up)] + 12, _vel(accv * (1 if i % 2 == 0 else 0.86))))
        elif acc_style == "harp":
            for k in range(slots_pb if not night else 1):
                for n_i, p in enumerate(up):
                    acc.append((t0 + k * slot_ticks + n_i * 36, slot_ticks if not night else bar, p + 12, _vel(accv * (0.9 + 0.03 * n_i))))
        elif acc_style == "pulse":
            for i in range(m["beats"] if m["unit"] == 4 else 2):
                q = bar // (m["beats"] if m["unit"] == 4 else 2)
                for p in v[1:]:
                    acc.append((t0 + i * q, E8, p + 12, _vel(accv * (1 if i == 0 else 0.85))))
        elif acc_style == "lilt":
            for i in (1, 2, 4, 5):
                for p in v[1:]:
                    acc.append((t0 + i * E8, E8, p + 12, _vel(accv * 0.85)))
        elif acc_style == "chorale":
            for k in range(slots_pb):
                for p in v:
                    acc.append((t0 + k * slot_ticks, slot_ticks, p + 12, _vel(accv)))

    # ---- bajo
    bass, prevb = [], None
    blo, bhi = tonic - 31, tonic - 13
    for b, r in enumerate(pl["roots"]):
        if mask.get("bass") and not mask["bass"][b]:
            continue
        rpc = (tonic + pitch(scale, 0, r)) % 12
        fifth_pc = (tonic + pitch(scale, 0, r + 4)) % 12
        def near(pc):
            cands = [p for p in range(blo, bhi + 1) if p % 12 == pc]
            return min(cands, key=lambda p: abs(p - (prevb if prevb is not None else (blo + bhi) / 2)))
        t0 = b * bar
        vb = (60 if night else 72) * (0.85 + 0.3 * dyn[b % len(dyn)])
        style = "whole" if night else bass_style
        if style == "pedal":
            p = near(tonic % 12); bass.append((t0, bar, p, _vel(vb)))
        elif style == "root5" and spec["meter"] != "3/4":
            p = near(rpc); bass.append((t0, bar // 2, p, _vel(vb)))
            q = near(fifth_pc); bass.append((t0 + bar // 2, bar // 2, q, _vel(vb * 0.85))); p = q
        elif style == "walk" and spec["meter"] == "4/4":
            p = near(rpc); bass.append((t0, 960, p, _vel(vb)))
            q = near(fifth_pc); bass.append((t0 + 960, 480, q, _vel(vb * 0.85)))
            nr = pl["roots"][(b + 1) % pl["bars"]]
            npc = (tonic + pitch(scale, 0, nr)) % 12
            target = near(npc)
            bass.append((t0 + 1440, 480, target + (1 if target < q else -1), _vel(vb * 0.8)))
            p = q
        elif style == "lilt":
            p = near(rpc); bass.append((t0, bar // 2, p, _vel(vb)))
            q = near(fifth_pc); bass.append((t0 + bar // 2, bar // 2, q, _vel(vb * 0.85)))
        else:
            p = near(rpc); bass.append((t0, bar, p, _vel(vb)))
        prevb = p

    # ---- contramelodía (secciones B y A2/A3): tono del acorde bajo la melodía, el que menos se mueve
    ctr, prevc = [], None
    if not night:
        for j in range(pl["slots"]):
            b, k = divmod(j, slots_pb)
            if sect[b] == "A":
                continue
            d = deg[j]
            tones = sorted(c for c in range(d - 7, d - 1) if c % 7 in chord_degrees(pl["roots"][b]))
            c = tones[-1] if prevc is None else min(tones, key=lambda c: (abs(c - prevc), -c))
            ctr.append((b * bar + k * slot_ticks, slot_ticks - 20, pitch(scale, tonic, c), _vel(60 * (0.85 + 0.3 * dyn[b % len(dyn)]))))
            prevc = c

    # ---- campanas: la estructura de la fuente
    feat = []
    feat_all = spec.get("feature_all", False) or night
    for (tb, idx) in src.get("feature", []):
        b = int(tb)
        if b >= pl["bars"] or (not feat_all and sect[b] == "A"):
            continue
        if mask.get("feature") and not mask["feature"][b]:
            continue
        r = pl["roots"][b]
        off = [0, 2, 4, 7, 9, 11][idx % 6]
        p = pitch(scale, tonic + 12, r + off)
        t = int(round(tb * bar / 20.0)) * 20
        feat.append((t, min(3 * E8, (b + 1) * bar - t), p, _vel((40 if night else 52) * (0.9 + 0.2 * ((idx + b) % 2)))))

    # ---- percusión suave
    perc = []
    if not night:
        if src.get("perc"):
            for tb, note, vel in src["perc"]:
                b = int(tb)
                if b < pl["bars"]:
                    perc.append((int(round(tb * bar / 20.0)) * 20, E8 // 2, note, _vel(vel * 0.8)))
        elif spec.get("perc") == "hand":
            for b in range(pl["bars"]):
                if sect[b] == "A" and b < 4:
                    continue
                for i in range(eighths):
                    if (i * 3) % eighths < 3:
                        perc.append((b * bar + i * E8, E8, 45 if i == 0 else 47, _vel(54 if i == 0 else 42)))
                    if i % 2 == 1:
                        perc.append((b * bar + i * E8, E8 // 2, 70, 30))

    mi = P[mel_i]
    tracks = [_track("Melody", 0, mi, mel, 100, 72)]
    if mel2:
        tracks.append(_track("Melody B", 1, P[mel2_i], [(t, d, p + MEL_SHIFT.get(mel2_i, 0) - mshift, v) for t, d, p, v in mel2], 96, 56))
    tracks += [_track("Pad", 2, P[pad_i], pad, 78, 64),
               _track("Accompaniment", 3, P[acc_i], acc, 84, 44),
               _track("Bass", 4, P[bass_i], bass, 96, 64)]
    if ctr:
        tracks.append(_track("Counter", 5, P[ctr_i], ctr, 80, 84))
    if feat:
        tracks.append(_track("Bells", 6, P[feat_i], feat, 74, 96))
    if perc:
        tracks.append(_track("Percussion", 9, None, perc, 70, 64))
    return tracks


def compose_combat(pl):
    """Capa de combate: encima de la de día, mismos acordes, mismo tempo y duración."""
    m, scale, tonic = pl["m"], pl["scale"], pl["tonic"]
    bar = m["bar"]
    eighths = bar // E8
    ost, brass, timp, drums = [], [], [], []
    voic = voicings_for(pl, False)
    for b, r in enumerate(pl["roots"]):
        t0 = b * bar
        rpc = (tonic + pitch(scale, 0, r)) % 12
        fpc = (tonic + pitch(scale, 0, r + 4)) % 12
        root = next(p for p in range(tonic - 30, tonic - 17) if p % 12 == rpc)
        fifth = next(p for p in range(root, root + 12) if p % 12 == fpc)
        for i in range(eighths):
            p = fifth if i % 4 == 2 else root + (12 if i % 4 == 3 else 0)
            ost.append((t0 + i * E8, E8 - 15, p, _vel(80 if i % 2 == 0 else 66)))
        v = voic[b]
        brass += [(t0, 420, p, 84) for p in v[1:]]
        if b % 2 == 1:
            brass += [(t0 + bar - 2 * E8, 2 * E8 - 20, p, 76) for p in v[1:]]
        tim = next(p for p in range(38, 55) if p % 12 == rpc)
        timp.append((t0, 300, tim, 90))
        timp.append((t0 + bar // 2, 300, next(p for p in range(38, 55) if p % 12 == fpc), 74))
        for i in range(eighths):
            if (i * 3) % eighths < 3:
                drums.append((t0 + i * E8, E8, 36, 92 if i == 0 else 78))
        for i in range(eighths * 2):
            if (i * 5) % (eighths * 2) < 5:
                drums.append((t0 + i * (E8 // 2), E8 // 2, [45, 47, 50][(b + i) % 3], 70))
        if b % 8 == 0:
            drums.append((t0, E8 * 2, 49, 64))
    return [_track("Ostinato", 0, P["strings"], ost, 92, 54),
            _track("Brass", 1, P["brass"], brass, 88, 74),
            _track("Timpani", 2, P["timpani"], timp, 96, 64),
            _track("War drums", 9, None, drums, 84, 64)]


def compose(spec, kind="day"):
    pl = plan(spec)
    m = pl["m"]
    bpm = spec["bpm"] if kind != "night" else round(spec["bpm"] * spec.get("night_tempo", 0.85))
    if kind == "combat":
        tracks = compose_combat(pl)
    else:
        tracks = compose_day(pl, night=(kind == "night"))
    suffix = {"day": "", "night": " (Night)", "combat": " (Combat layer)"}[kind]
    return dict(title=spec["title"] + suffix, text=spec["math"], bpm=bpm, beats_per_bar=m["beats"], beat_unit=m["unit"],
                length_ticks=pl["bars"] * m["bar"], tracks=tracks), pl
