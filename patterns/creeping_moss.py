"""
Creeping Moss - organic cellular growth that fills the panel, then an organic
die-back that creeps across it the same way, in an endless breathing cycle.

Two phases drive the whole animation:

  GROW  - rare spores sprout, mature cells creep into empty neighbors, and the
          colony fills the panel. When it's full enough we switch to...
  DEATH - death starts at a seed cell and spreads cell-to-cell (the same
          creeping mechanic as growth), each infected cell fading out. When the
          panel is empty we switch back to GROW.

Grid values (per cell): 0 = bare, 1..255 = moss "age" (drives color/brightness).
The physics runs on a slow fixed interval (independent of render FPS) to keep
the deliberately sluggish, organic morphing.
"""

import random
from patterns.base import Pattern, WIDTH, HEIGHT, xy_to_index, hsv_to_rgb


# How often the moss simulation advances one step (ms), independent of FPS.
STEP_INTERVAL_MS = 120

# Growth tuning.
SPROUT_START = 20    # age a new cell starts at (dim, so it fades in)
GROW_RATE = 8        # age gained per step while growing (slow fade-in)
SPORE_PEAK = 255     # peak age a spontaneous spore grows to
NEIGHBOR_PEAK = 210  # peak age a spread-to neighbor grows to
SPREAD_CHANCE = 16   # chance (0..255) a mature cell spreads to an empty neighbor
SPREAD_MATURITY = 60  # min age before a cell can spread (decoupled from brightness)
SPORE_CHANCE = 3     # chance (0..255) of a spontaneous new spore each step
FULL_THRESHOLD = 0.92  # occupancy fraction that triggers the death phase

# Death tuning.
DECAY_RATE = 9        # age lost per step once a cell is dying (slow fade-out)
DEATH_SPREAD = 70     # chance (0..255) a dying cell infects a living neighbor
DEATH_SEEDS = 2       # number of initial death seeds when the phase begins

# Neighbor glow: fraction of a lit pixel's color that bleeds into each of its
# 8 neighbors. Kept here to approximate the physical panel's diffuser (the
# hardware sketch disables software glow because the real diffuser does this).
GLOW = 0.28


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


