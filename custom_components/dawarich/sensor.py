"""Show statistical data from your Dawarich instance."""

import logging
from datetime import datetime, timedelta

from dawarich_api import DawarichAPI
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_platform
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.location import distance as location_distance

from custom_components.dawarich import DawarichConfigEntry

from .const import (
    CONF_DEVICE,
    CONF_GPS_ACCURACY_THRESHOLD,
    CONF_HEARTBEAT_IDLE_AFTER,
    CONF_HEARTBEAT_IDLE_INTERVAL,
    CONF_HEARTBEAT_INTERVAL,
    CONF_MIN_DISTANCE,
    DAWARICH_TRACK_MERGE_FLOOR_MINUTES,
    DEFAULT_GPS_ACCURACY_THRESHOLD,
    DEFAULT_HEARTBEAT_IDLE_AFTER,
    DEFAULT_HEARTBEAT_IDLE_INTERVAL,
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_MIN_DISTANCE,
    DEFAULT_MOVEMENT_METERS,
    DOMAIN,
    DawarichTrackerStates,
)
from .coordinator import DawarichStatsCoordinator, DawarichVersionCoordinator

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

VERSION_SENSOR_TYPES = SensorEntityDescription(
    key="version",
    name="Dawarich Version",
    translation_key="version",
)

