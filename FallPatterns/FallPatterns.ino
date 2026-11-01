/*
 * DiffusePanel - Fall Patterns with Auto-Cycling
 * ===============================================
 * Separate seasonal firmware containing the Fall/autumn patterns.
 * Define POWER_WALL for 2.5A wall adapter, otherwise defaults to USB-safe.
 *
 * Ported from patterns/fall.py (the Python simulator). The simulator's
 * hsv_to_rgb() is documented as matching FastLED's HSV model, so the same
 * numeric (hue, sat, val) triples from the Python source are fed directly
 * into CHSV() here, matching the convention already used when porting the
 * Halloween patterns.
 */

#include <FastLED.h>

// === Power Profile ===
// Uncomment ONE of the following:
// #define POWER_WALL

#ifdef POWER_WALL
  #define BRIGHTNESS       255    // Full range; FastLED power cap keeps draw safe
  #define MAX_MILLIAMPS    2500   // 2.5A wall supply
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
#define PATTERN_DURATION_MS  20000  // 20 seconds per pattern
#define TRANSITION_MS        1000   // 1 second fade transitions
#define NUM_PATTERNS         5

CRGB leds[NUM_LEDS];
uint32_t frame = 0;
uint8_t currentPattern = 0;
uint32_t lastPatternSwitch = 0;
bool transitioning = false;
uint32_t transitionStart = 0;
bool fadingIn = true;  // true = fading in at start, false = fading out before switch

// === Coordinate Mapping (serpentine wiring) ===
// The physical panel is mounted/wired 90 degrees rotated relative to the
// logical x/y axes used by every pattern (and by the Python simulator), so
// swap axes once here instead of touching each pattern's math.
uint16_t xyToIndex(uint8_t x, uint8_t y) {
  if (x % 2 == 0) {
    return x * HEIGHT + y;
  } else {
    return x * HEIGHT + (HEIGHT - 1 - y);
  }
}

static inline float smoothstep(float t) {
  t = constrain(t, 0.0f, 1.0f);
  return t * t * (3.0f - 2.0f * t);
}

// Uniform float in [lo, hi], matching Python's random.uniform(lo, hi).
static inline float randFloat(float lo, float hi) {
  return lo + (random16(0, 10001) / 10000.0f) * (hi - lo);
}

// Uniform integer in [lo, hi] inclusive, matching Python's random.randint(lo, hi).
static inline int32_t randRange(int32_t lo, int32_t hi) {
  return lo + (int32_t)random16(0, (uint16_t)(hi - lo + 1));
}

// ============================================================
// Pattern: Fall Embers
// Smooth noise-driven canopy, recolored from the shared Botanical Field /
// Feathered Grass noise technique (see HalloweenPatterns.ino and
// DiffusePanelPatterns.ino): same two-noise-channel mechanic, but the
// green midtones become orange, the near-black dark gaps become a dim
// ember red, and the golden highlight accent at intensity peaks is kept
// as-is.
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

static int8_t emberDirX = 1;  // +1 or -1
static int8_t emberDirY = 1;  // +1 or -1
static uint16_t emberOriginX = 0;  // Random noise-space origin, re-rolled each cycle
static uint16_t emberOriginY = 0;
static CRGB emberShown[WIDTH][HEIGHT];  // smoothed per-frame display buffer

// Per-frame temporal smoothing (out of 256): how far each pixel eases toward
// its freshly computed target each frame. Lower = smoother/softer (less
// flicker), higher = snappier.
#define EMBER_SMOOTH 90

void fallEmbersInit() {
  emberDirX = (random8() < 128) ? 1 : -1;
  emberDirY = (random8() < 128) ? 1 : -1;
  // Random origin shifts which region of the (periodic, continuous) noise field
  // we view, so the canopy texture AND drift differ each cycle/boot instead of
  // always settling into the same look.
  emberOriginX = random16();
  emberOriginY = random16();
  fill_solid((CRGB *)emberShown, WIDTH * HEIGHT, CRGB::Black);
}

