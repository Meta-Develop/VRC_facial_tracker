#!/usr/bin/env python3
"""
VRC Facial Tracker — Debug Visualization Tool

Real-time visualization for verifying facial expression detection.
Shows a composite window with:
  - Live camera feed with face mesh overlay
  - Grouped blend shape bar chart (eye gaze excluded)
  - FPS counter (capture + processing)
  - Per-frame latency breakdown (read / MediaPipe / total)
  - UDP connection statistics (drops, JPEG size, receiver FPS)
  - Face detection status

Designed for under-headset mounting: eye gaze tracking is disabled;
only blink / wide / squint are shown (may be unreliable).

Usage:
  python -m pc_app --debug --esp32 192.168.1.100
  python -m pc_app --debug --webcam 0

Keys:
  q / ESC  — quit
  m        — toggle mirror
  s        — save screenshot
  r        — reset stats
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import (
    FaceLandmarker,
    FaceLandmarkerOptions,
)

from .main import ensure_model, draw_face
from .osc_sender import OscSender

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
FEED_W, FEED_H = 640, 480
PANEL_W = 350
CANVAS_W = FEED_W + PANEL_W
CANVAS_H = FEED_H

# ---------------------------------------------------------------------------
# Colors (BGR)
# ---------------------------------------------------------------------------
C_BG      = (25, 20, 18)
C_PANEL   = (35, 28, 22)
C_WHITE   = (230, 230, 230)
C_DIM     = (130, 130, 130)
C_GREEN   = (80, 200, 0)
C_RED     = (50, 50, 240)
C_YELLOW  = (0, 200, 255)
C_CYAN    = (240, 200, 0)
C_ORANGE  = (0, 140, 255)
C_BAR_BG  = (55, 45, 38)
C_ACCENT  = (255, 160, 50)

FONT = cv2.FONT_HERSHEY_SIMPLEX

# ---------------------------------------------------------------------------
# Blend shapes grouped by category (eye gaze excluded)
# ---------------------------------------------------------------------------
BLEND_GROUPS: list[tuple[str, list[str]]] = [
    ("Jaw / Mouth", [
        "jawOpen", "jawLeft", "jawRight", "jawForward",
        "mouthSmileLeft", "mouthSmileRight",
        "mouthFrownLeft", "mouthFrownRight",
        "mouthPucker", "mouthFunnel",
        "mouthLeft", "mouthRight",
        "mouthShrugUpper", "mouthShrugLower",
    ]),
    ("Brow", [
        "browDownLeft", "browDownRight",
        "browInnerUp",
        "browOuterUpLeft", "browOuterUpRight",
    ]),
    ("Eye (under-HMD)", [
        "eyeBlinkLeft", "eyeBlinkRight",
        "eyeWideLeft", "eyeWideRight",
        "eyeSquintLeft", "eyeSquintRight",
    ]),
    ("Cheek / Nose / Tongue", [
        "cheekPuff",
        "cheekSquintLeft", "cheekSquintRight",
        "noseSneerLeft", "noseSneerRight",
        "tongueOut",
    ]),
]

# Short names for compact display
_SHORT: dict[str, str] = {
    "jawOpen": "jawOpen",
    "jawLeft": "jawLeft",
    "jawRight": "jawRight",
    "jawForward": "jawFwd",
    "mouthSmileLeft": "smileL",
    "mouthSmileRight": "smileR",
    "mouthFrownLeft": "frownL",
    "mouthFrownRight": "frownR",
    "mouthPucker": "pucker",
    "mouthFunnel": "funnel",
    "mouthLeft": "mouthL",
    "mouthRight": "mouthR",
    "mouthShrugUpper": "shrugUp",
    "mouthShrugLower": "shrugLo",
    "browDownLeft": "bDownL",
    "browDownRight": "bDownR",
    "browInnerUp": "bInnerUp",
    "browOuterUpLeft": "bOuterL",
    "browOuterUpRight": "bOuterR",
    "eyeBlinkLeft": "blinkL",
    "eyeBlinkRight": "blinkR",
    "eyeWideLeft": "wideL",
    "eyeWideRight": "wideR",
    "eyeSquintLeft": "squintL",
    "eyeSquintRight": "squintR",
    "cheekPuff": "cheekPuff",
    "cheekSquintLeft": "ckSquintL",
    "cheekSquintRight": "ckSquintR",
    "noseSneerLeft": "noseL",
    "noseSneerRight": "noseR",
    "tongueOut": "tongueOut",
}


# ---------------------------------------------------------------------------
# Smoothing
# ---------------------------------------------------------------------------
class _BlendShapeSmoother:
    """EMA smoother (local copy to keep this module self-contained)."""

    def __init__(self, alpha: float = 0.5):
        self._alpha = alpha
        self._prev: dict[str, float] = {}

    def smooth(self, raw: dict[str, float]) -> dict[str, float]:
        result: dict[str, float] = {}
        a = self._alpha
        for k, v in raw.items():
            if k in self._prev:
                result[k] = self._prev[k] + a * (v - self._prev[k])
            else:
                result[k] = v
        self._prev = result
        return result


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------
def _draw_stats_overlay(canvas: np.ndarray, stats: dict) -> None:
    """Semi-transparent stats bar overlaid on the camera feed."""
    # Darken top strip
    roi = canvas[0:58, 0:FEED_W]
    overlay = roi.copy()
    cv2.rectangle(overlay, (0, 0), (FEED_W, 58), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, roi, 0.45, 0, dst=roi)

    # FPS
    fps = stats.get("fps", 0.0)
    fps_color = C_GREEN if fps > 20 else (C_YELLOW if fps > 10 else C_RED)
    cv2.putText(canvas, f"FPS: {fps:.1f}", (10, 18),
                FONT, 0.50, fps_color, 1, cv2.LINE_AA)

    # Latency breakdown
    read_ms  = stats.get("read_ms", 0.0)
    mp_ms    = stats.get("mp_ms", 0.0)
    total_ms = stats.get("total_ms", 0.0)
    lat_color = C_GREEN if total_ms < 50 else (C_YELLOW if total_ms < 100 else C_RED)
    cv2.putText(canvas,
                f"Latency: {total_ms:.0f}ms  (read {read_ms:.0f} + MP {mp_ms:.0f})",
                (10, 36), FONT, 0.38, lat_color, 1, cv2.LINE_AA)

    # Face status
    face_ok = stats.get("face", False)
    if face_ok:
        cv2.circle(canvas, (FEED_W - 100, 14), 5, C_GREEN, -1, cv2.LINE_AA)
        cv2.putText(canvas, "Face OK", (FEED_W - 90, 18),
                    FONT, 0.40, C_GREEN, 1, cv2.LINE_AA)
    else:
        cv2.circle(canvas, (FEED_W - 118, 14), 5, C_RED, -1, cv2.LINE_AA)
        cv2.putText(canvas, "No Face", (FEED_W - 108, 18),
                    FONT, 0.40, C_RED, 1, cv2.LINE_AA)

    # UDP stats (if applicable)
    if stats.get("use_udp"):
        drops    = stats.get("drops", 0)
        jpeg_kb  = stats.get("jpeg_kb", 0.0)
        recv_fps = stats.get("recv_fps", 0.0)
        cv2.putText(canvas,
                    f"UDP  drops:{drops}  JPEG:{jpeg_kb:.1f}KB  rx:{recv_fps:.0f}fps",
                    (10, 52), FONT, 0.34, C_DIM, 1, cv2.LINE_AA)

    # OSC counter
    osc_n = stats.get("osc_sent", 0)
    cv2.putText(canvas, f"OSC:{osc_n}", (FEED_W - 80, 52),
                FONT, 0.34, C_DIM, 1, cv2.LINE_AA)


def _draw_blend_panel(canvas: np.ndarray,
                      blend_shapes: dict[str, float]) -> None:
    """Blend shape bar-chart panel on the right-hand side."""
    x0 = FEED_W

    # Panel background + left accent border
    cv2.rectangle(canvas, (x0, 0), (CANVAS_W, CANVAS_H), C_PANEL, -1)
    cv2.line(canvas, (x0, 0), (x0, CANVAS_H), C_ACCENT, 2)

    label_x = x0 + 10
    bar_x   = x0 + 95
    bar_w   = 150
    bar_h   = 9
    val_x   = bar_x + bar_w + 5

    y = 20

    # Title
    cv2.putText(canvas, "Blend Shapes", (x0 + 12, y),
                FONT, 0.52, C_CYAN, 1, cv2.LINE_AA)
    y += 8
    cv2.line(canvas, (x0 + 5, y), (CANVAS_W - 5, y), C_DIM, 1)
    y += 14

    for group_name, params in BLEND_GROUPS:
        # Group header
        cv2.putText(canvas, group_name, (label_x, y),
                    FONT, 0.38, C_YELLOW, 1, cv2.LINE_AA)
        y += 4
        cv2.line(canvas, (label_x, y), (label_x + 80, y), (70, 60, 40), 1)
        y += 11

        for name in params:
            val = blend_shapes.get(name, 0.0)
            short = _SHORT.get(name, name[:10])

            # Label
            cv2.putText(canvas, short, (label_x + 2, y + 3),
                        FONT, 0.32, C_DIM, 1, cv2.LINE_AA)

            # Background bar
            cv2.rectangle(canvas, (bar_x, y - 3),
                          (bar_x + bar_w, y + bar_h - 3), C_BAR_BG, -1)

            # Filled bar (colour depends on activation level)
            fill_w = max(0, min(int(val * bar_w), bar_w))
            if fill_w > 0:
                if val < 0.35:
                    color = C_GREEN
                elif val < 0.70:
                    color = C_YELLOW
                else:
                    color = C_ORANGE
                cv2.rectangle(canvas, (bar_x, y - 3),
                              (bar_x + fill_w, y + bar_h - 3), color, -1)

            # Numeric value
            cv2.putText(canvas, f"{val:.2f}", (val_x, y + 3),
                        FONT, 0.28, C_DIM, 1, cv2.LINE_AA)

            y += 13

        y += 4  # inter-group spacing

    # Footer
    cv2.putText(canvas, "Eye gaze: disabled  (under-HMD camera)",
                (x0 + 10, CANVAS_H - 28), FONT, 0.28, C_DIM, 1, cv2.LINE_AA)
    cv2.putText(canvas, "Keys: q=quit  m=mirror  s=screenshot  r=reset",
                (x0 + 10, CANVAS_H - 12), FONT, 0.28, C_DIM, 1, cv2.LINE_AA)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="VRC Facial Tracker — Debug Visualization Tool",
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument("--esp32", type=str, default=None,
                     help="ESP32 IP address for UDP stream")
    src.add_argument("--webcam", type=int, default=None,
                     help="Webcam device index (default: 0)")
    p.add_argument("--esp32-port", type=int, default=5555,
                   help="ESP32 UDP port (default: 5555)")
    p.add_argument("--osc-ip", type=str, default="127.0.0.1",
                   help="VRChat OSC IP (default: 127.0.0.1)")
    p.add_argument("--osc-port", type=int, default=9000,
                   help="VRChat OSC port (default: 9000)")
    p.add_argument("--smoothing", type=float, default=0.5,
                   help="EMA smoothing 0-1 (default: 0.5)")
    p.add_argument("--mirror", action="store_true",
                   help="Mirror the preview")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main() -> None:
    args = _parse_args()

    # ---- model ----
    model_path = ensure_model()

    # ---- video source ----
    use_udp = False
    if args.esp32:
        if args.esp32.startswith("http"):
            cap = cv2.VideoCapture(args.esp32)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            source_label = f"HTTP  {args.esp32}"
        else:
            from .udp_receiver import UdpReceiver
            use_udp = True
            cap = UdpReceiver(args.esp32, args.esp32_port)
            source_label = f"UDP  {args.esp32}:{args.esp32_port}"
    else:
        idx = args.webcam if args.webcam is not None else 0
        cap = cv2.VideoCapture(idx)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        source_label = f"Webcam {idx}"
        if not args.mirror:
            args.mirror = True  # default mirror for webcam

    print(f"[DEBUG] Source : {source_label}")
    print(f"[DEBUG] OSC    : {args.osc_ip}:{args.osc_port}")
    print(f"[DEBUG] Keys   : q=quit  m=mirror  s=screenshot  r=reset")

    # ---- FaceLandmarker ----
    base_options = mp.tasks.BaseOptions(model_asset_path=model_path)
    options = FaceLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=False,
    )
    landmarker = FaceLandmarker.create_from_options(options)

    # ---- OSC ----
    osc = OscSender(ip=args.osc_ip, port=args.osc_port)
    smoother = _BlendShapeSmoother(alpha=args.smoothing)

    mirror = args.mirror
    blend_shapes: dict[str, float] = {}
    _t0_mono = time.monotonic()

    # FPS tracking (EMA)
    fps = 0.0
    fps_alpha = 0.1
    last_time = time.time()

    # Latency tracking (EMA)
    read_ms_avg  = 0.0
    mp_ms_avg    = 0.0
    total_ms_avg = 0.0
    lat_alpha    = 0.15

    frame_count = 0
    screenshot_dir = os.path.join(os.path.dirname(__file__),
                                  "..", "screenshots")

    win_name = "VRC Facial Tracker - Debug"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_name, CANVAS_W, CANVAS_H)

    try:
        while True:
            t_start = time.perf_counter()

            # ---- read frame ----
            t_read = time.perf_counter()
            ret, frame = cap.read()
            read_ms = (time.perf_counter() - t_read) * 1000

            if not ret:
                if use_udp:
                    # Show "waiting for ESP32" screen
                    canvas = np.full((CANVAS_H, CANVAS_W, 3),
                                     C_BG, dtype=np.uint8)
                    cv2.putText(canvas,
                                f"Waiting for ESP32  ({source_label})...",
                                (40, CANVAS_H // 2 - 10),
                                FONT, 0.65, C_YELLOW, 1, cv2.LINE_AA)
                    cv2.putText(canvas,
                                "Make sure ESP32 is powered on and WiFi connected.",
                                (40, CANVAS_H // 2 + 20),
                                FONT, 0.40, C_DIM, 1, cv2.LINE_AA)
                    cv2.putText(canvas,
                                "Check Serial monitor for IP address.",
                                (40, CANVAS_H // 2 + 45),
                                FONT, 0.38, C_DIM, 1, cv2.LINE_AA)
                    cv2.imshow(win_name, canvas)
                    if (cv2.waitKey(100) & 0xFF) in (ord('q'), 27):
                        break
                    continue
                else:
                    continue

            # ---- MediaPipe inference ----
            t_mp = time.perf_counter()
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            timestamp_ms = int((time.monotonic() - _t0_mono) * 1000)
            result = landmarker.detect_for_video(mp_image, timestamp_ms)
            mp_ms = (time.perf_counter() - t_mp) * 1000

            face_ok = bool(result.face_landmarks and result.face_blendshapes)
            if face_ok:
                landmarks = result.face_landmarks[0]
                raw_bs = result.face_blendshapes[0]
                raw_dict = {bs.category_name: bs.score for bs in raw_bs}
                blend_shapes = smoother.smooth(raw_dict)
                osc.send_blendshapes(blend_shapes)
                draw_face(frame, landmarks)

            # ---- mirror ----
            if mirror:
                frame = cv2.flip(frame, 1)

            # ---- FPS (EMA) ----
            now = time.time()
            dt = now - last_time
            if dt > 0:
                fps = fps + fps_alpha * (1.0 / dt - fps)
            last_time = now

            # ---- latency (EMA) ----
            total_ms = (time.perf_counter() - t_start) * 1000
            read_ms_avg  += lat_alpha * (read_ms  - read_ms_avg)
            mp_ms_avg    += lat_alpha * (mp_ms    - mp_ms_avg)
            total_ms_avg += lat_alpha * (total_ms - total_ms_avg)

            # ---- composite canvas ----
            canvas = np.full((CANVAS_H, CANVAS_W, 3), C_BG, dtype=np.uint8)

            # Fit camera frame into the feed area
            h, w = frame.shape[:2]
            scale = min(FEED_W / w, FEED_H / h)
            new_w, new_h = int(w * scale), int(h * scale)
            resized = cv2.resize(frame, (new_w, new_h))
            y_off = (FEED_H - new_h) // 2
            x_off = (FEED_W - new_w) // 2
            canvas[y_off:y_off + new_h, x_off:x_off + new_w] = resized

            # Stats overlay on camera feed
            stats: dict = {
                "fps": fps,
                "read_ms": read_ms_avg,
                "mp_ms": mp_ms_avg,
                "total_ms": total_ms_avg,
                "face": face_ok,
                "use_udp": use_udp,
                "osc_sent": osc.messages_sent,
            }
            if use_udp:
                stats["drops"]    = cap.drop_count
                stats["jpeg_kb"]  = cap.jpeg_size / 1024
                stats["recv_fps"] = cap.fps

            _draw_stats_overlay(canvas, stats)
            _draw_blend_panel(canvas, blend_shapes)

            # Source label at the bottom of the feed area
            cv2.putText(canvas, source_label, (10, CANVAS_H - 8),
                        FONT, 0.33, C_DIM, 1, cv2.LINE_AA)

            cv2.imshow(win_name, canvas)

            # ---- key handling ----
            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), 27):
                break
            elif key == ord('m'):
                mirror = not mirror
            elif key == ord('s'):
                os.makedirs(screenshot_dir, exist_ok=True)
                ts = time.strftime("%Y%m%d_%H%M%S")
                path = os.path.join(screenshot_dir, f"debug_{ts}.png")
                cv2.imwrite(path, canvas)
                print(f"[DEBUG] Screenshot saved: {path}")
            elif key == ord('r'):
                fps = 0.0
                read_ms_avg = mp_ms_avg = total_ms_avg = 0.0
                frame_count = 0
                print("[DEBUG] Stats reset")

            frame_count += 1
            if frame_count % 300 == 0:
                extra = ""
                if use_udp:
                    extra = (f" | drops={cap.drop_count}"
                             f" jpg={cap.jpeg_size}B")
                print(f"[DEBUG] FPS:{fps:.1f}  lat:{total_ms_avg:.0f}ms"
                      f"  read:{read_ms_avg:.0f}ms  MP:{mp_ms_avg:.0f}ms"
                      f"  OSC:{osc.messages_sent}{extra}")

    except KeyboardInterrupt:
        print("\n[DEBUG] Interrupted")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        landmarker.close()
        print(f"[DEBUG] Frames: {frame_count}  OSC: {osc.messages_sent}")


if __name__ == "__main__":
    main()
