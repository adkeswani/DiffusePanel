"""
Bit-accurate Python port of FastLED's inoise8(x, y).

Ported directly from FastLED's src/noise.cpp.hpp so the values match what the
ESP32 actually computes. This lets us investigate the "flashing bright pixel"
artifact in the Botanical/Grass pattern without flashing firmware.

Key source pieces reproduced:
  - inoise8(x, y)      -> raw + 64, then qadd8(n, n)
  - inoise8_raw(x, y)  -> 2D Perlin with the FastLED hashing
  - grad8(hash, x, y)  -> the 2-arg gradient (noise.cpp.hpp line ~217)
  - avg7, lerp7by8, ease8InOutQuad (EASE8), scale8, qadd8
  - PERLIN permutation table (periodic, indexed & 255)

scale8 uses the modern FastLED default (FASTLED_SCALE8_FIXED == 1):
    scale8(i, sc) = (i * (1 + sc)) >> 8
"""

# FastLED permutation table (the classic Ken Perlin values used by FastLED).
PERM = [
    151, 160, 137, 91, 90, 15, 131, 13, 201, 95, 96, 53, 194, 233, 7, 225,
    140, 36, 103, 30, 69, 142, 8, 99, 37, 240, 21, 10, 23, 190, 6, 148,
    247, 120, 234, 75, 0, 26, 197, 62, 94, 252, 219, 203, 117, 35, 11, 32,
    57, 177, 33, 88, 237, 149, 56, 87, 174, 20, 125, 136, 171, 168, 68, 175,
    74, 165, 71, 134, 139, 48, 27, 166, 77, 146, 158, 231, 83, 111, 229, 122,
    60, 211, 133, 230, 220, 105, 92, 41, 55, 46, 245, 40, 244, 102, 143, 54,
    65, 25, 63, 161, 1, 216, 80, 73, 209, 76, 132, 187, 208, 89, 18, 169,
    200, 196, 135, 130, 116, 188, 159, 86, 164, 100, 109, 198, 173, 186, 3, 64,
    52, 217, 226, 250, 124, 123, 5, 202, 38, 147, 118, 126, 255, 82, 85, 212,
    207, 206, 59, 227, 47, 16, 58, 17, 182, 189, 28, 42, 223, 183, 170, 213,
    119, 248, 152, 2, 44, 154, 163, 70, 221, 153, 101, 155, 167, 43, 172, 9,
    129, 22, 39, 253, 19, 98, 108, 110, 79, 113, 224, 232, 178, 185, 112, 104,
    218, 246, 97, 228, 251, 34, 242, 193, 238, 210, 144, 12, 191, 179, 162, 241,
    81, 51, 145, 235, 249, 14, 239, 107, 49, 192, 214, 31, 181, 199, 106, 157,
    184, 84, 204, 176, 115, 121, 50, 45, 127, 4, 150, 254, 138, 236, 205, 93,
    222, 114, 67, 29, 24, 72, 243, 141, 128, 195, 78, 66, 215, 61, 156, 180,
]
assert len(PERM) == 256


def _u8(v: int) -> int:
    return v & 0xFF


def _i8(v: int) -> int:
    """Truncate to signed 8-bit, mirroring C int8_t assignment/overflow."""
    v &= 0xFF
    return v - 256 if v >= 128 else v


def p(i: int) -> int:
    """NOISE_P(x): permutation lookup, periodic with period 256."""
    return PERM[i & 255]


def scale8(i: int, sc: int) -> int:
    # FASTLED_SCALE8_FIXED == 1 (modern default)
    return ((i & 0xFF) * (1 + (sc & 0xFF))) >> 8 & 0xFF


def qadd8(i: int, j: int) -> int:
    s = (i & 0xFF) + (j & 0xFF)
    return 255 if s > 255 else s


def avg7(i: int, j: int) -> int:
    """Signed 7-bit average, rounded up. int8_t inputs and result."""
    i = _i8(i)
    j = _i8(j)
    return _i8(((i + j) >> 1) + (i & 1))


def grad8(hash_: int, x: int, y: int) -> int:
    """2D gradient (FastLED noise.cpp.hpp ~line 217). x, y are int8_t."""
    x = _i8(x)
    y = _i8(y)
    if hash_ & 4:
        u, v = y, x
    else:
        u, v = x, y
    if hash_ & 1:
        u = _i8(-u)
    if hash_ & 2:
        v = _i8(-v)
    return avg7(u, v)


def ease8InOutQuad(i: int) -> int:
    """EASE8 (lib8tion.h C implementation)."""
    i &= 0xFF
    j = i
    if j & 0x80:
        j = 255 - j
    jj = scale8(j, j)
    jj2 = (jj << 1) & 0xFF
    if i & 0x80:
        jj2 = 255 - jj2
    return jj2 & 0xFF


def lerp7by8(a: int, b: int, frac: int) -> int:
    """int8_t lerp with 8-bit fraction (FastLED)."""
    a = _i8(a)
    b = _i8(b)
    if b > a:
        delta = _u8(b - a)
        scaled = scale8(delta, frac)
        result = a + scaled
    else:
        delta = _u8(a - b)
        scaled = scale8(delta, frac)
        result = a - scaled
    return _i8(result)


def inoise8_raw(x: int, y: int) -> int:
    """2D raw noise, output range roughly -64..+64 (int8_t)."""
    x &= 0xFFFF
    y &= 0xFFFF

    X = (x >> 8) & 0xFF
    Y = (y >> 8) & 0xFF

    A = _u8(p(X) + Y)
    AA = p(A)
    AB = p(A + 1)
    B = _u8(p(X + 1) + Y)
    BA = p(B)
    BB = p(B + 1)

    u = x & 0xFF
    v = y & 0xFF

    xx = ((x & 0xFF) >> 1) & 0x7F
    yy = ((y & 0xFF) >> 1) & 0x7F
    N = 0x80

    u = ease8InOutQuad(u)
    v = ease8InOutQuad(v)

    X1 = lerp7by8(grad8(p(AA), xx, yy), grad8(p(BA), xx - N, yy), u)
    X2 = lerp7by8(grad8(p(AB), xx, yy - N), grad8(p(BB), xx - N, yy - N), u)
    ans = lerp7by8(X1, X2, v)
    return ans


def inoise8(x: int, y: int) -> int:
    """Scaled 2D noise, output range 0..255 (matches FastLED inoise8)."""
    n = inoise8_raw(x, y)  # -64..+64
    n += 64                # 0..128
    return qadd8(n, n)     # 0..255
