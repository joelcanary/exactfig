"""Portable floating-point maths: the same last bit on every machine.

IEEE 754 rounds `+ - * /` and `sqrt` correctly, so those give identical results everywhere. `sin`, `cos`, `atan2`,
`exp`, `log` and `pow` from the platform library do not: each C library rounds them its own way, and a last-bit
difference can flip a pixel that sits exactly on a threshold. Generators call the functions below instead. They are
written with basic arithmetic, `sqrt`, `floor`, `frexp` and `ldexp` only (all exact or correctly rounded), so a recipe
gives the same bytes on any platform by construction, not by luck.

The algorithms and coefficients are those of fdlibm (s_sin.c, k_sin.c, k_cos.c, s_atan.c, e_atan2.c, e_exp.c,
e_log.c), accurate to about one unit in the last place over the ranges used here:

    Copyright (C) 1993 by Sun Microsystems, Inc. All rights reserved.
    Developed at SunPro, a Sun Microsystems, Inc. business.
    Permission to use, copy, modify, and distribute this software is freely granted, provided that this notice
    is preserved.

Constants are written as their IEEE 754 bit patterns (the hex words of the fdlibm sources), so no decimal
conversion stands between the source and the value.
"""
from __future__ import annotations

import math
import struct

__all__ = ["pi", "tau", "sqrt", "floor", "hypot", "dist", "dist2", "radians", "sin", "cos", "atan", "atan2", "exp", "log",
           "log2", "pow", "cbrt"]


def _d(hi: int, lo: int) -> float:
    return struct.unpack(">d", struct.pack(">II", hi, lo))[0]


pi = math.pi                       # a constant, not a computation: the same double everywhere
tau = 2.0 * math.pi
sqrt = math.sqrt                   # IEEE 754 requires a correctly rounded square root
floor = math.floor


def hypot(x: float, y: float) -> float:
    """√(x² + y²) with basic arithmetic (the library hypot is not specified to the last bit)."""
    return sqrt(x * x + y * y)


def dist(a, b) -> float:
    """Euclidean distance between two points (math.dist is C code that a compiler may fuse into FMA)."""
    return sqrt(dist2(a, b))


def dist2(a, b) -> float:
    """Squared Euclidean distance: enough to compare distances, and exact operations only."""
    s = 0.0
    for u, v in zip(a, b):
        d = u - v
        s += d * d
    return s


_DEG = pi / 180.0


def radians(deg: float) -> float:
    """Degrees to radians by one multiplication with the double nearest π/180."""
    return deg * _DEG


# ---------------------------------------------------------------------------------------------- sin and cos
_INVPIO2 = _d(0x3FE45F30, 0x6DC9C883)      # 2/π
_PIO2_1 = _d(0x3FF921FB, 0x54400000)       # first 33 bits of π/2
_PIO2_1T = _d(0x3DD0B461, 0x1A626331)      # π/2 − PIO2_1
_PIO2_2 = _d(0x3DD0B461, 0x1A600000)       # second 33 bits of π/2
_PIO2_2T = _d(0x3BA3198A, 0x2E037073)      # π/2 − (PIO2_1 + PIO2_2)
_PIO2_3 = _d(0x3BA3198A, 0x2E000000)       # third 33 bits of π/2
_PIO2_3T = _d(0x397B839A, 0x252049C1)      # π/2 − (PIO2_1 + PIO2_2 + PIO2_3)
_PIO4 = _d(0x3FE921FB, 0x54442D18)
_REDUCE_MAX = _d(0x413921FB, 0x00000000)   # 2^20 · π/2: n·PIO2_1 stays exact below this

_S1 = _d(0xBFC55555, 0x55555549)
_S2 = _d(0x3F811111, 0x1110F8A6)
_S3 = _d(0xBF2A01A0, 0x19C161D5)
_S4 = _d(0x3EC71DE3, 0x57B1FE7D)
_S5 = _d(0xBE5AE5E6, 0x8A2B9CEB)
_S6 = _d(0x3DE5D93A, 0x5ACFD57C)

_C1 = _d(0x3FA55555, 0x5555554C)
_C2 = _d(0xBF56C16C, 0x16C15177)
_C3 = _d(0x3EFA01A0, 0x19CB1590)
_C4 = _d(0xBE927E4F, 0x809C52AD)
_C5 = _d(0x3E21EE9E, 0xBDB4B1C4)
_C6 = _d(0xBDA8FAE9, 0xBE8838D4)


def _ksin(x: float, y: float, iy: int) -> float:
    """sin(x + y) on [−π/4, π/4]; y is the tail of x."""
    z = x * x
    v = z * x
    r = _S2 + z * (_S3 + z * (_S4 + z * (_S5 + z * _S6)))
    if iy == 0:
        return x + v * (_S1 + z * r)
    return x - ((z * (0.5 * y - v * r) - y) - v * _S1)


def _kcos(x: float, y: float) -> float:
    """cos(x + y) on [−π/4, π/4]."""
    z = x * x
    w = z * z
    r = z * (_C1 + z * (_C2 + z * _C3)) + w * w * (_C4 + z * (_C5 + z * _C6))
    hz = 0.5 * z
    w = 1.0 - hz
    return w + (((1.0 - w) - hz) + (z * r - x * y))


