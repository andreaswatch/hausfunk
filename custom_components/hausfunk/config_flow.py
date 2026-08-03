"""Config flow for Hausfunk.

The integration's config entry stores only host-level settings (the HA
go2rtc instance). Each Pi is added as a *subentry* ("pi") via the device
subentry flow, so multiple Pis can share one go2rtc host.
"""

import logging

import voluptuous as vol

from homeassistant.components import network as ha_network
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigSubentryFlow,
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
    PI_SUBENTRY_TYPE,
    STREAM_MODE_RTSP,
    STREAM_MODE_WEBRTC,
)
from .go2rtc.client import Go2rtcClient, Go2rtcError
from .pi.installer import HausfunkInstaller
from .pi.ssh import PiCommandError, PiConnectionError, PiSSH

_LOGGER = logging.getLogger(__name__)

PI_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PI_HOST): str,
        vol.Required(CONF_PI_PORT, default=DEFAULT_SSH_PORT): int,
        vol.Required(CONF_PI_USERNAME, default="pi"): str,
        vol.Required(CONF_PI_PASSWORD): str,
        vol.Optional(CONF_SUDO_PASSWORD, default=""): str,
    }
)

INSTALL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_INSTALL_NOW, default=True): bool,
    }
)

# Device (Pi) settings — shown when adding or editing a Pi subentry.
def _pi_stream_schema(defaults: dict) -> vol.Schema:
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
                CONF_STREAM_MODE,
                default=defaults.get(CONF_STREAM_MODE, DEFAULT_STREAM_MODE),
            ): vol.In([STREAM_MODE_WEBRTC, STREAM_MODE_RTSP]),
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
    """Handle the host-level config flow (HA go2rtc settings only)."""

    VERSION = 2

    @staticmethod
    def async_supports_multiple_entries() -> bool:
        """Only one host entry (all Pis are subentries)."""
        return False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        return HausfunkOptionsFlow(config_entry)

    @staticmethod
    @callback
    def async_get_supported_subentry_types(
        config_entry: ConfigEntry,
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the subentry flow for adding Pi devices."""
        return {PI_SUBENTRY_TYPE: HausfunkPiSubentryFlow}

    async def async_step_user(self, user_input=None):
        """Host-level settings: the HA go2rtc instance."""
        if user_input is not None:
            return self.async_create_entry(
                title="Hausfunk", data=user_input
            )
        schema, detected = await self._detect_go2rtc()
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            description_placeholders={"detected": detected},
        )

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
        except Exception:  # noqa: BLE001 - network helper may be unavailable
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


def _has_pi_subentry(entry) -> bool:
    """True if a Pi subentry already exists (max. one device)."""
    return any(
        s.subentry_type == PI_SUBENTRY_TYPE
        for s in entry.subentries.values()
    )


class HausfunkPiSubentryFlow(ConfigSubentryFlow):
    """Handle adding / editing a Pi device as a subentry."""

    async def async_step_user(self, user_input=None):
        """Add a new Pi: SSH access + stream settings."""
        if _has_pi_subentry(self._get_entry()):
            return self.async_abort(reason="already_configured")
        errors = {}
        if user_input is not None:
            self._data = dict(user_input)
            errors = await self._validate_pi(user_input)
            if not errors:
                return await self.async_step_stream()
        return self.async_show_form(
            step_id="user", data_schema=PI_SCHEMA, errors=errors,
            description_placeholders={"fingerprint": getattr(self, "_fingerprint", "")},
        )

    async def async_step_stream(self, user_input=None):
        """Pi stream/camera settings."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_install()
        defaults = {k: v for k, v in self._data.items()}
        return self.async_show_form(
            step_id="stream", data_schema=_pi_stream_schema(defaults)
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
                title=self._data[CONF_PI_HOST],
                data=self._data,
                unique_id=self._data[CONF_PI_HOST],
            )
        return self.async_show_form(step_id="install", data_schema=INSTALL_SCHEMA)

    async def async_step_reconfigure(self, user_input=None):
        """Edit an existing Pi subentry."""
        subentry = self._get_reconfigure_subentry()
        current = dict(subentry.data)
        if user_input is not None:
            install_now = user_input.pop(CONF_INSTALL_NOW, False)
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                data_updates=user_input,
            )
        defaults = {k: v for k, v in current.items()}
        return self.async_show_form(
            step_id="reconfigure", data_schema=_pi_stream_schema(defaults)
        )

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
        entry = self._get_entry()
        host = dict(entry.data)
        data = {**host, **self._data}
        ssh = PiSSH(
            self._data[CONF_PI_HOST], self._data[CONF_PI_PORT],
            self._data[CONF_PI_USERNAME], self._data[CONF_PI_PASSWORD],
        )
        installer = HausfunkInstaller(self.hass, ssh, data)
        try:
            await installer.install(self._data.get(CONF_SUDO_PASSWORD))
        except PiCommandError as err:
            _LOGGER.error("Pi-Installation fehlgeschlagen: %s", err)
            return {"base": "install_failed"}
        return {}


class HausfunkOptionsFlow(OptionsFlow):
    """Handle host-level options (go2rtc settings)."""

    def __init__(self, entry: ConfigEntry):
        self._entry = entry

    async def async_step_init(self, user_input=None):
        current = {**self._entry.data, **self._entry.options}
        schema = vol.Schema(
            {
                vol.Required(CONF_GO2RTC_URL, default=current.get(CONF_GO2RTC_URL, DEFAULT_GO2RTC_URL)): str,
                vol.Optional(CONF_GO2RTC_USERNAME, default=current.get(CONF_GO2RTC_USERNAME, "")): str,
                vol.Optional(CONF_GO2RTC_PASSWORD, default=current.get(CONF_GO2RTC_PASSWORD, "")): str,
                vol.Required(CONF_GO2RTC_VERSION, default=current.get(CONF_GO2RTC_VERSION, DEFAULT_GO2RTC_VERSION)): str,
                vol.Required(CONF_GO2RTC_HOST, default=current.get(CONF_GO2RTC_HOST, DEFAULT_GO2RTC_HOST)): str,
                vol.Required(CONF_GO2RTC_RTSP_PORT, default=current.get(CONF_GO2RTC_RTSP_PORT, DEFAULT_GO2RTC_RTSP_PORT)): int,
                vol.Required(CONF_GO2RTC_WEBRTC_PORT, default=current.get(CONF_GO2RTC_WEBRTC_PORT, DEFAULT_GO2RTC_WEBRTC_PORT)): int,
                vol.Optional(CONF_GO2RTC_CANDIDATES, default=current.get(CONF_GO2RTC_CANDIDATES, DEFAULT_GO2RTC_CANDIDATES)): str,
            }
        )
        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                self._entry, options=user_input
            )
            await self.hass.config_entries.async_reload(self._entry.entry_id)
            return self.async_create_entry(data={})
        return self.async_show_form(step_id="init", data_schema=schema)
