/*
 * DiffusePanel - Halloween Patterns with Auto-Cycling
 * ===================================================
 * Separate seasonal firmware containing the Halloween patterns.
 * Define POWER_WALL for 2.5A wall adapter, otherwise defaults to USB-safe.
 */

#include <FastLED.h>

// === Power Profile ===
// Uncomment ONE of the following:
// #define POWER_WALL

#ifdef POWER_WALL
  #define BRIGHTNESS       255    // Full range; FastLED power cap keeps draw safe
  #define MAX_MILLIAMPS    2500   // 2.5A wall supply
  // At 2500mA / 256 LEDs ≈ 9.8mA per LED headroom.
  // With sparse blob patterns (~20-30% lit), effective per-pixel brightness is high.
  // FastLED dynamically scales if a frame would exceed the cap.
#else
  #define BRIGHTNESS       150    // Conservative for USB
  #define MAX_MILLIAMPS    400    // USB-safe power cap
#endif

// === Hardware Configuration ===
#define DATA_PIN    D0
#define LED_TYPE    WS2812B
#define COLOR_ORDER GRB

// === Panel Configuration ===
#define WIDTH       16
#define HEIGHT      16
#define NUM_LEDS    (WIDTH * HEIGHT)

// === Pattern Cycling ===
#define PATTERN_DURATION_MS  10000  // 10 seconds per pattern (temporary USB test setting)
#define TRANSITION_MS        1000   // 1 second fade transitions
#define NUM_PATTERNS         6

CRGB leds[NUM_LEDS];
uint32_t frame = 0;
uint8_t currentPattern = 0;
uint32_t lastPatternSwitch = 0;
bool transitioning = false;
uint32_t transitionStart = 0;
bool fadingIn = true;  // true = fading in at start, false = fading out before switch

// Forward declarations for structs (needed by Arduino auto-prototyping)
struct BokehOrb;
void bokehResetOrb(BokehOrb &o);

// === Coordinate Mapping (serpentine wiring) ===
uint16_t xyToIndex(uint8_t x, uint8_t y) {
  if (y % 2 == 0) {
    return y * WIDTH + x;
  } else {
    return y * WIDTH + (WIDTH - 1 - x);
  }
}

// === Shared slow rainbow hue (full spectrum cycle) ===
// Completes one full cycle every ~70 seconds at 60fps
static uint8_t hueOffset = 0;  // Random start hue, re-rolled each pattern switch
static int8_t hueDirection = 1;  // +1 or -1, randomized each pattern switch

uint8_t getSharedHue() {
  return (uint8_t)(frame * 0.06f * hueDirection) + hueOffset;
}

static inline float smoothstep(float t) {
  t = constrain(t, 0.0f, 1.0f);
  return t * t * (3.0f - 2.0f * t);
}

// ============================================================
// ============================================================
// Pattern: Botanical Field (smooth noise-driven green canopy)
// ============================================================

// Spike-safe 2D noise. FastLED's inoise8() wrapper has a sign-overflow bug:
// inoise8_raw() can return -65 (one below its -64 floor); the wrapper then does
// n = raw + 64 = -1 (int8_t) and qadd8(n, n) reinterprets -1 as 255 -> a lone
// blazing pixel. Clamping raw to -64 before scaling removes the spike at its
// source with zero false positives (raw only dips below -64 during the bug).
static inline uint8_t inoise8_fixed(uint16_t x, uint16_t y) {
  int8_t raw = inoise8_raw(x, y);
  if (raw < -64) raw = -64;
  uint8_t n = (uint8_t)(raw + 64);  // 0..128
  return qadd8(n, n);               // 0..255, matches inoise8() scaling
}

static int8_t botanicalDirX = 1;  // +1 or -1
static int8_t botanicalDirY = 1;  // +1 or -1
static uint16_t botanicalOriginX = 0;  // Random noise-space origin, re-rolled each cycle
static uint16_t botanicalOriginY = 0;
static CRGB botanicalShown[WIDTH][HEIGHT];  // smoothed per-frame display buffer

// Per-frame temporal smoothing (out of 256): how far each pixel eases toward
// its freshly computed target each frame. Lower = smoother/softer (less
// flicker), higher = snappier. Smooths out the discrete integer-time stepping
// and low-brightness quantization that can read as flicker.
#define GRASS_SMOOTH 90

void featheredGrassInit() {
  botanicalDirX = (random8() < 128) ? 1 : -1;
  botanicalDirY = (random8() < 128) ? 1 : -1;
  // Random origin shifts which region of the (periodic, continuous) noise field
  // we view, so the canopy texture AND drift differ each cycle/boot instead of
  // always settling into the same look.
  botanicalOriginX = random16();
  botanicalOriginY = random16();
  fill_solid((CRGB *)botanicalShown, WIDTH * HEIGHT, CRGB::Black);
}

