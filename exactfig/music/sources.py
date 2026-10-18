"""
Fuentes matemáticas de la música. Cada fuente devuelve un dict:
  skeleton : grados de la escala de las notas ESTRUCTURALES de la melodía (una por tiempo fuerte), en orden;
             el compositor elige la octava (la más cercana a la anterior) y armoniza alrededor de ellas;
  feature  : opcional, [(tiempo en compases, índice de nota del acorde)] para una capa de campanas/pulsos que dibuja
             la estructura (primos, celdas vivas, fichas aceptadas...). El índice 0 es la fundamental del acorde, 1 la
             tercera, 2 la quinta, 3 la octava...; así la capa nunca disuena con la armonía;
  perc     : opcional, [(tiempo en compases, nota GM de percusión, velocidad)];
  dyn      : opcional, intensidad 0..1 por compás (sobre la curva de frase);
  mask     : opcional, {capa: [bool por compás]} (qué capas suenan en cada compás).
`slots` es cuántas notas estructurales hacen falta y `bars` cuántos compases. Todo es determinista.
"""
import math

from .. import fmath as fm
PHI = (1 + fm.sqrt(5.0)) / 2


def cyc(seq, n, start=0):
    return [seq[(start + i) % len(seq)] for i in range(n)]


def primes_upto(n):
    """The primes up to n (sieve of Eratosthenes), as a list."""
    s = bytearray([1]) * (n + 1)
    s[0:2] = b"\x00\x00"
    for p in range(2, math.isqrt(n) + 1):
        if s[p]:
            s[p * p::p] = bytearray(len(s[p * p::p]))
    return [i for i in range(n + 1) if s[i]]


def is_prime(n):
    """Primality by trial division up to the integer square root."""
    return n > 1 and all(n % p for p in range(2, math.isqrt(n) + 1))


# ---------------------------------------------------------------- números y proporciones

def pisano(slots, bars, m=7, start=0):
    """F(n) mod m. Con m = 7 el periodo de Pisano es 16: la melodía se repite EXACTAMENTE cada 16 notas."""
    a, b, out = 0, 1, []
    for _ in range(start):
        a, b = b, (a + b) % m
    for _ in range(slots):
        out.append(a % 7)
        a, b = b, (a + b) % m
    return {"skeleton": out}


def phyllotaxis(slots, bars, alpha=None):
    """Ángulo áureo: la hoja k sale a k·(2 − φ) vueltas; su sector de 7 da el grado (teorema de las tres distancias)."""
    alpha = (2 - PHI) if alpha is None else alpha
    sk = [int(7 * ((k * alpha) % 1)) for k in range(slots)]
    # campanas en las hojas que caen en el primer séptimo (las que "se alinean" con el tallo)
    feat = [(k / 2, int(4 * ((k * alpha) % 1))) for k in range(bars * 2) if (k * alpha) % 1 < 3 / 7]
    return {"skeleton": sk, "feature": feat}


def silver(slots, bars):
    """Razón de plata δ = 1 + √2 (Pell): la misma construcción que el ángulo áureo con otro irracional."""
    return phyllotaxis(slots, bars, alpha=(1 + fm.sqrt(2.0)) % 1)


# ---------------------------------------------------------------- ondas, recurrencias y curvas

def tides(slots, bars):
    """Marea con dos constituyentes: M2 (12,42 h) y S2 (12,00 h). Un compás = una hora; la altura da el grado y la fuerza."""
    h = [fm.cos(2 * math.pi * t / 12.42) + 0.46 * fm.cos(2 * math.pi * t / 12.0)
         for t in (i * bars / slots for i in range(slots))]
    sk = [round(2 + 2.2 * x) for x in h]
    dyn = [0.5 + 0.35 * (fm.cos(2 * math.pi * b / 12.42) + 0.46 * fm.cos(2 * math.pi * b / 12)) / 1.46 for b in range(bars)]
    return {"skeleton": sk, "dyn": dyn}


def gould(slots, bars):
    """Triángulo de Pascal módulo 2 (Sierpinski): la fila r tiene 2^popcount(r) impares; popcount(r) da el grado."""
    sk = [bin(r).count("1") for r in range(slots)]
    feat = []
    for b in range(bars):
        row = [math.comb(b % 8, k) % 2 for k in range(b % 8 + 1)]
        feat += [(b + k / 8, k % 4) for k, odd in enumerate(row) if odd]
    return {"skeleton": sk, "feature": feat}


