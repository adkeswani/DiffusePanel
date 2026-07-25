"""
Watercolor - smooth Perlin-noise-based color fields that morph very slowly.

Like watching paint bleed on wet paper. Uses simplex-style noise
to create organic, slowly evolving color blends.
"""

import math
import random
from patterns.base import Pattern, WIDTH, HEIGHT, NUM_LEDS, xy_to_index, hsv_to_rgb


def _grad(h: int, x: float, y: float) -> float:
    """Simple 2D gradient for noise generation."""
    vectors = [(1, 1), (-1, 1), (1, -1), (-1, -1),
               (1, 0), (-1, 0), (0, 1), (0, -1)]
    g = vectors[h % 8]
    return g[0] * x + g[1] * y


def _fade(t: float) -> float:
    """Smoothstep fade curve."""
    return t * t * t * (t * (t * 6 - 15) + 10)


def _lerp(a: float, b: float, t: float) -> float:
    return a + t * (b - a)


class PerlinNoise:
    """Simple 2D Perlin noise implementation."""

    def __init__(self, seed: int = 42):
        random.seed(seed)
        self.perm = list(range(256))
        random.shuffle(self.perm)
        self.perm = self.perm + self.perm  # Double for overflow

    def noise(self, x: float, y: float) -> float:
        """Return noise value in range [-1, 1]."""
        # Grid cell coordinates
        xi = int(math.floor(x)) & 255
        yi = int(math.floor(y)) & 255

        # Relative position within cell
        xf = x - math.floor(x)
        yf = y - math.floor(y)

        # Fade curves
        u = _fade(xf)
        v = _fade(yf)

        # Hash corners
        aa = self.perm[self.perm[xi] + yi]
        ab = self.perm[self.perm[xi] + yi + 1]
        ba = self.perm[self.perm[xi + 1] + yi]
        bb = self.perm[self.perm[xi + 1] + yi + 1]

        # Gradient dot products and interpolation
        x1 = _lerp(_grad(aa, xf, yf), _grad(ba, xf - 1, yf), u)
        x2 = _lerp(_grad(ab, xf, yf - 1), _grad(bb, xf - 1, yf - 1), u)

        return _lerp(x1, x2, v)


class Watercolor(Pattern):
    name = "Watercolor"

    def __init__(self):
        super().__init__()
        self.noise = PerlinNoise(seed=random.randint(0, 10000))
        self.scale = 0.25      # Spatial scale (lower = larger blobs)
        self.time_speed = 0.003  # Very slow evolution

    def update(self, leds: list, frame: int) -> None:
        t = frame * self.time_speed

        for y in range(HEIGHT):
            for x in range(WIDTH):
                idx = xy_to_index(x, y)

                # Sample noise at different offsets for hue and brightness
                nx = x * self.scale
                ny = y * self.scale

                # Multi-octave noise for richer hue variation
                hue_noise = (
                    self.noise.noise(nx + t, ny + t * 0.7) * 0.6 +
                    self.noise.noise(nx * 2.0 + t * 1.3, ny * 2.0 + t * 0.5) * 0.3 +
                    self.noise.noise(nx * 4.0 + t * 0.8, ny * 4.0 + t * 1.1) * 0.1
                )
                # Amplify noise to use more of the hue range, plus a rotating offset
                # so we visit all colors over time
                hue_offset = frame * 0.12  # Slow full-spectrum rotation
                hue = int(hue_noise * 200 + hue_offset) % 256

                # Brightness from a different noise sample
                bright_noise = self.noise.noise(nx + 100 + t * 0.5, ny + 100 + t * 0.3)
                # Map to brightness range with a minimum floor
                brightness = int((bright_noise + 1.0) * 0.5 * 160 + 40)
                brightness = max(30, min(200, brightness))

                sat = 190
                leds[idx] = hsv_to_rgb(hue, sat, brightness)
