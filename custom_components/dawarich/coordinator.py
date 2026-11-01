"""Custom coordinator for Dawarich integration."""

import asyncio
import logging
from typing import Any

import aiohttp
from dawarich_api import DawarichAPI
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, GITHUB_RELEASE_URL, UPDATE_INTERVAL, VERSION_UPDATE_INTERVAL

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


class DawarichVersionCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Custom coordinator for Dawarich version and updates."""

    def __init__(self, hass: HomeAssistant, api: DawarichAPI, entry_id: str) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Dawarich Version",
            update_interval=VERSION_UPDATE_INTERVAL,
        )
        self.api = api
        self._entry_id = entry_id
        self._github_etag: str | None = None
        self._latest_release_data: dict[str, Any] | None = None

    async def _async_get_latest_release(self) -> dict[str, Any] | None:
        """Fetch the latest release information from GitHub."""
        session = async_get_clientsession(self.hass)
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "HomeAssistant-Dawarich-Integration",
        }
        if self._github_etag:
            headers["If-None-Match"] = self._github_etag

        try:
            async with asyncio.timeout(10):
                async with session.get(GITHUB_RELEASE_URL, headers=headers) as response:
                    if response.status == 304:
                        _LOGGER.debug("GitHub release data not modified (304)")
                        return self._latest_release_data
                    if response.status == 200:
                        self._github_etag = response.headers.get("ETag")
                        release_data = await response.json()
                        tag_name = str(release_data.get("tag_name", ""))
                        latest_version = tag_name.removeprefix("v").strip()
                        self._latest_release_data = {
                            "latest_version": latest_version,
                            "release_url": release_data.get("html_url"),
                            "release_notes": release_data.get("body"),
                        }
                        return self._latest_release_data
                    _LOGGER.debug(
                        "Unexpected status code from GitHub releases (%s): %s",
                        GITHUB_RELEASE_URL,
                        response.status,
                    )
        except (TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.debug(
                "Failed to fetch latest Dawarich release from GitHub: %s", err
            )
        except Exception:
            _LOGGER.debug("Error checking Dawarich release from GitHub", exc_info=True)

        return self._latest_release_data

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch version and health data from Dawarich API and GitHub."""
        response = await self.api.health()
        if response is None:
            _LOGGER.error("Dawarich API returned no data")
            raise UpdateFailed("Dawarich API returned no data")

        health_data = response.model_dump()

        installed_version: str | None = None
        if isinstance(health_data.get("version"), str):
            installed_version = health_data["version"].removeprefix("v").strip()
        elif (
            health_data.get("major") is not None
            and health_data.get("minor") is not None
            and health_data.get("patch") is not None
        ):
            installed_version = (
                f"{health_data['major']}.{health_data['minor']}.{health_data['patch']}"
            )

        latest_release_data = await self._async_get_latest_release()
        latest_version = None
        release_url = None
        release_notes = None
        if latest_release_data:
            latest_version = latest_release_data.get("latest_version")
            release_url = latest_release_data.get("release_url")
            release_notes = latest_release_data.get("release_notes")

        return {
            **health_data,
            "installed_version": installed_version,
            "latest_version": latest_version,
            "release_url": release_url,
            "release_notes": release_notes,
        }
