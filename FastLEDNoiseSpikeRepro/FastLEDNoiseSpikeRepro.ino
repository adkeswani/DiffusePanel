/*
 * FastLED inoise8() 2D value-overflow reproducer
 * ==============================================
 * Demonstrates that the scaled 2D inoise8(x, y) can return 255 (full white)
 * at isolated coordinates where the surrounding field is near-zero, producing
 * a single blazing "spark" pixel in an otherwise dark region.
 *
 * Root cause:
 *   inoise8_raw(x, y) is documented to return roughly -64..+64, but it can
 *   return -65 (one below the floor). The scaled wrapper then does:
 *
 *       int8_t n = inoise8_raw(x, y);   // -65
 *       n += 64;                        // -1  (still int8_t)
 *       uint8_t ans = qadd8(n, n);      // (uint8_t)(-1) = 255 -> qadd8(255,255)=255
 *
 *   The negative intermediate is reinterpreted as unsigned 255 and saturates,
 *   so a value that should map to ~0 becomes 255.
 *
 * This sketch scans a block of the 2D noise field and prints every coordinate
 * where inoise8_raw < -64 together with the resulting inoise8 value and the
 * value of the four orthogonal neighbours (to show it is an isolated spike).
 *
 * Expected serial output (abridged):
 *   SPIKE at (x=2944, y=2442): raw=-65  inoise8=255  neighbours[L,R,U,D]=0,0,2,0
 *   ...
 *   Scan complete. Spikes found: N
 *
 * Tested on: <fill in your board, e.g. Seeed XIAO ESP32C6, FastLED 3.x>
 *
 * NOTE: This runs entirely in setup(); it needs no LEDs connected.
 */

#include <FastLED.h>

// Scan window. The overflow is rare (~0.0003% of coordinates), so scan a
// reasonably large block. Adjust as needed; this covers the region containing
// the known example spike at (2944, 2442).
static const uint16_t X_START = 2800;
static const uint16_t X_END   = 3100;
static const uint16_t Y_START = 2300;
static const uint16_t Y_END   = 2600;

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println();
  Serial.println("FastLED inoise8() 2D overflow scan");
  Serial.print("FastLED version: ");
  Serial.println(FASTLED_VERSION);
  Serial.println("Scanning for inoise8_raw(x,y) < -64 ...");

  uint32_t spikes = 0;

  for (uint32_t x = X_START; x <= X_END; x++) {
    for (uint32_t y = Y_START; y <= Y_END; y++) {
      int8_t raw = inoise8_raw((uint16_t)x, (uint16_t)y);
      if (raw < -64) {
        uint8_t val = inoise8((uint16_t)x, (uint16_t)y);

        // Orthogonal neighbours to show the spike is isolated
        uint8_t nl = inoise8((uint16_t)(x - 1), (uint16_t)y);
        uint8_t nr = inoise8((uint16_t)(x + 1), (uint16_t)y);
        uint8_t nu = inoise8((uint16_t)x, (uint16_t)(y - 1));
        uint8_t nd = inoise8((uint16_t)x, (uint16_t)(y + 1));

        Serial.print("SPIKE at (x=");
        Serial.print(x);
        Serial.print(", y=");
        Serial.print(y);
        Serial.print("): raw=");
        Serial.print(raw);
        Serial.print("  inoise8=");
        Serial.print(val);
        Serial.print("  neighbours[L,R,U,D]=");
        Serial.print(nl); Serial.print(",");
        Serial.print(nr); Serial.print(",");
        Serial.print(nu); Serial.print(",");
        Serial.println(nd);

        spikes++;
      }
    }
  }

  Serial.print("Scan complete. Spikes found: ");
  Serial.println(spikes);
  Serial.println();
  Serial.println("Each SPIKE line shows a pixel that renders at 255 (full");
  Serial.println("brightness) while its neighbours are near 0 -> the visible");
  Serial.println("single-pixel flash.");
}

void loop() {
  // nothing
}