void patternFeatheredGrass() {
  uint32_t ms = millis();

  // Time offsets: two different speeds, direction randomized at init.
  // Divisors bumped ~44% from the original (9->14, 12->19) to slow the drift.
  // Negation is done by subtracting from 0 -- uint16_t wrapping is fine for noise input
  uint16_t rawX = (uint16_t)(ms / 14);
  uint16_t rawY = (uint16_t)(ms / 19);
  uint16_t timeX = (botanicalDirX > 0) ? rawX : (uint16_t)(0 - rawX);
  uint16_t timeY = (botanicalDirY > 0) ? rawY : (uint16_t)(0 - rawY);

  // Scale determines noise feature size
  uint16_t fieldScale = 24;

  for (uint8_t x = 0; x < WIDTH; x++) {
    for (uint8_t y = 0; y < HEIGHT; y++) {

      // Map grid to moving noise space (origin randomized per cycle)
      uint16_t noiseX = (y * fieldScale) + timeX + botanicalOriginX;
      uint16_t noiseY = (x * fieldScale) + timeY + botanicalOriginY;

      // Master intensity map (spike-safe: clamps FastLED's raw sign overflow)
      uint8_t intensity = inoise8_fixed(noiseX, noiseY);

      // Secondary hue morph (independent offset)
      uint8_t hueMorph = inoise8_fixed(noiseX + 5000, noiseY + 3000);

      // Nature palette: warm leaf-green (90) to pure green (104). Kept below
      // the jade/teal zone (hue ~112+) where FastLED's green->aqua ramp adds a
      // blue component that reads as a cold blue tint.
      uint8_t baseHue = map(hueMorph, 0, 255, 90, 104);
      uint8_t saturation = 245;

      // Brightness: dark lows, moderate highs
      uint8_t brightness = map(intensity, 0, 255, 10, 110);

      CRGB cellColor = CHSV(baseHue, saturation, brightness);

      // Highlight glow: golden accent at intensity peaks
      if (intensity > 185) {
        uint8_t blendAmount = map(intensity, 185, 255, 0, 120);
        cellColor = blend(cellColor, CRGB(180, 200, 20), blendAmount);
      }

      // Ease the shown pixel toward the target so discrete time-stepping and
      // low-brightness quantization don't read as flicker.
      nblend(botanicalShown[x][y], cellColor, GRASS_SMOOTH);
      leds[xyToIndex(x, y)] = botanicalShown[x][y];
    }
  }
}

// ============================================================
// Pattern: Bokeh
// Soft glowing orbs that fade in/out independently per LED.
// ============================================================
#define BOKEH_STATE_SLEEPING   0
#define BOKEH_STATE_FADING_IN  1
#define BOKEH_STATE_HOLDING    2
#define BOKEH_STATE_FADING_OUT 3

struct BokehOrb {
  uint8_t state;
  uint16_t frameInState;
  uint16_t sleepFrames;
  uint16_t fadeInDuration;
  uint16_t holdDuration;
  uint16_t fadeOutDuration;
  uint8_t maxBrightness;
  uint8_t blooms;       // bool
  uint8_t bloomAmount;
};

static BokehOrb bokehOrbs[NUM_LEDS];

#define BOKEH_SAT 240

void bokehResetOrb(BokehOrb &o) {
  o.state = BOKEH_STATE_SLEEPING;
  o.frameInState = 0;
  o.sleepFrames = random16(30, 200);
  o.fadeInDuration = random8(40, 120);
  o.holdDuration = random8(20, 80);
  o.fadeOutDuration = random8(50, 150);
  o.maxBrightness = random8(140, 255);
  o.blooms = (random8() < 102) ? 1 : 0;  // ~40%
  o.bloomAmount = o.blooms ? random8(80, 160) : 0;
}

void bokehInit() {
  for (uint16_t i = 0; i < NUM_LEDS; i++) {
    bokehResetOrb(bokehOrbs[i]);
    bokehOrbs[i].sleepFrames = random16(0, 180);  // stagger starts
  }
}

void patternBokeh() {
  // Cycle in orange range (hue 16-22) with random start
  uint8_t hue = 16 + (sin8((frame / 4) + hueOffset) * 6 / 255);
  uint8_t palSat = BOKEH_SAT;

  for (uint16_t i = 0; i < NUM_LEDS; i++) {
    BokehOrb &o = bokehOrbs[i];
    o.frameInState++;

    uint8_t brightness = 0;
    uint8_t sat = palSat;

    switch (o.state) {
      case BOKEH_STATE_SLEEPING:
        if (o.frameInState >= o.sleepFrames) {
          o.state = BOKEH_STATE_FADING_IN;
          o.frameInState = 0;
        }
        leds[i] = CRGB::Black;
        continue;

      case BOKEH_STATE_FADING_IN: {
        float t = smoothstep((float)o.frameInState / o.fadeInDuration);
        brightness = (uint8_t)(o.maxBrightness * t);
        if (o.frameInState >= o.fadeInDuration) {
          o.state = BOKEH_STATE_HOLDING;
          o.frameInState = 0;
        }
        break;
      }

      case BOKEH_STATE_HOLDING: {
        brightness = o.maxBrightness;
        float t = (float)o.frameInState / o.holdDuration;
        if (o.blooms) {
          sat = max(0, (int16_t)palSat - (int16_t)(o.bloomAmount * smoothstep(t)));
        }
        if (o.frameInState >= o.holdDuration) {
          o.state = BOKEH_STATE_FADING_OUT;
          o.frameInState = 0;
        }
        break;
      }

      case BOKEH_STATE_FADING_OUT: {
        float t = smoothstep(1.0f - (float)o.frameInState / o.fadeOutDuration);
        brightness = (uint8_t)(o.maxBrightness * t);
        float bloomRemaining = max(0.0f, 1.0f - (float)o.frameInState / o.fadeOutDuration);
        if (o.blooms) {
          sat = max(0, (int16_t)palSat - (int16_t)(o.bloomAmount * bloomRemaining));
        }
        if (o.frameInState >= o.fadeOutDuration) {
          bokehResetOrb(o);
        }
        break;
      }
    }

    if (brightness > 0) {
      leds[i] = CHSV(hue, sat, brightness);
    } else {
      leds[i] = CRGB::Black;
    }
  }
}

// ============================================================
// Pattern: Ripple
// Expanding ring ripples from random points, like raindrops.
// ============================================================
#define RIPPLE_MAX_ACTIVE 4

