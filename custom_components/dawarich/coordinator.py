"""Custom coordinator for Dawarich integration."""
import logging
from typing import Any

from dawarich_api import DawarichAPI
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class DawarichCoordinator(DataUpdateCoordinator):
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
                return response.response.dict()  # type: ignore[unknown-attr]
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