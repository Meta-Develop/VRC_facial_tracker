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
    Serial.println("Face tracker initialized.");

    Serial.println("Setup complete. Starting tracking loop...");
}

void loop() {
    // Capture frame
    camera_fb_t *fb = camera_capture();
    if (!fb) {
        Serial.println("WARN: Frame capture failed, skipping.");
        return;
    }

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
}
