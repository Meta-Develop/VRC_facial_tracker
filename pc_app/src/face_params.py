"""
VRC Facial Tracker — Face parameter extraction from MediaPipe Face Mesh.

Uses 468-landmark face mesh to compute VRChat-compatible blend shape
parameters. Landmarks are accessed by index per the MediaPipe canonical
face mesh layout.

Reference:
  https://github.com/google/mediapipe/blob/master/mediapipe/modules/
  face_geometry/data/canonical_face_model_uv_visualization.png
"""

from __future__ import annotations
import math
import numpy as np
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Canonical MediaPipe Face Mesh landmark indices
# ---------------------------------------------------------------------------

# Eyes — upper/lower lid landmarks for EAR (Eye Aspect Ratio)
LEFT_EYE_TOP    = [159, 145]   # upper lid pair
LEFT_EYE_BOTTOM = [23, 130]    # lower lid pair
LEFT_EYE_INNER  = 133
LEFT_EYE_OUTER  = 33

RIGHT_EYE_TOP    = [386, 374]
RIGHT_EYE_BOTTOM = [253, 359]
RIGHT_EYE_INNER  = 362
RIGHT_EYE_OUTER  = 263

# Iris (MediaPipe 478-landmark model)
LEFT_IRIS_CENTER  = 468
RIGHT_IRIS_CENTER = 473

# Eyebrows
LEFT_BROW   = [70, 63, 105, 66, 107]
RIGHT_BROW  = [300, 293, 334, 296, 336]
LEFT_BROW_INNER  = 107
LEFT_BROW_OUTER  = 70
RIGHT_BROW_INNER = 336
RIGHT_BROW_OUTER = 300

# Mouth (outer lips)
MOUTH_TOP     = 13
MOUTH_BOTTOM  = 14
MOUTH_LEFT    = 61
MOUTH_RIGHT   = 291
MOUTH_UPPER_LIP_TOP = 0
MOUTH_LOWER_LIP_BOT = 17

# Mouth inner
MOUTH_INNER_TOP    = 13
MOUTH_INNER_BOTTOM = 14
MOUTH_INNER_LEFT   = 78
MOUTH_INNER_RIGHT  = 308

# Jaw
JAW_TIP = 152
CHIN    = 175

# Nose
NOSE_TIP    = 1
NOSE_BRIDGE = 6

# Face contour (for face size normalization)
FACE_TOP    = 10   # forehead
FACE_BOTTOM = 152  # chin
FACE_LEFT   = 234
FACE_RIGHT  = 454


@dataclass
class FaceParams:
    """VRChat-compatible facial expression parameters (0.0 – 1.0)."""
    # Eyes
    eyeBlinkLeft:    float = 0.0
    eyeBlinkRight:   float = 0.0
    eyeWideLeft:     float = 0.0
    eyeWideRight:    float = 0.0
    eyeSquintLeft:   float = 0.0
    eyeSquintRight:  float = 0.0

    # Eyebrows
    browDownLeft:    float = 0.0
    browDownRight:   float = 0.0
    browUpLeft:      float = 0.0
    browUpRight:     float = 0.0
    browInnerUp:     float = 0.0

    # Mouth
    mouthOpen:       float = 0.0
    mouthSmileLeft:  float = 0.0
    mouthSmileRight: float = 0.0
    mouthFrownLeft:  float = 0.0
    mouthFrownRight: float = 0.0
    mouthPucker:     float = 0.0
    mouthLeft:       float = 0.0
    mouthRight:      float = 0.0
    mouthShrugUpper: float = 0.0
    mouthShrugLower: float = 0.0
    mouthFunnel:     float = 0.0

    # Jaw
    jawOpen:         float = 0.0
    jawLeft:         float = 0.0
    jawRight:        float = 0.0
    jawForward:      float = 0.0

    # Cheek
    cheekPuff:       float = 0.0
    cheekSquintLeft: float = 0.0
    cheekSquintRight:float = 0.0

    # Tongue
    tongueOut:       float = 0.0

    # Head pose (radians)
    headYaw:         float = 0.0
    headPitch:       float = 0.0
    headRoll:        float = 0.0


def _dist(a, b) -> float:
    """Euclidean distance between two 3D points."""
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2)


def _dist2d(a, b) -> float:
    """2D Euclidean distance."""
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _remap(value: float, in_min: float, in_max: float,
           out_min: float = 0.0, out_max: float = 1.0) -> float:
    """Linear remap and clamp."""
    if in_max - in_min < 1e-8:
        return out_min
    t = (value - in_min) / (in_max - in_min)
    return _clamp(out_min + t * (out_max - out_min), out_min, out_max)


