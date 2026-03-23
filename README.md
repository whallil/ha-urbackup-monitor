# UrBackup Monitor for Home Assistant

A [HACS](https://hacs.xyz/) custom integration that monitors your [UrBackup](https://www.urbackup.org/) server directly from Home Assistant.

## Features

- **Per-client devices** — each UrBackup client appears as a device in HA with OS and version info
- **Backup status sensors** — last file/image backup timestamps, backup health (ok/problem)
- **Storage statistics** — total, file, and image storage usage per client (GB)
- **Live backup tracking** — current backup activity, progress percentage, speed, and ETA
- **Activity history** — last completed backup with duration and size
- **Logbook events** — new backup completions/failures fire events into the HA logbook
- **Start backups** — trigger incremental/full file/image backups from HA via service call
- **Automations** — trigger on backup events (failures, completions, long-running backups)

## Installation

### HACS (Recommended)

1. Open **HACS** in your Home Assistant instance
2. Click the three-dot menu → **Custom repositories**
3. Add `whallil/ha-urbackup-monitor` with category **Integration**
4. Click **Download**
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/urbackup` folder into your HA `custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **UrBackup**
3. Enter your UrBackup server URL (e.g., `http://your-server:55414`)
4. Optionally enter username and password (leave blank for anonymous access)

## Entities

Each UrBackup client creates a device with the following entities:

### Sensors

| Entity | Description |
|---|---|
| Last file backup | Timestamp of the last completed file backup |
| Last image backup | Timestamp of the last completed image backup |
| Storage used | Total storage used in GB (attributes: files_gb, images_gb) |
| Backup activity | Current action: idle, incremental_file, full_file, etc. |
| Backup progress | Percentage complete (attributes: speed_mbps, eta_seconds) |
| Last activity | Timestamp of most recent activity (attributes: backup_type, duration, size_gb) |

### Binary Sensors

| Entity | Description |
|---|---|
| Online | Whether the client is currently connected |
| File backup problem | True when file backups are failing |
| Image backup problem | True when image backups are failing |

## Services

### `urbackup.start_backup`

Trigger a backup for a specific client.

| Field | Required | Description |
|---|---|---|
| `client_id` | Yes | The UrBackup client ID |
| `backup_type` | No | `incr_file` (default), `full_file`, `incr_image`, `full_image` |

**Example automation:**

```yaml
service: urbackup.start_backup
data:
  client_id: 4
  backup_type: full_file
```

## Events

The integration fires `urbackup_backup_activity` events when backups complete, fail, or are deleted. These appear in the HA logbook and can be used as automation triggers.

**Event data:**

| Field | Description |
|---|---|
| `client_name` | Name of the backup client |
| `client_id` | UrBackup client ID |
| `message` | Human-readable summary |
| `backup_type` | `file` or `image` |
| `incremental` | Whether the backup was incremental |
| `duration_seconds` | How long the backup took |
| `size_bytes` | Backup size |

**Example automation — notify on backup failure:**

```yaml
automation:
  trigger:
    - platform: state
      entity_id: binary_sensor.urbackup_dev3_file_backup_problem
      to: "on"
  action:
    - service: notify.mobile_app
      data:
        message: "UrBackup: File backup problem detected on dev3"
```

## Requirements

- UrBackup Server 2.x+
- Home Assistant 2024.1.0+
- HACS 2.0.0+

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE), the same license used by UrBackup.
