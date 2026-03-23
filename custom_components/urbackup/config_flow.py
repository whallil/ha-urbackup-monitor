"""Config flow for UrBackup integration."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import UrBackupApiClient, UrBackupApiError, UrBackupAuthenticationError
from .const import DEFAULT_PORT, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Optional(CONF_USERNAME, default=""): str,
        vol.Optional(CONF_PASSWORD, default=""): str,
    }
)


class UrBackupConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for UrBackup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")

            if not url.startswith(("http://", "https://")):
                url = f"http://{url}"

            parsed = urlparse(url)
            if not parsed.port:
                url = f"{parsed.scheme}://{parsed.hostname}:{DEFAULT_PORT}"

            self._async_abort_entries_match({CONF_URL: url})

            session = async_get_clientsession(self.hass)
            client = UrBackupApiClient(
                session=session,
                base_url=url,
                username=user_input.get(CONF_USERNAME, ""),
                password=user_input.get(CONF_PASSWORD, ""),
            )

            try:
                await client.login()
            except UrBackupAuthenticationError:
                errors["base"] = "invalid_auth"
            except UrBackupApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                user_input[CONF_URL] = url
                return self.async_create_entry(
                    title=f"UrBackup ({parsed.hostname})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
