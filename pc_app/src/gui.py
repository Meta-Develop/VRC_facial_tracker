#!/usr/bin/env python3
"""
VRC Facial Tracker — GUI Application

A tkinter-based graphical interface for the VRC Facial Tracker.
Shows live camera preview, blend shape visualization, and controls.

Usage:
  python -m pc_app.src.gui
"""

from __future__ import annotations

import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageTk  # type: ignore
import mediapipe as mp
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import (
    FaceLandmarker,
    FaceLandmarkerOptions,
    FaceLandmarksConnections,
)

from .osc_sender import OscSender, BLENDSHAPE_TO_VRC
from .main import ensure_model, BlendShapeSmoother, draw_face

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BG         = "#1a1a2e"
BG_DARK    = "#111122"
FG         = "#e0e0e0"
ACCENT     = "#4a9eff"
GREEN      = "#00c864"
RED        = "#ff4444"
YELLOW     = "#ffaa00"
BAR_BG     = "#2a2a3e"
BAR_FG     = "#00c864"

PREVIEW_W  = 480
PREVIEW_H  = 360

# Key blend shapes to show in the bar panel
DISPLAY_PARAMS = [
    "eyeBlinkLeft", "eyeBlinkRight",
    "eyeWideLeft", "eyeWideRight",
    "browDownLeft", "browInnerUp",
    "jawOpen",
    "mouthSmileLeft", "mouthSmileRight",
    "mouthFrownLeft",
    "mouthPucker", "mouthFunnel",
    "cheekPuff", "tongueOut",
    "noseSneerLeft", "noseSneerRight",
]


# ---------------------------------------------------------------------------
# Tracker thread
# ---------------------------------------------------------------------------

class TrackerThread(threading.Thread):
    """Background thread that captures frames and runs MediaPipe."""

    def __init__(self, source, osc: OscSender, smoothing: float = 0.5):
        super().__init__(daemon=True)
        self.source = source
        self.osc = osc
        self.smoothing = smoothing

        self.running = False
        self.frame: Optional[np.ndarray] = None
        self.blend_shapes: dict[str, float] = {}
        self.fps: float = 0.0
        self.face_detected: bool = False
        self.error: Optional[str] = None
        self._lock = threading.Lock()
        self._smoother = BlendShapeSmoother(alpha=smoothing)

    def run(self):
        self.running = True
        self.error = None

        # Model
        try:
            model_path = ensure_model()
        except Exception as e:
            self.error = f"Model download failed: {e}"
            self.running = False
            return

        # Video source
        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            self.error = f"Cannot open: {self.source}"
            self.running = False
            return
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # FaceLandmarker
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

        timestamp_ms = 0
        last_time = time.time()
        fps_alpha = 0.1

        try:
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    if isinstance(self.source, str):
                        # MJPEG reconnect
                        cap.release()
                        time.sleep(1.0)
                        cap = cv2.VideoCapture(self.source)
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        continue
                    else:
                        self.error = "Webcam read failed"
                        break

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                timestamp_ms += 33

                result = landmarker.detect_for_video(mp_image, timestamp_ms)

                face_ok = bool(result.face_landmarks and result.face_blendshapes)
                bs_dict: dict[str, float] = {}

                if face_ok:
                    landmarks = result.face_landmarks[0]
                    raw_bs = result.face_blendshapes[0]
                    for bs in raw_bs:
                        bs_dict[bs.category_name] = bs.score
                    bs_dict = self._smoother.smooth(bs_dict)
                    self.osc.send_blendshapes(bs_dict)
                    draw_face(frame, landmarks)

                # FPS
                now = time.time()
                dt = now - last_time
                if dt > 0:
                    inst_fps = 1.0 / dt
                    self.fps = self.fps + fps_alpha * (inst_fps - self.fps)
                last_time = now

                with self._lock:
                    self.frame = frame
                    self.blend_shapes = bs_dict
                    self.face_detected = face_ok

                # ~30fps pacing
                time.sleep(max(0, 0.033 - dt))

        finally:
            cap.release()
            landmarker.close()
            self.running = False

    def stop(self):
        self.running = False

    def get_state(self):
        with self._lock:
            return self.frame, self.blend_shapes.copy(), self.face_detected


