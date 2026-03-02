/**
 * VRC Facial Tracker - UDP Frame Streamer
 *
 * Sends camera frames as raw JPEG over UDP for minimum latency.
 * Replaces HTTP/MJPEG streaming with zero-overhead UDP transport.
 *
 * Protocol:
 *   PC  → ESP32 : 1-byte commands (0x01=register, 0x02=heartbeat)
 *   ESP32 → PC  : [2B frame_id LE] + [raw JPEG data]
 *
 * The PC sends a REGISTER packet to start receiving frames.
 * Heartbeats must be sent every <5 seconds or streaming stops.
 */

#pragma once

#include <stdint.h>

/// Start the UDP stream task on the given port.
void udp_stream_start(int port = 5555);

/// Returns true if a PC peer is registered and active.
bool udp_stream_has_peer();

/// Total frames sent since boot.
uint32_t udp_stream_frame_count();

/// Measured send FPS (updated every second).
float udp_stream_fps();