void patternFallEmbers() {
  uint32_t ms = millis();

  // Time offsets: two different speeds, direction randomized at init.
  uint16_t rawX = (uint16_t)(ms / 14);
  uint16_t rawY = (uint16_t)(ms / 19);
  uint16_t timeX = (emberDirX > 0) ? rawX : (uint16_t)(0 - rawX);
  uint16_t timeY = (emberDirY > 0) ? rawY : (uint16_t)(0 - rawY);

  // Scale determines noise feature size
  uint16_t fieldScale = 24;

  for (uint8_t x = 0; x < WIDTH; x++) {
    for (uint8_t y = 0; y < HEIGHT; y++) {

      // Map grid to moving noise space (origin randomized per cycle)
      uint16_t noiseX = (y * fieldScale) + timeX + emberOriginX;
      uint16_t noiseY = (x * fieldScale) + timeY + emberOriginY;

      // Master intensity map (spike-safe: clamps FastLED's raw sign overflow)
      uint8_t intensity = inoise8_fixed(noiseX, noiseY);

      // Secondary hue jitter (independent offset), layered on top of the
      // intensity-driven base hue below for organic variation.
      uint8_t hueMorph = inoise8_fixed(noiseX + 5000, noiseY + 3000);

      // Ember palette: hue tracks intensity itself -- dim cells read as a
      // dark ember red (hue ~0) instead of fading to black, and bright
      // cells read as orange (hue ~26), with a little jitter from the
      // secondary noise channel. Clamped (not wrapped) so it never dips
      // into pink/magenta at the low end.
      int16_t baseHueRaw = map(intensity, 0, 255, 0, 26);
      int16_t hueJitter = map(hueMorph, 0, 255, -6, 6);
      uint8_t baseHue = (uint8_t)constrain(baseHueRaw + hueJitter, 0, 32);
      uint8_t saturation = 245;

      // Brightness: dark lows, moderate highs (same curve as the source
      // noise mechanic -- just recolored).
      uint8_t brightness = map(intensity, 0, 255, 10, 110);

      CRGB cellColor = CHSV(baseHue, saturation, brightness);

      // Highlight glow: golden accent at intensity peaks (unchanged).
      if (intensity > 185) {
        uint8_t blendAmount = map(intensity, 185, 255, 0, 120);
        cellColor = blend(cellColor, CRGB(180, 200, 20), blendAmount);
      }

      // Ease the shown pixel toward the target so discrete time-stepping and
      // low-brightness quantization don't read as flicker.
      nblend(emberShown[x][y], cellColor, EMBER_SMOOTH);
      leds[xyToIndex(x, y)] = emberShown[x][y];
    }
  }
}

// ============================================================
// Fall color palette
// ============================================================

// Concrete RGB "fall colors" for patterns that pick from a fixed set of
// discrete colors (as opposed to a smoothly crossfading hue).
static const CRGB FALL_COLOR_STOPS[4] = {
  CRGB(255, 195, 25),  // yellow
  CRGB(255, 110, 10),  // orange
  CRGB(210, 35, 10),   // red
  CRGB(120, 65, 20),   // brown
};

struct FallHSV {
  uint8_t hue;
  uint8_t sat;
  uint8_t cap;  // brightness cap -- keeps muted colors (brown) from
                // blowing out to a bright orange at full value.
};

// Same four colors, as (hue, sat, cap) for smooth hue/sat crossfades.
static const FallHSV FALL_PALETTE_HSV[4] = {
  {32, 235, 255},  // yellow
  {20, 255, 255},  // orange
  {0, 230, 230},   // red
  {14, 190, 125},  // brown
};

// The same four stops, but in "bounce"/ping-pong order: yellow -> orange ->
// red -> brown -> red -> orange -> (loops back to yellow).
static const FallHSV FALL_PALETTE_HSV_BOUNCE[6] = {
  {32, 235, 255},  // yellow
  {20, 255, 255},  // orange
  {0, 230, 230},   // red
  {14, 190, 125},  // brown
  {0, 230, 230},   // red
  {20, 255, 255},  // orange
};

#define FALL_PALETTE_HOLD_FRAMES  420  // ~7s at 60fps
#define FALL_PALETTE_FADE_FRAMES  180  // ~3s crossfade
#define FALL_PALETTE_STEP_FRAMES  (FALL_PALETTE_HOLD_FRAMES + FALL_PALETTE_FADE_FRAMES)

