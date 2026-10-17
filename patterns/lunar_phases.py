"""Warm off-white moon progressing through a complete lunar phase cycle."""

import math

from patterns.base import HEIGHT, NUM_LEDS, WIDTH, Pattern, xy_to_index


class LunarPhases(Pattern):
    """A cratered moon that waxes from new to full and wanes back to new."""

    name = "Lunar Phases"

    def __init__(self):
        super().__init__()
        self.cx = (WIDTH - 1) / 2.0
        self.cy = (HEIGHT - 1) / 2.0
        self.radius = 7.15
        self.cycle_frames = 1200  # ~20 seconds at 60 FPS

        # Broad crater regions chosen to remain visible on a 16x16 diffuser.
        self.craters = (
            (4.2, 4.1, 1.55, 0.70),
            (10.8, 5.0, 1.25, 0.77),
            (8.6, 9.2, 1.65, 0.68),
            (3.8, 10.7, 1.05, 0.74),
            (11.7, 11.5, 0.85, 0.80),
            (7.0, 2.3, 0.75, 0.82),
        )

    def _surface_scale(self, x: int, y: int) -> float:
        scale = 1.0
        for crater_x, crater_y, radius, crater_scale in self.craters:
            distance = math.hypot(x - crater_x, y - crater_y)
            if distance < radius:
                # Soft crater interiors avoid single-pixel visual noise.
                influence = 1.0 - distance / radius
                scale *= 1.0 - (1.0 - crater_scale) * influence

        # A few lighter highlands keep the full moon from appearing flat.
        highland = math.exp(-((x - 6.0) ** 2 + (y - 11.8) ** 2) / 5.0)
        return min(1.08, scale + highland * 0.08)

    def update(self, leds: list, frame: int) -> None:
        for i in range(NUM_LEDS):
            leds[i] = (0, 0, 0)

        # Light starts behind the moon (new), moves around one side to full,
        # then continues around the other side back to new. This naturally
        # produces waxing/waning crescents and a curved terminator.
        phase = (frame % self.cycle_frames) / self.cycle_frames
        light_angle = math.pi - math.tau * phase
        light_x = math.sin(light_angle)
        light_z = math.cos(light_angle)

        for y in range(HEIGHT):
            for x in range(WIDTH):
                dx = (x - self.cx) / self.radius
                dy = (y - self.cy) / self.radius
                distance_sq = dx * dx + dy * dy
                if distance_sq > 1.0:
                    continue

                # Front-facing hemisphere normal and directional sunlight.
                normal_z = math.sqrt(max(0.0, 1.0 - distance_sq))
                light_dot = dx * light_x + normal_z * light_z

                # Use a narrow, softly feathered terminator instead of broad
                # Lambert shading. The lit area is therefore nearly uniform,
                # making the curved crescent silhouette obvious at 16x16.
                feather = 0.10
                illumination = max(0.0, min(1.0, (light_dot + feather) / (2.0 * feather)))
                illumination = illumination * illumination * (3.0 - 2.0 * illumination)

                # Earthshine keeps the complete cratered disc visible behind
                # the bright phase. A cooler dark-side tint separates it from
                # direct warm sunlight instead of washing out the crescent.
                limb = normal_z ** 0.35
                lit_surface = (0.78 + 0.22 * normal_z) * illumination
                earthshine = 0.075 * limb
                surface_scale = self._surface_scale(x, y)
                earthshine *= surface_scale
                sunlight = 0.925 * lit_surface * surface_scale

                # Warm ivory/yellow lunar palette with slightly cooler shadows.
                red = int(105 * earthshine + 246 * sunlight)
                green = int(112 * earthshine + 226 * sunlight)
                blue = int(135 * earthshine + 166 * sunlight)
                leds[xy_to_index(x, y)] = (
                    min(255, red),
                    min(255, green),
                    min(255, blue),
                )
