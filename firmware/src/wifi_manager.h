/**
 * VRC Facial Tracker - WiFi Manager
 *
 * Provides automatic WiFi credential management with captive portal.
 *
 * On first boot (or if saved credentials fail), the ESP32 creates a
 * WiFi access point "VRC-Tracker-XXXX" with a web-based configuration
 * portal.  Users connect to it with a phone / laptop and enter their
 * home WiFi credentials.  The credentials are saved to Preferences
 * (NVS) and used on subsequent boots.
 *
 * Reset button held for 5 s clears saved credentials and re-enters
 * AP mode on next reboot.
 */

#pragma once

#include <Arduino.h>

/**
 * Initialise WiFi with credential management.
 *
 * 1. Tries stored credentials from NVS.
 * 2. Falls back to compile-time WIFI_SSID / WIFI_PASSWORD.
 * 3. If still not connected → starts AP config portal.
 *
 * @return true when connected to a WiFi network in STA mode.
 */
bool wifi_manager_init();

/**
 * Must be called in loop().  Handles:
 *  - Portal requests while in AP mode
 *  - STA reconnect when signal drops
 */
void wifi_manager_loop();

/**
 * Erase saved credentials from NVS.
 * Call this then reboot to force portal mode.
 */
void wifi_manager_reset();

/**
 * @return true if we are currently in AP (portal) mode,
 *         false if connected in STA mode.
 */
bool wifi_manager_is_portal_active();

/**
 * @return the IP address string (AP IP or STA IP).
 */
const char* wifi_manager_get_ip();