struct RippleSource {
  float x, y;
  float radius;
  float speed;
  float maxRadius;
  float ringWidth;
  uint8_t hue;
  bool active;
};

static RippleSource ripples[RIPPLE_MAX_ACTIVE];
static int16_t rippleSpawnCooldown = 0;

void rippleInit() {
  for (uint8_t i = 0; i < RIPPLE_MAX_ACTIVE; i++) {
    ripples[i].active = false;
  }
  rippleSpawnCooldown = 0;
}

void patternRipple() {
  // Spawn logic
  rippleSpawnCooldown--;
  uint8_t activeCount = 0;
  for (uint8_t i = 0; i < RIPPLE_MAX_ACTIVE; i++) {
    if (ripples[i].active) activeCount++;
  }

  if (rippleSpawnCooldown <= 0 && activeCount < RIPPLE_MAX_ACTIVE) {
    for (uint8_t i = 0; i < RIPPLE_MAX_ACTIVE; i++) {
      if (!ripples[i].active) {
        ripples[i].x = 2.0f + random8(0, WIDTH - 4);
        ripples[i].y = 2.0f + random8(0, HEIGHT - 4);
        ripples[i].radius = 0.0f;
        ripples[i].speed = 0.05f + random8(0, 5) / 100.0f;
        ripples[i].maxRadius = 10.0f + random8(0, 8);
        ripples[i].ringWidth = 2.2f;
        // Teal / cyan / aqua range (hue 120-170, avoids full green)
        ripples[i].hue = 120 + random8(0, 50);
        ripples[i].active = true;
        break;
      }
    }
    rippleSpawnCooldown = random16(140, 207);
  }

  // Clear
  fill_solid(leds, NUM_LEDS, CRGB::Black);

  // Draw ripples
  for (uint8_t y = 0; y < HEIGHT; y++) {
    for (uint8_t x = 0; x < WIDTH; x++) {
      uint16_t idx = xyToIndex(x, y);
      float totalIntensity = 0.0f;
      float blendedHue = 0.0f;

      for (uint8_t i = 0; i < RIPPLE_MAX_ACTIVE; i++) {
        if (!ripples[i].active) continue;
        float dx = x - ripples[i].x;
        float dy = y - ripples[i].y;
        float dist = sqrtf(dx * dx + dy * dy);
        float ringDist = fabsf(dist - ripples[i].radius);
        if (ringDist > ripples[i].ringWidth) continue;

        float ringIntensity = 1.0f - (ringDist / ripples[i].ringWidth);
        float ageFade = 1.0f - (ripples[i].radius / ripples[i].maxRadius);
        float intensity = ringIntensity * ageFade * ageFade;

        totalIntensity += intensity;
        blendedHue += ripples[i].hue * intensity;
      }

      if (totalIntensity > 0.0f) {
        uint8_t hue = (uint8_t)((int)(blendedHue / totalIntensity) % 256);
        uint8_t brightness = min(200, (int)(totalIntensity * 200));
        leds[idx] = CHSV(hue, 240, brightness);
      }
    }
  }

  // Advance and cull
  for (uint8_t i = 0; i < RIPPLE_MAX_ACTIVE; i++) {
    if (!ripples[i].active) continue;
    ripples[i].radius += ripples[i].speed;
    if (ripples[i].radius >= ripples[i].maxRadius) {
      ripples[i].active = false;
    }
  }
}

// ============================================================
// Pattern: Ring Fade
// A thick glowing ring where a wave front sweeps around,
// changing the ring color behind it to a new hue.
// ============================================================
static float ringStartAngle = 0.0f;
static float ringDirection = 1.0f;  // +1 or -1
static float ringWaveAngle = 0.0f;
static uint8_t ringCurrentHue = 0;
static uint8_t ringNextHue = 0;
static float ringLastWaveAngle = 0.0f;
static float ringAccumulated = 0.0f;
static uint8_t ringBaseHueOffset = 0;  // Random start color

void ringFadeInit() {
  ringStartAngle = random16(0, 628) / 100.0f;  // Random start 0 to 2*PI
  ringDirection = (random8() < 128) ? 1.0f : -1.0f;  // Random direction
  ringCurrentHue = random8();
  ringNextHue = ringCurrentHue + 50 + random8(0, 40);
  ringWaveAngle = ringStartAngle;
  ringLastWaveAngle = ringWaveAngle;
  ringAccumulated = 0.0f;
  ringBaseHueOffset = random8();  // Start at random color
}

void patternRingFade() {
  const float cx = (WIDTH - 1) / 2.0f;
  const float cy = (HEIGHT - 1) / 2.0f;
  const float ringRadius = 5.8f;
  const float ringThickness = 2.8f;

  // How fast the "peak" rotates around the ring
  const float peakRotateSpeed = 0.035f;
  // How fast the base hue drifts through the spectrum
  const float hueShiftSpeed = 0.12f;
  // How many hue steps the peak deviates from the base
  const float peakDeviation = 50.0f;

  float peakAngle = fmodf(frame * peakRotateSpeed * ringDirection + ringStartAngle, 2.0f * PI);
  float baseHue = fmodf(frame * hueShiftSpeed * hueDirection + ringBaseHueOffset + 256.0f, 256.0f);

  for (uint8_t y = 0; y < HEIGHT; y++) {
    for (uint8_t x = 0; x < WIDTH; x++) {
      uint16_t idx = xyToIndex(x, y);
      float dx = x - cx;
      float dy = y - cy;
      float dist = sqrtf(dx * dx + dy * dy);
      float ringDist = fabsf(dist - ringRadius);

      if (ringDist < ringThickness) {
        // Quadratic falloff at edges
        float t = 1.0f - (ringDist / ringThickness);
        float ringFade = t * t;

        float pixelAngle = atan2f(dy, dx);

        // Angular distance from the peak (0 to PI)
        float angDist = fmodf(fabsf(pixelAngle - peakAngle) + 4.0f * PI, 2.0f * PI);
        if (angDist > PI) angDist = 2.0f * PI - angDist;

        // Smooth bell curve: full deviation at peak, zero at opposite side
        float peakInfluence = 0.5f * (1.0f + cosf(angDist));

        // Hue = base hue + peak deviation scaled by influence
        float hueF = baseHue + peakDeviation * peakInfluence;
        uint8_t hue = (uint8_t)((int)(hueF + 256.0f) % 256);

        uint8_t rawBrightness = (uint8_t)(190.0f * ringFade);
        if (rawBrightness == 0) {
          leds[idx] = CRGB::Black;
          continue;
        }

        leds[idx] = CHSV(hue, 230, rawBrightness);
      } else {
        leds[idx] = CRGB::Black;
      }
    }
  }
}

