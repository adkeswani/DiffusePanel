# DiffusePanel - Project Notes

## Overview

A calm ambient 16×16 LED panel display that cycles through organic patterns with smooth transitions. Designed for relaxing background illumination.

## Current Status (July 2026)

### Arduino Firmware — COMPLETE (4 patterns ported)

The firmware (`DiffusePanelPatterns/DiffusePanelPatterns.ino`) is fully functional with:

| Setting | Value |
|---------|-------|
| Target board | ESP32-C6 (XIAO) |
| LED type | WS2812B, 16×16 serpentine grid |
| Data pin | D0 |
| Brightness | 150/255 |
| Power cap | 400mA (USB-safe) |
| Pattern duration | 90 seconds |
| Transitions | 3-second smoothstep fade-in/fade-out |
| Frame rate | ~60 FPS (16ms delay) |

#### Ported Patterns (in cycle order)

1. **Plasma** — 3 drifting blobs with feathered edges, toroidal wrapping, purple/pink/magenta palette
2. **Bokeh** — Per-LED independent fade-in/hold/fade-out orbs, orange palette, ~40% bloom on hold
3. **Ripple** — Up to 4 concentric expanding rings from random points, teal/cyan/lavender palette
4. **Ring Fade** — Thick ring with a rotating brightness wave, shared slow rainbow hue, partial white desaturation at the peak

#### Pattern Cycling & Transitions

- Patterns auto-cycle every 90 seconds
- 3-second smoothstep fade-out starts at the end of each pattern's duration
- After fade-out completes, the next pattern initializes and fades in over 3 seconds
- Shared slow rainbow hue (`getSharedHue()`) cycles full spectrum every ~70 seconds
- `hueOffset` is randomized on each pattern switch for variety

### Patterns NOT Yet Ported to Arduino

- **Aurora** — Slow drifting color blobs (exists in Python simulator)
- **Watercolor** — Perlin noise morphing color fields (exists in Python simulator)
- **Moon** — Sphere with wandering 3D light source (exists in Python simulator)
- **Ring Wave** — (exists in Python simulator)

---

## Parts List

- **LED Panel**: BTF-LIGHTING Individual Addressable Flexible RGB LED Panel — https://www.amazon.com/BTF-LIGHTING-Individual-Addressable-Flexible-Controllers/dp/B088BTYJH6/
- **Cover Panel**: https://www.amazon.com/dp/B0DJLMVD6Q?ref=ppx_yo2ov_dt_b_fed_asin_title&th=1
  - **Note:** Does not provide any diffusion, it's just transparent

## LED Simulator

A local 16×16 LED panel simulator for testing patterns before uploading to hardware.

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
  ripple.py         Expanding rings from random points, like raindrops
  aurora.py         Slow drifting color blobs
  watercolor.py     Perlin noise morphing color fields
  ring_fade.py      Thick ring with a rotating color wave that fades behind it
  ring_wave.py      Ring wave pattern
  moon.py           Sphere with wandering 3D light source (Lambert shading)
simulator/
  main.py           Pygame-ce display engine
DiffusePanelPatterns/
  DiffusePanelPatterns.ino   Arduino firmware (all 4 ported patterns + auto-cycling)
DiffusePanelTest/
  DiffusePanelTest.ino       Hardware test sketch
diffusePanel.3mf             3D-printable frame/mask model
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
- Current firmware uses float math and runs fine — optimize only if frame budget becomes tight

#### Per-Pattern Porting Notes (for remaining patterns)

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

**Moon** (Moderate)
- Sphere normal computation: `nx = dx/r`, `ny = dy/r`, `nz = sqrt(1 - nx² - ny²)`
- Replace `math.sqrt` with `sqrt16()` or precompute a radial LUT (only 6-pixel radius = ~113 pixels inside sphere)
- Light direction uses layered sine waves — replace with `sin8()`/`cos8()` at different phase offsets
- Lambert dot product is just 3 multiplies + 2 adds — trivial in integer math
- Use 8.8 fixed point for normal components; final brightness fits in `uint8_t`

### Dependencies

- Python 3.10+ with `pygame-ce` and `numpy`
- Arduino IDE / PlatformIO with FastLED library
- Board support: ESP32-C6 (Seeed XIAO ESP32C6)

## Hardware / Enclosure Notes

- Need a way to keep a flat LED panel, so we'll need to stick a solid grid on the back, might need trusses on the grid? No, they aren't long arms
- Thicken the mask too so it doesn't warp
- And then update the grooves accordingly
- 3D model is in `diffusePanel.3mf`

## Next Steps
[ ] Finalize the patterns, especially blobs.
[ ] Maybe attach the power code with another zip tie to reduce strain.