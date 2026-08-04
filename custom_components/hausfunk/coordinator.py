"""Coordinator for Hausfunk: polls Pi reachability and stream state."""

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_GO2RTC_CANDIDATES,
    CONF_GO2RTC_HOST,
    CONF_GO2RTC_PASSWORD,
    CONF_GO2RTC_URL,
    CONF_GO2RTC_USERNAME,
    CONF_GO2RTC_WEBRTC_PORT,
    CONF_PI_GO2RTC_PORT,
    CONF_PI_HOST,
    CONF_PI_PASSWORD,
    CONF_PI_PORT,
    CONF_PI_USERNAME,
    CONF_RTSP_PORT,
    CONF_STREAM_MODE,
    CONF_STREAM_NAME,
    DEFAULT_GO2RTC_HOST,
    DEFAULT_GO2RTC_WEBRTC_PORT,
    DEFAULT_PI_GO2RTC_PORT,
    DEFAULT_STREAM_MODE,
    DOMAIN,
    STREAM_MODE_BOTH,
    STREAM_MODE_RTSP,
    STREAM_MODE_RTSP_WEBRTC,
    STREAM_MODE_WEBRTC,
)
from .go2rtc.client import Go2rtcClient, Go2rtcError
from .pi.installer import HausfunkInstaller
from .pi.ssh import PiCommandError, PiSSH

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)


