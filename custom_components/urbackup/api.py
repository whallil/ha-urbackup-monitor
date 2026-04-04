"""Async API client for UrBackup server."""

from __future__ import annotations

import binascii
import hashlib
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class UrBackupApiError(Exception):
    """Base exception for UrBackup API errors."""


class UrBackupAuthenticationError(UrBackupApiError):
    """Authentication failed."""


class UrBackupConnectionError(UrBackupApiError):
    """Connection failed."""


class UrBackupApiClient:
    """Async API client for UrBackup server."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        username: str = "",
        password: str = "",
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._server_session: str | None = None

    async def _request(
        self, action: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Make a request to the UrBackup API."""
        url = f"{self._base_url}/x?a={action}"
        data = params or {}
        if self._server_session:
            data["ses"] = self._server_session

        try:
            async with self._session.post(url, data=data) as response:
                response.raise_for_status()
                return await response.json(content_type=None)
        except aiohttp.ClientConnectorError as err:
            raise UrBackupConnectionError(
                f"Cannot connect to UrBackup server: {err}"
            ) from err
        except aiohttp.ClientError as err:
            raise UrBackupApiError(f"API request failed: {err}") from err

    async def login(self) -> bool:
        """Authenticate with the UrBackup server."""
        # Try anonymous login first
        result = await self._request("login")
        if result.get("success"):
            self._server_session = result.get("session")
            return True

        if not self._username:
            raise UrBackupAuthenticationError("Server requires credentials")

        # Get salt for password hashing
        salt_result = await self._request("salt", {"username": self._username})
        ses = salt_result.get("ses", "")
        salt = salt_result.get("salt", "")
        rnd = salt_result.get("rnd", "")
        pbkdf2_rounds = salt_result.get("pbkdf2_rounds", 0)

        if not ses or salt_result.get("error") == 1:
            raise UrBackupAuthenticationError("Failed to get authentication salt")

        # Hash password: MD5 of (salt + password) as raw bytes
        pw_hash_bin = hashlib.md5(
            (salt + self._password).encode()
        ).digest()
        pw_hash = binascii.hexlify(pw_hash_bin).decode()

        if pbkdf2_rounds > 0:
            pw_hash = binascii.hexlify(
                hashlib.pbkdf2_hmac(
                    "sha256",
                    pw_hash_bin,
                    salt.encode(),
                    pbkdf2_rounds,
                )
            ).decode()

        password_hash = hashlib.md5((rnd + pw_hash).encode()).hexdigest()

        # Login with hashed password
        self._server_session = ses
        result = await self._request(
            "login",
            {"username": self._username, "password": password_hash},
        )

        if not result.get("success"):
            self._server_session = None
            raise UrBackupAuthenticationError("Invalid credentials")

        return True

    async def _authenticated_request(
        self, action: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Make an authenticated request, re-logging in if needed."""
        if not self._server_session:
            await self.login()

        result = await self._request(action, params)

        # Re-login on session expiry
        if result.get("error") == 1:
            await self.login()
            result = await self._request(action, params)

        return result

    async def get_status(self) -> dict[str, Any]:
        """Get server and client status."""
        return await self._authenticated_request("status")

    async def get_usage(self) -> dict[str, Any]:
        """Get storage usage."""
        return await self._authenticated_request("usage")

    async def get_progress(self) -> dict[str, Any]:
        """Get active backup progress."""
        return await self._authenticated_request(
            "progress", {"with_lastacts": "1"}
        )

    async def get_activities(self) -> dict[str, Any]:
        """Get last activities."""
        return await self._authenticated_request("lastacts")

    async def start_backup(
        self, client_id: int, backup_type: str = "incr_file"
    ) -> dict[str, Any]:
        """Start a backup for a client."""
        return await self._authenticated_request(
            "start_backup",
            {"start_client": str(client_id), "start_type": backup_type},
        )
