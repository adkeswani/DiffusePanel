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

    def reset(self, start_from_bottom=False):
        # Position (float for smooth movement)
        self.x = random.uniform(0, WIDTH - 1)
        if start_from_bottom:
            # Spawn just below the visible area
            self.y = HEIGHT - 1 + random.uniform(0, 2.0)
        else:
            self.y = random.uniform(0, HEIGHT - 1)
        # Upward speed
        self.vy = -random.uniform(0.015, 0.045)  # negative = upward
        # Sinusoidal wobble parameters for curving horizontal motion
        self.wobble_amp = random.uniform(0.008, 0.025)  # gentle horizontal sway
        self.wobble_freq = random.uniform(0.02, 0.05)  # how fast it oscillates
        self.wobble_phase = random.uniform(0, 2 * math.pi)  # offset so blobs differ
        self.age = 0  # frame counter for wobble
        # Radius (how far the glow extends)
        self.radius = random.uniform(2.0, 4.5)
        # Brightness
        self.max_brightness = random.randint(150, 220)

    def advance(self):
        """Move the blob upward with gentle curving; respawn from bottom when it leaves the top."""
        self.age += 1
        # Horizontal movement follows a sine curve for organic drift
        self.x += self.wobble_amp * math.sin(self.wobble_freq * self.age + self.wobble_phase)
        self.y += self.vy

        # Wrap horizontal gently
        if self.x < -self.radius:
            self.x = WIDTH - 1 + self.radius
        elif self.x > WIDTH - 1 + self.radius:
            self.x = -self.radius

        # If blob has fully left the top, respawn from bottom
        if self.y < -self.radius:
            self.reset(start_from_bottom=True)
            self._push_apart_flag = True  # signal Aurora to spread it out

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
    MIN_DISTANCE = 4.0  # minimum distance between blob centers

    def __init__(self):
        super().__init__()
        # Spawn several blobs
        self.blobs = [Blob() for _ in range(6)]

    def _push_apart(self, blob: Blob):
        """Nudge a blob's x position so it doesn't spawn too close to others."""
        for _ in range(10):  # up to 10 attempts
            too_close = False
            for other in self.blobs:
                if other is blob:
                    continue
                dx = blob.x - other.x
                dy = blob.y - other.y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < self.MIN_DISTANCE:
                    too_close = True
                    break
            if not too_close:
                break
            # Try a new random x position
            blob.x = random.uniform(0, WIDTH - 1)

    def update(self, leds: list, frame: int) -> None:
        # Shared hue that slowly cycles through the spectrum
        hue = int(frame * 0.15) % 256
        sat = 210

        # Advance all blobs
        for blob in self.blobs:
            blob.advance()
            # If blob just respawned, spread it away from others
            if getattr(blob, '_push_apart_flag', False):
                self._push_apart(blob)
                blob._push_apart_flag = False

        # Gently repel blobs that drift too close to each other
        for i, a in enumerate(self.blobs):
            for b in self.blobs[i + 1:]:
                dx = a.x - b.x
                dy = a.y - b.y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < self.MIN_DISTANCE and dist > 0.01:
                    # Push them apart slightly along x
                    push = 0.05 * (self.MIN_DISTANCE - dist) / dist
                    a.x += dx * push
                    b.x -= dx * push

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
