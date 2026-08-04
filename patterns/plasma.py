"""
Plasma - upward-drifting purple/pink blobs with feathered edges and sinusoidal wobble.

Discrete blobs drift upward (negative x on physical panel) while oscillating
side-to-side on a sine wave. Smooth quadratic falloff gives soft-edged glows.
"""

import math
import random
from patterns.base import Pattern, WIDTH, HEIGHT, NUM_LEDS, xy_to_index, hsv_to_rgb


NUM_BLOBS = 4
MIN_DISTANCE = 3.0


class Blob:
    """A single drifting plasma blob."""

    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.start_y = 0.0
        self.vx = 0.0
        self.wobble_amp = 0.0
        self.wobble_freq = 0.0
        self.wobble_phase = 0.0
        self.radius = 0.0
        self.age = 0
        self.zone = 0
        self.zone_start = 0.0
        self.zone_end = 0.0


def reset_blob(b: Blob, from_bottom: bool = False):
    # Pick startY randomly within the blob's assigned zone
    b.start_y = random.uniform(b.zone_start, b.zone_end)
    b.y = b.start_y
    if from_bottom:
        b.x = (WIDTH - 1) + b.radius + 1.0 + random.uniform(0, 1.0)
    else:
        b.x = random.uniform(0, WIDTH - 1)
    b.vx = -(0.03 + random.uniform(0, 0.02))  # upward on physical panel
    b.wobble_amp = 1.2 + random.uniform(0, 0.8)
    b.wobble_freq = 0.020 + random.uniform(0, 0.015)
    b.wobble_phase = random.uniform(0, 2 * math.pi)
    b.radius = 2.5 + random.uniform(0, 0.5)
    b.age = 0


class Plasma(Pattern):
    name = "Plasma"

    def __init__(self):
        super().__init__()
        self.blobs = [Blob() for _ in range(NUM_BLOBS)]
        zone_height = HEIGHT / NUM_BLOBS
        for i, b in enumerate(self.blobs):
            b.zone = i
            b.zone_start = i * zone_height
            b.zone_end = (i + 1) * zone_height - 1.0
            reset_blob(b, False)
            # Random x across entire width (no correlation with zone)
            b.x = random.uniform(0, WIDTH - 1)

    def update(self, leds: list, frame: int) -> None:
        # Hue cycles in purple/pink/magenta range (200-240)
        hue = 200 + int((math.sin(frame / 6.0) * 0.5 + 0.5) * 40)
        sat = 200

        # Advance blobs
        for b in self.blobs:
            b.age += 1
            b.x += b.vx
            b.y = b.start_y + b.wobble_amp * math.sin(b.wobble_freq * b.age + b.wobble_phase)

            # Clamp y
            if b.y < 0:
                b.y = 0
            elif b.y > HEIGHT - 1:
                b.y = HEIGHT - 1

            # Respawn when off the top
            if b.x < -b.radius:
                too_close_to_spawn = any(
                    other.x > WIDTH - 2.0
                    for other in self.blobs
                    if other is not b
                )
                if too_close_to_spawn:
                    b.x = -b.radius
                else:
                    reset_blob(b, True)

        # Clamp wobble to zone bounds (keep blobs in their lane)
        for b in self.blobs:
            if b.start_y < b.zone_start:
                b.start_y = b.zone_start
            if b.start_y > b.zone_end:
                b.start_y = b.zone_end

        # Render
        for py in range(HEIGHT):
            for px in range(WIDTH):
                idx = xy_to_index(px, py)
                total_intensity = 0.0

                for b in self.blobs:
                    dx = px - b.x
                    dy = py - b.y
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist >= b.radius:
                        continue
                    t = dist / b.radius
                    intensity = (1.0 - t * t)
                    intensity = intensity * intensity
                    total_intensity += intensity

                if total_intensity > 0.0:
                    total_intensity = min(1.0, total_intensity)
                    brightness = int(total_intensity * 240.0)
                    if brightness < 30:
                        brightness = 0
                    if brightness > 0:
                        leds[idx] = hsv_to_rgb(hue, sat, brightness)
                    else:
                        leds[idx] = (0, 0, 0)
                else:
                    leds[idx] = (0, 0, 0)
