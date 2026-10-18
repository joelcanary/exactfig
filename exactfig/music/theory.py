"""
Teoría que usa el compositor, toda calculable:
  - modos de siete notas y grados (la nota MIDI de un grado, que puede pasar de la octava);
  - acordes por terceras apiladas sobre un grado y su FUNCIÓN (tónica, predominante, dominante) por modo;
  - armonización de una melodía por PROGRAMACIÓN DINÁMICA (Viterbi): cada compás, un acorde que contiene la nota del
    tiempo fuerte; se minimiza transición funcional + movimiento de voces, con las cadencias como restricciones;
  - conducción de voces ÓPTIMA: de todas las disposiciones del acorde en el registro, la que minimiza los semitonos
    movidos (distancia L1 entre acordes ordenados, la geometría de Tymoczko) más 4 por cada quinta u octava paralela;
    sin cruces de voces por construcción (las disposiciones van ordenadas).
"""
import itertools

MODES = {
    "ionian": [0, 2, 4, 5, 7, 9, 11],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "aeolian": [0, 2, 3, 5, 7, 8, 10],
    "harmonic": [0, 2, 3, 5, 7, 8, 11],              # menor armónica: V mayor con sensible
    "phrygian_dominant": [0, 1, 4, 5, 7, 8, 10],      # quinto modo de la armónica: desierto, fragua
}

# función de cada grado (0..6) como raíz de acorde: T tónica, P predominante, D dominante (y C = color)
FUNCTIONS = {
    "ionian": "TPTPDTD",
    "lydian": "TCTPDTD",            # II mayor = color lidio
    "mixolydian": "TPTPDTD",        # bVII = dominante modal (grado 6)
    "dorian": "TPTCDTD",            # IV mayor = color dórico
    "aeolian": "TPTPDPD",
    "harmonic": "TPTPDPD",
    "phrygian": "TDTPPPD",          # bII = dominante frigia
    "phrygian_dominant": "TDTPPPD",
}

# cadencias por modo: (grados que valen para cerrar a medias, para preparar el cierre)
CADENCE = {
    "ionian": ([4], [4]), "lydian": ([4, 1], [4, 1]), "mixolydian": ([6, 4], [6]), "dorian": ([4, 6], [6, 3]),
    "aeolian": ([4, 6], [6, 4]), "harmonic": ([4], [4]), "phrygian": ([1, 6], [1]), "phrygian_dominant": ([1, 6], [1]),
}

TRANS = {  # coste de pasar de una función a otra (la gramática T → P → D → T)
    ("T", "T"): 1.4, ("T", "P"): 0.6, ("T", "D"): 1.0, ("T", "C"): 0.8,
    ("P", "T"): 1.6, ("P", "P"): 1.3, ("P", "D"): 0.4, ("P", "C"): 1.2,
    ("D", "T"): 0.3, ("D", "P"): 2.6, ("D", "D"): 1.6, ("D", "C"): 2.0,
    ("C", "T"): 0.5, ("C", "P"): 1.0, ("C", "D"): 0.8, ("C", "C"): 1.8,
}


def pitch(scale, root, degree):
    """MIDI note of scale degree `degree` (any integer: octaves wrap) of `scale` (semitone offsets) above `root`."""
    o, k = divmod(degree, len(scale))
    return root + 12 * o + scale[k]


def chord_pcs(scale, root, deg, seventh=False):
    """Clases de altura (0..11, relativas a la tónica real) del acorde por terceras sobre el grado."""
    ks = [deg, deg + 2, deg + 4] + ([deg + 6] if seventh else [])
    return [(root + pitch(scale, 0, k)) % 12 for k in ks]


def is_diminished(scale, deg):
    """True when the triad in thirds on degree `deg` of `scale` is diminished (minor + minor third)."""
    a, b, c = (pitch(scale, 0, deg + i) for i in (0, 2, 4))
    return (b - a) % 12 == 3 and (c - b) % 12 == 3


def is_augmented(scale, deg):
    """True when the triad in thirds on degree `deg` of `scale` is augmented (major + major third)."""
    a, b, c = (pitch(scale, 0, deg + i) for i in (0, 2, 4))
    return (b - a) % 12 == 4 and (c - b) % 12 == 4


def vl_cost(prev, cur):
    """Movimiento mínimo (semitonos) entre dos conjuntos de clases de altura (cada nota a su más cercana)."""
    tot = 0
    for p in cur:
        tot += min(min((p - q) % 12, (q - p) % 12) for q in prev)
    return tot


