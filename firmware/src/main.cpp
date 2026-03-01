/**
 * VRC Facial Tracker - Main Entry Point
 *
 * Captures face images via OV2640 camera on XIAO ESP32S3 Sense,
 * performs facial landmark detection, and streams expression
 * parameters to VRChat over WiFi/OSC.
 */

#include <Arduino.h>
#include "config.h"
#include "camera.h"
#include "network.h"
#include "tracker.h"
#include "osc_sender.h"

static unsigned long stats_window_start_ms = 0;
static uint32_t frames_in_window = 0;
static uint32_t capture_fail_count = 0;
static size_t last_frame_size_bytes = 0;

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("VRC Facial Tracker - Initializing...");

    // Initialize camera
    if (!camera_init()) {
        Serial.println("ERROR: Camera initialization failed!");
        while (1) { delay(1000); }
    }
    Serial.println("Camera initialized.");

    // Initialize WiFi
    if (!network_init()) {
        Serial.println("ERROR: WiFi connection failed!");
        while (1) { delay(1000); }
    }
    Serial.println("WiFi connected.");

    // Initialize OSC sender
    osc_init();
    Serial.println("OSC sender initialized.");

    // Initialize face tracker
    tracker_init();
    Serial.printf("Face tracker initialized. Backend: %s\n", tracker_backend_name());

    Serial.println("Setup complete. Starting tracking loop...");
    stats_window_start_ms = millis();
}

void loop() {
    // Capture frame
    camera_fb_t *fb = camera_capture();
    if (!fb) {
        capture_fail_count++;
        return;
    }

    frames_in_window++;
    last_frame_size_bytes = fb->len;

    // Run face tracking inference
    FaceData face = tracker_process(fb);

    // Release frame buffer
    camera_release(fb);

    // Send tracking data via OSC if face detected
    if (face.detected) {
        osc_send(face);
    }

    // Maintain WiFi connection
    network_maintain();

    unsigned long now = millis();
    unsigned long elapsed = now - stats_window_start_ms;
    if (elapsed >= DEBUG_STATS_INTERVAL_MS) {
        float fps = (frames_in_window * 1000.0f) / (float)elapsed;
        OscStats osc_stats = osc_get_stats();
        float osc_msgs_per_sec = (osc_stats.interval_success * 1000.0f) / (float)elapsed;

        Serial.printf(
            "[DBG] frame=%uB fps=%.1f cap_fail=%lu heap=%uB psram=%uB osc_ok=%lu osc_fail=%lu osc_rate=%.1f msg/s\n",
            (unsigned int)last_frame_size_bytes,
            fps,
            (unsigned long)capture_fail_count,
            (unsigned int)ESP.getFreeHeap(),
            (unsigned int)ESP.getFreePsram(),
            (unsigned long)osc_stats.interval_success,
            (unsigned long)osc_stats.interval_failure,
            osc_msgs_per_sec
        );

        frames_in_window = 0;
        capture_fail_count = 0;
        stats_window_start_ms = now;
        osc_reset_interval_stats();
    }
}
