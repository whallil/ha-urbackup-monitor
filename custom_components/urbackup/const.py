"""Constants for the UrBackup integration."""

DOMAIN = "urbackup"
DEFAULT_PORT = 55414
DEFAULT_SCAN_INTERVAL = 300

BACKUP_ACTION_TYPES: dict[int, str] = {
    0: "idle",
    1: "incremental_file",
    2: "full_file",
    3: "incremental_image",
    4: "full_image",
    5: "resume_incremental_file",
    6: "resume_full_file",
    7: "cdp_sync",
    8: "restore_file",
    9: "restore_image",
    10: "update",
    11: "check_integrity",
    12: "backup_database",
    13: "recalculate_statistics",
    14: "nightly_cleanup",
    15: "emergency_cleanup",
    16: "storage_migration",
    17: "startup_recovery",
}
