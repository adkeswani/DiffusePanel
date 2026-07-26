"""
Moon - a sphere lit by an orbiting light source.

The light rotates around the sphere, causing the illuminated side
to sweep across the surface like lunar phases. Color slowly cycles.
"""

import math
from patterns.base import Pattern, WIDTH, HEIGHT, NUM_LEDS, xy_to_index, hsv_to_rgb


class Moon(Pattern):
    name = "Moon"

    def __init__(self):
        super().__init__()
        # Sphere geometry
        self.cx = (WIDTH - 1) / 2.0
        self.cy = (HEIGHT - 1) / 2.0
        self.radius = 6.0

        # Light orbit speed: frames for one full orbit
        self.orbit_frames = 600  # ~10 seconds at 60fps

    def update(self, leds: list, frame: int) -> None:
        # Slow continuous hue cycle
        hue = int(frame * 0.08) % 256
        sat = 200

        # Light wanders in 3D using layered sine waves at irrational ratios
        # This creates smooth, never-repeating motion
        t = frame / 60.0  # time in seconds

        # Multiple incommensurate frequencies for each axis
        light_x = (math.sin(t * 0.47) * 0.6
                   + math.sin(t * 0.31 + 1.7) * 0.3
                   + math.sin(t * 0.79 + 4.2) * 0.1)

        light_y = (math.sin(t * 0.53 + 2.1) * 0.6
                   + math.sin(t * 0.37 + 0.3) * 0.3
                   + math.sin(t * 0.83 + 5.1) * 0.1)

        light_z = (math.cos(t * 0.41 + 1.0) * 0.5
                   + math.cos(t * 0.67 + 3.3) * 0.3
                   + 0.3)  # bias toward front so it's not dark too often

        # Normalize to unit direction
        light_len = math.sqrt(light_x * light_x + light_y * light_y + light_z * light_z)
        light_x /= light_len
        light_y /= light_len
        light_z /= light_len

        for y in range(HEIGHT):
            for x in range(WIDTH):
                idx = xy_to_index(x, y)

                dx = x - self.cx
                dy = y - self.cy
                dist = math.sqrt(dx * dx + dy * dy)

                if dist <= self.radius + 3.0:
                    norm_dist = dist / self.radius

                    if norm_dist <= 1.0:
                        # Surface normal of a sphere at this pixel
                        # nx, ny from pixel offset; nz from hemisphere
                        nx = dx / self.radius
                        ny = dy / self.radius
                        nz = math.sqrt(1.0 - norm_dist * norm_dist)

                        # Lambert diffuse: dot(normal, light_dir)
                        dot = nx * light_x + ny * light_y + nz * light_z

                        # Wide wrap lighting: large partial-shade zone
                        # Maps dot from [-1,1] with heavy wrap so the
                        # transition from lit to dark is broad and gradual
                        lit = max(0.0, (dot + 0.7) / 1.7)
                        # Smooth it with a softer curve
                        lit = lit * lit

                        # Ambient so dark side isn't pure black
                        brightness = int(200 * (0.08 + 0.92 * lit))
                    else:
                        # Soft glow beyond sphere edge
                        falloff = max(0.0, 1.0 - (dist - self.radius) / 3.0)
                        glow = falloff * falloff

                        # Glow is stronger on the lit side
                        dx_n = dx / dist
                        dy_n = dy / dist
                        edge_dot = dx_n * light_x + dy_n * light_y
                        edge_lit = max(0.0, (edge_dot + 0.2) / 1.2)

                        brightness = int(60 * glow * edge_lit)

                    if brightness > 1:
                        leds[idx] = hsv_to_rgb(hue, sat, brightness)
                    else:
                        leds[idx] = (0, 0, 0)
                else:
                    leds[idx] = (0, 0, 0)
