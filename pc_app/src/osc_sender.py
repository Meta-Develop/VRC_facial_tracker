"""
VRC Facial Tracker — OSC sender for VRChat.

Sends face tracking parameters to VRChat via the OSC protocol.
VRChat listens on localhost:9000 for avatar parameters.

Supports two calling conventions:
  - send_blendshapes(dict)  — ARKit blend shape name → float  (used by GUI/CLI)

Reference:
  https://docs.vrchat.com/docs/osc-as-input-controller
"""

from __future__ import annotations

from pythonosc import udp_client

# VRChat OSC address prefix
PREFIX = "/avatar/parameters/"

# MediaPipe ARKit blend shape name → VRChat parameter name
BLENDSHAPE_TO_VRC: dict[str, str] = {
    "eyeBlinkLeft":     "EyeClosedLeft",
    "eyeBlinkRight":    "EyeClosedRight",
    "eyeWideLeft":      "EyeWideLeft",
    "eyeWideRight":     "EyeWideRight",
    "eyeSquintLeft":    "EyeSquintLeft",
    "eyeSquintRight":   "EyeSquintRight",
    # eyeLook* params removed — camera is mounted under VR headset,
    # so iris tracking is impossible.  Blink/wide/squint may still
    # partially work from the lower-face view.
    "browDownLeft":     "BrowDownLeft",
    "browDownRight":    "BrowDownRight",
    "browInnerUp":      "BrowInnerUp",
    "browOuterUpLeft":  "BrowOuterUpLeft",
    "browOuterUpRight": "BrowOuterUpRight",
    "mouthSmileLeft":   "MouthSmileLeft",
    "mouthSmileRight":  "MouthSmileRight",
    "mouthFrownLeft":   "MouthFrownLeft",
    "mouthFrownRight":  "MouthFrownRight",
    "mouthPucker":      "MouthPucker",
    "mouthLeft":        "MouthLeft",
    "mouthRight":       "MouthRight",
    "mouthFunnel":      "MouthFunnel",
    "mouthShrugUpper":  "MouthShrugUpper",
    "mouthShrugLower":  "MouthShrugLower",
    "jawOpen":          "JawOpen",
    "jawLeft":          "JawLeft",
    "jawRight":         "JawRight",
    "jawForward":       "JawForward",
    "cheekPuff":        "CheekPuff",
    "cheekSquintLeft":  "CheekSquintLeft",
    "cheekSquintRight": "CheekSquintRight",
    "tongueOut":        "TongueOut",
    "noseSneerLeft":    "NoseSneerLeft",
    "noseSneerRight":   "NoseSneerRight",
}


class OscSender:
    """Sends facial parameters to VRChat over OSC/UDP."""

    def __init__(self, ip: str = "127.0.0.1", port: int = 9000):
        self._client = udp_client.SimpleUDPClient(ip, port)
        self._sent = 0

    def send_blendshapes(self, blend_shapes: dict[str, float]) -> None:
        """Send ARKit blend shape dict as VRChat OSC messages."""
        for bs_name, vrc_name in BLENDSHAPE_TO_VRC.items():
            val = blend_shapes.get(bs_name, 0.0)
            self._client.send_message(PREFIX + vrc_name, float(val))
        self._sent += 1

    def reconfigure(self, ip: str, port: int) -> None:
        """Change OSC target at runtime (for GUI)."""
        self._client = udp_client.SimpleUDPClient(ip, port)

    @property
    def messages_sent(self) -> int:
        return self._sent
