/**
 * VRC Facial Tracker - Face Tracking Module
 *
 * Phase 2 tracker backend implementation.
 *
 * Backend strategy:
 * - ESP-WHO backend can be enabled when full dependency stack is available.
 * - Heuristic backend is kept as a robust fallback for Arduino-only builds.
 */

#include "tracker.h"
#include "config.h"
#include <Arduino.h>
#include <math.h>

static FaceData smoothed_face = {};

#if TRACKER_BACKEND == TRACKER_BACKEND_ESP_WHO
#define TRACKER_BACKEND_LABEL "esp-who"
#else
#define TRACKER_BACKEND_LABEL "heuristic"
#endif

typedef struct {
    float luma;
    float saturation;
} PixelFeatures;

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

static PixelFeatures get_pixel_features(const camera_fb_t *fb, int x, int y) {
    PixelFeatures features = {0.0f, 0.0f};
    const uint8_t *buf = fb->buf;

    if (fb->format == PIXFORMAT_GRAYSCALE) {
        int idx = y * fb->width + x;
        float gray = (float)buf[idx];
        features.luma = gray;
        features.saturation = 0.0f;
        return features;
    }

    if (fb->format == PIXFORMAT_RGB565) {
        int idx = (y * fb->width + x) * 2;
        uint16_t rgb565 = ((uint16_t)buf[idx + 1] << 8) | buf[idx];

        uint8_t r5 = (rgb565 >> 11) & 0x1F;
        uint8_t g6 = (rgb565 >> 5) & 0x3F;
        uint8_t b5 = rgb565 & 0x1F;

        float r = (float)(r5 * 255) / 31.0f;
        float g = (float)(g6 * 255) / 63.0f;
        float b = (float)(b5 * 255) / 31.0f;

        float maxc = r;
        if (g > maxc) {
            maxc = g;
        }
        if (b > maxc) {
            maxc = b;
        }

        float minc = r;
        if (g < minc) {
            minc = g;
        }
        if (b < minc) {
            minc = b;
        }

        features.luma = 0.299f * r + 0.587f * g + 0.114f * b;
        features.saturation = maxc - minc;
        return features;
    }

    int idx = y * fb->width + x;
    float gray = (float)buf[idx];
    features.luma = gray;
    features.saturation = 0.0f;
    return features;
}

static float region_luma_mean(const camera_fb_t *fb, int x0, int y0, int x1, int y1, int step) {
    float sum = 0.0f;
    uint32_t count = 0;

    if (x0 < 0) x0 = 0;
    if (y0 < 0) y0 = 0;
    if (x1 > fb->width) x1 = fb->width;
    if (y1 > fb->height) y1 = fb->height;

    if (step < 1) {
        step = 1;
    }

    for (int y = y0; y < y1; y += step) {
        for (int x = x0; x < x1; x += step) {
            PixelFeatures px = get_pixel_features(fb, x, y);
            sum += px.luma;
            count++;
        }
    }

    if (count == 0) {
        return 0.0f;
    }

    return sum / (float)count;
}

static float frame_luma_variance(const camera_fb_t *fb, float mean, int step) {
    float var_sum = 0.0f;
    uint32_t sample_count = 0;

    if (step < 1) {
        step = 1;
    }

    for (int y = 0; y < fb->height; y += step) {
        for (int x = 0; x < fb->width; x += step) {
            PixelFeatures px = get_pixel_features(fb, x, y);
            float diff = px.luma - mean;
            var_sum += diff * diff;
            sample_count++;
        }
    }

    if (sample_count == 0) {
        return 0.0f;
    }

    return var_sum / (float)sample_count;
}

static float region_saturation_mean(const camera_fb_t *fb, int x0, int y0, int x1, int y1, int step) {
    float sum = 0.0f;
    uint32_t count = 0;

    if (x0 < 0) x0 = 0;
    if (y0 < 0) y0 = 0;
    if (x1 > fb->width) x1 = fb->width;
    if (y1 > fb->height) y1 = fb->height;

    if (step < 1) {
        step = 1;
    }

    for (int y = y0; y < y1; y += step) {
        for (int x = x0; x < x1; x += step) {
            PixelFeatures px = get_pixel_features(fb, x, y);
            sum += px.saturation;
            count++;
        }
    }

    if (count == 0) {
        return 0.0f;
    }

    return sum / (float)count;
}

void tracker_init() {
    smoothed_face = {};
    Serial.printf("Tracker: Initialized (%s backend)\n", TRACKER_BACKEND_LABEL);
}

const char *tracker_backend_name() {
    return TRACKER_BACKEND_LABEL;
}

#if TRACKER_BACKEND == TRACKER_BACKEND_ESP_WHO
static bool esp_who_warning_printed = false;
#endif

static FaceData tracker_process_heuristic(camera_fb_t *fb) {
    FaceData face = {};

    const float frame_mean = region_luma_mean(fb, 0, 0, fb->width, fb->height, 4);
    const float variance = frame_luma_variance(fb, frame_mean, 4);

    float center_saturation = region_saturation_mean(
        fb,
        (fb->width * 20) / 100,
        (fb->height * 15) / 100,
        (fb->width * 80) / 100,
        (fb->height * 85) / 100,
        4
    );

    const bool brightness_ok = frame_mean > 25.0f && frame_mean < 225.0f;
    const bool texture_ok = variance > 220.0f && variance < 6500.0f;
    const bool color_or_texture_ok = (fb->format == PIXFORMAT_RGB565) ? (center_saturation > 8.0f || texture_ok) : texture_ok;

    face.detected = brightness_ok && texture_ok && color_or_texture_ok;
    if (!face.detected) {
        smoothed_face.detected = false;
        return smoothed_face;
    }

    const int width = fb->width;
    const int height = fb->height;

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

    float left_eye_mean = region_luma_mean(fb, left_eye_x0, eye_y0, left_eye_x1, eye_y1, 2);
    float right_eye_mean = region_luma_mean(fb, right_eye_x0, eye_y0, right_eye_x1, eye_y1, 2);
    float mouth_mean = region_luma_mean(fb, mouth_x0, mouth_y0, mouth_x1, mouth_y1, 2);

    face.eyeClosedLeft = safe_normalize(150.0f - left_eye_mean, 0.0f, 100.0f);
    face.eyeClosedRight = safe_normalize(150.0f - right_eye_mean, 0.0f, 100.0f);
    face.mouthOpen = safe_normalize(150.0f - mouth_mean, 0.0f, 110.0f);
    face.jawOpen = clamp01(face.mouthOpen * 0.9f);

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

FaceData tracker_process(camera_fb_t *fb) {
    if (!fb || !fb->buf || fb->len == 0) {
        return FaceData{};
    }

    if (fb->width <= 0 || fb->height <= 0) {
        return FaceData{};
    }

#if TRACKER_BACKEND == TRACKER_BACKEND_ESP_WHO
    if (!esp_who_warning_printed) {
        Serial.println("Tracker: ESP-WHO backend selected, but model integration is not linked in this build. Falling back to heuristic backend.");
        esp_who_warning_printed = true;
    }
    return tracker_process_heuristic(fb);
#else
    return tracker_process_heuristic(fb);
#endif
}
