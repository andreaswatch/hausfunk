"""Config flow for Hausfunk."""

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


def _go2rtc_options_schema(defaults: dict) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_GO2RTC_URL, default=defaults.get(CONF_GO2RTC_URL, DEFAULT_GO2RTC_URL)
            ): str,
            vol.Optional(
                CONF_GO2RTC_USERNAME, default=defaults.get(CONF_GO2RTC_USERNAME, "")
            ): str,
            vol.Optional(
                CONF_GO2RTC_PASSWORD, default=defaults.get(CONF_GO2RTC_PASSWORD, "")
            ): str,
            vol.Required(
                CONF_GO2RTC_VERSION,
                default=defaults.get(CONF_GO2RTC_VERSION, DEFAULT_GO2RTC_VERSION),
            ): str,
            vol.Required(
                CONF_GO2RTC_HOST, default=defaults.get(CONF_GO2RTC_HOST, DEFAULT_GO2RTC_HOST)
            ): str,
            vol.Required(
                CONF_GO2RTC_RTSP_PORT,
                default=defaults.get(CONF_GO2RTC_RTSP_PORT, DEFAULT_GO2RTC_RTSP_PORT),
            ): int,
            vol.Required(
                CONF_GO2RTC_WEBRTC_PORT,
                default=defaults.get(CONF_GO2RTC_WEBRTC_PORT, DEFAULT_GO2RTC_WEBRTC_PORT),
            ): int,
            vol.Optional(
                CONF_GO2RTC_CANDIDATES,
                default=defaults.get(CONF_GO2RTC_CANDIDATES, DEFAULT_GO2RTC_CANDIDATES),
            ): str,
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
    """Handle the config flow for Hausfunk.

    'Gerät hinzufügen' in the HA UI always starts this flow, creating a new
    'Hausfunk Sprechanlage' hub entry with go2rtc settings.

    Pi devices are added via HausfunkPiSubentryFlow, which is triggered by the
    'Pi hinzufügen' button on the hub device page.
    """

    VERSION = 1

    # SUBENTRY_FLOWS is assigned at module level after HausfunkPiSubentryFlow is defined
    SUBENTRY_FLOWS: dict = {}

    def __init__(self) -> None:
        """Initialize."""
        self._data = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        return HausfunkOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Create a new Hausfunk Sprechanlage (go2rtc hub config)."""
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

        schema = _go2rtc_options_schema(defaults)
        return schema, status


class HausfunkPiSubentryFlow(ConfigSubentryFlow):
    """Flow to add a Hausfunk Pi as a subentry to a Hausfunk Sprechanlage hub.

    Triggered by the 'Pi hinzufügen' button on the hub device page in HA.
    """

    def __init__(self) -> None:
        """Initialize."""
        self._data = {}
        self._fingerprint: str = ""

    async def async_step_user(self, user_input=None):
        """SSH credentials and stream details for the Pi."""
        errors = {}
        if user_input is not None:
            errors = await self._validate_pi(user_input)
            if not errors:
                self._data.update(user_input)
                self._data.setdefault(CONF_STREAM_MODE, DEFAULT_STREAM_MODE)
                return await self.async_step_install()
        return self.async_show_form(
            step_id="user",
            data_schema=PI_SCHEMA,
            errors=errors,
            description_placeholders={
                "fingerprint": self._fingerprint,
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
        """Install go2rtc on the Pi using the parent hub entry's go2rtc config."""
        ssh = PiSSH(
            self._data[CONF_PI_HOST], self._data[CONF_PI_PORT],
            self._data[CONF_PI_USERNAME], self._data[CONF_PI_PASSWORD],
        )
        # Merge go2rtc config from parent hub entry
        parent_entry = self.hass.config_entries.async_get_entry(self.config_entry_id)
        merged_config = {**(parent_entry.data if parent_entry else {}), **self._data}
        installer = HausfunkInstaller(self.hass, ssh, merged_config)
        try:
            await installer.install(self._data.get(CONF_SUDO_PASSWORD))
        except PiCommandError as err:
            _LOGGER.error("Pi-Installation failed: %s", err)
            return {"base": "install_failed"}
        return {}


class HausfunkOptionsFlow(OptionsFlow):
    """Handle options for a Hausfunk Sprechanlage hub entry (go2rtc settings)."""

    def __init__(self, entry: ConfigEntry):
        self._entry = entry

    async def async_step_init(self, user_input=None):
        """go2rtc settings for this hub entry."""
        if user_input is not None:
            new_data = {**self._entry.data, **user_input}
            self.hass.config_entries.async_update_entry(self._entry, data=new_data)
            # Reload this entry so all its Pi subentries pick up the new go2rtc config
            await self.hass.config_entries.async_reload(self._entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=_go2rtc_options_schema(self._entry.data),
        )


# Forward reference: HausfunkPiSubentryFlow is referenced in HausfunkConfigFlow.SUBENTRY_FLOWS
# but defined after. Patch the reference now.
HausfunkConfigFlow.SUBENTRY_FLOWS = {PI_SUBENTRY_TYPE: HausfunkPiSubentryFlow}
