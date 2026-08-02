import unittest

import tests.hass_mock

from custom_components.hausfunk.coordinator import HausfunkCoordinator
from custom_components.hausfunk.const import (
    CONF_GO2RTC_URL,
    CONF_PI_HOST,
    CONF_RTSP_PORT,
    CONF_STREAM_NAME,
    DEFAULT_GO2RTC_URL,
)

CONFIG = {
    CONF_PI_HOST: "192.168.178.11",
    CONF_RTSP_PORT: 8554,
    CONF_STREAM_NAME: "tuer",
    CONF_GO2RTC_URL: DEFAULT_GO2RTC_URL,
}


class TestCoordinator(unittest.TestCase):
    def test_stream_url(self):
        coordinator = HausfunkCoordinator(hass=None, config=CONFIG)
        self.assertEqual(
            coordinator.stream_url,
            "rtsp://192.168.178.11:8554/tuer#backchannel=1",
        )


if __name__ == "__main__":
    unittest.main()
