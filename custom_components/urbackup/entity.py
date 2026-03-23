"""Base entity for UrBackup."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import UrBackupDataUpdateCoordinator


class UrBackupEntity(CoordinatorEntity[UrBackupDataUpdateCoordinator]):
    """Base entity for UrBackup."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: UrBackupDataUpdateCoordinator,
        client_id: int,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._client_id = client_id
        self._entry_id = entry_id

    @property
    def client_data(self) -> dict[str, Any] | None:
        """Get this client's data from the coordinator."""
        return self.coordinator.data.get("clients", {}).get(self._client_id)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.client_data is not None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        client = self.client_data or {}
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_{self._client_id}")},
            name=client.get("name", f"Client {self._client_id}"),
            manufacturer="UrBackup",
            model=client.get(
                "os_version_string", client.get("os_simple", "Unknown")
            ),
            sw_version=client.get("client_version_string"),
        )
