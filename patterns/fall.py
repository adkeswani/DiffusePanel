"""Fall/autumn-themed patterns for the 16x16 simulator.

A self-contained sibling to halloween.py: same house style (chunky, high
contrast shapes; small helper functions mirroring what's easy to write in
Arduino/FastLED) but with its own seasonal color palette so it can be ported
to its own standalone .ino sketch later.

The four "fall colors" used throughout this file -- yellow, orange, red,
brown -- are always cycled in that order, which reads as a leaf's natural
decay: golden yellow, turning orange, then red, then brown, before looping
back to yellow.
"""

import math
import random

from patterns.base import HEIGHT, NUM_LEDS, WIDTH, Pattern, hsv_to_rgb, xy_to_index

BLACK = (0, 0, 0)

# Concrete RGB "fall colors", used wherever a pattern needs a fixed set of
# discrete colors to pick from (as opposed to a smoothly crossfading hue).
YELLOW = (255, 195, 25)
ORANGE = (255, 110, 10)
RED = (210, 35, 10)
BROWN = (120, 65, 20)

# Same four colors, ordered for a smooth seasonal gradient (yellow -> orange
# -> red -> brown), looping back to yellow.
FALL_COLOR_STOPS = (YELLOW, ORANGE, RED, BROWN)

# HSV equivalents (hue/sat 0-255, plus a brightness cap 0-255) of the same
# four colors, for patterns that want to crossfade smoothly through hue/sat
# space rather than blending concrete RGB stops. The cap keeps muted colors
# (especially brown) from being blown out to a bright orange at full value.
_YELLOW_HSV = (32, 235, 255)
_ORANGE_HSV = (20, 255, 255)
_RED_HSV = (0, 230, 230)
_BROWN_HSV = (14, 190, 125)

FALL_PALETTE_HSV = (_YELLOW_HSV, _ORANGE_HSV, _RED_HSV, _BROWN_HSV)

# The same four stops, but in "bounce"/ping-pong order: yellow -> orange ->
# red -> brown -> red -> orange -> (loops back to yellow), instead of
# snapping straight from brown back to yellow.
FALL_PALETTE_HSV_BOUNCE = FALL_PALETTE_HSV + FALL_PALETTE_HSV[-2:0:-1]

# How long to hold each color, and how long to crossfade to the next one.
FALL_PALETTE_HOLD_FRAMES = 420   # ~7s at 60fps
FALL_PALETTE_FADE_FRAMES = 180   # ~3s crossfade
FALL_PALETTE_STEP_FRAMES = FALL_PALETTE_HOLD_FRAMES + FALL_PALETTE_FADE_FRAMES


def get_fall_palette_color(frame: int) -> tuple[int, int, int]:
    """Return the current (hue, sat, cap) based on frame, slowly and
    smoothly bouncing back and forth through FALL_PALETTE_HSV_BOUNCE
    (yellow -> orange -> red -> brown -> red -> orange -> loop)."""
    stops = FALL_PALETTE_HSV_BOUNCE
    total_cycle = FALL_PALETTE_STEP_FRAMES * len(stops)
    pos = frame % total_cycle

    idx = pos // FALL_PALETTE_STEP_FRAMES
    frame_in_slot = pos % FALL_PALETTE_STEP_FRAMES

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

        # No white bloom -- keep orbs fully saturated so they stay true
        # autumn colors instead of fading toward white at their peak.
        self.blooms = False
        self.bloom_amount = 0

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


class _FallOrbIndependent(_FallOrb):
    """Like _FallOrb, but each orb independently picks its own random stop
    from the fall palette instead of following one shared, synced color."""

    def reset(self):
        super().reset()
        self.hue, self.sat, self.cap = random.choice(FALL_PALETTE_HSV)