def bresenham(slots, bars, k=5, m=8):
    """Algoritmo de Euclides hecho recta: ⌊i·k/m⌋ sube un grado k veces de cada m (la misma cuenta que los ritmos E(k,m))."""
    sk = [(i * k) // m for i in range(slots)]
    feat = [(b + i / 8, i % 3) for b in range(bars) for i in range(8) if (i * k) % m < k]
    return {"skeleton": sk, "feature": feat}


def thue_morse(slots, bars):
    """Thue–Morse t(n) = popcount(n) mod 2 decide en cada compás el motivo o su inversión: el reparto más justo posible."""
    motif = [0, 2, 1, 3]
    sk = []
    for i in range(slots):
        t = bin(i // 4).count("1") % 2
        sk.append(motif[i % 4] if t == 0 else 4 - motif[i % 4])
    return {"skeleton": sk}


def fifths(slots, bars):
    """Círculo de quintas en la escala: cada nota estructural, una cuarta más arriba (+3 grados): 0, 3, 6, 2, 5, 1, 4."""
    return {"skeleton": [(3 * i) % 7 for i in range(slots)]}


def koch(slots, bars, level=3):
    """Curva de Koch: F → F+F−−F+F (60°). La altura de cada vértice de la curva da el grado: la melodía es autosemejante."""
    turns = []
    def build(l):
        if l == 0:
            return []
        sub = build(l - 1)
        return sub + [60] + sub + [-120] + sub + [60] + sub
    turns = build(level)
    x = y = 0.0
    ang = 0.0
    ys = [0.0]
    for t in [0] + turns:
        ang += t
        x += fm.cos(fm.radians(ang)); y += fm.sin(fm.radians(ang))
        ys.append(y)
    top = max(ys) or 1
    return {"skeleton": cyc([round(6 * v / top) for v in ys], slots)}


def heat(slots, bars):
    """Ecuación del calor: la frase de los primos mod 7 se difunde (u ← u + ¼Δu) una vez más en cada frase: se derrite."""
    base = [p % 7 for p in primes_upto(60)][:8]
    u = [float(v) for v in base]
    sk = []
    while len(sk) < slots:
        sk += [round(v) for v in u]
        u = [u[i] + 0.25 * (u[i - 1] - 2 * u[i] + u[(i + 1) % len(u)]) for i in range(len(u))]
    return {"skeleton": sk[:slots]}


BESSEL_ZEROS = [2.404826, 3.831706, 5.135622, 5.520078, 6.380162, 7.015587, 7.588342, 8.417244, 8.653728, 8.771484]


def bessel(slots, bars):
    """Modos de una membrana circular (un tambor): las frecuencias van como los ceros j_mn de Bessel, NO armónicas."""
    semis = [12 * fm.log2(z / BESSEL_ZEROS[0]) for z in BESSEL_ZEROS]
    # semitonos → grado más cercano de una escala mayor (aproximación del timbre del tambor a la escala)
    major = [0, 2, 4, 5, 7, 9, 11]
    def deg(s):
        o, r = divmod(round(s), 12)
        return 7 * o + min(range(7), key=lambda k: abs(major[k] - r))
    arch = [deg(s) for s in semis[:6]] + [deg(s) for s in semis[4:0:-1]]
    feat = [(b + i / 4, [0, 1, 2, 3][(b + i) % 4]) for b in range(bars) for i in range(4) if (b * 4 + i) % 3 != 2]
    return {"skeleton": cyc(arch, slots), "feature": feat}


def logistic(slots, bars):
    """Mapa logístico x ← r·x(1−x): r = 3,2 → periodo 2; 3,5 → 4; 3,56 → 8 (duplicación de periodo, el borde del caos)."""
    rs = [3.2, 3.5, 3.56, 3.5]
    per = max(1, slots // len(rs))
    sk = []
    for r in rs:
        x = 0.5
        for _ in range(500):
            x = r * x * (1 - x)
        for _ in range(per):
            x = r * x * (1 - x)
            sk.append(int(7 * x) % 7)
    return {"skeleton": cyc(sk, slots)}


def lissajous(slots, bars):
    """Figura de Lissajous 3:2: x = sin 3θ (melodía) contra y = sin 2θ (campanas); polirritmo tres contra dos."""
    sk = [round(3 + 3 * fm.sin(3 * 2 * math.pi * i / 16)) for i in range(slots)]
    feat = [(b + k / 3, 2) for b in range(bars) for k in range(3)] + [(b + k / 2, 0) for b in range(bars) for k in range(2)]
    return {"skeleton": sk, "feature": sorted(feat)}


def kepler(slots, bars, e=0.6):
    """Segunda ley de Kepler: a tiempos iguales, áreas iguales. Se resuelve M = E − e·sen E (Newton) y la anomalía verdadera
    da el grado: cerca del perihelio la melodía corre por la escala, cerca del afelio casi se para."""
    per = 16
    sk = []
    for i in range(slots):
        M = 2 * math.pi * (i % per) / per
        E = M
        for _ in range(30):
            E -= (E - e * fm.sin(E) - M) / (1 - e * fm.cos(E))
        nu = 2 * fm.atan2(math.sqrt(1 + e) * fm.sin(E / 2), math.sqrt(1 - e) * fm.cos(E / 2))
        sk.append(round(7 * (nu % (2 * math.pi)) / (2 * math.pi)) % 7)
    return {"skeleton": sk}


# ---------------------------------------------------------------- análisis y física

ZETA = [14.134725, 21.022040, 25.010858, 30.424876, 32.935062, 37.586178, 40.918719, 43.327073,
        48.005151, 49.773832, 52.970321, 56.446248, 59.347044, 60.831779, 65.112544, 67.079811]


def zeta(slots, bars):
    """Los 16 primeros ceros no triviales de ζ(s) (½ + iγ): ⌊γ⌋ mod 7 da el grado. Los ceros se repelen: casi nunca hay dos iguales seguidos."""
    return {"skeleton": cyc([int(g) % 7 for g in ZETA], slots)}


def primes(slots, bars):
    """Primos mod 7 (Dirichlet: se reparten por igual entre 1..6) dan la melodía; los huecos entre primos, el ritmo de las campanas."""
    ps = primes_upto(2000)
    sk = [p % 7 for p in ps[:slots]]
    feat, t = [], 0.0
    for a, b in zip(ps, ps[1:]):
        if t >= bars:
            break
        feat.append((t, (b - a) // 2 % 4))
        t += (b - a) / 16          # un hueco de 2 = un octavo de compás
    return {"skeleton": sk, "feature": feat}


def pendulum(slots, bars):
    """Péndulo simple θ(t) = θ₀ cos(2πt/T), T = 2 compases: la melodía oscila alrededor de la quinta como algo que cuelga."""
    return {"skeleton": [round(4 + 3 * fm.cos(2 * math.pi * i / 4)) for i in range(slots)]}


def coupled(slots, bars):
    """Dos péndulos acoplados: la energía pasa de uno a otro (pulsaciones). La intensidad de la melodía va como |cos(Δω t/2)|."""
    w1, w2 = 2 * math.pi / 4, 2 * math.pi / 4.5
    sk = [round(3 + 1.6 * (fm.cos(w1 * i) + fm.cos(w2 * i))) for i in range(slots)]
    dyn = [0.35 + 0.6 * abs(fm.cos((w2 - w1) * b)) for b in range(bars)]
    return {"skeleton": sk, "dyn": dyn}


STILL_LIFES = {   # vidas quietas de B3/S23 (las que contamos para la OEIS): celdas (x, y)
    "block": [(0, 0), (1, 0), (0, 1), (1, 1)],
    "tub": [(1, 0), (0, 1), (2, 1), (1, 2)],
    "boat": [(0, 0), (1, 0), (0, 1), (2, 1), (1, 2)],
    "beehive": [(1, 0), (2, 0), (0, 1), (3, 1), (1, 2), (2, 2)],
    "ship": [(0, 0), (1, 0), (0, 1), (2, 1), (1, 2), (2, 2)],
    "loaf": [(1, 0), (2, 0), (0, 1), (3, 1), (1, 2), (3, 2), (2, 3)],
    "long boat": [(0, 0), (1, 0), (0, 1), (2, 1), (1, 2), (3, 2), (2, 3)],
    "pond": [(1, 0), (2, 0), (0, 1), (3, 1), (0, 2), (3, 2), (1, 3), (2, 3)],
}


def still_lifes(slots, bars):
    """Cada compás suena una vida quieta de Conway: cada celda viva es una nota (columna = tiempo, fila = nota del acorde).
    El grado estructural es el número de celdas − 4 (el índice n de la secuencia A019473)."""
    names = list(STILL_LIFES)
    sk, feat = [], []
    for b in range(bars):
        cells = STILL_LIFES[names[b % len(names)]]
        for x, y in sorted(cells):
            feat.append((b + x / 4 + y / 16, y))
    for i in range(slots):
        sk.append(len(STILL_LIFES[names[(i // 2) % len(names)]]) - 4 + (i % 2) * 2)
    return {"skeleton": sk, "feature": feat}


def ulam_xy(n):
    """Coordenadas de n en la espiral de Ulam (1 en el centro)."""
    if n == 1:
        return 0, 0
    k = math.ceil((math.sqrt(n) - 1) / 2)
    t = 2 * k + 1
    m = t * t
    t -= 1
    if n >= m - t: return k - (m - n), -k
    m -= t
    if n >= m - t: return -k, -k + (m - n)
    m -= t
    if n >= m - t: return -k + (m - n), k
    return k, k - (m - n - t)


def ulam(slots, bars):
    """Espiral de Ulam: n = 1, 2, 3... por octavos; si n es primo suena una campana con la diagonal (x + y) de su casilla.
    Los primos se amontonan en diagonales: las mismas notas vuelven."""
    feat = []
    for i in range(bars * 8):
        n = i + 1
        if is_prime(n):
            x, y = ulam_xy(n)
            feat.append((i / 8, (x + y) % 4))
    ps = primes_upto(5000)
    sk = [sum(ulam_xy(p)) % 7 for p in ps[:slots]]
    return {"skeleton": sk, "feature": feat}


def cantor_fn(x, depth=12):
    """Función de Cantor (escalera del diablo)."""
    y, scale = 0.0, 0.5
    for _ in range(depth):
        x *= 3
        d = int(x); x -= d
        if d == 1:
            return y + scale
        y += scale * (d // 2)
        scale /= 2
    return y


def cantor(slots, bars):
    """Escalera del diablo: la función de Cantor sube solo en el conjunto de Cantor y es plana en todo lo demás.
    Las campanas suenan en los 8 puntos de nivel 3 del conjunto (dígitos ternarios 0 y 2) de cada par de compases."""
    sk = [round(7 * cantor_fn(i / slots)) for i in range(slots)]
    pts = sorted(a * 9 + b * 3 + c for a in (0, 2) for b in (0, 2) for c in (0, 2))
    feat = [(2 * blk + 2 * p / 27, (p // 3) % 4) for blk in range(bars // 2) for p in pts]
    return {"skeleton": sk, "feature": feat}


# ---------------------------------------------------------------- curvas que llenan el plano

def hilbert_d2xy(order, d):
    """Position (x, y) of index d along the Hilbert curve of the given order (a 2^order × 2^order grid)."""
    n = 1 << order
    x = y = 0
    s, t = 1, d
    while s < n:
        rx = 1 & (t // 2)
        ry = 1 & (t ^ rx)
        if ry == 0:
            if rx == 1:
                x, y = s - 1 - x, s - 1 - y
            x, y = y, x
        x += s * rx; y += s * ry
        t //= 4
        s *= 2
    return x, y


def hilbert(slots, bars):
    """Curva de Hilbert de orden 3 sobre una rejilla 8×8: grado = x + y. Dos casillas seguidas de la curva son vecinas,
    así que la melodía va SIEMPRE por grados conjuntos (la localidad de la curva, la de nuestro calendario)."""
    return {"skeleton": cyc([sum(hilbert_d2xy(3, d)) for d in range(64)], slots)}


def lo_shu(slots, bars):
    """Cuadrado mágico Lo Shu: sus 8 líneas (filas, columnas, diagonales) suman 15. Cada compás toca una línea."""
    sq = [[4, 9, 2], [3, 5, 7], [8, 1, 6]]
    lines = sq + [list(c) for c in zip(*sq)] + [[sq[i][i] for i in range(3)], [sq[i][2 - i] for i in range(3)]]
    seq = [v - 1 for ln in lines for v in ln]
    feat = [(b + k / 3, (lines[b % 8][k] - 1) % 4) for b in range(bars) for k in range(3)]
    return {"skeleton": cyc(seq, slots), "feature": feat}


def lsystem(slots, bars):
    """Planta de Lindenmayer: X → F[+X][−X]FX, F → FF. F toca, + y − suben y bajan un grado, [ guarda y ] vuelve:
    cada rama sale de la nota del tronco y regresa a ella."""
    s = "X"
    for _ in range(3):
        s = "".join({"X": "F[+X][-X]FX", "F": "FF"}.get(c, c) for c in s)
    cur, stack, out = 0, [], []
    for c in s:
        if c == "F": out.append(cur)
        elif c == "+": cur += 1
        elif c == "-": cur -= 1
        elif c == "[": stack.append(cur)
        elif c == "]": cur = stack.pop()
    # sin notas repetidas seguidas (un tronco largo es una nota larga, no muchas iguales)
    ded = [v for i, v in enumerate(out) if i == 0 or v != out[i - 1]]
    return {"skeleton": cyc(ded, slots)}


def mandel_pi(slots, bars):
    """π en el conjunto de Mandelbrot (Boll, 1991): en c = −¾ + iε, las iteraciones hasta escapar ≈ π/ε.
    Se baja ε de 0,5 a 0,005 y las iteraciones mod 7 dan el grado; las campanas marcan cuando n·ε se acerca a π."""
    sk, feat = [], []
    for i in range(slots):
        eps = 0.5 * fm.pow(0.01, i / max(1, slots - 1))
        c = complex(-0.75, eps)
        z, n = 0j, 0
        while abs(z) <= 2 and n < 5000:
            z = z * z + c
            n += 1
        sk.append(n % 7)
        if abs(n * eps - math.pi) < 0.25:
            feat.append((i * bars / slots, 2))
    return {"skeleton": sk, "feature": feat}


def harmonics(slots, bars):
    """Armónicos de una cuerda: el n-ésimo suena 12·log₂(n) semitonos sobre la fundamental. Subida y bajada por la serie."""
    major = [0, 2, 4, 5, 7, 9, 11]
    def deg(s):
        o, r = divmod(round(s), 12)
        return 7 * o + min(range(7), key=lambda k: abs(major[k] - r))
    up = [deg(12 * fm.log2(n)) - 7 for n in range(2, 11)]
    return {"skeleton": cyc(up + up[-2:0:-1], slots)}


def b37_glider(slots, bars):
    """Nuestra regla B37/S2378: su planeador cruza un toro de 8×8 y vuelve a su sitio en 32 generaciones. Un compás =
    una generación: cada celda viva es una campana en el octavo x del compás con la nota y; se oye al planeador avanzar."""
    B, S, W = {3, 7}, {2, 3, 7, 8}, 8

    def step(g):
        cnt = {}
        for (x, y) in g:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx or dy:
                        k = ((x + dx) % W, (y + dy) % W)
                        cnt[k] = cnt.get(k, 0) + 1
        return frozenset(c for c, k in cnt.items() if (k in S if c in g else k in B))
    s = 231
    def rnd():
        nonlocal s
        s ^= (s << 13) & 0xFFFFFFFF; s ^= s >> 17; s ^= (s << 5) & 0xFFFFFFFF
        return s
    g = frozenset((x, y) for x in range(W) for y in range(W) if rnd() % 100 < 35)
    for _ in range(12):           # transitorio medido: a partir de aquí, un ciclo exacto de 32
        g = step(g)
    gens = []
    for _ in range(32):
        gens.append(g)
        g = step(g)
    assert g == gens[0], "el planeador no cerró el ciclo"
    feat, sk = [], []
    for b in range(bars):
        cells = sorted(gens[b % 32])
        for x, y in cells:
            feat.append((b + x / 8, y % 4))
        # la diagonal por la que viaja (x + y del centro) y la fase de su forma (4 fases)
        cx = round(sum(x for x, _ in cells) / len(cells)); cy = round(sum(y for _, y in cells) / len(cells))
        sk += [(cx + cy) % 7, (cx + cy + [0, 2, 4, 1][b % 4]) % 7]
    return {"skeleton": sk[:slots], "feature": feat}


def farey(slots, bars):
    """Sucesión de Farey F₅ (fracciones de denominador ≤ 5): son las posiciones de las campanas dentro del compás.
    Dos vecinas a/b, c/d cumplen bc − ad = 1; el grado es (a + b) mod 7."""
    fr = sorted({(a, b) for b in range(1, 6) for a in range(0, b)}, key=lambda t: t[0] / t[1])
    seq = [(a + b) % 7 for a, b in fr]
    feat = [(bar + a / b, b % 4) for bar in range(bars) for a, b in fr if bar % 2 == 0 or b <= 3]
    return {"skeleton": cyc(seq, slots), "feature": feat}


def tetractys(slots, bars):
    """La tetractys pitagórica (1, 2, 3, 4): solo octavas (2:1), quintas (3:2) y cuartas (4:3). Cada nota estructural salta
    una cuarta o una quinta según la paridad de los números triangulares."""
    sk, cur = [], 0
    for i in range(slots):
        sk.append(cur)
        tri = (i + 1) * (i + 2) // 2
        cur += 4 if tri % 2 else -3
        if cur > 6: cur -= 7
        if cur < -3: cur += 7
    return {"skeleton": sk}


def lorenz(slots, bars):
    """Atractor de Lorenz (σ = 10, ρ = 28, β = 8/3, RK4): el ala en la que está (signo de x) elige el centro de la melodía y
    la altura z la nota. Salta de ala sin periodo: la mariposa."""
    def f(v):
        x, y, z = v
        return (10 * (y - x), x * (28 - z) - y, x * y - 8 / 3 * z)
    v, dt, sk = (1.0, 1.0, 1.0), 0.01, []
    for _ in range(800):
        k1 = f(v); k2 = f(tuple(a + dt / 2 * b for a, b in zip(v, k1)))
        k3 = f(tuple(a + dt / 2 * b for a, b in zip(v, k2))); k4 = f(tuple(a + dt * b for a, b in zip(v, k3)))
        v = tuple(a + dt / 6 * (b + 2 * c + 2 * d + e) for a, b, c, d, e in zip(v, k1, k2, k3, k4))
        if _ >= 200 and _ % 18 == 0:
            sk.append((0 if v[0] > 0 else -2) + round((v[2] - 24) / 7))
    return {"skeleton": cyc(sk, slots)}


def fourier_square(slots, bars):
    """Serie de Fourier de la onda cuadrada: solo armónicos impares 1, 3, 5, 7, 9. Cada frase suma un término más:
    la melodía crece hacia la cuadrada (y las campanas tocan los armónicos que ya están)."""
    major = [0, 2, 4, 5, 7, 9, 11]
    def deg(s):
        o, r = divmod(round(s), 12)
        return 7 * o + min(range(7), key=lambda k: abs(major[k] - r))
    odd = [deg(12 * fm.log2(n)) for n in (1, 3, 5, 7, 9)]
    sk = []
    per_phrase = max(1, slots // 4)
    for ph in range(4):
        terms = odd[:ph + 2]
        for i in range(per_phrase):
            sk.append(terms[i % len(terms)] - (7 if terms[i % len(terms)] > 9 else 0))
    feat = [(b + k / 4, k) for b in range(bars) for k in range(min(4, 1 + b * 4 // bars + 1))]
    return {"skeleton": cyc(sk, slots), "feature": feat}


def dihedral(slots, bars):
    """El hielo es hexagonal: las 12 simetrías del hexágono (6 giros y 6 reflexiones, el grupo D6) actúan sobre un motivo
    de 6 notas; cada compás es una simetría distinta aplicada al motivo."""
    motif = [0, 2, 4, 5, 3, 1]
    els = [(r, False) for r in range(6)] + [(r, True) for r in range(6)]
    sk = []
    for i in range(slots):
        r, refl = els[(i // 2) % 12]
        v = (i % 2) * 2 + (i // 24) % 2
        idx = (-v + r) % 6 if refl else (v + r) % 6
        sk.append(motif[idx])
    return {"skeleton": sk}


def sieve(slots, bars):
    """Criba de Eratóstenes sobre los octavos (n = 2, 3, 4...): cada primo p ≤ 7 tacha sus múltiplos con su propio
    tambor (polirritmo 2:3:5:7) y lo que sobrevive, los primos, lo canta una campana."""
    perc, feat = [], []
    drums = {2: (45, 70), 3: (70, 55), 5: (54, 50), 7: (81, 45)}   # tom grave, maracas, pandereta, triángulo
    for i in range(bars * 8):
        n = i + 2
        for p, (note, vel) in drums.items():
            if n % p == 0 and n != p:
                perc.append((i / 8, note, vel))
        if is_prime(n):
            feat.append((i / 8, n % 4))
    return {"skeleton": [p % 7 for p in primes_upto(4000)[:slots]], "feature": feat, "perc": perc}


def mobius(slots, bars):
    """Cinta de Möbius: tras una vuelta se vuelve del revés. La segunda mitad es el motivo invertido (espejo en el grado 2)
    y la tercera vuelve a estar del derecho: hacen falta dos vueltas para volver al principio."""
    base = [0, 1, 3, 2, 4, 3, 1, 2]
    sk = []
    for i in range(slots):
        flip = (i // (slots // 2 or 1)) % 2 if slots >= 16 else 0
        v = base[i % 8]
        sk.append(4 - v if flip else v)
    return {"skeleton": sk}


# ---------------------------------------------------------------- combinatoria

def gray(slots, bars):
    """Código Gray de 3 bits: de un número al siguiente cambia UN solo bit. Da la melodía (0, 1, 3, 2, 6, 7, 5, 4) y en cada
    compás enciende o apaga exactamente una capa (bajo, arpegio, campanas)."""
    g = [i ^ (i >> 1) for i in range(8)]
    sk = cyc([v % 7 for v in g], slots)
    mask = {"bass": [], "acc": [], "feature": []}
    for b in range(bars):
        v = g[b % 8] | 0b001
        mask["bass"].append(True)
        mask["acc"].append(bool(v & 2) or b % 8 == 0)
        mask["feature"].append(bool(v & 4))
    feat = [(b + i / 4, (g[(b + i) % 8]) % 4) for b in range(bars) for i in range(4)]
    return {"skeleton": sk, "mask": mask, "feature": feat}


def catalan(slots, bars):
    """Camino de Dyck (paréntesis equilibrados: nunca cruza el suelo; hay C_n de semilongitud n, los números de Catalan).
    Este codifica un árbol de Fibonacci de altura 4 (28 pasos) y se da la vuelta: raíces que bajan bajo tierra y vuelven
    siempre a la superficie."""
    def tree(d):
        return "" if d == 0 else "(" + tree(d - 1) + ")" + "(" + tree(d - 2 if d > 1 else 0) + ")"
    word = tree(4)
    h, path = 0, []
    for c in word:
        h += 1 if c == "(" else -1
        path.append(-h)
    return {"skeleton": cyc(path, slots)}


def quadratic_residues(slots, bars):
    """Restos cuadráticos módulo 13: {1, 3, 4, 9, 10, 12}. Como 13 ≡ 1 (mod 4), el patrón es simétrico; se toca en las
    12 semicorcheas de un 3/4. La melodía es k² mod 13."""
    qr = {(k * k) % 13 for k in range(1, 13)}
    feat = [(b + i / 12, i % 4) for b in range(bars) for i in range(1, 13) if i in qr]
    return {"skeleton": [((k * k) % 13) % 7 for k in range(1, slots + 1)], "feature": feat}


def pi_digits(base, n):
    """Primeros n dígitos de π en la base dada (Machin, aritmética entera exacta)."""
    bits = 64 + int(n * fm.log2(base)) + 32
    one = 1 << bits
    def arctan_inv(x):
        s, t, k, sign = 0, one // x, 1, 1
        while t:
            s += sign * (t // k)
            t //= x * x; k += 2; sign = -sign
        return s
    p = 4 * (4 * arctan_inv(5) - arctan_inv(239))
    digits = [p >> bits]
    frac = p & (one - 1)
    for _ in range(n - 1):
        frac *= base
        digits.append(frac >> bits)
        frac &= one - 1
    return digits


def pi_base7(slots, bars):
    """π en base 7 = 3,0663651432036134... Siete dígitos para siete notas: cada dígito es un grado de la escala."""
    return {"skeleton": pi_digits(7, slots)}


def e_fraction(slots, bars):
    """Fracción continua de e = [2; 1, 2, 1, 1, 4, 1, 1, 6, ...]: los numeradores de las convergentes mod 7 dan la melodía y
    cada término a_k, la duración (en octavos) de una campana."""
    terms = [2]
    k = 1
    while len(terms) < 64:
        terms += [1, 2 * k, 1]; k += 1
    p0, p1, nums = 1, terms[0], [terms[0]]
    for a in terms[1:]:
        p0, p1 = p1, a * p1 + p0
        nums.append(p1)
    feat, t = [], 0.0
    for i, a in enumerate(terms[1:]):
        if t >= bars:
            break
        feat.append((t, i % 4))
        t += min(a, 6) / 8
    return {"skeleton": [v % 7 for v in nums[:slots]], "feature": feat}


def token_bucket(slots, bars, C=4, r=0.5):
    """El cubo de fichas que demostramos en Lean (aceptadas ≤ C + r·n): un herrero pide golpes a ráfagas; el cubo (capacidad 4,
    media ficha por octavo) acepta los que puede. Cada golpe aceptado es un yunque; la melodía sube cuando el cubo se llena."""
    tokens, perc, sk_t = float(C), [], []
    pattern = [6, 0, 0, 2, 1, 0, 3, 0]          # golpes pedidos por grupo de 2 octavos (ráfagas)
    accepted = 0
    for i in range(bars * 8):
        tokens = min(C, tokens + r)
        want = pattern[(i // 2) % len(pattern)] > (i % 2) * 2
        if want and tokens >= 1:
            tokens -= 1; accepted += 1
            perc.append((i / 8, 56 if i % 4 else 60, 70 + 10 * (i % 2 == 0)))   # cencerro / bongó agudo: yunque
        assert accepted <= C + r * (i + 1) + 1e-9
        if i % 4 == 0:
            sk_t.append(int(tokens))
    return {"skeleton": cyc(sk_t, slots), "perc": perc}


def ghz(slots, bars):
    """Estado GHZ (|000⟩ + |111⟩)/√2: al medir, los tres qubits dan siempre lo mismo. Cada compás es una medida (los bits de
    √2 hacen de azar): las tres voces saltan JUNTAS al acorde de arriba o al de abajo."""
    bits = bin(math.isqrt(2 << 200))[3:]
    sk = []
    for i in range(slots):
        b = bits[i // 2] == "1"
        sk.append((4 if b else 0) + (i % 2) * 2)
    return {"skeleton": sk}


def conway_glider(slots, bars):
    """El planeador de Conway (B3/S23): 4 fases y avanza una casilla en diagonal. Cada fase es un acorde partido; cada 4
    compases el planeador (y la melodía) sube un grado."""
    phases = [[(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)], [(0, 1), (2, 1), (1, 2), (2, 2), (1, 3)],
              [(2, 1), (0, 2), (2, 2), (1, 3), (2, 3)], [(1, 1), (2, 2), (3, 2), (1, 3), (2, 3)]]
    feat, sk = [], []
    for b in range(bars):
        for x, y in sorted(phases[b % 4]):
            feat.append((b + x / 4, y % 4))
    for i in range(slots):
        b = i // 2
        sk.append((b // 4) % 5 + [0, 2, 1, 3][b % 4] * (i % 2))
    return {"skeleton": sk, "feature": feat}


# ---------------------------------------------------------------- autómatas y más

def replicator(slots, bars):
    """Piedra, papel, tijera con la ecuación del replicador ẋᵢ = xᵢ((Ax)ᵢ − xᵀAx): las tres poblaciones giran sin fin.
    La que domina en cada momento elige la nota (tónica, tercera o quinta)."""
    A = [[0, -1, 1], [1, 0, -1], [-1, 1, 0]]
    x = [0.6, 0.25, 0.15]
    sk, dt = [], 0.05
    for i in range(slots * 6):
        f = [sum(A[k][j] * x[j] for j in range(3)) for k in range(3)]
        avg = sum(x[k] * f[k] for k in range(3))
        x = [x[k] + dt * x[k] * (f[k] - avg) for k in range(3)]
        s = sum(x); x = [v / s for v in x]
        if i % 6 == 0:
            sk.append([0, 2, 4][max(range(3), key=lambda k: x[k])])
    return {"skeleton": sk}


def divisors12(slots, bars):
    """Divisores de 12 (1, 2, 3, 4, 6, 12): cada uno es una capa de pulsos (cada d semicorcheas); la melodía es σ(n) mod 7,
    la suma de divisores."""
    sigma = [sum(d for d in range(1, n + 1) if n % d == 0) for n in range(1, slots + 1)]
    feat = [(b + i / 12, [12, 6, 4, 3, 2].index(d) % 4) for b in range(bars) for d in (12, 6, 4, 3)
            for i in range(0, 12, d)]
    return {"skeleton": [v % 7 for v in sigma], "feature": sorted(set(feat))}


def lunar(slots, bars):
    """Fases de la Luna: fracción iluminada f = (1 − cos(2πk/8))/2. La melodía crece y mengua con ella y el arpegio de
    campanas tiene tantas notas como cuartos de Luna iluminados."""
    f = [(1 - fm.cos(2 * math.pi * k / 8)) / 2 for k in range(8)]
    sk = [round(4 * f[(i // 2) % 8]) + (i % 2) for i in range(slots)]
    feat = [(b + j / 4, j) for b in range(bars) for j in range(round(4 * f[b % 8]))]
    return {"skeleton": sk, "feature": feat, "dyn": [0.45 + 0.4 * f[b % 8] for b in range(bars)]}


def triples(slots, bars):
    """Ternas pitagóricas a² + b² = c² (fórmula de Euclides): (3,4,5), (5,12,13), (8,15,17)... sus lados mod 7 son la melodía
    y el compás se agrupa 3 + 4 + 5 = 12."""
    ts = []
    for m in range(2, 9):
        for n in range(1, m):
            if (m - n) % 2 and math.gcd(m, n) == 1:
                ts.append((m * m - n * n, 2 * m * n, m * m + n * n))
    ts.sort(key=lambda t: t[2])
    seq = [v % 7 for t in ts for v in t]
    feat = [(b + s / 12, k) for b in range(bars) for k, s in enumerate((0, 3, 7))]
    return {"skeleton": cyc(seq, slots), "feature": feat}


def free_fall(slots, bars, g=1.62):
    """Caída libre en la Luna (g = 1,62 m/s², seis veces menos que en la Tierra): cada frase es una parábola
    y(t) = v₀t − ½gt², lenta como un salto de astronauta."""
    T = 4.0                                  # una parábola cada 4 compases (2 s de vuelo por compás a escala)
    v0 = g * T / 2
    sk = []
    for i in range(slots):
        t = (i * bars / slots) % T
        y = v0 * t - g * t * t / 2
        sk.append(round(6 * y / (v0 * v0 / (2 * g))))
    return {"skeleton": sk}


def swells(slots, bars):
    """Superposición de dos marejadas (periodos de 3 y 4 compases): y = sen(2πt/3) + 0,7·sen(2πt/4 + 1). Se baten cada
    12 compases; la suma da la melodía."""
    sk = []
    for i in range(slots):
        t = i * bars / slots
        y = fm.sin(2 * math.pi * t / 3) + 0.7 * fm.sin(2 * math.pi * t / 4 + 1)
        sk.append(round(2 + 2 * y))
    return {"skeleton": sk}


# ---------------------------------------------------------------- fractales y sistemas dinámicos

def nautilus_r(theta):
    """Espiral logarítmica áurea: r = φ^(2θ/π), crece φ en cada cuarto de vuelta."""
    return fm.pow(PHI, 2 * theta / math.pi)


def nautilus(slots, bars, turns=2):
    """La concha del nautilo (espiral logarítmica áurea r = φ^(2θ/π)). Un punto por octavo de vuelta; la melodía es la
    proyección r·cos θ, así que cada vuelta oscila más ancha que la anterior, y a las dos vueltas empieza una cámara
    nueva. Las campanas, en los tabiques (cada cuarto de vuelta)."""
    per = 8 * turns
    rmax = nautilus_r(turns * 2 * math.pi)
    sk = []
    for i in range(slots):
        th = (i % per) * math.pi / 4
        sk.append(round(2 + 4 * nautilus_r(th) / rmax * fm.cos(th)))
    feat = [(i * bars / slots, (i // 2) % 4) for i in range(slots) if (i % per) % 4 == 0]
    return {"skeleton": sk, "feature": feat}


BARNSLEY = [((0.0, 0.0, 0.0, 0.16, 0.0, 0.0), 1), ((0.85, 0.04, -0.04, 0.85, 0.0, 1.6), 85),
            ((0.2, -0.26, 0.23, 0.22, 0.0, 1.6), 7), ((-0.15, 0.28, 0.26, 0.24, 0.0, 0.44), 7)]


def barnsley_points(n, seed=2463534242, burn=20):
    """El juego del caos del helecho de Barnsley: tallo 1 %, hoja 85 %, foliolos 7 % y 7 %, elegidos con un xorshift
    de semilla fija. Devuelve [(x, y, aplicación)]."""
    s, x, y, out = seed, 0.0, 0.0, []
    for i in range(n + burn):
        s ^= (s << 13) & 0xFFFFFFFF; s ^= s >> 17; s ^= (s << 5) & 0xFFFFFFFF
        u, acc, k = s % 100, 0, 0
        for k, (_, w) in enumerate(BARNSLEY):
            acc += w
            if u < acc:
                break
        a, b, c, d, e, f = BARNSLEY[k][0]
        x, y = a * x + b * y + e, c * x + d * y + f
        if i >= burn:
            out.append((x, y, k))
    return out


def barnsley(slots, bars):
    """El helecho de Barnsley: la altura y del punto da el grado (el helecho crece hacia arriba) y una campana suena
    cada vez que el punto salta a un foliolo, a su lado."""
    pts = barnsley_points(slots)
    sk = [round(-1 + 0.8 * y) for x, y, k in pts]
    feat = [(i * bars / slots, 0 if k == 2 else 2) for i, (x, y, k) in enumerate(pts) if k in (2, 3)]
    return {"skeleton": sk, "feature": feat}


def sandpile_relax(grid):
    """Relaja una pila de arena abeliana (Bak–Tang–Wiesenfeld): una casilla con 4 granos o más da uno a cada vecina
    (los del borde se caen). Devuelve cuántos derrumbes hubo."""
    n = len(grid)
    topples = 0
    stack = [(i, j) for i in range(n) for j in range(n) if grid[i][j] >= 4]
    while stack:
        i, j = stack.pop()
        if grid[i][j] < 4:
            continue
        grid[i][j] -= 4
        topples += 1
        if grid[i][j] >= 4:
            stack.append((i, j))
        for a, b in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if 0 <= a < n and 0 <= b < n:
                grid[a][b] += 1
                if grid[a][b] >= 4:
                    stack.append((a, b))
    return topples


def sandpile(slots, bars, n=7):
    """Criticidad autoorganizada: en una pila de arena abeliana de 7×7 cae un grano por nota estructural (en un
    recorrido fijo de la rejilla) y la pila se derrumba en avalanchas de todos los tamaños, como las llamaradas. El
    tamaño de la avalancha y la altura donde cayó el grano dan el grado; cada derrumbe es un golpe de tambor grave."""
    grid = [[(i * j + i + 2 * j) % 4 for j in range(n)] for i in range(n)]
    sk, perc = [], []
    for k in range(slots):
        i, j = (3 * k + 1) % n, (5 * k + 2) % n
        grid[i][j] += 1
        size = sandpile_relax(grid)
        sk.append((2 * grid[i][j] + size) % 7)
        t = k * bars / slots
        for h in range(min(size, 4)):
            perc.append((t + h / 8, 41 if h == 0 else 43, 64 + min(size, 12) * 3 - h * 8))
    return {"skeleton": sk, "perc": perc}


FIGURE_EIGHT_T = 6.32591398


def figure_eight(steps=1200):
    """La órbita en ocho de tres cuerpos iguales (Chenciner–Montgomery, 2000; condiciones iniciales de Simó), G = m = 1,
    integrada con RK4 durante un periodo T = 6,3259. Devuelve [(x₁, y₁, energía cinética, energía total)]."""
    p = [[0.97000436, -0.24308753], [-0.97000436, 0.24308753], [0.0, 0.0]]
    w = [-0.93240737, -0.86473146]
    v = [[-w[0] / 2, -w[1] / 2], [-w[0] / 2, -w[1] / 2], w[:]]

    def acc(p):
        a = [[0.0, 0.0] for _ in range(3)]
        for i in range(3):
            for j in range(3):
                if i != j:
                    dx, dy = p[j][0] - p[i][0], p[j][1] - p[i][1]
                    r2 = dx * dx + dy * dy
                    r3 = r2 * fm.sqrt(r2)
                    a[i][0] += dx / r3
                    a[i][1] += dy / r3
        return a

    def energy(p, v):
        ke = sum(0.5 * (vx * vx + vy * vy) for vx, vy in v)
        pe = -sum(1 / fm.dist(p[i], p[j]) for i in range(3) for j in range(i + 1, 3))
        return ke, ke + pe

    def add(x, k, h):
        return [[x[i][d] + h * k[i][d] for d in range(2)] for i in range(3)]

    h = FIGURE_EIGHT_T / steps
    out = []
    for _ in range(steps + 1):
        ke, e = energy(p, v)
        out.append((p[0][0], p[0][1], ke, e))
        a1 = acc(p)
        p2, v2 = add(p, v, h / 2), add(v, a1, h / 2)
        a2 = acc(p2)
        p3, v3 = add(p, v2, h / 2), add(v, a2, h / 2)
        a3 = acc(p3)
        p4, v4 = add(p, v3, h), add(v, a3, h)
        a4 = acc(p4)
        p = [[p[i][d] + h / 6 * (v[i][d] + 2 * v2[i][d] + 2 * v3[i][d] + v4[i][d]) for d in range(2)] for i in range(3)]
        v = [[v[i][d] + h / 6 * (a1[i][d] + 2 * a2[i][d] + 2 * a3[i][d] + a4[i][d]) for d in range(2)] for i in range(3)]
    return out


def three_body(slots, bars):
    """Tres cuerpos iguales persiguiéndose por la misma órbita en ocho. La pieza recorre un periodo: x del cuerpo 1 da
    el grado y la energía cinética (corren más al cruzar el centro) la intensidad del compás: oleadas lentas y pesadas.
    Las campanas, cuando el cuerpo 1 cruza el centro del ocho."""
    steps = 1200
    orb = figure_eight(steps)
    xs = [orb[int(i * steps / slots)][0] for i in range(slots)]
    sk = [round(2 + 3.2 * x) for x in xs]
    kes = [orb[int(b * steps / bars)][2] for b in range(bars)]
    lo, hi = min(kes), max(kes)
    dyn = [0.25 + 0.7 * (k - lo) / (hi - lo) for k in kes]
    feat = [(i * bars / slots, 0) for i in range(1, slots) if xs[i - 1] * xs[i] <= 0]
    return {"skeleton": sk, "dyn": dyn, "feature": feat}


def fibonacci_word(n):
    """La palabra de Fibonacci (0 = largo, 1 = corto): s(k) = 2 + ⌊kφ⌋ − ⌊(k+1)φ⌋, un cuasicristal de una dimensión."""
    return [2 + math.floor(k * PHI) - math.floor((k + 1) * PHI) for k in range(1, n + 1)]


def quasicrystal(slots, bars):
    """Cuasicristal de Fibonacci: la sucesión de Beatty ⌊kφ⌋ mod 7 da la melodía (nunca se repite y nunca se desordena)
    y la palabra de Fibonacci pone una campana en los «largos» de los octavos fuertes: orden sin periodo, como el éter."""
    sk = [math.floor(k * PHI) % 7 for k in range(1, slots + 1)]
    wd = fibonacci_word(bars * 8)
    feat = [(i / 8, (i // 3) % 4) for i in range(bars * 8) if wd[i] == 0 and i % 2 == 0]
    return {"skeleton": sk, "feature": feat}


def rotation_curve(r, M=1.0, vh=1.0, a=1.5):
    """Curva de rotación de una galaxia: la masa visible M (casi toda en el centro) daría v_k = √(M/r) (Kepler); el halo
    isotermo de materia oscura añade v_h²·(1 − (a/r)·atan(r/a)). Devuelve (v_k, v observada)."""
    vk2 = M / r
    vd2 = vh * vh * (1 - (a / r) * fm.atan(r / a))
    return math.sqrt(vk2), math.sqrt(vk2 + vd2)


def dark_matter(slots, bars):
    """Materia oscura: la pieza va del centro de la galaxia al borde y vuelve (r de 0,5 a 10). La fracción invisible
    f = 1 − v_k²/v² (lo que la luz no explica de una curva de rotación plana) da el grado; las campanas suenan solo
    donde manda la materia oscura (f > 0,8) y el acompañamiento calla casi siempre: un vacío que pesa."""
    sk, feat = [], []
    half = slots // 2
    for i in range(slots):
        u = i / half if i < half else (slots - i) / half
        vk, v = rotation_curve(0.5 + 9.5 * u)
        f = 1 - (vk / v) * (vk / v)
        sk.append(round(6 * f) - (i % 3 == 2))
        if f > 0.8 and i % 4 == 0:
            feat.append((i * bars / slots, 2))
    mask = {"acc": [b % 4 == 2 for b in range(bars)], "bass": [b % 2 == 0 for b in range(bars)]}
    return {"skeleton": sk, "feature": feat, "mask": mask}


def midpoint_coast(levels=6, H=0.75, seed=2166136261):
    """Costa fractal por desplazamiento del punto medio: en cada nivel el desplazamiento se multiplica por 2^−H
    (exponente de Hurst H = 0,75, dimensión D = 2 − H = 1,25, la de la costa de Gran Bretaña según Richardson)."""
    s, pts, scale = seed, [0.0, 0.0], 1.0
    for _ in range(levels):
        nxt = []
        for a, b in zip(pts, pts[1:]):
            s ^= (s << 13) & 0xFFFFFFFF; s ^= s >> 17; s ^= (s << 5) & 0xFFFFFFFF
            nxt += [a, (a + b) / 2 + scale * ((s / 0xFFFFFFFF) * 2 - 1)]
        pts = nxt + [pts[-1]]
        scale *= fm.pow(2.0, -H)
    return pts


def coastline(slots, bars):
    """La paradoja de la costa: una costa fractal (D = 1,25) medida con una regla cada vez más corta no deja de crecer.
    La pieza camina la costa; su altura da el grado y los cabos (máximos locales) tocan las campanas."""
    pts = midpoint_coast()
    ys = [pts[int(i * (len(pts) - 1) / slots)] for i in range(slots)]
    lo, hi = min(ys), max(ys)
    sk = [round(-1 + 7 * (y - lo) / (hi - lo)) for y in ys]
    feat = [(i * bars / slots, 1) for i in range(1, slots - 1) if ys[i - 1] < ys[i] > ys[i + 1]]
    return {"skeleton": sk, "feature": feat}


def menger_solid(x, y, z, level=2):
    """Un cubito de la esponja de Menger de nivel 2 (9×9×9) está lleno si en ningún nivel dos de sus tres dígitos en
    base 3 son 1 a la vez."""
    for _ in range(level):
        if (x % 3 == 1) + (y % 3 == 1) + (z % 3 == 1) >= 2:
            return False
        x, y, z = x // 3, y // 3, z // 3
    return True


def menger(slots, bars):
    """La esponja de Menger, el sólido hueco: de 9³ = 729 cubitos quedan 20² = 400. Cada nota estructural cuenta los
    cubitos llenos de una fila (z de 0 a 8) y cada compás toca una fila de su cara, la alfombra de Sierpinski: las
    campanas suenan en los agujeros."""
    sk = []
    for j in range(slots):
        x, y = j % 9, (j // 9 + 4 * (j % 2)) % 9
        sk.append(sum(menger_solid(x, y, z) for z in range(9)) % 7)
    feat = [(b + x / 9, x % 3) for b in range(bars) for x in range(9) if not menger_solid(x, b % 9, 0)]
    return {"skeleton": sk, "feature": feat}


def packard(slots, bars, gens=48):
    """El copo de nieve de Packard: en una rejilla hexagonal se congela cada casilla que
    tiene EXACTAMENTE una vecina helada. Las casillas que se hielan en cada generación (siempre múltiplos de 6: el hielo es hexagonal)
    entre 6, módulo 7, dan el grado; el copo vuelve a empezar en las generaciones 2^k − 1 y la melodía también."""
    nb = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1))
    frozen, counts = {(0, 0)}, []
    for _ in range(gens):
        cand = {}
        for (q, r) in frozen:
            for dq, dr in nb:
                c = (q + dq, r + dr)
                if c not in frozen: cand[c] = cand.get(c, 0) + 1
        new = [c for c, n in cand.items() if n == 1]
        frozen.update(new)
        counts.append(len(new))
    return {"skeleton": cyc([(n // 6) % 7 for n in counts], slots)}


SOURCES = {f.__name__: f for f in [
    pisano, phyllotaxis, silver, tides, gould, bresenham, thue_morse, fifths, koch, heat, bessel, logistic, lissajous,
    kepler, zeta, primes, pendulum, coupled, still_lifes, ulam, cantor, hilbert, lo_shu, lsystem, mandel_pi, harmonics,
    b37_glider, farey, tetractys, lorenz, fourier_square, dihedral, sieve, mobius, gray, catalan, quadratic_residues,
    pi_base7, e_fraction, token_bucket, ghz, conway_glider, replicator, divisors12, lunar, triples, free_fall, swells,
    nautilus, barnsley, sandpile, three_body, quasicrystal, dark_matter, coastline, menger, packard]}
