# VRChat OSC Face Tracking Parameters

## Overview

This document lists all OSC parameters sent by the VRC Facial Tracker to VRChat.

## Enabling OSC in VRChat

1. Open VRChat
2. Open the Action Menu (R button on controller)
3. Navigate to **Options** → **OSC** → **Enabled**
4. VRChat will listen on port `9000` by default

## Parameter Reference

### Eye Parameters

| OSC Address | Type | Range | Description |
|-------------|------|-------|-------------|
| `/avatar/parameters/EyeClosedLeft` | float | 0.0 - 1.0 | Left eye closure |
| `/avatar/parameters/EyeClosedRight` | float | 0.0 - 1.0 | Right eye closure |
| `/avatar/parameters/EyeSquintLeft` | float | 0.0 - 1.0 | Left eye squint |
| `/avatar/parameters/EyeSquintRight` | float | 0.0 - 1.0 | Right eye squint |
| `/avatar/parameters/EyeWideLeft` | float | 0.0 - 1.0 | Left eye widened |
| `/avatar/parameters/EyeWideRight` | float | 0.0 - 1.0 | Right eye widened |

### Eyebrow Parameters

| OSC Address | Type | Range | Description |
|-------------|------|-------|-------------|
| `/avatar/parameters/BrowUpLeft` | float | 0.0 - 1.0 | Left eyebrow raise |
| `/avatar/parameters/BrowUpRight` | float | 0.0 - 1.0 | Right eyebrow raise |
| `/avatar/parameters/BrowDownLeft` | float | 0.0 - 1.0 | Left eyebrow lower |
| `/avatar/parameters/BrowDownRight` | float | 0.0 - 1.0 | Right eyebrow lower |

### Mouth Parameters

| OSC Address | Type | Range | Description |
|-------------|------|-------|-------------|
| `/avatar/parameters/MouthOpen` | float | 0.0 - 1.0 | Mouth opening |
| `/avatar/parameters/MouthSmile` | float | 0.0 - 1.0 | Smile intensity |
| `/avatar/parameters/MouthFrown` | float | 0.0 - 1.0 | Frown intensity |
| `/avatar/parameters/MouthPucker` | float | 0.0 - 1.0 | Lip pucker |

### Jaw Parameters

| OSC Address | Type | Range | Description |
|-------------|------|-------|-------------|
| `/avatar/parameters/JawOpen` | float | 0.0 - 1.0 | Jaw opening |
| `/avatar/parameters/JawLeft` | float | 0.0 - 1.0 | Jaw shift left |
| `/avatar/parameters/JawRight` | float | 0.0 - 1.0 | Jaw shift right |

### Other Parameters

| OSC Address | Type | Range | Description |
|-------------|------|-------|-------------|
| `/avatar/parameters/CheekPuff` | float | 0.0 - 1.0 | Cheek puffing |
| `/avatar/parameters/TongueOut` | float | 0.0 - 1.0 | Tongue extension |

## Avatar Setup

For these parameters to work, your VRChat avatar must have:

1. **Blend shapes** corresponding to each tracked expression
2. **VRC Expression Parameters** matching the OSC addresses above
3. **Animation layers** that drive blend shapes from these parameters

### Unity Setup Steps

1. Add float parameters to your avatar's Expression Parameters asset
2. Create animator layers with blend trees driven by these parameters
3. Map blend tree outputs to your avatar's blend shapes
4. Upload the avatar to VRChat

## Calibration

The tracker performs automatic calibration on startup. For manual recalibration:

1. Face the camera with a neutral expression
2. Press the reset button on the XIAO ESP32S3
3. Hold neutral for 3 seconds
4. Calibration is saved to flash memory