class FallBokehMix(Pattern):
    """Same bokeh mechanic as FallBokeh, but every pixel independently
    picks its own random fall color (yellow/orange/red/brown) instead of
    the whole panel sharing one synced color at a time."""

    name = "Fall Bokeh Mix"

    def __init__(self):
        super().__init__()
        self.orbs = []
        for i in range(NUM_LEDS):
            orb = _FallOrbIndependent()
            orb.sleep_frames = random.randint(0, 180)
            self.orbs.append(orb)

    def update(self, leds: list, frame: int) -> None:
        for i in range(NUM_LEDS):
            leds[i] = self.orbs[i].update()


class FallRingWave(Pattern):
    """A thick ring that's always fully lit, with a brighter wave of color
    chasing around it, recolored so the ring's base color smoothly cycles
    through the fall color spectrum (yellow -> orange -> red -> brown ->
    loop) instead of a full rainbow hue sweep."""

    name = "Fall Ring Wave"

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
        # Sample the same (bouncing) palette one full step ahead so the
        # wave highlight is always a clearly distinct fall color from the
        # base ring (e.g. an orange wave chasing around a yellow ring),
        # rather than just a brighter/less-saturated shade of the same hue.
        wave_hue, wave_sat, wave_cap = get_fall_palette_color(frame + FALL_PALETTE_STEP_FRAMES)
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
                        # Inside the wave: brighter, and a distinctly
                        # different fall color from the base ring.
                        t = 1.0 - (angle_diff / self.wave_width)
                        t = t * t * (3.0 - 2.0 * t)

                        brightness = int((120 + t * 100) * ring_fade)
                        pixel_hue = int(hue + (wave_hue - hue) * t) % 256
                        pixel_sat = int(sat + (wave_sat - sat) * t)
                        pixel_cap = int(cap + (wave_cap - cap) * t)
                    else:
                        # Rest of the ring: always lit with the base color.
                        brightness = int(120 * ring_fade)
                        pixel_hue = hue
                        pixel_sat = sat
                        pixel_cap = cap

                    # Clamp to this color's brightness cap so brown stays
                    # muted instead of blowing out to a bright orange.
                    brightness = min(brightness, pixel_cap)
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
        self.fall_speed = random.uniform(0.012, 0.028)
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


class _CanopyPixel:
    """A single canopy pixel's independent on/off flicker, like a leaf
    catching and losing the light."""

    def __init__(self):
        self.phase = random.uniform(0, 2 * math.pi)
        self.freq = random.uniform(0.02, 0.05)
        self.min_brightness = random.uniform(0.15, 0.35)

    def brightness(self, frame: int) -> float:
        t = (math.sin(frame * self.freq + self.phase) + 1.0) / 2.0  # 0..1
        return self.min_brightness + (1.0 - self.min_brightness) * t