// Current (hue, sat, cap) based on frame, slowly and smoothly bouncing back
// and forth through FALL_PALETTE_HSV_BOUNCE.
FallHSV getFallPaletteColor(uint32_t f) {
  const uint8_t numStops = 6;
  uint32_t totalCycle = (uint32_t)FALL_PALETTE_STEP_FRAMES * numStops;
  uint32_t pos = f % totalCycle;

  uint8_t idx = pos / FALL_PALETTE_STEP_FRAMES;
  uint32_t frameInSlot = pos % FALL_PALETTE_STEP_FRAMES;

  FallHSV cur = FALL_PALETTE_HSV_BOUNCE[idx];
  FallHSV nxt = FALL_PALETTE_HSV_BOUNCE[(idx + 1) % numStops];

  if (frameInSlot < FALL_PALETTE_HOLD_FRAMES) {
    return cur;
  }

  float t = (float)(frameInSlot - FALL_PALETTE_HOLD_FRAMES) / FALL_PALETTE_FADE_FRAMES;
  t = smoothstep(t);

  FallHSV result;
  int16_t hueDiff = (int16_t)nxt.hue - (int16_t)cur.hue;
  result.hue = (uint8_t)((int16_t)cur.hue + (int16_t)(hueDiff * t));
  result.sat = (uint8_t)(cur.sat + (int16_t)(nxt.sat - cur.sat) * t);
  result.cap = (uint8_t)(cur.cap + (int16_t)(nxt.cap - cur.cap) * t);
  return result;
}

// ============================================================
// Pattern: Fall Bokeh Mix
// Soft glowing orbs that fade in/out independently per LED, each
// independently picking its own random fall color.
// ============================================================
#define FALL_ORB_SLEEPING   0
#define FALL_ORB_FADING_IN  1
#define FALL_ORB_HOLDING    2
#define FALL_ORB_FADING_OUT 3

struct FallOrb {
  uint8_t state;
  uint16_t frameInState;
  uint16_t sleepFrames;
  uint16_t fadeInDuration;
  uint16_t holdDuration;
  uint16_t fadeOutDuration;
  uint8_t hue;
  uint8_t sat;
  uint8_t cap;
  uint8_t peakBrightness;
};

static FallOrb fallOrbs[NUM_LEDS];

void fallOrbReset(FallOrb &o) {
  o.state = FALL_ORB_SLEEPING;
  o.frameInState = 0;
  o.sleepFrames = randRange(30, 200);
  o.fadeInDuration = randRange(40, 120);
  o.holdDuration = randRange(20, 80);
  o.fadeOutDuration = randRange(50, 150);

  uint8_t stopIdx = randRange(0, 3);
  o.hue = FALL_PALETTE_HSV[stopIdx].hue;
  o.sat = FALL_PALETTE_HSV[stopIdx].sat;
  o.cap = FALL_PALETTE_HSV[stopIdx].cap;

  float brightnessFrac = randFloat(0.55f, 1.0f);
  o.peakBrightness = (uint8_t)(o.cap * brightnessFrac);
}

void fallBokehMixInit() {
  for (uint16_t i = 0; i < NUM_LEDS; i++) {
    fallOrbReset(fallOrbs[i]);
    fallOrbs[i].sleepFrames = randRange(0, 180);  // stagger starts
  }
}

void patternFallBokehMix() {
  for (uint16_t i = 0; i < NUM_LEDS; i++) {
    FallOrb &o = fallOrbs[i];
    o.frameInState++;

    uint8_t brightness = 0;

    switch (o.state) {
      case FALL_ORB_SLEEPING:
        if (o.frameInState >= o.sleepFrames) {
          o.state = FALL_ORB_FADING_IN;
          o.frameInState = 0;
        }
        leds[i] = CRGB::Black;
        continue;

      case FALL_ORB_FADING_IN: {
        float t = smoothstep((float)o.frameInState / o.fadeInDuration);
        brightness = (uint8_t)(o.peakBrightness * t);
        if (o.frameInState >= o.fadeInDuration) {
          o.state = FALL_ORB_HOLDING;
          o.frameInState = 0;
        }
        break;
      }

      case FALL_ORB_HOLDING: {
        brightness = o.peakBrightness;
        if (o.frameInState >= o.holdDuration) {
          o.state = FALL_ORB_FADING_OUT;
          o.frameInState = 0;
        }
        break;
      }

      case FALL_ORB_FADING_OUT: {
        float t = smoothstep(1.0f - (float)o.frameInState / o.fadeOutDuration);
        brightness = (uint8_t)(o.peakBrightness * t);
        if (o.frameInState >= o.fadeOutDuration) {
          fallOrbReset(o);
        }
        break;
      }
    }

    if (brightness > 0) {
      leds[i] = CHSV(o.hue, o.sat, brightness);
    } else {
      leds[i] = CRGB::Black;
    }
  }
}

