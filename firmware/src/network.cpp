/**
 * VRC Facial Tracker - Network Module
 */

#include "network.h"
#include "config.h"
#include <Arduino.h>
#include <WiFi.h>

static unsigned long lastReconnectAttempt = 0;
static const unsigned long RECONNECT_INTERVAL_MS = 5000;
static unsigned long lastLedToggleMs = 0;
static bool ledBlinkState = false;
static bool reconnecting = false;
static unsigned long reconnectStartedMs = 0;
static const unsigned long CONNECTING_WINDOW_MS = 5000;

static void set_led_state(bool on) {
    digitalWrite(WIFI_STATUS_LED_PIN, on ? HIGH : LOW);
}

static void update_connecting_led() {
    unsigned long now = millis();
    if (now - lastLedToggleMs >= WIFI_LED_BLINK_INTERVAL_MS) {
        lastLedToggleMs = now;
        ledBlinkState = !ledBlinkState;
        set_led_state(ledBlinkState);
    }
}

bool network_init() {
    pinMode(WIFI_STATUS_LED_PIN, OUTPUT);
    set_led_state(false);

    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    Serial.print("Connecting to WiFi");
    int timeout = 0;
    reconnecting = true;
    reconnectStartedMs = millis();
    while (WiFi.status() != WL_CONNECTED && timeout < 30) {
        update_connecting_led();
        delay(500);
        Serial.print(".");
        timeout++;
    }
    Serial.println();

    if (WiFi.status() != WL_CONNECTED) {
        reconnecting = false;
        set_led_state(false);
        Serial.println("WiFi connection timeout.");
        return false;
    }

    reconnecting = false;
    set_led_state(true);
    Serial.printf("Connected! IP: %s\n", WiFi.localIP().toString().c_str());
    return true;
}

void network_maintain() {
    wl_status_t status = WiFi.status();
    if (status != WL_CONNECTED) {
        unsigned long now = millis();
        if (now - lastReconnectAttempt > RECONNECT_INTERVAL_MS) {
            lastReconnectAttempt = now;
            Serial.println("WiFi disconnected, reconnecting...");
            WiFi.disconnect();
            WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
            reconnecting = true;
            reconnectStartedMs = now;
        }

        if (reconnecting) {
            if (now - reconnectStartedMs <= CONNECTING_WINDOW_MS) {
                update_connecting_led();
            } else {
                reconnecting = false;
                set_led_state(false);
            }
        } else {
            set_led_state(false);
        }
    } else {
        reconnecting = false;
        set_led_state(true);
    }
}

const char* network_get_ip() {
    static char ip[16];
    IPAddress addr = WiFi.localIP();
    snprintf(ip, sizeof(ip), "%d.%d.%d.%d", addr[0], addr[1], addr[2], addr[3]);
    return ip;
}

bool network_is_connected() {
    return WiFi.status() == WL_CONNECTED;
}
