"""
Ripple - occasional ripples emanate from random points, like raindrops on still water.

Peaceful and contemplative. Ripples expand outward as concentric rings
that fade as they grow.
"""

import math
import random
from patterns.base import Pattern, WIDTH, HEIGHT, NUM_LEDS, xy_to_index, hsv_to_rgb


class RippleSource:
    """A single ripple expanding from a point."""

    def __init__(self, x: float, y: float, hue: int):
        self.x = x
        self.y = y
        self.hue = hue
        self.radius = 0.0
        self.speed = random.uniform(0.08, 0.15)
        self.max_radius = random.uniform(8.0, 14.0)
        self.ring_width = 1.8  # How thick the visible ring is

    @property
    def alive(self) -> bool:
        return self.radius < self.max_radius

    def advance(self):
        self.radius += self.speed

    def intensity_at(self, x: int, y: int) -> float:
        """Return 0-1 intensity at the given grid position."""
        dist = math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)
        # Ring shape: bright near self.radius, fading away from it
        ring_dist = abs(dist - self.radius)
        if ring_dist > self.ring_width:
            return 0.0
        # Intensity within the ring
        ring_intensity = 1.0 - (ring_dist / self.ring_width)
        # Fade out as ripple expands
        age_fade = 1.0 - (self.radius / self.max_radius)
        return ring_intensity * age_fade * age_fade


class Ripple(Pattern):
    name = "Ripple"

    def __init__(self):
        super().__init__()
        self.ripples: list[RippleSource] = []
        self.spawn_cooldown = 0
        # Hue palette for ripples - full spectrum
        self.hue_options = list(range(0, 256, 16))

    def update(self, leds: list, frame: int) -> None:
        # Occasionally spawn a new ripple
        self.spawn_cooldown -= 1
        if self.spawn_cooldown <= 0 and len(self.ripples) < 4:
            x = random.uniform(2, WIDTH - 3)
            y = random.uniform(2, HEIGHT - 3)
            hue = random.choice(self.hue_options)
            self.ripples.append(RippleSource(x, y, hue))
            self.spawn_cooldown = random.randint(40, 100)

        # Clear to dark
        for i in range(NUM_LEDS):
            leds[i] = (0, 0, 0)

        # Draw all active ripples
        for y in range(HEIGHT):
            for x in range(WIDTH):
                idx = xy_to_index(x, y)
                total_intensity = 0.0
                blended_hue = 0.0

                for ripple in self.ripples:
                    intensity = ripple.intensity_at(x, y)
                    if intensity > 0:
                        total_intensity += intensity
                        blended_hue += ripple.hue * intensity

                if total_intensity > 0:
                    hue = int(blended_hue / total_intensity) % 256
                    brightness = min(200, int(total_intensity * 200))
                    sat = 180
                    leds[idx] = hsv_to_rgb(hue, sat, brightness)

        # Advance and cull ripples
        alive = []
        for ripple in self.ripples:
            ripple.advance()
            if ripple.alive:
                alive.append(ripple)
        self.ripples = alive