class FaceAnalyzer:
    """
    Converts MediaPipe Face Mesh landmarks into VRChat blend shape
    parameters.

    Call ``update(landmarks)`` each frame with the 468/478 landmark
    list from ``face_mesh.process()``. Then read ``params`` for the
    current blend shape values.
    """

    def __init__(self, smoothing: float = 0.4):
        self.params = FaceParams()
        self._smooth = smoothing   # exponential smoothing factor
        self._calibrated = False
        self._neutral_ear_l = 0.28
        self._neutral_ear_r = 0.28
        self._neutral_mar   = 0.02
        self._neutral_brow_l = 0.0
        self._neutral_brow_r = 0.0
        self._cal_frames = 0
        self._cal_ear_l_acc = 0.0
        self._cal_ear_r_acc = 0.0
        self._cal_mar_acc   = 0.0
        self._cal_brow_l_acc = 0.0
        self._cal_brow_r_acc = 0.0

    def update(self, landmarks) -> FaceParams:
        """
        Process one frame of landmarks.

        Parameters
        ----------
        landmarks : list-like
            Each element has .x, .y, .z (normalized 0–1 coords).

        Returns
        -------
        FaceParams with updated blend shape values.
        """
        lm = landmarks
        n = len(lm)
        if n < 468:
            return self.params

        # Helper: get 3D point as tuple
        def p(i):
            return (lm[i].x, lm[i].y, lm[i].z)

        # Face height for normalization
        face_h = _dist(p(FACE_TOP), p(FACE_BOTTOM))
        if face_h < 1e-6:
            return self.params

        # ---- Eye Aspect Ratio (EAR) ----
        ear_l = self._compute_ear(p, LEFT_EYE_TOP, LEFT_EYE_BOTTOM,
                                  LEFT_EYE_INNER, LEFT_EYE_OUTER)
        ear_r = self._compute_ear(p, RIGHT_EYE_TOP, RIGHT_EYE_BOTTOM,
                                  RIGHT_EYE_INNER, RIGHT_EYE_OUTER)

        # ---- Mouth Aspect Ratio (MAR) ----
        mar = _dist(p(MOUTH_TOP), p(MOUTH_BOTTOM)) / face_h

        # ---- Brow height ----
        brow_l = (sum(p(i)[1] for i in LEFT_BROW) / len(LEFT_BROW))
        eye_l_y = p(LEFT_EYE_INNER)[1]
        brow_l_rel = (eye_l_y - brow_l) / face_h

        brow_r = (sum(p(i)[1] for i in RIGHT_BROW) / len(RIGHT_BROW))
        eye_r_y = p(RIGHT_EYE_INNER)[1]
        brow_r_rel = (eye_r_y - brow_r) / face_h

        # ---- Auto-calibration (first 30 frames = neutral) ----
        if self._cal_frames < 30:
            self._cal_ear_l_acc += ear_l
            self._cal_ear_r_acc += ear_r
            self._cal_mar_acc   += mar
            self._cal_brow_l_acc += brow_l_rel
            self._cal_brow_r_acc += brow_r_rel
            self._cal_frames += 1
            if self._cal_frames == 30:
                self._neutral_ear_l  = self._cal_ear_l_acc / 30
                self._neutral_ear_r  = self._cal_ear_r_acc / 30
                self._neutral_mar    = self._cal_mar_acc   / 30
                self._neutral_brow_l = self._cal_brow_l_acc / 30
                self._neutral_brow_r = self._cal_brow_r_acc / 30
                self._calibrated = True
            return self.params

        raw = FaceParams()

        # ---- Eyes ----
        # Blink: EAR drops below neutral
        raw.eyeBlinkLeft  = _remap(ear_l, self._neutral_ear_l, 0.05, 0.0, 1.0)
        raw.eyeBlinkRight = _remap(ear_r, self._neutral_ear_r, 0.05, 0.0, 1.0)
        # Wide: EAR above neutral
        raw.eyeWideLeft  = _remap(ear_l, self._neutral_ear_l, self._neutral_ear_l * 1.6, 0.0, 1.0)
        raw.eyeWideRight = _remap(ear_r, self._neutral_ear_r, self._neutral_ear_r * 1.6, 0.0, 1.0)
        # Squint (lower lid push)
        raw.eyeSquintLeft  = _remap(ear_l, self._neutral_ear_l, self._neutral_ear_l * 0.7, 0.0, 0.6)
        raw.eyeSquintRight = _remap(ear_r, self._neutral_ear_r, self._neutral_ear_r * 0.7, 0.0, 0.6)

        # ---- Eyebrows ----
        brow_delta_l = brow_l_rel - self._neutral_brow_l
        brow_delta_r = brow_r_rel - self._neutral_brow_r
        raw.browUpLeft   = _clamp(brow_delta_l * 15.0)
        raw.browUpRight  = _clamp(brow_delta_r * 15.0)
        raw.browDownLeft  = _clamp(-brow_delta_l * 15.0)
        raw.browDownRight = _clamp(-brow_delta_r * 15.0)
        raw.browInnerUp  = _clamp((brow_delta_l + brow_delta_r) * 10.0)

        # ---- Mouth ----
        mouth_delta = mar - self._neutral_mar
        raw.mouthOpen = _remap(mouth_delta, 0.0, 0.12, 0.0, 1.0)
        raw.jawOpen   = _remap(mouth_delta, 0.0, 0.15, 0.0, 1.0)

        # Smile: mouth corners higher than lip center
        mouth_cx = (p(MOUTH_LEFT)[1] + p(MOUTH_RIGHT)[1]) / 2.0
        lip_mid_y = p(MOUTH_TOP)[1]
        smile_val = (lip_mid_y - mouth_cx) / face_h
        raw.mouthSmileLeft  = _remap(smile_val, 0.0, 0.03, 0.0, 1.0)
        raw.mouthSmileRight = _remap(smile_val, 0.0, 0.03, 0.0, 1.0)

        # Frown: corners lower than center
        raw.mouthFrownLeft  = _remap(-smile_val, 0.0, 0.02, 0.0, 1.0)
        raw.mouthFrownRight = _remap(-smile_val, 0.0, 0.02, 0.0, 1.0)

        # Pucker: mouth width narrows
        mouth_w = _dist2d(p(MOUTH_LEFT), p(MOUTH_RIGHT))
        face_w  = _dist2d(p(FACE_LEFT), p(FACE_RIGHT))
        mouth_w_ratio = mouth_w / face_w if face_w > 1e-6 else 0.5
        raw.mouthPucker = _remap(mouth_w_ratio, 0.35, 0.2, 0.0, 1.0)

        # Funnel (like saying 'O')
        raw.mouthFunnel = _clamp(raw.mouthOpen * (1.0 - mouth_w_ratio * 2.0))

        # Mouth left/right shift
        nose_x = p(NOSE_TIP)[0]
        mouth_center_x = (p(MOUTH_LEFT)[0] + p(MOUTH_RIGHT)[0]) / 2.0
        mouth_shift = (mouth_center_x - nose_x) / face_w if face_w > 1e-6 else 0
        raw.mouthLeft  = _remap(mouth_shift, 0.0, -0.03, 0.0, 1.0)
        raw.mouthRight = _remap(mouth_shift, 0.0,  0.03, 0.0, 1.0)

        # ---- Jaw ----
        jaw_x = p(JAW_TIP)[0] - p(NOSE_TIP)[0]
        raw.jawLeft  = _remap(jaw_x / face_w if face_w > 1e-6 else 0, 0.0, -0.02, 0.0, 1.0)
        raw.jawRight = _remap(jaw_x / face_w if face_w > 1e-6 else 0, 0.0,  0.02, 0.0, 1.0)

        # ---- Cheek ----
        raw.cheekSquintLeft  = raw.eyeSquintLeft * 0.8
        raw.cheekSquintRight = raw.eyeSquintRight * 0.8
        # Cheek puff approximation (mouth closed + jaw slightly open)
        raw.cheekPuff = _clamp(raw.jawOpen * 0.5 * (1.0 - raw.mouthOpen))

        # ---- Head Pose ----
        raw.headYaw, raw.headPitch, raw.headRoll = self._estimate_head_pose(p)

        # ---- Smoothing ----
        s = self._smooth
        for field_name in raw.__dataclass_fields__:
            old = getattr(self.params, field_name)
            new = getattr(raw, field_name)
            setattr(self.params, field_name, old + s * (new - old))

        return self.params

    @staticmethod
    def _compute_ear(p, top_ids, bottom_ids, inner_id, outer_id) -> float:
        """Eye Aspect Ratio."""
        v1 = _dist(p(top_ids[0]), p(bottom_ids[0]))
        v2 = _dist(p(top_ids[1]), p(bottom_ids[1]))
        h  = _dist(p(inner_id), p(outer_id))
        if h < 1e-8:
            return 0.3
        return (v1 + v2) / (2.0 * h)

    @staticmethod
    def _estimate_head_pose(p):
        """Rough head pose from key landmarks."""
        nose = np.array(p(NOSE_TIP))
        chin = np.array(p(JAW_TIP))
        left_eye  = np.array(p(LEFT_EYE_OUTER))
        right_eye = np.array(p(RIGHT_EYE_OUTER))
        forehead  = np.array(p(FACE_TOP))

        # Yaw: horizontal asymmetry between eyes and nose
        eye_center = (left_eye + right_eye) / 2
        yaw = math.atan2(nose[0] - eye_center[0], nose[2] - eye_center[2] + 1e-6)

        # Pitch: vertical tilt
        face_vec = chin - forehead
        pitch = math.atan2(face_vec[2], face_vec[1] + 1e-6)

        # Roll: eye line angle
        eye_vec = right_eye - left_eye
        roll = math.atan2(eye_vec[1], eye_vec[0])

        return float(yaw), float(pitch), float(roll)
