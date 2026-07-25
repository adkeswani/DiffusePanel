"""
Moon - a circle of LEDs that wanes from full to crescent to new moon,
then re-emerges with the next color in the cycle.

Uses proper crescent geometry: a shadow circle sweeps across the moon disk
to carve out the classic crescent shape.

Lifecycle per color:
  Full moon → waning crescent → new moon (dark) → change color → waxing crescent → full moon
"""

import math
from patterns.base import Pattern, WIDTH, HEIGHT, NUM_LEDS, xy_to_index, hsv_to_rgb


class Moon(Pattern):
    name = "Moon"

    def __init__(self):
        super().__init__()
        # Moon geometry
        self.cx = (WIDTH - 1) / 2.0
        self.cy = (HEIGHT - 1) / 2.0
        self.radius = 5.5

        # How many frames for one full cycle (full -> new -> full)
        self.cycle_frames = 1400  # ~23 seconds at 60fps for one complete cycle

    def update(self, leds: list, frame: int) -> None:
        # Slow continuous hue cycle (not palette-stepped)
        hue = int(frame * 0.08) % 256
        sat = 200

        # Use a sine wave for perfectly smooth, continuous motion
        # No segments, no transitions, no hitches
        t = (frame % self.cycle_frames) / self.cycle_frames
        # Sine goes from 0 to 1 to 0 smoothly with no discontinuities
        phase = 0.5 * (1.0 + math.cos(t * 2 * math.pi))
        # phase=1 at t=0 (full), phase=0 at t=0.5 (new), back to 1 at t=1

        # Alternate shadow direction each half-cycle
        # First half (waning): shadow comes from right
        # Second half (waxing): shadow comes from left
        if t < 0.5:
            shadow_direction = 1.0
        else:
            shadow_direction = -1.0

        # Crescent geometry using two overlapping circles:
        # The moon disk is centered at (cx, cy) with radius R.
        # A shadow circle (LARGER than the moon) sweeps across it.
        # Making the shadow larger ensures it fully covers the moon at phase=0
        # and prevents edge artifacts.
        shadow_radius = self.radius + 2.5  # Larger than moon to fully cover it
        # Shadow center x-offset from moon center:
        #   phase=1 (full): shadow is far away (no overlap with moon)
        #   phase=0 (new): shadow centered on moon (fully covers it)
        # Offset needed so shadow edge just clears moon at phase=1:
        #   offset = shadow_radius + moon_radius (shadow completely off to one side)
        max_offset = shadow_radius + self.radius
        shadow_offset_x = phase * max_offset * shadow_direction

        for y in range(HEIGHT):
            for x in range(WIDTH):
                idx = xy_to_index(x, y)

                dx = x - self.cx
                dy = y - self.cy
                dist_from_center = math.sqrt(dx * dx + dy * dy)

                if dist_from_center <= self.radius + 0.5:
                    # Inside or near the moon disk

                    # Soft circle edge
                    circle_edge = max(0.0, min(1.0, (self.radius + 0.5 - dist_from_center) * 2.0))

                    # Distance from the shadow circle center
                    shadow_cx = self.cx + shadow_offset_x
                    sdx = x - shadow_cx
                    sdy = y - self.cy
                    dist_from_shadow = math.sqrt(sdx * sdx + sdy * sdy)

                    # Pixel is lit if it's inside the moon disk but OUTSIDE the shadow
                    # Use smooth transition at shadow boundary
                    shadow_fade_width = 1.5  # pixels of soft edge on the shadow
                    if dist_from_shadow >= shadow_radius + shadow_fade_width:
                        # Fully outside shadow = fully lit
                        lit = 1.0
                    elif dist_from_shadow >= shadow_radius - shadow_fade_width:
                        # In the soft boundary zone
                        t = (dist_from_shadow - (shadow_radius - shadow_fade_width)) / (shadow_fade_width * 2)
                        lit = t * t * (3.0 - 2.0 * t)  # smoothstep
                    else:
                        # Inside shadow = dark
                        lit = 0.0

                    brightness = int(200 * lit * circle_edge)

                    if brightness > 1:
                        leds[idx] = hsv_to_rgb(hue, sat, brightness)
                    else:
                        leds[idx] = (0, 0, 0)
                else:
                    leds[idx] = (0, 0, 0)
