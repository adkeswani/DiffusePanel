"""
DiffusePanel LED Simulator
===========================
A 16x16 LED panel simulator using pygame-ce.

Controls:
  Left/Right arrows or A/D  - Switch patterns
  Up/Down arrows or W/S     - Adjust speed (FPS)
  Space                     - Pause/resume
  R                         - Reset current pattern
  G                         - Toggle grid lines
  B                         - Cycle brightness
  Q / Escape                - Quit

Run:
  python simulator/main.py
"""

import sys
import os

# Add project root to path so patterns can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from patterns import ALL_PATTERNS
from patterns.base import NUM_LEDS, WIDTH, HEIGHT, xy_to_index

# === Display Configuration ===
# Physical board: 5mm LED diameter, 5mm gap between LEDs
# So pitch (center-to-center) = diameter + gap = 10mm
# We map 5mm diameter -> LED_RADIUS pixels, 5mm gap -> GAP pixels
LED_DIAMETER = 20       # Pixels for the 5mm LED diameter
LED_RADIUS = LED_DIAMETER // 2
LED_GAP = 20            # Pixels for the 5mm gap between LEDs
CELL_PITCH = LED_DIAMETER + LED_GAP  # Center-to-center distance
PANEL_PADDING = 30      # Padding around the panel
LED_ALPHA = 153         # ~60% opacity (0.6 * 255)

# Calculate window dimensions
PANEL_WIDTH = (WIDTH - 1) * CELL_PITCH + LED_DIAMETER
PANEL_HEIGHT = (HEIGHT - 1) * CELL_PITCH + LED_DIAMETER
INFO_HEIGHT = 60       # Space for text info at the bottom
WINDOW_WIDTH = PANEL_WIDTH + 2 * PANEL_PADDING
WINDOW_HEIGHT = PANEL_HEIGHT + 2 * PANEL_PADDING + INFO_HEIGHT

# Colors
BG_COLOR = (20, 20, 25)
GRID_COLOR = (40, 40, 45)
TEXT_COLOR = (200, 200, 200)
HIGHLIGHT_COLOR = (100, 200, 255)

# Timing
DEFAULT_FPS = 60
MIN_FPS = 10
MAX_FPS = 120
FPS_STEP = 5


def draw_panel(screen: pygame.Surface, leds: list, show_grid: bool, brightness: float):
    """Draw the LED panel to the screen as semi-transparent circles."""
    # Create a surface with per-pixel alpha for the LED circles
    led_surface = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)

    for y in range(HEIGHT):
        for x in range(WIDTH):
            idx = xy_to_index(x, y)
            r, g, b = leds[idx]

            # Apply brightness
            r = int(r * brightness)
            g = int(g * brightness)
            b = int(b * brightness)

            # Calculate center of this LED circle
            cx = PANEL_PADDING + x * CELL_PITCH + LED_RADIUS
            cy = PANEL_PADDING + y * CELL_PITCH + LED_RADIUS

            # Draw filled circle with alpha
            pygame.draw.circle(led_surface, (r, g, b, LED_ALPHA), (cx, cy), LED_RADIUS)

            # Optional grid: draw circle outline
            if show_grid:
                pygame.draw.circle(led_surface, (*GRID_COLOR, 100), (cx, cy), LED_RADIUS, width=1)

    screen.blit(led_surface, (0, 0))


def draw_info(screen: pygame.Surface, font: pygame.font.Font, pattern_name: str,
              pattern_idx: int, num_patterns: int, fps: int, target_fps: int,
              paused: bool, brightness: float):
    """Draw the info bar at the bottom."""
    y_base = WINDOW_HEIGHT - INFO_HEIGHT + 10

    # Pattern name and index
    status = " [PAUSED]" if paused else ""
    text = f"Pattern: {pattern_name} ({pattern_idx + 1}/{num_patterns}){status}"
    surf = font.render(text, True, HIGHLIGHT_COLOR)
    screen.blit(surf, (PANEL_PADDING, y_base))

    # FPS and brightness
    bright_pct = int(brightness * 100)
    info = f"FPS: {fps}/{target_fps}  |  Brightness: {bright_pct}%  |  [A/D] Pattern  [W/S] Speed  [G]rid  [B]right  [Space] Pause"
    surf = font.render(info, True, TEXT_COLOR)
    screen.blit(surf, (PANEL_PADDING, y_base + 22))


def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("DiffusePanel Simulator - 16x16 LED")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 14)

    # State
    pattern_idx = 0
    patterns = [P() for P in ALL_PATTERNS]
    leds = [(0, 0, 0)] * NUM_LEDS
    frame = 0
    target_fps = DEFAULT_FPS
    paused = False
    show_grid = True
    brightness = 1.0
    brightness_levels = [1.0, 0.75, 0.5, 0.25, 0.1]
    brightness_idx = 0

    running = True
    while running:
        # === Event Handling ===
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_q, pygame.K_ESCAPE):
                    running = False

                # Pattern switching
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    pattern_idx = (pattern_idx + 1) % len(patterns)
                    frame = 0
                    leds = [(0, 0, 0)] * NUM_LEDS
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    pattern_idx = (pattern_idx - 1) % len(patterns)
                    frame = 0
                    leds = [(0, 0, 0)] * NUM_LEDS

                # Speed control
                elif event.key in (pygame.K_UP, pygame.K_w):
                    target_fps = min(MAX_FPS, target_fps + FPS_STEP)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    target_fps = max(MIN_FPS, target_fps - FPS_STEP)

                # Pause
                elif event.key == pygame.K_SPACE:
                    paused = not paused

                # Reset pattern
                elif event.key == pygame.K_r:
                    patterns[pattern_idx] = ALL_PATTERNS[pattern_idx]()
                    frame = 0
                    leds = [(0, 0, 0)] * NUM_LEDS

                # Grid toggle
                elif event.key == pygame.K_g:
                    show_grid = not show_grid

                # Brightness cycle
                elif event.key == pygame.K_b:
                    brightness_idx = (brightness_idx + 1) % len(brightness_levels)
                    brightness = brightness_levels[brightness_idx]

        # === Update ===
        if not paused:
            patterns[pattern_idx].update(leds, frame)
            frame += 1

        # === Draw ===
        screen.fill(BG_COLOR)
        draw_panel(screen, leds, show_grid, brightness)

        actual_fps = int(clock.get_fps())
        draw_info(screen, font, patterns[pattern_idx].name, pattern_idx,
                  len(patterns), actual_fps, target_fps, paused, brightness)

        pygame.display.flip()
        clock.tick(target_fps)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
