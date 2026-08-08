"""
Aurora Borealis - drifting emerald/cyan curtains with vertical folds over a
deep-indigo night sky.

Direct port of the FastLED `auroraBorealisEffect()` sketch, using the
bit-accurate inoise8() so the simulator matches what the ESP32 actually renders.

  * Feathering  - the curtain's bottom edge is softly feathered so it blends
                  out into "space" (as in the original sketch).
  * Fading      - a temporal blend between frames, so the fast-moving curtain
                  folds interpolate smoothly instead of juddering.
"""

from patterns.base import Pattern, WIDTH, HEIGHT, xy_to_index, hsv_to_rgb
from simulator.fastled_noise import inoise8, qadd8


# --- FastLED helpers not in base.py -----------------------------------------

def _map(x: int, in_min: int, in_max: int, out_min: int, out_max: int) -> int:
    """Integer re-map, matching Arduino's map() (no clamping)."""
    if in_max == in_min:
        return out_min
    return (x - in_min) * (out_max - out_min) // (in_max - in_min) + out_min


def _nscale8_video(rgb: tuple, scale: int) -> tuple:
    """
    Scale an RGB color by `scale`/255, FastLED's "video" variant: a non-zero
    channel never fades all the way to zero while `scale` is non-zero. Used for
    the feathered edges so faint aurora light stays faintly visible.
    """
    scale &= 0xFF
    nonzero = 1 if scale else 0
    r, g, b = rgb

    def ch(c: int) -> int:
        if c == 0:
            return 0
        return ((c * scale) >> 8) + nonzero

    return (ch(r), ch(g), ch(b))


# Temporal fade: fraction of the way each pixel moves toward its new target
# per frame (0 = frozen, 1 = no fade / instant like the raw sketch).
FADE = 0.35


class DreamyAurora(Pattern):
    name = "Aurora Borealis"

    def __init__(self):
        super().__init__()
        # Persistent float buffer for temporal fading (r, g, b per LED).
        self.buffer = [[0.0, 0.0, 0.0] for _ in range(WIDTH * HEIGHT)]

    def update(self, leds: list, frame: int) -> None:
        ms = self.elapsed()

        # Speed of the aurora curtains moving across the sky.
        drift_speed = ms // 6
        # Speed of the ripples/folds moving vertically up the curtains.
        wave_speed = ms // 3

        for x in range(WIDTH):
            # Base horizontal shape: tight X stretch gives clean vertical ribbons.
            noise_x = (x * 40) - drift_speed
            curtain_shape = inoise8(noise_x, ms // 20)

            for y in range(HEIGHT):
                # Invert Y so y=0 is the bottom row of the display.
                inv_y = (HEIGHT - 1) - y

                # Vertical folding wave behavior.
                curtain_fold = inoise8(noise_x, (inv_y * 35) + wave_speed)

                # Combine horizontal ribbon location with the vertical folds.
                final_intensity = qadd8(curtain_shape, curtain_fold // 2)

                # --- THE CUTOFF THRESHOLD: dark night sky ---
                if final_intensity < 135:
                    bg_val = _map(final_intensity, 0, 135, 2, 8)
                    color = hsv_to_rgb(175, 255, bg_val)  # deep indigo cosmos

                # --- THE AURORA CURTAIN RENDER ---
                else:
                    brightness = _map(final_intensity, 135, 255, 10, 140)
                    hue = 96  # pure emerald green

                    # Higher pixels morph toward cyan/teal or pinkish-purple.
                    if inv_y > 6:
                        alt_hue = _map(inv_y, 7, HEIGHT - 1, 130, 210)
                        hue = _map(inv_y, 7, HEIGHT - 1, 96, alt_hue)

                    color = hsv_to_rgb(hue, 240, brightness)

                    # Feathered edge: soften the bottom 3 rows into space.
                    if inv_y < 3:
                        color = _nscale8_video(color, _map(inv_y, 0, 2, 40, 255))

                # Added fading: ease the persistent buffer toward the target.
                idx = xy_to_index(x, y)
                buf = self.buffer[idx]
                buf[0] += (color[0] - buf[0]) * FADE
                buf[1] += (color[1] - buf[1]) * FADE
                buf[2] += (color[2] - buf[2]) * FADE

                leds[idx] = (int(buf[0]), int(buf[1]), int(buf[2]))