// ============================================================
// Pattern: Fall Ring Wave
// A thick ring that's always fully lit, with a brighter wave of color
// chasing around it. The ring's base color smoothly bounces through the
// fall color spectrum, and the wave is sampled a full palette-step ahead
// so it's a clearly distinct fall color from the base ring.
// ============================================================
void patternFallRingWave() {
  const float cx = (WIDTH - 1) / 2.0f;
  const float cy = (HEIGHT - 1) / 2.0f;
  const float ringRadius = 5.5f;
  const float ringThickness = 2.5f;
  const float speed = 0.02f;
  const float waveWidth = PI * 0.8f;

  FallHSV base = getFallPaletteColor(frame);
  FallHSV wave = getFallPaletteColor(frame + FALL_PALETTE_STEP_FRAMES);
  float waveAngle = frame * speed;

  for (uint8_t y = 0; y < HEIGHT; y++) {
    for (uint8_t x = 0; x < WIDTH; x++) {
      uint16_t idx = xyToIndex(x, y);

      float dx = x - cx;
      float dy = y - cy;
      float dist = sqrtf(dx * dx + dy * dy);
      float ringDist = fabsf(dist - ringRadius);

      if (ringDist < ringThickness) {
        float ringFade = 1.0f - (ringDist / ringThickness);
        ringFade *= ringFade;

        float pixelAngle = atan2f(dy, dx);
        float angleDiff = fmodf(pixelAngle - waveAngle, 2.0f * PI);
        if (angleDiff < 0) angleDiff += 2.0f * PI;
        if (angleDiff > PI) angleDiff = 2.0f * PI - angleDiff;

        uint8_t pixelHue, pixelSat, pixelCap;
        int16_t brightness;

        if (angleDiff < waveWidth) {
          float t = 1.0f - (angleDiff / waveWidth);
          t = smoothstep(t);

          brightness = (int16_t)((120 + t * 100) * ringFade);
          int16_t hueDiff = (int16_t)wave.hue - (int16_t)base.hue;
          pixelHue = (uint8_t)((int16_t)base.hue + (int16_t)(hueDiff * t));
          pixelSat = (uint8_t)(base.sat + (int16_t)(wave.sat - base.sat) * t);
          pixelCap = (uint8_t)(base.cap + (int16_t)(wave.cap - base.cap) * t);
        } else {
          brightness = (int16_t)(120 * ringFade);
          pixelHue = base.hue;
          pixelSat = base.sat;
          pixelCap = base.cap;
        }

        // Clamp to this color's brightness cap so brown stays muted
        // instead of blowing out to a bright orange.
        brightness = min(brightness, (int16_t)pixelCap);
        leds[idx] = CHSV(pixelHue, pixelSat, (uint8_t)brightness);
      } else {
        leds[idx] = CRGB::Black;
      }
    }
  }
}

// ============================================================
// Pattern: Tumbling Leaves
// Single pixels fall straight down the panel, each a fall color, with
// alternating brightness as they go to mimic a leaf tumbling end over
// end in the wind.
// ============================================================
#define MAX_LEAVES 14

struct TumblingLeaf {
  float x, y;
  float fallSpeed;
  CRGB color;
  float tumbleFreq;
  float tumblePhase;
  float minBrightness;
  int8_t driftDir;
  uint32_t nextDriftFrame;
  bool alive;
};

static TumblingLeaf leaves[MAX_LEAVES];
static int16_t leafSpawnCooldown = 0;