// ============================================================
// Pattern: Starfield
// Twinkling points at varied brightness. Cool white with
// occasional warm yellow or cyan-white tinted stars.
// ============================================================
#define STAR_COUNT       50     // Max simultaneous twinkling stars

struct Star {
  float fx, fy;       // Sub-pixel position for anti-aliasing
  uint16_t age;
  uint16_t fadeInLen;
  uint16_t holdLen;
  uint16_t fadeOutLen;
  uint8_t maxBri;
  uint8_t hue;
  uint8_t sat;
  bool active;
};

static Star stars[STAR_COUNT];
static uint8_t starSpawnTimer = 0;
static float starLissT = 0.0f;        // Parameter along Lissajous curve
static float starLissA = 3.0f;        // X frequency
static float starLissB = 2.0f;        // Y frequency
static float starLissDelta = 0.0f;    // Phase offset

#define STAR_SPAWN_INTERVAL 3   // Spawn one star every 3 frames (~20 per second)
#define STAR_LISS_STEP 0.37f    // How far along the curve each spawn advances

void starfieldInit() {
  for (uint8_t i = 0; i < STAR_COUNT; i++) {
    stars[i].active = false;
  }
  starSpawnTimer = 0;
  starLissT = random16(0, 628) / 100.0f;  // Random start point on curve
  // Pick from irrational-ratio pairs so the curve never repeats
  uint8_t pick = random8(0, 5);
  switch (pick) {
    case 0: starLissA = 3.0f;  starLissB = 2.236f; break;  // √5
    case 1: starLissA = 2.0f;  starLissB = 3.1416f; break; // π (was 3+π, too fast)
    case 2: starLissA = 2.0f;  starLissB = 2.618f; break;  // φ+1 (golden)
    case 3: starLissA = 2.618f; starLissB = 2.0f; break;   // φ+1 (was 4+π, too fast)
    case 4: starLissA = 2.236f; starLissB = 3.0f; break;   // √5
  }
  starLissDelta = random16(0, 628) / 100.0f;  // Random phase offset
}

static void starSpawn(uint8_t idx) {
  Star &s = stars[idx];
  // Position from Lissajous curve, mapped to panel coordinates (sub-pixel)
  float rawX = sinf(starLissA * starLissT + starLissDelta);  // -1 to 1
  float rawY = sinf(starLissB * starLissT);                   // -1 to 1
  s.fx = (rawX * 0.45f + 0.5f) * (WIDTH - 1);   // 0.0 .. WIDTH-1
  s.fy = (rawY * 0.45f + 0.5f) * (HEIGHT - 1);  // 0.0 .. HEIGHT-1
  // Clamp
  if (s.fx < 0.0f) s.fx = 0.0f;
  if (s.fx > WIDTH - 1) s.fx = WIDTH - 1;
  if (s.fy < 0.0f) s.fy = 0.0f;
  if (s.fy > HEIGHT - 1) s.fy = HEIGHT - 1;
  // Gentle velocity compensation: slightly larger steps at slow points
  float dx = starLissA * cosf(starLissA * starLissT + starLissDelta);
  float dy = starLissB * cosf(starLissB * starLissT);
  float speed = sqrtf(dx * dx + dy * dy);
  float maxSpeed = sqrtf(starLissA * starLissA + starLissB * starLissB);
  // Blend between 1.0 and a mild boost (max 1.5x) at slow points
  float speedRatio = speed / maxSpeed;  // 0 to 1
  float speedFactor = 1.0f + (1.0f - speedRatio) * 0.5f;  // 1.0 to 1.5
  float baseStep = 0.02f + random8(0, 3) / 100.0f;  // 0.02–0.05 (~30% slower)
  starLissT += baseStep * speedFactor;
  s.age = 0;
  s.fadeInLen = 8;
  s.holdLen = 15;
  s.fadeOutLen = 40;
  s.maxBri = 255;  // Always reach full brightness
  // Pure white with slight blue tint
  s.hue = 160;
  s.sat = 30 + random8(0, 30);  // 30-60, subtle blue-white
  s.active = true;
}

