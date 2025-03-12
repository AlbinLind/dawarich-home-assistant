"""The Dawarich integration."""

import logging
from dataclasses import dataclass

from dawarich_api import DawarichAPI
from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE, DOMAIN
from .coordinator import DawarichCoordinator
from .helpers import get_api

VERSION = "0.3.2"

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

type DawarichConfigEntry = config_entries.ConfigEntry[DawarichConfigEntryData]


@dataclass
class DawarichConfigEntryData:
    """Runtime data definitions."""

    api: DawarichAPI
    coordinator: DawarichCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: DawarichConfigEntry) -> bool:
    """Set up Dawarich from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    host = entry.data[CONF_HOST]
    api_key = entry.data[CONF_API_KEY]
    use_ssl = entry.data[CONF_SSL]
    verify_ssl = entry.data[CONF_VERIFY_SSL]

    api = get_api(host, api_key, use_ssl, verify_ssl)

    coordinator = DawarichCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = DawarichConfigEntryData(api=api, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


# Migration from 1 to 2
async def async_migrate_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    """Migrate an old entry."""
    if entry.version > 1:
        # Downgrade not supported
        return False

    if entry.version == 1:
        data = {}
        data[CONF_HOST] = (
            entry.data["url"]
            .removeprefix("https://")
            .removeprefix("http://")
            .split(":")[0]
        )
        try:
            data[CONF_PORT] = (
                entry.data["url"]
                .removeprefix("https://")
                .removeprefix("http://")
                .split(":")[1]
            )
        except IndexError:
            data[CONF_PORT] = 80 if entry.data["url"].startswith("http") else 443
        data[CONF_SSL] = entry.data["url"].startswith("https")
        data[CONF_API_KEY] = entry.data["api_key"]
        data[CONF_NAME] = entry.data["friendly_name"]
        data[CONF_VERIFY_SSL] = False
        data[CONF_DEVICE] = entry.data.get("mobile_app", None)

        hass.config_entries.async_update_entry(entry, data=data, version=2)

    _LOGGER.info("Migrated %s to config flow version %s", entry.entry_id, entry.version)
    return True
