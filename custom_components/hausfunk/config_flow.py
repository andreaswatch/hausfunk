"""Config flow for Hausfunk."""

import logging

import voluptuous as vol

from homeassistant.components import network as ha_network
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
)
from homeassistant.core import callback

from .const import (
    CONF_AUDIO_GAIN,
    CONF_FPS,
    CONF_GO2RTC_CANDIDATES,
    CONF_GO2RTC_HOST,
    CONF_GO2RTC_PASSWORD,
    CONF_GO2RTC_RTSP_PORT,
    CONF_GO2RTC_URL,
    CONF_GO2RTC_USERNAME,
    CONF_GO2RTC_VERSION,
    CONF_GO2RTC_WEBRTC_PORT,
    CONF_HEIGHT,
    CONF_INSTALL_NOW,
    CONF_PI_GO2RTC_PORT,
    CONF_PI_HOST,
    CONF_PI_PASSWORD,
    CONF_PI_PORT,
    CONF_PI_USERNAME,
    CONF_RTSP_PORT,
    CONF_STREAM_MODE,
    CONF_STREAM_NAME,
    CONF_SUDO_PASSWORD,
    CONF_WIDTH,
    DEFAULT_AUDIO_GAIN,
    DEFAULT_FPS,
    DEFAULT_GO2RTC_CANDIDATES,
    DEFAULT_GO2RTC_HOST,
    DEFAULT_GO2RTC_RTSP_PORT,
    DEFAULT_GO2RTC_URL,
    DEFAULT_GO2RTC_VERSION,
    DEFAULT_GO2RTC_WEBRTC_PORT,
    DEFAULT_HEIGHT,
    DEFAULT_PI_GO2RTC_PORT,
    DEFAULT_RTSP_PORT,
    DEFAULT_SSH_PORT,
    DEFAULT_STREAM_MODE,
    DEFAULT_STREAM_NAME,
    DEFAULT_WIDTH,
    DOMAIN,
    STREAM_MODE_RTSP,
    STREAM_MODE_WEBRTC,
)
from .go2rtc.client import Go2rtcClient, Go2rtcError
from .pi.installer import HausfunkInstaller
from .pi.ssh import PiCommandError, PiConnectionError, PiSSH
from . import get_main_entry

_LOGGER = logging.getLogger(__name__)

PI_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PI_HOST): str,
        vol.Required(CONF_PI_PORT, default=DEFAULT_SSH_PORT): int,
        vol.Required(CONF_PI_USERNAME, default="pi"): str,
        vol.Required(CONF_PI_PASSWORD): str,
        vol.Optional(CONF_SUDO_PASSWORD, default=""): str,
        vol.Required(CONF_STREAM_NAME, default=DEFAULT_STREAM_NAME): str,
        vol.Required(CONF_RTSP_PORT, default=DEFAULT_RTSP_PORT): int,
        vol.Required(CONF_PI_GO2RTC_PORT, default=DEFAULT_PI_GO2RTC_PORT): int,
        vol.Required(CONF_WIDTH, default=DEFAULT_WIDTH): int,
        vol.Required(CONF_HEIGHT, default=DEFAULT_HEIGHT): int,
        vol.Required(CONF_FPS, default=DEFAULT_FPS): int,
        vol.Required(CONF_AUDIO_GAIN, default=DEFAULT_AUDIO_GAIN): vol.Coerce(float),
    }
)

INSTALL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_INSTALL_NOW, default=True): bool,
    }
)


def _pi_connection_options_schema(defaults: dict) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_STREAM_NAME, default=defaults.get(CONF_STREAM_NAME, DEFAULT_STREAM_NAME)
            ): str,
            vol.Required(
                CONF_RTSP_PORT, default=defaults.get(CONF_RTSP_PORT, DEFAULT_RTSP_PORT)
            ): int,
            vol.Required(
                CONF_PI_GO2RTC_PORT,
                default=defaults.get(CONF_PI_GO2RTC_PORT, DEFAULT_PI_GO2RTC_PORT),
            ): int,
            vol.Required(
                CONF_WIDTH, default=defaults.get(CONF_WIDTH, DEFAULT_WIDTH)
            ): int,
            vol.Required(
                CONF_HEIGHT, default=defaults.get(CONF_HEIGHT, DEFAULT_HEIGHT)
            ): int,
            vol.Required(
                CONF_FPS, default=defaults.get(CONF_FPS, DEFAULT_FPS)
            ): int,
            vol.Required(
                CONF_AUDIO_GAIN,
                default=defaults.get(CONF_AUDIO_GAIN, DEFAULT_AUDIO_GAIN),
            ): vol.Coerce(float),
        }
    )


class HausfunkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Hausfunk."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._data = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        return HausfunkOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial config flow step."""
        # Check if the main config entry already exists
        existing_entries = self.hass.config_entries.async_entries(DOMAIN)
        main_entry = get_main_entry(self.hass)
        
        if main_entry or (existing_entries and any(CONF_PI_HOST not in e.data for e in existing_entries)):
            # Main entry already exists. Forward user to add a Pi.
            return await self.async_step_pi(user_input)

        # Otherwise, this is the initial setup. Configure the main HA-side go2rtc entry.
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(
                title="Hausfunk Sprechanlage",
                data=self._data,
            )

        schema, detected = await self._detect_go2rtc()
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            description_placeholders={"detected": detected},
        )

    async def async_step_pi(self, user_input=None):
        """Add a new Pi: SSH access."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_PI_HOST])
            self._abort_if_unique_id_configured()
            self._data.update(user_input)
            errors = await self._validate_pi(user_input)
            if not errors:
                # Populate default runtime/input settings
                self._data.setdefault(CONF_STREAM_MODE, DEFAULT_STREAM_MODE)
                return await self.async_step_install()
        return self.async_show_form(
            step_id="pi", data_schema=PI_SCHEMA, errors=errors,
            description_placeholders={
                "fingerprint": getattr(self, "_fingerprint", ""),
                "detected": "",
            },
        )

    async def async_step_install(self, user_input=None):
        """Optionally install/configure the Pi right away."""
        if user_input is not None:
            install_now = user_input.get(CONF_INSTALL_NOW, True)
            if install_now:
                errors = await self._do_install()
                if errors:
                    return self.async_show_form(
                        step_id="install", data_schema=INSTALL_SCHEMA, errors=errors
                    )
            return self.async_create_entry(
                title=f"Hausfunk Pi ({self._data[CONF_PI_HOST]})",
                data=self._data,
            )
        return self.async_show_form(step_id="install", data_schema=INSTALL_SCHEMA)

    async def _detect_go2rtc(self) -> tuple[vol.Schema, str]:
        """Try to auto-detect the HA go2rtc instance and LAN IP."""
        defaults = {
            CONF_GO2RTC_URL: DEFAULT_GO2RTC_URL,
            CONF_GO2RTC_USERNAME: "",
            CONF_GO2RTC_PASSWORD: "",
            CONF_GO2RTC_VERSION: DEFAULT_GO2RTC_VERSION,
            CONF_GO2RTC_HOST: DEFAULT_GO2RTC_HOST,
            CONF_GO2RTC_RTSP_PORT: DEFAULT_GO2RTC_RTSP_PORT,
            CONF_GO2RTC_WEBRTC_PORT: DEFAULT_GO2RTC_WEBRTC_PORT,
            CONF_GO2RTC_CANDIDATES: DEFAULT_GO2RTC_CANDIDATES,
        }
        status = "keine automatische Erkennung (Felder manuell ausfüllen)"

        found_url = None
        detected: dict = {}
        for candidate in (DEFAULT_GO2RTC_URL, "http://localhost:1984"):
            try:
                client = Go2rtcClient(url=candidate)
                await client.ensure_session()
                detected = await client.detect()
                await client.close()
                found_url = candidate
                break
            except (Go2rtcError, OSError):
                continue

        if found_url:
            defaults[CONF_GO2RTC_URL] = found_url
            defaults[CONF_GO2RTC_VERSION] = detected.get("version") or DEFAULT_GO2RTC_VERSION
            defaults[CONF_GO2RTC_WEBRTC_PORT] = detected.get("webrtc_port") or DEFAULT_GO2RTC_WEBRTC_PORT
            rtsp_listen = detected.get("rtsp_port")
            if rtsp_listen and rtsp_listen != 8554:
                defaults[CONF_GO2RTC_RTSP_PORT] = rtsp_listen
            status = f"go2rtc unter {found_url} erkannt (Version {detected.get('version') or '?'})"

        try:
            ips = await ha_network.async_get_ipv4_addresses(self.hass)
            lan = next((str(ip) for ip in ips if not ip.is_loopback), None)
            if lan:
                defaults[CONF_GO2RTC_HOST] = lan
                status += f" · LAN-IP {lan} erkannt"
        except Exception:
            pass

        schema = vol.Schema(
            {
                vol.Required(CONF_GO2RTC_URL, default=defaults[CONF_GO2RTC_URL]): str,
                vol.Optional(CONF_GO2RTC_USERNAME, default=defaults[CONF_GO2RTC_USERNAME]): str,
                vol.Optional(CONF_GO2RTC_PASSWORD, default=defaults[CONF_GO2RTC_PASSWORD]): str,
                vol.Required(CONF_GO2RTC_VERSION, default=defaults[CONF_GO2RTC_VERSION]): str,
                vol.Required(CONF_GO2RTC_HOST, default=defaults[CONF_GO2RTC_HOST]): str,
                vol.Required(CONF_GO2RTC_RTSP_PORT, default=defaults[CONF_GO2RTC_RTSP_PORT]): int,
                vol.Required(CONF_GO2RTC_WEBRTC_PORT, default=defaults[CONF_GO2RTC_WEBRTC_PORT]): int,
                vol.Optional(CONF_GO2RTC_CANDIDATES, default=defaults[CONF_GO2RTC_CANDIDATES]): str,
            }
        )
        return schema, status

    async def _validate_pi(self, data: dict) -> dict:
        ssh = PiSSH(
            data[CONF_PI_HOST], data[CONF_PI_PORT],
            data[CONF_PI_USERNAME], data[CONF_PI_PASSWORD],
        )
        try:
            await ssh.connect()
            self._fingerprint = ssh.host_key_fingerprint
            status, _out, _err = await ssh.run("uname -m")
            if status != 0:
                return {"base": "cannot_detect_arch"}
        except PiConnectionError as err:
            _LOGGER.error("SSH-Validierung fehlgeschlagen: %s", err)
            return {"base": "cannot_connect"}
        finally:
            await ssh.close()
        return {}

    async def _do_install(self) -> dict:
        ssh = PiSSH(
            self._data[CONF_PI_HOST], self._data[CONF_PI_PORT],
            self._data[CONF_PI_USERNAME], self._data[CONF_PI_PASSWORD],
        )
        main_entry = get_main_entry(self.hass)
        merged_config = {**main_entry.data, **self._data} if main_entry else self._data
        installer = HausfunkInstaller(self.hass, ssh, merged_config)
        try:
            await installer.install(self._data.get(CONF_SUDO_PASSWORD))
        except PiCommandError as err:
            _LOGGER.error("Pi-Installation failed: %s", err)
            return {"base": "install_failed"}
        return {}


class HausfunkOptionsFlow(OptionsFlow):
    """Handle options for Hausfunk."""

    def __init__(self, entry: ConfigEntry):
        self._entry = entry
        self._data = {}

    async def async_step_init(self, user_input=None):
        """Initialize options flow step."""
        if CONF_PI_HOST not in self._entry.data:
            # Main entry Options Flow (go2rtc settings)
            return await self.async_step_go2rtc(user_input)
        
        # Pi entry Options Flow (Pi connection settings)
        return await self.async_step_pi_options(user_input)

    async def async_step_pi_options(self, user_input=None):
        """Pi-specific connection settings."""
        if user_input is not None:
            self._data.update(user_input)
            new_data = {**self._entry.data, **self._data}
            self.hass.config_entries.async_update_entry(
                self._entry, data=new_data
            )
            # Reload this entry to apply changes
            await self.hass.config_entries.async_reload(self._entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=_pi_connection_options_schema(self._entry.data),
        )

    async def async_step_go2rtc(self, user_input=None):
        """HA-side go2rtc settings (shared across all devices)."""
        if user_input is not None:
            self._data.update(user_input)
            new_data = {**self._entry.data, **self._data}
            self.hass.config_entries.async_update_entry(
                self._entry, data=new_data
            )

            # Reload all Hausfunk entries to apply changes to all Pis
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                await self.hass.config_entries.async_reload(entry.entry_id)

            return self.async_create_entry(title="", data={})

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_GO2RTC_URL,
                    default=self._entry.data.get(CONF_GO2RTC_URL, DEFAULT_GO2RTC_URL),
                ): str,
                vol.Optional(
                    CONF_GO2RTC_USERNAME,
                    default=self._entry.data.get(CONF_GO2RTC_USERNAME, ""),
                ): str,
                vol.Optional(
                    CONF_GO2RTC_PASSWORD,
                    default=self._entry.data.get(CONF_GO2RTC_PASSWORD, ""),
                ): str,
                vol.Required(
                    CONF_GO2RTC_VERSION,
                    default=self._entry.data.get(CONF_GO2RTC_VERSION, DEFAULT_GO2RTC_VERSION),
                ): str,
                vol.Required(
                    CONF_GO2RTC_HOST,
                    default=self._entry.data.get(CONF_GO2RTC_HOST, DEFAULT_GO2RTC_HOST),
                ): str,
                vol.Required(
                    CONF_GO2RTC_RTSP_PORT,
                    default=self._entry.data.get(CONF_GO2RTC_RTSP_PORT, DEFAULT_GO2RTC_RTSP_PORT),
                ): int,
                vol.Required(
                    CONF_GO2RTC_WEBRTC_PORT,
                    default=self._entry.data.get(CONF_GO2RTC_WEBRTC_PORT, DEFAULT_GO2RTC_WEBRTC_PORT),
                ): int,
                vol.Optional(
                    CONF_GO2RTC_CANDIDATES,
                    default=self._entry.data.get(CONF_GO2RTC_CANDIDATES, DEFAULT_GO2RTC_CANDIDATES),
                ): str,
            }
        )
        return self.async_show_form(
            step_id="go2rtc",
            data_schema=schema,
        )