def _exponent(x: float) -> int:
    return math.frexp(x)[1]


def _reduce(x: float) -> tuple[int, float, float]:
    """x = n·π/2 + (y0 + y1), |y0 + y1| ≤ π/4, with up to three Cody–Waite rounds (fdlibm's medium-size path)."""
    if not abs(x) < _REDUCE_MAX:
        raise ValueError(f"fmath: argument {x!r} is too large for the portable reduction (|x| < 1.6e6)")
    n = int(floor(x * _INVPIO2 + 0.5))
    fn = float(n)
    r = x - fn * _PIO2_1
    w = fn * _PIO2_1T
    y0 = r - w
    j = _exponent(x)
    if j - _exponent(y0) > 16:
        t = r
        w = fn * _PIO2_2
        r = t - w
        w = fn * _PIO2_2T - ((t - r) - w)
        y0 = r - w
        if j - _exponent(y0) > 49:
            t = r
            w = fn * _PIO2_3
            r = t - w
            w = fn * _PIO2_3T - ((t - r) - w)
            y0 = r - w
    y1 = (r - y0) - w
    return n, y0, y1


def sin(x: float) -> float:
    """sin x, within 1 ulp; |x| must be below 2^20·π/2 (larger arguments raise ValueError)."""
    if abs(x) <= _PIO4:
        return _ksin(x, 0.0, 0)
    n, y0, y1 = _reduce(x)
    q = n & 3
    if q == 0:
        return _ksin(y0, y1, 1)
    if q == 1:
        return _kcos(y0, y1)
    if q == 2:
        return -_ksin(y0, y1, 1)
    return -_kcos(y0, y1)


def cos(x: float) -> float:
    """cos x, within 1 ulp; |x| must be below 2^20·π/2 (larger arguments raise ValueError)."""
    if abs(x) <= _PIO4:
        return _kcos(x, 0.0)
    n, y0, y1 = _reduce(x)
    q = n & 3
    if q == 0:
        return _kcos(y0, y1)
    if q == 1:
        return -_ksin(y0, y1, 1)
    if q == 2:
        return -_kcos(y0, y1)
    return _ksin(y0, y1, 1)


# ---------------------------------------------------------------------------------------------- atan and atan2
_ATANHI = (_d(0x3FDDAC67, 0x0561BB4F), _d(0x3FE921FB, 0x54442D18), _d(0x3FEF730B, 0xD281F69B), _d(0x3FF921FB, 0x54442D18))
_ATANLO = (_d(0x3C7A2B7F, 0x222F65E2), _d(0x3C81A626, 0x33145C07), _d(0x3C700788, 0x7AF0CBBD), _d(0x3C91A626, 0x33145C07))
_AT = (_d(0x3FD55555, 0x5555550D), _d(0xBFC99999, 0x9998EBC4), _d(0x3FC24924, 0x920083FF), _d(0xBFBC71C6, 0xFE231671),
       _d(0x3FB745CD, 0xC54C206E), _d(0xBFB3B0F2, 0xAF749A6D), _d(0x3FB10D66, 0xA0D03D51), _d(0xBFADDE2D, 0x52DEFD9A),
       _d(0x3FA97B4B, 0x24760DEB), _d(0xBFA2B444, 0x2C6A6C2F), _d(0x3F90AD3A, 0xE322DA11))
_PI_LO = _d(0x3CA1A626, 0x33145C07)        # π − pi


def atan(x: float) -> float:
    """atan x in [−π/2, π/2], within 1 ulp: fdlibm's reduction to |t| < 7/16 around atan(1/2), atan(1), atan(3/2)
    or atan(∞), then an odd polynomial in t with 11 coefficients."""
    if x != x:
        return x
    ax = abs(x)
    if ax >= 7.378697629483821e19:         # 2^66
        z = _ATANHI[3] + _ATANLO[3]
        return z if x > 0 else -z
    if ax < 0.4375:
        if ax < 3.725290298461914e-09:     # 2^-28
            return x
        i = -1
        t = x
    else:
        if ax < 1.1875:
            if ax < 0.6875:
                i, t = 0, (2.0 * ax - 1.0) / (2.0 + ax)
            else:
                i, t = 1, (ax - 1.0) / (ax + 1.0)
        elif ax < 2.4375:
            i, t = 2, (ax - 1.5) / (1.0 + 1.5 * ax)
        else:
            i, t = 3, -1.0 / ax
    z = t * t
    w = z * z
    s1 = z * (_AT[0] + w * (_AT[2] + w * (_AT[4] + w * (_AT[6] + w * (_AT[8] + w * _AT[10])))))
    s2 = w * (_AT[1] + w * (_AT[3] + w * (_AT[5] + w * (_AT[7] + w * _AT[9]))))
    if i < 0:
        return t - t * (s1 + s2)
    z = _ATANHI[i] - ((t * (s1 + s2) - _ATANLO[i]) - t)
    return -z if x < 0 else z