void patternStarfield() {
  fill_solid(leds, NUM_LEDS, CRGB::Black);

  // --- Twinkling stars ---
  starSpawnTimer++;
  if (starSpawnTimer >= STAR_SPAWN_INTERVAL) {
    starSpawnTimer = 0;
    for (uint8_t i = 0; i < STAR_COUNT; i++) {
      if (!stars[i].active) {
        starSpawn(i);
        break;
      }
    }
  }

  for (uint8_t i = 0; i < STAR_COUNT; i++) {
    Star &s = stars[i];
    if (!s.active) continue;
    s.age++;

    uint16_t totalLife = s.fadeInLen + s.holdLen + s.fadeOutLen;
    if (s.age >= totalLife) {
      s.active = false;
      continue;
    }

    float t;
    if (s.age < s.fadeInLen) {
      t = (float)s.age / s.fadeInLen;
      t = t * t;  // Ease-in
    } else if (s.age < s.fadeInLen + s.holdLen) {
      t = 1.0f;
    } else {
      uint16_t fadeAge = s.age - s.fadeInLen - s.holdLen;
      t = 1.0f - (float)fadeAge / s.fadeOutLen;
      t = t * t;  // Ease-out
    }

    uint8_t bri = (uint8_t)(t * s.maxBri);
    if (bri < 2) continue;

    // Bilinear anti-alias: splat brightness across up to 4 neighbouring pixels
    uint8_t x0 = (uint8_t)s.fx;
    uint8_t y0 = (uint8_t)s.fy;
    uint8_t x1 = (x0 < WIDTH - 1)  ? x0 + 1 : x0;
    uint8_t y1 = (y0 < HEIGHT - 1) ? y0 + 1 : y0;
    float xf = s.fx - x0;  // Fractional part 0..1
    float yf = s.fy - y0;
    // Weights for the 4 corners
    float w00 = (1.0f - xf) * (1.0f - yf);
    float w10 = xf * (1.0f - yf);
    float w01 = (1.0f - xf) * yf;
    float w11 = xf * yf;
    CHSV color(s.hue, s.sat, 0);
    uint8_t b;
    b = (uint8_t)(bri * w00); if (b > 1) { color.val = b; leds[xyToIndex(x0, y0)] += color; }
    b = (uint8_t)(bri * w10); if (b > 1) { color.val = b; leds[xyToIndex(x1, y0)] += color; }
    b = (uint8_t)(bri * w01); if (b > 1) { color.val = b; leds[xyToIndex(x0, y1)] += color; }
    b = (uint8_t)(bri * w11); if (b > 1) { color.val = b; leds[xyToIndex(x1, y1)] += color; }
  }
}

// ============================================================
// Halloween Pattern: Purple / Orange Ring Fade
// ============================================================
static float halloweenRingStartAngle = 0.0f;
static float halloweenRingDirection = 1.0f;
static CRGB halloweenRingBaseColor;
static CRGB halloweenRingWaveColor;

void halloweenRingInit() {
  halloweenRingStartAngle = random16(0, 628) / 100.0f;
  halloweenRingDirection = (random8() < 128) ? 1.0f : -1.0f;
  if (random8() < 128) {
    halloweenRingBaseColor = CRGB(255, 72, 0);
    halloweenRingWaveColor = CRGB(150, 0, 255);
  } else {
    halloweenRingBaseColor = CRGB(150, 0, 255);
    halloweenRingWaveColor = CRGB(255, 72, 0);
  }
}

void patternHalloweenRing() {
  const float cx = (WIDTH - 1) / 2.0f;
  const float cy = (HEIGHT - 1) / 2.0f;
  const float ringRadius = 5.7f;
  const float ringThickness = 2.7f;
  float peakAngle = halloweenRingStartAngle + halloweenRingDirection * frame * 0.035f;

  for (uint8_t y = 0; y < HEIGHT; y++) {
    for (uint8_t x = 0; x < WIDTH; x++) {
      float dx = x - cx;
      float dy = y - cy;
      float ringDistance = fabsf(sqrtf(dx * dx + dy * dy) - ringRadius);
      uint16_t idx = xyToIndex(x, y);
      if (ringDistance >= ringThickness) {
        leds[idx] = CRGB::Black;
        continue;
      }

      float edge = 1.0f - ringDistance / ringThickness;
      edge *= edge;
      float pixelAngle = atan2f(dy, dx);
      float angleDistance = fabsf(fmodf(pixelAngle - peakAngle + 3.0f * PI,
                                        2.0f * PI) - PI);
      float wave = 0.5f * (1.0f + cosf(angleDistance));
      wave = wave * wave * wave * wave;
      CRGB color = blend(halloweenRingBaseColor, halloweenRingWaveColor,
                         (uint8_t)(wave * 255.0f));
      uint8_t scale = (uint8_t)(255.0f * edge * (0.72f + 0.28f * wave));
      color.nscale8_video(scale);
      leds[idx] = color;
    }
  }
}

// ============================================================
// Halloween Pattern: Flowing Green Ooze
// ============================================================
static float flowFront[WIDTH];
static float flowSpeed[WIDTH];
static float flowLength[WIDTH];
static bool flowThickTip[WIDTH];

void halloweenFlowInit() {
  for (uint8_t x = 0; x < WIDTH; x++) {
    flowFront[x] = -12.0f + random8(0, 140) / 10.0f;
    flowSpeed[x] = 0.018f + random8(0, 38) / 1000.0f;
    flowLength[x] = 18.0f + random8(0, 101) / 10.0f;
    flowThickTip[x] = random8() < 85;
  }
}

