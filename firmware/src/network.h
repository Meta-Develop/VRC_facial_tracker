/**
 * VRC Facial Tracker - Network Module Header
 */

#pragma once

/**
 * Initialize WiFi connection using config.h credentials.
 * @return true if WiFi connected successfully.
 */
bool network_init();

/**
 * Maintain WiFi connection (reconnect if dropped).
 */
void network_maintain();

/**
 * Get the local IP address as a string.
 * @return IP address string.
 */
const char* network_get_ip();

/**
 * Check if WiFi is currently connected.
 * @return true if connected.
 */
bool network_is_connected();
