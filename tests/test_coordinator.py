import unittest

import tests.hass_mock

from custom_components.hausfunk.coordinator import HausfunkCoordinator
from custom_components.hausfunk.const import (
    CONF_GO2RTC_URL,
    CONF_PI_GO2RTC_PORT,
    CONF_PI_HOST,
    CONF_RTSP_PORT,
    CONF_STREAM_NAME,
    DEFAULT_GO2RTC_URL,
    DEFAULT_PI_GO2RTC_PORT,
)

CONFIG = {
    CONF_PI_HOST: "192.168.178.11",
    CONF_RTSP_PORT: 8554,
    CONF_STREAM_NAME: "tuer",
    CONF_GO2RTC_URL: DEFAULT_GO2RTC_URL,
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

    def test_default_pi_go2rtc_port(self):
        self.assertEqual(DEFAULT_PI_GO2RTC_PORT, 1984)


if __name__ == "__main__":
    unittest.main()
