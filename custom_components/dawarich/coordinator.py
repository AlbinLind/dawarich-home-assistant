"""Custom coordinator for Dawarich integration."""

import logging
from typing import Any

from dawarich_api import DawarichAPI
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import UPDATE_INTERVAL, VERSION_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class DawarichStatsCoordinator(DataUpdateCoordinator):
    """Custom coordinator."""

    def __init__(self, hass: HomeAssistant, api: DawarichAPI):
        """Initialize coordinator."""
        super().__init__(
            hass, _LOGGER, name="Dawarich Sensor", update_interval=UPDATE_INTERVAL
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        response = await self.api.get_stats()
        match response.response_code:
            case 200:
                if response.response is None:
                    _LOGGER.error(
                        "Dawarich API returned no data but returned status 200"
                    )
                    raise UpdateFailed("Dawarich API returned no data")
                return response.response.model_dump()
            case 401:
                _LOGGER.error(
                    "Invalid credentials when trying to fetch stats from Dawarich"
                )
                raise ConfigEntryAuthFailed("Invalid API key")
            case _:
                _LOGGER.error(
                    "Error fetching data from Dawarich (status %s) %s",
                    response.response_code,
                    response.error,
                )
                raise UpdateFailed from Warning(
                    f"Error fetching data from Dawarich (status {response.response_code})"
                )


class DawarichVersionCoordinator(DataUpdateCoordinator):
    """Custom coordinator for Dawarich version."""

    def __init__(self, hass: HomeAssistant, api: DawarichAPI):
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Dawarich Version",
            update_interval=VERSION_UPDATE_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, int]:
        response = await self.api.health()
        if response is None:
            _LOGGER.error("Dawarich API returned no data")
            raise UpdateFailed("Dawarich API returned no data")
        return response.model_dump()
