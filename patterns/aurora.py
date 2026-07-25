"""
Aurora - slow drifting blobs of solid color that fade softly at their edges.

Like luminous bubbles floating gently across the panel.
Each blob is a single hue with a radial gradient falloff.
"""

import math
import random
from patterns.base import Pattern, WIDTH, HEIGHT, NUM_LEDS, xy_to_index, hsv_to_rgb


class Blob:
    """A single drifting color blob."""

    def __init__(self):
        self.reset()

    def reset(self):
        # Position (float for smooth movement)
        self.x = random.uniform(0, WIDTH - 1)
        self.y = random.uniform(0, HEIGHT - 1)
        # Velocity - very slow drift
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(0.01, 0.04)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        # Radius (how far the glow extends)
        self.radius = random.uniform(2.0, 4.5)
        # Brightness
        self.max_brightness = random.randint(150, 220)

    def advance(self):
        """Move the blob, wrapping at edges."""
        self.x += self.vx
        self.y += self.vy

        # Soft wrap around edges
        if self.x < -self.radius:
            self.x = WIDTH - 1 + self.radius
        elif self.x > WIDTH - 1 + self.radius:
            self.x = -self.radius
        if self.y < -self.radius:
            self.y = HEIGHT - 1 + self.radius
        elif self.y > HEIGHT - 1 + self.radius:
            self.y = -self.radius

    def intensity_at(self, x: int, y: int) -> float:
        """Return 0-1 intensity at grid position based on distance from center."""
        dx = x - self.x
        dy = y - self.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist >= self.radius:
            return 0.0
        # Smooth radial falloff (cosine-based for soft edges)
        t = dist / self.radius
        return 0.5 * (1.0 + math.cos(t * math.pi))


class Aurora(Pattern):
    name = "Aurora"

    def __init__(self):
        super().__init__()
        # Spawn several blobs
        self.blobs = [Blob() for _ in range(6)]

    def update(self, leds: list, frame: int) -> None:
        # Shared hue that slowly cycles through the spectrum
        hue = int(frame * 0.15) % 256
        sat = 210

        # Advance all blobs
        for blob in self.blobs:
            blob.advance()

        # Render
        for y in range(HEIGHT):
            for x in range(WIDTH):
                idx = xy_to_index(x, y)
                r_total, g_total, b_total = 0.0, 0.0, 0.0

                for blob in self.blobs:
                    intensity = blob.intensity_at(x, y)
                    if intensity > 0.01:
                        brightness = int(blob.max_brightness * intensity)
                        r, g, b = hsv_to_rgb(hue, sat, brightness)
                        r_total += r
                        g_total += g
                        b_total += b

                leds[idx] = (
                    min(255, int(r_total)),
                    min(255, int(g_total)),
                    min(255, int(b_total)),
                )
