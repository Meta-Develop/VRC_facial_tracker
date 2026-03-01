"""
VRC Facial Tracker — OSC sender for VRChat.

Sends face tracking parameters to VRChat via the OSC protocol.
VRChat listens on localhost:9000 for avatar parameters.

Reference:
  https://docs.vrchat.com/docs/osc-as-input-controller
"""

from __future__ import annotations
from pythonosc import udp_client
from .face_params import FaceParams

# VRChat OSC address prefix
_PREFIX = "/avatar/parameters/"

# Mapping: FaceParams field name → VRChat parameter name
_PARAM_MAP = {
    "eyeBlinkLeft":     "EyeClosedLeft",
    "eyeBlinkRight":    "EyeClosedRight",
    "eyeWideLeft":      "EyeWideLeft",
    "eyeWideRight":     "EyeWideRight",
    "eyeSquintLeft":    "EyeSquintLeft",
    "eyeSquintRight":   "EyeSquintRight",
    "browDownLeft":     "BrowDownLeft",
    "browDownRight":    "BrowDownRight",
    "browUpLeft":       "BrowUpLeft",
    "browUpRight":      "BrowUpRight",
    "browInnerUp":      "BrowInnerUp",
    "mouthOpen":        "MouthOpen",
    "mouthSmileLeft":   "MouthSmileLeft",
    "mouthSmileRight":  "MouthSmileRight",
    "mouthFrownLeft":   "MouthFrownLeft",
    "mouthFrownRight":  "MouthFrownRight",
    "mouthPucker":      "MouthPucker",
    "mouthLeft":        "MouthLeft",
    "mouthRight":       "MouthRight",
    "mouthFunnel":      "MouthFunnel",
    "jawOpen":          "JawOpen",
    "jawLeft":          "JawLeft",
    "jawRight":         "JawRight",
    "cheekPuff":        "CheekPuff",
    "cheekSquintLeft":  "CheekSquintLeft",
    "cheekSquintRight": "CheekSquintRight",
    "tongueOut":        "TongueOut",
}


class OscSender:
    """Sends facial parameters to VRChat over OSC/UDP."""

    def __init__(self, ip: str = "127.0.0.1", port: int = 9000):
        self._client = udp_client.SimpleUDPClient(ip, port)
        self._sent = 0

    def send(self, params: FaceParams) -> None:
        """Send all face parameters as individual OSC messages."""
        for field_name, osc_name in _PARAM_MAP.items():
            value = getattr(params, field_name, 0.0)
            self._client.send_message(_PREFIX + osc_name, float(value))
        self._sent += 1

    @property
    def messages_sent(self) -> int:
        return self._sent
