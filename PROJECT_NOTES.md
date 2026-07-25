# DiffusePanel - Project Notes

## Parts List

- **LED Panel**: BTF-LIGHTING Individual Addressable Flexible RGB LED Panel — https://www.amazon.com/BTF-LIGHTING-Individual-Addressable-Flexible-Controllers/dp/B088BTYJH6/
- **Cover Panel**: https://www.amazon.com/dp/B0DJLMVD6Q?ref=ppx_yo2ov_dt_b_fed_asin_title&th=1
  - **Note:** Does not provide any diffusion, it's just transparent

## LED Simulator

A local 16x16 LED panel simulator for testing patterns before uploading to hardware.

### Running the Simulator

```bash
python run_simulator.py
```

### Controls

| Key | Action |
|-----|--------|
| A / D (or Left/Right) | Switch patterns |
| W / S (or Up/Down) | Adjust speed (FPS) |
| Space | Pause / Resume |
| R | Reset current pattern |
| G | Toggle grid lines |
| B | Cycle brightness levels |
| Q / Escape | Quit |

### Project Structure

```
patterns/           Python pattern files (simulator)
  base.py           Shared utilities: xy_to_index, hsv_to_rgb, Pattern base class
  bokeh.py          Soft glowing orbs fading in/out independently
  ripple.py         Expanding rings from random points
  aurora.py         Slow drifting color blobs
  watercolor.py     Perlin noise morphing color fields
simulator/
  main.py           Pygame-ce display engine
DiffusePanelPatterns/
  DiffusePanelPatterns.ino   Arduino template with ported patterns
```

### Porting Patterns to Arduino

The pattern API is designed so each Python pattern translates directly to C++:

| Python | Arduino/FastLED |
|--------|-----------------|
| `hsv_to_rgb(h, s, v)` | `CHSV(h, s, v)` |
| `leds[idx] = (r, g, b)` | `leds[idx] = CRGB(r, g, b)` |
| `xy_to_index(x, y)` | `xyToIndex(x, y)` |
| `math.sin(x)` | `sin8(x)` / `sin16(x)` |
| `math.cos(x)` | `cos8(x)` |
| `math.sqrt(x)` | `sqrt16(x)` or squared-distance comparison |
| `random.randint(a, b)` | `random8(a, b)` / `random16(a, b)` |
| `frame` counter | `frame` global or `millis()` |
| Perlin noise | `inoise8(x, y, z)` / `inoise16(x, y, z)` |

#### ESP32-C6 Considerations

- **No hardware FPU** — Use integer math (`uint8_t`, `uint16_t`, `int16_t`) wherever possible
- **Budget**: ~6ms per frame for pattern logic (WS2812B data for 256 LEDs takes ~7ms at 800kHz)
- FastLED provides optimized helpers: `sin8()`, `cos8()`, `sqrt16()`, `inoise8()`, `qadd8()`, `qsub8()`

#### Per-Pattern Porting Notes

**Bokeh** (Easy)
- Per-LED state machine with basic arithmetic — ports almost directly
- Each orb struct uses ~10 bytes × 256 = ~2.5KB RAM (fine for ESP32-C6's 512KB)
- Replace smoothstep with integer approximation: `t = (t * t * (768 - 256 * t)) >> 16` (8-bit fixed point)
- The palette cycling uses simple frame-count modular math

**Ripple** (Easy-Moderate)
- Only 4 active ripple sources at a time × 256 pixels = 1024 distance checks per frame
- Replace `math.sqrt` with squared-distance comparison: compare `dx*dx + dy*dy` against `radius_squared`
- Use `uint16_t` for distance math (values max at 16² + 16² = 512, fits fine)
- Ring intensity: precompute ring inner/outer radius² for fast range check

**Aurora** (Moderate)
- 6 blobs × 256 pixels = 1536 distance checks per frame
- Replace `math.sqrt` with squared-distance: `dist_sq = dx*dx + dy*dy`, compare against `radius_sq`
- Replace `math.cos(t * pi)` falloff with a lookup table or FastLED's `cos8()`
- Alternatively: use `255 - (dist_sq * 255 / radius_sq)` for linear falloff (simpler, still soft through diffuser)
- Blob positions stored as `int16_t` in 8.8 fixed point for sub-pixel movement

**Watercolor** (Moderate — use FastLED's built-in noise)
- Replace custom Perlin noise with `inoise8(x, y, z)` — it's designed for exactly this, runs in microseconds
- Multi-octave: call `inoise8` at 1x, 2x, 4x scales and blend (or just use single octave — looks great through diffuser)
- Hue offset rotation maps to a simple `(inoise8(...) + frame_offset) % 256`
- Full pattern becomes ~10 lines of C++ with `inoise8`

### Dependencies

- Python 3.10+ with `pygame-ce` and `numpy`

## Next Steps

- Somehow the depth of the acrylic groove went down, need to increase it back to where it was
- Truss is interfering with wires on the LED panel
- Reduce with by 1.5 - 2mm
