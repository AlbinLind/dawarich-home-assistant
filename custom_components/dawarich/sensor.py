"""Show statistical data from your Dawarich instance."""

import logging
from typing import TYPE_CHECKING

from dawarich_api import DawarichAPI
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_NAME,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .const import CONF_DEVICE, DOMAIN, DawarichTrackerStates
from .coordinator import DawarichStatsCoordinator

if TYPE_CHECKING:
    from .config_flow import DawarichConfigFlow

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = (
    SensorEntityDescription(
        key="total_distance_km",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        name="Total Distance",
        icon="mdi:map-marker-distance",
        device_class=SensorDeviceClass.DISTANCE,
        translation_key="total_distance",
    ),
    SensorEntityDescription(
        key="total_points_tracked",
        name="Total Points Tracked",
        icon="mdi:map-marker-multiple",
        translation_key="total_points_tracked",
    ),
    SensorEntityDescription(
        key="total_reverse_geocoded_points",
        name="Total Reverse Geocoded Points",
        icon="mdi:map-marker-question",
        translation_key="total_reverse_geocoded_points",
    ),
    SensorEntityDescription(
        key="total_countries_visited",
        name="Total Countries Visited",
        icon="mdi:earth",
        translation_key="total_countries_visited",
    ),
    SensorEntityDescription(
        key="total_cities_visited",
        name="Total Cities Visited",
        icon="mdi:city",
        translation_key="total_cities_visited",
    ),
)

TRACKER_SENSOR_TYPES = SensorEntityDescription(
    key="last_update",
    name="Last Update",
    device_class=SensorDeviceClass.ENUM,
    translation_key="last_update",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: "DawarichConfigFlow",
    async_add_entities: AddEntitiesCallback,
):
    """Set up Dawarich sensor."""
    url = entry.data[CONF_HOST]
    api_key = entry.data[CONF_API_KEY]
    name = entry.data[CONF_NAME]
    coordinator = entry.runtime_data.coordinator

    device_info = DeviceInfo(
        identifiers={(DOMAIN, api_key)},
        name=name,
        manufacturer="Dawarich",
        configuration_url=entry.runtime_data.api.url,
    )

    sensors: list[DawarichTrackerSensor | DawarichStatisticsSensor] = [
        DawarichStatisticsSensor(url, api_key, name, desc, coordinator, device_info)
        for desc in SENSOR_TYPES
    ]

    mobile_app = entry.data[CONF_DEVICE]
    if mobile_app is not None:
        _LOGGER.info("Adding tracker sensor for %s", mobile_app)
        api = entry.runtime_data.api
        sensors.append(
            DawarichTrackerSensor(
                api_key=api_key,
                device_name=name,
                mobile_app=mobile_app,
                api=api,
                hass=hass,
                device_info=device_info,
                description=TRACKER_SENSOR_TYPES,
            )
        )
    else:
        _LOGGER.info("No mobile device provided, skipping tracker sensor")

    async_add_entities(sensors)


class DawarichTrackerSensor(SensorEntity):
    """Sensor that updates and keep track of the updates to the Dawarich API."""

    def __init__(
        self,
        api_key: str,
        device_name: str,
        mobile_app,
        api: DawarichAPI,
        hass: HomeAssistant,
        device_info: DeviceInfo,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self._device_name = device_name
        self._mobile_app = mobile_app
        self._api_key = api_key
        self._hass = hass
        self._api = api
        self._attr_device_info = device_info
        self._attr_device_class = description.device_class
        self.entity_description = description

        self._async_unsubscribe_state_changed = async_track_state_change_event(
            hass=self._hass,
            entity_ids=[self._mobile_app],
            action=self._async_update_callback,
        )
        self._state: DawarichTrackerStates = DawarichTrackerStates.UNKNOWN
        self._attr_options = [state.value for state in DawarichTrackerStates]

    @property
    def unique_id(self) -> str:  # type: ignore[override]
        """Return a unique id for the sensor."""
        return f"{self._api_key}/tracker"

    @property
    def state(self) -> StateType:
        """Return the state of the sensor."""
        return self._state.value

    @property
    def icon(self) -> str:  # type: ignore[override]
        """Return the icon to use in the frontend."""
        return "mdi:map-marker-circle"

    async def _async_update_callback(self, event):
        """Update the Dawarich API with the new location."""
        _LOGGER.debug(
            "State change detected for %s, updating Dawarich", self._mobile_app
        )
        if (new_state := event.data.get("new_state")) is None:
            _LOGGER.error("No new state found for %s", self._mobile_app)
            return

        # Log received data
        new_data = new_state.attributes
        _LOGGER.debug("Received data: %s", new_data)

        # Get coordinates from new_data
        latitude = new_data.get("latitude")
        longitude = new_data.get("longitude")

        # Check if the coordinates are present
        if latitude is None or longitude is None:
            _LOGGER.debug("Coordinates are not present, skipping update")
            return

        # Only include optional parameters if they have valid values
        optional_params = {}

        if (gps_accuracy := new_data.get("gps_accuracy")) is not None:
            optional_params["horizontal_accuracy"] = gps_accuracy

        if (altitude := new_data.get("altitude")) is not None:
            optional_params["altitude"] = altitude

        if (vertical_accuracy := new_data.get("vertical_accuracy")) is not None:
            optional_params["vertical_accuracy"] = vertical_accuracy

        if (speed := new_data.get("speed")) is not None:
            optional_params["speed"] = speed

        if (battery := new_data.get("battery")) is not None:
            optional_params["battery"] = battery

        # Send to Dawarich API
        response = await self._api.add_one_point(
            name=self._device_name,
            latitude=latitude,
            longitude=longitude,
            **optional_params,
        )
        if response.success:
            _LOGGER.debug("Location sent to Dawarich API")
            self._state = DawarichTrackerStates.SUCCESS
        else:
            self._state = DawarichTrackerStates.ERROR
            _LOGGER.error(
                "Error sending location to Dawarich API response code %s and error: %s",
                response.response_code,
                response.error,
            )

    @property
    def name(self) -> str:  # type: ignore[override]
        """Return the name of the sensor."""
        return self._device_name + " Tracker"


class DawarichStatisticsSensor(CoordinatorEntity, SensorEntity):  # type: ignore[incompatible-subclass]
    """Representation fo a Dawarich sensor."""

    def __init__(
        self,
        url: str,
        api_key: str,
        device_name: str,
        description: SensorEntityDescription,
        coordinator: DawarichStatsCoordinator,
        device_info: DeviceInfo,
    ):
        """Initialize Dawarich sensor."""
        super().__init__(coordinator)
        self._api_key = api_key
        self._url = url
        self._device_name = device_name
        self.entity_description = description
        self._attr_unique_id = api_key + "/" + description.key
        self._attr_device_info = device_info
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self) -> StateType:  # type: ignore[override]
        """Return the state of the device."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data[self.entity_description.key]

    @property
    def icon(self) -> str:  # type: ignore[override]
        """Return the icon to use in the frontend."""
        if self.entity_description.icon is not None:
            return self.entity_description.icon
        return "mdi:eye"

    @property
    def name(self) -> str:  # type: ignore[override]
        """Return the name of the sensor."""
        if isinstance(self.entity_description.name, str):
            return f"{self._device_name} {self.entity_description.name.title()}"
        _LOGGER.error("Name is not a string for %s", self.entity_description.key)
        return f"{self._device_name}"
