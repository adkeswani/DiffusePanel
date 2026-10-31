"""Fall/autumn-themed patterns for the 16x16 simulator.

A self-contained sibling to halloween.py: same house style (chunky, high
contrast shapes; small helper functions mirroring what's easy to write in
Arduino/FastLED) but with its own seasonal color palette so it can be ported
to its own standalone .ino sketch later.

The five "fall colors" used throughout this file -- pale green, yellow,
orange, red, brown -- are always cycled in that order, which reads as a
leaf's natural decay: fresh green, turning yellow, then orange, then red,
then brown, before looping back to green.
"""

import math
import random

from patterns.base import HEIGHT, NUM_LEDS, WIDTH, Pattern, hsv_to_rgb, xy_to_index

BLACK = (0, 0, 0)

# Concrete RGB "fall colors", used wherever a pattern needs a fixed set of
# discrete colors to pick from (as opposed to a smoothly crossfading hue).
PALE_GREEN = (140, 205, 90)
YELLOW = (255, 195, 25)
ORANGE = (255, 110, 10)
RED = (210, 35, 10)
BROWN = (120, 65, 20)

# Same five colors, ordered for a smooth seasonal gradient (green -> yellow
# -> orange -> red -> brown), looping back to green.
FALL_COLOR_STOPS = (PALE_GREEN, YELLOW, ORANGE, RED, BROWN)

# HSV equivalents (hue/sat 0-255, plus a brightness cap 0-255) of the same
# five colors, for patterns that want to crossfade smoothly through hue/sat
# space rather than blending concrete RGB stops. The cap keeps muted colors
# (especially brown) from being blown out to a bright orange at full value.
_PALE_GREEN_HSV = (90, 130, 215)
_YELLOW_HSV = (42, 235, 255)
_ORANGE_HSV = (20, 255, 255)
_RED_HSV = (0, 230, 230)
_BROWN_HSV = (14, 190, 125)

FALL_PALETTE_HSV = (_PALE_GREEN_HSV, _YELLOW_HSV, _ORANGE_HSV, _RED_HSV, _BROWN_HSV)

# How long to hold each color, and how long to crossfade to the next one.
FALL_PALETTE_HOLD_FRAMES = 420   # ~7s at 60fps
FALL_PALETTE_FADE_FRAMES = 180   # ~3s crossfade


def get_fall_palette_color(frame: int) -> tuple[int, int, int]:
    """Return the current (hue, sat, cap) based on frame, slowly and
    smoothly cycling through FALL_PALETTE_HSV in order, looping forever."""
    stops = FALL_PALETTE_HSV
    cycle_length = FALL_PALETTE_HOLD_FRAMES + FALL_PALETTE_FADE_FRAMES
    total_cycle = cycle_length * len(stops)
    pos = frame % total_cycle

    idx = pos // cycle_length
    frame_in_slot = pos % cycle_length

    cur_hue, cur_sat, cur_cap = stops[idx]
    nxt_hue, nxt_sat, nxt_cap = stops[(idx + 1) % len(stops)]

    if frame_in_slot < FALL_PALETTE_HOLD_FRAMES:
        return (cur_hue, cur_sat, cur_cap)

    t = (frame_in_slot - FALL_PALETTE_HOLD_FRAMES) / FALL_PALETTE_FADE_FRAMES
    t = t * t * (3.0 - 2.0 * t)  # smoothstep
    hue = int(cur_hue + (nxt_hue - cur_hue) * t) % 256
    sat = int(cur_sat + (nxt_sat - cur_sat) * t)
    cap = int(cur_cap + (nxt_cap - cur_cap) * t)
    return (hue, sat, cap)


def _clear(leds: list, color: tuple[int, int, int] = BLACK) -> None:
    for i in range(NUM_LEDS):
        leds[i] = color


def _set(leds: list, x: int, y: int, color: tuple[int, int, int]) -> None:
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        leds[xy_to_index(x, y)] = color


