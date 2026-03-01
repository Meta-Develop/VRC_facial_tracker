/**
 * VRC Facial Tracker - OSC Sender Module
 */

#include "osc_sender.h"
#include "config.h"
#include <WiFiUdp.h>
#include <OSCMessage.h>

static WiFiUDP udp;

void osc_init() {
    udp.begin(OSC_LOCAL_PORT);
    Serial.printf("OSC: Sending to %s:%d\n", OSC_TARGET_IP, OSC_TARGET_PORT);
}

/**
 * Send a single float OSC parameter.
 */
static void send_param(const char *address, float value) {
    OSCMessage msg(address);
    msg.add(value);
    udp.beginPacket(OSC_TARGET_IP, OSC_TARGET_PORT);
    msg.send(udp);
    udp.endPacket();
    msg.empty();
}

void osc_send(const FaceData &face) {
    // VRChat face tracking OSC addresses
    // Reference: https://docs.vrchat.com/docs/osc-as-input-controller

    // Eyes
    send_param("/avatar/parameters/EyeClosedLeft",    face.eyeClosedLeft);
    send_param("/avatar/parameters/EyeClosedRight",   face.eyeClosedRight);
    send_param("/avatar/parameters/EyeSquintLeft",     face.eyeSquintLeft);
    send_param("/avatar/parameters/EyeSquintRight",    face.eyeSquintRight);
    send_param("/avatar/parameters/EyeWideLeft",       face.eyeWideLeft);
    send_param("/avatar/parameters/EyeWideRight",      face.eyeWideRight);

    // Eyebrows
    send_param("/avatar/parameters/BrowUpLeft",        face.browUpLeft);
    send_param("/avatar/parameters/BrowUpRight",       face.browUpRight);
    send_param("/avatar/parameters/BrowDownLeft",      face.browDownLeft);
    send_param("/avatar/parameters/BrowDownRight",     face.browDownRight);

    // Mouth
    send_param("/avatar/parameters/MouthOpen",         face.mouthOpen);
    send_param("/avatar/parameters/MouthSmile",        face.mouthSmile);
    send_param("/avatar/parameters/MouthFrown",        face.mouthFrown);
    send_param("/avatar/parameters/MouthPucker",       face.mouthPucker);

    // Jaw
    send_param("/avatar/parameters/JawOpen",           face.jawOpen);
    send_param("/avatar/parameters/JawLeft",           face.jawLeft);
    send_param("/avatar/parameters/JawRight",          face.jawRight);

    // Cheek
    send_param("/avatar/parameters/CheekPuff",         face.cheekPuff);

    // Tongue
    send_param("/avatar/parameters/TongueOut",         face.tongueOut);
}
