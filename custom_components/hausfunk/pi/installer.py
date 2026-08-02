"""One-time installation and update of the Hausfunk Pi via SSH."""

from pathlib import Path

import logging

from homeassistant.core import HomeAssistant

from ..const import (
    CONF_AUDIO_GAIN,
    CONF_FPS,
    CONF_GO2RTC_VERSION,
    CONF_HEIGHT,
    CONF_PI_USERNAME,
    CONF_RTSP_PORT,
    CONF_STREAM_NAME,
    CONF_WIDTH,
    GO2RTC_RELEASE_URL,
    PI_BINARY,
    PI_CONFIG,
    PI_INSTALL_DIR,
    PI_SERVICE_NAME,
)
from .ssh import PiCommandError, PiConnectionError, PiSSH

_LOGGER = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

# uname -m -> go2rtc release suffix
ARCH_MAP = {
    "aarch64": "arm64",
    "armv7l": "arm",
    "armv6l": "armv6",
    "x86_64": "amd64",
    "i686": "i386",
}

SERVICE_PATH = f"/etc/systemd/system/{PI_SERVICE_NAME}.service"
BINARY_PATH = f"{PI_INSTALL_DIR}/{PI_BINARY}"
CONFIG_PATH = f"{PI_INSTALL_DIR}/{PI_CONFIG}"


def _render(template_path: str, values: dict) -> str:
    """Render an asset template, replacing {{ token }} placeholders."""
    content = (ASSETS_DIR / template_path).read_text(encoding="utf-8")
    for key, value in values.items():
        content = content.replace(f"{{{{ {key} }}}}", str(value))
    return content


class HausfunkInstaller:
    """Executes the Pi setup steps over SSH."""

    def __init__(self, hass: HomeAssistant, ssh: PiSSH, config: dict):
        self.hass = hass
        self.ssh = ssh
        self.config = config
        self._sudo_password: str | None = None

    async def _sudo(self, command: str, timeout: int = 120):
        """Run a sudo command with the configured sudo password."""
        return await self.ssh.sudo(command, password=self._sudo_password, timeout=timeout)

    async def install(self, password: str | None = None) -> str:
        """Run the full install. Returns a status message."""
        self._sudo_password = password
        try:
            await self.ssh.connect()
            arch = await self._detect_arch()
            await self._ensure_ffmpeg()
            await self._download_binary(arch)
            await self._write_config()
            await self._write_service()
            await self._enable_service()
            return f"Hausfunk Pi eingerichtet (go2rtc {self.config[CONF_GO2RTC_VERSION]}, Arch: {arch})"
        finally:
            await self.ssh.close()

    async def update(self, password: str | None = None) -> str:
        """Update the go2rtc binary and restart the service."""
        self._sudo_password = password
        try:
            await self.ssh.connect()
            arch = await self._detect_arch()
            await self._download_binary(arch)
            status, _out, err = await self._sudo(
                f"systemctl restart {PI_SERVICE_NAME}"
            )
            if status != 0:
                raise PiCommandError(f"Restart fehlgeschlagen: {err}")
            return f"go2rtc auf {self.config[CONF_GO2RTC_VERSION]} aktualisiert"
        finally:
            await self.ssh.close()

    async def _detect_arch(self) -> str:
        status, out, _err = await self.ssh.run("uname -m")
        if status != 0:
            raise PiCommandError("uname -m fehlgeschlagen")
        arch = ARCH_MAP.get(out.strip())
        if arch is None:
            raise PiConnectionError(f"Nicht unterstützte Architektur: {out.strip()}")
        return arch

    async def _ensure_ffmpeg(self):
        status, _out, _err = await self.ssh.run("command -v ffmpeg")
        if status == 0:
            return
        _LOGGER.info("ffmpeg fehlt auf der Pi, installiere ...")
        status, _out, err = await self._sudo(
            "apt-get update && apt-get install -y ffmpeg", timeout=300
        )
        if status != 0:
            raise PiCommandError(f"ffmpeg-Installation fehlgeschlagen: {err}")

    async def _download_binary(self, arch: str):
        version = self.config[CONF_GO2RTC_VERSION]
        url = GO2RTC_RELEASE_URL.format(version=version, arch=arch)
        await self._ensure_dir()
        status, _out, err = await self._sudo(
            f"curl -fsSL -o {BINARY_PATH} {url} && chmod +x {BINARY_PATH}"
        )
        if status != 0:
            raise PiCommandError(f"Binary-Download fehlgeschlagen: {err}")

    async def _ensure_dir(self):
        status, _out, err = await self._sudo(f"mkdir -p {PI_INSTALL_DIR}")
        if status != 0:
            raise PiCommandError(f"mkdir fehlgeschlagen: {err}")

    async def _write_config(self):
        content = _render("go2rtc.yaml.j2", {
            "rtsp_port": self.config[CONF_RTSP_PORT],
            "stream_name": self.config[CONF_STREAM_NAME],
            "width": self.config[CONF_WIDTH],
            "height": self.config[CONF_HEIGHT],
            "fps": self.config[CONF_FPS],
            "audio_gain": self.config[CONF_AUDIO_GAIN],
        })
        await self.ssh.write_file(
            CONFIG_PATH, content, sudo=True, sudo_password=self._sudo_password
        )

    async def _write_service(self):
        status, out, _err = await self.ssh.run("id -u")
        if status != 0:
            raise PiCommandError("id -u fehlgeschlagen")
        uid = out.strip()
        content = _render("hausfunk-pi.service.j2", {
            "install_dir": PI_INSTALL_DIR,
            "pi_user": self.config[CONF_PI_USERNAME],
            "uid": uid,
        })
        await self.ssh.write_file(
            SERVICE_PATH, content, sudo=True, sudo_password=self._sudo_password
        )

    async def _enable_service(self):
        status, _out, err = await self._sudo(
            f"systemctl daemon-reload && systemctl enable --now {PI_SERVICE_NAME}"
        )
        if status != 0:
            raise PiCommandError(f"Service-Aktivierung fehlgeschlagen: {err}")
        status, out, _err = await self._sudo(
            f"systemctl is-active {PI_SERVICE_NAME}"
        )
        if status != 0 or "active" not in out:
            raise PiCommandError(f"Service nicht aktiv: {out.strip()}")
