"""Config flow for Hausfunk."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback

from .const import (
    CONF_AUDIO_GAIN,
    CONF_FPS,
    CONF_GO2RTC_HOST,
    CONF_GO2RTC_PASSWORD,
    CONF_GO2RTC_RTSP_PORT,
    CONF_GO2RTC_URL,
    CONF_GO2RTC_USERNAME,
    CONF_GO2RTC_VERSION,
    CONF_HEIGHT,
    CONF_INSTALL_NOW,
    CONF_PI_GO2RTC_PORT,
    CONF_PI_HOST,
    CONF_PI_PASSWORD,
    CONF_PI_PORT,
    CONF_PI_USERNAME,
    CONF_RTSP_PORT,
    CONF_STREAM_NAME,
    CONF_SUDO_PASSWORD,
    CONF_WIDTH,
    DEFAULT_AUDIO_GAIN,
    DEFAULT_FPS,
    DEFAULT_GO2RTC_HOST,
    DEFAULT_GO2RTC_RTSP_PORT,
    DEFAULT_GO2RTC_URL,
    DEFAULT_GO2RTC_VERSION,
    DEFAULT_HEIGHT,
    DEFAULT_PI_GO2RTC_PORT,
    DEFAULT_RTSP_PORT,
    DEFAULT_SSH_PORT,
    DEFAULT_STREAM_NAME,
    DEFAULT_WIDTH,
    DOMAIN,
)
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

STREAM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_STREAM_NAME, default=DEFAULT_STREAM_NAME): str,
        vol.Required(CONF_RTSP_PORT, default=DEFAULT_RTSP_PORT): int,
        vol.Required(
            CONF_PI_GO2RTC_PORT, default=DEFAULT_PI_GO2RTC_PORT
        ): int,
        vol.Required(CONF_WIDTH, default=DEFAULT_WIDTH): int,
        vol.Required(CONF_HEIGHT, default=DEFAULT_HEIGHT): int,
        vol.Required(CONF_FPS, default=DEFAULT_FPS): int,
        vol.Required(CONF_AUDIO_GAIN, default=DEFAULT_AUDIO_GAIN): vol.Coerce(float),
    }
)

GO2RTC_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_GO2RTC_URL, default=DEFAULT_GO2RTC_URL): str,
        vol.Optional(CONF_GO2RTC_USERNAME, default=""): str,
        vol.Optional(CONF_GO2RTC_PASSWORD, default=""): str,
        vol.Required(CONF_GO2RTC_VERSION, default=DEFAULT_GO2RTC_VERSION): str,
        vol.Required(CONF_GO2RTC_HOST, default=DEFAULT_GO2RTC_HOST): str,
        vol.Required(CONF_GO2RTC_RTSP_PORT, default=DEFAULT_GO2RTC_RTSP_PORT): int,
    }
)

INSTALL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_INSTALL_NOW, default=True): bool,
    }
)


def _all_options(entry: ConfigEntry) -> dict:
    return {**entry.data, **entry.options}


class HausfunkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hausfunk."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
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
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_go2rtc()
        return self.async_show_form(step_id="stream", data_schema=STREAM_SCHEMA)

    async def async_step_go2rtc(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_install()
        return self.async_show_form(step_id="go2rtc", data_schema=GO2RTC_SCHEMA)

    async def async_step_install(self, user_input=None):
        if user_input is not None:
            self._install_now = user_input.get(CONF_INSTALL_NOW, True)
            if not self._install_now:
                return self.async_create_entry(title="Hausfunk Pi", data=self._data)
            errors = await self._do_install()
            if errors:
                return self.async_show_form(
                    step_id="install", data_schema=INSTALL_SCHEMA, errors=errors
                )
            return self.async_create_entry(title="Hausfunk Pi", data=self._data)
        return self.async_show_form(step_id="install", data_schema=INSTALL_SCHEMA)

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
        installer = HausfunkInstaller(self.hass, ssh, self._data)
        try:
            await installer.install(self._data.get(CONF_SUDO_PASSWORD))
        except PiCommandError as err:
            _LOGGER.error("Pi-Installation fehlgeschlagen: %s", err)
            return {"base": "install_failed"}
        return {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return HausfunkOptionsFlow(config_entry)


class HausfunkOptionsFlow(OptionsFlow):
    """Handle Hausfunk options."""

    def __init__(self, entry: ConfigEntry):
        self._entry = entry

    async def async_step_init(self, user_input=None):
        errors = {}
        current = _all_options(self._entry)
        schema = vol.Schema(
            {
                vol.Required(CONF_PI_HOST, default=current.get(CONF_PI_HOST)): str,
                vol.Required(CONF_PI_PORT, default=current.get(CONF_PI_PORT, DEFAULT_SSH_PORT)): int,
                vol.Required(CONF_PI_USERNAME, default=current.get(CONF_PI_USERNAME)): str,
                vol.Required(CONF_PI_PASSWORD, default=current.get(CONF_PI_PASSWORD, "")): str,
                vol.Optional(CONF_SUDO_PASSWORD, default=current.get(CONF_SUDO_PASSWORD, "")): str,
                vol.Required(CONF_STREAM_NAME, default=current.get(CONF_STREAM_NAME, DEFAULT_STREAM_NAME)): str,
                vol.Required(CONF_RTSP_PORT, default=current.get(CONF_RTSP_PORT, DEFAULT_RTSP_PORT)): int,
                vol.Required(CONF_PI_GO2RTC_PORT, default=current.get(CONF_PI_GO2RTC_PORT, DEFAULT_PI_GO2RTC_PORT)): int,
                vol.Required(CONF_WIDTH, default=current.get(CONF_WIDTH, DEFAULT_WIDTH)): int,
                vol.Required(CONF_HEIGHT, default=current.get(CONF_HEIGHT, DEFAULT_HEIGHT)): int,
                vol.Required(CONF_FPS, default=current.get(CONF_FPS, DEFAULT_FPS)): int,
                vol.Required(CONF_AUDIO_GAIN, default=current.get(CONF_AUDIO_GAIN, DEFAULT_AUDIO_GAIN)): vol.Coerce(float),
                vol.Required(CONF_GO2RTC_URL, default=current.get(CONF_GO2RTC_URL, DEFAULT_GO2RTC_URL)): str,
                vol.Optional(CONF_GO2RTC_USERNAME, default=current.get(CONF_GO2RTC_USERNAME, "")): str,
                vol.Optional(CONF_GO2RTC_PASSWORD, default=current.get(CONF_GO2RTC_PASSWORD, "")): str,
                vol.Required(CONF_GO2RTC_VERSION, default=current.get(CONF_GO2RTC_VERSION, DEFAULT_GO2RTC_VERSION)): str,
                vol.Required(CONF_GO2RTC_HOST, default=current.get(CONF_GO2RTC_HOST, DEFAULT_GO2RTC_HOST)): str,
                vol.Required(CONF_GO2RTC_RTSP_PORT, default=current.get(CONF_GO2RTC_RTSP_PORT, DEFAULT_GO2RTC_RTSP_PORT)): int,
                vol.Required(CONF_INSTALL_NOW, default=False): bool,
            }
        )
        if user_input is not None:
            install_now = user_input.pop(CONF_INSTALL_NOW, False)
            self.hass.config_entries.async_update_entry(
                self._entry, options=user_input
            )
            if install_now:
                errors = await self._do_install(dict(user_input))
                if errors:
                    return self.async_show_form(
                        step_id="init", data_schema=schema, errors=errors
                    )
            await self.hass.config_entries.async_reload(self._entry.entry_id)
            return self.async_create_entry(data={})
        return self.async_show_form(step_id="init", data_schema=schema)

    async def _do_install(self, data: dict) -> dict:
        ssh = PiSSH(
            data[CONF_PI_HOST], data[CONF_PI_PORT],
            data[CONF_PI_USERNAME], data[CONF_PI_PASSWORD],
        )
        installer = HausfunkInstaller(self.hass, ssh, data)
        try:
            await installer.install(data.get(CONF_SUDO_PASSWORD))
        except PiCommandError as err:
            _LOGGER.error("Pi-Installation fehlgeschlagen: %s", err)
            return {"base": "install_failed"}
        return {}
