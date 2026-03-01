/**
 * VRC Facial Tracker - OSC Sender Module
 */

#include "osc_sender.h"
#include "config.h"
#include <WiFiUdp.h>
#include <OSCMessage.h>

static WiFiUDP udp;
static OscStats stats = {};

void osc_init() {
    udp.begin(OSC_LOCAL_PORT);
    Serial.printf("OSC: Sending to %s:%d\n", OSC_TARGET_IP, OSC_TARGET_PORT);
}

/**
 * Send a single float OSC parameter.
 */
static bool send_param(const char *address, float value) {
    OSCMessage msg(address);
    msg.add(value);
    udp.beginPacket(OSC_TARGET_IP, OSC_TARGET_PORT);
    msg.send(udp);
    bool ok = udp.endPacket() == 1;
    msg.empty();
    return ok;
}

void osc_send(const FaceData &face) {
    // VRChat face tracking OSC addresses
    // Reference: https://docs.vrchat.com/docs/osc-as-input-controller

    // Eyes
    bool ok = true;

    // Eyes
    ok &= send_param("/avatar/parameters/EyeClosedLeft",    face.eyeClosedLeft);
    ok &= send_param("/avatar/parameters/EyeClosedRight",   face.eyeClosedRight);
    ok &= send_param("/avatar/parameters/EyeSquintLeft",     face.eyeSquintLeft);
    ok &= send_param("/avatar/parameters/EyeSquintRight",    face.eyeSquintRight);
    ok &= send_param("/avatar/parameters/EyeWideLeft",       face.eyeWideLeft);
    ok &= send_param("/avatar/parameters/EyeWideRight",      face.eyeWideRight);

    // Eyebrows
    ok &= send_param("/avatar/parameters/BrowUpLeft",        face.browUpLeft);
    ok &= send_param("/avatar/parameters/BrowUpRight",       face.browUpRight);
    ok &= send_param("/avatar/parameters/BrowDownLeft",      face.browDownLeft);
    ok &= send_param("/avatar/parameters/BrowDownRight",     face.browDownRight);

    // Mouth
    ok &= send_param("/avatar/parameters/MouthOpen",         face.mouthOpen);
    ok &= send_param("/avatar/parameters/MouthSmile",        face.mouthSmile);
    ok &= send_param("/avatar/parameters/MouthFrown",        face.mouthFrown);
    ok &= send_param("/avatar/parameters/MouthPucker",       face.mouthPucker);

    // Jaw
    ok &= send_param("/avatar/parameters/JawOpen",           face.jawOpen);
    ok &= send_param("/avatar/parameters/JawLeft",           face.jawLeft);
    ok &= send_param("/avatar/parameters/JawRight",          face.jawRight);

    // Cheek
    ok &= send_param("/avatar/parameters/CheekPuff",         face.cheekPuff);

    // Tongue
    ok &= send_param("/avatar/parameters/TongueOut",         face.tongueOut);

    if (ok) {
        stats.total_success++;
        stats.interval_success++;
    } else {
        stats.total_failure++;
        stats.interval_failure++;
    }
}

OscStats osc_get_stats() {
    return stats;
}

void osc_reset_interval_stats() {
    stats.interval_success = 0;
    stats.interval_failure = 0;
}
