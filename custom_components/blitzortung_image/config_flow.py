"""Config flow for Blitzortung Image integration."""

from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol
from aiohttp.client_exceptions import (
    ClientConnectorDNSError,
    ConnectionTimeoutError,
)

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError

from .api import BlitzortungApi, BlitzortungAuthenticationError
from .const import DOMAIN, NAME, CONF_USERNAME, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Blitzortung Image."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] | None = {}
        data_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        if user_input is not None:
            try:
                api = BlitzortungApi(
                    self.hass, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
                await api.test_connection()
            except BlitzortungAuthenticationError:
                errors["base"] = "invalid_auth"
            except ClientConnectorDNSError:
                errors["base"] = "cannot_connect"
            except ConnectionTimeoutError:
                errors["base"] = "timeout"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=NAME, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
