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


class DawarichTrackerStates(Enum):
    """States of the Dawarich tracker sensor."""

    UNKNOWN = "unknown"
    SUCCESS = "success"
    ERROR = "error"
