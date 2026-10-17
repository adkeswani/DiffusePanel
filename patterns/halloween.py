"""Halloween-themed patterns for the 16x16 simulator.

These patterns intentionally use chunky silhouettes and high contrast so their
faces and motion remain readable through the panel diffuser.
"""

import math
import random

from patterns.base import HEIGHT, NUM_LEDS, WIDTH, Pattern, hsv_to_rgb, xy_to_index
from simulator.fastled_noise import inoise8_raw, qadd8

BLACK = (0, 0, 0)
ORANGE = (255, 72, 0)
PURPLE = (150, 0, 255)
BONE = (205, 220, 205)
GHOST_WHITE = (175, 210, 220)
SLIME_GREEN = (55, 235, 8)
IVORY_WHITE = (255, 244, 205)


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


def _map(x: int, in_min: int, in_max: int, out_min: int, out_max: int) -> int:
    """Integer remap matching Arduino's map()."""
    return (x - in_min) * (out_max - out_min) // (in_max - in_min) + out_min


def _inoise8_fixed(x: int, y: int) -> int:
    """Match the firmware's spike-safe FastLED inoise8 wrapper."""
    raw = max(-64, inoise8_raw(x, y))
    return qadd8(raw + 64, raw + 64)


class HalloweenRingFade(Pattern):
    """Purple/orange ring with a randomly selected wave color and direction."""

    name = "Halloween Ring Fade"

    def __init__(self):
        super().__init__()
        self.direction = random.choice((-1.0, 1.0))
        self.wave_color = random.choice((PURPLE, ORANGE))
        self.base_color = ORANGE if self.wave_color == PURPLE else PURPLE
        self.start_angle = random.uniform(0.0, math.tau)

    def update(self, leds: list, frame: int) -> None:
        cx = (WIDTH - 1) / 2.0
        cy = (HEIGHT - 1) / 2.0
        peak_angle = self.start_angle + self.direction * frame * 0.035

        for y in range(HEIGHT):
            for x in range(WIDTH):
                dx = x - cx
                dy = y - cy
                ring_distance = abs(math.hypot(dx, dy) - 5.7)
                if ring_distance >= 2.7:
                    _set(leds, x, y, BLACK)
                    continue

                edge = (1.0 - ring_distance / 2.7) ** 2
                pixel_angle = math.atan2(dy, dx)
                angle_distance = abs((pixel_angle - peak_angle + math.pi) % math.tau - math.pi)
                wave = ((1.0 + math.cos(angle_distance)) / 2.0) ** 4
                color = _blend(self.base_color, self.wave_color, wave)
                _set(leds, x, y, _scale(color, edge * (0.72 + 0.28 * wave)))


