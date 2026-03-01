# Assembly Guide

## Parts List

| # | Component | Quantity | Notes |
|---|-----------|----------|-------|
| 1 | Seeed Studio XIAO ESP32S3 Sense | 1 | Must be the "Sense" variant with camera |
| 2 | OV2640 Camera Module | 1 | Included with XIAO ESP32S3 Sense |
| 3 | USB-C Cable | 1 | For flashing and power |
| 4 | 3D Printed Mount | 1 | See `mechanical/` directory |
| 5 | Double-sided tape or velcro | - | For headset mounting |

## Assembly Steps

### 1. Prepare the XIAO ESP32S3 Sense

1. Attach the camera ribbon cable to the XIAO board
   - Lift the connector latch gently
   - Insert the ribbon cable with contacts facing down
   - Press the latch back down to secure

2. Verify the camera is recognized:
   ```
   Connect via USB-C → Open serial monitor → Check for "Camera initialized"
   ```

### 2. Flash the Firmware

See the main README.md for flashing instructions.

### 3. Mount to Headset

1. Print the appropriate mount from `mechanical/mounts/`
2. Insert the XIAO into the mount enclosure
3. Attach the mount to your headset using the provided clip or adhesive

### 4. Position the Camera

- The camera should face your mouth/lower face
- Distance: approximately 5-10 cm from face
- Angle: slightly upward toward the face

## Wiring Diagram

For the basic configuration, no additional wiring is needed — the XIAO ESP32S3 Sense
has the camera module built in.

### Optional: IR LED Array

For improved low-light performance, an IR LED array can be added:

```
XIAO D0 (GPIO1) ──── 100Ω ──── IR LED (+)
                                    │
                                   GND
```

Use 850nm IR LEDs for invisible illumination.
