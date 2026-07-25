"""
Base class for LED panel patterns.

All patterns inherit from this and implement update().
The API is designed to closely mirror what you'd write in Arduino/FastLED,
making porting straightforward.
"""

import math
import time


# Panel dimensions
WIDTH = 16
HEIGHT = 16
NUM_LEDS = WIDTH * HEIGHT


def xy_to_index(x: int, y: int) -> int:
    """
    Convert (x, y) coordinate to linear LED index.
    Assumes serpentine/zigzag wiring (even rows L->R, odd rows R->L).
    This matches the BTF-LIGHTING panel wiring.
    """
    if y % 2 == 0:
        return y * WIDTH + x
    else:
        return y * WIDTH + (WIDTH - 1 - x)


def index_to_xy(index: int) -> tuple[int, int]:
    """Convert linear LED index back to (x, y) coordinate."""
    y = index // WIDTH
    if y % 2 == 0:
        x = index % WIDTH
    else:
        x = (WIDTH - 1) - (index % WIDTH)
    return x, y


def hsv_to_rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
    """
    Convert HSV to RGB.
    h: 0-255 (wraps), s: 0-255, v: 0-255
    Returns (r, g, b) each 0-255.
    Matches FastLED's HSV model for easy porting.
    """
    h = (h % 256) / 255.0 * 360.0
    s = s / 255.0
    v = v / 255.0

    c = v * s
    x = c * (1 - abs((h / 60.0) % 2 - 1))
    m = v - c

    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x

    return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))


def millis() -> int:
    """Return milliseconds since epoch, like Arduino millis()."""
    return int(time.time() * 1000)


class Pattern:
    """
    Base class for all LED patterns.

    Subclass this and implement:
      - name: class variable with display name
      - update(self, leds, frame): fill the leds array each frame

    The leds array is a list of NUM_LEDS tuples: (r, g, b).
    frame is an incrementing counter.
    """

    name: str = "Unnamed Pattern"

    def __init__(self):
        """Override for pattern-specific initialization."""
        self.start_time = millis()

    def update(self, leds: list, frame: int) -> None:
        """
        Update the LED buffer. Override this in your pattern.

        Args:
            leds: list of NUM_LEDS items, each (r, g, b). Modify in place.
            frame: frame counter (increments each tick)
        """
        raise NotImplementedError

    def elapsed(self) -> int:
        """Milliseconds since pattern started."""
        return millis() - self.start_time
