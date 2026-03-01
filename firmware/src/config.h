/**
 * VRC Facial Tracker - Configuration
 *
 * Edit this file to match your network setup.
 */

#pragma once

// ============================================================
// WiFi Configuration
// ============================================================
#define WIFI_SSID     "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

// ============================================================
// OSC Configuration
// ============================================================
#define OSC_TARGET_IP   "192.168.1.100"   // PC IP running VRChat
#define OSC_TARGET_PORT 9000              // VRChat OSC receive port
#define OSC_LOCAL_PORT  9001              // Local OSC port

// ============================================================
// Camera Configuration
// ============================================================
#define CAMERA_FRAME_SIZE   FRAMESIZE_QVGA   // 320x240
#if TRACKER_BACKEND == TRACKER_BACKEND_STREAM
  #define CAMERA_PIXEL_FORMAT PIXFORMAT_JPEG   // JPEG for streaming efficiency
  #define CAMERA_FB_COUNT     2
#else
  #define CAMERA_PIXEL_FORMAT PIXFORMAT_RGB565  // RGB565 for on-device inference
  #define CAMERA_FB_COUNT     2
#endif

// ============================================================
// Tracking Configuration
// ============================================================
#define TRACKING_FPS        30      // Target tracking framerate
#define SMOOTHING_FACTOR    0.3f    // Expression smoothing (0-1, lower = smoother)
#define DETECTION_THRESHOLD 0.5f    // Face detection confidence threshold

#define TRACKER_BACKEND_HEURISTIC 1
#define TRACKER_BACKEND_ESP_WHO   2
#define TRACKER_BACKEND_STREAM    3   // PC-side processing via MJPEG stream
#ifndef TRACKER_BACKEND
  #define TRACKER_BACKEND           TRACKER_BACKEND_STREAM
#endif

// ============================================================
// MJPEG Stream Server (for TRACKER_BACKEND_STREAM)
// ============================================================
#define STREAM_SERVER_PORT  81

// ============================================================
// Runtime Debug / Health Monitoring
// ============================================================
#define DEBUG_STATS_INTERVAL_MS 1000

// ============================================================
// WiFi Status LED
// ============================================================
#define WIFI_STATUS_LED_PIN 21
#define WIFI_LED_BLINK_INTERVAL_MS 250

// ============================================================
// Hardware Pins (XIAO ESP32S3 Sense - OV2640)
// ============================================================
#define PWDN_GPIO_NUM     -1
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM     10
#define SIOD_GPIO_NUM     40
#define SIOC_GPIO_NUM     39

#define Y9_GPIO_NUM       48
#define Y8_GPIO_NUM       11
#define Y7_GPIO_NUM       12
#define Y6_GPIO_NUM       14
#define Y5_GPIO_NUM       16
#define Y4_GPIO_NUM       18
#define Y3_GPIO_NUM       17
#define Y2_GPIO_NUM       15
#define VSYNC_GPIO_NUM    38
#define HREF_GPIO_NUM     47
#define PCLK_GPIO_NUM     13
