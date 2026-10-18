"""
Deterministic randomness / azar determinista.

xorshift32 seeded from the SHA-256 of a text: the same seed gives the same sequence on any machine and any Python version
(only integer arithmetic). `random.Random` is never used by generators: its algorithm is an implementation detail.
xorshift32 sembrado con el SHA-256 de un texto: la misma semilla, la misma secuencia en cualquier máquina.
"""
from __future__ import annotations

import hashlib


class Rng:
    """xorshift32 (Marsaglia 2003) seeded with the first 4 bytes of the SHA-256 of the seed's text: equal seeds give
    equal streams on every platform and in every process, independent of Python's own `random`."""
    def __init__(self, seed: str | int):
        h = hashlib.sha256(str(seed).encode("utf-8")).digest()
        self.s = int.from_bytes(h[:4], "little") or 0x9E3779B9

    def u32(self) -> int:
        """The next 32 random bits."""
        x = self.s
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        self.s = x & 0xFFFFFFFF
        return self.s

    def random(self) -> float:
        """[0, 1) con 32 bits (exacto: u32 / 2^32)."""
        return self.u32() / 4294967296.0

    def randint(self, a: int, b: int) -> int:
        """An integer in [a, b], both ends included, as a + u32 mod (b − a + 1): the modulo bias is below
        (b − a + 1) / 2^32, negligible for the small ranges generators use."""
        return a + self.u32() % (b - a + 1)

    def uniform(self, a: float, b: float) -> float:
        """A uniform float in [a, b)."""
        return a + (b - a) * self.random()

    def chance(self, p: float) -> bool:
        """True with probability p."""
        return self.random() < p

    def pick(self, seq):
        """An element of a non-empty sequence (u32 mod its length, as in randint)."""
        return seq[self.u32() % len(seq)]

    def weighted(self, options: dict):
        """{"small": 60, "big": 25, "none": 15} → una clave según su peso."""
        total = sum(options.values())
        r = self.random() * total
        for k, w in options.items():
            r -= w
            if r < 0:
                return k
        return k

    def fork(self, label: str) -> "Rng":
        """Una subsecuencia independiente: cambiar una parte del dibujo no altera las demás."""
        return Rng(f"{self.s}:{label}")


def seed_int(seed: str | int, salt: str = "") -> int:
    """Una semilla entera de 31 bits a partir de cualquier texto (para hash2/fbm/worley)."""
    return int.from_bytes(hashlib.sha256(f"{seed}|{salt}".encode("utf-8")).digest()[:4], "little") & 0x7FFFFFFF