void tumblingLeafReset(TumblingLeaf &l) {
  l.x = (float)randRange(0, WIDTH - 1);
  l.y = randFloat(-4.0f, -0.5f);
  l.fallSpeed = randFloat(0.012f, 0.028f);
  l.color = FALL_COLOR_STOPS[randRange(0, 3)];

  l.tumbleFreq = randFloat(0.15f, 0.35f);
  l.tumblePhase = randFloat(0.0f, 2.0f * PI);
  l.minBrightness = randFloat(0.25f, 0.45f);

  l.driftDir = (int8_t)randRange(-1, 1);
  // Matches the Python source's next_drift_frame = random.randint(20, 60):
  // an absolute (not frame-relative) threshold, so a freshly spawned leaf
  // drifts almost immediately once `frame` has grown past this small value,
  // then schedules correctly (frame + randint(20, 60)) from then on.
  l.nextDriftFrame = randRange(20, 60);

  l.alive = true;
}

void tumblingLeafAdvance(TumblingLeaf &l) {
  l.y += l.fallSpeed;
  l.tumblePhase += l.tumbleFreq;
  if (frame >= l.nextDriftFrame) {
    l.x = constrain(l.x + l.driftDir, 0.0f, (float)(WIDTH - 1));
    l.driftDir = (int8_t)randRange(-1, 1);
    l.nextDriftFrame = frame + randRange(20, 60);
  }
}

float tumblingLeafBrightness(TumblingLeaf &l) {
  float t = (sinf(l.tumblePhase) + 1.0f) / 2.0f;
  return l.minBrightness + (1.0f - l.minBrightness) * t;
}

void tumblingLeavesInit() {
  for (uint8_t i = 0; i < MAX_LEAVES; i++) {
    leaves[i].alive = false;
  }
  leafSpawnCooldown = 0;
}

void patternTumblingLeaves() {
  leafSpawnCooldown--;

  uint8_t aliveCount = 0;
  for (uint8_t i = 0; i < MAX_LEAVES; i++) {
    if (leaves[i].alive) aliveCount++;
  }

  if (leafSpawnCooldown <= 0 && aliveCount < MAX_LEAVES) {
    for (uint8_t i = 0; i < MAX_LEAVES; i++) {
      if (!leaves[i].alive) {
        tumblingLeafReset(leaves[i]);
        break;
      }
    }
    leafSpawnCooldown = randRange(8, 20);
  }

  for (uint8_t i = 0; i < MAX_LEAVES; i++) {
    if (!leaves[i].alive) continue;
    tumblingLeafAdvance(leaves[i]);
    if (leaves[i].y >= HEIGHT + 1) leaves[i].alive = false;
  }

  fill_solid(leds, NUM_LEDS, CRGB::Black);
  for (uint8_t i = 0; i < MAX_LEAVES; i++) {
    if (!leaves[i].alive) continue;
    int x = (int)roundf(leaves[i].x);
    int y = (int)roundf(leaves[i].y);
    if (x >= 0 && x < WIDTH && y >= 0 && y < HEIGHT) {
      CRGB c = leaves[i].color;
      c.nscale8((uint8_t)(tumblingLeafBrightness(leaves[i]) * 255));
      leds[xyToIndex(x, y)] = c;
    }
  }
}

// ============================================================
// Pattern: Leaf Decay
// A full screen of yellow pixels that slowly decays: the color bleeds
// from yellow through orange and red into brown while individual pixels
// fade out one by one, like leaves falling. The last pixels left standing
// trace a branching, vein-like skeleton that itself recedes from its tips
// back to its root -- before everything goes dark and the cycle loops
// back to a fresh, full yellow screen.
// ============================================================
#define FALL_DECAY_CYCLE_FRAMES        2400  // full decay-and-reset cycle length
#define FALL_DECAY_COLOR_FRACTION      0.75f // color reaches brown by 75% through
#define FALL_DECAY_FADE_IN_FRACTION    0.08f // fade back in to full yellow over
                                              // this fraction, right after reset
#define FALL_DECAY_MAX_VEIN_PIXELS     90
#define FALL_DECAY_MAX_TIPS            128

static float fallDisappear[NUM_LEDS];
static float fallFadeOut[NUM_LEDS];

