/**
 * VRC Facial Tracker - Face Tracking Module
 *
 * Lightweight on-device face presence and expression estimation.
 * Uses grayscale region statistics as a fallback approach for
 * low-latency embedded execution.
 */

#include "tracker.h"
#include "config.h"
#include <Arduino.h>

static FaceData smoothed_face = {};

static float clamp01(float value) {
    if (value < 0.0f) {
        return 0.0f;
    }
    if (value > 1.0f) {
        return 1.0f;
    }
    return value;
}

static float safe_normalize(float value, float min_value, float max_value) {
    if (max_value <= min_value) {
        return 0.0f;
    }
    return clamp01((value - min_value) / (max_value - min_value));
}

static float region_mean(const uint8_t *buf, int width, int height, int x0, int y0, int x1, int y1, int step) {
    uint32_t sum = 0;
    uint32_t count = 0;

    if (x0 < 0) x0 = 0;
    if (y0 < 0) y0 = 0;
    if (x1 > width) x1 = width;
    if (y1 > height) y1 = height;

    if (step < 1) {
        step = 1;
    }

    for (int y = y0; y < y1; y += step) {
        const uint8_t *row = buf + (y * width);
        for (int x = x0; x < x1; x += step) {
            sum += row[x];
            count++;
        }
    }

    if (count == 0) {
        return 0.0f;
    }

    return (float)sum / (float)count;
}

void tracker_init() {
    smoothed_face = {};
    Serial.println("Tracker: Initialized (lightweight detection mode)");
}

FaceData tracker_process(camera_fb_t *fb) {
    FaceData face = {};

    if (!fb || !fb->buf || fb->len == 0) {
        return face;
    }

    const int width = fb->width;
    const int height = fb->height;

    if (width <= 0 || height <= 0) {
        return face;
    }

    const int sample_step = 4;
    const float frame_mean = region_mean(fb->buf, width, height, 0, 0, width, height, sample_step);

    uint32_t var_sum = 0;
    uint32_t sample_count = 0;
    for (int y = 0; y < height; y += sample_step) {
        const uint8_t *row = fb->buf + (y * width);
        for (int x = 0; x < width; x += sample_step) {
            int diff = (int)row[x] - (int)frame_mean;
            var_sum += (uint32_t)(diff * diff);
            sample_count++;
        }
    }

    float variance = 0.0f;
    if (sample_count > 0) {
        variance = (float)var_sum / (float)sample_count;
    }

    const bool brightness_ok = frame_mean > 25.0f && frame_mean < 225.0f;
    const bool texture_ok = variance > 200.0f && variance < 5000.0f;
    face.detected = brightness_ok && texture_ok;

    if (!face.detected) {
        smoothed_face.detected = false;
        return smoothed_face;
    }

    const int left_eye_x0 = (width * 18) / 100;
    const int left_eye_x1 = (width * 42) / 100;
    const int right_eye_x0 = (width * 58) / 100;
    const int right_eye_x1 = (width * 82) / 100;
    const int eye_y0 = (height * 20) / 100;
    const int eye_y1 = (height * 45) / 100;

    const int mouth_x0 = (width * 30) / 100;
    const int mouth_x1 = (width * 70) / 100;
    const int mouth_y0 = (height * 55) / 100;
    const int mouth_y1 = (height * 85) / 100;

    float left_eye_mean = region_mean(fb->buf, width, height, left_eye_x0, eye_y0, left_eye_x1, eye_y1, 2);
    float right_eye_mean = region_mean(fb->buf, width, height, right_eye_x0, eye_y0, right_eye_x1, eye_y1, 2);
    float mouth_mean = region_mean(fb->buf, width, height, mouth_x0, mouth_y0, mouth_x1, mouth_y1, 2);

    float eye_closed_left_raw = safe_normalize(150.0f - left_eye_mean, 0.0f, 100.0f);
    float eye_closed_right_raw = safe_normalize(150.0f - right_eye_mean, 0.0f, 100.0f);
    float mouth_open_raw = safe_normalize(150.0f - mouth_mean, 0.0f, 110.0f);
    float jaw_open_raw = clamp01(mouth_open_raw * 0.9f);

    face.eyeClosedLeft = eye_closed_left_raw;
    face.eyeClosedRight = eye_closed_right_raw;
    face.mouthOpen = mouth_open_raw;
    face.jawOpen = jaw_open_raw;

    face.eyeSquintLeft = 0.0f;
    face.eyeSquintRight = 0.0f;
    face.eyeWideLeft = 0.0f;
    face.eyeWideRight = 0.0f;
    face.browUpLeft = 0.0f;
    face.browUpRight = 0.0f;
    face.browDownLeft = 0.0f;
    face.browDownRight = 0.0f;
    face.mouthSmile = 0.0f;
    face.mouthFrown = 0.0f;
    face.mouthPucker = 0.0f;
    face.jawLeft = 0.0f;
    face.jawRight = 0.0f;
    face.cheekPuff = 0.0f;
    face.tongueOut = 0.0f;

    smoothed_face.detected = true;
    smoothed_face.eyeClosedLeft = smoothed_face.eyeClosedLeft + SMOOTHING_FACTOR * (face.eyeClosedLeft - smoothed_face.eyeClosedLeft);
    smoothed_face.eyeClosedRight = smoothed_face.eyeClosedRight + SMOOTHING_FACTOR * (face.eyeClosedRight - smoothed_face.eyeClosedRight);
    smoothed_face.mouthOpen = smoothed_face.mouthOpen + SMOOTHING_FACTOR * (face.mouthOpen - smoothed_face.mouthOpen);
    smoothed_face.jawOpen = smoothed_face.jawOpen + SMOOTHING_FACTOR * (face.jawOpen - smoothed_face.jawOpen);

    smoothed_face.eyeSquintLeft = face.eyeSquintLeft;
    smoothed_face.eyeSquintRight = face.eyeSquintRight;
    smoothed_face.eyeWideLeft = face.eyeWideLeft;
    smoothed_face.eyeWideRight = face.eyeWideRight;
    smoothed_face.browUpLeft = face.browUpLeft;
    smoothed_face.browUpRight = face.browUpRight;
    smoothed_face.browDownLeft = face.browDownLeft;
    smoothed_face.browDownRight = face.browDownRight;
    smoothed_face.mouthSmile = face.mouthSmile;
    smoothed_face.mouthFrown = face.mouthFrown;
    smoothed_face.mouthPucker = face.mouthPucker;
    smoothed_face.jawLeft = face.jawLeft;
    smoothed_face.jawRight = face.jawRight;
    smoothed_face.cheekPuff = face.cheekPuff;
    smoothed_face.tongueOut = face.tongueOut;

    return smoothed_face;
}