class HausfunkCoordinator(DataUpdateCoordinator):
    """Polls Pi reachability and go2rtc stream registration.

    ``host_config`` holds the entry-level go2rtc settings, ``pi_config`` the
    per-device settings. They are merged so both are available via ``config``
    (used by entities).
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        host_config: dict,
        pi_config: dict,
        pi_id: str | None = None,
        subentry_id: str | None = None,
    ):
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL
        )
        self.config_entry = entry
        self.host_config = host_config
        self.pi_config = pi_config
        self.pi_id = pi_id
        self.subentry_id = subentry_id
        self.config = {**host_config, **pi_config}
        self.go2rtc = Go2rtcClient(
            url=host_config[CONF_GO2RTC_URL],
            username=host_config.get(CONF_GO2RTC_USERNAME) or None,
            password=host_config.get(CONF_GO2RTC_PASSWORD) or None,
        )

    async def async_update_setting(self, key: str, value: any):
        """Update a config entry setting and apply the change."""
        # 1. Update the config entry data
        new_data = {**self.config_entry.data, key: value}
        self.hass.config_entries.async_update_entry(
            self.config_entry, data=new_data
        )

        # 2. Update cached configs
        self.config[key] = value
        if key in self.pi_config:
            self.pi_config[key] = value
        if key in self.host_config:
            self.host_config[key] = value

        # 3. Apply the changes
        if key == CONF_STREAM_MODE:
            # Rewrite the Pi's go2rtc config and restart its service
            await self._update_pi_config()
            # Re-register the stream in HA's go2rtc and restart it
            await self.register_stream(persist=True, restart=True)

    async def _update_pi_config(self):
        """Rewrite the Pi's go2rtc config and restart its go2rtc service.

        The Pi config depends on the stream mode (e.g. the WebRTC server
        section for ``webrtc``/``both``), so the config is re-rendered and
        pushed whenever the mode changes. Failures are logged but do not
        abort the mode switch on the HA side.
        """
        ssh = PiSSH(
            self.pi_config[CONF_PI_HOST],
            self.pi_config[CONF_PI_PORT],
            self.pi_config[CONF_PI_USERNAME],
            self.pi_config[CONF_PI_PASSWORD],
        )
        installer = HausfunkInstaller(self.hass, ssh, self.config)
        try:
            await installer.connect_and_update_config()
        except (PiCommandError, OSError) as err:
            _LOGGER.warning(
                "Pi-Konfiguration konnte nicht aktualisiert werden: %s", err
            )


    @property
    def webrtc_candidates(self) -> str | None:
        """WebRTC candidates for the HA go2rtc config.

        Falls nicht konfiguriert, wird automatisch
        ``<go2rtc_host>:<webrtc_port>`` als Kandidat abgeleitet, damit der
        Browser die Medienverbindung zum HA go2rtc aufbauen kann (127.0.0.1
        wird dabei ignoriert, weil von außen nicht erreichbar).
        """
        configured = self.config.get(CONF_GO2RTC_CANDIDATES)
        if configured:
            return configured
        host = self.config.get(CONF_GO2RTC_HOST, DEFAULT_GO2RTC_HOST)
        port = self.config.get(
            CONF_GO2RTC_WEBRTC_PORT, DEFAULT_GO2RTC_WEBRTC_PORT
        )
        if host in ("127.0.0.1", "localhost", "::1"):
            return None
        return f"{host}:{port}"

    @property
    def stream_urls(self) -> list[str]:
        """HA go2rtc source URLs for the Pi stream.

        ``webrtc`` mode uses a go2rtc-to-go2rtc WebRTC client link
        (webrtc:ws://.../api/ws) which reliably exposes the Pi's RTSP
        backchannel to WebRTC clients. ``rtsp`` mode pulls the stream
        directly (backchannel support depends on the Pi go2rtc). ``both``
        registers both sources so go2rtc can fall back to the RTSP pull
        when the WebRTC link is unavailable. ``rtsp_webrtc`` is like
        ``both`` but with RTSP as the primary source.
        """
        pi_host = self.config[CONF_PI_HOST]
        stream_name = self.config[CONF_STREAM_NAME]
        mode = self.config.get(CONF_STREAM_MODE, DEFAULT_STREAM_MODE)
        pi_go2rtc_port = self.config.get(
            CONF_PI_GO2RTC_PORT, DEFAULT_PI_GO2RTC_PORT
        )
        webrtc_url = (
            f"webrtc:ws://{pi_host}:{pi_go2rtc_port}/api/ws"
            f"?src={stream_name}"
        )
        rtsp_url = (
            f"rtsp://{pi_host}:{self.config[CONF_RTSP_PORT]}"
            f"/{stream_name}#backchannel=1"
        )
        if mode == STREAM_MODE_RTSP:
            return [rtsp_url]
        if mode == STREAM_MODE_BOTH:
            return [webrtc_url, rtsp_url]
        if mode == STREAM_MODE_RTSP_WEBRTC:
            return [rtsp_url, webrtc_url]
        return [webrtc_url]

    @property
    def stream_url(self) -> str:
        """Primary HA go2rtc source URL for the Pi stream."""
        return self.stream_urls[0]

    async def register_stream(
        self, persist: bool = True, restart: bool = False
    ):
        """Register the stream in go2rtc and optionally persist + restart.

        ``restart=True`` triggers a go2rtc restart after persisting so the
        new config becomes active without manual interaction.
        """
        name = self.config[CONF_STREAM_NAME]
        urls = self.stream_urls
        try:
            await self.go2rtc.ensure_stream(name, urls)
            if persist:
                await self.go2rtc.persist_stream(
                    name,
                    urls,
                    webrtc_port=self.config.get(
                        CONF_GO2RTC_WEBRTC_PORT, DEFAULT_GO2RTC_WEBRTC_PORT
                    ),
                    candidates=self.webrtc_candidates,
                )
                if restart:
                    await self.go2rtc.restart()
        except Go2rtcError:
            _LOGGER.exception("Stream-Registrierung in go2rtc fehlgeschlagen")
            return False
        return True

    async def remove_stream(self):
        """Remove the stream from go2rtc."""
        try:
            await self.go2rtc.remove_stream(self.config[CONF_STREAM_NAME])
        except Go2rtcError:
            _LOGGER.exception("Stream-Entfernung in go2rtc fehlgeschlagen")
            return False
        return True

    async def restart_go2rtc(self):
        """Restart the HA go2rtc instance."""
        try:
            await self.go2rtc.restart()
        except Go2rtcError:
            _LOGGER.exception("go2rtc-Neustart fehlgeschlagen")
            return False
        return True

    async def _async_update_data(self) -> dict:
        pi_reachable = await self._probe_pi()
        stream_active = False
        if pi_reachable:
            try:
                streams = await self.go2rtc.get_streams()
                stream_active = self.config[CONF_STREAM_NAME] in streams
            except Go2rtcError:
                pass
        return {"pi_reachable": pi_reachable, "stream_active": stream_active}

    async def _probe_pi(self) -> bool:
        try:
            _reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self.config[CONF_PI_HOST], self.config[CONF_RTSP_PORT]
                ),
                timeout=5,
            )
            writer.close()
            await writer.wait_closed()
            return True
        except (OSError, asyncio.TimeoutError):
            return False

    async def async_close(self):
        await self.go2rtc.close()
