"""Update entities for Dawarich integration."""

import logging
from typing import Any

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.dawarich import DawarichConfigEntry

from .const import DOMAIN
from .coordinator import DawarichVersionCoordinator
from .helpers import get_addon_by_host

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DawarichConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dawarich update entity."""
    name = entry.data[CONF_NAME]
    entry_id = entry.entry_id
    version_coordinator = entry.runtime_data.version_coordinator

    installed_version = (
        version_coordinator.data.get("installed_version")
        if version_coordinator.data
        else None
    )

    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name=name,
        manufacturer="Dawarich",
        configuration_url=entry.runtime_data.api.url,
        entry_type=DeviceEntryType.SERVICE,
        sw_version=installed_version,
    )

    async_add_entities(
        [
            DawarichUpdateEntity(
                coordinator=version_coordinator,
                entry=entry,
                device_info=device_info,
            )
        ]
    )


class DawarichUpdateEntity(CoordinatorEntity[DawarichVersionCoordinator], UpdateEntity):
    """Representation of a Dawarich update entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_title = "Dawarich"

    def __init__(
        self,
        coordinator: DawarichVersionCoordinator,
        entry: DawarichConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the Dawarich update entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}/update"
        self._attr_device_info = device_info
        self._attr_in_progress = False

    @property
    def _addon_update_entity_id(self) -> str | None:
        """Get the Dawarich add-on update entity ID if configured URL points to an add-on."""
        host = self._entry.data.get(CONF_HOST, "")
        return get_addon_by_host(self.hass, host)

    @property
    def _is_managed_by_addon(self) -> bool:
        """Return whether Dawarich is managed as a Home Assistant add-on."""
        return self._addon_update_entity_id is not None

    @property
    def supported_features(self) -> UpdateEntityFeature:
        """Flag supported features based on whether Dawarich is managed as an add-on."""
        features = UpdateEntityFeature(0)
        if self._is_managed_by_addon:
            features |= UpdateEntityFeature.INSTALL | UpdateEntityFeature.BACKUP
        if self.coordinator.data and self.coordinator.data.get("release_notes"):
            features |= UpdateEntityFeature.RELEASE_NOTES
        return features

    @property
    def in_progress(self) -> bool:
        """Return True if an update is in progress."""
        if self._attr_in_progress:
            return True
        addon_entity_id = self._addon_update_entity_id
        if addon_entity_id:
            state = self.hass.states.get(addon_entity_id)
            if state and state.attributes.get("in_progress"):
                return True
        return False

    @property
    def update_percentage(self) -> int | None:
        """Return the update percentage if in progress."""
        addon_entity_id = self._addon_update_entity_id
        if addon_entity_id:
            state = self.hass.states.get(addon_entity_id)
            if state and "update_percentage" in state.attributes:
                val = state.attributes.get("update_percentage")
                if isinstance(val, int):
                    return val
        return None

    @property
    def installed_version(self) -> str | None:
        """Return the currently installed version of Dawarich."""
        addon_entity_id = self._addon_update_entity_id
        if addon_entity_id:
            state = self.hass.states.get(addon_entity_id)
            if state and state.attributes.get("installed_version"):
                return (
                    str(state.attributes["installed_version"]).removeprefix("v").strip()
                )

        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("installed_version")

    @property
    def latest_version(self) -> str | None:
        """Return the latest available version of Dawarich."""
        addon_entity_id = self._addon_update_entity_id
        if addon_entity_id:
            state = self.hass.states.get(addon_entity_id)
            if state and state.attributes.get("latest_version"):
                return str(state.attributes["latest_version"]).removeprefix("v").strip()

        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("latest_version")

    @property
    def release_url(self) -> str | None:
        """Return the URL to the release notes."""
        addon_entity_id = self._addon_update_entity_id
        if addon_entity_id:
            state = self.hass.states.get(addon_entity_id)
            if state and state.attributes.get("release_url"):
                return str(state.attributes["release_url"])

        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("release_url")

    async def async_release_notes(self) -> str | None:
        """Return the release notes for the latest version."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("release_notes")

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update via Home Assistant add-on manager."""
        addon_entity_id = self._addon_update_entity_id
        if not addon_entity_id:
            raise HomeAssistantError(
                "Cannot trigger update: Dawarich is self-hosted outside of Home Assistant management or the add-on update entity was not found."
            )

        self._attr_in_progress = True
        self.async_write_ha_state()

        try:
            await self.hass.services.async_call(
                "update",
                "install",
                {
                    "entity_id": addon_entity_id,
                    "backup": backup,
                },
                blocking=True,
            )
        finally:
            self._attr_in_progress = False
            await self.coordinator.async_request_refresh()
            self.async_write_ha_state()
