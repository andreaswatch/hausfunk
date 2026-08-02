"""Thin asyncssh wrapper for one-shot Pi administration commands."""

import asyncio
import logging

import asyncssh

_LOGGER = logging.getLogger(__name__)


class PiConnectionError(Exception):
    """Raised when the Pi cannot be reached over SSH."""


class PiCommandError(Exception):
    """Raised when a command on the Pi fails."""


class PiSSH:
    """AsyncSSH client for one-shot commands and file writes."""

    def __init__(self, host, port, username, password=None, ssh_key=None):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._ssh_key = ssh_key
        self._conn = None

    async def connect(self):
        """Establish the SSH connection. Accepts unknown host keys."""
        kwargs = {
            "host": self._host,
            "port": self._port,
            "username": self._username,
            "known_hosts": None,
        }
        if self._password:
            kwargs["password"] = self._password
        if self._ssh_key:
            kwargs["client_keys"] = [self._ssh_key]
        try:
            self._conn = await asyncio.wait_for(
                asyncssh.connect(**kwargs), timeout=20
            )
        except (OSError, asyncssh.Error) as err:
            raise PiConnectionError(f"SSH-Verbindung fehlgeschlagen: {err}") from err
        return self

    @property
    def host_key_fingerprint(self):
        """SHA256 host-key fingerprint (empty string if unknown)."""
        if self._conn is None or self._conn.host_key is None:
            return ""
        return self._conn.host_key.fingerprint.hash

    async def run(self, command, input_data=None, timeout=60):
        """Run a command and return (exit_status, stdout, stderr)."""
        if self._conn is None:
            raise PiConnectionError("Nicht verbunden")
        try:
            result = await asyncio.wait_for(
                self._conn.run(command, input=input_data, check=False),
                timeout=timeout,
            )
        except (OSError, asyncssh.Error) as err:
            raise PiCommandError(f"Kommando fehlgeschlagen: {err}") from err
        return result.exit_status, result.stdout, result.stderr

    async def sudo(self, command, password=None, timeout=120):
        """Run a command via `sudo -S`, feeding the password to stdin."""
        sudo_pwd = password or self._password or ""
        return await self.run(
            f"sudo -S {command}", input_data=f"{sudo_pwd}\n", timeout=timeout
        )

    async def write_file(
        self, path, content, mode=None, sudo=False, sudo_password=None
    ):
        """Write a file over SFTP, optionally via sudo (temp file + move)."""
        if self._conn is None:
            raise PiConnectionError("Nicht verbunden")
        async with self._conn.start_sftp_client() as sftp:
            if sudo:
                tmp = f"/tmp/hausfunk-{path.rsplit('/', 1)[-1]}"
            else:
                tmp = path
            async with sftp.open(tmp, "w") as fh:
                await fh.write(content)
            if mode is not None:
                await sftp.chmod(tmp, mode)
            if sudo:
                status, _out, err = await self.sudo(
                    f"mv {tmp} {path}", password=sudo_password
                )
                if status != 0:
                    raise PiCommandError(f"mv nach {path} fehlgeschlagen: {err}")
                if mode is not None:
                    status, _out, err = await self.sudo(
                        f"chmod {mode:o} {path}", password=sudo_password
                    )
                    if status != 0:
                        raise PiCommandError(f"chmod fehlgeschlagen: {err}")

    async def close(self):
        """Close the SSH connection."""
        if self._conn is not None:
            self._conn.close()
            await self._conn.wait_closed()
            self._conn = None