void renderHalloweenFlow(const CRGB &background, const CRGB &stream,
                         const CRGB &brightTip, const CRGB &innerTip) {
  fill_solid(leds, NUM_LEDS, background);

  for (uint8_t x = 0; x < WIDTH; x++) {
    flowFront[x] += flowSpeed[x];
    float tail = flowFront[x] - flowLength[x];
    if (tail > HEIGHT - 1) {
      flowFront[x] = -10.0f + random8(0, 91) / 10.0f;
      flowSpeed[x] = 0.018f + random8(0, 38) / 1000.0f;
      flowLength[x] = 18.0f + random8(0, 101) / 10.0f;
      flowThickTip[x] = random8() < 85;
      tail = flowFront[x] - flowLength[x];
    }

    for (uint8_t y = 0; y < HEIGHT; y++) {
      if (y < tail || y > flowFront[x]) continue;
      float depth = max(0.0f, flowFront[x] - y);
      float shimmer = 0.80f + 0.20f * sinf(frame * 0.08f + x * 1.7f + y * 0.3f);
      float brightness = (0.42f + 0.58f * expf(-depth / 8.0f)) * shimmer;
      CRGB color = stream;
      color.nscale8_video((uint8_t)(brightness * 255.0f));
      leds[xyToIndex(x, y)] = color;
    }

    int16_t tip = (int16_t)flowFront[x];
    if (flowThickTip[x] && tip >= 0 && tip < HEIGHT) {
      leds[xyToIndex(x, tip)] = brightTip;
      if (tip > 0) leds[xyToIndex(x, tip - 1)] = innerTip;
    }
  }
}

void patternFlowingSlime() {
  renderHalloweenFlow(CRGB(2, 0, 0), CRGB(235, 10, 8),
                      CRGB(255, 50, 20), CRGB(175, 5, 5));
}

// ============================================================
// Halloween Pattern: Pac-Man Ghost (White)
// Classic arcade ghost silhouette recolored ivory. Rounded dome, a
// feathered 3-lobe sine-wave hem, constant-speed bob, and eyes that
// drift left/right at twice the bob's speed.
// ============================================================
static inline CRGB ghostScale(const CRGB &color, float amount) {
  CRGB c = color;
  c.nscale8_video((uint8_t)constrain(amount * 255.0f, 0.0f, 255.0f));
  return c;
}

void patternPacManGhost() {
  fill_solid(leds, NUM_LEDS, CRGB::Black);

  const float domeRadius = 4.0f;
  const float footCenter = 12.5f;
  const float footAmplitude = 1.3f;
  const uint8_t footPeriods = 3;
  const uint16_t bobToggleFrames = 90;  // constant bob cadence; eyes move at 2x this rate

  float pulse = 0.85f + 0.15f * ((sinf(frame * 0.06f) + 1.0f) / 2.0f);
  CRGB body = ghostScale(CRGB(255, 244, 205), pulse);
  uint8_t bob = (frame / bobToggleFrames) % 2;
  uint8_t eyeDx = (frame / (bobToggleFrames / 2)) % 2;

  // Gently sway the wave's phase so the feet sway side to side.
  float phaseShift = sinf(frame * 0.05f) * 1.2f;
  float angularFreq = 2.0f * PI * footPeriods / 14.0f;

  for (uint8_t i = 0; i < 14; i++) {
    uint8_t x = i + 1;

    // Smooth circular corner: how far this column is inset from the top,
    // rounded to a hard-edged row (no feathering on the dome).
    float edgeDist = min((float)(x - 1), (float)(14 - x));
    edgeDist = constrain(edgeDist, 0.0f, domeRadius);
    float topF = domeRadius - sqrtf(max(0.0f, domeRadius * domeRadius -
                                             (domeRadius - edgeDist) * (domeRadius - edgeDist)));
    int16_t fullTop = (int16_t)roundf(topF) + bob;

    float wave = sinf((i + phaseShift) * angularFreq + PI / 2.0f);
    float bottomF = footCenter + wave * footAmplitude;

    int16_t fullBottom = (int16_t)floorf(bottomF) + bob;
    float fracBottom = bottomF - floorf(bottomF);

    for (int16_t y = fullTop; y <= fullBottom; y++) {
      if (y >= 0 && y < HEIGHT) leds[xyToIndex(x, y)] = body;
    }

    // Feather only the hem's final row by its fractional coverage.
    if (fracBottom > 0.02f && fullBottom + 1 >= 0 && fullBottom + 1 < HEIGHT) {
      leds[xyToIndex(x, fullBottom + 1)] = ghostScale(body, fracBottom);
    }
  }

  // Eyes are dark cutouts with a small cyan dot that drifts left/right at
  // twice the bob's speed (vertical position still follows the bob).
  static const uint8_t eyeXs[] = {4, 10};
  for (uint8_t e = 0; e < 2; e++) {
    uint8_t ex = eyeXs[e];
    for (uint8_t dy = 0; dy < 3; dy++) {
      for (uint8_t dx = 0; dx < 2; dx++) {
        uint8_t y = 5 + dy + bob;
        if (y < HEIGHT) leds[xyToIndex(ex + dx, y)] = CRGB::Black;
      }
    }
    uint8_t py = 6 + bob;
    if (py < HEIGHT) leds[xyToIndex(ex + eyeDx, py)] = CRGB(60, 220, 255);
  }
}

// ============================================================
// Halloween Pattern: Evil Eyes
// ============================================================
static CRGB evilEyeColor;

void evilEyesInit() {
  static const CRGB golds[] = {
    CRGB(255, 150, 0), CRGB(255, 185, 0),
    CRGB(255, 215, 20), CRGB(235, 175, 25)
  };
  evilEyeColor = golds[random8(0, 4)];
}

