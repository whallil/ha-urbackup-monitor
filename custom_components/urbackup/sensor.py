"""Sensor platform for UrBackup."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import UrBackupConfigEntry
from .const import BACKUP_ACTION_TYPES
from .coordinator import UrBackupDataUpdateCoordinator
from .entity import UrBackupEntity


def _timestamp_to_datetime(ts: int | str | None) -> datetime | None:
    """Convert unix timestamp to datetime."""
    if ts is None or ts == 0 or ts == -1 or ts == "-":
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=UTC)
    except (ValueError, TypeError, OSError):
        return None


def _bytes_to_gb(value: float | int | None) -> float | None:
    """Convert bytes to gigabytes."""
    if value is None:
        return None
    gb = round(max(0, value) / (1024**3), 2)
    return gb


def _get_active_action(data: dict[str, Any]) -> str:
    """Get the current backup action as a string."""
    proc = data.get("active_process")
    if not proc:
        return "idle"
    return BACKUP_ACTION_TYPES.get(proc.get("action", 0), "unknown")


def _get_progress_pct(data: dict[str, Any]) -> float | None:
    """Get current backup progress percentage."""
    proc = data.get("active_process")
    if not proc:
        return None
    pcdone = proc.get("pcdone", -1)
    if pcdone < 0:
        return None
    return round(pcdone, 1)


def _get_progress_attrs(data: dict[str, Any]) -> dict[str, Any]:
    """Get extra attributes for backup progress."""
    proc = data.get("active_process")
    if not proc:
        return {}
    attrs: dict[str, Any] = {}
    if (speed := proc.get("speed_bpms")) and speed > 0:
        attrs["speed_mbps"] = round(speed * 1000 / (1024**2), 2)
    if (eta := proc.get("eta_ms")) and eta > 0:
        attrs["eta_seconds"] = round(eta / 1000)
    if (done := proc.get("done_bytes")) is not None:
        attrs["done_gb"] = _bytes_to_gb(done)
    if (total := proc.get("total_bytes")) is not None:
        attrs["total_gb"] = _bytes_to_gb(total)
    if proc.get("paused"):
        attrs["paused"] = True
    return attrs


def _get_last_activity(data: dict[str, Any]) -> dict[str, Any] | None:
    """Get the most recent non-deleted activity for a client."""
    activities = data.get("last_activities", [])
    for act in activities:
        if not act.get("del", False):
            return act
    return None


def _get_last_activity_time(data: dict[str, Any]) -> datetime | None:
    """Get the timestamp of the last activity."""
    act = _get_last_activity(data)
    if not act:
        return None
    return _timestamp_to_datetime(act.get("backuptime"))


def _format_duration_short(seconds: int) -> str:
    """Format seconds into a readable string."""
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}h {minutes}m"


def _get_last_activity_attrs(data: dict[str, Any]) -> dict[str, Any]:
    """Get attributes from the last activity."""
    act = _get_last_activity(data)
    if not act:
        return {}
    attrs: dict[str, Any] = {
        "backup_type": "image" if act.get("image", 0) == 1 else "file",
        "incremental": act.get("incremental", 0) > 0,
    }
    duration = act.get("duration", 0)
    if duration > 0:
        attrs["duration"] = _format_duration_short(duration)
        attrs["duration_seconds"] = duration
    size_bytes = act.get("size_bytes", -1)
    if size_bytes > 0:
        attrs["size_gb"] = _bytes_to_gb(size_bytes)
    if act.get("resumed", 0) == 1:
        attrs["resumed"] = True
    if act.get("restore", 0) == 1:
        attrs["restore"] = True
    return attrs


@dataclass(frozen=True, kw_only=True)
class UrBackupSensorEntityDescription(SensorEntityDescription):
    """Describe an UrBackup sensor."""

    value_fn: Callable[[dict[str, Any]], Any]
    attr_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


SENSOR_DESCRIPTIONS: tuple[UrBackupSensorEntityDescription, ...] = (
    UrBackupSensorEntityDescription(
        key="last_file_backup",
        translation_key="last_file_backup",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: _timestamp_to_datetime(data.get("lastbackup")),
        attr_fn=lambda data: {
            "issues": data.get("last_filebackup_issues", 0),
            "disabled": data.get("file_disabled", False),
        },
    ),
    UrBackupSensorEntityDescription(
        key="last_image_backup",
        translation_key="last_image_backup",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: _timestamp_to_datetime(
            data.get("lastbackup_image")
        ),
        attr_fn=lambda data: {
            "disabled": data.get("image_disabled", False),
        },
    ),
    UrBackupSensorEntityDescription(
        key="storage_used",
        translation_key="storage_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        value_fn=lambda data: _bytes_to_gb(data.get("storage_used")),
        attr_fn=lambda data: {
            "files_gb": _bytes_to_gb(data.get("storage_files")),
            "images_gb": _bytes_to_gb(data.get("storage_images")),
        },
    ),
    UrBackupSensorEntityDescription(
        key="backup_activity",
        translation_key="backup_activity",
        value_fn=_get_active_action,
        attr_fn=_get_progress_attrs,
    ),
    UrBackupSensorEntityDescription(
        key="backup_progress",
        translation_key="backup_progress",
        native_unit_of_measurement="%",
        suggested_display_precision=1,
        value_fn=_get_progress_pct,
        attr_fn=_get_progress_attrs,
    ),
    UrBackupSensorEntityDescription(
        key="last_activity",
        translation_key="last_activity",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_get_last_activity_time,
        attr_fn=_get_last_activity_attrs,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UrBackupConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UrBackup sensors."""
    coordinator = entry.runtime_data.coordinator

    entities: list[UrBackupSensorEntity] = []
    for client_id in coordinator.data.get("clients", {}):
        for description in SENSOR_DESCRIPTIONS:
            entities.append(
                UrBackupSensorEntity(
                    coordinator=coordinator,
                    description=description,
                    client_id=client_id,
                    entry_id=entry.entry_id,
                )
            )

    async_add_entities(entities)


class UrBackupSensorEntity(UrBackupEntity, SensorEntity):
    """Representation of an UrBackup sensor."""

    entity_description: UrBackupSensorEntityDescription

    def __init__(
        self,
        coordinator: UrBackupDataUpdateCoordinator,
        description: UrBackupSensorEntityDescription,
        client_id: int,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator, client_id, entry_id)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{client_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        if (client := self.client_data) is None:
            return None
        return self.entity_description.value_fn(client)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if self.entity_description.attr_fn and (client := self.client_data):
            return self.entity_description.attr_fn(client)
        return None
