"""
Empirically hunt for the Botanical/Grass "flashing bright pixel" artifact.

This walks the EXACT coordinate space the grass pattern uses on-device and runs
FastLED's bit-accurate inoise8() over it, looking for:

  1. SPATIAL spikes  - a pixel whose intensity differs from ALL its neighbours
                       by a large margin (an isolated dot in an otherwise smooth
                       region). This is what a "bright dot in a dark area" is.
  2. TEMPORAL spikes - a pixel that jumps sharply for a single frame then
                       returns (the "flashing" part).

It also reports the normal distribution of neighbour-to-neighbour deltas so we
know what "large" means, and checks whether the two-sample (n1 vs n2) guard the
firmware now uses would have caught each spike.

Run:
    python grass_noise_scan.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulator.fastled_noise import inoise8

WIDTH = 16
HEIGHT = 16
FIELD_SCALE = 24

# Two-sample guard used in the firmware fix
GUARD_OFFSET_X = 11
GUARD_OFFSET_Y = 7
GUARD_THRESHOLD = 60

# What counts as an isolated spatial spike: pixel exceeds its brightest
# neighbour by at least this much (0..255 intensity scale).
SPATIAL_SPIKE_DELTA = 60


def grass_intensity(x, y, time_x, time_y):
    """Single-sample intensity exactly as the original grass code computed it."""
    noise_x = (y * FIELD_SCALE + time_x) & 0xFFFF
    noise_y = (x * FIELD_SCALE + time_y) & 0xFFFF
    return inoise8(noise_x, noise_y)


def guarded_intensity(x, y, time_x, time_y):
    """Two-sample guard: use n1 unless it disagrees sharply with n2, then min."""
    noise_x = (y * FIELD_SCALE + time_x) & 0xFFFF
    noise_y = (x * FIELD_SCALE + time_y) & 0xFFFF
    n1 = inoise8(noise_x, noise_y)
    n2 = inoise8((noise_x + GUARD_OFFSET_X) & 0xFFFF,
                 (noise_y + GUARD_OFFSET_Y) & 0xFFFF)
    if abs(n1 - n2) > GUARD_THRESHOLD:
        return min(n1, n2)
    return n1


def compute_frame(time_x, time_y, fn):
    return [[fn(x, y, time_x, time_y) for y in range(HEIGHT)] for x in range(WIDTH)]


def neighbours(grid, x, y):
    out = []
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1),
                   (-1, -1), (-1, 1), (1, -1), (1, 1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < WIDTH and 0 <= ny < HEIGHT:
            out.append(grid[nx][ny])
    return out


def find_spatial_spikes(grid):
    """Return list of (x, y, value, brightest_neighbour, delta)."""
    spikes = []
    for x in range(WIDTH):
        for y in range(HEIGHT):
            nb = neighbours(grid, x, y)
            hi = max(nb)
            if grid[x][y] - hi >= SPATIAL_SPIKE_DELTA:
                spikes.append((x, y, grid[x][y], hi, grid[x][y] - hi))
    return spikes


def max_local_delta(grid):
    """Largest single adjacent (4-neighbour) difference anywhere in the frame."""
    m = 0
    for x in range(WIDTH):
        for y in range(HEIGHT):
            for dx, dy in ((1, 0), (0, 1)):
                nx, ny = x + dx, y + dy
                if nx < WIDTH and ny < HEIGHT:
                    m = max(m, abs(grid[x][y] - grid[nx][ny]))
    return m


def main():
    # The device advances time as: rawX = ms/9, rawY = ms/12 (uint16).
    # Direction can be +/- per axis; scan all four sign combinations because
    # the negation path (uint16 wrap) is a prime suspect for discontinuities.
    dir_combos = [(1, 1), (1, -1), (-1, 1), (-1, -1)]

    # Simulate ~10 minutes of runtime at 60fps for each direction combo.
    # 10 min * 60 fps = 36000 frames; step a few frames to keep it quick but
    # dense enough to catch a brief flash.
    FRAME_STEP = 1
    TOTAL_FRAMES = 36000

    total_spatial = 0
    total_temporal = 0
    worst_local = 0
    spatial_examples = []
    temporal_examples = []
    guard_caught = 0
    guard_missed = 0

    for dir_x, dir_y in dir_combos:
        prev_grid = None
        prev_prev_grid = None
        for f in range(0, TOTAL_FRAMES, FRAME_STEP):
            ms = f * 16  # 60fps -> ~16ms/frame
            raw_x = (ms // 9) & 0xFFFF
            raw_y = (ms // 12) & 0xFFFF
            time_x = raw_x if dir_x > 0 else (0 - raw_x) & 0xFFFF
            time_y = raw_y if dir_y > 0 else (0 - raw_y) & 0xFFFF

            grid = compute_frame(time_x, time_y, grass_intensity)

            worst_local = max(worst_local, max_local_delta(grid))

            # Spatial spikes
            for (x, y, val, hi, delta) in find_spatial_spikes(grid):
                total_spatial += 1
                # Does the two-sample guard catch this pixel?
                g = guarded_intensity(x, y, time_x, time_y)
                if g < val:
                    guard_caught += 1
                else:
                    guard_missed += 1
                if len(spatial_examples) < 8:
                    spatial_examples.append(
                        (dir_x, dir_y, f, ms, x, y, val, hi, delta, g))

            # Temporal spikes: pixel jumps up for exactly one frame.
            if prev_grid is not None and prev_prev_grid is not None:
                for x in range(WIDTH):
                    for y in range(HEIGHT):
                        cur = prev_grid[x][y]
                        before = prev_prev_grid[x][y]
                        after = grid[x][y]
                        if cur - before >= 60 and cur - after >= 60:
                            total_temporal += 1
                            if len(temporal_examples) < 8:
                                temporal_examples.append(
                                    (dir_x, dir_y, f - 1, x, y,
                                     before, cur, after))

            prev_prev_grid = prev_grid
            prev_grid = grid

    print("=" * 70)
    print("GRASS NOISE SPIKE SCAN")
    print("=" * 70)
    print(f"Frames scanned per direction : {TOTAL_FRAMES // FRAME_STEP}")
    print(f"Direction combos             : {dir_combos}")
    print(f"Field scale                  : {FIELD_SCALE}")
    print()
    print(f"Worst adjacent delta (normal): {worst_local}  "
          f"(spatial-spike threshold = {SPATIAL_SPIKE_DELTA})")
    print()
    print(f"SPATIAL spikes found         : {total_spatial}")
    print(f"TEMPORAL (1-frame) spikes    : {total_temporal}")
    print()
    if total_spatial:
        print(f"Two-sample guard caught      : {guard_caught}")
        print(f"Two-sample guard MISSED      : {guard_missed}")
        print()
        print("Sample spatial spikes (dirX,dirY,frame,ms,x,y,value,"
              "brightestNeighbour,delta,guardedValue):")
        for e in spatial_examples:
            print("   ", e)
        print()
    if total_temporal:
        print("Sample temporal spikes (dirX,dirY,frame,x,y,"
              "before,peak,after):")
        for e in temporal_examples:
            print("   ", e)
        print()

    if total_spatial == 0 and total_temporal == 0:
        print("RESULT: No spikes found in the grass coordinate walk.")
        print("        The single-pixel-flash is NOT produced by inoise8 in")
        print("        this coordinate space -> root cause lies elsewhere")
        print("        (e.g. power/brightness, WS2812 timing, or rendering).")
    else:
        print("RESULT: Reproduced anomalies above. The coordinates/values are")
        print("        concrete evidence of the inoise8 discontinuity.")


if __name__ == "__main__":
    main()
