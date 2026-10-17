"""Red-orange solar eclipse designed for a low-resolution LED panel."""

import math

from patterns.base import HEIGHT, NUM_LEDS, WIDTH, Pattern, xy_to_index


class BloodMoonEclipse(Pattern):
    """A black moon crosses a red-orange sun and reveals a dark-red corona."""

    name = "Blood Moon Eclipse"

    def __init__(self):
        super().__init__()
        self.cx = (WIDTH - 1) / 2.0
        self.cy = (HEIGHT - 1) / 2.0
        self.sun_radius = 6.25
        self.moon_radius = 6.0
        self.cycle_frames = 1200  # ~20 seconds at 60 FPS

    @staticmethod
    def _mix(
        first: tuple[int, int, int],
        second: tuple[int, int, int],
        amount: float,
    ) -> tuple[int, int, int]:
        amount = max(0.0, min(1.0, amount))
        return tuple(int(a + (b - a) * amount) for a, b in zip(first, second))

    def update(self, leds: list, frame: int) -> None:
        for i in range(NUM_LEDS):
            leds[i] = (0, 0, 0)

        cycle_frame = frame % self.cycle_frames

        # Timeline at 60 FPS: one second clear, seven seconds ingress, 1.3
        # seconds held exactly at totality, seven seconds egress, then 3.7
        # seconds clear. Smoothstep keeps the transit from starting abruptly.
        ingress_start = 60
        ingress_end = 480
        totality_end = 558
        egress_end = 978
        if cycle_frame < ingress_start:
            moon_x = self.cx + 14.5
        elif cycle_frame < ingress_end:
            progress = (cycle_frame - ingress_start) / (ingress_end - ingress_start)
            progress = progress * progress * (3.0 - 2.0 * progress)
            moon_x = self.cx + 14.5 * (1.0 - progress)
        elif cycle_frame < totality_end:
            moon_x = self.cx
        elif cycle_frame < egress_end:
            progress = (cycle_frame - totality_end) / (egress_end - totality_end)
            progress = progress * progress * (3.0 - 2.0 * progress)
            moon_x = self.cx - 14.5 * progress
        else:
            moon_x = self.cx - 14.5
        moon_y = self.cy
        center_separation = math.hypot(moon_x - self.cx, moon_y - self.cy)
        totality = max(0.0, 1.0 - center_separation / 2.2)
        totality = totality * totality * (3.0 - 2.0 * totality)
        brightness_breathe = 0.95 + 0.05 * math.sin(frame * 0.022)

        for y in range(HEIGHT):
            for x in range(WIDTH):
                sun_distance = math.hypot(x - self.cx, y - self.cy)
                moon_distance = math.hypot(x - moon_x, y - moon_y)

                color = (0, 0, 0)

                # Wide red atmospheric glow surrounding the orange solar disc.
                if sun_distance <= self.sun_radius + 2.0:
                    glow = max(0.0, 1.0 - (sun_distance - self.sun_radius) / 2.0)
                    glow = min(1.0, glow) ** 2
                    color = (int(75 * glow * brightness_breathe),
                             int(3 * glow * brightness_breathe), 0)

                if sun_distance <= self.sun_radius:
                    radial = max(0.0, 1.0 - sun_distance / self.sun_radius)
                    # Slow shared breathing over the entire sun, with only a
                    # slight spatial heat variation so it moves as one disc.
                    shimmer = 0.97 + 0.03 * math.sin(frame * 0.013 + x * 1.3 + y * 0.8)
                    center = (255, 105, 0)
                    limb = (220, 22, 0)
                    color = self._mix(limb, center, radial * 0.85)
                    color = tuple(int(channel * shimmer * brightness_breathe) for channel in color)

                # The corona belongs to the stationary sun, not the moving
                # lunar disc. Near totality, brighten a fixed annulus and broad
                # radial rays around the solar center.
                corona_distance = abs(sun_distance - self.sun_radius)
                corona_width = 0.90
                if totality > 0.0 and corona_distance < corona_width:
                    corona = (1.0 - corona_distance / corona_width) * totality
                    solar_angle = math.atan2(y - self.cy, x - self.cx)
                    fixed_rays = 0.78 + 0.22 * math.sin(solar_angle * 8.0)
                    # Share the sun's slow breathing; the dark-red corona
                    # remains fixed to the sun during the totality hold.
                    corona *= fixed_rays * brightness_breathe
                    corona_color = (155, 5, 2)
                    color = self._mix(color, corona_color, min(1.0, corona * 1.35))

                # Feather the lunar edge across roughly one LED instead of
                # switching pixels off abruptly as the disc crosses them.
                disc_feather = 1.05
                occlusion = (self.moon_radius + disc_feather - moon_distance) / (2.0 * disc_feather)
                occlusion = max(0.0, min(1.0, occlusion))
                occlusion = occlusion * occlusion * (3.0 - 2.0 * occlusion)
                if occlusion > 0.0:
                    color = self._mix(color, (0, 0, 0), occlusion)

                leds[xy_to_index(x, y)] = color
