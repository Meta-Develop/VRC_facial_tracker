/**
 * VRC Facial Tracker - Face Tracking Module Header
 */

#pragma once

#include "esp_camera.h"

/**
 * Face tracking result data structure.
 * Contains normalized expression parameters (0.0 - 1.0).
 */
struct FaceData {
    bool detected;

    // Eye tracking
    float eyeClosedLeft;
    float eyeClosedRight;
    float eyeSquintLeft;
    float eyeSquintRight;
    float eyeWideLeft;
    float eyeWideRight;

    // Eyebrow
    float browUpLeft;
    float browUpRight;
    float browDownLeft;
    float browDownRight;

    // Mouth
    float mouthOpen;
    float mouthSmile;
    float mouthFrown;
    float mouthPucker;

    // Jaw
    float jawOpen;
    float jawLeft;
    float jawRight;

    // Cheek
    float cheekPuff;

    // Tongue
    float tongueOut;
};

/**
 * Initialize the face tracking engine.
 */
void tracker_init();

/**
 * Process a camera frame and extract facial expression data.
 * @param fb Camera frame buffer.
 * @return FaceData with expression parameters.
 */
FaceData tracker_process(camera_fb_t *fb);
