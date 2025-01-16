"""Dawarich integration."""

from logging import getLogger

from dawarich_api import DawarichAPI
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import Event, EventStateChangedData, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_DEVICE

_LOGGER = getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    if not config_entry.data.get(CONF_DEVICE):
        _LOGGER.warning(
            "No mobile_app entity found, skipping Dawarich mobile tracking setup"
        )
        return
    name = config_entry.data[CONF_NAME]
    api_key = config_entry.data[CONF_API_KEY]
    mobile_app = config_entry.data[CONF_DEVICE]
    api = config_entry.runtime_data.api
    async_add_entities(
        [DawarichDeviceTracker(name, api_key, mobile_app, api, hass=hass)]
    )


class DawarichDeviceTracker(TrackerEntity):
    """Dawarich Sensor Class."""

    def __init__(
        self,
        name: str,
        api_key: str,
        mobile_app: str,
        api: DawarichAPI,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the sensor."""
        self._friendly_name = name
        self._api_key = api_key
        self._mobile_app = mobile_app

        self._latitude = 0.0
        self._longitude = 0.0
        self._location_name = "Home"
        self._location_accuracy = 2

        self._api = api
        self._hass = hass

        self._async_unsubscribe_state_changed = async_track_state_change_event(
            hass=self._hass,
            entity_ids=[self._mobile_app],
            action=self._get_state_change,
        )
        _LOGGER.debug("Dawarich Sensor initialized")

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._friendly_name

    @property
    def latitude(self) -> float:
        """Return latitude value of the device."""
        return self._latitude

    @property
    def longitude(self) -> float:
        """Return longitude value of the device."""
        return self._longitude

    @property
    def location_name(self) -> str:
        """Return a location name for the entity."""
        return self._location_name

    @property
    def location_accuracy(self) -> int:
        """Return the location accuracy of the device."""
        return self._location_accuracy

    async def _get_state_change(
        self, event: Event[EventStateChangedData], *args, **kwargs
    ):
        """Handle the state change."""
        _LOGGER.debug(
            "State change detected for %s, updating Dawarich", self._mobile_app
        )
        if (new_state := event.data.get("new_state")) is None:
            _LOGGER.error("No new state found for %s", self._mobile_app)
            return
        
        new_data = new_state.attributes
        
        # Update internal state with new attributes
        self._location_name = new_data.get("location_name", "Home")
        self._latitude = new_data.get("latitude", 0.0)
        self._longitude = new_data.get("longitude", 0.0)
        self._location_accuracy = new_data.get("gps_accuracy", 2)

        # Send to Dawarich API
        response = await self._api.add_one_point(
            name=self._friendly_name,
            latitude=self._latitude,
            longitude=self._longitude,
            horizontal_accuracy=self._location_accuracy,
            altitude=new_data.get("altitude", 0),
            vertical_accuracy=new_data.get("vertical_accuracy", 0),
            speed= new_data.get("speed", 0)
        )
        if response.success:
            _LOGGER.debug("Location sent to Dawarich API")
        else:
            _LOGGER.error(
                "Error sending location to Dawarich API response code %s and error: %s",
                response.response_code,
                response.error,
            )
