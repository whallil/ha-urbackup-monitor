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


def _normalize_url(raw_url: str) -> str:
    """Build a base URL out of whatever the user typed.

    A bare host gets the UrBackup scheme and port ("nas" ->
    "http://nas:55414"), while a host that already carries a port keeps it.
    An explicit scheme is left untouched, so an UrBackup server behind a
    reverse proxy on 80/443 still works.
    """
    url = raw_url.strip().rstrip("/")
    if url.startswith(("http://", "https://")):
        return url

    url = f"http://{url}"
    try:
        has_port = urlparse(url).port is not None
    except ValueError:
        # Unparseable port - leave it alone and let the login attempt fail
        # with a connection error rather than mangling the input further.
        return url

    return url if has_port else f"{url}:{DEFAULT_PORT}"


class UrBackupConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for UrBackup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = _normalize_url(user_input[CONF_URL])
            parsed = urlparse(url)

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
