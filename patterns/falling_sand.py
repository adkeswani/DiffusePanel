"""
Calming Falling Sand - sparse grains drift down and pile into slow green mounds,
then the whole pile calmly drains out the bottom before refilling. A gentle,
meditative cycle.

Inspired by the FastLED `calmingFallingSand()` sketch, with two changes for a
more soothing feel:

  * Pacing   - the physics step is decoupled from the render framerate and runs
               on a slow fixed interval, so the sand falls with a heavy,
               deliberate pace no matter how fast the simulator refreshes.
  * Clearing - instead of grains randomly dissolving in place (which looks
               muddy and unclear), once the pile fills up the pattern switches
               to a DRAIN phase: spawning stops and the sand pours out the
               bottom row-by-row like an emptying hourglass, then refills.

Grid values (per cell):
    0        empty
    255      active, freshly falling grain (vibrant lime)
    1..254   settled sand ("age", drives the forest-green color gradient)

Note: the original sketch referenced `sandGrid[x][y].status`, which isn't valid
on a plain uint8_t. The intent is "slide diagonally while the grain is still
active/fresh", so we test `cell == 255 or cell > 200`.
"""

import random
from patterns.base import Pattern, WIDTH, HEIGHT, xy_to_index, hsv_to_rgb


# --- Calming pace knobs ------------------------------------------------------

# How often the sand physics advances one step (milliseconds). Larger = slower,
# more meditative. Independent of the simulator's render FPS.
STEP_INTERVAL_MS = 110

# Chance (0..255) per step to spawn a new grain at the top while filling.
SPAWN_CHANCE = 18

# Start draining once this fraction of the grid is occupied.
FILL_THRESHOLD = 0.55

# While draining, remove the bottom row every this many steps (higher = gentler).
DRAIN_EVERY = 2


def _map(x: int, in_min: int, in_max: int, out_min: int, out_max: int) -> int:
    """Integer re-map, matching Arduino's map() (no clamping)."""
    if in_max == in_min:
        return out_min
    return (x - in_min) * (out_max - out_min) // (in_max - in_min) + out_min


def _random8(n: int | None = None) -> int:
    """FastLED random8(): 0..255, or random8(n) -> 0..n-1."""
    if n is None:
        return random.randint(0, 255)
    return random.randint(0, n - 1)


class FallingSand(Pattern):
    name = "Falling Sand"

    def __init__(self):
        super().__init__()
        # sandGrid[x][y] -- column-major to match the sketch's indexing.
        self.grid = [[0 for _ in range(HEIGHT)] for _ in range(WIDTH)]
        self.last_step_ms = 0
        self.draining = False
        self.step_count = 0

    # ------------------------------------------------------------------ #

    def _occupancy(self) -> float:
        filled = sum(1 for col in self.grid for c in col if c > 0)
        return filled / (WIDTH * HEIGHT)

    def _is_empty(self) -> bool:
        return all(c == 0 for col in self.grid for c in col)

    def _spawn(self):
        if _random8() < SPAWN_CHANCE:
            spawn_x = _random8(WIDTH)
            if self.grid[spawn_x][0] == 0:
                self.grid[spawn_x][0] = 255  # brand new active falling grain

    def _drain_bottom(self):
        """Open the floor: clear the bottom row so the pile pours downward."""
        for x in range(WIDTH):
            self.grid[x][HEIGHT - 1] = 0

    def _apply_gravity(self):
        """One physics step: bottom-to-top so grains fall cleanly."""
        grid = self.grid
        for y in range(HEIGHT - 1, -1, -1):
            for x in range(WIDTH):
                cell = grid[x][y]
                if cell <= 0:
                    continue

                # Bottom row: settle (while draining the floor is cleared
                # separately, so grains keep pouring out).
                if y == HEIGHT - 1:
                    if cell == 255:
                        grid[x][y] = 254
                    continue

                # Fall straight down if the cell below is empty.
                if grid[x][y + 1] == 0:
                    grid[x][y + 1] = cell
                    grid[x][y] = 0
                # Otherwise, active/fresh grains slide diagonally to form mounds.
                elif cell == 255 or cell > 200:
                    left_blocked = (x == 0) or (grid[x - 1][y + 1] != 0)
                    right_blocked = (x == WIDTH - 1) or (grid[x + 1][y + 1] != 0)

                    if not left_blocked and not right_blocked:
                        d = -1 if _random8(2) == 0 else 1
                        grid[x + d][y + 1] = 254
                        grid[x][y] = 0
                    elif not left_blocked:
                        grid[x - 1][y + 1] = 254
                        grid[x][y] = 0
                    elif not right_blocked:
                        grid[x + 1][y + 1] = 254
                        grid[x][y] = 0
                    else:
                        # Completely trapped: settle.
                        if cell == 255:
                            grid[x][y] = 254

    def _age(self):
        """Gently age settled sand so mounds drift through the green gradient."""
        grid = self.grid
        for x in range(WIDTH):
            for y in range(HEIGHT):
                cell = grid[x][y]
                if 1 < cell < 255:
                    if _random8() < 12:
                        grid[x][y] = cell - 1

    def _step(self):
        """Advance the whole simulation one deliberate step."""
        self.step_count += 1

        if not self.draining:
            self._spawn()
            self._apply_gravity()
            self._age()
            # Once the pile is high enough, begin the calming drain.
            if self._occupancy() >= FILL_THRESHOLD:
                self.draining = True
        else:
            # Pour the pile out the bottom, gently.
            if self.step_count % DRAIN_EVERY == 0:
                self._drain_bottom()
            self._apply_gravity()
            self._age()
            if self._is_empty():
                self.draining = False

    def _render(self, leds: list):
        for x in range(WIDTH):
            for y in range(HEIGHT):
                idx = xy_to_index(x, y)
                state = self.grid[x][y]

                if state == 255:
                    # Active falling grain: vibrant glowing lime.
                    leds[idx] = hsv_to_rgb(92, 230, 160)
                elif state > 0:
                    # Settled mounds: forest greens fading as they age.
                    hue = _map(state, 1, 254, 115, 98)
                    brightness = _map(state, 1, 254, 8, 90)
                    leds[idx] = hsv_to_rgb(hue, 255, brightness)
                else:
                    leds[idx] = (0, 0, 0)

    # ------------------------------------------------------------------ #

    def update(self, leds: list, frame: int) -> None:
        # Advance physics on a slow fixed interval, independent of render FPS.
        now = self.elapsed()
        while now - self.last_step_ms >= STEP_INTERVAL_MS:
            self.last_step_ms += STEP_INTERVAL_MS
            self._step()

        self._render(leds)
