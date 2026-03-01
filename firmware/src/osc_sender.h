/**
 * VRC Facial Tracker - OSC Sender Module Header
 */

#pragma once

#include "tracker.h"

/**
 * Initialize the OSC UDP sender.
 */
void osc_init();

/**
 * Send face tracking data as OSC messages to VRChat.
 * @param face Face tracking data to send.
 */
void osc_send(const FaceData &face);
