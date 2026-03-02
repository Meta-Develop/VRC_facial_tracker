/**
 * VRC Facial Tracker - MJPEG Stream Server (DEPRECATED)
 *
 * Replaced by udp_stream.cpp for lower latency.
 * Kept for reference. This file is excluded from compilation.
 */

#include "config.h"

/* Disabled: replaced by UDP streaming (udp_stream.cpp) */
#if 0  /* was: TRACKER_BACKEND == TRACKER_BACKEND_STREAM */

#include "stream_server.h"
#include <Arduino.h>
#include <WiFi.h>
#include <esp_http_server.h>
#include <esp_camera.h>

#define PART_BOUNDARY "vrcfacetracker"
static const char *STREAM_CONTENT_TYPE =
    "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char *STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char *STREAM_PART =
    "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

static httpd_handle_t s_httpd = NULL;
static volatile uint32_t s_frame_count = 0;
static volatile int s_client_count = 0;

// ---------------------------------------------------------------
// /stream handler — MJPEG multipart
// ---------------------------------------------------------------
static esp_err_t stream_handler(httpd_req_t *req) {
    esp_err_t res = ESP_OK;
    char part_buf[64];

    res = httpd_resp_set_type(req, STREAM_CONTENT_TYPE);
    if (res != ESP_OK) return res;

    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_hdr(req, "Cache-Control", "no-cache, no-store, must-revalidate");

    s_client_count++;
    Serial.printf("[STREAM] Client connected (%d active)\n", s_client_count);

    while (true) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (!fb) {
            Serial.println("[STREAM] Camera capture failed");
            vTaskDelay(pdMS_TO_TICKS(10));
            continue;
        }

        // If camera is not JPEG, convert
        uint8_t *jpg_buf = NULL;
        size_t jpg_len = 0;
        bool converted = false;

        if (fb->format != PIXFORMAT_JPEG) {
            converted = frame2jpg(fb, 80, &jpg_buf, &jpg_len);
            if (!converted) {
                esp_camera_fb_return(fb);
                Serial.println("[STREAM] JPEG conversion failed");
                continue;
            }
        } else {
            jpg_buf = fb->buf;
            jpg_len = fb->len;
        }

        // Send boundary
        res = httpd_resp_send_chunk(req, STREAM_BOUNDARY, strlen(STREAM_BOUNDARY));
        if (res == ESP_OK) {
            // Send part header
            size_t hlen = snprintf(part_buf, sizeof(part_buf), STREAM_PART, (unsigned)jpg_len);
            res = httpd_resp_send_chunk(req, part_buf, hlen);
        }
        if (res == ESP_OK) {
            // Send JPEG data
            res = httpd_resp_send_chunk(req, (const char *)jpg_buf, jpg_len);
        }

        if (converted && jpg_buf) free(jpg_buf);
        esp_camera_fb_return(fb);

        if (res != ESP_OK) break;

        s_frame_count++;
    }

    s_client_count--;
    Serial.printf("[STREAM] Client disconnected (%d active)\n", s_client_count);
    return res;
}

// ---------------------------------------------------------------
// / handler — Status page
// ---------------------------------------------------------------
static esp_err_t index_handler(httpd_req_t *req) {
    char buf[512];
    snprintf(buf, sizeof(buf),
        "<html><head><title>VRC Facial Tracker</title></head>"
        "<body style='font-family:monospace;background:#111;color:#eee;padding:2em'>"
        "<h1>VRC Facial Tracker</h1>"
        "<p>Stream URL: <a href='/stream' style='color:#4af'>http://%s:%d/stream</a></p>"
        "<p>Frames served: %lu</p>"
        "<img src='/stream' style='max-width:640px'/>"
        "</body></html>",
        WiFi.localIP().toString().c_str(),
        STREAM_SERVER_PORT,
        (unsigned long)s_frame_count
    );

    httpd_resp_set_type(req, "text/html");
    return httpd_resp_send(req, buf, strlen(buf));
}

// ---------------------------------------------------------------
// Public API
// ---------------------------------------------------------------
void stream_server_start(int port) {
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = port;
    config.ctrl_port = port + 1;
    config.max_open_sockets = 2;
    config.stack_size = 8192;

    if (httpd_start(&s_httpd, &config) == ESP_OK) {
        httpd_uri_t stream_uri = {
            .uri = "/stream",
            .method = HTTP_GET,
            .handler = stream_handler,
            .user_ctx = NULL
        };
        httpd_register_uri_handler(s_httpd, &stream_uri);

        httpd_uri_t index_uri = {
            .uri = "/",
            .method = HTTP_GET,
            .handler = index_handler,
            .user_ctx = NULL
        };
        httpd_register_uri_handler(s_httpd, &index_uri);

        Serial.printf("[STREAM] Server started on port %d\n", port);
    } else {
        Serial.println("[STREAM] Failed to start server!");
    }
}

bool stream_server_has_clients() {
    return s_client_count > 0;
}

uint32_t stream_server_frame_count() {
    return s_frame_count;
}

#endif // TRACKER_BACKEND == TRACKER_BACKEND_STREAM