type DawarichSensors = (
    DawarichTrackerSensor | DawarichStatisticsSensor | DawarichVersionSensor
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DawarichConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Dawarich sensor."""
    url = entry.data[CONF_HOST]
    name = entry.data[CONF_NAME]
    coordinator = entry.runtime_data.coordinator
    # Use entry_id for stable identifiers (doesn't change when API key changes)
    entry_id = entry.entry_id

    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name=name,
        manufacturer="Dawarich",
        configuration_url=entry.runtime_data.api.url,
        entry_type=DeviceEntryType.SERVICE,
    )

    # Add statistics sensor
    sensors: list[DawarichSensors] = [
        DawarichStatisticsSensor(url, entry_id, name, desc, coordinator, device_info)
        for desc in SENSOR_TYPES
    ]

    # Add version sensor
    sensors.append(
        DawarichVersionSensor(
            coordinator=entry.runtime_data.version_coordinator,
            description=VERSION_SENSOR_TYPES,
            entry_id=entry_id,
            device_info=device_info,
        )
    )

    # Add (optional) mobile app tracker sensor
    mobile_app = entry.data[CONF_DEVICE]
    if mobile_app is not None:
        _LOGGER.info("Adding tracker sensor for %s", mobile_app)
        api = entry.runtime_data.api
        idle_interval = entry.data.get(
            CONF_HEARTBEAT_IDLE_INTERVAL, DEFAULT_HEARTBEAT_IDLE_INTERVAL
        )
        if 0 < idle_interval <= DAWARICH_TRACK_MERGE_FLOOR_MINUTES:
            _LOGGER.warning(
                (
                    "The idle heartbeat interval (%s minutes) is not above Dawarich's "
                    "%s minute track merge floor, so stationary periods will still be "
                    "merged into the surrounding track. Consider raising it."
                ),
                idle_interval,
                DAWARICH_TRACK_MERGE_FLOOR_MINUTES,
            )

        sensors.append(
            DawarichTrackerSensor(
                entry_id=entry_id,
                device_name=name,
                mobile_app=mobile_app,
                api=api,
                hass=hass,
                device_info=device_info,
                description=TRACKER_SENSOR_TYPES,
                min_distance=entry.data.get(CONF_MIN_DISTANCE, DEFAULT_MIN_DISTANCE),
                heartbeat_interval=entry.data.get(
                    CONF_HEARTBEAT_INTERVAL, DEFAULT_HEARTBEAT_INTERVAL
                ),
                heartbeat_idle_after=entry.data.get(
                    CONF_HEARTBEAT_IDLE_AFTER, DEFAULT_HEARTBEAT_IDLE_AFTER
                ),
                heartbeat_idle_interval=idle_interval,
                gps_accuracy_threshold=entry.data.get(
                    CONF_GPS_ACCURACY_THRESHOLD, DEFAULT_GPS_ACCURACY_THRESHOLD
                ),
            )
        )

        platform = entity_platform.async_get_current_platform()
        platform.async_register_entity_service(
            "push_location", {}, "async_push_location"
        )
    else:
        _LOGGER.info("No mobile device provided, skipping tracker sensor")

    async_add_entities(sensors)


class DawarichTrackerSensor(SensorEntity):
    """Sensor that updates and keep track of the updates to the Dawarich API."""

    def __init__(
        self,
        entry_id: str,
        device_name: str,
        mobile_app: str,
        api: DawarichAPI,
        hass: HomeAssistant,
        device_info: DeviceInfo,
        description: SensorEntityDescription,
        min_distance: int = 0,
        heartbeat_interval: int = 0,
        heartbeat_idle_after: int = 0,
        heartbeat_idle_interval: int = 0,
        gps_accuracy_threshold: int = 0,
    ) -> None:
        """Initialize the sensor."""
        self._device_name = device_name
        self._mobile_app = mobile_app
        self._entry_id = entry_id
        self._hass = hass
        self._api = api
        self._attr_device_info = device_info
        self._attr_device_class = description.device_class
        self.entity_description = description
        self._repair_issue_created = False

        self._min_distance = min_distance
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_idle_after = heartbeat_idle_after
        self._heartbeat_idle_interval = heartbeat_idle_interval
        self._gps_accuracy_threshold = gps_accuracy_threshold

        # Distance that counts as the device having genuinely moved, as opposed
        # to GPS jitter or an attribute-only state change.
        self._movement_distance = min_distance or DEFAULT_MOVEMENT_METERS

        self._last_sent_coordinates: tuple[float, float] | None = None
        self._last_movement: datetime | None = None
        self._is_idle = False

        self._async_unsubscribe_state_changed = async_track_state_change_event(
            hass=self._hass,
            entity_ids=[self._mobile_app],
            action=self._async_update_callback,
        )

        self._async_unsubscribe_heartbeat = None
        if self._heartbeat_interval > 0:
            _LOGGER.info(
                "Enabling heartbeat for %s every %s minute(s)",
                self._mobile_app,
                self._heartbeat_interval,
            )
            self._async_schedule_heartbeat(self._heartbeat_interval)

        self._state: DawarichTrackerStates = DawarichTrackerStates.UNKNOWN
        self._attr_options = [state.value for state in DawarichTrackerStates]

    @callback
    def _async_schedule_heartbeat(self, interval_minutes: int) -> None:
        """(Re)schedule the heartbeat timer at the given interval."""
        if self._async_unsubscribe_heartbeat is not None:
            self._async_unsubscribe_heartbeat()
            self._async_unsubscribe_heartbeat = None

        if interval_minutes <= 0:
            return

        self._async_unsubscribe_heartbeat = async_track_time_interval(
            self._hass,
            self._async_heartbeat_callback,
            timedelta(minutes=interval_minutes),
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        # Check initial state of the tracked entity
        initial_state = self._hass.states.get(self._mobile_app)
        self._async_check_entity_availability(initial_state)

    @property
    def _issue_id(self) -> str:
        """Return the issue id for the repair issue."""
        return f"device_tracker_unavailable_{self._entry_id}"

    @callback
    def _async_check_entity_availability(self, state) -> bool:
        """Check if the tracked entity is available and manage repair issue.

        Returns True if the entity is available, False otherwise.
        """
        if state is None or state.state in ("unavailable", "unknown"):
            if not self._repair_issue_created:
                _LOGGER.warning(
                    "Device tracker %s is not available. Please check the entity.",
                    self._mobile_app,
                )
                async_create_issue(
                    self._hass,
                    DOMAIN,
                    self._issue_id,
                    is_fixable=False,
                    severity=IssueSeverity.WARNING,
                    translation_key="device_tracker_unavailable",
                    translation_placeholders={
                        "device_tracker": self._mobile_app,
                        "device_name": self._device_name,
                    },
                )
                self._repair_issue_created = True
            return False
        if self._repair_issue_created:
            _LOGGER.info(
                "Device tracker %s is available again, clearing repair issue.",
                self._mobile_app,
            )
            async_delete_issue(self._hass, DOMAIN, self._issue_id)
            self._repair_issue_created = False
        return True

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        self._async_unsubscribe_state_changed()
        if self._async_unsubscribe_heartbeat is not None:
            self._async_unsubscribe_heartbeat()
        if self._repair_issue_created:
            async_delete_issue(self._hass, DOMAIN, self._issue_id)

    @property
    def unique_id(self) -> str:  # type: ignore[override]
        """Return a unique id for the sensor."""
        return f"{self._entry_id}/tracker"

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
        if await self._async_check_is_disabled():
            return

        _LOGGER.debug(
            "State change detected for %s, updating Dawarich", self._mobile_app
        )
        new_state = event.data.get("new_state")

        if not self._async_check_entity_availability(new_state):
            return

        if new_state is None:
            _LOGGER.error("No new state found for %s", self._mobile_app)
            return

        new_data = new_state.attributes

        if self._async_is_low_accuracy(new_data):
            return

        coordinates = self._async_get_coordinates(new_data)
        if coordinates is None:
            return

        latitude, longitude = coordinates
        moved_distance = self._distance_from_last_sent(latitude, longitude)
        has_moved = moved_distance is None or moved_distance >= self._movement_distance

        # A state change that didn't move the device far enough is usually an
        # attribute-only update (battery, wifi, GPS jitter). Dropping those keeps
        # redundant points out of Dawarich.
        if self._min_distance > 0 and not has_moved:
            _LOGGER.debug(
                (
                    "State change for %s moved only %.1f m (threshold %s m), "
                    "skipping update"
                ),
                self._mobile_app,
                moved_distance or 0.0,
                self._min_distance,
            )
            return

        if has_moved:
            # Leaving a place the device had settled at: re-send the old position
            # first so the visit is closed at the moment of departure rather than
            # at the last heartbeat, and so the new journey starts from there.
            if self._is_idle:
                await self._async_send_departure_ping(new_data)
            self._async_mark_moved()

        await self._async_send_location(new_state)

    @callback
    def _async_mark_moved(self) -> None:
        """Record genuine movement and restore the active heartbeat cadence."""
        self._last_movement = dt_util.utcnow()
        if self._is_idle:
            _LOGGER.debug(
                "%s is moving again, restoring heartbeat to %s minute(s)",
                self._mobile_app,
                self._heartbeat_interval,
            )
            self._is_idle = False
            self._async_schedule_heartbeat(self._heartbeat_interval)

    async def _async_send_departure_ping(self, new_data: dict) -> None:
        """Re-send the last known stationary position as the device leaves it.

        Without this the visit would end at the last idle heartbeat, which can be
        a whole idle interval earlier than the actual departure.
        """
        if self._last_sent_coordinates is None:
            return

        latitude, longitude = self._last_sent_coordinates
        # Must land strictly before the point we are about to send, otherwise
        # Dawarich sees the two points out of order.
        timestamp = self._next_timestamp(new_data) - timedelta(seconds=1)

        _LOGGER.debug(
            "Sending departure ping for %s at last known position", self._mobile_app
        )
        response = await self._api.add_one_point(
            name=self._device_name,
            latitude=latitude,
            longitude=longitude,
            timestamp=timestamp,
        )
        if not response.success:
            _LOGGER.warning(
                "Departure ping for %s failed (status %s): %s",
                self._mobile_app,
                response.response_code,
                response.error,
            )

    def _next_timestamp(self, new_data: dict) -> datetime:
        """Resolve the timestamp the next point will carry."""
        raw = new_data.get("last_seen") or new_data.get("last_timestamp")
        parsed = None
        if isinstance(raw, datetime):
            parsed = raw
        elif isinstance(raw, str):
            parsed = dt_util.parse_datetime(raw)
        elif isinstance(raw, (int, float)):
            parsed = dt_util.utc_from_timestamp(raw)

        return parsed or dt_util.utcnow()

    @callback
    def _async_is_low_accuracy(self, new_data: dict) -> bool:
        """Whether the GPS fix is too inaccurate to act on."""
        if self._gps_accuracy_threshold <= 0:
            return False
        gps_accuracy = new_data.get("gps_accuracy")
        if gps_accuracy is None:
            return False
        try:
            accuracy = float(gps_accuracy)
        except (TypeError, ValueError):
            return False
        if accuracy > self._gps_accuracy_threshold:
            _LOGGER.debug(
                "GPS accuracy for %s is %.0f m (threshold %s m), skipping",
                self._mobile_app,
                accuracy,
                self._gps_accuracy_threshold,
            )
            return True
        return False

    @callback
    def _async_get_coordinates(self, new_data: dict) -> tuple[float, float] | None:
        """Extract coordinates from state attributes, warning if unusable."""
        _LOGGER.debug("Received data: %s", new_data)

        latitude = new_data.get("latitude")
        longitude = new_data.get("longitude")

        if latitude is None or longitude is None:
            if new_data.get("source") != SourceType.GPS:
                _LOGGER.warning(
                    (
                        "The choosen device tracker (%s) is emitting a '%s' "
                        "source type which typically does not have coordinates. "
                        "Please change the device tracker to one that provides GPS coordinates."
                    ),
                    self._mobile_app,
                    new_data.get("source"),
                )
            _LOGGER.debug("Coordinates are not present, skipping update")
            return None

        return latitude, longitude

    def _distance_from_last_sent(
        self, latitude: float, longitude: float
    ) -> float | None:
        """Distance in meters from the last point sent, or None if unknown."""
        if self._last_sent_coordinates is None:
            return None

        last_latitude, last_longitude = self._last_sent_coordinates
        return location_distance(last_latitude, last_longitude, latitude, longitude)

    async def _async_heartbeat_callback(self, now: datetime) -> None:
        """Re-send the current position on a timer, independent of state changes.

        Keeps a point flowing to Dawarich while the device is stationary so its
        visit detection doesn't read tracker silence as a departure and return.
        """
        if await self._async_check_is_disabled():
            return

        if self._async_should_decay(now):
            _LOGGER.debug(
                "%s has been stationary, dropping heartbeat to %s minute(s)",
                self._mobile_app,
                self._heartbeat_idle_interval,
            )
            self._is_idle = True
            self._async_schedule_heartbeat(self._heartbeat_idle_interval)
            if self._heartbeat_idle_interval <= 0:
                return

        state = self._hass.states.get(self._mobile_app)
        if not self._async_check_entity_availability(state) or state is None:
            return

        if self._async_is_low_accuracy(state.attributes):
            return

        _LOGGER.debug("Heartbeat triggered for %s, updating Dawarich", self._mobile_app)
        await self._async_send_location(state, use_current_time=True)

    @callback
    def _async_should_decay(self, now: datetime) -> bool:
        """Whether the heartbeat should drop to its idle cadence."""
        if self._is_idle or self._heartbeat_idle_after <= 0:
            return False
        if self._last_movement is None:
            return False

        return now - self._last_movement >= timedelta(
            minutes=self._heartbeat_idle_after
        )

    async def async_push_location(self) -> None:
        """Push the tracker's current location to Dawarich on demand.

        Entry point for the `dawarich.push_location` service, so users can drive
        it from their own automations.
        """
        if await self._async_check_is_disabled():
            return

        state = self._hass.states.get(self._mobile_app)
        if not self._async_check_entity_availability(state) or state is None:
            return

        await self._async_send_location(state, use_current_time=True)

    async def _async_send_location(
        self, state: State, *, use_current_time: bool = False
    ) -> None:
        """Send the given state's coordinates to the Dawarich API."""
        new_data = state.attributes
        coordinates = self._async_get_coordinates(new_data)
        if coordinates is None:
            return

        latitude, longitude = coordinates
        optional_params = await self._async_add_optional_params(
            new_data, use_current_time=use_current_time
        )

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
            self._last_sent_coordinates = (latitude, longitude)
            if self._last_movement is None:
                self._last_movement = dt_util.utcnow()
        else:
            self._state = DawarichTrackerStates.ERROR
            _LOGGER.error(
                "Error sending location to Dawarich API response code %s and error: %s",
                response.response_code,
                response.error,
            )

    async def _async_add_optional_params(
        self, new_data: dict, *, use_current_time: bool = False
    ) -> dict:
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
        elif (velocity := new_data.get("velocity")) is not None:
            optional_params["speed"] = velocity

        if (battery := new_data.get("battery")) is not None:
            optional_params["battery"] = battery

        # Heartbeat and service pushes deliberately skip the entity's own
        # last_seen/last_timestamp: it reflects the last state change, not "now",
        # so reusing it would send a run of points all sharing one stale
        # timestamp instead of spreading them over time. Omitting it lets the API
        # default to the current time.
        if not use_current_time and (
            (raw_timestamp := new_data.get("last_seen")) is not None
            or (raw_timestamp := new_data.get("last_timestamp")) is not None
        ):
            optional_params["timestamp"] = raw_timestamp

        return optional_params

    async def _async_check_is_disabled(self) -> bool:
        """Check if the Dawarich tracker sensor is disabled."""
        device_registry = dr.async_get(self._hass)
        entity_registry = er.async_get(self._hass)

        # Look up device
        if self.device_entry is None:
            _LOGGER.debug("No device entry found, instead looking based on identifiers")
            device = device_registry.async_get_device(
                identifiers={(DOMAIN, self._entry_id)}
            )
        else:
            _LOGGER.debug(
                "Device entry found (%s), looking up device based on device entry",
                self.device_entry.id,
            )
            # While the device entry could be the same we are re-querying
            # it to ensure that we do not get a stale version.
            device = device_registry.async_get(self.device_entry.id)
        if device is None:
            _LOGGER.warning(
                "Device not found in device registry. This should not typically "
                "happen. Try restarting Home Assistant.",
            )
            return False

        # Look up entity
        if self.registry_entry is None:
            _LOGGER.debug("No registry entry found, looking up based on unique id")
            entity_entry = entity_registry.async_get(self.unique_id)
        else:
            _LOGGER.debug(
                "Registry entry found (%s), looking up entity based on registry entry",
                self.registry_entry.entity_id,
            )
            # While the registry entry could be the same we are re-querying
            # it to ensure that we do not get a stale version.
            entity_entry = entity_registry.async_get(self.registry_entry.entity_id)
        if entity_entry is None:
            _LOGGER.warning(
                "Entity not found in entity registry. This should not typically "
                "happen. Try restarting Home Assistant.",
            )
            return False

        if device.disabled:
            _LOGGER.debug(
                "State change detected for %s, however, Dawarich device is disabled, not updating.",
                self._mobile_app,
            )
            return True
        if entity_entry.disabled:
            _LOGGER.debug(
                "State change detected for %s, however, Dawarich tracker sensor is disabled, not updating.",
                self._mobile_app,
            )
            return True
        return False

    @property
    def name(self) -> str:  # type: ignore[override]
        """Return the name of the sensor."""
        return self._device_name + " Tracker"


class DawarichStatisticsSensor(CoordinatorEntity, SensorEntity):  # type: ignore[incompatible-subclass]
    """Representation of a Dawarich sensor."""

    def __init__(
        self,
        url: str,
        entry_id: str,
        device_name: str,
        description: SensorEntityDescription,
        coordinator: DawarichStatsCoordinator,
        device_info: DeviceInfo,
    ):
        """Initialize Dawarich sensor."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._url = url
        self._device_name = device_name
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}/{description.key}"
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


class DawarichVersionSensor(
    CoordinatorEntity[DawarichVersionCoordinator], SensorEntity
):  # type: ignore[incompatible-subclass]
    """Representation of a Dawarich version sensor."""

    def __init__(
        self,
        coordinator: DawarichVersionCoordinator,
        description: SensorEntityDescription,
        entry_id: str,
        device_info: DeviceInfo,
    ):
        """Initialize Dawarich version sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}/{description.key}"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> StateType:  # type: ignore[override]
        """Return the state of the device."""
        if self.coordinator.data is None:
            return None
        # Combine the version parts
        major = self.coordinator.data["major"]
        minor = self.coordinator.data["minor"]
        patch = self.coordinator.data["patch"]
        return f"{major}.{minor}.{patch}"

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return "mdi:information-outline"
