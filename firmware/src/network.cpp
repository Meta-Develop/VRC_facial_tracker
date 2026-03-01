/**
 * VRC Facial Tracker - Network Module
 */

#include "network.h"
#include "config.h"
#include <WiFi.h>

static unsigned long lastReconnectAttempt = 0;
static const unsigned long RECONNECT_INTERVAL_MS = 5000;

bool network_init() {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    Serial.print("Connecting to WiFi");
    int timeout = 0;
    while (WiFi.status() != WL_CONNECTED && timeout < 30) {
        delay(500);
        Serial.print(".");
        timeout++;
    }
    Serial.println();

    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi connection timeout.");
        return false;
    }

    Serial.printf("Connected! IP: %s\n", WiFi.localIP().toString().c_str());
    return true;
}

void network_maintain() {
    if (WiFi.status() != WL_CONNECTED) {
        unsigned long now = millis();
        if (now - lastReconnectAttempt > RECONNECT_INTERVAL_MS) {
            lastReconnectAttempt = now;
            Serial.println("WiFi disconnected, reconnecting...");
            WiFi.disconnect();
            WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
        }
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