class FallTree(Pattern):
    """A simple tree: a white trunk with white branches that fan out
    widely and fork as they grow upward from partway down the trunk,
    reaching all the way to the top of the display (and getting cut off
    at the top/sides -- that's fine, it just reads as a big tree filling
    the panel).

    The branches themselves stay white (the tree's bare structure); fall-
    colored "leaf" pixels cluster around them instead, each fading on and
    off on its own cycle (like catching and losing the light), while the
    whole tree's leaf color slowly bounces back and forth through the
    fall spectrum together (yellow -> orange -> red -> brown -> back).
    """

    name = "Fall Tree"

    _TRUNK_LEFT = 7
    _TRUNK_RIGHT = 8
    _TRUNK_TOP = 10
    _TRUNK_BOTTOM = 15
    _TRUNK_COLOR = (200, 200, 200)

    # Branches start partway down the trunk (not just its very top), so
    # the lowest branches read as growing out of the trunk itself.
    _BRANCH_START_Y = 13

    _MAX_BRANCH_PIXELS = 60
    _MAX_LEAF_PIXELS = 360

    def __init__(self):
        super().__init__()
        self._build_tree()

    def _build_tree(self):
        """Grow a wide, forking network of white branches up from partway
        down the trunk via a fanned-out random walk, then scatter fall-
        colored "leaf" pixels around the resulting branch structure."""
        branch_coords: set[tuple[int, int]] = set()

        # Several branches all start right at the trunk, but each is
        # given its own outward "bias" (a target direction it keeps
        # gently steering toward, on top of its own random wobble) so as
        # a group they fan out wide as they climb, instead of all
        # wandering off independently from a single point.
        num_starts = 7
        tips = []
        for i in range(num_starts):
            spread = (i / (num_starts - 1)) - 0.5  # -0.5 .. 0.5
            bias = spread * 3.0
            start_x = (self._TRUNK_LEFT + self._TRUNK_RIGHT) / 2.0 + bias * 0.3
            start_y = self._BRANCH_START_Y + random.uniform(-1.0, 0.5)
            tips.append((start_x, start_y, bias * 0.3, bias))

        while tips and len(branch_coords) < self._MAX_BRANCH_PIXELS:
            x, y, drift, bias = tips.pop()

            # Walk this branch upward a short run before deciding whether
            # to fork, stop, or keep going.
            run_length = random.randint(2, 4)
            for _ in range(run_length):
                branch_coords.add((int(round(x)), int(round(y))))
                y -= 1
                # Random wobble, plus a gentle, persistent pull toward
                # this branch's own outward bias direction.
                drift += random.uniform(-0.5, 0.5) + bias * 0.12
                drift = max(-2.2, min(2.2, drift))
                x += drift
                # Let branches run off the top/sides -- just stop growing
                # that particular branch once it's well past the edge.
                if y < -2 or x < -3 or x > WIDTH + 2:
                    break
            else:
                if y < -2 or len(branch_coords) >= self._MAX_BRANCH_PIXELS:
                    continue
                if random.random() < 0.45:
                    # Fork into two branches, inheriting diverging biases
                    # so each half keeps fanning further apart.
                    tips.append((x, y, drift + random.uniform(0.3, 0.8), bias + 0.6))
                    tips.append((x, y, drift - random.uniform(0.3, 0.8), bias - 0.6))
                else:
                    tips.append((x, y, drift, bias))

        self.branches = sorted(branch_coords)

        # Scatter leaf pixels in the neighborhood of the branches, so the
        # branch skeleton stays a clean white while the foliage reads as
        # a separate, fall-colored layer around it. Leaves cluster densely
        # right around each branch pixel, and more sparsely a bit further
        # out, for a fuller foliage look around a thin branch structure.
        leaf_coords: set[tuple[int, int]] = set()
        near_offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        far_offsets = [
            (dx, dy)
            for dx in (-2, -1, 0, 1, 2)
            for dy in (-2, -1, 0, 1, 2)
            if (dx, dy) not in near_offsets and (dx, dy) != (0, 0)
        ]
        for bx, by in branch_coords:
            if len(leaf_coords) >= self._MAX_LEAF_PIXELS:
                break
            for dx, dy in near_offsets:
                if random.random() < 0.65:
                    nx, ny = bx + dx, by + dy
                    if (nx, ny) not in branch_coords:
                        leaf_coords.add((nx, ny))
            for dx, dy in far_offsets:
                if random.random() < 0.18:
                    nx, ny = bx + dx, by + dy
                    if (nx, ny) not in branch_coords:
                        leaf_coords.add((nx, ny))

        self.leaves = [(x, y, _CanopyPixel()) for x, y in leaf_coords]

    def update(self, leds: list, frame: int) -> None:
        hue, sat, cap = get_fall_palette_color(frame)
        leaf_color = hsv_to_rgb(hue, sat, cap)

        _clear(leds)
        for x, y, pixel in self.leaves:
            _set(leds, x, y, _scale(leaf_color, pixel.brightness(frame)))

        for x, y in self.branches:
            _set(leds, x, y, self._TRUNK_COLOR)

        for y in range(self._TRUNK_TOP, self._TRUNK_BOTTOM + 1):
            _set(leds, self._TRUNK_LEFT, y, self._TRUNK_COLOR)
            _set(leds, self._TRUNK_RIGHT, y, self._TRUNK_COLOR)