def harmonize(mode, skeleton_deg, cadences, chords_per_bar=1):
    """
    Viterbi sobre los compases. skeleton_deg: grado (cualquier entero) del tiempo fuerte de cada compás.
    cadences: {compás: lista de raíces permitidas}. Devuelve (raíces, skeleton ajustado).
    Si una cadencia no admite la nota de la melodía, la nota se mueve al tono del acorde más cercano (lo mínimo).
    """
    scale = MODES[mode]
    fn = FUNCTIONS[mode]
    n = len(skeleton_deg)
    cands = []
    skel = list(skeleton_deg)
    for i, d in enumerate(skel):
        allowed = cadences.get(i)
        dd = d % 7
        opts = [r for r in range(7) if dd in ((r) % 7, (r + 2) % 7, (r + 4) % 7)]
        if allowed is not None:
            ok = [r for r in opts if r in allowed]
            if not ok:
                r = allowed[0]
                tones = [(r + k) % 7 for k in (0, 2, 4)]
                # el tono del acorde más cercano en grados (ida o vuelta)
                best = min(tones, key=lambda t: (min((t - dd) % 7, (dd - t) % 7), t))
                delta = (best - dd) % 7
                delta = delta - 7 if delta > 3 else delta
                skel[i] = d + delta
                ok = [r]
            opts = ok
        cands.append(opts)
    INF = float("inf")
    cost = [{r: INF for r in c} for c in cands]
    back = [{r: None for r in c} for c in cands]
    for r in cands[0]:
        cost[0][r] = (0 if r == 0 else 2.0) + (3 if is_diminished(scale, r) and mode != "harmonic" else 0)
    for i in range(1, n):
        for r in cands[i]:
            for q in cands[i - 1]:
                if cost[i - 1][q] == INF:
                    continue
                c = cost[i - 1][q] + TRANS[(fn[q], fn[r])]
                c += 0.15 * vl_cost(chord_pcs(scale, 0, q), chord_pcs(scale, 0, r))
                if r == q:
                    c += 0.9                      # el mismo acorde dos compases: algo de movimiento
                if is_diminished(scale, r):
                    c += 2.5
                if is_augmented(scale, r):
                    c += 4.0                      # III+ de la armónica, bVI+ del frigio dominante: áspero de fondo
                if c < cost[i][r]:
                    cost[i][r], back[i][r] = c, q
    r = min(cost[-1], key=cost[-1].get)
    roots = [r]
    for i in range(n - 1, 0, -1):
        r = back[i][r]
        roots.append(r)
    return list(reversed(roots)), skel


def voicings(pcs, lo, hi, voices):
    """Todas las disposiciones ordenadas de `voices` notas en [lo, hi] que usan todas las clases del acorde."""
    pool = [p for p in range(lo, hi + 1) if p % 12 in pcs]
    out = []
    for combo in itertools.combinations(pool, voices):
        if set(p % 12 for p in combo) >= set(pcs[:3]):
            # separación: ninguna voz superior a más de una octava de la de abajo (salvo el bajo del pad)
            if all(combo[k + 1] - combo[k] <= 12 for k in range(1, voices - 1)):
                out.append(combo)
    return out


def best_voicing(prev, pcs, lo, hi, voices=4):
    """La disposición óptima desde `prev`: mínimo de (semitonos movidos + 4 × quintas/octavas paralelas)."""
    cand = voicings(pcs, lo, hi, voices)
    if not cand:
        raise ValueError("sin disposición en el registro")
    if prev is None:
        mid = (lo + hi) / 2
        return min(cand, key=lambda c: abs(sum(c) / len(c) - mid))
    return min(cand, key=lambda c: voice_leading_score(prev, c, voices))


def voice_leading_score(prev, c, voices=4):
    """Semitonos movidos + 4 por cada par de voces en quintas u octavas paralelas."""
    move = sum(abs(a - b) for a, b in zip(prev, c))
    par = 0
    for i, j in itertools.combinations(range(voices), 2):
        a0, a1, b0, b1 = prev[i], c[i], prev[j], c[j]
        if a0 != a1 and (b1 - a1) % 12 in (0, 7) and (b0 - a0) % 12 == (b1 - a1) % 12:
            par += 1
    return move + 4 * par
