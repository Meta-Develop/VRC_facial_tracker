# VRC Facial Tracker

An open-source facial tracking device for VRChat, built with the Seeed Studio XIAO ESP32S3 Sense.

## Overview

This project provides a low-cost, DIY facial tracking solution compatible with VRChat's OSC (Open Sound Control) protocol. It captures facial expressions via the onboard camera of the XIAO ESP32S3 Sense and streams tracking data wirelessly to VRChat.

## Features

- **Real-time facial expression tracking** using the ESP32S3 onboard camera
- **Wireless streaming** over WiFi via OSC protocol
- **VRChat native support** through OSC face tracking parameters
- **Compact design** suitable for mounting on VR headsets
- **Low latency** optimized for real-time avatar expression mirroring
- **Open hardware** — full schematics and 3D-printable mount designs included

## Hardware

### Components

| Component | Description |
|-----------|-------------|
| Seeed Studio XIAO ESP32S3 Sense | Main MCU with OV2640 camera |
| 3D Printed Mount | Headset-specific mounting bracket |
| USB-C Cable | For initial flashing and power |

### Supported VR Headsets

- Meta Quest 2 / 3 / Pro
- Valve Index
- Other headsets (with custom mount)

## System Architecture

```
ESP32S3 (Camera + ML Inference)
    │
    ├── OV2640 Camera Capture
    ├── Face Detection & Landmark Extraction
    ├── Expression Parameter Calculation
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
| `MouthSmile` | 0.0 - 1.0 | Smile intensity |
| `BrowUpLeft` | 0.0 - 1.0 | Left eyebrow raise |
| `BrowUpRight` | 0.0 - 1.0 | Right eyebrow raise |
| `CheekPuff` | 0.0 - 1.0 | Cheek puff |
| `TongueOut` | 0.0 - 1.0 | Tongue extension |
| `JawOpen` | 0.0 - 1.0 | Jaw opening |

> Full parameter list and avatar setup guide available in [`docs/PARAMETERS.md`](docs/PARAMETERS.md).

## Build & Flash

```bash
# Using PlatformIO CLI
cd firmware
pio run -t upload

# Monitor serial output
pio device monitor
```

## Calibration

After flashing, the device enters calibration mode on first boot:

1. Face the camera directly with a neutral expression
2. Press the reset button to capture baseline
3. The device saves calibration data to flash memory
4. Subsequent boots use saved calibration

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No WiFi connection | Check SSID/password in config.h |
| No tracking in VRChat | Ensure OSC is enabled in VRChat settings |
| Laggy tracking | Reduce inference resolution in config |
| Camera not detected | Verify XIAO ESP32S3 **Sense** variant is used |

## Contributing

Contributions are welcome! Please open an issue or pull request.

## License

MIT License — see [LICENSE](LICENSE) for details.

## Acknowledgments

- [VRChat OSC Documentation](https://docs.vrchat.com/docs/osc-overview)
- [Seeed Studio XIAO ESP32S3 Sense](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/)
- [MediaPipe Face Mesh](https://developers.google.com/mediapipe/solutions/vision/face_landmarker)