struct FallVeinTip {
  float x, y, drift;
};

void fallLeafDecayBuildOrder() {
  static int16_t veinOrder[WIDTH][HEIGHT];
  for (uint8_t x = 0; x < WIDTH; x++) {
    for (uint8_t y = 0; y < HEIGHT; y++) {
      veinOrder[x][y] = -1;
    }
  }
  uint8_t veinCount = 0;

  static FallVeinTip tipStack[FALL_DECAY_MAX_TIPS];
  uint8_t tipCount = 0;

  const uint8_t numStarts = 5;
  for (uint8_t i = 0; i < numStarts; i++) {
    tipStack[tipCount].x = (float)randRange(2, WIDTH - 3);
    tipStack[tipCount].y = (float)(HEIGHT - 1);
    tipStack[tipCount].drift = randFloat(-0.5f, 0.5f);
    tipCount++;
  }

  while (tipCount > 0 && veinCount < FALL_DECAY_MAX_VEIN_PIXELS) {
    FallVeinTip cur = tipStack[--tipCount];  // pop last, matches Python's list.pop()
    float x = cur.x, y = cur.y, drift = cur.drift;
    uint8_t runLength = randRange(2, 4);
    bool brokeEarly = false;

    for (uint8_t s = 0; s < runLength; s++) {
      int ix = (int)roundf(x);
      int iy = (int)roundf(y);
      if (ix >= 0 && ix < WIDTH && iy >= 0 && iy < HEIGHT &&
          veinOrder[ix][iy] == -1 && veinCount < FALL_DECAY_MAX_VEIN_PIXELS) {
        veinOrder[ix][iy] = veinCount;
        veinCount++;
      }
      y -= 1.0f;
      drift += randFloat(-0.5f, 0.5f);
      drift = constrain(drift, -1.8f, 1.8f);
      x += drift;
      if (y < -1.0f || x < -2.0f || x > WIDTH + 1.0f) {
        brokeEarly = true;
        break;
      }
    }

    if (!brokeEarly && y >= -1.0f && veinCount < FALL_DECAY_MAX_VEIN_PIXELS) {
      bool forks = random8() < 128;  // ~50%, matches random.random() < 0.5
      if (forks && tipCount + 2 <= FALL_DECAY_MAX_TIPS) {
        tipStack[tipCount].x = x;
        tipStack[tipCount].y = y;
        tipStack[tipCount].drift = drift + randFloat(0.3f, 0.8f);
        tipCount++;
        tipStack[tipCount].x = x;
        tipStack[tipCount].y = y;
        tipStack[tipCount].drift = drift - randFloat(0.3f, 0.8f);
        tipCount++;
      } else if (!forks && tipCount + 1 <= FALL_DECAY_MAX_TIPS) {
        tipStack[tipCount].x = x;
        tipStack[tipCount].y = y;
        tipStack[tipCount].drift = drift;
        tipCount++;
      }
    }
  }

  uint8_t maxGrowth = (veinCount > 1) ? (veinCount - 1) : 1;

  for (uint8_t y = 0; y < HEIGHT; y++) {
    for (uint8_t x = 0; x < WIDTH; x++) {
      uint16_t idx = xyToIndex(x, y);
      if (veinOrder[x][y] >= 0) {
        float normalized = (float)veinOrder[x][y] / (float)maxGrowth;
        // Tips (normalized near 1) disappear first within the vein's own
        // late window; roots (near 0) hold on the longest, so the
        // skeleton recedes tip-to-root.
        fallDisappear[idx] = 0.95f - normalized * 0.40f;
        fallFadeOut[idx] = randFloat(0.05f, 0.10f);
      } else {
        fallDisappear[idx] = randFloat(0.05f, 0.8f);
        fallFadeOut[idx] = randFloat(0.03f, 0.08f);
      }
    }
  }
}

