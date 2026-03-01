# VRC Facial Tracker

An open-source facial tracking system for VRChat, built with the Seeed Studio XIAO ESP32S3 Sense.

## Overview

A low-cost, DIY facial tracking solution that captures facial expressions via the XIAO ESP32S3 Sense camera and sends tracking data to VRChat via OSC.

Two operating modes:

| Mode | Processing | Blend Shapes | FPS |
|------|-----------|--------------|-----|
| **Stream** (default) | ESP32 → WiFi MJPEG → PC (MediaPipe) → OSC | **52** (ARKit) | 30+ |
| **On-device** | ESP32 ESP-DL inference → OSC | 5 keypoints | ~15 |

**Recommended:** Stream mode — offloads face analysis to PC for dramatically richer expression tracking (52 ARKit blend shapes vs 5 keypoints).

## System Architecture

```
┌─────────────────────────────────┐     WiFi      ┌──────────────────────────────┐
│  XIAO ESP32S3 Sense             │    MJPEG      │  PC Application              │
│  ┌────────────┐  ┌───────────┐  │   stream      │  ┌────────────────────────┐  │
│  │ OV3660     │→ │ MJPEG     │──╂──────────────→│  │ MediaPipe              │  │
│  │ Camera     │  │ Server    │  │  :81/stream   │  │ FaceLandmarker         │  │
│  │ 320×240    │  │ Port 81   │  │               │  │ 478 landmarks          │  │
│  └────────────┘  └───────────┘  │               │  │ 52 ARKit blend shapes  │  │
│                                 │               │  └──────────┬─────────────┘  │
│  WiFi Manager (AP config portal)│               │             │                │
│  NVS credential storage         │               │  ┌──────────▼─────────────┐  │
│  Status LED (GPIO 21)           │               │  │ OSC Sender             │  │
└─────────────────────────────────┘               │  │ localhost:9000         │──╂──→ VRChat
                                                  │  └────────────────────────┘  │
                                                  │  Preview window + debug HUD  │
                                                  └──────────────────────────────┘
```

## Hardware

| Component | Description |
|-----------|-------------|
| Seeed Studio XIAO ESP32S3 Sense | ESP32-S3R8, OV3660 camera, 8MB Flash, 8MB PSRAM |
| 3D Printed Mount | Headset-specific bracket (see `mechanical/`) |
| USB-C Cable | Power and initial firmware flash |

## Quick Start

### 1. Flash the ESP32 Firmware

```bash
cd firmware
pip install platformio  # if not installed

# Flash stream mode (recommended)
pio run -e xiao_stream -t upload

# Monitor serial output
pio device monitor
```

### 2. Configure WiFi

On first boot, the ESP32 creates an access point: **VRC-Tracker-XXXX**

1. Connect to it with your phone or laptop
2. A captive portal opens automatically (or browse to `http://192.168.4.1`)
3. Select your WiFi network and enter the password
4. The ESP32 reboots and connects — the Serial monitor shows the stream URL

Alternatively, edit `firmware/src/config.h` before flashing:
```cpp
#define WIFI_SSID     "your_wifi_ssid"
#define WIFI_PASSWORD "your_wifi_password"
```

### 3. Install & Run the PC App

```bash
cd pc_app
pip install -r requirements.txt

# Connect to ESP32 stream
python -m pc_app --esp32 http://<ESP32_IP>:81/stream

# Or use a webcam for testing
python -m pc_app --webcam 0
```

### 4. Enable OSC in VRChat

Action Menu → Options → OSC → **Enabled**

The tracker sends 40+ facial parameters to `localhost:9000`.

## PC App Usage

```
python -m pc_app [options]

Options:
  --esp32 URL       ESP32 MJPEG stream URL
  --webcam INDEX    Webcam device index (default: 0)
  --osc-ip IP       VRChat OSC IP (default: 127.0.0.1)
  --osc-port PORT   VRChat OSC port (default: 9000)
  --smoothing FLOAT EMA smoothing 0-1 (default: 0.5)
  --no-preview      Disable preview window
  --mirror          Mirror the preview
  --fps-limit FPS   Max FPS (default: 30)

Preview keys:
  q / ESC  — quit
  d        — toggle debug overlay
  m        — toggle mirror
```

The FaceLandmarker model (~3.6 MB) is auto-downloaded on first run.

## VRChat OSC Parameters

40 parameters sent via OSC to `/avatar/parameters/`:

| Category | Parameters |
|----------|-----------|
| **Eyes** | EyeClosedLeft/Right, EyeWideLeft/Right, EyeSquintLeft/Right, EyeLookUp/Down/In/OutLeft/Right |
| **Brows** | BrowDownLeft/Right, BrowInnerUp, BrowOuterUpLeft/Right |
| **Mouth** | MouthSmileLeft/Right, MouthFrownLeft/Right, MouthPucker, MouthFunnel, MouthLeft/Right, MouthShrugUpper/Lower |
| **Jaw** | JawOpen, JawLeft, JawRight, JawForward |
| **Cheek** | CheekPuff, CheekSquintLeft/Right |
| **Nose** | NoseSneerLeft/Right |
| **Tongue** | TongueOut |

## Build Environments

| Environment | Mode | Backend | RAM | Flash |
|-------------|------|---------|-----|-------|
| `xiao_stream` | WiFi camera | MJPEG → PC | 17.5% | 26.4% |
| `xiao_esp32s3` | On-device | Heuristic | 15.0% | 23.9% |
| `xiao_espidf` | On-device | ESP-DL | 14.2% | 39.5% |

```bash
# Build specific environment
pio run -e xiao_stream       # WiFi camera (default)
pio run -e xiao_esp32s3      # Heuristic on-device
pio run -e xiao_espidf       # ESP-DL on-device
```

## Directory Structure

```
firmware/          ESP32S3 firmware (PlatformIO)
  src/
    main.cpp       Entry point (3 operating modes)
    config.h       WiFi, camera, tracking configuration
    camera.cpp     OV3660 camera driver
    stream_server  MJPEG HTTP streaming server
    wifi_manager   AP config portal + NVS credential storage
    tracker.cpp    On-device face analysis
    osc_sender.cpp ESP32-side OSC (on-device modes)
    network.cpp    Simple WiFi STA (on-device modes)
pc_app/            PC-side application (Python)
  src/
    main.py        Entry point (MediaPipe + OSC)
    face_params.py Landmark → blend shape extraction
    osc_sender.py  python-osc VRChat sender
  requirements.txt Python dependencies
hardware/          Schematics
mechanical/        3D print files
docs/              Documentation
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Can't connect to AP portal | Look for `VRC-Tracker-XXXX` WiFi network |
| Stream URL not shown | Check Serial monitor at 115200 baud |
| No face detected (PC app) | Ensure good lighting and camera angle |
| Preview freezes | Check network stability; try `--fps-limit 15` |
| VRChat doesn't respond | Enable OSC in VRChat settings |
| PSRAM error | Use `sdkconfig.defaults` with `CONFIG_ESP32S3_SPIRAM_SUPPORT=y` |

## License

MIT License — see [LICENSE](LICENSE) for details.

## Acknowledgments

- [MediaPipe FaceLandmarker](https://developers.google.com/mediapipe/solutions/vision/face_landmarker) — 52 ARKit blend shapes
- [Espressif ESP-DL](https://github.com/espressif/esp-dl) — on-device face detection
- [VRChat OSC](https://docs.vrchat.com/docs/osc-overview) — avatar parameter protocol
- [Seeed Studio XIAO ESP32S3 Sense](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/)