def atan2(y: float, x: float) -> float:
    """Angle of (x, y) in (−π, π], with the sign conventions of C's atan2 for zeros."""
    if x != x or y != y:
        return x + y
    if y == 0.0:
        if math.copysign(1.0, x) > 0:
            return y                        # ±0
        return math.copysign(pi, y)
    if x == 0.0:
        return math.copysign(_ATANHI[3] + _ATANLO[3], y)
    if math.isinf(x) or math.isinf(y):
        return math.atan2(y, x)            # exact special values (±π/4, ±3π/4, ±π/2, ±0, ±π): fixed by C99
    z = atan(abs(y / x))
    if x > 0:
        return math.copysign(z, y)
    return math.copysign(pi - (z - _PI_LO), y)


# ---------------------------------------------------------------------------------------------- exp, log, pow
_LN2HI = _d(0x3FE62E42, 0xFEE00000)
_LN2LO = _d(0x3DEA39EF, 0x35793C76)
_INVLN2 = _d(0x3FF71547, 0x652B82FE)
_P1 = _d(0x3FC55555, 0x5555553E)
_P2 = _d(0xBF66C16C, 0x16BEBD93)
_P3 = _d(0x3F11566A, 0xAF25DE2C)
_P4 = _d(0xBEBBBD41, 0xC5D26BF1)
_P5 = _d(0x3E663769, 0x72BEA4D0)


def exp(x: float) -> float:
    """e^x, within 1 ulp; 0 below −745.13 and inf above 709.78."""
    if x != x:
        return x
    if x > 709.782712893384:
        return math.inf
    if x < -745.1332191019411:
        return 0.0
    if abs(x) < 3.725290298461914e-09:     # 2^-28
        return 1.0 + x
    k = int(floor(x * _INVLN2 + 0.5))
    hi = x - k * _LN2HI
    lo = k * _LN2LO
    r = hi - lo
    t = r * r
    c = r - t * (_P1 + t * (_P2 + t * (_P3 + t * (_P4 + t * _P5))))
    y = 1.0 - ((lo - (r * c) / (2.0 - c)) - hi)
    return math.ldexp(y, k)                # multiplying by 2^k is exact (outside the subnormal range)


_LG1 = _d(0x3FE55555, 0x55555593)
_LG2 = _d(0x3FD99999, 0x9997FA04)
_LG3 = _d(0x3FD24924, 0x94229359)
_LG4 = _d(0x3FCC71C5, 0x1D8E78AF)
_LG5 = _d(0x3FC74664, 0x96CB03DE)
_LG6 = _d(0x3FC39A09, 0xD078C69F)
_LG7 = _d(0x3FC2F112, 0xDF3E5244)
_SQRT_HALF = _d(0x3FE6A09E, 0x667F3BCD)


def _log_reduce(x: float):
    """x = 2^k · (1 + f) with √2/2 ≤ 1 + f < √2 (exact, by frexp and Sterbenz), and fdlibm's pieces of log(1 + f)."""
    if not x > 0.0 or math.isinf(x):
        raise ValueError(f"fmath: log of {x!r}")
    m, k = math.frexp(x)
    if m < _SQRT_HALF:
        m *= 2.0
        k -= 1
    f = m - 1.0
    s = f / (2.0 + f)
    z = s * s
    w = z * z
    t1 = w * (_LG2 + w * (_LG4 + w * _LG6))
    t2 = z * (_LG1 + w * (_LG3 + w * (_LG5 + w * _LG7)))
    return k, f, s, t2 + t1, 0.5 * f * f


def log(x: float) -> float:
    """Natural logarithm of x > 0, within 1 ulp; ValueError for x ≤ 0, inf or NaN."""
    k, f, s, R, hfsq = _log_reduce(x)
    dk = float(k)
    return dk * _LN2HI - ((hfsq - (s * (hfsq + R) + dk * _LN2LO)) - f)


def log2(x: float) -> float:
    """log₂ x; exact for powers of two (the integer part comes from the exponent)."""
    k, f, s, R, hfsq = _log_reduce(x)
    return k + (f - (hfsq - s * (hfsq + R))) * _INVLN2


def pow(x: float, y: float) -> float:
    """x ** y for x > 0 (or any x with an integer y). Integer exponents up to 64 by repeated squaring."""
    if y == 0.0:
        return 1.0
    if y == 0.5:
        return sqrt(x)
    if float(y).is_integer() and abs(y) <= 64:
        n = int(abs(y))
        acc, b = 1.0, x
        while n:
            if n & 1:
                acc *= b
            b *= b
            n >>= 1
        return 1.0 / acc if y < 0 else acc
    if x == 0.0:
        return 0.0 if y > 0 else math.inf
    if x < 0.0:
        raise ValueError(f"fmath: {x!r} ** {y!r} is not real")
    if x == 1.0:
        return 1.0
    return exp(y * log(x))


def cbrt(x: float) -> float:
    """Real cube root, one Newton step on top of exp(log(x)/3)."""
    if x == 0.0 or x != x:
        return x
    a = abs(x)
    c = exp(log(a) / 3.0)
    c = c - (c * c * c - a) / (3.0 * c * c)
    return c if x > 0 else -c
