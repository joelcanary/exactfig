"""
Math-music tests / pruebas de la música matemática (python -m unittest discover tests).

The mathematics behind each source is checked against known, independent facts; the composer against its own rules
(cadences, optimal voice leading, determinism); the MIDI writer by round trip.
"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from exactfig.music import composer, smf, sources, theory  # noqa: E402

SPECS = [
    dict(seed="t1", title="Pisano Period", math="Fibonacci mod 7", source="pisano", mode="dorian", tonic=62, bpm=96, meter="4/4",
         bars=16, ensemble="forest"),
    dict(seed="t2", title="Packard", math="snowflake", source="packard", mode="lydian", tonic=64, bpm=84, meter="3/4", bars=16,
         ensemble="snow"),
    dict(seed="t3", title="Glider", math="B3/S23", source="conway_glider", mode="aeolian", tonic=57, bpm=80, meter="6/8", bars=24,
         ensemble="mist"),
    dict(seed="t4", title="Kepler", math="Kepler equation", source="kepler", mode="phrygian", tonic=60, bpm=110, meter="4/4", bars=32,
         ensemble="desert", density="lively"),
]


def life_step(cells, B, S):
    cnt = {}
    for (x, y) in cells:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    cnt[(x + dx, y + dy)] = cnt.get((x + dx, y + dy), 0) + 1
    return {c for c, k in cnt.items() if (k in S if c in cells else k in B)}


class Maths(unittest.TestCase):
    def test_pisano_period_of_7_is_16(self):
        sk = sources.pisano(48, 24)["skeleton"]
        self.assertEqual(sk[:16], sk[16:32])
        self.assertNotEqual(sk[:8], sk[8:16])
        self.assertEqual(sk[:8], [0, 1, 1, 2, 3, 5, 1, 6])          # 0 1 1 2 3 5 8≡1 13≡6

    def test_pi_in_base_7(self):
        # π = 3.0663651432036134110263560425... (base 7); comprobado también desde el valor decimal
        self.assertEqual(sources.pi_digits(7, 12), [3, 0, 6, 6, 3, 6, 5, 1, 4, 3, 2, 0])
        self.assertEqual(sources.pi_digits(10, 15), [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7, 9])
        v = sum(d * 7.0 ** -i for i, d in enumerate(sources.pi_digits(7, 18)))
        self.assertAlmostEqual(v, math.pi, places=12)

    def test_hilbert_curve_visits_every_cell_by_neighbours(self):
        pts = [sources.hilbert_d2xy(3, d) for d in range(64)]
        self.assertEqual(len(set(pts)), 64)
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            self.assertEqual(abs(x0 - x1) + abs(y0 - y1), 1)
        sk = sources.hilbert(64, 32)["skeleton"]
        self.assertTrue(all(abs(a - b) == 1 for a, b in zip(sk, sk[1:])), "la melodía va por grados conjuntos")

    def test_ulam_spiral_is_a_walk_by_neighbours(self):
        pts = [sources.ulam_xy(n) for n in range(1, 200)]
        self.assertEqual(len(set(pts)), len(pts))
        for a, b in zip(pts, pts[1:]):
            self.assertEqual(abs(a[0] - b[0]) + abs(a[1] - b[1]), 1)

    def test_still_lifes_are_still_under_b3_s23(self):
        for name, cells in sources.STILL_LIFES.items():
            self.assertEqual(life_step(set(cells), {3}, {2, 3}), set(cells), name)

    def test_conway_glider_phases_follow_the_rule(self):
        # las 4 fases que usa la pieza: cada una es la siguiente generación de la anterior (y la 5ª, la 1ª desplazada)
        src = sources.conway_glider(8, 4)
        phases = [{(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)}]
        for _ in range(4):
            phases.append(life_step(phases[-1], {3}, {2, 3}))
        self.assertEqual(phases[4], {(x + 1, y + 1) for x, y in phases[0]})
        heard = [sorted((round((t - b) * 4), idx) for t, idx in src["feature"] if int(t) == b) for b in range(4)]
        for b in range(4):
            self.assertEqual([x for x, _ in heard[b]], sorted(x for x, _ in phases[b]))

    def test_b37_glider_cycle_is_exactly_32(self):
        src = sources.b37_glider(64, 32)            # la propia fuente comprueba el ciclo (assert)
        bars = {int(t) for t, _ in src["feature"]}
        self.assertEqual(bars, set(range(32)))
        self.assertTrue(all(sum(1 for t, _ in src["feature"] if int(t) == b) == 5 for b in range(32)), "5 celdas vivas")

    def test_token_bucket_never_exceeds_C_plus_r_n(self):
        src = sources.token_bucket(48, 24)
        hits = sorted(t for t, _, _ in src["perc"])
        for n in range(1, 24 * 8 + 1):
            self.assertLessEqual(sum(1 for t in hits if t * 8 < n), 4 + 0.5 * n)

    def test_kepler_equation_is_solved(self):
        e = 0.6
        for i in range(16):
            M = 2 * math.pi * i / 16
            E = M
            for _ in range(30):
                E -= (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
            self.assertAlmostEqual(E - e * math.sin(E), M, places=10)
        sk = sources.kepler(16, 8)["skeleton"]
        moves = [abs(b - a) % 7 for a, b in zip(sk, sk[1:])]
        self.assertGreater(moves[0] + moves[-1], moves[7] + moves[8], "corre en el perihelio, se arrastra en el afelio")

    def test_logistic_map_doubles_its_period(self):
        sk = sources.logistic(64, 32)["skeleton"]
        self.assertEqual(sk[0:2], sk[2:4])                 # r = 3,2: periodo 2
        self.assertEqual(sk[16:20], sk[20:24])             # r = 3,5: periodo 4

    def test_quadratic_residues_mod_13_are_symmetric(self):
        qr = {(k * k) % 13 for k in range(1, 13)}
        self.assertEqual(qr, {1, 3, 4, 9, 10, 12})
        self.assertEqual(qr, {13 - q for q in qr})

    def test_e_continued_fraction(self):
        sk = sources.e_fraction(6, 4)["skeleton"]
        self.assertEqual(sk, [2, 3, 8 % 7, 11 % 7, 19 % 7, 87 % 7])   # 2, 3, 8/3, 11/4, 19/7, 87/32 → e

    def test_lo_shu_lines_sum_to_15(self):
        seq = [v + 1 for v in sources.lo_shu(24, 12)["skeleton"]]
        for k in range(8):
            self.assertEqual(sum(seq[3 * k:3 * k + 3]), 15)

    def test_zeta_zeros_are_increasing_with_known_first_values(self):
        self.assertAlmostEqual(sources.ZETA[0], 14.134725, places=5)
        self.assertTrue(all(a < b for a, b in zip(sources.ZETA, sources.ZETA[1:])))


class Composer(unittest.TestCase):
    def test_voice_leading_is_optimal(self):
        scale = theory.MODES["ionian"]
        prev = (55, 60, 64, 67)
        for deg in range(7):
            pcs = theory.chord_pcs(scale, 0, deg)
            best = theory.best_voicing(prev, pcs, 48, 69, 4)
            allv = theory.voicings(pcs, 48, 69, 4)
            score = lambda c: theory.voice_leading_score(prev, c)  # noqa: E731
            self.assertEqual(score(best), min(score(c) for c in allv), "óptimo por fuerza bruta")

    def test_harmony_has_cadences_and_contains_the_melody(self):
        for spec in SPECS:
            pl = composer.plan(spec)
            self.assertEqual(pl["roots"][0], 0, spec["seed"])
            self.assertIn(pl["roots"][-1], theory.CADENCE[spec["mode"]][0], spec["seed"] + ": el bucle acaba en dominante")
            for b in range(7, pl["bars"] - 1, 8):
                self.assertEqual(pl["roots"][b], 0, f"{spec['seed']}: cadencia a la tónica en el compás {b + 1}")
            spb = pl["m"]["slots"]
            for b, r in enumerate(pl["roots"]):
                self.assertIn(pl["deg"][b * spb] % 7, composer.chord_degrees(r))

    def test_same_recipe_same_bytes(self):
        for spec in SPECS:
            for kind in ("day", "combat"):
                a, _ = composer.compose(spec, kind)
                b, _ = composer.compose(spec, kind)
                self.assertEqual(smf.encode(**a), smf.encode(**b))

    def test_midi_round_trip_and_seamless_loop(self):
        args, _ = composer.compose(SPECS[0], "day")
        data = smf.encode(**args)
        r = smf.read(data)
        self.assertEqual(r["names"][0], "Pisano Period")
        self.assertEqual(len(r["tempos"]), 1)
        self.assertEqual(r["length"], args["length_ticks"])
        self.assertTrue(all(e == args["length_ticks"] for e in r["ends"]), "todas las pistas acaban en el tick del bucle")
        self.assertEqual(len(r["notes"]), sum(len(t["notes"]) for t in args["tracks"]))

    def test_every_source_is_deterministic_and_in_range(self):
        for name, fn in sources.SOURCES.items():
            a, b = fn(64, 32), fn(64, 32)
            self.assertEqual(a, b, name)
            self.assertGreaterEqual(len(a["skeleton"]), 1, name)
            self.assertTrue(all(isinstance(d, int) for d in a["skeleton"]), name)


class Fractals(unittest.TestCase):
    """Fractales y sistemas dinámicos: nautilo, helecho, pila de arena, tres cuerpos, costa, esponja."""

    def test_nautilus_grows_by_phi_every_quarter_turn(self):
        for k in range(8):
            th = k * math.pi / 2
            self.assertAlmostEqual(sources.nautilus_r(th + math.pi / 2) / sources.nautilus_r(th), sources.PHI, places=12)
        sk = sources.nautilus(64, 32)["skeleton"]
        self.assertEqual(sk[:16], sk[16:32], "a las dos vueltas empieza una cámara nueva igual")
        self.assertLess(max(sk[:8]) - min(sk[:8]), max(sk[8:16]) - min(sk[8:16]), "la segunda vuelta es más ancha")

    def test_barnsley_fern_stays_in_its_box_and_uses_its_weights(self):
        pts = sources.barnsley_points(4000)
        self.assertTrue(all(-2.2 <= x <= 2.7 and 0 <= y <= 10 for x, y, _ in pts))
        share = [sum(1 for *_, k in pts if k == i) / len(pts) for i in range(4)]
        for got, (_, w) in zip(share, sources.BARNSLEY):
            self.assertAlmostEqual(got, w / 100, delta=0.03)

    def test_sandpile_is_abelian_and_stable(self):
        g = [[0] * 3 for _ in range(3)]
        g[1][1] = 4
        self.assertEqual(sources.sandpile_relax(g), 1)
        self.assertEqual(g, [[0, 1, 0], [1, 0, 1], [0, 1, 0]])
        drops = [(i % 5, (3 * i) % 5) for i in range(60)]
        results = []
        for order in (drops, drops[::-1]):
            g = [[3] * 5 for _ in range(5)]
            for i, j in order:
                g[i][j] += 1
                sources.sandpile_relax(g)
            self.assertTrue(all(c < 4 for row in g for c in row))
            results.append(g)
        self.assertEqual(results[0], results[1], "el orden de los granos no cambia la pila final (grupo abeliano)")

    def test_figure_eight_conserves_energy_and_closes(self):
        orb = sources.figure_eight(1200)
        e0 = orb[0][3]
        self.assertLess(max(abs(o[3] - e0) for o in orb) / abs(e0), 1e-6)
        self.assertAlmostEqual(orb[-1][0], orb[0][0], places=4)
        self.assertAlmostEqual(orb[-1][1], orb[0][1], places=4)

    def test_fibonacci_word(self):
        w = sources.fibonacci_word(13)
        self.assertEqual("".join(map(str, w)), "0100101001001")
        w = sources.fibonacci_word(987)
        self.assertAlmostEqual(w.count(0) / w.count(1), sources.PHI, places=2)

    def test_rotation_curve_is_flat_where_kepler_falls(self):
        vk5, v5 = sources.rotation_curve(5)
        vk10, v10 = sources.rotation_curve(10)
        self.assertAlmostEqual(vk10 / vk5, 2 ** -0.5, places=12)      # Kepler: v ∝ r^(−1/2)
        self.assertLess(abs(v10 / v5 - 1), 0.08, "la observada casi no baja")
        self.assertGreater(1 - (vk10 / v10) ** 2, 1 - (vk5 / v5) ** 2, "lejos del centro manda la materia oscura")

    def test_coastline_grows_with_a_shorter_ruler(self):
        pts = sources.midpoint_coast()
        self.assertEqual(len(pts), 2 ** 6 + 1)
        self.assertEqual((pts[0], pts[-1]), (0.0, 0.0))

        def length(step):
            q = pts[::step]
            return sum(math.hypot(1 / (len(q) - 1), b - a) for a, b in zip(q, q[1:]))
        ls = [length(2 ** k) for k in (4, 3, 2, 1, 0)]
        self.assertEqual(ls, sorted(ls), "cuanto más corta la regla, más larga la costa")

    def test_menger_sponge_counts(self):
        self.assertEqual(sum(sources.menger_solid(x, y, z) for x in range(9) for y in range(9) for z in range(9)), 400)
        self.assertEqual(sum(sources.menger_solid(x, y, 0) for x in range(9) for y in range(9)), 64, "la cara es la alfombra")
        self.assertFalse(sources.menger_solid(4, 4, 0))


if __name__ == "__main__":
    unittest.main()
