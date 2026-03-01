# VRC Facial Tracker — PC App

Receives camera frames from an ESP32 MJPEG stream or local webcam, runs
MediaPipe FaceLandmarker for 478-landmark + 52 ARKit blend shape tracking,
and sends VRChat-compatible OSC parameters.

## Quick Start

```bash
pip install -r requirements.txt
python -m pc_app --esp32 http://<ESP32_IP>:81/stream
# or
python -m pc_app --webcam 0
```

The FaceLandmarker model (~3.6 MB) is auto-downloaded on first run.

## Requirements

- Python 3.9+
- Webcam or ESP32 WiFi camera stream
- VRChat with OSC enabled (port 9000)

## Features

- **MediaPipe FaceLandmarker** (Tasks API) — 478 landmarks + 52 native ARKit blend shapes
- **40 VRChat parameters** — eyes, brows, mouth, jaw, cheeks, nose, tongue
- **Real-time preview** — face mesh overlay with debug HUD
- **EMA smoothing** — configurable exponential moving average
- **Auto-reconnect** — handles ESP32 stream drops gracefully
- **Dual input** — ESP32 MJPEG stream or local webcam

## CLI Options

```
--esp32 URL        ESP32 stream URL (e.g. http://192.168.1.100:81/stream)
--webcam INDEX     Webcam index (default: 0)
--osc-ip IP        VRChat IP (default: 127.0.0.1)
--osc-port PORT    VRChat OSC port (default: 9000)
--smoothing FLOAT  EMA factor 0-1 (default: 0.5)
--no-preview       Headless mode
--mirror           Mirror preview
--fps-limit FPS    Max FPS (default: 30)
```

## Preview Keys

| Key | Action |
|-----|--------|
| `q` / ESC | Quit |
| `d` | Toggle debug overlay |
| `m` | Toggle mirror |
