"""Custom coordinator for Dawarich integration."""

import logging
from typing import Any

from dawarich_api import DawarichAPI
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL, VERSION_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class DawarichStatsCoordinator(DataUpdateCoordinator):
    """Custom coordinator."""

    def __init__(self, hass: HomeAssistant, api: DawarichAPI, entry_id: str):
        """Initialize coordinator."""
        super().__init__(
            hass, _LOGGER, name="Dawarich Sensor", update_interval=UPDATE_INTERVAL
        )
        self.api = api
        self._entry_id = entry_id
        self._api_issue_created = False

    @property
    def _api_issue_id(self) -> str:
        """Return the issue id for the API unavailable repair issue."""
        return f"api_unavailable_{self._entry_id}"

    def _async_create_api_issue(self, status_code: int, error: str | None) -> None:
        """Create a repair issue for API unavailability."""
        if not self._api_issue_created:
            _LOGGER.warning(
                "Dawarich API is unavailable (status %s). Creating repair issue.",
                status_code,
            )
            async_create_issue(
                self.hass,
                DOMAIN,
                self._api_issue_id,
                is_fixable=False,
                severity=IssueSeverity.ERROR,
                translation_key="api_unavailable",
                translation_placeholders={
                    "status_code": str(status_code),
                    "error": str(error) if error else "Unknown error",
                    "url": self.api.url,
                },
            )
            self._api_issue_created = True

    def _async_delete_api_issue(self) -> None:
        """Delete the API unavailable repair issue if it exists."""
        async_delete_issue(self.hass, DOMAIN, self._api_issue_id)
        if self._api_issue_created:
            _LOGGER.info("Dawarich API is available again, clearing repair issue.")
            self._api_issue_created = False

    async def _async_update_data(self) -> dict[str, Any]:
        response = await self.api.get_stats()
        match response.response_code:
            case 200:
                if response.response is None:
                    _LOGGER.error(
                        "Dawarich API returned no data but returned status 200"
                    )
                    raise UpdateFailed("Dawarich API returned no data")
                # API is working, clear any existing issue
                self._async_delete_api_issue()
                return response.response.model_dump()
            case 401:
                _LOGGER.error(
                    "Invalid credentials when trying to fetch stats from Dawarich"
                )
                raise ConfigEntryAuthFailed("Invalid API key")
            case _:
                # Check if error message indicates an authentication issue
                # Some servers return 500 but include 401/Unauthorized in the error
                error_str = str(response.error) if response.error else ""
                if "401" in error_str or "unauthorized" in error_str:
                    _LOGGER.error(
                        "Invalid credentials when trying to fetch stats from Dawarich (status %s)",
                        response.response_code,
                    )
                    raise ConfigEntryAuthFailed("Invalid API key")

                _LOGGER.error(
                    "Error fetching data from Dawarich (status %s) %s",
                    response.response_code,
                    response.error,
                )
                
                # Create repair issue for API unavailability (5xx errors, timeouts, etc.)
                self._async_create_api_issue(response.response_code, response.error)
                
                raise UpdateFailed(
                    f"Error fetching data from Dawarich (status {response.response_code})"
                )


class DawarichVersionCoordinator(DataUpdateCoordinator):
    """Custom coordinator for Dawarich version."""

    def __init__(self, hass: HomeAssistant, api: DawarichAPI, entry_id: str):
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Dawarich Version",
            update_interval=VERSION_UPDATE_INTERVAL,
        )
        self.api = api
        self._entry_id = entry_id

    async def _async_update_data(self) -> dict[str, int]:
        response = await self.api.health()
        if response is None:
            _LOGGER.error("Dawarich API returned no data")
            raise UpdateFailed("Dawarich API returned no data")
        return response.model_dump()
