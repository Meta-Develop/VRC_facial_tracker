/**
 * VRC Facial Tracker - Camera Module Header
 */

#pragma once

#include "esp_camera.h"

/**
 * Initialize the OV2640 camera on XIAO ESP32S3 Sense.
 * @return true if initialization succeeded.
 */
bool camera_init();

/**
 * Capture a single frame from the camera.
 * @return Pointer to frame buffer, or nullptr on failure.
 */
camera_fb_t* camera_capture();

/**
 * Release a previously captured frame buffer.
 * @param fb Pointer to frame buffer to release.
 */
void camera_release(camera_fb_t *fb);