def _scale(color: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    amount = max(0.0, min(1.0, amount))
    return tuple(int(channel * amount) for channel in color)


def _blend(
    first: tuple[int, int, int], second: tuple[int, int, int], amount: float
) -> tuple[int, int, int]:
    amount = max(0.0, min(1.0, amount))
    return tuple(int(a + (b - a) * amount) for a, b in zip(first, second))


class _FallOrb:
    """A single LED's bokeh lifecycle, using the shared fall palette."""

    def __init__(self):
        self.hue = 0
        self.sat = 0
        self.cap = 255
        self.reset()

    def reset(self):
        """Start a new lifecycle with random parameters."""
        self.sleep_frames = random.randint(30, 200)
        self.age = 0

        # Fraction of the current palette color's brightness cap this orb
        # peaks at, so not every orb is equally bright.
        self.brightness_frac = random.uniform(0.55, 1.0)

        self.fade_in_duration = random.randint(40, 120)
        self.hold_duration = random.randint(20, 80)
        self.fade_out_duration = random.randint(50, 150)

        self.blooms = random.random() < 0.35
        self.bloom_amount = random.randint(60, 120) if self.blooms else 0

        self.state = "sleeping"  # sleeping -> fading_in -> holding -> fading_out -> sleeping
        self.frame_in_state = 0

    def set_color(self, hue: int, sat: int, cap: int):
        """Set the shared palette color for this orb."""
        self.hue = hue
        self.sat = sat
        self.cap = cap

    @property
    def _peak_brightness(self) -> int:
        return int(self.cap * self.brightness_frac)

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
            t = self.frame_in_state / self.fade_in_duration
            t = self._ease_in_out(t)

            brightness = int(self._peak_brightness * t)
            color = hsv_to_rgb(self.hue, self.sat, brightness)

            if self.frame_in_state >= self.fade_in_duration:
                self.state = "holding"
                self.frame_in_state = 0
            return color

        elif self.state == "holding":
            self.frame_in_state += 1
            t = self.frame_in_state / self.hold_duration

            sat = self.sat - int(self.bloom_amount * self._ease_in_out(t))
            sat = max(0, sat)
            color = hsv_to_rgb(self.hue, sat, self._peak_brightness)

            if self.frame_in_state >= self.hold_duration:
                self.state = "fading_out"
                self.frame_in_state = 0
            return color

        elif self.state == "fading_out":
            self.frame_in_state += 1
            t = 1.0 - (self.frame_in_state / self.fade_out_duration)
            t = self._ease_in_out(max(0, t))

            brightness = int(self._peak_brightness * t)
            bloom_remaining = max(0.0, 1.0 - (self.frame_in_state / self.fade_out_duration))
            sat = self.sat - int(self.bloom_amount * bloom_remaining)
            sat = max(0, sat)
            color = hsv_to_rgb(self.hue, sat, brightness)

            if self.frame_in_state >= self.fade_out_duration:
                self.reset()
            return color

        return (0, 0, 0)

    @staticmethod
    def _ease_in_out(t: float) -> float:
        t = max(0.0, min(1.0, t))
        return t * t * (3.0 - 2.0 * t)


class FallBokeh(Pattern):
    """Bokeh pattern (soft glowing orbs), recolored with fall colors:
    pale green, yellow, orange, red, and brown, smoothly crossfading
    through that seasonal order."""

    name = "Fall Bokeh"

    def __init__(self):
        super().__init__()
        self.orbs = []
        for i in range(NUM_LEDS):
            orb = _FallOrb()
            # Stagger initial sleep so they don't all start together.
            orb.sleep_frames = random.randint(0, 180)
            self.orbs.append(orb)

    def update(self, leds: list, frame: int) -> None:
        hue, sat, cap = get_fall_palette_color(frame)
        for i in range(NUM_LEDS):
            self.orbs[i].set_color(hue, sat, cap)
            leds[i] = self.orbs[i].update()


class FallRingFade(Pattern):
    """The thick-ring-with-rotating-wave pattern, recolored so the ring's
    base color smoothly cycles through the fall color spectrum (pale
    green -> yellow -> orange -> red -> brown -> loop) instead of a full
    rainbow hue sweep."""

    name = "Fall Ring Fade"

    def __init__(self):
        super().__init__()
        self.cx = (WIDTH - 1) / 2.0
        self.cy = (HEIGHT - 1) / 2.0
        self.ring_radius = 5.5
        self.ring_thickness = 2.5
        self.speed = 0.02
        self.wave_width = math.pi * 0.8

    def update(self, leds: list, frame: int) -> None:
        hue, sat, cap = get_fall_palette_color(frame)
        wave_angle = frame * self.speed

        for y in range(HEIGHT):
            for x in range(WIDTH):
                idx = xy_to_index(x, y)

                dx = x - self.cx
                dy = y - self.cy
                dist = math.sqrt(dx * dx + dy * dy)

                ring_dist = abs(dist - self.ring_radius)

                if ring_dist < self.ring_thickness:
                    ring_fade = 1.0 - (ring_dist / self.ring_thickness)
                    ring_fade = ring_fade * ring_fade

                    pixel_angle = math.atan2(dy, dx)
                    angle_diff = (pixel_angle - wave_angle) % (2 * math.pi)
                    if angle_diff > math.pi:
                        angle_diff = 2 * math.pi - angle_diff

                    if angle_diff < self.wave_width:
                        t = 1.0 - (angle_diff / self.wave_width)
                        t = t * t * (3.0 - 2.0 * t)

                        brightness = int((60 + t * 180) * ring_fade)
                        pixel_hue = (hue + int(t * 10)) % 256
                        pixel_sat = max(0, sat - int(t * 20))
                    else:
                        brightness = int(40 * ring_fade)
                        pixel_hue = hue
                        pixel_sat = sat

                    # Clamp to this color's brightness cap so brown stays
                    # muted instead of blowing out to a bright orange.
                    brightness = min(brightness, cap)
                    leds[idx] = hsv_to_rgb(pixel_hue, pixel_sat, brightness)
                else:
                    leds[idx] = (0, 0, 0)


class _TumblingLeaf:
    """A single leaf falling straight down as one pixel, with brightness
    oscillating to mimic it tumbling end over end and catching the light."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.x = float(random.randint(0, WIDTH - 1))
        self.y = random.uniform(-4.0, -0.5)
        self.fall_speed = random.uniform(0.03, 0.07)
        self.color = random.choice(FALL_COLOR_STOPS)

        # Tumbling flicker: brightness oscillates between a dim and bright
        # extreme as the leaf "spins".
        self.tumble_freq = random.uniform(0.15, 0.35)
        self.tumble_phase = random.uniform(0, 2 * math.pi)
        self.min_brightness = random.uniform(0.25, 0.45)

        # Occasional small sideways drift as it tumbles.
        self.drift_dir = random.choice((-1, 0, 1))
        self.next_drift_frame = random.randint(20, 60)

    @property
    def alive(self) -> bool:
        return self.y < HEIGHT + 1

    def advance(self, frame: int):
        self.y += self.fall_speed
        self.tumble_phase += self.tumble_freq
        if frame >= self.next_drift_frame:
            self.x = max(0.0, min(float(WIDTH - 1), self.x + self.drift_dir))
            self.drift_dir = random.choice((-1, 0, 1))
            self.next_drift_frame = frame + random.randint(20, 60)

    def brightness(self) -> float:
        t = (math.sin(self.tumble_phase) + 1.0) / 2.0  # 0..1
        return self.min_brightness + (1.0 - self.min_brightness) * t


class TumblingLeaves(Pattern):
    """Single pixels fall straight down the panel, each a fall color, with
    alternating brightness as they go to mimic a leaf tumbling end over
    end in the wind."""

    name = "Tumbling Leaves"

    def __init__(self):
        super().__init__()
        self.leaves: list[_TumblingLeaf] = []
        self.spawn_cooldown = 0
        self.max_leaves = 14

    def update(self, leds: list, frame: int) -> None:
        self.spawn_cooldown -= 1
        if self.spawn_cooldown <= 0 and len(self.leaves) < self.max_leaves:
            self.leaves.append(_TumblingLeaf())
            self.spawn_cooldown = random.randint(8, 20)

        for leaf in self.leaves:
            leaf.advance(frame)
        self.leaves = [leaf for leaf in self.leaves if leaf.alive]

        _clear(leds)
        for leaf in self.leaves:
            x = int(round(leaf.x))
            y = int(round(leaf.y))
            if 0 <= y < HEIGHT:
                _set(leds, x, y, _scale(leaf.color, leaf.brightness()))


class MapleLeaf(Pattern):
    """A single maple-leaf silhouette that slowly shifts color through the
    fall spectrum (green -> yellow -> orange -> red -> brown), then
    crumbles apart pixel by pixel as it darkens, before a fresh leaf grows
    back in and the cycle repeats.

    The silhouette is a simple 3-lobed outline (one point up, two lower
    side points) computed from a polar radius function rather than a hand
    drawn bitmap, so it stays smooth/anti-aliased and is easy to shrink
    for the crumbling effect.
    """

    name = "Maple Leaf"

    _CX, _CY = 7.5, 6.5
    _R0 = 4.3    # base radius of the lobed outline
    _R1 = 2.1    # lobe amplitude (how pointy the 3 lobes are)
    _STEM_LEN = 3

    _CYCLE_FRAMES = 1800        # ~30s at 60fps for one full life of a leaf
    _CRUMBLE_START = 0.78       # fraction of the cycle where crumbling begins

    def __init__(self):
        super().__init__()
        self._build_shape()
        self._last_cycle_index = -1
        self.crumble_thresholds = [0.0] * len(self.pixels)

    def _build_shape(self):
        """Precompute the leaf's pixel coordinates and edge-antialiasing
        coverage (0-1), plus a short stem below the lowest point."""
        self.pixels: list[tuple[int, int, float]] = []
        for y in range(HEIGHT):
            for x in range(WIDTH):
                dx = x - self._CX
                dy = self._CY - y  # flip so "up" is positive, matching theta=90 as the top point
                theta = math.atan2(dy, dx)
                dist = math.hypot(dx, dy)
                outline = self._R0 + self._R1 * math.cos(3 * (theta - math.pi / 2))
                coverage = outline - dist
                if coverage > 0:
                    self.pixels.append((x, y, min(1.0, coverage)))

        # Stem hangs straight down from the lowest (pinched-in) point of
        # the outline.
        stem_x = int(round(self._CX))
        base_y = int(round(self._CY + (self._R0 - self._R1)))
        for i in range(1, self._STEM_LEN + 1):
            self.pixels.append((stem_x, base_y + i, 1.0))

    def _color_at(self, t: float) -> tuple[int, int, int]:
        """Blend through FALL_COLOR_STOPS as t goes 0 -> 1 across the
        non-crumbling part of the cycle."""
        stops = FALL_COLOR_STOPS
        span = min(t, self._CRUMBLE_START) / self._CRUMBLE_START
        scaled = span * (len(stops) - 1)
        idx = min(len(stops) - 2, int(scaled))
        frac = scaled - idx
        return _blend(stops[idx], stops[idx + 1], frac)

    def update(self, leds: list, frame: int) -> None:
        cycle_index = frame // self._CYCLE_FRAMES
        if cycle_index != self._last_cycle_index:
            self._last_cycle_index = cycle_index
            self.crumble_thresholds = [
                random.uniform(self._CRUMBLE_START, 1.0) for _ in self.pixels
            ]

        t = (frame % self._CYCLE_FRAMES) / self._CYCLE_FRAMES
        color = self._color_at(t)

        if t > self._CRUMBLE_START:
            darken_t = (t - self._CRUMBLE_START) / (1.0 - self._CRUMBLE_START)
            brightness_scale = max(0.0, 1.0 - darken_t)
        else:
            brightness_scale = 1.0
        color = _scale(color, brightness_scale)

        _clear(leds)
        for (x, y, coverage), threshold in zip(self.pixels, self.crumble_thresholds):
            if t >= threshold:
                continue  # this pixel has crumbled away for the rest of this leaf's life
            _set(leds, x, y, _scale(color, coverage))
