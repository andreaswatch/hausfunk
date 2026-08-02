import unittest

import tests.hass_mock

from custom_components.hausfunk.go2rtc.client import _encode_src


class TestGo2rtcUrlEncoding(unittest.TestCase):
    def test_fragment_is_encoded(self):
        url = "rtsp://192.168.178.11:8554/tuer#backchannel=1"
        encoded = _encode_src(url)
        self.assertIn("%23backchannel=1", encoded)
        self.assertNotIn("#", encoded)

    def test_scheme_and_path_preserved(self):
        url = "rtsp://192.168.178.11:8554/tuer#backchannel=1"
        encoded = _encode_src(url)
        self.assertTrue(encoded.startswith("rtsp://192.168.178.11:8554/tuer"))
        self.assertIn("%23backchannel", encoded)

    def test_query_params(self):
        url = "rtsp://u:p@192.168.178.11/stream?proto=Onvif&channel=1#backchannel=1"
        encoded = _encode_src(url)
        self.assertNotIn("&", encoded)  # raw & must not break the query string
        self.assertIn("%26", encoded)


if __name__ == "__main__":
    unittest.main()
