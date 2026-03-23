"""The UrBackup integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import UrBackupApiClient
from .const import DOMAIN
from .coordinator import UrBackupDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

SERVICE_START_BACKUP_SCHEMA = vol.Schema(
    {
        vol.Required("client_id"): vol.Coerce(int),
        vol.Optional("backup_type", default="incr_file"): vol.In(
            ["incr_file", "full_file", "incr_image", "full_image"]
        ),
    }
)

type UrBackupConfigEntry = ConfigEntry[UrBackupRuntimeData]


@dataclass
class UrBackupRuntimeData:
    """Runtime data for UrBackup integration."""

    coordinator: UrBackupDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: UrBackupConfigEntry
) -> bool:
    """Set up UrBackup from a config entry."""
    session = async_get_clientsession(hass)
    client = UrBackupApiClient(
        session=session,
        base_url=entry.data[CONF_URL],
        username=entry.data.get(CONF_USERNAME, ""),
        password=entry.data.get(CONF_PASSWORD, ""),
    )

    coordinator = UrBackupDataUpdateCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = UrBackupRuntimeData(coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def handle_start_backup(call: ServiceCall) -> None:
        """Handle the start_backup service call."""
        client_id = call.data["client_id"]
        backup_type = call.data.get("backup_type", "incr_file")

        result = await coordinator.client.start_backup(client_id, backup_type)
        for r in result.get("result", []):
            if r.get("start_ok"):
                _LOGGER.info(
                    "Started %s backup for client %s", backup_type, client_id
                )
            else:
                _LOGGER.error(
                    "Failed to start %s backup for client %s",
                    backup_type,
                    client_id,
                )

        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        "start_backup",
        handle_start_backup,
        schema=SERVICE_START_BACKUP_SCHEMA,
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: UrBackupConfigEntry
) -> bool:
    """Unload a config entry."""
    hass.services.async_remove(DOMAIN, "start_backup")
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
