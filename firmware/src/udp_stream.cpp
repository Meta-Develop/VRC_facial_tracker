/**
 * VRC Facial Tracker - UDP Frame Streamer
 *
 * Captures camera frames and blasts them over UDP with minimal overhead.
 * Uses raw POSIX/lwIP sockets (not Arduino WiFiUDP) to avoid the 1460-byte
 * buffer limitation and eliminate unnecessary copies.
 *
 * Frame packet: [2 bytes frame_id (LE)] + [raw JPEG payload]
 * IP fragmentation handles payloads > MTU on the local WiFi network.
 *
 * A dedicated FreeRTOS task on core 1 runs the tight capture→send loop.
 */

#include "config.h"

#if TRACKER_BACKEND == TRACKER_BACKEND_STREAM

#include "udp_stream.h"
#include <Arduino.h>
#include <esp_camera.h>

#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <unistd.h>
#include <string.h>

// ---------------------------------------------------------------------------
// Protocol constants
// ---------------------------------------------------------------------------
#define CMD_REGISTER    0x01
#define CMD_HEARTBEAT   0x02
#define PEER_TIMEOUT_MS 5000
#define MAX_JPEG_SIZE   (48 * 1024)   // 48 KB max (plenty for QVGA)

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
static int                s_sock = -1;
static struct sockaddr_in s_peer_addr;
static volatile bool      s_has_peer     = false;
static volatile uint32_t  s_last_hb_ms   = 0;
static volatile uint32_t  s_frame_count  = 0;
static volatile float     s_fps          = 0.0f;
static uint16_t           s_frame_id     = 0;
static uint8_t           *s_send_buf     = NULL;   // PSRAM

// ---------------------------------------------------------------------------
// Stream task — runs on core 1
// ---------------------------------------------------------------------------
static void stream_task(void * /*param*/) {
    uint8_t recv_buf[8];
    struct sockaddr_in from_addr;
    socklen_t from_len;

    uint32_t fps_frames   = 0;
    uint32_t fps_start_ms = millis();

    for (;;) {
        /* ---- 1. Check for incoming commands (non-blocking) ---- */
        from_len = sizeof(from_addr);
        int n = recvfrom(s_sock, recv_buf, sizeof(recv_buf), MSG_DONTWAIT,
                         (struct sockaddr *)&from_addr, &from_len);
        if (n > 0 && (recv_buf[0] == CMD_REGISTER ||
                      recv_buf[0] == CMD_HEARTBEAT)) {
            s_peer_addr = from_addr;
            s_has_peer  = true;
            s_last_hb_ms = millis();

            if (recv_buf[0] == CMD_REGISTER) {
                char ip_str[INET_ADDRSTRLEN];
                inet_ntoa_r(from_addr.sin_addr, ip_str, sizeof(ip_str));
                Serial.printf("[UDP] Peer registered: %s:%d\n",
                              ip_str, ntohs(from_addr.sin_port));
            }
        }

        /* ---- 2. Peer timeout check ---- */
        if (s_has_peer && (millis() - s_last_hb_ms > PEER_TIMEOUT_MS)) {
            Serial.println("[UDP] Peer timeout — pausing stream");
            s_has_peer = false;
        }

        /* ---- 3. No peer → sleep and retry ---- */
        if (!s_has_peer) {
            vTaskDelay(pdMS_TO_TICKS(50));
            continue;
        }

        /* ---- 4. Capture frame (blocks until camera produces one) ---- */
        camera_fb_t *fb = esp_camera_fb_get();
        if (!fb) {
            vTaskDelay(pdMS_TO_TICKS(1));
            continue;
        }

        /* Skip oversized frames */
        if (fb->len > MAX_JPEG_SIZE) {
            esp_camera_fb_return(fb);
            continue;
        }

        /* If camera didn't produce JPEG, convert (rare with PIXFORMAT_JPEG) */
        uint8_t *jpg_buf = fb->buf;
        size_t   jpg_len = fb->len;
        bool     converted = false;

        if (fb->format != PIXFORMAT_JPEG) {
            converted = frame2jpg(fb, CAMERA_JPEG_QUALITY, &jpg_buf, &jpg_len);
            if (!converted) {
                esp_camera_fb_return(fb);
                continue;
            }
        }

        /* ---- 5. Build & send packet: [2B id] + [JPEG] ---- */
        s_send_buf[0] = (uint8_t)(s_frame_id & 0xFF);
        s_send_buf[1] = (uint8_t)((s_frame_id >> 8) & 0xFF);
        memcpy(s_send_buf + 2, jpg_buf, jpg_len);

        int sent = sendto(s_sock, s_send_buf, 2 + jpg_len, 0,
                          (struct sockaddr *)&s_peer_addr,
                          sizeof(s_peer_addr));

        if (converted && jpg_buf) free(jpg_buf);
        esp_camera_fb_return(fb);

        if (sent > 0) {
            s_frame_id++;
            s_frame_count++;
            fps_frames++;
        }

        /* ---- 6. FPS measurement ---- */
        uint32_t now = millis();
        uint32_t elapsed = now - fps_start_ms;
        if (elapsed >= 1000) {
            s_fps = fps_frames * 1000.0f / (float)elapsed;
            fps_frames   = 0;
            fps_start_ms = now;
        }
    }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

void udp_stream_start(int port) {
    /* Allocate PSRAM send buffer */
    s_send_buf = (uint8_t *)ps_malloc(MAX_JPEG_SIZE + 2);
    if (!s_send_buf) {
        Serial.println("[UDP] FATAL: PSRAM alloc failed for send buffer");
        return;
    }

    /* Create UDP socket */
    s_sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (s_sock < 0) {
        Serial.println("[UDP] FATAL: socket() failed");
        return;
    }

    /* Bind to port */
    struct sockaddr_in addr = {};
    addr.sin_family      = AF_INET;
    addr.sin_port        = htons(port);
    addr.sin_addr.s_addr = INADDR_ANY;
    if (bind(s_sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        Serial.println("[UDP] FATAL: bind() failed");
        close(s_sock);
        s_sock = -1;
        return;
    }

    Serial.printf("[UDP] Listening on port %d (waiting for peer REGISTER)\n",
                  port);

    /* Launch streaming task pinned to core 1 (core 0 = WiFi/system) */
    xTaskCreatePinnedToCore(stream_task, "udp_stream",
                            8192,   /* stack */
                            NULL,   /* param */
                            5,      /* priority */
                            NULL,   /* handle */
                            1       /* core */);
}

bool udp_stream_has_peer() {
    return s_has_peer;
}

uint32_t udp_stream_frame_count() {
    return s_frame_count;
}

float udp_stream_fps() {
    return s_fps;
}

#endif /* TRACKER_BACKEND == TRACKER_BACKEND_STREAM */
