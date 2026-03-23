"""Binary sensor platform for UrBackup."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import UrBackupConfigEntry
from .coordinator import UrBackupDataUpdateCoordinator
from .entity import UrBackupEntity


@dataclass(frozen=True, kw_only=True)
class UrBackupBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe an UrBackup binary sensor."""

    value_fn: Callable[[dict[str, Any]], bool | None]


BINARY_SENSOR_DESCRIPTIONS: tuple[UrBackupBinarySensorEntityDescription, ...] = (
    UrBackupBinarySensorEntityDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda data: data.get("online", False),
    ),
    UrBackupBinarySensorEntityDescription(
        key="file_backup_status",
        translation_key="file_backup_status",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: (
            not data.get("file_ok", True)
            if not data.get("file_disabled")
            else None
        ),
    ),
    UrBackupBinarySensorEntityDescription(
        key="image_backup_status",
        translation_key="image_backup_status",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: (
            not data.get("image_ok", True)
            if not data.get("image_disabled")
            and not data.get("image_not_supported")
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UrBackupConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UrBackup binary sensors."""
    coordinator = entry.runtime_data.coordinator

    entities: list[UrBackupBinarySensorEntity] = []
    for client_id in coordinator.data.get("clients", {}):
        for description in BINARY_SENSOR_DESCRIPTIONS:
            entities.append(
                UrBackupBinarySensorEntity(
                    coordinator=coordinator,
                    description=description,
                    client_id=client_id,
                    entry_id=entry.entry_id,
                )
            )

    async_add_entities(entities)


class UrBackupBinarySensorEntity(UrBackupEntity, BinarySensorEntity):
    """Representation of an UrBackup binary sensor."""

    entity_description: UrBackupBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: UrBackupDataUpdateCoordinator,
        description: UrBackupBinarySensorEntityDescription,
        client_id: int,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator, client_id, entry_id)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{client_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        if (client := self.client_data) is None:
            return None
        return self.entity_description.value_fn(client)
