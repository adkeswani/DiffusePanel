"""
Ring Fade - a thick circle ring with a wave of color that rotates around it.
LEDs behind the wave fade to black.
"""

import math
from patterns.base import Pattern, WIDTH, HEIGHT, NUM_LEDS, xy_to_index, hsv_to_rgb


class RingFade(Pattern):
    name = "Ring Fade"

    def __init__(self):
        super().__init__()
        # Ring geometry (centered on panel)
        self.cx = (WIDTH - 1) / 2.0
        self.cy = (HEIGHT - 1) / 2.0
        # Ring radius (center of the ring band)
        self.ring_radius = 5.5
        # Thickness of the ring (how far from ring_radius pixels are lit)
        self.ring_thickness = 2.5
        # Wave rotation speed (radians per frame)
        self.speed = 0.02
        # Angular width of the bright wave (radians)
        self.wave_width = math.pi * 0.8

    def update(self, leds: list, frame: int) -> None:
        # Cycling base hue
        base_hue = int(frame * 0.18) % 256

        # Wave angle position
        wave_angle = frame * self.speed

        for y in range(HEIGHT):
            for x in range(WIDTH):
                idx = xy_to_index(x, y)

                dx = x - self.cx
                dy = y - self.cy
                dist = math.sqrt(dx * dx + dy * dy)

                # How far this pixel is from the ring band
                ring_dist = abs(dist - self.ring_radius)

                if ring_dist < self.ring_thickness:
                    # Inside the ring band — compute radial falloff
                    ring_fade = 1.0 - (ring_dist / self.ring_thickness)
                    ring_fade = ring_fade * ring_fade  # Soft edge

                    # Angular position of this pixel
                    pixel_angle = math.atan2(dy, dx)

                    # Angular distance from wave center (wrapped)
                    angle_diff = (pixel_angle - wave_angle) % (2 * math.pi)
                    if angle_diff > math.pi:
                        angle_diff = 2 * math.pi - angle_diff

                    if angle_diff < self.wave_width:
                        # Inside the wave: bright
                        t = 1.0 - (angle_diff / self.wave_width)
                        t = t * t * (3.0 - 2.0 * t)  # smoothstep

                        brightness = int((60 + t * 180) * ring_fade)
                        hue = int(base_hue + t * 40) % 256
                        sat = int(220 - t * 40)
                    else:
                        # Behind the wave: fade to black
                        brightness = int(40 * ring_fade)
                        hue = base_hue
                        sat = 200

                    leds[idx] = hsv_to_rgb(hue, sat, brightness)
                else:
                    leds[idx] = (0, 0, 0)
