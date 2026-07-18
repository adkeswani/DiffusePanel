#include <FastLED.h>

// === Configuration ===
#define NUM_LEDS    256
#define DATA_PIN    D0      // Xiao ESP32C6 pin connected to WS2812B data line
#define BRIGHTNESS  255     // Max brightness during fade peak
#define LED_TYPE    WS2812B
#define COLOR_ORDER GRB

// Fade speed: lower = slower fade, higher = faster
// Each step delays this many milliseconds
#define FADE_DELAY_MS 1

// Brightness increment per fade step (1-85). Larger = faster fade, fewer steps.
// Must divide evenly into 255 for a clean fade (e.g. 1, 3, 5, 15, 17, 51, 85)
#define FADE_STEP 85

CRGB leds[NUM_LEDS];

// Color test patterns: R, G, B, R+G, G+B, R+B, R+G+B
const CRGB testColors[] = {
  CRGB(1, 0, 0),  // Red
  CRGB(0, 1, 0),  // Green
  CRGB(0, 0, 1),  // Blue
  CRGB(1, 1, 0),  // Red + Green (Yellow)
  CRGB(0, 1, 1),  // Green + Blue (Cyan)
  CRGB(1, 0, 1),  // Red + Blue (Magenta)
  CRGB(1, 1, 1),  // Red + Green + Blue (White)
};
const uint8_t NUM_COLORS = sizeof(testColors) / sizeof(testColors[0]);

void setup() {
  Serial.begin(115200);
  delay(500);

  FastLED.addLeds<LED_TYPE, DATA_PIN, COLOR_ORDER>(leds, NUM_LEDS)
         .setCorrection(TypicalLEDStrip);
  FastLED.setBrightness(BRIGHTNESS);

  // Start with all LEDs off
  FastLED.clear(true);

  Serial.println("=== WS2812B Panel Test ===");
  Serial.print("LEDs: "); Serial.println(NUM_LEDS);
  Serial.print("Colors to test: "); Serial.println(NUM_COLORS);
}

// Fade a single LED up from 0 to 255 then back down to 0 for a given color
void fadePixel(uint16_t pixel, CRGB color) {
  // Ramp up: 0 -> 255
  for (uint16_t bright = 0; bright <= 255; bright += FADE_STEP) {
    leds[pixel].r = color.r * bright;
    leds[pixel].g = color.g * bright;
    leds[pixel].b = color.b * bright;
    FastLED.show();
    delay(FADE_DELAY_MS);
  }

  // Ramp down: 255 -> 0
  for (int16_t bright = 255; bright >= 0; bright -= FADE_STEP) {
    leds[pixel].r = color.r * bright;
    leds[pixel].g = color.g * bright;
    leds[pixel].b = color.b * bright;
    FastLED.show();
    delay(FADE_DELAY_MS);
  }

  // Guarantee LED is fully off
  leds[pixel] = CRGB::Black;
  FastLED.show();
}

void loop() {
  const char* colorNames[] = {
    "Red", "Green", "Blue",
    "Yellow (R+G)", "Cyan (G+B)", "Magenta (R+B)",
    "White (R+G+B)"
  };

  for (uint8_t c = 0; c < NUM_COLORS; c++) {
    Serial.print("Testing color: ");
    Serial.println(colorNames[c]);

    for (uint16_t i = 0; i < NUM_LEDS; i++) {
      fadePixel(i, testColors[c]);
    }

    // Brief pause between color rounds
    delay(200);
  }

  Serial.println("=== Full cycle complete, restarting ===");
  delay(1000);
}
