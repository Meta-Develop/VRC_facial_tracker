# Hardware

Schematics and wiring diagrams for the VRC Facial Tracker.

## Contents

- `schematics/` — KiCad schematic files
- `wiring/` — Wiring diagrams and pin mapping

## XIAO ESP32S3 Sense Pinout

The camera interface uses the default XIAO ESP32S3 Sense camera connector.
No additional wiring is required for basic operation.

### Optional IR LED Array (for low-light tracking)

| XIAO Pin | Function | Description |
|----------|----------|-------------|
| D0 (GPIO1) | IR_LED_EN | IR LED array enable |
| 3V3 | VCC | Power supply |
| GND | GND | Ground |
