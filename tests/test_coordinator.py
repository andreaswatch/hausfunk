import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import tests.hass_mock

from custom_components.hausfunk.coordinator import HausfunkCoordinator
from custom_components.hausfunk.const import (
    CONF_GO2RTC_CANDIDATES,
    CONF_GO2RTC_HOST,
    CONF_GO2RTC_URL,
    CONF_PI_GO2RTC_PORT,
    CONF_PI_HOST,
    CONF_PI_PASSWORD,
    CONF_PI_PORT,
    CONF_PI_USERNAME,
    CONF_RTSP_PORT,
    CONF_STREAM_MODE,
    CONF_STREAM_NAME,
    DEFAULT_GO2RTC_URL,
    DEFAULT_PI_GO2RTC_PORT,
    STREAM_MODE_BOTH,
    STREAM_MODE_RTSP,
    STREAM_MODE_RTSP_WEBRTC,
    STREAM_MODE_WEBRTC,
)

HOST_CONFIG = {
    CONF_GO2RTC_URL: DEFAULT_GO2RTC_URL,
    CONF_GO2RTC_HOST: "192.168.178.21",
    CONF_GO2RTC_CANDIDATES: "",
}

PI_CONFIG = {
    CONF_PI_HOST: "192.168.178.11",
    CONF_PI_PORT: 22,
    CONF_PI_USERNAME: "pi",
    CONF_PI_PASSWORD: "secret",
    CONF_RTSP_PORT: 8554,
    CONF_STREAM_NAME: "tuer",
}


class TestCoordinator(unittest.TestCase):
    def _coordinator(self, **pi_overrides):
        pi = dict(PI_CONFIG)
        pi.update(pi_overrides)
        entry = MagicMock()
        entry.data = {**HOST_CONFIG, **pi}
        return HausfunkCoordinator(
            hass=None,
            entry=entry,
            host_config=HOST_CONFIG,
            pi_config=pi,
            pi_id="192.168.178.11",
        )

    def test_stream_url_rtsp_default(self):
        self.assertEqual(
            self._coordinator().stream_url,
            "rtsp://192.168.178.11:8554/tuer#backchannel=1",
        )

    def test_stream_url_custom_go2rtc_port_rtsp(self):
        self.assertEqual(
            self._coordinator(**{CONF_PI_GO2RTC_PORT: 1985}).stream_url,
            "rtsp://192.168.178.11:8554/tuer#backchannel=1",
        )

    def test_stream_url_rtsp_mode(self):
        self.assertEqual(
            self._coordinator(**{CONF_STREAM_MODE: STREAM_MODE_RTSP}).stream_url,
            "rtsp://192.168.178.11:8554/tuer#backchannel=1",
        )

    def test_stream_url_webrtc_mode_explicit(self):
        self.assertEqual(
            self._coordinator(**{CONF_STREAM_MODE: STREAM_MODE_WEBRTC}).stream_url,
            "webrtc:ws://192.168.178.11:1984/api/ws?src=tuer",
        )

    def test_stream_urls_both_mode(self):
        self.assertEqual(
            self._coordinator(**{CONF_STREAM_MODE: STREAM_MODE_BOTH}).stream_urls,
            [
                "webrtc:ws://192.168.178.11:1984/api/ws?src=tuer",
                "rtsp://192.168.178.11:8554/tuer#backchannel=1",
            ],
        )

    def test_stream_url_primary_in_both_mode(self):
        self.assertEqual(
            self._coordinator(**{CONF_STREAM_MODE: STREAM_MODE_BOTH}).stream_url,
            "webrtc:ws://192.168.178.11:1984/api/ws?src=tuer",
        )

    def test_stream_urls_rtsp_webrtc_mode(self):
        self.assertEqual(
            self._coordinator(**{CONF_STREAM_MODE: STREAM_MODE_RTSP_WEBRTC}).stream_urls,
            [
                "rtsp://192.168.178.11:8554/tuer#backchannel=1",
                "webrtc:ws://192.168.178.11:1984/api/ws?src=tuer",
            ],
        )

    def test_stream_url_primary_in_rtsp_webrtc_mode(self):
        self.assertEqual(
            self._coordinator(**{CONF_STREAM_MODE: STREAM_MODE_RTSP_WEBRTC}).stream_url,
            "rtsp://192.168.178.11:8554/tuer#backchannel=1",
        )

    def test_default_pi_go2rtc_port(self):
        self.assertEqual(DEFAULT_PI_GO2RTC_PORT, 1984)

    def test_webrtc_candidates_derived_from_host(self):
        self.assertEqual(
            self._coordinator().webrtc_candidates, "192.168.178.21:8555"
        )

    def test_webrtc_candidates_configured_win(self):
        host = dict(HOST_CONFIG)
        host[CONF_GO2RTC_CANDIDATES] = (
            "go2rtc-ha.moers.webredirect.org:8555, 192.168.178.21:8555"
        )
        entry = MagicMock()
        entry.data = {**host, **PI_CONFIG}
        coordinator = HausfunkCoordinator(
            hass=None, entry=entry, host_config=host, pi_config=dict(PI_CONFIG), pi_id="192.168.178.11"
        )
        self.assertEqual(
            coordinator.webrtc_candidates,
            "go2rtc-ha.moers.webredirect.org:8555, 192.168.178.21:8555",
        )

    def test_webrtc_candidates_none_for_loopback(self):
        host = dict(HOST_CONFIG)
        host[CONF_GO2RTC_HOST] = "127.0.0.1"
        entry = MagicMock()
        entry.data = {**host, **PI_CONFIG}
        coordinator = HausfunkCoordinator(
            hass=None, entry=entry, host_config=host, pi_config=dict(PI_CONFIG), pi_id="192.168.178.11"
        )
        self.assertIsNone(coordinator.webrtc_candidates)


class TestCoordinatorPiConfig(unittest.IsolatedAsyncioTestCase):
    async def test_update_pi_config_uses_installer(self):
        entry = MagicMock()
        entry.data = {**HOST_CONFIG, **PI_CONFIG}
        coordinator = HausfunkCoordinator(
            hass=MagicMock(),
            entry=entry,
            host_config=dict(HOST_CONFIG),
            pi_config=dict(PI_CONFIG),
            pi_id="192.168.178.11",
        )
        with patch("custom_components.hausfunk.coordinator.PiSSH") as mock_ssh, patch(
            "custom_components.hausfunk.coordinator.HausfunkInstaller"
        ) as mock_installer:
            installer = mock_installer.return_value
            installer.connect_and_update_config = AsyncMock()

            await coordinator._update_pi_config()

            mock_ssh.assert_called_once_with(
                "192.168.178.11", 22, "pi", "secret"
            )
            mock_installer.assert_called_once_with(
                coordinator.hass, mock_ssh.return_value, coordinator.config
            )
            installer.connect_and_update_config.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
