#!/usr/bin/env python3
"""
VRC Facial Tracker — PC Application

Receives camera frames from an ESP32 MJPEG stream (or a local webcam),
runs MediaPipe FaceLandmarker (Tasks API) to extract 478 landmarks and
52 ARKit-compatible blend shapes, then sends VRChat-compatible parameters
via OSC.

Usage:
  # From ESP32 stream
  python -m pc_app --esp32 http://192.168.1.100:81/stream

  # From webcam (default)
  python -m pc_app --webcam 0

  # Custom OSC target
  python -m pc_app --esp32 http://192.168.1.100:81/stream \
      --osc-ip 127.0.0.1 --osc-port 9000

Key bindings (preview window):
  q / ESC   — quit
  d         — toggle debug overlay
  m         — toggle mirror mode
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.request

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import (
    FaceLandmarker,
    FaceLandmarkerOptions,
    FaceLandmarksConnections,
)

from .osc_sender import OscSender

# ---------------------------------------------------------------------------
# Model download
# ---------------------------------------------------------------------------
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
)
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
MODEL_PATH = os.path.join(MODEL_DIR, "face_landmarker.task")


def ensure_model() -> str:
    """Download the FaceLandmarker model if not already present."""
    if os.path.isfile(MODEL_PATH):
        return MODEL_PATH
    os.makedirs(MODEL_DIR, exist_ok=True)
    print(f"[INFO] Downloading FaceLandmarker model...")
    print(f"       {MODEL_URL}")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print(f"[INFO] Model saved to {MODEL_PATH}")
    return MODEL_PATH


# Blend shape mapping is centralized in osc_sender.py


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="vrc_facial_tracker",
        description="VRC Facial Tracker — MediaPipe FaceLandmarker → OSC for VRChat",
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument(
        "--esp32", type=str, default=None,
        help="ESP32 MJPEG stream URL (e.g. http://192.168.1.100:81/stream)",
    )
    src.add_argument(
        "--webcam", type=int, default=None,
        help="Webcam device index (default: 0)",
    )
    p.add_argument("--osc-ip", type=str, default="127.0.0.1",
                    help="VRChat OSC target IP (default: 127.0.0.1)")
    p.add_argument("--osc-port", type=int, default=9000,
                    help="VRChat OSC port (default: 9000)")
    p.add_argument("--smoothing", type=float, default=0.5,
                    help="EMA smoothing factor 0-1 (default: 0.5)")
    p.add_argument("--no-preview", action="store_true",
                    help="Disable OpenCV preview window")
    p.add_argument("--mirror", action="store_true",
                    help="Mirror the preview (useful for webcam)")
    p.add_argument("--fps-limit", type=int, default=30,
                    help="Max processing FPS (default: 30)")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

_CONNS_TESSELATION = FaceLandmarksConnections.FACE_LANDMARKS_TESSELATION
_CONNS_EYES_L      = FaceLandmarksConnections.FACE_LANDMARKS_LEFT_EYE
_CONNS_EYES_R      = FaceLandmarksConnections.FACE_LANDMARKS_RIGHT_EYE
_CONNS_LIPS        = FaceLandmarksConnections.FACE_LANDMARKS_LIPS
_CONNS_BROW_L      = FaceLandmarksConnections.FACE_LANDMARKS_LEFT_EYEBROW
_CONNS_BROW_R      = FaceLandmarksConnections.FACE_LANDMARKS_RIGHT_EYEBROW


def draw_face(frame: np.ndarray, landmarks: list) -> None:
    """Draw face mesh overlay on the frame."""
    h, w = frame.shape[:2]

    # Tesselation (faint)
    for conn in _CONNS_TESSELATION:
        pt1 = landmarks[conn.start]
        pt2 = landmarks[conn.end]
        x1, y1 = int(pt1.x * w), int(pt1.y * h)
        x2, y2 = int(pt2.x * w), int(pt2.y * h)
        cv2.line(frame, (x1, y1), (x2, y2), (40, 40, 40), 1)

    # Key regions with color
    for conns, color in [
        (_CONNS_EYES_L,  (0, 255, 200)),
        (_CONNS_EYES_R,  (0, 255, 200)),
        (_CONNS_LIPS,    (200, 100, 255)),
        (_CONNS_BROW_L,  (255, 200, 0)),
        (_CONNS_BROW_R,  (255, 200, 0)),
    ]:
        for conn in conns:
            pt1 = landmarks[conn.start]
            pt2 = landmarks[conn.end]
            x1, y1 = int(pt1.x * w), int(pt1.y * h)
            x2, y2 = int(pt2.x * w), int(pt2.y * h)
            cv2.line(frame, (x1, y1), (x2, y2), color, 1)


def draw_debug_hud(frame: np.ndarray, blend_shapes: dict[str, float],
                   fps: float) -> None:
    """Draw blend shape bar chart on the frame."""
    h, w = frame.shape[:2]
    y = 20
    line_h = 16
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.38
    white = (255, 255, 255)
    green = (0, 200, 100)
    gray  = (80, 80, 80)

    cv2.putText(frame, f"FPS: {fps:.1f}  Params: {len(blend_shapes)}",
                (5, y), font, scale, white, 1)
    y += line_h + 4

    show_params = [
        "eyeBlinkLeft", "eyeBlinkRight",
        "eyeWideLeft", "eyeSquintLeft",
        "browDownLeft", "browInnerUp",
        "jawOpen", "mouthSmileLeft", "mouthSmileRight",
        "mouthFrownLeft", "mouthPucker", "mouthFunnel",
        "cheekPuff", "tongueOut",
    ]
    bar_x = w - 100
    bar_w = 80
    for name in show_params:
        val = blend_shapes.get(name, 0.0)
        fill = max(0, min(int(val * bar_w), bar_w))
        cv2.rectangle(frame, (bar_x, y - 8), (bar_x + fill, y + 2), green, -1)
        cv2.rectangle(frame, (bar_x, y - 8), (bar_x + bar_w, y + 2), gray, 1)
        cv2.putText(frame, name[:16], (bar_x - 110, y), font, scale, white, 1)
        y += line_h


# ---------------------------------------------------------------------------
# Smoothing
# ---------------------------------------------------------------------------

class BlendShapeSmoother:
    """Exponential moving average for blend shape values."""

    def __init__(self, alpha: float = 0.5):
        self._alpha = alpha
        self._prev: dict[str, float] = {}

    def smooth(self, raw: dict[str, float]) -> dict[str, float]:
        result = {}
        a = self._alpha
        for k, v in raw.items():
            if k in self._prev:
                result[k] = self._prev[k] + a * (v - self._prev[k])
            else:
                result[k] = v
        self._prev = result
        return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # ---- Model ----
    model_path = ensure_model()

    # ---- Video source ----
    if args.esp32:
        source = args.esp32
        print(f"[INFO] Connecting to ESP32 stream: {source}")
    else:
        source = args.webcam if args.webcam is not None else 0
        print(f"[INFO] Using webcam index: {source}")
        if not args.mirror:
            args.mirror = True

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open video source: {source}")
        print("  - ESP32: check WiFi connection and URL")
        print("  - Webcam: check device index")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

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
    smoother = BlendShapeSmoother(alpha=args.smoothing)

    print(f"[INFO] OSC → {args.osc_ip}:{args.osc_port}")
    print(f"[INFO] Smoothing: {args.smoothing}")
    if not args.no_preview:
        print("[INFO] Preview: q/ESC=quit, d=debug, m=mirror")

    show_debug = True
    mirror = args.mirror
    frame_interval = 1.0 / args.fps_limit if args.fps_limit > 0 else 0
    fps = 0.0
    fps_alpha = 0.1
    frame_count = 0
    last_time = time.time()
    blend_shapes: dict[str, float] = {}
    timestamp_ms = 0

    try:
        while True:
            t0 = time.time()

            ret, frame = cap.read()
            if not ret:
                if args.esp32:
                    print("[WARN] Stream dropped, reconnecting...")
                    cap.release()
                    time.sleep(1.0)
                    cap = cv2.VideoCapture(source)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    continue
                else:
                    print("[ERROR] Webcam read failed")
                    break

            # MediaPipe Image
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            timestamp_ms += 33

            # Detect
            result = landmarker.detect_for_video(mp_image, timestamp_ms)

            if result.face_landmarks and result.face_blendshapes:
                landmarks = result.face_landmarks[0]
                raw_bs = result.face_blendshapes[0]

                # Extract into dict
                raw_dict: dict[str, float] = {}
                for bs in raw_bs:
                    raw_dict[bs.category_name] = bs.score

                blend_shapes = smoother.smooth(raw_dict)

                # Send OSC
                osc.send_blendshapes(blend_shapes)

                # Draw
                if not args.no_preview:
                    draw_face(frame, landmarks)

            # FPS
            now = time.time()
            dt = now - last_time
            if dt > 0:
                fps = fps + fps_alpha * (1.0 / dt - fps)
            last_time = now

            # Preview
            if not args.no_preview:
                display = cv2.flip(frame, 1) if mirror else frame.copy()
                if show_debug and blend_shapes:
                    draw_debug_hud(display, blend_shapes, fps)
                elif show_debug:
                    cv2.putText(display, f"FPS: {fps:.1f} | No face",
                                (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                                (255, 255, 255), 1)

                cv2.imshow("VRC Facial Tracker", display)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord('q'), 27):
                    break
                elif key == ord('d'):
                    show_debug = not show_debug
                elif key == ord('m'):
                    mirror = not mirror

            # FPS limit
            elapsed = time.time() - t0
            if frame_interval > elapsed:
                time.sleep(frame_interval - elapsed)

            frame_count += 1
            if frame_count % 300 == 0:
                print(f"[INFO] FPS: {fps:.1f} | OSC: {osc.messages_sent}"
                      f" | BS: {len(blend_shapes)}")

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        landmarker.close()
        print(f"[INFO] Frames: {frame_count}, OSC: {osc.messages_sent}")


if __name__ == "__main__":
    main()