void patternEvilEyes() {
  fill_solid(leds, NUM_LEDS, CRGB::Black);
  uint16_t cycle = frame % 300;
  float fade;
  if (cycle < 70) fade = (float)cycle / 70.0f;
  else if (cycle < 190) fade = 1.0f;
  else if (cycle < 270) fade = 1.0f - (float)(cycle - 190) / 80.0f;
  else fade = 0.0f;
  fade = smoothstep(fade);

  CRGB eye = evilEyeColor;
  eye.nscale8_video((uint8_t)(fade * 255.0f));
  CRGB pupil(80, 35, 0);
  pupil.nscale8_video((uint8_t)(fade * 255.0f));

  static const uint8_t leftEye[][2] = {
    {0,4}, {1,4}, {2,4}, {3,5}, {4,5}, {5,6}, {6,6},
    {1,5}, {2,5}, {3,6}, {4,6}, {5,7}, {6,7},
    {2,6}, {3,7}, {4,7}
  };
  for (uint8_t i = 0; i < sizeof(leftEye) / sizeof(leftEye[0]); i++) {
    uint8_t x = leftEye[i][0];
    uint8_t y = leftEye[i][1];
    leds[xyToIndex(x, y)] = eye;
    leds[xyToIndex(15 - x, y)] = eye;
  }

  // TODO (optional): use eye here too for a single-color eye shape.
  static const uint8_t pupils[][2] = {{4,6}, {11,6}, {5,6}, {10,6}};
  for (uint8_t i = 0; i < 4; i++) {
    leds[xyToIndex(pupils[i][0], pupils[i][1])] = pupil;
  }
}

// ============================================================
// Halloween Pattern: Breathing Purple Fog
// Purple/lavender counterpart to patternFeatheredGrass().
// ============================================================
static int8_t fogDirX = 1;
static int8_t fogDirY = 1;
static uint16_t fogOriginX = 0;
static uint16_t fogOriginY = 0;
static CRGB fogShown[WIDTH][HEIGHT];

void breathingFogInit() {
  fogDirX = (random8() < 128) ? 1 : -1;
  fogDirY = (random8() < 128) ? 1 : -1;
  fogOriginX = random16();
  fogOriginY = random16();
  fill_solid((CRGB *)fogShown, WIDTH * HEIGHT, CRGB::Black);
}

void patternBreathingFog() {
  uint32_t ms = millis();
  uint16_t rawX = (uint16_t)(ms / 14);
  uint16_t rawY = (uint16_t)(ms / 19);
  uint16_t timeX = (fogDirX > 0) ? rawX : (uint16_t)(0 - rawX);
  uint16_t timeY = (fogDirY > 0) ? rawY : (uint16_t)(0 - rawY);
  const uint16_t fieldScale = 24;

  for (uint8_t x = 0; x < WIDTH; x++) {
    for (uint8_t y = 0; y < HEIGHT; y++) {
      uint16_t noiseX = y * fieldScale + timeX + fogOriginX;
      uint16_t noiseY = x * fieldScale + timeY + fogOriginY;
      uint8_t intensity = inoise8_fixed(noiseX, noiseY);
      uint8_t hueMorph = inoise8_fixed(noiseX + 5000, noiseY + 3000);
      uint8_t hue = map(hueMorph, 0, 255, 182, 207);
      uint8_t brightness = map(intensity, 0, 255, 2, 125);
      CRGB color = CHSV(hue, 235, brightness);
      if (intensity > 185) {
        uint8_t amount = map(intensity, 185, 255, 0, 145);
        color = blend(color, CRGB(190, 135, 255), amount);
      }
      nblend(fogShown[x][y], color, GRASS_SMOOTH);
      leds[xyToIndex(x, y)] = fogShown[x][y];
    }
  }
}

// ============================================================
// Halloween Pattern: Blood Moon Eclipse
// Stationary red-orange sun, moving dark disc, fixed dark-red corona.
// ============================================================
static inline CRGB eclipseMix(const CRGB &a, const CRGB &b, float amount) {
  amount = constrain(amount, 0.0f, 1.0f);
  return CRGB((uint8_t)(a.r + (b.r - (int)a.r) * amount),
              (uint8_t)(a.g + (b.g - (int)a.g) * amount),
              (uint8_t)(a.b + (b.b - (int)a.b) * amount));
}

void patternBloodMoonEclipse() {
  const float cx = (WIDTH - 1) / 2.0f;
  const float cy = (HEIGHT - 1) / 2.0f;
  const float sunRadius = 6.25f;
  const float moonRadius = 6.0f;
  const uint16_t cycleFrame = frame % 1200;  // ~20s at 60 FPS

  // 1s clear, 7s ingress, 1.3s totality, 7s egress, 3.7s clear.
  float moonX;
  if (cycleFrame < 60) {
    moonX = cx + 14.5f;
  } else if (cycleFrame < 480) {
    float progress = smoothstep((float)(cycleFrame - 60) / 420.0f);
    moonX = cx + 14.5f * (1.0f - progress);
  } else if (cycleFrame < 558) {
    moonX = cx;
  } else if (cycleFrame < 978) {
    float progress = smoothstep((float)(cycleFrame - 558) / 420.0f);
    moonX = cx - 14.5f * progress;
  } else {
    moonX = cx - 14.5f;
  }

  float totality = smoothstep(1.0f - fabsf(moonX - cx) / 2.2f);
  float breathe = 0.95f + 0.05f * sinf(frame * 0.022f);

  for (uint8_t y = 0; y < HEIGHT; y++) {
    for (uint8_t x = 0; x < WIDTH; x++) {
      float dx = x - cx;
      float dy = y - cy;
      float sunDistance = sqrtf(dx * dx + dy * dy);
      float moonDx = x - moonX;
      float moonDistance = sqrtf(moonDx * moonDx + dy * dy);
      CRGB color = CRGB::Black;

      if (sunDistance <= sunRadius + 2.0f) {
        float glow = constrain(1.0f - (sunDistance - sunRadius) / 2.0f, 0.0f, 1.0f);
        glow *= glow;
        color = CRGB((uint8_t)(75.0f * glow * breathe),
                     (uint8_t)(3.0f * glow * breathe), 0);
      }

      if (sunDistance <= sunRadius) {
        float radial = max(0.0f, 1.0f - sunDistance / sunRadius);
        float shimmer = 0.97f + 0.03f * sinf(frame * 0.013f + x * 1.3f + y * 0.8f);
        color = eclipseMix(CRGB(220, 22, 0), CRGB(255, 105, 0), radial * 0.85f);
        float intensity = shimmer * breathe;
        color = CRGB((uint8_t)(color.r * intensity),
                     (uint8_t)(color.g * intensity),
                     (uint8_t)(color.b * intensity));
      }

      // Corona width and rays are fixed relative to the SUN, not the moon.
      float coronaDistance = fabsf(sunDistance - sunRadius);
      if (totality > 0.0f && coronaDistance < 0.90f) {
        float corona = (1.0f - coronaDistance / 0.90f) * totality;
        float solarAngle = atan2f(dy, dx);
        float fixedRays = 0.78f + 0.22f * sinf(solarAngle * 8.0f);
        corona *= fixedRays * breathe;
        color = eclipseMix(color, CRGB(155, 5, 2), min(1.0f, corona * 1.35f));
      }

      // A one-LED feather lets each pixel dim gradually under the moving disc.
      float occlusion = smoothstep((moonRadius + 1.05f - moonDistance) / 2.10f);
      leds[xyToIndex(x, y)] = eclipseMix(color, CRGB(1, 0, 2), occlusion);
    }
  }
}

