/*
 * DiffusePanel - Arduino Pattern Template
 * ========================================
 * This sketch mirrors the Python simulator's pattern API.
 * To port a pattern from the simulator:
 *   1. Copy the update() logic into the corresponding updatePattern() function
 *   2. Replace Python math with Arduino equivalents (see mapping below)
 *
 * === Python -> Arduino Mapping ===
 *
 *   Python                     Arduino/FastLED
 *   ------                     ---------------
 *   hsv_to_rgb(h, s, v)        CHSV(h, s, v)
 *   leds[idx] = (r, g, b)      leds[idx] = CRGB(r, g, b)
 *   xy_to_index(x, y)          xyToIndex(x, y)
 *   math.sin(x)                sin8(x) or sin16(x)
 *   random.randint(a, b)       random8(a, b) or random16(a, b)
 *   frame counter              Passed as argument or use millis()
 *   WIDTH, HEIGHT              WIDTH, HEIGHT (constants below)
 */

#include <FastLED.h>

// === Hardware Configuration ===
#define DATA_PIN    D0
#define LED_TYPE    WS2812B
#define COLOR_ORDER GRB
#define BRIGHTNESS  150

// === Panel Configuration ===
#define WIDTH       16
#define HEIGHT      16
#define NUM_LEDS    (WIDTH * HEIGHT)

CRGB leds[NUM_LEDS];
uint32_t frame = 0;

// === Coordinate Mapping (serpentine wiring) ===
uint16_t xyToIndex(uint8_t x, uint8_t y) {
  if (y % 2 == 0) {
    return y * WIDTH + x;
  } else {
    return y * WIDTH + (WIDTH - 1 - x);
  }
}

// === Pattern: Rainbow Wave ===
// Ported from: patterns/rainbow_wave.py
void patternRainbowWave() {
  for (uint8_t y = 0; y < HEIGHT; y++) {
    for (uint8_t x = 0; x < WIDTH; x++) {
      uint8_t hue = (x * 8 + y * 8 + frame * 2) % 256;
      uint16_t idx = xyToIndex(x, y);
      leds[idx] = CHSV(hue, 255, 255);
    }
  }
}

// === Pattern: Plasma ===
// Ported from: patterns/plasma.py
void patternPlasma() {
  uint8_t t = frame;
  for (uint8_t y = 0; y < HEIGHT; y++) {
    for (uint8_t x = 0; x < WIDTH; x++) {
      // Use sin8 for fast integer sine (0-255 output)
      uint8_t v1 = sin8(x * 19 + t * 3);
      uint8_t v2 = sin8(y * 19 + t * 2);
      uint8_t v3 = sin8((x + y) * 13 + t);
      uint8_t v4 = sin8(sqrt16(x * x * 64 + y * y * 64) + t * 4);

      uint8_t hue = (v1 + v2 + v3 + v4) / 4;
      uint16_t idx = xyToIndex(x, y);
      leds[idx] = CHSV(hue, 255, 255);
    }
  }
}

// === Pattern: Fire ===
// Ported from: patterns/fire.py
static uint8_t heat[HEIGHT][WIDTH];

void patternFire() {
  uint8_t cooling = 55;
  uint8_t sparking = 120;

  for (uint8_t x = 0; x < WIDTH; x++) {
    // Cool down
    for (uint8_t y = 0; y < HEIGHT; y++) {
      uint8_t cool = random8(0, ((cooling * 10) / HEIGHT) + 2);
      heat[y][x] = qsub8(heat[y][x], cool);
    }

    // Heat rises
    for (uint8_t y = HEIGHT - 1; y >= 2; y--) {
      heat[y][x] = (heat[y-1][x] + heat[y-2][x] + heat[y-2][x]) / 3;
    }

    // Sparks
    if (random8() < sparking) {
      uint8_t sy = random8(0, 2);
      heat[sy][x] = qadd8(heat[sy][x], random8(160, 255));
    }
  }

  // Map heat to colors
  for (uint8_t y = 0; y < HEIGHT; y++) {
    for (uint8_t x = 0; x < WIDTH; x++) {
      uint16_t idx = xyToIndex(x, y);
      // HeatColor is a built-in FastLED function
      leds[idx] = HeatColor(heat[y][x]);
    }
  }
}

// === Main ===
void setup() {
  Serial.begin(115200);
  delay(500);

  FastLED.addLeds<LED_TYPE, DATA_PIN, COLOR_ORDER>(leds, NUM_LEDS)
         .setCorrection(TypicalLEDStrip);
  FastLED.setBrightness(BRIGHTNESS);
  FastLED.clear(true);

  // Initialize heat map
  memset(heat, 0, sizeof(heat));

  Serial.println("DiffusePanel Ready");
}

void loop() {
  // Change which pattern function is called here:
  patternRainbowWave();
  // patternPlasma();
  // patternFire();

  FastLED.show();
  frame++;
  delay(16);  // ~60 FPS
}