class LaughingSkeleton(Pattern):
    """Bobbing skull and rib cage with a jaw that opens in laughter."""

    name = "Laughing Skeleton"

    def update(self, leds: list, frame: int) -> None:
        _clear(leds)
        bob = 1 if math.sin(frame * 0.12) > 0.7 else 0
        jaw_open = (frame // 10) % 2 == 0
        bone = _scale(BONE, 0.82 + 0.18 * ((math.sin(frame * 0.08) + 1.0) / 2.0))

        # Skull dome, cheekbones, and temples.
        skull_rows = {
            0: range(5, 11),
            1: range(4, 12),
            2: range(3, 13),
            3: range(3, 13),
            4: range(3, 13),
            5: range(4, 12),
            6: range(5, 11),
        }
        for y, xs in skull_rows.items():
            for x in xs:
                _set(leds, x, y + bob, bone)

        # Deep eye sockets and triangular nose cavity.
        for x, y in ((4, 3), (5, 3), (4, 4), (10, 3), (11, 3), (11, 4),
                     (7, 5), (8, 5), (7, 6)):
            _set(leds, x, y + bob, BLACK)

        # Hinged jaw: alternating open mouth gives a clear laughing motion.
        if jaw_open:
            for y in range(7, 10):
                for x in range(5, 11):
                    if y == 7 or y == 9 or x in (5, 10):
                        _set(leds, x, y + bob, bone)
            for x in (7, 9):
                _set(leds, x, 8 + bob, bone)
        else:
            for x in range(5, 11):
                _set(leds, x, 7 + bob, bone)
            for x in (6, 8, 10):
                _set(leds, x, 8 + bob, bone)

        # Neck, spine, ribs, and raised laughing arms.
        for x, y in ((7, 10), (8, 10), (7, 11), (8, 11), (7, 12), (8, 12),
                     (7, 13), (8, 13), (7, 14), (8, 14),
                     (4, 11), (5, 11), (6, 11), (9, 11), (10, 11), (11, 11),
                     (3, 13), (4, 13), (5, 13), (6, 13), (9, 13), (10, 13),
                     (11, 13), (12, 13), (2, 10), (3, 11), (12, 11), (13, 10),
                     (1, 8), (2, 9), (13, 9), (14, 8)):
            _set(leds, x, y, bone)


class BedsheetGhost(Pattern):
    """Floating bedsheet ghost with cut-out eyes and a rippling hem."""

    name = "Bedsheet Ghost"

    def update(self, leds: list, frame: int) -> None:
        _clear(leds, (0, 0, 3))
        bob = int(round(math.sin(frame * 0.045)))
        pulse = 0.72 + 0.20 * ((math.sin(frame * 0.07) + 1.0) / 2.0)
        cloth = _scale(GHOST_WHITE, pulse)
        edge = _scale((100, 140, 190), pulse)

        # Rounded head flowing into a widening sheet.
        for y in range(1, 14):
            yy = y + bob
            if y <= 2:
                left, right = 6 - (y - 1), 9 + (y - 1)
            elif y <= 5:
                left, right = 4, 11
            else:
                spread = min(2, (y - 5) // 3)
                left, right = 4 - spread, 11 + spread
            for x in range(left, right + 1):
                color = edge if x in (left, right) else cloth
                _set(leds, x, yy, color)

        # Eye holes stay completely dark against the luminous sheet.
        for x, y in ((5, 4), (6, 4), (5, 5), (6, 5),
                     (9, 4), (10, 4), (9, 5), (10, 5)):
            _set(leds, x, y + bob, BLACK)

        # Replace the lower edge with a travelling three-lobed ripple.
        for x in range(1, 15):
            for y in range(12 + bob, 16):
                _set(leds, x, y, BLACK)
            hem_y = 13 + bob + int(round(math.sin(x * 1.25 + frame * 0.13)))
            for y in range(11 + bob, hem_y + 1):
                _set(leds, x, y, edge if y == hem_y else cloth)


class PacManGhost(Pattern):
    """A classic arcade ghost silhouette, recolored an off-white ivory.

    Uses the familiar rounded-dome / straight-sided / three-lobed-foot shape,
    with every curved edge (dome and hem) anti-aliased via fractional
    brightness so the silhouette reads smoothly instead of stair-stepping.
    """

    name = "Pac-Man Ghost (White)"

    # Corner radius used to round the dome into a smooth quarter-circle
    # instead of a hard-edged staircase.
    _DOME_RADIUS = 4.0
    # The wavy hem is a continuous, feathered sine wave (three gentle lobes
    # across the 14-column body) rather than a hard-edged lookup table, so
    # the "feet" anti-alias smoothly instead of stair-stepping.
    _FOOT_CENTER = 12.5
    _FOOT_AMPLITUDE = 1.3
    _FOOT_PERIODS = 3
    _BOB_TOGGLE_FRAMES = 90  # constant bob cadence; eyes move at 2x this rate

    def update(self, leds: list, frame: int) -> None:
        _clear(leds)
        pulse = 0.85 + 0.15 * ((math.sin(frame * 0.06) + 1.0) / 2.0)
        body = _scale(IVORY_WHITE, pulse)
        bob = (frame // self._BOB_TOGGLE_FRAMES) % 2
        eye_dx = (frame // (self._BOB_TOGGLE_FRAMES // 2)) % 2

        # Gently sway the wave's phase so the feet sway side to side, rather
        # than the previous hard two-frame swish. This stays independent of
        # the vertical bob above.
        phase_shift = math.sin(frame * 0.05) * 1.2
        angular_freq = 2 * math.pi * self._FOOT_PERIODS / 14
        r = self._DOME_RADIUS

        for i, x in enumerate(range(1, 15)):
            # Smooth circular corner: how far this column is inset from the
            # top, rounded to a hard-edged row (no feathering on the dome).
            edge_dist = min(x - 1, 14 - x)
            edge_dist = max(0.0, min(r, edge_dist))
            top_f = r - math.sqrt(max(0.0, r * r - (r - edge_dist) ** 2))
            full_top = int(round(top_f)) + bob

            wave = math.sin((i + phase_shift) * angular_freq + math.pi / 2)
            bottom_f = self._FOOT_CENTER + wave * self._FOOT_AMPLITUDE

            full_bottom = int(math.floor(bottom_f)) + bob
            frac_bottom = bottom_f - math.floor(bottom_f)

            for y in range(full_top, full_bottom + 1):
                _set(leds, x, y, body)

            # Feather only the hem's final row by its fractional coverage,
            # for a smooth, anti-aliased point instead of a hard pixel cutoff.
            if frac_bottom > 0.02:
                _set(leds, x, full_bottom + 1, _scale(body, frac_bottom))

        # Eyes are dark cutouts with a small cyan dot that drifts left/right
        # at twice the bob's speed (vertical position still follows the bob).
        for ex in (4, 10):
            for dy in range(3):
                for dx in range(2):
                    _set(leds, ex + dx, 5 + dy + bob, BLACK)
            _set(leds, ex + eye_dx, 6 + bob, (60, 220, 255))


class _FlowingDrips(Pattern):
    """Shared downward-stream motion for the green ooze."""

    def __init__(self):
        super().__init__()
        self.fronts = [random.uniform(-12.0, 2.0) for _ in range(WIDTH)]
        self.speeds = [random.uniform(0.018, 0.055) for _ in range(WIDTH)]
        # Each stream has a trailing edge. It resets only after that tail has
        # crossed the bottom, so a completed column visibly drains downward.
        self.lengths = [random.uniform(18.0, 28.0) for _ in range(WIDTH)]
        self.widths = [random.choice((0, 0, 1)) for _ in range(WIDTH)]

    def update(self, leds: list, frame: int) -> None:
        _clear(leds, self.background_color)

        for x in range(WIDTH):
            self.fronts[x] += self.speeds[x]
            tail = self.fronts[x] - self.lengths[x]
            if tail > HEIGHT - 1:
                self.fronts[x] = random.uniform(-10.0, -1.0)
                self.speeds[x] = random.uniform(0.018, 0.055)
                self.lengths[x] = random.uniform(18.0, 28.0)
                tail = self.fronts[x] - self.lengths[x]

            front = self.fronts[x]
            for y in range(HEIGHT):
                if tail <= y <= front:
                    depth = max(0.0, front - y)
                    shimmer = 0.80 + 0.20 * math.sin(frame * 0.08 + x * 1.7 + y * 0.3)
                    brightness = (0.42 + 0.58 * math.exp(-depth / 8.0)) * shimmer
                    _set(leds, x, y, _scale(self.stream_color, brightness))

            # Rounded bright bead at the tip of occasional thicker drips.
            tip = int(front)
            if self.widths[x] and 0 <= tip < HEIGHT:
                _set(leds, x, tip, self.bright_tip_color)
                if tip > 0:
                    _set(leds, x, tip - 1, self.inner_tip_color)

class FlowingSlime(_FlowingDrips):
    """Toxic-green streams that drain off the bottom of the panel."""

    name = "Flowing Slime"
    background_color = (0, 2, 0)
    stream_color = SLIME_GREEN
    bright_tip_color = (105, 255, 20)
    inner_tip_color = (45, 175, 5)


class SinisterHeartbeat(Pattern):
    """Broad red double-pulse followed by an ominous dark resting interval."""

    name = "Sinister Heartbeat"

    def update(self, leds: list, frame: int) -> None:
        cycle = frame % 180

        # A strong "lub" followed quickly by a smaller "dub". Gaussian
        # envelopes avoid abrupt frame transitions and read well at 16x16.
        lub = math.exp(-((cycle - 28) / 8.0) ** 2)
        dub = 0.68 * math.exp(-((cycle - 57) / 10.0) ** 2)
        pulse = min(1.0, lub + dub)

        # The illuminated mass contracts toward the center at each peak, then
        # leaves a dim red field that decays almost to black during the rest.
        cx = (WIDTH - 1) / 2.0
        cy = (HEIGHT - 1) / 2.0
        radius = 10.5 - pulse * 5.5
        rest_glow = 0.025 + 0.055 * max(0.0, 1.0 - cycle / 150.0)

        for y in range(HEIGHT):
            for x in range(WIDTH):
                distance = math.hypot(x - cx, y - cy)
                inside = max(0.0, 1.0 - distance / radius)
                core = inside * inside

                # A faint full-panel blood-red haze plus a bright contracting
                # center. At the beat peak the core approaches warm scarlet.
                red = int(255 * min(1.0, rest_glow + pulse * (0.35 + 0.65 * core)))
                green = int(32 * pulse * core)
                blue = int(10 * pulse * core)
                _set(leds, x, y, (red, green, blue))


class LaughingPumpkin(Pattern):
    """Full-panel jack-o'-lantern whose carved mouth laughs open and shut."""

    name = "Laughing Pumpkin"

    def update(self, leds: list, frame: int) -> None:
        pulse = 0.78 + 0.18 * ((math.sin(frame * 0.055) + 1.0) / 2.0)
        orange = _scale(ORANGE, pulse)
        _clear(leds, orange)

        # Subtle vertical pumpkin ribs while preserving the full orange field.
        for x in (1, 5, 10, 14):
            for y in range(HEIGHT):
                _set(leds, x, y, _scale(orange, 0.68))

        # Slanted triangular eyes and a small nose.
        for x, y in ((3, 4), (4, 4), (5, 4), (4, 5), (5, 5), (5, 6),
                     (10, 4), (11, 4), (12, 4), (10, 5), (11, 5), (10, 6),
                     (7, 7), (8, 7), (7, 8), (8, 8)):
            _set(leds, x, y, BLACK)

        mouth_open = (frame // 11) % 2 == 0
        if mouth_open:
            mouth = {
                9: range(3, 13),
                10: range(2, 14),
                11: range(3, 13),
                12: range(4, 12),
                13: range(5, 11),
            }
            for y, xs in mouth.items():
                for x in xs:
                    _set(leds, x, y, BLACK)
            # Orange teeth interrupt the dark laughing mouth.
            for x, y in ((4, 9), (7, 9), (10, 9), (5, 12), (8, 12), (11, 11)):
                _set(leds, x, y, orange)
        else:
            for x, y in ((3, 10), (4, 11), (5, 11), (6, 12), (7, 12),
                         (8, 12), (9, 12), (10, 11), (11, 11), (12, 10)):
                _set(leds, x, y, BLACK)


class EvilEyes(Pattern):
    """A pair of slanted eyes that emerge from darkness and fade away."""

    name = "Evil Eyes"

    def __init__(self):
        super().__init__()
        # Pick one warm, readable eye color per activation.
        self.eye_color = random.choice((
            (255, 150, 0),
            (255, 185, 0),
            (255, 215, 20),
            (235, 175, 25),
        ))

    def update(self, leds: list, frame: int) -> None:
        _clear(leds)
        cycle = frame % 300
        if cycle < 70:
            fade = cycle / 70.0
        elif cycle < 190:
            fade = 1.0
        elif cycle < 270:
            fade = 1.0 - (cycle - 190) / 80.0
        else:
            fade = 0.0
        fade = fade * fade * (3.0 - 2.0 * fade)

        eye_color = _scale(self.eye_color, fade)
        pupil_color = _scale((80, 35, 0), fade)

        # Inner corners point downward, producing an unmistakably angry slant.
        left_eye = ((0, 4), (1, 4), (2, 4), (3, 5), (4, 5), (5, 6), (6, 6),
                    (1, 5), (2, 5), (3, 6), (4, 6), (5, 7), (6, 7),
                    (2, 6), (3, 7), (4, 7))
        right_eye = tuple((15 - x, y) for x, y in left_eye)
        for x, y in left_eye + right_eye:
            _set(leds, x, y, eye_color)

        # TODO (optional): Use eye_color here too for a single-color eye shape.
        for x, y in ((4, 6), (11, 6), (5, 6), (10, 6)):
            _set(leds, x, y, pupil_color)


class LaughingSkullCloseup(Pattern):
    """Full-panel frontal skull with an exaggerated laughing jaw."""

    name = "Laughing Skull Close-up"

    def update(self, leds: list, frame: int) -> None:
        _clear(leds)

        # A slightly irregular laugh cadence: closed, half-open, wide-open,
        # half-open. The skull bobs upward during the widest part.
        phase = (frame // 7) % 8
        jaw_drop = (0, 0, 1, 2, 2, 1, 0, 1)[phase]
        bob = -1 if phase in (3, 4) else 0
        bone = (218, 210, 175)
        highlight = (255, 244, 205)
        shadow = (120, 105, 90)

        # Broad cranium and cheekbones fill nearly the entire panel. Large
        # shapes are intentional so the silhouette survives the diffuser.
        skull_rows = (
            (5, 10),
            (3, 12),
            (2, 13),
            (1, 14),
            (1, 14),
            (1, 14),
            (2, 13),
            (2, 13),
            (3, 12),
            (2, 13),
        )
        for y, (left, right) in enumerate(skull_rows):
            for x in range(left, right + 1):
                edge = x in (left, right) or y == 0
                _set(leds, x, y + bob, shadow if edge else bone)

        # Forehead highlight gives the pale mass some dimension without
        # introducing details smaller than a diffuser cell.
        for x, y in ((5, 1), (6, 1), (7, 1), (4, 2), (5, 2), (6, 2)):
            _set(leds, x, y + bob, highlight)

        # Oversized, angled eye sockets.
        left_socket = (
            (3, 3), (4, 3), (5, 3),
            (2, 4), (3, 4), (4, 4), (5, 4), (6, 4),
            (2, 5), (3, 5), (4, 5), (5, 5), (6, 5),
            (3, 6), (4, 6), (5, 6),
        )
        for x, y in left_socket:
            _set(leds, x, y + bob, BLACK)
            _set(leds, 15 - x, y + bob, BLACK)

        # Simple inverted-heart nasal opening.
        for x, y in ((7, 6), (8, 6), (6, 7), (7, 7), (8, 7), (9, 7),
                     (7, 8), (8, 8)):
            _set(leds, x, y + bob, BLACK)

        # Black mouth cavity separates the fixed upper teeth from the jaw.
        for y in range(9 + bob, 13 + jaw_drop):
            for x in range(3, 13):
                _set(leds, x, y, BLACK)

        # Fixed upper gum and four oversized upper teeth.
        for x in range(3, 13):
            _set(leds, x, 9 + bob, shadow)
        for x in (4, 5, 7, 8, 10, 11):
            _set(leds, x, 9 + bob, highlight)
            _set(leds, x, 10 + bob, bone)

        # The lower jaw translates independently. Four chunky lower teeth are
        # more readable than attempting a realistic row of tiny teeth.
        jaw_top = 11 + jaw_drop
        for x in (4, 5, 7, 8, 10, 11):
            _set(leds, x, jaw_top, highlight)
        for y in range(jaw_top, 14 + jaw_drop):
            _set(leds, 2 + (y - jaw_top), y, shadow)
            _set(leds, 13 - (y - jaw_top), y, shadow)
        for x in range(5, 11):
            _set(leds, x, 13 + jaw_drop, bone)
        for x in range(6, 10):
            _set(leds, x, 14 + jaw_drop, shadow)


class BreathingFog(Pattern):
    """Purple counterpart to the firmware's noise-driven botanical field."""

    name = "Breathing Fog"

    def __init__(self):
        super().__init__()
        self.direction_x = random.choice((-1, 1))
        self.direction_y = random.choice((-1, 1))
        self.origin_x = random.randint(0, 65535)
        self.origin_y = random.randint(0, 65535)
        self.buffer = [[0.0, 0.0, 0.0] for _ in range(NUM_LEDS)]

    def update(self, leds: list, frame: int) -> None:
        del frame
        ms = self.elapsed()
        raw_x = ms // 14
        raw_y = ms // 19
        time_x = raw_x if self.direction_x > 0 else -raw_x
        time_y = raw_y if self.direction_y > 0 else -raw_y
        field_scale = 24

        for x in range(WIDTH):
            for y in range(HEIGHT):
                noise_x = y * field_scale + time_x + self.origin_x
                noise_y = x * field_scale + time_y + self.origin_y
                intensity = _inoise8_fixed(noise_x, noise_y)
                hue_morph = _inoise8_fixed(noise_x + 5000, noise_y + 3000)

                # Black lows through deep purple to lavender highlights.
                hue = _map(hue_morph, 0, 255, 182, 207)
                brightness = _map(intensity, 0, 255, 2, 125)
                target = hsv_to_rgb(hue, 235, brightness)
                if intensity > 185:
                    blend_amount = _map(intensity, 185, 255, 0, 145) / 255.0
                    target = _blend(target, (190, 135, 255), blend_amount)

                # GRASS_SMOOTH is 90/256 in the firmware.
                idx = xy_to_index(x, y)
                shown = self.buffer[idx]
                for channel in range(3):
                    shown[channel] += (target[channel] - shown[channel]) * (90 / 256)
                leds[idx] = tuple(int(channel) for channel in shown)


class CauldronBubbles(Pattern):
    """Acid-green bubbles rise from a purple, gently sloshing cauldron."""

    name = "Cauldron Bubbles"

    def __init__(self):
        super().__init__()
        self.bubbles: list[list[float]] = []

    def update(self, leds: list, frame: int) -> None:
        _clear(leds, (2, 0, 5))

        # Purple cauldron body and luminous green brew surface.
        for y in range(11, 16):
            inset = max(0, y - 13)
            for x in range(2 + inset, 14 - inset):
                _set(leds, x, y, (65, 0, 95) if y < 15 else (35, 0, 55))
        for x in range(2, 14):
            surface_y = 10 + int(round(0.5 * math.sin(x * 0.9 + frame * 0.12)))
            _set(leds, x, surface_y, (85, 255, 10))
            _set(leds, x, surface_y + 1, (30, 110, 5))

        if frame % 15 == 0 and len(self.bubbles) < 8:
            self.bubbles.append([
                random.uniform(3.0, 12.0),
                10.0,
                random.uniform(0.035, 0.075),
                random.choice((1.0, 1.0, 1.5)),
            ])

        living = []
        for bubble in self.bubbles:
            bubble[1] -= bubble[2]
            x = bubble[0] + math.sin(frame * 0.06 + bubble[0]) * 0.7
            y = bubble[1]
            radius = bubble[3]
            if y > -2:
                living.append(bubble)
            for py in range(HEIGHT):
                for px in range(WIDTH):
                    distance = math.hypot(px - x, py - y)
                    if abs(distance - radius) < 0.55:
                        _set(leds, px, py, (105, 255, 20))
        self.bubbles = living


class LightningStorm(Pattern):
    """A persistent bolt that flashes repeatedly, then fades from view."""

    name = "Lightning Storm"

    def __init__(self):
        super().__init__()
        self.bolt: list[tuple[int, int]] = []
        self.strike_frame = -1
        self.next_strike = random.randint(45, 100)

    def _strike(self) -> None:
        x = random.randint(4, 11)
        self.bolt = []
        for y in range(1, HEIGHT):
            self.bolt.append((x, y))
            if y % 2 == 0:
                x = max(1, min(WIDTH - 2, x + random.choice((-1, 0, 1))))
            if y in (6, 10) and random.random() < 0.75:
                direction = random.choice((-1, 1))
                self.bolt.extend((x + direction * step, y + step) for step in (1, 2))
        self.strike_frame = 0

    def update(self, leds: list, frame: int) -> None:
        del frame
        if self.strike_frame < 0:
            self.next_strike -= 1
            if self.next_strike <= 0:
                self._strike()

        # Three flashes reuse exactly the same bolt. The long final flash and
        # afterglow make its shape readable through a coarse diffuser.
        phase = self.strike_frame
        bright = phase in range(0, 7) or phase in range(12, 21) or phase in range(26, 43)
        afterglow = phase in range(43, 75)
        between_flashes = phase in range(7, 12) or phase in range(21, 26)

        background = (65, 42, 95) if bright else (10, 3, 20)
        _clear(leds, background)
        for x in range(WIDTH):
            cloud_y = 1 + int(round(math.sin(x * 0.8)))
            for y in range(max(0, cloud_y), min(4, cloud_y + 2)):
                _set(leds, x, y, (35, 12, 55))

        if bright or afterglow or between_flashes:
            if bright:
                bolt_color = (255, 245, 190)
                glow_color = (120, 65, 180)
            elif between_flashes:
                bolt_color = (90, 55, 130)
                glow_color = (35, 15, 60)
            else:
                fade = 1.0 - (phase - 43) / 32.0
                bolt_color = _scale((155, 100, 220), fade)
                glow_color = _scale((70, 35, 110), fade * 0.6)

            # One-pixel side glow thickens the bolt enough to survive 16x16.
            for x, y in self.bolt:
                _set(leds, x - 1, y, glow_color)
                _set(leds, x + 1, y, glow_color)
                _set(leds, x, y, bolt_color)

        if self.strike_frame >= 0:
            self.strike_frame += 1
            if self.strike_frame >= 75:
                self.strike_frame = -1
                self.next_strike = random.randint(70, 150)


class Spiderweb(Pattern):
    """A silver radial web with a small purple spider circling its strands."""

    name = "Spiderweb"

    def update(self, leds: list, frame: int) -> None:
        _clear(leds, (1, 0, 4))
        cx, cy = 7.5, 7.5
        web = (105, 105, 125)

        for y in range(HEIGHT):
            for x in range(WIDTH):
                dx, dy = x - cx, y - cy
                distance = math.hypot(dx, dy)
                angle = math.atan2(dy, dx)
                spoke = abs(math.sin(angle * 4.0)) < 0.105
                ring = min(abs(distance - radius) for radius in (3.0, 5.5, 8.0)) < 0.34
                if spoke or ring:
                    _set(leds, x, y, web)

        angle = frame * 0.025
        radius = 5.4 + math.sin(frame * 0.04) * 1.4
        spider_x = int(round(cx + math.cos(angle) * radius))
        spider_y = int(round(cy + math.sin(angle) * radius))
        for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, 1)):
            _set(leds, spider_x + dx, spider_y + dy, (180, 20, 255))


class GraveyardLightning(Pattern):
    """Tombstone silhouettes appear only when distant lightning flashes."""

    name = "Graveyard Lightning"

    def __init__(self):
        super().__init__()
        self.flash_left = 0
        self.next_flash = random.randint(60, 140)

    def update(self, leds: list, _frame: int) -> None:
        del _frame
        self.next_flash -= 1
        if self.next_flash <= 0:
            self.flash_left = random.randint(3, 7)
            self.next_flash = random.randint(80, 190)

        flashing = self.flash_left > 0
        _clear(leds, (35, 20, 55) if flashing else (1, 0, 4))
        moon = (150, 125, 180) if flashing else (18, 12, 25)
        for y in range(1, 6):
            for x in range(10, 15):
                if math.hypot(x - 12, y - 3) <= 2.2:
                    _set(leds, x, y, moon)

        ground = (8, 5, 12)
        for y in range(13, HEIGHT):
            for x in range(WIDTH):
                _set(leds, x, y, ground)

        stone = (12, 8, 16) if flashing else (3, 2, 5)
        for left, top, width in ((1, 8, 4), (6, 10, 3), (11, 7, 4)):
            for y in range(top, 14):
                for x in range(left, left + width):
                    if y > top or x not in (left, left + width - 1):
                        _set(leds, x, y, stone)
            _set(leds, left + width // 2, top, stone)

        if flashing:
            self.flash_left -= 1


class SwarmingBats(Pattern):
    """Tiny V-shaped bats stream across a dim, oversized moon."""

    name = "Swarming Bats"

    def __init__(self):
        super().__init__()
        self.bats = [
            [random.uniform(-WIDTH, WIDTH), random.uniform(2, 13), random.uniform(0.025, 0.07)]
            for _ in range(7)
        ]

    def update(self, leds: list, frame: int) -> None:
        _clear(leds, (3, 1, 8))
        moon_color = (115, 80, 135)
        for y in range(2, 14):
            for x in range(3, 15):
                if math.hypot(x - 9, y - 7.5) <= 5.2:
                    _set(leds, x, y, moon_color)

        for bat in self.bats:
            bat[0] += bat[2]
            if bat[0] > WIDTH + 2:
                bat[0] = random.uniform(-8, -2)
                bat[1] = random.uniform(2, 13)
            x = int(round(bat[0]))
            y = int(round(bat[1] + math.sin(frame * 0.04 + bat[0]) * 1.2))
            wings_up = (frame // 7 + int(bat[0])) % 2 == 0
            shape = ((0, 0), (-1, -1), (1, -1)) if wings_up else ((0, 0), (-1, 1), (1, 1))
            for dx, dy in shape:
                _set(leds, x + dx, y + dy, BLACK)


class PossessedStatic(Pattern):
    """Purple monochrome static with intermittent red signal corruption."""

    name = "Possessed Static"

    def update(self, leds: list, frame: int) -> None:
        red_intrusion = frame % 180 in range(125, 145)
        scanline = (frame // 2) % HEIGHT
        for y in range(HEIGHT):
            for x in range(WIDTH):
                value = random.randint(0, 100)
                if y == scanline:
                    value = min(180, value + 70)
                if red_intrusion and random.random() < 0.22:
                    color = (min(255, value * 2), 0, 3)
                else:
                    color = (value // 2, 0, min(255, value * 2))
                _set(leds, x, y, color)
