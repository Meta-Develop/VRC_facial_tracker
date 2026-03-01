/**
 * VRC Facial Tracker - OSC Sender Module Header
 */

#pragma once

#include <stdint.h>
#include "tracker.h"

struct OscStats {
    uint32_t total_success;
    uint32_t total_failure;
    uint32_t interval_success;
    uint32_t interval_failure;
};

/**
 * Initialize the OSC UDP sender.
 */
void osc_init();

/**
 * Send face tracking data as OSC messages to VRChat.
 * @param face Face tracking data to send.
 */
void osc_send(const FaceData &face);

/**
 * Get OSC transmission statistics.
 * @return OscStats snapshot.
 */
OscStats osc_get_stats();

/**
 * Reset interval counters used for periodic reporting.
 */
void osc_reset_interval_stats();
