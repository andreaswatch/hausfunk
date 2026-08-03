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
    PI_SERVICE_NAME,
    PI_SUBDIR,
    PI_USER_SERVICE_DIR,
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

SERVICE_PATH_TEMPLATE = "{home_dir}/{service_dir}/{service_name}.service"


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
        self._home_dir: str = ""
        self._binary_path: str = ""
        self._config_path: str = ""

    async def _sudo(self, command: str, timeout: int = 120):
        """Run a sudo command with the configured sudo password."""
        return await self.ssh.sudo(command, password=self._sudo_password, timeout=timeout)

    async def _detect_home(self):
        """Detect the user's home directory."""
        status, out, _err = await self.ssh.run("echo $HOME")
        if status != 0:
            raise PiCommandError("Konnte Home-Verzeichnis nicht ermitteln")
        self._home_dir = out.strip()
        self._binary_path = f"{self._home_dir}/{PI_SUBDIR}/{PI_BINARY}"
        self._config_path = f"{self._home_dir}/{PI_SUBDIR}/{PI_CONFIG}"

    async def install(self, password: str | None = None) -> str:
        """Run the full install. Returns a status message."""
        self._sudo_password = password
        try:
            await self.ssh.connect()
            _LOGGER.info("Verbunden mit Pi, starte Installation")
            
            await self._detect_home()
            _LOGGER.info(f"Home-Verzeichnis: {self._home_dir}")
            
            arch = await self._detect_arch()
            _LOGGER.info(f"Architektur erkannt: {arch}")
            
            await self._ensure_ffmpeg()
            _LOGGER.info("ffmpeg vorhanden")
            
            await self._download_binary(arch)
            _LOGGER.info(f"Binary installiert: {self._binary_path}")
            
            await self._write_config()
            _LOGGER.info(f"Config geschrieben: {self._config_path}")
            
            await self._write_service()
            _LOGGER.info("Service-Datei geschrieben")
            
            await self._enable_service()
            _LOGGER.info("Service aktiviert und gestartet")
            
            return f"Hausfunk Pi eingerichtet (go2rtc {self.config[CONF_GO2RTC_VERSION]}, Arch: {arch})"
        finally:
            await self.ssh.close()

    async def update(self, password: str | None = None) -> str:
        """Update the go2rtc binary and restart the service."""
        self._sudo_password = password
        try:
            await self.ssh.connect()
            _LOGGER.info("Verbunden mit Pi, starte Update")
            
            await self._detect_home()
            arch = await self._detect_arch()
            
            await self._download_binary(arch)
            _LOGGER.info(f"Binary aktualisiert: {self._binary_path}")
            
            # Restart service
            status, out, err = await self.ssh.run(f"systemctl --user restart {PI_SERVICE_NAME}")
            if status != 0:
                status2, out2, err2 = await self.ssh.run(f"systemctl --user status {PI_SERVICE_NAME} || true")
                raise PiCommandError(f"Restart fehlgeschlagen: {err}\nStatus: {out2}")
            
            # Wait for restart
            await self.ssh.run("sleep 2")
            
            # Verify service is active
            status, out, err = await self.ssh.run(f"systemctl --user is-active {PI_SERVICE_NAME}")
            if status != 0 or "active" not in out:
                status2, out2, err2 = await self.ssh.run(f"systemctl --user status {PI_SERVICE_NAME} || true")
                raise PiCommandError(f"Service nicht aktiv nach Restart: {out.strip()}\nStatus: {out2}")
            
            _LOGGER.info("Service erfolgreich neu gestartet")
            return f"go2rtc auf {self.config[CONF_GO2RTC_VERSION]} aktualisiert"
        finally:
            await self.ssh.close()

    async def uninstall(self, password: str | None = None) -> str:
        """Stop, disable and remove the Pi service, config and binary."""
        self._sudo_password = password
        try:
            await self.ssh.connect()
            _LOGGER.info("Verbunden mit Pi, starte Deinstallation")
            await self._detect_home()

            # Stop and disable the service
            await self.ssh.run(f"systemctl --user disable --now {PI_SERVICE_NAME}")
            await self.ssh.run(f"systemctl --user daemon-reload")

            # Remove service file, config and binary (best effort)
            service_path = SERVICE_PATH_TEMPLATE.format(
                home_dir=self._home_dir,
                service_dir=PI_USER_SERVICE_DIR,
                service_name=PI_SERVICE_NAME,
            )
            for path in (service_path, self._config_path, self._binary_path):
                status, _out, _err = await self.ssh.run(f"rm -f {path}")
                if status != 0:
                    _LOGGER.warning("Konnte %s nicht entfernen", path)

            return "Hausfunk Pi deinstalliert"
        finally:
            await self.ssh.close()

    async def restart_service(self, password: str | None = None) -> str:
        """Restart only the go2rtc systemd service on the Pi (no device reboot)."""
        try:
            await self.ssh.connect()
            status, out, err = await self.ssh.run(
                f"systemctl --user restart {PI_SERVICE_NAME}"
            )
            if status != 0:
                raise PiCommandError(f"go2rtc-Neustart fehlgeschlagen: {err or out}")
            await self.ssh.run("sleep 2")
            status, out, err = await self.ssh.run(
                f"systemctl --user is-active {PI_SERVICE_NAME}"
            )
            if status != 0 or out.strip() != "active":
                raise PiCommandError(
                    f"go2rtc-Dienst nicht aktiv nach Neustart: {out.strip()}"
                )
            return "go2rtc auf Pi neu gestartet"
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
        """Download go2rtc binary with robust error handling."""
        version = self.config[CONF_GO2RTC_VERSION]
        url = GO2RTC_RELEASE_URL.format(version=version, arch=arch)
        
        await self._ensure_dir()
        
        # Download to temporary file first
        temp_path = f"{self._binary_path}.tmp"
        _LOGGER.info(f"Lade go2rtc von {url} herunter")
        
        status, out, err = await self.ssh.run(
            f"curl -fsSL --max-time 120 -o {temp_path} {url}",
            timeout=150
        )
        if status != 0:
            # Clean up temp file if it exists
            await self.ssh.run(f"rm -f {temp_path}")
            raise PiCommandError(f"Download fehlgeschlagen: {err or out}")
        
        # Verify temp file exists and has content
        status, out, err = await self.ssh.run(f"test -s {temp_path}")
        if status != 0:
            await self.ssh.run(f"rm -f {temp_path}")
            raise PiCommandError(f"Downloaded Datei ist leer oder fehlt")
        
        # Make executable and move to final location
        status, out, err = await self.ssh.run(f"chmod +x {temp_path} && mv {temp_path} {self._binary_path}")
        if status != 0:
            await self.ssh.run(f"rm -f {temp_path}")
            raise PiCommandError(f"Konnte Binary nicht installieren: {err}")
        
        # Verify final binary is executable
        status, out, err = await self.ssh.run(f"test -x {self._binary_path}")
        if status != 0:
            raise PiCommandError(f"Binary nicht ausführbar nach Installation")
        
        _LOGGER.debug(f"Binary erfolgreich installiert: {self._binary_path}")

    async def _ensure_dir(self):
        """Ensure the installation directory exists and is writable."""
        install_dir = f"{self._home_dir}/{PI_SUBDIR}"
        
        # Create directory
        status, out, err = await self.ssh.run(f"mkdir -p {install_dir}")
        if status != 0:
            raise PiCommandError(f"Konnte Verzeichnis nicht erstellen: {install_dir} - {err}")
        
        # Verify directory exists and is writable
        status, out, err = await self.ssh.run(f"test -d {install_dir} && test -w {install_dir}")
        if status != 0:
            raise PiCommandError(f"Verzeichnis nicht beschreibbar: {install_dir}")
        
        _LOGGER.debug(f"Installationsverzeichnis bereit: {install_dir}")

    async def _write_config(self):
        """Write go2rtc config file with verification."""
        content = _render("go2rtc.yaml.j2", {
            "rtsp_port": self.config[CONF_RTSP_PORT],
            "stream_name": self.config[CONF_STREAM_NAME],
            "width": self.config[CONF_WIDTH],
            "height": self.config[CONF_HEIGHT],
            "fps": self.config[CONF_FPS],
            "audio_gain": self.config[CONF_AUDIO_GAIN],
        })
        
        await self.ssh.write_file(self._config_path, content)
        
        # Verify config was written
        status, out, err = await self.ssh.run(f"test -s {self._config_path}")
        if status != 0:
            raise PiCommandError(f"Config-Datei wurde nicht geschrieben: {self._config_path}")
        
        _LOGGER.debug(f"Config erfolgreich geschrieben: {self._config_path}")

    async def _write_service(self):
        """Write systemd user service file with verification."""
        status, out, _err = await self.ssh.run("id -u")
        if status != 0:
            raise PiCommandError("id -u fehlgeschlagen")
        uid = out.strip()
        
        content = _render("hausfunk-pi.service.j2", {
            "binary_path": self._binary_path,
            "config_path": self._config_path,
            "pi_user": self.config[CONF_PI_USERNAME],
            "uid": uid,
        })
        
        service_path = SERVICE_PATH_TEMPLATE.format(
            home_dir=self._home_dir,
            service_dir=PI_USER_SERVICE_DIR,
            service_name=PI_SERVICE_NAME,
        )
        
        # Ensure service directory exists
        service_dir = f"{self._home_dir}/{PI_USER_SERVICE_DIR}"
        status, out, err = await self.ssh.run(f"mkdir -p {service_dir}")
        if status != 0:
            raise PiCommandError(f"Konnte Service-Verzeichnis nicht erstellen: {service_dir} - {err}")
        
        # Write service file
        await self.ssh.write_file(service_path, content)
        
        # Verify service file was written
        status, out, err = await self.ssh.run(f"test -s {service_path}")
        if status != 0:
            raise PiCommandError(f"Service-Datei wurde nicht geschrieben: {service_path}")
        
        _LOGGER.debug(f"Service-Datei erfolgreich geschrieben: {service_path}")

    async def _enable_service(self):
        """Enable and start the systemd user service with verification."""
        # Reload systemd daemon
        status, out, err = await self.ssh.run("systemctl --user daemon-reload")
        if status != 0:
            raise PiCommandError(f"systemctl daemon-reload fehlgeschlagen: {err}")
        
        # Enable and start service
        status, out, err = await self.ssh.run(f"systemctl --user enable --now {PI_SERVICE_NAME}")
        if status != 0:
            # Get more detailed error info
            status2, out2, err2 = await self.ssh.run(f"systemctl --user status {PI_SERVICE_NAME} || true")
            raise PiCommandError(f"Service-Aktivierung fehlgeschlagen: {err}\nStatus: {out2}")
        
        # Wait a moment for service to start
        await self.ssh.run("sleep 2")
        
        # Verify service is active
        status, out, err = await self.ssh.run(f"systemctl --user is-active {PI_SERVICE_NAME}")
        if status != 0 or "active" not in out:
            # Get detailed status for debugging
            status2, out2, err2 = await self.ssh.run(f"systemctl --user status {PI_SERVICE_NAME} || true")
            raise PiCommandError(f"Service nicht aktiv: {out.strip()}\nStatus: {out2}")
        
        _LOGGER.debug(f"Service erfolgreich aktiviert: {PI_SERVICE_NAME}")
