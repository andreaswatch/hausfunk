import unittest

import tests.hass_mock

from custom_components.hausfunk.const import (
    DEFAULT_GO2RTC_VERSION,
    DEFAULT_GO2RTC_WEBRTC_PORT,
    DEFAULT_PI_GO2RTC_PORT,
    DEFAULT_RTSP_PORT,
    DEFAULT_STREAM_NAME,
    DOMAIN,
    NAME,
    PLATFORMS,
)


class TestConst(unittest.TestCase):
    def test_domain(self):
        self.assertEqual(DOMAIN, "hausfunk")
        self.assertEqual(NAME, "Hausfunk")

    def test_defaults(self):
        self.assertEqual(DEFAULT_STREAM_NAME, "tuer")
        self.assertEqual(DEFAULT_RTSP_PORT, 8554)
        self.assertTrue(DEFAULT_GO2RTC_VERSION.startswith("v1.9"))
        self.assertEqual(DEFAULT_PI_GO2RTC_PORT, 1984)
        self.assertEqual(DEFAULT_GO2RTC_WEBRTC_PORT, 8555)

    def test_platforms(self):
        self.assertEqual(
            set(PLATFORMS),
            {"binary_sensor", "switch", "camera", "button"},
        )


if __name__ == "__main__":
    unittest.main()
