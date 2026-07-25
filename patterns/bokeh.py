"""
Bokeh pattern - soft glowing orbs that fade in and out independently.

Each LED is an independent "orb" that:
  - Sleeps for a random duration (off/dim)
  - Fades in to a random warm/cool color
  - Drifts towards white (bloom) or fades towards black (dim)
  - Fades out and sleeps again

The randomness of timing creates a dreamy, unfocused quality -
like out-of-focus city lights at night.
"""

import random
import math
from patterns.base import Pattern, WIDTH, HEIGHT, NUM_LEDS, xy_to_index, hsv_to_rgb


# Palette: warm amber, soft pink, cool blue, soft green
PALETTE = [
    (28, 220),    # Warm amber/gold  (hue, saturation)
    (235, 170),   # Soft pink/magenta
    (155, 195),   # Cool blue
    (85, 200),    # Soft green
]

# How many frames to spend on each palette color, and crossfade duration
PALETTE_HOLD_FRAMES = 600   # ~10 seconds at 60fps
PALETTE_FADE_FRAMES = 180   # ~3 seconds crossfade


def get_palette_color(frame: int) -> tuple[int, int]:
    """Return the current (hue, saturation) based on frame, slowly cycling the palette."""
    cycle_length = PALETTE_HOLD_FRAMES + PALETTE_FADE_FRAMES
    total_cycle = cycle_length * len(PALETTE)
    pos = frame % total_cycle

    idx = pos // cycle_length
    frame_in_slot = pos % cycle_length

    current_hue, current_sat = PALETTE[idx]
    next_hue, next_sat = PALETTE[(idx + 1) % len(PALETTE)]

    if frame_in_slot < PALETTE_HOLD_FRAMES:
        return (current_hue, current_sat)
    else:
        # Crossfade to next color
        t = (frame_in_slot - PALETTE_HOLD_FRAMES) / PALETTE_FADE_FRAMES
        t = t * t * (3.0 - 2.0 * t)  # smoothstep
        hue = int(current_hue + (next_hue - current_hue) * t)
        sat = int(current_sat + (next_sat - current_sat) * t)
        return (hue, sat)


class Orb:
    """A single LED's bokeh lifecycle."""

    def __init__(self):
        self.hue = 0
        self.sat = 0
        self.reset()

    def reset(self):
        """Start a new lifecycle with random parameters."""
        # How long to stay dark before fading in
        self.sleep_frames = random.randint(30, 200)
        self.age = 0

        self.max_brightness = random.randint(140, 255)

        # Fade durations (in frames)
        self.fade_in_duration = random.randint(40, 120)
        self.hold_duration = random.randint(20, 80)
        self.fade_out_duration = random.randint(50, 150)

        # Whether this orb blooms toward white at peak
        self.blooms = random.random() < 0.4
        # How much saturation drops at peak (bloom effect)
        self.bloom_amount = random.randint(80, 160) if self.blooms else 0

        # Current state
        self.state = "sleeping"  # sleeping -> fading_in -> holding -> fading_out -> sleeping
        self.frame_in_state = 0

    def set_color(self, hue: int, sat: int):
        """Set the shared palette color for this orb."""
        self.hue = hue
        self.sat = sat

    def update(self) -> tuple[int, int, int]:
        """Advance one frame, return (r, g, b)."""
        self.age += 1

        if self.state == "sleeping":
            self.frame_in_state += 1
            if self.frame_in_state >= self.sleep_frames:
                self.state = "fading_in"
                self.frame_in_state = 0
            return (0, 0, 0)

        elif self.state == "fading_in":
            self.frame_in_state += 1
            t = self.frame_in_state / self.fade_in_duration  # 0 -> 1
            t = self._ease_in_out(t)

            brightness = int(self.max_brightness * t)
            # Saturation stays full during fade in
            sat = self.sat
            color = hsv_to_rgb(self.hue, sat, brightness)

            if self.frame_in_state >= self.fade_in_duration:
                self.state = "holding"
                self.frame_in_state = 0
            return color

        elif self.state == "holding":
            self.frame_in_state += 1
            t = self.frame_in_state / self.hold_duration  # 0 -> 1

            # During hold, bloom towards white if this orb blooms
            sat = self.sat - int(self.bloom_amount * self._ease_in_out(t))
            sat = max(0, sat)
            color = hsv_to_rgb(self.hue, sat, self.max_brightness)

            if self.frame_in_state >= self.hold_duration:
                self.state = "fading_out"
                self.frame_in_state = 0
            return color

        elif self.state == "fading_out":
            self.frame_in_state += 1
            t = 1.0 - (self.frame_in_state / self.fade_out_duration)  # 1 -> 0
            t = self._ease_in_out(max(0, t))

            brightness = int(self.max_brightness * t)
            # Saturation recovers as it fades out
            bloom_remaining = max(0, 1.0 - (self.frame_in_state / self.fade_out_duration))
            sat = self.sat - int(self.bloom_amount * bloom_remaining)
            sat = max(0, sat)
            color = hsv_to_rgb(self.hue, sat, brightness)

            if self.frame_in_state >= self.fade_out_duration:
                self.reset()
            return color

        return (0, 0, 0)

    @staticmethod
    def _ease_in_out(t: float) -> float:
        """Smooth easing function for organic-feeling fades."""
        # Smoothstep
        t = max(0.0, min(1.0, t))
        return t * t * (3.0 - 2.0 * t)


class Bokeh(Pattern):
    name = "Bokeh"

    def __init__(self):
        super().__init__()
        # Each LED gets its own orb with staggered start times
        self.orbs = []
        for i in range(NUM_LEDS):
            orb = Orb()
            # Stagger initial sleep so they don't all start together
            orb.sleep_frames = random.randint(0, 180)
            self.orbs.append(orb)

    def update(self, leds: list, frame: int) -> None:
        # Get the current shared color from the palette
        hue, sat = get_palette_color(frame)

        for i in range(NUM_LEDS):
            self.orbs[i].set_color(hue, sat)
            leds[i] = self.orbs[i].update()
