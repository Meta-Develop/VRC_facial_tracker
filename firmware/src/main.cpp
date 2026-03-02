/**
 * VRC Facial Tracker - Main Entry Point
 *
 * Three operating modes (selected at compile time via TRACKER_BACKEND):
 *
 *   STREAM    — ESP32 acts as WiFi camera. PC app does MediaPipe
 *               face mesh and sends OSC to VRChat. (default)
 *   ESP_WHO   — On-device ESP-DL face detection (5-point keypoints).
 *   HEURISTIC — Lightweight region-based analysis (no ML).
 */

#include <Arduino.h>
#include "config.h"
#include "camera.h"

#if TRACKER_BACKEND == TRACKER_BACKEND_STREAM
  #include "wifi_manager.h"
  #include "udp_stream.h"
#else
  #include "network.h"
  #include "tracker.h"
  #include "osc_sender.h"
#endif

/* ESP-IDF + Arduino hybrid mode needs explicit app_main() entry point. */
#if defined(TRACKER_USE_ESP_DL)
#ifdef __cplusplus
extern "C" {
#endif
void app_main(void) {
    initArduino();
    setup();
    for (;;) { loop(); }
}
#ifdef __cplusplus
}
#endif
#endif

static unsigned long stats_window_start_ms = 0;
static uint32_t frames_in_window = 0;

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("=== VRC Facial Tracker ===");
#if TRACKER_BACKEND == TRACKER_BACKEND_STREAM
    Serial.println("Mode: STREAM (PC-side processing)");
#elif TRACKER_BACKEND == TRACKER_BACKEND_ESP_WHO
    Serial.println("Mode: ESP-DL (on-device face detection)");
#else
    Serial.println("Mode: HEURISTIC (on-device, no ML)");
#endif

    // Initialize camera
    if (!camera_init()) {
        Serial.println("ERROR: Camera initialization failed!");
        while (1) { delay(1000); }
    }
    Serial.println("Camera initialized.");

    // Initialize WiFi
#if TRACKER_BACKEND == TRACKER_BACKEND_STREAM
    // WiFi Manager: tries stored creds → compile-time creds → AP portal
    bool wifi_ok = wifi_manager_init();
    if (!wifi_ok) {
        // AP portal is running — user needs to configure WiFi
        // We still start camera + stream server once WiFi is set
        Serial.println("Waiting for WiFi config via AP portal...");
        while (wifi_manager_is_portal_active()) {
            wifi_manager_loop();
            delay(10);
        }
        // After portal saves creds, ESP reboots — but just in case:
    }
    Serial.printf("WiFi connected. IP: %s\n", wifi_manager_get_ip());

    // Start UDP frame streamer
    udp_stream_start(UDP_STREAM_PORT);
    Serial.printf("UDP stream: port %d (send REGISTER to start)\n",
                  UDP_STREAM_PORT);
    Serial.println("Waiting for PC app to connect...");
#else
    // On-device modes use simpler network module
    if (!network_init()) {
        Serial.println("WARNING: WiFi failed. Running in offline mode.");
    } else {
        Serial.printf("WiFi connected. IP: %s\n", network_get_ip());
    }

    // Initialize OSC + tracker for on-device modes
    osc_init();
    tracker_init();
    Serial.printf("Tracker backend: %s\n", tracker_backend_name());
#endif

    Serial.println("Setup complete.");
    stats_window_start_ms = millis();
}

void loop() {
#if TRACKER_BACKEND == TRACKER_BACKEND_STREAM
    // In stream mode, the HTTP server handles frame capture on its own thread.
    // Main loop just maintains WiFi and prints stats.
    wifi_manager_loop();

    unsigned long now = millis();
    unsigned long elapsed = now - stats_window_start_ms;
    if (elapsed >= DEBUG_STATS_INTERVAL_MS) {
        Serial.printf(
            "[DBG] udp_fps=%.1f frames=%lu peer=%d heap=%uB psram=%uB\n",
            udp_stream_fps(),
            (unsigned long)udp_stream_frame_count(),
            udp_stream_has_peer() ? 1 : 0,
            (unsigned int)ESP.getFreeHeap(),
            (unsigned int)ESP.getFreePsram()
        );
        stats_window_start_ms = now;
    }
    delay(100); // low duty — streaming runs in dedicated task

#else
    // On-device inference mode (ESP_WHO or HEURISTIC)
    camera_fb_t *fb = camera_capture();
    if (!fb) { return; }

    frames_in_window++;

    FaceData face = tracker_process(fb);
    camera_release(fb);

    if (face.detected && network_is_connected()) {
        osc_send(face);
    }

    network_maintain();

    unsigned long now = millis();
    unsigned long elapsed = now - stats_window_start_ms;
    if (elapsed >= DEBUG_STATS_INTERVAL_MS) {
        float fps = (frames_in_window * 1000.0f) / (float)elapsed;
        Serial.printf(
            "[DBG] fps=%.1f heap=%uB psram=%uB\n",
            fps,
            (unsigned int)ESP.getFreeHeap(),
            (unsigned int)ESP.getFreePsram()
        );
        frames_in_window = 0;
        stats_window_start_ms = now;
    }
#endif
}
