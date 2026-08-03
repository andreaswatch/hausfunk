import unittest

import tests.hass_mock

from custom_components.hausfunk.coordinator import HausfunkCoordinator
from custom_components.hausfunk.const import (
    CONF_GO2RTC_CANDIDATES,
    CONF_GO2RTC_HOST,
    CONF_GO2RTC_URL,
    CONF_PI_GO2RTC_PORT,
    CONF_PI_HOST,
    CONF_RTSP_PORT,
    CONF_STREAM_MODE,
    CONF_STREAM_NAME,
    DEFAULT_GO2RTC_URL,
    DEFAULT_PI_GO2RTC_PORT,
    STREAM_MODE_RTSP,
    STREAM_MODE_WEBRTC,
)

CONFIG = {
    CONF_PI_HOST: "192.168.178.11",
    CONF_RTSP_PORT: 8554,
    CONF_STREAM_NAME: "tuer",
    CONF_GO2RTC_URL: DEFAULT_GO2RTC_URL,
    CONF_GO2RTC_HOST: "192.168.178.21",
    CONF_GO2RTC_CANDIDATES: "",
}


class TestCoordinator(unittest.TestCase):
    def test_stream_url_webrtc_go2rtc(self):
        coordinator = HausfunkCoordinator(hass=None, config=CONFIG)
        self.assertEqual(
            coordinator.stream_url,
            "webrtc:ws://192.168.178.11:1984/api/ws?src=tuer",
        )

    def test_stream_url_custom_go2rtc_port(self):
        config = dict(CONFIG)
        config[CONF_PI_GO2RTC_PORT] = 1985
        coordinator = HausfunkCoordinator(hass=None, config=config)
        self.assertEqual(
            coordinator.stream_url,
            "webrtc:ws://192.168.178.11:1985/api/ws?src=tuer",
        )

    def test_stream_url_rtsp_mode(self):
        config = dict(CONFIG)
        config[CONF_STREAM_MODE] = STREAM_MODE_RTSP
        coordinator = HausfunkCoordinator(hass=None, config=config)
        self.assertEqual(
            coordinator.stream_url,
            "rtsp://192.168.178.11:8554/tuer#backchannel=1",
        )

    def test_stream_url_webrtc_mode_explicit(self):
        config = dict(CONFIG)
        config[CONF_STREAM_MODE] = STREAM_MODE_WEBRTC
        coordinator = HausfunkCoordinator(hass=None, config=config)
        self.assertEqual(
            coordinator.stream_url,
            "webrtc:ws://192.168.178.11:1984/api/ws?src=tuer",
        )

    def test_default_pi_go2rtc_port(self):
        self.assertEqual(DEFAULT_PI_GO2RTC_PORT, 1984)

    def test_webrtc_candidates_derived_from_host(self):
        coordinator = HausfunkCoordinator(hass=None, config=CONFIG)
        self.assertEqual(coordinator.webrtc_candidates, "192.168.178.21:8555")

    def test_webrtc_candidates_configured_win(self):
        config = dict(CONFIG)
        config[CONF_GO2RTC_CANDIDATES] = (
            "go2rtc-ha.moers.webredirect.org:8555, 192.168.178.21:8555"
        )
        coordinator = HausfunkCoordinator(hass=None, config=config)
        self.assertEqual(
            coordinator.webrtc_candidates,
            "go2rtc-ha.moers.webredirect.org:8555, 192.168.178.21:8555",
        )

    def test_webrtc_candidates_none_for_loopback(self):
        config = dict(CONFIG)
        config[CONF_GO2RTC_HOST] = "127.0.0.1"
        coordinator = HausfunkCoordinator(hass=None, config=config)
        self.assertIsNone(coordinator.webrtc_candidates)


if __name__ == "__main__":
    unittest.main()