class CreepingMoss(Pattern):
    name = "Creeping Moss"

    def __init__(self):
        super().__init__()
        self.grid = [[0 for _ in range(HEIGHT)] for _ in range(WIDTH)]
        # Per-cell target peak; while age < peak the cell is fading IN.
        self.peak = [[0 for _ in range(HEIGHT)] for _ in range(WIDTH)]
        # Per-cell death flag; a dying cell fades out and infects neighbors.
        self.dying = [[False for _ in range(HEIGHT)] for _ in range(WIDTH)]
        self.phase = "grow"
        self.last_step_ms = 0

    # -- helpers ------------------------------------------------------------- #

    def _sprout(self, grid, peak, x, y, target):
        """Seed a new dim cell that will fade in toward `target`."""
        grid[x][y] = SPROUT_START
        peak[x][y] = target

    def _occupancy(self) -> float:
        filled = sum(1 for col in self.grid for c in col if c > 0)
        return filled / (WIDTH * HEIGHT)

    def _live_cells(self):
        return [
            (x, y)
            for x in range(WIDTH)
            for y in range(HEIGHT)
            if self.grid[x][y] > 0
        ]

    # -- phases -------------------------------------------------------------- #

    def _grow_step(self):
        grid, peak = self.grid, self.peak

        # Spontaneous sprouting (rare seed of new life).
        if _random8() < SPORE_CHANCE:
            sx, sy = _random8(WIDTH), _random8(HEIGHT)
            if grid[sx][sy] == 0:
                self._sprout(grid, peak, sx, sy, SPORE_PEAK)

        nxt = [col[:] for col in grid]
        nxt_peak = [col[:] for col in peak]

        for x in range(WIDTH):
            for y in range(HEIGHT):
                current_age = grid[x][y]
                if current_age <= 0:
                    continue

                # Fade in toward peak; cells then hold at peak (alive).
                if current_age < peak[x][y]:
                    nxt[x][y] = min(peak[x][y], current_age + GROW_RATE)

                # Mature cells creep into an empty neighbor.
                if current_age > SPREAD_MATURITY and _random8() < SPREAD_CHANCE:
                    nx = x + (_random8(3) - 1)
                    ny = y + (_random8(3) - 1)
                    if 0 <= nx < WIDTH and 0 <= ny < HEIGHT:
                        if grid[nx][ny] == 0 and nxt[nx][ny] == 0:
                            self._sprout(nxt, nxt_peak, nx, ny, NEIGHBOR_PEAK)

        self.grid, self.peak = nxt, nxt_peak

        # Panel full enough -> begin the organic die-back.
        if self._occupancy() >= FULL_THRESHOLD:
            self.phase = "death"
            live = self._live_cells()
            random.shuffle(live)
            for (sx, sy) in live[:DEATH_SEEDS]:
                self.dying[sx][sy] = True

    def _death_step(self):
        grid, dying = self.grid, self.dying
        nxt = [col[:] for col in grid]
        nxt_dying = [col[:] for col in dying]

        for x in range(WIDTH):
            for y in range(HEIGHT):
                if grid[x][y] <= 0:
                    continue

                if dying[x][y]:
                    # Fade out.
                    nxt[x][y] = max(0, grid[x][y] - DECAY_RATE)
                    if nxt[x][y] == 0:
                        nxt_dying[x][y] = False
                        self.peak[x][y] = 0

                    # Death creeps into a living neighbor (same mechanic as growth).
                    if _random8() < DEATH_SPREAD:
                        nx = x + (_random8(3) - 1)
                        ny = y + (_random8(3) - 1)
                        if 0 <= nx < WIDTH and 0 <= ny < HEIGHT:
                            if grid[nx][ny] > 0 and not dying[nx][ny]:
                                nxt_dying[nx][ny] = True

        self.grid, self.dying = nxt, nxt_dying

        # Everything gone -> back to growth.
        if self._occupancy() == 0:
            self.phase = "grow"
            return

        # Safeguard: if the death front burned out but survivors remain
        # (isolated pockets the infection never reached), re-seed so the
        # die-back always completes instead of stalling.
        if not any(c for col in self.dying for c in col):
            live = self._live_cells()
            random.shuffle(live)
            for (sx, sy) in live[:DEATH_SEEDS]:
                self.dying[sx][sy] = True

    def _step(self):
        if self.phase == "grow":
            self._grow_step()
        else:
            self._death_step()

    def _render(self, leds: list):
        # Base color per cell.
        base = [[(0, 0, 0)] * HEIGHT for _ in range(WIDTH)]
        for x in range(WIDTH):
            for y in range(HEIGHT):
                age = self.grid[x][y]
                if age > 0:
                    hue = _map(age, 1, 255, 135, 90)         # deep teal -> emerald
                    brightness = _map(age, 1, 255, 2, 110)  # dimmer peak, crisp
                    base[x][y] = hsv_to_rgb(hue, 255, brightness)

        # Composite each pixel plus a soft glow bled in from its 8 neighbors.
        for x in range(WIDTH):
            for y in range(HEIGHT):
                r, g, b = base[x][y]
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < WIDTH and 0 <= ny < HEIGHT:
                            nr, ng, nb = base[nx][ny]
                            r += nr * GLOW
                            g += ng * GLOW
                            b += nb * GLOW
                leds[xy_to_index(x, y)] = (
                    min(255, int(r)),
                    min(255, int(g)),
                    min(255, int(b)),
                )

    def update(self, leds: list, frame: int) -> None:
        now = self.elapsed()
        while now - self.last_step_ms >= STEP_INTERVAL_MS:
            self.last_step_ms += STEP_INTERVAL_MS
            self._step()
        self._render(leds)