// ============================================================
// Pattern Switching
// ============================================================
typedef void (*PatternFunc)();

PatternFunc patterns[] = {
  patternHalloweenRing,
  patternEvilEyes,
  patternBreathingFog,
  patternFlowingSlime,
  patternBloodMoonEclipse,
  patternPacManGhost,
};

void resetPatternState() {
  // Re-initialize stateful patterns when switching
  // Randomize shared hue offset and direction
  hueOffset = random8();
  hueDirection = (random8() < 128) ? 1 : -1;
  switch (currentPattern) {
    case 0: halloweenRingInit(); break;
    case 1: evilEyesInit(); break;
    case 2: breathingFogInit(); break;
    case 3: halloweenFlowInit(); break;
    case 4: break;  // Eclipse is derived entirely from frame; no state to reset.
    case 5: break;  // Ghost is derived entirely from frame; no state to reset.
  }
}

// ============================================================
// Main
// ============================================================
void setup() {
#ifdef POWER_WALL
  delay(30000);  // 30s startup delay on wall power
#else
  delay(3000);   // 3s startup delay on USB power
#endif
  Serial.begin(115200);
  delay(500);

  // Seed from the ESP32 hardware RNG for unique patterns each boot.
  // esp_random() is a true hardware random source on the ESP32C6 and needs no
  // floating-pin trick. Mix in micros() for a little extra variation.
  uint32_t seed = esp_random() ^ micros();
  randomSeed(seed);
  random16_set_seed(seed & 0xFFFF);

  FastLED.addLeds<LED_TYPE, DATA_PIN, COLOR_ORDER>(leds, NUM_LEDS)
         .setCorrection(TypicalLEDStrip);
  FastLED.setBrightness(BRIGHTNESS);
  FastLED.setMaxPowerInVoltsAndMilliamps(5, MAX_MILLIAMPS);
  FastLED.clear(true);

  // Initialize the first Halloween pattern. Stateful patterns are reset on selection.
  hueOffset = random8();
  halloweenRingInit();

  lastPatternSwitch = millis();
  transitionStart = millis();
  fadingIn = true;
  transitioning = false;
  Serial.println("DiffusePanel Halloween Ready - 6 patterns (10s, 1s fades)");
}

void loop() {
  uint32_t now = millis();
  uint32_t elapsed = now - lastPatternSwitch;

  // Check if it's time to start fading out
  if (!transitioning && elapsed >= (PATTERN_DURATION_MS - TRANSITION_MS)) {
    transitioning = true;
    fadingIn = false;
    transitionStart = now;
  }

  // Run current pattern
  patterns[currentPattern]();

  // Apply fade envelope
  uint8_t fadeBrightness = 255;
  if (fadingIn) {
    // Fade-in at pattern start
    uint32_t fadeElapsed = now - transitionStart;
    if (fadeElapsed < TRANSITION_MS) {
      float t = (float)fadeElapsed / TRANSITION_MS;
      t = t * t * (3.0f - 2.0f * t);  // smoothstep
      fadeBrightness = (uint8_t)(t * 255.0f);
    } else {
      fadingIn = false;  // Fade-in complete
    }
  } else if (transitioning) {
    // Fade-out before pattern switch
    uint32_t fadeElapsed = now - transitionStart;
    if (fadeElapsed < TRANSITION_MS) {
      float t = 1.0f - (float)fadeElapsed / TRANSITION_MS;
      t = t * t * (3.0f - 2.0f * t);  // smoothstep
      fadeBrightness = (uint8_t)(t * 255.0f);
    } else {
      // Transition complete - switch pattern
      transitioning = false;
      fadingIn = true;
      transitionStart = now;
      lastPatternSwitch = now;
      currentPattern = (currentPattern + 1) % NUM_PATTERNS;
      frame = 0;
      FastLED.clear();
      resetPatternState();
      Serial.print("Pattern: ");
      Serial.println(currentPattern);
      fadeBrightness = 0;
    }
  }

  // Dim all LEDs by fade envelope
  if (fadeBrightness < 255) {
    nscale8(leds, NUM_LEDS, fadeBrightness);
  }

  FastLED.show();
  frame++;
  delay(16);  // ~60 FPS
}
