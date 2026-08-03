"""Coordinator for Hausfunk: polls Pi reachability and stream state."""

import asyncio
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_GO2RTC_CANDIDATES,
    CONF_GO2RTC_PASSWORD,
    CONF_GO2RTC_URL,
    CONF_GO2RTC_USERNAME,
    CONF_GO2RTC_WEBRTC_PORT,
    CONF_PI_GO2RTC_PORT,
    CONF_PI_HOST,
    CONF_RTSP_PORT,
    CONF_STREAM_NAME,
    DEFAULT_GO2RTC_WEBRTC_PORT,
    DEFAULT_PI_GO2RTC_PORT,
    DOMAIN,
)
from .go2rtc.client import Go2rtcClient, Go2rtcError

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)


class HausfunkCoordinator(DataUpdateCoordinator):
    """Polls Pi reachability and go2rtc stream registration."""

    def __init__(self, hass: HomeAssistant, config: dict):
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL
        )
        self.config = config
        self.go2rtc = Go2rtcClient(
            url=config[CONF_GO2RTC_URL],
            username=config.get(CONF_GO2RTC_USERNAME) or None,
            password=config.get(CONF_GO2RTC_PASSWORD) or None,
        )

    @property
    def stream_url(self) -> str:
        """HA go2rtc source URL for the Pi stream.

        Uses a go2rtc-to-go2rtc WebRTC client link (webrtc:ws://.../api/ws)
        instead of plain RTSP, because that is the only way the HA go2rtc
        reliably exposes the Pi's RTSP backchannel to WebRTC clients.
        """
        pi_go2rtc_port = self.config.get(
            CONF_PI_GO2RTC_PORT, DEFAULT_PI_GO2RTC_PORT
        )
        return (
            f"webrtc:ws://{self.config[CONF_PI_HOST]}:{pi_go2rtc_port}/api/ws"
            f"?src={self.config[CONF_STREAM_NAME]}"
        )

    async def register_stream(self, persist: bool = True):
        """Register the stream in go2rtc and persist it to its config."""
        name = self.config[CONF_STREAM_NAME]
        try:
            await self.go2rtc.ensure_stream(name, [self.stream_url])
            if persist:
                await self.go2rtc.persist_stream(
                    name,
                    [self.stream_url],
                    webrtc_port=self.config.get(
                        CONF_GO2RTC_WEBRTC_PORT, DEFAULT_GO2RTC_WEBRTC_PORT
                    ),
                    candidates=self.config.get(CONF_GO2RTC_CANDIDATES),
                )
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
