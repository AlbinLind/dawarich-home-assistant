"""Constants for the Dawarich integration."""

from datetime import timedelta
from enum import Enum

DOMAIN = "dawarich"


DEFAULT_PORT = 80
DEFAULT_NAME = "Dawarich"
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True
CONF_DEVICE = "mobile_app"
UPDATE_INTERVAL = timedelta(seconds=60)
VERSION_UPDATE_INTERVAL = timedelta(hours=1)

CONF_MIN_DISTANCE = "min_distance"
DEFAULT_MIN_DISTANCE = 0
CONF_HEARTBEAT_INTERVAL = "heartbeat_interval"
DEFAULT_HEARTBEAT_INTERVAL = 0
CONF_HEARTBEAT_IDLE_AFTER = "heartbeat_idle_after"
# Kept short on purpose: active-cadence heartbeats fired while the device is
# already parked fall inside the merge floor, so they extend the journey's track
# by however long this is. Just long enough to establish the visit.
DEFAULT_HEARTBEAT_IDLE_AFTER = 30
CONF_HEARTBEAT_IDLE_INTERVAL = "heartbeat_idle_interval"
DEFAULT_HEARTBEAT_IDLE_INTERVAL = 45

# Distance used to decide "the device actually moved" when no explicit
# minimum distance is configured. Keeps GPS jitter from resetting the
# heartbeat back to its active cadence.
DEFAULT_MOVEMENT_METERS = 50

# Dawarich merges two tracks whose gap is within
# `max(minutes_between_routes, 30.minutes)` (Tracks::BoundaryDetector), so an
# idle cadence at or below 30 minutes can never produce separate tracks.
DAWARICH_TRACK_MERGE_FLOOR_MINUTES = 30


class DawarichTrackerStates(Enum):
    """States of the Dawarich tracker sensor."""

    UNKNOWN = "unknown"
    SUCCESS = "success"
    ERROR = "error"