# ---------------------------------------------------------------------------
# GUI Application
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VRC Facial Tracker")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # State
        self._tracker: Optional[TrackerThread] = None
        self._osc = OscSender()
        self._mirror = tk.BooleanVar(value=True)
        self._photo: Optional[ImageTk.PhotoImage] = None

        self._build_ui()
        self._update_loop()

    # ---------------------------------------------------------------
    # UI Construction
    # ---------------------------------------------------------------
    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.TFrame", background=BG)
        style.configure("Dark.TLabel", background=BG, foreground=FG,
                         font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=BG, foreground=ACCENT,
                         font=("Segoe UI", 14, "bold"))
        style.configure("Status.TLabel", background=BG_DARK, foreground=YELLOW,
                         font=("Segoe UI", 9))
        style.configure("Dark.TLabelframe", background=BG, foreground=FG)
        style.configure("Dark.TLabelframe.Label", background=BG, foreground=ACCENT,
                         font=("Segoe UI", 10, "bold"))
        style.configure("Dark.TCheckbutton", background=BG, foreground=FG,
                         font=("Segoe UI", 9))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

        # Top frame: title + status
        top = ttk.Frame(self, style="Dark.TFrame")
        top.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Label(top, text="VRC Facial Tracker", style="Title.TLabel").pack(side=tk.LEFT)
        self._status_label = ttk.Label(top, text="Stopped", style="Status.TLabel")
        self._status_label.pack(side=tk.RIGHT, padx=5)

        # Main content: left = preview, right = bars + settings
        main = ttk.Frame(self, style="Dark.TFrame")
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # --- Left: Camera preview ---
        left = ttk.Frame(main, style="Dark.TFrame")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._canvas = tk.Canvas(left, width=PREVIEW_W, height=PREVIEW_H,
                                  bg=BG_DARK, highlightthickness=0)
        self._canvas.pack(padx=5, pady=5)

        # FPS label under preview
        self._fps_label = ttk.Label(left, text="FPS: --", style="Dark.TLabel")
        self._fps_label.pack()

        # --- Right: controls + blend shapes ---
        right = ttk.Frame(main, style="Dark.TFrame", width=280)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        right.pack_propagate(False)

        # Settings frame
        settings = ttk.LabelFrame(right, text="Settings",
                                   style="Dark.TLabelframe")
        settings.pack(fill=tk.X, pady=(0, 5))

        # Source
        row = ttk.Frame(settings, style="Dark.TFrame")
        row.pack(fill=tk.X, padx=8, pady=3)
        ttk.Label(row, text="Source:", style="Dark.TLabel").pack(side=tk.LEFT)
        self._source_var = tk.StringVar(value="0")
        self._source_entry = ttk.Entry(row, textvariable=self._source_var, width=28)
        self._source_entry.pack(side=tk.RIGHT)

        # Hint
        hint = ttk.Label(settings,
                          text="Webcam: 0  |  ESP32: http://IP:81/stream",
                          style="Dark.TLabel")
        hint.pack(padx=8, pady=(0, 3))

        # OSC IP
        row2 = ttk.Frame(settings, style="Dark.TFrame")
        row2.pack(fill=tk.X, padx=8, pady=3)
        ttk.Label(row2, text="OSC IP:", style="Dark.TLabel").pack(side=tk.LEFT)
        self._osc_ip_var = tk.StringVar(value="127.0.0.1")
        ttk.Entry(row2, textvariable=self._osc_ip_var, width=16).pack(side=tk.RIGHT)

        # OSC Port
        row3 = ttk.Frame(settings, style="Dark.TFrame")
        row3.pack(fill=tk.X, padx=8, pady=3)
        ttk.Label(row3, text="OSC Port:", style="Dark.TLabel").pack(side=tk.LEFT)
        self._osc_port_var = tk.StringVar(value="9000")
        ttk.Entry(row3, textvariable=self._osc_port_var, width=8).pack(side=tk.RIGHT)

        # Smoothing
        row4 = ttk.Frame(settings, style="Dark.TFrame")
        row4.pack(fill=tk.X, padx=8, pady=3)
        ttk.Label(row4, text="Smoothing:", style="Dark.TLabel").pack(side=tk.LEFT)
        self._smooth_var = tk.DoubleVar(value=0.5)
        self._smooth_scale = ttk.Scale(row4, from_=0.1, to=1.0,
                                        variable=self._smooth_var,
                                        orient=tk.HORIZONTAL, length=120)
        self._smooth_scale.pack(side=tk.RIGHT)

        # Mirror checkbox
        ttk.Checkbutton(settings, text="Mirror preview",
                         variable=self._mirror,
                         style="Dark.TCheckbutton").pack(padx=8, pady=3, anchor=tk.W)

        # Start / Stop
        btn_frame = ttk.Frame(settings, style="Dark.TFrame")
        btn_frame.pack(fill=tk.X, padx=8, pady=8)
        self._start_btn = tk.Button(btn_frame, text="Start",
                                     bg=GREEN, fg="white",
                                     font=("Segoe UI", 10, "bold"),
                                     relief=tk.FLAT, padx=16, pady=4,
                                     command=self._start_tracking)
        self._start_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))
        self._stop_btn = tk.Button(btn_frame, text="Stop",
                                    bg=RED, fg="white",
                                    font=("Segoe UI", 10, "bold"),
                                    relief=tk.FLAT, padx=16, pady=4,
                                    state=tk.DISABLED,
                                    command=self._stop_tracking)
        self._stop_btn.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(4, 0))

        # Blend shape bars (scrollable)
        bars_frame = ttk.LabelFrame(right, text="Blend Shapes",
                                     style="Dark.TLabelframe")
        bars_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        self._bars_canvas = tk.Canvas(bars_frame, bg=BG, highlightthickness=0,
                                       width=260)
        self._bars_canvas.pack(fill=tk.BOTH, expand=True)

        self._bar_items: dict[str, tuple] = {}
        self._create_bars()

    def _create_bars(self):
        """Create blend shape bar chart items on the bars canvas."""
        c = self._bars_canvas
        y = 8
        name_w = 110
        bar_x = name_w + 5
        bar_w = 120
        bar_h = 12
        gap = 18

        for name in DISPLAY_PARAMS:
            # Label
            tid = c.create_text(name_w, y + bar_h // 2, text=name,
                                 anchor=tk.E, fill=FG,
                                 font=("Consolas", 8))
            # Background bar
            bg_id = c.create_rectangle(bar_x, y, bar_x + bar_w, y + bar_h,
                                        fill=BAR_BG, outline="")
            # Foreground (value) bar
            fg_id = c.create_rectangle(bar_x, y, bar_x, y + bar_h,
                                        fill=BAR_FG, outline="")
            # Value text
            vt_id = c.create_text(bar_x + bar_w + 5, y + bar_h // 2,
                                   text="0.00", anchor=tk.W, fill="#888",
                                   font=("Consolas", 7))
            self._bar_items[name] = (fg_id, bar_x, bar_w, vt_id, y, bar_h)
            y += gap

        c.configure(scrollregion=(0, 0, 260, y + 10))

    def _update_bars(self, blend_shapes: dict[str, float]):
        c = self._bars_canvas
        for name, (fg_id, bar_x, bar_w, vt_id, y, bar_h) in self._bar_items.items():
            val = blend_shapes.get(name, 0.0)
            fill_w = max(0, min(int(val * bar_w), bar_w))
            c.coords(fg_id, bar_x, y, bar_x + fill_w, y + bar_h)

            # Color gradient: green → yellow → red
            if val < 0.5:
                r = int(val * 2 * 255)
                g = 200
            else:
                r = 255
                g = int((1.0 - val) * 2 * 200)
            color = f"#{r:02x}{g:02x}00"
            c.itemconfig(fg_id, fill=color)
            c.itemconfig(vt_id, text=f"{val:.2f}")

    # ---------------------------------------------------------------
    # Tracking Control
    # ---------------------------------------------------------------
    def _start_tracking(self):
        source_str = self._source_var.get().strip()

        # Parse source: int = webcam, string = URL
        try:
            source = int(source_str)
        except ValueError:
            source = source_str
            if not source.startswith("http"):
                messagebox.showerror("Error",
                    "Source must be a webcam index (0, 1, ...) or\n"
                    "an HTTP URL (http://IP:81/stream)")
                return

        # Configure OSC
        try:
            port = int(self._osc_port_var.get())
        except ValueError:
            port = 9000
        self._osc.reconfigure(self._osc_ip_var.get().strip(), port)

        # Start tracker thread
        self._tracker = TrackerThread(
            source=source,
            osc=self._osc,
            smoothing=self._smooth_var.get(),
        )
        self._tracker.start()

        self._start_btn.config(state=tk.DISABLED)
        self._stop_btn.config(state=tk.NORMAL)
        self._source_entry.config(state=tk.DISABLED)
        self._status_label.config(text="Starting...", foreground=YELLOW)

    def _stop_tracking(self):
        if self._tracker:
            self._tracker.stop()
            self._tracker = None

        self._start_btn.config(state=tk.NORMAL)
        self._stop_btn.config(state=tk.DISABLED)
        self._source_entry.config(state=tk.NORMAL)
        self._status_label.config(text="Stopped", foreground=YELLOW)
        self._fps_label.config(text="FPS: --")

        # Clear preview
        self._canvas.delete("all")

    # ---------------------------------------------------------------
    # Main UI update loop (30fps)
    # ---------------------------------------------------------------
    def _update_loop(self):
        if self._tracker and self._tracker.running:
            frame, bs, face_ok = self._tracker.get_state()

            if frame is not None:
                # Mirror
                if self._mirror.get():
                    frame = cv2.flip(frame, 1)

                # Resize to fit canvas
                h, w = frame.shape[:2]
                scale = min(PREVIEW_W / w, PREVIEW_H / h)
                new_w, new_h = int(w * scale), int(h * scale)
                frame = cv2.resize(frame, (new_w, new_h))

                # BGR → RGB → PIL → Tk
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(rgb)
                self._photo = ImageTk.PhotoImage(pil_img)
                self._canvas.delete("all")
                self._canvas.create_image(
                    PREVIEW_W // 2, PREVIEW_H // 2,
                    image=self._photo, anchor=tk.CENTER,
                )

            # Update bars
            if bs:
                self._update_bars(bs)

            # Status
            fps = self._tracker.fps
            self._fps_label.config(text=f"FPS: {fps:.1f}")
            osc_count = self._osc.messages_sent
            if face_ok:
                self._status_label.config(
                    text=f"Tracking  |  OSC: {osc_count}",
                    foreground=GREEN)
            else:
                self._status_label.config(
                    text=f"No face  |  OSC: {osc_count}",
                    foreground=YELLOW)

        elif self._tracker and not self._tracker.running:
            # Tracker stopped (error or stream end)
            err = self._tracker.error
            self._tracker = None
            self._start_btn.config(state=tk.NORMAL)
            self._stop_btn.config(state=tk.DISABLED)
            self._source_entry.config(state=tk.NORMAL)
            if err:
                self._status_label.config(text=f"Error: {err}", foreground=RED)
            else:
                self._status_label.config(text="Stopped", foreground=YELLOW)

        self.after(33, self._update_loop)  # ~30fps UI refresh

    def _on_close(self):
        if self._tracker:
            self._tracker.stop()
        self.destroy()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
