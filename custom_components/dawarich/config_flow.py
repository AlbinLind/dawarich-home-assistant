"""Config flow for Dawarich integration."""

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers import selector

from .const import (
    CONF_DEVICE,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)
from .helpers import get_api

_LOGGER = logging.getLogger(__name__)


class DawarichConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dawarich."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize Dawarich config flow."""
        self._config: dict[str, Any] = {}
        self._reconfigure_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            self._config = {
                CONF_HOST: f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
                CONF_NAME: user_input[CONF_NAME],
                CONF_SSL: user_input[CONF_SSL],
                CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                CONF_DEVICE: user_input.get(CONF_DEVICE),
            }

            self._async_abort_entries_match(
                {
                    CONF_HOST: self._config[CONF_HOST],
                    CONF_API_KEY: self._config.get(CONF_API_KEY),
                }
            )

            if not (errors := await self._async_test_connect()):
                return self.async_create_entry(
                    title=self._config[CONF_NAME], data=self._config
                )

            if CONF_API_KEY in errors:
                return await self.async_step_api_key()

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                    vol.Required(
                        CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)
                    ): vol.Coerce(int),
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                    ): str,
                    vol.Optional(
                        CONF_DEVICE, msg="If you want to track your device"
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["device_tracker", "person"]
                        )
                    ),
                    vol.Required(
                        CONF_SSL, default=user_input.get(CONF_SSL, DEFAULT_SSL)
                    ): bool,
                    vol.Required(
                        CONF_VERIFY_SSL,
                        default=user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_api_key(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle API key step."""
        errors = {}
        if user_input is not None:
            self._config[CONF_API_KEY] = user_input[CONF_API_KEY]

            self._async_abort_entries_match(
                {
                    CONF_HOST: self._config[CONF_HOST],
                    CONF_API_KEY: self._config[CONF_API_KEY],
                }
            )
            if not (errors := await self._async_test_connect()):
                return self.async_create_entry(
                    title=self._config[CONF_NAME], data=self._config
                )

        return self.async_show_form(
            step_id="api_key",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle re-auth flow."""
        self._config = dict(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle re-auth confirmation."""
        errors = {}
        if user_input is not None:
            self._config = {**self._config, CONF_API_KEY: user_input[CONF_API_KEY]}

            if not (errors := await self._async_test_connect()):
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),  # type: ignore[unkown]
                    data=self._config,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={
                CONF_HOST: self._config[CONF_HOST],
            },
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration flow."""
        self._reconfigure_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if self._reconfigure_entry is None:
            return self.async_abort(reason="reconfigure_failed")

        return await self.async_step_reconfigure_confirm()

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration confirmation."""
        errors: dict[str, str] = {}
        assert self._reconfigure_entry is not None

        # Get current values from the entry
        current_data = self._reconfigure_entry.data
        # Parse host and port from the stored host:port format
        host_and_port_string = current_data.get(CONF_HOST, "")
        if ":" in host_and_port_string:
            current_host, port_str = host_and_port_string.rsplit(":", 1)
            try:
                current_port = int(port_str)
            except ValueError:
                _LOGGER.warning(
                    "Failed to parse port from stored host value '%s', using default port %s",
                    host_and_port_string,
                    DEFAULT_PORT,
                )
                current_host = host_and_port_string
                current_port = DEFAULT_PORT
        else:
            current_host = host_and_port_string
            current_port = DEFAULT_PORT

        if user_input is not None:
            # Use new API key if provided, otherwise keep existing one
            new_api_key = user_input.get(CONF_API_KEY)
            if not new_api_key:
                new_api_key = current_data.get(CONF_API_KEY)

            # Build new config from user input
            self._config = {
                CONF_HOST: f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
                CONF_NAME: user_input[CONF_NAME],
                CONF_SSL: user_input[CONF_SSL],
                CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                CONF_DEVICE: user_input.get(CONF_DEVICE),
                CONF_API_KEY: new_api_key,
            }

            # Test the connection with new settings
            if not (errors := await self._async_test_connect()):
                return self.async_update_reload_and_abort(
                    self._reconfigure_entry,
                    data=self._config,
                    title=self._config[CONF_NAME],
                )
        else:
            # Set default values for the form
            user_input = {
                CONF_HOST: current_host,
                CONF_PORT: current_port,
                CONF_NAME: current_data.get(CONF_NAME, DEFAULT_NAME),
                CONF_SSL: current_data.get(CONF_SSL, DEFAULT_SSL),
                CONF_VERIFY_SSL: current_data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            }

        return self.async_show_form(
            step_id="reconfigure_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=user_input.get(CONF_HOST),
                    ): str,
                    vol.Required(
                        CONF_PORT,
                        default=user_input.get(CONF_PORT),
                    ): vol.Coerce(int),
                    vol.Required(
                        CONF_NAME,
                        default=user_input.get(CONF_NAME),
                    ): str,
                    vol.Optional(
                        CONF_DEVICE,
                        description={"suggested_value": current_data.get(CONF_DEVICE)},
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="device_tracker")
                    ),
                    vol.Required(
                        CONF_SSL,
                        default=user_input.get(CONF_SSL),
                    ): bool,
                    vol.Required(
                        CONF_VERIFY_SSL,
                        default=user_input.get(CONF_VERIFY_SSL),
                    ): bool,
                    vol.Optional(
                        CONF_API_KEY,
                        description={"suggested_value": ""},
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders={
                CONF_HOST: current_data.get(CONF_HOST, ""),
            },
        )

    async def _async_test_connect(self) -> dict[str, str]:
        # Test and make sure the API key is valid
        if CONF_API_KEY not in self._config:
            return {CONF_API_KEY: "no api key"}

        host = self._config[CONF_HOST]
        use_ssl = self._config[CONF_SSL]
        api_key = self._config[CONF_API_KEY]
        verify_ssl = self._config[CONF_VERIFY_SSL]

        api = get_api(host, api_key, use_ssl, verify_ssl)

        # TODO: We should do a health check to see if the API is reachable
        # that way we can display if it is a connection issue or an invalid API key
        api_stats = await api.get_stats()

        match api_stats.response_code:
            case 200:
                return {}
            case 401:
                return {CONF_API_KEY: "invalid api key"}
            case _:
                return {"base": "connection_error"}
