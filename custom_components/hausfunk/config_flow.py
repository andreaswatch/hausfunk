"""Config flow for Hausfunk.

Mirrors the Landroid Cloud pattern: one config entry is a hub holding the
host-level go2rtc settings. Pi devices are stored in entry options and their
entities create the device entries automatically via ``device_info``
(identifiers) — exactly like Landroid Cloud does. No subentries.
"""

import logging

import voluptuous as vol

from homeassistant.components import network as ha_network
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
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
    PIS,
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

    VERSION = 1

    @staticmethod
    def async_supports_multiple_entries() -> bool:
        """Only one hub entry (all Pis are devices under it)."""
        return False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        return HausfunkOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Host-level settings: the HA go2rtc instance."""
        if user_input is not None:
            return self.async_create_entry(
                title="Hausfunk", data=user_input, options={PIS: {}}
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


class HausfunkOptionsFlow(OptionsFlow):
    """Handle host options (go2rtc) and Pi device management.

    Like Landroid Cloud, the options flow is a menu: go2rtc settings and
    manage devices. Pi devices live in entry.options[PIS]; their entities
    create the device entries automatically.
    """

    def __init__(self, entry: ConfigEntry):
        self._entry = entry
        self._data: dict = {}

    def _pis(self) -> dict:
        return dict(self._entry.options.get(PIS, {}))

    def _save(self, options: dict):
        self.hass.config_entries.async_update_entry(self._entry, options=options)

    async def async_step_init(self, user_input=None):
        """Menu: go2rtc settings or manage devices."""
        if user_input is not None:
            choice = user_input["next_step"]
            if choice == "host":
                return await self.async_step_host()
            if choice == "add_pi":
                return await self.async_step_add_pi()
            if choice == "remove_pi":
                return await self.async_step_remove_pi()
        schema = vol.Schema(
            {
                vol.Required("next_step"): vol.In(
                    ["host", "add_pi", "remove_pi"]
                ),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={
                "pi_count": str(len(self._pis())),
                "pids": ", ".join(self._pis()) or "-",
            },
        )

    async def async_step_host(self, user_input=None):
        """Edit host-level go2rtc settings."""
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
                self._entry, data=user_input
            )
            await self.hass.config_entries.async_reload(self._entry.entry_id)
            return self.async_create_entry(data={})
        return self.async_show_form(step_id="host", data_schema=schema)

    async def async_step_add_pi(self, user_input=None):
        """Add a new Pi device."""
        errors = {}
        if user_input is not None:
            host = user_input[CONF_PI_HOST]
            if host in self._pis():
                errors[CONF_PI_HOST] = "already_exists"
            else:
                self._data = dict(user_input)
                errors = await self._validate_pi(user_input)
                if not errors:
                    return await self.async_step_stream()
        return self.async_show_form(
            step_id="add_pi", data_schema=PI_SCHEMA, errors=errors
        )

    async def async_step_stream(self, user_input=None):
        """Pi stream/camera settings."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_install()
        return self.async_show_form(
            step_id="stream", data_schema=_pi_stream_schema({})
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
            pis = self._pis()
            pis[self._data[CONF_PI_HOST]] = dict(self._data)
            self._save({**self._entry.options, PIS: pis})
            await self.hass.config_entries.async_reload(self._entry.entry_id)
            return self.async_create_entry(data={})
        return self.async_show_form(step_id="install", data_schema=INSTALL_SCHEMA)

    async def async_step_remove_pi(self, user_input=None):
        """Remove a Pi device."""
        pis = self._pis()
        if not pis:
            return self.async_abort(reason="no_pis")
        schema = vol.Schema(
            {
                vol.Required(CONF_PI_HOST): vol.In(list(pis)),
            }
        )
        if user_input is not None:
            host = user_input[CONF_PI_HOST]
            pis.pop(host, None)
            self._save({**self._entry.options, PIS: pis})
            await self.hass.config_entries.async_reload(self._entry.entry_id)
            return self.async_create_entry(data={})
        return self.async_show_form(step_id="remove_pi", data_schema=schema)

    async def _validate_pi(self, data: dict) -> dict:
        ssh = PiSSH(
            data[CONF_PI_HOST], data[CONF_PI_PORT],
            data[CONF_PI_USERNAME], data[CONF_PI_PASSWORD],
        )
        try:
            await ssh.connect()
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
        host = dict(self._entry.data)
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
