"""DataUpdateCoordinator for UrBackup."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import UrBackupApiClient, UrBackupApiError, UrBackupAuthenticationError
from .const import BACKUP_ACTION_TYPES, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

EVENT_BACKUP_ACTIVITY = f"{DOMAIN}_backup_activity"


def _format_size(size_bytes: int) -> str:
    """Format bytes into a human-readable string."""
    if size_bytes < 0:
        return "unknown"
    if size_bytes < 1024**2:
        return f"{size_bytes / 1024:.0f} KB"
    if size_bytes < 1024**3:
        return f"{size_bytes / (1024**2):.1f} MB"
    return f"{size_bytes / (1024**3):.2f} GB"


def _format_duration(seconds: int) -> str:
    """Format seconds into a human-readable string."""
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}min"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}h {minutes}min" if minutes else f"{hours}h"


class UrBackupDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage fetching UrBackup data."""

    def __init__(self, hass: HomeAssistant, client: UrBackupApiClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self._seen_activity_ids: set[int] = set()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from UrBackup server."""
        try:
            status = await self.client.get_status()
            usage = await self.client.get_usage()
            progress = await self.client.get_progress()

            clients: dict[int, dict[str, Any]] = {}
            for client in status.get("status", []):
                clients[client["id"]] = client

            # Merge usage data (keyed by name) into client dicts
            usage_by_name = {
                u["name"]: u for u in usage.get("usage", [])
            }
            for client in clients.values():
                if (u := usage_by_name.get(client["name"])):
                    client["storage_used"] = u.get("used", 0)
                    client["storage_files"] = u.get("files", 0)
                    client["storage_images"] = u.get("images", 0)

            # Merge active progress (keyed by clientid) into client dicts
            for client in clients.values():
                client["active_process"] = None
            for proc in progress.get("progress", []):
                cid = proc.get("clientid")
                if cid in clients:
                    clients[cid]["active_process"] = proc

            # Attach last activities per client and fire events for new ones
            activities_by_client: dict[int, list[dict[str, Any]]] = {}
            for act in progress.get("lastacts", []):
                cid = act.get("clientid")
                activities_by_client.setdefault(cid, []).append(act)

                act_id = act.get("id")
                if act_id and act_id not in self._seen_activity_ids:
                    self._seen_activity_ids.add(act_id)
                    # Only fire events after first poll (skip initial load)
                    if self.data is not None:
                        self._fire_activity_event(act, clients.get(cid, {}))

            for client in clients.values():
                client["last_activities"] = activities_by_client.get(
                    client["id"], []
                )

            return {
                "clients": clients,
                "server_identity": status.get("server_identity"),
                "server_version": status.get("curr_version_str"),
            }
        except UrBackupAuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except UrBackupApiError as err:
            raise UpdateFailed(
                f"Error communicating with UrBackup: {err}"
            ) from err

    def _fire_activity_event(
        self, activity: dict[str, Any], client: dict[str, Any]
    ) -> None:
        """Fire an HA event for a new backup activity."""
        client_name = activity.get("name", client.get("name", "Unknown"))
        is_image = activity.get("image", 0) == 1
        is_incremental = activity.get("incremental", 0) > 0
        is_restore = activity.get("restore", 0) == 1
        is_deleted = activity.get("del", False)
        duration = activity.get("duration", 0)
        size_bytes = activity.get("size_bytes", -1)

        if is_deleted:
            backup_kind = "image" if is_image else "file"
            message = f"{client_name} — {backup_kind} backup deleted"
        elif is_restore:
            backup_kind = "image" if is_image else "file"
            message = f"{client_name} — {backup_kind} restore completed"
        else:
            inc_label = "incremental" if is_incremental else "full"
            backup_kind = "image" if is_image else "file"
            parts = [f"{client_name} — {inc_label} {backup_kind} backup completed"]
            details = []
            if duration > 0:
                details.append(_format_duration(duration))
            if size_bytes > 0:
                details.append(_format_size(size_bytes))
            if details:
                parts.append(f"({', '.join(details)})")
            message = " ".join(parts)

        self.hass.bus.async_fire(
            EVENT_BACKUP_ACTIVITY,
            {
                "client_name": client_name,
                "client_id": activity.get("clientid"),
                "message": message,
                "backup_type": "image" if is_image else "file",
                "incremental": is_incremental,
                "restore": is_restore,
                "deleted": is_deleted,
                "duration_seconds": duration,
                "size_bytes": size_bytes,
            },
        )