// One-way smooth crossfade through yellow -> orange -> red -> brown as t
// goes 0 -> 1 (no bounce -- this only runs once per decay cycle, unlike
// the looping fall palette).
FallHSV fallDecayColor(float t) {
  const uint8_t segments = 3;  // len(FALL_PALETTE_HSV) - 1
  t = constrain(t, 0.0f, 1.0f);
  float pos = t * segments;
  uint8_t idx = (uint8_t)pos;
  if (idx > segments - 1) idx = segments - 1;
  float localT = smoothstep(pos - idx);

  FallHSV cur = FALL_PALETTE_HSV[idx];
  FallHSV nxt = FALL_PALETTE_HSV[idx + 1];

  FallHSV result;
  int16_t hueDiff = (int16_t)nxt.hue - (int16_t)cur.hue;
  result.hue = (uint8_t)((int16_t)cur.hue + (int16_t)(hueDiff * localT));
  result.sat = (uint8_t)(cur.sat + (int16_t)(nxt.sat - cur.sat) * localT);
  result.cap = (uint8_t)(cur.cap + (int16_t)(nxt.cap - cur.cap) * localT);
  return result;
}

void fallLeafDecayInit() {
  fallLeafDecayBuildOrder();
}

void patternFallLeafDecay() {
  uint32_t cycleFrame = frame % FALL_DECAY_CYCLE_FRAMES;
  if (cycleFrame == 0 && frame > 0) {
    fallLeafDecayBuildOrder();
  }
  float tc = (float)cycleFrame / FALL_DECAY_CYCLE_FRAMES;

  FallHSV dc = fallDecayColor(tc / FALL_DECAY_COLOR_FRACTION);

  float fadeIn;
  if (tc < FALL_DECAY_FADE_IN_FRACTION) {
    fadeIn = smoothstep(tc / FALL_DECAY_FADE_IN_FRACTION);
  } else {
    fadeIn = 1.0f;
  }
  uint8_t brightness = (uint8_t)(dc.cap * fadeIn);
  CRGB color = CHSV(dc.hue, dc.sat, brightness);

  for (uint16_t i = 0; i < NUM_LEDS; i++) {
    float disappear = fallDisappear[i];
    float fadeOut = fallFadeOut[i];
    float fadeStart = disappear - fadeOut;

    if (tc >= disappear) {
      leds[i] = CRGB::Black;
    } else if (tc >= fadeStart) {
      float localT = smoothstep((tc - fadeStart) / fadeOut);
      CRGB c = color;
      c.nscale8((uint8_t)((1.0f - localT) * 255));
      leds[i] = c;
    } else {
      leds[i] = color;
    }
  }
}

// ============================================================
// Pattern Switching
// ============================================================
typedef void (*PatternFunc)();

PatternFunc patterns[] = {
  patternFallRingWave,
  patternFallBokehMix,
  patternFallEmbers,
  patternTumblingLeaves,
  patternFallLeafDecay,
};

void resetPatternState() {
  switch (currentPattern) {
    case 0: break;  // Ring Wave is derived entirely from frame; no state to reset.
    case 1: fallBokehMixInit(); break;
    case 2: fallEmbersInit(); break;
    case 3: tumblingLeavesInit(); break;
    case 4: fallLeafDecayInit(); break;
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
  uint32_t seed = esp_random() ^ micros();
  randomSeed(seed);
  random16_set_seed(seed & 0xFFFF);

  FastLED.addLeds<LED_TYPE, DATA_PIN, COLOR_ORDER>(leds, NUM_LEDS)
         .setCorrection(TypicalLEDStrip);
  FastLED.setBrightness(BRIGHTNESS);
  FastLED.setMaxPowerInVoltsAndMilliamps(5, MAX_MILLIAMPS);
  FastLED.clear(true);

  // Initialize the first Fall pattern. Stateful patterns are reset on selection.
  currentPattern = 0;
  resetPatternState();

  lastPatternSwitch = millis();
  transitionStart = millis();
  fadingIn = true;
  transitioning = false;
  Serial.println("DiffusePanel Fall Ready - 5 patterns");
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
      t = smoothstep(t);
      fadeBrightness = (uint8_t)(t * 255.0f);
    } else {
      fadingIn = false;  // Fade-in complete
    }
  } else if (transitioning) {
    // Fade-out before pattern switch
    uint32_t fadeElapsed = now - transitionStart;
    if (fadeElapsed < TRANSITION_MS) {
      float t = 1.0f - (float)fadeElapsed / TRANSITION_MS;
      t = smoothstep(t);
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
