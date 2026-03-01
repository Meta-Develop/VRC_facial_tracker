/**
 * VRC Facial Tracker - MJPEG Stream Server
 *
 * Serves camera frames as MJPEG over HTTP for PC-side processing.
 * Accessible at http://<device-ip>:81/stream
 */

#pragma once

#include <stdint.h>

/// Start the HTTP MJPEG stream server on the given port.
void stream_server_start(int port = 81);

/// Returns true if at least one client is connected to the stream.
bool stream_server_has_clients();

/// Returns total frames served since boot.
uint32_t stream_server_frame_count();
