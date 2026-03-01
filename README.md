# VRC Facial Tracker

An open-source facial tracking device for VRChat, built with the Seeed Studio XIAO ESP32S3 Sense.

## Overview

This project provides a low-cost, DIY facial tracking solution compatible with VRChat's OSC (Open Sound Control) protocol. It captures facial expressions via the onboard camera of the XIAO ESP32S3 Sense and streams tracking data wirelessly to VRChat.

**Current Status:** Hardware-verified — ESP-DL face detection running at **14.8 fps** on real device.

## Features

- **ESP-DL face detection** — neural network inference on-device (HumanFaceDetectMSR01)
- **5-point keypoint tracking** — eyes, nose, mouth corners for expression extraction
- **14.8 fps real-time** — camera capture + inference pipeline
- **Wireless streaming** over WiFi via OSC protocol to VRChat
- **Dual build modes** — ESP-IDF+Arduino hybrid (ESP-DL) or Arduino-only (heuristic fallback)
- **Offline mode** — runs without WiFi for standalone testing
- **8MB PSRAM** — OPI 80MHz for frame buffers and model storage
- **240MHz ESP32-S3** — optimized cache configuration (64KB / 8-way / 64B line)

## Hardware

### Components

| Component | Description |
|-----------|-------------|
| Seeed Studio XIAO ESP32S3 Sense | ESP32-S3R8 MCU + OV3660 camera, 8MB Flash, 8MB PSRAM |
| 3D Printed Mount | Headset-specific mounting bracket |
| USB-C Cable | For flashing, power, and serial debug |

### Supported VR Headsets

- Meta Quest 2 / 3 / Pro
- Valve Index
- Other headsets (with custom mount)

## System Architecture

```
XIAO ESP32S3 Sense (Camera + ESP-DL Inference)
    │
    ├── OV3660 Camera Capture (QVGA 320x240 RGB565, 24MHz XCLK)
    ├── ESP-DL Face Detection (HumanFaceDetectMSR01)
    ├── 5-Point Keypoint → Expression Parameter Extraction
    │   ├── eyeClosedLeft / eyeClosedRight
    │   ├── mouthOpen / jawOpen
    │   └── mouthSmile
    │
    └── WiFi OSC Transmission
            │
            └── VRChat (OSC Receiver)
                    │
                    └── Avatar Blend Shapes
```

## Directory Structure

```
firmware/           ESP32S3 firmware (PlatformIO / Arduino)
hardware/           Schematics and wiring diagrams
mechanical/         3D printable mount designs (STL / STEP)
pc_app/             PC-side receiver application (optional)
docs/               User documentation and guides
```

## Getting Started

### Prerequisites

- [PlatformIO](https://platformio.org/) or Arduino IDE
- Seeed Studio XIAO ESP32S3 Sense
- WiFi network (2.4GHz)
- VRChat with OSC enabled

### Quick Start

1. Clone this repository
2. Open the `firmware/` directory in PlatformIO
3. Configure your WiFi credentials in `firmware/src/config.h`
4. Flash the firmware to your XIAO ESP32S3 Sense
5. Enable OSC in VRChat (Action Menu → Options → OSC → Enabled)
6. The tracker will automatically connect and start streaming

### WiFi Configuration

Create or edit `firmware/src/config.h`:

```cpp
#define WIFI_SSID     "your_wifi_ssid"
#define WIFI_PASSWORD "your_wifi_password"
#define OSC_TARGET_IP "192.168.x.x"  // Your PC's local IP
#define OSC_TARGET_PORT 9000          // VRChat OSC port
```

## VRChat OSC Parameters

The tracker sends the following face tracking parameters:

| Parameter | Range | Description |
|-----------|-------|-------------|
| `EyeClosedLeft` | 0.0 - 1.0 | Left eye closure |
| `EyeClosedRight` | 0.0 - 1.0 | Right eye closure |
| `MouthOpen` | 0.0 - 1.0 | Mouth opening |
| `JawOpen` | 0.0 - 1.0 | Jaw opening |
| `MouthSmile` | 0.0 - 1.0 | Smile intensity |

> Full parameter list and avatar setup guide available in [`docs/PARAMETERS.md`](docs/PARAMETERS.md).

## Build & Flash

```bash
# ESP-DL face detection (recommended — requires ESP-IDF+Arduino hybrid)
cd firmware
pio run -e xiao_esp32s3_espidf -t upload

# Arduino-only fallback (heuristic backend, simpler build)
pio run -e xiao_esp32s3 -t upload

# Monitor serial output
pio device monitor
```

### Build Stats

| Environment | Backend | RAM | Flash | FPS |
|-------------|---------|-----|-------|-----|
| `xiao_esp32s3_espidf` | ESP-DL | 14.2% | 39.5% | 14.8 |
| `xiao_esp32s3` | Heuristic | 15.0% | 23.6% | 14.8 |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No WiFi connection | Check SSID/password in `config.h` |
| No tracking in VRChat | Ensure OSC is enabled in VRChat settings |
| Camera not detected | Verify XIAO ESP32S3 **Sense** variant is used |
| PSRAM allocation failed | Use `sdkconfig.defaults` with `CONFIG_ESP32S3_SPIRAM_SUPPORT=y` |
| Build fails (ESP-IDF) | Run `pio run -e xiao_esp32s3` for Arduino-only fallback |

## Contributing

Contributions are welcome! Please open an issue or pull request.

## License

MIT License — see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Espressif ESP-DL](https://github.com/espressif/esp-dl) — on-device face detection model
- [VRChat OSC Documentation](https://docs.vrchat.com/docs/osc-overview)
- [Seeed Studio XIAO ESP32S3 Sense](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/)
- [PlatformIO](https://platformio.org/) — build system
