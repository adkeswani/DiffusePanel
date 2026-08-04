"""
Falling Leaves - bright green and yellow-green leaves drift down in small arcs.

Leaves spawn near the top and float downward with gentle sinusoidal sway,
like autumn leaves caught in a light breeze.
"""

import math
import random
from patterns.base import Pattern, WIDTH, HEIGHT, NUM_LEDS, xy_to_index, hsv_to_rgb


class Leaf:
    """A single leaf drifting downward in an arc."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Spawn at the top with random parameters."""
        self.x = random.uniform(0, WIDTH - 1)
        self.y = random.uniform(-3.0, -0.5)
        # Fall speed (pixels per frame)
        self.fall_speed = random.uniform(0.02, 0.05)
        # Horizontal sway
        self.sway_amplitude = random.uniform(1.0, 2.5)
        self.sway_frequency = random.uniform(0.02, 0.05)
        self.sway_phase = random.uniform(0, 2 * math.pi)
        # Size (radius of glow)
        self.size = random.uniform(1.0, 1.8)
        # Brightness
        self.brightness = random.randint(200, 255)
        # Hue: green (96) to yellow-green (64ish in FastLED HSV)
        # In our HSV: green ~96, yellow-green ~80, yellow ~64
        self.hue = random.randint(72, 100)
        # Saturation: mostly saturated with some variation
        self.saturation = random.randint(200, 255)
        # Age tracker for sway
        self.age = 0.0

    @property
    def alive(self) -> bool:
        return self.y < HEIGHT + 2

    def advance(self):
        self.age += 1.0
        self.y += self.fall_speed
        # Sinusoidal horizontal drift
        self.x += math.sin(self.age * self.sway_frequency + self.sway_phase) * 0.03 * self.sway_amplitude

    def intensity_at(self, px: int, py: int) -> float:
        """Return 0-1 glow intensity at a grid cell."""
        dx = px - self.x
        dy = py - self.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > self.size:
            return 0.0
        # Smooth falloff
        return (1.0 - (dist / self.size)) ** 1.5


class FallingLeaves(Pattern):
    name = "Falling Leaves"

    def __init__(self):
        super().__init__()
        self.leaves: list[Leaf] = []
        self.spawn_cooldown = 0
        self.max_leaves = 14

    def update(self, leds: list, frame: int) -> None:
        # Spawn new leaves periodically
        self.spawn_cooldown -= 1
        if self.spawn_cooldown <= 0 and len(self.leaves) < self.max_leaves:
            self.leaves.append(Leaf())
            self.spawn_cooldown = random.randint(12, 35)

        # Advance all leaves
        for leaf in self.leaves:
            leaf.advance()

        # Remove dead leaves and respawn
        self.leaves = [l for l in self.leaves if l.alive]

        # Dim background - very dark green-black
        for i in range(NUM_LEDS):
            leds[i] = (0, 2, 0)

        # Draw leaves
        for y in range(HEIGHT):
            for x in range(WIDTH):
                idx = xy_to_index(x, y)
                r_total, g_total, b_total = leds[idx]

                for leaf in self.leaves:
                    intensity = leaf.intensity_at(x, y)
                    if intensity > 0:
                        r, g, b = hsv_to_rgb(leaf.hue, leaf.saturation, int(leaf.brightness * intensity))
                        r_total = min(255, r_total + r)
                        g_total = min(255, g_total + g)
                        b_total = min(255, b_total + b)

                leds[idx] = (r_total, g_total, b_total)
