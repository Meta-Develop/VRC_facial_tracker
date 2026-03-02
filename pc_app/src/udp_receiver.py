"""
VRC Facial Tracker — UDP Frame Receiver

Receives raw JPEG frames from ESP32 via UDP with minimal latency.
Implements a "latest-frame-wins" strategy: all stale frames in the
socket buffer are drained, and only the newest frame is returned.

Protocol (matching firmware/src/udp_stream.cpp):
  PC  → ESP32 : 1-byte command  (0x01 = REGISTER, 0x02 = HEARTBEAT)
  ESP32 → PC  : [2B frame_id LE] + [raw JPEG data]

Usage:
  cap = UdpReceiver("192.168.1.100")
  ok, frame = cap.read()   # returns latest frame (np.ndarray BGR)
  cap.release()

Drop-in replacement for cv2.VideoCapture (same read/release API).
"""

from __future__ import annotations

import select
import socket
import struct
import threading
import time
from typing import Optional

import cv2
import numpy as np

CMD_REGISTER  = b'\x01'
CMD_HEARTBEAT = b'\x02'

# Default ESP32 UDP port (must match firmware UDP_STREAM_PORT)
DEFAULT_PORT = 5555

# Socket receive buffer size (512 KB — holds ~50-80 frames)
RECV_BUF_SIZE = 512 * 1024


class UdpReceiver:
    """Receives JPEG frames from ESP32 via UDP.

    Mimics ``cv2.VideoCapture`` interface for easy integration.
    """

    def __init__(self, esp32_ip: str, esp32_port: int = DEFAULT_PORT):
        self._esp32_addr = (esp32_ip, esp32_port)

        # Create & configure socket
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(
            socket.SOL_SOCKET, socket.SO_RCVBUF, RECV_BUF_SIZE
        )
        self._sock.bind(('', 0))        # OS picks a free port
        self._sock.setblocking(False)

        self._opened = True
        self._running = True

        # Stats
        self._frame_count = 0
        self._drop_count = 0
        self._last_frame_id = -1
        self._last_jpeg_size = 0
        self._fps = 0.0
        self._fps_frames = 0
        self._fps_t0 = time.monotonic()

        # Send REGISTER to ESP32
        self._sock.sendto(CMD_REGISTER, self._esp32_addr)

        # Background heartbeat thread (keeps ESP32 streaming)
        self._hb_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True
        )
        self._hb_thread.start()

    # ------------------------------------------------------------------
    #  cv2.VideoCapture-compatible API
    # ------------------------------------------------------------------

    def read(self) -> tuple[bool, Optional[np.ndarray]]:
        """Return the *latest* available frame, dropping stale ones.

        Returns ``(True, frame)`` on success, ``(False, None)`` if no
        frame is available within ~100 ms.
        """
        latest: Optional[bytes] = None

        # 1. Drain everything already in the buffer (non-blocking)
        while True:
            try:
                data, _ = self._sock.recvfrom(65535)
                if len(data) > 2:
                    latest = data
            except BlockingIOError:
                break

        # 2. If buffer was empty, wait briefly for next frame
        if latest is None:
            try:
                ready, _, _ = select.select([self._sock], [], [], 0.1)
                if ready:
                    data, _ = self._sock.recvfrom(65535)
                    if len(data) > 2:
                        latest = data
                    # Drain any that arrived between select and recvfrom
                    while True:
                        try:
                            data, _ = self._sock.recvfrom(65535)
                            if len(data) > 2:
                                latest = data
                        except BlockingIOError:
                            break
            except Exception:
                pass

        if latest is None:
            return False, None

        # 3. Parse header
        frame_id = struct.unpack('<H', latest[:2])[0]
        jpeg_data = latest[2:]
        self._last_jpeg_size = len(jpeg_data)

        # 4. Track drops
        if self._last_frame_id >= 0:
            expected = (self._last_frame_id + 1) & 0xFFFF
            if frame_id != expected:
                gap = (frame_id - self._last_frame_id - 1) & 0xFFFF
                self._drop_count += gap
        self._last_frame_id = frame_id

        # 5. Decode JPEG → BGR ndarray
        frame = cv2.imdecode(
            np.frombuffer(jpeg_data, dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )
        if frame is None:
            return False, None

        # 6. Stats
        self._frame_count += 1
        self._fps_frames += 1
        now = time.monotonic()
        dt = now - self._fps_t0
        if dt >= 1.0:
            self._fps = self._fps_frames / dt
            self._fps_frames = 0
            self._fps_t0 = now

        return True, frame

    def isOpened(self) -> bool:          # noqa: N802 (cv2 compat)
        return self._opened

    def release(self) -> None:
        self._running = False
        try:
            self._sock.close()
        except Exception:
            pass
        self._opened = False

    def set(self, prop_id: int, value: float) -> bool:   # noqa: N802
        """No-op for cv2 compatibility (e.g. CAP_PROP_BUFFERSIZE)."""
        return True

    # ------------------------------------------------------------------
    #  Stats helpers
    # ------------------------------------------------------------------

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def drop_count(self) -> int:
        return self._drop_count

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def jpeg_size(self) -> int:
        """Size of the last received JPEG in bytes."""
        return self._last_jpeg_size

    # ------------------------------------------------------------------
    #  Internal
    # ------------------------------------------------------------------

    def _heartbeat_loop(self) -> None:
        while self._running:
            try:
                self._sock.sendto(CMD_HEARTBEAT, self._esp32_addr)
            except Exception:
                pass
            time.sleep(1.0)
